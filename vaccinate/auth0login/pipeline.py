from django.contrib.auth.models import Group


def provide_admin_access_based_on_auth0_role(backend, user, response, *args, **kwargs):
    if backend.name == "auth0":
        roles = kwargs.get("details", {}).get("roles", {}) or []
        should_be_staff = "Vaccinate CA Staff" in roles
        should_be_superuser = "VIAL super-user" in roles
        group = Group.objects.get_or_create(name="default-view-core")[0]
        needs_save = False
        if should_be_staff != user.is_staff:
            user.is_staff = should_be_staff
            needs_save = True
        if should_be_superuser != user.is_superuser:
            user.is_superuser = should_be_superuser
            needs_save = True
        if needs_save:
            user.save()
        # Ensure user has membership of group (or not)
        if should_be_staff:
            group.user_set.add(user)
        else:
            group.user_set.remove(user)
        # Stash the id_token as 'jwt' in the session
        kwargs["request"].session["jwt"] = response["id_token"]
