import httpx
import probableparsing
import usaddress


def derive_county(latitude, longitude):
    url = "https://us-counties.datasette.io/counties/county_for_latitude_longitude.json"
    params = {"longitude": longitude, "latitude": latitude, "_shape": "array"}
    results = httpx.get(url, params=params).json()
    if len(results) != 1:
        return None
    return results[0]


def extract_city_and_zip_code(address):
    try:
        address_components = usaddress.tag(address)[0]
        city = address_components.get("PlaceName") or None
        zip = address_components.get("ZipCode") or None
        return city, zip
    except probableparsing.RepeatedLabelError:
        return None, None
