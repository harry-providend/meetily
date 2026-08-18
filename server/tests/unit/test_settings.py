"""Entra identifiers have two valid spellings each; both must be accepted."""

from app.core.config import Settings

TENANT = "11111111-2222-3333-4444-555555555555"
CLIENT = "66666666-7777-8888-9999-000000000000"


def _settings(app_id_uri: str) -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://u:p@localhost/db",
        entra_tenant_id=TENANT,
        entra_api_app_id_uri=app_id_uri,
    )


def test_both_audience_spellings_are_accepted() -> None:
    # Entra uses the App ID URI or the bare GUID depending on accessTokenAcceptedVersion.
    audiences = _settings(f"api://{CLIENT}").entra_accepted_audiences
    assert audiences == [f"api://{CLIENT}", CLIENT]


def test_a_custom_app_id_uri_yields_only_itself() -> None:
    # A host-style URI has no bare-GUID form to derive.
    assert _settings("api://meetings.providend.com/app").entra_accepted_audiences == [
        "api://meetings.providend.com/app"
    ]


def test_both_issuer_versions_are_accepted_for_this_tenant() -> None:
    issuers = _settings(f"api://{CLIENT}").entra_accepted_issuers
    assert issuers == [
        f"https://login.microsoftonline.com/{TENANT}/v2.0",
        f"https://sts.windows.net/{TENANT}/",
    ]


def test_issuers_are_pinned_to_the_configured_tenant() -> None:
    # The whole point of checking iss: another tenant's issuer must never match.
    for issuer in _settings(f"api://{CLIENT}").entra_accepted_issuers:
        assert TENANT in issuer
        assert "common" not in issuer
