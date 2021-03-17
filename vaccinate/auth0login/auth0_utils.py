import functools

import beeline
import requests
from django.conf import settings
from jose import jwt

DEFAULT_ISSUER = "https://" + settings.SOCIAL_AUTH_AUTH0_DOMAIN + "/"


@functools.cache
@beeline.traced(name="jwks")
def jwks():
    jwt_keys_url = (
        "https://" + settings.SOCIAL_AUTH_AUTH0_DOMAIN + "/.well-known/jwks.json"
    )
    return requests.get(jwt_keys_url, timeout=5).content


@beeline.traced(name="decode_and_verify_jwt")
def decode_and_verify_jwt(jwt_token, audience, issuer=DEFAULT_ISSUER):
    "Verify the signature of a JWT and return the decoded payload"
    return jwt.decode(
        jwt_token,
        jwks(),
        algorithms=["RS256"],
        audience=audience,
        issuer=issuer,
    )
