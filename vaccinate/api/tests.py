import random
import time

import pytest
from core.models import AvailabilityTag, Reporter

from .models import ApiKey, Switch
from .views import user_should_have_reports_reviewed

GOODTOKEN = "1953b7a735274809f4ff230048b60a4a"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "token,expected_error,expected_body",
    (
        ("", "Bearer token must contain one ':'", None),
        ("1", "Bearer token must contain one ':'", None),
        ("2:123", "API key does not exist", None),
        ("1:123", "Invalid API key", None),
        (f"1:{GOODTOKEN}", None, {}),
    ),
)
def test_verify_token(client, token, expected_error, expected_body):
    ApiKey.objects.create(id=1, key=GOODTOKEN, description="Test")
    response = client.get(
        "/api/verifyToken", HTTP_AUTHORIZATION="Bearer {}".format(token)
    )
    if expected_error:
        assert response.status_code == 403
        assert response.json()["error"] == expected_error
    else:
        assert response.status_code == 200
        data = response.json()
        assert data["key_id"] == 1
        assert data["description"] == "Test"
        assert data["last_seen_at"]


@pytest.mark.django_db
def test_verify_token_last_seen_at(client):
    api_key = ApiKey.objects.create(
        id=2, key="8a2e60eb55011904fa495a27cd9c6393", description="Test"
    )
    token = api_key.token
    # Making two requests should not update last_seen_at
    response = client.get(
        "/api/verifyToken", HTTP_AUTHORIZATION="Bearer {}".format(token)
    )
    last_seen_at = response.json()["last_seen_at"]
    time.sleep(0.3)
    response2 = client.get(
        "/api/verifyToken", HTTP_AUTHORIZATION="Bearer {}".format(token)
    )
    last_seen_at2 = response2.json()["last_seen_at"]
    assert last_seen_at == last_seen_at2


@pytest.mark.django_db
def test_availability_tags(client):
    response = client.get("/api/availabilityTags")
    availability_tags = response.json()["availability_tags"]
    assert availability_tags == list(
        AvailabilityTag.objects.filter(disabled=False).values(
            "slug", "name", "group", "notes", "previous_names"
        )
    )


@pytest.mark.django_db
def test_user_should_have_reports_reviewed():
    user = Reporter.objects.get_or_create(external_id="test:1")[0]
    user.auth0_role_names = ""
    assert not user_should_have_reports_reviewed(user)
    # If user is Trainee, then yes
    user.auth0_role_names = "Blah, Trainee"
    assert user_should_have_reports_reviewed(user)
    # If user is Journeyman, then 15% of the time
    random.seed(1)
    user.auth0_role_names = "Journeyman"
    passes = 0
    for i in range(100):
        if user_should_have_reports_reviewed(user):
            passes += 1
    assert passes == 13
    random.seed(int(time.time()))


@pytest.mark.django_db
def test_switch_api_disabled(client, jwt_id_token):
    Switch.objects.filter(name="disable_api").update(on=True)
    response = client.post(
        "/api/requestCall",
        {},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert response.status_code == 400
    assert (
        response.content
        == b'{"error": "This application is currently disabled - please try again later"}'
    )
