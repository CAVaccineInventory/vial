from github_contents import GithubContents
from .models import (
    AppointmentTag,
    AvailabilityTag,
    Report,
    Location,
    State,
    LocationType,
    Provider,
    County,
    ProviderType,
    Reporter,
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
    }
    return Location.objects.update_or_create(
        airtable_id=location["airtable_id"], defaults=kwargs
    )[0]


def import_airtable_report(report, availability_tags=None):
    fix_availability_tags = {}
    if not availability_tags:
        availability_tags = AvailabilityTag.objects.all()
    for tag in availability_tags:
        for previous_name in tag.previous_names:
            fix_availability_tags[previous_name] = tag.name

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
        "appointment_tag": AppointmentTag.objects.get(slug=appointment_tag_string),
        "appointment_details": appointment_details,
        # "public_notes": "",
        "internal_notes": report.get("Internal Notes"),
        "reported_by": reported_by,
        "created_at": report["airtable_createdTime"],
        # "call_request" isn't a concept that exists in Airtable
        "airtable_json": report,
    }

    tags = []
    for tag_name in report.get("Availability") or []:
        tag_name = fix_availability_tags.get(tag_name, tag_name)
        try:
            tags.append(AvailabilityTag.objects.get(name=tag))
        except AvailabilityTag.DoesNotExist:
            assert False, "Invalid tag: {}".format(tag)

    report_obj = Report.objects.update_or_create(
        airtable_id=report["airtable_id"], defaults=kwargs
    )[0]

    for availability_tag in tags:
        report_obj.availability_tags.add(availability_tag)

    return report_obj


def derive_appointment_tag(appointments_by_phone, appointment_scheduling_instructions):
    # https://github.com/CAVaccineInventory/django.vaccinate/issues/20
    # Returns (appointment_tag, other_instructions)
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
