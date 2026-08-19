//! Tauri commands for sign-in. A stored session counts as signed in even with an expired token,
//! so refresh failure is not fatal.

use tauri::command;
use tracing::{info, warn};

use super::config::AuthConfig;
use super::entra;
use super::session::{self, SessionInfo};

/// Returns the current sign-in state. Safe to call on every app start.
#[command]
pub async fn auth_get_session() -> Result<SessionInfo, String> {
    let configured = AuthConfig::is_configured();

    let stored = session::load().map_err(|e| e.to_string())?;
    let Some(current) = stored else {
        return Ok(SessionInfo::signed_out(configured));
    };

    if !current.needs_refresh() {
        return Ok(current.info(configured));
    }

    // Stay signed in if Entra is unreachable -- the user may be offline mid-meeting.
    match entra::refresh(&current).await {
        Ok(refreshed) => {
            if let Err(e) = session::store(&refreshed) {
                warn!("Refreshed session could not be persisted: {}", e);
            }
            Ok(refreshed.info(configured))
        }
        Err(e) => {
            warn!(
                "Could not refresh the Entra session, continuing with the stored one: {}",
                e
            );
            Ok(current.info(configured))
        }
    }
}

/// Runs the interactive browser sign-in and persists the resulting session.
#[command]
pub async fn auth_sign_in() -> Result<SessionInfo, String> {
    if !AuthConfig::is_configured() {
        return Err(
            "Sign-in is not configured yet. The Entra tenant and client IDs are missing."
                .to_string(),
        );
    }

    let session = entra::interactive_login().await.map_err(|e| e.to_string())?;
    session::store(&session).map_err(|e| e.to_string())?;

    info!(
        "Signed in as {}",
        session
            .account
            .username
            .as_deref()
            .unwrap_or(&session.account.oid)
    );

    // Startup seeding runs before anyone is signed in, so its push is rejected. Retry now that
    // there is a token.
    tauri::async_runtime::spawn(async {
        if let Err(e) = crate::summary::templates::seed_templates().await {
            warn!("Failed to seed summary templates after sign-in: {}", e);
        }
    });

    Ok(session.info(true))
}

/// Clears the stored session. Local meetings and recordings are untouched.
#[command]
pub async fn auth_sign_out() -> Result<SessionInfo, String> {
    session::clear().map_err(|e| e.to_string())?;
    info!("Signed out; cleared the stored Entra session");
    Ok(SessionInfo::signed_out(AuthConfig::is_configured()))
}

/// Returns a usable access token, refreshing if needed. Not a Tauri command: tokens must not
/// reach the webview.
#[allow(dead_code)]
pub async fn access_token() -> anyhow::Result<String> {
    use anyhow::Context;

    let current = session::load()?.context("not signed in")?;

    if !current.needs_refresh() {
        return Ok(current.access_token);
    }

    let refreshed = entra::refresh(&current).await?;
    session::store(&refreshed)?;
    Ok(refreshed.access_token)
}
