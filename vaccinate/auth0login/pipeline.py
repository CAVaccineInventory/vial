from django.contrib.auth.models import Group


def provide_admin_access_based_on_auth0_role(backend, user, response, *args, **kwargs):
    if backend.name == "auth0":
        roles = kwargs.get("details", {}).get("roles", {}) or []
        should_be_staff = "Vaccinate CA Staff" in roles
        group = Group.objects.get_or_create(name="default-view-core")[0]
        if should_be_staff == user.is_staff:
            # No changes needed
            return
        if should_be_staff:
            user.is_staff = True
            user.save()
            # Ensure user is in group
            group.user_set.add(user)
        else:
            user.is_staff = False
            user.save()
            # Ensure user is not in group
            group.user_set.remove(user)
