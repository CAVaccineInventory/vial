from auth0login.auth0_utils import decode_and_verify_jwt
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from pydantic import BaseModel, validator, ValidationError, Field
from typing import List, Optional
from core.models import AppointmentTag, AvailabilityTag, Location, Report, Reporter
from core.import_utils import derive_appointment_tag, resolve_availability_tags
import json


class ReportValidator(BaseModel):
    location: str = Field(alias="Location")
    appointment_details: Optional[str] = Field(
        alias="Appointment scheduling instructions"
    )
    appointments_by_phone: Optional[bool] = Field(alias="Appointments by phone?")
    availability: List[str] = Field(alias="Availability")
    public_notes: Optional[str] = Field(alias="Notes")
    internal_notes: Optional[str] = Field(alias="Internal Notes")

    @validator("location")
    def location_must_exist(cls, v):
        try:
            return Location.objects.get(public_id=v)
        except Location.DoesNotExist:
            raise ValueError("Location '{}' does not exist".format(v))


@csrf_exempt
def submit_report(request):
    # The ?test=1 version accepts &fake_user=external_id
    reporter = None
    user_info = {}
    if bool(request.GET.get("test")) and request.GET.get("fake_user"):
        reporter = Reporter.objects.get_or_create(
            external_id="auth0:{}".format(request.GET["fake_user"]),
        )[0]
        user_info = {"fake": reporter.external_id}
    else:
        authorization = request.META.get("HTTP_AUTHORIZATION") or ""
        if not authorization.startswith("Bearer "):
            return JsonResponse(
                {"error": "Authorization header must start with 'Bearer'"}
            )
        # Check JWT token is valid
        jwt_id_token = authorization.split("Bearer ")[1]
        try:
            jwt_payload = decode_and_verify_jwt(jwt_id_token)
        except Exception as e:
            return JsonResponse({"error": "Could not decode JWT", "details": str(e)})
        reporter = Reporter.objects.update_or_create(
            external_id="auth0:{}".format(jwt_payload["sub"]),
            defaults={
                "name": jwt_payload["name"],
                "auth0_role_name": ", ".join(
                    sorted(jwt_payload.get("https://help.vaccinateca.com/roles", []))
                ),
            },
        )[0]
        user_info = jwt_payload

    try:
        post_data = json.loads(request.body.decode("utf-8"))
    except ValueError as e:
        return JsonResponse({"error": str(e), "user": user_info})
    try:
        report_data = ReportValidator(**post_data).dict()
    except ValidationError as e:
        return JsonResponse({"error": e.errors(), "user": user_info})
    # Now we add the report
    appointment_tag_string, appointment_details = derive_appointment_tag(
        report_data["appointments_by_phone"], report_data["appointment_details"]
    )
    availability_tags = resolve_availability_tags(report_data["availability"])
    report = Report.objects.create(
        is_test_data=bool(request.GET.get("test")),
        location=report_data["location"],
        # Currently hard-coded to caller app:
        report_source="ca",
        appointment_tag=AppointmentTag.objects.get(slug=appointment_tag_string),
        appointment_details=appointment_details,
        public_notes=report_data["public_notes"],
        internal_notes=report_data["internal_notes"],
        reported_by=reporter,
    )
    for tag_model in availability_tags:
        report.availability_tags.add(tag_model)

    # Refresh Report from DB to get .public_id
    report.refresh_from_db()

    return JsonResponse(
        {
            "admin_url": "/admin/core/report/{}/change/".format(report.pk),
            "created": [report.public_id],
            "appointment_tag_string": appointment_tag_string,
            "appointment_details": appointment_details,
            "availability_tags": [str(a) for a in availability_tags],
            "report": str(report),
            "user_info": user_info,
        }
    )


def submit_report_debug(request):
    return render(
        request,
        "api/submit_report_debug.html",
        {"jwt": request.session["jwt"] if "jwt" in request.session else ""},
    )
