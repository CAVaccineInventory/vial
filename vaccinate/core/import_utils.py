from github_contents import GithubContents
from .models import Location, State, LocationType, Provider, County, ProviderType


def load_airtable_backup(filepath, token):
    github = GithubContents("CAVaccineInventory", "airtable-data-backup", token)
    return github.read_large(filepath)[0]


def import_airtable_location(location):
    assert location.get("Name"), "No name"
    ca = State.objects.get(abbreviation="CA")
    # Special case: # "Napa ": "recjptepZLP1mzVDC" was a duplicate county
    fix_counties = {
        # 'Napa ' => 'Napa'
        "recjptepZLP1mzVDC": "recJ1fLYsngDaIRLG",
        # 'San Francisco County' => 'San Francisco'
        "recKSehOUATJ8CUkp": "recOuBZk28GMl7mVw",
    }
    address = location.get("Address") or ""
    # For the moment we default LocationType to Pharmacy - we should add "Unknown"
    location_type = location.get("Location Type", "Other")
    provider = None
    if location.get("Affiliation"):
        provider = Provider.objects.get_or_create(
            name=location["Affiliation"],
            defaults={"provider_type": lambda: ProviderType.objects.get(name="Other")},
        )[0]
    county = None
    if location.get("County link"):
        county = County.objects.get(
            airtable_id=fix_counties.get(
                location["County link"][0], location["County link"][0]
            )
        )
    elif location.get("County"):
        county = County.objects.get(
            state__abbreviation="CA", name=location["County"].replace(" County", "")
        )
    else:
        assert False, "No county"
    assert location.get("Latitude"), "No latitude"
    kwargs = {
        "name": location["Name"],
        "full_address": address,
        "street_address": address.split(",")[0].strip(),
        # "city": - will need to normalize and parse the address
        "phone_number": location.get("Phone number"),
        "state": ca,
        "hours": location.get("Hours"),
        "location_type": LocationType.objects.get_or_create(name=location_type)[0],
        "provider": provider,
        "google_places_id": location.get("google_places_id"),
        "county": county,
        "latitude": location["Latitude"],
        "longitude": location["Longitude"],
    }
    return Location.objects.update_or_create(
        airtable_id=location["airtable_id"], defaults=kwargs
    )[0]
