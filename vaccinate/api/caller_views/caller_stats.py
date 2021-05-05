import beeline  # type: ignore
from api.utils import JWTRequest, jwt_auth
from django.http import JsonResponse
from django.utils.timezone import localdate
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
@beeline.traced(name="caller_stats")
@jwt_auth(required_permissions=["caller"])
def caller_stats(request: JWTRequest) -> JsonResponse:
    reports = request.reporter.reports.exclude(soft_deleted=True)
    return JsonResponse(
        {
            "total": reports.count(),
            "today": reports.filter(created_at__date=localdate()).count(),
        }
    )
