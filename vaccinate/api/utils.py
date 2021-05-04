import datetime
import json
import secrets
from functools import wraps
from typing import Optional, Union

import beeline
import requests
from auth0login.auth0_utils import decode_and_verify_jwt
from core.models import Reporter
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseServerError, JsonResponse
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


def log_api_requests(view_fn):
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
            # Create the log record
            post_body = None
            post_body_json = None
            response_body = None
            response_body_json = None
            if request.method == "POST":
                try:
                    post_body_json = json.loads(request.body)
                except ValueError:
                    post_body = request.body
            try:
                response_body_json = json.loads(response.content)
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


@beeline.traced("reporter_from_request")
def reporter_from_request(
    request: HttpRequest, allow_test=False
) -> Union[Reporter, JsonResponse]:
    if allow_test and bool(request.GET.get("test")) and request.GET.get("fake_user"):
        reporter = Reporter.objects.get_or_create(
            external_id="auth0-fake:{}".format(request.GET["fake_user"]),
        )[0]
        user_info = {"fake": reporter.external_id}
        return reporter
    # Use Bearer token in Authorization header
    authorization = request.META.get("HTTP_AUTHORIZATION") or ""
    if not authorization.startswith("Bearer "):
        return JsonResponse(
            {"error": "Authorization header must start with 'Bearer'"}, status=403
        )
    # Check JWT token is valid
    jwt_access_token = authorization.split("Bearer ")[1]
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
        except Exception:
            return JsonResponse(
                {"error": "Could not decode JWT", "details": str(e)}, status=403
            )
    external_id = "auth0:{}".format(jwt_payload["sub"])

    # We have an _access_ token, not an _id_ token.  This means that
    # it has authorization information, but no authentication
    # information -- just an id, and a statement that the user is
    # authenticated to hit this API.  https://auth0.com/docs/tokens
    # describes this in more detail.
    jwt_auth0_role_names = ", ".join(
        sorted(jwt_payload.get("https://help.vaccinateca.com/roles", []))
    )
    try:
        reporter = Reporter.objects.get(external_id=external_id)
        # Have their auth0 roles changed?
        if reporter.auth0_role_names != jwt_auth0_role_names:
            reporter.auth0_role_names = jwt_auth0_role_names
            reporter.save()
        return reporter
    except Reporter.DoesNotExist:
        pass

    # If name is missing we need to fetch userdetails
    if "name" not in jwt_payload or "email" not in jwt_payload:
        with beeline.tracer(name="get user_info"):
            user_info_response = requests.get(
                "https://vaccinateca.us.auth0.com/userinfo",
                headers={"Authorization": "Bearer {}".format(jwt_access_token)},
                timeout=5,
            )
            beeline.add_context({"status": user_info_response.status_code})
            user_info_response.raise_for_status()
            user_info = user_info_response.json()
            name = user_info["name"]
            email = user_info["email"]
    else:
        name = jwt_payload["name"]
        email = jwt_payload["email"]
    defaults = {"auth0_role_names": jwt_auth0_role_names}
    if name is not None:
        defaults["name"] = name
    if email is not None:
        defaults["email"] = email
    reporter = Reporter.objects.update_or_create(
        external_id=external_id,
        defaults=defaults,
    )[0]
    return reporter
