import pytest
from core.models import SourceLocation


@pytest.mark.parametrize("use_location_pk", (True, False))
@pytest.mark.parametrize("use_source_location_pk", (True, False))
def test_update_source_location_match_by_api_key(
    client, api_key, ten_locations, use_location_pk, use_source_location_pk
):
    location = ten_locations[0]
    source_location = SourceLocation.objects.create(
        source_name="test",
        source_uid="test:1",
    )
    assert source_location.matched_location is None

    post_data = {}
    if use_location_pk:
        post_data["location"] = location.pk
    else:
        post_data["location"] = location.public_id
    if use_source_location_pk:
        post_data["source_location"] = source_location.pk
    else:
        post_data["source_location"] = source_location.source_uid

    response = client.post(
        "/api/updateSourceLocationMatch",
        post_data,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    assert response.status_code == 200
    assert response.json() == {
        "matched": {
            "location": {"id": location.public_id, "name": "Location 1"},
            "source_location": {"source_uid": "test:1", "name": None},
        }
    }

    source_location.refresh_from_db()
    assert source_location.matched_location.public_id == location.public_id

    # History record should have been created
    history = source_location.source_location_match_history.first()
    assert history.old_match_location is None
    assert history.new_match_location == location
    assert history.api_key.token == api_key

    # Do an update and check the history afterwards
    second_location = ten_locations[1]
    post_data["location"] = second_location.public_id

    response2 = client.post(
        "/api/updateSourceLocationMatch",
        post_data,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    assert response2.status_code == 200

    assert source_location.source_location_match_history.count() == 2
    history2 = source_location.source_location_match_history.order_by("-pk")[0]
    assert history2.old_match_location == location
    assert history2.new_match_location == second_location
