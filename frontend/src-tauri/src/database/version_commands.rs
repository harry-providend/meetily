use crate::backend::client::{require_client, BackendError};
use crate::backend::versions::VersionsApi;
use serde::{Deserialize, Serialize};

/// One row in the version history list.
#[derive(Debug, Serialize, Deserialize)]
pub struct VersionInfo {
    pub version: i64,
    /// What caused the snapshot, e.g. 'retranscription' or 'restore'
    pub reason: String,
    pub created_at: String,
    /// Segment count for transcripts, word count for summaries
    pub size: i64,
}

#[tauri::command]
pub async fn api_list_transcript_versions(meeting_id: String) -> Result<Vec<VersionInfo>, String> {
    let client = require_client().map_err(|e| e.to_string())?;
    let rows = VersionsApi::new(&client)
        .list_transcript_versions(&meeting_id)
        .await
        .map_err(|e| format!("Failed to list transcript versions: {}", e))?;

    Ok(rows
        .into_iter()
        .map(|r| VersionInfo {
            version: r.version,
            reason: r.reason,
            created_at: r.created_at,
            size: r.segment_count,
        })
        .collect())
}

#[tauri::command]
pub async fn api_list_summary_versions(meeting_id: String) -> Result<Vec<VersionInfo>, String> {
    let client = require_client().map_err(|e| e.to_string())?;
    let rows = VersionsApi::new(&client)
        .list_summary_versions(&meeting_id)
        .await
        .map_err(|e| format!("Failed to list summary versions: {}", e))?;

    Ok(rows
        .into_iter()
        .map(|r| {
            let markdown = summary_value_to_markdown(&r.result_json);
            VersionInfo {
                version: r.version,
                reason: r.reason,
                created_at: r.created_at,
                size: markdown.split_whitespace().count() as i64,
            }
        })
        .collect())
}

/// Renders an archived transcript version as markdown for preview and export.
#[tauri::command]
pub async fn api_render_transcript_version(
    meeting_id: String,
    version: i64,
) -> Result<String, String> {
    let client = require_client().map_err(|e| e.to_string())?;
    let row = VersionsApi::new(&client)
        .get_transcript_version(&meeting_id, version)
        .await
        .map_err(|e| match e {
            BackendError::NotFound => format!("Transcript version {} not found", version),
            other => format!("Failed to read transcript version: {}", other),
        })?;

    Ok(row
        .segments_json
        .iter()
        .map(|s| format!("{} {}  ", format_offset(s.audio_start_time, &s.timestamp), s.transcript))
        .collect::<Vec<_>>()
        .join("\n"))
}

/// Renders an archived summary version as markdown for preview and export.
#[tauri::command]
pub async fn api_render_summary_version(
    meeting_id: String,
    version: i64,
) -> Result<String, String> {
    let client = require_client().map_err(|e| e.to_string())?;
    let row = VersionsApi::new(&client)
        .get_summary_version(&meeting_id, version)
        .await
        .map_err(|e| match e {
            BackendError::NotFound => format!("Summary version {} not found", version),
            other => format!("Failed to read summary version: {}", other),
        })?;

    Ok(summary_value_to_markdown(&row.result_json))
}

#[tauri::command]
pub async fn api_restore_transcript_version(
    meeting_id: String,
    version: i64,
) -> Result<usize, String> {
    let client = require_client().map_err(|e| e.to_string())?;
    VersionsApi::new(&client)
        .restore_transcript_version(&meeting_id, version)
        .await
        .map_err(|e| format!("Failed to restore transcript version {}: {}", version, e))
}

#[tauri::command]
pub async fn api_restore_summary_version(meeting_id: String, version: i64) -> Result<(), String> {
    let client = require_client().map_err(|e| e.to_string())?;
    VersionsApi::new(&client)
        .restore_summary_version(&meeting_id, version)
        .await
        .map_err(|e| format!("Failed to restore summary version {}: {}", version, e))
}

/// Mirrors the frontend's [MM:SS] formatting, falling back to the wall-clock
/// timestamp for transcripts recorded before audio offsets were stored.
fn format_offset(seconds: Option<f64>, fallback: &str) -> String {
    match seconds {
        Some(s) => {
            let total = s.max(0.0) as u64;
            format!("[{:02}:{:02}]", total / 60, total % 60)
        }
        None => fallback.to_string(),
    }
}

/// Summaries are stored as `{"markdown": "..."}`; older rows may hold the
/// section map the pre-BlockNote UI used.
fn summary_value_to_markdown(value: &serde_json::Value) -> String {
    if let Some(markdown) = value.get("markdown").and_then(|m| m.as_str()) {
        return markdown.to_string();
    }

    let Some(sections) = value.as_object() else {
        return value.to_string();
    };

    sections
        .iter()
        .filter_map(|(_, section)| {
            let title = section.get("title")?.as_str()?;
            let blocks = section.get("blocks")?.as_array()?;
            let body = blocks
                .iter()
                .filter_map(|b| b.get("content")?.as_str())
                .map(|c| format!("- {}", c))
                .collect::<Vec<_>>()
                .join("\n");
            Some(format!("## {}\n\n{}", title, body))
        })
        .collect::<Vec<_>>()
        .join("\n\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_format_offset() {
        assert_eq!(format_offset(Some(0.0), "14:30:05"), "[00:00]");
        assert_eq!(format_offset(Some(125.7), "14:30:05"), "[02:05]");
        assert_eq!(format_offset(Some(3661.0), "14:30:05"), "[61:01]");
        assert_eq!(format_offset(None, "14:30:05"), "14:30:05");
    }

    #[test]
    fn test_summary_json_prefers_markdown_field() {
        let value = serde_json::json!({"markdown": "## Notes\n\n- one"});
        assert_eq!(summary_value_to_markdown(&value), "## Notes\n\n- one");
    }

    #[test]
    fn test_summary_json_renders_legacy_sections() {
        let value = serde_json::json!({
            "a": {"title": "Action Items", "blocks": [{"content": "Ship it"}]}
        });
        assert_eq!(
            summary_value_to_markdown(&value),
            "## Action Items\n\n- Ship it"
        );
    }

    #[test]
    fn test_summary_json_falls_back_to_the_raw_json_for_an_unexpected_shape() {
        // The server sends decoded JSON, so this can no longer be unparseable text -- only an
        // object shape neither renderer recognises.
        let value = serde_json::json!(["not", "an", "object"]);
        assert_eq!(
            summary_value_to_markdown(&value),
            r#"["not","an","object"]"#
        );
    }
}
