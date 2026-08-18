//! Session state in the OS keychain. Tokens never reach a plaintext store or the webview; the
//! frontend gets identity only.

use anyhow::{Context, Result};
use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use base64::Engine;
use chrono::{DateTime, Duration, Utc};
use keyring::Entry;
use serde::{Deserialize, Serialize};
use tracing::{debug, warn};

const KEYCHAIN_ACCOUNT: &str = "entra-session";

/// Refresh this far before actual expiry, so a request does not race the clock.
const REFRESH_SKEW: i64 = 120;

/// The signed-in user, as asserted by the ID token.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Account {
    /// Immutable per-tenant user ID -- the value to key data on, unlike email.
    pub oid: String,
    pub tid: String,
    pub name: Option<String>,
    /// Usually the UPN / email address.
    pub username: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthSession {
    pub access_token: String,
    pub refresh_token: Option<String>,
    pub expires_at: DateTime<Utc>,
    pub account: Account,
}

/// The safe projection handed to the frontend. No tokens.
#[derive(Debug, Clone, Serialize)]
pub struct SessionInfo {
    pub signed_in: bool,
    pub account: Option<Account>,
    /// Refresh is due. The app stays usable regardless.
    pub needs_refresh: bool,
    /// False when the Entra IDs are unset, so the UI can say so.
    pub configured: bool,
}

impl SessionInfo {
    pub fn signed_out(configured: bool) -> Self {
        Self {
            signed_in: false,
            account: None,
            needs_refresh: false,
            configured,
        }
    }
}

impl AuthSession {
    pub fn info(&self, configured: bool) -> SessionInfo {
        SessionInfo {
            signed_in: true,
            account: Some(self.account.clone()),
            needs_refresh: self.needs_refresh(),
            configured,
        }
    }

    pub fn needs_refresh(&self) -> bool {
        Utc::now() + Duration::seconds(REFRESH_SKEW) >= self.expires_at
    }
}

/// Persists the session, replacing any existing one.
pub fn store(session: &AuthSession) -> Result<()> {
    let json = serde_json::to_string(session).context("failed to serialize session")?;
    entry()?
        .set_password(&json)
        .context("failed to write the session to the OS keychain")?;
    debug!("Stored Entra session for {}", session.account.oid);
    Ok(())
}

/// Loads the stored session. A corrupt entry is cleared and treated as signed out.
pub fn load() -> Result<Option<AuthSession>> {
    let raw = match entry()?.get_password() {
        Ok(raw) => raw,
        Err(keyring::Error::NoEntry) => return Ok(None),
        Err(e) => return Err(e).context("failed to read the session from the OS keychain"),
    };

    match serde_json::from_str::<AuthSession>(&raw) {
        Ok(session) => Ok(Some(session)),
        Err(e) => {
            warn!("Discarding unreadable stored session: {}", e);
            let _ = clear();
            Ok(None)
        }
    }
}

/// Removes the stored session. Succeeds when there was nothing to remove.
pub fn clear() -> Result<()> {
    match entry()?.delete_credential() {
        Ok(()) => Ok(()),
        Err(keyring::Error::NoEntry) => Ok(()),
        Err(e) => Err(e).context("failed to clear the session from the OS keychain"),
    }
}

fn entry() -> Result<Entry> {
    // Per-environment, so a dev sign-in cannot overwrite the production session.
    let service = crate::environment::Environment::current().keychain_service();
    Entry::new(service, KEYCHAIN_ACCOUNT)
        .context("failed to open the OS keychain entry for sign-in")
}

/// Reads identity claims from an ID token. The signature is not verified: it came over TLS from
/// Entra and the claims only drive display. The backend does verify, against JWKS.
pub fn account_from_id_token(id_token: &str) -> Result<Account> {
    let payload = id_token
        .split('.')
        .nth(1)
        .context("ID token is not a well-formed JWT")?;

    let decoded = URL_SAFE_NO_PAD
        .decode(payload)
        .context("ID token payload is not valid base64url")?;

    #[derive(Deserialize)]
    struct Claims {
        oid: Option<String>,
        sub: Option<String>,
        tid: Option<String>,
        name: Option<String>,
        preferred_username: Option<String>,
        upn: Option<String>,
        email: Option<String>,
    }

    let claims: Claims =
        serde_json::from_slice(&decoded).context("ID token payload is not valid JSON")?;

    // oid is stable per tenant; sub is only stable per (user, application).
    let oid = claims
        .oid
        .or(claims.sub)
        .context("ID token contained neither an oid nor a sub claim")?;

    Ok(Account {
        oid,
        tid: claims.tid.unwrap_or_default(),
        name: claims.name,
        username: claims
            .preferred_username
            .or(claims.upn)
            .or(claims.email),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn id_token_with(payload: serde_json::Value) -> String {
        let encoded = URL_SAFE_NO_PAD.encode(payload.to_string());
        format!("header.{}.signature", encoded)
    }

    #[test]
    fn reads_identity_claims() {
        let token = id_token_with(serde_json::json!({
            "oid": "user-object-id",
            "tid": "tenant-id",
            "name": "Ada Lovelace",
            "preferred_username": "ada@providend.com",
        }));

        let account = account_from_id_token(&token).unwrap();
        assert_eq!(account.oid, "user-object-id");
        assert_eq!(account.tid, "tenant-id");
        assert_eq!(account.name.as_deref(), Some("Ada Lovelace"));
        assert_eq!(account.username.as_deref(), Some("ada@providend.com"));
    }

    #[test]
    fn prefers_oid_over_sub() {
        let token = id_token_with(serde_json::json!({ "oid": "the-oid", "sub": "the-sub" }));
        assert_eq!(account_from_id_token(&token).unwrap().oid, "the-oid");
    }

    #[test]
    fn falls_back_to_sub_when_oid_absent() {
        let token = id_token_with(serde_json::json!({ "sub": "the-sub" }));
        assert_eq!(account_from_id_token(&token).unwrap().oid, "the-sub");
    }

    #[test]
    fn falls_back_through_username_claims() {
        let token = id_token_with(serde_json::json!({ "oid": "o", "upn": "via-upn@x.com" }));
        assert_eq!(
            account_from_id_token(&token).unwrap().username.as_deref(),
            Some("via-upn@x.com")
        );

        let token = id_token_with(serde_json::json!({ "oid": "o", "email": "via-email@x.com" }));
        assert_eq!(
            account_from_id_token(&token).unwrap().username.as_deref(),
            Some("via-email@x.com")
        );
    }

    #[test]
    fn rejects_malformed_tokens() {
        assert!(account_from_id_token("not-a-jwt").is_err());
        assert!(account_from_id_token("header.!!!not-base64!!!.sig").is_err());
        // Valid JWT shape and base64, but no usable subject claim.
        assert!(account_from_id_token(&id_token_with(serde_json::json!({ "tid": "t" }))).is_err());
    }

    #[test]
    fn expiry_accounts_for_refresh_skew() {
        let account = Account {
            oid: "o".into(),
            tid: "t".into(),
            name: None,
            username: None,
        };

        let nearly_expired = AuthSession {
            access_token: "a".into(),
            refresh_token: None,
            // Inside the skew window, so a refresh is due before actual expiry.
            expires_at: Utc::now() + Duration::seconds(REFRESH_SKEW / 2),
            account: account.clone(),
        };
        assert!(nearly_expired.needs_refresh());

        let fresh = AuthSession {
            access_token: "a".into(),
            refresh_token: None,
            expires_at: Utc::now() + Duration::hours(1),
            account,
        };
        assert!(!fresh.needs_refresh());
    }

    #[test]
    fn session_info_never_carries_tokens() {
        let session = AuthSession {
            access_token: "super-secret-access-token".into(),
            refresh_token: Some("super-secret-refresh-token".into()),
            expires_at: Utc::now() + Duration::hours(1),
            account: Account {
                oid: "o".into(),
                tid: "t".into(),
                name: None,
                username: None,
            },
        };

        let serialized = serde_json::to_string(&session.info(true)).unwrap();
        assert!(!serialized.contains("super-secret-access-token"));
        assert!(!serialized.contains("super-secret-refresh-token"));
    }
}
