use tauri::{AppHandle, Runtime};
use tauri_plugin_dialog::DialogExt;

const MAX_FILENAME_CHARS: usize = 120;

/// Opens a native save dialog and writes `contents` to the chosen path.
/// Returns the written path, or None when the user cancels.
#[tauri::command]
pub async fn api_export_markdown<R: Runtime>(
    app: AppHandle<R>,
    suggested_filename: String,
    contents: String,
) -> Result<Option<String>, String> {
    let (tx, rx) = tokio::sync::oneshot::channel();

    app.dialog()
        .file()
        .set_file_name(sanitize_filename(&suggested_filename))
        .add_filter("Markdown", &["md"])
        .save_file(move |path| {
            let _ = tx.send(path);
        });

    let selection = rx
        .await
        .map_err(|e| format!("Save dialog closed unexpectedly: {}", e))?;

    let Some(file_path) = selection else {
        return Ok(None);
    };

    let path = file_path
        .into_path()
        .map_err(|e| format!("Unsupported save location: {}", e))?;

    std::fs::write(&path, contents)
        .map_err(|e| format!("Failed to write {}: {}", path.display(), e))?;

    log::info!("Exported markdown to {}", path.display());
    Ok(Some(path.to_string_lossy().to_string()))
}

/// Windows rejects names with leading or trailing spaces and dots.
fn is_edge_char(c: char) -> bool {
    c == ' ' || c == '.' || c == '-'
}

/// Replaces characters that are illegal in Windows or macOS filenames and
/// guarantees a non-empty name ending in `.md`.
fn sanitize_filename(raw: &str) -> String {
    let mut cleaned = String::with_capacity(raw.len());
    for c in raw.chars() {
        let mapped = match c {
            '<' | '>' | ':' | '"' | '/' | '\\' | '|' | '?' | '*' => '-',
            c if c.is_control() => '-',
            c => c,
        };

        // Collapse the runs left behind by stripping illegal characters.
        if mapped == '-' && cleaned.ends_with('-') {
            continue;
        }
        cleaned.push(mapped);
    }

    let trimmed = cleaned.trim_matches(is_edge_char);
    let stem = trimmed.strip_suffix(".md").unwrap_or(trimmed);
    let stem: String = stem.chars().take(MAX_FILENAME_CHARS).collect();
    let stem = stem.trim_matches(is_edge_char);

    if stem.is_empty() {
        "export.md".to_string()
    } else {
        format!("{}.md", stem)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sanitize_filename_appends_extension() {
        assert_eq!(sanitize_filename("Team Standup"), "Team Standup.md");
        assert_eq!(sanitize_filename("Team Standup.md"), "Team Standup.md");
    }

    #[test]
    fn test_sanitize_filename_strips_path_separators() {
        assert_eq!(sanitize_filename("../../etc/passwd"), "etc-passwd.md");
        assert_eq!(sanitize_filename("a\\b:c*d?.md"), "a-b-c-d.md");
        assert_eq!(sanitize_filename("Q3 review: draft"), "Q3 review- draft.md");
    }

    #[test]
    fn test_sanitize_filename_falls_back_when_empty() {
        assert_eq!(sanitize_filename(""), "export.md");
        assert_eq!(sanitize_filename("   ..  "), "export.md");
        assert_eq!(sanitize_filename("///"), "export.md");
    }

    #[test]
    fn test_sanitize_filename_caps_length() {
        let name = sanitize_filename(&"x".repeat(500));
        assert_eq!(name.chars().count(), MAX_FILENAME_CHARS + 3);
    }
}
