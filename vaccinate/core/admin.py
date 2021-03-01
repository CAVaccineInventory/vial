from django.contrib import admin
from django.db.models import Count
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.html import escape
import json
from .models import (
    LocationType,
    ProviderType,
    Provider,
    State,
    County,
    Location,
    Reporter,
    AvailabilityTag,
    AppointmentTag,
    Report,
    EvaReport,
    CallRequestReason,
    CallRequest,
    PublishedReport,
)

# Simple models first
for model in (LocationType, ProviderType, State):
    admin.site.register(model)


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "main_url", "provider_type")
    list_filter = ("provider_type",)


@admin.register(County)
class CountyAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "state", "fips_code")
    list_filter = ("state",)
    readonly_fields = ("airtable_id",)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    search_fields = ("name", "full_address")
    list_display = (
        "name",
        "times_called",
        "full_address",
        "state",
        "county",
        "location_type",
        "provider",
        "soft_deleted",
    )
    list_filter = ("location_type", "state", "provider", "soft_deleted")
    raw_id_fields = ("county", "provider", "duplicate_of")
    readonly_fields = ("airtable_id",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(times_called_count=Count("call_reports"))

    def times_called(self, inst):
        return inst.times_called_count

    times_called.admin_order_field = "times_called_count"


class CountryFilter(admin.SimpleListFilter):
    title = "Provider"  # or use _('country') for translated title
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
    list_display = ("external_id", "name", "call_count")
    list_filter = (CountryFilter,)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(reporter_call_count=Count("call_reports"))

    def call_count(self, inst):
        return inst.reporter_call_count

    call_count.admin_order_field = "reporter_call_count"

    readonly_fields = ("recent_calls",)

    def recent_calls(self, instance):
        return mark_safe(
            render_to_string(
                "admin/_reporter_recent_calls.html",
                {
                    "reporter": instance,
                    "recent_calls": instance.call_reports.order_by("-created_at")[:20],
                    "call_count": instance.call_reports.count(),
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
        "created_at",
        "availability",
        "location",
        "appointment_tag",
        "reported_by",
        "created_at",
    )
    raw_id_fields = ("location", "reported_by", "call_request")
    list_filter = (
        "created_at",
        "appointment_tag",
        ("airtable_json", admin.EmptyFieldListFilter),
    )
    exclude = ("airtable_json",)
    readonly_fields = ("airtable_id", "airtable_json_prettified")
    ordering = ("-created_at",)

    def lookup_allowed(self, lookup, value):
        "Enable all querystring lookups! Really powerful, and we trust our staff"
        return True

    def airtable_json_prettified(self, instance):
        return mark_safe(
            '<pre style="font-size: 0.8em">{}</pre>'.format(
                escape(json.dumps(instance.airtable_json, indent=2))
            )
        )

    airtable_json_prettified.short_description = "Airtable JSON"


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


@admin.register(CallRequest)
class CallRequestAdmin(admin.ModelAdmin):
    list_display = (
        "location",
        "vesting_at",
        "claimed_by",
        "claimed_until",
        "call_request_reason",
    )
    list_filter = ("call_request_reason",)
    raw_id_fields = ("claimed_by", "tip_report")


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
        "call_reports",
        "eva_reports",
    )
