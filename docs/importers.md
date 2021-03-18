# Importer scripts

Importers are scripts that live in the `importers/` directory in this repository. They consume locations from a variety of sources and send them to the `/api/importLocations` API to import them into the database.

You can run the tests for the importers by changing into the top level directory (`vial`) and running `pytest importers`

## importers.vaccinefinder

Run this importer from the top-level `vial` folder like so:

    python -m importers.vaccinefinder --help

The script takes as arguments a list of JSON files or of directories containing JSON files.

Here's how to run it against all locations in Rhode Island.

First, checkout the `vaccine-feeds/raw-feed-data` directory. Here I'm checking it out to my `/tmp` directory:

    git clone git@github.com:vaccine-feeds/raw-feed-data /tmp/raw-feed-data

You can run a dry run to see what will happen like so:

    python -m importers.vaccinefinder \
        ../raw-feed-data/vaccine-finder/RI/locations \
        --dry-run

This will output a preview of the data, transformed into our API format.

You can add `--derive-counties` to make an API call for each location to derive the county for it based on its latitude and longitude.

To run the actual import, add the `--token` argument with as API Key (created at https://vial.calltheshots.us/admin/api/apikey/) and use the `--url` argument to specify the API endpoint to send the data to (it defaults to `http://localhost:3000/api/importLocations` for testing).

Here's the comand-line recipe to import every Rhode Island location to our staging server:

    python -m importers.vaccinefinder \
        ../raw-feed-data/vaccine-finder/RI/locations \
        --url 'https://vial-staging.calltheshots.us/api/importLocations' \
        --token '1:e6c5e05637fdb6718d0c40efb3dfc98f' \
        --derive-counties

## importers.oregon_tableau_annotated

For this file: https://github.com/vaccine-feeds/raw-feed-data/blob/main/tableau/oregon.health.authority.covid.19/admin_site_and_county_map_site_no_info_with_places_data.json

Run like so:

    python -i -m importers.oregon_tableau_annotated \
        admin_site_and_county_map_site_no_info_with_places_data.json \
        --token 'xxx' --url 'http://0.0.0.0:3000/api/importLocations'

Leave off the `--url` argument to defalt to sending production.
