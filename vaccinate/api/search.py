import json
from collections import namedtuple
from html import escape
from typing import Callable, Dict, Union

import beeline
from core.models import ConcordanceIdentifier, Location, SourceLocation, State
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

from .utils import jwt_auth, log_api_requests

OutputFormat = namedtuple(
    "OutputFormat", ("start", "transform", "separator", "end", "content_type")
)


@log_api_requests
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
    latitude = request.GET.get("latitude")
    longitude = request.GET.get("longitude")
    radius = request.GET.get("radius")
    if state:
        try:
            State.objects.get(abbreviation=state)
        except State.DoesNotExist:
            return JsonResponse({"error": "State does not exist"}, status=400)
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
    qs = location_json_queryset(qs)

    formats = make_formats(location_json, location_geojson)
    formats["v0preview"] = OutputFormat(
        start=(
            '{"usage": {"notice": "Please contact Vaccinate The States and let '
            "us know if you plan to rely on or publish this data. This "
            "data is provided with best-effort accuracy. If you are "
            "displaying this data, we expect you to display it responsibly. "
            'Please do not display it in a way that is easy to misread.",'
            '"contact": {"partnersEmail": "api@vaccinatethestates.com"}},'
            '"content": ['
        ),
        transform=lambda l: json.dumps(location_v0_json(l)),
        separator=",",
        end=lambda qs: "]}",
        content_type="application/json",
    )

    if format not in formats:
        return JsonResponse({"error": "Invalid format"}, status=400)

    formatter = formats[format]

    stream_qs = qs[:size]
    if all:
        stream_qs = keyset_pagination_iterator(qs)

    stream = _build_stream(
        qs, stream_qs, formatter, beeline_trace_name="search_locations_stream"
    )

    if debug:
        if all:
            return JsonResponse({"error": "Cannot use both all and debug"}, status=400)
        output = "".join(stream())
        if formatter.content_type == "application/json":
            output = json.dumps(json.loads(output), indent=2)
        return render(
            request,
            "api/search_locations_debug.html",
            {
                "output": mark_safe(escape(output)),
            },
        )

    return StreamingHttpResponse(stream(), content_type=formatter.content_type)


def _build_stream(qs, stream_qs, formatter, beeline_trace_name):
    trace_id = None
    parent_id = None
    bl = beeline.get_beeline()
    if bl:
        trace_id = bl.tracer_impl.get_active_trace_id()
        parent_id = bl.tracer_impl.get_active_span().id

    @beeline.traced(beeline_trace_name, trace_id=trace_id, parent_id=parent_id)
    def stream():
        if callable(formatter.start):
            yield formatter.start(qs)
        else:
            yield formatter.start
        started = False
        for location in stream_qs:
            if started and formatter.separator:
                yield formatter.separator
            started = True
            yield formatter.transform(location)
        if callable(formatter.end):
            yield formatter.end(qs)
        else:
            yield formatter.end

    return stream


def location_json_queryset(queryset: QuerySet[Location]) -> QuerySet[Location]:
    return (
        queryset.select_related(
            "state",
            "county",
            "location_type",
            "provider__provider_type",
        ).prefetch_related("concordances")
    ).only(
        "public_id",
        "name",
        "state__abbreviation",
        "latitude",
        "longitude",
        "location_type__name",
        "import_ref",
        "phone_number",
        "full_address",
        "city",
        "county__name",
        "google_places_id",
        "vaccinefinder_location_id",
        "vaccinespotter_location_id",
        "zip_code",
        "hours",
        "website",
        "preferred_contact_method",
        "provider__name",
        "provider__provider_type__name",
    )


def location_json(
    location: Location, include_soft_deleted: bool = False
) -> Dict[str, object]:
    data = {
        "id": location.public_id,
        "name": location.name,
        "state": location.state.abbreviation,
        "latitude": float(location.latitude),
        "longitude": float(location.longitude),
        "location_type": location.location_type.name,
        "import_ref": location.import_ref,
        "phone_number": location.phone_number,
        "full_address": location.full_address,
        "city": location.city,
        "county": location.county.name if location.county else None,
        "google_places_id": location.google_places_id,
        "vaccinefinder_location_id": location.vaccinefinder_location_id,
        "vaccinespotter_location_id": location.vaccinespotter_location_id,
        "zip_code": location.zip_code,
        "hours": location.hours,
        "website": location.website,
        "preferred_contact_method": location.preferred_contact_method,
        "provider": {
            "name": location.provider.name,
            "type": location.provider.provider_type.name,
        }
        if location.provider
        else None,
        "concordances": [str(c) for c in location.concordances.all()],
    }
    if include_soft_deleted:
        data["soft_deleted"] = location.soft_deleted
    return data


def location_geojson(location: Location) -> Dict[str, object]:
    properties = location_json(location)
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "Point",
            "coordinates": [float(location.longitude), float(location.latitude)],
        },
    }


def location_v0_json(location: Location) -> Dict[str, object]:
    return {
        "id": location.public_id,
        "name": location.name,
        "state": location.state.abbreviation,
        "latitude": float(location.latitude),
        "longitude": float(location.longitude),
        "location_type": location.location_type.name,
        "full_address": location.full_address,
        "city": location.city,
        "county": location.county.name if location.county else None,
        "zip_code": location.zip_code,
        "hours": location.hours,
        "website": location.website,
        "concordances": [str(c) for c in location.concordances.all()],
    }


def make_formats(json_convert, geojson_convert):
    return {
        "json": OutputFormat(
            start='{"results": [',
            transform=lambda l: json.dumps(json_convert(l)),
            separator=",",
            end=lambda qs: '], "total": TOTAL}'.replace("TOTAL", str(qs.count())),
            content_type="application/json",
        ),
        "geojson": OutputFormat(
            start='{"type": "FeatureCollection", "features": [',
            transform=lambda l: json.dumps(geojson_convert(l)),
            separator=",",
            end=lambda qs: "]}",
            content_type="application/json",
        ),
        "nlgeojson": OutputFormat(
            start="",
            transform=lambda l: json.dumps(geojson_convert(l)),
            separator="\n",
            end="",
            content_type="text/plain",
        ),
    }


@log_api_requests
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
        return {
            "type": "Feature",
            "properties": properties,
            "geometry": {
                "type": "Point",
                "coordinates": [
                    float(source_location.longitude)
                    if source_location.longitude is not None
                    else None,
                    float(source_location.latitude)
                    if source_location.latitude is not None
                    else None,
                ],
            },
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

    if format not in formats:
        return JsonResponse({"error": "Invalid format"}, status=400)

    formatter = formats[format]

    stream_qs = qs[:size]
    if all:
        stream_qs = keyset_pagination_iterator(qs)

    stream = _build_stream(
        qs, stream_qs, formatter, beeline_trace_name="search_source_locations_stream"
    )

    if debug:
        return render(
            request,
            "api/search_locations_debug.html",
            {
                "output": mark_safe(
                    escape(json.dumps(json.loads("".join(stream())), indent=2))
                ),
            },
        )

    return StreamingHttpResponse(stream(), content_type=formatter.content_type)
