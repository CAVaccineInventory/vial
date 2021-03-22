from io import StringIO

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core import management
from django.shortcuts import render


@login_required
@user_passes_test(lambda user: user.is_superuser)
def admin_tools(request):
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
        "admin/tools.html",
        {
            "output": command_output.getvalue(),
            "error": error,
            "message": message,
        },
    )
