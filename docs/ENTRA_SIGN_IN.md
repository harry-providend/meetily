# Entra ID sign-in and environments

Client-side Microsoft sign-in. The app obtains tokens from Entra directly and
presents them to `/server`, which validates them and holds the meeting data.

## What this does and does not do

**Does:** gates app entry behind a Providend account and gives the app the user's
identity (stable object ID, tenant, name, email).

**Does not:** by itself enforce access to data — that is the server's job. Sign-in
yields an access token whose audience is our API scope, and `/server` scopes every
read and write to the token's `oid`/`tid`. Meetings, transcripts and summaries live
there, so revoking the account cuts off the data. What stays on the device is
machine state (downloaded models, audio device preferences) and the recordings
themselves, which are not yet uploaded.

## Environments

Three environments, installable side by side. The bundle identifier decides which
is running, so it cannot drift from the build.

| | Identifier | Recordings | Data dir |
|---|---|---|---|
| dev | `com.providend.meetingassistant.dev` | `meetily-recordings-dev` | separate |
| staging | `…assistant.staging` | `meetily-recordings-staging` | separate |
| prod | `…assistant` | `meetily-recordings` | separate |

Because the identifier differs, the OS gives each its own application-data
directory — so database, models, and preference stores isolate automatically.
Recordings and keychain entries live elsewhere and are suffixed explicitly.
Non-production builds carry a badge in the UI and a tagged window title.

Prod keeps the unsuffixed names so existing installs and recordings still resolve.

### Running and building

```bash
pnpm tauri:dev              # dev (default)
pnpm tauri:dev:staging
pnpm tauri:dev:prod

pnpm tauri:build            # prod (default)
pnpm tauri:build:dev
pnpm tauri:build:staging
```

`--config src-tauri/tauri.<env>.conf.json` is what switches the identifier. Those
overlay files are *merged* into the base `tauri.conf.json`, so permissions, CSP,
and bundle settings are inherited — they only override `productName` and
`identifier`. Note the merge is a JSON merge-patch, which **replaces arrays**, so
never override an array field (like `app.windows`) in an overlay.

### Configuration

Per-environment values live in `src-tauri/.env.dev`, `.env.staging`, `.env.prod`:

```
AUTH_TENANT_ID=
AUTH_CLIENT_ID=
API_BASE_URL=        # /server base URL; MEETILY_API_BASE_URL overrides at runtime
```

These are committed and baked into the binary by `build.rs` at compile time — an
installed app has no `.env` beside it to read. All three are compiled in; the
running one is selected at runtime from the identifier.

**Non-secret values only.** Never an API key, client secret, connection string, or
password: anyone with the binary can read these out of it. Entra tenant and client
IDs are safe because they are identifiers, not credentials — a desktop app is a
"public client" that cannot hold a secret at all.

Runtime overrides for ad-hoc testing:

```bash
MEETILY_AUTH_TENANT_ID=… MEETILY_AUTH_CLIENT_ID=… pnpm tauri:dev
MEETILY_ENV=staging pnpm tauri:dev     # staging settings, dev data dirs
```

## One-time Azure setup

Needs app-registration rights. Repeat per environment if you want separate
registrations; pointing all three at one to begin with is fine.

1. **Entra ID → App registrations → New registration**
2. **Supported account types:** *this organizational directory only* (single tenant)
3. **Redirect URI:** platform **Mobile and desktop applications**, value `http://localhost`
4. **Register**, then copy **Application (client) ID** and **Directory (tenant) ID** from Overview
5. **Authentication** → **Allow public client flows = Yes**. Without this, sign-in
   fails with `AADSTS7000218` complaining about a missing `client_secret`.
6. **API permissions** → Graph → Delegated → `User.Read`. Grant admin consent if required.

Entra ignores the port for `http://localhost`, so the app binds an ephemeral port
rather than contending over a fixed one. If you hit a redirect mismatch, register
the exact `http://localhost:PORT` the app logs.

## How the flow works

1. Bind a loopback listener; build an authorize URL with a PKCE `code_challenge`
   (S256) and random `state`.
2. Open the **system browser** — not a webview — so the user sees the genuine
   Microsoft origin and tenant MFA / Conditional Access apply.
3. Microsoft redirects to `http://localhost:PORT/?code=…&state=…`. A mismatched
   `state` is rejected.
4. Rust exchanges the code plus the PKCE verifier for tokens, over TLS.
5. The session goes to the OS keychain (Keychain / Credential Manager / Secret
   Service), keyed per environment.

Tokens never reach the webview. The CSP needs no changes: the browser handles the
interactive part and the token exchange happens in Rust.

## Offline behaviour

A **stored** session counts as signed in even with an expired access token.
Refresh is opportunistic and its failure is logged, not fatal. Only a completely
absent session shows the sign-in screen — a recorder that stops working when the
network drops is worse than one holding a stale token.

`offline_access` is requested, which is what yields the refresh token.

## Testing

1. `pnpm tauri:dev` → sign-in screen, with a **DEV** badge.
2. Sign in; a browser opens; complete it; the app proceeds.
3. Your name/email appears above **Sign out** in the sidebar footer.
4. Restart → straight in, no browser.
5. Disable networking and restart → still straight in.
6. **Sign out** → back to the sign-in screen; local meetings survive.
7. Run prod (`pnpm tauri:dev:prod`) and confirm it asks you to sign in again —
   proving the keychain entries are separate.

Inspect the keychain entry on macOS:

```bash
security find-generic-password -s com.providend.meetingassistant.dev -a entra-session
```

Add `-w` to print the stored JSON. It contains live tokens — treat as a credential.

## Files

| Path | Role |
|---|---|
| `src-tauri/src/environment.rs` | Environment detection and per-env settings |
| `src-tauri/build/env_config.rs` | Bakes `.env.<env>` in at compile time |
| `src-tauri/tauri.{dev,staging}.conf.json` | Identifier overlays |
| `src-tauri/src/auth/pkce.rs` | Code verifier and S256 challenge |
| `src-tauri/src/auth/loopback.rs` | Redirect listener, state check |
| `src-tauri/src/auth/entra.rs` | Authorize URL, code redemption, refresh |
| `src-tauri/src/auth/session.rs` | Session type, keychain I/O, ID-token claims |
| `src-tauri/src/auth/commands.rs` | `auth_get_session`, `auth_sign_in`, `auth_sign_out` |
| `src/contexts/AuthContext.tsx` | React session state |
| `src/components/AuthGate.tsx` | Gate ahead of the provider tree |
| `src/components/EnvironmentBadge.tsx` | Non-production marker |
