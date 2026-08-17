//! Microsoft Entra ID sign-in. Client-side only -- Entra authenticates the user
//! directly with the app, so no backend of ours is involved yet.

pub mod commands;
pub mod config;
pub mod entra;
pub mod loopback;
pub mod pkce;
pub mod session;
