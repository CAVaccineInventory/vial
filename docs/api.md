# API documentation

The goal is to update this documentation as part of any commit that modifies how the API works in any way.
  
The base URL for every API is https://vial-staging.calltheshots.us/

## VIAL admin utilities

### GET /admin/edit-location/&lt;public_id&gt;/

Not a JSON API, but this is a convenient way to link to the edit page for a specific location. You can contruct this URL with the public ID of the location and VIAL will redirect the authenticated user to the corresponding edit interface for that location.

## Search APIs

### GET /api/searchLocations

Search all of our locations, excluding those that have been soft-deleted.

Optional query string parameters:

- `q=` - a term to search for in the `name` field
- `size=` - the number of results to return, up to 1000
- `format=` - the output format, see below.
- `state=` - a state code such as `CA` or `OR`
- `id=` - a public ID for one of our locations, can be passed multiple times to retrieve multiple locations at once by their IDs
- `idref=` - one or more concordance identifiers, e.g. `google_places:ChIJsb3xzpJNg4ARVC7_9DDwJnU` - will return results that match any of those identifiers
- `all=1` - use with caution: this causes EVERY result to be efficiently streamed back to you. Used without any other parameters this can return every location in our database!
- `latitude=&longitude=&radius=` - return results within `radius` meters of the point defined by `latitude` and `longitude`

The following output formats are supported:

- `json` - the default. [Example JSON](https://vial-staging.calltheshots.us/api/searchLocations?q=walgreens&format=json)
- `geojson` - a GeoJSON Feature Collection. [Example GeoJSON](https://vial-staging.calltheshots.us/api/searchLocations?q=walgreens&format=geojson)
- `nlgeojson` - Newline-delimited GeoJSON. [Example nl-GeoJSON](https://vial-staging.calltheshots.us/api/searchLocations?q=walgreens&format=nlgeojson)
- `map` - a basic Leaflet map that renders that GeoJSON. [Example map](https://vial-staging.calltheshots.us/api/searchLocations?q=walgreens&format=map)

You can also add `debug=1` to the JSON output to wrap them in an HTML page. This is primarily useful in development as it enables the Django Debug Toolbar for those results.

### GET /api/searchSourceLocations

Source locations are "raw" location data that has been imported into VIAL by one of our data ingestion flows. We do not expose these to end-users - we instead use them as part of our internal processes for identifying new vaccination sources and turning those into public locations.

Optional query string parameters:

- `q=` - a term to search for in the `name` field.
- `size=` - the number of results to return, up to 1000.
- `id=` - an ID for one of our source location records, can be passed multiple times. This accepts both numeric database IDs and `source_uid` values.
- `source_name=` - a source name, e.g. `vaccinespotter_org`. Can be specified multiple times.
- `state=` - a state, e.g. `MN`.
- `location_id=` - a public ID for one of our locations - this will return any source locations that have been marked as matching that location.
- `idref=` - one or more concordance identifiers, e.g. `google_places:ChIJsb3xzpJNg4ARVC7_9DDwJnU` - will return results that match any of those identifiers.
- `all=1` - use with caution: this causes EVERY result to be efficiently streamed back to you. Used without any other parameters this can return every source location in our database!
- `unmatched=1` - returns only source locations that have not yet been matched with a location.
- `matched=1` - returns only source locations that HAVE been matched with a location.
- `haspoint=1` - only return locations that have a latitude and longitude
- `random=1` - return results in a random order.
- `latitude=&longitude=&radius=` - return results within `radius` meters of the point defined by `latitude` and `longitude`
- `format=` - same options as `/api/searchLocations`: `json`, `geojson`, `nlgeojson`, `map`.

As with `/api/searchLocations` you can add `debug=1` to the URL if you are working with the Django Debug Toolbar.

Some examples:

- https://vial-staging.calltheshots.us/api/searchSourceLocations
- https://vial-staging.calltheshots.us/api/searchSourceLocations?state=MN
- https://vial-staging.calltheshots.us/api/searchSourceLocations?q=walgreens
- https://vial-staging.calltheshots.us/api/searchSourceLocations?unmatched=1
- https://vial-staging.calltheshots.us/api/searchSourceLocations?unmatched=1&random=1

## APIs used by our Scooby caller app

### POST /api/submitReport
  
This API records a new "report" in our database. A report is when someone checks with a vaccination location - usually by calling them - to find out their current status.
  
You call this API by HTTP POST, sending JSON as the POST body. A valid Auth0 JWT should be included in a `Authorization: Bearer JWT-GOES-HERE` HTTP header.

The JSON document should have the following keys:

* **Location** (required): the ID of one of our locations, e.g. `recaQlVkkI1rNarvx`
* **Appointment scheduling instructions**: a free text field of scheduling instructions.
* **Appointments by phone?**: a true or false boolean
* **Availability** (required): a list of availability tags, see below
* **Notes**: A free text field of public notes
* **Internal Notes**: A free text field of private, internal notes
* **Do not call until**: An ISO 8601-formatted timestamp, before which this location should not be called again

Optional fields:

* **is_pending_review**: Optional boolean - set this to `true` to specify that this report should be reviewed by our QA team
* **restriction_notes**: Optional string describing any specific restrictions
* **vaccines_offered**: Optional array of vaccines. Valid options are one or more of `"Moderna"`, `"Pfizer"`, `"Johnson & Johnson"`, `"Other"`
* **website**: Optional string for updating the website (``web`` is accepted for this key too)
* **full_address**: Optional string for updating the address (``address`` is accepted too)
* **hours**: Optional string for updating the hours information
* **planned_closure**: Optional `yyyy-mm-dd` date detailing the planned closure date for this site

Here is an example submission:
```json
{
    "Location": "recgDrq7aQMo0M5x7",
    "Appointment scheduling instructions": "www.walgreens.com",
    "Availability": [
        "Yes: vaccinating 65+",
        "Yes: appointment required",
        "Vaccinating essential workers"
    ],
    "Notes": "Check the Walgreens site regularly to see when appointments open up.",
    "Internal Notes": ""
}
```
#### Availability tags

For backwards compatibility with the existing application, there is some degree of flexibility in accepting availability tags.

Ideally you would use the slug for a tag, for example `only_staff` for only vaccinating staff.

You can alternatively use the tag's full name, or one of the names contained in the "previous names" array.

A list of valid tags with their slugs, names and previous_names can be found at https://vial-staging.calltheshots.us/api/availabilityTags

#### Skip requests

If a `Do not call until` timestamp is provided _and_ one of the availability tags is "Call back later"/"Skip: call back later",
a new call request is enqueued with a vesting time equal to the `Do not call until` timestamp.
This handles reports like "Closed until Monday" while making sure that we don't drop the request.

An example of one of these requests:
```json
{
  "Location": "rec5RXyYpi7IHQ2eN",
  "Availability":["Skip: call back later"],
  "Notes": "Feb 21: This location does not currently have vaccine available but may get stock in the coming weeks.", 
  "Internal Notes": "Feb 21: The pharmacy tech transferred me to the \"dispensing pharmacy\" as the best place to get questions answered.", 
  "Do not call until": "2021-03-07T18:35:03.742Z"
}
```

#### Return value

The API returns an indication that the record has been created, including the newly created record's public ID.

```json
{
    "created": ["rec234252"]
}
```
It currently returns other debugging data (as exposed in the API explorer) but you should ignore this - it's there for debugging and is likely to be removed soon.

#### Debug mode

A tool for exercising this API is available at https://vial-staging.calltheshots.us/api/submitReport/debug - if you have previously signed into the tool at https://vial-staging.calltheshots.us/ the interface will be pre-populated with a valid JWT token. If that token has expired you can get a new one by signing in and out again.

### POST /api/requestCall

Request a new location to call. This record will pick the request from the call queue with the highest priority and "lock" that record for twenty minutes, assigning it to your authenticated user.

HTTP POST, sending an empty `{}` JSON object as the POST body. A valid Auth0 JWT should be included in a `Authorization: Bearer JWT-GOES-HERE` HTTP header.

You can customize the results returned by this API by passing querystring parameters:

- `location_id` - pass a public location ID (like `reczHoKmlWd3XiI63` or `ldfzg`) to force VIAL to return that specific location
- `state` - the two-letter capitalized abbreviation for a state that you would like a call request for. If you do not provide this `CA` will be used as the default. You can pass `all` to specify calls from any states.
- `no_claim` - set this to `1` to avoid locking this call request for twenty minutes. Useful for testing.

These are querystring parameters, so you should `POST` to `/api/requestCall?state=OR` while still sending an empty `{}` JSON object as the POST body.

The response from this API currently looks like this:

```json

    "id": "lcyzg",
    "Name": "Fred Meyer Pharmacy #70100165",
    "Phone number": "(541) 884-1780",
    "Address": "2655 Shasta Way, Klamath Falls, OR, 97603",
    "Internal notes": null,
    "Hours": null,
    "County": "Klamath",
    "Location Type": "Unknown",
    "Affiliation": null,
    "Latest report": null,
    "Latest report notes": [
        null
    ],
    "County vaccine info URL": [
        null
    ],
    "County Vaccine locations URL": [
        null
    ],
    "Latest Internal Notes": [
        null
    ],
    "Availability Info": [],
    "Number of Reports": 0,
    "county_record": {
        "id": 2225,
        "County": "Klamath",
        "Vaccine info URL": null,
        "Vaccine locations URL": null,
        "Notes": null
    },
    "provider_record": {}
}
```

Try this API: https://vial-staging.calltheshots.us/api/requestCall/debug

### GET /api/verifyToken

Private API for testing our own API tokens (not the JWTs). Send an API key as the `Authorization: Bearer API-KEY-GOES-HERE` HTTP header.

Returns status 302 and an `{"error": "message"}` if the API key is invalid, otherwise returns:

```json
{
    "key_id": 1,
    "description": "Description of the key",
    "last_seen_at": "2021-03-10T01:43:32.010Z"
}
```

### POST /api/callerStats

Returns stats for the authenticated user.

HTTP POST, sending an empty `{}` JSON object as the POST body. A valid Auth0 JWT should be included in a `Authorization: Bearer JWT-GOES-HERE` HTTP header.

You can use `GET` here too.

The response currently looks like this:

```json
{
  "total": 23,
  "today": 3
}
```

Try this API: https://vial-staging.calltheshots.us/api/callerStats/debug

## APIs used for getting data into VIAL

### POST /api/startImportRun

POST an empty body to this at the beginning of a source location import run to get an import ID, needed for the calls to `/api/importSourceLocations` in order to tie everything together.

Returns the following JSON:

```json
{
    "import_run_id": 2
}
```

Try it: https://vial-staging.calltheshots.us/api/startImportRun/debug


### POST /api/importSourceLocations?import_run_id=X

POST this a newline-delimited list of JSON objects. The `?import_run_id` parameter must be the ID of an import run you have previously created using `POST /api/startImportRun`.

Each newline-delimited JSON object should have the following shape:

- `source_uid` - the ID within that other source, UUID etc or whatever they have - it’s globally unique and it includes a prefix (a copy of the source_name)
- `source_name` - text name of the source (e.g. `vaccinespotter`)
- `name` - optional name of the location
- `latitude` - optional latitude
- `longitude` - optional longitude
- `import_json` - the big bag of JSON (required)

Returns a 400 error on errors, a 200 on success.

Try it: https://vial-staging.calltheshots.us/api/importSourceLocations/debug

### POST /api/importLocations

Private API for us to import new locations into the database - or update existing locations.

Accepts a POST with a JSON document with either a single location object or a list of location objects.

You'll need an API key, which you pass in the `Authorization: Bearer API-KEY-GOES-HERE` HTTP header. API keys can be created in the Django admin at https://vial-staging.calltheshots.us/admin/api/apikey/

Each location should look like this:

```json
{
    "name": "Walgreens San Francisco III",
    "state": "CA",
    "latitude": 37.781869,
    "longitude": -122.439517,
    "location_type": "Pharmacy",
}
```
Each of these fields is required.

The `state` value should be the two letter acronym for a state (or `AS` for American Samoa, `GU` for Guam, `MP` for Northern Mariana Islands, `PR` for Puerto Rico, `VI` for Virgin Islands or `DC` for District of Columbia).

The latitude and longitude should be floating point values.

The `location_type` should be one of the values shown on https://vial-staging.calltheshots.us/api/locationTypes

There is also an optional `import_ref` key, described below.

The API returns the following:

```json
{
    "errors": [],
    "added": ["lc", "ld"],
    "updated": ["lb"],
}
```

- `errors` will contain a list of validation errors, if any.
- `added` returns the public IDs of any added locations.
- `updated` returns the public IDs of locatinos that were updated using an `import_ref`.

The following input fields are all optional strings:

- `phone_number`
- `full_address`
- `city`
- `county` - special case, see below
- `google_places_id`
- `vaccinespotter_location_id`
- `vaccinefinder_location_id`
- `zip_code`
- `hours`
- `website`
- `airtable_id`
- `import_json` - dictionary

If you are providing a `county` it must be the name of a county that exists within the provided state.

You can also specify a `provider_name` and a `provider_type`, if the location belongs to a chain of locations.

The `provider_type` must be one of the list of types from [/api/providerTypes](https://vial-staging.calltheshots.us/api/providerTypes).

The `provider_name` will be used to either create a new provider or associate your location with an existing provider with that name.

If you provide the `import_json` dictionary it should be the original, raw JSON data that your importer script is working against. This will be stored in the `import_json` column in the locations table, and can later be used for debugging purposes.

#### Using import_ref to import and later update locations

If you are importing locations from another source that may provide updated data in the future, you can use the `import_ref` key to specify a unique import reference for the record.

If you call `/api/importLocations` again in the future with the same `import_ref` value, the record will be updated in place rather than a new location being created.

For example, submitting the following:

```json
{
    "name": "Walgreens San Francisco III",
    "state": "CA",
    "latitude": 37.781869,
    "longitude": -122.439517,
    "location_type": "Pharmacy",
    "import_ref": "walgreens-scraper:1231"
}
```
Will assign an `import_ref` of `walgreens-scraper:1231` to the record. If you later submit the following:

```json
{
    "name": "Walgreens San Francisco",
    "state": "CA",
    "latitude": 37.781869,
    "longitude": -122.439517,
    "location_type": "Super Site",
    "import_ref": "walgreens-scraper:1231"
}
```
The existing record will be updated with those altered values.

Make sure you pick import refs that won't be used by anyone else: using a prefix that matches the location you are pulling from is a good idea.

Try this API: https://vial-staging.calltheshots.us/api/importLocations/debug

### POST /api/updateLocations

This API can be used to update fields on one or more locations. The POSTed JSON looks like this:

```json
{
  "update": {
    "$location_id": {
      "$field1": "new_value",
      "$field2": "new_value",
      "$field3": "..."
    }
  },
  "revision_comment": "Optional comment"
}
```

In the above example, `$location_id` is the public location ID - a string such as `rec9Zc6A08cEWyNpR` or `lgzgq`.

This is a bulk API, so you can provide multiple nested location ID dictionaries.

Only the fields that you provide will be updated on the record - so unlike `/api/importLocations` with an `import_ref` this API allows partial updates of just specified fields.

The following example will set a new name on location `rec9Zc6A08cEWyNpR` and a new phone number on location `lgzgq`. It will also set a custom revision message (visible in the object history) of `"New details"`.

```json
{
  "update": {
    "rec9Zc6A08cEWyNpR": {
      "name": "Berkeley Clinic II"
    },
    "lgzgq": {
      "phone_number": "(555) 555-5551"
    }
  },
  "revision_comment": "New details"
}
```
The `"revision_comment"` key can be ommitted entirely, in which a default comment of `"/api/updateLocations by API_KEY"` will be used.

The following fields can be updated using this API. All are optional.

- `name` - string
- `state` - e.g. `CA`
- `latitude` - floating point
- `longitude` - floating point
- `location_type` - string, one of [these](https://vial-staging.calltheshots.us/api/locationTypes)
- `phone_number` - string
- `full_address` - string
- `city` - string
- `county` - string, must be the name of a county in the specified state
- `google_places_id` - string
- `vaccinefinder_location_id` - string
- `vaccinespotter_location_id` - string
- `zip_code` - string
- `hours` - string
- `website` - string
- `preferred_contact_method` - string, one of `research_online` or `outbound_call`
- `provider_type` - one of the types from [/api/providerTypes](https://vial-staging.calltheshots.us/api/providerTypes)
- `provider_name` - the name of the provider

Try this API: https://vial-staging.calltheshots.us/api/updateLocations/debug

### POST /api/updateLocationConcordances

Bulk API for adding and removing concordances (IDs from other systems) to our locations.

The API is similar to `/api/updateLocations`. The input looks like this:

```json
{
  "update": {
    "$location_id": {
      "add": [
        "$authority:$identifier"
      ]
    }
  }
}
```
To add a Google Places ID of `ChIJsb3xzpJNg4ARVC7_9DDwJnU` to the location with ID `recfwh2p1fNN7TN4C` you would send this:
```json
{
  "update": {
    "recfwh2p1fNN7TN4C": {
      "add": [
        "google_places:ChIJsb3xzpJNg4ARVC7_9DDwJnU"
      ]
    }
  }
}
```
Note that the concordance ID references used here are always `authority:identifier` - where the authority is something like `google_places` or `vaccinespotter` or `vaccinefinder`.

A full list of authorities currently in use can be found on the [concordance identifier listing page](https://vial-staging.calltheshots.us/admin/core/concordanceidentifier/).

To remove a concordance identifier, use `"remove"` instead of `"add"`:
```json
{
  "update": {
    "recfwh2p1fNN7TN4C": {
      "remove": [
        "google_places:ChIJsb3xzpJNg4ARVC7_9DDwJnU"
      ]
    }
  }
}
```
You can pass multiple ID references to both the `"add"` and the `"remove"` action. You can send multiple location IDs to the endpoint at once.

Try this API: https://vial-staging.calltheshots.us/api/updateLocationConcordances/debug

### POST /api/updateSourceLocationMatch

API for updating a specifiec source location to mark it as being a confirmed match for a specific location. This modifies the `source_location` table to update the `matched_location_id` column, and records a history record with the old and new values in the `source_location_match_history` table.

Accepts either an API key or a JWT token for authentication.

POST the following JSON:

```json
{
  "source_location": "vaccinespotter_org:206891330",
  "location": "lxyz"
}
```

- `source_location` should be a `source_uid`, but can alternatively be an internal database integer ID
- `location` should be a public location identifier, but can also be an internal location database integer ID

Returns the following:

```json
{
  "matched": {
    "location": {
      "id": "lxx",
      "name": "Location 1"
    },
    "source_location": {
      "source_uid": "test:1",
      "name": "Test location"
    }
  }
}
```

Try this API: https://vial-staging.calltheshots.us/api/updateSourceLocationMatch/debug

### POST /api/createLocationFromSourceLocation

Creates a new location record from an available source location, provided that source location has not yet been marked as matching an existing location.

Accepts either an API key or a JWT token for authentication.

POST the following JSON:

```json
{
  "source_location": "vaccinespotter_org:206891330",
}
```

`source_location` should be a `source_uid`, but can alternatively be an internal database integer ID

Returns the following:

```json
{
  "location": {
    "id": "lxx",
    "name": "Location 1",
    "vial_url": "https://vial-staging.calltheshots.us/admin/core/location/1234/change/"
  }
}
```

Try this API: https://vial-staging.calltheshots.us/api/createLocationFromSourceLocation/debug

### POST /api/importReports

Private API for us to import old reports from Airtable into the VIAL database.

Accepts a JSON array of items from the [airtable-data-backup/backups/Reports.json](https://github.com/CAVaccineInventory/airtable-data-backup/blob/main/backups/Reports.json) file.

Try this API: https://vial-staging.calltheshots.us/api/importReports/debug

## Miscellaneous read-only data APIs

### GET /api/location/PUBLIC_ID/concordances

Retrieve the concordances (external identifiers) for a specific location.

Example output:
```json
{
    "concordances": [
        "google_places:ChIJh1Vp2AhS2YAReWQls7L8uKY",
        "vaccinespotter:798382",
        "vaccinefinder:bdae81b3-d682-405a-b66e-50052e4a140a"
    ]
}
```
Try this API: https://vial-staging.calltheshots.us/api/location/rec1wYYRF8RLX9B9y/concordances

### GET /api/providerTypes

Unauthenticated. Returns a `"provider_types"` key containing a JSON array of names of valid provider types, e.g. `Pharmacy`.

Example output:

```json
{
    "provider_types": [
        "Pharmacy",
        "Hospital",
        "Health Plan",
        "Other"
    ]
}
```

Try this API: https://vial-staging.calltheshots.us/api/providerTypes

### GET /api/locationTypes

Unauthenticated. Returns a `"location_types"` key containing a JSON array of names of valid location types, e.g. `Pharmacy`.

Example output:

```json
{
    "location_types": [
        "Hospital / Clinic",
        "Pharmacy",
        "Super Site",
        "Private Practice",
        "School",
        "Other",
        "Nursing home",
        "Urgent care",
        "Dialysis clinic",
        "Health department",
        "Santa Barbara County Juvenile Hall",
        "Mobile clinic",
        "Specialist",
        "Ambulance",
        "In-home Senior Care",
        "Mental Health",
        "Rehabilitation Center",
        "First Responder",
        "Shelter",
        "Unknown"
    ]
}
```

Try this API: https://vial-staging.calltheshots.us/api/locationTypes

### GET /api/availabilityTags

Unauthenticated. Returns a `"availability_tags"` key containing a JSON array of availability tags.

Example output:

```json
{
  "availability_tags": [
    {
      "slug": "only_staff",
      "name": "Only vaccinating staff",
      "group": "no",
      "notes": "This location is currently only vaccinating their own staff",
      "previous_names": [
        "No: only vaccinating staff"
      ]
    },
    {
      "slug": "not_open_to_the_public",
      "name": "Not open to the public",
      "group": "no",
      "notes": "This location is currently not open to the public",
      "previous_names": [
        "No: not open to the public"
      ]
    },
    {
      "slug": "only_health_care_workers",
      "name": "Only vaccinating health care workers",
      "group": "no",
      "notes": "This location is currently only vaccinating healthcare workers",
      "previous_names": [
        "No: only vaccinating health care workers"
      ]
    }
  ]
}
```

Try this API: https://vial-staging.calltheshots.us/api/availabilityTags

### GET /api/counties/&lt;state&gt;

Unauthenticated. Returns a list of counties for the two-letter state code.

```json
{
  "state_name": "Rhode Island",
  "state_abbreviation": "RI",
  "state_fips_code": "44",
  "counties": [
    {
      "county_name": "Bristol",
      "county_fips_code": "44001"
    },
    {
      "county_name": "Kent",
      "county_fips_code": "44003"
    },
    {
      "county_name": "Newport",
      "county_fips_code": "44005"
    },
    {
      "county_name": "Providence",
      "county_fips_code": "44007"
    },
    {
      "county_name": "Washington",
      "county_fips_code": "44009"
    }
  ]
}
```

Examples:

- https://vial-staging.calltheshots.us/api/counties/CA
- https://vial-staging.calltheshots.us/api/counties/OR
- https://vial-staging.calltheshots.us/api/counties/RI

## APIs for exporting data

### POST /api/exportMapbox

Uploads the location JSON to Mapbox.

### GET /api/exportMapboxPreview

Preview the JSON that we generate for Mapbox. This returns 20 recent locations by default, or use one or more `?id=public_id` parameters to see specific locations.

- https://vial-staging.calltheshots.us/api/exportMapboxPreview
- https://vial-staging.calltheshots.us/api/exportMapboxPreview?id=recgP5RSXunz1yrwm

### GET /api/exportPreview/Locations.json

Debugging endpoint showing a preview of the `Locations.json` feed generated by VIAL.

Defaults to returning 10 locations. You can also feed it multiple `?id=recxxx` public location IDs to see those specific location representations.

Try it: https://vial-staging.calltheshots.us/api/exportPreview/Locations.json

### GET /api/exportPreview/Providers.json

Debugging endpoint showing a preview of the `Providers.json` feed generated by VIAL.

Defaults to returning 10 providers. You can also feed it multiple `?id=recxxx` public location IDs to see those specific provider representations.

Try it: https://vial-staging.calltheshots.us/api/exportPreview/Providers.json
