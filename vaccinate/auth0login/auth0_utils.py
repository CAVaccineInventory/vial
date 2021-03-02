from django.conf import settings
from jose import jwt
import requests


def decode_and_verify_jwt(jwt_id_token):
    # Verifies the signature of a JWT and returns the decoded payload
    DOMAIN = settings.SOCIAL_AUTH_AUTH0_DOMAIN
    jwt_keys_url = "https://" + DOMAIN + "/.well-known/jwks.json"
    jwks = requests.get(jwt_keys_url).content
    return jwt.decode(
        jwt_id_token,
        jwks,
        algorithms=["RS256"],
        audience=settings.SOCIAL_AUTH_AUTH0_KEY,
        issuer="https://" + DOMAIN + "/",
    )
