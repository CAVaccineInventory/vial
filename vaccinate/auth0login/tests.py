import pytest
import urllib


@pytest.mark.django_db
def test_login_with_auth0_start(client):
    response = client.get("/login/auth0")
    assert 302 == response.status_code
    assert response.url.startswith("https://vaccinateca.us.auth0.com/authorize?")
    qs_bits = dict(urllib.parse.parse_qsl(response.url.split("?")[1]))
    assert "state" in qs_bits
    assert (
        qs_bits.items()
        >= {
            "redirect_uri": "http://testserver/complete/auth0",
            "response_type": "code",
            "scope": "openid profile email",
        }.items()
    )
