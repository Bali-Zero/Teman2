---
date: 2026-05-13
component: wr2-orchestrator
status: draft (design phase, not yet implemented)
author: Antonello + Claude Opus 4.7
cross_llm_panel: Gemini 3.1 Pro + GPT-5.5 codex + DeepSeek V4 Pro
related_branch: feat/wr2-canva-pdf-render-2026-05-13
supersedes: scripts/wr2_canva_apply.py (legacy, to be disabled)
---

# WR2 Orchestrator PDF Render Design

End-to-end pipeline closing the loop `slides.json → PDF → Tigris → Canva
import` without an LLM in the orchestration path. Replaces the legacy
`scripts/wr2_canva_apply.py` (`claude -p APPLICA_WAR_ROOM.md` subprocess
with 50% MCP cold-fail rate documented in 7 days of telemetry).

## 1. Background

### 1.1 Existing state at design time (2026-05-13)

| Component | Status | Notes |
|---|---|---|
| `scripts/wr2_canva_pdf_render.py` (renderer) | ✅ shipped on branch | 1176 LOC, 12 layout families, ReportLab text-layered PDF |
| `scripts/wr2_canva_apply.py` (legacy orchestrator) | ⚠️ kill-switch OFF | Plist boot-out 2026-05-13. PG `system_settings.wr2_canva_renderer_enabled='false'`. Plist file preserved on disk |
| Yellow badge WCAG AAA | ✅ commit 940fc77 in ~/.claude | Article 14.4 |
| Constitution Article 15 (5 banned type-as-design) | ✅ commit 9cb50c2 in ~/.claude | |
| Smoke PDFs v2 | ✅ visually approved | `/tmp/wr2_smoke_v2.pdf` (6pp KEP-71), `/tmp/wr2_parq_v2.pdf` (11pp Parq Ambassador) |
| Adapter legacy schema → v2 | ✅ working draft | `/tmp/wr2_legacy_adapter.py` (130 LOC) |
| Canva MCP dynamic client registration | ✅ verified empirically | `POST mcp.canva.com/register` returns 201 + client_id |

### 1.2 Why a new orchestrator

The legacy `wr2_canva_apply.py` shells out to `claude -p` with the
`canva-apply` skill (~1200 LOC of MCP element_id remapping). It carries
inherent fragility:

- 50% cold-fail rate on MCP Canva (`MCP_NOT_AVAILABLE_SENTINELS` retry
  pattern). Empirical telemetry 2026-05-07 → 2026-05-13.
- 25-32 minute subprocess execution per draft. The Fly Postgres tunnel
  closes idle TCP sockets inside this window — observed crash
  2026-05-07 23:53 → 00:26 UTC, `_persist_canva_result` raised
  `ConnectionDoesNotExistError`.
- Master template `DAHJEkWpkzY` required structural validation (Phase
  -1, see cicatrix-scars-archive entry "WR2 master template
  structural validation gap"). The new flow bypasses master templates
  entirely.

The new pipeline runs **deterministic**: PG select → ReportLab
subprocess → boto3 Tigris upload → Canva MCP `import-design-from-url`
→ PG update. 5 steps, ~5-15 seconds per draft, no LLM in the loop.

### 1.3 Architectural decisions log

| ID | Decision | Approved by | Date |
|---|---|---|---|
| D0 | Orchestrator runtime: Python + httpx + official `mcp` SDK 1.12.4 (NOT claude -p subprocess, NOT OpenClaw+GPT-5.5) | Antonello + 3-LLM panel | 2026-05-13 |
| D1 | File location: NEW `scripts/wr2_canva_pdf_apply.py` accanto al legacy (rollback-friendly) | Antonello | 2026-05-13 |
| D2 | Legacy slides_json schema: adapter inline in orchestrator (riusa `/tmp/wr2_legacy_adapter.py` as `_schema_adapter.py`) | Antonello | 2026-05-13 |
| D3 (v1, discarded) | OAuth token storage: shared `~/.mcp-auth/mcp-remote-0.1.37/` cache | rejected after 3-LLM panel | 2026-05-13 |
| D3 (v3, final) | OAuth token storage: orchestrator-owned `~/.config/wr2/canva_tokens.json` + dedicated bootstrap script + HMAC integrity + proactive refresh + flock + dynamic client registration | Antonello + 3-LLM panel + empirical verify | 2026-05-13 |

### 1.4 Cross-LLM design-review trail

This spec passed through a structured 3-LLM panel review at each section
(rule established 2026-05-13, memory `feedback_always_review_spec_with_4_llm.md`).
Convergent flaws caught by panel:

- **OAuth client_id binding** (v1 → v2 pivot): all 3 LLMs identified
  that tokens are bound to `client_id` at registration time. Sharing
  the `mcp-remote` cache would cross-corrupt the Claude Code interactive
  session. → drove pivot to orchestrator-owned storage.
- **mtime compare-before-replace** (v2 → v3 pivot): DeepSeek V4 Pro
  caught that mtime check inside flock causes self-lockout if any
  non-flocking process touches the file. → removed in v3.
- **launchd restart loop** (v2 → v3 pivot): both Gemini and DeepSeek
  flagged that `SuccessfulExit=true` alone doesn't prevent loops on
  exit 4/5/7. v3 uses array form `SuccessfulExit: [0, 4, 5, 7]`.
- **Token expiry race** (v2 → v3 pivot): Gemini caught absence of
  proactive refresh. v3 adds 5min margin + 0-15s jitter.

Empirical verifications that overruled panel claims:

- **Canva dynamic client registration**: 2/3 LLMs claimed "Canva
  requires manual Developer Portal registration." Live HTTP POST to
  `mcp.canva.com/register` returned 201 with valid `client_id`. Panel
  wrong. Stored as fact `canva-mcp-dynamic-client-registration`.

Cost of panel: ~$0.03 DeepSeek + 0 Gemini + 0 codex = $0.03 for entire
spec. Wall time: ~5min for 2 rounds.

## 2. Architecture

### 2.1 High-level diagram

```
                ┌──────────────────────────────────────────────────────┐
                │  com.balizero.wr2.canva-renderer.plist  (every 5min) │
                │  exec: python3 scripts/wr2_canva_pdf_apply.py        │
                └────────────────────────┬─────────────────────────────┘
                                         │
                                         ▼
            ┌────────────────────────────────────────────────────────┐
            │  scripts/wr2_canva_pdf_apply.py  (orchestrator)        │
            │                                                        │
            │  1. kill_switch_check (PG SELECT)                      │
            │  2. fetch_ready_drafts (PG SELECT, LIMIT 3)            │
            │  3. for draft in drafts:                               │
            │     a. adapt_legacy_schema if needed                   │
            │     b. write slides_json → /tmp/slides_<id>.json       │
            │     c. subprocess.run(wr2_canva_pdf_render.py)         │
            │        → /tmp/wr2_<id>.pdf                             │
            │     d. boto3.put_object → Tigris s3://...wr2-pdf/<id>  │
            │     e. mcp_session.call_tool(import-design-from-url)   │
            │        + move-item-to-folder  (WR2 Drafts 2026)        │
            │     f. PG UPDATE canva_design_id, canva_edit_url,      │
            │        status='rendered'                               │
            │     g. Telegram notify                                 │
            │  4. log telemetry JSONL (riuso pattern legacy)         │
            └────────────────────────────────────────────────────────┘
                            │           │              │
                ┌───────────┼───────────┼──────────────┼─────────────┐
                ▼           ▼           ▼              ▼             ▼
            asyncpg      ReportLab   boto3        mcp.ClientSession  urllib
            (PG)       (subprocess)  (Tigris)     (Canva HTTP MCP)   (Telegram)
```

### 2.2 Module decomposition

| Module | LOC est. | Responsibility | Isolated test |
|---|---|---|---|
| `_pg.py` | 80 | asyncpg connect, kill switch, fetch drafts, persist result | mock `asyncpg.Connection` |
| `_schema_adapter.py` | 130 | Detect legacy schema (`slide_type` present, no `layout_family`) + adapt | Pure function, 3 fixture drafts |
| `_pdf_pipeline.py` | 60 | subprocess `wr2_canva_pdf_render` + verify file size > 0 | tmp_path fixture |
| `_tigris.py` | 90 | boto3 `put_object` with 3 retry + public URL build | `moto` mock S3 |
| `_canva_mcp.py` | 120 | `mcp.ClientSession` init + `call_tool` import-design + move-to-folder | mock `streamable_http_client` |
| `_token_storage.py` | 180 | `OrchestratorTokenStorage(TokenStorage)` with flock + HMAC + proactive refresh | tmp dir fixture |
| `_telegram.py` | 40 | Best-effort notify (legacy pattern) | requests-mock |
| `wr2_canva_pdf_apply.py` | 120 | Top-level orchestrator composing the above | asyncio integration test |
| `wr2_bootstrap_canva_oauth.py` | 150 | One-shot interactive bootstrap (run on Pro once) | manual smoke |
| `wr2_canva_token_watchdog.py` | 60 | Daily check `last_refreshed_iso`, alert >75d/>85d | tmp file fixture |
| **Total** | **~1030** | | |

All modules go under `apps/backend-rag/backend/services/canva_renderer_v2/`
to keep test infra co-located with the legacy `canva_renderer/` package.
The launcher `scripts/wr2_canva_pdf_apply.py` is a thin entrypoint
(~30 LOC) that imports `from backend.services.canva_renderer_v2 import run`.

## 3. Token storage and OAuth lifecycle

### 3.1 Bootstrap (one-shot, interactive)

`scripts/wr2_bootstrap_canva_oauth.py`:

1. Construct `mcp.client.auth.OAuthClientProvider` with own `OAuthClientMetadata`:
   ```python
   client_name = "WR2 Pipeline Orchestrator"
   redirect_uris = ["http://localhost:0/oauth/callback"]  # ephemeral port
   grant_types = ["authorization_code", "refresh_token"]
   response_types = ["code"]
   token_endpoint_auth_method = "none"  # Canva confirmed public-client
   scope = "user:read offline_access account:read teams:read"
   ```
2. Bind local HTTP server on `127.0.0.1:0` (kernel-assigned ephemeral
   port). Record the assigned port and patch `redirect_uri` in the
   metadata before initiating the flow.
3. POST `https://mcp.canva.com/register` → receive `client_id`.
4. Open browser to authorization endpoint with PKCE challenge.
5. Operator authorizes. Local server receives callback with auth code.
6. Exchange code for tokens at `mcp.canva.com/token`.
7. Compute HMAC-SHA256 over canonical JSON. Write to
   `~/.config/wr2/canva_tokens.json` (0600):
   ```json
   {
     "client_id": "...",
     "client_secret": "",  // empty, none auth method
     "access_token": "...",
     "refresh_token": "...",
     "scope": "user:read offline_access account:read teams:read",
     "token_type": "bearer",
     "expires_at_epoch": 1778614000.0,
     "issued_at": "2026-05-13T18:30:00Z",
     "last_refreshed_iso": "2026-05-13T18:30:00Z",
     "_hmac": "0123abcd..."  // hex-encoded SHA-256
   }
   ```
8. Smoke test: `mcp_session.call_tool("list-brand-kits")` → assert
   returns Bali Zero team. Failure → exit 2 with diagnostic.

The `WR2_CANVA_HMAC_KEY` env var (32 random bytes hex-encoded) lives
in `~/.nuzantara-secrets.env`. Bootstrap script asserts presence
before running.

### 3.2 Runtime: `OrchestratorTokenStorage(TokenStorage)`

Key invariants:
- Reads/writes are protected by `fcntl.LOCK_EX` on a sidecar
  `canva_tokens.lock` file (advisory exclusive).
- Every read verifies HMAC. Mismatch → `RuntimeError("Token HMAC
  mismatch")` → orchestrator exits 7 with backup copy
  `canva_tokens.broken-<YYYYMMDD-HHMMSS>.json`.
- Proactive refresh: `get_tokens()` returns `None` if
  `expires_at_epoch - now() < 300 + uniform(0, 15)` seconds, forcing
  `OAuthClientProvider` to refresh.
- On refresh, Canva may omit `refresh_token` in the response (standard
  OAuth pattern). `set_tokens` merges and preserves the existing
  `refresh_token` if absent.
- Atomic write: temp file in same dir + `replace()`.
- NO mtime-compare check (anti-pattern per DeepSeek panel).

### 3.3 Refresh-token expiry watchdog

`scripts/wr2_canva_token_watchdog.py` invoked daily via
`com.balizero.wr2.canva-token-watchdog.daily.plist` (09:00 WITA):

1. Read `canva_tokens.json`. Verify HMAC.
2. Compute days since `last_refreshed_iso`.
3. If >75 days → Telegram warn "Canva refresh token expires in 15d.
   Plan re-bootstrap."
4. If >85 days → Telegram critical "Canva refresh expires in 5d.
   Re-bootstrap NOW."
5. If file missing or HMAC mismatch → Telegram alert.

Canva's documented refresh-token decay window is 90 days of non-use;
the watchdog gives a 15-day buffer. Re-bootstrap is a 30-second manual
operation on Pro.

### 3.4 Failure exit codes

| Exit | Meaning | launchd `SuccessfulExit`? | Telegram? |
|---|---|---|---|
| 0 | Normal | yes | no (per-draft notify) |
| 1 | Transient (network, PG transient) | no (auto-retry next tick) | no |
| 2 | DSN missing or config invalid | no | yes |
| 3 | Kill switch off (expected quiet exit) | yes | no |
| 4 | Token file missing → run bootstrap | yes (no restart loop) | yes |
| 5 | Refresh revoked → re-auth needed | yes | yes (high priority) |
| 6 | flock contention exhausted | no (retry) | no |
| 7 | Token JSON corrupt | yes | yes |

`com.balizero.wr2.canva-renderer.plist`:
```xml
<key>SuccessfulExit</key>
<array>
  <integer>0</integer>
  <integer>3</integer>
  <integer>4</integer>
  <integer>5</integer>
  <integer>7</integer>
</array>
<key>ThrottleInterval</key>
<integer>300</integer>
```

## 4. Per-draft flow and error handling

### 4.1 Draft lifecycle

```
drafts_imaged_checked  ─[orchestrator pickup]→  (transient)
                                                    │
                                                    ├─ PDF gen OK ────────────┐
                                                    │                         │
                                                    └─ PDF gen FAIL ──→ status='pdf_render_failed' (new terminal)
                                                                              │
                                                                     ┌────────┴────────┐
                                                                     │ MCP import OK   │
                                                                     ├──→ status='rendered'
                                                                     │   canva_*=populated
                                                                     │
                                                                     │ MCP import FAIL
                                                                     └──→ status='canva_import_failed' (new terminal)
```

Two new terminal status values are added to the schema vocabulary:
- `pdf_render_failed` — ReportLab subprocess exit≠0, file size==0,
  or Tigris upload exhausted retries
- `canva_import_failed` — MCP `import-design-from-url` raised after
  retries

Both are terminal and NOT picked up by the next cron tick. Antonello
manually re-promotes them to `drafts_imaged_checked` after fixing the
underlying issue.

### 4.2 Per-draft pseudo-code

See section 2.2 of this spec for module boundaries. The orchestrator
top-level (`wr2_canva_pdf_apply.py`) iterates over drafts:

```python
async def _apply_one_draft(conn, mcp_session, row, *, dsn):
    draft_id = row["id"]
    t0 = time.time()

    # A — schema adapt
    slides = json.loads(row["slides_json"]) if isinstance(row["slides_json"], str) else row["slides_json"]
    if _is_legacy_schema(slides):
        slides = adapt_legacy_schema(slides, topic=row["topic"])

    # B — PDF render via subprocess
    pdf_path = await _render_pdf(slides, draft_id)  # raises PdfRenderError
    if pdf_path is None:
        await _mark_failed(conn, draft_id, "pdf_render_failed", "subprocess exit≠0")
        return False

    # C — Tigris upload
    pdf_url = await _upload_to_tigris(pdf_path, draft_id)  # 3 retries
    if pdf_url is None:
        await _mark_failed(conn, draft_id, "pdf_render_failed", "tigris exhausted")
        return False

    # D — MCP import-design-from-url
    try:
        result = await mcp_session.call_tool(
            "import-design-from-url",
            arguments={"url": pdf_url, "title": row["topic"][:80]},
        )
        design_id = _parse_design_id(result)
        edit_url = f"https://www.canva.com/design/{design_id}/edit"
    except Exception as exc:
        await _mark_failed(conn, draft_id, "canva_import_failed", f"{type(exc).__name__}: {exc}")
        _send_telegram(f"🚨 WR2 MCP import FAILED draft={draft_id} err={exc}")
        return False

    # E — move-to-folder (best effort, non-fatal)
    try:
        await mcp_session.call_tool(
            "move-item-to-folder",
            arguments={"item_id": design_id, "folder_id": WR2_DRAFTS_FOLDER_ID},
        )
    except Exception as exc:
        logger.warning("Draft %s move-to-folder failed: %s", draft_id, exc)

    # F — persist with reconnect-on-dead-conn (legacy pattern)
    await _persist_canva_result(conn, draft_id, design_id, edit_url, dsn=dsn)
    _send_telegram(f"🎨 WR2 rendered: {row['topic'][:80]}\n{edit_url}\nduration: {time.time()-t0:.1f}s")
    _log_telemetry(draft_id, "success", time.time() - t0)
    return True
```

### 4.3 Failure classification

| Failure point | New status | Retry-able? | Alert? |
|---|---|---|---|
| A schema adapt KeyError | no DB change | no, fixable in code | logger.error, no Telegram |
| B PDF render exit≠0 | `pdf_render_failed` | manual re-promote | Telegram |
| B subprocess timeout 120s | `pdf_render_failed` | manual | Telegram |
| C Tigris boto3 ClientError | `pdf_render_failed` | auto 3 retry then terminal | Telegram |
| D MCP call_tool raises | `canva_import_failed` | manual | Telegram (escalation) |
| D OAuth token expired AND refresh succeeded | (transparent retry) | yes | no |
| D OAuth refresh revoked | (orchestrator exits 5) | re-bootstrap | Telegram high prio |
| E move-to-folder fails | status stays `rendered` | non-fatal | warn log |
| F PG UPDATE crashes | orphan (Canva exists, DB unaware) | reconnect-on-dead-conn (legacy) | Telegram persist_failed |

### 4.4 Inherited patterns from legacy

Three patterns from `scripts/wr2_canva_apply.py` are reused verbatim:

1. **`_persist_canva_result` reconnect-on-dead-conn** — the `conn`
   opened in `run()` may close during long MCP HTTP call. Although
   the Fly tunnel scenario is less acute here (MCP HTTP not Fly
   tunnel), the pattern stays safe.
2. **Telemetry JSONL append-only** at
   `~/logs/wr2_canva_pdf_apply_telemetry.jsonl` — outcome / duration
   / attempt fields kept identical to legacy for log analyzer
   continuity.
3. **`MAX_DRAFTS_PER_RUN = 3`** — limit stampede on launchd 5-min tick.

## 5. launchd plist and operational lifecycle

### 5.1 Production plist

File: `infra/launchagents/com.balizero.wr2.canva-renderer.plist`
(replaces existing plist of same label):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.balizero.wr2.canva-renderer</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python</string>
    <string>/Users/nuzantara/Desktop/nuzantara/scripts/wr2_canva_pdf_apply.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/nuzantara/Desktop/nuzantara</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>DATABASE_URL</key>
    <string>postgresql://...127.0.0.1:15432/nuzantara_rag</string>
    <key>WR2_CANVA_TOKEN_FILE</key>
    <string>/Users/nuzantara/.config/wr2/canva_tokens.json</string>
    <key>WR2_CANVA_HMAC_KEY</key>
    <string>${SECRET_HEX}</string>
    <key>AWS_ACCESS_KEY_ID</key>
    <string>${TIGRIS_ACCESS_KEY}</string>
    <key>AWS_SECRET_ACCESS_KEY</key>
    <string>${TIGRIS_SECRET_KEY}</string>
    <key>AWS_ENDPOINT_URL_S3</key>
    <string>https://fly.storage.tigris.dev</string>
    <key>TIGRIS_BUCKET</key>
    <string>nuzantara-warroom-images</string>
    <key>TELEGRAM_BOT_TOKEN</key>
    <string>${TELEGRAM_BOT_TOKEN}</string>
    <key>TELEGRAM_OWNER_CHAT_ID</key>
    <string>1125336968</string>
  </dict>
  <key>StartInterval</key>
  <integer>300</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>SuccessfulExit</key>
  <array>
    <integer>0</integer>
    <integer>3</integer>
    <integer>4</integer>
    <integer>5</integer>
    <integer>7</integer>
  </array>
  <key>ThrottleInterval</key>
  <integer>300</integer>
  <key>StandardOutPath</key>
  <string>/Users/nuzantara/logs/wr2_canva_pdf_apply.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/nuzantara/logs/wr2_canva_pdf_apply.error.log</string>
</dict>
</plist>
```

Token watchdog plist
(`infra/launchagents/com.balizero.wr2.canva-token-watchdog.daily.plist`)
runs at 09:00 WITA daily, similar structure but `StartCalendarInterval`
instead of `StartInterval`.

### 5.2 PG kill switch

Stays at `system_settings.wr2_canva_renderer_enabled` (boolean as
text 'true'/'false'). Orchestrator checks first thing; if not 'true',
exits 3 (quiet). To flip: `psql -c "UPDATE system_settings SET
value='true' WHERE key='wr2_canva_renderer_enabled'"`. Same kill
switch as legacy — reused.

### 5.3 Bootstrap sequence (one-time)

```bash
# 1. Ensure env vars set in ~/.nuzantara-secrets.env
#    WR2_CANVA_HMAC_KEY=<openssl rand -hex 32>
#    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, TIGRIS_BUCKET already present

# 2. Run bootstrap (Pro, browser available)
source ~/.nuzantara-secrets.env
mkdir -p ~/.config/wr2 && chmod 700 ~/.config/wr2
cd ~/Desktop/nuzantara
apps/backend-rag/.venv/bin/python scripts/wr2_bootstrap_canva_oauth.py

# Browser opens. Authorize Bali Zero team. Wait for "✅ Bootstrap complete".

# 3. Verify
ls -la ~/.config/wr2/canva_tokens.json  # mode 0600
python -c "from backend.services.canva_renderer_v2._token_storage import OrchestratorTokenStorage; \
           import asyncio; \
           t = OrchestratorTokenStorage(); \
           print(asyncio.run(t.get_tokens()))"
```

### 5.4 Flip-on sequence

```bash
# After bootstrap done + spec approved:
# 1. Update plist file
cp infra/launchagents/com.balizero.wr2.canva-renderer.plist ~/Library/LaunchAgents/

# 2. Flip PG kill switch
psql -h 127.0.0.1 -p 15432 -U postgres -d nuzantara_rag \
  -c "UPDATE system_settings SET value='true' WHERE key='wr2_canva_renderer_enabled'"

# 3. Bootstrap plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.canva-renderer.plist

# 4. Monitor first 2-3 ticks (10-15min wall-clock)
tail -F ~/logs/wr2_canva_pdf_apply.log
psql -c "SELECT id, status, canva_edit_url FROM war_room_drafts WHERE status IN ('drafts_imaged_checked','rendered') ORDER BY created_at DESC LIMIT 5"
```

### 5.5 Rollback procedure

If new orchestrator misbehaves:

```bash
# 1. Stop new
launchctl bootout gui/$(id -u)/com.balizero.wr2.canva-renderer
# 2. PG kill switch OFF
psql -c "UPDATE system_settings SET value='false' WHERE key='wr2_canva_renderer_enabled'"
# 3. (Optional) Restart legacy: switch ProgramArguments back to wr2_canva_apply.py
#    (legacy script still in repo for ~2 weeks)
```

## 6. Testing strategy

| Test layer | Coverage | Tool |
|---|---|---|
| Unit (per module) | 80%+ | pytest + asyncpg mock + moto S3 + httpx_mock |
| Schema adapter | 3 fixture drafts (Parq, KEP-71, deep schema v2) | pytest |
| Token storage flock + HMAC | concurrent process spawn test | pytest + multiprocessing |
| Bootstrap script | manual smoke (browser-bound) | wiki runbook |
| End-to-end | 1 real draft from PG | manual on staging UUID |

CI: existing PR-checks (E2E, MCP Server Tests) cover unrelated code
paths. New unit tests added under
`apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/`.

## 7. Deliverables and commit plan

### 7.1 Files to create (production code)

| Path | LOC est. | Module |
|---|---|---|
| `apps/backend-rag/backend/services/canva_renderer_v2/__init__.py` | 5 | package init |
| `apps/backend-rag/backend/services/canva_renderer_v2/_pg.py` | 80 | DB layer |
| `apps/backend-rag/backend/services/canva_renderer_v2/_schema_adapter.py` | 130 | legacy schema adapt |
| `apps/backend-rag/backend/services/canva_renderer_v2/_pdf_pipeline.py` | 60 | renderer subprocess |
| `apps/backend-rag/backend/services/canva_renderer_v2/_tigris.py` | 90 | S3 upload |
| `apps/backend-rag/backend/services/canva_renderer_v2/_canva_mcp.py` | 120 | MCP client |
| `apps/backend-rag/backend/services/canva_renderer_v2/_token_storage.py` | 180 | OAuth |
| `apps/backend-rag/backend/services/canva_renderer_v2/_telegram.py` | 40 | notify |
| `apps/backend-rag/backend/services/canva_renderer_v2/orchestrator.py` | 120 | top-level `run()` |
| `scripts/wr2_canva_pdf_apply.py` | 30 | thin entrypoint |
| `scripts/wr2_bootstrap_canva_oauth.py` | 150 | bootstrap |
| `scripts/wr2_canva_token_watchdog.py` | 60 | daily watchdog |
| `infra/launchagents/com.balizero.wr2.canva-renderer.plist` | xml | updated plist |
| `infra/launchagents/com.balizero.wr2.canva-token-watchdog.daily.plist` | xml | new watchdog plist |

### 7.2 Files to create (tests)

| Path | LOC est. |
|---|---|
| `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_pg.py` | 100 |
| `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_schema_adapter.py` | 120 |
| `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_pdf_pipeline.py` | 60 |
| `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_tigris.py` | 90 |
| `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_canva_mcp.py` | 100 |
| `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_token_storage.py` | 150 |
| `apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/test_orchestrator_integration.py` | 100 |
| `apps/backend-rag/backend/tests/fixtures/canva_renderer_v2/draft_legacy_parq.json` | data |
| `apps/backend-rag/backend/tests/fixtures/canva_renderer_v2/draft_v2_kep71.json` | data |

### 7.3 Commit sequence (WIP-every-step anti-hijack)

| Commit | Subject | Files |
|---|---|---|
| 1 | `docs(wr2): spec for orchestrator PDF render pipeline` | this design doc |
| 2 | `feat(canva-renderer-v2): module scaffolding + _pg.py + _telegram.py` | 2 modules + tests |
| 3 | `feat(canva-renderer-v2): _schema_adapter.py with 3 fixtures` | adapter + fixtures + tests |
| 4 | `feat(canva-renderer-v2): _pdf_pipeline.py subprocess wrapper` | pipeline + tests |
| 5 | `feat(canva-renderer-v2): _tigris.py boto3 with 3-retry` | tigris + tests |
| 6 | `feat(canva-renderer-v2): _token_storage.py HMAC+flock+proactive-refresh` | storage + tests |
| 7 | `feat(canva-renderer-v2): _canva_mcp.py ClientSession wrapper` | mcp + tests |
| 8 | `feat(canva-renderer-v2): orchestrator.py top-level + scripts entrypoint` | orchestrator + script + integration test |
| 9 | `feat(wr2): bootstrap_canva_oauth.py one-shot interactive script` | bootstrap |
| 10 | `feat(wr2): canva_token_watchdog.py daily expiry check` | watchdog |
| 11 | `feat(infra): launchd plist for v2 renderer + token watchdog` | 2 plist files |
| 12 | `docs(cicatrix): update DAHJEkWpkzY scar — v3 orchestrator live` | scar update |

Push after every commit. WIP-commit-every-10min anti-hijack.

### 7.4 Stop condition

The wave terminates when:
1. Branch `feat/wr2-orchestrator-pdf-render-2026-MM-DD` opened as PR
2. Bootstrap script run manually on Pro, `~/.config/wr2/canva_tokens.json` exists with HMAC valid
3. 1 real draft from PG processed end-to-end → `canva_edit_url`
   populated → design opens in Chrome Bali Zero team → layer-editable
   verified visually
4. 2-3 cron ticks monitored (15min wall) zero errors
5. Cicatrix-scar updated with "loop chiuso end-to-end live"
6. Telegram alert to Antonello: "WR2 pipeline live, first draft
   processed $DRAFT_ID"

Do NOT batch-regenerate 35 legacy drafts in same wave — that's a
separate ticket (rate limits on MCP Canva + Codex imagegen cost if
hero needed).

## 8. Risks and mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Canva removes RFC 7591 dynamic registration | high | Token watchdog detects 401 on `/register` rebootstrap path, falls back to Canva Developer Portal manual |
| `mcp` Python SDK 1.12.4 breaking change in 1.13+ | medium | Pin in `requirements.txt`. Renovate PR review opt-in for MCP-SDK bump |
| Tigris bucket policy change (no public PDF read) | high | Pre-validate bucket policy in bootstrap. Telegram alert if signed-url fallback path triggers |
| Refresh token decay >90d during long idle | medium | Daily watchdog at 75d/85d warning |
| Sibling automation branch hijack during code write | high | WIP-commit-every-10min + scope-limited git add (no `-A` bare) |
| `mcp.canva.com` rate limit (288 runs/day) | low | MAX_DRAFTS_PER_RUN=3 → max 864 calls/day. Canva published limit unknown, monitor empirically |
| Yellow-badge regression in renderer | medium | renderer is on the branch and committed; no regression expected. Smoke PDFs re-runnable any time |

## 9. Out of scope

- Re-rendering 35 legacy drafts → separate ticket, requires manual decision per draft (hero re-gen Codex imagegen cost ~$0.04 each)
- Migration of legacy slides_json schema in PG → status quo: adapter inline
- WR2 image-generator backend (Sprint 1.6 W3, see CLAUDE.md §11) → unrelated, already shipped
- Article 15 banned type-as-design enforcement at slide level → renderer handles this already

## 10. Acceptance gates

| Gate | Owner | Pass criteria |
|---|---|---|
| 3-LLM spec review | Claude + Gemini + DeepSeek (+ Codex when alive) | This document already passed sections 1-3. Sections 4-7 panel pending if Antonello requests. |
| User review of written spec | Antonello | This file approved as-is, or change requests merged via Edit + re-review |
| Unit test coverage 80%+ | CI | pytest-cov ≥0.8 per module |
| Bootstrap smoke | Antonello on Pro | `list-brand-kits` returns Bali Zero team |
| End-to-end real draft | Antonello + me on Pro | 1 draft `rendered`, Canva edit URL opens, layer-editable |
| Cicatrix-scar update | me | "loop chiuso end-to-end live" appended to active scar |

---

**Status**: draft, awaiting user review before transitioning to
implementation plan (writing-plans skill).
