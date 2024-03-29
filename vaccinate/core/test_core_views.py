import pytest


@pytest.mark.django_db
def test_signed_out_homepage(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b'<a href="/login/auth0">Sign in</a>' in response.content
