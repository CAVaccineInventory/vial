import pytest
from core.models import Task, TaskType, User


@pytest.mark.django_db
def test_request_task_queue_empty(client, jwt_id_token):
    response = client.post(
        "/api/requestTask",
        {"task_type": "Potential duplicate"},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert response.status_code == 200
    assert response.json() == {
        "task": None,
        "task_type": "Potential duplicate",
        "warning": 'No unresolved tasks of type "Potential duplicate"',
    }


@pytest.mark.django_db
def test_request_task(client, jwt_id_token, ten_locations):
    creator = User.objects.create(username="creator")
    for i in range(10):
        Task.objects.create(
            created_by=creator,
            task_type=TaskType.objects.get(name="Potential duplicate"),
            location=ten_locations[0],
            other_location=ten_locations[1],
            details={"i": i},
        )
    response = client.post(
        "/api/requestTask",
        {"task_type": "Potential duplicate"},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(jwt_id_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"task_type", "task", "unresolved_of_this_type"}
    assert data["task_type"] == "Potential duplicate"
    assert data["unresolved_of_this_type"] == 10
    task = data["task"]
    assert set(task.keys()) == {
        "id",
        "task_type",
        "location",
        "other_location",
        "details",
    }
    assert set(task["details"].keys()) == {"i"}
    # location and source_location should both be locations, with soft_deleted key
    for key in ("location", "other_location"):
        assert {"id", "name", "state", "soft_deleted"}.issubset(task[key].keys())
