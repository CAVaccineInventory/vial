# API documentation

The goal is to update this documentation as part of any commit that modifies how the API works in any way.
  
The base URL for every API is currently https://vaccinateca-preview.herokuapp.com/
  
## /api/submitReport
  
This API records a new "report" in our database. A report is when someone checks with a vaccination location - usually by calling them - to find out their current status.
  
You call this API by HTTP POST, sending JSON as the POST body. A valid Auth0 JWT should be included in a `Authorization: Bearer JWT-GOES-HERE` HTTP header.

The JSON document have the following keys:

* **Location** (required): the ID of one of our locations, e.g. `recaQlVkkI1rNarvx`
* **Appointment scheduling instructions**: a free text field of scheduling instructions.
* **Appointments by phone?**: a true or false boolean
* **Availability** (required): a list of availability tags, see below
* **Notes**: A free text field of public notes
* **Internal Notes**: A free text field of private, internal notes

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

For backwards compatibility with the existing application, there is some degree of flexibility in accepting availability tags. Our database at https://vaccinateca-preview.herokuapp.com/admin/core/availabilitytag/ lists the current tags, but each tag also has "previous names" which can be used instead.

Valid tags right now are:

- "Only vaccinating staff" - also known as: "No: only vaccinating staff"
- "Not open to the public" - also known as: "No: not open to the public"
- "Only vaccinating health care workers" - also known as: "No: only vaccinating health care workers"
- "No vaccine inventory" - also known as: "No: no vaccine inventory"
- "Incorrect contact information" - also known as: "No: incorrect contact information"
- "Location permanently closed" - also known as: "No: location permanently closed"
- "Will never be a vaccination site" - also known as: "No: will never be a vaccination site"
- "Walk-ins accepted" - also known as: "Yes: walk-ins accepted"
- "Appointment required" - also known as: "Yes: appointment required"
- "Vaccinating 65+" - also known as: "Yes: vaccinating 65+"
- "Vaccinating 70+" - also known as: "Yes: vaccinating 70+"
- "Vaccinating 75+" - also known as: "Yes: vaccinating 75+"
- "Vaccinating 80+" - also known as: "Yes: vaccinating 80+"
- "Vaccinating 85+" - also known as: "Yes: vaccinating 85+"
- "Restricted to county residents" - also known as: "Yes: restricted to county residents"
- "Must be a current patient" - also known as: "Yes: must be a current patient"
- "Must be a veteran" - also known as: "Yes: must be a veteran"
- "Appointment calendar currently full" - also known as: "Yes: appointment calendar currently full"
- "Coming soon" - also known as: "Yes: coming soon"
- "Call back later" - also known as: "Skip: call back later"
- "May be a vaccination site in the future" - also known as: "No: may be a vaccination site in the future"
- "Vaccinating essential workers" - also known as: "Yes: Vaccinating essential workers"
- "Restricted to city residents" - also known as: "Yes: restricted to city residents"
- "Scheduling second dose only" - also known as: "Yes: Scheduling second dose only"
- "Vaccinating 50+" - also known as: "Yes: vaccinating 50+"

### Return value

The API returns an indication that the record has been created, including the newly created record's public ID.

```json
{
    "created": ["rec234252"]
}
```
It currently returns other debugging data (as exposed in the API explorer) but you should ignore this - it's there for debugging and is likely to be removed soon.

### Debug mode

A tool for trying out this API is available at https://vaccinateca-preview.herokuapp.com/api/submitReport/debug - if you have previously signed into the tool at https://vaccinateca-preview.herokuapp.com/ the interface will be pre-populated with a valid JWT token. If that token has expired you can get a new one by signing in and out again.

Anything submitted using that tool will have `is_test_data` set to True in the database.

You can view test reports here: https://vaccinateca-preview.herokuapp.com/admin/core/report/?is_test_data__exact=1

## api/submitAvailabilityReport

This endpoint records an availability report for a location, which generally includes a list of known appointment windows.
It will usually be used by an automated script.

This API endpoint is called with an HTTP post, with JSON in teh POST body.
The `SCRAPER_API_KEY` should be sent in the header as `Authorization: Bearer <SCRAPER_API_KEY>`.

The JSON document must have the following keys:
- `feed_update`: an object with three keys: `uuid`, `github_url`, and `feed_provider`.
  This should be the same for all reports submitted in a single session (e.g., as a result of a single feed update or scrape).
  The `uuid` should be generated by the client (e.g., using Python's `uuid.uuid4()` method).
  The `github_url` is a URL to our repository on GitHub where the raw data can be inspected.
  The `feed_provider` is a slug that uniquely refers to this particular data source (e.g., `curative` for Curative's JSON feed).
  Provider slugs are available in the `Feed provider` table.
- `location`. This is a unique identifier to the location _used by this feed provider_.
  It is not the `public_id` of the location.
  A pre-submitted concordance is used to map this to a location in our database.
- `availability_windows` is a list of objects, each of which has the fields  `starts_at`, `ends_at`, `slots`, and `additional_restrictions`.
  The `starts_at` and `ends_at` fields are timestamps that indicate the bounds of this window.
  The `slots` field indicates the number of currently available slots in this window.
  The `additional_restrictions` field is a list of availability tags, using their slugs (see above).
  
Optionally, the JSON document may include a `feed_json` key, with a value consisting of the raw JSON (e.g., from a provider's API)
used to inform the availability report _for this location_.

For example:
```json
{
  "feed_update": {
    "uuid": "02d63a35-5dbc-4ac8-affb-14603bf6eb2e",
    "github_url": "https://example.com",
    "feed_provider": "test_provider"
  },
  "location": "116",
  "availability_windows": [
    {
      "starts_at": "2021-02-28T10:00:00Z",
      "ends_at": "2021-02-28T11:00:00Z",
      "slots": 25,
      "additional_restrictions": []
    },
    {
      "starts_at": "2021-02-28T11:00:00Z",
      "ends_at": "2021-02-28T12:00:00Z",
      "slots": 18,
      "additional_restrictions": [
        "vaccinating_65_plus"
      ]
    }
  ]
}
```

If the request was successful, it returns a 201 Created HTTP response.

A common reason for an unsuccessful request is the lack of concordance between the provider's location ID and our known
locations. In general, an automated process should find and flag new locations in each scrape before publshing availability.
