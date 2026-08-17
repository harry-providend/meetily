# Entra ID sign-in (Phase 1)

Client-side Microsoft sign-in for the desktop app. There is no backend in this
phase — Entra authenticates the user directly with the app.

## What this does and does not do

**Does:** gates app entry behind a Providend account, and gives the app the
signed-in user's identity (stable object ID, tenant, name, email).

**Does not:** enforce access to data. The app is local-first and works offline,
so a stored session and locally-stored meetings stay reachable. An offboarded
user with the app still installed is not hard-stopped by this alone. Real
enforcement arrives when the server holds the data (Phase 2). The value here is
the token plumbing Phase 2 builds on.

## One-time Azure setup

Needs someone with app-registration rights in the tenant.

1. **Portal → Microsoft Entra ID → App registrations → New registration**
2. **Name:** `Providend Meeting Assistant`
3. **Supported account types:** *Accounts in this organizational directory only*
   (single tenant)
4. **Redirect URI:** platform **Mobile and desktop applications**, value
   `http://localhost`
5. **Register.** From **Overview**, copy the **Application (client) ID** and the
   **Directory (tenant) ID**.
6. **Authentication** blade → confirm **Allow public client flows = Yes**. This
   is what permits PKCE without a client secret. If it is off, sign-in fails with
   a confusing `AADSTS7000218` error about a missing `client_secret`.
7. **API permissions** → Microsoft Graph → Delegated → `User.Read` (normally
   present by default). Grant admin consent if the tenant requires it.

Note on the redirect URI: Entra treats `http://localhost` specially and ignores
the port when matching, so the app binds an ephemeral port each time rather than
fighting over a fixed one. If you do hit a redirect-mismatch error, register the
exact `http://localhost:PORT` the app logs at sign-in.

## Configuring the app

Neither ID is a secret — they are identifiers, and a public client cannot hold a
secret by definition. Both are safe to commit.

Either fill in the constants:

```rust
// frontend/src-tauri/src/auth/config.rs
pub const TENANT_ID: &str = "<directory-tenant-id>";
pub const CLIENT_ID: &str = "<application-client-id>";
```

Or set environment variables, which take precedence:

```bash
export MEETILY_AUTH_TENANT_ID=<directory-tenant-id>
export MEETILY_AUTH_CLIENT_ID=<application-client-id>
./clean_run.sh
```

With neither set, the app shows an explicit "sign-in is not configured" panel
rather than pushing you into a broken browser flow.

## How the flow works

1. The app binds a loopback listener on `127.0.0.1:0` and builds an authorize URL
   carrying a PKCE `code_challenge` (S256) and a random `state`.
2. It opens the **system browser** — not an embedded webview — so the user sees
   the genuine Microsoft origin and tenant MFA / Conditional Access apply.
3. Microsoft redirects back to `http://localhost:PORT/?code=…&state=…`. The
   listener rejects any callback whose `state` does not match.
4. Rust exchanges the code plus the PKCE `code_verifier` for tokens, over TLS,
   directly with Entra.
5. The session (access token, refresh token, expiry, account) goes into the OS
   keychain: macOS Keychain, Windows Credential Manager, or Secret Service.

Tokens never cross into the webview. The frontend receives only identity fields.

The CSP needs no changes — the browser handles the interactive part and the token
exchange happens in Rust, so the webview never talks to Microsoft.

## Offline behaviour

A **stored** session counts as signed in even when the access token has expired.
Refresh is attempted opportunistically and its failure is logged, not fatal. Only
the complete absence of a stored session shows the sign-in screen. This is
deliberate: a meeting recorder that stops working when the network drops is worse
than one with a stale token.

`offline_access` is among the requested scopes, which is what yields the refresh
token. Without it the session would die roughly hourly and bounce the user back
to the browser.

## Testing it

1. Configure the two IDs, then `./clean_run.sh`.
2. You should land on the sign-in screen rather than the app.
3. Click **Sign in with Microsoft**; a browser opens.
4. Complete sign-in; the tab reports success and the app proceeds.
5. Your name or email appears above **Sign out** in the sidebar footer.
6. Restart the app — it should go straight in, no browser.
7. Turn off networking and restart — it should still go straight in.
8. **Sign out**, and confirm you are returned to the sign-in screen. Local
   meetings survive; sign-out clears the session, it does not wipe the device.

To confirm the keychain entry on macOS:

```bash
security find-generic-password -s com.providend.meetingassistant -a entra-session
```

Add `-w` to print the stored JSON — it contains live tokens, so treat that output
as a credential.

## Files

| Path | Role |
|---|---|
| `src-tauri/src/auth/config.rs` | Tenant/client IDs, scopes, endpoints |
| `src-tauri/src/auth/pkce.rs` | Code verifier and S256 challenge |
| `src-tauri/src/auth/loopback.rs` | Single-shot redirect listener, state check |
| `src-tauri/src/auth/entra.rs` | Authorize URL, code redemption, refresh |
| `src-tauri/src/auth/session.rs` | Session type, keychain I/O, ID-token claims |
| `src-tauri/src/auth/commands.rs` | `auth_get_session`, `auth_sign_in`, `auth_sign_out` |
| `src/contexts/AuthContext.tsx` | React session state |
| `src/components/AuthGate.tsx` | Gate ahead of the provider tree |
| `src/components/LoginScreen.tsx` | Sign-in UI |
| `src/services/authService.ts` | Typed command wrappers |
