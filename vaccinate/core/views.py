import json
import os
import sys

import pkg_resources
from api import search as search_views
from api.export_mapbox import export_mapbox_preview
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import connection
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.test.client import RequestFactory
from reversion import get_registered_models

from .models import Location


def index(request):
    user = request.user
    if user.is_authenticated:
        return redirect("/admin/")
    else:
        return render(request, "index.html")


def healthcheck(request):
    cursor = connection.cursor()
    cursor.execute("SELECT version();")
    return JsonResponse(
        {
            "deployed_sha": os.environ.get("COMMIT_SHA"),
            "postgresql_version": cursor.fetchone()[0],
            "python_version": sys.version,
            "package_versions": {
                d.project_name: d.version
                for d in sorted(
                    pkg_resources.working_set, key=lambda d: d.project_name.lower()
                )
            },
            "reversion_models": [m._meta.label for m in get_registered_models()],
        }
    )


@login_required
@user_passes_test(lambda user: user.is_staff)
def location_search(request):
    return render(request, "location_search.html")


@login_required
@user_passes_test(lambda user: user.is_staff)
def location(request, public_id):
    location = get_object_or_404(Location, public_id=public_id)
    api_previews = {}
    rf = RequestFactory()
    for title, view_fn, url, transform in (
        (
            "Mapbox GeoJSON representation (for vaccinatethestates.com)",
            export_mapbox_preview,
            "/?raw=1&id=" + location.public_id,
            lambda d: d["geojson"][0],
        ),
        (
            "APIv0 (for api.vaccinatethestates.com)",
            search_views.search_locations,
            "/?format=v0preview&id=" + location.public_id,
            lambda d: d["content"][0],
        ),
        (
            "APIv0 GeoJSON (for api.vaccinatethestates.com)",
            search_views.search_locations,
            "/?format=v0preview-geojson&id=" + location.public_id,
            lambda d: d["features"][0],
        ),
    ):
        req = rf.get(url)
        req.skip_api_logging = True
        req.skip_jwt_auth = True
        res = view_fn(req)
        if hasattr(res, "streaming_content"):
            content = b"".join(res.streaming_content)
        else:
            content = res.content
        data = transform(json.loads(content))
        api_previews[title] = json.dumps(data, indent=4)

    # Come up with a timeline of source locations and reports
    availability_reports = (
        location.reports.all()
        .exclude(soft_deleted=True)
        .prefetch_related("availability_tags")
        .exclude(availability_tags__group="skip")
        .order_by("-created_at")
    )

    availability_source_locations = (
        location.matched_source_locations.all()
        .order_by("-last_imported_at")
        .exclude(import_json__availability=None)
    )

    vaccines_offered_reports = (
        location.reports.all()
        .exclude(soft_deleted=True)
        .prefetch_related("availability_tags")
        .exclude(availability_tags__group="skip")
        .exclude(vaccines_offered__isnull=True)
        .order_by("-created_at")
    )

    vaccines_offered_source_locations = (
        location.matched_source_locations.all()
        .order_by("-last_imported_at")
        .exclude(import_json__inventory=None)
    )

    availability_timeline = []
    for report in availability_reports:
        availability_timeline.append(
            {
                "type": "report",
                "report": report,
                "when": report.created_at,
            }
        )
    for source_location in availability_source_locations:
        availability_timeline.append(
            {
                "type": "source_location",
                "source_location": source_location,
                "when": source_location.last_imported_at,
            }
        )
    availability_timeline.sort(key=lambda r: r["when"], reverse=True)

    vaccines_offered_timeline = []
    for report in vaccines_offered_reports:
        vaccines_offered_timeline.append(
            {
                "type": "report",
                "report": report,
                "when": report.created_at,
            }
        )
    for source_location in vaccines_offered_source_locations:
        vaccines_offered_timeline.append(
            {
                "type": "source_location",
                "source_location": source_location,
                "when": source_location.last_imported_at,
            }
        )
    vaccines_offered_timeline.sort(key=lambda r: r["when"], reverse=True)

    return render(
        request,
        "location.html",
        {
            "location": location,
            "derived_availability_and_inventory": json.dumps(
                location.derive_availability_and_inventory()._asdict(),
                indent=4,
                default=lambda v: v.isoformat() if hasattr(v, "isoformat") else repr(v),
            ),
            "availability_timeline": availability_timeline,
            "vaccines_offered_timeline": vaccines_offered_timeline,
            "source_locations": location.matched_source_locations.order_by(
                "-created_at"
            ).prefetch_related("concordances"),
            "api_previews": api_previews.items(),
        },
    )
