import re
from io import StringIO

import requests
import reversion
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core import management
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render

from .models import CallRequest, County, Location, Report


def extract_ids(s):
    return re.split(
        r"[\n\r,\s]+", (s or "").replace('"', "").replace("[", "".replace("]", ""))
    )


@login_required
@user_passes_test(lambda user: user.has_perm("core.add_callrequest"))
def import_call_requests(request):
    error = None
    messages = []
    priority_groups = CallRequest.PriorityGroup.choices
    if request.method == "POST":
        for group_id, group_name in priority_groups:
            field = "location_ids_group_{}".format(group_id)
            location_ids = extract_ids(request.POST.get(field))
            locations = Location.objects.filter(public_id__in=location_ids)
            if locations.count() != 0:
                # Delete any already-existing incomplete call requests for these locations
                num_deleted = CallRequest.objects.filter(
                    location__public_id__in=location_ids,
                    completed=False,
                ).delete()[0]
                CallRequest.insert(
                    locations=locations,
                    reason="Imported",
                    priority_group=group_id,
                )
                messages.append(
                    "Added {} locations to priority {} (deleted {} existing call requests)".format(
                        len(locations), group_name, num_deleted
                    )
                )
    return render(
        request,
        "admin/import_call_requests.html",
        {
            "choices": priority_groups,
            "error": error,
            "message": "\n".join(messages),
        },
    )


@login_required
@user_passes_test(lambda user: user.is_superuser)
def bulk_delete_reports(request):
    error = None
    message = None
    report_ids = []
    location_ids = []
    if request.method == "POST":
        report_ids = [r for r in extract_ids(request.POST.get("report_ids")) if r]
        if not isinstance(report_ids, list) or any(
            not str(r).startswith("r") for r in report_ids
        ):
            error = (
                "Input must be a newline or comma separated list of 'rxx' report IDs"
            )
        if report_ids and not error:
            reports_qs = Report.objects.filter(public_id__in=report_ids)
            if reports_qs.exists():
                location_ids = list(
                    reports_qs.values_list("location_id", flat=True).distinct()
                )
                # set null on any denormalized references
                Location.objects.filter(
                    dn_latest_report__public_id__in=report_ids
                ).update(dn_latest_report=None)
                Location.objects.filter(
                    dn_latest_report_including_pending__public_id__in=report_ids
                ).update(dn_latest_report_including_pending=None)
                Location.objects.filter(
                    dn_latest_yes_report__public_id__in=report_ids
                ).update(dn_latest_yes_report=None)
                Location.objects.filter(
                    dn_latest_skip_report__public_id__in=report_ids
                ).update(dn_latest_skip_report=None)
                Location.objects.filter(
                    dn_latest_non_skip_report__public_id__in=report_ids
                ).update(dn_latest_non_skip_report=None)
                # Delete the availability tags
                report_availability_tag_qs = (
                    Report.availability_tags.through.objects.filter(
                        report__public_id__in=report_ids
                    )
                )
                report_availability_tag_qs._raw_delete(report_availability_tag_qs.db)
                # Delete those reports
                reports_qs._raw_delete(reports_qs.db)
                # Refresh the denormalized columns on those locations
                locations_qs = Location.objects.filter(pk__in=location_ids)
                for location in locations_qs:
                    location.update_denormalizations()
                message = (
                    "Delete complete - {} affected locations have been updated".format(
                        locations_qs.count()
                    )
                )

    return render(
        request,
        "admin/bulk_delete_reports.html",
        {
            "error": error,
            "message": message,
        },
    )


@login_required
@user_passes_test(lambda user: user.is_superuser)
def admin_tools(request):
    command_output = StringIO()
    error = None
    message = None
    if request.method == "POST":
        if request.POST.get("airtable_counties_url"):
            airtable_counties_url = request.POST["airtable_counties_url"]
            try:
                airtable_counties = requests.get(airtable_counties_url).json()
                updated = import_airtable_counties(airtable_counties, request.user)
                message = "Updated details for {} counties".format(len(updated))
            except Exception as e:
                error = str(e)
        else:
            # Run management commands
            command_to_run, args = {
                "import_counties": ("import_counties", []),
            }.get(request.POST.get("command"), (None, None))
            if command_to_run is None:
                error = "Unknown command"
            else:
                management.call_command(command_to_run, *args, stdout=command_output)
                message = "Ran command: {}".format(command_to_run)
    return render(
        request,
        "admin/tools.html",
        {
            "output": command_output.getvalue(),
            "error": error,
            "message": message,
        },
    )


def import_airtable_counties(airtable_counties, user):
    updated = []
    with reversion.create_revision():
        for airtable_county in airtable_counties:
            changed = False
            try:
                county = County.objects.get(airtable_id=airtable_county["airtable_id"])
            except County.DoesNotExist:
                continue
            for airtable_key, django_key in {
                "County vaccination reservations URL": "vaccine_reservations_url",
                "Facebook Page": "facebook_page",
                # "Worked on By": "",
                "Internal notes": "internal_notes",
                "Notes": "public_notes",
                "Twitter Page": "twitter_page",
                "Vaccine info URL": "vaccine_info_url",
                "Vaccine locations URL": "vaccine_locations_url",
                "Official volunteering opportunities": "official_volunteering_url",
                "population": "population",
                "age_floor_without_restrictions": "age_floor_without_restrictions",
            }.items():
                new_value = airtable_county.get(airtable_key) or ""
                old_value = getattr(county, django_key, "")
                if new_value != old_value:
                    setattr(county, django_key, new_value)
                    changed = True
            if changed:
                county.save()
                updated.append(county)
        reversion.set_user(user)
        reversion.set_comment(
            "Imported airtable county information using /admin/tools/"
        )
    return updated


def get_winner_loser(d):
    try:
        winner = Location.objects.get(public_id=d.get("winner"))
    except Location.DoesNotExist:
        winner = None
    try:
        loser = Location.objects.get(public_id=d.get("loser"))
    except Location.DoesNotExist:
        loser = None
    return winner, loser


@login_required
@user_passes_test(lambda user: user.has_perm("core.merge_locations"))
def merge_locations(request):
    if request.method == "POST":
        winner, loser = get_winner_loser(request.POST)
        if (
            winner
            and loser
            and (winner.pk != loser.pk)
            and not (winner.soft_deleted or loser.soft_deleted)
        ):
            # Merge them
            with reversion.create_revision():
                loser.reports.update(location=winner.pk)
                loser.soft_deleted = True
                loser.soft_deleted_because = "Merged into location {}".format(
                    winner.public_id
                )
                loser.duplicate_of = winner
                loser.save()
                reversion.set_user(request.user)
                reversion.set_comment(
                    "Merged locations, winner = {}, loser = {}".format(
                        winner.public_id, loser.public_id
                    )
                )
            messages.success(request, "Locations merged")
            return HttpResponseRedirect(
                f"/admin/core/location/{winner.pk}/change/#location-h2"
            )
    else:
        winner, loser = get_winner_loser(request.GET)
    return render(
        request,
        "admin/merge_locations.html",
        {
            "winner": winner,
            "loser": loser,
        },
    )


def edit_location_redirect(request, public_id):
    location = get_object_or_404(Location, public_id=public_id)
    return HttpResponseRedirect("/admin/core/location/{}/change/".format(location.pk))


@login_required
@user_passes_test(lambda user: user.has_perm("core.delete_callrequest"))
def bulk_delete_call_requests(request):
    error = None
    message = None
    call_request_ids = []
    if request.method == "POST":
        call_request_ids = [
            r for r in extract_ids(request.POST.get("call_request_ids")) if r
        ]
        if any(not r.isdigit() for r in call_request_ids):
            error = "Input must be a newline or comma separated list of integer call request IDs"
        if call_request_ids and not error:
            call_requests = CallRequest.objects.filter(id__in=call_request_ids)
            if call_requests.exists():
                deleted = call_requests.delete()
                message = "Deleted {} call requests".format(deleted[0])

    return render(
        request,
        "admin/bulk_delete_call_requests.html",
        {
            "error": error,
            "message": message,
        },
    )
