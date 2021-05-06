import json

import pytest
from core.models import ConcordanceIdentifier, Location, SourceLocation, State


def search_locations(
    client, api_key, query_string, path="/api/searchLocations", expected_status_code=200
):
    response = client.get(
        path + "?" + query_string,
        HTTP_AUTHORIZATION=f"Bearer {api_key}",
    )
    assert response.status_code == expected_status_code
    if hasattr(response, "streaming_content"):
        content = b"".join(response.streaming_content)
    else:
        content = response.content
    return json.loads(content)


def search_source_locations(client, api_key, query_string, expected_status_code=200):
    return search_locations(
        client,
        api_key,
        query_string,
        path="/api/searchSourceLocations",
        expected_status_code=expected_status_code,
    )


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
def test_search_locations(client, api_key, query_string, expected, ten_locations):
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
    data = search_locations(client, api_key, query_string)
    names = {r["name"] for r in data["results"]}
    assert names == set(expected)
    assert data["total"] == len(expected)


def test_search_locations_by_id(client, api_key, ten_locations):
    data = search_locations(
        client,
        api_key,
        "id={}&id={}".format(ten_locations[0].public_id, ten_locations[1].public_id),
    )
    names = {r["name"] for r in data["results"]}
    assert names == {ten_locations[0].name, ten_locations[1].name}
    assert data["total"] == 2


def test_search_locations_ignores_soft_deleted(client, api_key, ten_locations):
    assert search_locations(client, api_key, "q=Location+1")["total"] == 2
    Location.objects.filter(name="Location 10").update(soft_deleted=True)
    assert search_locations(client, api_key, "q=Location+1")["total"] == 1


def test_search_locations_format_json(client, api_key, ten_locations):
    result = search_locations(client, api_key, "q=Location+1")
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


def test_search_locations_format_geojson(client, api_key, ten_locations):
    result = search_locations(client, api_key, "q=Location+1&format=geojson")
    assert set(result.keys()) == {"type", "features"}
    assert result["type"] == "FeatureCollection"
    record = result["features"][0]
    assert set(record.keys()) == {"type", "properties", "geometry"}
    assert record["geometry"] == {"type": "Point", "coordinates": [40.0, 30.0]}


def test_search_locations_format_nlgeojson(client, api_key, ten_locations):
    response = client.get(
        "/api/searchLocations?q=Location+1&format=nlgeojson",
        HTTP_AUTHORIZATION=f"Bearer {api_key}",
    )
    assert response.status_code == 200
    joined = b"".join(response.streaming_content)
    # Should return two results split by newlines
    lines = joined.split(b"\n")
    assert len(lines) == 2
    for line in lines:
        record = json.loads(line)
        assert set(record.keys()) == {"type", "properties", "geometry"}


def test_search_stream_all(client, api_key, two_hundred_locations):
    # I would have used parametrize here, but that runs two_hundred_locations
    # fixture three times and I only want to run it once
    for format, check in (
        ("json", lambda r: len(json.loads(r)["results"]) == 200),
        ("geojson", lambda r: len(json.loads(r)["features"]) == 200),
        ("nlgeojson", lambda r: len(r.split(b"\n")) == 200),
    ):
        response = client.get(
            "/api/searchLocations?format={}&all=1".format(format),
            HTTP_AUTHORIZATION=f"Bearer {api_key}",
        )
        assert response.status_code == 200
        joined = b"".join(response.streaming_content)
        assert check(joined)


def test_search_locations_num_queries(
    client, api_key, ten_locations, django_assert_num_queries
):
    # Failure of this assert means that a field needs to be added to the "only" of
    # location_json_queryset.  The 6 queries are:
    # 1. Look up the api_key
    # 2. Update the api_key's last_seen_at
    # 3. Insert into the api_log
    # 4. Fetch the locations, and all of the 1-to-1 or many-to-1 tables
    # 5. Fetch the condordances, which are many-to-many
    # 6. Repeat the locations fetch to verify we found all of them
    with django_assert_num_queries(6):
        search_locations(client, api_key, "all=1&format=geojson")


@pytest.mark.parametrize(
    "radius,expected",
    (
        (10, {"Location 1"}),
        (10000, {"Location 1", "Location 2"}),
    ),
)
def test_search_locations_point_radius(
    client, api_key, ten_locations, radius, expected
):
    for i, location in enumerate(ten_locations):
        location.latitude = 37.5
        location.longitude = -122.4 + (i / 10.0)
        location.save()
    results = search_locations(
        client, api_key, "latitude=37.5&longitude=-122.4&radius={}".format(radius)
    )
    assert {r["name"] for r in results["results"]} == expected


def test_search_locations_point_radius_errors(client, api_key):
    for qs in (
        "latitude=bad&longitude=-122.4&radius=10",
        "latitude=43.4&longitude=bad&radius=10",
        "latitude=43.4&longitude=-122.4&radius=bad",
    ):
        assert search_locations(client, api_key, qs, expected_status_code=400) == {
            "error": "latitude/longitude/radius should be numbers"
        }


def test_search_allows_users_with_cookie(client, admin_client, ten_locations):
    assert client.get("/api/searchLocations").status_code == 403
    assert admin_client.get("/api/searchLocations").status_code == 200


@pytest.mark.parametrize(
    "query_string,expected_names",
    (
        ("", {"One", "Two", "Three Matched"}),
        ("unmatched=1", {"One", "Two"}),
        ("matched=1", {"Three Matched"}),
        ("id=test:1&id=test:2", {"One", "Two"}),
        ("id=ID_OF_ONE", {"One"}),
        ("idref=foo:bar", {"Two"}),
    ),
)
def test_search_source_locations(
    client, api_key, ten_locations, query_string, expected_names
):
    id_of_one = SourceLocation.objects.create(
        source_name="test",
        source_uid="test:1",
        name="One",
    ).pk
    query_string = query_string.replace("ID_OF_ONE", str(id_of_one))
    two = SourceLocation.objects.create(
        source_name="test",
        source_uid="test:2",
        name="Two",
    )
    two.concordances.add(ConcordanceIdentifier.for_idref("foo:bar"))
    SourceLocation.objects.create(
        source_name="test",
        source_uid="test:3",
        name="Three Matched",
        matched_location=ten_locations[0],
    )
    data = search_source_locations(client, api_key, query_string)
    assert data["total"] == len(expected_names)
    assert {result["name"] for result in data["results"]} == expected_names


def test_search_source_locations_all(client, api_key):
    # Create 1001 source locations and check they are returned
    expected_source_uids = set()
    for i in range(1, 1002):
        SourceLocation.objects.create(
            source_name="test",
            source_uid="test:{}".format(i),
            name=str(i),
        )
        expected_source_uids.add("test:{}".format(i))
    data = search_source_locations(client, api_key, "all=1")
    assert data["total"] == 1001
    assert {result["source_uid"] for result in data["results"]} == expected_source_uids
