import datetime
import json
import secrets
from functools import wraps

from django.http import JsonResponse
from django.utils import timezone

from .models import ApiKey, ApiLog


def auth_error(message):
    return JsonResponse({"error": message}, status=403)


def require_api_key(view_fn):
    @wraps(view_fn)
    def protected_view_fn(request, *args, **kwargs):
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
        return view_fn(request, *args, **kwargs)

    return protected_view_fn


def log_api_requests(view_fn):
    @wraps(view_fn)
    def replacement_view_function(request, *args, **kwargs):
        on_request_logged = []
        kwargs["on_request_logged"] = on_request_logged.append
        response = view_fn(request, *args, **kwargs)
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
            method=request.method,
            path=request.path,
            query_string=request.META.get("QUERY_STRING") or "",
            remote_ip=request.META.get("REMOTE_ADDR") or "",
            post_body=post_body,
            post_body_json=post_body_json,
            response_status=response.status_code,
            response_body=response_body,
            response_body_json=response_body_json,
        )
        for callback in on_request_logged:
            callback(log)
        return response

    return replacement_view_function
