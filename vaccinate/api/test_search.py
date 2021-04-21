import json

import pytest
from core.models import ConcordanceIdentifier, Location, State


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
    response = client.get("/api/searchLocations?" + query_string)
    assert response.status_code == 200
    data = json.loads(response.content)
    names = [r["name"] for r in data["results"]]
    assert names == expected
    assert data["total"] == len(expected)


def test_search_locations_ignores_soft_deleted(client, ten_locations):
    assert (
        json.loads(client.get("/api/searchLocations?q=Location+1").content)["total"]
        == 2
    )
    Location.objects.filter(name="Location 10").update(soft_deleted=True)
    assert (
        json.loads(client.get("/api/searchLocations?q=Location+1").content)["total"]
        == 1
    )
