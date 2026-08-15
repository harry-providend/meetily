-- Archive superseded transcripts and summaries so retranscription and
-- regeneration stop destroying the previous copy.
-- Rows are written only when something is overwritten; `reason` records what
-- caused the snapshot, since the archived copy's own model is not knowable here.

CREATE TABLE IF NOT EXISTS transcript_versions (
    id            TEXT PRIMARY KEY NOT NULL,
    meeting_id    TEXT NOT NULL,
    version       INTEGER NOT NULL,
    reason        TEXT NOT NULL,
    segments_json TEXT NOT NULL,
    segment_count INTEGER NOT NULL,
    created_at    TEXT NOT NULL,
    UNIQUE(meeting_id, version),
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transcript_versions_meeting
    ON transcript_versions(meeting_id, version DESC);

CREATE TABLE IF NOT EXISTS summary_versions (
    id          TEXT PRIMARY KEY NOT NULL,
    meeting_id  TEXT NOT NULL,
    version     INTEGER NOT NULL,
    reason      TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE(meeting_id, version),
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_summary_versions_meeting
    ON summary_versions(meeting_id, version DESC);

-- Rescue any in-flight backup left by a generation that never completed.
INSERT INTO summary_versions (id, meeting_id, version, reason, result_json, created_at)
SELECT 'sumver-' || meeting_id || '-1', meeting_id, 1, 'regeneration', result_backup,
       COALESCE(result_backup_timestamp, updated_at)
FROM summary_processes
WHERE result_backup IS NOT NULL;
