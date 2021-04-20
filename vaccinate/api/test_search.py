import json

import pytest
from core.models import Location


@pytest.mark.parametrize(
    "query_string,expected", (("q=location+1", ["Location 1", "Location 10"]),)
)
def test_search_locations(client, query_string, expected, ten_locations):
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
