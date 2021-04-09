import datetime
import urllib

import pytest
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session


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


@pytest.mark.django_db
@pytest.mark.parametrize(
    # I generated these id_token values using the process described in this issue comment:
    # https://github.com/CAVaccineInventory/vial/issues/8#issuecomment-785429712
    "id_token,expected_email,should_be_staff",
    (
        (
            "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImZydGlQYXhnX2UyV29NMXhUb1IwRyJ9.eyJodHRwczovL2hlbHAudmFjY2luYXRlY2EuY29tL3JvbGVzIjpbXSwibmlja25hbWUiOiJzd2lsbGlzb24rYXV0aDAtdGVzdC11c2VyIiwibmFtZSI6InN3aWxsaXNvbithdXRoMC10ZXN0LXVzZXJAZ21haWwuY29tIiwicGljdHVyZSI6Imh0dHBzOi8vcy5ncmF2YXRhci5jb20vYXZhdGFyL2RiZTBkYmE5MzVjNzgxOWVmOTMyMTZhODc5ODhjZGY5P3M9NDgwJnI9cGcmZD1odHRwcyUzQSUyRiUyRmNkbi5hdXRoMC5jb20lMkZhdmF0YXJzJTJGc3cucG5nIiwidXBkYXRlZF9hdCI6IjIwMjEtMDItMjRUMjI6MDU6MDguODM4WiIsImVtYWlsIjoic3dpbGxpc29uK2F1dGgwLXRlc3QtdXNlckBnbWFpbC5jb20iLCJlbWFpbF92ZXJpZmllZCI6ZmFsc2UsImlzcyI6Imh0dHBzOi8vdmFjY2luYXRlY2EudXMuYXV0aDAuY29tLyIsInN1YiI6ImF1dGgwfDYwMzZjZDk0MmMwYjJhMDA3MDkzY2JmMCIsImF1ZCI6IjdKTU00YmIxZUM3dGFHTjFPbGFMQklYSk4xdzQydmFjIiwiaWF0IjoxNjE0MjA0MzA5LCJleHAiOjE2MTQyNDAzMDl9.d-KbGqjMRmMg8jjZsqBVQxmJ9X_yhNkSqgwE09y6dhwMzd4QJBlTqPE4tM22zddkyaxTFF50y_-kdNdEvRQppGeg1NLEz-UqzPSKuAiSB4m2l-OIK465lFBpzKbFL01lnPpm0xMypi27tSQEXQFaPRXzS3hbew9dmfmcrq29lQIoUTLwLWexlmkzJZSJOD3C2O3d9XwXcum5FtAv8OAMKYyis7gJQQnmYq0MYnHqCTTxppYK4UFJPlfFrWoNPc75FrKcjx2zDmux_Ln-EOm8RSSy-4Uul_bh3_zVcdzeT-D9nHaXkRcBHLAClN2HQhgxCGpU4zrEgjxb4KkTxm7dfw",
            "swillison+auth0-test-user@gmail.com",
            False,
        ),
        (
            "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImZydGlQYXhnX2UyV29NMXhUb1IwRyJ9.eyJodHRwczovL2hlbHAudmFjY2luYXRlY2EuY29tL3JvbGVzIjpbIlZhY2NpbmF0ZSBDQSBTdGFmZiJdLCJuaWNrbmFtZSI6InN3aWxsaXNvbithdXRoMC10ZXN0LXN0YWZmLXVzZXIiLCJuYW1lIjoic3dpbGxpc29uK2F1dGgwLXRlc3Qtc3RhZmYtdXNlckBnbWFpbC5jb20iLCJwaWN0dXJlIjoiaHR0cHM6Ly9zLmdyYXZhdGFyLmNvbS9hdmF0YXIvNmQ0YjgzYTUwYjBjODg3OWU0NWViNmUxZWE4Y2EwMWM_cz00ODAmcj1wZyZkPWh0dHBzJTNBJTJGJTJGY2RuLmF1dGgwLmNvbSUyRmF2YXRhcnMlMkZzdy5wbmciLCJ1cGRhdGVkX2F0IjoiMjAyMS0wMi0yNFQyMjoyOTo0OC4zMjdaIiwiZW1haWwiOiJzd2lsbGlzb24rYXV0aDAtdGVzdC1zdGFmZi11c2VyQGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjpmYWxzZSwiaXNzIjoiaHR0cHM6Ly92YWNjaW5hdGVjYS51cy5hdXRoMC5jb20vIiwic3ViIjoiYXV0aDB8NjAzNmQzMDc0Nzc5ODcwMDY5YmY3NzlkIiwiYXVkIjoiN0pNTTRiYjFlQzd0YUdOMU9sYUxCSVhKTjF3NDJ2YWMiLCJpYXQiOjE2MTQyMDU3ODgsImV4cCI6MTYxNDI0MTc4OH0.QFMZEvFoi1v0gfLXcVzmzTHzm4l-klVDtFFfV_UInf7TUn1tQ_zNkYhdSTCP73zjiXdurmvm4UjMtR9H4AqkFOR2ySRtG7W3H7YmI_k8LttT_4Va1TYl6DGwayu8ld4XQJnAiMWVDP8Kpo9Hy1STZihRikEVQ9_ziJRq4h5XikqyadH8SvmxemCp-u6xxLsk9dO-KgIzskLh2Od_XNASzRKh5fBphDbxgtyp4efhNPWq7UZMtHtC0CE7UH3q5UOB_lIqYO_GmvWSeSGtXAaXQJKg8W0Z9AHFGRGgFZZPifhWp8Z6zBz76MobZDbY6EC_eV0n0gqbMBH04avwcMxYeQ",
            "swillison+auth0-test-staff-user@gmail.com",
            True,
        ),
    ),
)
def test_login_with_auth0_complete(
    client,
    requests_mock,
    time_machine,
    id_token,
    expected_email,
    should_be_staff,
    mock_well_known_jwts,
):
    # The tokens I baked into the tests have an expiry date:
    time_machine.move_to(datetime.datetime(2021, 2, 24, 10, 0, 0))
    requests_mock.post(
        "https://vaccinateca.us.auth0.com/oauth/token",
        json={
            "access_token": "xOiL1rNfVMPdnJ8RF5qXu6zd4QVdSLw2",
            "id_token": id_token,
            "scope": "openid profile email",
            "expires_in": 86400,
            "token_type": "Bearer",
        },
    )
    state = _get_state(client)
    response = client.get("/complete/auth0?code=auth0code&state={}".format(state))
    sessionid = response.cookies["sessionid"]
    # Look up session in the database and load the user
    session = Session.objects.get(session_key=sessionid.value)
    decoded = session.get_decoded()
    assert decoded["auth0_state"] == state
    user_id = decoded["_auth_user_id"]
    user = User.objects.get(pk=user_id)
    assert user.email == expected_email
    assert user.is_staff == should_be_staff
    if should_be_staff:
        assert user.groups.filter(name="Vaccinate CA Staff").exists()
    else:
        assert not user.groups.filter(name="Vaccinate CA Staff").exists()
    # Should redirect to / - redirecting to /admin/ caused
    # a redirect loop for not-staff users
    assert response.url == "/"


def _get_state(client):
    response = client.get("/login/auth0")
    qs_bits = dict(urllib.parse.parse_qsl(response.url.split("?")[1]))
    return qs_bits["state"]
