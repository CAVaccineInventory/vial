import pytest
from core.models import Task, TaskType, User
from django.utils import timezone


@pytest.mark.django_db
def test_resolve_task_non_existent_task(client, jwt_id_token):
    response = client.post(
        "/api/resolveTask",
        {"task_id": 12313},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert response.status_code == 400
    assert response.json() == {
        "error": [
            {
                "loc": ["task_id"],
                "msg": "Task 12313 does not exist",
                "type": "value_error",
            }
        ]
    }


def test_resolve_task_already_resolved_task(client, jwt_id_token, ten_locations):
    user = User.objects.create(username="u")
    task = Task.objects.create(
        task_type=TaskType.objects.get(name="Confirm address"),
        location=ten_locations[0],
        created_by=user,
        resolved_by=user,
        resolved_at=timezone.now(),
    )
    response = client.post(
        "/api/resolveTask",
        {"task_id": task.pk},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert response.status_code == 400
    assert response.json() == {
        "error": [
            {
                "loc": ["task_id"],
                "msg": "Task {} is already resolved".format(task.pk),
                "type": "value_error",
            }
        ]
    }


@pytest.mark.parametrize("resolution", (None, {"foo": "bar"}))
def test_resolve_task(client, jwt_id_token, ten_locations, resolution):
    user = User.objects.create(username="u")
    task = Task.objects.create(
        task_type=TaskType.objects.get(name="Confirm address"),
        location=ten_locations[0],
        created_by=user,
    )
    assert not task.resolved_by
    assert not task.resolved_at
    input = {"task_id": task.pk}
    if resolution:
        input["resolution"] = resolution
    response = client.post(
        "/api/resolveTask",
        input,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert response.status_code == 200
    assert response.json() == {
        "task_id": task.pk,
        "resolution": resolution,
        "resolved": True,
    }
    task.refresh_from_db()
    assert task.resolved_by
    assert task.resolved_at
