import json
from collections import namedtuple
from html import escape

import beeline
from core.models import ConcordanceIdentifier, Location, State
from core.utils import keyset_pagination_iterator
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance
from django.http import JsonResponse
from django.http.response import StreamingHttpResponse
from django.shortcuts import render
from django.utils.safestring import mark_safe

from .utils import log_api_requests, require_api_key_or_cookie_user

OutputFormat = namedtuple(
    "Format", ("start", "transform", "separator", "end", "content_type")
)


@log_api_requests
@require_api_key_or_cookie_user
@beeline.traced("search_locations")
def search_locations(request, on_request_logged):
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

    qs = Location.objects.filter(soft_deleted=False)
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
            point__distance_lt=(
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

    if format not in FORMATS:
        return JsonResponse({"error": "Invalid format"}, status=400)

    formatter = FORMATS[format]

    stream_qs = qs[:size]
    if all:
        stream_qs = keyset_pagination_iterator(qs)

    trace_id = None
    parent_id = None
    bl = beeline.get_beeline()
    if bl:
        trace_id = bl.tracer_impl.get_active_trace_id()
        parent_id = bl.tracer_impl.get_active_span().id

    @beeline.traced("search_locations_stream", trace_id=trace_id, parent_id=parent_id)
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


def location_json_queryset(queryset):
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


def location_json(location):
    return {
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


def location_geojson(location):
    properties = location_json(location)
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "Point",
            "coordinates": [float(location.longitude), float(location.latitude)],
        },
    }


FORMATS = {
    "json": OutputFormat(
        start='{"results": [',
        transform=lambda l: json.dumps(location_json(l)),
        separator=",",
        end=lambda qs: '], "total": TOTAL}'.replace("TOTAL", str(qs.count())),
        content_type="application/json",
    ),
    "geojson": OutputFormat(
        start='{"type": "FeatureCollection", "features": [',
        transform=lambda l: json.dumps(location_geojson(l)),
        separator=",",
        end=lambda qs: "]}",
        content_type="application/json",
    ),
    "nlgeojson": OutputFormat(
        start="",
        transform=lambda l: json.dumps(location_geojson(l)),
        separator="\n",
        end="",
        content_type="text/plain",
    ),
}
