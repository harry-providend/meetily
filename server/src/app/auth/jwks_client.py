import jwt


class JwksClient:
    """Thin wrapper around PyJWT's PyJWKClient -- isolates the third-party type behind our own
    class so EntraTokenValidator depends on a name we control, not a library import directly."""

    def __init__(self, jwks_uri: str) -> None:
        self._client = jwt.PyJWKClient(jwks_uri, cache_keys=True, lifespan=3600)

    def get_signing_key(self, token: str) -> jwt.PyJWK:
        return self._client.get_signing_key_from_jwt(token)
