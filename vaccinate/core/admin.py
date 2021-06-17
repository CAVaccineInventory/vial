import json

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.models import LogEntry
from django.db.models import Count, Exists, Max, Min, OuterRef, Q, TextField
from django.db.models.query import QuerySet
from django.forms import Textarea
from django.http import HttpRequest, HttpResponseNotAllowed, HttpResponseRedirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import dateformat, timezone
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.utils.text import Truncator
from reversion.models import Revision, Version
from reversion_compare.admin import CompareVersionAdmin

from .admin_actions import export_as_csv_action
from .admin_filters import DateYesterdayFieldListFilter, make_csv_filter
from .models import (
    AppointmentTag,
    AvailabilityTag,
    CallRequest,
    CallRequestReason,
    CompletedLocationMerge,
    ConcordanceIdentifier,
    County,
    EvaReport,
    ImportRun,
    Location,
    LocationReviewNote,
    LocationReviewTag,
    LocationType,
    Provider,
    ProviderPhase,
    ProviderType,
    Report,
    Reporter,
    ReportReviewNote,
    ReportReviewTag,
    SourceLocation,
    SourceLocationMatchHistory,
    State,
    Task,
    TaskType,
)

# Simple models first
for model in (LocationType, ProviderType, ProviderPhase, TaskType):
    admin.site.register(
        model, actions=[export_as_csv_action()], search_fields=("name",)
    )


@admin.register(ImportRun)
class ImportRunAdmin(admin.ModelAdmin):
    list_display = ("created_at", "api_key", "source_locations")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("api_key").annotate(
            source_locations_count=Count("imported_source_locations")
        )

    def source_locations(self, obj):
        return obj.source_locations_count

    source_locations.admin_order_field = (  # type:ignore[attr-defined]
        "source_locations_count"
    )

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ConcordanceIdentifier)
class ConcordanceIdentifierAdmin(admin.ModelAdmin):
    search_fields = ("identifier",)
    list_display = (
        "authority",
        "identifier",
        "locations_summary",
        "source_locations_summary",
    )
    list_display_links = ("authority", "identifier")
    list_filter = ("authority",)
    raw_id_fields = ("locations", "source_locations")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("locations", "source_locations")

    def locations_summary(self, obj):
        return mark_safe(
            "<br>".join(
                '<a href="/admin/core/location/{}/change/">{}</a>'.format(
                    location.pk, escape(location.name)
                )
                for location in obj.locations.all()
            )
        )

    def source_locations_summary(self, obj):
        return mark_safe(
            "<br>".join(
                '<a href="/admin/core/sourcelocation/{}/change/">{}</a>'.format(
                    location.pk, escape(location.name)
                )
                for location in obj.source_locations.all()
            )
        )

    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return ("created_at", "authority", "identifier")
        return ["created_at"]

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SourceLocation)
class SourceLocationAdmin(admin.ModelAdmin):
    list_display = (
        "source_uid",
        "source_name",
        "name",
        "latitude",
        "longitude",
        "import_run",
        "last_imported_at",
    )
    readonly_fields = ("concordances_summary",)
    raw_id_fields = ("matched_location",)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def concordances_summary(self, obj):
        bits = []
        for concordance in obj.concordances.all():
            bits.append(
                '<p><a href="/admin/core/concordanceidentifier/{}/change/">{}</a></p>'.format(
                    concordance.pk,
                    escape(str(concordance)),
                )
            )
        return mark_safe("\n".join(bits))


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
        "provider_type",
        "current_phases",
        "main_url",
        "contact_phone_number",
    )
    list_display_links = ("public_id", "name")
    actions = [export_as_csv_action()]
    autocomplete_fields = ("phases",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "public_id",
                    "name",
                    "provider_type",
                    "contact_phone_number",
                    "internal_contact_instructions",
                )
            },
        ),
        (
            "Public data",
            {
                "fields": (
                    "last_updated",
                    "phases",
                    "public_notes",
                    "main_url",
                    "vaccine_info_url",
                    "vaccine_locations_url",
                    "appointments_url",
                )
            },
        ),
        (
            "Identifiers",
            {
                "classes": ("collapse",),
                "fields": (
                    "airtable_id",
                    "import_json",
                ),
            },
        ),
    )
    readonly_fields = ("public_id",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("phases")

    def current_phases(self, obj):
        return [phase.name for phase in obj.phases.all()]


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
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "state",
                    "population",
                    "internal_notes",
                    "fips_code",
                )
            },
        ),
        (
            "Public data",
            {
                "fields": (
                    "age_floor_without_restrictions",
                    "public_notes",
                    "hotline_phone_number",
                    "vaccine_info_url",
                    "vaccine_locations_url",
                    "vaccine_reservations_url",
                    "vaccine_data_url",
                    "vaccine_arcgis_url",
                    "vaccine_dashboard_url",
                )
            },
        ),
        (
            "Social / engagement",
            {
                "fields": (
                    "facebook_page",
                    "twitter_page",
                    "official_volunteering_url",
                )
            },
        ),
        ("Identifiers", {"classes": ("collapse",), "fields": ("airtable_id",)}),
    )
    readonly_fields = ("fips_code", "name", "state", "airtable_id", "population")
    ordering = ("name",)
    actions = [export_as_csv_action()]

    def short_public_notes(self, obj):
        return (
            obj.public_notes
            if (obj.public_notes is None or len(obj.public_notes) < 50)
            else (obj.public_notes[:47] + "..")
        )

    short_public_notes.short_description = "Public Notes"  # type:ignore[attr-defined]


def make_call_request_queue_action(reason: str):
    def add_to_call_request_queue(
        modeladmin: LocationAdmin, request: HttpRequest, queryset: QuerySet[Location]
    ):
        # We have to flatten this into IDs to make insert able to deal
        # -- it may have GROUP BY, which makes us unable to SELECT FOR
        # UPDATE it.
        queryset = Location.objects.filter(id__in=[loc.id for loc in queryset])
        inserted = CallRequest.insert(queryset, reason)

        message = "Added {} location{} to queue with reason: {}".format(
            len(inserted), "s" if len(inserted) == 1 else "", reason
        )
        if len(inserted) < queryset.count():
            skipped = queryset.count() - len(inserted)
            message += ". Skipped {} location{}".format(
                skipped, "s" if skipped != 1 else ""
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
                Exists(
                    CallRequest.objects.filter(location=OuterRef("pk"), completed=False)
                ),
            )
        if self.value() == "no":
            return queryset.filter(
                ~Exists(
                    CallRequest.objects.filter(location=OuterRef("pk"), completed=False)
                ),
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


def claim_objects(modeladmin, request, queryset, object_name):
    count = queryset.update(claimed_by=request.user, claimed_at=timezone.now())
    messages.success(
        request,
        f"You claimed {count} {object_name}{'s' if count != 1 else ''}",
    )


def unclaim_objects_you_have_claimed(modeladmin, request, queryset, object_name):
    count = queryset.filter(claimed_by=request.user).update(
        claimed_by=None, claimed_at=None
    )
    messages.success(
        request,
        f"You unclaimed {count} {object_name}{'s' if count != 1 else ''}",
    )


def claim_reports(modeladmin, request, queryset):
    claim_objects(modeladmin, request, queryset, object_name="report")


def claim_locations(modeladmin, request, queryset):
    claim_objects(modeladmin, request, queryset, object_name="location")


def unclaim_reports_you_have_claimed(modeladmin, request, queryset):
    unclaim_objects_you_have_claimed(
        modeladmin, request, queryset, object_name="report"
    )


def unclaim_locations_you_have_claimed(modeladmin, request, queryset):
    unclaim_objects_you_have_claimed(
        modeladmin, request, queryset, object_name="location"
    )


@admin.register(LocationReviewTag)
class LocationReviewTagAdmin(admin.ModelAdmin):
    search_fields = ("tag",)


@admin.register(LocationReviewNote)
class LocationReviewNoteAdmin(admin.ModelAdmin):
    list_display_links = None
    list_display = (
        "created_at",
        "author",
        # "location_summary",
        "note_tags",
        "note",
    )
    readonly_fields = ("created_at", "author", "tags")
    ordering = ("-created_at",)

    def get_actions(self, request):
        return []

    def queryset(self, request, queryset):
        return queryset.select_related("location__created_by")

    # def report_summary(self, obj):
    #     return mark_safe(
    #         f"<strong>Report <a href=\"/admin/core/location/{obj.id}/change/\">{obj.public_id}</a></strong>"
    #         '<strong>Report <a href="/admin/core/report/{}/change/">{}</a></strong><br>by {}<br>on {}'.format(
    #             obj.report_id,
    #             obj.report.public_id,
    #             escape(obj.report.reported_by),
    #             dateformat.format(
    #                 timezone.localtime(obj.report.created_at), "jS M Y g:i:s A e"
    #             ),
    #         )
    #         + '<br>On <a href="/admin/core/location/{}/change/">{}</a>'.format(
    #             obj.report.location_id, escape(obj.report.location.name)
    #         )
    #     )

    def note_tags(self, obj):
        return ", ".join([t.tag for t in obj.tags.all()])

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Location)
class LocationAdmin(DynamicListDisplayMixin, CompareVersionAdmin):
    change_form_template = "admin/change_location.html"
    save_on_top = True
    autocomplete_fields = [
        "claimed_by",
    ]
    actions = [
        claim_locations,
        unclaim_locations_you_have_claimed,
        "bulk_approve_locations",
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
            "QA summary",
            {
                "fields": (
                    "is_pending_review",
                    "claimed_by",
                    "claimed_at",
                ),
            },
        ),
        (
            "Location Details",
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
                    "preferred_contact_method",
                    "provider",
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
        ("Identifiers", {"fields": ("public_id", "concordances_summary")}),
        (
            "Data Fields",
            {
                "classes": ("collapse",),
                "fields": (
                    "created_by",
                    "created_at",
                    "import_run",
                    "provenance",
                    "airtable_id",
                    "vaccinespotter_location_id",
                    "vaccinefinder_location_id",
                    "google_places_id",
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
        (
            "Matched source locations",
            {"classes": ("collapse",), "fields": ("matched_source_locations",)},
        ),
        (
            "Location data for debugging",
            {
                "classes": ("collapse",),
                "fields": (
                    "vaccines_offered",
                    "accepts_appointments",
                    "accepts_walkins",
                    "public_notes",
                    "internal_notes",
                ),
            },
        ),
    )
    deliberately_omitted_from_fieldsets = ("point",)

    def matched_source_locations(self, obj):
        return mark_safe(
            "".join(
                '<p><a href="/admin/core/sourcelocation/{}/change/">{}:{} {}</a></p>'.format(
                    source_location.pk,
                    source_location.source_uid,
                    source_location.source_name,
                    source_location.name,
                )
                for source_location in obj.matched_source_locations.all()
            )
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

    def _reversion_revisionform_view(
        self, request, version, template_name, extra_context=None
    ):
        if request.method == "POST":
            return HttpResponseNotAllowed("This breaks VIAL, so we can't do it!")
        return super()._reversion_revisionform_view(
            request, version, template_name, extra_context
        )

    search_fields = (
        "name",
        "full_address",
        "public_id",
        "phone_number",
        "county__name",
    )
    list_display_links = None
    list_display = (
        "summary",
        "public_id",
        "times_reported",
        "scooby_report_link",
        "request_a_call",
        "is_pending_review",
        "claimed_by",
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
        "is_pending_review",
        ClaimFilter,
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
        "created_at",
        "created_by",
        "request_a_call",
        "public_id",
        "airtable_id",
        "vaccinespotter_location_id",
        "vaccinefinder_location_id",
        "google_places_id",
        "import_json",
        "import_ref",
        "reports_history",
        "concordances_summary",
        "dn_latest_report",
        "dn_latest_report_including_pending",
        "dn_latest_yes_report",
        "dn_latest_skip_report",
        "dn_latest_non_skip_report",
        "dn_skip_report_count",
        "dn_yes_report_count",
        "matched_source_locations",
        "vaccines_offered",
        "accepts_appointments",
        "accepts_walkins",
        "public_notes",
        "claimed_at",
    )

    def bulk_approve_locations(self, request, queryset):
        pending_review = queryset.filter(is_pending_review=True)
        count = pending_review.count()

        if count:
            approved = LocationReviewTag.objects.get(tag="Approved")

            for location in pending_review:
                note = location.location_review_notes.create(author=request.user)
                note.tags.add(approved)

            pending_review.update(is_pending_review=False)

        self.message_user(
            request,
            f"Approved {count} location{'s' if count != 1 else ''}",
            messages.SUCCESS,
        )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
            obj.is_pending_review = request.user.groups.filter(
                name="WB Trainee"
            ).exists()
        if obj.claimed_by and "claimed_by" in form.changed_data:
            obj.claimed_at = timezone.now()

        # If the user toggled it to is_pending_review=False, record note
        marked_as_reviewed = (
            "is_pending_review" in form.changed_data and not obj.is_pending_review
        )
        if marked_as_reviewed:
            note = obj.location_review_notes.create(author=request.user)
            note.tags.add(LocationReviewTag.objects.get(tag="Approved"))

        super().save_model(request, obj, form, change)

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

    summary.admin_order_field = "name"  # type:ignore[attr-defined]

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

    times_reported.admin_order_field = (  # type:ignore[attr-defined]
        "times_reported_count"
    )

    def latest_non_skip_report_date(self, obj):
        if obj.dn_latest_non_skip_report:
            return obj.dn_latest_non_skip_report.created_at

    latest_non_skip_report_date.admin_order_field = (  # type:ignore[attr-defined]
        "dn_latest_non_skip_report__created_at"
    )

    def lookup_allowed(self, lookup, value):
        return True

    def reports_history(self, obj):
        return reports_history(obj)

    def concordances_summary(self, obj):
        bits = []
        for concordance in obj.concordances.all():
            bits.append(
                '<p data-idref="{}">{}: <a href="/admin/core/concordanceidentifier/{}/change/">{}</a></p>'.format(
                    escape(str(concordance)),
                    escape(concordance.authority),
                    concordance.pk,
                    escape(concordance.identifier),
                )
            )
        return mark_safe(
            '<div data-public-id="{}" data-authorities="{}" class="edit-concordances">'.format(
                escape(obj.public_id),
                escape(
                    json.dumps(
                        list(
                            ConcordanceIdentifier.objects.values_list(
                                "authority", flat=True
                            ).distinct()
                        )
                    )
                ),
            )
            + '<div class="existing-concordances">'
            + "\n".join(bits)
            + "</div></div>"
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
    search_fields = ("external_id", "display_name", "name", "email")
    list_display = (
        "__str__",
        "external_id",
        "name",
        "roles",
        "report_count",
        "latest_report",
    )
    list_filter = (
        ReporterProviderFilter,
        make_csv_filter(
            filter_title="Roles",
            filter_parameter_name="role",
            table="reporter",
            column="auth0_role_names",
        ),
    )
    actions = [export_as_csv_action()]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            reporter_report_count=Count("reports"),
            reporter_latest_report=Max("reports__created_at"),
        )

    def report_count(self, obj):
        return obj.reporter_report_count

    report_count.admin_order_field = (  # type:ignore[attr-defined]
        "reporter_report_count"
    )

    def latest_report(self, obj):
        return obj.reporter_latest_report

    latest_report.admin_order_field = (  # type:ignore[attr-defined]
        "reporter_latest_report"
    )

    def roles(self, obj):
        return [r.strip() for r in (obj.auth0_role_names or "").split(",")]

    readonly_fields = (
        "name",
        "external_id",
        "email",
        "auth0_role_names",
        "reporter_qa_summary",
    )

    def reporter_qa_summary(self, obj):
        return reporter_qa_summary(obj)

    reporter_qa_summary.short_description = (  # type:ignore[attr-defined]
        "Caller QA summary"
    )


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


def bulk_approve_reports(modeladmin, request, queryset):
    pending_review = queryset.filter(is_pending_review=True)
    # Add a comment to them all
    approved = ReportReviewTag.objects.get(tag="Approved")
    for report in pending_review:
        note = report.review_notes.create(author=request.user)
        note.tags.add(approved)
    count = pending_review.count()
    messages.success(
        request,
        "Approved {} report{}".format(count, "s" if count != 1 else ""),
    )


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
        "reported_by__display_name",
    )

    list_display = (
        "created_id_deleted",
        "location_link",
        "is_pending_review",
        "claimed_by",
        "availability",
        "public_notes",
        "internal_notes",
        "appointment_tag_and_scheduling",
        "reporter",
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
        "report_source",
        ("created_at", DateYesterdayFieldListFilter),
        make_csv_filter(
            filter_title="Roles",
            filter_parameter_name="role",
            table="reporter",
            column="auth0_role_names",
            queryset_column="reported_by__auth0_role_names",
        ),
        "availability_tags",
        "appointment_tag",
        SoftDeletedFilter,
        ("airtable_json", admin.EmptyFieldListFilter),  # type:ignore[attr-defined]
    )
    ordering = ("-created_at",)

    formfield_overrides = {
        TextField: {"widget": Textarea(attrs={"rows": 4, "cols": 150})}
    }
    readonly_fields = (
        "location_link",
        "reporter",
        "county_summary",
        "created_at",
        "claimed_at",
        "created_at_utc",
        "originally_pending_review",
        "pending_review_because",
        "public_id",
        "airtable_id",
        "airtable_json",
        "reporter_qa_summary",
        "location_reports_history",
        "hours",
        "full_address",
        "website",
    )
    inlines = [ReportReviewNoteInline]
    deliberately_omitted_from_fieldsets = ("location", "reported_by")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "reporter",
                    "public_id",
                    "location_link",
                    "created_at",
                )
            },
        ),
        (
            "QA summary",
            {
                "fields": (
                    "originally_pending_review",
                    "is_pending_review",
                    "pending_review_because",
                    "claimed_by",
                    "claimed_at",
                ),
            },
        ),
        (
            "Report Details",
            {
                "fields": (
                    "availability_tags",
                    "public_notes",
                    "internal_notes",
                    "appointment_tag",
                    "appointment_details",
                    "call_request",
                    "report_source",
                    "reported_by",
                    "planned_closure",
                    "vaccines_offered",
                    "restriction_notes",
                ),
            },
        ),
        ("County summary", {"classes": ("collapse",), "fields": ("county_summary",)}),
        (
            "Location history",
            {
                "classes": ("collapse",),
                "fields": ("location_reports_history",),
            },
        ),
        (
            "Caller history",
            {
                "classes": ("collapse",),
                "fields": ("reporter_qa_summary",),
            },
        ),
        (
            "Report deletion",
            {
                "classes": ("collapse",),
                "fields": (
                    "soft_deleted",
                    "soft_deleted_because",
                ),
            },
        ),
        (
            "Identifiers",
            {
                "classes": ("collapse",),
                "fields": ("airtable_id", "airtable_json"),
            },
        ),
        (
            "Report data for debugging",
            {
                "classes": ("collapse",),
                "fields": (
                    "hours",
                    "full_address",
                    "website",
                ),
            },
        ),
    )

    def created_id_deleted(self, obj):
        date = (
            dateformat.format(timezone.localtime(obj.created_at), "j M g:iA e")
            .replace("PM", "pm")
            .replace("AM", "am")
            .replace(" ", "\u00a0")
        )
        html = format_html(
            '<a href="{}">{}<br><b>{}</b></a>',
            reverse("admin:core_report_change", args=(obj.id,)),
            date,
            obj.public_id,
        )

        if obj.soft_deleted:
            html += mark_safe('<br><strong style="color: red">Soft deleted</strong>')
        return mark_safe(html)

    created_id_deleted.short_description = "created"  # type:ignore[attr-defined]
    created_id_deleted.admin_order_field = "created_at"  # type:ignore[attr-defined]

    def location_link(self, obj):
        return format_html(
            '<strong><a href="{}">{}</a></strong><br>{}',
            reverse("admin:core_location_change", args=(obj.location.id,)),
            obj.location.name,
            obj.location.full_address,
        )

    location_link.short_description = "Location"  # type:ignore[attr-defined]
    location_link.admin_order_field = "location__name"  # type:ignore[attr-defined]

    def reporter(self, obj):
        return format_html(
            '<strong><a href="{}">{}</a></strong><br>{}',
            reverse("admin:core_reporter_change", args=(obj.reported_by.id,)),
            obj.reported_by,
            escape(obj.reported_by.auth0_role_names or ""),
        )

    reporter.short_description = "Reporter"  # type:ignore[attr-defined]
    reporter.admin_order_field = "reported_by"  # type:ignore[attr-defined]

    def appointment_tag_and_scheduling(self, obj):
        raw_details = obj.full_appointment_details()
        if raw_details and (
            raw_details.startswith("http://") or raw_details.startswith("https://")
        ):
            details = format_html(
                '<a target="_blank" href="{}">{}</a>',
                raw_details,
                Truncator(raw_details).chars(75),
            )
        else:
            details = escape(raw_details or "")
        if not obj.appointment_details:
            # If this is from fallback on the location or provider, italicize it
            details = mark_safe("<i>{}</i>".format(details))

        return mark_safe("<b>{}</b><br>{}".format(obj.appointment_tag.name, details))

    appointment_tag_and_scheduling.admin_order_field = (  # type:ignore[attr-defined]
        "appointment_tag"
    )
    appointment_tag_and_scheduling.short_description = (  # type:ignore[attr-defined]
        "appointment info"
    )

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

    def save_model(self, request, obj, form, change):
        if not change:
            is_wb_trainee = request.user.groups.filter(name="WB Trainee").exists()
            obj.is_pending_review = is_wb_trainee or obj.report_source != "ca"
        if obj.claimed_by and "claimed_by" in form.changed_data:
            obj.claimed_at = timezone.now()
        # If the user toggled it to is_pending_review=False, record note
        marked_as_reviewed = (
            "is_pending_review" in form.changed_data and not obj.is_pending_review
        )
        super().save_model(request, obj, form, change)
        if marked_as_reviewed:
            note = obj.review_notes.create(author=request.user)
            note.tags.add(ReportReviewTag.objects.get(tag="Approved"))

    def state(self, obj):
        return obj.location.state.abbreviation

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "location__provider",
                "location__state",
                "location__county",
                "reported_by",
                "appointment_tag",
            )
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

    def reporter_qa_summary(self, obj):
        return reporter_qa_summary(obj.reported_by)

    reporter_qa_summary.short_description = "QA summary"  # type:ignore[attr-defined]

    def location_reports_history(self, obj):
        return reports_history(obj.location)

    location_reports_history.short_description = (  # type:ignore[attr-defined]
        "Location history"
    )


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
                escape(obj.report.reported_by),
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
            (None, "In queue ready to be assigned"),
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
            ).exclude(
                Q(location__phone_number__isnull=True) | Q(location__phone_number="")
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
    add_form_template = "admin/add_call_request.html"
    change_form_template = "admin/change_call_request.html"
    search_fields = (
        "location__name",
        "location__full_address",
        "location__public_id",
        "location__phone_number",
    )
    list_display = (
        "summary",
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
    readonly_fields = ("priority", "created_at")

    def summary(self, obj):
        bits = [escape(obj.location.name)]
        if not obj.location.phone_number:
            bits.append('<span style="color: red">Has no phone number</span>')
        now = timezone.now()
        if obj.claimed_by_id and obj.claimed_until > now:
            bits.append(
                '<span style="color: green">Claim locked for another {:d} minutes</span>'.format(
                    int((obj.claimed_until - now).total_seconds() / 60)
                )
            )
        if obj.completed_at:
            if obj.completed_at.date() == timezone.now().date():
                format_string = "g:i A e"
            else:
                format_string = "jS M Y g:i A e"
            bits.append(
                '<span style="color: orange">Request completed at {}</span>'.format(
                    dateformat.format(
                        timezone.localtime(obj.completed_at), format_string
                    ),
                )
            )
        return mark_safe("<br>".join(bits))

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

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["redirect_from_create"] = False
        if request.GET.get("redirect_from_create"):
            extra_context["redirect_from_create"] = True
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["existing_call_request"] = None
        if request.GET.get("location"):
            location = Location.objects.get(pk=request.GET["location"])
            extra_context["existing_call_request"] = location.call_requests.filter(
                completed=False
            ).first()
        return super().add_view(
            request,
            form_url,
            extra_context=extra_context,
        )


@admin.register(SourceLocationMatchHistory)
class SourceLocationMatchHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "source_location",
        "new_match_location",
        "reporter",
        "api_key",
    )
    actions = [export_as_csv_action()]
    raw_id_fields = (
        "api_key",
        "reporter",
        "source_location",
        "old_match_location",
        "new_match_location",
    )


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    search_fields = (
        "location__name",
        "location__full_address",
        "location__public_id",
        "location__phone_number",
    )
    list_display = (
        "task_type",
        "location",
        "other_location",
        "created_by",
        "created_at",
        "resolved_by",
        "resolved_at",
    )
    list_filter = ("task_type",)
    actions = [
        export_as_csv_action(),
    ]
    raw_id_fields = ("location", "other_location", "created_by", "resolved_by")


@admin.register(CompletedLocationMerge)
class CompletedLocationMergeAdmin(admin.ModelAdmin):
    search_fields = (
        "winner_location__name",
        "winner_location__full_address",
        "winner_location__public_id",
        "loser_location__name",
        "loser_location__full_address",
        "loser_location__public_id",
    )
    raw_id_fields = ("winner_location", "loser_location", "created_by", "task")


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


def reporter_qa_summary(reporter):
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


def reports_history(location):
    reports = location.reports.exclude(soft_deleted=True)
    return mark_safe(
        render_to_string(
            "admin/_reports_history.html",
            {
                "location_id": location.pk,
                "reports_datetimes": [
                    d.isoformat() for d in reports.values_list("created_at", flat=True)
                ],
                "reports": reports.select_related("reported_by")
                .prefetch_related("availability_tags")
                .order_by("-created_at"),
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

    object_link.short_description = "object"  # type:ignore[attr-defined]

    def action_message(self, obj):
        change_message = obj.get_change_message()
        # If there is no change message then use the action flag label
        if not change_message:
            change_message = "{}.".format(obj.get_action_flag_display())
        return change_message

    action_message.short_description = "action"  # type:ignore[attr-defined]

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
