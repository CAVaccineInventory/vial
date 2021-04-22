import datetime
import json
import secrets
from functools import wraps
from typing import Optional

from django.http import HttpResponse, HttpResponseServerError, JsonResponse
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
        return auth_error("Bearer token must contain one ':'")
    id, key = token.split(":")
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
