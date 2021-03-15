import json
import pathlib

import click
import httpx
from click.exceptions import ClickException

from .import_utils import derive_county


@click.command()
@click.argument(
    "filepath",
    type=click.Path(dir_okay=False, file_okay=True, allow_dash=True),
)
@click.option(
    "--url",
    default="https://vaccinateca-preview.herokuapp.com/api/importLocations",
    help="API URL to send locations to",
)
@click.option("--token", help="API token to use", envvar="IMPORT_API_TOKEN")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Display locations without sending them to the API",
)
def cli(filepath, url, token, dry_run):
    "Import locations from admin_site_and_county_map_site_no_info_with_places_data"
    if not dry_run and not token:
        raise ClickException("--token is required unless running a --dry-run")
    # Run the import, twenty at a time
    locations = json.load(open(filepath))
    batch = []
    for location in locations:
        batch.append(location)
        if len(batch) == 20:
            import_batch(batch, url, token, dry_run)
            batch = []
    if batch:
        import_batch(batch, url, token, dry_run)


def import_batch(batch, url, token, dry_run):
    fixed = [convert_location(item) for item in batch]
    fixed = [f for f in fixed if f and f.get("phone_number")]
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


def convert_location(location):
    import_ref = "oregon-tableau:{}".format(location["Location ID-value"])
    place_data = location.get("google_places_data")
    if not place_data:
        return None
    hours = None
    weekday_text = place_data.get("opening_hours", {}).get("weekday_text")
    if weekday_text:
        hours = "\n".join(weekday_text)
    return {
        "name": location["Organization-alias"],
        "full_address": place_data["formatted_address"],
        "street_address": location["Administration  Address-alias"],
        "city": location["City-alias"],
        "phone_number": place_data.get("formatted_phone_number"),
        "zip_code": location["Zip Code-alias"],
        "website": place_data.get("website"),
        "google_places_id": location["google_places_id"],
        "state": location["GEOAdmin State-alias"],
        "location_type": "Unknown",
        "latitude": place_data["geometry"]["location"]["lat"],
        "longitude": place_data["geometry"]["location"]["lng"],
        "hours": hours,
        "import_ref": import_ref,
    }


if __name__ == "__main__":
    cli()
