import httpx
from core.models import County, Location
from django.core.management.base import BaseCommand


def derive_county(latitude, longitude):
    url = "https://us-counties.datasette.io/counties/county_for_latitude_longitude.json"
    params = {"longitude": longitude, "latitude": latitude, "_shape": "array"}
    results = httpx.get(url, params=params).json()
    if len(results) != 1:
        return None
    fips = results[0]["county_fips"]
    try:
        return County.objects.get(fips_code=fips)
    except County.DoesNotExist:
        return None


class Command(BaseCommand):
    "Try to backfill the county for locations with no county but a latitude/longitude"

    def handle(self, *args, **options):
        for location in Location.objects.filter(county__isnull=True):
            county = derive_county(location.latitude, location.longitude)
            if county is not None:
                location.county = county
                location.save()
                print("{}: {} is in county {}".format(location.id, location, county))
            else:
                print(
                    "No county found for {} ({}, {})".format(
                        location, location.latitude, location.longitude
                    )
                )
