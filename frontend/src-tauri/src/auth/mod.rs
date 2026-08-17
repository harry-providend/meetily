//! Microsoft Entra ID sign-in for the desktop app.
//!
//! Phase 1 of the private-deployment work: identity only, entirely client-side.
//! Entra authenticates the user directly with the app, so no backend of ours is
//! involved yet. See `commands` for the offline-tolerance rules and the limits
//! of what client-side sign-in actually enforces.

pub mod commands;
pub mod config;
pub mod entra;
pub mod loopback;
pub mod pkce;
pub mod session;
