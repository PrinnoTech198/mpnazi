"""
Authentication helpers for DRF.

When mobile clients persist JWTs and attach them to every request, an expired
or malformed Bearer token causes SimpleJWT to raise before permissions run,
so even AllowAny / PublicReadAdminWrite endpoints return 401. Optional JWT
treats bad tokens like "no auth" so public reads still work.
"""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class OptionalJWTAuthentication(JWTAuthentication):
    """
    Same as JWTAuthentication, but invalid/expired tokens do not abort the request.

    Returns None so DRF treats the user as anonymous; views with AllowAny or
    PublicReadAdminWrite can still serve GET without a valid token.
    """

    def authenticate(self, request):
        try:
            header = self.get_header(request)
            if header is None:
                return None

            raw_token = self.get_raw_token(header)
            if raw_token is None:
                return None

            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
            return user, validated_token
        except (TokenError, InvalidToken, AuthenticationFailed):
            return None
        except Exception:
            # Any malformed/expired credential on public endpoints should not 401.
            return None
