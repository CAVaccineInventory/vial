from django.contrib import admin
from django.urls import path, include
from auth0login import views


urlpatterns = [
    path("", views.index),
    path("dashboard", views.dashboard),
    path("logout", views.logout),
    path("", include("django.contrib.auth.urls")),
    path("", include("social_django.urls")),
    path("admin/", admin.site.urls),
]
