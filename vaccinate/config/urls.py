import debug_toolbar
import django_sql_dashboard
from api import views as api_views
from auth0login.views import login, logout
from core import tool_views
from core import views as core_views
from django.conf import settings
from django.contrib import admin
from django.http.response import HttpResponsePermanentRedirect
from django.shortcuts import redirect
from django.urls import include, path

admin.site.site_title = "VIAL admin"
admin.site.index_title = "VIAL: Vaccine Information Archive and Library"

urlpatterns = [
    path("", core_views.index),
    path("healthcheck", core_views.healthcheck),
    path("logout", logout),
    path("dashboard/", include(django_sql_dashboard.urls)),
    path("api/docs", api_views.api_docs),
    path("api/submitReport", api_views.submit_report),
    path(
        "api/submitReport/debug",
        api_views.api_debug_view(
            "api/submitReport",
            body_textarea=True,
            docs="/api/docs#post-apisubmitreport",
        ),
    ),
    path("api/requestCall", api_views.request_call),
    path(
        "api/requestCall/debug",
        api_views.api_debug_view(
            "api/requestCall",
            body_textarea=True,
            default_body="{}",
            docs="/api/docs#post-apirequestcall",
        ),
    ),
    path("api/callerStats", api_views.caller_stats),
    path(
        "api/callerStats/debug",
        api_views.api_debug_view(
            "api/callerStats", body_textarea=False, docs="/api/docs#post-apicallerstats"
        ),
    ),
    path("api/verifyToken", api_views.verify_token),
    path("api/importLocations", api_views.import_locations),
    path(
        "api/importLocations/debug",
        api_views.api_debug_view(
            "api/importLocations",
            use_jwt=False,
            body_textarea=True,
            default_body="[]",
            docs="/api/docs#post-apiimportlocations",
        ),
    ),
    path("api/startImportRun", api_views.start_import_run),
    path(
        "api/startImportRun/debug",
        api_views.api_debug_view(
            "api/startImportRun",
            use_jwt=False,
            body_textarea=False,
            docs="/api/docs#post-apistartimportrun",
        ),
    ),
    path("api/importSourceLocations", api_views.import_source_locations),
    path(
        "api/importSourceLocations/debug",
        api_views.api_debug_view(
            "api/importSourceLocations",
            use_jwt=False,
            body_textarea=True,
            textarea_placeholder="Newline delimited JSON records",
            querystring_fields=["import_run_id"],
            docs="/api/docs#post-apiimportsourcelocationsimport_run_idx",
        ),
    ),
    path("api/importReports", api_views.import_reports),
    path(
        "api/importReports/debug",
        api_views.api_debug_view(
            "api/importReports",
            use_jwt=False,
            body_textarea=True,
            default_body="[]",
            docs="/api/docs#post-apiimportreports",
        ),
    ),
    path("api/locationTypes", api_views.location_types),
    path("api/providerTypes", api_views.provider_types),
    path("api/availabilityTags", api_views.availability_tags),
    path("api/export", api_views.api_export),
    path("api/export-preview/Locations.json", api_views.api_export_preview_locations),
    path("api/export-preview/Providers.json", api_views.api_export_preview_providers),
    path("api/export-mapbox/Locations.geojson", api_views.export_mapbox_geojson),
    path("api/export-mapbox/Locations.ndgeojson", api_views.export_mapbox_ndgeojson),
    path("api/location_metrics", api_views.location_metrics),
    path("api/counties/<state_abbreviation>", api_views.counties),
    path("", include("django.contrib.auth.urls")),
    path("", include("social_django.urls")),
    path("admin_tools/", include("admin_tools.urls")),
    path("admin/docs/", lambda r: redirect("/admin/docs/models/", permanent=False)),
    path("admin/docs/", include("django.contrib.admindocs.urls")),
    path(
        # I renamed this model
        "admin/core/callreport/",
        lambda r: HttpResponsePermanentRedirect("/admin/core/report/"),
    ),
    # I shipped code that sent the wrong URLs to a Discord bot in #96
    path(
        "admin/core/report/change/<int:id>/",
        lambda r, id: HttpResponsePermanentRedirect(
            "/admin/core/report/{}/change/".format(id)
        ),
    ),
    path("admin/commands/", lambda r: redirect("/admin/tools/")),
    path("admin/tools/", tool_views.admin_tools),
    path("admin/merge-locations/", tool_views.merge_locations),
    path("admin/edit-location/<public_id>/", tool_views.edit_location_redirect),
    path("admin/bulk-delete-reports/", tool_views.bulk_delete_reports),
    path("admin/bulk-delete-call-requests/", tool_views.bulk_delete_call_requests),
    path("admin/import-call-requests/", tool_views.import_call_requests),
    # Over-ride Django admin default login/logout
    path("admin/login/", login),
    path("admin/logout/", lambda r: redirect("/logout", permanent=False)),
    path("admin/", admin.site.urls),
] + ([path("__debug__/", include(debug_toolbar.urls))] if settings.DEBUG else [])
