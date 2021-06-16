import datetime

import pytest
from django.utils import timezone

from .models import (
    AppointmentTag,
    AvailabilityTag,
    DeriveAvailabilityAndInventoryResults,
    Reporter,
)


@pytest.fixture
def location(ten_locations):
    return ten_locations[0]


@pytest.fixture
def reporter(db):
    return Reporter.objects.get_or_create(external_id="auth0:reporter")[0]


def test_no_reports_no_source_locations(location):
    assert (
        location.derive_availability_and_inventory()
        == DeriveAvailabilityAndInventoryResults(
            vaccines_offered=None,
            vaccines_offered_provenance_report=None,
            vaccines_offered_provenance_source_location=None,
            vaccines_offered_last_updated_at=None,
            accepts_appointments=None,
            accepts_walkins=None,
            appointments_walkins_provenance_report=None,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=None,
            most_recent_report_on_vaccines_offered=None,
            most_recent_source_location_on_vaccines_offered=None,
            most_recent_report_on_availability=None,
            most_recent_source_location_on_availability=None,
        )
    )


def test_one_report_vaccines_offered(location, reporter):
    web = AppointmentTag.objects.get(slug="web")
    report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
        vaccines_offered=["Pfizer"],
    )
    assert (
        location.derive_availability_and_inventory()
        == DeriveAvailabilityAndInventoryResults(
            vaccines_offered=["Pfizer"],
            vaccines_offered_provenance_report=report,
            vaccines_offered_provenance_source_location=None,
            vaccines_offered_last_updated_at=report.created_at,
            accepts_appointments=False,
            accepts_walkins=False,
            appointments_walkins_provenance_report=report,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=report.created_at,
            most_recent_report_on_vaccines_offered=report,
            most_recent_source_location_on_vaccines_offered=None,
            most_recent_report_on_availability=report,
            most_recent_source_location_on_availability=None,
        )
    )


def test_two_reports_vaccines_offered_should_use_most_recent(location, reporter):
    web = AppointmentTag.objects.get(slug="web")
    report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
        vaccines_offered=["Pfizer"],
    )
    location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
        vaccines_offered=["Moderna"],
        created_at=timezone.now() - datetime.timedelta(days=1),
    )
    assert (
        location.derive_availability_and_inventory()
        == DeriveAvailabilityAndInventoryResults(
            vaccines_offered=["Pfizer"],
            vaccines_offered_provenance_report=report,
            vaccines_offered_provenance_source_location=None,
            vaccines_offered_last_updated_at=report.created_at,
            accepts_appointments=False,
            accepts_walkins=False,
            appointments_walkins_provenance_report=report,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=report.created_at,
            most_recent_report_on_vaccines_offered=report,
            most_recent_source_location_on_vaccines_offered=None,
            most_recent_report_on_availability=report,
            most_recent_source_location_on_availability=None,
        )
    )


def test_one_source_location_vaccines_offered(location):
    source_location = location.matched_source_locations.create(
        source_uid="test_source_location:1",
        source_name="test_source_location",
        name="Blah",
        import_json={
            "inventory": [
                {"vaccine": "moderna", "supply_level": "out_of_stock"},
                # No supply_level implies in-stock:
                {"vaccine": "pfizer_biontech"},
                {"vaccine": "johnson_johnson_janssen", "supply_level": "in_stock"},
            ]
        },
        last_imported_at=timezone.now() - datetime.timedelta(hours=1),
    )
    assert (
        location.derive_availability_and_inventory()
        == DeriveAvailabilityAndInventoryResults(
            vaccines_offered=["Johnson & Johnson", "Pfizer"],
            vaccines_offered_provenance_report=None,
            vaccines_offered_provenance_source_location=source_location,
            vaccines_offered_last_updated_at=source_location.last_imported_at,
            accepts_appointments=None,
            accepts_walkins=None,
            appointments_walkins_provenance_report=None,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=None,
            most_recent_report_on_vaccines_offered=None,
            most_recent_source_location_on_vaccines_offered=source_location,
            most_recent_report_on_availability=None,
            most_recent_source_location_on_availability=None,
        )
    )


def test_two_source_locations_vaccines_offered(location):
    location.matched_source_locations.create(
        source_uid="test_source_location:1",
        source_name="test_source_location",
        name="Blah",
        import_json={
            "inventory": [
                {"vaccine": "pfizer_biontech"},
            ]
        },
        last_imported_at=timezone.now() - datetime.timedelta(hours=2),
    )
    source_location2 = location.matched_source_locations.create(
        source_uid="test_source_location:2",
        source_name="test_source_location",
        name="Blah",
        import_json={
            "inventory": [
                {"vaccine": "johnson_johnson_janssen", "supply_level": "in_stock"},
            ]
        },
        last_imported_at=timezone.now() - datetime.timedelta(hours=1),
    )
    assert (
        location.derive_availability_and_inventory()
        == DeriveAvailabilityAndInventoryResults(
            vaccines_offered=["Johnson & Johnson"],
            vaccines_offered_provenance_report=None,
            vaccines_offered_provenance_source_location=source_location2,
            vaccines_offered_last_updated_at=source_location2.last_imported_at,
            accepts_appointments=None,
            accepts_walkins=None,
            appointments_walkins_provenance_report=None,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=None,
            most_recent_report_on_vaccines_offered=None,
            most_recent_source_location_on_vaccines_offered=source_location2,
            most_recent_report_on_availability=None,
            most_recent_source_location_on_availability=None,
        )
    )


@pytest.mark.parametrize("report_is_most_recent", (True, False))
def test_report_and_source_location_vaccines_offered_most_recent_wins(
    report_is_most_recent, reporter, location
):
    if report_is_most_recent:
        report_created_at = timezone.now() - datetime.timedelta(hours=1)
        source_location_imported_at = timezone.now() - datetime.timedelta(hours=2)
    else:
        report_created_at = timezone.now() - datetime.timedelta(hours=2)
        source_location_imported_at = timezone.now() - datetime.timedelta(hours=1)
    report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=AppointmentTag.objects.get(slug="web"),
        vaccines_offered=["Pfizer"],
        created_at=report_created_at,
    )
    source_location = location.matched_source_locations.create(
        source_uid="test_source_location:1",
        source_name="test_source_location",
        name="Blah",
        import_json={
            "inventory": [
                {"vaccine": "moderna", "supply_level": "in_stock"},
            ]
        },
        last_imported_at=source_location_imported_at,
    )
    if report_is_most_recent:
        expected = DeriveAvailabilityAndInventoryResults(
            vaccines_offered=["Pfizer"],
            vaccines_offered_provenance_report=report,
            vaccines_offered_provenance_source_location=None,
            vaccines_offered_last_updated_at=report.created_at,
            accepts_appointments=False,
            accepts_walkins=False,
            appointments_walkins_provenance_report=report,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=report.created_at,
            most_recent_report_on_vaccines_offered=report,
            most_recent_source_location_on_vaccines_offered=source_location,
            most_recent_report_on_availability=report,
            most_recent_source_location_on_availability=None,
        )
    else:
        expected = DeriveAvailabilityAndInventoryResults(
            vaccines_offered=["Moderna"],
            vaccines_offered_provenance_report=None,
            vaccines_offered_provenance_source_location=source_location,
            vaccines_offered_last_updated_at=source_location.last_imported_at,
            accepts_appointments=False,
            accepts_walkins=False,
            appointments_walkins_provenance_report=report,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=report.created_at,
            most_recent_report_on_vaccines_offered=report,
            most_recent_source_location_on_vaccines_offered=source_location,
            most_recent_report_on_availability=report,
            most_recent_source_location_on_availability=None,
        )
    assert location.derive_availability_and_inventory() == expected


@pytest.mark.parametrize(
    "availability_tags,expected_accepts_appointments,expected_accepts_walkins",
    (
        (["appointment_calendar_currently_full"], True, False),
        (["appointment_required"], True, False),
        (["appointments_available"], True, False),
        (["appointments_or_walkins"], True, True),
        (["walk_ins_only"], False, True),
        (["must_be_a_veteran"], False, False),
    ),
)
def test_one_report_availability(
    location,
    reporter,
    availability_tags,
    expected_accepts_appointments,
    expected_accepts_walkins,
):
    web = AppointmentTag.objects.get(slug="web")
    report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
    )
    for availability_tag in availability_tags:
        report.availability_tags.add(AvailabilityTag.objects.get(slug=availability_tag))
    assert (
        location.derive_availability_and_inventory()
        == DeriveAvailabilityAndInventoryResults(
            vaccines_offered=None,
            vaccines_offered_provenance_report=None,
            vaccines_offered_provenance_source_location=None,
            vaccines_offered_last_updated_at=None,
            accepts_appointments=expected_accepts_appointments,
            accepts_walkins=expected_accepts_walkins,
            appointments_walkins_provenance_report=report,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=report.created_at,
            most_recent_report_on_vaccines_offered=None,
            most_recent_source_location_on_vaccines_offered=None,
            most_recent_report_on_availability=report,
            most_recent_source_location_on_availability=None,
        )
    )


@pytest.mark.parametrize(
    "import_json_availability,expected_accepts_appointments,expected_accepts_walkins",
    (
        ({}, False, False),
        ({"appointments": True}, True, False),
        ({"appointments": False}, False, False),
        ({"drop_in": True}, False, True),
        ({"drop_in": False}, False, False),
        ({"appointments": True, "drop_in": False}, True, False),
        ({"appointments": False, "drop_in": True}, False, True),
        ({"appointments": False, "drop_in": False}, False, False),
        ({"appointments": True, "drop_in": True}, True, True),
    ),
)
def test_one_source_location_availability(
    location,
    import_json_availability,
    expected_accepts_appointments,
    expected_accepts_walkins,
):
    source_location = location.matched_source_locations.create(
        source_uid="test_source_location:1",
        source_name="test_source_location",
        name="Blah",
        import_json={
            "availability": import_json_availability,
        },
        last_imported_at=timezone.now() - datetime.timedelta(hours=1),
    )
    assert (
        location.derive_availability_and_inventory()
        == DeriveAvailabilityAndInventoryResults(
            vaccines_offered=None,
            vaccines_offered_provenance_report=None,
            vaccines_offered_provenance_source_location=None,
            vaccines_offered_last_updated_at=None,
            accepts_appointments=expected_accepts_appointments,
            accepts_walkins=expected_accepts_walkins,
            appointments_walkins_provenance_report=None,
            appointments_walkins_provenance_source_location=source_location,
            appointments_walkins_last_updated_at=source_location.last_imported_at,
            most_recent_report_on_vaccines_offered=None,
            most_recent_source_location_on_vaccines_offered=None,
            most_recent_report_on_availability=None,
            most_recent_source_location_on_availability=source_location,
        )
    )


@pytest.mark.parametrize("report_is_most_recent", (True, False))
def test_report_and_source_location_availability_most_recent_wins(
    report_is_most_recent, reporter, location
):
    if report_is_most_recent:
        report_created_at = timezone.now() - datetime.timedelta(hours=1)
        source_location_imported_at = timezone.now() - datetime.timedelta(hours=2)
    else:
        report_created_at = timezone.now() - datetime.timedelta(hours=2)
        source_location_imported_at = timezone.now() - datetime.timedelta(hours=1)
    report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=AppointmentTag.objects.get(slug="web"),
        created_at=report_created_at,
    )
    # The report says walk-ins only:
    report.availability_tags.add(AvailabilityTag.objects.get(slug="walk_ins_only"))
    # The source location says appointments only:
    source_location = location.matched_source_locations.create(
        source_uid="test_source_location:3",
        source_name="test_source_location",
        name="Blah",
        import_json={"availability": {"appointments": True, "drop_in": False}},
        last_imported_at=source_location_imported_at,
    )
    if report_is_most_recent:
        expected = DeriveAvailabilityAndInventoryResults(
            vaccines_offered=None,
            vaccines_offered_provenance_report=None,
            vaccines_offered_provenance_source_location=None,
            vaccines_offered_last_updated_at=None,
            accepts_appointments=False,
            accepts_walkins=True,
            appointments_walkins_provenance_report=report,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=report.created_at,
            most_recent_report_on_vaccines_offered=None,
            most_recent_source_location_on_vaccines_offered=None,
            most_recent_report_on_availability=report,
            most_recent_source_location_on_availability=source_location,
        )
    else:
        expected = DeriveAvailabilityAndInventoryResults(
            vaccines_offered=None,
            vaccines_offered_provenance_report=None,
            vaccines_offered_provenance_source_location=None,
            vaccines_offered_last_updated_at=None,
            accepts_appointments=True,
            accepts_walkins=False,
            appointments_walkins_provenance_report=None,
            appointments_walkins_provenance_source_location=source_location,
            appointments_walkins_last_updated_at=source_location.last_imported_at,
            most_recent_report_on_vaccines_offered=None,
            most_recent_source_location_on_vaccines_offered=None,
            most_recent_report_on_availability=report,
            most_recent_source_location_on_availability=source_location,
        )
    assert location.derive_availability_and_inventory() == expected
