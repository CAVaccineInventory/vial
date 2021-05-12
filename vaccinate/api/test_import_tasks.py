import pytest
from core.models import Task, TaskType


@pytest.mark.django_db
@pytest.mark.parametrize("use_list", (False, True))
def test_import_tasks(client, api_key, ten_locations, use_list):
    assert Task.objects.count() == 0
    TaskType.objects.get_or_create(name="Possible duplicate")
    input = {
        "task_type": "Possible duplicate",
        "location": ten_locations[0].public_id,
        "other_location": ten_locations[1].public_id,
    }
    if use_list:
        input = [input]
    response = client.post(
        "/api/importTasks",
        input,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    assert response.status_code == 200
    created = response.json()["created"]
    assert isinstance(created, list)
    assert len(created) == 1
    assert Task.objects.count() == 1
    task = Task.objects.first()
    assert task.task_type.name == "Possible duplicate"
    assert task.location.pk == ten_locations[0].pk
    assert task.other_location.pk == ten_locations[1].pk
    assert task.created_by


@pytest.mark.django_db
def test_task_types(client):
    response = client.get("/api/taskTypes")
    assert response.json() == {
        "task_types": list(TaskType.objects.values_list("name", flat=True))
    }
