import pytest
from core.models import ConcordanceIdentifier, Task, TaskType
from django.contrib.auth.models import User


@pytest.mark.django_db
@pytest.mark.parametrize(
    "winner,loser,expected_error",
    (
        (
            "rec-one",
            "rec-one",
            {
                "loc": ["loser"],
                "msg": "Winner and loser should not be the same",
                "type": "value_error",
            },
        ),
        (
            "rec-one-soft-deleted",
            "rec-two",
            {
                "loc": ["winner"],
                "msg": "Location rec-one-soft-deleted is soft deleted",
                "type": "value_error",
            },
        ),
        (
            "rec-one",
            "rec-two-soft-deleted",
            {
                "loc": ["loser"],
                "msg": "Location rec-two-soft-deleted is soft deleted",
                "type": "value_error",
            },
        ),
    ),
)
def test_merge_locations_errors(
    client, jwt_id_token_write_locations, ten_locations, winner, loser, expected_error
):
    one, two, one_soft_deleted, two_soft_deleted = ten_locations[:4]
    one.public_id = "rec-one"
    one.save()
    two.public_id = "rec-two"
    two.save()
    one_soft_deleted.soft_deleted = True
    one_soft_deleted.public_id = "rec-one-soft-deleted"
    one_soft_deleted.save()
    two_soft_deleted.soft_deleted = True
    two_soft_deleted.public_id = "rec-two-soft-deleted"
    two_soft_deleted.save()
    response = client.post(
        "/api/mergeLocations",
        {"winner": winner, "loser": loser},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token_write_locations),
    )
    assert response.status_code == 400
    assert response.json() == {"error": [expected_error]}


def test_merge_locations(client, jwt_id_token_write_locations, ten_locations):
    winner, loser = ten_locations[:2]
    loser.concordances.add(ConcordanceIdentifier.for_idref("google_places:123"))
    assert winner.concordances.count() == 0
    response = client.post(
        "/api/mergeLocations",
        {"winner": winner.public_id, "loser": loser.public_id},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token_write_locations),
    )
    assert response.status_code == 200
    assert response.json() == {
        "winner": {
            "id": winner.public_id,
            "name": "Location 1",
            "vial_url": "http://testserver/admin/core/location/{}/change/".format(
                winner.pk
            ),
        },
        "loser": {
            "id": loser.public_id,
            "name": "Location 2",
            "vial_url": "http://testserver/admin/core/location/{}/change/".format(
                loser.pk
            ),
        },
    }
    assert winner.concordances.count() == 1
    loser.refresh_from_db()
    assert loser.soft_deleted
    assert loser.duplicate_of_id == winner.pk


def test_merge_locations_resolve_task(
    client, jwt_id_token_write_locations, ten_locations
):
    winner, loser = ten_locations[:2]
    user = User.objects.create(username="u")
    task = Task.objects.create(
        task_type=TaskType.objects.get(name="Potential duplicate"),
        location=winner,
        other_location=loser,
        created_by=user,
    )
    assert not task.resolved_by
    assert not task.resolved_at
    response = client.post(
        "/api/mergeLocations",
        {"winner": winner.public_id, "loser": loser.public_id, "task_id": task.pk},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token_write_locations),
    )
    assert response.status_code == 200
    task.refresh_from_db()
    assert task.resolved_by.username.startswith("r")
    assert task.resolved_at
    assert task.resolution == {
        "winner": winner.public_id,
        "loser": loser.public_id,
        "merged_locations": True,
    }
