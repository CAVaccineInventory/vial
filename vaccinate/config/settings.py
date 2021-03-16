import os
from pathlib import Path

import dj_database_url
import sentry_sdk
from django.conf.locale.en import formats as en_formats
from sentry_sdk.integrations.django import DjangoIntegration

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
PRODUCTION = os.environ.get("PRODUCTION")
DEBUG = bool(os.environ.get("DJANGO_DEBUG"))
INTERNAL_IPS = ["127.0.0.1"]

ALLOWED_HOSTS = ["*"]

# Sentry
SENTRY_DSN = os.environ.get("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=1.0,
        send_default_pii=True,
        environment=os.environ.get("DEPLOY", "unknown"),
        release=os.environ.get("COMMIT_SHA", None),
    )

# Auth0
SOCIAL_AUTH_TRAILING_SLASH = False
SOCIAL_AUTH_AUTH0_DOMAIN = "vaccinateca.us.auth0.com"
SOCIAL_AUTH_AUTH0_KEY = os.environ.get(
    "SOCIAL_AUTH_AUTH0_KEY", "7JMM4bb1eC7taGN1OlaLBIXJN1w42vac"
)
SOCIAL_AUTH_AUTH0_SECRET = os.environ["SOCIAL_AUTH_AUTH0_SECRET"]
SOCIAL_AUTH_AUTH0_SCOPE = ["openid", "profile", "email"]

SOCIAL_AUTH_PIPELINE = (
    # Get the information we can about the user and return it in a simple
    # format to create the user instance later. On some cases the details are
    # already part of the auth response from the provider, but sometimes this
    # could hit a provider API.
    "social_core.pipeline.social_auth.social_details",
    # Get the social uid from whichever service we're authing thru. The uid is
    # the unique identifier of the given user in the provider.
    "social_core.pipeline.social_auth.social_uid",
    # Verifies that the current auth process is valid within the current
    # project, this is where emails and domains whitelists are applied (if
    # defined).
    "social_core.pipeline.social_auth.auth_allowed",
    # Checks if the current social-account is already associated in the site.
    "social_core.pipeline.social_auth.social_user",
    # Make up a username for this person, appends a random string at the end if
    # there's any collision.
    "social_core.pipeline.user.get_username",
    # Create a user account if we haven't found one yet.
    "social_core.pipeline.user.create_user",
    # Create the record that associated the social account with this user.
    "social_core.pipeline.social_auth.associate_user",
    # Populate the extra_data field in the social record with the values
    # specified by settings (and the default ones like access_token, etc).
    "social_core.pipeline.social_auth.load_extra_data",
    # Update the user record with any changed info from the auth service.
    "social_core.pipeline.user.user_details",
    # CUSTOM: assign staff permissions based on their Auth0 roles
    "auth0login.pipeline.provide_admin_access_based_on_auth0_role",
)

AUTHENTICATION_BACKENDS = {
    "auth0login.auth0backend.Auth0",
    "django.contrib.auth.backends.ModelBackend",
}
LOGIN_URL = "/login/auth0"
LOGIN_REDIRECT_URL = "/"

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admindocs",
    "django_migration_linter",
    "django_sql_dashboard",
    "social_django",
    "corsheaders",
    "auth0login",
    "core",
    "api",
]
if DEBUG:
    INSTALLED_APPS += ["debug_toolbar"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "beeline.middleware.django.HoneyMiddleware",
    "core.logging_middleware.RequestLoggingMiddleware",
    "core.timezone_middleware.TimezoneMiddleware",
] + (["debug_toolbar.middleware.DebugToolbarMiddleware"] if DEBUG else [])

# CORS using https://github.com/adamchainz/django-cors-headers
CORS_URLS_REGEX = r"^/api/.*$"
# Swap this out later for CORS_ALLOWED_ORIGINS = ["https://example.com", ...]
CORS_ALLOW_ALL_ORIGINS = True


if PRODUCTION:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True

ROOT_URLCONF = "config.urls"


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": "vaccinate",
    }
}


if "DATABASE_URL" in os.environ:
    # Parse database configuration from $DATABASE_URL
    DATABASES["default"] = dj_database_url.config()

    # Work around https://github.com/jacobian/dj-database-url/pull/113
    DATABASES["default"]["HOST"] = (
        DATABASES["default"]["HOST"].replace("%3a", ":").replace("%3A", ":")
    )

# 'dashboard' should be a read-only connection
if "DASHBOARD_DATABASE_URL" in os.environ:
    DATABASES["dashboard"] = dj_database_url.parse(os.environ["DASHBOARD_DATABASE_URL"])
    DATABASES["dashboard"]["OPTIONS"] = {
        "options": "-c default_transaction_read_only=on -c statement_timeout=1000"
    }


# Static files
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATIC_URL = "/static/"
# Ensure STATIC_ROOT exists.
os.makedirs(STATIC_ROOT, exist_ok=True)
WHITENOISE_ROOT = os.path.join(BASE_DIR, "rootfiles")


# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True
en_formats.DATETIME_FORMAT = "jS M Y fA e"

TEST_RUNNER = "test_runner.PytestTestRunner"
