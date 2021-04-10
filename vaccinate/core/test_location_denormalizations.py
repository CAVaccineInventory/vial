import datetime

import pytest
from django.utils import timezone

from .models import (
    AppointmentTag,
    AvailabilityTag,
    County,
    Location,
    LocationType,
    Reporter,
    State,
)


@pytest.mark.django_db
def test_denormalized_location_report_columns():
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
    assert location.dn_latest_report is None
    assert location.dn_latest_report_including_pending is None
    assert location.dn_latest_yes_report is None
    assert location.dn_latest_skip_report is None
    assert location.dn_latest_non_skip_report is None
    assert location.dn_skip_report_count == 0
    assert location.dn_yes_report_count == 0
    # Now add an is_pending_review yes report
    reporter = Reporter.objects.get_or_create(external_id="auth0:reporter")[0]
    web = AppointmentTag.objects.get(slug="web")
    report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
        is_pending_review=True,
    )
    plus_65 = AvailabilityTag.objects.get(slug="vaccinating_65_plus")
    report.availability_tags.add(plus_65)
    location.refresh_from_db()
    assert location.dn_latest_report is None
    assert location.dn_latest_report_including_pending == report
    assert location.dn_latest_yes_report is None
    assert location.dn_latest_skip_report is None
    assert location.dn_latest_non_skip_report is None
    assert location.dn_skip_report_count == 0
    assert location.dn_yes_report_count == 0
    # Make it not pending any more
    report.is_pending_review = False
    report.save()
    location.refresh_from_db()
    assert location.dn_latest_report == report
    assert location.dn_latest_report_including_pending == report
    assert location.dn_latest_yes_report == report
    assert location.dn_latest_skip_report is None
    assert location.dn_latest_non_skip_report == report
    assert location.dn_skip_report_count == 0
    assert location.dn_yes_report_count == 1
    # Remove that availability tag - should no longer be a 'yes'
    report.availability_tags.remove(plus_65)
    location.refresh_from_db()
    assert location.dn_latest_report == report
    assert location.dn_latest_report_including_pending == report
    assert location.dn_latest_yes_report is None
    assert location.dn_latest_skip_report is None
    assert location.dn_latest_non_skip_report == report
    assert location.dn_skip_report_count == 0
    assert location.dn_yes_report_count == 0
    # Delete the report
    report.delete()
    location.refresh_from_db()
    assert location.dn_latest_report is None
    assert location.dn_latest_report_including_pending is None
    assert location.dn_latest_yes_report is None
    assert location.dn_latest_skip_report is None
    assert location.dn_latest_non_skip_report is None
    assert location.dn_skip_report_count == 0
    assert location.dn_yes_report_count == 0
    # Add a single skip report
    report2 = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
    )
    skip_call_back_later = AvailabilityTag.objects.get(slug="skip_call_back_later")
    report2.availability_tags.add(skip_call_back_later)
    location.refresh_from_db()
    assert location.dn_latest_report == report2
    assert location.dn_latest_report_including_pending == report2
    assert location.dn_latest_yes_report is None
    assert location.dn_latest_skip_report == report2
    assert location.dn_latest_non_skip_report is None
    assert location.dn_skip_report_count == 1
    assert location.dn_yes_report_count == 0
    # Add two yes reports and confirm that the latest one is correct
    report2.delete()
    early_yes = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
        created_at=timezone.now() - datetime.timedelta(days=1),
    )
    early_yes.availability_tags.add(plus_65)
    later_yes = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
        created_at=timezone.now(),
    )
    later_yes.availability_tags.add(plus_65)
    location.refresh_from_db()
    assert location.dn_latest_report == later_yes
    assert location.dn_latest_report_including_pending == later_yes
    assert location.dn_latest_yes_report == later_yes
    assert location.dn_skip_report_count == 0
    assert location.dn_yes_report_count == 2
    # Soft delete the later yes report
    later_yes.soft_deleted = True
    later_yes.save()
    location.refresh_from_db()
    assert location.dn_latest_report == early_yes
    assert location.dn_latest_report_including_pending == early_yes
    assert location.dn_latest_yes_report == early_yes
    assert location.dn_skip_report_count == 0
    assert location.dn_yes_report_count == 1
