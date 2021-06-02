import pytest
from core.models import Location, State


@pytest.mark.parametrize(
    "api_response,expected_county",
    (
        (
            [
                {
                    "state_fips": "06",
                    "state": "CA",
                    "county_fips": "06081",
                    "county_name": "San Mateo",
                    "COUNTYNS": "00277305",
                    "AFFGEOID": "0500000US06081",
                    "GEOID": "06081",
                    "LSAD": "06",
                    "ALAND": 1161960635,
                    "AWATER": 757110545,
                }
            ],
            "San Mateo",
        ),
        (
            [],
            None,
        ),
    ),
)
def test_resolve_missing_counties(
    client, db, httpx_mock, api_response, expected_county
):
    httpx_mock.add_response(json=api_response)
    location = Location.objects.create(
        name="Location mising county",
        phone_number="(555) 555-5512",
        state_id=State.objects.get(abbreviation="CA").id,
        location_type_id=1,
        latitude=37.5,
        longitude=-122.4,
    )
    assert location.county is None

    response = client.post(
        "/api/resolveMissingCounties",
        {},
        content_type="application/json",
    )
    assert response.status_code == 200
    if expected_county:
        expected_response = {"failed": [], "resolved": [location.public_id]}
    else:
        expected_response = {"failed": [location.public_id], "resolved": []}
    assert response.json() == expected_response
    location.refresh_from_db()
    if expected_county:
        assert location.county.name == expected_county
        assert location.tasks.count() == 0
    else:
        assert location.county is None
        assert location.tasks.count() == 1
        assert location.tasks.all()[0].task_type.name == "Resolve county"
