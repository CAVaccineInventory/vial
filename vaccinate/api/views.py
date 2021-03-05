from datetime import datetime
from uuid import UUID

from django.views.decorators.http import require_http_methods

from auth0login.auth0_utils import decode_and_verify_jwt
from dateutil import parser
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from pydantic import BaseModel, validator, ValidationError, Field
from typing import List, Optional

from config.settings import SCRAPER_API_KEY
from core.models import (
    AppointmentTag,
    AvailabilityTag,
    Location,
    Report,
    Reporter,
    FeedProvider,
    FeedUpdate,
    AppointmentAvailabilityReport,
    AppointmentAvailabilityWindow,
    LocationFeedConcordance,
)
from core.import_utils import derive_appointment_tag, resolve_availability_tags
from .utils import log_api_requests
import json
import pytz


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
@log_api_requests
def submit_report(request, on_request_logged):
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
                {"error": "Authorization header must start with 'Bearer'"}, status=403
            )
        # Check JWT token is valid
        jwt_id_token = authorization.split("Bearer ")[1]
        try:
            jwt_payload = decode_and_verify_jwt(jwt_id_token, try_fallback=True)
        except Exception as e:
            return JsonResponse(
                {"error": "Could not decode JWT", "details": str(e)}, status=403
            )
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
        return JsonResponse({"error": str(e), "user": user_info}, status=400)
    try:
        report_data = ReportValidator(**post_data).dict()
    except ValidationError as e:
        return JsonResponse({"error": e.errors(), "user": user_info}, status=400)
    # Now we add the report
    appointment_tag_string, appointment_details = derive_appointment_tag(
        report_data["appointments_by_phone"], report_data["appointment_details"]
    )
    availability_tags = resolve_availability_tags(report_data["availability"])
    kwargs = dict(
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
    if bool(request.GET.get("test")) and request.GET.get("fake_timestamp"):
        fake_timestamp = parser.parse(request.GET["fake_timestamp"])
        if fake_timestamp.tzinfo is None:
            # Assume this is UTC
            fake_timestamp = pytz.UTC.localize(fake_timestamp)
        kwargs["created_at"] = fake_timestamp

    report = Report.objects.create(**kwargs)
    for tag_model in availability_tags:
        report.availability_tags.add(tag_model)

    # Refresh Report from DB to get .public_id
    report.refresh_from_db()

    def log_created_report(log):
        log.created_report = report
        log.save()

    on_request_logged(log_created_report)

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


class FeedUpdateValidator(BaseModel):
    uuid: UUID = Field()
    feed_provider: str = Field()
    github_url: str = Field()

    @validator("feed_provider")
    def feed_provider_must_exist(cls, v):
        try:
            return FeedProvider.objects.get(slug=v)
        except FeedProvider.DoesNotExist:
            raise ValueError("Feed provider '{}' does not exist".format(v))


class AppointmentAvailabilityWindowValidator(BaseModel):
    starts_at: datetime = Field()
    ends_at: datetime = Field()
    slots: int = Field()
    additional_restrictions: List[str] = Field()

    @validator("additional_restrictions")
    def additional_restrictions_are_availability_tags(cls, ls):
        tags = []
        for tag in ls:
            try:
                tags.append(AvailabilityTag.objects.get(slug=tag))
            except AvailabilityTag.DoesNotExist:
                raise ValueError(
                    "Availability tag with slug '{}' does not exist".format(tag)
                )
        return tags


class AppointmentAvailabilityReportValidator(BaseModel):
    location: str = Field()
    feed_json: Optional[str] = Field()
    feed_update: FeedUpdateValidator = Field()
    availability_windows: List[AppointmentAvailabilityWindowValidator] = Field()

    appointment_details: Optional[str] = Field(
        alias="Appointment scheduling instructions"
    )


@csrf_exempt
@log_api_requests
@require_http_methods(["POST"])
def submit_availability_report(request, on_request_logged):
    authorization = request.META.get("HTTP_AUTHORIZATION") or ""
    if not authorization.startswith("Bearer "):
        return JsonResponse(
            {"error": "Authorization header must start with 'Bearer'"}, status=403
        )

    # Check that the API key is correct
    api_key = authorization.split("Bearer ")[1]
    if api_key != SCRAPER_API_KEY:
        return JsonResponse({"error": "Invalid API key"}, status=403)

    try:
        post_data = json.loads(request.body.decode("utf-8"))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    try:
        data = AppointmentAvailabilityReportValidator(**post_data).dict()
    except ValidationError as e:
        return JsonResponse({"error": e.errors()}, status=400)

    # Check if we already know about this feed update; create it if we don't
    feed_update, _ = FeedUpdate.objects.update_or_create(
        uuid=data["feed_update"]["uuid"],
        feed_provider=data["feed_update"]["feed_provider"],
        github_url=data["feed_update"]["github_url"],
    )

    try:
        location = LocationFeedConcordance.objects.get(
            feed_provider=data["feed_update"]["feed_provider"],
            provider_id=data["location"],
        ).location
    except LocationFeedConcordance.DoesNotExist:
        return JsonResponse(
            {"error": "Location is not matched to any known location."}, status=400
        )

    # Create the availability report
    report_kwargs = dict(
        is_test_data=bool(request.POST.get("test")),
        location=location,
        feed_update=feed_update,
        feed_json=data["feed_json"],
    )
    if bool(request.GET.get("test")) and request.GET.get("fake_timestamp"):
        fake_timestamp = parser.parse(request.GET["fake_timestamp"])
        if fake_timestamp.tzinfo is None:
            # Assume this is UTC
            fake_timestamp = pytz.UTC.localize(fake_timestamp)
        report_kwargs["created_at"] = fake_timestamp

    report = AppointmentAvailabilityReport.objects.create(**report_kwargs)

    for window_data in data["availability_windows"]:
        window = AppointmentAvailabilityWindow.objects.create(
            availability_report=report,
            starts_at=window_data["starts_at"],
            ends_at=window_data["ends_at"],
            slots=window_data["slots"],
        )
        for tag in window_data["additional_restrictions"]:
            window.additional_restrictions.add(tag)

    # Refresh Report from DB to get .public_id
    report.refresh_from_db()

    def log_created_report(log):
        log.created_availability_report = report
        log.save()

    on_request_logged(log_created_report)
    return HttpResponse(status=201)  # 201 Created
