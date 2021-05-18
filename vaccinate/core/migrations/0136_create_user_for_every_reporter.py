from django.db import migrations


def get_user_for_reporter(self, User, UserSocialAuth):
    # A user may exist based on a `UserSocialAuth` record
    assert self.external_id.startswith(
        "auth0:"
    ), "Only auth0 reporters can be associated with Django users, not {}".format(
        self.external_id
    )
    identifier = self.external_id[len("auth0:") :]
    user_social_auth = UserSocialAuth.objects.filter(uid=identifier).first()
    if not user_social_auth:
        # Create user, associate it and return
        username = "r{}".format(self.pk)
        # Some users have their email address as their name
        email = self.email
        if not email and self.name and "@" in self.name:
            email = self.name
        if email and "@" in email:
            username += "-" + email.split("@")[0]
        user = User.objects.create(
            username=username,
            email=email or "",
            first_name=self.name or "",
        )
        UserSocialAuth.objects.create(uid=identifier, provider="auth0", user=user)
        self.user = user
    else:
        self.user = user_social_auth.user
    self.save()
    return self.user


def create_user_for_every_reporter(apps, schema_editor):
    UserSocialAuth = apps.get_model("social_django", "UserSocialAuth")
    User = apps.get_model("auth", "User")
    Reporter = apps.get_model("core", "Reporter")

    for reporter in Reporter.objects.filter(user=None).exclude(
        external_id__startswith="airtable:"
    ):
        get_user_for_reporter(reporter, User, UserSocialAuth)


class Migration(migrations.Migration):

    dependencies = [
        ("social_django", "0010_uid_db_index"),
        ("core", "0135_walkins_only"),
    ]

    operations = [
        migrations.RunPython(
            create_user_for_every_reporter,
            reverse_code=lambda apps, schema_editor: None,
        )
    ]
