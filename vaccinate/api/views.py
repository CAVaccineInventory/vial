import json
import os
from datetime import datetime, timedelta
from typing import List, Optional

import pytz
import requests
from auth0login.auth0_utils import decode_and_verify_jwt
from core.import_utils import derive_appointment_tag, resolve_availability_tags
from core.models import (
    AppointmentTag,
    CallRequest,
    CallRequestReason,
    County,
    Location,
    LocationType,
    Report,
    Reporter,
    State,
)
from dateutil import parser
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from pydantic import BaseModel, Field, ValidationError, validator

from .utils import log_api_requests, require_api_key


class ReportValidator(BaseModel):
    location: str = Field(alias="Location")
    appointment_details: Optional[str] = Field(
        alias="Appointment scheduling instructions"
    )
    appointments_by_phone: Optional[bool] = Field(alias="Appointments by phone?")
    availability: List[str] = Field(alias="Availability")
    public_notes: Optional[str] = Field(alias="Notes")
    internal_notes: Optional[str] = Field(alias="Internal Notes")
    do_not_call_until: Optional[datetime] = Field(alias="Do not call until")

    @validator("location")
    def location_must_exist(cls, v):
        try:
            return Location.objects.get(public_id=v)
        except Location.DoesNotExist:
            raise ValueError("Location '{}' does not exist".format(v))


def reporter_from_request(request, allow_test=False):
    if allow_test and bool(request.GET.get("test")) and request.GET.get("fake_user"):
        reporter = Reporter.objects.get_or_create(
            external_id="auth0:{}".format(request.GET["fake_user"]),
        )[0]
        user_info = {"fake": reporter.external_id}
        return reporter, user_info
    # Use Bearer token in Authorization header
    authorization = request.META.get("HTTP_AUTHORIZATION") or ""
    if not authorization.startswith("Bearer "):
        return (
            JsonResponse(
                {"error": "Authorization header must start with 'Bearer'"}, status=403
            ),
            None,
        )
    # Check JWT token is valid
    jwt_id_token = authorization.split("Bearer ")[1]
    try:
        jwt_payload = decode_and_verify_jwt(jwt_id_token, try_fallback=True)
    except Exception as e:
        return (
            JsonResponse(
                {"error": "Could not decode JWT", "details": str(e)}, status=403
            ),
            None,
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
    return reporter, user_info


@csrf_exempt
@log_api_requests
def submit_report(request, on_request_logged):
    # The ?test=1 version accepts &fake_user=external_id
    reporter, user_info = reporter_from_request(request, allow_test=True)
    if isinstance(reporter, JsonResponse):
        return reporter
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

    # Handle skip requests
    # Only check if "Do not call until is set"
    if report_data["do_not_call_until"] is not None:
        skip_reason = CallRequestReason.objects.get(short_reason="Previously skipped")
        if skip_reason is None:
            return JsonResponse(
                {
                    "error": "Report set do not call time but the database is missing the skip reason."
                },
                status=500,
            )

        if "skip_call_back_later" not in [tag.slug for tag in availability_tags]:
            return JsonResponse(
                {"error": "Report set do not call time but did not request a skip."},
                status=400,
            )

        CallRequest.objects.create(
            location=report_data["location"],
            vesting_at=report_data["do_not_call_until"],
            call_request_reason=skip_reason,
            tip_type=CallRequest.TipType.SCOOBY,
            tip_report=report,
        )

    def log_created_report(log):
        log.created_report = report
        log.save()

        # Send it to Zapier too
        if os.environ.get("ZAPIER_REPORT_URL"):
            requests.post(
                os.environ["ZAPIER_REPORT_URL"],
                json={
                    "report_url": request.build_absolute_uri(
                        "/admin/core/report/{}/change/".format(report.pk)
                    ),
                    "report_public_notes": report.public_notes,
                    "report_internal_notes": report.internal_notes,
                    "location_name": report.location.name,
                    "location_full_address": report.location.full_address,
                    "location_state": report.location.state.abbreviation,
                    "reporter_name": report.reported_by.name,
                    "reporter_id": report.reported_by.external_id,
                    "reporter_role": report.reported_by.auth0_role_name,
                    "availability_tags": list(
                        report.availability_tags.values_list("name", flat=True)
                    ),
                },
            )

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


def request_call_debug(request):
    return render(
        request,
        "api/request_call_debug.html",
        {"jwt": request.session["jwt"] if "jwt" in request.session else ""},
    )


@csrf_exempt
@log_api_requests
def request_call(request, on_request_logged):
    if request.method != "POST":
        return JsonResponse(
            {"error": "Must be a POST"},
            status=400,
        )
    reporter, user_info = reporter_from_request(request)
    if isinstance(reporter, JsonResponse):
        return reporter
    # Override location selection: pass the public_id of a rocation to
    # skip the normal view selection code and return that ID specifically
    location_id = request.GET.get("location_id") or None
    # Skip updating the record to lock it from other callers - use for testing
    no_claim = bool(request.GET.get("no_claim"))
    if location_id:
        try:
            location = Location.objects.get(public_id=location_id)
        except Location.DoesNotExist:
            return JsonResponse(
                {"error": "Location with that public_id does not exist"},
                status=400,
            )
    else:
        now = timezone.now()
        # Pick a random location from the call list
        available_requests = CallRequest.available_requests()
        # We need to lock the record we randomly select so we can update
        # it marking that we have claimed it
        call_requests = available_requests.select_for_update().order_by("?")[:1]
        with transaction.atomic():
            try:
                request = call_requests[0]
            except IndexError:
                request = None
            if request is not None and not no_claim:
                request.claimed_by = reporter
                request.claimed_until = now + timedelta(minutes=20)
                request.save()
        if request is None:
            return JsonResponse(
                {"error": "Couldn't find somewhere to call"},
                status=400,
            )
        location = request.location

    try:
        latest_report = location.reports.order_by("-created_at")[0]
    except IndexError:
        latest_report = None

    county_record = {}
    if location.county:
        county_record = {
            "id": location.county.airtable_id
            if location.county.airtable_id
            else location.county.id,
            "County": location.county.name,
            "Vaccine info URL": location.county.vaccine_info_url,
            "Vaccine locations URL": location.county.vaccine_locations_url,
            "Notes": location.county.public_notes,
        }

    provider_record = {}
    if location.provider:
        provider = location.provider
        provider_record = {
            "id": provider.id,
            "Provider": provider.name,
            "Vaccine info URL": provider.vaccine_info_url,
            "Public Notes": provider.public_notes,
            # TODO: What's Phase? In example it was
            # ["Not currently vaccinating"]
            "Phase": [],
            "Provider network type": provider.provider_type.name,
            # TODO: This should be a real date:
            "Last Updated": "YYYY-MM-DD",
        }

    return JsonResponse(
        {
            "id": location.public_id,
            "Name": location.name,
            "Phone number": location.phone_number,
            "Address": location.full_address,
            "Internal notes": location.internal_notes,
            "Hours": location.hours,
            "County": location.county.name if location.county else None,
            "Location Type": location.location_type.name,
            "Affiliation": location.provider.name if location.provider else None,
            "Latest report": str(latest_report.created_at) if latest_report else None,
            "Latest report notes": [
                latest_report.public_notes if latest_report else None
            ],
            "County vaccine info URL": [
                location.county.vaccine_info_url if location.county else None
            ],
            "County Vaccine locations URL": [
                location.county.vaccine_locations_url if location.county else None
            ],
            "Latest Internal Notes": [
                latest_report.internal_notes if latest_report else None
            ],
            "Availability Info": list(
                latest_report.availability_tags.values_list("name", flat=True)
            )
            if latest_report
            else [],
            "Number of Reports": location.reports.count(),
            "county_record": county_record,
            "provider_record": provider_record,
        },
        status=200,
    )


@require_api_key
def verify_token(request):
    return JsonResponse(
        {
            "key_id": request.api_key.id,
            "last_seen_at": request.api_key.last_seen_at,
            "description": request.api_key.description,
        }
    )


class LocationValidator(BaseModel):
    name: str
    state: str
    latitude: float
    longitude: float
    location_type: str
    import_ref: Optional[str]
    # All of these are optional:
    phone_number: Optional[str]
    full_address: Optional[str]
    city: Optional[str]
    county: Optional[str]
    google_places_id: Optional[str]
    zip_code: Optional[str]
    hours: Optional[str]
    website: Optional[str]
    airtable_id: Optional[str]

    @validator("state")
    def state_must_exist(cls, value):
        try:
            return State.objects.get(abbreviation=value)
        except State.DoesNotExist:
            raise ValueError("State '{}' does not exist".format(value))

    @validator("county")
    def county_must_exist(cls, value, values):
        try:
            return values["state"].counties.get(name=value)
        except County.DoesNotExist:
            raise ValueError(
                "County '{}' does not exist in state {}".format(
                    value, values["state"].name
                )
            )

    @validator("location_type")
    def location_type_must_exist(cls, value):
        try:
            return LocationType.objects.get(name=value)
        except LocationType.DoesNotExist:
            raise ValueError("LocationType '{}' does not exist".format(value))


@log_api_requests
@require_api_key
def import_locations(request, on_request_logged):
    try:
        post_data = json.loads(request.body.decode("utf-8"))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    added_locations = []
    updated_locations = []
    errors = []
    if isinstance(post_data, dict):
        post_data = [post_data]
    for location_json in post_data:
        try:
            location_data = LocationValidator(**location_json).dict()
            kwargs = dict(
                name=location_data["name"],
                latitude=location_data["latitude"],
                longitude=location_data["longitude"],
                state=location_data["state"],
                location_type=location_data["location_type"],
                import_json=location_json,
            )
            for key in (
                "phone_number",
                "full_address",
                "city",
                "county",
                "google_places_id",
                "zip_code",
                "hours",
                "website",
                "latitude",
                "longitude",
                "airtable_id",
            ):
                kwargs[key] = location_data.get(key)
            kwargs["street_address"] = (kwargs["full_address"] or "").split(",")[0]
            if location_json.get("import_ref"):
                location, created = Location.objects.update_or_create(
                    import_ref=location_json["import_ref"], defaults=kwargs
                )
                if created:
                    added_locations.append(location)
                else:
                    updated_locations.append(location)
            else:
                location = Location.objects.create(**kwargs)
                added_locations.append(location)
        except ValidationError as e:
            errors.append((location_json, e.errors()))
    for location in added_locations:
        location.refresh_from_db()
    return JsonResponse(
        {
            "added": [location.public_id for location in added_locations],
            "updated": [location.public_id for location in updated_locations],
            "errors": errors,
        }
    )


def location_types(request):
    return JsonResponse(
        {"location_types": list(LocationType.objects.values_list("name", flat=True))}
    )


def counties(request, state_abbreviation):
    try:
        state = State.objects.get(abbreviation=state_abbreviation)
    except State.DoesNotExist:
        return JsonResponse({"error": "Unknown state"}, status=404)
    return JsonResponse(
        {
            "state_name": state.name,
            "state_abbreviation": state.abbreviation,
            "state_fips_code": state.fips_code,
            "counties": [
                {
                    "county_name": county.name,
                    "county_fips_code": county.fips_code,
                }
                for county in state.counties.all()
            ],
        }
    )
