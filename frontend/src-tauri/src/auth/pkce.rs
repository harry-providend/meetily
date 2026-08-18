//! PKCE (RFC 7636). A desktop app holds no client secret, so an intercepted authorization code
//! would otherwise suffice to obtain tokens: send a hash up front, prove possession on redeem.

use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use base64::Engine;
use rand::Rng;
use sha2::{Digest, Sha256};

/// RFC 7636 permits 43-128 characters.
const VERIFIER_LEN: usize = 64;

/// Unreserved characters permitted in a code verifier by RFC 7636.
const VERIFIER_CHARS: &[u8] =
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~";

#[derive(Debug, Clone)]
pub struct Pkce {
    /// The secret. Never leaves this process.
    pub verifier: String,
    /// base64url(sha256(verifier)) -- safe to put in a URL.
    pub challenge: String,
}

impl Pkce {
    pub fn generate() -> Self {
        let mut rng = rand::thread_rng();
        let verifier: String = (0..VERIFIER_LEN)
            .map(|_| {
                let idx = rng.gen_range(0..VERIFIER_CHARS.len());
                VERIFIER_CHARS[idx] as char
            })
            .collect();

        let digest = Sha256::digest(verifier.as_bytes());
        let challenge = URL_SAFE_NO_PAD.encode(digest);

        Self {
            verifier,
            challenge,
        }
    }
}

/// Binds the callback to this sign-in attempt, so a replayed redirect is rejected.
pub fn random_state() -> String {
    uuid::Uuid::new_v4().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn verifier_length_is_within_rfc_bounds() {
        let pkce = Pkce::generate();
        assert!(pkce.verifier.len() >= 43 && pkce.verifier.len() <= 128);
    }

    #[test]
    fn verifier_uses_only_unreserved_characters() {
        let pkce = Pkce::generate();
        assert!(pkce
            .verifier
            .bytes()
            .all(|b| VERIFIER_CHARS.contains(&b)));
    }

    #[test]
    fn challenge_is_url_safe_and_unpadded() {
        let pkce = Pkce::generate();
        assert!(!pkce.challenge.contains('='));
        assert!(!pkce.challenge.contains('+'));
        assert!(!pkce.challenge.contains('/'));
    }

    #[test]
    fn challenge_matches_the_rfc_7636_reference_vector() {
        // Appendix B of RFC 7636.
        let verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk";
        let digest = Sha256::digest(verifier.as_bytes());
        assert_eq!(
            URL_SAFE_NO_PAD.encode(digest),
            "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        );
    }

    #[test]
    fn each_generation_is_distinct() {
        assert_ne!(Pkce::generate().verifier, Pkce::generate().verifier);
        assert_ne!(random_state(), random_state());
    }
}
