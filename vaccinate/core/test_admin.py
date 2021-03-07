import re

import pytest
from django.contrib.messages import get_messages

from .models import CallRequest, Location


@pytest.fixture()
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


def test_admin_create_location_sets_public_id(admin_client):
    assert Location.objects.count() == 0
    response = admin_client.post(
        "/admin/core/location/add/",
        {
            "name": "hello",
            "state": "13",
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
    assert location.state.id == 13
    assert location.location_type.id == 1
    assert location.pid.startswith("l")
    assert location.public_id == location.pid


def test_admin_location_actions_for_queue(admin_client):
    assert CallRequest.objects.count() == 0
    assert Location.objects.count() == 0
    locations = []
    for i in range(1, 11):
        locations.append(
            Location.objects.create(
                name="Location {}".format(i),
                state_id=13,
                location_type_id=1,
                latitude=30,
                longitude=40,
            )
        )
    locations_to_queue = locations[:3]
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
        re.compile(">(Location \d+)<").findall(response3.content.decode("utf-8"))
    )
    assert listed_locations == {"Location 3", "Location 2", "Location 1"}
