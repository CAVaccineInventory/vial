import datetime
from html import escape
from typing import Callable, Dict, Union

import beeline
import orjson
from core.baseconverter import pid
from core.models import ConcordanceIdentifier, County, Location, SourceLocation, State
from core.utils import keyset_pagination_iterator
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance
from django.db.models import Q
from django.db.models.query import QuerySet
from django.http import HttpRequest
from django.http.response import (
    HttpResponse,
    HttpResponseBase,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import render
from django.utils.safestring import mark_safe

from .serialize import (
    OutputFormat,
    build_stream,
    location_formats,
    location_json_queryset,
    make_formats,
)
from .utils import jwt_auth, log_api_requests_no_response_body


@log_api_requests_no_response_body
@beeline.traced("search_locations")
@jwt_auth(
    allow_session_auth=True,
    allow_internal_api_key=True,
    required_permissions=["read:locations"],
)
def search_locations(
    request: HttpRequest, on_request_logged: Callable
) -> HttpResponseBase:
    format = request.GET.get("format") or "json"
    size = min(int(request.GET.get("size", "10")), 1000)
    q = (request.GET.get("q") or "").strip().lower()
    all = request.GET.get("all")
    state = (request.GET.get("state") or "").upper()
    county_fips = request.GET.get("county_fips") or ""
    exportable = request.GET.get("exportable")
    latitude = request.GET.get("latitude")
    longitude = request.GET.get("longitude")
    radius = request.GET.get("radius")
    provider = request.GET.get("provider")
    provider_null = request.GET.get("provider_null")
    if state:
        try:
            State.objects.get(abbreviation=state)
        except State.DoesNotExist:
            return JsonResponse({"error": "State does not exist"}, status=400)
    if county_fips:
        try:
            County.objects.get(fips_code=county_fips)
        except County.DoesNotExist:
            return JsonResponse(
                {"error": "County does not exist for that FIPS code"}, status=400
            )
    # debug wraps in HTML so we can run django-debug-toolbar
    debug = request.GET.get("debug")
    if format == "map":
        get = request.GET.copy()
        get["format"] = "geojson"
        if "debug" in get:
            del get["debug"]
        return render(
            request, "api/search_locations_map.html", {"query_string": get.urlencode()}
        )

    qs: QuerySet[Location] = Location.objects.filter(soft_deleted=False)
    if q:
        qs = qs.filter(name__icontains=q)
    if state:
        qs = qs.filter(state__abbreviation=state)
    if county_fips:
        qs = qs.filter(county__fips_code=county_fips)
    if latitude and longitude and radius:
        for value in (latitude, longitude, radius):
            try:
                float(value)
            except ValueError:
                return JsonResponse(
                    {"error": "latitude/longitude/radius should be numbers"}, status=400
                )
        qs = qs.filter(
            point__dwithin=(
                Point(float(longitude), float(latitude)),
                Distance(m=float(radius)),
            )
        )
    ids = request.GET.getlist("id")
    if ids:
        qs = qs.filter(public_id__in=ids)
    idrefs = request.GET.getlist("idref")
    if idrefs:
        # Matching any of those idrefs
        idref_filter = ConcordanceIdentifier.filter_for_idrefs(idrefs)
        qs = qs.filter(
            concordances__in=ConcordanceIdentifier.objects.filter(idref_filter)
        )
    authorities = request.GET.getlist("authority")
    if authorities:
        qs = qs.filter(concordances__authority__in=authorities)
    exclude_authorities = request.GET.getlist("exclude.authority")
    if exclude_authorities:
        qs = qs.exclude(concordances__authority__in=exclude_authorities)
    if provider:
        qs = qs.filter(provider__name=provider)
    if provider_null:
        qs = qs.filter(provider__isnull=True)
    if exportable:
        qs = filter_for_export(qs)

    qs = location_json_queryset(qs)

    formats = location_formats()

    if format not in formats:
        return JsonResponse({"error": "Invalid format"}, status=400)

    formatter = formats[format]

    qs = formatter.prepare_queryset(qs)

    stream_qs = qs[:size]
    if all:
        stream_qs = keyset_pagination_iterator(qs)

    stream = build_stream(
        qs, stream_qs, formatter, beeline_trace_name="search_locations_stream"
    )

    if debug:
        if all:
            return JsonResponse({"error": "Cannot use both all and debug"}, status=400)
        output = b"".join(stream())
        if formatter.content_type == "application/json":
            output = orjson.dumps(orjson.loads(output), option=orjson.OPT_INDENT_2)
        return render(
            request,
            "api/search_locations_debug.html",
            {
                "output": mark_safe(escape(output.decode("utf-8"))),
            },
        )

    return StreamingHttpResponse(stream(), content_type=formatter.content_type)


@log_api_requests_no_response_body
@beeline.traced("search_source_locations")
@jwt_auth(
    allow_session_auth=True,
    allow_internal_api_key=True,
    required_permissions=["read:locations"],
)
def search_source_locations(
    request: HttpRequest, on_request_logged: Callable
) -> Union[HttpResponse, StreamingHttpResponse]:
    format = request.GET.get("format") or "json"
    size = min(int(request.GET.get("size", "10")), 1000)
    q = (request.GET.get("q") or "").strip().lower()
    debug = request.GET.get("debug")
    all = request.GET.get("all")
    unmatched = request.GET.get("unmatched")
    matched = request.GET.get("matched")
    state = (request.GET.get("state") or "").upper()
    haspoint = request.GET.get("haspoint")
    random = request.GET.get("random")
    source_names = request.GET.getlist("source_name")
    ids = request.GET.getlist("id")
    location_ids = request.GET.getlist("location_id")
    idrefs = request.GET.getlist("idref")
    latitude = request.GET.get("latitude")
    longitude = request.GET.get("longitude")
    radius = request.GET.get("radius")

    if all and random:
        return JsonResponse({"error": "Cannot use both all and random"}, status=400)

    if all and debug:
        return JsonResponse({"error": "Cannot use both all and debug"}, status=400)

    qs = SourceLocation.objects.all()
    if ids:
        numeric_ids = []
        source_uids = []
        for id in ids:
            if id.isdigit():
                numeric_ids.append(id)
            else:
                source_uids.append(id)
        qs = qs.filter(Q(id__in=numeric_ids) | Q(source_uid__in=source_uids))
    if location_ids:
        qs = qs.filter(matched_location__public_id__in=location_ids)
    if q:
        qs = qs.filter(name__icontains=q)
    if idrefs:
        idref_filter = ConcordanceIdentifier.filter_for_idrefs(idrefs)
        qs = qs.filter(
            concordances__in=ConcordanceIdentifier.objects.filter(idref_filter)
        )
    if source_names:
        qs = qs.filter(source_name__in=source_names)
    if unmatched:
        qs = qs.filter(matched_location=None)
    if matched:
        qs = qs.exclude(matched_location=None)
    if state:
        qs = qs.filter(import_json__address__state=state)
    if haspoint:
        qs = qs.exclude(latitude__isnull=True).exclude(longitude__isnull=True)
    if latitude and longitude and radius:
        for value in (latitude, longitude, radius):
            try:
                float(value)
            except ValueError:
                return JsonResponse(
                    {"error": "latitude/longitude/radius should be numbers"}, status=400
                )
        qs = qs.filter(
            point__dwithin=(
                Point(float(longitude), float(latitude)),
                Distance(m=float(radius)),
            )
        )
    if random:
        qs = qs.order_by("?")
    qs = qs.prefetch_related("concordances")

    if format == "map":
        get = request.GET.copy()
        get["format"] = "geojson"
        if "debug" in get:
            del get["debug"]
        return render(
            request, "api/search_locations_map.html", {"query_string": get.urlencode()}
        )

    def source_location_geojson(source_location: SourceLocation) -> Dict[str, object]:
        properties = source_location_json(source_location)
        id = properties.pop("id")
        return {
            "type": "Feature",
            "id": id,
            "properties": properties,
            "geometry": {
                "type": "Point",
                "coordinates": [
                    float(source_location.longitude),
                    float(source_location.latitude),
                ],
            }
            if source_location.latitude is not None
            and source_location.longitude is not None
            else None,
        }

    def source_location_json(source_location: SourceLocation) -> Dict[str, object]:
        return {
            "id": source_location.id,
            "source_uid": source_location.source_uid,
            "source_name": source_location.source_name,
            "name": source_location.name,
            "latitude": float(source_location.latitude)
            if source_location.latitude
            else None,
            "longitude": float(source_location.longitude)
            if source_location.longitude
            else None,
            "import_json": source_location.import_json,
            "matched_location": {
                "id": source_location.matched_location.public_id,
                "name": source_location.matched_location.name,
                "vial_url": request.build_absolute_uri(
                    "/admin/core/location/{}/change/".format(
                        source_location.matched_location.id
                    )
                ),
            }
            if source_location.matched_location
            else None,
            "created_at": source_location.created_at.isoformat(),
            "last_imported_at": source_location.last_imported_at.isoformat()
            if source_location.last_imported_at
            else None,
            "concordances": [str(c) for c in source_location.concordances.all()],
            "vial_url": request.build_absolute_uri(
                "/admin/core/sourcelocation/{}/change/".format(source_location.id)
            ),
        }

    formats = make_formats(source_location_json, source_location_geojson)
    formats["summary"] = OutputFormat(
        prepare_queryset=lambda qs: qs.only(
            "source_uid", "matched_location", "content_hash"
        ).prefetch_related(None),
        start=b"",
        transform=lambda l: {
            "source_uid": l.source_uid,
            "matched_location_id": "l{}".format(pid.from_int(l.matched_location_id))
            if l.matched_location_id is not None
            else None,
            "content_hash": l.content_hash,
        },
        transform_batch=lambda batch: batch,
        serialize=orjson.dumps,
        separator=b"\n",
        end=lambda qs: b"",
        content_type="text/plain",
    )

    if format not in formats:
        return JsonResponse({"error": "Invalid format"}, status=400)

    formatter = formats[format]

    qs = formatter.prepare_queryset(qs)

    stream_qs = qs[:size]
    if all:
        stream_qs = keyset_pagination_iterator(qs)

    stream = build_stream(
        qs, stream_qs, formatter, beeline_trace_name="search_source_locations_stream"
    )

    if debug:
        output = b"".join(stream())
        if formatter.content_type == "application/json":
            output = orjson.dumps(orjson.loads(output), option=orjson.OPT_INDENT_2)
        return render(
            request,
            "api/search_locations_debug.html",
            {
                "output": mark_safe(escape(output.decode("utf-8"))),
            },
        )

    return StreamingHttpResponse(stream(), content_type=formatter.content_type)


def filter_for_export(qs):
    # Filter down to locations that we think should be exported
    # to the public map on www.vaccinatethestates.com
    return qs.exclude(
        dn_latest_non_skip_report__planned_closure__lt=datetime.date.today()
    ).exclude(
        dn_latest_non_skip_report__availability_tags__slug__in=(
            "incorrect_contact_information",
            "location_permanently_closed",
            "may_be_a_vaccination_site_in_the_future",
            "not_open_to_the_public",
            "will_never_be_a_vaccination_site",
            "only_staff",
        )
    )
