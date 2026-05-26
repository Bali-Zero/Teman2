---
date: 2026-05-27
domain: wr2
client_case: ig-layer-verify
sources:
  - apps/backend-rag/backend/services/publisher/ig_publisher.py (313 LOC)
  - apps/backend-rag/backend/services/measurer/ig_graph_sensor.py (153 LOC)
  - apps/backend-rag/backend/app/setup/service_initializer.py:1154-1167
  - apps/backend-rag/backend/services/sota_loop/m13_collect.py:66-84
  - apps/backend-rag/backend/app/setup/app_factory.py:595,606 (lifespan close hooks)
  - ~/Library/LaunchAgents/com.balizero.wr2.ig-metrics-analyst.weekly.plist (last mod 2026-05-10)
  - ~/Library/LaunchAgents/com.balizero.wr2.ig-scraper.daily.plist (last mod 2026-05-09)
  - ~/scripts/wr2-ig-metrics-analyst-run.sh (wrapper)
  - ~/.claude/skills/bali-zero-brand/_ig-metrics-scraper.py (Playwright, no Graph API)
---

## Verdict

**CODE_INCOMPLETE** — IGPublisher class is functionally complete + tested, but ZERO non-test caller exists in backend. Orchestrator integration missing: no router, no service registration, no scheduled job, no `_initialize_ig_publisher` analog. Pipeline cannot call `IGPublisher.publish()` today. Secrets injection is also a moving target (3 distinct env-var conventions across codebase).

## ig_publisher.py analysis

- **Path**: `apps/backend-rag/backend/services/publisher/ig_publisher.py`
- **LOC**: 313
- **Key functions**:
  - `IGPublisher.__init__(ig_user_id, access_token, graph_base, http_client, timeout)` — auto-reads env with fallback chain `IG_USER_ID` → `INSTAGRAM_ACCOUNT_ID` and `IG_LONG_LIVED_TOKEN` → `INSTAGRAM_ACCESS_TOKEN`; raises `PublisherError` if both missing.
  - `validate(draft) -> ValidationResult` — checks cover_image_url present, max 10 carousel items (cover+9 slides), caption ≤2200 chars.
  - `publish(draft) -> PublishResult` — 3-step Meta Graph flow: per-slide child container → parent CAROUSEL container → `/media_publish` → optional permalink fetch. Returns `PublishResult(ok, post_external_id, post_url, meta={carousel_items, parent_id})`.
  - `delete(post_external_id) -> bool` — best-effort DELETE.
  - `_create_child_container`, `_create_parent_container`, `_publish_parent`, `_fetch_permalink` — internal API call helpers.
  - `close_ig_publisher_client()` — module-level singleton AsyncClient close hook (Golden Rule #10).
- **Dependencies**: `httpx`, `backend.services.publisher.base` (Publisher, DraftPayload, SlidePayload, ValidationResult, PublishResult, PublisherError), `backend.services.war_room.models.Platform`.
- **Endpoint**: `https://graph.facebook.com/v20.0` (constant `DEFAULT_GRAPH_BASE`, overridable via ctor).
- **Error handling**: Top-level `try/except Exception` returns `PublishResult(ok=False, error=...)` with type+message; per-step `if not container_id` returns named-step failure. Non-200 responses logged at WARNING with body truncated to 300 chars. NO retry logic (comment line 18: "Orchestrator handles retries"). NO rate-limit handling. NO idempotency check (re-running same draft would create duplicate carousel).
- **Async**: fully async (`async def`). Module-level singleton client lazily allocated, closed in `app_factory.lifespan()`.

## ig_graph_sensor.py analysis

- **Path**: `apps/backend-rag/backend/services/measurer/ig_graph_sensor.py`
- **LOC**: 153
- **Key metrics**: per-post `IGPostMetrics(post_id, caption, format, timestamp, permalink, likes, comments, saves, reach, impressions=0, video_views=0)`. Account: `followers_count, media_count, biography, username`.
- **API pattern**:
  - `read_account_summary()` → `GET /{ig_user_id}?fields=followers_count,media_count,...`.
  - `read_posts(limit=25)` → `GET /{ig_user_id}/media?fields=id,caption,media_type,...` then per-media `_fetch_insights`.
  - `_fetch_insights(media_id, media_type)` → `GET /{media_id}/insights?metric=likes,comments,saved,reach[,video_views]`. Note: `impressions` deprecated in Graph v22+, dataclass keeps default=0 for forward compat.
- **Endpoint**: `https://graph.facebook.com/v21.0` (constant `GRAPH_API_BASE`, NOT overridable).
- **Auth model**: token + ig_user_id passed in ctor (no env fallback inside class). Caller responsible for sourcing.
- **Scope** (docstring line 9-11): "ONLY @balizero0 own account. Competitor posts scraped manually."
- **Scheduling assumptions**: docstring line 13 "Token renewal: Meta long-lived tokens expire ~60 days. Watchdog TBD Task 30." — watchdog NOT yet shipped.
- **Caller**: 1 non-test consumer = `sota_loop/m13_collect.py:72` — collects post insights at T+24h/T+72h/T+168h horizons for published WR2 posts.

## Secrets injection check

| Plist                                              | Path                                     | Last mod   | Injects IG vars?         | Notes                                                                                                                                                                                                          |
| -------------------------------------------------- | ---------------------------------------- | ---------- | ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `com.balizero.wr2.ig-metrics-analyst.weekly.plist` | `/Users/nuzantara/Library/LaunchAgents/` | 2026-05-10 | **N** (only HOME+PATH)   | Wrapper `~/scripts/wr2-ig-metrics-analyst-run.sh` does `source ~/.nuzantara-secrets.env` (line 19) — content not inspectable (permission).                                                                     |
| `com.balizero.wr2.ig-scraper.daily.plist`          | `/Users/nuzantara/Library/LaunchAgents/` | 2026-05-09 | **N** (only HOME+PATH)   | Calls `~/.claude/skills/bali-zero-brand/_ig-metrics-scraper.py` — uses Playwright stealth + logged-in `@balizero0` Chrome profile at `~/.chrome-cdp-profile/balizero0-ig`. NOT Graph API. Token-free workflow. |
| **`com.balizero.wr2.ig-publisher.*.plist`**        | —                                        | —          | **PLIST DOES NOT EXIST** | No LaunchAgent invokes IGPublisher.publish() on a schedule today.                                                                                                                                              |

**3 distinct env-var conventions across codebase** (incoherent SSOT):

1. `IG_USER_ID` + `IG_LONG_LIVED_TOKEN` (primary) — `ig_publisher.py` ctor
2. `INSTAGRAM_ACCOUNT_ID` + `INSTAGRAM_ACCESS_TOKEN` (fallback in publisher; primary in `service_initializer.py:1154-1155` for InstagramChannelAdapter messaging)
3. `IG_BUSINESS_ACCOUNT_ID` + `IG_GRAPH_API_TOKEN` (orthogonal pair in `m13_collect.py:67-68`) — neither matches publisher nor messaging convention.

Risk: any operator who sets vars under one convention will silently disarm consumers using a different convention. Spec must enforce single canonical name.

## Meta Graph smoke

**SKIPPED — operator-only verify needed.**

`~/.nuzantara-secrets.env` Read returned `permission denied` (expected per task constraint). No alternative path to extract token from in-session context (env vars not exported in current shell; no `os.environ` access via current MCP surface).

Operator-only verification command (run on Pro, NOT in this session):

```bash
source ~/.nuzantara-secrets.env
# Verify which convention is populated:
echo "IG_USER_ID=${IG_USER_ID:-MISSING}  IG_LONG_LIVED_TOKEN=${IG_LONG_LIVED_TOKEN:+SET ($((${#IG_LONG_LIVED_TOKEN})) chars)}"
echo "INSTAGRAM_ACCOUNT_ID=${INSTAGRAM_ACCOUNT_ID:-MISSING}  INSTAGRAM_ACCESS_TOKEN=${INSTAGRAM_ACCESS_TOKEN:+SET}"
echo "IG_BUSINESS_ACCOUNT_ID=${IG_BUSINESS_ACCOUNT_ID:-MISSING}  IG_GRAPH_API_TOKEN=${IG_GRAPH_API_TOKEN:+SET}"

# Endpoint reachability (use whichever token is set):
TOK="${IG_LONG_LIVED_TOKEN:-${INSTAGRAM_ACCESS_TOKEN:-${IG_GRAPH_API_TOKEN}}}"
curl -sf "https://graph.facebook.com/v20.0/me?access_token=${TOK}" | head -c 500
# Expect: {"name":"...","id":"..."}  → token valid
# 400/401/403 → token expired/invalid → rotate via Meta Business Suite

# Token expiry check:
curl -sf "https://graph.facebook.com/debug_token?input_token=${TOK}&access_token=${TOK}" | python3 -m json.tool
# Look for "expires_at": <unix_ts>. If unix_ts < now+7d → ROTATE within week.
```

## Wiring requirements per FASE B spec

For IGPublisher to be called by the WR2 orchestrator, the spec must address:

1. **Env-var canonicalization** (P1 blocker): pick ONE convention, deprecate the other two with explicit fallback chain or migration plan. Recommend: `IG_USER_ID` + `IG_LONG_LIVED_TOKEN` (already publisher primary, matches Meta's own docs naming).

2. **Service registration** in `service_initializer.py` (mirror `_initialize_channel_adapters` pattern at line 1119+):
   - Read env, call `IGPublisher(...)` ctor, register in a `publishers_registry` keyed by `Platform.INSTAGRAM`.
   - Register service status in `service_registry` (HEALTHY/DEGRADED).
   - Add `close_ig_publisher_client` to `app_factory.lifespan()` — **ALREADY WIRED** at `app_factory.py:595` (verify presence in spec).

3. **Orchestrator caller wiring** — currently zero. Spec must specify:
   - Trigger: cron LaunchAgent (`com.balizero.wr2.ig-publisher.*.plist`) OR HTTP router (`POST /api/wr2/publish/ig/{draft_id}`) OR queue worker consuming `wr2_drafts.state='approved'`.
   - Idempotency layer (IGPublisher has NONE): track `draft_id → post_external_id` in DB so re-runs don't duplicate-publish. Suggest column `war_room_drafts.published_post_id` UNIQUE.
   - Retry policy: comment line 18 says "Orchestrator handles retries" — spec must define retry budget (e.g. 3 attempts, exp backoff), how to distinguish transient (5xx, timeout) vs permanent (4xx 100/190 token-expired) failures.
   - Rate-limit handling: Meta enforces ~200 calls/hour/user. Spec must define throttle for bulk catch-up scenarios.

4. **Token rotation watchdog** (referenced in `ig_graph_sensor.py:13` as "TBD Task 30", not shipped): cron that queries `/debug_token` daily, alerts Telegram 7d before expiry, blocks publish if <24h to expiry.

5. **Pre-publish validation**: `IGPublisher.validate()` enforces only IG-format limits. Spec should also gate on:
   - Image URLs publicly reachable (Meta fetches them server-side — if private, `_create_child_container` returns no `id`).
   - Caption brand-voice approval (cross-ref bali-zero-brand skill if applicable).

6. **Error-state surfacing**: today `PublishResult(ok=False, error=str)` is returned but no caller exists to read it. Spec must define DLQ / Telegram alert / dashboard row when `ok=False`.

7. **Plist creation**: if cron-driven, create `com.balizero.wr2.ig-publisher.{cadence}.plist` mirroring existing WR2 plist structure (`/Users/nuzantara/Library/LaunchAgents/com.balizero.wr2.*.plist`). Wrapper must `source ~/.nuzantara-secrets.env` before invoking. Document StartCalendarInterval (e.g. hourly checkpoint of `approved`-state drafts).
