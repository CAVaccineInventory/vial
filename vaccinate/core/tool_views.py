from io import StringIO

import requests
import reversion
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core import management
from django.http.response import HttpResponseRedirect
from django.shortcuts import render

from .models import County, Location


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
            return HttpResponseRedirect(f"/admin/core/location/{winner.pk}/change/")
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
