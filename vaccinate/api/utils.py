import json
from functools import wraps

from .models import ApiLog


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
