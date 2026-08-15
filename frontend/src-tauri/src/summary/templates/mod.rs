//! Meeting summary template management
//!
//! This module provides a flexible template system for generating meeting summaries.
//! It supports both built-in templates (embedded in the binary) and custom user templates
//! (loaded from the application data directory).
//!
//! # Architecture
//!
//! Templates live in the `summary_templates` table of the app database. Templates
//! shipped with the app (bundled resource JSON files, plus constants embedded at
//! compile time) are seeded into that table at startup with `is_builtin = 1`.
//!
//! - **Seeding**: re-runs on every launch, but skips rows the user has edited, so
//!   app upgrades never clobber customizations of a shipped template.
//! - **Editing a built-in**: sets `user_modified = 1`; "reset to default" clears
//!   the flag and lets the next seed pass restore the shipped content.
//! - **Fallback**: if a row is missing entirely, the embedded constants still
//!   answer for the two core templates so summary generation cannot be stranded.
//! - **Legacy import**: JSON files from the pre-SQLite custom templates directory
//!   are imported once at startup, then the directory is archived.
//!
//! # Usage
//!
//! ```no_run
//! # async fn example(pool: &sqlx::SqlitePool) -> Result<(), String> {
//! use app_lib::summary::templates;
//!
//! // Load a specific template
//! let template = templates::get_template(pool, "daily_standup").await?;
//!
//! // Generate markdown structure
//! let markdown = template.to_markdown_structure();
//!
//! // Generate LLM instructions
//! let instructions = template.to_section_instructions();
//!
//! // List available template ids
//! let available = templates::list_template_ids(pool).await?;
//! # Ok(())
//! # }
//! ```

mod defaults;
mod loader;
mod types;

// Re-export public API
pub use loader::{
    derive_unique_id, get_template, list_template_ids, sanitize_template_id, seed_shipped_templates,
    seed_templates, set_bundled_templates_dir, validate_and_parse_template,
};
pub use types::{Template, TemplateSection};

#[cfg(test)]
mod tests {
    use super::*;
    use crate::database::repositories::template::TemplatesRepository;
    use sqlx::SqlitePool;

    /// In-memory database with the real migrations applied, seeded with the
    /// templates shipped in the binary.
    async fn seeded_pool() -> SqlitePool {
        let pool = SqlitePool::connect("sqlite::memory:")
            .await
            .expect("in-memory sqlite");

        sqlx::migrate!("./migrations")
            .run(&pool)
            .await
            .expect("migrations apply");

        seed_shipped_templates(&pool).await.expect("seeding works");
        pool
    }

    fn sections_json(title: &str) -> String {
        serde_json::to_string(&vec![TemplateSection {
            title: title.to_string(),
            instruction: "Do the thing".to_string(),
            format: "paragraph".to_string(),
            item_format: None,
            example_item_format: None,
        }])
        .expect("sections serialize")
    }

    #[tokio::test]
    async fn seeding_populates_builtin_templates() {
        let pool = seeded_pool().await;

        let ids = list_template_ids(&pool).await.expect("list ids");
        assert!(ids.contains(&"standard_meeting".to_string()));
        assert!(ids.contains(&"daily_standup".to_string()));

        for id in ids {
            let template = get_template(&pool, &id).await;
            assert!(template.is_ok(), "template '{}' failed to load", id);
        }
    }

    #[tokio::test]
    async fn seeding_is_idempotent() {
        let pool = seeded_pool().await;
        let before = list_template_ids(&pool).await.expect("list ids");

        seed_shipped_templates(&pool).await.expect("re-seed");

        let after = list_template_ids(&pool).await.expect("list ids");
        assert_eq!(before, after);
    }

    #[tokio::test]
    async fn user_edits_to_builtins_survive_reseeding() {
        let pool = seeded_pool().await;

        TemplatesRepository::upsert_user_template(
            &pool,
            "standard_meeting",
            "My Standard Meeting",
            "Edited by the user",
            &sections_json("Custom Section"),
        )
        .await
        .expect("edit builtin");

        // An app upgrade re-runs the seeder; the edit must not be clobbered.
        seed_shipped_templates(&pool).await.expect("re-seed");

        let template = get_template(&pool, "standard_meeting")
            .await
            .expect("load edited template");
        assert_eq!(template.name, "My Standard Meeting");
        assert_eq!(template.sections[0].title, "Custom Section");
    }

    #[tokio::test]
    async fn reset_restores_shipped_builtin() {
        let pool = seeded_pool().await;
        let original = get_template(&pool, "standard_meeting")
            .await
            .expect("load original");

        TemplatesRepository::upsert_user_template(
            &pool,
            "standard_meeting",
            "My Standard Meeting",
            "Edited by the user",
            &sections_json("Custom Section"),
        )
        .await
        .expect("edit builtin");

        TemplatesRepository::clear_user_modified(&pool, "standard_meeting")
            .await
            .expect("clear flag");
        seed_shipped_templates(&pool).await.expect("re-seed");

        let restored = get_template(&pool, "standard_meeting")
            .await
            .expect("load restored");
        assert_eq!(restored.name, original.name);
        assert_eq!(restored.sections.len(), original.sections.len());
    }

    #[tokio::test]
    async fn user_templates_round_trip_and_delete() {
        let pool = seeded_pool().await;

        let id = derive_unique_id(&pool, "Weekly Sync").await.expect("derive id");
        assert_eq!(id, "weekly_sync");

        TemplatesRepository::upsert_user_template(
            &pool,
            &id,
            "Weekly Sync",
            "Our weekly sync",
            &sections_json("Agenda"),
        )
        .await
        .expect("save template");

        let template = get_template(&pool, &id).await.expect("load saved");
        assert_eq!(template.name, "Weekly Sync");
        assert_eq!(template.sections[0].title, "Agenda");

        // A second template with the same display name gets a distinct id.
        let second = derive_unique_id(&pool, "Weekly Sync").await.expect("derive id");
        assert_eq!(second, "weekly_sync_2");

        assert!(TemplatesRepository::delete(&pool, &id).await.expect("delete"));
        assert!(get_template(&pool, &id).await.is_err());
    }

    #[tokio::test]
    async fn missing_template_reports_available_ids() {
        let pool = seeded_pool().await;

        let err = get_template(&pool, "does_not_exist")
            .await
            .expect_err("unknown template errors");
        assert!(err.contains("standard_meeting"), "got: {}", err);
    }
}
