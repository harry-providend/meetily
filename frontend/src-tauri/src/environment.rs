//! Build environment: dev, staging, prod. The bundle identifier decides which is running, so it
//! cannot drift; precedence is `MEETILY_ENV`, then identifier, then the debug/release default.
//! A distinct identifier also gives each environment its own OS data directory, isolating the
//! database, models and preferences for free. Recordings and keychain entries are suffixed below.

use std::fmt;
use std::sync::OnceLock;
use tracing::{info, warn};

/// Must match `identifier` in `tauri.conf.json`.
const PROD_IDENTIFIER: &str = "com.providend.meetingassistant";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Environment {
    Dev,
    Staging,
    Prod,
}

/// Entra IDs are identifiers, not credentials -- a desktop app is a public client
/// and cannot hold a secret -- so they are safe to commit.
#[derive(Debug, Clone, Copy)]
pub struct EntraSettings {
    pub tenant_id: &'static str,
    pub client_id: &'static str,
}

static DETECTED: OnceLock<Environment> = OnceLock::new();

impl Environment {
    pub fn current() -> Self {
        // Not cached: an explicit override should win even if something read the
        // environment before startup detection ran.
        if let Some(overridden) = runtime_override() {
            return overridden;
        }
        DETECTED.get().copied().unwrap_or_else(build_profile_default)
    }

    /// Called once during app setup, as early as possible.
    pub fn init_from_identifier(identifier: &str) {
        match Self::from_identifier(identifier) {
            Some(env) => {
                let _ = DETECTED.set(env);
                match runtime_override() {
                    Some(overridden) if overridden != env => warn!(
                        "MEETILY_ENV={overridden} overrides identifier '{identifier}' ({env}): \
                         settings are {overridden}'s but data directories stay {env}'s."
                    ),
                    _ => info!("Environment: {env} (identifier '{identifier}')"),
                }
            }
            None => warn!(
                "Unrecognised bundle identifier '{identifier}'; using '{}'.",
                Self::current()
            ),
        }
    }

    pub fn from_identifier(identifier: &str) -> Option<Self> {
        match identifier {
            PROD_IDENTIFIER => Some(Self::Prod),
            other if other == format!("{PROD_IDENTIFIER}.dev") => Some(Self::Dev),
            other if other == format!("{PROD_IDENTIFIER}.staging") => Some(Self::Staging),
            _ => None,
        }
    }

    pub fn parse(raw: &str) -> Option<Self> {
        match raw.trim().to_ascii_lowercase().as_str() {
            "dev" | "development" | "local" => Some(Self::Dev),
            "staging" | "stage" | "uat" => Some(Self::Staging),
            "prod" | "production" => Some(Self::Prod),
            _ => None,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Dev => "dev",
            Self::Staging => "staging",
            Self::Prod => "prod",
        }
    }

    /// Badge text. `None` for prod, which should look like the plain product.
    pub fn label(&self) -> Option<&'static str> {
        match self {
            Self::Dev => Some("DEV"),
            Self::Staging => Some("STAGING"),
            Self::Prod => None,
        }
    }

    pub fn is_production(&self) -> bool {
        matches!(self, Self::Prod)
    }

    pub fn bundle_identifier(&self) -> String {
        match self {
            Self::Prod => PROD_IDENTIFIER.to_string(),
            Self::Dev => format!("{PROD_IDENTIFIER}.dev"),
            Self::Staging => format!("{PROD_IDENTIFIER}.staging"),
        }
    }

    /// Recordings live outside the app-data directory, so they need an explicit
    /// suffix. Prod keeps the original name so existing recordings still resolve.
    pub fn recordings_dir_name(&self) -> &'static str {
        match self {
            Self::Dev => "meetily-recordings-dev",
            Self::Staging => "meetily-recordings-staging",
            Self::Prod => "meetily-recordings",
        }
    }

    /// Suffixed so a dev sign-in cannot overwrite the production session.
    pub fn keychain_service(&self) -> &'static str {
        match self {
            Self::Dev => "com.providend.meetingassistant.dev",
            Self::Staging => "com.providend.meetingassistant.staging",
            Self::Prod => PROD_IDENTIFIER,
        }
    }

    /// From `.env.<env>`. `MEETILY_AUTH_*` still overrides at runtime.
    pub fn entra(&self) -> EntraSettings {
        match self {
            Self::Dev => EntraSettings {
                tenant_id: env!("ENV_DEV_AUTH_TENANT_ID"),
                client_id: env!("ENV_DEV_AUTH_CLIENT_ID"),
            },
            Self::Staging => EntraSettings {
                tenant_id: env!("ENV_STAGING_AUTH_TENANT_ID"),
                client_id: env!("ENV_STAGING_AUTH_CLIENT_ID"),
            },
            Self::Prod => EntraSettings {
                tenant_id: env!("ENV_PROD_AUTH_TENANT_ID"),
                client_id: env!("ENV_PROD_AUTH_CLIENT_ID"),
            },
        }
    }

    /// Our backend's base URL, or `None` when this environment has none configured. Owned rather
    /// than `&'static str` because `MEETILY_API_BASE_URL` can override it at runtime.
    pub fn api_base_url(&self) -> Option<String> {
        if let Ok(from_env) = std::env::var("MEETILY_API_BASE_URL") {
            let trimmed = from_env.trim();
            if !trimmed.is_empty() {
                return Some(trimmed.trim_end_matches('/').to_string());
            }
        }

        let raw = match self {
            Self::Dev => env!("ENV_DEV_API_BASE_URL"),
            Self::Staging => env!("ENV_STAGING_API_BASE_URL"),
            Self::Prod => env!("ENV_PROD_API_BASE_URL"),
        };
        let trimmed = raw.trim().trim_end_matches('/');
        (!trimmed.is_empty()).then(|| trimmed.to_string())
    }
}

impl fmt::Display for Environment {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

fn runtime_override() -> Option<Environment> {
    std::env::var("MEETILY_ENV")
        .ok()
        .and_then(|raw| Environment::parse(&raw))
}

fn build_profile_default() -> Environment {
    if cfg!(debug_assertions) {
        Environment::Dev
    } else {
        Environment::Prod
    }
}

/// Tags the window title for non-prod builds. Done at runtime because `--config` merge-patches
/// arrays wholesale, so an `app.windows` overlay would discard the base size and theme.
pub fn apply_window_title<R: tauri::Runtime>(app: &tauri::AppHandle<R>) {
    use tauri::Manager;

    let Some(label) = Environment::current().label() else {
        return;
    };

    for window in app.webview_windows().values() {
        let current = window.title().unwrap_or_default();
        if current.contains(label) {
            continue;
        }
        if let Err(e) = window.set_title(&format!("{current} ({label})")) {
            warn!("Could not tag the window title with the environment: {e}");
        }
    }
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct EnvironmentInfo {
    pub name: String,
    pub label: Option<String>,
    pub is_production: bool,
}

#[tauri::command]
pub fn get_environment() -> EnvironmentInfo {
    let env = Environment::current();
    EnvironmentInfo {
        name: env.as_str().to_string(),
        label: env.label().map(str::to_string),
        is_production: env.is_production(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn maps_identifiers_to_environments() {
        assert_eq!(
            Environment::from_identifier("com.providend.meetingassistant"),
            Some(Environment::Prod)
        );
        assert_eq!(
            Environment::from_identifier("com.providend.meetingassistant.dev"),
            Some(Environment::Dev)
        );
        assert_eq!(
            Environment::from_identifier("com.providend.meetingassistant.staging"),
            Some(Environment::Staging)
        );
    }

    #[test]
    fn unrecognised_identifiers_are_not_guessed() {
        // Upstream's identifier must never be mistaken for one of ours.
        assert_eq!(Environment::from_identifier("com.meetily.ai"), None);
        assert_eq!(Environment::from_identifier(""), None);
        assert_eq!(
            Environment::from_identifier("com.providend.meetingassistant.qa"),
            None
        );
    }

    #[test]
    fn identifier_mapping_round_trips() {
        for env in [Environment::Dev, Environment::Staging, Environment::Prod] {
            assert_eq!(
                Environment::from_identifier(&env.bundle_identifier()),
                Some(env),
                "{env} did not round-trip"
            );
        }
    }

    #[test]
    fn parses_accepted_spellings() {
        assert_eq!(Environment::parse("dev"), Some(Environment::Dev));
        assert_eq!(Environment::parse("development"), Some(Environment::Dev));
        assert_eq!(Environment::parse("local"), Some(Environment::Dev));
        assert_eq!(Environment::parse("staging"), Some(Environment::Staging));
        assert_eq!(Environment::parse("stage"), Some(Environment::Staging));
        assert_eq!(Environment::parse("uat"), Some(Environment::Staging));
        assert_eq!(Environment::parse("prod"), Some(Environment::Prod));
        assert_eq!(Environment::parse("production"), Some(Environment::Prod));
    }

    #[test]
    fn parsing_is_case_and_whitespace_insensitive() {
        assert_eq!(Environment::parse("  PROD "), Some(Environment::Prod));
        assert_eq!(Environment::parse("Staging"), Some(Environment::Staging));
    }

    #[test]
    fn rejects_unknown_override_values() {
        // Must defer to the identifier rather than guess.
        assert_eq!(Environment::parse("qa"), None);
        assert_eq!(Environment::parse(""), None);
        assert_eq!(Environment::parse("prod!"), None);
    }

    #[test]
    fn every_environment_is_isolated_from_the_others() {
        let envs = [Environment::Dev, Environment::Staging, Environment::Prod];

        for (i, a) in envs.iter().enumerate() {
            for b in &envs[i + 1..] {
                assert_ne!(
                    a.bundle_identifier(),
                    b.bundle_identifier(),
                    "{a} and {b} share a bundle identifier"
                );
                assert_ne!(
                    a.recordings_dir_name(),
                    b.recordings_dir_name(),
                    "{a} and {b} share a recordings folder"
                );
                assert_ne!(
                    a.keychain_service(),
                    b.keychain_service(),
                    "{a} and {b} share a keychain entry"
                );
            }
        }
    }

    #[test]
    fn production_keeps_the_unsuffixed_names() {
        // Existing installs and recordings must not be orphaned.
        assert_eq!(
            Environment::Prod.bundle_identifier(),
            "com.providend.meetingassistant"
        );
        assert_eq!(Environment::Prod.recordings_dir_name(), "meetily-recordings");
        assert_eq!(
            Environment::Prod.keychain_service(),
            "com.providend.meetingassistant"
        );
    }

    #[test]
    fn only_non_production_is_labelled() {
        assert!(Environment::Prod.label().is_none());
        assert!(Environment::Dev.label().is_some());
        assert!(Environment::Staging.label().is_some());
    }

    #[test]
    fn is_production_is_exclusive() {
        assert!(Environment::Prod.is_production());
        assert!(!Environment::Dev.is_production());
        assert!(!Environment::Staging.is_production());
    }
}
