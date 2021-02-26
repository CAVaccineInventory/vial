from github_contents import GithubContents
from .models import (
    AppointmentTag,
    AvailabilityTag,
    CallReport,
    Location,
    State,
    LocationType,
    Provider,
    County,
    ProviderType,
    Reporter,
)

FIX_AVAILABILITY_TAGS = {
    "Vaccinating essential workers": "Yes: Vaccinating essential workers",
    "Scheduling second dose only": "Yes: Scheduling second dose only",
}
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
    else:
        assert False, "No county"
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
    }
    return Location.objects.update_or_create(
        airtable_id=location["airtable_id"], defaults=kwargs
    )[0]


def import_airtable_report(report):
    other = AppointmentTag.objects.get(name="other")

    assert "Reported by" in report, "Missing 'Reported by'"
    if report.get("auth0_reporter_id"):
        reported_by = Reporter.objects.get_or_create(
            auth0_name=report["auth0_reporter_id"],
            defaults={"auth0_role_name": report["auth0_reporter_roles"]},
        )[0]
    else:
        reported_by = Reporter.objects.get_or_create(
            airtable_name=report["Reported by"]["id"],
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
        # Currently hard-coded to 'other' - this is solvable with more thought:
        "appointment_tag": other,
        # "appointment_details": "",
        # "public_notes": "",
        "internal_notes": report.get("Internal Notes"),
        "reported_by": reported_by,
        "created_at": report["airtable_createdTime"],
        # "call_request" isn't a concept that exists in Airtable
        "airtable_json": report,
    }

    tags = []
    assert "Availability" in report, "Missing Availability"
    for tag in report["Availability"]:
        tag = FIX_AVAILABILITY_TAGS.get(tag, tag)
        try:
            tags.append(AvailabilityTag.objects.get(name=tag))
        except AvailabilityTag.DoesNotExist:
            assert False, "Invalid tag: {}".format(tag)

    report_obj = CallReport.objects.update_or_create(
        airtable_id=report["airtable_id"], defaults=kwargs
    )[0]

    for availability_tag in tags:
        report_obj.availability_tags.add(availability_tag)

    return report_obj
