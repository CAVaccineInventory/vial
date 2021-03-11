import requests
from django.conf import settings
from jose import jwt


def decode_and_verify_jwt(jwt_id_token, try_fallback=False):
    # Verifies the signature of a JWT and returns the decoded payload
    DOMAIN = settings.SOCIAL_AUTH_AUTH0_DOMAIN
    jwt_keys_url = "https://" + DOMAIN + "/.well-known/jwks.json"
    jwks = requests.get(jwt_keys_url).content
    try:
        return jwt.decode(
            jwt_id_token,
            jwks,
            algorithms=["RS256"],
            audience=settings.SOCIAL_AUTH_AUTH0_KEY,
            issuer="https://" + DOMAIN + "/",
        )
    except Exception:
        if try_fallback:
            fallback_response = requests.get(
                "https://vaccinateca.us.auth0.com/userinfo",
                headers={"Authorization": "Bearer {}".format(jwt_id_token)},
            )
            fallback_response.raise_for_status()
            return fallback_response.json()
        else:
            raise
