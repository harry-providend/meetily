//! Meeting summary template management
//!
//! Templates live in the `summary_templates` table. Those shipped with the app
//! (bundled resource JSON plus embedded constants) are seeded there at startup
//! with `is_builtin = 1`; seeding skips rows flagged `user_modified` so edits
//! survive app upgrades, and reset clears the flag to restore the original.
//! The embedded constants remain a fallback if a row is missing entirely.
//!
//! ```no_run
//! # async fn example(pool: &sqlx::SqlitePool) -> Result<(), String> {
//! use app_lib::summary::templates;
//!
//! let template = templates::get_template(pool, "daily_standup").await?;
//! let markdown = template.to_markdown_structure();
//! let instructions = template.to_section_instructions();
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

    /// In-memory database with the real migrations applied, then seeded.
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

        // An app upgrade re-runs the seeder
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
