import pytest

from .import_utils import import_vaccinefinder_location
from .models import Location

location_json = {
    "lat": 45.429994,
    "zip": "97015",
    "city": "Clackamas",
    "guid": "d958a6fe-df1f-41b0-ac87-b3457ce95b53",
    "long": -122.539509,
    "name": "Walgreens Co. #15927",
    "notes": "Appointments are required to receive a COVID-19 vaccine. No walk-ins are accepted at this time.",
    "phone": "503-653-1526",
    "state": "OR",
    "website": "https://www.walgreens.com",
    "address1": "11995 SE Sunnyside Rd",
    "address2": "",
    "hours_fri": "08:00AM - 10:00PM",
    "hours_mon": "08:00AM - 10:00PM",
    "hours_sat": "08:00AM - 10:00PM",
    "hours_sun": "08:00AM - 10:00PM",
    "hours_tue": "08:00AM - 10:00PM",
    "hours_wed": "08:00AM - 10:00PM",
    "inventory": [
        {
            "guid": "779bfe52-0dd8-4023-a183-457eb100fccc",
            "name": "Moderna COVID Vaccine",
            "in_stock": "FALSE",
            "supply_level": "NO_SUPPLY",
        },
        {
            "guid": "a84fb9ed-deb4-461c-b785-e17c782ef88b",
            "name": "Pfizer-BioNTech COVID Vaccine",
            "in_stock": "FALSE",
            "supply_level": "NO_SUPPLY",
        },
        {
            "guid": "784db609-dc1f-45a5-bad6-8db02e79d44f",
            "name": "Johnson & Johnson's Janssen COVID Vaccine",
            "in_stock": "FALSE",
            "supply_level": "NO_SUPPLY",
        },
    ],
    "hours_thur": "08:00AM - 10:00PM",
    "last_updated": "2021-03-06T09:50:17Z",
    "accepts_walk_ins": False,
    "accepts_insurance": True,
    "prescreening_site": "https://www.walgreens.com/findcare/vaccination/covid-19",
}


@pytest.mark.django_db
def test_import_vaccinefinder_location():
    assert not Location.objects.filter(
        import_ref="vf:d958a6fe-df1f-41b0-ac87-b3457ce95b53"
    ).exists()
    location = import_vaccinefinder_location(location_json)
    assert Location.objects.filter(
        import_ref="vf:d958a6fe-df1f-41b0-ac87-b3457ce95b53"
    ).exists()
    assert location.name == "Walgreens Co. #15927"
    assert location.phone_number == "503-653-1526"
    assert location.full_address == "11995 SE Sunnyside Rd, Clackamas, OR, 97015"
    assert location.street_address == "11995 SE Sunnyside Rd"
    assert location.city == "Clackamas"
    assert location.state.abbreviation == "OR"
    assert location.zip_code == "97015"
    assert location.website == "https://www.walgreens.com"
    assert location.latitude == 45.429994
    assert location.longitude == -122.539509
    assert location.import_ref == "vf:d958a6fe-df1f-41b0-ac87-b3457ce95b53"
