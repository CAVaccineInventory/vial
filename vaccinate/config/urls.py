import debug_toolbar
import django_sql_dashboard
from api import caller_views as caller_api_views
from api import export_mapbox as export_mapbox_views
from api import search as search_views
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
    path("api/submitReport", caller_api_views.submit_report),
    path(
        "api/submitReport/debug",
        api_views.api_debug_view(
            "api/submitReport",
            body_textarea=True,
            docs="/api/docs#post-apisubmitreport",
        ),
    ),
    path("api/requestCall", caller_api_views.request_call),
    path(
        "api/requestCall/debug",
        api_views.api_debug_view(
            "api/requestCall",
            body_textarea=True,
            default_body="{}",
            docs="/api/docs#post-apirequestcall",
        ),
    ),
    path("api/callerStats", caller_api_views.caller_stats),
    path(
        "api/callerStats/debug",
        api_views.api_debug_view(
            "api/callerStats", body_textarea=False, docs="/api/docs#post-apicallerstats"
        ),
    ),
    path("api/verifyToken", api_views.verify_token),
    path("api/searchLocations", search_views.search_locations),
    path("api/searchSourceLocations", search_views.search_source_locations),
    path("api/location/<public_id>/concordances", api_views.location_concordances),
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
    path("api/updateLocations", api_views.update_locations),
    path(
        "api/updateLocations/debug",
        api_views.api_debug_view(
            "api/updateLocations",
            use_jwt=False,
            body_textarea=True,
            default_body="{}",
            docs="/api/docs#post-apiupdatelocations",
        ),
    ),
    path("api/updateLocationConcordances", api_views.update_location_concordances),
    path(
        "api/updateLocationConcordances/debug",
        api_views.api_debug_view(
            "api/updateLocationConcordances",
            use_jwt=False,
            body_textarea=True,
            default_body="{}",
            docs="/api/docs#post-apiupdatelocationconcordances",
        ),
    ),
    path("api/updateSourceLocationMatch", api_views.update_source_location_match),
    path(
        "api/updateSourceLocationMatch/debug",
        api_views.api_debug_view(
            "api/updateSourceLocationMatch",
            use_jwt=False,
            body_textarea=True,
            default_body="{}",
            docs="/api/docs#post-apiupdatesourcelocationmatch",
        ),
    ),
    path(
        "api/createLocationFromSourceLocation",
        api_views.create_location_from_source_location,
    ),
    path(
        "api/createLocationFromSourceLocation/debug",
        api_views.api_debug_view(
            "api/createLocationFromSourceLocation",
            use_jwt=False,
            body_textarea=True,
            default_body="{}",
            docs="/api/docs#post-apicreatelocationfromsourcelocation",
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
    path("api/importTasks", api_views.import_tasks),
    path(
        "api/importTasks/debug",
        api_views.api_debug_view(
            "api/importTasks",
            use_jwt=False,
            body_textarea=True,
            docs="/api/docs#post-apiimporttasks",
        ),
    ),
    path("api/requestTask", api_views.request_task),
    path(
        "api/requestTask/debug",
        api_views.api_debug_view(
            "api/requestTask",
            use_jwt=True,
            body_textarea=True,
            default_body='{"task_type": "Potential duplicate"}',
            docs="/api/docs#post-apirequesttask",
        ),
    ),
    path("api/resolveTask", api_views.resolve_task),
    path(
        "api/resolveTask/debug",
        api_views.api_debug_view(
            "api/resolveTask",
            use_jwt=True,
            body_textarea=True,
            default_body='{"task_id": null}',
            docs="/api/docs#post-apiresolvetask",
        ),
    ),
    path("api/locationTypes", api_views.location_types),
    path("api/providerTypes", api_views.provider_types),
    path("api/taskTypes", api_views.task_types),
    path("api/availabilityTags", api_views.availability_tags),
    path("api/export", api_views.api_export),
    path("api/exportPreview/Locations.json", api_views.api_export_preview_locations),
    path("api/exportPreview/Providers.json", api_views.api_export_preview_providers),
    path("api/exportMapbox", export_mapbox_views.export_mapbox),
    path("api/exportMapboxPreview", export_mapbox_views.export_mapbox_preview),
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
