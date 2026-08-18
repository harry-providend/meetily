from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    """Identity from a validated Entra access token. No local user directory: a user exists
    to this backend the moment they present a valid token, keyed on oid + tid."""

    oid: str
    tenant_id: str
    display_name: str | None
    upn: str | None
