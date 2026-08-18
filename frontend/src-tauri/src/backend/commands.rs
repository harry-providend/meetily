//! Tauri commands for the backend connection.

use serde::{Deserialize, Serialize};
use tauri::command;

use crate::backend::client::{require_client, BackendError};

/// Result of a connectivity check, structured so the UI can say *which* step failed rather than
/// only "it didn't work".
#[derive(Debug, Serialize)]
pub struct BackendStatus {
    /// A backend URL is configured for this environment.
    pub configured: bool,
    pub base_url: Option<String>,
    /// `/health` answered -- the server is running and reachable.
    pub reachable: bool,
    /// An authenticated request succeeded, so the token's audience and signature are accepted.
    pub authenticated: bool,
    /// Meetings visible to the signed-in user; proves the query reached Postgres.
    pub meeting_count: Option<i64>,
    pub error: Option<String>,
}

impl BackendStatus {
    fn not_configured() -> Self {
        Self {
            configured: false,
            base_url: None,
            reachable: false,
            authenticated: false,
            meeting_count: None,
            error: Some("no backend URL configured for this environment".to_string()),
        }
    }
}

#[derive(Debug, Deserialize)]
struct MeetingListResponse {
    total: i64,
}

/// Checks the app -> backend chain end to end and reports how far it got. An unreachable server
/// and a rejected token need very different fixes, so they are reported separately.
#[command]
pub async fn backend_status() -> Result<BackendStatus, String> {
    let client = match require_client() {
        Ok(client) => client,
        Err(BackendError::NotConfigured) => return Ok(BackendStatus::not_configured()),
        Err(other) => return Err(other.to_string()),
    };

    let mut status = BackendStatus {
        configured: true,
        base_url: Some(client.base_url().to_string()),
        reachable: false,
        authenticated: false,
        meeting_count: None,
        error: None,
    };

    if let Err(e) = client.health().await {
        status.error = Some(e.to_string());
        return Ok(status);
    }
    status.reachable = true;

    match client
        .get::<MeetingListResponse>("/api/v1/meetings?page=1&page_size=1")
        .await
    {
        Ok(list) => {
            status.authenticated = true;
            status.meeting_count = Some(list.total);
        }
        Err(e) => status.error = Some(e.to_string()),
    }

    Ok(status)
}
