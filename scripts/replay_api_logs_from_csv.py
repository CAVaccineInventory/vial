import csv
import time
from collections import defaultdict
from urllib.parse import urlencode

import click
import httpx
import orjson
import pytz
from dateutil import parser


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
    "Replace CSV API logs exported from Airtable, see https://github.com/CAVaccineInventory/vial/issues/29"
    url = base_url + endpoint
    print(url)
    reader = csv.DictReader(csv_filepath)
    # Collect all of the rows we are going to process in memory
    # - streaming would be more efficient, but I want to count
    # the endpoint matches and show a progress bar
    rows = [
        row
        for row in reader
        if row["endpoint"] == endpoint and "SERVICE_UNAVAILABLE" not in row["payload"]
    ]
    status_count = defaultdict(int)
    with click.progressbar(rows, show_pos=True) as progress_rows:
        for row in progress_rows:
            status, data = send_row(row, url)
            status_count[status] += 1
            if status != 200:
                click.echo(orjson.dumps(data, option=orjson.OPT_INDENT_2), err=True)
    click.echo(orjson.dumps(status_count))


def send_row(row, url):
    created_in_los_angeles = parser.parse(row["Created"])
    tz = pytz.timezone("America/Los_Angeles")
    created_in_utc = tz.localize(created_in_los_angeles).astimezone(pytz.UTC)
    url += "?" + urlencode(
        {
            "test": 1,
            "fake_user": row["auth0_reporter_id"],
            "fake_timestamp": created_in_utc.isoformat(),
            "fake_remote_ip": row["remote_ip"],
        }
    )
    payload = orjson.loads(row["payload"])
    response = None
    errors = []
    for i in range(1, 4):
        try:
            response = httpx.post(url, json=payload)
        except Exception as e:
            time.sleep(i)
            errors.append(str(e))
            continue
        else:
            break
    if response is None:
        return 600, {"errors": errors}
    try:
        data = response.json()
    except Exception as e:
        data = {"json_error": str(e)}
    return response.status_code, {
        "status": response.status_code,
        "input": payload,
        "output": data,
    }


if __name__ == "__main__":
    cli()
