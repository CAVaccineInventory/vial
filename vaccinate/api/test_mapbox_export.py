import json

import pytest


@pytest.fixture
def ten_locations_one_soft_deleted(ten_locations):
    soft_deleted = ten_locations[3]
    soft_deleted.soft_deleted = True
    soft_deleted.save()
    return ten_locations


@pytest.mark.django_db
def test_mapbox_export_geojson(client, ten_locations_one_soft_deleted):
    response = client.get("/api/export-mapbox/Locations.geojson")
    joined = b"".join(response.streaming_content)
    assert json.loads(joined) == {
        "type": "FeatureCollection",
        "features": [
            expected_feature(location)
            for location in ten_locations_one_soft_deleted
            if not location.soft_deleted
        ],
    }


@pytest.mark.django_db
def test_mapbox_export_ndgeojson(client, ten_locations_one_soft_deleted):
    response = client.get("/api/export-mapbox/Locations.ndgeojson")
    joined = b"".join(response.streaming_content)
    features = [json.loads(line) for line in joined.split(b"\n") if line.strip()]
    assert features == [
        expected_feature(location)
        for location in ten_locations_one_soft_deleted
        if not location.soft_deleted
    ]


def expected_feature(location):
    return {
        "type": "Feature",
        "properties": {
            "id": location.public_id,
            "name": location.name,
            "location_type": "Hospital / Clinic",
            "website": None,
            "address": None,
            "hours": None,
            "public_notes": None,
        },
        "geometry": {"type": "Point", "coordinates": [40.0, 30.0]},
    }
