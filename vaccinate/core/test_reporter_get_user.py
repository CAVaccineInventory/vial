import pytest
from django.contrib.auth.models import User
from social_django.models import UserSocialAuth

from .models import Reporter


@pytest.mark.django_db
def test_reporter_get_user_creates_user():
    reporter = Reporter.objects.create(
        external_id="auth0:auth0|60634083d767850069d0ee83",
        name="Barry",
        email="barry@example.com",
    )
    assert UserSocialAuth.objects.count() == 0
    assert not reporter.user
    assert User.objects.count() == 0
    user = reporter.get_user()
    assert User.objects.count() == 1
    assert user == User.objects.first()
    assert not user.is_superuser
    assert not user.is_staff
    assert user.is_active
    assert user.username == "r{}-barry".format(reporter.pk)
    assert user.first_name == "Barry"
    assert user.email == "barry@example.com"
    # Should have created a UserSocialAuth too
    assert UserSocialAuth.objects.count() == 1
    user_social_auth = UserSocialAuth.objects.first()
    assert user_social_auth.uid == "auth0|60634083d767850069d0ee83"
    assert user_social_auth.user == user


@pytest.mark.django_db
def test_reporter_get_user_finds_existing_user():
    reporter = Reporter.objects.create(
        external_id="auth0:auth0|60634083d767850069d0ee83",
        name="Barry",
        email="barry@example.com",
    )
    user = User.objects.create(username="barry")
    UserSocialAuth.objects.create(
        uid="auth0|60634083d767850069d0ee83", provider="auth0", user=user
    )
    assert not reporter.user
    assert User.objects.count() == 1
    user = reporter.get_user()
    assert User.objects.count() == 1
    assert user == User.objects.first()
