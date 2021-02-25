from django.contrib import admin
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
    CallReport,
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


@admin.register(Reporter)
class ReporterAdmin(admin.ModelAdmin):
    search_fields = ("airtable_name", "auth0_name")
    list_display = ("airtable_name", "auth0_name", "auth0_role_name")
    list_filter = ("auth0_role_name",)


@admin.register(AvailabilityTag)
class AvailabilityTagAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "notes", "disabled")
    list_filter = ("disabled",)


@admin.register(AppointmentTag)
class AppointmentTagAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "has_details")


@admin.register(CallReport)
class CallReportAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "availability",
        "location",
        "report_source",
        "reported_by",
        "created_at",
    )
    raw_id_fields = ("location", "reported_by", "call_request")
    list_filter = ("created_at", "report_source")
    readonly_fields = ("airtable_id",)
    ordering = ("-created_at",)


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
