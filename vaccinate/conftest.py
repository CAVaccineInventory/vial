import datetime

import pytest

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


@pytest.fixture
def jwt_unauth_id_token(time_machine, mock_well_known_jwts, mock_auth0_userinfo):
    time_machine.move_to(datetime.datetime(2021, 3, 17, 10, 0, 0))
    # This token created for auth0 user swillison+auth0-test-user@gmail.com
    # by signing into https://help.calltheshots.us/call/ and sniffing
    # network traffic on 17th March 2021.  It has an empty "permissions" list,
    # and as such will fail auth:
    # {
    #     "https://help.vaccinateca.com/roles": [],
    #     "iss": "https://vaccinateca.us.auth0.com/",
    #     "sub": "auth0|6036cd942c0b2a007093cbf0",
    #     "aud": [
    #         "https://help.vaccinateca.com",
    #         "https://vaccinateca.us.auth0.com/userinfo"
    #     ],
    #     "iat": 1616018322,
    #     "exp": 1616104722,
    #     "azp": "ZnpcUDelsgbXXXMTayxzdPWTX8wikGi5",
    #     "scope": "openid profile email",
    #     "permissions": []
    # }
    return "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImZydGlQYXhnX2UyV29NMXhUb1IwRyJ9.eyJodHRwczovL2hlbHAudmFjY2luYXRlY2EuY29tL3JvbGVzIjpbXSwiaXNzIjoiaHR0cHM6Ly92YWNjaW5hdGVjYS51cy5hdXRoMC5jb20vIiwic3ViIjoiYXV0aDB8NjAzNmNkOTQyYzBiMmEwMDcwOTNjYmYwIiwiYXVkIjpbImh0dHBzOi8vaGVscC52YWNjaW5hdGVjYS5jb20iLCJodHRwczovL3ZhY2NpbmF0ZWNhLnVzLmF1dGgwLmNvbS91c2VyaW5mbyJdLCJpYXQiOjE2MTYwMTgzMjIsImV4cCI6MTYxNjEwNDcyMiwiYXpwIjoiWm5wY1VEZWxzZ2JYWFhNVGF5eHpkUFdUWDh3aWtHaTUiLCJzY29wZSI6Im9wZW5pZCBwcm9maWxlIGVtYWlsIiwicGVybWlzc2lvbnMiOltdfQ.JAcWaIjhKmVWaivlF3IIhm6S1_vQz3Imgod6zoahqS2v5wIhjSuFFB1GaKlOWNlOVvE7Q5oVSwLl3JeBxIQObKln5pWvN-O5dBKtfF8K71k6MUKj4IHFVfEWZMEn0EC6rnsCWwlzIIJSM1-VedawbStd8C07KPnBGlTaO6DdS40aaWD1rxu664dsF_bfeOMXlSH5ayqcVSt3HcaTDRr27_cOVCA06ovIKq8uerSj6NNhBOd2ui9v_G-8xvyHbNukCKV-s-Knwlm9-WQOLxXznMQR5PdAl0VprpaL886wY-F2Ewrw6BLId4hZNDC6DubSkYlwoodsEDuh5o5cDsv_Lw"


@pytest.fixture
def jwt_id_token(time_machine, mock_well_known_jwts, mock_auth0_userinfo):
    time_machine.move_to(datetime.datetime(2021, 5, 4, 8, 0, 0))
    # This token created for auth0 user alex+testuser@vaccinateca.com
    # by signing into https://help.calltheshots.us/call/ and sniffing
    # network traffic on 2021-05-04.
    #
    # This decodes to:
    # {
    #     "https://help.vaccinateca.com/roles": [
    #         "Volunteer Caller"
    #     ],
    #     "iss": "https://vaccinateca.us.auth0.com/",
    #     "sub": "auth0|604b00092f4fe10068f49191",
    #     "aud": [
    #         "https://help.vaccinateca.com",
    #         "https://vaccinateca.us.auth0.com/userinfo"
    #     ],
    #     "iat": 1620114112,
    #     "exp": 1620200512,
    #     "azp": "ZnpcUDelsgbXXXMTayxzdPWTX8wikGi5",
    #     "scope": "openid profile email",
    #     "permissions": [
    #         "caller"
    #     ]
    # }
    return "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImZydGlQYXhnX2UyV29NMXhUb1IwRyJ9.eyJodHRwczovL2hlbHAudmFjY2luYXRlY2EuY29tL3JvbGVzIjpbIlZvbHVudGVlciBDYWxsZXIiXSwiaXNzIjoiaHR0cHM6Ly92YWNjaW5hdGVjYS51cy5hdXRoMC5jb20vIiwic3ViIjoiYXV0aDB8NjA0YjAwMDkyZjRmZTEwMDY4ZjQ5MTkxIiwiYXVkIjpbImh0dHBzOi8vaGVscC52YWNjaW5hdGVjYS5jb20iLCJodHRwczovL3ZhY2NpbmF0ZWNhLnVzLmF1dGgwLmNvbS91c2VyaW5mbyJdLCJpYXQiOjE2MjAxMTQxMTIsImV4cCI6MTYyMDIwMDUxMiwiYXpwIjoiWm5wY1VEZWxzZ2JYWFhNVGF5eHpkUFdUWDh3aWtHaTUiLCJzY29wZSI6Im9wZW5pZCBwcm9maWxlIGVtYWlsIiwicGVybWlzc2lvbnMiOlsiY2FsbGVyIl19.gbsWLsMkLkjqh-boc9ChgeNs52eQSW_PSJ7AxorfIKqYQtmuY-u52dSl4bgz0qoQ883Bl3yfGMy1KwalA3FpbVB8efqkWsNCHfMk64W4DQ4BLpANpiqI4D0T8XYREWJ8PAJdrYEvFItjinyVupZ4SLPCpf9amgamJPWiej3CbuNqvKsMFpxSmR09N8QfVU5D1bv2Ca_NYZ-QdnTvFCuDU2jJAgUBmlpHQHqQ9MsZcWV-OfKZgozZMWYkK0ZEmINC7bmSUNK7Af64QCtdCjzSpKIUG-0QwX18maWumERrrnARuqBS4WeL0EaRsIpJdiaHtpbrY-ruZf6NFpOxR8OKhw"


@pytest.fixture
def jwt_id_token_write_locations(
    time_machine, mock_well_known_jwts, mock_auth0_userinfo
):
    time_machine.move_to(datetime.datetime(2021, 5, 11, 8, 0, 0))
    # This token created for auth0 user simonw+write-locations-test@vaccinateca.com
    # by signing into https://help.calltheshots.us/call/ and sniffing
    # network traffic on 2021-05-11.
    #
    # This decodes to:
    # {
    #     "https://help.vaccinateca.com/roles": [],
    #     "iss": "https://vaccinateca.us.auth0.com/",
    #     "sub": "auth0|609b197a8a85860069bd53dd",
    #     "aud": [
    #         "https://help.vaccinateca.com",
    #         "https://vaccinateca.us.auth0.com/userinfo"
    #     ],
    #     "iat": 1620777401,
    #     "exp": 1620863801,
    #     "azp": "ZnpcUDelsgbXXXMTayxzdPWTX8wikGi5",
    #     "scope": "openid profile email",
    #     "permissions": [
    #         "write:locations"
    #     ]
    # }
    return "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImZydGlQYXhnX2UyV29NMXhUb1IwRyJ9.eyJodHRwczovL2hlbHAudmFjY2luYXRlY2EuY29tL3JvbGVzIjpbXSwiaXNzIjoiaHR0cHM6Ly92YWNjaW5hdGVjYS51cy5hdXRoMC5jb20vIiwic3ViIjoiYXV0aDB8NjA5YjE5N2E4YTg1ODYwMDY5YmQ1M2RkIiwiYXVkIjpbImh0dHBzOi8vaGVscC52YWNjaW5hdGVjYS5jb20iLCJodHRwczovL3ZhY2NpbmF0ZWNhLnVzLmF1dGgwLmNvbS91c2VyaW5mbyJdLCJpYXQiOjE2MjA3Nzc0MDEsImV4cCI6MTYyMDg2MzgwMSwiYXpwIjoiWm5wY1VEZWxzZ2JYWFhNVGF5eHpkUFdUWDh3aWtHaTUiLCJzY29wZSI6Im9wZW5pZCBwcm9maWxlIGVtYWlsIiwicGVybWlzc2lvbnMiOlsid3JpdGU6bG9jYXRpb25zIl19.SKtWyyoNp9HkqAvxQjAdTuk1RD8GV04d7jp6Urqp7p2-JqTu-16GfVApYoZxlJq6Cp8yDi2_kGT96kfzoX2xzUwHpbdTy5HyXAzIcD22UHLWm0eH3B3aEq7y2FA3MrhbPxPWlKOuhJgpns_noDVjth3c0wytWeOYC6gWO1GOzW7NuvrtA2ENVcaBIPBts7gaIYkpkEauqZ6sUXIGMVrNSu_Cvi4WAhm50yhaOd9nLXI09lqvdCp8O9A6u0xcpEbooxP9yDL82auNEAYqYcIyTuDH51QfWc2csAa2ZAbvN_hx3CxqSr-dVZ2qHhWDUCH6W39VvSXfoUsUYmQw4s4-sQ"


@pytest.fixture
def mock_well_known_jwts(requests_mock):
    requests_mock.get(
        "https://vaccinateca.us.auth0.com/.well-known/jwks.json",
        json=MOCK_JWKS,
    )


@pytest.fixture
def mock_auth0_userinfo(requests_mock):
    requests_mock.get(
        "https://vaccinateca.us.auth0.com/userinfo",
        json={
            "sub": "auth0|604b00092f4fe10068f49191",
            "nickname": "test+1",
            "name": "Test User",
            "picture": "https://s.gravatar.com/avatar/029b23ca46bc262bef1b1fabafe07ca9?s=480&r=pg&d=https%3A%2F%2Fcdn.auth0.com%2Favatars%2Fte.png",
            "updated_at": "2021-05-04T07:44:07.316Z",
            "email": "alex+testuser@vaccinateca.com",
            "email_verified": True,
            "https://help.vaccinateca.com/roles": ["Volunteer Caller"],
        },
    )


def make_locations(n):
    from core.models import Location, State

    locations = []
    for i in range(1, n + 1):
        location = Location.objects.create(
            name="Location {}".format(i),
            phone_number="(555) 555-55{:02}".format(i),
            state_id=State.objects.get(abbreviation="OR").id,
            location_type_id=1,
            latitude=30,
            longitude=40,
        )
        location.refresh_from_db()
        locations.append(location)

    return locations


@pytest.fixture
def ten_locations(db):
    return make_locations(10)


@pytest.fixture
def two_hundred_locations(db):
    return make_locations(200)


@pytest.fixture
def api_key(db):
    from api.models import ApiKey
    from django.contrib.auth.models import User

    api_key = ApiKey.objects.create(
        id=1,
        key="1953b7a735274809f4ff230048b60a4a",
        description="Test",
        user=User.objects.create(username="user"),
    )
    return api_key.token
