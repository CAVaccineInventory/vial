import json
import pathlib
import re
from typing import Any, Callable, Dict, List, Optional, Union

import beeline
import markdown
import reversion
from api.location_metrics import LocationMetricsReport
from bigmap.transform import source_to_location
from core import exporter
from core.import_utils import import_airtable_report
from core.models import (
    AvailabilityTag,
    ConcordanceIdentifier,
    County,
    ImportRun,
    Location,
    LocationType,
    Provider,
    ProviderType,
    SourceLocation,
    State,
    Task,
    TaskType,
)
from core.utils_merge_locations import merge_locations
from django.http import HttpRequest, JsonResponse
from django.http.response import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from mdx_urlize import UrlizeExtension
from pydantic import BaseModel, ValidationError, validator
from vaccine_feed_ingest_schema.schema import ImportSourceLocation, Link

from .serialize import location_json
from .utils import (
    PrettyJsonResponse,
    jwt_auth,
    log_api_requests,
    require_api_key,
    require_api_key_or_cookie_user,
)


@require_api_key
def verify_token(request):
    return PrettyJsonResponse(
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
        for location_raw in post_data:
            try:
                with beeline.tracer(name="location_validator"):
                    location_data = LocationValidator(**location_raw).dict()
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
                if location_raw.get("import_ref"):
                    location, created = Location.objects.update_or_create(
                        import_ref=location_raw["import_ref"], defaults=kwargs
                    )
                    if created:
                        added_locations.append(location)
                    else:
                        updated_locations.append(location)
                else:
                    location = Location.objects.create(**kwargs)
                    added_locations.append(location)
            except ValidationError as e:
                errors.append((location_raw, e.errors()))
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
        json_records = [json.loads(line) for line in lines if line.strip()]
    except ValueError as e:
        return JsonResponse({"error": "JSON error: " + str(e)}, status=400)
    # Validate those JSON records
    errors = []
    records = []
    for json_record in json_records:
        try:
            record = ImportSourceLocation(**json_record)
            if (
                record.import_json.address is not None
                and record.import_json.address.state is None
            ):
                errors.append((json_record, "no state specified on address"))
            records.append(record)
        except ValidationError as e:
            errors.append((json_record, e.errors()))
    if errors:
        return JsonResponse({"errors": errors}, status=400)
    # All are valid, record them
    created = []
    updated = []
    for json_record, record in zip(json_records, records):
        matched_location = None
        if record.match is not None and record.match.action == "existing":
            matched_location = Location.objects.get(public_id=record.match.id)

        defaults = {
            "source_name": record.source_name,
            "name": record.name,
            "latitude": record.latitude,
            "longitude": record.longitude,
            "import_json": json_record["import_json"],
            "import_run": import_run,
            "last_imported_at": timezone.now(),
        }

        source_location, was_created = SourceLocation.objects.update_or_create(
            source_uid=record.source_uid, defaults=defaults
        )
        safe_to_match = was_created or source_location.matched_location is None

        if safe_to_match and matched_location is not None:
            source_location.matched_location = matched_location
            source_location.save()

        import_json = record.import_json
        links = list(import_json.links) if import_json.links is not None else []
        # Always use the (source, id) as a concordance
        links.append(
            Link(authority=import_json.source.source, id=import_json.source.id)
        )

        for link in links:
            identifier, _ = ConcordanceIdentifier.objects.get_or_create(
                authority=link.authority, identifier=link.id
            )
            identifier.source_locations.add(source_location)

        if safe_to_match:
            if record.match is not None and record.match.action == "new":
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
    if location_kwargs["state"] is not None:
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
    return PrettyJsonResponse(
        {"location_types": list(LocationType.objects.values_list("name", flat=True))}
    )


def provider_types(request):
    return PrettyJsonResponse(
        {"provider_types": list(ProviderType.objects.values_list("name", flat=True))}
    )


def task_types(request):
    return PrettyJsonResponse(
        {"task_types": list(TaskType.objects.values_list("name", flat=True))}
    )


def availability_tags(request):
    return PrettyJsonResponse(
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


@csrf_exempt
@beeline.traced(name="api_export_vaccinate_the_states")
def api_export_vaccinate_the_states(request):
    if request.method != "POST":
        return JsonResponse(
            {"error": "Must be a POST"},
            status=400,
        )
    if not exporter.api_export_vaccinate_the_states():
        return JsonResponse(
            {"error": "Failed to export; check Sentry"},
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


class UpdateSourceLocationMatchValidator(BaseModel):
    source_location: SourceLocation
    location: Union[Location, None]


@log_api_requests
@beeline.traced("update_source_location_match")
@jwt_auth(
    allow_session_auth=False,
    allow_internal_api_key=True,
    required_permissions=["write:locations"],
)
@csrf_exempt
def update_source_location_match(
    request: HttpRequest, on_request_logged: Callable
) -> HttpResponse:
    try:
        post_data = json.loads(request.body.decode("utf-8"))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    try:
        data = UpdateSourceLocationMatchValidator(**post_data)
    except ValidationError as e:
        return JsonResponse({"error": e.errors()}, status=400)

    source_location = data.source_location
    location = data.location

    old_matched_location = source_location.matched_location

    source_location.matched_location = location
    source_location.save()

    # Record the history record
    kwargs = {
        "old_match_location": old_matched_location,
        "new_match_location": location,
    }
    if hasattr(request, "reporter"):
        kwargs["reporter"] = request.reporter  # type:ignore[attr-defined]
    else:
        kwargs["api_key"] = request.api_key  # type:ignore[attr-defined]
    source_location.source_location_match_history.create(  # type:ignore[attr-defined]
        **kwargs
    )

    return JsonResponse(
        {
            "matched": {
                "location": {
                    "id": location.public_id,  # type:ignore[attr-defined]
                    "name": location.name,  # type:ignore[attr-defined]
                }
                if location
                else None,
                "source_location": {
                    "source_uid": source_location.source_uid,  # type:ignore[attr-defined]
                    "name": source_location.name,  # type:ignore[attr-defined]
                },
            }
        }
    )


class CreateLocationFromSourceLocationValidator(BaseModel):
    source_location: SourceLocation


@log_api_requests
@beeline.traced("create_location_from_source_location")
@jwt_auth(
    allow_session_auth=False,
    allow_internal_api_key=True,
    required_permissions=["write:locations"],
)
@csrf_exempt
def create_location_from_source_location(
    request: HttpRequest, on_request_logged: Callable
) -> HttpResponse:
    try:
        post_data = json.loads(request.body.decode("utf-8"))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    try:
        data = CreateLocationFromSourceLocationValidator(**post_data)
    except ValidationError as e:
        return JsonResponse({"error": e.errors()}, status=400)

    with reversion.create_revision():
        location = build_location_from_source_location(data.source_location)
        credit = ""
        if getattr(request, "api_key", None):
            credit = "API key {}".format(str(request.api_key))  # type: ignore[attr-defined]
        elif getattr(request, "reporter", None):
            credit = "Reporter {}".format(str(request.reporter))  # type: ignore[attr-defined]
        reversion.set_comment("/api/createLocationFromSourceLocation {}".format(credit))

    return JsonResponse(
        {
            "location": {
                "id": location.public_id,
                "name": location.name,
                "vial_url": request.build_absolute_uri(
                    "/admin/core/location/{}/change/".format(location.id)
                ),
            }
        }
    )


class TaskValidator(BaseModel):
    task_type: TaskType
    location: Location
    other_location: Optional[Location]
    details: Optional[dict]


class ImportTasksValidator(BaseModel):
    items: List[TaskValidator]


@log_api_requests
@beeline.traced("import_tasks")
@jwt_auth(
    allow_session_auth=False,
    allow_internal_api_key=True,
    required_permissions=["write:tasks"],
)
@csrf_exempt
def import_tasks(request: HttpRequest, on_request_logged: Callable) -> HttpResponse:
    try:
        post_data = json.loads(request.body.decode("utf-8"))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    if isinstance(post_data, dict):
        post_data = [post_data]

    try:
        items = ImportTasksValidator(items=post_data).items
    except ValidationError as e:
        return JsonResponse({"error": e.errors()}, status=400)

    # Create those items!
    user = request.api_key.user if hasattr(request, "api_key") else request.reporter.get_user()  # type: ignore[attr-defined]

    created = Task.objects.bulk_create(
        [
            Task(
                task_type=item.task_type,
                created_by=user,
                location=item.location,
                other_location=item.other_location,
                details=item.details,
            )
            for item in items
        ]
    )
    return JsonResponse({"created": [item.pk for item in created]})


def task_json(task: Task) -> Dict[str, object]:
    return {
        "id": task.id,
        "task_type": task.task_type.name,
        "location": location_json(task.location, include_soft_deleted=True),
        "other_location": location_json(task.other_location, include_soft_deleted=True)
        if task.other_location
        else None,
        "details": task.details,
    }


class RequestTaskValidator(BaseModel):
    task_type: TaskType
    state: Optional[State]
    q: Optional[str]


@log_api_requests
@beeline.traced("request_task")
@jwt_auth(
    allow_session_auth=False,
    allow_internal_api_key=True,
    required_permissions=["caller"],
)
@csrf_exempt
def request_task(request: HttpRequest, on_request_logged: Callable) -> HttpResponse:
    try:
        post_data = json.loads(request.body.decode("utf-8"))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    try:
        info = RequestTaskValidator(**post_data)
    except ValidationError as e:
        return JsonResponse({"error": e.errors()}, status=400)

    kwargs = {"resolved_at": None}  # type: Dict[str, Any]
    if info.q:
        kwargs["location__name__icontains"] = info.q
    if info.state:
        kwargs["location__state"] = info.state

    tasks = info.task_type.tasks.filter(**kwargs)
    task = tasks.order_by("?").first()
    if not task:
        return JsonResponse(
            {
                "task_type": info.task_type.name,
                "task": None,
                "warning": 'No unresolved tasks of type "{}"'.format(
                    info.task_type.name
                ),
            }
        )

    return JsonResponse(
        {
            "task_type": task.task_type.name,
            "task": task_json(task),
            "unresolved_of_this_type": tasks.count(),
        }
    )


class ResolveTaskValidator(BaseModel):
    task_id: Task
    resolution: Optional[dict]

    @validator("task_id")
    def task_must_not_be_resolved(cls, task):
        if task.resolved_by:
            raise ValueError("Task {} is already resolved".format(task.pk))
        return task


@log_api_requests
@beeline.traced("resolve_task")
@jwt_auth(
    allow_session_auth=False,
    allow_internal_api_key=True,
    required_permissions=["caller"],
)
@csrf_exempt
def resolve_task(request: HttpRequest, on_request_logged: Callable) -> HttpResponse:
    try:
        post_data = json.loads(request.body.decode("utf-8"))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    try:
        info = ResolveTaskValidator(**post_data)
    except ValidationError as e:
        return JsonResponse({"error": e.errors()}, status=400)

    user = request.api_key.user if hasattr(request, "api_key") else request.reporter.get_user()  # type: ignore[attr-defined]

    task = info.task_id
    task.resolved_by = user
    task.resolved_at = timezone.now()
    if info.resolution:
        task.resolution = info.resolution
    task.save()

    return JsonResponse(
        {"task_id": task.id, "resolution": task.resolution, "resolved": True}
    )


class MergeLocationsValidator(BaseModel):
    winner: Location
    loser: Location
    task_id: Optional[Task]

    @validator("winner")
    def winner_must_not_be_soft_deleted(cls, winner):
        if winner.soft_deleted:
            raise ValueError("Location {} is soft deleted".format(winner.public_id))
        return winner

    @validator("loser")
    def loser_must_not_be_soft_deleted(cls, loser):
        if loser.soft_deleted:
            raise ValueError("Location {} is soft deleted".format(loser.public_id))
        return loser

    @validator("loser")
    def winner_and_loser_differ(cls, loser, values):
        if "winner" in values and loser.pk == values["winner"].pk:
            raise ValueError("Winner and loser should not be the same")
        return loser

    @validator("task_id")
    def task_must_not_be_resolved(cls, task):
        if task.resolved_by:
            raise ValueError("Task {} is already resolved".format(task.pk))
        return task


@log_api_requests
@beeline.traced("merge_locations")
@jwt_auth(
    allow_session_auth=False,
    allow_internal_api_key=True,
    required_permissions=["write:locations"],
)
@csrf_exempt
def merge_locations_endpoint(
    request: HttpRequest, on_request_logged: Callable
) -> HttpResponse:
    try:
        post_data = json.loads(request.body.decode("utf-8"))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    try:
        info = MergeLocationsValidator(**post_data)
    except ValidationError as e:
        return JsonResponse({"error": e.errors()}, status=400)

    user = request.api_key.user if hasattr(request, "api_key") else request.reporter.get_user()  # type: ignore[attr-defined]

    merge_locations(info.winner, info.loser, user)

    # If task_id was provided, resolve that task
    task = info.task_id
    if task:
        task.resolved_by = user
        task.resolved_at = timezone.now()
        task.resolution = {
            "merged_locations": True,
            "winner": info.winner.public_id,
            "loser": info.loser.public_id,
        }
        task.save()

    return JsonResponse(
        {
            "winner": {
                "id": info.winner.public_id,
                "name": info.winner.name,
                "vial_url": request.build_absolute_uri(
                    "/admin/core/location/{}/change/".format(info.winner.id)
                ),
            },
            "loser": {
                "id": info.loser.public_id,
                "name": info.loser.name,
                "vial_url": request.build_absolute_uri(
                    "/admin/core/location/{}/change/".format(info.loser.id)
                ),
            },
        }
    )
