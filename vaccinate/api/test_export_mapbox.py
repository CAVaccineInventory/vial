import json

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


def test_export_mapbox_location_with_report(client, ten_locations):
    location = ten_locations[0]
    reporter = Reporter.objects.get_or_create(external_id="auth0:reporter")[0]
    web = AppointmentTag.objects.get(slug="web")
    report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
        planned_closure="2029-05-01",
        vaccines_offered=["Pfizer", "Moderna"],
        restriction_notes="No notes",
    )
    plus_65 = AvailabilityTag.objects.get(slug="vaccinating_65_plus")
    plus_50 = AvailabilityTag.objects.get(slug="vaccinating_50_plus")
    report.availability_tags.add(plus_65)
    report.availability_tags.add(plus_50)
    report.refresh_from_db()
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
            "public_notes": None,
            "appointment_method": "web",
            "appointment_details": None,
            "latest_contact": report.created_at.isoformat(),
            "availability_tags": [
                {
                    "name": "Vaccinating 50+",
                    "group": "yes",
                    "slug": "vaccinating_50_plus",
                },
                {
                    "name": "Vaccinating 65+",
                    "group": "yes",
                    "slug": "vaccinating_65_plus",
                },
            ],
            "planned_closure": "2029-05-01",
            "vaccines_offered": ["Pfizer", "Moderna"],
            "restriction_notes": "No notes",
        },
        "geometry": {"type": "Point", "coordinates": [40.0, 30.0]},
    }
