from .models import Location
import pytest


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
