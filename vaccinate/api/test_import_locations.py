import pytest
from core.models import Location, LocationType, Provider, ProviderType

from .models import ApiLog


@pytest.mark.django_db
@pytest.mark.parametrize("use_list", (False, True))
def test_import_location(client, api_key, use_list):
    assert Location.objects.count() == 0
    assert Provider.objects.count() == 0
    location_input = {
        "name": "Walgreens San Francisco",
        "phone_number": "(555) 555-5554",
        "full_address": "5th Second Avenue, San Francisco, CA",
        "city": "San Francisco",
        "state": "CA",
        "county": "San Francisco",
        "google_places_id": "google-places-1",
        "vaccinespotter_location_id": "vaccine-spotter-1",
        "vaccinefinder_location_id": "vaccine-finder-1",
        "zip_code": "94102",
        "hours": "Opening hours go here",
        "website": "www.example.com",
        "latitude": 37.781869,
        "longitude": -122.439517,
        "location_type": "Pharmacy",
        "airtable_id": "airtable-1",
        "provider_name": "Walgreens",
        "provider_type": "Pharmacy",
    }
    json_input = location_input
    if use_list:
        json_input = [location_input]
    response = client.post(
        "/api/importLocations",
        json_input,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    assert response.status_code == 200
    assert not response.json()["errors"]
    assert Location.objects.count() == 1
    assert Provider.objects.count() == 1
    provider = Provider.objects.get()
    assert provider.name == "Walgreens"
    assert provider.provider_type.name == "Pharmacy"
    location = Location.objects.get()
    assert response.json() == {
        "errors": [],
        "added": [location.public_id],
        "updated": [],
    }
    assert location.name == "Walgreens San Francisco"
    assert location.phone_number == "(555) 555-5554"
    assert location.full_address == "5th Second Avenue, San Francisco, CA"
    assert location.street_address == "5th Second Avenue"
    assert location.city == "San Francisco"
    assert location.zip_code == "94102"
    assert location.state.name == "California"
    assert location.hours == "Opening hours go here"
    assert location.website == "www.example.com"
    assert location.county.name == "San Francisco"
    assert location.google_places_id == "google-places-1"
    assert location.vaccinespotter_location_id == "vaccine-spotter-1"
    assert location.vaccinefinder_location_id == "vaccine-finder-1"
    assert location.airtable_id == "airtable-1"
    assert location.latitude == 37.781869
    assert location.longitude == -122.439517
    assert location.location_type.name == "Pharmacy"
    assert location.import_json is None
    # Check that ApiLog record was created
    log = ApiLog.objects.get()
    assert log.api_key.token == api_key


@pytest.mark.django_db
def test_import_location_with_import_json(client, api_key):
    location_input = {
        "name": "Walgreens San Francisco II",
        "import_json": {"This is import json": True},
        "location_type": "Pharmacy",
        "state": "CA",
        "latitude": 37.781869,
        "longitude": -122.439517,
        "preferred_contact_method": "research_online",
    }
    assert Location.objects.count() == 0
    response = client.post(
        "/api/importLocations",
        location_input,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    assert response.status_code == 200
    assert not response.json()["errors"]
    assert Location.objects.count() == 1
    location = Location.objects.get()
    assert location.name == "Walgreens San Francisco II"
    assert location.preferred_contact_method == "research_online"
    assert location.import_json == {"This is import json": True}


@pytest.mark.django_db
def test_import_location_with_import_ref(client, api_key):
    assert Location.objects.count() == 0
    response = client.post(
        "/api/importLocations",
        {
            "name": "Walgreens San Francisco II",
            "state": "CA",
            "latitude": 37.781869,
            "longitude": -122.439517,
            "location_type": "Pharmacy",
            "import_ref": "my-import-ref",
        },
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    assert response.status_code == 200
    assert Location.objects.count() == 1
    location = Location.objects.get()
    assert location.name == "Walgreens San Francisco II"
    assert not location.soft_deleted
    # Now do it again with the same import ref
    response2 = client.post(
        "/api/importLocations",
        {
            "name": "Walgreens San Francisco III",
            "state": "CA",
            "latitude": 37.781869,
            "longitude": -122.439517,
            "location_type": "Pharmacy",
            "import_ref": "my-import-ref",
        },
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    assert response2.status_code == 200
    assert Location.objects.count() == 1
    location2 = Location.objects.get()
    assert location2.name == "Walgreens San Francisco III"
    assert response2.json() == {
        "errors": [],
        "updated": [location2.public_id],
        "added": [],
    }


@pytest.mark.django_db
def test_import_soft_deleted_location(client, api_key):
    assert Location.objects.count() == 0
    response = client.post(
        "/api/importLocations",
        {
            "name": "Walgreens San Francisco II",
            "state": "CA",
            "latitude": 37.781869,
            "longitude": -122.439517,
            "location_type": "Pharmacy",
            "import_ref": "my-import-ref",
            "soft_deleted": True,
        },
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    assert response.status_code == 200
    assert Location.objects.count() == 1
    location = Location.objects.get()
    assert location.soft_deleted


@pytest.mark.django_db
def test_import_duplicate_location(client, api_key, ten_locations):
    other = ten_locations[0]
    response = client.post(
        "/api/importLocations",
        {
            "name": "Walgreens San Francisco II",
            "state": "CA",
            "latitude": 37.781869,
            "longitude": -122.439517,
            "location_type": "Pharmacy",
            "import_ref": "my-import-ref",
            "soft_deleted": True,
            "duplicate_of": other.public_id,
        },
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer {}".format(api_key),
    )
    assert response.status_code == 200
    assert Location.objects.count() == 11
    location = Location.objects.get(soft_deleted=True)
    assert location.duplicate_of == other


@pytest.mark.django_db
def test_provider_types(client):
    response = client.get("/api/providerTypes")
    assert response.json() == {
        "provider_types": list(ProviderType.objects.values_list("name", flat=True))
    }


@pytest.mark.django_db
def test_location_types(client):
    response = client.get("/api/locationTypes")
    assert response.json() == {
        "location_types": list(LocationType.objects.values_list("name", flat=True))
    }
