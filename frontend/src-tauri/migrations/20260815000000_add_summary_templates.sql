-- Add summary_templates table; templates were previously JSON files on disk.
-- Built-ins are seeded at startup; user_modified marks rows the seeder must skip.
CREATE TABLE IF NOT EXISTS summary_templates (
    id            TEXT PRIMARY KEY NOT NULL,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL,
    sections_json TEXT NOT NULL,
    is_builtin    INTEGER NOT NULL DEFAULT 0,
    user_modified INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_summary_templates_updated_at ON summary_templates(updated_at);
