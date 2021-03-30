import os
import sys

from django.db import connection
from django.http.response import JsonResponse
from django.shortcuts import redirect, render
from reversion import get_registered_models


def index(request):
    user = request.user
    if user.is_authenticated:
        return redirect("/admin/")
    else:
        return render(request, "index.html")


def healthcheck(request):
    cursor = connection.cursor()
    cursor.execute("SELECT version();")
    return JsonResponse(
        {
            "deployed_sha": os.environ.get("COMMIT_SHA"),
            "postgresql_version": cursor.fetchone()[0],
            "python_version": sys.version,
            "reversion_models": [m._meta.label for m in get_registered_models()],
        }
    )
