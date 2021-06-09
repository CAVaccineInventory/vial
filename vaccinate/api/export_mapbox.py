import beeline
import orjson
import requests
from api.utils import log_api_requests, require_api_key
from core.expansions import VaccineFinderInventoryExpansion
from core.models import Location
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils.html import escape
from django.views.decorators.csrf import csrf_exempt

from .search import filter_for_export


def _mapbox_locations_queryset():
    qs = (
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
        .exclude(soft_deleted=True)
    )
    return filter_for_export(qs)


def _mapbox_geojson(location, expansion):
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
    report = None
    if location.dn_latest_non_skip_report:
        report = location.dn_latest_non_skip_report
        properties.update(
            {
                "public_notes": report.public_notes,
                "appointment_method": report.appointment_tag.name,
                "appointment_details": report.full_appointment_details(location),
                "latest_contact": report.created_at.isoformat(),
                "planned_closure": report.planned_closure.isoformat()
                if report.planned_closure
                else None,
                "restriction_notes": report.restriction_notes,
            }
        )
        tag_slugs = {tag.slug for tag in report.availability_tags.all()}
        if "appointments_available" in tag_slugs:
            properties["available_appointments"] = True
            properties["accepts_appointments"] = True
        if "appointments_or_walkins" in tag_slugs or "walk_ins_only" in tag_slugs:
            properties["available_walkins"] = True
            properties["accepts_walkins"] = True
        if (
            "appointment_required" in tag_slugs
            or "appointments_or_walkins" in tag_slugs
        ):
            properties["accepts_appointments"] = True

    # vaccine info comes from vaccinefinder if available, falls back on report
    vaccinefinder_inventory = expansion.expand([properties])[properties["id"]]
    vaccines_offered = None
    if vaccinefinder_inventory:
        vaccines_offered = vaccinefinder_inventory
    elif report:
        vaccines_offered = report.vaccines_offered

    fidelity = 0
    for property, vaccine_name in (
        ("vaccine_moderna", "Moderna"),
        ("vaccine_pfizer", "Pfizer"),
        ("vaccine_jj", "Johnson & Johnson"),
    ):
        if vaccines_offered and vaccine_name in vaccines_offered:
            properties[property] = True
            fidelity = 1

    properties["fidelity"] = fidelity

    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "Point",
            "coordinates": [float(location.longitude), float(location.latitude)],
        },
    }


def export_mapbox_preview(request):
    # For debugging: shows the GeoJSON we would send to Mapbox. Also
    # used by our unit tests.
    locations = _mapbox_locations_queryset()
    ids = request.GET.getlist("id")
    if ids:
        locations = locations.filter(public_id__in=ids)
    # Maximum of 20 for the debugging preview
    locations = locations.order_by("-id")[:20]

    expansion = VaccineFinderInventoryExpansion(load_all=not ids)

    preview = {
        "geojson": [_mapbox_geojson(location, expansion) for location in locations]
    }
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
            escape(orjson.dumps(preview, option=orjson.OPT_INDENT_2).decode("utf-8")),
            escape(raw_url),
        ).strip()
    )


@require_api_key
@log_api_requests
@csrf_exempt
def export_mapbox(request, on_request_logged):
    if request.method != "POST":
        return JsonResponse(
            {"error": "Must be a POST"},
            status=400,
        )

    locations = _mapbox_locations_queryset()
    expansion = VaccineFinderInventoryExpansion(load_all=True)

    post_data = []
    for location in locations.all():
        post_data.append(
            orjson.dumps(
                _mapbox_geojson(location, expansion), option=orjson.OPT_APPEND_NEWLINE
            )
        )

    access_token = settings.MAPBOX_ACCESS_TOKEN
    if not access_token:
        return JsonResponse(
            {
                "upload": f"Would upload {sum([len(x) for x in post_data])} bytes",
            }
        )

    with beeline.tracer(name="geojson-upload"):
        upload_resp = requests.put(
            f"https://api.mapbox.com/tilesets/v1/sources/calltheshots/vial?access_token={access_token}",
            files={"file": b"".join(post_data)},
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
