import json

from core.models import ConcordanceIdentifier


def test_update_location_concordances(client, api_key, ten_locations):
    location1, location2 = ten_locations[0], ten_locations[1]
    assert location1.concordances.count() == 0
    assert location2.concordances.count() == 0
    # Create a concordance that will be garbage collected
    ConcordanceIdentifier.objects.create(authority="gc_test", identifier="collect_me")
    # And one that won't
    ConcordanceIdentifier.objects.create(
        authority="gc_test", identifier="leave_me"
    ).source_locations.create(
        source_uid="gc_test:1", source_name="gc_test", name="Blah"
    )
    assert [str(c) for c in ConcordanceIdentifier.objects.all()] == [
        "gc_test:collect_me",
        "gc_test:leave_me",
    ]
    response = client.post(
        "/api/updateLocationConcordances",
        {
            "update": {
                location1.public_id: {
                    "add": ["google_places:123", "vaccinefinder:456"]
                },
                location2.public_id: {"add": ["google_places:123", "sav-on:678"]},
            }
        },
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    assert response.status_code == 200
    assert response.json()["updated"] == [location1.public_id, location2.public_id]
    assert [str(c) for c in ConcordanceIdentifier.objects.all()] == [
        "gc_test:leave_me",
        "google_places:123",
        "vaccinefinder:456",
        "sav-on:678",
    ]
    assert [str(c) for c in location1.concordances.all()] == [
        "google_places:123",
        "vaccinefinder:456",
    ]
    assert [str(c) for c in location2.concordances.all()] == [
        "google_places:123",
        "sav-on:678",
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
    assert [str(c) for c in ConcordanceIdentifier.objects.all()] == [
        "gc_test:leave_me",
        "vaccinefinder:456",
        "sav-on:678",
        "cvs:8874",
    ]
    assert [str(c) for c in location1.concordances.all()] == ["vaccinefinder:456"]
    assert [str(c) for c in location2.concordances.all()] == [
        "sav-on:678",
        "cvs:8874",
    ]


def test_update_location_concordances_with_user_cookie(
    client, admin_client, admin_user, ten_locations
):
    # Without staff cookie should return error
    location = ten_locations[0]
    request_body = {
        "update": {
            location.public_id: {"add": ["google_places:127"]},
        }
    }
    assert location.concordances.count() == 0
    deny_response = client.post(
        "/api/updateLocationConcordances",
        request_body,
        content_type="application/json",
    )
    assert deny_response.status_code == 403
    assert location.concordances.count() == 0
    assert admin_user.api_logs.count() == 0
    # Should work for logged in user
    allow_response = admin_client.post(
        "/api/updateLocationConcordances",
        request_body,
        content_type="application/json",
    )
    assert allow_response.status_code == 200
    assert location.concordances.count() == 1
    assert str(location.concordances.get()) == "google_places:127"
    # Should have created an API log
    assert (
        admin_user.api_logs.values("path")[0]["path"]
        == "/api/updateLocationConcordances"
    )


def test_get_location_concordances(client, ten_locations):
    location = ten_locations[0]
    location.concordances.add(ConcordanceIdentifier.for_idref("foo:bar"))
    response = client.get("/api/location/{}/concordances".format(location.public_id))
    assert json.loads(response.content) == {"concordances": ["foo:bar"]}
