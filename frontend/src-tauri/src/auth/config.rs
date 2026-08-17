//! Entra ID application settings.
//!
//! The tenant and client IDs are identifiers, not credentials -- Entra treats a
//! desktop app as a *public client*, which by definition cannot hold a secret.
//! They are safe to commit.
//!
//! Resolution order: environment variable first (convenient for dev and for
//! pointing a build at a different tenant), then the compiled-in constant.

use anyhow::{Context, Result};

/// Directory (tenant) ID from the app registration's Overview blade.
pub const TENANT_ID: &str = "";

/// Application (client) ID from the app registration's Overview blade.
pub const CLIENT_ID: &str = "";

/// Scopes requested at sign-in.
///
/// `offline_access` is what yields a refresh token -- without it the session
/// dies when the access token expires (~1 hour) and the user is bounced back to
/// the browser. `User.Read` is only needed to read the signed-in user's own
/// profile.
const SCOPES: &[&str] = &["openid", "profile", "email", "offline_access", "User.Read"];

#[derive(Debug, Clone)]
pub struct AuthConfig {
    pub tenant_id: String,
    pub client_id: String,
}

impl AuthConfig {
    /// Reads configuration, preferring environment overrides.
    ///
    /// Returns an error rather than a partial config when either value is
    /// missing, so the failure surfaces at sign-in with a clear message instead
    /// of as an opaque redirect error from Entra.
    pub fn resolve() -> Result<Self> {
        let tenant_id = env_or_const("MEETILY_AUTH_TENANT_ID", TENANT_ID)
            .context("Entra tenant ID is not configured. Set MEETILY_AUTH_TENANT_ID or fill in TENANT_ID in src/auth/config.rs")?;
        let client_id = env_or_const("MEETILY_AUTH_CLIENT_ID", CLIENT_ID)
            .context("Entra client ID is not configured. Set MEETILY_AUTH_CLIENT_ID or fill in CLIENT_ID in src/auth/config.rs")?;

        Ok(Self {
            tenant_id,
            client_id,
        })
    }

    /// True when both IDs are present, so the UI can explain that sign-in is
    /// unconfigured instead of failing mid-flow.
    pub fn is_configured() -> bool {
        Self::resolve().is_ok()
    }

    pub fn authorize_endpoint(&self) -> String {
        format!(
            "https://login.microsoftonline.com/{}/oauth2/v2.0/authorize",
            self.tenant_id
        )
    }

    pub fn token_endpoint(&self) -> String {
        format!(
            "https://login.microsoftonline.com/{}/oauth2/v2.0/token",
            self.tenant_id
        )
    }

    pub fn scope_param(&self) -> String {
        SCOPES.join(" ")
    }
}

fn env_or_const(var: &str, fallback: &str) -> Option<String> {
    let from_env = std::env::var(var).ok().filter(|v| !v.trim().is_empty());
    from_env.or_else(|| {
        let trimmed = fallback.trim();
        (!trimmed.is_empty()).then(|| trimmed.to_string())
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scope_param_requests_a_refresh_token() {
        let cfg = AuthConfig {
            tenant_id: "t".into(),
            client_id: "c".into(),
        };
        // Losing offline_access silently downgrades the session to ~1 hour.
        assert!(cfg.scope_param().contains("offline_access"));
    }

    #[test]
    fn endpoints_are_tenant_scoped() {
        let cfg = AuthConfig {
            tenant_id: "contoso".into(),
            client_id: "c".into(),
        };
        assert!(cfg.authorize_endpoint().contains("/contoso/"));
        assert!(cfg.token_endpoint().contains("/contoso/"));
    }

    #[test]
    fn blank_constants_are_treated_as_unset() {
        assert_eq!(env_or_const("MEETILY_TEST_UNSET_VAR_XYZ", "   "), None);
        assert_eq!(
            env_or_const("MEETILY_TEST_UNSET_VAR_XYZ", " value "),
            Some("value".to_string())
        );
    }
}
