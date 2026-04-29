# 09 — Migration plan: ordine onde + sequenziamento Q2-B

**Data**: 2026-04-29
**Stato**: FASE 2 design — implementation ordering + parallelism policy
**Riferimenti**: 07 protocol + 08 failure isolation + Q2-B alignment con Zero (parallel solo file/repo, serial Air/Fly/Vercel runtime)

---

## 1. Sequenziamento policy (Q2-B clarification)

**Da Zero alignment**: "parallel solo dove blast è file, serial dove blast è runtime".

| Wave | Parallel? | Motivo |
|---|---|---|
| Wave 0 — Foundations (Genoma + Supervisor deploy) | NO | Setup unico, non parallelizzabile |
| Wave 1 — backend-rag heartbeat (file repo) | SÌ (parallel subagent worktrees) | Solo modifiche file in repo, blast è solo PR |
| Wave 2 — Air cron + LaunchAgent | NO (serial) | SSH Air, runtime side-effect (launchctl kickstart) |
| Wave 3 — 7 channel + 3 MCP server | NO (serial) | Backend-internal runtime impact, deploy Fly per-channel |
| Wave 4 — 8 Vercel subdomain frontend | SÌ (parallel preview) | Vercel preview-only, Production rollout in chaos test |
| Wave 5 (FASE 4) — Chaos test on Pro reale | NO (serial, controllato) | Q3-A guardrails: ordine non-distruttivo→distruttivo, abort criteria |

**Subagent dispatch policy** (per Wave 1 + 4 parallele):
- Skill `superpowers:dispatching-parallel-agents` + `superpowers:using-git-worktrees` (mandatory).
- Worktree directory: `~/Desktop/nuzantara-worktrees/innervation-{wave-id}/`.
- Subagent termina → merge worktree branch → cleanup.

---

## 2. Wave 0 — Foundations (sequenziale, ~2h)

**Goal**: deploy Supervisor + control panel + scheduled_tick + Genoma file + Cell new sensor. **Risk: medium** (touches LaunchAgent live, plist mass corruption cicatrix recente).

### 2.1 Step W0.1 — Genoma file build

- File `apps/organism/organism/genome.yaml` — entries iniziali per Wave 1 organi (4 entry: backend.api, drive_poll_service, claude_max_watcher, login_healthcheck) + scheletro 149.
- File `apps/organism/organism/tools/validate_genome.py` (~50 LOC) — validation script (unique IDs, valid enums, dependencies graph acyclic, checksum SHA256).
- Pre-commit hook (`.husky/pre-commit` o `.git/hooks/pre-commit`) → `python -m organism.tools.validate_genome`.
- Tests: `apps/organism/tests/test_genome_validation.py` — 8 unit tests (happy path, invalid runtime, dup IDs, missing deps, bad checksum, ecc.).

### 2.2 Step W0.2 — Cell new sensor

- File `apps/cell/cell/sensors/genome_aggregator_sensor.py` — sensor reads Genoma + last_seen SQLite + bridge sources.
- File `apps/cell/cell/main.py` — wire sensor in PulseEngine.
- Tests: `apps/cell/tests/test_genome_aggregator_sensor.py` — 6 unit tests.

### 2.3 Step W0.3 — Bridge sources reader

- File `apps/cell/cell/sensors/bridge_state_reader.py` — read state files Pattern A (state_file type bridge_source).
- Initial coverage: state files in `~/.agent/decisions/state/*.last.json` + `~/.cron-agent-python/*.state.json`.
- Tests: 8 unit tests.

### 2.4 Step W0.4 — Supervisor deploy

- Verify `apps/organism/organism/launchd/com.nuzantara.organism.supervisor.plist` content (already in repo).
- **Pre-deploy verification**: read plist, check ProgramArguments/EnvironmentVariables (PATH+HOME mandatory per VADEMECUM §11), StandardOut/ErrorPath in `~/logs/`.
- `chmod u+w` (cicatrix P0-3 protection unset for write) → `cp` → `~/Library/LaunchAgents/` → `chmod 0444` (re-protect) → `launchctl load`.
- Verify: `launchctl list com.nuzantara.organism.supervisor` → LastExitStatus=0. Check `redis-cli GET organism:supervisor:heartbeat` → fresh timestamp.

### 2.5 Step W0.5 — Control panel deploy

- Same procedure as W0.4 for `com.nuzantara.organism.control-panel.plist`.
- Setup operator token: `mkdir -p ~/.organism && head -c 32 /dev/urandom | base64 > ~/.organism/token && chmod 600 ~/.organism/token`.
- Verify: `curl http://127.0.0.1:1819/health` → 200. `curl :1819/stats -H "X-Organism-Token: $(cat ~/.organism/token)"` → JSON with stats.

### 2.6 Step W0.6 — scheduled_tick LaunchAgent

- New plist `apps/organism/organism/launchd/com.nuzantara.organism.scheduled-tick.plist` (NUOVO, non in repo oggi).
- Schedule: `StartCalendarInterval` ogni ora (Minute=0). RunAtLoad=true.
- ProgramArguments: `python -m organism.scheduled_tick`.
- Tests: integration test che valida emit 1 event per call.

### 2.7 Step W0.7 — Wave 0 commit + verify

- Single PR with all W0 steps (~10 file modifications + 4 new files + 3 plist additions).
- CI tests must pass.
- Manual deploy after merge: `bash apps/organism/scripts/deploy_w0.sh` (NUOVO script orchestrating W0.4/W0.5/W0.6 atomically).
- Smoke test: 5 minuti dopo deploy, controllo `organism:events` stream count, JSONL writes, heartbeat key, control panel /health.

**Wave 0 success criteria**:
- ✅ Genoma loadable, checksum valid.
- ✅ Cell pulse runs with new sensor, no exception.
- ✅ Supervisor LaunchAgent active, heartbeat fresh.
- ✅ Control panel HTTP responsive.
- ✅ scheduled_tick fires hourly (verifiable in JSONL).

**Wave 0 abort if**: any LaunchAgent fails to start within 60s (suggests P0-3 plist corruption recurrence). Fall back to investigation.

---

## 3. Wave 1 — Backend-rag heartbeat (parallel subagent, ~3h)

**Goal**: 4 critical organi emit heartbeat verso `organism:events`. Parallel via worktree subagents.

**Organi target**:
1. `backend.api` (FastAPI lifespan) — 60s heartbeat
2. `backend.crm.drive_poll` (Air cron, currently DISABLED) — heartbeat **only when re-enabled** (Wave 2 dependent)
3. `pro.claude_max_watcher` (~/scripts/claude-max-usage-watcher.py) — 3600s heartbeat (hourly)
4. `pro.login_probe` (~/scripts/login-healthcheck.sh) — 900s heartbeat (15min)

**Parallel dispatch policy**: 2 subagent paralleli (max), worktree separati.
- Subagent A: backend-rag api lifespan (Python). Branch `feat/innervation-w1-backend-api`.
- Subagent B: Pro home scripts heartbeat (sh+py). Branch `feat/innervation-w1-pro-scripts`.

(drive_poll bloccato fino a Wave 2 cicatrix re-enable; quindi solo 2 subagent in W1, non 4.)

**Cost LOC**: ~30 lines per subagent. Each → 1 PR, L2 auto-merge if CI green.

### 3.1 Subagent A brief (excerpt)

```
Goal: Add heartbeat emission to backend-rag FastAPI lifespan.
Scope:
  - apps/backend-rag/backend/app/main.py (or app_factory.py): in lifespan(), spawn asyncio task that calls await emit_event(kind="heartbeat", source="backend.api", payload={...}) every 60s.
  - emit_event must use the new (TBD) helper that prefers JSONL → Redis stream
    (already exists at apps/organism/organism/emit.py — import from there if importable from
    backend-rag, or re-implement minimal version to avoid cross-app coupling).
Constraints:
  - graceful shutdown: cancel heartbeat task on lifespan exit
  - failure tolerance: emit_event exceptions must not crash backend
  - test: backend/tests/app/test_lifespan_heartbeat.py
```

### 3.2 Subagent B brief (excerpt)

```
Goal: Add heartbeat emission to ~/scripts/claude-max-usage-watcher.py and ~/scripts/login-healthcheck.sh.
Scope:
  - claude-max-usage-watcher.py: at end of cycle, before exit, emit_event(kind="heartbeat", source="pro.claude_max_watcher", payload={"check_count": N}).
  - login-healthcheck.sh: invoke a small Python helper (~/scripts/innervate.py) that does emit_event() — sh can't import organism module directly.
  - ~/scripts/innervate.py: thin wrapper around organism.emit.emit_event for shell scripts.
Constraints:
  - Pro homedir scripts NOT in git repo for this branch — manual install via cp.
  - Verify emit appears in JSONL within 5s after script run.
```

---

## 4. Wave 2 — Air cron + LaunchAgent (serial, ~3h)

**Goal**: re-enable drive_poll_service (after 48h test green per cicatrix) + Air `indexing-sweep` heartbeat.

**Serial reason**: SSH Air access for re-enable cron + verify launchctl. Cannot parallelize SSH operations (one SSH multiplex slot, plus risk of cron conflicts).

### 4.1 Step W2.1 — Pre-condition check

- Verify drive_poll_service hotfix `720d54f5c` is in main, deploy completed, 48h have passed.
- Read `~/.agent/decisions/state/drive_poll.last.json` (if exists) for last status.

### 4.2 Step W2.2 — Re-enable drive_poll cron Pro

- Edit `~/scripts/openclaw-cron/drive-poll.sh` o equivalente (cicatrix mention `# DISABLED 2026-04-29 02:42`).
- Re-enable cron + add heartbeat emission at end.
- Verify: 5min later, JSONL has heartbeat from `backend.crm.drive_poll`.

### 4.3 Step W2.3 — Air indexing-sweep heartbeat

- SSH Air, edit `~/Projects/nuzantara/scripts/daily_indexing_cron.sh` o equivalent.
- Add heartbeat emission via `~/scripts/innervate.py` (Air-side copy).
- Verify next 00:30 WITA cron run emits heartbeat.

### 4.4 Step W2.4 — Update Genoma

- Add 2 entries to `genome.yaml`: `backend.crm.drive_poll`, `air.indexing_sweep`.
- bridge_source for both: state file paths.
- PR + merge.

---

## 5. Wave 3 — 7 channel + 3 MCP server (serial, ~4h)

**Goal**: 7 channel processor (whatsapp, telegram, instagram, twitter, web, gchat, slack) + 3 MCP server emit lifecycle events.

**Serial reason**: backend-rag deploy per change → Fly machine restart per change. Parallelizing = 7 deploy concurrent = cicatrix `SQL v2 migrations OLD image` ready to fire.

### 5.1 Step W3.1 — webhook_processor heartbeat

- `apps/backend-rag/backend/services/channels/webhook_processor.py` (PR #360 ack-first) — add heartbeat 60s in async loop.
- Bridge: `inbound_webhooks` SQL table → bridge_source `sql_table` for Genoma channel entries.

### 5.2 Step W3.2 — 7 channel adapter heartbeat

- For each channel (`apps/backend-rag/backend/channels/{whatsapp,telegram,instagram,twitter,web,gchat,slack}/`):
  - Add startup emit_event `kind=channel_started` con channel name.
  - Add periodic heartbeat 60s while channel webhook processor active.
  - Genoma entry per channel with bridge_source = `inbound_webhooks` table filtered by channel.

### 5.3 Step W3.3 — MCP server lifecycle events

- `apps/nuzantara-mcp/`, `apps/nuzantara-mcp-advanced/`, `apps/nuzantara-mcp-browser/`:
  - On startup (FastMCP `lifespan`): emit `kind=mcp_started, source=mcp.<name>`.
  - On tool invocation: increment counter, every 100 invocations emit `kind=mcp_active, payload={tool_count: N}` (no continuous heartbeat — they're sporadic, session-bound).
  - On shutdown: emit `kind=mcp_stopped`.
- Genoma entry: type=`mcp_session`, expected_hb_seconds=0 (sporadic, no heartbeat required).

### 5.4 Step W3.4 — Single PR per channel/MCP

- 7 + 3 = 10 PRs. Auto-merge if CI green. Sequential to avoid Fly deploy collisions.

---

## 6. Wave 4 — Vercel subdomain frontend (parallel preview, ~2h)

**Goal**: 8 Vercel subdomain emit client beacon on page load. Parallel via Vercel preview (NOT prod) until chaos test.

### 6.1 Step W4.1 — Beacon API endpoint

- New backend endpoint `POST /api/innervation/beacon` accepting `{source, page, ts}` from frontend.
- Auth: API key + same-origin enforcement (CORS).
- Emit: convert beacon → `organism:events {kind=heartbeat, source=vercel.<subdomain>, payload={page, ua}}`.
- Rate limit: 1 per minute per session (avoid abuse).

### 6.2 Step W4.2 — Frontend beacon JS

- `apps/mouth/src/lib/innervation-beacon.ts` (NUOVO, ~30 LOC) — sendBeacon API on page load.
- Wire in `(workspace)/layout.tsx`, `(blog)/layout.tsx`, `(book)/layout.tsx`.
- Per-subdomain identification via `window.location.hostname`.

### 6.3 Step W4.3 — Genoma 8 frontend entries

- Add 8 entries `vercel.kita`, `vercel.my`, `vercel.prime`, `vercel.mail`, `vercel.calendar`, `vercel.drive`, `vercel.knowledge`, `vercel.zantara`.
- expected_hb_seconds: 1800 (30min, page load is sporadic).
- recovery_action: `human_only` (Vercel rollback is manual).

### 6.4 Step W4.4 — Vercel preview verification

- Deploy preview branch, browse 8 subdomain via `mcp__claude-in-chrome__*`, verify JSONL contains 8 heartbeat entries within 1min of page load.

---

## 7. Wave 5 (FASE 4) — Chaos test su Pro reale

Dettagli in `10_chaos_test_results.md` (FASE 4 doc, NOT this doc).

**Pre-condizioni**:
- W0+W1+W2+W3 merged + deploy + verified.
- W4 in Vercel preview only (no production beacon yet).
- Telegram alert pre-armato (Q3-A guardrail #1).
- Rollback button ready: `fly machine start <id> --app nuzantara-rag` con ID copied.

**Ordine 5 test**:
1. Stop drive_poll cron Air (non-distruttivo) → 5min observation.
2. Kill claude-max-usage-watcher Pro (non-distruttivo) → 60min observation? (No — test the *detection* in shorter window using a manual `expected_hb_seconds=300` override for test).
3. Kill Cell process (medium) → 90s ABORT criteria.
4. Kill Organism Supervisor (high) → 60s detection target.
5. Kill nuzantara-rag api machine (full prod) → 60s recovery target.

**Documentazione live**: per ogni test, riga in `10_chaos_test_results.md` con timestamp, action, recovery time observed, verdict.

---

## 8. Output FASE 2 finale

✅ Protocol decided (07).
✅ Failure isolation analyzed (08).
✅ Migration plan ordered (09 — questo).

→ FASE 3 implementation può partire. Wave 0 sequenziale prima di tutto.

---

## 9. Time estimate totale

| Fase | Effort | Wall-clock |
|---|---|---|
| FASE 1 (audit + dispatch) | ~3h orchestrator | DONE |
| FASE 2 (design 07/08/09) | ~2h orchestrator | DONE |
| FASE 3 Wave 0 | ~2h sequenziale | TBD |
| FASE 3 Wave 1 | ~3h (2 subagent paralleli) | TBD |
| FASE 3 Wave 2 | ~3h sequenziale (Air SSH) | TBD |
| FASE 3 Wave 3 | ~4h sequenziale (7 channel + 3 MCP, deploy Fly per-PR) | TBD |
| FASE 3 Wave 4 | ~2h parallel preview | TBD |
| FASE 4 chaos test | ~1.5h sequenziale | TBD |
| **Totale** | **~21-22h** | spread over multiple sessions |

Spread realistico: 2-3 giorni di sessioni Opus + Sonnet (Sonnet 4.6 medium effort per Wave 1-4 implementation, Opus per chaos test + final docs).
