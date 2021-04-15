import json

import pytest


@pytest.mark.django_db
def test_mapbox_export(client, ten_locations):
    response = client.get("/api/export-mapbox/Locations.geojson")
    joined = b"".join(response.streaming_content)
    assert json.loads(joined) == {
        "type": "FeatureCollection",
        "features": [
            {
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
            for location in ten_locations
        ],
    }
