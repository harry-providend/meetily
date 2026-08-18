//! Client for our own backend (`/server`), as distinct from [`crate::api`]. Ownership comes from
//! the token's claims, so the client never sends a user id.

pub mod client;
pub mod commands;
pub mod dto;
pub mod meetings;
pub mod summaries;
pub mod templates;
pub mod versions;
