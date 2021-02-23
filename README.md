# django.vaccinate

**This repository is currently a prototype / proof of concept**. This message will be removed should that no longer be true!

## What this does so far

- SSO using Auth0 to sign users in with a Django user account

## What this will do

- Run tests in GitHub Actions CI using pytest-django
- Django ORM models for the schema needed to replace the core reports and locations tables from Airtable
- Django admin configured to support managing those
- Import existing data so we can really exercise the prototype
- I'm going to try setting up [django-reversion](https://github.com/etianen/django-reversion) to get full change history for those items

## Setup

Check out the repository. Create a new Python virtual environment for it (I use `pipenv shell` to do this). Install the dependencies with `pip install -r requirements.txt`.

Set your environment variables, see *Configuration* section below.

Run the server with `./manage.py runserver 0.0.0.0:3000`

Visit it at `http://localhost:3000/dashboard` - it's important to use `localhost:3000` as that is the URL that is allow-listed for logins by the Auth0 configuration.

## Configuration

Running this requires two environment variables. I have a file called `env.sh` which I `source env.sh` when working on the project which looks like this:

    export SOCIAL_AUTH_AUTH0_SECRET="secret from the auth0 dashboard"
    export DJANGO_SECRET_KEY="just a big random string"
    export DJANGO_DEBUG=1

## Running the tests

To run the tests, change directory to the `vaccinate` folder and run `pytest`.
