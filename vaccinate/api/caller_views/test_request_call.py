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
def test_unauth_request_call(client, jwt_unauth_id_token):
    # No auth header fails
    response = client.post(
        "/api/requestCall",
        {},
        content_type="application/json",
    )
    assert response.status_code == 403
    assert response.json() == {"error": "Authorization header must start with 'Bearer'"}

    # A valid JWT, but with no permissions
    response = client.post(
        "/api/requestCall",
        {},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_unauth_id_token),
    )
    assert response.status_code == 403
    assert response.json() == {"error": "Missing permissions: caller"}


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
    county = County.objects.create(
        name="Multnomah",
        fips_code="41051",
        state=State.objects.get(abbreviation="OR"),
    )
    county.age_floor_without_restrictions = 50
    county.save()
    locations = []
    for i in range(3):
        location = Location.objects.create(
            county=county,
            state=State.objects.get(abbreviation="OR"),
            name="Multnomah Pharmacy {}".format(i),
            phone_number="555 555-5555" if i > 1 else None,
            full_address="5 5th Street",
            location_type=LocationType.objects.get(name="Pharmacy"),
            latitude=45.5760998,
            longitude=-122.5134775,
        )
        # Ensure location.public_id is correct:
        location.refresh_from_db()
        locations.append(location)
    # Add several call requests so we can test we get the highest priority
    reason = CallRequestReason.objects.get(short_reason="New location")
    for location in locations:
        call_request = location.call_requests.create(
            call_request_reason=reason, vesting_at=timezone.now(), priority=i
        )
        assert call_request.claimed_by is None
        assert call_request.claimed_until is None
    response2 = client.post(
        "/api/requestCall?state=OR",
        {},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert response2.status_code == 200
    data = response2.json()
    # This should have claimed the report with the highest priority
    # where the location has a phone number
    call_request = CallRequest.objects.exclude(location__phone_number=None).order_by(
        "-priority"
    )[0]
    assert call_request.claimed_by is not None
    assert call_request.claimed_until is not None
    assert data == {
        "id": call_request.location.public_id,
        "Name": "Multnomah Pharmacy 2",
        "Phone number": "555 555-5555",
        "Address": "5 5th Street",
        "Internal notes": None,
        "Hours": None,
        "State": "OR",
        "County": "Multnomah",
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
            "id": county.id,
            "County": "Multnomah",
            "Vaccine info URL": None,
            "Vaccine locations URL": None,
            "Notes": None,
        },
        "county_age_floor_without_restrictions": [50],
        "provider_record": {},
        "confirm_address": False,
        "confirm_hours": False,
        "confirm_website": False,
        "timezone": "America/Los_Angeles",
    }
