import pytest
from django.conf import settings

from .models import State


@pytest.mark.django_db
def test_states_were_populated():
    assert State.objects.count() == 55


def test_security_middleware_is_first():
    assert settings.MIDDLEWARE[0] == "django.middleware.security.SecurityMiddleware"


def test_redirect_callreport_to_report(client):
    response = client.get("/admin/core/callreport/")
    assert response.status_code == 301
    assert response.url == "/admin/core/report/"
