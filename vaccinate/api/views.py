import json
import pathlib
import re
from datetime import timedelta
from typing import Dict, List, Optional

import beeline
import markdown
import reversion
from api.location_metrics import LocationMetricsReport
from bigmap.transform import source_to_location
from core import exporter
from core.import_utils import import_airtable_report
from core.models import (
    AvailabilityTag,
    CallRequest,
    ConcordanceIdentifier,
    County,
    ImportRun,
    Location,
    LocationType,
    Provider,
    ProviderType,
    SourceLocation,
    State,
)
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.timezone import localdate
from django.views.decorators.csrf import csrf_exempt
from mdx_urlize import UrlizeExtension
from pydantic import BaseModel, ValidationError, validator
from timezonefinder import TimezoneFinder
from vaccine_feed_ingest_schema.schema import ImportSourceLocation

from .utils import (
    deny_if_api_is_disabled,
    log_api_requests,
    reporter_from_request,
    require_api_key,
    require_api_key_or_cookie_user,
)


@csrf_exempt
@log_api_requests
@deny_if_api_is_disabled
@beeline.traced(name="request_call")
def request_call(request, on_request_logged):
    if request.method != "POST":
        return JsonResponse(
            {"error": "Must be a POST"},
            status=400,
        )
    reporter, user_info = reporter_from_request(request)
    if isinstance(reporter, JsonResponse):
        return reporter
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
                    request = call_requests[0]
                except IndexError:
                    request = None
                if request is not None and not no_claim:
                    request.claimed_by = reporter
                    request.claimed_until = now + timedelta(
                        minutes=settings.CLAIM_LOCK_MINUTES
                    )
                    request.save()
            if request is None:
                return JsonResponse(
                    {"error": "Couldn't find somewhere to call"},
                    status=400,
                )
            location = request.location

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


@require_api_key
def verify_token(request):
    return JsonResponse(
        {
            "key_id": request.api_key.id,
            "last_seen_at": request.api_key.last_seen_at,
            "description": request.api_key.description,
        }
    )


class _LocationSharedValidators(BaseModel):
    # We use check_fields=Falsse because this class
    # is designed to be used as a subclass/mixin,
    # and without check_fields=False pydantic will
    # show an error because the validator refers
    # to a field not available on this class.
    @validator("state", check_fields=False)
    def state_must_exist(cls, value):
        try:
            return State.objects.get(abbreviation=value)
        except State.DoesNotExist:
            raise ValueError("State '{}' does not exist".format(value))

    @validator("county", check_fields=False)
    def set_county_to_null_if_it_does_not_exist(cls, value, values):
        try:
            return values["state"].counties.get(name=value)
        except County.DoesNotExist:
            return None

    @validator("location_type", check_fields=False)
    def location_type_must_exist(cls, value):
        try:
            return LocationType.objects.get(name=value)
        except LocationType.DoesNotExist:
            raise ValueError("LocationType '{}' does not exist".format(value))

    @validator("provider_type", check_fields=False)
    def provider_type_must_exist(cls, value):
        try:
            return ProviderType.objects.get(name=value)
        except ProviderType.DoesNotExist:
            raise ValueError("ProviderType '{}' does not exist".format(value))

    @validator("provider_name", check_fields=False)
    def provider_name_requires_provider_type(cls, value, values):
        assert values.get(
            "provider_type"
        ), "provider_type must be provided if provider_name is used"
        return value


class LocationValidator(_LocationSharedValidators):
    name: str
    state: str
    latitude: float
    longitude: float
    location_type: str
    import_ref: Optional[str]
    # All of these are optional:
    import_json: Optional[dict]
    phone_number: Optional[str]
    full_address: Optional[str]
    city: Optional[str]
    county: Optional[str]
    google_places_id: Optional[str]
    vaccinefinder_location_id: Optional[str]
    vaccinespotter_location_id: Optional[str]
    zip_code: Optional[str]
    hours: Optional[str]
    website: Optional[str]
    airtable_id: Optional[str]
    soft_deleted: Optional[bool]
    duplicate_of: Optional[str]
    preferred_contact_method: Optional[str]
    # Provider
    provider_type: Optional[str]
    provider_name: Optional[str]


@csrf_exempt
@log_api_requests
@require_api_key
@beeline.traced(name="import_locations")
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
    with reversion.create_revision():
        for location_json in post_data:
            try:
                with beeline.tracer(name="location_validator"):
                    location_data = LocationValidator(**location_json).dict()
                kwargs = dict(
                    name=location_data["name"],
                    latitude=location_data["latitude"],
                    longitude=location_data["longitude"],
                    state=location_data["state"],
                    location_type=location_data["location_type"],
                    import_json=location_data.get("import_json") or None,
                )
                if location_data.get("provider_type"):
                    kwargs["provider"] = Provider.objects.update_or_create(
                        name=location_data["provider_name"],
                        defaults={"provider_type": location_data["provider_type"]},
                    )[0]
                for key in (
                    "phone_number",
                    "full_address",
                    "city",
                    "county",
                    "google_places_id",
                    "vaccinefinder_location_id",
                    "vaccinespotter_location_id",
                    "zip_code",
                    "hours",
                    "website",
                    "preferred_contact_method",
                    "latitude",
                    "longitude",
                    "airtable_id",
                ):
                    kwargs[key] = location_data.get(key)
                kwargs["street_address"] = (kwargs["full_address"] or "").split(",")[0]
                # Handle lted and duplicate_of
                if location_data.get("soft_deleted"):
                    kwargs["soft_deleted"] = True
                if location_data.get("duplicate_of"):
                    try:
                        duplicate_location = Location.objects.get(
                            public_id=location_data["duplicate_of"]
                        )
                        kwargs["duplicate_of"] = duplicate_location
                    except Location.DoesNotExist:
                        errors.append(
                            (
                                location_json,
                                "Marked as duplicate of {} which does not exist".format(
                                    location_data["duplicate_of"]
                                ),
                            )
                        )
                        continue
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
            reversion.set_comment(
                "/api/importLocations called with API key {}".format(
                    str(request.api_key)
                )
            )
    for location in added_locations:
        location.refresh_from_db()
    return JsonResponse(
        {
            "added": [location.public_id for location in added_locations],
            "updated": [location.public_id for location in updated_locations],
            "errors": errors,
        }
    )


@csrf_exempt
@log_api_requests
@require_api_key
def start_import_run(request, on_request_logged):
    if request.method == "POST":
        import_run = ImportRun.objects.create(api_key=request.api_key)
        return JsonResponse({"import_run_id": import_run.pk})
    else:
        return JsonResponse({"error": "POST required"}, status=400)


@csrf_exempt
@log_api_requests
@require_api_key
@beeline.traced(name="import_source_locations")
def import_source_locations(request, on_request_logged):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)
    try:
        import_run = ImportRun.objects.get(id=request.GET.get("import_run_id", "0"))
    except ImportRun.DoesNotExist:
        return JsonResponse({"error": "?import_run_id=X is required"}, status=400)
    try:
        post_data = request.body.decode("utf-8")
        lines = post_data.split("\n")
        records = [json.loads(l) for l in lines if l.strip()]
    except ValueError as e:
        return JsonResponse({"error": "JSON error: " + str(e)}, status=400)
    # Validate those JSON records
    errors = []
    for record in records:
        try:
            ImportSourceLocation(**record).dict()
        except ValidationError as e:
            errors.append((record, e.errors()))
    if errors:
        return JsonResponse({"errors": errors}, status=400)
    # All are valid, record them
    created = []
    updated = []
    for record in records:
        matched_location = None
        if "match" in record and record["match"]["action"] == "existing":
            matched_location = Location.objects.get(public_id=record["match"]["id"])

        source_location, was_created = SourceLocation.objects.update_or_create(
            source_uid=record["source_uid"],
            defaults={
                "source_name": record["source_name"],
                "name": record.get("name"),
                "latitude": record.get("latitude"),
                "longitude": record.get("longitude"),
                "import_json": record["import_json"],
                "import_run": import_run,
                "matched_location": matched_location,
                "last_imported_at": timezone.now(),
            },
        )

        import_json = record["import_json"]

        links = (
            list(import_json.get("links"))
            if import_json.get("links") is not None
            else []
        )
        # Always use the (source, id) as a concordance
        links.append(
            {
                "authority": import_json["source"]["source"],
                "id": import_json["source"]["id"],
            }
        )

        for link in links:
            identifier, _ = ConcordanceIdentifier.objects.get_or_create(
                authority=link["authority"], identifier=link["id"]
            )
            identifier.source_locations.add(source_location)

        if "match" in record and record["match"]["action"] == "new":
            matched_location = build_location_from_source_location(source_location)

        if matched_location is not None:
            new_concordances = source_location.concordances.difference(
                matched_location.concordances.all()
            )
            matched_location.concordances.add(*new_concordances)

        if was_created:
            created.append(source_location.pk)
        else:
            updated.append(source_location.pk)
    return JsonResponse({"created": created, "updated": updated})


def build_location_from_source_location(source_location: SourceLocation):
    location_kwargs = source_to_location(source_location.import_json)
    location_kwargs["state"] = State.objects.get(
        abbreviation=location_kwargs["state"].upper()
    )
    unknown_location_type = LocationType.objects.get(name="Unknown")

    location = Location.objects.create(
        location_type=unknown_location_type,
        import_run=source_location.import_run,
        **location_kwargs,
    )
    location.concordances.set(source_location.concordances.all())
    location.save()
    source_location.matched_location = location
    source_location.save()

    return location


@csrf_exempt
@log_api_requests
@require_api_key
@beeline.traced(name="import_reports")
def import_reports(request, on_request_logged):
    try:
        post_data = json.loads(request.body.decode("utf-8"))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    if not isinstance(post_data, list) or any(
        not isinstance(p, dict) for p in post_data
    ):
        return JsonResponse(
            {"error": "POST body should be a JSON list of dictionaries"}, status=400
        )
    availability_tags = AvailabilityTag.objects.all()
    added = []
    updated = []
    errors = []

    for report in post_data:
        try:
            report_obj, created = import_airtable_report(report, availability_tags)
            if created:
                added.append(report_obj.public_id)
            else:
                updated.append(report_obj.public_id)
        except (KeyError, AssertionError) as e:
            errors.append((report["airtable_id"], str(e)))
            continue

    return JsonResponse(
        {
            "added": added,
            "updated": updated,
            "errors": errors,
        }
    )


def location_types(request):
    return JsonResponse(
        {"location_types": list(LocationType.objects.values_list("name", flat=True))}
    )


def provider_types(request):
    return JsonResponse(
        {"provider_types": list(ProviderType.objects.values_list("name", flat=True))}
    )


def availability_tags(request):
    return JsonResponse(
        {
            "availability_tags": list(
                AvailabilityTag.objects.filter(disabled=False).values(
                    "slug", "name", "group", "notes", "previous_names"
                )
            )
        }
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
                for county in state.counties.order_by("name")
            ],
        }
    )


@csrf_exempt
@beeline.traced(name="caller_stats")
def caller_stats(request):
    reporter, user_info = reporter_from_request(request)
    if isinstance(reporter, JsonResponse):
        return reporter
    reports = reporter.reports.exclude(soft_deleted=True)
    return JsonResponse(
        {
            "total": reports.count(),
            "today": reports.filter(created_at__date=localdate()).count(),
        }
    )


def api_debug_view(
    api_path,
    use_jwt=True,
    body_textarea=False,
    docs=None,
    default_body=None,
    textarea_placeholder=None,
    querystring_fields=None,
):
    def debug_view(request):
        api_key = None
        if request.user.is_authenticated:
            api_key = request.user.api_keys.order_by("-last_seen_at").first()
        return render(
            request,
            "api/api_debug.html",
            {
                "use_jwt": use_jwt,
                "jwt": request.session["jwt"] if "jwt" in request.session else "",
                "api_key": api_key,
                "api_path": api_path,
                "body_textarea": body_textarea,
                "textarea_placeholder": textarea_placeholder,
                "querystring_fields": querystring_fields,
                "default_body": default_body,
                "docs": docs,
            },
        )

    return debug_view


def api_docs(request):
    content = (
        pathlib.Path(__file__).parent.parent.parent / "docs" / "api.md"
    ).read_text()
    # Remove first line (header)
    lines = content.split("\n")
    content = "\n".join(lines[1:]).strip()
    # Replace https://vial-staging.calltheshots.us/ with our current hostname
    content = content.replace(
        "https://vial-staging.calltheshots.us/", request.build_absolute_uri("/")
    )
    md = markdown.Markdown(
        extensions=["toc", "fenced_code", UrlizeExtension()], output_format="html5"
    )
    html = md.convert(content)
    return render(
        request,
        "api/api_docs.html",
        {
            "content": html,
            "toc": md.toc,
        },
    )


@csrf_exempt
@beeline.traced(name="api_export")
def api_export(request):
    if request.method != "POST":
        return JsonResponse(
            {"error": "Must be a POST"},
            status=400,
        )
    if not exporter.api_export():
        return JsonResponse(
            {"error": "Failed to write one or more endpoints; check Sentry"},
            status=500,
        )
    return JsonResponse({"ok": 1})


def api_export_preview_locations(request):
    # Show a preview of the export API for a subset of locations
    location_ids = request.GET.getlist("id")
    with exporter.dataset() as ds:
        if location_ids:
            ds.locations = ds.locations.filter(public_id__in=location_ids)
        else:
            ds.locations = ds.locations.exclude(dn_latest_non_skip_report=None)[:10]
        api = exporter.V1(ds)
        return JsonResponse(api.metadata_wrap(api.get_locations()))


def api_export_preview_providers(request):
    # Show a preview of the export API for a subset of locations
    provider_ids = request.GET.getlist("id")
    with exporter.dataset() as ds:
        if provider_ids:
            ds.providers = ds.providers.filter(public_id__in=provider_ids)
        api = exporter.V1(ds)
        return JsonResponse(api.metadata_wrap(api.get_providers()))


@csrf_exempt
@beeline.traced(name="location_metrics")
def location_metrics(request):
    return LocationMetricsReport().serve()


class UpdateLocationsFieldsValidator(_LocationSharedValidators):
    name: Optional[str]
    state: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    location_type: Optional[str]
    phone_number: Optional[str]
    full_address: Optional[str]
    city: Optional[str]
    county: Optional[str]
    google_places_id: Optional[str]
    vaccinefinder_location_id: Optional[str]
    vaccinespotter_location_id: Optional[str]
    zip_code: Optional[str]
    hours: Optional[str]
    website: Optional[str]
    preferred_contact_method: Optional[str]
    provider_type: Optional[str]
    provider_name: Optional[str]


class UpdateLocationsValidator(BaseModel):
    update: Dict[str, UpdateLocationsFieldsValidator]
    revision_comment: Optional[str]

    @validator("update")
    def check_update(cls, v):
        # Every key should correspond to an existing location
        location_ids = set(v.keys())
        found = set(
            Location.objects.filter(public_id__in=location_ids).values_list(
                "public_id", flat=True
            )
        )
        assert location_ids.issubset(found), "Invalid location IDs: {}".format(
            ", ".join(location_ids - found)
        )
        return v


@csrf_exempt
@log_api_requests
@require_api_key
@beeline.traced(name="update_locations")
def update_locations(request, on_request_logged):
    try:
        post_data = json.loads(request.body.decode("utf-8"))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    try:
        data = UpdateLocationsValidator(**post_data)
    except ValidationError as e:
        return JsonResponse({"error": e.errors()}, status=400)

    updates = data.dict(exclude_unset=True)["update"]
    updated = []

    with reversion.create_revision():
        for location_id, fields in updates.items():
            location = Location.objects.get(public_id=location_id)
            for key, value in fields.items():
                if key == "provider_type":
                    continue
                elif key == "provider_name":
                    location.provider = Provider.objects.update_or_create(
                        name=fields["provider_name"],
                        defaults={"provider_type": fields["provider_type"]},
                    )[0]
                else:
                    setattr(location, key, value)
            location.save()
            updated.append(location.public_id)
        comment = data.revision_comment or "/api/updateLocations"
        reversion.set_comment("{} by {}".format(comment, request.api_key))

    return JsonResponse({"updated": updated}, status=200)


idref_re = re.compile("[a-zA-Z0-9_-]+:.*")


class UpdateLocationConcordancesFieldsValidator(BaseModel):
    add: Optional[List[str]]
    remove: Optional[List[str]]

    @validator("add")
    def check_add(cls, idrefs):
        bad = [idref for idref in idrefs if not idref_re.match(idref)]
        assert (
            not bad
        ), "Invalid references: {} - should be 'authority:identifier'".format(bad)
        return idrefs

    @validator("remove")
    def check_remove(cls, idrefs):
        return cls.check_add(idrefs)


class UpdateLocationConcordancesValidator(BaseModel):
    update: Dict[str, UpdateLocationConcordancesFieldsValidator]

    @validator("update")
    def check_update(cls, v):
        # Every key should correspond to an existing location
        location_ids = set(v.keys())
        found = set(
            Location.objects.filter(public_id__in=location_ids).values_list(
                "public_id", flat=True
            )
        )
        assert location_ids.issubset(found), "Invalid location IDs: {}".format(
            ", ".join(location_ids - found)
        )
        return v


@csrf_exempt
@log_api_requests
@require_api_key_or_cookie_user
@beeline.traced(name="update_location_concordances")
def update_location_concordances(request, on_request_logged):
    try:
        post_data = json.loads(request.body.decode("utf-8"))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    try:
        data = UpdateLocationConcordancesValidator(**post_data)
    except ValidationError as e:
        return JsonResponse({"error": e.errors()}, status=400)

    update = data.dict(exclude_unset=True)["update"]
    updated = []
    for location_id, updates in update.items():
        location = Location.objects.get(public_id=location_id)
        for idref in updates.get("add") or []:
            location.concordances.add(ConcordanceIdentifier.for_idref(idref))
        # Removing is more efficient:
        for idref in updates.get("remove") or []:
            authority, identifier = idref.split(":", 1)
            ConcordanceIdentifier.locations.through.objects.filter(
                location=location,
                concordanceidentifier__identifier=identifier,
                concordanceidentifier__authority=authority,
            ).delete()
        if updates.get("add") or updates.get("remove"):
            updated.append(location_id)

    # Garbage collection: delete any ConcordanceIdentifier
    # that no loger have locations or source_locations
    deleted_count = ConcordanceIdentifier.objects.filter(
        locations__isnull=True, source_locations__isnull=True
    ).delete()[0]
    return JsonResponse(
        {"updated": updated, "deleted_concordance_identifiers": deleted_count}
    )


def location_concordances(request, public_id):
    try:
        location = Location.objects.filter(soft_deleted=False).get(public_id=public_id)
    except Location.DoesNotExist:
        return JsonResponse({"error": "Location does not exist"}, status=404)
    return JsonResponse({"concordances": [str(c) for c in location.concordances.all()]})
