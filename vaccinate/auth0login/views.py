from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import logout as log_out
from django.http import HttpResponseRedirect
from django.shortcuts import render


def login(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect("/login/auth0")
    # If user is logged in but doesn't have staff permisisons, show error
    if not request.user.is_staff:
        return render(request, "admin/not_staff.html")

    return HttpResponseRedirect("/dashboard/")


def logout(request):
    log_out(request)
    return_to = urlencode({"returnTo": request.build_absolute_uri("/")})
    logout_url = "https://%s/v2/logout?client_id=%s&%s" % (
        settings.SOCIAL_AUTH_AUTH0_DOMAIN,
        settings.SOCIAL_AUTH_AUTH0_KEY,
        return_to,
    )
    return HttpResponseRedirect(logout_url)
