# Providend Meeting Assistant — backend

FastAPI resource server backing the desktop app. Validates the Entra ID access tokens the app
already obtains (see `docs/ENTRA_SIGN_IN.md`), and stores meetings, transcripts, summaries, and
notes in Postgres so access control lives somewhere a departed employee does not take home.

Not to be confused with `/backend`, which is an archived, unrelated legacy service.

## Architecture

Layered, deliberately in the shape of a Spring application:

```
routers/       Controllers. HTTP only -- no business logic, no DB access.
services/      Business logic. interfaces/ (ABCs) + implementations/ (Default*Service).
repositories/  Data access. interfaces/ (ABCs) + sqlalchemy/ (SqlAlchemy*Repository).
domain/        SQLAlchemy entities.
schemas/       Pydantic DTOs. Entities never leave the service layer.
dependencies/  The DI graph -- the one place interfaces bind to implementations.
```

Conventions: interfaces are bare nouns (`MeetingRepository`), implementations are prefixed
(`SqlAlchemyMeetingRepository`, `DefaultMeetingService`). Services depend on repository
*interfaces*, never on concrete classes. `mypy --strict` is a merge gate.

### How tenancy is enforced

`provide_current_user` is the only source of identity: it validates the bearer token and yields
an `AuthenticatedUser` carrying `oid` and `tid`. Every service method takes that object, and
every `MeetingRepository` method takes `owner_user_id` and `owner_tenant_id` as **required**
parameters — the interface has no unfiltered read at all.

That is the structural fix for `frontend/src-tauri/src/database/repositories/meeting.rs:12`,
which is a bare `SELECT * FROM meetings` with no ownership filter. Here, writing that query
would mean adding a new abstract method — a visible diff in review, not a forgotten `WHERE`.

Child aggregates (transcripts, summaries, notes) are scoped by `meeting_id` only. Their services
call `MeetingOwnershipGuard.require_owned_meeting` first, which raises `NotFoundException` —
**not** `Forbidden` — when the meeting belongs to someone else, so a caller cannot distinguish
"does not exist" from "not yours" and probe for other people's meeting ids.

### Deliberately absent

- **No user table.** Identity comes from the token per request. SCIM provisioning, if added
  later, is additive: a `users` table, a SCIM router with its own auth, and one `is_active`
  lookup inside `provide_current_user`.
- **No API-key storage.** The desktop app's `settings` / `transcript_settings` tables held
  per-user plaintext provider keys; they are not ported, and nothing here has an equivalent
  column. Provider config becomes admin policy.
- **No `licensing` table.** Nothing in the current desktop codebase references it.

## Running locally

```bash
uv venv --python 3.13
uv pip install -e ".[dev]"
cp .env.example .env          # then fill in ENTRA_API_APP_ID_URI

docker compose up -d postgres
alembic upgrade head
uvicorn app.main:create_app --factory --reload --port 8000
```

`/docs` serves the OpenAPI UI. `/health` is the only unauthenticated route.

## Tests

Three layers, each catching what the layer below cannot:

| Layer | Location | What it covers | Needs Postgres |
|---|---|---|---|
| Unit | `tests/unit` | Service logic against hand-written fakes implementing the repository ABCs: tenancy rules, last-writer-wins, timestamp parsing. Milliseconds, no I/O. | no |
| Integration | `tests/integration` | Repositories against real Postgres: `JSONB`, `TIMESTAMPTZ`, `ON DELETE CASCADE`, `IDENTITY` ordering — none of which behave the same on SQLite. | yes |
| API | `tests/api` | The real app end to end: HTTP → router → service → repository → Postgres. Catches a mis-wired DI graph, an unserialisable DTO, a wrong status code, and a route that forgot its auth dependency. | yes |

```bash
pytest                                    # all three (starts a Postgres container)
pytest tests/unit                          # no Postgres needed
MEETILY_TEST_DATABASE_URL=postgresql+asyncpg://... pytest   # reuse a running Postgres
mypy src/ tests/ scripts/
ruff check src/ tests/ scripts/
```

`tests/api/test_auth_boundary.py` walks the OpenAPI schema rather than a hardcoded list, so a
route added later without authentication fails the suite without anyone remembering to test it.

**What is not automated:** a genuine end-to-end run with a real Entra token. That needs an
interactive browser sign-in, and it is blocked on the app-registration prerequisite below. API
tests substitute the token *validator* only — header parsing and the 401 paths are still real
code. Keep the real-token check as a manual step at cutover.

## Blocking prerequisite: the token audience

The desktop app currently requests only `User.Read`, a Microsoft Graph scope, so its access
tokens carry `aud` = Graph — **not this backend**. Validating those as if they were meant for us
would be wrong. Before real tokens can be accepted:

1. Entra app registration → **Expose an API** → set an App ID URI and define a scope
   (e.g. `access_as_user`).
2. Append that scope to `SCOPES` in `frontend/src-tauri/src/auth/config.rs`.
3. Set `ENTRA_API_APP_ID_URI` here to match.

Dev tenant IDs are already real and in `.env.example`; staging and prod registrations are still
empty placeholders in the frontend's `.env.staging` / `.env.prod`.

Also outstanding on the Rust side: `APP_SERVER_URL` is a hardcoded `http://localhost:5167`, and
`commands.rs::access_token()` — doc-commented as "the seam the Phase 2 backend client will use" —
is still dead code.

## Migrating a device's SQLite data

```bash
# 1. Rehearse. Writes an audit report, touches nothing.
python scripts/migrate_sqlite_to_postgres.py \
    --sqlite-path ~/Library/Application\ Support/com.providend.meetingassistant/meetily.db \
    --owner-oid <entra-object-id> --owner-tenant-id <entra-tenant-id> --dry-run

# 2. Read the report, then run for real.
python scripts/migrate_sqlite_to_postgres.py ... \
    --database-url postgresql+asyncpg://... --acknowledge-dropped-tables
```

Every meeting is attributed to one owner, passed on the command line, because the local schema
has no ownership concept. The script refuses to run without `--acknowledge-dropped-tables`, so
dropping the settings and licensing tables is a decision someone made, not a silent default.

It handles, deliberately:

- **Three timestamp encodings** in the same logical column. Unparseable values are quarantined
  and reported, never defaulted to `now()` — that would manufacture false history.
- **Segment ordering.** SQLite's implicit `rowid` is the only record of transcript order, and it
  does not survive the move; the export reads `ORDER BY rowid` and writes an explicit
  per-meeting `sequence_number`. This is the one thing that cannot be recovered afterwards.
- **Orphaned children** whose parent meeting is gone: skipped and counted rather than failing the
  whole run on a foreign-key violation.
- **Duplicate `(meeting_id, version)`** rows, which SQLite's derived-string primary key could
  mask: reported as a blocker for manual review, never auto-deduplicated.
- **Re-runs**, via merge-on-natural-id plus `ON CONFLICT DO NOTHING` for version rows.

The audit report contains row counts and column names only — never a secret value — so it is
safe to attach to a cutover ticket. It is gitignored regardless.
