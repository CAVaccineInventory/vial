import os
import sys
from io import StringIO

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core import management
from django.db import connection
from django.http.response import JsonResponse
from django.shortcuts import redirect, render


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
            "deployed_sha": os.environ.get("COMMIT_SHA")
            or os.environ.get("HEROKU_SLUG_COMMIT"),
            "postgresql_version": cursor.fetchone()[0],
            "python_version": sys.version,
        }
    )


@login_required
@user_passes_test(lambda user: user.is_superuser)
def admin_commands(request):
    command_output = StringIO()
    error = None
    message = None
    if request.method == "POST":
        command_to_run, args = {
            "import_counties": ("import_counties", []),
        }.get(request.POST.get("command"), (None, None))
        if command_to_run is None:
            error = "Unknown command"
        else:
            management.call_command(command_to_run, *args, stdout=command_output)
            message = "Ran command: {}".format(command_to_run)
    return render(
        request,
        "admin/commands.html",
        {
            "output": command_output.getvalue(),
            "error": error,
            "message": message,
        },
    )
