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

A tool for trying out this API is available at https://vaccinateca-preview.herokuapp.com/api/submitReport/debug - if you have previously signed into the tool at https://vaccinateca-preview.herokuapp.com/ the interface will be pre-populated with a valid JWT token. If that token has expired you can get a new one by signing in and out again.

Anything submitted using that tool will have `is_test_data` set to True in the database.

You can view test reports here: https://vaccinateca-preview.herokuapp.com/admin/core/report/?is_test_data__exact=1

## /api/requestCall

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
