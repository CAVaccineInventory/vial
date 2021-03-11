import csv
import io

import requests
from core.models import County, State
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    @transaction.atomic
    def handle(self, *args, **options):
        counties_url = "https://us-counties.datasette.io/counties/county_fips.csv?_stream=on&_size=max"
        # Bulk load all states
        states = {state.abbreviation: state for state in State.objects.all()}
        # Load all fips codes we've seen before so we can skip them
        existing_county_fips_codes = {
            str(fips)
            for fips in County.objects.select_for_update().values_list(
                "fips_code", flat=True
            )
        }
        s = io.StringIO(requests.get(counties_url).text)
        to_create = []
        for county in csv.DictReader(s):
            if str(county["county_fips"]) in existing_county_fips_codes:
                continue
            if county["state"] not in states:
                print(
                    "Skipping {}, state = {}".format(
                        county["county_name"], county["state"]
                    )
                )
                continue
            to_create.append(
                County(
                    fips_code=county["county_fips"],
                    name=county["county_name"],
                    state=states[county["state"]],
                )
            )
        County.objects.bulk_create(to_create)
