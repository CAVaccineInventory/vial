from django.contrib import admin
from django.http.response import HttpResponsePermanentRedirect
from django.urls import path, include
from auth0login import views


urlpatterns = [
    path("", views.index),
    path("dashboard", views.dashboard),
    path("logout", views.logout),
    path("", include("django.contrib.auth.urls")),
    path("", include("social_django.urls")),
    path(
        "admin/core/callreport/",
        lambda r: HttpResponsePermanentRedirect("/admin/core/report/"),
    ),
    path("admin/", admin.site.urls),
]
