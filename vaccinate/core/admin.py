import json

from django.contrib import admin, messages
from django.db.models import Count, Max
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

from .models import (
    AppointmentTag,
    AvailabilityTag,
    CallRequest,
    CallRequestReason,
    County,
    EvaReport,
    Location,
    LocationType,
    Provider,
    ProviderType,
    PublishedReport,
    Report,
    Reporter,
    State,
)

# Simple models first
for model in (LocationType, ProviderType, State):
    admin.site.register(model)


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "main_url", "contact_phone_number", "provider_type")
    list_editable = ("main_url", "contact_phone_number", "provider_type")


@admin.register(County)
class CountyAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "state", "fips_code")
    list_filter = ("state",)
    readonly_fields = ("airtable_id",)


def make_call_request_queue_action(reason):
    def add_to_call_request_queue(modeladmin, request, queryset):
        locations = list(queryset.all())
        now = timezone.now()
        reason_obj = CallRequestReason.objects.get(short_reason=reason)
        CallRequest.objects.bulk_create(
            [
                CallRequest(
                    location=location, vesting_at=now, call_request_reason=reason_obj
                )
                for location in locations
            ]
        )
        messages.success(
            request,
            "Added {} location{} to queue with reason: {}".format(
                len(locations), "s" if len(locations) == 1 else "", reason
            ),
        )

    return add_to_call_request_queue


class LocationInQueueFilter(admin.SimpleListFilter):
    title = "Currently queued"
    parameter_name = "currently_queued"

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return (
            ("no", "No"),
            ("yes", "Yes"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(call_requests__isnull=False)
        if self.value() == "no":
            return queryset.filter(call_requests__isnull=True)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.update(
            {
                "add_to_call_request_queue_{}".format(
                    reason.lower().replace(" ", "_")
                ): (
                    make_call_request_queue_action(reason),
                    "add_to_call_request_queue_{}".format(
                        reason.lower().replace(" ", "_")
                    ),
                    "Add to queue: {}".format(reason),
                )
                for reason in CallRequestReason.objects.values_list(
                    "short_reason", flat=True
                )
            }
        )
        return actions

    search_fields = ("name", "full_address")
    list_display = (
        "name",
        "times_reported",
        "full_address",
        "state",
        "county",
        "location_type",
        "provider",
        "soft_deleted",
    )
    list_filter = (
        LocationInQueueFilter,
        "location_type",
        "state",
        "provider",
        "soft_deleted",
    )
    raw_id_fields = ("county", "provider", "duplicate_of")
    readonly_fields = ("public_id", "airtable_id", "import_json")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(times_reported_count=Count("reports"))

    def times_reported(self, inst):
        return inst.times_reported_count

    times_reported.admin_order_field = "times_reported_count"


class ReporterProviderFilter(admin.SimpleListFilter):
    title = "Provider"
    parameter_name = "provider"

    def lookups(self, request, model_admin):
        return (("auth0", "Auth0"), ("airtable", "Airtable"))

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(external_id__startswith=self.value())
        else:
            return queryset


@admin.register(Reporter)
class ReporterAdmin(admin.ModelAdmin):
    list_display = ("external_id", "name", "report_count", "latest_report")
    list_filter = (ReporterProviderFilter, "auth0_role_name")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            reporter_report_count=Count("reports"),
            reporter_latest_report=Max("reports__created_at"),
        )

    def report_count(self, inst):
        return inst.reporter_report_count

    report_count.admin_order_field = "reporter_report_count"

    def latest_report(self, inst):
        return inst.reporter_latest_report

    latest_report.admin_order_field = "reporter_latest_report"

    readonly_fields = ("recent_calls",)

    def recent_calls(self, instance):
        return mark_safe(
            render_to_string(
                "admin/_reporter_recent_calls.html",
                {
                    "reporter": instance,
                    "recent_reports": instance.reports.order_by("-created_at")[:20],
                    "report_count": instance.reports.count(),
                },
            )
        )


@admin.register(AvailabilityTag)
class AvailabilityTagAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "group", "notes", "slug", "disabled")
    list_filter = ("group", "disabled")


@admin.register(AppointmentTag)
class AppointmentTagAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "has_details")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "test",
        "created_at",
        "availability",
        "location",
        "appointment_tag",
        "reported_by",
        "created_at_utc",
    )
    list_display_links = ("test", "created_at")
    raw_id_fields = ("location", "reported_by", "call_request")
    list_filter = (
        "created_at",
        "appointment_tag",
        "is_test_data",
        ("airtable_json", admin.EmptyFieldListFilter),
    )
    readonly_fields = (
        "created_at_utc",
        "public_id",
        "airtable_id",
        "airtable_json",
    )
    ordering = ("-created_at",)

    def test(self, instance):
        return instance.is_test_data

    test.boolean = True

    def lookup_allowed(self, lookup, value):
        "Enable all querystring lookups! Really powerful, and we trust our staff"
        return True


@admin.register(EvaReport)
class EvaReportAdmin(admin.ModelAdmin):
    list_display = (
        "location",
        "name_from_import",
        "has_vaccines",
        "hung_up",
        "valid_at",
    )
    raw_id_fields = ("location",)
    list_filter = ("valid_at", "has_vaccines")
    readonly_fields = ("airtable_id",)


@admin.register(CallRequestReason)
class CallRequestReasonAdmin(admin.ModelAdmin):
    list_display = ("short_reason", "long_reason")


def clear_claims(modeladmin, request, queryset):
    updated = queryset.exclude(claimed_by=None).update(
        claimed_by=None, claimed_until=None
    )
    messages.success(
        request,
        "Cleared claims for {} call request{}".format(
            updated, "s" if updated != 1 else ""
        ),
    )


@admin.register(CallRequest)
class CallRequestAdmin(admin.ModelAdmin):
    list_display = (
        "location",
        "vesting_at",
        "claimed_by",
        "claimed_until",
        "call_request_reason",
    )
    actions = [clear_claims]
    list_filter = ("call_request_reason",)
    raw_id_fields = ("location", "claimed_by", "tip_report")


@admin.register(PublishedReport)
class PublishedReportAdmin(admin.ModelAdmin):
    list_display = (
        "location",
        "appointment_tag",
        "reported_by",
        "valid_at",
        "created_at",
    )
    raw_id_fields = (
        "location",
        "reported_by",
        "reports",
        "eva_reports",
    )
