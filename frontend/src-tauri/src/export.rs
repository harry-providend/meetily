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
    let extension = requested_extension(&suggested_filename);
    let filter_label = if extension == "txt" { "Text" } else { "Markdown" };

    app.dialog()
        .file()
        .set_file_name(sanitize_filename(&suggested_filename, extension))
        .add_filter(filter_label, &[extension])
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

    log::info!("Exported {} to {}", extension, path.display());
    Ok(Some(path.to_string_lossy().to_string()))
}

/// Windows rejects names with leading or trailing spaces and dots.
fn is_edge_char(c: char) -> bool {
    c == ' ' || c == '.' || c == '-'
}

/// Picks the export format from the caller's suggested name, defaulting to markdown.
fn requested_extension(raw: &str) -> &'static str {
    if raw.to_ascii_lowercase().ends_with(".txt") {
        "txt"
    } else {
        "md"
    }
}

/// Replaces characters that are illegal in Windows or macOS filenames and
/// guarantees a non-empty name ending in `extension`.
fn sanitize_filename(raw: &str, extension: &str) -> String {
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

    // Drop the caller's extension so it is not doubled up below.
    let suffix = format!(".{}", extension);
    let stem = match trimmed.to_ascii_lowercase().ends_with(&suffix) {
        true => &trimmed[..trimmed.len() - suffix.len()],
        false => trimmed,
    };

    let stem: String = stem.chars().take(MAX_FILENAME_CHARS).collect();
    let stem = stem.trim_matches(is_edge_char);

    if stem.is_empty() {
        format!("export.{}", extension)
    } else {
        format!("{}.{}", stem, extension)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sanitize_filename_appends_extension() {
        assert_eq!(sanitize_filename("Team Standup", "md"), "Team Standup.md");
        assert_eq!(sanitize_filename("Team Standup.md", "md"), "Team Standup.md");
    }

    #[test]
    fn test_sanitize_filename_strips_path_separators() {
        assert_eq!(sanitize_filename("../../etc/passwd", "md"), "etc-passwd.md");
        assert_eq!(sanitize_filename("a\\b:c*d?.md", "md"), "a-b-c-d.md");
        assert_eq!(
            sanitize_filename("Q3 review: draft", "md"),
            "Q3 review- draft.md"
        );
    }

    #[test]
    fn test_sanitize_filename_falls_back_when_empty() {
        assert_eq!(sanitize_filename("", "md"), "export.md");
        assert_eq!(sanitize_filename("   ..  ", "md"), "export.md");
        assert_eq!(sanitize_filename("///", "md"), "export.md");
    }

    #[test]
    fn test_sanitize_filename_caps_length() {
        let name = sanitize_filename(&"x".repeat(500), "md");
        assert_eq!(name.chars().count(), MAX_FILENAME_CHARS + 3);
    }

    #[test]
    fn test_sanitize_filename_honours_text_extension() {
        assert_eq!(sanitize_filename("Standup.txt", "txt"), "Standup.txt");
        assert_eq!(sanitize_filename("Standup", "txt"), "Standup.txt");
        assert_eq!(sanitize_filename("", "txt"), "export.txt");
    }

    #[test]
    fn test_requested_extension_defaults_to_markdown() {
        assert_eq!(requested_extension("notes.txt"), "txt");
        assert_eq!(requested_extension("notes.TXT"), "txt");
        assert_eq!(requested_extension("notes.md"), "md");
        assert_eq!(requested_extension("notes"), "md");
    }
}
