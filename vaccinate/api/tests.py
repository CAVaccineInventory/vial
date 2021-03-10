import time

import pytest

from .models import ApiKey


@pytest.mark.django_db
@pytest.mark.parametrize(
    "token,expected_error,expected_body",
    (
        ("", "Bearer token must contain one ':'", None),
        ("1", "Bearer token must contain one ':'", None),
        ("2:123", "API key does not exist", None),
        ("1:123", "Invalid API key", None),
        ("1:1953b7a735274809f4ff230048b60a4a", None, {}),
    ),
)
def test_verify_token(client, token, expected_error, expected_body):
    api_key = ApiKey.objects.create(
        id=1, key="1953b7a735274809f4ff230048b60a4a", description="Test"
    )
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
    token = api_key.token()
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
