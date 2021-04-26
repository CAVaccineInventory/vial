import pytest
from core.models import (
    AppointmentTag,
    CallRequest,
    CallRequestReason,
    County,
    Location,
    LocationType,
    Reporter,
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
    }


@pytest.mark.django_db()
@pytest.mark.django_db()
def test_backfill_queue(client, jwt_id_token, settings, ten_locations):
    settings.MIN_CALL_REQUEST_QUEUE_ITEMS = 3
    assert CallRequest.available_requests().count() == 0
    response = client.post(
        "/api/requestCall?state=OR",
        {},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert response.status_code == 200
    assert CallRequest.available_requests().count() == 2
    # Try again but mark some of the locations as 'called'
    CallRequest.objects.all().delete()
    reporter = Reporter.objects.get_or_create(external_id="test:1")[0]
    web = AppointmentTag.objects.get(slug="web")
    for location in ten_locations[:8]:
        location.reports.create(
            reported_by=reporter,
            report_source="ca",
            appointment_tag=web,
        )
    response = client.post(
        "/api/requestCall?state=OR",
        {},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert response.status_code == 200
    assert CallRequest.available_requests().count() == 2
    call_requests = CallRequest.available_requests()
    # These should be to the locations with no reports
    for call_request in call_requests:
        assert call_request.location.reports.count() == 0


def test_backfill_queue_does_not_duplicate_locations(
    client, jwt_id_token, settings, ten_locations
):
    settings.MIN_CALL_REQUEST_QUEUE_ITEMS = 20
    assert CallRequest.available_requests().count() == 0
    response = client.post(
        "/api/requestCall?state=OR",
        {},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert response.status_code == 200
    assert CallRequest.available_requests().count() == 9
    assert CallRequest.objects.count() == 10
