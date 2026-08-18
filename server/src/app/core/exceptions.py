class AppException(Exception):
    """Base class for application errors that carry an HTTP-meaningful status."""

    status_code: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundException(AppException):
    """Used identically for absent and someone-else's, so ownership never leaks."""

    status_code = 404


class UnauthorizedException(AppException):
    """Raised when no valid bearer token is present."""

    status_code = 401


class ForbiddenException(AppException):
    """Valid token but unusable claims (no oid/tid), or an operation disallowed for reasons
    unrelated to ownership."""

    status_code = 403


class ConflictException(AppException):
    """Raised for state conflicts, e.g. a stale sync push that should be reported as such."""

    status_code = 409
