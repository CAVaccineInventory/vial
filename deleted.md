# Deleted code

An index of code that we have deleted from this project, to make it easy to refer back to should we ever need to.

## importers - deleted May 11th 2011

Prior to the creation of the [vaccine-feed-ingest](https://github.com/CAVaccineInventory/vaccine-feed-ingest) repo the `importers/` folder in VIAL included standalone Python scripts for importing data into VIAL by calling the `/api/importLocations` endpoint.

This included the code for copying across data from our Airtable instance.

Importer scripts: https://github.com/CAVaccineInventory/vial/tree/80ceac90a72e54731a169330a71c1f1bfa43e35a/importers

Importer documentation: https://github.com/CAVaccineInventory/vial/blob/80ceac90a72e54731a169330a71c1f1bfa43e35a/docs/importers.md

The `import_utils.py` module included a handy function for deriving the county for a location based on its latitude and longitude, using the https://us-counties.datasette.io/ API:

https://github.com/CAVaccineInventory/vial/blob/80ceac90a72e54731a169330a71c1f1bfa43e35a/importers/import_utils.py
