import json

import click
import httpx
from click.exceptions import ClickException

from .import_utils import extract_city_and_zip_code


@click.command()
@click.argument(
    "filepath_or_url",
    type=str,
)
@click.option(
    "--url",
    default="https://vial.calltheshots.us/api/importLocations",
    help="API URL to send locations to",
)
@click.option("--token", help="API token to use", envvar="IMPORT_API_TOKEN")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Display locations without sending them to the API",
)
def cli(filepath_or_url, url, token, dry_run):
    "Import VaccinateCA Airtable locations"
    if not dry_run and not token:
        raise ClickException("--token is required unless running a --dry-run")
    # Run the import, twenty at a time
    locations = yield_locations(filepath_or_url)
    batch = []
    for location in locations:
        batch.append(location)
        if len(batch) == 20:
            import_batch(batch, url, token, dry_run)
            batch = []
    if batch:
        import_batch(batch, url, token, dry_run)


def yield_locations(filepath_or_url):
    if filepath_or_url.startswith("https://") or filepath_or_url.startswith("http://"):
        yield from httpx.get(filepath_or_url)
    else:
        yield from json.load(open(filepath_or_url))


def import_batch(batch, url, token, dry_run):
    fixed = []
    for item in batch:
        try:
            fixed.append(convert_airtable(item))
        except Exception as e:
            print(e)
            continue
    if dry_run:
        click.echo(json.dumps(fixed, indent=2))
    else:
        response = httpx.post(
            url,
            json=fixed,
            headers={"Authorization": "Bearer {}".format(token)},
            timeout=20,
        )
        try:
            response.raise_for_status()
        except Exception as e:
            print(response.text)
            raise ClickException(e)
        click.echo(response.status_code)
        click.echo(json.dumps(response.json(), indent=2))


def convert_airtable(location):
    import_ref = "vca-airtable:{}".format(location["airtable_id"])
    address = location["Address"]
    address_bits = [s.strip() for s in address.split(",")]
    city, zip_code = extract_city_and_zip_code(address)
    info = {
        "name": location["Name"],
        "full_address": ", ".join(address_bits),
        "street_address": address_bits[0],
        "city": city,
        "phone_number": location.get("Phone number"),
        "zip_code": zip_code,
        "website": location.get("Website"),
        "hours": location.get("Hours"),
        "county": location["County"].replace(" County", "").strip(),
        "state": "CA",
        "location_type": location.get("Location Type"),
        "latitude": location["Latitude"],
        "longitude": location["Longitude"],
        "import_ref": import_ref,
        "airtable_id": location["airtable_id"],
        "google_places_id": location.get("google_places_id"),
        "import_json": location,
    }
    return info


if __name__ == "__main__":
    cli()
