import datetime
from unittest import mock
from unittest.mock import MagicMock

import orjson
import pytest
from core.exporter import api, dataset, storage

from .models import (
    AppointmentTag,
    AvailabilityTag,
    County,
    Location,
    LocationType,
    Provider,
    ProviderType,
    Reporter,
    State,
)


@pytest.mark.django_db
@mock.patch("core.exporter.api_export")
def test_post_to_api_export_endpoint(api_export, client, api_key):
    # Return error if not authenticated
    assert not api_export.called
    response = client.post("/api/export")
    assert response.status_code == 403
    assert not api_export.called
    # With API key should work
    response = client.post(
        "/api/export", HTTP_AUTHORIZATION="Bearer {}".format(api_key)
    )
    assert response.status_code == 200
    assert api_export.called
    assert response.content == b'{"ok": 1}'


@pytest.mark.django_db
def test_dataset(django_assert_num_queries):
    county = County.objects.get(fips_code="06079")  # San Luis Obispo
    location = Location.objects.create(
        county=county,
        state=State.objects.get(abbreviation="CA"),
        name="SLO Pharmacy",
        phone_number="555 555-5555",
        full_address="5 5th Street",
        location_type=LocationType.objects.get(name="Pharmacy"),
        latitude=35.279,
        longitude=-120.664,
    )

    # Two queries of these four are for the atomic savepoint; the
    # other is for the locations.
    with django_assert_num_queries(3):
        with dataset() as ds:
            locations = list(ds.locations)
    assert len(locations) == 1

    location_report = locations[0]
    assert location_report.county.name == "San Luis Obispo"
    assert location_report.name == "SLO Pharmacy"

    reporter = Reporter.objects.get_or_create(external_id="auth0:reporter")[0]
    web = AppointmentTag.objects.get(slug="web")
    report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
    )
    # Add multiple tags so we catch any issues with rollups and de-duplication
    plus_65 = AvailabilityTag.objects.get(slug="vaccinating_65_plus")
    report.availability_tags.add(plus_65)
    current_patient = AvailabilityTag.objects.get(slug="must_be_a_current_patient")
    report.availability_tags.add(current_patient)

    # This is now four queries; two for savepoint, one for locations,
    # and an additional prefetch of the latest calls'
    # availability_tags, which is one query for all locations.
    with django_assert_num_queries(4):
        with dataset() as ds:
            assert locations == list(ds.locations)

    # Two queries for the savepoint, one for the counties.
    with django_assert_num_queries(3):
        with dataset() as ds:
            counties = list(ds.counties)

            assert len(counties) == 58
            for c in counties:
                if c.name == "San Luis Obispo":
                    assert c.locations_with_reports == 1
                    assert c.locations_with_latest_yes == 1
                else:
                    assert c.locations_with_reports == 0
                    assert c.locations_with_latest_yes == 0

    # Add a flagged no report should not alter the results
    no_report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
        is_pending_review=True,
    )
    no_inventory = AvailabilityTag.objects.get(slug="no_vaccine_inventory")
    no_report.availability_tags.add(no_inventory)
    no_report.save()
    with dataset() as ds:
        assert counties == list(ds.counties)
        slo = [c for c in counties if c.name == "San Luis Obispo"][0]
        assert slo.locations_with_reports == 1
        assert slo.locations_with_latest_yes == 1

    # Unflag the no, which should decrement the yeses down to 0
    no_report.is_pending_review = False
    no_report.save()
    with dataset() as ds:
        counties = list(ds.counties)
        slo = [c for c in counties if c.name == "San Luis Obispo"][0]
        assert slo.locations_with_reports == 1
        assert slo.locations_with_latest_yes == 0

    # Add a skip, which should change nothing
    skip_report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
    )
    skip_tag = AvailabilityTag.objects.get(slug="skip_call_back_later")
    skip_report.availability_tags.add(skip_tag)
    skip_report.save()
    with dataset() as ds:
        assert counties == list(ds.counties)
        assert ds.locations.count() == 1

    # Set planned closure on most recent report, which should remove it
    no_report.planned_closure = datetime.date.today() - datetime.timedelta(days=1)
    no_report.save()
    with dataset() as ds:
        assert ds.locations.count() == 0


@pytest.mark.django_db
def test_v1_provider_contents(django_assert_num_queries):
    Provider.objects.create(
        name="Example Pharmacy Chain",
        provider_type=ProviderType.objects.get(name="Pharmacy"),
        public_notes="Details about this chain",
        contact_phone_number="(800) 555-1234",
        main_url="https://pharmacy.example.com/",
        appointments_url="https://pharmacy.example.com/appointments/",
        vaccine_info_url="https://pharmacy.example.com/covid/",
        vaccine_locations_url="https://pharmacy.example.com/locations/",
    )
    # Two queries of these four are for the atomic savepoint.  The
    # other two fetch all of the provider information, and the
    # many-to-many information for phases.
    with django_assert_num_queries(4):
        with dataset() as ds:
            providers = api(1, ds).get_providers()
            assert len(providers) == 1
    assert providers[0]["Provider"] == "Example Pharmacy Chain"
    assert providers[0]["Provider network type"] == "Pharmacy"


@pytest.mark.django_db
def test_v1_location_county_contents(django_assert_num_queries):
    county = County.objects.get(fips_code="06079")  # San Luis Obispo
    location = Location.objects.create(
        county=county,
        state=State.objects.get(abbreviation="CA"),
        name="SLO Pharmacy",
        phone_number="555 555-5555",
        full_address="5 5th Street",
        location_type=LocationType.objects.get(name="Pharmacy"),
        latitude=35.279,
        longitude=-120.664,
    )
    reporter = Reporter.objects.get_or_create(external_id="auth0:reporter")[0]
    web = AppointmentTag.objects.get(slug="web")
    report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
    )
    # Add multiple tags so we catch any issues with rollups and de-duplication
    plus_65 = AvailabilityTag.objects.get(slug="vaccinating_65_plus")
    report.availability_tags.add(plus_65)
    current_patient = AvailabilityTag.objects.get(slug="must_be_a_current_patient")
    report.availability_tags.add(current_patient)

    # Two queries of these four are for the atomic savepoint.  The
    # other two are the locations, and the prefetch to get the
    # one-to-many availability tags.
    #
    # If this assert begins failing, it is likely because an
    # additional column is being accessed that is not in the .only()
    # call inside dataset(); this causes an extra query per row, with
    # disastrous performance consequences in production.
    #
    # Adjusting the number of queries is almost certainly not correct.
    with django_assert_num_queries(4):
        with dataset() as ds:
            locations = api(1, ds).get_locations()
            assert len(locations) == 1

    exported_location = locations[0]
    assert "id" in exported_location
    assert "internal_notes" not in exported_location
    assert exported_location["Has Report"] == 1
    assert exported_location["Latest report yes?"] == 1
    assert sorted(exported_location["Availability Info"]) == sorted(
        [
            "Yes: vaccinating 65+",
            "Yes: must be a current patient",
        ]
    )

    # Verify the data is as exoected on the counties side
    with django_assert_num_queries(3):
        with dataset() as ds:
            counties = api(1, ds).get_counties()
    assert len(counties) == 58
    slo = [c for c in counties if c["County"] == "San Luis Obispo County"][0]
    assert slo["Total reports"] == 1
    assert slo["Yeses"] == 1

    # Flag the report, so it disappears
    report.is_pending_review = True
    report.save()

    # With no reports, this is now only 3 queries, since we don't need
    # to fetch the availability tags.
    with django_assert_num_queries(3):
        with dataset() as ds:
            locations = api(1, ds).get_locations()
            assert len(locations) == 1
    exported_location = locations[0]
    assert exported_location["Has Report"] == 0
    assert exported_location["Latest report yes?"] == 0
    assert "Availability Info" not in exported_location

    with django_assert_num_queries(3):
        with dataset() as ds:
            counties = api(1, ds).get_counties()
    slo = [c for c in counties if c["County"] == "San Luis Obispo County"][0]
    assert slo["Total reports"] == 0
    assert slo["Yeses"] == 0

    # Make a no on top of the flagged yes, so the no is the latest
    no_report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
    )
    no_inventory = AvailabilityTag.objects.get(slug="no_vaccine_inventory")
    no_report.availability_tags.add(no_inventory)
    no_report.save()

    # This has a report, so we're back to needing the 4th query for
    # all location tags
    with django_assert_num_queries(4):
        with dataset() as ds:
            locations = api(1, ds).get_locations()
            assert len(locations) == 1
    exported_location = locations[0]
    assert exported_location["Has Report"] == 1
    assert exported_location["Latest report yes?"] == 0
    assert exported_location["Availability Info"] == [
        "No: no vaccine inventory",
    ]

    with django_assert_num_queries(3):
        with dataset() as ds:
            counties = api(1, ds).get_counties()
    slo = [c for c in counties if c["County"] == "San Luis Obispo County"][0]
    assert slo["Total reports"] == 1
    assert slo["Yeses"] == 0

    # Set the planned_closure on that report to yesterday
    no_report.planned_closure = datetime.date.today() - datetime.timedelta(days=1)
    no_report.save()
    with dataset() as ds:
        locations = api(1, ds).get_locations()
        assert len(locations) == 0


@pytest.mark.django_db
def test_api_v0_framing():
    writer = MagicMock()
    with dataset() as ds:
        api(0, ds).write(writer)

    # We expect to have written three endpoints
    writer.write.assert_called()
    calls = writer.write.call_args_list
    assert len(calls) == 2
    assert set(["Locations.json", "Counties.json"]) == set([c.args[0] for c in calls])

    # Verify that they have no metadata
    for c in calls:
        output = c.args[1]
        data = orjson.loads(b"".join(output))
        assert isinstance(data, list)


@pytest.mark.django_db
def test_api_v1_framing():
    writer = MagicMock()
    with dataset() as ds:
        api(1, ds).write(writer)

    # We expect to have written three endpoints
    writer.write.assert_called()
    calls = writer.write.call_args_list
    assert len(calls) == 3
    assert (
        set(
            [
                "locations.json",
                "providers.json",
                "counties.json",
            ]
        )
        == set([c.args[0] for c in calls])
    )

    # Verify that the V1 had metadata on it
    for c in calls:
        output = c.args[1]
        data = orjson.loads(b"".join(output))
        assert "usage" in data
        assert "content" in data
        assert isinstance(data["content"], list)


@pytest.mark.django_db
def test_api_serialization():
    county = County.objects.get(fips_code="06079")  # San Luis Obispo
    location = Location.objects.create(
        county=county,
        state=State.objects.get(abbreviation="CA"),
        name="SLO Pharmacy",
        phone_number="555 555-5555",
        full_address="5 5th Street",
        location_type=LocationType.objects.get(name="Pharmacy"),
        latitude=35.279,
        longitude=-120.664,
    )
    reporter = Reporter.objects.get_or_create(external_id="auth0:reporter")[0]
    web = AppointmentTag.objects.get(slug="web")
    report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
    )
    plus_65 = AvailabilityTag.objects.get(slug="vaccinating_65_plus")
    report.availability_tags.add(plus_65)
    current_patient = AvailabilityTag.objects.get(slug="must_be_a_current_patient")
    report.availability_tags.add(current_patient)

    writer = storage.DebugWriter()
    with dataset() as ds:
        api(1, ds).write(writer)
        api(0, ds).write(writer)


@pytest.mark.django_db
def test_api_export_vaccinate_the_states(client, ten_locations):
    client.post("/api/exportVaccinateTheStates")
