import pytest
from reversion.models import Revision


@pytest.mark.django_db
@pytest.mark.parametrize(
    "fields,expected",
    (
        ({"name": "!"}, lambda l: l.name == "!"),
        ({"state": "RI"}, lambda l: l.state.abbreviation == "RI"),
        (
            {"latitude": 30.0, "longitude": 40.0},
            lambda l: l.latitude == 30.0 and l.longitude == 40.0,
        ),
        (
            {"location_type": "Private Practice"},
            lambda l: l.location_type.name == "Private Practice",
        ),
        (
            {"phone_number": "(555) 555-8888"},
            lambda l: l.phone_number == "(555) 555-8888",
        ),
        ({"full_address": "123 Bob St"}, lambda l: l.full_address == "123 Bob St"),
        ({"city": "Banzibar"}, lambda l: l.city == "Banzibar"),
        ({"state": "CA", "county": "Kern"}, lambda l: l.county.name == "Kern"),
        ({"google_places_id": "GP"}, lambda l: l.google_places_id == "GP"),
        (
            {"vaccinefinder_location_id": "VF"},
            lambda l: l.vaccinefinder_location_id == "VF",
        ),
        (
            {"vaccinespotter_location_id": "VS"},
            lambda l: l.vaccinespotter_location_id == "VS",
        ),
        ({"zip_code": "90210"}, lambda l: l.zip_code == "90210"),
        ({"hours": "M-F"}, lambda l: l.hours == "M-F"),
        (
            {"website": "https://example.com/"},
            lambda l: l.website == "https://example.com/",
        ),
        (
            {"preferred_contact_method": "research_online"},
            lambda l: l.preferred_contact_method == "research_online",
        ),
        (
            {"provider_type": "Pharmacy", "provider_name": "Costco"},
            lambda l: l.provider.name == "Costco",
        ),
    ),
)
def test_update_locations(client, api_key, ten_locations, fields, expected):
    location = ten_locations[0]
    assert Revision.objects.count() == 0
    input_data = {"update": {location.public_id: fields}}
    if fields.get("zip_code"):
        input_data["revision_comment"] = "Fixed zip"
    response = client.post(
        "/api/updateLocations",
        input_data,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    assert response.status_code == 200
    assert response.json()["updated"] == [location.public_id]
    location.refresh_from_db()
    assert expected(location)
    assert Revision.objects.count() == 1
    revision = Revision.objects.get()
    expected_comment = "/api/updateLocations"
    if fields.get("zip_code"):
        expected_comment = "Fixed zip"
    assert revision.comment == "{} by {}...".format(expected_comment, api_key[:10])
