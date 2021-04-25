import json
import pathlib

import pytest
from core.models import (
    ConcordanceIdentifier,
    ImportRun,
    Location,
    LocationType,
    SourceLocation,
    State,
)

tests_dir = pathlib.Path(__file__).parent / "test-data" / "importSourceLocations"


@pytest.mark.django_db
@pytest.mark.parametrize("json_path", tests_dir.glob("*.json"))
def test_import_location(client, api_key, json_path):
    fixture = json.load(json_path.open())

    assert Location.objects.count() == 0
    assert ImportRun.objects.count() == 0
    assert SourceLocation.objects.count() == 0
    assert ConcordanceIdentifier.objects.count() == 0

    # First, create one of the ConcordanceIdentifiers to test that logic
    ConcordanceIdentifier.objects.create(authority="rite_aid", identifier="5751")

    original_location = None
    if "match" in fixture and "id" in fixture["match"]:
        # Create a location to match against first
        original_location = Location.objects.create(
            public_id=fixture["match"]["id"],
            name=fixture["name"],
            latitude=fixture["latitude"],
            longitude=fixture["longitude"],
            location_type=LocationType.objects.filter(name="Pharmacy").get(),
            state=State.objects.filter(abbreviation="CA").get(),
        )
        assert original_location.public_id is not None

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
    if (
        "links" in fixture["import_json"]
        and fixture["import_json"]["links"] is not None
    ):
        # Add one for the source concordance
        assert ConcordanceIdentifier.objects.count() == 1 + len(
            fixture["import_json"]["links"]
        )
    json_response = response.json()
    assert "created" in json_response
    assert len(json_response["created"]) == 1
    source_location = SourceLocation.objects.get()
    assert source_location.id == json_response["created"][0]

    assert source_location.name == fixture["name"]
    assert source_location.latitude == fixture["import_json"]["location"]["latitude"]
    assert source_location.longitude == fixture["import_json"]["location"]["longitude"]
    assert source_location.import_json == fixture["import_json"]
    # TODO add more assertions about fields later

    # Source concordance must be associated with concordances
    source_concordance = ConcordanceIdentifier.objects.get(
        authority=fixture["source_name"], identifier=fixture["source_uid"]
    )
    assert source_concordance in source_location.concordances.all()

    if (
        "match" in fixture
        and "action" in fixture["match"]
        and fixture["match"]["action"] == "new"
    ):
        assert Location.objects.count() == 1
        assert source_location.matched_location is not None
        location = source_location.matched_location
        assert location.name == fixture["name"]
        assert (
            location.location_type.name == "Unknown"
        )  # all source location conversions use unknown for now
        if "location" in fixture:
            assert location.latitude == fixture["location"]["latitude"]
            assert location.longitude == fixture["location"]["longitude"]
        assert set(source_location.concordances.all()) == set(
            location.concordances.all()
        )
    elif original_location is not None:
        assert source_location.matched_location == original_location
        concordances = set(original_location.concordances.all())
        source_concordanes = set(source_location.concordances.all())
        assert source_concordanes.issubset(concordances)
