use crate::database::repositories::template::TemplatesRepository;
use crate::state::AppState;
use crate::summary::templates::{self, TemplateSection};
use serde::{Deserialize, Serialize};
use tauri::Runtime;
use tracing::{info, warn};

/// Template metadata for UI display
#[derive(Debug, Serialize, Deserialize)]
pub struct TemplateInfo {
    /// Template identifier (e.g., "daily_standup", "standard_meeting")
    pub id: String,

    /// Display name for the template
    pub name: String,

    /// Brief description of the template's purpose
    pub description: String,

    /// True when the template ships with the app. Built-ins can be edited and
    /// reset, but not deleted.
    pub is_builtin: bool,

    /// True when a built-in has been edited by the user, meaning "reset to
    /// default" is available.
    pub user_modified: bool,

    /// RFC 3339 timestamp of the last edit
    pub updated_at: String,
}

/// Full template structure for the editor
#[derive(Debug, Serialize, Deserialize)]
pub struct TemplateDetails {
    /// Template identifier
    pub id: String,

    /// Display name
    pub name: String,

    /// Description
    pub description: String,

    /// Full section definitions, including the LLM instruction and format for each
    pub sections: Vec<TemplateSection>,

    /// True when the template ships with the app
    pub is_builtin: bool,

    /// True when a built-in has been edited by the user
    pub user_modified: bool,
}

/// Payload for creating or updating a template
#[derive(Debug, Deserialize)]
pub struct SaveTemplateRequest {
    /// Existing identifier when updating. Omit to create, in which case an id is
    /// derived from the name.
    pub id: Option<String>,
    pub name: String,
    pub description: String,
    pub sections: Vec<TemplateSection>,
}

/// Lists all available templates
///
/// Built-in templates are returned first, then user templates alphabetically.
#[tauri::command]
pub async fn api_list_templates<R: Runtime>(
    _app: tauri::AppHandle<R>,
    state: tauri::State<'_, AppState>,
) -> Result<Vec<TemplateInfo>, String> {
    let pool = state.db_manager.pool();

    let rows = TemplatesRepository::list(pool)
        .await
        .map_err(|e| format!("Failed to list templates: {}", e))?;

    let template_infos: Vec<TemplateInfo> = rows
        .into_iter()
        .map(|row| TemplateInfo {
            id: row.id,
            name: row.name,
            description: row.description,
            is_builtin: row.is_builtin != 0,
            user_modified: row.user_modified != 0,
            updated_at: row.updated_at,
        })
        .collect();

    info!("Found {} available templates", template_infos.len());

    Ok(template_infos)
}

/// Gets the full definition of a template, including per-section instructions.
///
/// This is what backs the template editor, so it returns whole `TemplateSection`
/// values rather than just section titles.
#[tauri::command]
pub async fn api_get_template_details<R: Runtime>(
    _app: tauri::AppHandle<R>,
    state: tauri::State<'_, AppState>,
    template_id: String,
) -> Result<TemplateDetails, String> {
    info!("api_get_template_details called for template_id: {}", template_id);

    let pool = state.db_manager.pool();
    let template = templates::get_template(pool, &template_id).await?;

    // Flags come from the row when present; a template answered by the embedded
    // fallback is by definition an unmodified built-in.
    let (is_builtin, user_modified) = match TemplatesRepository::get(pool, &template_id).await {
        Ok(Some(row)) => (row.is_builtin != 0, row.user_modified != 0),
        Ok(None) => (true, false),
        Err(e) => {
            warn!("Failed to read template flags for '{}': {}", template_id, e);
            (false, false)
        }
    };

    Ok(TemplateDetails {
        id: template_id,
        name: template.name,
        description: template.description,
        sections: template.sections,
        is_builtin,
        user_modified,
    })
}

/// Creates or updates a template.
///
/// Returns the identifier of the saved template, which for a newly created
/// template is derived from its name.
#[tauri::command]
pub async fn api_save_template<R: Runtime>(
    _app: tauri::AppHandle<R>,
    state: tauri::State<'_, AppState>,
    request: SaveTemplateRequest,
) -> Result<String, String> {
    let pool = state.db_manager.pool();

    let template = templates::Template {
        name: request.name.trim().to_string(),
        description: request.description.trim().to_string(),
        sections: request.sections,
    };
    template.validate()?;

    let id = match request.id {
        Some(existing) => {
            let id = templates::sanitize_template_id(&existing)?;
            if !TemplatesRepository::exists(pool, &id)
                .await
                .map_err(|e| format!("Database error: {}", e))?
            {
                return Err(format!("Template '{}' not found", id));
            }
            id
        }
        None => templates::derive_unique_id(pool, &template.name).await?,
    };

    let sections_json = serde_json::to_string(&template.sections)
        .map_err(|e| format!("Failed to serialize sections: {}", e))?;

    TemplatesRepository::upsert_user_template(
        pool,
        &id,
        &template.name,
        &template.description,
        &sections_json,
    )
    .await
    .map_err(|e| format!("Failed to save template: {}", e))?;

    info!("Saved template '{}' ({})", template.name, id);

    Ok(id)
}

/// Deletes a user-authored template.
///
/// Built-in templates cannot be deleted; use `api_reset_template` to restore one
/// to its shipped content.
#[tauri::command]
pub async fn api_delete_template<R: Runtime>(
    _app: tauri::AppHandle<R>,
    state: tauri::State<'_, AppState>,
    template_id: String,
) -> Result<(), String> {
    let pool = state.db_manager.pool();
    let id = templates::sanitize_template_id(&template_id)?;

    let row = TemplatesRepository::get(pool, &id)
        .await
        .map_err(|e| format!("Database error: {}", e))?
        .ok_or_else(|| format!("Template '{}' not found", id))?;

    if row.is_builtin != 0 {
        return Err(
            "Built-in templates cannot be deleted. Use \"Reset to default\" instead.".to_string(),
        );
    }

    TemplatesRepository::delete(pool, &id)
        .await
        .map_err(|e| format!("Failed to delete template: {}", e))?;

    info!("Deleted template '{}'", id);

    Ok(())
}

/// Restores a built-in template to the content shipped with the app.
#[tauri::command]
pub async fn api_reset_template<R: Runtime>(
    _app: tauri::AppHandle<R>,
    state: tauri::State<'_, AppState>,
    template_id: String,
) -> Result<(), String> {
    let pool = state.db_manager.pool();
    let id = templates::sanitize_template_id(&template_id)?;

    let row = TemplatesRepository::get(pool, &id)
        .await
        .map_err(|e| format!("Database error: {}", e))?
        .ok_or_else(|| format!("Template '{}' not found", id))?;

    if row.is_builtin == 0 {
        return Err("Only built-in templates can be reset to default".to_string());
    }

    // Clearing the flag makes the row eligible for the seeder again, which then
    // rewrites it from the shipped definition.
    TemplatesRepository::clear_user_modified(pool, &id)
        .await
        .map_err(|e| format!("Failed to reset template: {}", e))?;

    templates::seed_shipped_templates(pool).await?;

    info!("Reset template '{}' to its shipped definition", id);

    Ok(())
}

/// Validates a template JSON string
///
/// Used by the template editor's import flow to check a pasted or imported
/// definition before saving it.
///
/// # Returns
/// Ok(template_name) if valid, Err(error_message) if invalid
#[tauri::command]
pub async fn api_validate_template<R: Runtime>(
    _app: tauri::AppHandle<R>,
    template_json: String,
) -> Result<String, String> {
    match templates::validate_and_parse_template(&template_json) {
        Ok(template) => {
            info!("Template '{}' validated successfully", template.name);
            Ok(template.name)
        }
        Err(e) => {
            warn!("Template validation failed: {}", e);
            Err(e)
        }
    }
}

#[cfg(test)]
mod tests {
    use crate::summary::templates;

    #[test]
    fn test_validate_template_valid() {
        let valid_json = r#"
        {
            "name": "Test Template",
            "description": "A test template",
            "sections": [
                {
                    "title": "Summary",
                    "instruction": "Provide a summary",
                    "format": "paragraph"
                }
            ]
        }"#;

        let result = templates::validate_and_parse_template(valid_json);
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_template_invalid() {
        let result = templates::validate_and_parse_template("invalid json");
        assert!(result.is_err());
    }
}
