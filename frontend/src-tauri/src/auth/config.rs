//! Resolves Entra settings and endpoints. Per-environment IDs come from
//! [`crate::environment`]; `MEETILY_AUTH_*` env vars override them.

use anyhow::{Context, Result};

use crate::environment::Environment;

/// `offline_access` yields the refresh token; without it the session dies hourly.
const SCOPES: &[&str] = &["openid", "profile", "email", "offline_access", "User.Read"];

#[derive(Debug, Clone)]
pub struct AuthConfig {
    pub tenant_id: String,
    pub client_id: String,
}

impl AuthConfig {
    /// Errors rather than returning a partial config, so a missing value surfaces
    /// clearly at sign-in instead of as an opaque Entra redirect error.
    pub fn resolve() -> Result<Self> {
        let env = Environment::current();
        let registered = env.entra();

        let tenant_id = env_or_const("MEETILY_AUTH_TENANT_ID", registered.tenant_id)
            .with_context(|| format!("Entra tenant ID is not configured for the '{env}' environment. Set MEETILY_AUTH_TENANT_ID, or fill it in under Environment::{env:?} in src/environment.rs"))?;
        let client_id = env_or_const("MEETILY_AUTH_CLIENT_ID", registered.client_id)
            .with_context(|| format!("Entra client ID is not configured for the '{env}' environment. Set MEETILY_AUTH_CLIENT_ID, or fill it in under Environment::{env:?} in src/environment.rs"))?;

        Ok(Self {
            tenant_id,
            client_id,
        })
    }

    /// True when both IDs are present.
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
