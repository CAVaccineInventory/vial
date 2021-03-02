from auth0login.auth0_utils import decode_and_verify_jwt
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from pydantic import BaseModel, validator, ValidationError
from core.models import Location, Report
import json


class ReportValidator(BaseModel):
    location: str

    @validator("location")
    def location_must_exist(cls, v):
        if not Location.objects.filter(public_id=v).exists():
            raise ValueError("Location '{}' does not exist".format(v))
        return v


@csrf_exempt
def submit_report(request):
    authorization = request.META.get("HTTP_AUTHORIZATION") or ""
    if not authorization.startswith("Bearer "):
        return JsonResponse({"error": "Authorization header must start with 'Bearer'"})
    # Check JWT token is valid
    jwt_id_token = authorization.split("Bearer ")[1]
    try:
        payload = decode_and_verify_jwt(jwt_id_token)
    except Exception as e:
        return JsonResponse({"error": "Could not decode JWT", 'details': str(e)})
    try:
        post_data = json.loads(request.body.decode("utf-8"))
    except ValueError as e:
        return JsonResponse({"error": str(e), "user": payload})
    try:
        report_data = ReportValidator(**post_data)
    except ValidationError as e:
        return JsonResponse({"error": e.errors(), "user": payload})
    return JsonResponse({"blah": report_data.dict(), "user": payload})


def submit_report_debug(request):
    return render(
        request,
        "api/submit_report_debug.html",
        {"jwt": request.session["jwt"] if "jwt" in request.session else ""},
    )
