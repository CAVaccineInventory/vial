import httpx


def derive_county(latitude, longitude):
    url = "https://us-counties.datasette.io/counties/county_for_latitude_longitude.json"
    params = {"longitude": longitude, "latitude": latitude, "_shape": "array"}
    results = httpx.get(url, params=params).json()
    if len(results) != 1:
        return None
    return results[0]
