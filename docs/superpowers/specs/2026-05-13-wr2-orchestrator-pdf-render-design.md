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

### 4.0 Cross-LLM panel revisions (2026-05-13, post sez 4-7 review)

3-LLM panel (Gemini + GPT-5.5 codex + DeepSeek V4 Pro) caught **6 flaws**
in earlier sez 4-7 drafts. Applied inline below; full table in §1.4.

| Convergence | Flaw | Mitigation in this section |
|---|---|---|
| 2/3 (high) | **Per-draft lease / idempotency** — overlapping launchd run can double-process same draft mid-tigris-upload, before PG UPDATE | §4.1.1 lease table |
| 3/3 (medium) | **Tigris orphan PDF** on `canva_import_failed` path | §4.3 cleanup step |
| 2/3 (high) | **Overlapping launchd runs** — default launchd does NOT serialize a job with itself on `StartInterval` | §5.1 LaunchOnlyOnce + flock advisory in orchestrator |
| 2/3 (high) | **429/5xx → mark `canva_import_failed` aggressive** — should backoff + leave in `drafts_imaged_checked` for retry | §4.3 transient-vs-permanent classifier |
| 2/3 (high) | **Plist envvar rotation gap** — secrets baked at bootstrap, no hot-reload | §5.1 zsh wrapper `source ~/.nuzantara-secrets.env && exec ...` (consistent with legacy plist) |
| 2/3 (medium) | **E2E test on real PG draft pollutes production** | §6.4 synthetic `e2e_test_client` + namespaced Tigris prefix + dedicated Canva folder |
| 2/3 (split) | **Commit ordering bisectability** — keep imports green at every commit | §7.3 restructure |

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

### 4.1.1 Per-draft lease (new, post-panel)

Race condition discovered by panel: even with `MAX_DRAFTS_PER_RUN=3`,
two overlapping orchestrator runs (slow MCP call extending past 5min
StartInterval) can both SELECT the same draft, double-upload PDF to
Tigris, and double-import to Canva.

**Fix — compare-and-swap status transition** at fetch time:

```sql
UPDATE war_room_drafts
   SET status = 'rendering',
       lease_owner = $1,           -- new column: text (orchestrator PID + hostname)
       lease_acquired_at = NOW()    -- new column: timestamptz
 WHERE id = $2
   AND status = 'drafts_imaged_checked'
   AND canva_edit_url IS NULL
RETURNING id, topic, register, slides_json
```

Only the row that wins the CAS is processed. After success → status
`'rendered'` clears the lease. After terminal failure → status
`'pdf_render_failed'` / `'canva_import_failed'` clears the lease.

Stale lease watchdog: `lease_acquired_at < NOW() - INTERVAL '15 minutes'`
AND `status='rendering'` → reset to `'drafts_imaged_checked'`,
nullify lease fields, alert Telegram (orphan recovery).

Schema migration: new SQL v2 migration `NNN_wr2_draft_lease.sql` adds
`lease_owner text` + `lease_acquired_at timestamptz` to `war_room_drafts`.

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

### 4.3 Failure classification (revised post-panel)

Two new classes added for panel feedback: **transient** (retry naturally
next cron tick, stay in `drafts_imaged_checked` after lease release)
vs **permanent** (mark terminal). MCP 429/5xx and OAuth transient errors
are transient; structural failures are permanent.

| Failure point | Classification | DB status | Lease release | Tigris cleanup | Telegram |
|---|---|---|---|---|---|
| A schema adapt KeyError | permanent | `pdf_render_failed` | yes | n/a (pre-upload) | yes |
| B PDF render exit≠0 | permanent | `pdf_render_failed` | yes | n/a | yes |
| B subprocess timeout 120s | permanent | `pdf_render_failed` | yes | n/a | yes |
| C Tigris boto3 ClientError (3 retry exh) | permanent | `pdf_render_failed` | yes | best-effort delete partial | yes |
| D MCP `call_tool` raises 429 / 5xx / Retry-After | **transient** | revert to `drafts_imaged_checked` | yes | **delete uploaded PDF** | warn log only |
| D MCP `call_tool` raises 4xx structural | permanent | `canva_import_failed` | yes | **delete uploaded PDF** | yes (escalation) |
| D OAuth token expired AND refresh succeeded | transparent retry | (no change mid-flow) | held | n/a | no |
| D OAuth refresh revoked | (orchestrator exits 5) | revert to `drafts_imaged_checked` | yes | **delete uploaded PDF** | yes high prio |
| E move-to-folder fails | non-fatal | stays `rendered` | yes | n/a | warn log |
| F PG UPDATE crashes | orphan | (Canva exists, DB unaware) | held → watchdog resets | n/a | yes persist_failed |

**Tigris cleanup (new step §4.3.1)**: on transient or permanent path D
failure, orchestrator MUST call `boto3.delete_object` on the uploaded
PDF before mutating DB. Best-effort: failure to delete is logged but
does not change status flow (S3 lifecycle policy is the safety net,
see §5.6).

**Backoff classifier**: MCP responses with `Retry-After` header or
HTTP 429/502/503/504 → classified transient. Other HTTP 4xx →
permanent. `httpx.NetworkError` / `httpx.TimeoutException` → transient
with cap (after 3 consecutive transient failures on same draft across
ticks, escalate to permanent).

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

### 5.1 Production plist (revised post-panel)

Two changes from v1 driven by panel:

1. **No inline `EnvironmentVariables`** — use bash wrapper that sources
   `~/.nuzantara-secrets.env` at execution time. Fresh secrets every
   tick, no `bootout`+`bootstrap` for rotation. Consistent with legacy
   plist convention (verified empirically via `launchctl print`).
2. **Single-instance flock** in `ProgramArguments` wrapper — prevents
   overlapping runs from launchd (StartInterval=300 doesn't serialize
   on slow tick).

File: `infra/launchagents/com.balizero.wr2.canva-renderer.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.balizero.wr2.canva-renderer</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>source ~/.nuzantara-secrets.env 2>/dev/null; exec /opt/homebrew/bin/flock -n /tmp/wr2_canva_pdf_apply.lock /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python -u /Users/nuzantara/Desktop/nuzantara/scripts/wr2_canva_pdf_apply.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/nuzantara/Desktop/nuzantara</string>
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

Notes:
- `flock -n` (non-blocking): if a previous instance still holds the
  lock, this tick exits 1 (non-success, but no error log). Next tick
  retries naturally. Lock file `/tmp/wr2_canva_pdf_apply.lock`.
- `flock` binary at `/opt/homebrew/bin/flock` (brew, v0.4.0,
  verified 2026-05-13). Pre-existing in stack (cf. git-pull.5min plist
  + mini-migration `lessons_python_ssh_heredoc_escape.md` fix).
- `-l` on `/bin/zsh` ensures `.zshrc` is sourced (PATH+brew available),
  matching the empirically-verified legacy plist convention.
- `exec` replaces the shell process → launchd sees the Python PID
  directly for accurate `SuccessfulExit` evaluation.

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

### 5.6 Tigris S3 lifecycle policies (new post-panel)

Two prefixes with distinct retention:

```
s3://nuzantara-warroom-images/wr2-pdf/                  retention 30 days (production)
s3://nuzantara-warroom-images/wr2-pdf-tests/             retention 1 day  (E2E namespace)
```

`infra/tigris/wr2-pdf-lifecycle.json` defines the policy. Applied via:

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket nuzantara-warroom-images \
  --lifecycle-configuration file://infra/tigris/wr2-pdf-lifecycle.json \
  --endpoint-url https://fly.storage.tigris.dev
```

Rationale: 30-day retention covers re-import-from-url replay if Canva
design is accidentally deleted client-side. 1-day on `tests/` prefix
auto-cleans E2E artifacts. Both serve as safety net for orphan-PDF
class even when orchestrator cleanup step fails.

### 5.7 Stale-lease watchdog (new post-panel)

`scripts/wr2_canva_lease_watchdog.py` runs every 10 minutes via plist
`com.balizero.wr2.canva-lease-watchdog.10min.plist`:

1. SELECT id, lease_owner, lease_acquired_at FROM war_room_drafts
   WHERE status='rendering' AND lease_acquired_at < NOW() - INTERVAL '15 minutes'.
2. UPDATE status='drafts_imaged_checked', clear lease fields.
3. Telegram alert per orphan recovered (sample: 5 max per run to avoid
   flood).

This + Tigris S3 lifecycle = belt+suspenders against orphan state.

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

### 6.4 E2E isolation strategy (new post-panel)

Panel flagged that "1 real draft from PG" as test fixture pollutes
production data. Revised approach:

| Layer | Production | E2E |
|---|---|---|
| PG client_id | real Bali Zero clients | permanent synthetic `e2e_test_client` row in `clients` table |
| PG draft | created by storyboarder | created by `scripts/wr2_e2e_create_fixture_draft.py` with `client_id=e2e_test_client`, `topic="[E2E TEST]..."`, fixed UUID `00000000-0000-0000-e2e0-000000000001` |
| Tigris prefix | `wr2-pdf/` | `wr2-pdf-tests/` (1-day lifecycle) |
| Canva folder | "WR2 Drafts 2026" | "E2E Tests (Auto-Delete)" (separate `WR2_DRAFTS_FOLDER_ID_E2E` env) |
| Status terminal | normal | teardown script DELETEs Canva design + PG row immediately after assert |

Orchestrator detects E2E mode via `WR2_E2E_MODE=true` env var (set by
test runner only). In E2E mode: uses test Tigris prefix, test Canva
folder, and outputs more verbose diagnostics. Production never sets
this var.

E2E test scenarios:

1. **Happy path** — synthetic draft → fully rendered + Canva URL valid
2. **Lease race** — spawn 2 orchestrator instances simultaneously,
   assert only 1 processes
3. **OAuth refresh mid-flow** — pre-expire token, assert transparent
   refresh + success
4. **Tigris 503 transient** — moto intercepts, assert backoff
5. **Stale lease recovery** — manually insert `status='rendering'`
   row with `lease_acquired_at` 20min ago, assert watchdog resets

E2E pytest fixtures live in
`apps/backend-rag/backend/tests/e2e/canva_renderer_v2/`. Run manually
on Pro after bootstrap; not in CI (browser-bound OAuth flow).

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

### 7.3 Commit sequence (revised post-panel — bisect-safe)

Panel split on commit ordering (Gemini OK, GPT-5.5 + DeepSeek
"restructure for bisectability"). Resolution: every commit must keep
`pytest --collect-only` green (no missing-import errors) even if
feature is incomplete. Pure-library modules first, then wiring last.

| # | Subject | Files | Bisect-safe? |
|---|---|---|---|
| 1 | `docs(wr2): spec for orchestrator PDF render pipeline` | this design doc | yes |
| 2 | `feat(db): SQL v2 migration NNN_wr2_draft_lease.sql` | lease columns | yes |
| 3 | `feat(canva-renderer-v2): pkg init + _telegram.py + _pg.py (read-only)` | 3 files + tests | yes (no external IO except mocked PG) |
| 4 | `feat(canva-renderer-v2): _schema_adapter.py + fixtures` | adapter + 3 fixtures + tests | yes (pure function) |
| 5 | `feat(canva-renderer-v2): _pdf_pipeline.py subprocess wrapper` | pipeline + tests | yes (mocks subprocess) |
| 6 | `feat(canva-renderer-v2): _tigris.py boto3 + S3 lifecycle JSON` | tigris + tests + infra/tigris/ | yes (moto S3) |
| 7 | `feat(canva-renderer-v2): _token_storage.py HMAC+flock+proactive-refresh` | storage + tests | yes (tmp fixture) |
| 8 | `feat(canva-renderer-v2): _canva_mcp.py ClientSession wrapper` | mcp + tests | yes (httpx_mock) |
| 9 | `feat(canva-renderer-v2): _pg.py write path + lease CAS` | pg lease + tests | yes |
| 10 | `feat(canva-renderer-v2): orchestrator.py top-level (wired)` | orchestrator + integration test | yes (all deps committed) |
| 11 | `feat(wr2): scripts/wr2_canva_pdf_apply.py thin entrypoint` | script | yes |
| 12 | `feat(wr2): bootstrap_canva_oauth.py + canva_token_watchdog.py + lease_watchdog.py` | 3 scripts | yes |
| 13 | `feat(infra): launchd plist for v2 renderer + token watchdog + lease watchdog` | 3 plist files | yes |
| 14 | `feat(canva-renderer-v2): E2E fixtures + scripts/wr2_e2e_create_fixture_draft.py` | e2e infra | yes |
| 15 | `docs(cicatrix): update DAHJEkWpkzY scar — v3 orchestrator live` | scar update | yes |

Push after every commit. WIP-commit-every-10min anti-hijack.
`git bisect` valid across all 15 commits because each isolated module
has its own passing test suite and no commit leaves the imports
broken (orchestrator.py last, after all deps shipped).

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
