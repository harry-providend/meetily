//! Single-shot loopback listener that catches the Entra redirect.
//!
//! Hand-rolled rather than pulling in an HTTP server -- it serves one request and
//! stops. Entra ignores the port for `http://localhost`, so port 0 avoids
//! contending over a fixed one.

use anyhow::{anyhow, bail, Context, Result};
use std::io::{Read, Write};
use std::net::{Ipv4Addr, SocketAddr, TcpListener, TcpStream};
use std::time::{Duration, Instant};
use tracing::{debug, warn};
use url::Url;

/// How long to wait for the user to finish signing in before giving up.
const DEFAULT_TIMEOUT: Duration = Duration::from_secs(300);

/// Short: the browser sends headers immediately, so a slow connection is a probe.
const READ_TIMEOUT: Duration = Duration::from_secs(5);

/// Bounds allocation from a misbehaving client. Real callbacks are under 2 KiB.
const MAX_REQUEST_BYTES: usize = 16 * 1024;

pub struct LoopbackServer {
    listener: TcpListener,
    port: u16,
}

/// What the browser came back with.
pub enum Callback {
    Code(String),
    /// Entra reported a failure (user cancelled, consent denied, ...).
    Failed { error: String, description: String },
}

impl LoopbackServer {
    /// Binds an ephemeral port on the loopback interface only.
    pub fn bind() -> Result<Self> {
        let listener = TcpListener::bind(SocketAddr::from((Ipv4Addr::LOCALHOST, 0)))
            .context("failed to bind a loopback port for the sign-in redirect")?;
        let port = listener
            .local_addr()
            .context("failed to read the bound loopback port")?
            .port();
        debug!("Sign-in redirect listener bound on 127.0.0.1:{}", port);
        Ok(Self { listener, port })
    }

    pub fn port(&self) -> u16 {
        self.port
    }

    pub fn redirect_uri(&self) -> String {
        // Entra ignores the port for http://localhost, so the registration only
        // needs the bare host.
        format!("http://localhost:{}", self.port)
    }

    /// Blocks until the redirect arrives. Requests without `code`/`error` (favicon,
    /// speculative connections) are answered and ignored.
    pub fn wait_for_callback(self, expected_state: &str) -> Result<Callback> {
        self.wait_for_callback_with_timeout(expected_state, DEFAULT_TIMEOUT)
    }

    pub fn wait_for_callback_with_timeout(
        self,
        expected_state: &str,
        timeout: Duration,
    ) -> Result<Callback> {
        let deadline = Instant::now() + timeout;
        self.listener
            .set_nonblocking(false)
            .context("failed to configure the redirect listener")?;

        loop {
            if Instant::now() >= deadline {
                bail!("timed out waiting for the browser sign-in to complete");
            }

            let (mut stream, _peer) = match self.listener.accept() {
                Ok(pair) => pair,
                Err(e) => {
                    warn!("Redirect listener accept failed: {}", e);
                    continue;
                }
            };

            let request = match read_request_line(&mut stream) {
                Ok(line) => line,
                Err(e) => {
                    debug!("Ignoring unreadable request on redirect listener: {}", e);
                    continue;
                }
            };

            let target = match request_target(&request) {
                Some(t) => t,
                None => {
                    respond(&mut stream, "Waiting for sign-in...");
                    continue;
                }
            };

            match parse_callback(&target, expected_state) {
                Ok(Some(outcome)) => {
                    let body = match &outcome {
                        Callback::Code(_) => "Signed in. You can close this tab and return to the app.",
                        Callback::Failed { .. } => {
                            "Sign-in did not complete. You can close this tab and try again."
                        }
                    };
                    respond(&mut stream, body);
                    return Ok(outcome);
                }
                Ok(None) => {
                    // Not the callback (favicon, preflight, bare '/').
                    respond(&mut stream, "Waiting for sign-in...");
                }
                Err(e) => {
                    respond(&mut stream, "Sign-in could not be verified. Please try again.");
                    return Err(e);
                }
            }
        }
    }
}

fn read_request_line(stream: &mut TcpStream) -> Result<String> {
    stream
        .set_read_timeout(Some(READ_TIMEOUT))
        .context("failed to set read timeout")?;

    let mut buf = Vec::new();
    let mut chunk = [0u8; 1024];

    loop {
        let n = stream.read(&mut chunk).context("failed to read request")?;
        if n == 0 {
            break;
        }
        buf.extend_from_slice(&chunk[..n]);

        // The request line is all we need; stop as soon as we have a full line.
        if buf.windows(2).any(|w| w == b"\r\n") || buf.contains(&b'\n') {
            break;
        }
        if buf.len() >= MAX_REQUEST_BYTES {
            bail!("request exceeded {} bytes", MAX_REQUEST_BYTES);
        }
    }

    let text = String::from_utf8_lossy(&buf);
    let first = text
        .lines()
        .next()
        .ok_or_else(|| anyhow!("empty request"))?
        .to_string();
    Ok(first)
}

/// Pulls the path+query out of a request line like `GET /?code=x HTTP/1.1`.
fn request_target(request_line: &str) -> Option<String> {
    let mut parts = request_line.split_whitespace();
    let _method = parts.next()?;
    let target = parts.next()?;
    Some(target.to_string())
}

/// `Ok(None)` = not the callback, keep listening. `Err` = arrived but untrusted,
/// which must abort the sign-in.
fn parse_callback(target: &str, expected_state: &str) -> Result<Option<Callback>> {
    // A relative target needs a base to parse against; the base is discarded.
    let url = Url::parse("http://localhost")
        .and_then(|base| base.join(target))
        .context("failed to parse redirect target")?;

    let mut code = None;
    let mut state = None;
    let mut error = None;
    let mut error_description = None;

    for (key, value) in url.query_pairs() {
        match key.as_ref() {
            "code" => code = Some(value.to_string()),
            "state" => state = Some(value.to_string()),
            "error" => error = Some(value.to_string()),
            "error_description" => error_description = Some(value.to_string()),
            _ => {}
        }
    }

    if code.is_none() && error.is_none() {
        return Ok(None);
    }

    // Must match on success and failure alike, or we report on someone else's
    // sign-in attempt.
    match state.as_deref() {
        Some(s) if s == expected_state => {}
        Some(_) => bail!("sign-in state did not match; ignoring this redirect"),
        None => bail!("sign-in redirect was missing its state parameter"),
    }

    if let Some(error) = error {
        return Ok(Some(Callback::Failed {
            description: error_description.unwrap_or_default(),
            error,
        }));
    }

    Ok(Some(Callback::Code(
        code.ok_or_else(|| anyhow!("redirect had no authorization code"))?,
    )))
}

fn respond(stream: &mut TcpStream, message: &str) {
    let body = format!(
        "<!doctype html><meta charset=\"utf-8\"><title>Sign-in</title>\
         <body style=\"font-family:system-ui,sans-serif;padding:3rem;text-align:center\">\
         <p>{}</p></body>",
        message
    );
    let response = format!(
        "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
        body.len(),
        body
    );
    let _ = stream.write_all(response.as_bytes());
    let _ = stream.flush();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extracts_request_target() {
        assert_eq!(
            request_target("GET /?code=abc&state=xyz HTTP/1.1").as_deref(),
            Some("/?code=abc&state=xyz")
        );
        assert_eq!(request_target("garbage"), None);
    }

    #[test]
    fn accepts_matching_code() {
        let out = parse_callback("/?code=abc&state=xyz", "xyz").unwrap();
        match out {
            Some(Callback::Code(c)) => assert_eq!(c, "abc"),
            _ => panic!("expected a code"),
        }
    }

    #[test]
    fn ignores_requests_without_code_or_error() {
        assert!(parse_callback("/favicon.ico", "xyz").unwrap().is_none());
        assert!(parse_callback("/", "xyz").unwrap().is_none());
    }

    #[test]
    fn rejects_mismatched_state() {
        // The whole point of state: a redirect we did not initiate must not be
        // accepted as our sign-in.
        assert!(parse_callback("/?code=abc&state=wrong", "xyz").is_err());
    }

    #[test]
    fn rejects_missing_state() {
        assert!(parse_callback("/?code=abc", "xyz").is_err());
    }

    #[test]
    fn surfaces_entra_errors_with_matching_state() {
        let out = parse_callback(
            "/?error=access_denied&error_description=User+cancelled&state=xyz",
            "xyz",
        )
        .unwrap();
        match out {
            Some(Callback::Failed { error, description }) => {
                assert_eq!(error, "access_denied");
                assert_eq!(description, "User cancelled");
            }
            _ => panic!("expected a failure"),
        }
    }

    #[test]
    fn error_with_bad_state_is_still_rejected() {
        assert!(parse_callback("/?error=access_denied&state=wrong", "xyz").is_err());
    }

    #[test]
    fn binds_a_loopback_port() {
        let server = LoopbackServer::bind().unwrap();
        assert!(server.port() > 0);
        assert_eq!(
            server.redirect_uri(),
            format!("http://localhost:{}", server.port())
        );
    }
}
