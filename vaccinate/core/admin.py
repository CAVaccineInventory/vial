import datetime

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.models import LogEntry
from django.db.models import Count, Exists, Max, Min, OuterRef, Q
from django.http import HttpResponseRedirect
from django.template.loader import render_to_string
from django.utils import dateformat, timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe
from reversion.models import Revision, Version
from reversion_compare.admin import CompareVersionAdmin

from .admin_actions import export_as_csv_action
from .admin_filters import DateYesterdayFieldListFilter
from .models import (
    AppointmentTag,
    AvailabilityTag,
    CallRequest,
    CallRequestReason,
    County,
    EvaReport,
    ImportRun,
    Location,
    LocationType,
    Provider,
    ProviderPhase,
    ProviderType,
    Report,
    Reporter,
    ReportReviewNote,
    ReportReviewTag,
    State,
)

# Simple models first
for model in (LocationType, ProviderType, ProviderPhase):
    admin.site.register(
        model, actions=[export_as_csv_action()], search_fields=("name",)
    )


@admin.register(ImportRun)
class ImportRunAdmin(admin.ModelAdmin):
    list_display = ("created_at", "api_key")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
class ProviderAdmin(DynamicListDisplayMixin, CompareVersionAdmin):
    save_on_top = True
    search_fields = ("name",)
    list_display = (
        "public_id",
        "name",
        "main_url",
        "contact_phone_number",
        "provider_type",
    )
    list_display_links = ("public_id", "name")
    actions = [export_as_csv_action()]
    autocomplete_fields = ("phases",)
    readonly_fields = ("airtable_id", "public_id", "import_json")


@admin.register(County)
class CountyAdmin(DynamicListDisplayMixin, CompareVersionAdmin):
    save_on_top = True
    search_fields = ("name",)
    list_display = (
        "name",
        "state",
        "vaccine_info_url",
        "short_public_notes",
        "age_floor_without_restrictions",
        "fips_code",
    )
    list_filter = ("state",)
    readonly_fields = ("airtable_id",)
    ordering = ("name",)
    actions = [export_as_csv_action()]

    def short_public_notes(self, obj):
        return (
            obj.public_notes
            if (obj.public_notes is None or len(obj.public_notes) < 50)
            else (obj.public_notes[:47] + "..")
        )

    short_public_notes.short_description = "Public Notes"


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


class SoftDeletedFilter(admin.SimpleListFilter):
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
class LocationAdmin(DynamicListDisplayMixin, CompareVersionAdmin):
    save_on_top = True
    actions = [
        export_as_csv_action(),
        export_as_csv_action(
            specific_columns={
                "Name": "name",
                "Phone number": "phone_number",
                "Website": "website",
                "Location ID": "public_id",
            },
            suffix="phone_website",
            description="Export CSV with phone and website info",
        ),
    ]
    fieldsets = (
        (
            None,
            {"fields": ("scooby_report_link",)},
        ),
        (
            None,
            {
                "fields": (
                    "name",
                    "location_type",
                    "phone_number",
                    "full_address",
                    "street_address",
                    "city",
                    "state",
                    "zip_code",
                    "county",
                    "latitude",
                    "longitude",
                    "hours",
                    "website",
                    "vaccinespotter_location_id",
                    "vaccinefinder_location_id",
                    "preferred_contact_method",
                    "provider",
                    "internal_notes",
                )
            },
        ),
        ("Actions", {"fields": ("request_a_call",)}),
        ("Reports", {"fields": ("reports_history",)}),
        (
            "Advanced Actions",
            {
                "classes": ("collapse",),
                "fields": (
                    "do_not_call",
                    "do_not_call_reason",
                    "soft_deleted",
                    "soft_deleted_because",
                    "duplicate_of",
                ),
            },
        ),
        (
            "Data Fields",
            {
                "classes": ("collapse",),
                "fields": (
                    "provenance",
                    "public_id",
                    "airtable_id",
                    "import_ref",
                    "import_json",
                    "dn_latest_report",
                    "dn_latest_report_including_pending",
                    "dn_latest_yes_report",
                    "dn_latest_skip_report",
                    "dn_latest_non_skip_report",
                    "dn_skip_report_count",
                    "dn_yes_report_count",
                ),
            },
        ),
    )

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

    search_fields = ("name", "full_address", "public_id")
    list_display_links = None
    list_display = (
        "summary",
        "public_id",
        "times_reported",
        "scooby_report_link",
        "request_a_call",
        "full_address",
        "state",
        "county",
        "preferred_contact_method",
        "location_type",
        "provider",
        "latest_non_skip_report_date",
        "dn_skip_report_count",
    )
    list_filter = (
        LocationInQueueFilter,
        SoftDeletedFilter,
        "do_not_call",
        "preferred_contact_method",
        "location_type",
        "state",
        "provider",
    )
    raw_id_fields = ("county", "provider", "duplicate_of")
    readonly_fields = (
        "scooby_report_link",
        "request_a_call",
        "public_id",
        "airtable_id",
        "import_json",
        "reports_history",
        "dn_latest_report",
        "dn_latest_report_including_pending",
        "dn_latest_yes_report",
        "dn_latest_skip_report",
        "dn_latest_non_skip_report",
        "dn_skip_report_count",
        "dn_yes_report_count",
    )

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
        if obj.soft_deleted:
            html += '<br><strong style="color: red">Soft deleted</strong>'
        return mark_safe(html)

    summary.admin_order_field = "name"

    def request_a_call(self, obj):
        return mark_safe(
            '<strong><a href="/admin/core/callrequest/add/?location={}" target="_blank">Request a call</a></strong>'.format(
                obj.id
            )
        )

    def scooby_report_link(self, obj):
        if settings.SCOOBY_URL:
            return mark_safe(
                '<a href="{}?location_id={}" target="_blank"><span class="primary-button">File report</span></a>'.format(
                    settings.SCOOBY_URL, obj.public_id
                )
            )
        else:
            return ""

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "county", "state", "provider", "location_type", "dn_latest_non_skip_report"
        ).annotate(times_reported_count=Count("reports"))

    def times_reported(self, obj):
        return obj.times_reported_count

    times_reported.admin_order_field = "times_reported_count"

    def latest_non_skip_report_date(self, obj):
        if obj.dn_latest_non_skip_report:
            return obj.dn_latest_non_skip_report.created_at

    latest_non_skip_report_date.admin_order_field = (
        "dn_latest_non_skip_report__created_at"
    )

    def lookup_allowed(self, lookup, value):
        return True

    def reports_history(self, obj):
        reports = obj.reports.exclude(soft_deleted=True)
        return mark_safe(
            render_to_string(
                "admin/_reports_history.html",
                {
                    "location_id": obj.pk,
                    "reports_datetimes": [
                        d.isoformat()
                        for d in reports.values_list("created_at", flat=True)
                    ],
                    "reports": reports.select_related("reported_by")
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

    def report_count(self, obj):
        return obj.reporter_report_count

    report_count.admin_order_field = "reporter_report_count"

    def latest_report(self, obj):
        return obj.reporter_latest_report

    latest_report.admin_order_field = "reporter_latest_report"

    readonly_fields = ("qa_summary",)

    def qa_summary(self, obj):
        return qa_summary(obj)

    qa_summary.short_description = "QA summary"

    def has_change_permission(self, request, obj=None):
        return False


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


def claim_reports(modeladmin, request, queryset):
    count = queryset.update(claimed_by=request.user, claimed_at=timezone.now())
    messages.success(
        request,
        "You claimed {} report{}".format(count, "s" if count != 1 else ""),
    )


def unclaim_reports_you_have_claimed(modeladmin, request, queryset):
    count = queryset.filter(claimed_by=request.user).update(
        claimed_by=None, claimed_at=None
    )
    messages.success(
        request,
        "You unclaimed {} report{}".format(count, "s" if count != 1 else ""),
    )


def bulk_approve_reports(modeladmin, request, queryset):
    pending_review = queryset.filter(is_pending_review=True)
    # Add a comment to them all
    approved = ReportReviewTag.objects.get(tag="Approved")
    for report in pending_review:
        note = report.review_notes.create(author=request.user)
        note.tags.add(approved)
    count = pending_review.count()
    pending_review.update(is_pending_review=False)
    messages.success(
        request,
        "Approved {} report{}".format(count, "s" if count != 1 else ""),
    )


class ClaimFilter(admin.SimpleListFilter):
    title = "Claim status"

    parameter_name = "claim_status"

    def lookups(self, request, model_admin):
        return (
            ("you", "Claimed by you"),
            ("anyone", "Claimed by anyone"),
            ("unclaimed", "Unclaimed"),
        )

    def queryset(self, request, queryset):
        if self.value() == "you":
            return queryset.filter(claimed_by=request.user)
        elif self.value() == "anyone":
            return queryset.exclude(claimed_by=None)
        elif self.value() == "unclaimed":
            return queryset.filter(claimed_by=None)


@admin.register(Report)
class ReportAdmin(DynamicListDisplayMixin, admin.ModelAdmin):
    save_on_top = True
    change_form_template = "admin/change_report.html"
    search_fields = (
        "public_id",
        "location__public_id",
        "location__name",
        "reported_by__external_id",
        "reported_by__email",
        "reported_by__name",
    )
    list_display = (
        "id_and_note",
        "created_at_short",
        "public_id",
        "availability",
        "is_pending_review",
        "claimed_by",
        "location",
        "appointment_tag",
        "reporter",
        "created_at_utc",
    )
    autocomplete_fields = ("availability_tags", "claimed_by")
    list_display_links = ("id", "created_at", "public_id")
    actions = [
        claim_reports,
        unclaim_reports_you_have_claimed,
        bulk_approve_reports,
        export_as_csv_action(
            customize_queryset=lambda qs: qs.prefetch_related("availability_tags"),
            extra_columns=["availability_tags"],
            extra_columns_factory=lambda row: [
                ", ".join(t.name for t in row.availability_tags.all())
            ],
        ),
    ]
    raw_id_fields = ("location", "reported_by", "call_request")
    list_filter = (
        "is_pending_review",
        ClaimFilter,
        SoftDeletedFilter,
        ("created_at", DateYesterdayFieldListFilter),
        "availability_tags",
        "reported_by__auth0_role_names",
        "appointment_tag",
        ("airtable_json", admin.EmptyFieldListFilter),
    )

    readonly_fields = (
        "county_summary",
        "created_at",
        "claimed_at",
        "created_at_utc",
        "originally_pending_review",
        "public_id",
        "airtable_id",
        "airtable_json",
        "qa_summary",
    )
    inlines = [ReportReviewNoteInline]
    ordering = ("-created_at",)

    def id_and_note(self, obj):
        html = '<a href="/admin/core/report/{}/change/"><strong>{}</strong></a>'.format(
            obj.id,
            obj.id,
        )
        if obj.soft_deleted:
            html += '<br><strong style="color: red">Soft deleted</strong>'
        return mark_safe(html)

    id_and_note.short_description = "id"
    id_and_note.admin_order_field = "id"

    def created_at_short(self, obj):
        return mark_safe(
            dateformat.format(timezone.localtime(obj.created_at), "j M g:iA e")
            .replace("PM", "pm")
            .replace("AM", "am")
            .replace(" ", "&nbsp;")
        )

    created_at_short.short_description = "created"
    created_at_short.admin_order_field = "created_at"

    def reporter(self, obj):
        return mark_safe(
            "<strong>{}</strong><br>{}".format(
                escape(obj.reported_by.name),
                escape(obj.reported_by.auth0_role_names or ""),
            )
        )

    reporter.admin_order_field = "reported_by"

    def has_delete_permission(self, request, obj=None):
        # Soft delete only
        return False

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_save_and_add_another"] = False
        extra_context[
            "your_pending_claimed_reports"
        ] = request.user.claimed_reports.filter(
            is_pending_review=True, soft_deleted=False
        ).count()
        return super().change_view(
            request,
            object_id,
            form_url,
            extra_context=extra_context,
        )

    def response_change(self, request, obj):
        res = super().response_change(request, obj)
        if "_review_next" in request.POST:
            next_to_review = request.user.claimed_reports.filter(
                is_pending_review=True, soft_deleted=False
            ).first()
            if next_to_review:
                return HttpResponseRedirect(
                    "/admin/core/report/{}/change/".format(next_to_review.pk)
                )
        else:
            return res

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        for instance in instances:
            instance.author = request.user
            instance.save()
        formset.save_m2m()
        # Does a review posted created within last 5 seconds have the 'approved' tag?
        recently_added_review = form.instance.review_notes.filter(
            created_at__gte=timezone.now() - datetime.timedelta(seconds=5)
        ).last()
        if (
            recently_added_review is not None
            and recently_added_review.tags.filter(tag="Approved").exists()
            and form.instance.is_pending_review
        ):
            obj = form.instance
            obj.is_pending_review = False
            obj.save()
            obj.location.update_denormalizations()

    def save_model(self, request, obj, form, change):
        if obj.claimed_by and "claimed_by" in form.changed_data:
            obj.claimed_at = timezone.now()
        super().save_model(request, obj, form, change)

    def state(self, obj):
        return obj.location.state.abbreviation

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("location__state", "reported_by", "appointment_tag")
            .prefetch_related("availability_tags")
        )

    def lookup_allowed(self, lookup, value):
        return True

    def county_summary(self, obj):
        return mark_safe(
            render_to_string(
                "admin/_county_summary.html",
                {
                    "county": obj.location.county,
                },
            )
        )

    def qa_summary(self, obj):
        return qa_summary(obj.reported_by)

    qa_summary.short_description = "QA summary"


@admin.register(ReportReviewTag)
class ReportReviewTagAdmin(admin.ModelAdmin):
    search_fields = ("tag",)


@admin.register(ReportReviewNote)
class ReportReviewNoteAdmin(admin.ModelAdmin):
    list_display_links = None
    list_display = (
        "created_at",
        "author",
        "report_summary",
        "note_tags",
        "note",
    )
    readonly_fields = ("created_at", "author", "tags")
    ordering = ("-created_at",)

    def get_actions(self, request):
        return []

    def queryset(self, request, queryset):
        return queryset.select_related("report__reported_by", "report__location")

    def report_summary(self, obj):
        return mark_safe(
            '<strong>Report <a href="/admin/core/report/{}/change/">{}</a></strong><br>by {}<br>on {}'.format(
                obj.report_id,
                obj.report.public_id,
                escape(obj.report.reported_by.name),
                dateformat.format(
                    timezone.localtime(obj.report.created_at), "jS M Y g:i:s A e"
                ),
            )
            + '<br>On <a href="/admin/core/location/{}/change/">{}</a>'.format(
                obj.report.location_id, escape(obj.report.location.name)
            )
        )

    def note_tags(self, obj):
        return ", ".join([t.tag for t in obj.tags.all()])

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


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
            "Updated priority within group on {}".format(num_affected),
        )

    modify_call_request_order.short_description = (
        "Bump to {} of their priority group".format(top_or_bottom)
    )
    modify_call_request_order.__name__ = "bump_to_{}".format(top_or_bottom)
    return modify_call_request_order


def make_call_request_move_to_priority_group(priority_group):
    group_id, group_name = priority_group

    def modify_group_action(modeladmin, request, queryset):
        num_affected = queryset.update(priority_group=group_id)
        messages.success(
            request,
            "Moved {} items to group {}".format(num_affected, group_name),
        )

    modify_group_action.short_description = "Move to priority group {}".format(
        group_name
    )
    modify_group_action.__name__ = "move_to_group_{}".format(group_id)
    return modify_group_action


@admin.register(CallRequest)
class CallRequestAdmin(DynamicListDisplayMixin, admin.ModelAdmin):
    search_fields = ("location__name", "location__public_id")
    list_display = (
        "location",
        "state",
        "priority_group",
        "queue_status",
        "call_request_reason",
        "completed_at",
    )
    list_filter = (
        CallRequestQueueStatus,
        "priority_group",
        "call_request_reason",
    )
    actions = [
        clear_claims,
        export_as_csv_action(),
        make_call_request_bump_action("top"),
        make_call_request_bump_action("bottom"),
    ] + [
        make_call_request_move_to_priority_group(priority_group)
        for priority_group in CallRequest.PriorityGroup.choices
    ]
    raw_id_fields = ("location", "claimed_by", "tip_report")

    def state(self, obj):
        return obj.location.state.abbreviation

    def lookup_allowed(self, lookup, value):
        return True

    def queue_status(self, obj):
        now = timezone.now()
        if obj.completed:
            return "Completed"
        if obj.claimed_by_id and obj.claimed_until > now:
            return "Assigned to {} until {}".format(
                obj.claimed_by,
                dateformat.format(
                    timezone.localtime(obj.claimed_until), "jS M Y g:i:s A e"
                ),
            )
        if obj.vesting_at > now:
            return mark_safe(
                "<em>Scheduled</em> for {}".format(
                    dateformat.format(
                        timezone.localtime(obj.vesting_at), "jS M Y g:i:s A e"
                    ),
                )
            )
        return "Available"


# NOT CURRENTLY USED
# See https://github.com/CAVaccineInventory/vial/issues/179#issuecomment-815353624
#
# @admin.register(PublishedReport)
# class PublishedReportAdmin(admin.ModelAdmin):
#     list_display = (
#         "location",
#         "appointment_tag",
#         "reported_by",
#         "valid_at",
#         "created_at",
#     )
#     raw_id_fields = (
#         "location",
#         "reported_by",
#         "reports",
#         "eva_reports",
#     )
#     actions = [export_as_csv_action()]


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
    reports = reporter.reports.exclude(soft_deleted=True)
    return mark_safe(
        render_to_string(
            "admin/_reporter_qa_summary.html",
            {
                "reporter": reporter,
                "recent_reports": reports.select_related("location")
                .prefetch_related("availability_tags")
                .order_by("-created_at")[:20],
                "recent_report_datetimes": [
                    d.isoformat()
                    for d in reports.values_list("created_at", flat=True)[:100]
                ],
                "report_count": reports.count(),
            },
        )
    )


class LogEntryAdmin(admin.ModelAdmin):
    # Derived from https://github.com/radwon/django-admin-logs
    # MIT licensed
    fields = (
        "action_time",
        "user",
        "content_type",
        "object_id",
        "object_repr",
        "action_flag",
        "change_message",
    )
    list_display = (
        "action_time",
        "user",
        "action_message",
        "content_type",
        "object_link",
    )
    list_filter = (
        "action_time",
        ("user", admin.RelatedOnlyFieldListFilter),
        "action_flag",
        "content_type",
    )
    search_fields = (
        "object_repr",
        "change_message",
    )

    def object_link(self, obj):
        admin_url = None if obj.is_deletion() else obj.get_admin_url()
        if admin_url:
            return mark_safe(
                '<a href="{}">{}</a>'.format(escape(admin_url), escape(obj.object_repr))
            )
        else:
            return obj.object_repr

    object_link.short_description = "object"

    def action_message(self, obj):
        change_message = obj.get_change_message()
        # If there is no change message then use the action flag label
        if not change_message:
            change_message = "{}.".format(obj.get_action_flag_display())
        return change_message

    action_message.short_description = "action"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("content_type")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # Prevent changes to log entries creating their own log entries!
    def log_addition(self, request, object, message):
        pass

    def log_change(self, request, object, message):
        pass

    def log_deletion(self, request, object, object_repr):
        pass


admin.site.register(LogEntry, LogEntryAdmin)
