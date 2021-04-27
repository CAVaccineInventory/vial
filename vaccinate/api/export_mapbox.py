import json

import beeline
import requests
from core.models import Location
from django.http import HttpResponse, JsonResponse
from django.utils.html import escape
from django.views.decorators.csrf import csrf_exempt


def _mapbox_locations_queryset():
    locations = (
        Location.objects.all()
        .select_related(
            "location_type",
            "dn_latest_non_skip_report",
            "dn_latest_non_skip_report__appointment_tag",
            "county",
            "state",
            "provider",
        )
        .prefetch_related("dn_latest_non_skip_report__availability_tags")
        .only(
            "public_id",
            "name",
            "location_type__name",
            "website",
            "full_address",
            "county__name",
            "county__vaccine_reservations_url",
            "state__abbreviation",
            "phone_number",
            "google_places_id",
            "vaccinefinder_location_id",
            "vaccinespotter_location_id",
            "hours",
            "dn_latest_non_skip_report__planned_closure",
            "dn_latest_non_skip_report__public_notes",
            "dn_latest_non_skip_report__appointment_tag__slug",
            "dn_latest_non_skip_report__appointment_tag__name",
            "dn_latest_non_skip_report__appointment_details",
            "dn_latest_non_skip_report__location_id",
            "dn_latest_non_skip_report__created_at",
            "dn_latest_non_skip_report__vaccines_offered",
            "dn_latest_non_skip_report__restriction_notes",
            "website",
            "provider__appointments_url",
            "longitude",
            "latitude",
        )
    )
    locations = locations.exclude(soft_deleted=True)
    return locations


def _mapbox_geojson(location):
    properties = {
        "id": location.public_id,
        "name": location.name,
        "location_type": location.location_type.name,
        "website": location.website,
        "address": location.full_address,
        "county": location.county.name if location.county else None,
        "state_abbreviation": location.state.abbreviation,
        "phone_number": location.phone_number,
        "google_places_id": location.google_places_id,
        "vaccinefinder_location_id": location.vaccinefinder_location_id,
        "vaccinespotter_location_id": location.vaccinespotter_location_id,
        "hours": location.hours,
    }
    if location.dn_latest_non_skip_report:
        report = location.dn_latest_non_skip_report
        properties.update(
            {
                "public_notes": report.public_notes,
                "appointment_method": report.appointment_tag.name,
                "appointment_details": report.full_appointment_details(location),
                "latest_contact": report.created_at.isoformat(),
                "availability_tags": [
                    {"name": tag.name, "group": tag.group, "slug": tag.slug}
                    for tag in report.availability_tags.all()
                ],
                "planned_closure": report.planned_closure.isoformat()
                if report.planned_closure
                else None,
                "vaccines_offered": report.vaccines_offered,
                "restriction_notes": report.restriction_notes,
            }
        )
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "Point",
            "coordinates": [location.longitude, location.latitude],
        },
    }


def export_mapbox_preview(request):
    locations = _mapbox_locations_queryset()
    # For debugging: shows the GeoJSON we would send to Mapbox
    ids = request.GET.getlist("id")
    if ids:
        locations = locations.filter(public_id__in=ids)
    # Maximum of 20 for the debugging preview
    locations = locations.order_by("-id")[:20]
    preview = {"geojson": [_mapbox_geojson(location) for location in locations]}
    # Defaults to wrapping in HTML so you can see Django debug toolbar
    # Use ?raw=1 to get back a raw JSON response
    if request.GET.get("raw"):
        return JsonResponse(preview)
    raw_url = request.build_absolute_uri()
    if "?" not in raw_url:
        raw_url += "?raw=1"
    else:
        raw_url += "&raw=1"
    return HttpResponse(
        """
        <html><head><title>Mapbox preview</title></head>
        <body>
        <h1>Mapbox preview</h1>
        <pre>{}</pre>
        <p><a href="{}">Raw JSON</a></p>
        </body></html>
    """.format(
            escape(json.dumps(preview, indent=4)), escape(raw_url)
        ).strip()
    )


@csrf_exempt
def export_mapbox(request):
    if request.method != "POST":
        return JsonResponse(
            {"error": "Must be a POST"},
            status=400,
        )

    locations = _mapbox_locations_queryset()

    post_data = ""
    for location in locations.all():
        post_data += json.dumps(_mapbox_geojson(location)) + "\n"

    access_token = settings.MAPBOX_ACCESS_TOKEN
    if not access_token:
        return JsonResponse(
            {
                "upload": f"Would upload {len(post_data)} bytes",
            }
        )

    with beeline.tracer(name="geojson-upload"):
        upload_resp = requests.put(
            f"https://api.mapbox.com/tilesets/v1/sources/calltheshots/vial?access_token={access_token}",
            files={"file": post_data},
            timeout=30,
        )
        upload_resp.raise_for_status()

    with beeline.tracer(name="geojson-publish"):
        publish_resp = requests.post(
            f"https://api.mapbox.com/tilesets/v1/calltheshots.vaccinatethestates/publish?access_token={access_token}",
            timeout=30,
        )
        publish_resp.raise_for_status()

    return JsonResponse(
        {
            "upload": upload_resp.json(),
            "publish": publish_resp.json(),
        }
    )
