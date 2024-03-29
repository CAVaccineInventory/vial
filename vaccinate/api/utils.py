import datetime
import secrets
from functools import wraps
from typing import Any, Callable, List, Optional, Set

import beeline
import orjson
import requests
from auth0login.auth0_utils import decode_and_verify_jwt
from core.models import Reporter
from django.conf import settings
from django.db import transaction
from django.http import HttpRequest
from django.http.response import (
    HttpResponse,
    HttpResponseBase,
    HttpResponseServerError,
    JsonResponse,
)
from django.utils import timezone

from .models import ApiKey, ApiLog, Switch


def auth_error(message):
    return JsonResponse({"error": message}, status=403)


def require_api_key_or_cookie_user(view_fn):
    "Allows request with an api key OR request.user from cookies"

    @wraps(view_fn)
    def protected_view_fn(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_fn(request, *args, **kwargs)
        api_key_error = check_request_for_api_key(request)
        if api_key_error:
            return api_key_error
        return view_fn(request, *args, **kwargs)

    return protected_view_fn


def check_request_for_api_key(request):
    authorization = request.META.get("HTTP_AUTHORIZATION") or ""
    if not authorization.startswith("Bearer "):
        return auth_error("Authorization header must start with 'Bearer'")
    token = authorization.split("Bearer ")[1]
    if token.count(":") != 1:
        return auth_error("Bearer token is expected to be nnn:long-string")
    id, key = token.split(":")
    if not id.isnumeric():
        return auth_error("Bearer token is expected to be nnn:long-string")
    try:
        api_key = ApiKey.objects.get(pk=id)
    except ApiKey.DoesNotExist:
        return auth_error("API key does not exist")
    if not secrets.compare_digest(api_key.key, key):
        return auth_error("Invalid API key")
    # update last_seen_at if not seen in last 5 minutes
    if api_key.last_seen_at is None or api_key.last_seen_at < (
        timezone.now() - datetime.timedelta(minutes=1)
    ):
        api_key.last_seen_at = timezone.now()
        api_key.save()
    beeline.add_trace_field("user.api_key", api_key.id)
    request.api_key = api_key
    return None


def require_api_key(view_fn):
    @wraps(view_fn)
    def protected_view_fn(request, *args, **kwargs):
        api_key_error = check_request_for_api_key(request)
        if api_key_error:
            return api_key_error
        return view_fn(request, *args, **kwargs)

    return protected_view_fn


def log_api_requests_no_response_body(view_fn):
    return log_api_requests(view_fn, log_response=False)


def log_api_requests(view_fn, log_response=True):
    @wraps(view_fn)
    def replacement_view_function(request, *args, **kwargs):
        response: Optional[HttpResponse] = None
        on_request_logged = []
        kwargs["on_request_logged"] = on_request_logged.append
        try:
            response = view_fn(request, *args, **kwargs)
        finally:
            if response is None:
                response = HttpResponseServerError()
            if getattr(request, "skip_api_logging", False):
                return response
            # Create the log record
            post_body = None
            post_body_json = None
            response_body = None
            response_body_json = None
            if request.method == "POST":
                try:
                    post_body_json = orjson.loads(request.body)
                except ValueError:
                    post_body = request.body
            if log_response:
                try:
                    response_body_json = orjson.loads(response.content)
                except ValueError:
                    response_body = response.content
                except AttributeError:
                    # Streaming responses have no .content
                    pass
            log = ApiLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                method=request.method,
                path=request.path,
                query_string=request.META.get("QUERY_STRING") or "",
                remote_ip=request.META.get("REMOTE_ADDR") or "",
                post_body=post_body,
                post_body_json=post_body_json,
                response_status=response.status_code,
                response_body=response_body,
                response_body_json=response_body_json,
                api_key=getattr(request, "api_key", None) or None,
            )

        # If the request was _successful_, we go on to call the callbacks.
        for callback in on_request_logged:
            callback(log)
        return response

    return replacement_view_function


def deny_if_api_is_disabled(view_fn):
    @wraps(view_fn)
    def inner(request, *args, **kwargs):
        if Switch.objects.filter(name="disable_api", on=True).exists():
            return JsonResponse(
                {
                    "error": "This application is currently disabled - please try again later"
                },
                status=400,
            )
        return view_fn(request, *args, **kwargs)

    return inner


@beeline.traced("jwt_auth")
def _jwt_auth(
    required_permissions: Set[str],
    request: HttpRequest,
    update_metadata: bool,
) -> Optional[JsonResponse]:
    # Use Bearer token in Authorization header
    authorization = request.META.get("HTTP_AUTHORIZATION") or ""
    if not authorization.startswith("Bearer "):
        return JsonResponse(
            {"error": "Authorization header must start with 'Bearer'"},
            status=403,
        )

    # Check JWT token is valid
    jwt_access_token = authorization.split("Bearer ")[1]
    check_permissions = True
    try:
        jwt_payload = decode_and_verify_jwt(
            jwt_access_token, settings.HELP_JWT_AUDIENCE
        )
    except Exception as e:
        try:
            # We _also_ try to decode as the VIAL audience, since the
            # /api/requestCall/debug endpoint passes in _our_ JWT, not
            # help's.  Our JWT is an id token, not an access token,
            # which means it won't have permissions in it (see below)
            jwt_payload = decode_and_verify_jwt(
                jwt_access_token, settings.VIAL_JWT_AUDIENCE
            )
            check_permissions = False
        except Exception:
            return JsonResponse(
                {"error": "Could not decode JWT", "details": str(e)}, status=403
            )

    # We have an _access_ token, not an _id_ token.  This means that
    # it has authorization information, but no authentication
    # information -- just an id, and a statement that the user is
    # authenticated to hit this API.  https://auth0.com/docs/tokens
    # describes this in more detail.
    jwt_auth0_role_names = ", ".join(
        sorted(jwt_payload.get("https://help.vaccinateca.com/roles", []))
    )
    name: Optional[str] = None
    email: Optional[str] = None

    external_id = "auth0:{}".format(jwt_payload["sub"])
    with transaction.atomic():
        # Get full metadata if the user doesn't exist; also take a lock on the user.
        reporter = (
            Reporter.objects.select_for_update().filter(external_id=external_id).first()
        )
        # We may want to update the email address and name; we do this
        # sparingly, since it's a round-trip to the Auth0 endpoint, which
        # is somewhat slow.  Again, we must do this because we're getting
        # an access token, not an id token.
        if not reporter or update_metadata:
            with beeline.tracer(name="get user_info"):
                user_info_response = requests.get(
                    "https://vaccinateca.us.auth0.com/userinfo",
                    headers={"Authorization": "Bearer {}".format(jwt_access_token)},
                    timeout=5,
                )
                beeline.add_context({"status": user_info_response.status_code})
                # If this fails, we don't fail the request; they still
                # had a valid access token, auth0 is just being slow
                # telling us their bio.
                if user_info_response.status_code == 200:
                    user_info = user_info_response.json()
                    name = user_info["name"]
                    if user_info["email_verified"]:
                        email = user_info["email"]
                    jwt_auth0_role_names = ", ".join(
                        sorted(user_info["https://help.vaccinateca.com/roles"])
                    )

        external_id = "auth0:{}".format(jwt_payload["sub"])
        defaults = {"auth0_role_names": jwt_auth0_role_names}
        if name is not None:
            defaults["name"] = name
        if email is not None:
            defaults["email"] = email
        reporter = Reporter.objects.update_or_create(
            external_id=external_id,
            defaults=defaults,
        )[0]

    # Finally, make sure they have the required permissions
    if check_permissions:
        missing_perms = required_permissions - set(jwt_payload["permissions"])
        if missing_perms:
            return JsonResponse(
                {
                    "error": "Missing permissions: %s"
                    % (", ".join(list(missing_perms)),),
                },
                status=403,
            )
    request.reporter = reporter  # type: ignore[attr-defined]
    return None


def jwt_auth(
    allow_session_auth=False,
    allow_internal_api_key=False,
    required_permissions: List[str] = ["caller"],
    update_metadata=False,
) -> Callable[[Callable[..., HttpResponseBase]], Callable[..., HttpResponseBase]]:
    def wrapper(
        view_fn: Callable[..., HttpResponseBase]
    ) -> Callable[..., HttpResponseBase]:
        @wraps(view_fn)
        def inner(request: HttpRequest, *args, **kwargs: Any) -> HttpResponseBase:
            if getattr(request, "skip_jwt_auth", False):
                return view_fn(request, *args, **kwargs)
            # Two other kinds of auth to possibly check
            if allow_session_auth and request.user.is_authenticated:
                return view_fn(request, *args, **kwargs)
            if allow_internal_api_key and not check_request_for_api_key(request):
                return view_fn(request, *args, **kwargs)

            auth_failure = _jwt_auth(
                set(required_permissions), request, update_metadata
            )
            if auth_failure:
                return auth_failure

            return view_fn(request, *args, **kwargs)

        return inner

    return wrapper


class PrettyJsonResponse(JsonResponse):
    # Pretty-printed JSON response. Use this for API methods that return
    # a small amount of reference data, e.g. /api/taskTypes
    def __init__(self, *args, **kwargs):
        if "json_dumps_params" not in kwargs:
            kwargs["json_dumps_params"] = {}
        kwargs["json_dumps_params"]["indent"] = 4
        super().__init__(*args, **kwargs)
