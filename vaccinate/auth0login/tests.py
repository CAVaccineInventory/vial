from django.contrib.sessions.models import Session
from django.contrib.auth.models import User
import pytest
import urllib


# Copied from https://vaccinateca.us.auth0.com/.well-known/jwks.json on 24th Feb 2021:
MOCK_JWKS = {
    "keys": [
        {
            "alg": "RS256",
            "kty": "RSA",
            "use": "sig",
            "n": "rahm2egU3O9X4fevh2YFm8aJPhA5TPGuWZPQldVCSrRs7G1bv7D4Hpkal8SuGjkFilK5r6r8-LoRlgvFgPXMYhmZ6C2iVX6diqd2hlayC6nmJmj9wIJ8uwFoC6piaEZD2SOki4bK1c_1yUICF3b_tcFsCS3g7mBihEF31_ohAoleRnGMqLZPkpY1tK52iuw4rQaTO9SAh4wPExLpjPyVKzE8DuVHQY9dJc8XtzY0_niwcqkAS4rPhBeiWUq04blf2KM_ypGmh4HovEMZIqClKkb6OraAqxEwjsRmxSXjI9CKjnQ6q8dF04mUN1OuZKYEjxumT2BhU0UloserH87n0Q",
            "e": "AQAB",
            "kid": "frtiPaxg_e2WoM1xToR0G",
            "x5t": "hPIXTWMzKF6ixWVcJfMyNYVJfEk",
            "x5c": [
                "MIIDCzCCAfOgAwIBAgIJPLztFasLKg/YMA0GCSqGSIb3DQEBCwUAMCMxITAfBgNVBAMTGHZhY2NpbmF0ZWNhLnVzLmF1dGgwLmNvbTAeFw0yMTAyMDQwMjE0MDFaFw0zNDEwMTQwMjE0MDFaMCMxITAfBgNVBAMTGHZhY2NpbmF0ZWNhLnVzLmF1dGgwLmNvbTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAK2oZtnoFNzvV+H3r4dmBZvGiT4QOUzxrlmT0JXVQkq0bOxtW7+w+B6ZGpfErho5BYpSua+q/Pi6EZYLxYD1zGIZmegtolV+nYqndoZWsgup5iZo/cCCfLsBaAuqYmhGQ9kjpIuGytXP9clCAhd2/7XBbAkt4O5gYoRBd9f6IQKJXkZxjKi2T5KWNbSudorsOK0GkzvUgIeMDxMS6Yz8lSsxPA7lR0GPXSXPF7c2NP54sHKpAEuKz4QXollKtOG5X9ijP8qRpoeB6LxDGSKgpSpG+jq2gKsRMI7EZsUl4yPQio50OqvHRdOJlDdTrmSmBI8bpk9gYVNFJaLHqx/O59ECAwEAAaNCMEAwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQUBw5XPQZ3owZj1knalUBOLA0PEPAwDgYDVR0PAQH/BAQDAgKEMA0GCSqGSIb3DQEBCwUAA4IBAQBsAQ0uFOmLK3DaJt2CtKQpdvoIj00/oWS9B6ZANZzfwZ/CDPqpvjGDwnK2ImDArKqsfLf1vQUVIm9miASIWWjLCruxk4AFZeeNGYnBIvdv2+zMk7C0VDsFbUoAWHAfSUn2iCnSG57N6A1bNf/nZTHHfiR/O1zRFmQ1wQHbhjYHcidxTeQaSEJI+2A4SKCMm0nMrICc6jUXIet8KrSiizJonDSqXd8X9JQ+Y4aHK4ob2DFUCxkAUdX+BS18P7/oMibWxwG0wLbpSbSLqmESfOsin/HrTGdv89bjmuQJTzVNnuZsJl43zVwpiwWMJZMpQW2SjNI+wTwiMAyLxAnPQVGS"
            ],
        },
        {
            "alg": "RS256",
            "kty": "RSA",
            "use": "sig",
            "n": "0bgROqkt_6dGvytITrOTiCsirpr45osjigg2tQ1YkXS_H6out_QegcIxr_qe01JompD5mOIpCGZSsCAavM9FHhf7tTp21fJr7N_fSKndl6d5QCwhRjjA-3DAAJzt42UMg6YSATi0BLM60ap1SA9O6GPYrfL3IevCWqEcHuQjfiSdGTStoUkI6YO_4cTyuILvjY58369HMYjYA5303hQND9ckR8_z8oalmh9OEmBdHpilg0ZnhITiTT-sFr3RafKGGaxCUXjLbeR7NaaRIQ_LUoDvHLyVh40XoEeSOyIj7n3a18WE4qhCmrc539nb3d9jY3b4xiD6kcHxYOfzf_vBIw",
            "e": "AQAB",
            "kid": "xU8DLqrQ61ymbiAPwrhlz",
            "x5t": "OMRUjd9Xz-7VjO73LHOw0uq2HZQ",
            "x5c": [
                "MIIDCzCCAfOgAwIBAgIJdr+IWJ/wZxkWMA0GCSqGSIb3DQEBCwUAMCMxITAfBgNVBAMTGHZhY2NpbmF0ZWNhLnVzLmF1dGgwLmNvbTAeFw0yMTAyMDQwMjE0MDJaFw0zNDEwMTQwMjE0MDJaMCMxITAfBgNVBAMTGHZhY2NpbmF0ZWNhLnVzLmF1dGgwLmNvbTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBANG4ETqpLf+nRr8rSE6zk4grIq6a+OaLI4oINrUNWJF0vx+qLrf0HoHCMa/6ntNSaJqQ+ZjiKQhmUrAgGrzPRR4X+7U6dtXya+zf30ip3ZeneUAsIUY4wPtwwACc7eNlDIOmEgE4tASzOtGqdUgPTuhj2K3y9yHrwlqhHB7kI34knRk0raFJCOmDv+HE8riC742OfN+vRzGI2AOd9N4UDQ/XJEfP8/KGpZofThJgXR6YpYNGZ4SE4k0/rBa90WnyhhmsQlF4y23kezWmkSEPy1KA7xy8lYeNF6BHkjsiI+592tfFhOKoQpq3Od/Z293fY2N2+MYg+pHB8WDn83/7wSMCAwEAAaNCMEAwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQUcZKBYTZsFJVhcGqKx6Px3oRmXsAwDgYDVR0PAQH/BAQDAgKEMA0GCSqGSIb3DQEBCwUAA4IBAQC8HtDPG3FDzoz2yU38xWpx58VP8Q6FERWsjhJ20Yc1xTYmrNel37Y7zA/MkcHOc+tZI4W2GpdiFtYQmsrZ2176gSCnHaWt8uc/u5PTVeXMYgVGeBWby76fc0Ci9UP0++xcCqK3CNyOP+aTh1lGYdinT/s1P91IiK0fMTjnD1z/E4jEUkYi7zg81XooP+Bvbq8DdJwl0ZfaQk1cpE983iybgRSof0X54QJsNwSOFMfKZoXZSozHDyAwZ0UbKdazwCwMytJu5lp87QMmCgF17pV21op+++BhD2VYbYRGsZqRalbNJB1cUCxkkVUIAPqDSNrgUat1eblkvMdzRokgbENA"
            ],
        },
    ]
}


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
    # https://github.com/CAVaccineInventory/django.vaccinate/issues/8#issuecomment-785429712
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
    client, requests_mock, id_token, expected_email, should_be_staff
):
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
    requests_mock.get(
        "https://vaccinateca.us.auth0.com/.well-known/jwks.json",
        json=MOCK_JWKS,
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
        assert user.groups.filter(name='default-view-core').exists()
    else:
        assert not user.groups.filter(name='default-view-core').exists()

def _get_state(client):
    response = client.get("/login/auth0")
    qs_bits = dict(urllib.parse.parse_qsl(response.url.split("?")[1]))
    return qs_bits["state"]
