from datetime import timedelta
from typing import Callable, Optional

import beeline  # type: ignore
from api.models import ApiLog
from api.utils import JWTRequest, deny_if_api_is_disabled, jwt_auth, log_api_requests
from core.models import CallRequest, Location
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from timezonefinder import TimezoneFinder


@csrf_exempt
@beeline.traced(name="request_call")
@log_api_requests
@deny_if_api_is_disabled
@jwt_auth(required_permissions=set(["caller"]))
def request_call(
    request: JWTRequest, on_request_logged: Callable[[Callable[[ApiLog], None]], None]
):
    if request.method != "POST":
        return JsonResponse(
            {"error": "Must be a POST"},
            status=400,
        )
    # Ensure there are at least MIN_QUEUE items in the queue
    CallRequest.backfill_queue()
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
        with beeline.tracer(name="examine_queue"):
            # Obey ?state= if present, otherwise default to California
            state = request.GET.get("state") or "CA"
            now = timezone.now()
            # Pick the next item from the call list for that state
            available_requests = CallRequest.available_requests()
            if state != "all":
                available_requests = available_requests.filter(
                    location__state__abbreviation=state
                )
            # We need to lock the record we select so we can update
            # it marking that we have claimed it
            call_requests = available_requests.select_for_update()[:1]
            with transaction.atomic():
                try:
                    call_request: Optional[CallRequest] = call_requests[0]
                except IndexError:
                    call_request = None
                if call_request is not None and not no_claim:
                    call_request.claimed_by = request.reporter
                    call_request.claimed_until = now + timedelta(
                        minutes=settings.CLAIM_LOCK_MINUTES
                    )
                    call_request.save()
            if call_request is None:
                return JsonResponse(
                    {"error": "Couldn't find somewhere to call"},
                    status=400,
                )
            location = call_request.location

    latest_report = location.dn_latest_non_skip_report

    county_record = {}
    county_age_floor_without_restrictions = []
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
        county_age_floor_without_restrictions = [
            location.county.age_floor_without_restrictions
        ]

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
            "State": location.state.abbreviation,
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
            "county_age_floor_without_restrictions": county_age_floor_without_restrictions,
            "timezone": TimezoneFinder().timezone_at(
                lng=float(location.longitude), lat=float(location.latitude)
            ),
            # TODO: these should be True sometimes for locations that need updates:
            "confirm_address": False,
            "confirm_hours": False,
            "confirm_website": False,
        },
        status=200,
    )
