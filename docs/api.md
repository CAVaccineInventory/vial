# API documentation

The goal is to update this documentation as part of any commit that modifies how the API works in any way.
  
The base URL for every API is https://vial.calltheshots.us/
  
## POST /api/submitReport
  
This API records a new "report" in our database. A report is when someone checks with a vaccination location - usually by calling them - to find out their current status.
  
You call this API by HTTP POST, sending JSON as the POST body. A valid Auth0 JWT should be included in a `Authorization: Bearer JWT-GOES-HERE` HTTP header.

The JSON document have the following keys:

* **Location** (required): the ID of one of our locations, e.g. `recaQlVkkI1rNarvx`
* **Appointment scheduling instructions**: a free text field of scheduling instructions.
* **Appointments by phone?**: a true or false boolean
* **Availability** (required): a list of availability tags, see below
* **Notes**: A free text field of public notes
* **Internal Notes**: A free text field of private, internal notes
* **Do not call until**: An ISO 8601-formatted timestamp, before which this location should not be called again

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
### Availability tags

For backwards compatibility with the existing application, there is some degree of flexibility in accepting availability tags.

Ideally you would use the slug for a tag, for example `only_staff` for only vaccinating staff.

You can alternatively use the tag's full name, or one of the names contained in the "previous names" array.

A list of valid tags with their slugs, names and previous_names can be found at https://vial.calltheshots.us/api/availabilityTags

### Skip requests

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

### Return value

The API returns an indication that the record has been created, including the newly created record's public ID.

```json
{
    "created": ["rec234252"]
}
```
It currently returns other debugging data (as exposed in the API explorer) but you should ignore this - it's there for debugging and is likely to be removed soon.

### Debug mode

A tool for trying out this API is available at https://vial.calltheshots.us/api/submitReport/debug - if you have previously signed into the tool at https://vial.calltheshots.us/ the interface will be pre-populated with a valid JWT token. If that token has expired you can get a new one by signing in and out again.

Anything submitted using that tool will have `is_test_data` set to True in the database.

You can view test reports here: https://vial.calltheshots.us/admin/core/report/?is_test_data__exact=1

## POST /api/requestCall

Request a new location to call. This record will pick a location from the upcoming call queue and "lock" that record for twenty minutes, assigning it to your authenticated user.

HTTP POST, sending an empty `{}` JSON object as the POST body. A valid Auth0 JWT should be included in a `Authorization: Bearer JWT-GOES-HERE` HTTP header.

The response currently looks like this:

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

## GET /api/verifyToken

Private API for testing our own API tokens (not the JWTs). Send an API key as the `Authorization: Bearer API-KEY-GOES-HERE` HTTP header.

Returns status 302 and an `{"error": "message"}` if the API key is invalid, otherwise returns:

```json
{
    "key_id": 1,
    "description": "Description of the key",
    "last_seen_at": "2021-03-10T01:43:32.010Z"
}
```

## POST /api/importLocations

Private API for us to import new locations into the database - or update existing locations.

Accepts a POST with a JSON document with either a single location object or a list of location objects.

You'll need an API key, which you pass in the `Authorization: Bearer API-KEY-GOES-HERE` HTTP header. API keys can be created in the Django admin at https://vial.calltheshots.us/admin/api/apikey/

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

The `location_type` should be one of the values shown on https://vial.calltheshots.us/api/locationTypes

There is also an optional `import_ref` key, described below.

The API returns the following:

```json
{
    "errors": [],
    "added": ["lc", "ld"],
    "updated": ["lb"],
}
```

`errors` will contain a list of validation errors, if any.

`added` returns the public IDs of any added locations.

`updated` returns the public IDs of locatinos that were updated using an `import_ref`.

### Using import_ref to import and later update locations

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

The following fields are all optional strings:

- `phone_number`
- `full_address`
- `city`
- `county` - special case, see below
- `google_places_id`
- `zip_code`
- `hours`
- `website`
- `airtable_id`
- `import_json` - dictionary

If you are providing a `county` it must be the name of a county that exists within the provided state.

You can also specify a `provider_name` and a `provider_type`, if the location belongs to a chain of locations.

The `provider_type` must be one of the list of types from `/api/providerTypes`.

The `provider_name` will be used to either create a new provider or associate your location with an existing provider with that name.

If you provide the `import_json` dictionary it should be the original, raw JSON data that your importer script is working against. This will be stored in the `import_json` column in the locations table, and can later be used for debugging purposes.

## GET /api/providerTypes

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

## GET /api/locationTypes

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

## GET /api/availabilityTags

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

## GET /api/counties/&lt;state&gt;

Unauthenticated. Returns a list of counties for the two-letter state code. For example: https://vial.calltheshots.us/api/counties/RI

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
