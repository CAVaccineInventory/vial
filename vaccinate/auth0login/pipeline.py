from django.contrib.auth import logout
from django.contrib.auth.models import Group
from django.conf import settings

AUTH0_ROLES_TO_REFLECT = {
    "Vaccinate CA Staff",
    "VIAL super-user",
    "Reports QA",
    "VIAL data corrections",
}
if settings.STAGING:
    AUTH0_ROLES_TO_REFLECT = {name + " STAGING" for name in AUTH0_ROLES_TO_REFLECT}


def provide_admin_access_based_on_auth0_role(backend, user, response, *args, **kwargs):
    if backend.name == "auth0":
        users_roles = kwargs.get("details", {}).get("roles", {}) or []
        groups = {
            name: Group.objects.get_or_create(name=name)[0]
            for name in AUTH0_ROLES_TO_REFLECT
        }
        should_be_staff = any(
            auth0_role in users_roles for auth0_role in AUTH0_ROLES_TO_REFLECT
        )
        if should_be_staff != user.is_staff:
            user.is_staff = should_be_staff
            user.save()
        # Add user to groups if necessary:
        for auth0_role in AUTH0_ROLES_TO_REFLECT:
            group = groups[auth0_role]
            if auth0_role in users_roles:
                group.user_set.add(user)
            else:
                group.user_set.remove(user)
        # Stash the id_token as 'jwt' in the session
        kwargs["request"].session["jwt"] = response["id_token"]


def social_user_or_logout(backend, uid, user=None, *args, **kwargs):
    provider = backend.name
    social = backend.strategy.storage.user.get_social_auth(provider, uid)
    if social:
        if user and social.user != user:
            logout(backend.strategy.request)
        elif not user:
            user = social.user
    return {
        "social": social,
        "user": user,
        "is_new": user is None,
        "new_association": False,
    }
