from .models import Location, CallReport
from .import_utils import import_airtable_location, import_airtable_report
import pytest


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
def test_import_airtable_report():
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
        "location_id": ["receRct4dcHKQmvDs"],
        "location_latest_eva_report_time": ["2021-02-20T03:33:41.000Z"],
        "location_latest_report_id": [21388],
        "location_latest_report_time": ["2021-02-20T05:09:06.000Z"],
        "parent_external_report": ["recTghCHUuoq2ZNkf"],
        "report_id": "reczzhVUpoBQb6CUA",
        "soft-dropped-column: Vaccines available?": "No",
        "time": "2021-01-28T03:19:51.000Z",
        "tmp_eva_flips": [None],
    }
    assert not CallReport.objects.filter(airtable_id="rec00NpJzUnVDpLaQ").exists()

    # The location would have been created already
    import_airtable_location(location_json)

    report = import_airtable_report(report_json)

    assert report.report_source == "ca"
    assert report.appointment_tag.name == "other"
    assert report.location.name == "Kaiser Permanente Pharmacy #568"
    assert (
        report.internal_notes
        == "The automotive mentioned that riteaid.com will have all the information they're looking for. As soon as they get the vaccines, based on eligibility they are going to deliver it to the public\n"
    )
    assert report.reported_by.airtable_name == "usrsCexDQt6GmdDm0"
    assert str(report.created_at) == "2021-01-28T03:19:51.000Z"
    assert report.airtable_id == "reczzhVUpoBQb6CUA"
    assert list(report.availability_tags.values_list("name", flat=True)) == [
        "No: no vaccine inventory"
    ]
