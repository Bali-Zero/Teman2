# Executive Summary — Audit zero-crash 2026-04-29

> **Goal:** From 2026-04-30, no Nuzantara crash without automatic recovery.
> **Author:** Opus 4.7 + 4-LLM dispatch (Codex GPT-5.5, Gemini 3.1 Pro, DeepSeek v4-pro, NotebookLM NB-1)
> **Status:** Audit complete. Implementation plan and per-P0 brainstorms ready for L2 autonomous execution.

---

## TL;DR

**The system Antonello uses every day is not healthy. It survives because Antonello restarts what breaks before it cascades.**

Sentinel reports at audit time: 10/58 jobs healthy (17%), 16/58 circuit breakers OPEN (28%), 54 DLQ entries (7 terminal), 7404 escalation lines pending. 53 LaunchAgents on Pro, only 7 (13%) configured to auto-restart. Backend `/health` endpoint can return HTTP 200 even when the app's startup_failed=True — Fly never restarts the broken machine. Cell, the organism's own nervous system, classifies health on HTTP code only — it can't see semantic body status. EventBus uses PostgreSQL LISTEN/NOTIFY (not Redis Streams as Symbiosis.md claims), and any event published during a 5-second listener disconnect is silently lost.

Five LLMs analyzed the system independently. They converged on **8 P0 surfaces** (crash without recovery TODAY) and **5 P1 surfaces** (degrade without alert). The audit also found **7 surfaces NOT in the original brief** (Brevo SPOF, Tigris untested backups, Tailscale single-link risk, Sentinel recursive watchdog, Federation launcher restart, system_doctor naming clash, Vercel monorepo cross-import lint).

**Fixes are scoped, low-risk, and L2-autonomous.** Total estimated effort: ~3-4 weeks at autonomy L2.

---

## Top 3 P0 — implement THIS WEEK

### 1. P0-0 — `/health` masks `startup_failed` (foundational, 1-2h)

`apps/backend-rag/backend/app/routers/health.py:147-266` never calls the existing `_check_startup_failed()` helper at line 48. A backend with broken critical services keeps returning HTTP 200, Fly never restarts, monitoring stays green. **Discovered by Codex empirical trace, no other LLM saw it.** This is exactly the 2026-04-29 03:11Z incident pattern (kita.balizero.com login broke, Fly didn't restart, manual intervention required).

Fix: 3 lines in `health.py` + warmup deadline in `app_factory.py` + Cell pulse classify body status. Foundation for all other fixes' visibility.

### 2. P0-2 — EventBus PG NOTIFY without Outbox = silent event loss (1-3 days)

NotebookLM NB-1 corrected my assumption: EventBus is **PostgreSQL LISTEN/NOTIFY**, not Redis Streams as Symbiosis.md says. When PG listener disconnects (5s reconnect window), events vanish — no queue. Affects: practice/client/compliance changes, war_room events, intel events, cognitive events.

Fix: Outbox Pattern. Reference impl already in `services/bridge/outbox.py`. Generalize via `services/events/outbox.py` + new migration 141 + replay-on-reconnect.

### 3. P0-3 — 53 LaunchAgents, only 7 with KeepAlive=true (3-4h)

Codex empirically counted 53 project plist on Pro. Of these:
- 7/53 (13%) have `KeepAlive=true`
- 11/53 (21%) have NO KeepAlive directive at all
- 5/53 (9%) missing `EnvironmentVariables` (VADEMECUM §11 violation)
- 6/53 (11%) logging to `/tmp/` (lost on reboot, breaks Sentinel)

Cell, Organism, NLM-bridge, post-publish-poller — all daemons that should auto-restart but don't.

Fix: Auto-patch script per VADEMECUM §11 + lint script + PreToolUse hook for regression prevention.

---

## Top 3 P1 — implement WITHIN 2 WEEKS

### 1. P1-7 — NLM pipelines DLQ stuck (54 entries, 7 terminal) — 4h

NB-1, NB-6, NB-7, NB-8 in persistent escalation state. Daily ground-truth refresh stops. Bali Zero clients receive stale answers.

Fix: `system_doctor.py` Pro extension — detect pipelines stuck >24h, attempt auto-rerun, escalate to Telegram only if rerun fails.

### 2. P1-8 — escalations.jsonl 7404 lines pending (1 day)

`shared/escalations_pro.jsonl` is append-only since inception. No retention. No reader.

Fix: Migrate to SQLite with retention cron (active/resolved/archived).

### 3. P1-10 — Frontend i18n provider per route group (4h)

PR #273 white-screen bug pattern. Any new route group adopting `useTranslation()` without `<I18nProvider>` ancestor causes throw → unmount → white screen.

Fix: AST-based CI lint that fails before deploy.

---

## Dispatch resilience log: 4/4 LLMs successfully delivered

Dispatch failed 8 times across 4 LLMs before all returned useful output. Each failure had a different root cause (bash redirect order, OAuth token expiry in MCP, sandbox+plan blocks tools, subshell env not propagated, model alias deprecation). Documented in [`07_dispatch_resilience_log.md`](07_dispatch_resilience_log.md). The pattern — every failure was silent or had a misleading first signal — is exactly what we are fixing in Nuzantara.

**Eat your own dogfood:** the audit infrastructure itself has the same fragility classes as the audited system.

---

## Files in this audit

| File | Purpose |
|------|---------|
| `00_executive_summary.md` | This file — top-level recommendations |
| `01_brief_dispatched.md` | Uniform brief sent to all 4 LLMs |
| `02_opus_analysis.md` | Opus 4.7 independent analysis (24KB) |
| `03_codex_analysis.md` | Codex GPT-5.5 empirical audit (62KB, with file paths + line numbers) |
| `04_gemini_analysis.md` | Gemini 3.1 Pro structured analysis (15KB) |
| `05_deepseek_analysis.md` | DeepSeek v4-pro deep reasoning chain (35KB, 7271 reasoning tokens) |
| `06_notebooklm_analysis.md` | NotebookLM NB-1 ground-truth corrections (12KB, 39 citations) |
| `07_dispatch_resilience_log.md` | Failures + root causes during dispatch (11KB) |
| `08_convergent_findings.md` | 5-LLM convergence/divergence/blind-spots synthesis (14KB) |
| `09_intervention_plan.md` | Per-fix detailed intervention plan with verify+rollback (35KB) |
| `10_cell_genoma_alignment.md` | Touchpoint matrix Cell/Genoma per fix (8KB) |
| `11_brainstorms/` | Per-P0 implementation strategy (8 files, ~40KB total) |

---

## Numbers that survived 5-LLM cross-check (Symbiosis Law 7 — numeri prima)

These baselines should be remembered and re-measured after every wave of fixes:

| Metric | At audit time | Target after Week 1 fixes |
|---|---|---|
| Sentinel jobs healthy | 10/58 (17%) | >50/58 (>86%) |
| Circuit breakers OPEN | 16/58 (28%) | <5/58 (<9%) |
| DLQ entries | 54 | <10 |
| Escalations.jsonl pending | 7404 | <100 active (after SQLite migration) |
| LaunchAgents KeepAlive=true (daemons only) | 7/53 | all daemons (~25/53 after classification) |
| Backend /health returns 503 on startup_failed | NO | YES |
| Cell pulse classifies semantic health | NO | YES |
| SQL v2 migrations apply on fresh image | NO (manual workaround) | YES |
| EventBus durable on PG disconnect | NO (events lost) | YES (Outbox replay) |

---

## Decisions for Zero (escalation needed)

These items reach beyond L2 autonomy and need Antonello's input:

1. **MCP partition** (P1-9): split 115-tool monolite into 3 specialized servers. Architectural change. Effort 2-3 days. Decision: yes/no?
2. **Cell standby on Air** (Section "Cell crisis path" in 10_cell_genoma_alignment.md): should Air run a "Cell Lite" that takes over if Pro Cell silent >1h? Currently Air doesn't run Cell. Decision: yes/no?
3. **Symbiosis Law 4 docs vs code**: docs say "Redis Streams", code uses PG LISTEN/NOTIFY. Two paths: (a) update docs to match code + add Outbox (P0-2), (b) migrate code to Redis Streams (1-2 weeks). Decision: keep PG (recommended) or migrate?
4. **nuzantara-qdrant Fly app SUSPENDED**: zombie state. Re-enable or destroy?
5. **Brevo email SPOF** (NB-E): add Resend or SES as fallback provider. Requires creating second-provider account. Decision: yes/no on second provider, and which?

These are flagged in `09_intervention_plan.md` as "L2 autonomy NO" or "Zero handoff first" markers.

---

## Recommended implementation roadmap

**Week 1:**
- Day 1: P0-0 + P0-7 + P0-4 (3.5h total)
- Day 2-3: P0-1 + P0-3 (4h)
- Day 4-5: Start P0-2 (Outbox migration + helper)

**Week 2:**
- Continue P0-2 (callsite refactor + tests)
- P0-6 (channels ack-first + Twitter CRC)

**Week 3:**
- P0-5 (httpx audit, mass conversion)
- P1-7, P1-8, P1-10, P1-11 (4h each = ~2 days)

**Week 4+:**
- P1-9 architectural (Zero handoff)
- P2-12..15 + NB-A..G (cleanup)

After Week 4, re-run this audit. Sentinel jobs healthy should be >85%, circuit OPEN <10%, DLQ <10. The system should be at "Antonello can take a 2-week vacation without the system needing him" baseline.

---

## Open invitation

This audit is **read-only**. No code or config changed. The implementation begins in subsequent sessions under AUTONOMOUS_OPS L2.

Per memory `feedback_dispatch_carousel_method` and the user's preference for proposals before action, each P0 fix can be:
- Implemented end-to-end in single L2 session (recommended for P0-0, P0-3, P0-4, P0-7)
- Implemented in phases with PR review checkpoints (recommended for P0-2, P0-5, P0-6)
- Brainstormed further before implementation if the strategy options need debate (P0-1)

The brainstorms in `11_brainstorms/` are starting points, not commitments. Each can be revisited.

**Start with P0-0.** Without it, every other fix is invisible.
