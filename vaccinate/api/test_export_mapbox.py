import datetime
import json

import pytest
from core.models import AppointmentTag, AvailabilityTag, Reporter


def test_export_mapbox_location_with_no_report(client, ten_locations):
    location = ten_locations[0]
    response = client.get(
        "/api/export-mapbox-preview?id={}&raw=1".format(location.public_id)
    )
    data = json.loads(response.content)["geojson"][0]
    assert data == {
        "type": "Feature",
        "properties": {
            "id": location.public_id,
            "name": "Location 1",
            "location_type": "Hospital / Clinic",
            "website": None,
            "address": None,
            "county": None,
            "state_abbreviation": "OR",
            "phone_number": "(555) 555-5501",
            "google_places_id": None,
            "vaccinefinder_location_id": None,
            "vaccinespotter_location_id": None,
            "hours": None,
        },
        "geometry": {"type": "Point", "coordinates": [40.0, 30.0]},
    }


@pytest.mark.parametrize(
    "vaccines_offered,availability_tags,expected_booleans",
    (
        (["Pfizer", "Moderna"], [], ["vaccine_pfizer", "vaccine_moderna"]),
        (["Pfizer"], [], ["vaccine_pfizer"]),
        (["Johnson & Johnson"], [], ["vaccine_jj"]),
        ([], ["appointments_or_walkins"], ["available_walkins"]),
        ([], ["walk_ins_accepted"], ["available_walkins"]),
        ([], ["appointments_available"], ["available_appointments"]),
    ),
)
def test_export_mapbox_location_with_report(
    client, ten_locations, vaccines_offered, availability_tags, expected_booleans
):
    location = ten_locations[0]
    reporter = Reporter.objects.get_or_create(external_id="auth0:reporter")[0]
    web = AppointmentTag.objects.get(slug="web")
    report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
        planned_closure="2029-05-01",
        vaccines_offered=vaccines_offered,
        restriction_notes="No notes",
    )
    for tag in availability_tags:
        report.availability_tags.add(AvailabilityTag.objects.get(slug=tag))
    report.refresh_from_db()
    response = client.get(
        "/api/export-mapbox-preview?id={}&raw=1".format(location.public_id)
    )
    data = json.loads(response.content)["geojson"][0]
    expected_properties = {
        "id": location.public_id,
        "name": "Location 1",
        "location_type": "Hospital / Clinic",
        "website": None,
        "address": None,
        "county": None,
        "state_abbreviation": "OR",
        "phone_number": "(555) 555-5501",
        "google_places_id": None,
        "vaccinefinder_location_id": None,
        "vaccinespotter_location_id": None,
        "hours": None,
        "public_notes": None,
        "appointment_method": "web",
        "appointment_details": None,
        "latest_contact": report.created_at.isoformat(),
        "planned_closure": "2029-05-01",
        "restriction_notes": "No notes",
    }
    for property in expected_booleans:
        expected_properties[property] = True

    assert data == {
        "type": "Feature",
        "properties": expected_properties,
        "geometry": {"type": "Point", "coordinates": [40.0, 30.0]},
    }


@pytest.mark.parametrize("has_planned_closure", (True, False))
def test_planned_closure_location_not_returned(
    client, ten_locations, has_planned_closure
):
    location = ten_locations[0]
    reporter = Reporter.objects.get_or_create(external_id="auth0:reporter")[0]
    web = AppointmentTag.objects.get(slug="web")
    planned_closure = (
        (datetime.date.today() - datetime.timedelta(days=1))
        if has_planned_closure
        else None
    )
    location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
        planned_closure=planned_closure,
    )
    response = client.get(
        "/api/export-mapbox-preview?id={}&raw=1".format(location.public_id)
    )
    geojson = json.loads(response.content)["geojson"]
    assert isinstance(geojson, list)
    if has_planned_closure:
        assert len(geojson) == 0
    else:
        assert len(geojson) == 1
