# WR2 Sprint B → F — Detailed Implementation Plan

> **Status**: Pre-implementation review. Owner-approved scope from `2026-05-07-wr2-longterm-design.md`.
> **Author**: Claude Opus 4.7 in collaboration with Antonello Siano.
> **Audience**: future Claude sessions executing these sprints, future contributors.

---

## How to read this document

For each step:

1. **Scope** — what changes, what stays, what file/path
2. **Design** — concrete architecture or code shape
3. **Risk review** — what can go wrong + mitigation
4. **Test plan** — pre-merge verification, post-merge verification
5. **Rollout** — merge order, deploy steps, rollback path

Sprints execute sequentially: **B → C → D → E → F**. Within each sprint, steps execute in numeric order unless explicitly parallelisable.

---

## SPRINT B — Stabilizzazione canva-apply (3-4 giorni)

**Goal**: portare canva-apply success rate da ~50% empirico a ≥90% deterministico.

**Empirical baseline (2026-05-07)**:

- 5 run: 1 success (DAHI7R8qiMo) + 4 failure (mix of "MCP not available", timeout, italiano output, stale-cache)
- Frequency of failure pattern: non-deterministic, both subprocess-fresh and subprocess-warm produce both outcomes

---

## ⚠️ POST-REVIEW REVISION 2026-05-08 — HYPOTHESIS INVALIDATED

After 4 independent reviews of B1-B4, the foundational hypothesis "MCP Canva
has a server-side cache that probes can warm" is **architecturally false**:

- Each `claude -p` invocation spawns `mcp-remote` as a fresh child process
- OAuth tokens in `~/.mcp-auth/` are persistent auth, NOT warm cache
- No shared state exists between two consecutive `claude -p` subprocess on the
  Anthropic / Canva connector side that survives process termination
- The 50% empirical fail rate is therefore **not explained** by warm/cold
  cache — true cause is unknown until we instrument

**Plus B4 has 3 BLOCKER issues**:

- `scripts/wr2_fact_extractor.py` does NOT exist on disk (only the plist)
- `scripts/wr2_fact_checker.py` does NOT exist on disk
- DB has no `fact_check_json` / `fact_check_status` columns
- B4 is a net-new build (12-16h), not a 4h restore

### Revised Sprint B order

**B0 (NEW, replaces B1+B2 first attempt)** — Diagnostic instrumentation:
detect-sentinel + 60s sleep + retry-once pattern in `_apply_one_draft`.
Adds a dense per-attempt log (stdout head/tail, exit code, duration, sentinel-detected flag).
Zero overhead on happy path. Run for 7 days to collect ≥7 real datapoints.

**Decision gate post-B0** (after 7 days): inspect data, decide if B1 (probe)
or B2 (canary) is justified, or pivot to a different workaround.

**B3** — Salvabile con fix forniti dalla review: dedicated heartbeat
connection (NOT on LISTEN connection), Squawk ignore comment, 7-day
rolling window for success rate (1 draft/day too sparse for 24h).

**B4** — Spostato fuori da Sprint B (12-16h effort, requires writing 2
scripts + migration + atomic deploy of supervisor + canva-apply + reconciler).
Goes into Sprint C (or new Sprint B-bis) after instrumentation data
clarifies whether fact-checking is even the bottleneck.

**B5** — OK as-is, bundle with B0.

### B0 — Diagnostic instrumentation (NEW, replaces B1+B2 first attempt)

**Scope**: instrument `_apply_one_draft` in `scripts/wr2_canva_apply.py` to
collect per-attempt diagnostic data (stdout head/tail, exit code, duration,
sentinel-detected flag) AND implement detect-sentinel + 60s sleep + retry-once
pattern. Also bump `CODEX_TIMEOUT_SEC` 600→900s (was B5).

**File modificato**: `scripts/wr2_canva_apply.py`

**Design**:

```python
MCP_NOT_AVAILABLE_SENTINELS = (
    "MCP Canva not available",
    "Canva cloud connector requires claude.ai",
    "claude.ai Canva server is not in mcp-needs-auth-cache",
)

def _is_mcp_cold_failure(exc: CanvaInvokeError) -> bool:
    msg = str(exc)
    return any(s in msg for s in MCP_NOT_AVAILABLE_SENTINELS)

def _log_run_telemetry(draft_id, attempt, outcome, duration_s, exc_text):
    """One JSONL line per run attempt to ~/logs/wr2_canva_apply_telemetry.jsonl."""
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "draft_id": str(draft_id),
        "attempt": attempt,  # 1 = first try, 2 = retry-after-cold
        "outcome": outcome,  # 'success' | 'cold_sentinel' | 'timeout' | 'other'
        "duration_s": round(duration_s, 1),
        "exc_head": (exc_text or "")[:200],
    }
    log_path = Path.home() / "logs" / "wr2_canva_apply_telemetry.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(rec) + "\n")

# In _apply_one_draft, replace the single invoke_claude_apply block:
t0 = time.time()
try:
    result = invoke_claude_apply(pending_path)
    _log_run_telemetry(draft_id, 1, "success", time.time()-t0, "")
except CanvaInvokeError as exc:
    duration = time.time() - t0
    if _is_mcp_cold_failure(exc):
        _log_run_telemetry(draft_id, 1, "cold_sentinel", duration, str(exc))
        logger.warning("Draft %s: MCP cold sentinel detected — sleep 60s then retry once", draft_id)
        time.sleep(60)
        t1 = time.time()
        try:
            result = invoke_claude_apply(pending_path)
            _log_run_telemetry(draft_id, 2, "success", time.time()-t1, "")
        except CanvaInvokeError as exc2:
            outcome = "cold_sentinel" if _is_mcp_cold_failure(exc2) else (
                "timeout" if "timed out" in str(exc2) else "other"
            )
            _log_run_telemetry(draft_id, 2, outcome, time.time()-t1, str(exc2))
            logger.error("Draft %s retry failed: %s", draft_id, exc2)
            _send_telegram(...)
            return False
    else:
        outcome = "timeout" if "timed out" in str(exc) else "other"
        _log_run_telemetry(draft_id, 1, outcome, duration, str(exc))
        logger.error("Draft %s Canva apply failed: %s", draft_id, exc)
        _send_telegram(...)
        return False
```

**Risk review**:

- ✅ Zero overhead on happy path (50% baseline) — log write only
- ✅ 60s on cold path is far cheaper than the 25-min B1 probe approach
- ✅ Telemetry JSONL append-only, no DB schema change, no migration risk
- ⚠️ JSONL grows unbounded — at 1-3 attempts/day, 365 days = ~1000 lines, ~200KB. Negligible.
- ⚠️ Telegram alert still fires on retry-after-cold-fail, no flood

**Test plan**:

- [ ] py_compile + ast.parse OK
- [ ] Unit: simulate `invoke_claude_apply` raising CanvaInvokeError with sentinel string → assert sleep+retry called once
- [ ] Unit: simulate timeout exception → assert no retry, telemetry "timeout"
- [ ] Live trigger: 3 parallel runs on different drafts (force kickstart) → check ~/logs/wr2_canva_apply_telemetry.jsonl rows

**Rollout**:

1. PR `fix/wr2-b0-instrument-detect-sentinel-2026-05-08`
2. CI green, admin merge
3. Deploy worktree pull
4. canva-apply LaunchAgent re-bootstrap
5. Trigger 3 parallel test runs immediately to seed JSONL
6. Wait 7 days; analyze telemetry; decide B1/B2/other

**Effort**: 2h.

#### B0 known issue: telemetry success vs DB persist race (FIXED 2026-05-08)

The first B0 implementation (PR #516) wrote `_log_run_telemetry(draft_id, n, "success", ...)` BEFORE `_persist_canva_result`, so the JSONL recorded "success" while DB persist could still crash. Empirical case: draft `0e8e1cf5` 2026-05-07 23:53 → 2026-05-08 00:26 UTC — telemetry shows `outcome="success" duration_s=1943.4` but DB row has `canva_design_id=NULL`. Root cause: the asyncpg connection opened in `run()` was held open across the 32-min synchronous `subprocess.run([claude, -p, ...])` blocking call inside `invoke_claude_apply()`. The Fly Postgres tunnel / wireguard proxy closed the idle TCP socket. `_persist_canva_result` then raised `asyncpg.exceptions.ConnectionDoesNotExistError: connection was closed in the middle of operation` (two empirical occurrences in `~/logs/wr2_canva_apply.launchd.err.log`, both at the persist call site post-32min subprocess).

**Fix**: PR `fix/wr2-canva-persist-race-2026-05-08` reorders telemetry to write `success` only AFTER `_persist_canva_result` returns; on persist exception writes `outcome="persist_failed"` so JSONL truthfully mirrors DB state. `_persist_canva_result` accepts `dsn` and re-opens a fresh connection if `conn.is_closed()` — making persist resilient to wireguard idle-timeout. Tests: `scripts/tests/test_wr2_canva_apply_persist_race.py` (4 scenarios). The B0 success-rate denominator now equals the DB-persisted-rendered count, not the apply-returned-result count.

### B-NEW — Canva OAuth watchdog (SHIPPED 2026-05-08, replaces B1+B2)

**Scope**: every 6h, probe whether `claude -p` subprocess sees ≥30 `mcp__claude_ai_Canva__*` tools loaded. If fewer (or non-numeric output), the OAuth token in `~/.mcp-auth/` has gone stale → fetch the re-auth URL via a second `claude -p` calling `mcp__claude_ai_Canva__authenticate` and Telegram alert (P0) the operator with the URL embedded as a click link. 24h cooldown between alerts; first healthy→stale transition always alerts.

**Why this replaces B1 (MCP pre-warm wrapper) and B2 (session keeper daemon)**: 4 review streams (Codex/Gemini/DeepSeek/NotebookLM, 2026-05-07) independently rejected the "MCP cache warming" hypothesis as architecturally unfounded. Empirical 4 datapoints from B0 telemetry showed the only consistent failure mode is "MCP Canva not visible in `claude -p` subprocess" — which `claude -p` cannot self-heal because re-auth is browser-OAuth-interactive. A watchdog that pages an operator is the cheapest-correct mitigation; a wrapper that probes pre-call would just double the failure surface without unblocking re-auth.

**Files (Pro-local, NOT in repo, with snapshot for audit)**:

- `~/scripts/wr2-canva-oauth-watchdog.sh` — bash script (set -uo pipefail, flock single-instance, key=value state file)
- `~/Library/LaunchAgents/com.balizero.wr2.canva-oauth-watchdog.plist` — `StartInterval=21600` + `RunAtLoad=true`, mode 0444 per cicatrix P0-3
- `infra/launchagents/com.balizero.wr2.canva-oauth-watchdog.plist` — repo mirror
- `docs/wr2/skill-snapshots/canva-oauth-watchdog-2026-05-08.md` — script body snapshot for repo tracking + operator runbook
- `tests/lint/test_canva_oauth_watchdog.sh` — extracts the bash body from the snapshot, runs 6 scenarios with a stub `claude` (healthy / first stale / cooldown active / cooldown elapsed / non-numeric output / boundary count=29), 17 assertions

**Probe contract**:
- Healthy → integer ≥ `MIN_TOOLS=30` → exit 0, state.last_status=healthy.
- Stale → empty/non-numeric or < 30 → exit 1, state.last_status=stale, alert if no cooldown.
- 60s probe timeout (`PROBE_TIMEOUT`); 86400s alert cooldown (`ALERT_COOLDOWN_SEC`).

**Empirical post-bootstrap (2026-05-08)**: launchd `state=not running, last exit code=0`; first probe at 04:34:37 WITA logged `OK: 32 mcp__claude_ai_Canva__* tools visible (>= 30)`; next fire +21600s.

**Discovery during build**: sourcing `~/.nuzantara-secrets.env` with `set -a` poisons the `claude -p` subprocess env (likely `OPENROUTER_API_KEY` or `MINIMAX_API_KEY`) — the count probe silently returned 0. Mitigated by extracting only `TELEGRAM_BOT_TOKEN` + `TELEGRAM_OWNER_CHAT_ID` via grep+cut. `< /dev/null` is mandatory on the probe call (otherwise the "no stdin data received in 3s" warning pollutes the captured output).

### B1 — MCP pre-warm wrapper (PARKED — pending B0 data)

**Scope**: prima del `claude -p` "vero", lancia un probe `claude -p` short-running per portare in cache la connessione MCP Canva. Se probe fallisce → retry con backoff. Se persiste fail → Telegram alert + skip draft.

**File modificato**: `apps/backend-rag/backend/services/canva_renderer/claude_invoker.py`

**Design**:

```python
# Add at top of invoke_claude_apply, before the heavy subprocess

async def _probe_mcp_canva_warm(claude_bin: str, claude_cwd: Path, timeout_sec: int = 60) -> bool:
    """Probe whether MCP Canva tools are loaded in a fresh `claude -p` subprocess.

    Returns True if subprocess output mentions any mcp__claude_ai_Canva__* tool name,
    False if subprocess returns the "MCP Canva not available" sentinel or empty list.

    Cheap: runs in 15-45s. Done synchronously in the same process so the cache
    warms in this subprocess's connector context, then the heavy
    invoke_claude_apply call inherits the warm cache.
    """
    probe_prompt = (
        "List all MCP tool names available in this session whose names "
        "contain 'canva' (case-insensitive). Output ONLY a comma-separated "
        "list, no prose. If no canva tools, output exactly NONE."
    )
    completed = subprocess.run(
        [claude_bin, "-p", probe_prompt],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        cwd=str(claude_cwd),
        check=False,
    )
    if completed.returncode != 0:
        return False
    output = completed.stdout.strip()
    return "mcp__claude_ai_Canva__" in output and "NONE" not in output


def invoke_claude_apply(canva_pending_path: Path, *, ...) -> CanvaApplyResult:
    ...
    # Pre-warm with up to 3 retries, each 60s timeout, 30s backoff between
    for attempt in range(3):
        if _probe_mcp_canva_warm(claude_bin, claude_cwd):
            logger.info("MCP Canva warmed (attempt %d)", attempt + 1)
            break
        logger.warning("MCP Canva probe failed (attempt %d/3)", attempt + 1)
        if attempt < 2:
            time.sleep(30)
    else:
        raise CanvaInvokeError(
            "MCP Canva probe failed 3x in 5min — cache cold or connector down. "
            "Skipping draft to avoid wasted 25min subprocess run."
        )

    # ... rest of existing flow ...
```

**Risk review**:

- **Risk**: 3× probe × 45s = 2 min budget aggiuntivo per ogni run. Per 1 carosello/giorno trascurabile.
- **Risk**: probe hits MCP rate limit (60 req/min documented). Mitigation: probe è 1 chiamata `list tools`, non hits Canva API.
- **Risk**: false positive — probe vede tool ma vero run fallisce. Mitigation: niente; in quel caso il run principale fallisce con timeout ed entriamo nel watchdog (B3).
- **Risk**: false negative — probe fallisce ma cache si scalderebbe nel run principale. Mitigation: 3 retries + Telegram alert sul terzo fallimento (operator può manualmente kickstartare).

**Test plan**:

- [ ] Unit: mock `subprocess.run` per simulare entrambi gli output ("mcp**claude_ai_Canva**... " vs "NONE"). Assert return True/False.
- [ ] Integration: lancia `python -m backend.services.canva_renderer.claude_invoker.test_probe` script ad-hoc 10 volte in 1 ora; misura % success.
- [ ] E2E post-merge: 3 run consecutivi sul cron 05:10 con probe attivo; confronta success rate vs baseline 7-maggio.

**Rollout**:

1. PR su branch `fix/wr2-canva-mcp-prewarm-2026-05-XX`
2. CI green → admin merge
3. Deploy worktree pull
4. LaunchAgent canva-apply restart
5. Manual kickstart su 1 draft pending → verifica probe log line presente

**Effort**: 4h.

### B2 — Canva session keeper daemon

**Scope**: cron Pro ogni 30 min lancia `claude -p "ping mcp canva"` per mantenere il connector cache caldo 24/7. Indipendente dai run canva-apply.

**File creato**: `~/scripts/wr2-canva-mcp-keeper.sh`

**Design**:

```bash
#!/bin/bash
# wr2-canva-mcp-keeper.sh — keep MCP Canva connector cache warm.
# Runs every 30 min via LaunchAgent com.balizero.wr2.canva-mcp-keeper.
set -euo pipefail

source ~/.nuzantara-secrets.env 2>/dev/null || true
LOG=~/logs/wr2_canva_mcp_keeper.log
mkdir -p "$(dirname "$LOG")"

cd ~/Desktop/nuzantara

OUTPUT=$(claude -p "Output the count of MCP tool names containing 'canva'. Just a number." \
    --output-format text 2>&1 | tail -1 | tr -d '[:space:]')

TS=$(date "+%Y-%m-%d %H:%M:%S WITA")
if [[ "$OUTPUT" =~ ^[0-9]+$ ]] && [[ "$OUTPUT" -ge 30 ]]; then
    echo "$TS keeper OK: $OUTPUT canva tools visible" >> "$LOG"
else
    echo "$TS keeper FAIL: output='$OUTPUT'" >> "$LOG"
    # Telegram alert tier P1 if 3 consecutive fails (track via state file)
    STATE=~/.agent/decisions/state/wr2_canva_keeper.state
    mkdir -p "$(dirname "$STATE")"
    FAILS=$(cat "$STATE" 2>/dev/null || echo "0")
    FAILS=$((FAILS + 1))
    echo "$FAILS" > "$STATE"
    if [[ "$FAILS" -ge 3 ]]; then
        ~/.claude/scripts/hotfix-notify.sh \
          "WR2 Canva MCP keeper: 3 consecutive failures. Subprocess cannot see MCP Canva. Investigate." || true
    fi
    exit 1
fi
# Reset fail counter on success
echo "0" > ~/.agent/decisions/state/wr2_canva_keeper.state 2>/dev/null || true
```

**File creato**: `~/Library/LaunchAgents/com.balizero.wr2.canva-mcp-keeper.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
  <key>Label</key><string>com.balizero.wr2.canva-mcp-keeper</string>
  <key>Program</key><string>/Users/nuzantara/scripts/wr2-canva-mcp-keeper.sh</string>
  <key>StartInterval</key><integer>1800</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/Users/nuzantara/logs/wr2_canva_mcp_keeper.launchd.out.log</string>
  <key>StandardErrorPath</key><string>/Users/nuzantara/logs/wr2_canva_mcp_keeper.launchd.err.log</string>
  <key>EnvironmentVariables</key><dict>
    <key>HOME</key><string>/Users/nuzantara</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
</dict></plist>
```

**Risk review**:

- **Risk**: keeper consume Claude OPUS Max plan quota. Mitigation: probe è 1 messaggio short, ~5s subprocess, no thinking, no tool call → quota burn trascurabile (48 probe/giorno × 5s = 4 min CPU + minimal token).
- **Risk**: keeper innesca race con run canva-apply concomitante. Mitigation: keeper exit fast (≤30s), canva-apply prende ~25 min — race window improbabile a meno che cron 30-min keeper coincida con kickstart canva-apply. Se succede, keeper può fallire ma non danneggia il run principale.
- **Risk**: keeper su Mac dorme (laptop in sleep). Mitigation: Pro è H24 server, no sleep configurato per design. Se sleep avviene, keeper riparte al wake — accettabile.

**Test plan**:

- [ ] Manual: lanciare `~/scripts/wr2-canva-mcp-keeper.sh` 5 volte in 5 min. Verifica log: 5 "keeper OK".
- [ ] Edge case: simula fail (rinomina temp `claude` binary). Verifica state file incrementa, dopo 3 fail Telegram fires.
- [ ] Verifica plist: `launchctl bootstrap`, `launchctl print` mostra `state = waiting` con next-fire `+1800s`.

**Rollout**:

1. Script + plist drop su disco
2. plutil -lint OK
3. `launchctl bootstrap gui/$UID`
4. Wait 30 min, verifica log entry
5. PR mirror plist `infra/launchagents/`

**Effort**: 6h (incluso testing + osservazione 1 ora).

### B3 — Supervisor watchdog + heartbeat table

**Scope**: nuova tabella `wr2_supervisor_heartbeat` + daemon esterno che pinga supervisor e alerta se canva-apply success rate <80% in 24h.

**Migration creata**: `apps/backend-rag/backend/db/migrations_v2/161_wr2_supervisor_heartbeat.sql`

**Design**:

```sql
-- migration 161 — wr2_supervisor_heartbeat
CREATE TABLE IF NOT EXISTS wr2_supervisor_heartbeat (
    id BIGSERIAL PRIMARY KEY,
    pid INTEGER NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    last_notify_at TIMESTAMPTZ,
    last_kickstart_at TIMESTAMPTZ,
    last_kickstart_target TEXT,
    pending_drafts_count INTEGER NOT NULL DEFAULT 0,
    oldest_pending_age_seconds INTEGER NOT NULL DEFAULT 0,
    written_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_wr2_supervisor_heartbeat_written_at
    ON wr2_supervisor_heartbeat (written_at DESC);

-- === ROLLBACK ===
DROP INDEX IF EXISTS ix_wr2_supervisor_heartbeat_written_at;
DROP TABLE IF EXISTS wr2_supervisor_heartbeat;
```

**Modifica `scripts/wr2_supervisor.py`**:

```python
# In supervisor main loop, every 60s:
async def _write_heartbeat(conn, pid, last_notify_at, last_kickstart_at, last_kickstart_target):
    pending_count = await conn.fetchval("""
        SELECT COUNT(*) FROM war_room_drafts
         WHERE status NOT IN ('rendered','rejected','published')
    """)
    oldest_age = await conn.fetchval("""
        SELECT EXTRACT(EPOCH FROM (NOW() - MIN(updated_at)))::int
          FROM war_room_drafts
         WHERE status NOT IN ('rendered','rejected','published')
    """) or 0
    await conn.execute("""
        INSERT INTO wr2_supervisor_heartbeat
            (pid, started_at, last_notify_at, last_kickstart_at,
             last_kickstart_target, pending_drafts_count,
             oldest_pending_age_seconds)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
    """, pid, _started_at, last_notify_at, last_kickstart_at,
        last_kickstart_target, pending_count, oldest_age)
```

**File creato**: `scripts/wr2_supervisor_watchdog.py`

```python
"""WR2 Supervisor Watchdog — alerts on liveness + canva success rate.

Runs as launchd daemon (KeepAlive=true), every 60s reads
wr2_supervisor_heartbeat + computes:
  - heartbeat freshness (age of latest row)
  - canva-apply 24h success rate (rendered_24h / drafts_imaged_24h)
  - oldest pending draft age

Telegram tiered:
  P0: heartbeat older than 5 min → supervisor crashed/stuck
  P0: oldest pending >2h AND no rendered in 24h → pipeline frozen
  P1: success rate <80% in 24h
  P2: anything below — dashboard only (Sprint C)
"""
```

**File creato**: `~/Library/LaunchAgents/com.balizero.wr2.supervisor-watchdog.plist`
KeepAlive=true daemon, no schedule, RunAtLoad=true.

**Risk review**:

- **Risk**: heartbeat insert ogni 60s = 1440 rows/day. Crescita unbounded. Mitigation: cron daily prune `DELETE WHERE written_at < NOW() - INTERVAL '7 days'`.
- **Risk**: watchdog stesso può crashare. Mitigation: `KeepAlive=true` launchd respawn entro 10s. Meta-watchdog (watchdog del watchdog) non implementato — accettabile.
- **Risk**: race condition tra supervisor heartbeat write e watchdog read. Mitigation: read è semplice SELECT con ORDER BY DESC LIMIT 1, no lock contention.

**Test plan**:

- [ ] Unit: mock conn pool, verifica query SQL syntax con asyncpg fake.
- [ ] Integration: kill supervisor, verifica watchdog Telegram fires entro 5 min.
- [ ] E2E: simula 24h con success rate forzato 70%, verifica P1 alert.

**Rollout**:

1. Migration 161 PR (Squawk lint passes — tabella nuova zero contention).
2. Supervisor patch heartbeat write nello stesso PR.
3. CI green → admin merge.
4. Deploy migration via post-deploy job (PR #336 path).
5. Supervisor restart (bootout + bootstrap).
6. PR successivo per `wr2_supervisor_watchdog.py` + plist.
7. Bootstrap watchdog daemon.
8. Verifica Telegram alert su test crash forzato.

**Effort**: 8h (3h supervisor patch + 4h watchdog + 1h E2E test).

### B4 — Restore fact-extractor + fact-checker

**Scope**: ripristinare i 2 plist da `.disabled/` + restore TRANSITIONS chain. Sostituisce il bypass Sprint A.

**Owner decision (decisione 2 del long-term design)**: sì, ripristina fact-checking. Plus aggiungi supervisor liveness (B3 già copre).

**File mossi**:

- `~/Library/LaunchAgents/.disabled/com.balizero.wr2.fact-extractor.plist` → `~/Library/LaunchAgents/`
- `~/Library/LaunchAgents/.disabled/com.balizero.wr2.fact-checker.plist` → `~/Library/LaunchAgents/`

**Modifica `scripts/wr2_supervisor.py`**:

```python
# Revert Sprint A bypass — restore the full chain
TRANSITIONS = {
    ("*", "briefed"):                                  "com.balizero.wr2.draft-generator",
    ("briefed", "drafts"):                             "com.balizero.wr2.image-generator",
    ("drafts", "drafts_imaged"):                       "com.balizero.wr2.fact-extractor",  # RESTORED
    ("drafts_imaged", "drafts_imaged_facted"):         "com.balizero.wr2.fact-checker",     # RESTORED
    ("drafts_imaged_facted", "drafts_imaged_checked"): "com.balizero.wr2.canva-apply",
    # ... terminals ...
}
```

**Modifica `scripts/wr2_canva_apply.py`**:

```python
# Sprint A widened to ('drafts_imaged', 'drafts'); restore narrow filter
WHERE status = 'drafts_imaged_checked'  # only post fact-check
```

**Risk review**:

- **Risk**: fact-extractor + fact-checker codice non testato da 2 mesi (disabled da PR #299 cutover). Mitigation: lancia `launchctl kickstart` su un draft sintetico prima di production cron.
- **Risk**: fact-checker LLM choice ancora open question (OPUS o Gemini). Mitigation: parte con Claude OPUS (default), Sprint B follow-up può switchare a Gemini se quota burn alto.
- **Risk**: 2 stage in più = +5-10 min totale per draft. Mitigation: era questo lo stato originale (PR #171 → 26 aprile). Cadence 1/giorno facilmente sostiene.

**Test plan**:

- [ ] Manual kickstart fact-extractor su draft test → verifica status transition `drafts_imaged → drafts_imaged_facted`.
- [ ] Idem fact-checker → `drafts_imaged_facted → drafts_imaged_checked`.
- [ ] E2E live cron 05:10 successivo → carosello arriva a `rendered`.

**Rollout**:

1. PR `fix/wr2-restore-fact-stages-2026-05-XX`
2. plist mossi (chmod u+w → mv → chmod 0444)
3. supervisor TRANSITIONS revertite
4. wr2_canva_apply.py status filter narrowed
5. CI + admin merge
6. Deploy worktree pull
7. Bootstrap fact-extractor + fact-checker plists
8. Supervisor restart
9. Watch cron 05:10 successivo

**Effort**: 4h (2h verify codice + 2h E2E test).

### B5 — Codex timeout bump 600→900s

**Scope**: trivial. Run de69f035 (7 maggio 12:00) ha avuto slide 6 timeout a 648.7s sul Codex CLI default 600s.

**File modificato**: `scripts/wr2_image_generator.py`

```python
CODEX_TIMEOUT_SEC = float(os.environ.get("WR2_CODEX_TIMEOUT_SEC", "900"))  # was 600
```

**Risk review**: nessuno. 900s lascia headroom su 800s p99 osservato.

**Test plan**: nessuno richiesto. Single-line const change.

**Rollout**: incluso nel PR fact-stages restore (B4) come piccolo follow-up.

**Effort**: 5 min.

---

## SPRINT C — Deploy governance + telemetry (week 2, ~2 giorni)

**Goal**: zero "deploy drift" + visibilità real-time stato pipeline.

### C1 — Auto-pull deploy worktree hourly

**Scope**: nuovo LaunchAgent che ogni ora fa `git -C ~/Desktop/nuzantara-deploy pull origin main --ff-only`. Telegram P1 alert su conflict.

**File creato**: `~/scripts/wr2-deploy-pull.sh`

```bash
#!/bin/bash
set -euo pipefail
LOG=~/logs/wr2_deploy_pull.log
mkdir -p "$(dirname "$LOG")"

cd ~/Desktop/nuzantara-deploy

# Lockfile to avoid concurrent pulls
LOCK=/tmp/wr2-deploy-pull.lock
exec 200>"$LOCK"
flock -n 200 || { echo "$(date) — already running, skip" >> "$LOG"; exit 0; }

BEFORE=$(git rev-parse HEAD)
git fetch origin main 2>>"$LOG"
if git merge-base --is-ancestor origin/main HEAD; then
    echo "$(date) — already up to date ($BEFORE)" >> "$LOG"
    exit 0
fi

if ! git pull --ff-only origin main 2>>"$LOG"; then
    echo "$(date) — PULL FAILED (likely non-FF or conflict)" >> "$LOG"
    ~/.claude/scripts/hotfix-notify.sh \
      "WR2 deploy-pull conflict on $(hostname). Manual intervention required." || true
    exit 1
fi
AFTER=$(git rev-parse HEAD)
echo "$(date) — pulled $BEFORE → $AFTER" >> "$LOG"
```

**File creato**: `~/Library/LaunchAgents/com.balizero.wr2.deploy-puller.plist`

```xml
<key>StartInterval</key><integer>3600</integer>
<key>RunAtLoad</key><true/>
```

**Risk review**:

- **Risk**: pull avviene mentre cron canva-apply gira (legge file dal worktree). Mitigation: `flock` lockfile + cron canva-apply avviene 05:10 una volta al giorno, finestra collisione minima.
- **Risk**: non-FF pull (forced push su main, MAI dovrebbe accadere). Mitigation: `--ff-only` esce non-zero, Telegram alert P1 P. Operator manuale.
- **Risk**: pull viola Sprint A "Sprint A1: deploy worktree manual pull post-merge" pattern. Mitigation: ora è sostituito dal puller; aggiorna `2026-05-07-wr2-longterm-design.md` per riflettere.

**Test plan**:

- [ ] Manual: trigger script, verifica log + git log -1.
- [ ] Edge: forza conflict (commit locale on deploy/main). Verifica Telegram fires.

**Rollout**:

1. Script + plist
2. Bootstrap
3. Wait 1h, verifica log entry

**Effort**: 2h.

### C2 — Pro-local dashboard

**Scope**: web UI Pro-only su `127.0.0.1:8090/wr2`. Single HTML page, plain Python `http.server` + jinja2 templates. Read-only views.

**File creato**: `apps/backend-rag/backend/services/wr2_dashboard/server.py`

**Views (4 sezioni)**:

1. **Pipeline status** — counts by status (briefed, drafts, drafts_imaged, ...), oldest pending age
2. **Supervisor health** — heartbeat freshness, last NOTIFY, last kickstart
3. **Recent runs** — last 20 drafts: id, status, design_id, applied_at
4. **Logs tail** — last 50 lines per stage (canva-apply, image-gen, draft-gen)

**Risk review**:

- **Risk**: server expone dati sensibili. Mitigation: bind solo `127.0.0.1`, no remote access.
- **Risk**: server crash. Mitigation: KeepAlive=true LaunchAgent.
- **Risk**: query DB ogni refresh = load. Mitigation: cache in-memory 30s TTL.

**Test plan**:

- [ ] curl `127.0.0.1:8090/wr2/api/status` → JSON shape valido
- [ ] Browser → 4 view rendered
- [ ] kill server → KeepAlive respawn entro 10s

**Effort**: 6h.

### C3 — Tiered Telegram alerts

**Scope**: aggiornare `~/.claude/scripts/hotfix-notify.sh` per accettare `--tier=P0|P1|P2` argomento. P2 → solo log file no Telegram.

**File modificato**: `~/.claude/scripts/hotfix-notify.sh`

**Cooldown logic**: state file per-tier che traccia last-fire timestamp.

**Risk review**: trivial. Backward compatible (default P0 se no flag).

**Effort**: 3h.

---

## SPRINT D — NLM feeder Mini routing fix (1 giorno)

**Goal**: NB-INTEL torna a ricevere OSINT fresh da Mini Redis stream.

### D1 — Verifica PR #486 status

**Scope**: nessun codice. Solo `gh pr view 486` per capire se è merged, conflict, draft.

**Effort**: 5 min.

### D2 — Patch base_worker.redis_cmd (se non già merged)

**Scope**: leggi `GARUDA_REDIS_HOST` env, prepend `-h $host` a redis-cli args.

**File modificato**: `apps/mata-garuda/mata_garuda/workers/base_worker.py`

**Design**: già documentato in cicatrix (NLM feeder split-brain entry, ANTIBODY shipped on `fix/nlm-feeder-resurrect-2026-05-06`). Cherry-pick se non in main.

**Risk review**: minimo, fix locale.

**Test plan**: 9 unit test già scritti nel branch resurrect.

**Effort**: 1h se cherry-pick, 0 se già merged.

### D3 — E2E feeder

**Scope**: lancia 1 cron tick manuale, verifica NB-INTEL count incrementa.

**Effort**: passive 1h watch.

---

## SPRINT E — Auto-learning chain (week 3-4, ~5-7 giorni)

**Goal**: measurer + learner-nightly + oracle + strategos vivi → carousel migliora settimanalmente con feedback loop.

**Critical decision: IG metrics ingestion path**

3 opzioni (vedi long-term design doc §Sprint E):

- E.opt-1: GA4 (proxy weak)
- E.opt-2: Telegram `/posted` + `/metrics` manual paste
- **Recommended: E.opt-2** (zero infra, Damar discipline-based)

### E1 — Telegram bot extension

**Scope**: aggiungi 2 commands al bot `@Balizerobot`:

- `/posted <ig_url>` — Damar replica al messaggio review-gate, IG URL parsato → INSERT `war_room_posts (draft_id, ig_url, posted_at)`
- `/metrics likes=X saves=Y comments=Z reach=R` — 24h dopo post, Damar invia metrics → INSERT `post_metrics_history`

**File modificato**: `apps/backend-rag/backend/services/telegram/handlers.py` (bot router)

**Migration creata**: 162 (war_room_posts + post_metrics_history) — verifica se già esiste in migration 112.

**Risk review**:

- **Risk**: Damar non è disciplinato. Mitigation: bot reminder 24h post `/posted` con `/metrics ?` template prefilled.
- **Risk**: malformed input. Mitigation: regex parser strict, error message su parse fail.

**Effort**: 4h.

### E2 — Measurer cron

**Scope**: `com.balizero.wr2.measurer` schedule daily 12:00 WITA. Reads `war_room_posts` 24h+ old WHERE has metrics, computes engagement_rate, stores in `post_metrics_history`.

**File modificato**: `apps/backend-rag/backend/services/wr2_measurer/cli.py`

**Effort**: 2h.

### E3 — Learner-nightly

**Scope**: `com.balizero.wr2.learner-nightly` 03:00 WITA. Read 30d post_metrics_history, compute correlations (topic-cluster × engagement), update `m13_retrain_log`.

**Effort**: 4h.

### E4 — Oracle weekly

**Scope**: `com.balizero.wr2.oracle` Sun 22:30 WITA. Read learner output, propone 3 topic suggestions per week, write to `oracle_digest` table (new).

**Effort**: 4h.

### E5 — Strategos weekly

**Scope**: `com.balizero.wr2.strategos` Sun 22:00 WITA. Reviews topic mix balance (visa% / tax% / property% / business%), proposes rebalance to oracle next week.

**Effort**: 4h.

---

## SPRINT F — Decommission cleanup (week 5, 1 giorno)

| ID  | Task                                  | File                                                                   |
| --- | ------------------------------------- | ---------------------------------------------------------------------- |
| F1  | Archive `wr2_canva_desktop_apply.py`  | move → `archive/wr2_canva_desktop_apply.py.deprecated-2026-05-XX`      |
| F2  | Remove `runbooks/APPLICA_WAR_ROOM.md` | rm in repo (skill is SSOT)                                             |
| F3  | Decommission trend-hunter             | `launchctl bootout` + `rm` plist + remove from supervisor (if any ref) |
| F4  | Update `docs/wr2/SUPERVISOR.md`       | fact-stages restored, watchdog added                                   |
| F5  | Update `docs/wr2/sprint2-mapping.md`  | reflect target state                                                   |

**Effort**: 1 giorno.

---

## INVARIANTS (owner-binding)

Già documentati in `2026-05-07-wr2-longterm-design.md` §6. Ricapitolo:

- OB-1: human-in-loop permanente
- OB-2: 1 carosello/giorno, no scale-up
- OB-3: Anthropic OAuth-only
- OB-4: cost constraint per LLM
- OB-5: `wr2_status_change` volatile by design
- OB-6: WR2 non scrive client-facing
- OB-7: test designs trash-after-test

---

## TIMELINE STIMATA

| Sprint                 | Duration   | Cumulato     |
| ---------------------- | ---------- | ------------ |
| B (canva stabilizz)    | 3-4 giorni | 4 giorni     |
| C (deploy + dashboard) | 2 giorni   | 6 giorni     |
| D (NLM feeder)         | 1 giorno   | 7 giorni     |
| E (auto-learning)      | 5-7 giorni | 12-14 giorni |
| F (cleanup)            | 1 giorno   | 13-15 giorni |

**Conservative total**: 3 settimane lavorative.

---

## METRICHE DI SUCCESSO

| Sprint  | Metric                           | Target                            |
| ------- | -------------------------------- | --------------------------------- |
| B       | canva-apply success rate / 24h   | ≥80% (da ~50% baseline)           |
| B       | Heartbeat freshness              | <2 min                            |
| C       | Deploy drift                     | 0 manual pulls in 7 giorni        |
| C       | Dashboard uptime                 | ≥99%                              |
| D       | NB-INTEL fresh sources / week    | ≥50                               |
| E       | Auto-learning loop closed        | Weekly oracle digest produced     |
| Globale | 1 carosello/giorno deterministic | 7/7 days, 4 settimane consecutive |

---

— Drafted 2026-05-08, Antonello + Claude Opus 4.7 (1M context)
