//! Tauri commands for sign-in.
//!
//! Offline behaviour is the important design point here. The app records and
//! transcribes locally and must keep working without a network, so a *stored*
//! session counts as signed in even when its access token has expired. Refresh
//! is attempted opportunistically and its failure is not fatal. Only the absence
//! of any stored session sends the user to the sign-in screen.
//!
//! Sign-in state is therefore a gate on app entry, not access control -- local
//! data remains on disk regardless. Real enforcement arrives with the backend.

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

    // Token is due for renewal. Try, but stay signed in if we cannot reach
    // Entra -- the user may simply be offline mid-meeting.
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

    Ok(session.info(true))
}

/// Clears the stored session.
///
/// Local meetings, transcripts, and recordings are untouched -- this signs out,
/// it does not wipe the device.
#[command]
pub async fn auth_sign_out() -> Result<SessionInfo, String> {
    session::clear().map_err(|e| e.to_string())?;
    info!("Signed out; cleared the stored Entra session");
    Ok(SessionInfo::signed_out(AuthConfig::is_configured()))
}

/// Returns a usable access token, refreshing first if needed.
///
/// Intentionally *not* a Tauri command: tokens must not cross into the webview.
/// This is the seam the backend client will call once Phase 2 lands.
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
