import pytest

from .import_utils import (
    derive_appointment_tag,
    import_airtable_location,
    import_airtable_report,
)
from .models import Location, Report

location_json = {
    "# Data corrections": 0,
    "# Unhandled data corrections": 0,
    "Add external report link": "...",
    "Address": "12761 Schabarum Ave Plaza Level RM 1100, Irwindale, CA 91706",
    "Affiliation": "Kaiser",
    "County": "Los Angeles County",
    "County Vaccine locations URL": [
        "http://publichealth.lacounty.gov/acd/ncorona2019/vaccine/hcwsignup/pods/#a93d55e49fd32ffd49714d7cc8a1be83"
    ],
    "County link": ["recZNvS1ogJzGOPgG"],
    "County vaccine info URL": [
        "http://publichealth.lacounty.gov/media/coronavirus/vaccine/"
    ],
    "Has Report": 0,
    "Hours": "Monday - Friday: 8:00 AM \u2013 5:00 PM\nSaturday - Sunday: Closed",
    "Latest Eva Report forced update?": 0,
    "Latest report yes?": 0,
    "Latitude": 34.081292,
    "Latlong": "34.081292, -117.996576",
    "Location ID": "rec00NpJzUnVDpLaQ",
    "Location Type": "Pharmacy",
    "Longitude": -117.996576,
    "Name": "Kaiser Permanente Pharmacy #568",
    'Number of "yes" reports': 0,
    "Number of Reports": 0,
    "Phone number": "xxx-xxx-xxxx",
    "airtable_createdTime": "2021-01-16T06:29:48.000Z",
    "airtable_id": "rec00NpJzUnVDpLaQ",
    "county_id": ["recZNvS1ogJzGOPgG"],
    "county_notes": [
        "[Feb 17] Currently vaccinating phase 1a (healthcare workers) and county residents 65+."
    ],
    "export_in_flight": 0,
    "google_places_id": "ChIJizKuijvXwoAR4VAXM2Ek4Nc",
    "is_callable_now": 1,
    "is_stale_report": 1,
    "latest_report_id": 0,
    "main_base_record_id": "rec00NpJzUnVDpLaQ",
    "manish_test_is_latest_dupe": 0,
    "reported_not_a_vaccination_site_count": 0,
    "reported_permanently_closed_count": 0,
    "tmp_latest_report_eva_or_stale": 1,
    "preferred_contact_method": "research_online",
}


@pytest.mark.django_db
def test_import_airtable_location():
    assert not Location.objects.filter(airtable_id="rec00NpJzUnVDpLaQ").exists()
    location = import_airtable_location(location_json)
    assert location.name == "Kaiser Permanente Pharmacy #568"
    assert location.phone_number == "xxx-xxx-xxxx"
    assert (
        location.full_address
        == "12761 Schabarum Ave Plaza Level RM 1100, Irwindale, CA 91706"
    )
    assert location.street_address == "12761 Schabarum Ave Plaza Level RM 1100"
    assert location.state.name == "California"
    assert (
        location.hours
        == "Monday - Friday: 8:00 AM – 5:00 PM\nSaturday - Sunday: Closed"
    )
    assert location.location_type.name == "Pharmacy"
    assert location.google_places_id == "ChIJizKuijvXwoAR4VAXM2Ek4Nc"
    assert location.provider.name == "Kaiser"
    assert location.county.name == "Los Angeles"
    assert location.latitude == 34.081292
    assert location.longitude == -117.996576
    assert location.airtable_id == "rec00NpJzUnVDpLaQ"


@pytest.mark.django_db
def test_import_airtable_report_pre_help_vaccinate_launch():
    # This report is from before the help.vaccinateca app was launched
    report_json = {
        "Affiliation (from Location)": ["Rite-Aid"],
        "Availability": ["No: no vaccine inventory"],
        "County (from Location)": ["Yolo County"],
        "Hour": 3,
        "ID": 4678,
        "Internal Notes": "The automotive mentioned that riteaid.com will have all the information they're looking for. As soon as they get the vaccines, based on eligibility they are going to deliver it to the public\n",
        "Location": ["rec00NpJzUnVDpLaQ"],
        "Location Type (from Location)": ["Pharmacy"],
        "Name (from Location)": ["RITE AID PHARMACY 06066"],
        "Number of Reports (from Location)": [11],
        "Report Type": "Call center",
        "Reported by": {
            "email": "4549424b@gmail.com",
            "id": "usrsCexDQt6GmdDm0",
            "name": "E B",
        },
        "airtable_createdTime": "2021-01-28T03:19:51.000Z",
        "airtable_id": "reczzhVUpoBQb6CUA",
        "is_latest_report_for_location": 0,
        "location_id": ["rec00NpJzUnVDpLaQ"],
        "location_latest_eva_report_time": ["2021-02-20T03:33:41.000Z"],
        "location_latest_report_id": [21388],
        "location_latest_report_time": ["2021-02-20T05:09:06.000Z"],
        "parent_external_report": ["recTghCHUuoq2ZNkf"],
        "report_id": "reczzhVUpoBQb6CUA",
        "soft-dropped-column: Vaccines available?": "No",
        "time": "2021-01-28T03:19:51.000Z",
        "tmp_eva_flips": [None],
    }
    assert not Report.objects.filter(airtable_id="rec00NpJzUnVDpLaQ").exists()

    # The location would have been created already
    import_airtable_location(location_json)

    report, created = import_airtable_report(report_json)

    assert report.report_source == "ca"
    assert report.appointment_tag.slug == "other"
    assert report.location.name == "Kaiser Permanente Pharmacy #568"
    assert (
        report.internal_notes
        == "The automotive mentioned that riteaid.com will have all the information they're looking for. As soon as they get the vaccines, based on eligibility they are going to deliver it to the public\n"
    )
    assert report.reported_by.external_id == "airtable:usrsCexDQt6GmdDm0"
    assert str(report.created_at) == "2021-01-28 03:19:51+00:00"
    assert report.airtable_id == "reczzhVUpoBQb6CUA"
    assert report.public_id == "reczzhVUpoBQb6CUA"
    assert list(report.availability_tags.values_list("name", flat=True)) == [
        "No vaccine inventory"
    ]


POST_HELP_LAUNCH_REPORT = {
    "ID": 26383,
    "Hour": 23,
    "time": "2021-02-25T23:54:04.000Z",
    "Location": ["rec00NpJzUnVDpLaQ"],
    "report_id": "recXBlDw9Zr7bB84O",
    "Report Type": "Volunteer",
    "Reported by": {
        "id": "usr3nFXwxJnpVjv4i",
        "name": "Help.vaccinateCA RW Role account for API token",
        "email": "jesse+role-rw-help-vaccinateca@vaccinateca.com",
    },
    "Notes": "Jan 23: Has vaccine but no appointments available.",
    "airtable_id": "recXBlDw9Zr7bB84O",
    "location_id": ["rec00NpJzUnVDpLaQ"],
    "Availability": [
        "Yes: vaccinating 65+",
        "Yes: appointment required",
        "Yes: appointment calendar currently full",
    ],
    "tmp_eva_flips": [None],
    "Internal Notes": "Essential workers start March 1st\n",
    "Do not call until": "2021-02-26T00:49:34.606Z",
    "auth0_reporter_id": "auth0|6037",
    "auth0_reporter_name": "S B",
    "Name (from Location)": ["RITE AID PHARMACY 05537"],
    "airtable_createdTime": "2021-02-25T23:54:04.000Z",
    "auth0_reporter_roles": "Volunteer Caller",
    "Appointments by phone?": True,
    "County (from Location)": ["Los Angeles County"],
    "location_latest_report_id": [26383],
    "Affiliation (from Location)": ["Rite-Aid"],
    "location_latest_report_time": ["2021-02-25T23:54:04.000Z"],
    "Location Type (from Location)": ["Pharmacy"],
    "is_latest_report_for_location": 1,
    "location_latest_eva_report_time": ["2021-02-24T05:16:09.000Z"],
    "Number of Reports (from Location)": [3],
    "Appointment scheduling instructions": "Uses county scheduling system",
}


@pytest.mark.django_db
def test_import_airtable_report_post_help_vaccinate_launch_using_api(client, api_key):
    # This report is from AFTER help.vaccinateca app launched
    assert not Report.objects.filter(airtable_id="recXBlDw9Zr7bB84O").exists()

    import_airtable_location(location_json)

    # Do this one with the API
    response = client.post(
        "/api/importReports",
        [POST_HELP_LAUNCH_REPORT],
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    assert response.json() == {
        "added": ["recXBlDw9Zr7bB84O"],
        "updated": [],
        "errors": [],
    }

    report = Report.objects.get(airtable_id="recXBlDw9Zr7bB84O")
    assert report.report_source == "ca"
    assert report.appointment_tag.slug == "county_website"
    assert report.location.name == "Kaiser Permanente Pharmacy #568"
    assert report.internal_notes == "Essential workers start March 1st\n"
    assert report.public_notes == "Jan 23: Has vaccine but no appointments available."
    assert report.reported_by.external_id == "auth0:auth0|6037"
    assert report.reported_by.auth0_role_names == "Volunteer Caller"
    assert str(report.created_at) == "2021-02-25 23:54:04+00:00"
    assert report.airtable_id == "recXBlDw9Zr7bB84O"
    assert report.public_id == "recXBlDw9Zr7bB84O"
    assert set(report.availability_tags.values_list("name", flat=True)) == {
        "Vaccinating 65+",
        "Appointment required",
        "Appointment calendar currently full",
    }


@pytest.mark.parametrize(
    "appointments_by_phone,appointment_scheduling_instructions,expected_tag,expected_instructions",
    (
        (True, "555-555-5555", "phone", "555-555-5555"),
        (True, "Uses county scheduling system", "county_website", None),
        (False, "Uses county scheduling system", "county_website", None),
        (False, "https://myturn.ca.gov/", "myturn_ca_gov", None),
        (False, "www.example.com", "web", "www.example.com"),
        (False, "http://www.example.com", "web", "http://www.example.com"),
        (False, "https://www.example.com", "web", "https://www.example.com"),
        (False, "Something else", "other", "Something else"),
    ),
)
def test_derive_appointment_tag(
    appointments_by_phone,
    appointment_scheduling_instructions,
    expected_tag,
    expected_instructions,
):
    actual_tag, actual_instructions = derive_appointment_tag(
        appointments_by_phone, appointment_scheduling_instructions
    )
    assert actual_tag == expected_tag
    assert actual_instructions == expected_instructions


@pytest.mark.django_db
def test_import_soft_deleted_location():
    location_json_copy = dict(location_json)
    location_json_copy["is_soft_deleted"] = True

    location = import_airtable_location(location_json_copy)

    assert location.soft_deleted


@pytest.mark.django_db
def test_import_duplicate_location(ten_locations):
    other = ten_locations[0]
    location_json_copy = dict(location_json)
    location_json_copy["is_soft_deleted"] = True
    location_json_copy["duplicate_of"] = [other.public_id]

    location = import_airtable_location(location_json_copy)

    assert location.soft_deleted
    assert location.duplicate_of == other
