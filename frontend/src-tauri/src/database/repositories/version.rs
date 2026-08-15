use crate::database::models::{ArchivedSegment, SummaryVersionRow, TranscriptVersionRow};
use chrono::Utc;
use sqlx::{SqliteConnection, SqlitePool};

/// Versions kept per meeting per kind before the oldest are pruned.
pub const MAX_VERSIONS_PER_MEETING: i64 = 20;

pub struct VersionsRepository;

impl VersionsRepository {
    /// Archives the meeting's current transcript. Returns the new version number,
    /// or None when the meeting has no segments to preserve.
    ///
    /// Takes a connection so callers can enlist this in the same transaction as
    /// the overwrite it is protecting.
    pub async fn archive_transcript(
        conn: &mut SqliteConnection,
        meeting_id: &str,
        reason: &str,
    ) -> Result<Option<i64>, sqlx::Error> {
        let segments = sqlx::query_as::<_, ArchivedSegment>(
            "SELECT id, transcript, timestamp, audio_start_time, audio_end_time, duration
             FROM transcripts WHERE meeting_id = ? ORDER BY rowid",
        )
        .bind(meeting_id)
        .fetch_all(&mut *conn)
        .await?;

        if segments.is_empty() {
            return Ok(None);
        }

        let segments_json = serde_json::to_string(&segments).map_err(|e| {
            sqlx::Error::Protocol(format!("Failed to serialize transcript segments: {}", e))
        })?;

        let version = Self::next_version(&mut *conn, "transcript_versions", meeting_id).await?;

        sqlx::query(
            "INSERT INTO transcript_versions
             (id, meeting_id, version, reason, segments_json, segment_count, created_at)
             VALUES (?, ?, ?, ?, ?, ?, ?)",
        )
        .bind(format!("tsver-{}-{}", meeting_id, version))
        .bind(meeting_id)
        .bind(version)
        .bind(reason)
        .bind(&segments_json)
        .bind(segments.len() as i64)
        .bind(Utc::now().to_rfc3339())
        .execute(&mut *conn)
        .await?;

        Self::prune(&mut *conn, "transcript_versions", meeting_id).await?;
        Ok(Some(version))
    }

    /// Archives a summary payload that is about to be replaced.
    pub async fn archive_summary(
        conn: &mut SqliteConnection,
        meeting_id: &str,
        result_json: &str,
        reason: &str,
    ) -> Result<i64, sqlx::Error> {
        let version = Self::next_version(&mut *conn, "summary_versions", meeting_id).await?;

        sqlx::query(
            "INSERT INTO summary_versions
             (id, meeting_id, version, reason, result_json, created_at)
             VALUES (?, ?, ?, ?, ?, ?)",
        )
        .bind(format!("sumver-{}-{}", meeting_id, version))
        .bind(meeting_id)
        .bind(version)
        .bind(reason)
        .bind(result_json)
        .bind(Utc::now().to_rfc3339())
        .execute(&mut *conn)
        .await?;

        Self::prune(&mut *conn, "summary_versions", meeting_id).await?;
        Ok(version)
    }

    pub async fn list_transcript_versions(
        pool: &SqlitePool,
        meeting_id: &str,
    ) -> Result<Vec<TranscriptVersionRow>, sqlx::Error> {
        sqlx::query_as::<_, TranscriptVersionRow>(
            "SELECT * FROM transcript_versions WHERE meeting_id = ? ORDER BY version DESC",
        )
        .bind(meeting_id)
        .fetch_all(pool)
        .await
    }

    pub async fn list_summary_versions(
        pool: &SqlitePool,
        meeting_id: &str,
    ) -> Result<Vec<SummaryVersionRow>, sqlx::Error> {
        sqlx::query_as::<_, SummaryVersionRow>(
            "SELECT * FROM summary_versions WHERE meeting_id = ? ORDER BY version DESC",
        )
        .bind(meeting_id)
        .fetch_all(pool)
        .await
    }

    pub async fn get_transcript_version(
        pool: &SqlitePool,
        meeting_id: &str,
        version: i64,
    ) -> Result<Option<TranscriptVersionRow>, sqlx::Error> {
        sqlx::query_as::<_, TranscriptVersionRow>(
            "SELECT * FROM transcript_versions WHERE meeting_id = ? AND version = ?",
        )
        .bind(meeting_id)
        .bind(version)
        .fetch_optional(pool)
        .await
    }

    pub async fn get_summary_version(
        pool: &SqlitePool,
        meeting_id: &str,
        version: i64,
    ) -> Result<Option<SummaryVersionRow>, sqlx::Error> {
        sqlx::query_as::<_, SummaryVersionRow>(
            "SELECT * FROM summary_versions WHERE meeting_id = ? AND version = ?",
        )
        .bind(meeting_id)
        .bind(version)
        .fetch_optional(pool)
        .await
    }

    /// Replaces the live transcript with an archived version, archiving the
    /// current one first so the restore is itself undoable.
    pub async fn restore_transcript_version(
        pool: &SqlitePool,
        meeting_id: &str,
        version: i64,
    ) -> Result<usize, sqlx::Error> {
        let target = Self::get_transcript_version(pool, meeting_id, version)
            .await?
            .ok_or(sqlx::Error::RowNotFound)?;

        let segments: Vec<ArchivedSegment> = serde_json::from_str(&target.segments_json)
            .map_err(|e| {
                sqlx::Error::Protocol(format!("Version {} is not readable: {}", version, e))
            })?;

        let mut tx = pool.begin().await?;

        Self::archive_transcript(&mut *tx, meeting_id, "restore").await?;

        sqlx::query("DELETE FROM transcripts WHERE meeting_id = ?")
            .bind(meeting_id)
            .execute(&mut *tx)
            .await?;

        for segment in &segments {
            sqlx::query(
                "INSERT INTO transcripts
                 (id, meeting_id, transcript, timestamp, audio_start_time, audio_end_time, duration)
                 VALUES (?, ?, ?, ?, ?, ?, ?)",
            )
            .bind(&segment.id)
            .bind(meeting_id)
            .bind(&segment.transcript)
            .bind(&segment.timestamp)
            .bind(segment.audio_start_time)
            .bind(segment.audio_end_time)
            .bind(segment.duration)
            .execute(&mut *tx)
            .await?;
        }

        tx.commit().await?;
        Ok(segments.len())
    }

    /// Replaces the live summary with an archived version, archiving the current
    /// one first so the restore is itself undoable.
    pub async fn restore_summary_version(
        pool: &SqlitePool,
        meeting_id: &str,
        version: i64,
    ) -> Result<(), sqlx::Error> {
        let target = Self::get_summary_version(pool, meeting_id, version)
            .await?
            .ok_or(sqlx::Error::RowNotFound)?;

        let mut tx = pool.begin().await?;

        let current: Option<String> =
            sqlx::query_scalar("SELECT result FROM summary_processes WHERE meeting_id = ?")
                .bind(meeting_id)
                .fetch_optional(&mut *tx)
                .await?
                .flatten();

        if let Some(current) = current {
            Self::archive_summary(&mut *tx, meeting_id, &current, "restore").await?;
        }

        let now = Utc::now();
        sqlx::query(
            "UPDATE summary_processes SET result = ?, updated_at = ? WHERE meeting_id = ?",
        )
        .bind(&target.result_json)
        .bind(now)
        .bind(meeting_id)
        .execute(&mut *tx)
        .await?;

        sqlx::query("UPDATE meetings SET updated_at = ? WHERE id = ?")
            .bind(now)
            .bind(meeting_id)
            .execute(&mut *tx)
            .await?;

        tx.commit().await?;
        Ok(())
    }

    /// Removes both kinds of version for a meeting. Foreign keys are not
    /// enforced on this connection, so deletes are explicit.
    pub async fn delete_for_meeting(
        conn: &mut SqliteConnection,
        meeting_id: &str,
    ) -> Result<(), sqlx::Error> {
        sqlx::query("DELETE FROM transcript_versions WHERE meeting_id = ?")
            .bind(meeting_id)
            .execute(&mut *conn)
            .await?;

        sqlx::query("DELETE FROM summary_versions WHERE meeting_id = ?")
            .bind(meeting_id)
            .execute(&mut *conn)
            .await?;

        Ok(())
    }

    #[cfg(test)]
    async fn count(pool: &SqlitePool, table: &str, meeting_id: &str) -> i64 {
        sqlx::query_scalar(&format!(
            "SELECT COUNT(*) FROM {} WHERE meeting_id = ?",
            table
        ))
        .bind(meeting_id)
        .fetch_one(pool)
        .await
        .expect("count query")
    }

    async fn next_version(
        conn: &mut SqliteConnection,
        table: &str,
        meeting_id: &str,
    ) -> Result<i64, sqlx::Error> {
        // `table` is a hardcoded literal at every call site, never user input.
        let sql = format!(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM {} WHERE meeting_id = ?",
            table
        );

        sqlx::query_scalar(&sql)
            .bind(meeting_id)
            .fetch_one(&mut *conn)
            .await
    }

    async fn prune(
        conn: &mut SqliteConnection,
        table: &str,
        meeting_id: &str,
    ) -> Result<(), sqlx::Error> {
        let sql = format!(
            "DELETE FROM {t} WHERE meeting_id = ? AND version <= (
                 SELECT MAX(version) FROM {t} WHERE meeting_id = ?
             ) - ?",
            t = table
        );

        sqlx::query(&sql)
            .bind(meeting_id)
            .bind(meeting_id)
            .bind(MAX_VERSIONS_PER_MEETING)
            .execute(&mut *conn)
            .await?;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const MEETING: &str = "meeting-test";

    async fn test_pool() -> SqlitePool {
        let pool = SqlitePool::connect("sqlite::memory:")
            .await
            .expect("in-memory sqlite");
        sqlx::migrate!("./migrations")
            .run(&pool)
            .await
            .expect("migrations apply");

        sqlx::query("INSERT INTO meetings (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)")
            .bind(MEETING)
            .bind("Test Meeting")
            .bind("2026-08-15T00:00:00Z")
            .bind("2026-08-15T00:00:00Z")
            .execute(&pool)
            .await
            .expect("seed meeting");

        pool
    }

    async fn set_transcripts(pool: &SqlitePool, texts: &[&str]) {
        sqlx::query("DELETE FROM transcripts WHERE meeting_id = ?")
            .bind(MEETING)
            .execute(pool)
            .await
            .expect("clear transcripts");

        for (i, text) in texts.iter().enumerate() {
            sqlx::query(
                "INSERT INTO transcripts (id, meeting_id, transcript, timestamp, audio_start_time)
                 VALUES (?, ?, ?, ?, ?)",
            )
            .bind(format!("seg-{}-{}", text, i))
            .bind(MEETING)
            .bind(*text)
            .bind("00:00:00")
            .bind(i as f64)
            .execute(pool)
            .await
            .expect("insert transcript");
        }
    }

    async fn live_transcripts(pool: &SqlitePool) -> Vec<String> {
        sqlx::query_scalar("SELECT transcript FROM transcripts WHERE meeting_id = ? ORDER BY rowid")
            .bind(MEETING)
            .fetch_all(pool)
            .await
            .expect("read transcripts")
    }

    #[tokio::test]
    async fn archiving_an_empty_transcript_is_a_no_op() {
        let pool = test_pool().await;
        let mut conn = pool.acquire().await.expect("connection");

        let version = VersionsRepository::archive_transcript(&mut conn, MEETING, "retranscription")
            .await
            .expect("archive");

        assert_eq!(version, None);
        assert_eq!(VersionsRepository::count(&pool, "transcript_versions", MEETING).await, 0);
    }

    #[tokio::test]
    async fn transcript_versions_increment_per_snapshot() {
        let pool = test_pool().await;
        let mut conn = pool.acquire().await.expect("connection");

        set_transcripts(&pool, &["first"]).await;
        let v1 = VersionsRepository::archive_transcript(&mut conn, MEETING, "retranscription")
            .await
            .expect("archive");

        set_transcripts(&pool, &["second"]).await;
        let v2 = VersionsRepository::archive_transcript(&mut conn, MEETING, "retranscription")
            .await
            .expect("archive");

        assert_eq!((v1, v2), (Some(1), Some(2)));
    }

    #[tokio::test]
    async fn restoring_a_transcript_archives_the_current_one() {
        let pool = test_pool().await;
        let mut conn = pool.acquire().await.expect("connection");

        set_transcripts(&pool, &["original"]).await;
        VersionsRepository::archive_transcript(&mut conn, MEETING, "retranscription")
            .await
            .expect("archive");
        set_transcripts(&pool, &["retranscribed"]).await;

        let restored = VersionsRepository::restore_transcript_version(&pool, MEETING, 1)
            .await
            .expect("restore");

        assert_eq!(restored, 1);
        assert_eq!(live_transcripts(&pool).await, vec!["original"]);

        // The replaced transcript is itself recoverable
        let versions = VersionsRepository::list_transcript_versions(&pool, MEETING)
            .await
            .expect("list");
        assert_eq!(versions.len(), 2);
        assert_eq!(versions[0].reason, "restore");
        assert!(versions[0].segments_json.contains("retranscribed"));
    }

    #[tokio::test]
    async fn transcript_versions_are_pruned_to_the_cap() {
        let pool = test_pool().await;
        let mut conn = pool.acquire().await.expect("connection");
        set_transcripts(&pool, &["text"]).await;

        for _ in 0..MAX_VERSIONS_PER_MEETING + 5 {
            VersionsRepository::archive_transcript(&mut conn, MEETING, "retranscription")
                .await
                .expect("archive");
        }

        let versions = VersionsRepository::list_transcript_versions(&pool, MEETING)
            .await
            .expect("list");

        assert_eq!(versions.len() as i64, MAX_VERSIONS_PER_MEETING);
        // Newest kept, oldest dropped
        assert_eq!(versions[0].version, MAX_VERSIONS_PER_MEETING + 5);
        assert_eq!(versions[versions.len() - 1].version, 6);
    }

    #[tokio::test]
    async fn restoring_a_summary_swaps_the_live_result() {
        let pool = test_pool().await;
        let mut conn = pool.acquire().await.expect("connection");

        sqlx::query(
            "INSERT INTO summary_processes (meeting_id, status, created_at, updated_at, result)
             VALUES (?, 'completed', ?, ?, ?)",
        )
        .bind(MEETING)
        .bind("2026-08-15T00:00:00Z")
        .bind("2026-08-15T00:00:00Z")
        .bind(r#"{"markdown":"current"}"#)
        .execute(&pool)
        .await
        .expect("seed summary");

        VersionsRepository::archive_summary(
            &mut conn,
            MEETING,
            r#"{"markdown":"older"}"#,
            "regeneration",
        )
        .await
        .expect("archive");

        VersionsRepository::restore_summary_version(&pool, MEETING, 1)
            .await
            .expect("restore");

        let live: Option<String> =
            sqlx::query_scalar("SELECT result FROM summary_processes WHERE meeting_id = ?")
                .bind(MEETING)
                .fetch_one(&pool)
                .await
                .expect("read summary");

        assert_eq!(live.as_deref(), Some(r#"{"markdown":"older"}"#));

        // The summary that was replaced is recoverable in turn
        let versions = VersionsRepository::list_summary_versions(&pool, MEETING)
            .await
            .expect("list");
        assert_eq!(versions.len(), 2);
        assert_eq!(versions[0].reason, "restore");
        assert!(versions[0].result_json.contains("current"));
    }
}
