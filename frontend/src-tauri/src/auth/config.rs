//! Resolves Entra settings and endpoints. Per-environment IDs come from
//! [`crate::environment`]; `MEETILY_AUTH_*` env vars override them.

use anyhow::{Context, Result};

use crate::environment::Environment;

/// OIDC scopes only, which are resource-agnostic. No Graph scope: a token has one `aud`, so one
/// request cannot cover two resources, and nothing here calls Graph.
const SCOPES: &[&str] = &["openid", "profile", "email", "offline_access"];

/// Scope exposed by our own API registration, and the one resource the token is minted for.
const API_SCOPE_SUFFIX: &str = "user_impersonation";

#[derive(Debug, Clone)]
pub struct AuthConfig {
    pub tenant_id: String,
    pub client_id: String,
}

impl AuthConfig {
    /// Errors rather than returning a partial config, so a missing value surfaces at sign-in.
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

    /// Assumes the default App ID URI `api://<client_id>`; a custom one must be mirrored here.
    pub fn api_scope(&self) -> String {
        format!("api://{}/{}", self.client_id, API_SCOPE_SUFFIX)
    }

    pub fn scope_param(&self) -> String {
        let mut scopes: Vec<String> = SCOPES.iter().map(|s| s.to_string()).collect();
        scopes.push(self.api_scope());
        scopes.join(" ")
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
    fn scope_param_requests_our_own_api() {
        let cfg = AuthConfig {
            tenant_id: "t".into(),
            client_id: "abc-123".into(),
        };
        // Without this scope the token's audience is Microsoft Graph, which the backend refuses.
        assert!(cfg.scope_param().contains("api://abc-123/user_impersonation"));
    }

    #[test]
    fn scope_param_names_exactly_one_resource() {
        let cfg = AuthConfig {
            tenant_id: "t".into(),
            client_id: "abc-123".into(),
        };
        let scopes = cfg.scope_param();
        // A token carries one `aud`, so a Graph scope here would displace our own.
        for graph_scope in ["User.Read", "Mail.Read", "https://graph.microsoft.com"] {
            assert!(
                !scopes.contains(graph_scope),
                "{scopes} must not request the Graph resource"
            );
        }
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
