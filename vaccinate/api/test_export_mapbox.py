import datetime

import orjson
import pytest
from core.models import AppointmentTag, AvailabilityTag, Reporter, SourceLocation


def test_export_mapbox_location_with_no_report(client, ten_locations):
    location = ten_locations[0]
    response = client.get(
        "/api/exportMapboxPreview?id={}&raw=1".format(location.public_id)
    )
    data = orjson.loads(response.content)["geojson"][0]
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
            "fidelity": 0,
        },
        "geometry": {"type": "Point", "coordinates": [40.0, 30.0]},
    }


@pytest.mark.parametrize(
    "inventory,expected_properties",
    (
        (
            [
                {
                    "guid": "779bfe52-0dd8-4023-a183-457eb100fccc",
                    "name": "Moderna COVID Vaccine",
                    "in_stock": "TRUE",
                    "supply_level": "NO_SUPPLY",
                },
                {
                    "guid": "a84fb9ed-deb4-461c-b785-e17c782ef88b",
                    "name": "Pfizer-BioNTech COVID Vaccine",
                    "in_stock": "FALSE",
                    "supply_level": "NO_SUPPLY",
                },
                {
                    "guid": "784db609-dc1f-45a5-bad6-8db02e79d44f",
                    "name": "Johnson & Johnson's Janssen COVID Vaccine",
                    "in_stock": "FALSE",
                    "supply_level": "NO_SUPPLY",
                },
            ],
            {"vaccine_moderna"},
        ),
        (
            [
                {
                    "guid": "779bfe52-0dd8-4023-a183-457eb100fccc",
                    "name": "Moderna COVID Vaccine",
                    "in_stock": "FALSE",
                    "supply_level": "NO_SUPPLY",
                },
                {
                    "guid": "a84fb9ed-deb4-461c-b785-e17c782ef88b",
                    "name": "Pfizer-BioNTech COVID Vaccine",
                    "in_stock": "TRUE",
                    "supply_level": "NO_SUPPLY",
                },
                {
                    "guid": "784db609-dc1f-45a5-bad6-8db02e79d44f",
                    "name": "Johnson & Johnson's Janssen COVID Vaccine",
                    "in_stock": "FALSE",
                    "supply_level": "NO_SUPPLY",
                },
            ],
            {"vaccine_pfizer"},
        ),
        (
            [
                {
                    "guid": "779bfe52-0dd8-4023-a183-457eb100fccc",
                    "name": "Moderna COVID Vaccine",
                    "in_stock": "FALSE",
                    "supply_level": "NO_SUPPLY",
                },
                {
                    "guid": "a84fb9ed-deb4-461c-b785-e17c782ef88b",
                    "name": "Pfizer-BioNTech COVID Vaccine",
                    "in_stock": "FALSE",
                    "supply_level": "NO_SUPPLY",
                },
                {
                    "guid": "784db609-dc1f-45a5-bad6-8db02e79d44f",
                    "name": "Johnson & Johnson/Janssen (age 18+)",
                    "in_stock": "TRUE",
                    "supply_level": "NO_SUPPLY",
                },
            ],
            {"vaccine_jj"},
        ),
    ),
)
def test_export_mapbox_location_with_vaccinefinder_source_location(
    client, ten_locations, inventory, expected_properties
):
    location = ten_locations[0]
    SourceLocation.objects.create(
        source_uid="uid",
        source_name="vaccinefinder_org",
        import_json={"source": {"data": {"inventory": inventory}}},
        matched_location=location,
    )
    response = client.get(
        "/api/exportMapboxPreview?id={}&raw=1".format(location.public_id)
    )
    data = orjson.loads(response.content)["geojson"][0]
    for property in ("vaccine_moderna", "vaccine_pfizer", "vaccine_jj"):
        if property in expected_properties:
            assert data["properties"][property]
        else:
            assert property not in data["properties"]


@pytest.mark.parametrize(
    "vaccines_offered,availability_tags,expected_booleans",
    (
        (["Pfizer", "Moderna"], [], ["vaccine_pfizer", "vaccine_moderna"]),
        (["Pfizer"], [], ["vaccine_pfizer"]),
        (["Johnson & Johnson"], [], ["vaccine_jj"]),
        (
            [],
            ["appointments_or_walkins"],
            ["available_walkins", "accepts_appointments", "accepts_walkins"],
        ),
        ([], ["walk_ins_only"], ["available_walkins", "accepts_walkins"]),
        (
            [],
            ["appointments_available"],
            ["available_appointments", "accepts_appointments"],
        ),
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
        "/api/exportMapboxPreview?id={}&raw=1".format(location.public_id)
    )
    data = orjson.loads(response.content)["geojson"][0]
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
        "fidelity": 1
        if any(v for v in expected_booleans if v.startswith("vaccine_"))
        else 0,
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
        "/api/exportMapboxPreview?id={}&raw=1".format(location.public_id)
    )
    geojson = orjson.loads(response.content)["geojson"]
    assert isinstance(geojson, list)
    if has_planned_closure:
        assert len(geojson) == 0
    else:
        assert len(geojson) == 1


@pytest.mark.parametrize(
    "tag",
    (
        "incorrect_contact_information",
        "location_permanently_closed",
        "may_be_a_vaccination_site_in_the_future",
        "not_open_to_the_public",
        "will_never_be_a_vaccination_site",
        "only_staff",
    ),
)
def test_locations_with_specific_availability_tags_not_exported(
    client, ten_locations, tag
):
    location = ten_locations[0]
    reporter = Reporter.objects.get_or_create(external_id="auth0:reporter")[0]
    web = AppointmentTag.objects.get(slug="web")
    report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
    )
    report.availability_tags.add(AvailabilityTag.objects.get(slug=tag))
    response = client.get(
        "/api/exportMapboxPreview?id={}&raw=1".format(location.public_id)
    )
    geojson = orjson.loads(response.content)["geojson"]
    assert isinstance(geojson, list)
    assert len(geojson) == 0
