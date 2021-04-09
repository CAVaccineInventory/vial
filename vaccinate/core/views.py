import os
import sys

import pkg_resources
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
            "package_versions": {
                d.project_name: d.version
                for d in sorted(
                    pkg_resources.working_set, key=lambda d: d.project_name.lower()
                )
            },
            "reversion_models": [m._meta.label for m in get_registered_models()],
        }
    )
