# vial

 The Django application powering calltheshots.us

Project background: [Spinning up a new Django app to act as a backend for VaccinateCA](https://github.com/CAVaccineInventory/simonw-internal-blog/blob/main/2021-02/2021-02-23.md)

## Where this is hosted

- https://vial.calltheshots.us/ is production - manually deployed using `scripts/deploy.sh`
- https://vial-staging.calltheshots.us/ is our Google Cloud Run staging server - code is automatically deployed there on every commit
- https://vaccinateca-preview.herokuapp.com/ is our Heroku staging server, soon to be retired - also uses continous deployment

## Architectural principles for this app

- Write code (and issue comments and commit messages) with the expectation that the entire repository will be open to the public some day. So keep secrets out of the code, and don't be uncouth!
- As few moving parts as possible. Right now this means:
  - The app is written in Django
  - _All_ data is stored in PostgreSQL - even data that might be a better fit for a dedicated logging system or message queue. We'll adopt additional storage mechanisms only when PostgreSQL starts creaking at the seams.
- Django migrations are great. We use these enthusiastically, with a goal of making schema changes boring and common, not exciting and rare.

As a result, hosting this (or moving this to a different host) should be as easy as setting up a Django app with an attached PostgreSQL database.

## What this does so far

- SSO using Auth0 to sign users in with a Django user account
- Run tests in GitHub Actions CI using pytest-django
- Enforce Black code style in GitHub Actions
- Django ORM models for the new schema currently under discussion
- Populates the state and county tables with 50 states + every county in CA
- Configures Django Admin to run against those new models
- Continuous Deployment to a staging environment (temporarily hosted on Heroku)
- Imports existing location and reports data from Airtable
- Provides a number of [fully documented](docs/api.md) APIs:
  - `POST /api/submitReport` that imitates the Netlify/Airtable one for submitting a call report
  - `POST /api/requestCall` (again imitating Netlify) for getting a new location to call
  - `GET /api/verifyToken` to verify an API token
  - `POST /api/importLocations` to import new locations
  - `GET /api/providerTypes` - see valid provider types
  - `GET /api/locationTypes` - see valid location types
  - `GET /api/counties/CA` - list counties in a state - accepts two letter state codes

For ongoing updates, see [simonw-internal-blog](https://github.com/CAVaccineInventory/simonw-internal-blog).

## What this will do

- Export options matching the public APIs we currently generate from Airtable
- I'm going to try setting up [django-reversion](https://github.com/etianen/django-reversion) to get full change history for those items

The [issues](https://github.com/CAVaccineInventory/django.vaccinate/issues) in this repo closely track upcoming work.

## Setting up a development environment

Check out the repository. Create a new Python virtual environment for it (I use `pipenv shell` to do this). Install the dependencies with `pip install -r requirements.txt`.

Set your environment variables, see *Configuration* section below.

`cd vaccinate` and then run the server with `./manage.py runserver 0.0.0.0:3000`

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

## Configuration

Running this requires some secrets in environment variables:

- `SOCIAL_AUTH_AUTH0_SECRET` can be found in the [Auth0 application configuration page](https://manage.auth0.com/dashboard/us/vaccinateca/applications/7JMM4bb1eC7taGN1OlaLBIXJN1w42vac/settings).
- `DJANGO_SECRET_KEY` can be any random string.  One way to generate one is via `python -c "import secrets; print(secrets.token_urlsafe())"`

Create a file like this named  `.env`, which is loaded by Django:

    SOCIAL_AUTH_AUTH0_SECRET="secret from the auth0 dashboard"
    DJANGO_SECRET_KEY="just a big random string"
    DJANGO_DEBUG=1

In development you will need to have a local PostgreSQL server running - I use PostgreSQL.app on my Mac for this.

Then create a database called `vaccinate` by running this in the terminal:

    createdb vaccinate

If your database has alternative connection details you can specify them using a `DATABASE_URL` environment variable of the format `postgres://USER:PASSWORD@HOST:PORT/NAME`.  You can place this in the `.env` file.

## Running the tests

To run the tests, change directory to the `vaccinate` folder and run `pytest`.

## Code formatting

This repository uses [Black](https://github.com/psf/black) and [isort](https://pycqa.github.io/isort/) to enforce coding style as part of the CI tests.

Run `black .` and `isort .` in the top-level directory to ensure your code is formatted correctly, then enjoy never having to think about how to best indent your Python code ever again.
