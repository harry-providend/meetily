# Meeting Summary Templates

This directory contains the template definitions that ship with the app. They are
bundled as Tauri resources and seeded into the `summary_templates` table of the
app database at startup.

**Templates are stored in SQLite, not on disk.** The JSON files here are seed data.
To change a template at runtime, use the in-app editor (Template → Manage
templates…) rather than editing these files.

## Available Templates

### 1. `daily_standup.json`
Time-boxed daily updates template designed for engineering/product teams.

**Sections:**
- Date
- Attendees
- Yesterday (completed work)
- Today (planned work)
- Blockers
- Notes

### 2. `standard_meeting.json`
General-purpose meeting notes template focusing on key outcomes and actions.

**Sections:**
- Summary
- Key Decisions
- Action Items
- Discussion Highlights

## Template Structure

Each template JSON file follows this schema:

```json
{
  "name": "Template Name",
  "description": "Brief description of the template's purpose",
  "sections": [
    {
      "title": "Section Title",
      "instruction": "Instructions for the LLM on what to extract/include",
      "format": "paragraph|list|string",
      "item_format": "Optional: Markdown table format for list items"
    }
  ]
}
```

## Custom Templates

Custom templates are created and edited in the app (Template → Manage templates…)
and stored in the `summary_templates` table.

### Seeding and user edits

Templates in this directory are seeded with `is_builtin = 1` on every launch.
Editing a built-in sets `user_modified = 1`, which makes the seeder skip that row
so the edit survives app upgrades. "Reset to default" clears the flag and lets the
next seed pass restore the shipped content. Built-ins can be edited and reset, but
not deleted; user-authored templates can be deleted.

### Legacy on-disk templates

Before templates moved into SQLite, custom templates were read from:

- **macOS**: `~/Library/Application Support/Meetily/templates/`
- **Windows**: `%APPDATA%\Meetily\templates\`
- **Linux**: `~/.config/Meetily/templates/`

Any JSON files still in that directory are imported once at startup, after which
the directory is renamed to `templates.imported`. Files whose id already exists in
the database are skipped rather than overwriting it.

## Template Fields

### Root Level
- `name` (required): Display name for the template
- `description` (required): Brief explanation of the template's use case
- `sections` (required): Array of section definitions

### Section Object
- `title` (required): Section heading text
- `instruction` (required): LLM guidance for this section
- `format` (required): One of `"paragraph"`, `"list"`, or `"string"`
- `item_format` (optional): Markdown formatting hint for list items (e.g., table structure)
- `example_item_format` (optional): Alternative formatting hint

## Usage in Code

Templates are loaded through the `templates` module, which reads from the database:

```rust
use crate::summary::templates;

// Get a specific template
let template = templates::get_template(pool, "daily_standup").await?;

// List available template ids
let available = templates::list_template_ids(pool).await?;

// Validate template JSON before saving
let validated = templates::validate_and_parse_template(&json)?;
```

Seeding runs from `DatabaseManager::new`, which every startup path goes through
(normal launch, fresh install, legacy database import).

## Tauri Commands

| Command | Purpose |
| --- | --- |
| `api_list_templates` | List all templates with `is_builtin` / `user_modified` flags |
| `api_get_template_details` | Full definition, including per-section instructions |
| `api_save_template` | Create (omit `id`) or update a template |
| `api_delete_template` | Delete a user-authored template |
| `api_reset_template` | Restore a built-in to its shipped definition |
| `api_validate_template` | Validate a raw template JSON string |
