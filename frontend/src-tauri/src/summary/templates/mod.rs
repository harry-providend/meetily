//! Meeting summary template management
//!
//! Templates are stored per user by the backend. Those shipped with the app (bundled resource JSON
//! plus embedded constants) are pushed there at startup as builtins; the server skips rows the user
//! has edited, so edits survive app upgrades, and reset clears that flag so the next push restores
//! the shipped content. The embedded constants remain a fallback if the server has no row at all.
//!
//! The seeding rules themselves are tested server-side, where they are enforced.
//!
//! ```no_run
//! # async fn example() -> Result<(), String> {
//! use app_lib::summary::templates;
//!
//! let template = templates::get_template("daily_standup").await?;
//! let markdown = template.to_markdown_structure();
//! let instructions = template.to_section_instructions();
//! let available = templates::list_template_ids().await?;
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
