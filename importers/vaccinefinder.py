import json
import pathlib

import click
import httpx
from click.exceptions import ClickException

from .import_utils import derive_county


@click.command()
@click.argument(
    "filepaths",
    type=click.Path(dir_okay=True, file_okay=True, allow_dash=True),
    nargs=-1,
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
@click.option(
    "--derive-counties",
    is_flag=True,
    help="Derive counties from latitude/longitude",
)
def cli(filepaths, url, token, dry_run, derive_counties):
    "Import Vaccine Spotter locations - accepts multiple JSON files or directories containing JSON files"
    if not dry_run and not token:
        raise ClickException("--token is required unless running a --dry-run")
    # Run the import, twenty at a time
    locations = yield_locations(filepaths)
    batch = []
    for location in locations:
        batch.append(location)
        if len(batch) == 20:
            import_batch(batch, url, token, dry_run, derive_counties)
            batch = []
    if batch:
        import_batch(batch, url, token, dry_run, derive_counties)


def yield_locations(filepaths):
    for filepath in filepaths:
        path = pathlib.Path(filepath)
        if path.is_file() and path.suffix == ".json":
            data = json.loads(path.read_bytes())
            if data:
                if isinstance(data, list):
                    yield from data
                else:
                    yield data
        elif path.is_dir():
            for file in path.glob("**/*.json"):
                data = json.loads(file.read_bytes())
                if isinstance(data, list):
                    yield from data
                else:
                    yield data


def import_batch(batch, url, token, dry_run, derive_counties):
    fixed = [convert_vaccinefinder(item, derive_counties) for item in batch]
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


def convert_vaccinefinder(location, derive_counties):
    import_ref = "vf:{}".format(location["guid"])
    address_bits = [
        location[key]
        for key in ("address1", "address2", "city", "state", "zip")
        if location[key]
    ]
    info = {
        "name": location["name"],
        "full_address": ", ".join(address_bits),
        "street_address": address_bits[0],
        "city": location["city"],
        "phone_number": location["phone"],
        "zip_code": location["zip"],
        "website": location.get("website"),
        "state": location["state"],
        "location_type": "Unknown",
        "latitude": location["lat"],
        "longitude": location["long"],
        "import_ref": import_ref,
    }
    if derive_counties:
        county = derive_county(info["latitude"], info["longitude"])
        if county:
            info["county"] = county["county_name"]
    return info


if __name__ == "__main__":
    cli()
