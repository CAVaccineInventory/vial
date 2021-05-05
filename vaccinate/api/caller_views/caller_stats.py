import beeline
from api.utils import jwt_auth
from django.http import HttpRequest, JsonResponse
from django.utils.timezone import localdate
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
@beeline.traced(name="caller_stats")
@jwt_auth(required_permissions=["caller"], update_metadata=True)
def caller_stats(request: HttpRequest) -> JsonResponse:
    reports = request.reporter.reports.exclude(soft_deleted=True)  # type: ignore[attr-defined]
    return JsonResponse(
        {
            "total": reports.count(),
            "today": reports.filter(created_at__date=localdate()).count(),
        }
    )
