import json
import pathlib

from core.models import ConcordanceIdentifier, Location, SourceLocation
from reversion.models import Revision


def test_create_location_from_source_location(client, api_key):
    fixture = json.load(
        (
            pathlib.Path(__file__).parent
            / "test-data"
            / "importSourceLocations"
            / "002-new-location.json"
        ).open()
    )
    source_location = SourceLocation.objects.create(
        source_uid=fixture["source_uid"],
        source_name=fixture["source_name"],
        name=fixture["name"],
        latitude=fixture["latitude"],
        longitude=fixture["longitude"],
        import_json=fixture["import_json"],
    )
    source_location.concordances.add(ConcordanceIdentifier.for_idref("foo:bar"))
    assert SourceLocation.objects.count() == 1
    assert Location.objects.count() == 0
    assert Revision.objects.count() == 0

    response = client.post(
        "/api/createLocationFromSourceLocation",
        {"source_location": fixture["source_uid"]},
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    assert response.status_code == 200

    location = Location.objects.first()

    assert response.json() == {
        "location": {
            "id": location.public_id,
            "name": "Rite Aid",
            "vial_url": "http://testserver/admin/core/location/{}/change/".format(
                location.pk
            ),
        }
    }

    # Ensure source location concordances were copied over
    assert [str(c) for c in location.concordances.all()] == ["foo:bar"]

    source_location.refresh_from_db()
    assert source_location.matched_location == location

    # Should have created a revision
    revision = Revision.objects.first()
    assert (
        revision.comment
        == "/api/createLocationFromSourceLocation API key 1:1953b7a7..."
    )
