use crate::database::models::SummaryTemplateRow;
use chrono::Utc;
use sqlx::SqlitePool;

pub struct TemplatesRepository;

impl TemplatesRepository {
    /// Fetches a single template row by identifier.
    pub async fn get(
        pool: &SqlitePool,
        id: &str,
    ) -> Result<Option<SummaryTemplateRow>, sqlx::Error> {
        sqlx::query_as::<_, SummaryTemplateRow>("SELECT * FROM summary_templates WHERE id = ?")
            .bind(id)
            .fetch_optional(pool)
            .await
    }

    /// Lists every template, built-in ones first, then alphabetically by name.
    ///
    /// Built-ins lead so the familiar defaults stay at the top of the picker even
    /// after a user adds their own templates.
    pub async fn list(pool: &SqlitePool) -> Result<Vec<SummaryTemplateRow>, sqlx::Error> {
        sqlx::query_as::<_, SummaryTemplateRow>(
            "SELECT * FROM summary_templates ORDER BY is_builtin DESC, name COLLATE NOCASE ASC",
        )
        .fetch_all(pool)
        .await
    }

    /// Returns true when a template with this identifier already exists.
    pub async fn exists(pool: &SqlitePool, id: &str) -> Result<bool, sqlx::Error> {
        let row: Option<(i64,)> = sqlx::query_as("SELECT 1 FROM summary_templates WHERE id = ?")
            .bind(id)
            .fetch_optional(pool)
            .await?;
        Ok(row.is_some())
    }

    /// Inserts or updates a user-authored template.
    ///
    /// Preserves `is_builtin` and `created_at` on an existing row, and marks the
    /// row `user_modified = 1` so the startup seeder stops overwriting it.
    pub async fn upsert_user_template(
        pool: &SqlitePool,
        id: &str,
        name: &str,
        description: &str,
        sections_json: &str,
    ) -> Result<(), sqlx::Error> {
        let now = Utc::now().to_rfc3339();

        sqlx::query(
            r#"
            INSERT INTO summary_templates
                (id, name, description, sections_json, is_builtin, user_modified, created_at, updated_at)
            VALUES ($1, $2, $3, $4, 0, 1, $5, $5)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                sections_json = excluded.sections_json,
                user_modified = 1,
                updated_at = excluded.updated_at
            "#,
        )
        .bind(id)
        .bind(name)
        .bind(description)
        .bind(sections_json)
        .bind(&now)
        .execute(pool)
        .await?;

        Ok(())
    }

    /// Seeds a built-in template.
    ///
    /// Skips rows the user has edited (`user_modified = 1`) so app upgrades never
    /// clobber customizations of a shipped template.
    pub async fn seed_builtin(
        pool: &SqlitePool,
        id: &str,
        name: &str,
        description: &str,
        sections_json: &str,
    ) -> Result<(), sqlx::Error> {
        let now = Utc::now().to_rfc3339();

        sqlx::query(
            r#"
            INSERT INTO summary_templates
                (id, name, description, sections_json, is_builtin, user_modified, created_at, updated_at)
            VALUES ($1, $2, $3, $4, 1, 0, $5, $5)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                sections_json = excluded.sections_json,
                is_builtin = 1,
                updated_at = excluded.updated_at
            WHERE summary_templates.user_modified = 0
            "#,
        )
        .bind(id)
        .bind(name)
        .bind(description)
        .bind(sections_json)
        .bind(&now)
        .execute(pool)
        .await?;

        Ok(())
    }

    /// Imports a template discovered in the legacy on-disk templates directory.
    ///
    /// Only inserts when the identifier is absent, so a one-time import can never
    /// overwrite a seeded built-in or a template the user has since edited.
    pub async fn insert_if_absent(
        pool: &SqlitePool,
        id: &str,
        name: &str,
        description: &str,
        sections_json: &str,
        is_builtin: bool,
    ) -> Result<bool, sqlx::Error> {
        let now = Utc::now().to_rfc3339();

        let result = sqlx::query(
            r#"
            INSERT OR IGNORE INTO summary_templates
                (id, name, description, sections_json, is_builtin, user_modified, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, 0, $6, $6)
            "#,
        )
        .bind(id)
        .bind(name)
        .bind(description)
        .bind(sections_json)
        .bind(if is_builtin { 1 } else { 0 })
        .bind(&now)
        .execute(pool)
        .await?;

        Ok(result.rows_affected() > 0)
    }

    /// Deletes a template outright. Used for user-authored templates.
    pub async fn delete(pool: &SqlitePool, id: &str) -> Result<bool, sqlx::Error> {
        let result = sqlx::query("DELETE FROM summary_templates WHERE id = ?")
            .bind(id)
            .execute(pool)
            .await?;

        Ok(result.rows_affected() > 0)
    }

    /// Clears the `user_modified` flag on a built-in template so the next seed
    /// pass restores its shipped content.
    pub async fn clear_user_modified(pool: &SqlitePool, id: &str) -> Result<bool, sqlx::Error> {
        let result =
            sqlx::query("UPDATE summary_templates SET user_modified = 0 WHERE id = ? AND is_builtin = 1")
                .bind(id)
                .execute(pool)
                .await?;

        Ok(result.rows_affected() > 0)
    }
}
