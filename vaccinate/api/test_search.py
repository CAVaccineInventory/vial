import json

import pytest
from core.models import ConcordanceIdentifier, Location, State


def search_get_json(client, query_string):
    response = client.get("/api/searchLocations?" + query_string)
    assert response.status_code == 200
    joined = b"".join(response.streaming_content)
    return json.loads(joined)


@pytest.mark.parametrize(
    "query_string,expected",
    (
        ("q=location+1", ["Location 1", "Location 10"]),
        ("state=ks", ["Location 6"]),
        ("idref=google_places:123", ["Location 7"]),
        (
            "idref=google_places:123&idref=google_places:456",
            ["Location 8", "Location 7"],
        ),
    ),
)
def test_search_locations(client, query_string, expected, ten_locations):
    in_kansas = ten_locations[5]
    in_kansas.state = State.objects.get(name="Kansas")
    in_kansas.save()
    with_concordances_1 = ten_locations[6]
    with_concordances_2 = ten_locations[7]
    with_concordances_1.concordances.add(
        ConcordanceIdentifier.for_idref("google_places:123")
    )
    with_concordances_2.concordances.add(
        ConcordanceIdentifier.for_idref("google_places:456")
    )
    data = search_get_json(client, query_string)
    names = [r["name"] for r in data["results"]]
    assert names == expected
    assert data["total"] == len(expected)


def test_search_locations_ignores_soft_deleted(client, ten_locations):
    assert search_get_json(client, "q=Location+1")["total"] == 2
    Location.objects.filter(name="Location 10").update(soft_deleted=True)
    assert search_get_json(client, "q=Location+1")["total"] == 1


def test_search_locations_format_json(client, ten_locations):
    result = search_get_json(client, "q=Location+1")
    assert set(result.keys()) == {"results", "total"}
    record = result["results"][0]
    assert set(record.keys()) == {
        "id",
        "name",
        "state",
        "latitude",
        "longitude",
        "location_type",
        "import_ref",
        "phone_number",
        "full_address",
        "city",
        "county",
        "google_places_id",
        "vaccinefinder_location_id",
        "vaccinespotter_location_id",
        "zip_code",
        "hours",
        "website",
        "preferred_contact_method",
        "provider",
        "concordances",
    }


def test_search_locations_format_geojson(client, ten_locations):
    result = search_get_json(client, "q=Location+1&format=geojson")
    assert set(result.keys()) == {"type", "features"}
    assert result["type"] == "FeatureCollection"
    record = result["features"][0]
    assert set(record.keys()) == {"type", "properties", "geometry"}
    assert record["geometry"] == {"type": "Point", "coordinates": [40.0, 30.0]}


def test_search_locations_format_nlgeojson(client, ten_locations):
    response = client.get("/api/searchLocations?q=Location+1&format=nlgeojson")
    assert response.status_code == 200
    joined = b"".join(response.streaming_content)
    # Should return two results split by newlines
    lines = joined.split(b"\n")
    assert len(lines) == 2
    for line in lines:
        record = json.loads(line)
        assert set(record.keys()) == {"type", "properties", "geometry"}
