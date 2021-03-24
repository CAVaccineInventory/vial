import datetime
import re

import pytest
from django.contrib.messages import get_messages
from django.utils import timezone

from .models import CallRequest, Location, Reporter, State


@pytest.fixture
def ten_locations(db):
    locations = []
    for i in range(1, 11):
        locations.append(
            Location.objects.create(
                name="Location {}".format(i),
                state_id=State.objects.get(abbreviation="OR").id,
                location_type_id=1,
                latitude=30,
                longitude=40,
            )
        )
    return locations


def test_admin_create_location_sets_public_id(admin_client):
    assert Location.objects.count() == 0
    response = admin_client.post(
        "/admin/core/location/add/",
        {
            "name": "hello",
            "state": State.objects.get(abbreviation="OR").id,
            "location_type": "1",
            "latitude": "0",
            "longitude": "0",
            "_save": "Save",
        },
    )
    # 200 means the form is being re-displayed with errors
    assert response.status_code == 302
    location = Location.objects.order_by("-id")[0]
    assert location.name == "hello"
    assert location.state.id == State.objects.get(abbreviation="OR").pk
    assert location.location_type.id == 1
    assert location.pid.startswith("l")
    assert location.public_id == location.pid


def test_admin_location_actions_for_queue(admin_client, ten_locations):
    assert CallRequest.objects.count() == 0
    assert Location.objects.count() == 10
    locations_to_queue = ten_locations[:3]
    # /admin/core/location/ should have 10 locations + actions menu
    response = admin_client.get("/admin/core/location/")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    for fragment in (
        '<option value="add_to_call_request_queue_stale_report">Add to queue: Stale report</option>',
        '<option value="add_to_call_request_queue_new_location">Add to queue: New location</option>',
        '<option value="add_to_call_request_queue_eva_tip">Add to queue: Eva tip</option>',
        '<option value="add_to_call_request_queue_data_corrections_tip">Add to queue: Data corrections tip</option>',
    ):
        assert fragment in html
    # Now try submitting the form, with three items selected
    response2 = admin_client.post(
        "/admin/core/location/",
        {
            "action": "add_to_call_request_queue_data_corrections_tip",
            "_selected_action": [l.id for l in locations_to_queue],
        },
    )
    assert response2.status_code == 302
    assert response2.url == "/admin/core/location/"
    messages = list(get_messages(response2.wsgi_request))
    assert len(messages) == 1
    assert (
        messages[0].message
        == "Added 3 location to queue with reason: Data corrections tip"
    )
    # Call requests should have been created
    assert CallRequest.objects.count() == 3
    assert set(CallRequest.objects.values_list("location_id", flat=True)) == set(
        location.id for location in locations_to_queue
    )
    # If we filter locations by "?currently_queued=yes" we should see them
    response3 = admin_client.get("/admin/core/location/?currently_queued=yes")
    assert response3.status_code == 200
    listed_locations = set(
        re.compile(r">(Location \d+)<").findall(response3.content.decode("utf-8"))
    )
    assert listed_locations == {"Location 3", "Location 2", "Location 1"}


def test_clear_claims_action(admin_client):
    locations = []
    for i in range(1, 4):
        locations.append(
            Location.objects.create(
                name="Location {}".format(i),
                state_id=State.objects.get(abbreviation="OR").id,
                location_type_id=1,
                latitude=30,
                longitude=40,
            )
        )
    assert CallRequest.objects.count() == 0
    # Add them to the call queue
    admin_client.post(
        "/admin/core/location/",
        {
            "action": "add_to_call_request_queue_data_corrections_tip",
            "_selected_action": [l.id for l in locations],
        },
    )
    assert CallRequest.objects.count() == 3
    assert CallRequest.available_requests().count() == 3
    # Claim all three
    reporter = Reporter.objects.get_or_create(external_id="auth0:claimer")[0]
    CallRequest.objects.all().update(
        claimed_by=reporter,
        claimed_until=timezone.now() + datetime.timedelta(minutes=10),
    )
    assert CallRequest.available_requests().count() == 0
    # Now clear two of them
    response = admin_client.post(
        "/admin/core/callrequest/",
        {
            "action": "clear_claims",
            "_selected_action": [cr.id for cr in CallRequest.objects.all()[:2]],
        },
    )
    messages = list(get_messages(response.wsgi_request))
    assert len(messages) == 2
    assert messages[1].message == "Cleared claims for 2 call requests"
    assert CallRequest.available_requests().count() == 2


# Using reset_sequences for predictable IDs in CSV output
@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_admin_export_csv(admin_client, django_assert_num_queries, ten_locations):
    # Add those locations to the call queue
    admin_client.post(
        "/admin/core/location/",
        {
            "action": "add_to_call_request_queue_data_corrections_tip",
            "_selected_action": [l.id for l in ten_locations],
        },
    )
    # Ensure they have predictable vesting_at values
    CallRequest.objects.all().update(vesting_at="2021-03-24 15:11:23")
    with django_assert_num_queries(9) as captured:
        response = admin_client.post(
            "/admin/core/callrequest/",
            {
                "action": "export_as_csv",
                "_selected_action": [cr.id for cr in CallRequest.objects.all()],
            },
        )
        csv_bytes = b"".join(chunk for chunk in response.streaming_content)
        csv_string = csv_bytes.decode("utf-8")
        assert csv_string == (
            "id,location_id,location,vesting_at,claimed_by_id,claimed_by,claimed_until,call_request_reason_id,call_request_reason,tip_type,tip_report_id,tip_report\r\n"
            "1,10,Location 10,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,,,\r\n"
            "2,9,Location 9,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,,,\r\n"
            "3,8,Location 8,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,,,\r\n"
            "4,7,Location 7,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,,,\r\n"
            "5,6,Location 6,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,,,\r\n"
            "6,5,Location 5,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,,,\r\n"
            "7,4,Location 4,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,,,\r\n"
            "8,3,Location 3,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,,,\r\n"
            "9,2,Location 2,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,,,\r\n"
            "10,1,Location 1,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,,,\r\n"
        )
