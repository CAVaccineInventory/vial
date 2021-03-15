import functools

import requests
from django.conf import settings
from jose import jwt

DOMAIN = settings.SOCIAL_AUTH_AUTH0_DOMAIN


@functools.cache
def jwks():
    jwt_keys_url = "https://" + DOMAIN + "/.well-known/jwks.json"
    return requests.get(jwt_keys_url, timeout=5).content


def decode_and_verify_jwt(jwt_id_token, try_fallback=False):
    # Verifies the signature of a JWT and returns the decoded payload
    try:
        return jwt.decode(
            jwt_id_token,
            jwks(),
            algorithms=["RS256"],
            audience=settings.SOCIAL_AUTH_AUTH0_KEY,
            issuer="https://" + DOMAIN + "/",
        )
    except Exception as e:
        if try_fallback:
            fallback_response = requests.get(
                "https://vaccinateca.us.auth0.com/userinfo",
                headers={"Authorization": "Bearer {}".format(jwt_id_token)},
                timeout=5,
            )
            fallback_response.raise_for_status()
            return fallback_response.json()
        else:
            raise
