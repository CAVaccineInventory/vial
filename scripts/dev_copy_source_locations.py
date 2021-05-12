import click
import httpx
from click.exceptions import ClickException
import json


@click.command()
@click.option(
    "--source-url",
    default="https://vial.calltheshots.us/api/searchSourceLocations",
    help="API URL to fetch source locations from",
)
@click.option(
    "--source-token",
    help="API token to use when fetching data from the search API",
    envvar="SOURCE_TOKEN",
    required=True,
)
@click.option(
    "--destination-url",
    default="http://0.0.0.0:3000/api/importSourceLocations",
    help="API URL to send source locations to",
)
@click.option(
    "--destination-token",
    help="API token to use when sending data to the import API",
    envvar="DESTINATION_TOKEN",
    required=True,
)
def cli(source_url, source_token, destination_url, destination_token):
    "Export source locations from one instance and submit them via the import API to another instance - intended for populating development environments"
    # Run the import, twenty at a time
    source_locations = yield_source_locations(source_url, source_token)
    batch = []
    # Create an import run
    response = httpx.post(
        destination_url.replace("/api/importSourceLocations", "/api/startImportRun"),
        headers={"Authorization": "Bearer {}".format(destination_token)},
    )
    response.raise_for_status()
    import_run_id = response.json()["import_run_id"]
    for source_location in source_locations:
        batch.append(source_location)
        if len(batch) == 20:
            import_batch(batch, destination_url, destination_token, import_run_id)
            batch = []
    if batch:
        import_batch(batch, destination_url, destination_token, import_run_id)


def yield_source_locations(base_url, source_token):
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
            properties = json.loads(line)["properties"]
            # We just want source_uid, source_name, name, latitude, longitude, import_json
            yield {
                key: properties[key]
                for key in (
                    "source_uid",
                    "source_name",
                    "name",
                    "latitude",
                    "longitude",
                    "import_json",
                )
            }


def import_batch(batch, destination_url, destination_token, import_run_id):
    response = httpx.post(
        destination_url + "?import_run_id={}".format(import_run_id),
        data="\n".join(json.dumps(record) for record in batch),
        headers={"Authorization": "Bearer {}".format(destination_token)},
        timeout=20,
    )
    try:
        response.raise_for_status()
    except Exception as e:
        print(response.text)
        raise ClickException(e)
    click.echo(response.status_code)
    click.echo(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    cli()
