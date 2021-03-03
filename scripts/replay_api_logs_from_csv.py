from collections import defaultdict
from urllib.parse import urlencode
import click
import csv
import httpx
import json


@click.command()
@click.argument("endpoint", type=click.Choice(["submitReport"], case_sensitive=False))
@click.argument(
    "csv_filepath",
    # Using utf-8-sig to skip the BOM at the start of the file
    type=click.File(encoding="utf-8-sig"),
)
@click.option(
    "--base-url",
    default="http://localhost:3000/api/",
    help="URL to the base of the API",
)
def cli(endpoint, csv_filepath, base_url):
    "Replace CSV API logs exported from Airtable, see https://github.com/CAVaccineInventory/django.vaccinate/issues/29"
    url = base_url + endpoint
    print(url)
    reader = csv.DictReader(csv_filepath)
    # Collect all of the rows we are going to process in memory
    # - streaming would be more efficient, but I want to count
    # the endpoint matches and show a progress bar
    rows = [row for row in reader if row["endpoint"] == endpoint]
    status_count = defaultdict(int)
    with click.progressbar(rows) as progress_rows:
        for row in progress_rows:
            status = send_row(row, url)
            status_count[status] += 1
    print(status_count)


def send_row(row, url):
    url += "?" + urlencode({"test": 1, "fake_user": row["auth0_reporter_id"]})
    response = httpx.post(url, json=json.loads(row["payload"]))
    return response.status_code


if __name__ == "__main__":
    cli()
