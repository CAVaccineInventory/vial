from .models import Location, County, State
from .import_utils import import_airtable_location
import pytest


@pytest.mark.django_db
def test_import_airtable_location():
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
