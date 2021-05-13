# VIAL

VIAL = Vaccine Information Archive and Library.

This is the Django application that powers https://help.vaccinateca.com/ and provides the backend data for https://www.vaccinateca.com/

Project background: [Spinning up a new Django app to act as a backend for VaccinateCA](https://github.com/CAVaccineInventory/simonw-internal-blog/blob/main/2021-02/2021-02-23.md)

## Where this is hosted

- https://vial.calltheshots.us/ is production - manually deployed using `scripts/deploy.sh`
- https://vial-staging.calltheshots.us/ is our Google Cloud Run staging server - code is automatically deployed there on every commit

## Auth0 user permissions

This app is built around the Django admin, but uses Auth0 for authentication.

User permissions are controlled using Auth0 roles. Users can be assigned these roles in the Auth0 interface at https://manage.auth0.com/dashboard/us/vaccinateca/roles

The following Auth0 roles grant access to VIAL, and place the user in a VIAL permissions group with the same name as the Auth0 role. The permissions assigned to those groups can be seen and edited in the VIAL groups interface, by users with the `VIAL super-user` role.

- Vaccinate CA Staff
- Reports QA
- VIAL data corrections
- VIAL super-user

Membership of these groups should be controlled entirely through Auth0 role assignments. If a VIAL super-user adds or removes someone from one of these groups using the VIAL interface that user will have their membership reset next time they sign into VIAL.

If you want to grant permissions to specific users within VIAL independent of their AUth0 roles you can do so by editing that user's list of permissions directly on the edit user page.

## Architectural principles for this app

- Write code (and issue comments and commit messages) with the expectation that the entire repository will be open to the public some day. So keep secrets out of the code, and don't be uncouth!
- As few moving parts as possible. Right now this means:
  - The app is written in Django
  - _All_ data is stored in PostgreSQL - even data that might be a better fit for a dedicated logging system or message queue. We'll adopt additional storage mechanisms only when PostgreSQL starts creaking at the seams.
- Django migrations are great. We use these enthusiastically, with a goal of making schema changes boring and common, not exciting and rare.

## API documentation

Comprehensive documentation for the VIAL web API is available in [docs/api.md](docs/api.md). This documentation should be updated in sync with changes made to the APIs - any time the documentation becomes out of sync with the implementation should be considered a bug and fixed ASAP!

This documentation is also included in VIAL deployments:

- https://vial.calltheshots.us/api/docs for production
- https://vial-staging.calltheshots.us/api/docs for staging (which is continually deployed from this repo so should reflect the most recent `main` branch)

## Setting up a development environment

If you run into issues during environment setup, start with the [FAQ][1] for troubleshooting.

_If you encounter any issues in setup, please document them and add them to the [FAQ][1]._

Check out the repository. Create a new Python virtual environment for it (I use `pipenv shell` to do this); we depend on Python 3.7 or later, and only test and deploy on Python 3.9.  Install the dependencies with `pip install -r requirements.txt`.

Set your environment variables, see _Configuration_ section below.

You'll need a PostgreSQL database called "vaccinate". On macOS I've used https://postgresapp.com/ for that.

Alternatively, you can use [Docker](docs/docker.md).

We use GeoDjango, so you'll need GDAL installed. If you run into trouble with this check out the [GeoDjango installation instructions](https://docs.djangoproject.com/en/3.2/ref/contrib/gis/install/).

You'll need to run `./manage.py` commands from the `vaccinate` directory, so `cd vaccinate`.

Then run the database migrations with `./manage.py migrate` - you'll need to run this command any time we release new migrations.

Run the development server using `./manage.py runserver 0.0.0.0:3000`

To enable the Django debug toolbar, run this instead:

    DEBUG=1 ./manage.py runserver 0.0.0.0:3000

Visit it at `http://localhost:3000/` - it's important to use `localhost:3000` as that is the URL that is allow-listed for logins by the Auth0 configuration. Click "sign in" and sign in with an Auth0 account.

Once you have signed in and created an account you should grant yourself super-user access so you can use every feature of the admin site. You can do that by running the following:

    cd vaccinate
    ./manage.py shell
    >>> from django.contrib.auth.models import User
    >>> User.objects.all().update(is_superuser=True, is_staff=True)
    >>> <Ctrl+D> to exit

You'll also neet to run this command once or your static assets will 404:

    ./manage.py collectstatic

To get the `/dashboard/` interface working in your local development environment you can run this:

    DASHBOARD_DATABASE_URL=postgres://localhost/vaccinate \
        ./manage.py runserver 0.0.0.0:3000

## Configuration

Running this requires some secrets in environment variables:

- `SOCIAL_AUTH_AUTH0_SECRET` should be set to
  `iqSZmWfTZeXMfmFCBp8Pmyb9ZaFOXHsJ69BxwslUYo4whUjVLwtthNUaMT1TWUDx`.
  (This secret is OK to include in this README because it is only used
  for local development)
- `DJANGO_SECRET_KEY` can be any random string. One way to generate
  one is via `python -c "import secrets; print(secrets.token_urlsafe())"`

Create a file like this named `.env`, which is loaded by Django:

    SOCIAL_AUTH_AUTH0_SECRET="iqSZmWfTZeXMfmFCBp8Pmyb9ZaFOXHsJ69BxwslUYo4whUjVLwtthNUaMT1TWUDx"
    DJANGO_SECRET_KEY="just a big random string"
    DJANGO_DEBUG=1

In development you will need to have a local PostgreSQL server running - I use PostgreSQL.app on my Mac for this. Alternatively, you can use [Docker][<docs/docker.md>]

Then create a database called `vaccinate` by running this in the terminal:

    createdb vaccinate

If your database has alternative connection details you can specify them using a `DATABASE_URL` environment variable of the format `postgres://USER:PASSWORD@HOST:PORT/NAME`. You can place this in the `.env` file.

## Importing sample data from live or staging

Two scripts are provided for importing data from our live or staging instances into your development environment, using the export and import APIs.

To use these scripts, you will need two API keys: one for your development environment (which you can create at http://0.0.0.0:3000/admin/api/apikey/) and one for the production or staging environment that you wish to import data from.

To import locations:
```bash
python scripts/dev_copy_locations.py \
   --source-token '17:ce619e0...' \
   --destination-token '4:09b190...' \
   --source-url 'https://vial.calltheshots.us/api/searchLocations?size=100'
```
Where `source-token` is the API key from production, and `destination-token` is your API key created for your local development environment.

You can pass different arguments in the query string for `--source-url` to retrieve different subsets of our data. If you wanted to import every location in Puerto Rico for example you could use:

```
   --source-url 'https://vial.calltheshots.us/api/searchLocations?state=PR&all=1'
```
Be careful with the `all=1` argument - used carelessly you could accidentally pull 60,000+ records into your local environment!

Source locations are raw, unprocessed location data gathered by our [vaccine-feed-ingest](https://github.com/CAVaccineInventory/vaccine-feed-ingest) mechanism.

You can import these in a similar way to locations, using this script:
```bash
python dev_copy_source_locations.py 
  --source-token '17:ce619e0...' \
  --destination-token '4:09b19...' \
  --destination-url 'https://vial.calltheshots.us/api/searchSourceLocations?state=RI&source_name=vaccinefinder_org'
```
This will import all of the source locations in Rhode Island that were originally imported from `vaccinefinder_org`.

## Running the tests

To run the tests, change directory to the `vaccinate` folder and run `pytest`.

## Code formatting and linting

This repository uses [Black](https://github.com/psf/black) and [isort](https://pycqa.github.io/isort/) to enforce coding style as part of the CI tests.

Run `black .` and `isort .` in the top-level directory to ensure your code is formatted correctly, then enjoy never having to think about how to best indent your Python code ever again.

Run `scripts/run-flake8` in the top-level directory to check for missing or unused imports.

Run `scripts/run-mypy` in the top-level directory to run the mypy type checker.

Run `scripts/lint-migrations` in the top-level directory to verify that migrations do not have any backwards-incompatible changes that could cause problems during a deploy while the site is serving traffic.

## Logging SQL

You can set the `DJANGO_DEBUG_LOG_ALL_SQL=1` environment variable to log all SQL executed by Django to the console. This can be useful for things like understanding how complex migrations work:

    DJANGO_DEBUG_LOG_ALL_SQL=1 ./manage.py migrate

[1]: docs/env-setup-faq.md

## Django SQL Dashboard

https://vial.calltheshots.us/dashboard/ and https://vial-staging.calltheshots.us/dashboard/ offer an interface for running read-only SQL queries against our database and bookmarking the results, using [Django SQL Dashboard](https://django-sql-dashboard.datasette.io/).

You can create saved dashboards at https://vial.calltheshots.us/admin/django_sql_dashboard/dashboard/ - these will then be available at URLs like https://vial.calltheshots.us/dashboard/closest-locations/

Only a specific list of tables are available through that interface. To make a new table available follow these instructions:

1. Make sure you're auth'd at the command line as someone who can connect to the database; you may need to bootstrap to a service account; the process there is:
   ```
   # Fetch a key
   gcloud iam service-accounts keys create ./staging-key.json --iam-account staging@django-vaccinateca.iam.gserviceaccount.com
   # Enable it:
   gcloud auth activate-service-account --key-file=./staging-key.json
   ```
2. [Download](https://cloud.google.com/sql/docs/mysql/connect-admin-proxy#install) and start the cloud SQL proxy:
   ```
   ./cloud_sql_proxy -instances=django-vaccinateca:us-west2:staging=tcp:5432
   ```
3. Look up [the `django-staging-env` secret in Secret Manager](https://console.cloud.google.com/security/secret-manager/secret/django-staging-env/versions?project=django-vaccinateca), click the triple-dots, and show the current value; pull out the secret for the `vaccinate` user from the `DATABASE_URL` line.
4. Connect with that password:
   ```
   psql -U vaccinate -h localhost -p 5432 vaccinate
   ```
5. Grant the rights:
   ```
   grant select on
     public.api_apikey,
     public.api_log
   to "read-only-core-tables";
   
   grant select on
     public.api_apikey,
     public.api_log
   to "datascience";
   ```

...then repeat that for production. The `read-only-core-tables` role is used by Django SQL Dashboard, and the `datascience` role is used by Mode.
