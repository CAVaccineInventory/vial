import pathlib
import random
import time
from datetime import datetime

import orjson
import pytest
from api.models import ApiLog
from core.models import CallRequest, CallRequestReason, Location, Report, State
from dateutil import parser
from django.utils import timezone

tests_dir = pathlib.Path(__file__).parent / "test-data" / "submitReport"


@pytest.mark.django_db
def test_submit_report_api_bad_token(client):
    response = client.post("/api/submitReport")
    assert response.json() == {"error": "Authorization header must start with 'Bearer'"}
    assert response.status_code == 403
    last_log = ApiLog.objects.order_by("-id")[0]
    assert {
        "method": "POST",
        "path": "/api/submitReport",
        "query_string": "",
        "remote_ip": "127.0.0.1",
        "response_status": 403,
        "created_report_id": None,
    }.items() <= last_log.__dict__.items()


@pytest.mark.django_db
def test_submit_report_unauth_token(client, jwt_unauth_id_token):
    # A valid JWT, but with no permissions
    response = client.post(
        "/api/submitReport",
        {},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_unauth_id_token),
    )
    assert response.status_code == 403
    assert response.json() == {"error": "Missing permissions: caller"}


@pytest.mark.django_db
def test_submit_report_api_invalid_json(client, jwt_id_token):
    response = client.post(
        "/api/submitReport",
        "This is bad JSON",
        content_type="text/plain",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert response.status_code == 400
    assert (
        response.json()["error"]
        == "expected value at line 1 column 1: line 1 column 1 (char 0)"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("json_path", tests_dir.glob("*.json"))
def test_submit_report_api_example(
    client, json_path, jwt_id_token, monkeypatch, requests_mock
):
    monkeypatch.setenv("ZAPIER_REPORT_URL", "https://zapier.example.com/")
    mocked_zapier = requests_mock.post(
        "https://zapier.example.com/",
        json={
            "ok": True,
        },
    )
    with json_path.open() as fixture_file:
        fixture = orjson.loads(fixture_file.read())
    assert Report.objects.count() == 0
    assert CallRequest.objects.count() == 0
    # Ensure location exists
    location = Location.objects.get_or_create(
        public_id=fixture["input"]["Location"],
        defaults={
            "name": "A location",
            "latitude": 0,
            "longitude": 0,
            "location_type_id": 1,
            "phone_number": "(555) 555-5555",
            "state": State.objects.get(abbreviation="OR"),
            "county_id": 1,
        },
    )[0]
    # Check user stats before
    assert client.post(
        "/api/callerStats",
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    ).json() == {
        "total": 0,
        "today": 0,
    }
    # Create a call request for this location
    call_request = location.call_requests.create(
        call_request_reason=CallRequestReason.objects.get(short_reason="New location"),
        vesting_at=timezone.now(),
        priority_group=2,
    )
    assert not call_request.completed
    assert call_request.completed_at is None
    assert not call_request.claimed_by
    assert call_request.claimed_until is None
    assert CallRequest.available_requests().count() == 1

    # Claim that call request
    call_request_response = client.post(
        "/api/requestCall?state=all",
        {},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert call_request_response.status_code == 200
    claimed_location = call_request_response.json()
    assert claimed_location["id"] == location.public_id
    call_request.refresh_from_db()
    assert call_request.claimed_by
    assert call_request.claimed_until is not None

    # Submit the report; because we randomly sample 2% of all reports,
    # we explicitly seed so we can predict if this will be selected.
    random.seed(1)
    response = client.post(
        "/api/submitReport",
        fixture["input"],
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    random.seed(int(time.time()))
    assert response.status_code == fixture["expected_status"]

    # Call request should have been marked as complete
    call_request.refresh_from_db()
    assert call_request.completed
    assert call_request.completed_at is not None

    # Load new report from DB and check it
    report = Report.objects.order_by("-id")[0]
    assert response.json()["created"] == [report.public_id]
    assert report.pid == response.json()["created"][0]
    assert report.call_request == call_request
    expected_field_values = Report.objects.filter(pk=report.pk).values(
        *list(fixture["expected_fields"].keys())
    )[0]
    expected_fields = fixture["expected_fields"]
    # Special case for dates:
    for key, value in expected_fields.items():
        if key in ("planned_closure",):
            expected_fields[key] = parser.parse(value).date()
    assert expected_field_values == expected_fields
    # And check the tags
    actual_tags = [tag.slug for tag in report.availability_tags.all()]
    assert actual_tags == fixture["expected_availability_tags"]
    # Should have been submitted by the JWT user
    assert report.reported_by.external_id == "auth0:auth0|604b00092f4fe10068f49191"

    if "expected_call_request" in fixture:  # this was a skip request
        # need to manually parse out date for comparison
        fixture["expected_call_request"]["vesting_at"] = datetime.strptime(
            fixture["expected_call_request"]["vesting_at"], "%Y-%m-%dT%H:%M:%S.%f%z"
        )
        field_values = CallRequest.objects.order_by("-id").values(
            *list(fixture["expected_call_request"].keys())
        )[0]
        assert field_values == fixture["expected_call_request"]
    else:
        # There should be no available call requests
        assert CallRequest.available_requests().count() == 0

    # Check user stats after
    assert client.post(
        "/api/callerStats",
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    ).json() == {
        "total": 1,
        "today": 1,
    }

    # Should have posted to Zapier
    assert mocked_zapier.called_once
    assert orjson.loads(mocked_zapier.last_request.body) == {
        "report_url": "http://testserver/admin/core/report/{}/change/".format(
            report.pk
        ),
        "report_public_notes": report.public_notes,
        "report_internal_notes": report.internal_notes,
        "location_name": "A location",
        "location_full_address": None,
        "location_state": "OR",
        "reporter_name": "Test User",
        "reporter_id": "auth0:auth0|604b00092f4fe10068f49191",
        "reporter_role": "Volunteer Caller",
        "availability_tags": list(
            report.availability_tags.values_list("name", flat=True)
        ),
    }

    # Soft delete that report and check callerStats again
    report.soft_deleted = True
    report.save()
    assert client.post(
        "/api/callerStats",
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    ).json() == {
        "total": 0,
        "today": 0,
    }


def test_submit_report_updates_location_fields(location, client, jwt_id_token):
    assert location.vaccines_offered is None
    assert location.accepts_appointments is None
    assert location.accepts_walkins is None
    assert location.vaccines_offered_provenance_report is None
    assert location.appointments_walkins_provenance_report is None

    random.seed(1)
    response = client.post(
        "/api/submitReport",
        {
            "Location": location.public_id,
            "Availability": [
                "Yes: appointment required",
                "Vaccinating essential workers",
            ],
            "vaccines_offered": ["Moderna", "Johnson & Johnson", "Other"],
        },
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert response.status_code == 200
    random.seed(int(time.time()))

    location2 = Location.objects.get(pk=location.pk)
    report = location2.reports.all()[0]
    assert (
        report.availability() == "Appointment required, Vaccinating essential workers"
    )
    assert report.vaccines_offered == ["Moderna", "Johnson & Johnson", "Other"]
    assert not report.is_pending_review
    assert not report.soft_deleted
    # Should have updated fields on location:
    assert location2.vaccines_offered == ["Moderna", "Johnson & Johnson", "Other"]
    assert location2.accepts_appointments is True
    assert location2.accepts_walkins is False
    assert location2.vaccines_offered_provenance_report == report
    assert location2.appointments_walkins_provenance_report == report
