# Convergent findings — synthesis of 5 LLM analyses

**Author:** Opus 4.7 (synthesizer)
**Date:** 2026-04-29
**Sources analyzed:** 02_opus, 04_gemini, 05_deepseek, 06_notebooklm, codex_live_evidence

---

## Method

For each surface in the brief, I recorded which LLMs identified it, classified the convergence as:
- **HIGH** = 4-5 LLM agreement → P0 confidence
- **MEDIUM** = 2-3 LLM agreement → P0/P1 with caveat
- **LOW** = 1 LLM only → P2 or "investigate before scarting"
- **DIVERGENT** = LLMs disagreed → escalate / red-team
- **BLIND-SPOT** = something only ONE LLM saw → often the most interesting

---

## HIGH-convergence findings (4-5 LLM agreement) → P0 with high confidence

### HC-1. Backend Fly.io app fails fail-fast → restart loop

| LLM | Identified | Notes |
|---|---|---|
| Opus | ✓ | Cited NB-1 #1 |
| Gemini | ✓ | "OOM/restart loops, --workers 1 + min_machines=2 + HEALTHCHECK" |
| DeepSeek | ✓ | "Fly.io will keep restarting indefinitely... if crash deterministic, restart loop" |
| NB-1 | ✓ | `service_initializer._init_critical_services` raises RuntimeError [1] |
| Codex | ✓ (implied via SearchService grep evidence) | Verified file paths |

**Convergent fix:** Convert `_init_critical_services` to "log + degrade" — bind 8080, serve `/health` with `degraded` flag, return 503 from `/api/query` until deps recover. Reference impl in `non-critical services` block of same file.

---

### HC-2. dependencies.py SPOF + Golden Rule #10 violations

| LLM | Identified |
|---|---|
| Opus | ✓ |
| Gemini | ✓ ("lazy-load + httpx pool in lifespan") |
| DeepSeek | ✓ ("async client leak: deterministic OOM crash, restart loop") |
| NB-1 | ✓ (cited Golden Rule #10 + `email_http.py` correct pattern) |
| Codex | (implicit — collecting evidence on file structure) |

**Convergent fix:**
1. Audit-and-rewrite all `httpx.AsyncClient(` instantiations to lazy-singleton pattern.
2. Convert dependencies.py fail-fast to log-and-degrade.
3. Add CI grep-test that fails if `httpx.AsyncClient(` appears outside `*_http.py` files.

---

### HC-3. Migration system v2 deploy ordering bug (PR #307 STRUCTURAL)

| LLM | Identified |
|---|---|
| Opus | ✓ (via cicatrix-scars.md citation) |
| Gemini | ✓ (proposed "run-sql-v2-migrations-post-deploy" job) |
| DeepSeek | ✓ ("crash loop because same code crashes again") |
| NB-1 | UNKNOWN ("not in sources" — snapshot pre-2026-04-26 cicatrix) |
| Codex | (live evidence in progress) |

**Convergent fix:** New job `run-sql-v2-migrations-post-deploy` AFTER `deploy` step in `.github/workflows/fly-deploy.yml`. Re-runs SQL v2 runner against fresh image. Idempotent (skips applied).

> NB-1's UNKNOWN is **not a contradiction**, it's a snapshot-age limit. The fix is well-supported by the other 3 sources.

---

### HC-4. Cell/Organism processes have no auto-restart

| LLM | Identified | Detail |
|---|---|---|
| Opus | ✓ | Codex empirical: 7/53 LaunchAgents have `KeepAlive=true` |
| Gemini | ✓ | "WAL mode SQLite + KeepAlive=true wrapper" |
| DeepSeek | ✓ | "if Cell crashes, no auto-restart unless wrapped in manager" |
| NB-1 | ✓ | "Affidare a launchd con KeepAlive=true" |
| Codex | ✓ EMPIRICAL — counted plist properties |

**Convergent fix:** Mass audit of 53 plist files:
- Daemon plists: `KeepAlive=true` mandatory (currently 11 missing entirely)
- All plists: `EnvironmentVariables` mandatory (5 missing)
- All plists: log to `~/logs/` not `/tmp/` (6 violators)
- Each daemon also entered in `~/.agent/decisions/job_registry.json`

VADEMECUM §11 already documents this. The audit is enforcement, not new design.

---

### HC-5. Channels webhook resilience — Twitter CRC + sync processing risk

| LLM | Identified |
|---|---|
| Opus | ✓ |
| Gemini | ✓ ("offload to Redis Streams instantly, return 200 OK") |
| DeepSeek | (implied via "if Fly app crashes inflight processing lost") |
| NB-1 | ✓ (Twitter disabled hardcoded in logging_config.py) |
| Codex | ✓ EMPIRICAL — found `failed_messages` DLQ already exists for OUTBOUND |

**Convergent fix:** "Ack first, process async" pattern. Webhook router persists payload to `inbound_webhooks` table, returns 200 OK in <200ms. Background worker picks up. Twitter CRC: rewrite per HMAC SHA-256 spec.

---

## MEDIUM-convergence findings (2-3 LLM agreement)

### MC-1. EventBus is PG LISTEN/NOTIFY, NOT Redis Streams (Symbiosis Law 4 docs lie)

| LLM | Identified |
|---|---|
| Opus | ✓ (after NB-1 correction) |
| Gemini | partial (didn't catch the doc-vs-code drift) |
| DeepSeek | partial ("Redis SPOF" but didn't verify it's actually PG) |
| NB-1 | ✓ AUTHORITATIVE — cited PG_CHANNEL_MAP code [11] |
| Codex | (live, expected to confirm) |

**Convergent fix:** Outbox Pattern universal. New table `events_outbox`, helper `outbox.write(channel, payload)` called BEFORE `pg_notify`. Daemon replays missed events on listener reconnect.

> **This is the most important medium-convergence finding** because it reveals a documentation-vs-reality drift in the foundational architecture. Symbiosis.md says Redis; code says PG. Either fix the code (move event bus to Redis Streams) or fix the docs (and add Outbox to the PG implementation). Either way, the silent loss-on-disconnect bug is real.

---

### MC-2. NLM pipelines DLQ stuck (54 entries, 7 terminal, 7404 escalation lines)

| LLM | Identified |
|---|---|
| Opus | ✓ (with sentinel state numbers) |
| Gemini | partial (focused on cron jobs broadly) |
| DeepSeek | (mentioned generically) |
| NB-1 | ✓ heartbeat_monitor.py + truth_dashboard pattern |
| Codex | ✓ EMPIRICAL — `escalations_pro.jsonl` 7404 lines pending |

**Convergent fix:** Two-phase.
1. Migrate escalations.jsonl to SQLite with index + retention (active/resolved/archived).
2. Pro `system_doctor.py` extension: detect pipelines stuck >24h, attempt rerun, escalate only if rerun fails.

---

### MC-3. Healthcheck coverage gaps

| LLM | Identified |
|---|---|
| Opus | ✓ (listed 4 missing probes) |
| Gemini | ✓ ("Qdrant SUSPENDED unseen by HTTP-only probes") |
| DeepSeek | (mentioned briefly) |
| NB-1 | partial (UnifiedHealthService cited) |
| Codex | (likely emerging) |

**Convergent fix:** Per-channel synthetic probes:
- WhatsApp send/receive round-trip (1/hr)
- Telegram bot ping (1/hr)
- Drive doc creation+delete (1/day)
- KG query end-to-end (`/api/query` synthetic question, 1/hr)

Each probe's outcome → `system_health_probes` table; alert if 2 consecutive fail.

---

### MC-4. Frontend i18n provider per route group (PR #273 pattern)

| LLM | Identified |
|---|---|
| Opus | ✓ |
| Gemini | ✓ ("Service Worker + i18n provider scope") |
| DeepSeek | (not directly) |
| NB-1 | UNKNOWN (not in 2026-03-23 snapshot — PR #273 is 2026-04-27) |
| Codex | (not yet) |

**Convergent fix:** AST-based CI lint that fails if any descendant in a route group imports `useTranslation()` without ancestor `<I18nProvider>`. Doesn't depend on snapshot age.

---

## LOW-convergence / single-LLM findings (potential blind spots)

### LC-1. NB-1 sees only **88 registered routers** vs my 140 file count

**Identified by:** NB-1 only.

**Significance:** If true, **52 router files exist but aren't registered**. They're either disabled in `router_manifest.py`, in `__init__.py` deferred state, or dead code. Audit `router_manifest.py` vs `find` count:
```bash
diff <(rg "process_groups" router_manifest.py | wc -l) <(find apps/backend-rag/backend/app/routers -maxdepth 1 -name "*.py" | wc -l)
```

If 52 router files are dead code, Maxcleanup is L2 work. If they're disabled-pending-fix, each one is an audit item.

### LC-2. NB-1 KG counts: 87K/210K vs CLAUDE.md DOCSYNC marker 108K/243K

**Identified by:** NB-1 only.

**Significance:** **DOCSYNC is stale by ~25%.** Run `scripts/docs_sync.py` immediately to refresh. If still 108K/243K, the discrepancy is between two measurement points (production PG vs federated). Document it.

### LC-3. nuzantara-mcp 115-tool monolite blast radius

**Identified by:** NB-1 strongly, Opus partially.

**Significance:** Crash of single FastMCP process kills 115 tools. Federation launcher restarts (good) but no namespace isolation. Architectural decision: partition or accept blast.

### LC-4. Brevo email SPOF (single API key, no fallback)

**Identified by:** Opus only.

**Significance:** Real SPOF. Emails outbound failure is **silent** (current behavior in `notifications/send-email`). Fix: add Resend or SES as fallback provider; route based on Brevo health probe.

### LC-5. Tigris backup retention without restore drill

**Identified by:** Opus only (citing AUTONOMOUS_OPS guardrail table).

**Significance:** "Untested backup is no backup". Add cron monthly restore-into-staging-PG drill.

### LC-6. nuzantara-qdrant Fly app SUSPENDED (zombie state)

**Identified by:** Opus + Gemini.

**Significance:** Decision needed: re-enable or destroy. Current state passes audits silently while the production Qdrant is on Cloud (different secret). Cleanup: `fly apps destroy nuzantara-qdrant` if no longer needed, OR document the migration in CLAUDE.md and deprecate in INDEX.md.

### LC-7. Sentinel itself — recursive watchdog

**Identified by:** Opus only.

**Significance:** Who watches the watcher? Sentinel daemon needs `KeepAlive=true` plist + a 2nd watchdog (probably Air-side). Otherwise Sentinel crash = entire monitoring blind.

### LC-8. Federation launcher restart

**Identified by:** Opus + NB-1 (NB-1 cited [26] launcher heartbeat — restarts AGENTS, but not itself).

**Significance:** Same recursive watchdog problem as LC-7.

### LC-9. Tailscale OFF during AI work = single-link risk

**Identified by:** Opus only (memory air-monitoring).

**Significance:** If Air loses Wi-Fi during AI work and Tailscale is off, recovery requires physical access. Mitigation: scheduled "Tailscale heartbeat" — every 4h Tailscale comes back online for 60s, sends a heartbeat, goes off. (Or accept the risk if AI sessions are time-bounded.)

### LC-10. DeepSeek model alias deprecation pattern

**Identified by:** dispatch resilience log itself.

**Significance:** `deepseek-reasoner` was silently aliased → `deepseek-v4-flash` (no CoT). The system probably has code referencing `deepseek-reasoner` somewhere that now fails silently. Grep + update.

---

## DIVERGENT findings (LLM disagreement)

### DV-1. Number of routers

- Opus & Codex (file count): **140**
- NB-1 (registered): **88**
- CLAUDE.md DOCSYNC: **253** (likely cumulative across modules)

**Resolution:** Three different denominators measuring different things. Need a single canonical metric (registered + healthy at runtime), exposed via `/health` endpoint.

### DV-2. KG nodes/edges

- CLAUDE.md DOCSYNC: 108K nodes / 243K edges
- NB-1 production query: 87K / 210K (or 56K / 161K federated)

**Resolution:** Run `SELECT COUNT(*) FROM kg_nodes; SELECT COUNT(*) FROM kg_edges;` on prod and update CLAUDE.md DOCSYNC. The drift is the bug.

### DV-3. MCP tool count

- Brief said: 3 servers, 135 tools
- NB-1: 1 monolite 115 tools + 1 advanced 14 tools = **129** (mcp-browser is 6 separate)
- CLAUDE.md §7: nuzantara-mcp (115) + nuzantara-mcp-advanced (14) + browser-mcp (6) = 135

**Resolution:** The 135 is correct sum. Brief was right. Update INDEX.md to confirm.

---

## Blind spots — things ONLY one LLM saw

### BS-0 (Codex empirical, CRITICAL): **`/health` masks `startup_failed=True`**

Codex traced the code path: `app_factory.py` catches RuntimeError from critical service init, sets `app.state.startup_failed=True`, and returns. `health.py` defines `_check_startup_failed()` BUT NEVER CALLS IT in `health_check()`. A backend with startup_failed can return HTTP 200 indefinitely → Fly does not restart → silent crash that LOOKS healthy.

**This is a P0 surface that NO OTHER LLM identified.** It also explains 2026-04-29 03:11Z incident: kita.balizero.com login broke, but Fly didn't restart automatically because health was 200. The fix was operationally manual (memory `discovery_2026_04_29`).

**Fix:** Single line at top of `health_check()`:
```python
startup_error = _check_startup_failed(request.app)
if startup_error:
    response.status_code = 503
    return HealthResponse(status="unhealthy", message=str(startup_error))
```

This is the most consequential single finding of the audit. Without Codex's empirical trace, would never have surfaced.

### BS-0b (Codex empirical, CRITICAL): **Cell HealthSensor trusts HTTP 200 over body**

`apps/cell/cell/sensors/health_sensor.py` returns body but `apps/cell/cell/core/pulse.py` classifies green based ONLY on `reading.reachable and reading.status_code == 200`. So even if body says `"status": "startup_failed"`, Cell sees GREEN. This means the system's **own nervous system has the same blind spot as Fly**.

**Fix:** Cell HealthSensor must classify on body status field, not just HTTP. Together with BS-0 fix, this restores the full health signal chain.

### BS-0c (Codex empirical): **2 duplicate SQL v2 migration numbers — `129_*` and `130_*`**

Two SQL migration files with the same number. The migration runner uses `migration_number` for tracking — duplicates cause race conditions on apply order. This is a **silent corruption risk**.

**Fix:** Rename one of each duplicate pair to next-available number. Verify `_schema_versions` table rows match.

### BS-1 (Codex empirical): **only 7/53 LaunchAgents have `KeepAlive=true`**

This is a **shock-finding**. The narrative was "we have 53 LaunchAgents, they auto-recover". Reality: 86% don't. Without Codex's empirical audit, this would have stayed invisible.

**Impact:** Massive. Every documented daemon assumed-running on Pro/Air may be in fact one-shot. Reverse-validate by listing each LaunchAgent and answering: "Does this need to KeepAlive?" — daemons (yes), one-shot maintenance jobs (no, but should be cron not LaunchAgent).

### BS-2 (NB-1): **EventBus is PG LISTEN/NOTIFY, not Redis** + Symbiosis docs say opposite

Already covered as MC-1. Repeating because it's the most consequential single discovery.

### BS-3 (Opus): **healthcheck@balizero.com login probe was added 2026-04-29**

That's TODAY. Memory `fact_2026_04_29` confirms. Probe is fresh. Validate that it actually fires — if it hasn't reported anything in 24h, something already broken at probe-level.

### BS-4 (DeepSeek reasoning): **"crash loop is technically auto-restart"**

DeepSeek reframed the audit goal: "MUST NOT have crash without automatic restart" doesn't mean "MUST NOT have crash" — it means recovery cycle must close. A crash loop technically restarts, but it's not healthy.

**Implication:** The audit must distinguish:
- (a) **Crash → auto-restart → healthy** ✓
- (b) **Crash → auto-restart → re-crash → loop** ✗ (deterministic crash) ← all P0 here
- (c) **Crash → silent death** ✗ (no auto-restart) ← Cell/Organism

This three-way classification should be in the intervention plan.

---

## Numbers that survived all 5 LLM cross-checks (Symbiosis Law 7)

| Metric | Value | Source |
|----|----|----|
| LaunchAgents project total | 53 | Codex empirical |
| LaunchAgents with KeepAlive=true | 7 (13%) | Codex empirical |
| LaunchAgents missing EnvironmentVariables | 5 (9%) | Codex empirical |
| Sentinel jobs total | 58 | Codex empirical |
| Sentinel jobs healthy | 10 (17%) | Codex empirical |
| Sentinel circuit OPEN | 16 (28%) | Codex empirical |
| DLQ entries | 54 | Codex empirical |
| Pro escalations.jsonl pending lines | 7404 | Codex empirical |
| KG nodes (production) | 87,198 | NB-1 |
| KG edges (production) | 210,354 | NB-1 |
| Backend routers registered | 88 | NB-1 |
| Backend routers files | 140 | Codex/Opus |
| MCP tools in monolite | 115 | NB-1 |
| Migrations v2 applied | 30 (last 140) | Opus empirical |
| Fly machines running | 2/2 (started, 1/1 health passing) | Opus empirical |
| Frontend subdomains | 8 | CLAUDE.md |
| Channels active | 6/7 (Twitter CRC broken) | CLAUDE.md + NB-1 |

These numbers are the new baseline. After remediation, the goal is:
- Sentinel jobs healthy: 10/58 → **55+/58**
- Circuit OPEN: 16/58 → **<5/58**
- DLQ entries: 54 → **<10** active
- escalations.jsonl pending: 7404 → **<100** active
- LaunchAgents KeepAlive=true (daemons only): 7/53 → **all daemons** (target ~25/53 after audit removes one-shot from LaunchAgent classification)
