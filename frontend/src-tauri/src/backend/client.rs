//! Typed HTTP client for the Providend Meeting Assistant backend.

use std::sync::OnceLock;
use std::time::Duration;

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
    /// Usually a wrong audience, meaning the API scope was not requested.
    Unauthorized(String),
    /// The server does not distinguish absent from someone else's, so neither can we.
    NotFound,
    /// Any other transport or server-side failure.
    Failed(String),
}

impl std::fmt::Display for BackendError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NotConfigured => write!(f, "no backend is configured for this environment"),
            Self::NotAuthenticated(m) => write!(f, "not signed in: {m}"),
            Self::Unauthorized(m) => write!(f, "backend rejected the token: {m}"),
            Self::NotFound => write!(f, "not found"),
            Self::Failed(m) => write!(f, "backend request failed: {m}"),
        }
    }
}

pub struct BackendClient {
    base_url: String,
    http: reqwest::Client,
}

impl BackendClient {
    /// `None` when no backend is configured for this environment.
    fn for_current_environment() -> Option<Self> {
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
        self.get_with_query(path, &[]).await
    }

    /// GET with query parameters. reqwest percent-encodes them, so values may contain anything.
    pub async fn get_with_query<T: DeserializeOwned>(
        &self,
        path: &str,
        query: &[(&str, String)],
    ) -> Result<T, BackendError> {
        let (url, response) = self
            .dispatch::<()>(reqwest::Method::GET, path, None, query)
            .await?;
        response
            .json::<T>()
            .await
            .map_err(|e| BackendError::Failed(format!("{url} returned undecodable JSON: {e}")))
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

    /// PUT a JSON body and decode the JSON response, authenticated.
    pub async fn put<B: Serialize, T: DeserializeOwned>(
        &self,
        path: &str,
        body: &B,
    ) -> Result<T, BackendError> {
        self.send::<B, T>(reqwest::Method::PUT, path, Some(body))
            .await
    }

    /// PATCH a JSON body and decode the JSON response, authenticated.
    pub async fn patch<B: Serialize, T: DeserializeOwned>(
        &self,
        path: &str,
        body: &B,
    ) -> Result<T, BackendError> {
        self.send::<B, T>(reqwest::Method::PATCH, path, Some(body))
            .await
    }

    /// DELETE a resource, authenticated. The server answers 204, so there is nothing to decode.
    pub async fn delete(&self, path: &str) -> Result<(), BackendError> {
        self.send_discarding_body::<()>(reqwest::Method::DELETE, path, None)
            .await
    }

    /// Unauthenticated, so "unreachable" stays distinguishable from "up but rejected us".
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
        let (url, response) = self.dispatch(method, path, body, &[]).await?;
        response
            .json::<T>()
            .await
            .map_err(|e| BackendError::Failed(format!("{url} returned undecodable JSON: {e}")))
    }

    async fn send_discarding_body<B: Serialize>(
        &self,
        method: reqwest::Method,
        path: &str,
        body: Option<&B>,
    ) -> Result<(), BackendError> {
        self.dispatch(method, path, body, &[]).await.map(|_| ())
    }

    /// Returns the URL alongside the response so callers can name it in their errors.
    async fn dispatch<B: Serialize>(
        &self,
        method: reqwest::Method,
        path: &str,
        body: Option<&B>,
        query: &[(&str, String)],
    ) -> Result<(String, reqwest::Response), BackendError> {
        let token = access_token()
            .await
            .map_err(|e| BackendError::NotAuthenticated(e.to_string()))?;

        let url = format!("{}{}", self.base_url, path);
        let mut request = self.http.request(method, &url).bearer_auth(token);
        if !query.is_empty() {
            request = request.query(query);
        }
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
        if status == reqwest::StatusCode::NOT_FOUND {
            return Err(BackendError::NotFound);
        }
        if !status.is_success() {
            let detail = response.text().await.unwrap_or_default();
            return Err(BackendError::Failed(format!(
                "{url} returned {status}: {detail}"
            )));
        }

        Ok((url, response))
    }
}

/// One client for the whole process: `reqwest::Client` owns the connection pool and the TLS
/// session cache, so building one per call would re-handshake and discard keep-alive every time.
static CLIENT: OnceLock<Option<BackendClient>> = OnceLock::new();

/// The shared client, or why there isn't one.
pub fn require_client() -> Result<&'static BackendClient, BackendError> {
    CLIENT
        .get_or_init(BackendClient::for_current_environment)
        .as_ref()
        .ok_or(BackendError::NotConfigured)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_client_is_built_once_and_shared() {
        let first: *const _ = CLIENT.get_or_init(BackendClient::for_current_environment);
        let second: *const _ = CLIENT.get_or_init(BackendClient::for_current_environment);
        assert_eq!(first, second);
    }
}
