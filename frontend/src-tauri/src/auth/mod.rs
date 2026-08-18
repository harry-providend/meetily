//! Microsoft Entra ID sign-in. The app obtains tokens directly and presents them to `/server`.

pub mod commands;
pub mod config;
pub mod entra;
pub mod loopback;
pub mod pkce;
pub mod session;
