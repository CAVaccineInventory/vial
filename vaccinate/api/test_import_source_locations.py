import datetime
import json
import pathlib

import pytest
from bigmap.transform import source_to_location
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
    import_run = ImportRun.objects.get()
    json_start_response = start_response.json()
    assert "import_run_id" in json_start_response
    assert json_start_response["import_run_id"] == import_run.id

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
    assert float(source_location.latitude) == pytest.approx(
        fixture["import_json"]["location"]["latitude"]
    )
    assert float(source_location.longitude) == pytest.approx(
        fixture["import_json"]["location"]["longitude"]
    )
    assert source_location.import_json == fixture["import_json"]
    # TODO add more assertions about fields later

    # Source concordance must be associated with concordances
    source_concordance = ConcordanceIdentifier.objects.get(
        authority=fixture["import_json"]["source"]["source"],
        identifier=fixture["import_json"]["source"]["id"],
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
        # https://github.com/CAVaccineInventory/vial/issues/443
        assert location.public_id.startswith("l")
        assert location.name == fixture["name"]
        assert location.import_run == import_run
        assert (
            location.location_type.name == "Unknown"
        )  # all source location conversions use unknown for now
        if "location" in fixture:
            assert location.latitude == fixture["location"]["latitude"]
            assert location.longitude == fixture["location"]["longitude"]
        assert set(source_location.concordances.all()) == set(
            location.concordances.all()
        )

        if fixture["import_json"].get("contact") is not None:
            # source_to_location is tested separately
            correct_contact = source_to_location(fixture["import_json"])
            assert location.phone_number == correct_contact.get("phone_number")
            assert location.website == correct_contact.get("website")

    elif original_location is not None:
        assert source_location.matched_location == original_location
        concordances = set(original_location.concordances.all())
        source_concordanes = set(source_location.concordances.all())
        assert source_concordanes.issubset(concordances)


def test_import_location_twice_updates(client, api_key):
    fixture = json.load((tests_dir / "001-no-match.json").open())
    import_run_id = client.post(
        "/api/startImportRun", HTTP_AUTHORIZATION="Bearer {}".format(api_key)
    ).json()["import_run_id"]
    # Make the API request
    client.post(
        "/api/importSourceLocations?import_run_id={}".format(import_run_id),
        fixture,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    source_location = SourceLocation.objects.first()
    assert source_location.name == "Rite Aid"
    # Edit it a bit
    fake_last_imported_at = source_location.last_imported_at - datetime.timedelta(
        hours=1
    )
    source_location.last_imported_at = fake_last_imported_at
    source_location.name = "Update me"
    source_location.save()
    source_location.refresh_from_db()
    assert source_location.last_imported_at == fake_last_imported_at
    assert source_location.name == "Update me"
    client.post(
        "/api/importSourceLocations?import_run_id={}".format(import_run_id),
        fixture,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    source_location.refresh_from_db()
    assert source_location.last_imported_at != fake_last_imported_at
    assert source_location.name == "Rite Aid"


MATCH_ACTIONS = [None, {"action": "existing", "id": "foo"}, {"action": "new"}]


@pytest.mark.parametrize("match_action", MATCH_ACTIONS)
def test_import_does_not_overwrite_existing_match(client, api_key, match_action):
    fixture = json.load((tests_dir / "003-match-existing.json").open())

    # Create a location to match against first
    original_location = Location.objects.create(
        public_id=fixture["match"]["id"],
        name=fixture["name"],
        latitude=fixture["latitude"],
        longitude=fixture["longitude"],
        location_type=LocationType.objects.filter(name="Pharmacy").get(),
        state=State.objects.filter(abbreviation="CA").get(),
    )
    # Create a second location
    second_location = Location.objects.create(
        public_id="foo",
        name="TEST",
        latitude=fixture["latitude"],
        longitude=fixture["longitude"],
        location_type=LocationType.objects.filter(name="Pharmacy").get(),
        state=State.objects.filter(abbreviation="CA").get(),
    )

    # Create a source location that matches this, as from Velma
    source_location = SourceLocation.objects.create(
        source_name=fixture["source_name"],
        source_uid=fixture["source_uid"],
        matched_location=original_location,
    )
    source_location.refresh_from_db()
    assert source_location.matched_location == original_location

    # Modify the fixture to delete the match
    if match_action is None:
        del fixture["match"]
        assert "match" not in fixture
    else:
        fixture["match"] = match_action

    # Now start an import run for that location
    import_run_id = client.post(
        "/api/startImportRun", HTTP_AUTHORIZATION="Bearer {}".format(api_key)
    ).json()["import_run_id"]
    # Make the API request
    client.post(
        "/api/importSourceLocations?import_run_id={}".format(import_run_id),
        fixture,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )

    assert SourceLocation.objects.count() == 1
    source_location.refresh_from_db()
    assert source_location.matched_location == original_location

    # Check that we did not copy concordances onto the second location
    concordances = set(second_location.concordances.all())
    source_concordanes = set(source_location.concordances.all())
    assert not source_concordanes.issubset(concordances)
