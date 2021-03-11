import json

from click.testing import CliRunner

from .vaccinefinder import cli

VACCINEFINDER_JSON = {
    "address1": "63 Newport Ave",
    "address2": "",
    "city": "Rumford",
    "distance": 1.03,
    "guid": "91c4731f-11e4-4b04-80a7-f0ae39cd859b",
    "in_stock": True,
    "lat": 41.857945,
    "long": -71.35557,
    "name": "CVS Pharmacy, Inc. #07387",
    "phone": "(555) 555-0461",
    "state": "RI",
    "zip": "02916",
}
EXPECTED = {
    "name": "CVS Pharmacy, Inc. #07387",
    "full_address": "63 Newport Ave, Rumford, RI, 02916",
    "street_address": "63 Newport Ave",
    "city": "Rumford",
    "phone_number": "(555) 555-0461",
    "zip_code": "02916",
    "website": None,
    "state": "RI",
    "location_type": "Unknown",
    "latitude": 41.857945,
    "longitude": -71.35557,
    "import_ref": "vf:91c4731f-11e4-4b04-80a7-f0ae39cd859b",
}


def test_help():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert result.output.startswith("Usage: cli [OPTIONS] [FILEPATHS]...")


def test_import_location_dry_run(httpx_mock):
    runner = CliRunner()
    with runner.isolated_filesystem():
        open("example.json", "w").write(json.dumps(VACCINEFINDER_JSON))
        result = runner.invoke(cli, ["example.json", "--dry-run"])
        assert result.exit_code == 0
        assert json.loads(result.output) == [EXPECTED]


def test_import_location_with_counties(httpx_mock):
    runner = CliRunner()
    httpx_mock.add_response(
        url="https://us-counties.datasette.io/counties/county_for_latitude_longitude.json?longitude=-71.35557&latitude=41.857945&_shape=array",
        json=[
            {
                "state_fips": "44",
                "state": "RI",
                "county_fips": "44007",
                "county_name": "Providence",
                "COUNTYNS": "01219781",
                "AFFGEOID": "0500000US44007",
                "GEOID": "44007",
                "LSAD": "06",
                "ALAND": 1060563722,
                "AWATER": 67858981,
            }
        ],
    )
    httpx_mock.add_response(
        method="POST",
        url="https://vaccinateca-preview.herokuapp.com/api/importLocations",
        json={"ok": True},
    )
    with runner.isolated_filesystem():
        open("example.json", "w").write(json.dumps(VACCINEFINDER_JSON))
        result = runner.invoke(
            cli, ["example.json", "--token", "x", "--derive-counties"]
        )
        assert result.exit_code == 0
        assert result.output == '200\n{\n  "ok": true\n}\n'
    import_locations_request = httpx_mock.get_requests()[1]
    expected_with_county = {**EXPECTED, **{"county": "Providence"}}
    assert json.loads(import_locations_request.read()) == [expected_with_county]
