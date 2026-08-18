from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed config from env / .env. Non-secret identifiers only: this is a JWT resource
    server, not an identity provider."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    entra_tenant_id: str
    entra_api_app_id_uri: str

    @property
    def entra_jwks_uri(self) -> str:
        return f"https://login.microsoftonline.com/{self.entra_tenant_id}/discovery/v2.0/keys"

    @property
    def entra_expected_issuer(self) -> str:
        return f"https://login.microsoftonline.com/{self.entra_tenant_id}/v2.0"

    @property
    def entra_accepted_audiences(self) -> list[str]:
        """Both spellings of this API's audience: Entra uses the App ID URI or the bare GUID
        depending on accessTokenAcceptedVersion. Same application either way."""
        audiences = [self.entra_api_app_id_uri]
        bare = self.entra_api_app_id_uri.removeprefix("api://")
        if bare != self.entra_api_app_id_uri and "/" not in bare:
            audiences.append(bare)
        return audiences


@lru_cache
def get_settings() -> Settings:
    return Settings()
