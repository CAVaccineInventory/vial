import json

import beeline
import httpx
from github_contents import GithubContents

from .models import (
    AppointmentTag,
    AvailabilityTag,
    County,
    Location,
    LocationType,
    Provider,
    ProviderType,
    Report,
    Reporter,
    State,
)

FIX_COUNTIES = {
    # 'Napa ' => 'Napa'
    "recjptepZLP1mzVDC": "recJ1fLYsngDaIRLG",
    # 'San Francisco County' => 'San Francisco'
    "recKSehOUATJ8CUkp": "recOuBZk28GMl7mVw",
}


def load_airtable_backup(filepath, token):
    github = GithubContents("CAVaccineInventory", "airtable-data-backup", token)
    return github.read_large(filepath)[0]


def import_airtable_location(location):
    assert location.get("Name"), "No name"
    ca = State.objects.get(abbreviation="CA")
    address = location.get("Address") or ""
    # For the moment we default LocationType to Pharmacy - we should add "Unknown"
    location_type = location.get("Location Type", "Other")
    provider = None
    if location.get("Affiliation"):
        provider = Provider.objects.get_or_create(
            name=location["Affiliation"],
            defaults={"provider_type": lambda: ProviderType.objects.get(name="Other")},
        )[0]
    county = None
    if location.get("County link"):
        county = County.objects.get(
            airtable_id=FIX_COUNTIES.get(
                location["County link"][0], location["County link"][0]
            )
        )
    elif location.get("County"):
        county = County.objects.get(
            state__abbreviation="CA", name=location["County"].replace(" County", "")
        )
    assert location.get("Latitude"), "No latitude"
    kwargs = {
        "name": location["Name"],
        "full_address": address,
        "street_address": address.split(",")[0].strip(),
        # "city": - will need to normalize and parse the address
        "phone_number": location.get("Phone number"),
        "state": ca,
        "hours": location.get("Hours"),
        "location_type": LocationType.objects.get_or_create(name=location_type)[0],
        "provider": provider,
        "google_places_id": location.get("google_places_id"),
        "county": county,
        "latitude": location["Latitude"],
        "longitude": location["Longitude"],
        "public_id": location["airtable_id"],
        "preferred_contact_method": location.get("preferred_contact_method") or None,
    }
    # Handle soft deletion and merges
    if location.get("is_soft_deleted"):
        kwargs["soft_deleted"] = True
    if location.get("duplicate_of"):
        try:
            duplicate_location = Location.objects.get(
                public_id=location["duplicate_of"][0]
            )
            kwargs["duplicate_of"] = duplicate_location
        except Location.DoesNotExist:
            kwargs["soft_deleted"] = True
    return Location.objects.update_or_create(
        airtable_id=location["airtable_id"], defaults=kwargs
    )[0]


def import_airtable_report(report, availability_tags=None):
    appointment_tag_string = "other"
    appointment_details = ""
    if (
        "Appointments by phone?" in report
        or "Appointment scheduling instructions" in report
    ):
        appointments_by_phone = bool(report.get("Appointments by phone?"))
        appointment_scheduling_instructions = (
            report.get("Appointment scheduling instructions") or ""
        )
        appointment_tag_string, appointment_details = derive_appointment_tag(
            appointments_by_phone, appointment_scheduling_instructions
        )

    assert "Reported by" in report, "Missing 'Reported by'"
    if report.get("auth0_reporter_id"):
        reported_by = Reporter.objects.update_or_create(
            external_id="auth0:{}".format(report["auth0_reporter_id"]),
            defaults={
                "name": report.get("auth0_reporter_name"),
                "auth0_role_names": report.get("auth0_reporter_roles"),
            },
        )[0]
    else:
        reported_by = Reporter.objects.update_or_create(
            external_id="airtable:{}".format(report["Reported by"]["id"]),
            defaults={
                "name": report["Reported by"]["name"],
                "email": report["Reported by"]["email"],
            },
        )[0]

    try:
        location = Location.objects.get(airtable_id=report["Location"][0])
    except Location.DoesNotExist:
        assert False, "No location record for location ID={}".format(report["Location"])
    except KeyError:
        assert False, "No Location key in JSON object at all"

    kwargs = {
        "location": location,
        # Currently hard-coded to caller app:
        "report_source": "ca",
        "appointment_tag": AppointmentTag.objects.get(slug=appointment_tag_string),
        "appointment_details": appointment_details,
        "public_notes": report.get("Notes"),
        "internal_notes": report.get("Internal Notes"),
        "reported_by": reported_by,
        "created_at": report["airtable_createdTime"],
        # "call_request" isn't a concept that exists in Airtable
        "airtable_json": report,
        "public_id": report["airtable_id"],
        "is_pending_review": bool(report.get("is_pending_review")),
    }

    report_obj, created = Report.objects.update_or_create(
        airtable_id=report["airtable_id"], defaults=kwargs
    )
    for tag_model in resolve_availability_tags(
        report.get("Availability") or [], availability_tags=availability_tags
    ):
        report_obj.availability_tags.add(tag_model)
    report_obj.refresh_from_db()
    return report_obj, created


def derive_appointment_tag(appointments_by_phone, appointment_scheduling_instructions):
    # https://github.com/CAVaccineInventory/vial/issues/20
    # Returns (appointment_tag, other_instructions)
    appointment_scheduling_instructions = appointment_scheduling_instructions or ""
    if appointment_scheduling_instructions == "Uses county scheduling system":
        return "county_website", None
    elif appointment_scheduling_instructions == "https://myturn.ca.gov/":
        return "myturn_ca_gov", None
    elif appointments_by_phone:
        return "phone", appointment_scheduling_instructions
    elif (
        appointment_scheduling_instructions.startswith("http://")
        or appointment_scheduling_instructions.startswith("https://")
        or appointment_scheduling_instructions.startswith("www.")
    ):
        return "web", appointment_scheduling_instructions
    else:
        return "other", appointment_scheduling_instructions


@beeline.traced(name="resolve_availability_tags")
def resolve_availability_tags(tags, availability_tags=None):
    # Given a list of string tags e.g. ["Yes: vaccinating 65+"]
    # returns matching AvailabilityTag objects, taking any
    # previous_names into account
    fix_availability_tags = {}
    if not availability_tags:
        availability_tags = AvailabilityTag.objects.all()
    for availability_tag in availability_tags:
        fix_availability_tags[availability_tag.name] = availability_tag.slug
        for previous_name in availability_tag.previous_names:
            fix_availability_tags[previous_name] = availability_tag.slug

    tag_models = []
    for tag_name in tags:
        tag_name = fix_availability_tags.get(tag_name, tag_name)
        try:
            tag_models.append(AvailabilityTag.objects.get(slug=tag_name))
        except AvailabilityTag.DoesNotExist:
            assert False, "Invalid tag: {}".format(tag_name)
    return tag_models


def load_vaccinefinder_locations(path_within_repo, github_token):
    url = "https://api.github.com/repos/vaccine-feeds/raw-feed-data/contents/{}".format(
        path_within_repo
    )
    response = httpx.get(
        url, headers={"Authorization": "Bearer {}".format(github_token)}
    )
    response.raise_for_status()
    # It may be a list OR a single item
    data = response.json()
    if isinstance(data, dict):
        download_url = data["download_url"]
        return httpx.get(download_url).json()
    else:
        # It's a directory listing - using download_urls is unlikely
        # to work due to possible rate limits on the tokens. Instead
        # we need to use the GithubContents class
        github = GithubContents("vaccine-feeds", "raw-feed-data", github_token)
        for item in data:
            yield json.loads(github.read(item["path"])[0])


def import_vaccinefinder_location(location):
    import_ref = "vf:{}".format(location["guid"])
    address_bits = [
        location[key]
        for key in ("address1", "address2", "city", "state", "zip")
        if location[key]
    ]
    kwargs = {
        "name": location["name"],
        "full_address": ", ".join(address_bits),
        "street_address": address_bits[0],
        "city": location["city"],
        "phone_number": location["phone"],
        "zip_code": location["zip"],
        "website": location["website"],
        "state": State.objects.get(abbreviation=location["state"]),
        # TODO: populate this:
        # "hours": ""
        "location_type": LocationType.objects.get(name="Unknown"),
        "provider": None,
        "latitude": location["lat"],
        "longitude": location["long"],
        "import_json": location,
    }
    return Location.objects.update_or_create(import_ref=import_ref, defaults=kwargs)[0]
