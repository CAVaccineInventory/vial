from config.settings import SCRAPER_API_KEY
from core.models import (
    Report,
    Location,
    FeedProvider,
    AppointmentAvailabilityWindow,
    AppointmentAvailabilityReport,
    LocationFeedConcordance,
)
from api.models import ApiLog
import json
import pathlib
import pytest

tests_dir = pathlib.Path(__file__).parent / "test-data" / "submitAvailabilityReport"


@pytest.mark.django_db
def test_submit_availability_report_api_bad_token(client):
    response = client.post("/api/submitAvailabilityReport")
    assert response.json() == {"error": "Authorization header must start with 'Bearer'"}
    assert response.status_code == 403
    last_log = ApiLog.objects.order_by("-id")[0]
    assert {
        "method": "POST",
        "path": "/api/submitAvailabilityReport",
        "query_string": "",
        "remote_ip": "127.0.0.1",
        "response_status": 403,
        "created_report_id": None,
    }.items() <= last_log.__dict__.items()


@pytest.mark.django_db
def test_submit_report_api_invalid_json(client):
    response = client.post(
        "/api/submitAvailabilityReport",
        "This is bad JSON",
        content_type="text/plain",
        HTTP_AUTHORIZATION="Bearer {}".format(SCRAPER_API_KEY),
    )
    assert response.status_code == 400
    assert response.json()["error"] == "Expecting value: line 1 column 1 (char 0)"


@pytest.mark.django_db
@pytest.mark.parametrize("json_path", tests_dir.glob("*.json"))
def test_submit_report_api_example(client, json_path):
    fixture = json.load(json_path.open())
    assert Report.objects.count() == 0
    # Ensure location exists
    location, _ = Location.objects.get_or_create(
        public_id=fixture["location"],
        defaults={
            "latitude": 0,
            "longitude": 0,
            "location_type_id": 1,
            "state_id": 1,
            "county_id": 1,
        },
    )
    # Ensure feed provider exists
    provider, _ = FeedProvider.objects.get_or_create(
        name="Test feed", slug=fixture["input"]["feed_update"]["feed_provider"]
    )
    # Create concordance
    LocationFeedConcordance.objects.create(
        feed_provider=provider,
        location=location,
        provider_id=fixture["input"]["location"],
    )

    response = client.post(
        "/api/submitAvailabilityReport",
        fixture["input"],
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(SCRAPER_API_KEY),
    )
    assert response.status_code == fixture["expected_status"]
    # Load new report from DB and check it
    report = AppointmentAvailabilityReport.objects.order_by("-id")[0]
    expected_field_values = AppointmentAvailabilityReport.objects.filter(
        pk=report.pk
    ).values(*list(fixture["expected_fields"].keys()))[0]
    assert expected_field_values == fixture["expected_fields"]

    # Check the windows
    for window, expected_window in zip(
        report.windows.all(), fixture["expected_windows"]
    ):
        expected_field_values = AppointmentAvailabilityWindow.objects.filter(
            pk=window.pk
        ).values(*list(expected_window["expected_fields"].keys()))[0]
        assert expected_field_values == expected_window["expected_fields"]

        actual_tags = [tag.slug for tag in window.additional_restrictions.all()]
        assert actual_tags == expected_window["expected_additional_restrictions"]
