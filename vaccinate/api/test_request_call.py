import pytest
from core.models import (
    CallRequest,
    CallRequestReason,
    County,
    Location,
    LocationType,
    State,
)
from django.utils import timezone


@pytest.mark.django_db
def test_request_call(client, jwt_id_token):
    assert CallRequest.objects.count() == 0
    # First attempt should return 'no calls' error
    response1 = client.post(
        "/api/requestCall",
        {},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert response1.status_code == 400
    assert response1.json() == {"error": "Couldn't find somewhere to call"}
    # Queue up a request and try again
    county = County.objects.get(fips_code="06079")  # San Luis Obispo
    location = Location.objects.create(
        county=county,
        state=State.objects.get(abbreviation="OR"),
        name="SLO Pharmacy",
        phone_number="555 555-5555",
        full_address="5 5th Street",
        location_type=LocationType.objects.get(name="Pharmacy"),
        latitude=35.279,
        longitude=-120.664,
    )
    # Ensure location.public_id is correct:
    location.refresh_from_db()
    call_request = location.call_requests.create(
        call_request_reason=CallRequestReason.objects.get(short_reason="New location"),
        vesting_at=timezone.now(),
    )
    assert call_request.claimed_by is None
    assert call_request.claimed_until is None
    response2 = client.post(
        "/api/requestCall",
        {},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert response2.status_code == 200
    data = response2.json()
    # This should have claimed the report
    call_request.refresh_from_db()
    assert call_request.claimed_by is not None
    assert call_request.claimed_until is not None
    assert data == {
        "id": location.public_id,
        "Name": "SLO Pharmacy",
        "Phone number": "555 555-5555",
        "Address": "5 5th Street",
        "Internal notes": None,
        "Hours": None,
        "County": "San Luis Obispo",
        "Location Type": "Pharmacy",
        "Affiliation": None,
        "Latest report": None,
        "Latest report notes": [None],
        "County vaccine info URL": [None],
        "County Vaccine locations URL": [None],
        "Latest Internal Notes": [None],
        "Availability Info": [],
        "Number of Reports": 0,
        "county_record": {
            "id": county.airtable_id,
            "County": "San Luis Obispo",
            "Vaccine info URL": None,
            "Vaccine locations URL": None,
            "Notes": None,
        },
        "provider_record": {},
    }
