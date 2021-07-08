import datetime

import pytest
from django.utils import timezone

from .models import AppointmentTag, AvailabilityTag, DerivedResults, Location, Reporter


@pytest.fixture
def reporter(db):
    return Reporter.objects.get_or_create(external_id="auth0:reporter")[0]


def assert_derived_results_match(location, expected):
    assert location.derive_details() == expected
    # Now try it with save=
    location.derive_details(save=True)
    location2 = Location.objects.get(pk=location.pk)
    for key, value in expected._asdict().items():
        if key not in (
            "most_recent_report_on_vaccines_offered",
            "most_recent_source_location_on_vaccines_offered",
            "most_recent_report_on_availability",
            "most_recent_source_location_on_availability",
            "most_recent_source_location_on_hours_json",
        ):
            assert getattr(location2, key) == value


def test_no_reports_no_source_locations(location):
    assert_derived_results_match(
        location,
        DerivedResults(
            vaccines_offered=None,
            vaccines_offered_provenance_report=None,
            vaccines_offered_provenance_source_location=None,
            vaccines_offered_last_updated_at=None,
            accepts_appointments=None,
            accepts_walkins=None,
            appointments_walkins_provenance_report=None,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=None,
            hours_json=None,
            hours_json_last_updated_at=None,
            hours_json_provenance_source_location=None,
            most_recent_report_on_vaccines_offered=None,
            most_recent_source_location_on_vaccines_offered=None,
            most_recent_report_on_availability=None,
            most_recent_source_location_on_availability=None,
            most_recent_source_location_on_hours_json=None,
        ),
    )


def test_one_report_vaccines_offered(location, reporter):
    web = AppointmentTag.objects.get(slug="web")
    report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
        vaccines_offered=["Pfizer"],
    )
    assert_derived_results_match(
        location,
        DerivedResults(
            vaccines_offered=["Pfizer"],
            vaccines_offered_provenance_report=report,
            vaccines_offered_provenance_source_location=None,
            vaccines_offered_last_updated_at=report.created_at,
            accepts_appointments=False,
            accepts_walkins=False,
            appointments_walkins_provenance_report=report,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=report.created_at,
            hours_json=None,
            hours_json_last_updated_at=None,
            hours_json_provenance_source_location=None,
            most_recent_report_on_vaccines_offered=report,
            most_recent_source_location_on_vaccines_offered=None,
            most_recent_report_on_availability=report,
            most_recent_source_location_on_availability=None,
            most_recent_source_location_on_hours_json=None,
        ),
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
    assert_derived_results_match(
        location,
        DerivedResults(
            vaccines_offered=["Pfizer"],
            vaccines_offered_provenance_report=report,
            vaccines_offered_provenance_source_location=None,
            vaccines_offered_last_updated_at=report.created_at,
            accepts_appointments=False,
            accepts_walkins=False,
            appointments_walkins_provenance_report=report,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=report.created_at,
            hours_json=None,
            hours_json_last_updated_at=None,
            hours_json_provenance_source_location=None,
            most_recent_report_on_vaccines_offered=report,
            most_recent_source_location_on_vaccines_offered=None,
            most_recent_report_on_availability=report,
            most_recent_source_location_on_availability=None,
            most_recent_source_location_on_hours_json=None,
        ),
    )


def test_one_source_location_vaccines_offered(location):
    source_location = location.matched_source_locations.create(
        source_uid="vaccinefinder_org:1",
        source_name="vaccinefinder_org",
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
    assert_derived_results_match(
        location,
        DerivedResults(
            vaccines_offered=["Johnson & Johnson", "Pfizer"],
            vaccines_offered_provenance_report=None,
            vaccines_offered_provenance_source_location=source_location,
            vaccines_offered_last_updated_at=source_location.last_imported_at,
            accepts_appointments=None,
            accepts_walkins=None,
            appointments_walkins_provenance_report=None,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=None,
            hours_json=None,
            hours_json_last_updated_at=None,
            hours_json_provenance_source_location=None,
            most_recent_report_on_vaccines_offered=None,
            most_recent_source_location_on_vaccines_offered=source_location,
            most_recent_report_on_availability=None,
            most_recent_source_location_on_availability=None,
            most_recent_source_location_on_hours_json=None,
        ),
    )


def test_two_source_locations_vaccines_offered(location):
    location.matched_source_locations.create(
        source_uid="vaccinefinder_org:1",
        source_name="vaccinefinder_org",
        name="Blah",
        import_json={
            "inventory": [
                {"vaccine": "pfizer_biontech"},
            ]
        },
        last_imported_at=timezone.now() - datetime.timedelta(hours=2),
    )
    source_location2 = location.matched_source_locations.create(
        source_uid="vaccinefinder_org:2",
        source_name="vaccinefinder_org",
        name="Blah",
        import_json={
            "inventory": [
                {"vaccine": "johnson_johnson_janssen", "supply_level": "in_stock"},
            ]
        },
        last_imported_at=timezone.now() - datetime.timedelta(hours=1),
    )
    assert_derived_results_match(
        location,
        DerivedResults(
            vaccines_offered=["Johnson & Johnson"],
            vaccines_offered_provenance_report=None,
            vaccines_offered_provenance_source_location=source_location2,
            vaccines_offered_last_updated_at=source_location2.last_imported_at,
            accepts_appointments=None,
            accepts_walkins=None,
            appointments_walkins_provenance_report=None,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=None,
            hours_json=None,
            hours_json_last_updated_at=None,
            hours_json_provenance_source_location=None,
            most_recent_report_on_vaccines_offered=None,
            most_recent_source_location_on_vaccines_offered=source_location2,
            most_recent_report_on_availability=None,
            most_recent_source_location_on_availability=None,
            most_recent_source_location_on_hours_json=None,
        ),
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
        source_uid="vaccinefinder_org:1",
        source_name="vaccinefinder_org",
        name="Blah",
        import_json={
            "inventory": [
                {"vaccine": "moderna", "supply_level": "in_stock"},
            ]
        },
        last_imported_at=source_location_imported_at,
    )
    if report_is_most_recent:
        expected = DerivedResults(
            vaccines_offered=["Pfizer"],
            vaccines_offered_provenance_report=report,
            vaccines_offered_provenance_source_location=None,
            vaccines_offered_last_updated_at=report.created_at,
            accepts_appointments=False,
            accepts_walkins=False,
            appointments_walkins_provenance_report=report,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=report.created_at,
            hours_json=None,
            hours_json_last_updated_at=None,
            hours_json_provenance_source_location=None,
            most_recent_report_on_vaccines_offered=report,
            most_recent_source_location_on_vaccines_offered=source_location,
            most_recent_report_on_availability=report,
            most_recent_source_location_on_availability=None,
            most_recent_source_location_on_hours_json=None,
        )
    else:
        expected = DerivedResults(
            vaccines_offered=["Moderna"],
            vaccines_offered_provenance_report=None,
            vaccines_offered_provenance_source_location=source_location,
            vaccines_offered_last_updated_at=source_location.last_imported_at,
            accepts_appointments=False,
            accepts_walkins=False,
            appointments_walkins_provenance_report=report,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=report.created_at,
            hours_json=None,
            hours_json_last_updated_at=None,
            hours_json_provenance_source_location=None,
            most_recent_report_on_vaccines_offered=report,
            most_recent_source_location_on_vaccines_offered=source_location,
            most_recent_report_on_availability=report,
            most_recent_source_location_on_availability=None,
            most_recent_source_location_on_hours_json=None,
        )
    assert_derived_results_match(location, expected)


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
    assert_derived_results_match(
        location,
        DerivedResults(
            vaccines_offered=None,
            vaccines_offered_provenance_report=None,
            vaccines_offered_provenance_source_location=None,
            vaccines_offered_last_updated_at=None,
            accepts_appointments=expected_accepts_appointments,
            accepts_walkins=expected_accepts_walkins,
            appointments_walkins_provenance_report=report,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=report.created_at,
            hours_json=None,
            hours_json_last_updated_at=None,
            hours_json_provenance_source_location=None,
            most_recent_report_on_vaccines_offered=None,
            most_recent_source_location_on_vaccines_offered=None,
            most_recent_report_on_availability=report,
            most_recent_source_location_on_availability=None,
            most_recent_source_location_on_hours_json=None,
        ),
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
        source_uid="vaccinefinder_org:1",
        source_name="vaccinefinder_org",
        name="Blah",
        import_json={
            "availability": import_json_availability,
        },
        last_imported_at=timezone.now() - datetime.timedelta(hours=1),
    )
    assert_derived_results_match(
        location,
        DerivedResults(
            vaccines_offered=None,
            vaccines_offered_provenance_report=None,
            vaccines_offered_provenance_source_location=None,
            vaccines_offered_last_updated_at=None,
            accepts_appointments=expected_accepts_appointments,
            accepts_walkins=expected_accepts_walkins,
            appointments_walkins_provenance_report=None,
            appointments_walkins_provenance_source_location=source_location,
            appointments_walkins_last_updated_at=source_location.last_imported_at,
            hours_json=None,
            hours_json_last_updated_at=None,
            hours_json_provenance_source_location=None,
            most_recent_report_on_vaccines_offered=None,
            most_recent_source_location_on_vaccines_offered=None,
            most_recent_report_on_availability=None,
            most_recent_source_location_on_availability=source_location,
            most_recent_source_location_on_hours_json=None,
        ),
    )


@pytest.mark.parametrize(
    "source_name,should_be_trusted",
    (
        ("vaccinefinder_org", True),
        ("vaccinespotter_org", True),
        ("getmyvax_org", True),
        ("not_one_of_them", False),
    ),
)
def test_only_trust_source_locations_from_specific_source_names(
    location,
    source_name,
    should_be_trusted,
):
    source_location = location.matched_source_locations.create(
        source_uid="{}:1".format(source_name),
        source_name=source_name,
        name="Blah",
        import_json={"availability": {"appointments": True, "drop_in": True}},
        last_imported_at=timezone.now() - datetime.timedelta(hours=1),
    )
    derived = location.derive_details()
    if should_be_trusted:
        assert (
            derived.appointments_walkins_provenance_source_location == source_location
        )
        assert derived.accepts_appointments
        assert derived.accepts_walkins
    else:
        assert derived.appointments_walkins_provenance_source_location is None
        assert not derived.accepts_appointments
        assert not derived.accepts_walkins


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
        source_uid="vaccinefinder_org:3",
        source_name="vaccinefinder_org",
        name="Blah",
        import_json={"availability": {"appointments": True, "drop_in": False}},
        last_imported_at=source_location_imported_at,
    )
    if report_is_most_recent:
        expected = DerivedResults(
            vaccines_offered=None,
            vaccines_offered_provenance_report=None,
            vaccines_offered_provenance_source_location=None,
            vaccines_offered_last_updated_at=None,
            accepts_appointments=False,
            accepts_walkins=True,
            appointments_walkins_provenance_report=report,
            appointments_walkins_provenance_source_location=None,
            appointments_walkins_last_updated_at=report.created_at,
            hours_json=None,
            hours_json_last_updated_at=None,
            hours_json_provenance_source_location=None,
            most_recent_report_on_vaccines_offered=None,
            most_recent_source_location_on_vaccines_offered=None,
            most_recent_report_on_availability=report,
            most_recent_source_location_on_availability=source_location,
            most_recent_source_location_on_hours_json=None,
        )
    else:
        expected = DerivedResults(
            vaccines_offered=None,
            vaccines_offered_provenance_report=None,
            vaccines_offered_provenance_source_location=None,
            vaccines_offered_last_updated_at=None,
            accepts_appointments=True,
            accepts_walkins=False,
            appointments_walkins_provenance_report=None,
            appointments_walkins_provenance_source_location=source_location,
            appointments_walkins_last_updated_at=source_location.last_imported_at,
            hours_json=None,
            hours_json_last_updated_at=None,
            hours_json_provenance_source_location=None,
            most_recent_report_on_vaccines_offered=None,
            most_recent_source_location_on_vaccines_offered=None,
            most_recent_report_on_availability=report,
            most_recent_source_location_on_availability=source_location,
            most_recent_source_location_on_hours_json=None,
        )
    assert_derived_results_match(location, expected)


@pytest.mark.parametrize(
    "source_name,should_be_trusted",
    (
        ("vaccinefinder_org", True),
        ("getmyvax_org", False),
        ("not_one_of_them", False),
    ),
)
def test_hours_json_from_source_location(
    location,
    source_name,
    should_be_trusted,
):
    hours = [
        {"day": "monday", "opens": "08:00", "closes": "18:00"},
        {"day": "tuesday", "opens": "08:00", "closes": "18:00"},
    ]
    source_location = location.matched_source_locations.create(
        source_uid="{}:1".format(source_name),
        source_name=source_name,
        name="Blah",
        import_json={"opening_hours": hours},
        last_imported_at=timezone.now() - datetime.timedelta(hours=1),
    )
    derived = location.derive_details()
    if should_be_trusted:
        assert derived.hours_json_provenance_source_location == source_location
        assert derived.hours_json == hours
    else:
        assert derived.hours_json_provenance_source_location is None
        assert not derived.hours_json
