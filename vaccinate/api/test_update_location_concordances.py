def test_update_location_concordances(client, api_key, ten_locations):
    location1, location2 = ten_locations[0], ten_locations[1]
    assert location1.concordances.count() == 0
    assert location2.concordances.count() == 0
    response = client.post(
        "/api/updateLocationConcordances",
        {
            "update": {
                location1.public_id: {
                    "add": ["google_places:123", "vaccinefinder:456"]
                },
                location2.public_id: {
                    "add": ["google_places:123", "vaccinefinder:678"]
                },
            }
        },
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    assert response.status_code == 200
    assert response.json()["updated"] == [location1.public_id, location2.public_id]
    assert [str(c) for c in location1.concordances.all()] == [
        "google_places:123",
        "vaccinefinder:456",
    ]
    assert [str(c) for c in location2.concordances.all()] == [
        "google_places:123",
        "vaccinefinder:678",
    ]
    # Now try the delete API (and add another at the same time)
    response2 = client.post(
        "/api/updateLocationConcordances",
        {
            "update": {
                location1.public_id: {"remove": ["google_places:123"]},
                location2.public_id: {
                    "remove": ["google_places:123"],
                    "add": ["cvs:8874"],
                },
            }
        },
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    assert response2.status_code == 200
    assert [str(c) for c in location1.concordances.all()] == ["vaccinefinder:456"]
    assert [str(c) for c in location2.concordances.all()] == [
        "vaccinefinder:678",
        "cvs:8874",
    ]
