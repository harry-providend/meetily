from abc import ABC, abstractmethod

import jwt

from app.auth.current_user import AuthenticatedUser
from app.auth.exceptions import InvalidTokenError
from app.auth.jwks_client import JwksClient


class TokenValidator(ABC):
    @abstractmethod
    async def validate(self, bearer_token: str) -> AuthenticatedUser: ...


class EntraTokenValidator(TokenValidator):
    """Validates an Entra *access* token against the tenant's JWKS. The ID token never leaves
    the client, and client-side claim reading is unsigned -- this is the only real check."""

    def __init__(
        self,
        jwks_client: JwksClient,
        expected_issuer: str,
        expected_audiences: list[str],
    ) -> None:
        self._jwks_client = jwks_client
        self._expected_issuer = expected_issuer
        self._expected_audiences = expected_audiences

    async def validate(self, bearer_token: str) -> AuthenticatedUser:
        try:
            signing_key = self._jwks_client.get_signing_key(bearer_token)
            claims = jwt.decode(
                bearer_token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._expected_issuer,
                audience=self._expected_audiences,
                options={"require": ["exp", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(f"token validation failed: {exc}") from exc

        oid = claims.get("oid") or claims.get("sub")
        tid = claims.get("tid")
        if not oid or not tid:
            raise InvalidTokenError("token is missing required oid/sub or tid claim")

        return AuthenticatedUser(
            oid=oid,
            tenant_id=tid,
            display_name=claims.get("name"),
            upn=claims.get("preferred_username") or claims.get("upn"),
        )
