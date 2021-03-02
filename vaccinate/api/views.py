from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from pydantic import BaseModel, validator, ValidationError
from pydantic.types import Json
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
    try:
        post_data = json.loads(request.body.decode("utf-8"))
    except ValueError as e:
        return JsonResponse({"error": str(e)})
    try:
        report_data = ReportValidator(**post_data)
    except ValidationError as e:
        return JsonResponse({"error": e.errors()})
    return JsonResponse(report_data.dict())


def submit_report_debug(request):
    return render(
        request,
        "api/submit_report_debug.html",
        {"jwt": request.session["jwt"] if "jwt" in request.session else ""},
    )
