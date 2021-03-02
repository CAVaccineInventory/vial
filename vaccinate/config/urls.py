from django.contrib import admin
from django.http.response import HttpResponsePermanentRedirect
from django.urls import path, include
from django.shortcuts import redirect
from auth0login.views import logout
from core import views as core_views


urlpatterns = [
    path("", core_views.index),
    path("logout", logout),
    path("", include("django.contrib.auth.urls")),
    path("", include("social_django.urls")),
    path(
        "admin/core/callreport/",
        lambda r: HttpResponsePermanentRedirect("/admin/core/report/"),
    ),
    # Over-ride Django admin default login/logout
    path("admin/login/", lambda r: redirect("/login/auth0", permanent=False)),
    path("admin/logout/", lambda r: redirect("/logout/", permanent=False)),
    path("admin/", admin.site.urls),
]
