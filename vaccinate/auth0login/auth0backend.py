from social_core.backends.oauth import BaseOAuth2
from .auth0_utils import decode_and_verify_jwt


class Auth0(BaseOAuth2):
    """Auth0 OAuth authentication backend"""

    name = "auth0"
    SCOPE_SEPARATOR = " "
    ACCESS_TOKEN_METHOD = "POST"
    REDIRECT_STATE = False
    EXTRA_DATA = [("picture", "picture"), ("email", "email")]

    def authorization_url(self):
        return "https://" + self.setting("DOMAIN") + "/authorize"

    def access_token_url(self):
        return "https://" + self.setting("DOMAIN") + "/oauth/token"

    def get_user_id(self, details, response):
        """Return current user id."""
        return details["user_id"]

    def get_user_details(self, response):
        id_token = response.get("id_token")
        payload = decode_and_verify_jwt(id_token)
        # Example payload:
        # {
        #     "https://help.vaccinateca.com/roles": [
        #         "Vaccinate CA Staff",
        #         "Volunteer Caller",
        #     ],
        #     "given_name": "Simon",
        #     "family_name": "Willison",
        #     "nickname": "swillison",
        #     "name": "Simon Willison",
        #     "picture": "https://lh3.googleusercontent.com/a-/AOh14Gg9Loyxove5ocfBp0mg0u2afcTpM1no8QJnwbWnxw=s96-c",
        #     "locale": "en-GB",
        #     "updated_at": "2021-02-24T20:44:31.243Z",
        #     "email": "...@gmail.com",
        #     "email_verified": True,
        #     "iss": "https://vaccinateca.us.auth0.com/",
        #     "sub": "google-oauth2|10636...",
        #     "aud": "7JMM4...",
        #     "iat": 1614199471,
        #     "exp": 1614235471,
        # }
        return {
            "username": payload["nickname"],
            "first_name": payload["name"],
            "picture": payload["picture"],
            "user_id": payload["sub"],
            "email": payload["email"],
            "roles": payload["https://help.vaccinateca.com/roles"],
        }
