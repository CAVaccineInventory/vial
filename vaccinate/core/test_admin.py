import datetime
import re

import pytest
from django.contrib.messages import get_messages
from django.utils import timezone

from .models import CallRequest, County, Location, Reporter, State


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


def test_admin_location_actions_for_queue(admin_client):
    assert CallRequest.objects.count() == 0
    assert Location.objects.count() == 0
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


def test_admin_commands_superuser_only(client, django_user_model):
    # No logged out users
    assert client.get("/admin/commands/").status_code == 302
    # No non-staff users
    user = django_user_model.objects.create_user(username="not-staff")
    client.force_login(user)
    assert client.get("/admin/commands/").status_code == 302
    # No staff users who are not super-users
    staff_user = django_user_model.objects.create_user(username="staff", is_staff=True)
    client.force_login(staff_user)
    assert client.get("/admin/commands/").status_code == 302
    # Super-users are allowed
    super_user = django_user_model.objects.create_user(
        username="super", is_staff=True, is_superuser=True
    )
    client.force_login(super_user)
    assert client.get("/admin/commands/").status_code == 200


def test_admin_commands_import_counties(admin_client, requests_mock):
    requests_mock.get(
        "https://us-counties.datasette.io/counties/county_fips.csv?_stream=on&_size=max",
        text=(
            "state,state_fips,county_fips,county_name\n"
            "AK,02,02013,Aleutians East\n"
            "AK,02,02016,Aleutians West"
        ),
    )
    assert County.objects.filter(state__abbreviation="AK").count() == 0
    admin_client.post("/admin/commands/", {"command": "import_counties"})
    assert County.objects.filter(state__abbreviation="AK").count() == 2
