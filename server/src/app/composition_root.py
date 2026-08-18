from functools import lru_cache

from app.auth.entra_token_validator import EntraTokenValidator, TokenValidator
from app.auth.jwks_client import JwksClient
from app.core.config import get_settings


@lru_cache
def get_token_validator() -> TokenValidator:
    """App-lifetime singleton: the JWKS client caches Entra's signing keys, so rebuilding it
    per request would refetch the key set every call."""
    settings = get_settings()
    return EntraTokenValidator(
        jwks_client=JwksClient(settings.entra_jwks_uri),
        expected_issuer=settings.entra_expected_issuer,
        expected_audiences=settings.entra_accepted_audiences,
    )
