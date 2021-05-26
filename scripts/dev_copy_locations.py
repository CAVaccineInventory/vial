import click
import httpx
import orjson
from click.exceptions import ClickException


@click.command()
@click.option(
    "--source-url",
    default="https://vial.calltheshots.us/api/searchLocations",
    help="API URL to fetch locations from",
)
@click.option(
    "--source-token",
    help="API token to use when fetching data from the search API",
    envvar="SOURCE_TOKEN",
    required=True,
)
@click.option(
    "--destination-url",
    default="http://0.0.0.0:3000/api/importLocations",
    help="API URL to send locations to",
)
@click.option(
    "--destination-token",
    help="API token to use when sending data to the import API",
    envvar="DESTINATION_TOKEN",
    required=True,
)
def cli(source_url, source_token, destination_url, destination_token):
    "Export locations from one instance and submit them via the import API to another instance - intended for populating development environments"
    # Run the import, twenty at a time
    locations = yield_locations(source_url, source_token)
    batch = []
    for location in locations:
        batch.append(location)
        if len(batch) == 20:
            import_batch(batch, destination_url, destination_token)
            batch = []
    if batch:
        import_batch(batch, destination_url, destination_token)


def yield_locations(base_url, source_token):
    # Use format=nlgeojson
    if "?" not in base_url:
        base_url += "?"
    else:
        base_url += "&"
    base_url += "format=nlgeojson"
    with httpx.stream(
        "GET", base_url, headers={"Authorization": "Bearer {}".format(source_token)}
    ) as response:
        for line in response.iter_lines():
            geojson = orjson.loads(line)
            properties = geojson["properties"]
            data = {
                key: properties[key]
                for key in (
                    "name",
                    "state",
                    "location_type",
                    "phone_number",
                    "full_address",
                    "city",
                    "county",
                    "zip_code",
                    "hours",
                    "website",
                )
            }
            longitude, latitude = geojson["geometry"]["coordinates"]
            data["latitude"] = latitude
            data["longitude"] = longitude
            yield data


def import_batch(batch, destination_url, destination_token):
    response = httpx.post(
        destination_url,
        json=batch,
        headers={"Authorization": "Bearer {}".format(destination_token)},
        timeout=20,
    )
    try:
        response.raise_for_status()
    except Exception as e:
        print(response.text)
        raise ClickException(e)
    click.echo(response.status_code)
    click.echo(orjson.dumps(response.json(), option=orjson.OPT_INDENT_2))


if __name__ == "__main__":
    cli()
