//! Bakes `.env.<name>` into the binary -- an installed app has no `.env` beside it. All three
//! are baked in and chosen at runtime from the bundle identifier, so the target env need not be
//! known at compile time. Non-secret configuration only.

use std::collections::HashMap;
use std::fs;
use std::path::Path;

/// Environments and the `.env` file for each.
const ENVIRONMENTS: &[(&str, &str)] = &[
    ("DEV", ".env.dev"),
    ("STAGING", ".env.staging"),
    ("PROD", ".env.prod"),
];

/// Emitted for every environment, empty when absent, so `env!` always resolves.
const KEYS: &[&str] = &["AUTH_TENANT_ID", "AUTH_CLIENT_ID", "API_BASE_URL"];

pub fn emit() {
    for (env_name, file_name) in ENVIRONMENTS {
        // Re-run when a file changes, and also when a missing one appears.
        println!("cargo:rerun-if-changed={file_name}");

        let values = read_env_file(Path::new(file_name));

        for key in KEYS {
            let value = values.get(*key).map(String::as_str).unwrap_or("");
            println!("cargo:rustc-env=ENV_{env_name}_{key}={value}");
        }
    }
}

/// Parses a minimal `KEY=VALUE` file. Blank lines and `#` comments are skipped;
/// surrounding single or double quotes are stripped.
fn read_env_file(path: &Path) -> HashMap<String, String> {
    let mut values = HashMap::new();

    let Ok(contents) = fs::read_to_string(path) else {
        // Not an error: an unconfigured environment is reported at sign-in.
        return values;
    };

    for line in contents.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }

        let Some((key, value)) = line.split_once('=') else {
            continue;
        };

        let key = key.trim();
        let value = value.trim().trim_matches('"').trim_matches('\'').trim();

        if key.is_empty() {
            continue;
        }

        // Reject anything that would break the cargo directive it is emitted in.
        if value.contains('\n') || value.contains('\r') {
            println!("cargo:warning=Ignoring {key} in {}: contains a newline", path.display());
            continue;
        }

        values.insert(key.to_string(), value.to_string());
    }

    values
}
