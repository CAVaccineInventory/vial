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

As a result, hosting this (or moving this to a different host) should be as easy as setting up a Django app with an attached PostgreSQL database.

## What this does so far

- SSO using Auth0 to sign users in with a Django user account
- Allows users to make changes to locations and other entities through the Django admin. These changes are tracked using [django-reversion](https://django-reversion.readthedocs.io/)
- Run tests in GitHub Actions CI using pytest-django
- Enforce Black code style in GitHub Actions
- Django ORM models for the new schema currently under discussion
- Populates the state and county tables with 50 states + every county in CA
- Configures Django Admin to run against those new models
- Continuous Deployment to a staging environment
- Imports existing location and reports data from Airtable
- Provides a number of [fully documented](docs/api.md) APIs

For ongoing updates, see [simonw-internal-blog](https://github.com/CAVaccineInventory/simonw-internal-blog).

The [issues](https://github.com/CAVaccineInventory/vial/issues) in this repo closely track upcoming work.

## Setting up a development environment

Check out the repository. Create a new Python virtual environment for it (I use `pipenv shell` to do this). Install the dependencies with `pip install -r requirements.txt`.

Set your environment variables, see _Configuration_ section below.

You'll need a PostgreSQL database called "vaccinate". On macOS I've used https://postgresapp.com/ for that.

Alternatively, you can use [Docker](docs/docker.md).

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

- `SOCIAL_AUTH_AUTH0_SECRET` can be found in the [Auth0 application configuration page](https://manage.auth0.com/dashboard/us/vaccinateca/applications/7JMM4bb1eC7taGN1OlaLBIXJN1w42vac/settings).
- `DJANGO_SECRET_KEY` can be any random string. One way to generate one is via `python -c "import secrets; print(secrets.token_urlsafe())"`

Create a file like this named `.env`, which is loaded by Django:

    SOCIAL_AUTH_AUTH0_SECRET="secret from the auth0 dashboard"
    DJANGO_SECRET_KEY="just a big random string"
    DJANGO_DEBUG=1

In development you will need to have a local PostgreSQL server running - I use PostgreSQL.app on my Mac for this. Alternatively, you can use [Docker][<docs/docker.md>]

Then create a database called `vaccinate` by running this in the terminal:

    createdb vaccinate

If your database has alternative connection details you can specify them using a `DATABASE_URL` environment variable of the format `postgres://USER:PASSWORD@HOST:PORT/NAME`. You can place this in the `.env` file.

## Running the tests

To run the tests, change directory to the `vaccinate` folder and run `pytest`.

## Code formatting and linting

This repository uses [Black](https://github.com/psf/black) and [isort](https://pycqa.github.io/isort/) to enforce coding style as part of the CI tests.

Run `black .` and `isort .` in the top-level directory to ensure your code is formatted correctly, then enjoy never having to think about how to best indent your Python code ever again.

Run `scripts/run-pyflakes` in the top-level directory to check for missing or unused imports.

Run `scripts/lint-migrations` in the top-level directory to verify that migrations do not have any backwards-incompatible changes that could cause problems during a deploy while the site is serving traffic.

## Logging SQL

You can set the `DJANGO_DEBUG_LOG_ALL_SQL=1` environment variable to log all SQL executed by Django to the console. This can be useful for things like understanding how complex migrations work:

    DJANGO_DEBUG_LOG_ALL_SQL=1 ./manage.py migrate
