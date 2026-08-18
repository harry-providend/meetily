//! Client for our own backend (`/server`), as distinct from [`crate::api`]. Every request carries
//! the Entra access token and the server derives ownership from its claims, so the client never
//! sends a user id.

pub mod client;
pub mod commands;
