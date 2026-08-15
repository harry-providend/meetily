use super::defaults;
use super::types::Template;
use crate::database::repositories::template::TemplatesRepository;
use once_cell::sync::Lazy;
use sqlx::SqlitePool;
use std::path::PathBuf;
use std::sync::RwLock;
use tracing::{debug, info, warn};

// Global storage for the bundled templates directory path
static BUNDLED_TEMPLATES_DIR: Lazy<RwLock<Option<PathBuf>>> = Lazy::new(|| RwLock::new(None));

/// Set the bundled templates directory path (called once at app startup)
pub fn set_bundled_templates_dir(path: PathBuf) {
    info!("Bundled templates directory set to: {:?}", path);
    if let Ok(mut dir) = BUNDLED_TEMPLATES_DIR.write() {
        *dir = Some(path);
    }
}

/// Legacy on-disk custom templates directory.
///
/// Templates now live in SQLite. This path is only read once at startup so that
/// anyone who dropped JSON files here before the move keeps their templates:
/// - macOS: ~/Library/Application Support/Meetily/templates/
/// - Windows: %APPDATA%\Meetily\templates\
/// - Linux: ~/.config/Meetily/templates/
fn legacy_custom_templates_dir() -> Option<PathBuf> {
    let mut path = dirs::data_dir()?;
    path.push("Meetily");
    path.push("templates");
    Some(path)
}

/// A template identifier is used as a primary key, and previously as a filename.
/// Constrain it to a slug so it stays safe for export filenames and legible in
/// the UI.
pub fn sanitize_template_id(raw: &str) -> Result<String, String> {
    let slug: String = raw
        .trim()
        .to_lowercase()
        .chars()
        .map(|c| match c {
            'a'..='z' | '0'..='9' => c,
            _ => '_',
        })
        .collect();

    let slug = slug.trim_matches('_').to_string();
    // Collapse runs of underscores introduced by the mapping above.
    let mut collapsed = String::with_capacity(slug.len());
    let mut last_underscore = false;
    for c in slug.chars() {
        if c == '_' {
            if !last_underscore {
                collapsed.push(c);
            }
            last_underscore = true;
        } else {
            collapsed.push(c);
            last_underscore = false;
        }
    }

    if collapsed.is_empty() {
        return Err("Template id must contain at least one letter or digit".to_string());
    }

    if collapsed.len() > 64 {
        return Err("Template id must be 64 characters or fewer".to_string());
    }

    Ok(collapsed)
}

/// Derive a template id from a display name, appending a numeric suffix until it
/// no longer collides with an existing row.
pub async fn derive_unique_id(pool: &SqlitePool, name: &str) -> Result<String, String> {
    let base = sanitize_template_id(name)?;

    let mut candidate = base.clone();
    let mut suffix = 2;
    loop {
        let exists = TemplatesRepository::exists(pool, &candidate)
            .await
            .map_err(|e| format!("Database error checking template id: {}", e))?;

        if !exists {
            return Ok(candidate);
        }

        candidate = format!("{}_{}", base, suffix);
        suffix += 1;

        if suffix > 1000 {
            return Err("Could not derive a unique template id".to_string());
        }
    }
}

/// Read a bundled template JSON file from the app resources directory.
fn read_bundled_template(template_id: &str) -> Option<String> {
    let bundled_dir = BUNDLED_TEMPLATES_DIR.read().ok()?.clone()?;
    let template_path = bundled_dir.join(format!("{}.json", template_id));

    match std::fs::read_to_string(&template_path) {
        Ok(content) => Some(content),
        Err(e) => {
            debug!("No bundled template '{}' found: {}", template_id, e);
            None
        }
    }
}

/// Collect every template shipped with the app: bundled resource JSON files plus
/// the constants embedded in the binary. Bundled files win when both provide the
/// same id, since resources can ship fixes without a code change.
fn collect_shipped_templates() -> Vec<(String, String)> {
    let mut shipped: Vec<(String, String)> = Vec::new();
    let mut seen: Vec<String> = Vec::new();

    if let Ok(bundled_dir_lock) = BUNDLED_TEMPLATES_DIR.read() {
        if let Some(bundled_dir) = bundled_dir_lock.as_ref() {
            if bundled_dir.exists() {
                match std::fs::read_dir(bundled_dir) {
                    Ok(entries) => {
                        for entry in entries.flatten() {
                            let filename = entry.file_name();
                            let Some(filename) = filename.to_str() else {
                                continue;
                            };
                            let Some(id) = filename.strip_suffix(".json") else {
                                continue;
                            };
                            if let Some(content) = read_bundled_template(id) {
                                seen.push(id.to_string());
                                shipped.push((id.to_string(), content));
                            }
                        }
                    }
                    Err(e) => warn!("Failed to read bundled templates directory: {}", e),
                }
            }
        }
    }

    for (id, content) in defaults::get_builtin_templates() {
        if !seen.iter().any(|s| s == id) {
            shipped.push((id.to_string(), content.to_string()));
        }
    }

    shipped
}

/// Seed shipped templates into the database and import any legacy on-disk
/// templates. Safe to run on every startup: built-ins the user has edited are
/// left alone, and legacy files are only inserted when the id is absent.
pub async fn seed_templates(pool: &SqlitePool) -> Result<(), String> {
    seed_shipped_templates(pool).await?;
    import_legacy_templates(pool).await;
    Ok(())
}

/// Seeds only the templates shipped with the app.
///
/// Split out from [`seed_templates`] so it can be exercised without touching the
/// user's data directory.
pub async fn seed_shipped_templates(pool: &SqlitePool) -> Result<(), String> {
    for (id, json) in collect_shipped_templates() {
        let template = match validate_and_parse_template(&json) {
            Ok(t) => t,
            Err(e) => {
                warn!("Skipping invalid shipped template '{}': {}", id, e);
                continue;
            }
        };

        let sections_json = serde_json::to_string(&template.sections)
            .map_err(|e| format!("Failed to serialize sections for '{}': {}", id, e))?;

        TemplatesRepository::seed_builtin(
            pool,
            &id,
            &template.name,
            &template.description,
            &sections_json,
        )
        .await
        .map_err(|e| format!("Failed to seed template '{}': {}", id, e))?;
    }

    Ok(())
}

/// One-time import of the pre-SQLite templates directory.
///
/// Files whose id is already present are skipped. Once every file is accounted
/// for, the directory is renamed so the import does not run again.
async fn import_legacy_templates(pool: &SqlitePool) {
    let Some(legacy_dir) = legacy_custom_templates_dir() else {
        return;
    };

    if !legacy_dir.exists() {
        return;
    }

    info!("Importing legacy on-disk templates from {:?}", legacy_dir);

    let entries = match std::fs::read_dir(&legacy_dir) {
        Ok(entries) => entries,
        Err(e) => {
            warn!("Failed to read legacy templates directory: {}", e);
            return;
        }
    };

    let mut imported = 0usize;
    let mut failed = 0usize;

    for entry in entries.flatten() {
        let filename = entry.file_name();
        let Some(filename) = filename.to_str() else {
            continue;
        };
        let Some(raw_id) = filename.strip_suffix(".json") else {
            continue;
        };

        let Ok(id) = sanitize_template_id(raw_id) else {
            warn!("Skipping legacy template with unusable id: {}", raw_id);
            failed += 1;
            continue;
        };

        let content = match std::fs::read_to_string(entry.path()) {
            Ok(content) => content,
            Err(e) => {
                warn!("Failed to read legacy template '{}': {}", raw_id, e);
                failed += 1;
                continue;
            }
        };

        let template = match validate_and_parse_template(&content) {
            Ok(t) => t,
            Err(e) => {
                warn!("Skipping invalid legacy template '{}': {}", raw_id, e);
                failed += 1;
                continue;
            }
        };

        let sections_json = match serde_json::to_string(&template.sections) {
            Ok(json) => json,
            Err(e) => {
                warn!("Failed to serialize legacy template '{}': {}", raw_id, e);
                failed += 1;
                continue;
            }
        };

        match TemplatesRepository::insert_if_absent(
            pool,
            &id,
            &template.name,
            &template.description,
            &sections_json,
            false,
        )
        .await
        {
            Ok(true) => {
                info!("Imported legacy template '{}'", id);
                imported += 1;
            }
            Ok(false) => debug!("Legacy template '{}' already present, skipping", id),
            Err(e) => {
                warn!("Failed to import legacy template '{}': {}", id, e);
                failed += 1;
            }
        }
    }

    if failed > 0 {
        warn!(
            "Legacy template import finished with {} failure(s); leaving {:?} in place",
            failed, legacy_dir
        );
        return;
    }

    // Everything landed in the database. Rename rather than delete so the user's
    // original files remain recoverable.
    let archived = legacy_dir.with_file_name("templates.imported");
    match std::fs::rename(&legacy_dir, &archived) {
        Ok(_) => info!(
            "Imported {} legacy template(s); archived directory to {:?}",
            imported, archived
        ),
        Err(e) => warn!("Failed to archive legacy templates directory: {}", e),
    }
}

/// Load and parse a template by identifier.
///
/// Reads from SQLite, falling back to the embedded constants if the row is
/// missing so a failed seed can never leave summary generation without a
/// template.
pub async fn get_template(pool: &SqlitePool, template_id: &str) -> Result<Template, String> {
    debug!("Loading template: {}", template_id);

    let row = TemplatesRepository::get(pool, template_id)
        .await
        .map_err(|e| format!("Database error loading template: {}", e))?;

    if let Some(row) = row {
        let sections = serde_json::from_str(&row.sections_json)
            .map_err(|e| format!("Failed to parse sections for '{}': {}", template_id, e))?;

        let template = Template {
            name: row.name,
            description: row.description,
            sections,
        };

        template.validate()?;
        return Ok(template);
    }

    if let Some(builtin) = defaults::get_builtin_template(template_id) {
        warn!(
            "Template '{}' missing from database, falling back to embedded copy",
            template_id
        );
        return validate_and_parse_template(builtin);
    }

    let available = list_template_ids(pool).await.unwrap_or_default();
    Err(format!(
        "Template '{}' not found. Available templates: {}",
        template_id,
        available.join(", ")
    ))
}

/// Validate and parse template JSON
///
/// # Arguments
/// * `json_content` - Raw JSON string
///
/// # Returns
/// Parsed and validated Template struct
pub fn validate_and_parse_template(json_content: &str) -> Result<Template, String> {
    let template: Template = serde_json::from_str(json_content)
        .map_err(|e| format!("Failed to parse template JSON: {}", e))?;

    template.validate()?;

    Ok(template)
}

/// List all available template identifiers
pub async fn list_template_ids(pool: &SqlitePool) -> Result<Vec<String>, String> {
    let rows = TemplatesRepository::list(pool)
        .await
        .map_err(|e| format!("Database error listing templates: {}", e))?;

    Ok(rows.into_iter().map(|row| row.id).collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sanitize_template_id() {
        assert_eq!(sanitize_template_id("Daily Standup").unwrap(), "daily_standup");
        assert_eq!(sanitize_template_id("  Weekly  Sync  ").unwrap(), "weekly_sync");
        assert_eq!(sanitize_template_id("Q1/Q2 Review").unwrap(), "q1_q2_review");
    }

    #[test]
    fn test_sanitize_rejects_path_traversal() {
        // Separators collapse into underscores rather than escaping the keyspace.
        assert_eq!(sanitize_template_id("../../etc/passwd").unwrap(), "etc_passwd");
        assert!(sanitize_template_id("../..").is_err());
        assert!(sanitize_template_id("").is_err());
        assert!(sanitize_template_id("///").is_err());
    }

    #[test]
    fn test_sanitize_rejects_overlong_id() {
        assert!(sanitize_template_id(&"a".repeat(65)).is_err());
        assert!(sanitize_template_id(&"a".repeat(64)).is_ok());
    }

    #[test]
    fn test_validate_invalid_json() {
        let result = validate_and_parse_template("invalid json");
        assert!(result.is_err());
    }

    #[test]
    fn test_embedded_defaults_are_valid() {
        for (id, content) in defaults::get_builtin_templates() {
            assert!(
                validate_and_parse_template(content).is_ok(),
                "Embedded template '{}' failed validation",
                id
            );
        }
    }
}
