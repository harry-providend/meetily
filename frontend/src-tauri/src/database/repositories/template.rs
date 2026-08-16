use crate::database::models::SummaryTemplateRow;
use chrono::Utc;
use sqlx::SqlitePool;

pub struct TemplatesRepository;

impl TemplatesRepository {
    pub async fn get(
        pool: &SqlitePool,
        id: &str,
    ) -> Result<Option<SummaryTemplateRow>, sqlx::Error> {
        sqlx::query_as::<_, SummaryTemplateRow>("SELECT * FROM summary_templates WHERE id = ?")
            .bind(id)
            .fetch_optional(pool)
            .await
    }

    /// Lists all templates, built-ins first so the defaults stay at the top of the picker.
    pub async fn list(pool: &SqlitePool) -> Result<Vec<SummaryTemplateRow>, sqlx::Error> {
        sqlx::query_as::<_, SummaryTemplateRow>(
            "SELECT * FROM summary_templates ORDER BY is_builtin DESC, name COLLATE NOCASE ASC",
        )
        .fetch_all(pool)
        .await
    }

    pub async fn exists(pool: &SqlitePool, id: &str) -> Result<bool, sqlx::Error> {
        let row: Option<(i64,)> = sqlx::query_as("SELECT 1 FROM summary_templates WHERE id = ?")
            .bind(id)
            .fetch_optional(pool)
            .await?;
        Ok(row.is_some())
    }

    /// Saves a user edit, preserving is_builtin and flagging the row so seeding skips it.
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

    /// Seeds a shipped template, skipping rows the user has edited.
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

    /// Inserts only when the id is free, so the legacy import can never overwrite.
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

    pub async fn delete(pool: &SqlitePool, id: &str) -> Result<bool, sqlx::Error> {
        let result = sqlx::query("DELETE FROM summary_templates WHERE id = ?")
            .bind(id)
            .execute(pool)
            .await?;

        Ok(result.rows_affected() > 0)
    }

    /// Makes a built-in eligible for seeding again, which restores its shipped content.
    pub async fn clear_user_modified(pool: &SqlitePool, id: &str) -> Result<bool, sqlx::Error> {
        let result =
            sqlx::query("UPDATE summary_templates SET user_modified = 0 WHERE id = ? AND is_builtin = 1")
                .bind(id)
                .execute(pool)
                .await?;

        Ok(result.rows_affected() > 0)
    }
}
