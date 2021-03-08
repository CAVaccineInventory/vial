import csv
import io

import httpx
from core.models import County, State
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    def handle(self, *args, **options):
        counties_url = "https://us-counties.datasette.io/counties/county_fips.csv?_stream=on&_size=max"
        # Bulk load all states
        states = {state.abbreviation: state for state in State.objects.all()}
        s = io.StringIO(httpx.get(counties_url).text)
        for county in csv.DictReader(s):
            if county["state"] not in states:
                print(
                    "Skipping {}, state = {}".format(
                        county["county_name"], county["state"]
                    )
                )
                continue
            County.objects.update_or_create(
                fips_code=county["county_fips"],
                defaults={
                    "name": county["county_name"],
                    "state": states[county["state"]],
                },
            )
