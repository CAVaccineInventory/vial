from core.models import Report, Location
from api.models import ApiLog
import json
import pathlib
import pytest

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
def test_submit_report_api_invalid_json(client, jwt_id_token):
    response = client.post(
        "/api/submitReport",
        "This is bad JSON",
        content_type="text/plain",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert response.status_code == 400
    assert response.json()["error"] == "Expecting value: line 1 column 1 (char 0)"


@pytest.mark.django_db
@pytest.mark.parametrize("json_path", tests_dir.glob("*.json"))
def test_submit_report_api_example(client, json_path, jwt_id_token):
    fixture = json.load(json_path.open())
    assert Report.objects.count() == 0
    # Ensure location exists
    Location.objects.get_or_create(
        public_id=fixture["input"]["Location"],
        defaults={
            "latitude": 0,
            "longitude": 0,
            "location_type_id": 1,
            "state_id": 1,
            "county_id": 1,
        },
    )
    response = client.post(
        "/api/submitReport",
        fixture["input"],
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert response.status_code == fixture["expected_status"]
    # Load new report from DB and check it
    report = Report.objects.order_by("-id")[0]
    assert response.json()["created"] == [report.public_id]
    assert report.pid == response.json()["created"][0]
    expected_field_values = Report.objects.filter(pk=report.pk).values(
        *list(fixture["expected_fields"].keys())
    )[0]
    assert expected_field_values == fixture["expected_fields"]
    # And check the tags
    actual_tags = [tag.slug for tag in report.availability_tags.all()]
    assert actual_tags == fixture["expected_availability_tags"]
    # Should have been submitted by the JWT user
    assert report.reported_by.external_id == "auth0:auth0|6036cd942c0b2a007093cbf0"