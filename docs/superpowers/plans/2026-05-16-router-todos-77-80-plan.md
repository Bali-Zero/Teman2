# Router TODOs #77-#80 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close 4 numbered TODOs in backend-rag routers (dream MOCK_DB, dream scrape, debug logs, newsletter double-opt-in) with TDD + 1 commit per TODO.

**Architecture:**
- TODO #77: Add Postgres JSONB persistence for dream room state via new table `dream_room_state(user_id PK, state JSONB, updated_at)`. Drop in-memory `MOCK_DB`. Migration `178_dream_room_state.sql` with `-- === ROLLBACK ===` marker. Pool injected via `get_database_pool` like newsletter.
- TODO #78: Replace mock scraper with `httpx + BeautifulSoup4` (both already in `requirements.txt`). No paid Firecrawl dependency. Strip scripts/styles, extract title + first 5 paragraphs as `keyPoints`, blockquotes as `quotes`.
- TODO #79: Add `RingBufferLogHandler` (in-memory `collections.deque`) attached to root logger in `configure_logging()`. `/api/debug/logs` filters the deque by module/level. Zero new dependencies; works on Fly without flyctl auth.
- TODO #80: Implement `send_confirmation_email(email, token)` helper that reuses `backend.app.services.internal_email.send_internal_email` (Brevo via internal endpoint `/api/notifications/send-email`). Wire it into `subscribe()` for new + resent confirmation flows. Add token-only `GET /confirm` endpoint to support the existing `apps/mouth` frontend redirect link. Bonus: enforce confirmation_token uniqueness via partial unique index.

**Tech Stack:** FastAPI, asyncpg, httpx, beautifulsoup4, pytest, Pydantic v2.

---

## File Structure

**Create:**
- `apps/backend-rag/backend/db/migrations_v2/178_dream_room_state.sql`
- `apps/backend-rag/backend/db/migrations_v2/179_newsletter_confirmation_token_unique.sql`
- `apps/backend-rag/backend/services/scraping/__init__.py`
- `apps/backend-rag/backend/services/scraping/url_scraper.py`
- `apps/backend-rag/backend/app/services/log_ring_buffer.py`
- `apps/backend-rag/backend/tests/unit/app/routers/test_dream_router.py`
- `apps/backend-rag/backend/tests/unit/services/scraping/__init__.py`
- `apps/backend-rag/backend/tests/unit/services/scraping/test_url_scraper.py`
- `apps/backend-rag/backend/tests/unit/app/services/test_log_ring_buffer.py`
- `apps/backend-rag/backend/tests/unit/app/routers/test_newsletter_confirmation_email.py`

**Modify:**
- `apps/backend-rag/backend/app/routers/dream.py` (replace MOCK_DB, wire DB pool, wire URL scraper)
- `apps/backend-rag/backend/app/routers/debug.py` (wire `get_logs` to ring buffer)
- `apps/backend-rag/backend/app/routers/newsletter.py` (call send_confirmation_email, add GET /confirm)
- `apps/backend-rag/backend/app/setup/logging_config.py` (mount RingBufferLogHandler)
- `apps/backend-rag/backend/tests/unit/app/routers/test_debug.py` (extend get_logs test)

---

## TODO #77 — dream.py MOCK_DB → Postgres JSONB

### Current state
`apps/backend-rag/backend/app/routers/dream.py:54-77`
- Line 54-56: `MOCK_DB: dict[str, Any] = {}` (module-level in-memory dict)
- Line 61-70: `save_state(user_id, state)` writes to `MOCK_DB[user_id]`
- Line 73-77: `get_state(user_id)` reads from `MOCK_DB.get(user_id)`

### Root cause
TODO(#77) markers explicitly state "use Redis or Postgres" — Postgres chosen for durability + transactional consistency with the rest of the backend. No Redis tier on Fly today.

### Design fix
1. New migration `178_dream_room_state.sql` creating:
   ```sql
   CREATE TABLE IF NOT EXISTS dream_room_state (
       user_id     VARCHAR(255) PRIMARY KEY,
       state       JSONB        NOT NULL DEFAULT '{}'::jsonb,
       created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
       updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
   );
   ```
   Plus a `-- === ROLLBACK ===` section dropping the table. Squawk-compliant (no `DROP COLUMN`, no `CREATE INDEX CONCURRENTLY`, no defaults on existing data).

2. Refactor `save_state` / `get_state` to inject `pool=Depends(get_database_pool)`:
   - UPSERT via `INSERT INTO dream_room_state (user_id, state) VALUES ($1, $2::jsonb) ON CONFLICT (user_id) DO UPDATE SET state = EXCLUDED.state, updated_at = NOW()`.
   - **Anti jsonb-double-encoding** (per `discovery_jsonb_double_encoding_systemic_2026_05_14`): pool may have an init codec that encodes dict→json automatically; check by inspecting whether `get_database_pool` produces a pool with `init=init_db_connection`. If yes → pass `state` as Python dict (no `json.dumps`) and cast to `$2::jsonb`. If no codec → use `json.dumps(state)`. Verify empirically via test.

3. Remove module-level `MOCK_DB`.

### Test plan
- `test_dream_save_state_inserts_new_row` — happy path, asserts UPSERT row appears.
- `test_dream_save_state_updates_existing` — second save for same user_id updates row.
- `test_dream_get_state_returns_none_when_missing` — returns `{"success": True, "state": None}`.
- `test_dream_get_state_returns_dict_when_present`.
- Tests use a stub pool (`AsyncMock`) — no live DB needed for unit tests.

### Rollback
- `DROP TABLE IF EXISTS dream_room_state;` in `-- === ROLLBACK ===` section.
- Code rollback: revert single commit.

---

## TODO #78 — dream.py scrape via httpx + BeautifulSoup

### Current state
`apps/backend-rag/backend/app/routers/dream.py:80-103`
- `scrape_url(request: ScrapingRequest)` returns hardcoded mock content after `asyncio.sleep(1.5)`.

### Root cause
TODO(#78) asks "Firecrawl OR httpx+BS4 fallback". No `FIRECRAWL_API_KEY` in secrets; user rule "no paid API" → BS4 path only.

### Design fix
1. New module `backend/services/scraping/url_scraper.py`:
   ```python
   async def scrape_url(url: str, *, timeout: float = 10.0) -> ScrapedContent:
       """Fetch URL via shared httpx client, extract title + key paragraphs + blockquotes."""
   ```
2. Function signature returns a `ScrapedContent` Pydantic model with `title`, `keyPoints`, `quotes`. Caller (router) wraps it into `ScrapingResponse`.
3. URL validation: only `http://` / `https://` schemes; reject `file://`, `javascript:`, etc. (SSRF defense, basic level — does NOT block private IPs since the backend already serves on a private network).
4. Use `httpx.AsyncClient` with 10s timeout; on any exception return `success=False` + empty fields (mirroring the existing AI generate fallback).
5. Wire router to call `await scrape_url(request.url)`.

### Test plan
- `test_url_scraper_extracts_title` — mock httpx response with `<title>Hello</title>`.
- `test_url_scraper_extracts_paragraphs_as_key_points` — `<p>` tags become keyPoints.
- `test_url_scraper_extracts_blockquotes_as_quotes`.
- `test_url_scraper_strips_scripts_and_styles` — security sanity check.
- `test_url_scraper_rejects_non_http_url` — raises ValueError.
- `test_url_scraper_handles_http_error_gracefully` — returns success=False.
- `test_scrape_endpoint_uses_real_scraper` — router integration with monkey-patched `scrape_url`.

### Rollback
- Revert commit. Mock scraper still in git history.

---

## TODO #79 — debug.py /logs wired to ring buffer

### Current state
`apps/backend-rag/backend/app/routers/debug.py:108-141`
- Returns hardcoded placeholder dict.

### Root cause
TODO(#79) says "Loki or fly logs --json". Loki requires extra infra. `fly logs --json` via subprocess requires flyctl auth inside the container. Simpler: in-process ring buffer (last N records) — same approach as `request_tracing` middleware. Loki/fly logs remain available as future option.

### Design fix
1. New module `backend/app/services/log_ring_buffer.py`:
   ```python
   class RingBufferLogHandler(logging.Handler):
       def __init__(self, capacity: int = 2000): ...
       def emit(self, record): ...   # appends serialized record
       def snapshot(self, *, module=None, level=None, limit=100) -> list[dict]: ...
   ```
2. Module-level singleton `get_ring_buffer_handler()` so debug router and logging config use the same instance.
3. `configure_logging()` (in `apps/backend-rag/backend/app/setup/logging_config.py`) attaches the singleton to the root logger.
4. `/api/debug/logs` calls `get_ring_buffer_handler().snapshot(module=..., level=..., limit=...)` and returns `{"success": True, "logs": [...], "count": N}`.

### Test plan
- `test_ring_buffer_appends_records` — emit 3 records, snapshot returns 3.
- `test_ring_buffer_respects_capacity` — emit `capacity+10`, snapshot returns `capacity`.
- `test_ring_buffer_filter_by_module` — only matching `record.name`.
- `test_ring_buffer_filter_by_level` — only `level >= filter`.
- `test_ring_buffer_singleton_identity` — `get_ring_buffer_handler() is get_ring_buffer_handler()`.
- `test_get_logs_returns_ring_buffer` — debug router returns actual buffer content (extend existing `test_get_logs`).

### Rollback
- Revert commit. Old placeholder dict in git history.

---

## TODO #80 — newsletter.py double-opt-in email via Brevo

### Current state
`apps/backend-rag/backend/app/routers/newsletter.py:210-211`
- New-subscriber flow inserts row, generates `confirmation_token`, but the email is NOT sent (commented placeholder).
- Resubscribe + resend paths (lines 130-186) also don't send.

### Root cause
TODO(#80) requires double-opt-in email. Backend already has `confirmation_token` column (migration 033) and `send_internal_email` helper in `backend/app/services/internal_email.py`. Just need a thin wrapper + 3 callsites.

### Design fix
1. Add `send_confirmation_email(email: str, token: str, *, frontend_base_url: str | None = None) -> None` inside `newsletter.py` (private helper). Reads `PUBLIC_HOST` env var with default `https://balizero.com` (consistent with `funnel_email/scheduler.py` pattern). Builds confirm link `{base}/api/blog/newsletter/confirm?token={url-encoded}`. Renders minimal HTML body (English + Indonesian sentence). Logs success/failure.
2. Call `send_confirmation_email(email, token)` in **3** callsites: new subscriber, resubscribing path, resend-confirmation path.
3. Add `GET /api/blog/newsletter/confirm?token=...` endpoint that resolves subscriber by token alone (token is URL-safe 32-byte = 43 chars, indistinguishable in practice). Reuses the confirm logic; calls `invalidate_cache`. Returns `{success: bool, message: str}` (the mouth frontend already redirects to `/insights?newsletter=confirmed` on 200).
4. **Defense in depth:** migration `179_newsletter_confirmation_token_unique.sql` adds partial unique index `CREATE UNIQUE INDEX IF NOT EXISTS uq_newsletter_confirmation_token ON newsletter_subscribers (confirmation_token) WHERE confirmation_token IS NOT NULL;`. Prevents two unconfirmed subs ever sharing the same token (1-in-2^256 collision is theoretical, but cheap to enforce). Squawk note: requires `# squawk-ignore: prefer-text-field` if it complains; index on VARCHAR(64) is fine.
5. **Brevo regola fissa (CLAUDE.md):** `from=zantara@balizero.com` (already handled by `send_internal_email` — payload only contains `to`, `subject`, `body`, `cc`; the backend `/api/notifications/send-email` adapter sets the from header). No SDK Brevo terzo, no `notifications@`/`newsletter@`.

### Test plan
- `test_send_confirmation_email_calls_internal_email` — mock `send_internal_email`, verify it gets called with expected `to`, subject in English, body containing the link.
- `test_send_confirmation_email_uses_public_host_env` — `monkeypatch.setenv("PUBLIC_HOST", "https://example.com")` → link uses example.com.
- `test_send_confirmation_email_url_encodes_token` — token with non-URL-safe chars (we use `secrets.token_urlsafe` so they're already URL-safe; this is a regression-prevention test).
- `test_subscribe_new_calls_send_confirmation_email` — full subscribe flow with mocked pool + mocked sender.
- `test_subscribe_resubscribe_calls_send_confirmation_email`.
- `test_subscribe_resend_calls_send_confirmation_email`.
- `test_confirm_via_get_resolves_token_alone` — GET /confirm?token=X confirms the subscriber.
- `test_confirm_via_get_returns_404_for_invalid_token`.

### Rollback
- Revert commit. No data loss (token rows still exist, just unsent emails — admin can resend manually via existing endpoint or trigger script).
- Migration 179 rollback: `DROP INDEX IF EXISTS uq_newsletter_confirmation_token;`.

---

## Pre-deploy gate after each commit

```bash
cd /Users/nuzantara/Desktop/nuzantara-wt-router-todos/apps/backend-rag
PYTHONPATH=. /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python -c "from backend.app.dependencies import get_current_user; print('OK')"
```

Expected: `OK`. Fail → fix before next commit.

## Final verification before PR

```bash
PYTHONPATH=. .venv/bin/pytest \
  backend/tests/unit/services/scraping/ \
  backend/tests/unit/app/services/test_log_ring_buffer.py \
  backend/tests/unit/app/routers/test_dream_router.py \
  backend/tests/unit/app/routers/test_newsletter_confirmation_email.py \
  backend/tests/unit/app/routers/test_debug.py \
  -q --tb=short
```

Expected: all green.

## Out of scope

- Authentication on dream endpoints (`save_state`/`get_state` take `user_id` as plain string — pre-existing security gap, not part of this PR).
- Replacing `call_claude_with_retry` in `generate_content` with the OAuth CLI path (separate refactor).
- Rate limiting on `/scrape` (FastAPI middleware exists elsewhere; orthogonal).
- Loki / fly-logs integration for `/debug/logs` (ring buffer covers the immediate need; Loki is a future epic).
- Migrating frontend `apps/mouth/.../confirm/route.ts` to use POST + body (the GET shim added here closes the gap without changing frontend contract).
