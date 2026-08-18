from app.core.exceptions import UnauthorizedException


class InvalidTokenError(UnauthorizedException):
    """The bearer token failed signature, issuer, audience, or claim-shape validation."""
