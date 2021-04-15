import json

import pytest


@pytest.mark.django_db
def test_mapbox_export(client, ten_locations):
    soft_deleted = ten_locations[3]
    soft_deleted.soft_deleted = True
    soft_deleted.save()
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
            if not location.soft_deleted
        ],
    }
