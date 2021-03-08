import json

import pytest


@pytest.mark.django_db
def test_healthcheck(client):
    response = client.get("/healthcheck")
    data = json.loads(response.content)
    assert set(data.keys()) == {"COMMIT_SHA", "postgresql_version", "python_version"}
    assert data["postgresql_version"].startswith("PostgreSQL ")
    assert data["python_version"].startswith("3.")
