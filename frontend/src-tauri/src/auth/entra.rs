//! Entra authorization-code + PKCE flow, through the system browser so the user sees the genuine
//! Microsoft origin and tenant policy applies.

use anyhow::{bail, Context, Result};
use chrono::{Duration, Utc};
use serde::Deserialize;
use std::collections::HashMap;
use std::time::Duration as StdDuration;
use tracing::{info, warn};
use url::Url;

use super::config::AuthConfig;
use super::loopback::{Callback, LoopbackServer};
use super::pkce::{random_state, Pkce};
use super::session::{account_from_id_token, AuthSession};

/// Token endpoint requests are quick; a long hang here means something is wrong.
const TOKEN_REQUEST_TIMEOUT: StdDuration = StdDuration::from_secs(30);

#[derive(Debug, Deserialize)]
struct TokenResponse {
    access_token: String,
    refresh_token: Option<String>,
    id_token: Option<String>,
    /// Access token lifetime in seconds.
    expires_in: Option<i64>,
}

#[derive(Debug, Deserialize)]
struct TokenErrorResponse {
    error: Option<String>,
    error_description: Option<String>,
}

/// Runs the interactive sign-in. The loopback wait is blocking, hence the spawned task.
pub async fn interactive_login() -> Result<AuthSession> {
    let config = AuthConfig::resolve()?;

    let server = LoopbackServer::bind()?;
    let redirect_uri = server.redirect_uri();
    let pkce = Pkce::generate();
    let state = random_state();

    let auth_url = build_authorize_url(&config, &redirect_uri, &pkce.challenge, &state)?;

    info!("Opening system browser for Entra sign-in");
    open_in_browser(auth_url.as_str())?;

    let expected_state = state.clone();
    let callback = tokio::task::spawn_blocking(move || {
        server.wait_for_callback(&expected_state)
    })
    .await
    .context("sign-in listener task failed")??;

    let code = match callback {
        Callback::Code(code) => code,
        Callback::Failed { error, description } => {
            // access_denied is the ordinary "user closed the dialog" case.
            bail!(
                "sign-in was not completed ({}){}",
                error,
                if description.is_empty() {
                    String::new()
                } else {
                    format!(": {}", description)
                }
            );
        }
    };

    let tokens = redeem_code(&config, &redirect_uri, &code, &pkce.verifier).await?;
    session_from_tokens(tokens)
}

/// Exchanges a refresh token for a new access token.
pub async fn refresh(session: &AuthSession) -> Result<AuthSession> {
    let config = AuthConfig::resolve()?;
    let refresh_token = session
        .refresh_token
        .as_deref()
        .context("stored session has no refresh token; interactive sign-in is required")?;

    let mut form = HashMap::new();
    form.insert("client_id", config.client_id.as_str());
    form.insert("grant_type", "refresh_token");
    form.insert("refresh_token", refresh_token);
    let scope = config.scope_param();
    form.insert("scope", scope.as_str());

    let tokens = post_token_request(&config, form).await?;

    // A refresh may omit id_token, meaning identity is unchanged.
    let account = tokens
        .id_token
        .as_deref()
        .and_then(|token| match account_from_id_token(token) {
            Ok(account) => Some(account),
            Err(e) => {
                warn!("Ignoring unreadable ID token in refresh response: {}", e);
                None
            }
        })
        .unwrap_or_else(|| session.account.clone());

    let lifetime = tokens.expires_in.unwrap_or(3600).max(0);

    Ok(AuthSession {
        access_token: tokens.access_token,
        // Entra may omit a new refresh token; the existing one must be carried forward.
        refresh_token: tokens
            .refresh_token
            .or_else(|| session.refresh_token.clone()),
        expires_at: Utc::now() + Duration::seconds(lifetime),
        account,
    })
}

fn build_authorize_url(
    config: &AuthConfig,
    redirect_uri: &str,
    code_challenge: &str,
    state: &str,
) -> Result<Url> {
    let mut url = Url::parse(&config.authorize_endpoint())
        .context("failed to build the Entra authorize URL")?;

    url.query_pairs_mut()
        .append_pair("client_id", &config.client_id)
        .append_pair("response_type", "code")
        .append_pair("redirect_uri", redirect_uri)
        .append_pair("response_mode", "query")
        .append_pair("scope", &config.scope_param())
        .append_pair("state", state)
        .append_pair("code_challenge", code_challenge)
        .append_pair("code_challenge_method", "S256");

    Ok(url)
}

async fn redeem_code(
    config: &AuthConfig,
    redirect_uri: &str,
    code: &str,
    code_verifier: &str,
) -> Result<TokenResponse> {
    let mut form = HashMap::new();
    form.insert("client_id", config.client_id.as_str());
    form.insert("grant_type", "authorization_code");
    form.insert("code", code);
    form.insert("redirect_uri", redirect_uri);
    form.insert("code_verifier", code_verifier);
    let scope = config.scope_param();
    form.insert("scope", scope.as_str());

    post_token_request(config, form).await
}

async fn post_token_request(
    config: &AuthConfig,
    form: HashMap<&str, &str>,
) -> Result<TokenResponse> {
    let client = reqwest::Client::builder()
        .timeout(TOKEN_REQUEST_TIMEOUT)
        .build()
        .context("failed to build the token HTTP client")?;

    let response = client
        .post(config.token_endpoint())
        .form(&form)
        .send()
        .await
        .context("failed to reach the Entra token endpoint")?;

    let status = response.status();
    let body = response
        .text()
        .await
        .context("failed to read the Entra token response")?;

    if !status.is_success() {
        // error_description carries the AADSTS code, which is the actionable part.
        let parsed: Option<TokenErrorResponse> = serde_json::from_str(&body).ok();
        let detail = parsed
            .and_then(|e| e.error_description.or(e.error))
            .unwrap_or_else(|| body.chars().take(300).collect());
        bail!("Entra rejected the token request (HTTP {}): {}", status, detail);
    }

    serde_json::from_str(&body).context("failed to parse the Entra token response")
}

fn session_from_tokens(tokens: TokenResponse) -> Result<AuthSession> {
    let id_token = tokens
        .id_token
        .as_deref()
        .context("token response contained no ID token; is the 'openid' scope granted?")?;

    let account = account_from_id_token(id_token)?;
    let lifetime = tokens.expires_in.unwrap_or(3600).max(0);

    Ok(AuthSession {
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        expires_at: Utc::now() + Duration::seconds(lifetime),
        account,
    })
}

fn open_in_browser(url: &str) -> Result<()> {
    use std::process::Command;

    let result = if cfg!(target_os = "windows") {
        // `start` treats a lone quoted argument as the window title, hence the empty one.
        Command::new("cmd").args(["/C", "start", "", url]).spawn()
    } else if cfg!(target_os = "macos") {
        Command::new("open").arg(url).spawn()
    } else {
        Command::new("xdg-open").arg(url).spawn()
    };

    result
        .map(|_| ())
        .context("failed to open the system browser for sign-in")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn config() -> AuthConfig {
        AuthConfig {
            tenant_id: "tenant-123".into(),
            client_id: "client-456".into(),
        }
    }

    fn params(url: &Url) -> HashMap<String, String> {
        url.query_pairs()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect()
    }

    #[test]
    fn authorize_url_carries_the_pkce_challenge() {
        let url =
            build_authorize_url(&config(), "http://localhost:5555", "challenge-abc", "state-xyz")
                .unwrap();
        let p = params(&url);

        assert_eq!(p.get("code_challenge").unwrap(), "challenge-abc");
        // S256 rather than "plain" -- plain would defeat the point of PKCE.
        assert_eq!(p.get("code_challenge_method").unwrap(), "S256");
        assert_eq!(p.get("response_type").unwrap(), "code");
        assert_eq!(p.get("state").unwrap(), "state-xyz");
        assert_eq!(p.get("redirect_uri").unwrap(), "http://localhost:5555");
        assert_eq!(p.get("client_id").unwrap(), "client-456");
    }

    #[test]
    fn authorize_url_targets_the_configured_tenant() {
        let url = build_authorize_url(&config(), "http://localhost:1", "c", "s").unwrap();
        assert!(url.as_str().starts_with(
            "https://login.microsoftonline.com/tenant-123/oauth2/v2.0/authorize"
        ));
    }

    #[test]
    fn authorize_url_never_contains_a_client_secret() {
        let url = build_authorize_url(&config(), "http://localhost:1", "c", "s").unwrap();
        let p = params(&url);
        assert!(!p.contains_key("client_secret"));
    }

    #[test]
    fn session_derives_expiry_from_expires_in() {
        let tokens = TokenResponse {
            access_token: "at".into(),
            refresh_token: Some("rt".into()),
            id_token: Some(test_id_token()),
            expires_in: Some(600),
        };

        let before = Utc::now();
        let session = session_from_tokens(tokens).unwrap();
        let delta = (session.expires_at - before).num_seconds();
        assert!((595..=605).contains(&delta), "unexpected delta {}", delta);
    }

    #[test]
    fn session_defaults_expiry_when_absent() {
        let tokens = TokenResponse {
            access_token: "at".into(),
            refresh_token: None,
            id_token: Some(test_id_token()),
            expires_in: None,
        };
        let session = session_from_tokens(tokens).unwrap();
        assert!(session.expires_at > Utc::now());
    }

    #[test]
    fn session_requires_an_id_token() {
        let tokens = TokenResponse {
            access_token: "at".into(),
            refresh_token: None,
            id_token: None,
            expires_in: Some(60),
        };
        assert!(session_from_tokens(tokens).is_err());
    }

    fn test_id_token() -> String {
        use base64::engine::general_purpose::URL_SAFE_NO_PAD;
        use base64::Engine;
        let payload = serde_json::json!({ "oid": "o", "tid": "t" }).to_string();
        format!("h.{}.s", URL_SAFE_NO_PAD.encode(payload))
    }
}
