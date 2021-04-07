from django.contrib import admin, messages
from django.db.models import Count, Exists, Max, Min, OuterRef, Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe
from reversion.models import Revision, Version
from reversion_compare.admin import CompareVersionAdmin as VersionAdmin

from .admin_actions import export_as_csv_action
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
    ReportReviewNote,
    ReportReviewTag,
    State,
)

# Simple models first
for model in (LocationType, ProviderType):
    admin.site.register(model, actions=[export_as_csv_action()])


class DynamicListDisplayMixin:
    def get_list_display(self, request):
        list_display = list(self.list_display)
        if "_extra" in request.GET:
            request.GET = request.GET.copy()
            extras = request.GET.getlist("_extra")
            list_display += extras
            request.GET.pop("_extra")
        return list_display


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "abbreviation", "fips_code")
    ordering = ("name",)
    actions = [export_as_csv_action()]


@admin.register(Provider)
class ProviderAdmin(DynamicListDisplayMixin, admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "main_url", "contact_phone_number", "provider_type")
    list_editable = ("main_url", "contact_phone_number", "provider_type")
    actions = [export_as_csv_action()]


@admin.register(County)
class CountyAdmin(DynamicListDisplayMixin, VersionAdmin):
    search_fields = ("name",)
    list_display = ("name", "state", "fips_code")
    list_filter = ("state",)
    readonly_fields = ("airtable_id",)
    ordering = ("name",)
    actions = [export_as_csv_action()]


def make_call_request_queue_action(reason):
    def add_to_call_request_queue(modeladmin, request, queryset):
        locations = list(queryset.exclude(do_not_call=True))
        num_do_not_call_locations = queryset.filter(do_not_call=True).count()
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
        message = "Added {} location{} to queue with reason: {}".format(
            len(locations), "s" if len(locations) == 1 else "", reason
        )
        if num_do_not_call_locations:
            message += '. Skipped {} location{} marked "do not call"'.format(
                num_do_not_call_locations, "s" if num_do_not_call_locations != 1 else ""
            )
        messages.success(request, message)

    return add_to_call_request_queue


class LocationInQueueFilter(admin.SimpleListFilter):
    title = "Currently queued"
    parameter_name = "currently_queued"

    def lookups(self, request, model_admin):
        return (
            ("no", "No"),
            ("yes", "Yes"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(
                Exists(CallRequest.objects.filter(location=OuterRef("pk"))),
            )
        if self.value() == "no":
            return queryset.filter(
                ~Exists(CallRequest.objects.filter(location=OuterRef("pk"))),
            )


class LocationDeletedFilter(admin.SimpleListFilter):
    title = "soft deleted"

    parameter_name = "soft_deleted"

    def lookups(self, request, model_admin):
        return (
            (None, "Not deleted"),
            ("deleted", "Deleted"),
            ("all", "All"),
        )

    def choices(self, cl):
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == lookup,
                "query_string": cl.get_query_string(
                    {
                        self.parameter_name: lookup,
                    },
                    [],
                ),
                "display": title,
            }

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.filter(soft_deleted=False)
        elif self.value() == "all":
            return queryset
        elif self.value() == "deleted":
            return queryset.filter(soft_deleted=True)


@admin.register(Location)
class LocationAdmin(DynamicListDisplayMixin, VersionAdmin):
    actions = [export_as_csv_action()]

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
    list_display_links = None
    list_display = (
        "summary",
        "public_id",
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
        LocationDeletedFilter,
        "do_not_call",
        "location_type",
        "state",
        "provider",
    )
    raw_id_fields = ("county", "provider", "duplicate_of")
    readonly_fields = ("public_id", "airtable_id", "import_json", "reports_history")

    def summary(self, obj):
        html = (
            '<a href="/admin/core/location/{}/change/"><strong>{}</strong></a>'.format(
                obj.id,
                escape(obj.name),
            )
        )
        if obj.do_not_call:
            html += "<br><strong>Do not call</strong>"
        if obj.do_not_call_reason:
            html += " " + obj.do_not_call_reason
        return mark_safe(html)

    summary.admin_order_field = "name"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "county", "state", "provider", "location_type"
        ).annotate(times_reported_count=Count("reports"))

    def times_reported(self, inst):
        return inst.times_reported_count

    times_reported.admin_order_field = "times_reported_count"

    def lookup_allowed(self, lookup, value):
        return True

    def reports_history(self, instance):
        return mark_safe(
            render_to_string(
                "admin/_reports_history.html",
                {
                    "location_id": instance.pk,
                    "reports_datetimes": [
                        d.isoformat()
                        for d in instance.reports.values_list("created_at", flat=True)
                    ],
                    "reports": instance.reports.select_related("reported_by")
                    .prefetch_related("availability_tags")
                    .order_by("-created_at"),
                },
            )
        )


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
    search_fields = ("external_id", "name", "email")
    list_display = ("external_id", "name", "report_count", "latest_report")
    list_filter = (ReporterProviderFilter, "auth0_role_names")
    actions = [export_as_csv_action()]

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

    readonly_fields = ("qa_summary",)

    def qa_summary(self, instance):
        return qa_summary(instance)

    qa_summary.short_description = "QA summary"


@admin.register(AvailabilityTag)
class AvailabilityTagAdmin(DynamicListDisplayMixin, admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "group", "notes", "slug", "disabled")
    list_filter = ("group", "disabled")
    actions = [export_as_csv_action()]


@admin.register(AppointmentTag)
class AppointmentTagAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "has_details")
    actions = [export_as_csv_action()]


class ReportReviewNoteInline(admin.StackedInline):
    model = ReportReviewNote
    extra = 1
    readonly_fields = ("created_at", "author")
    autocomplete_fields = ("tags",)

    def has_add_permission(self, request, obj):
        return True

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Report)
class ReportAdmin(DynamicListDisplayMixin, admin.ModelAdmin):
    search_fields = (
        "public_id",
        "location__public_id",
        "location__name",
        "reported_by__external_id",
        "reported_by__email",
    )
    list_display = (
        "state",
        "created_at",
        "public_id",
        "availability",
        "location",
        "appointment_tag",
        "reported_by",
        "created_at_utc",
    )
    list_display_links = ("created_at", "public_id")
    actions = [export_as_csv_action()]
    raw_id_fields = ("location", "reported_by", "call_request")
    list_filter = (
        "created_at",
        "appointment_tag",
        "location__state__abbreviation",
        ("airtable_json", admin.EmptyFieldListFilter),
    )

    readonly_fields = (
        "created_at_utc",
        "public_id",
        "airtable_id",
        "airtable_json",
        "qa_summary",
    )
    inlines = [ReportReviewNoteInline]
    ordering = ("-created_at",)

    def save_formset(self, request, form, formset, change):
        for form in formset.forms:
            form.instance.author = request.user
        formset.save()

    def state(self, instance):
        return instance.location.state.abbreviation

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("location__state", "reported_by", "appointment_tag")
            .prefetch_related("availability_tags")
        )

    def lookup_allowed(self, lookup, value):
        return True

    def qa_summary(self, instance):
        return qa_summary(instance.reported_by)

    qa_summary.short_description = "QA summary"


@admin.register(ReportReviewTag)
class ReportReviewTagAdmin(admin.ModelAdmin):
    search_fields = ("tag",)


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
    actions = [export_as_csv_action()]


@admin.register(CallRequestReason)
class CallRequestReasonAdmin(admin.ModelAdmin):
    list_display = ("short_reason", "long_reason")
    actions = [export_as_csv_action()]


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


class CallRequestQueueStatus(admin.SimpleListFilter):
    title = "Queue status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return (
            (None, "Ready to be assigned"),
            ("claimed", "Currently assigned"),
            ("scheduled", "Scheduled for future"),
            ("completed", "Completed"),
            ("all", "All"),
        )

    def choices(self, cl):
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == lookup,
                "query_string": cl.get_query_string(
                    {
                        self.parameter_name: lookup,
                    },
                    [],
                ),
                "display": title,
            }

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() is None:
            return queryset.filter(
                Q(vesting_at__lte=now)
                & Q(completed=False)
                & (Q(claimed_until__isnull=True) | Q(claimed_until__lte=now))
            )
        elif self.value() == "claimed":
            return queryset.filter(claimed_until__gt=now, completed=False)
        elif self.value() == "scheduled":
            return queryset.filter(vesting_at__gt=now, completed=False)
        elif self.value() == "completed":
            return queryset.filter(completed=True)
        elif self.value() == "all":
            return queryset


def make_call_request_bump_action(top_or_bottom):
    def modify_call_request_order(modeladmin, request, queryset):
        if top_or_bottom == "top":
            priority = CallRequest.objects.all().aggregate(m=Max("priority"))["m"] + 1
        elif top_or_bottom == "bottom":
            priority = CallRequest.objects.all().aggregate(m=Min("priority"))["m"] - 1
        else:
            assert False, "Must be 'top' or 'bottom'"
        num_affected = queryset.update(priority=priority)
        messages.success(
            request,
            "Updated priority on {}".format(num_affected),
        )

    modify_call_request_order.short_description = "Bump to {} of the queue".format(
        top_or_bottom
    )
    modify_call_request_order.__name__ = "bump_to_{}".format(top_or_bottom)
    return modify_call_request_order


@admin.register(CallRequest)
class CallRequestAdmin(DynamicListDisplayMixin, admin.ModelAdmin):
    search_fields = ("location__name", "location__public_id")
    list_display = (
        "location",
        "vesting_at",
        "claimed_by",
        "claimed_until",
        "call_request_reason",
        "priority",
    )
    list_filter = (
        CallRequestQueueStatus,
        "call_request_reason",
    )
    actions = [
        clear_claims,
        export_as_csv_action(),
        make_call_request_bump_action("top"),
        make_call_request_bump_action("bottom"),
    ]
    raw_id_fields = ("location", "claimed_by", "tip_report")

    def lookup_allowed(self, lookup, value):
        return True


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
    actions = [export_as_csv_action()]


class RevisionAdmin(admin.ModelAdmin):
    list_display = ("id", "date_created", "user", "comment")
    list_display_links = ("date_created",)
    list_select_related = ("user",)
    date_hierarchy = "date_created"
    ordering = ("-date_created",)
    list_filter = ("user", "comment")
    search_fields = ("user", "comment")
    raw_id_fields = ("user",)


admin.site.register(Revision, RevisionAdmin)


class VersionAdmin(admin.ModelAdmin):
    def comment(self, obj):
        return obj.revision.comment

    list_display = ("object_repr", "comment", "object_id", "content_type", "format")
    list_display_links = ("object_repr", "object_id")
    list_filter = ("content_type", "format")
    list_select_related = ("revision", "content_type")
    search_fields = ("object_repr", "serialized_data")
    raw_id_fields = ("revision",)


admin.site.register(Version, VersionAdmin)


def qa_summary(reporter):
    return mark_safe(
        render_to_string(
            "admin/_reporter_qa_summary.html",
            {
                "reporter": reporter,
                "recent_reports": reporter.reports.select_related("location")
                .prefetch_related("availability_tags")
                .order_by("-created_at")[:20],
                "recent_report_datetimes": [
                    d.isoformat()
                    for d in reporter.reports.values_list("created_at", flat=True)[:100]
                ],
                "report_count": reporter.reports.count(),
            },
        )
    )
