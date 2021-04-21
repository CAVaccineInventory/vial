import json
from html import escape

import beeline
from core.models import Location, State
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.safestring import mark_safe


@beeline.traced("search_locations")
def search_locations(request):
    format = request.GET.get("format") or "json"
    size = min(int(request.GET.get("size", "10")), 1000)
    q = (request.GET.get("q") or "").strip().lower()
    state = (request.GET.get("state") or "").upper()
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
    qs = location_json_queryset(qs)
    page_qs = qs[:size]
    json_results = lambda: {
        "results": [location_json(location) for location in page_qs],
        "total": qs.count(),
    }
    output = None
    if format == "geojson":
        output = {
            "type": "FeatureCollection",
            "features": [location_geojson(location) for location in qs],
        }

    else:
        output = json_results()
    if debug:
        return render(
            request,
            "api/search_locations_debug.html",
            {
                "json_results": mark_safe(escape(json.dumps(output, indent=2))),
            },
        )
    else:
        return JsonResponse(output)


def location_json_queryset(queryset):
    return queryset.select_related(
        "state", "county", "location_type", "provider__provider_type"
    )


def location_json(location):
    return {
        "id": location.public_id,
        "name": location.name,
        "state": location.state.abbreviation,
        "latitude": location.latitude,
        "longitude": location.longitude,
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
    }


def location_geojson(location):
    properties = location_json(location)
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "Point",
            "coordinates": [location.longitude, location.latitude],
        },
    }
