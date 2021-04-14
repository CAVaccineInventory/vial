import json

import pytest


@pytest.mark.django_db
def test_healthcheck(client, monkeypatch):
    response = client.get("/healthcheck")
    data = json.loads(response.content)
    assert set(data.keys()) == {
        "deployed_sha",
        "postgresql_version",
        "python_version",
        "reversion_models",
        "package_versions",
    }
    assert data["postgresql_version"].startswith("PostgreSQL ")
    assert data["python_version"].startswith("3.")
    assert set(data["reversion_models"]) == {
        "core.County",
        "core.Location",
        "core.Provider",
    }
    # Monkey-patch in some environment variables
    monkeypatch.setenv("COMMIT_SHA", "COMMIT_SHA")
    assert (
        json.loads(client.get("/healthcheck").content)["deployed_sha"] == "COMMIT_SHA"
    )
