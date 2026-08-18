//! Typed HTTP client for the Providend Meeting Assistant backend.

use std::time::Duration;

use anyhow::{anyhow, Context, Result};
use serde::de::DeserializeOwned;
use serde::Serialize;

use crate::auth::commands::access_token;
use crate::environment::Environment;

const REQUEST_TIMEOUT: Duration = Duration::from_secs(30);

/// Reasons a backend call can fail that the caller may want to distinguish.
#[derive(Debug)]
pub enum BackendError {
    /// No backend configured for this environment -- the app is running purely locally.
    NotConfigured,
    /// Not signed in, or the stored session could not be refreshed.
    NotAuthenticated(String),
    /// The server rejected our token. Usually the access token's audience is wrong, which means
    /// the app is not requesting the API scope (see `auth::config::api_scope`).
    Unauthorized(String),
    /// Any other transport or server-side failure.
    Failed(String),
}

impl std::fmt::Display for BackendError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NotConfigured => write!(f, "no backend is configured for this environment"),
            Self::NotAuthenticated(m) => write!(f, "not signed in: {m}"),
            Self::Unauthorized(m) => write!(f, "backend rejected the token: {m}"),
            Self::Failed(m) => write!(f, "backend request failed: {m}"),
        }
    }
}

pub struct BackendClient {
    base_url: String,
    http: reqwest::Client,
}

impl BackendClient {
    /// Builds a client for the running environment, or `None` when no backend is configured.
    pub fn for_current_environment() -> Option<Self> {
        let base_url = Environment::current().api_base_url()?;
        let http = reqwest::Client::builder()
            .timeout(REQUEST_TIMEOUT)
            .build()
            .ok()?;
        Some(Self { base_url, http })
    }

    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    /// GET a JSON resource, authenticated.
    pub async fn get<T: DeserializeOwned>(&self, path: &str) -> Result<T, BackendError> {
        self.send::<(), T>(reqwest::Method::GET, path, None).await
    }

    /// POST a JSON body and decode the JSON response, authenticated.
    pub async fn post<B: Serialize, T: DeserializeOwned>(
        &self,
        path: &str,
        body: &B,
    ) -> Result<T, BackendError> {
        self.send::<B, T>(reqwest::Method::POST, path, Some(body))
            .await
    }

    /// Unauthenticated liveness probe: skips the token so "unreachable" is distinguishable
    /// from "up but rejected us".
    pub async fn health(&self) -> Result<(), BackendError> {
        let url = format!("{}/health", self.base_url);
        let response = self
            .http
            .get(&url)
            .send()
            .await
            .map_err(|e| BackendError::Failed(format!("{url} unreachable: {e}")))?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(BackendError::Failed(format!(
                "{url} returned {}",
                response.status()
            )))
        }
    }

    async fn send<B: Serialize, T: DeserializeOwned>(
        &self,
        method: reqwest::Method,
        path: &str,
        body: Option<&B>,
    ) -> Result<T, BackendError> {
        let token = access_token()
            .await
            .map_err(|e| BackendError::NotAuthenticated(e.to_string()))?;

        let url = format!("{}{}", self.base_url, path);
        let mut request = self.http.request(method, &url).bearer_auth(token);
        if let Some(body) = body {
            request = request.json(body);
        }

        let response = request
            .send()
            .await
            .map_err(|e| BackendError::Failed(format!("{url}: {e}")))?;

        let status = response.status();
        if status == reqwest::StatusCode::UNAUTHORIZED {
            let detail = response.text().await.unwrap_or_default();
            return Err(BackendError::Unauthorized(detail));
        }
        if !status.is_success() {
            let detail = response.text().await.unwrap_or_default();
            return Err(BackendError::Failed(format!("{url} returned {status}: {detail}")));
        }

        response
            .json::<T>()
            .await
            .map_err(|e| BackendError::Failed(format!("{url} returned undecodable JSON: {e}")))
    }
}

/// Builds a client or explains why it could not be built.
pub fn require_client() -> Result<BackendClient, BackendError> {
    BackendClient::for_current_environment().ok_or(BackendError::NotConfigured)
}

/// Convenience for call sites that want anyhow rather than [`BackendError`].
#[allow(dead_code)]
pub fn client_or_anyhow() -> Result<BackendClient> {
    BackendClient::for_current_environment()
        .ok_or_else(|| anyhow!("no backend configured"))
        .context("backend client")
}
