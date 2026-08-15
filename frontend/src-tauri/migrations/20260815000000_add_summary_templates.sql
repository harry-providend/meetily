-- Move summary templates from JSON files on disk into SQLite.
--
-- Built-in templates (shipped as bundled resources / embedded constants) are
-- seeded into this table at startup with is_builtin = 1. Editing a built-in
-- template sets user_modified = 1, which makes the seeder skip it on subsequent
-- launches so user edits survive app upgrades. "Reset to default" clears the
-- flag and lets the seeder overwrite the row again.
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

-- Supports "recently edited first" ordering in the template picker.
CREATE INDEX IF NOT EXISTS idx_summary_templates_updated_at ON summary_templates(updated_at);
