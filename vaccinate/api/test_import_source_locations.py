import json
import pathlib

import pytest
from core.models import ConcordanceIdentifier, ImportRun, SourceLocation

tests_dir = pathlib.Path(__file__).parent / "test-data" / "importSourceLocations"


@pytest.mark.django_db
@pytest.mark.parametrize("json_path", tests_dir.glob("*.json"))
def test_import_location(client, api_key, json_path):
    fixture = json.load(json_path.open())

    assert ImportRun.objects.count() == 0
    assert SourceLocation.objects.count() == 0
    assert ConcordanceIdentifier.objects.count() == 0

    # First, create one of the ConcordanceIdentifiers to test that logic
    ConcordanceIdentifier.objects.create(source="rite_aid", identifier="5751")

    # Initiate an import run
    start_response = client.post(
        "/api/startImportRun", HTTP_AUTHORIZATION="Bearer {}".format(api_key)
    )

    assert start_response.status_code == 200
    assert ImportRun.objects.count() == 1
    json_start_response = start_response.json()
    assert "import_run_id" in json_start_response
    assert json_start_response["import_run_id"] == ImportRun.objects.get().id

    # Make the API request
    response = client.post(
        "/api/importSourceLocations?import_run_id={}".format(
            json_start_response["import_run_id"]
        ),
        fixture,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )

    assert response.status_code == 200
    assert SourceLocation.objects.count() == 1
    assert ConcordanceIdentifier.objects.count() == 2
    json_response = response.json()
    assert "created" in json_response
    assert len(json_response["created"]) == 1
    source_location = SourceLocation.objects.get()
    assert source_location.id == json_response["created"][0]

    assert source_location.name == fixture["name"]
    # TODO add more assertions about fields later
