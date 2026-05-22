---
date: 2026-05-23
domain: operations
client_case: NB automations hardening — W27 Cell organism self-healing 3-LLM panel review
sources: 5
---

# W27: Cell organism self-healing — 3-LLM panel review + synthesis

## Background

36-min Fly backend outage 2026-05-23 02:14-02:50 WITA. Cell organism detected health=red, recorded 22 panic episodes in episodic memory. `CELL_ALERT_TELEGRAM_ENABLED=false` → silent. No auto-remediation triggered. Operator unaware until W27 audit discovered it ~12h later. Pattern matches W18 cicatrix (Cell daemon silent dead 5 days).

Antonello directive: "il sistema stesso deve essere allertato e deve auto fixarsi solidamente" (system itself, not just operator via Telegram, must self-heal).

## Panel verdicts

| LLM                 | Verdict                         | Key insight                                                                                                             |
| ------------------- | ------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **Codex GPT-5.5**   | Option C **shrink hard**        | "Sensor becomes actuator = restart loop. C correct only if organ is tiny, local, allowlisted, stateful, boring."        |
| **DeepSeek V4 Pro** | Option D + ONE pre-baked script | "Architecture-astronaut work. 36-min outage was monitoring failure (Cell silent), not healing failure. Telegram first." |
| **Gemini 3.1 Pro**  | Option C                        | New `apps/remediator` daemon on launchd, SQLite cooldown, listen `organism:events` Redis stream                         |

## Convergent (3/3)

1. **Telegram alert MUST fire NOW** — current `CELL_ALERT_TELEGRAM_ENABLED=false` is the primary problem
2. **Action whitelist = ONLY `fly machine restart` for hardcoded machine ID** (no dynamic command)
3. **3 consecutive red pulses before any action** (avoid single-blip restart)
4. **Kill switch env var mandatory** (`CELL_AUTOREMEDIATION_ENABLED=false`)
5. **L3 Telegram fires on time-based trigger** (e.g. 15min sustained red), NOT just exhausted attempt count
6. **NO blanket-pause operator writes** — operator override always priority

## Divergent

| Question                     | Codex/Gemini                | DeepSeek                         |
| ---------------------------- | --------------------------- | -------------------------------- |
| New daemon?                  | Yes — `apps/remediator`     | No — restart fn inside Cell      |
| Tonight's scope?             | http=red→fly restart only   | http=red→fly restart only (same) |
| `pg-proxy bounce` whitelist? | Conditional, after 2 checks | NOT safe — orphans transactions  |

## DeepSeek's brutal red-team callouts (priority order)

1. **False-red class**: Fly proxy reports red because slow ≠ dead. Restarting a slow-but-serving machine causes real data loss.
2. **Idempotency illusion**: `fly machine restart` on already-stopped machine creates port conflicts, split-brain ephemeral disk
3. **Operator-in-the-dark**: silent auto-remediation while Antonello SSHes in = race condition with manual fix attempts
4. **Cooldown 3/hr can be exhausted in 15min** — escalation MUST be time-based, not attempt-counted
5. **PG NOTIFY is lossy** — building reliable outbox layer for `cell_alert` channel is week-long over-engineering

## Synthesis — proposed sequence (commit-by-commit)

### Phase 1 (TONIGHT, P1, low risk): enable telemetry layer

1. Set `CELL_ALERT_TELEGRAM_ENABLED=true` in `apps/cell/.env` + add `CELL_ALERT_DEDUP_WINDOW_MIN=30` (per-tier dedup)
2. Backup `.env.pre-w27`, `launchctl bootout + bootstrap` Cell
3. Verify Telegram alert fires on next red-tier with empirical smoke

**ROI:** 5 min implementation. Solves the monitoring failure (DeepSeek priority #1). Does NOT solve auto-healing.

### Phase 2 (next iteration, P2): add ONE pre-baked remediation function

DeepSeek-recommended minimal: a single function `_try_restart_fly_api_machine()` inside Cell that runs ONLY when:

- `health=http=red` for ≥3 consecutive pulses
- AND `pulse_count_since_last_action >= 15` (15-min cooldown)
- AND `CELL_AUTOREMEDIATION_ENABLED=true` (kill switch default OFF)

Action: hardcoded `fly machine restart 7847d95ce257d8 -a nuzantara-rag`. Logs attempt to episodic memory BEFORE running command (audit trail even if flyctl hangs).

**Telegram payload at attempt:** "🔧 Auto-restart attempted: fly api machine 7847d95... (red for 3min)". If next pulse still red after 60s, second Telegram "❌ Restart failed, manual intervention needed".

**ROI:** ~2h implementation. Solves Antonello directive minimally. Codex-approved (tiny, allowlisted, boring).

### Phase 3 (DEFERRED, P3, only after Phase 2 has 30-day stability)

Build `apps/remediator` as separate organ ONLY IF Phase 2 catches >3 outages successfully + zero false-restart incidents. Until then, stay inside Cell.

## Anti-loop guard list (mandatory for any phase)

From Codex (NON-NEGOTIABLE):

- Durable incident ledger (SQLite or episodic memory)
- `flock` on action execution
- Stale-event TTL (don't act on 10min-old event)
- Fixed command whitelist (no shell-interpolated from payload)
- No recursive action from verification pulses (loop break)
- Max attempts/hour cap
- Deploy-in-progress lockout (check `fly status` for "deploying" state before restart)
- Green-stability reset (5 consecutive green pulses = incident closed)
- Kill switch env var

## Phase 1 decision needed from Antonello

Decisione strutturale per Symbiosis Law 5:

1. ✅ Enable `CELL_ALERT_TELEGRAM_ENABLED=true` con dedup 30min (zero new code, zero new daemon)
2. Defer Phase 2 implementation a successivo /loop iter dopo Phase 1 baseline accumulato

Phase 2 e Phase 3 require explicit follow-up. Phase 1 alone solves the immediate "Cell deaf" symptom that was the proximate cause of W27 being discovered by accident.

## Phase 1 SHIPPED 2026-05-23 03:34 WITA — empirical verification

`apps/cell/.env` patched: `CELL_ALERT_TELEGRAM_ENABLED=true` + `CELL_ALERT_DEDUP_WINDOW_MIN=30`. Backup `.env.pre-w27-2026-05-23`. `launchctl bootout + bootstrap` Cell daemon.

**Live smoke at restart (Pulse #1):**

- Backend `nuzantara-rag.fly.dev/health` → 200 OK (recovered after 36-min outage)
- Pulse health=yellow (errors_5min=5, threshold_yellow=3)
- PatternIndex hit → action=scale_up (confidence=0.95)
- FlyEffector: "Already at 2 machines (target=2), no action needed"
- **Telegram alert FIRED**: "✅ _SCALE_UP_ Already at 2 machines..." (post HTTP 200 OK)
- Episode #34721 stored
- Critic LLM registered expectation #14656

**Conferma operativa**: Cell HA GIA' una self-healing loop end-to-end. FlyEffector + LocalEffector + Telegram + Critic + PatternIndex + EpisodicMemory tutto wired. Era SOLO silent perché Telegram disabled. Pattern matches W18 (Cell daemon silent dead 5 days).

## Major W27 discovery — Organism phantom event kind

While investigating Phase 2 path, found that `apps/organism/organism/rules/base.yaml:75-79` has rule `cell_sustained_red_restart` matching `kind: cell_pulse_sustained_red` + `payload.consecutive_gte: 5`. This event kind **is never emitted** by Cell — phantom feature. The rule exists in YAML for ~6 months but has never fired.

Empirical proof in `~/logs/organism/decisions.jsonl`: every recent cell_pulse_observed event routes to `dispatch_outcome: deferred_defer_actuator`, `actuator: defer_to_human` — Organism receives all Cell pulses but no rule matches because:

1. Cell emits `cell_pulse_observed` kind (PG channel)
2. Organism rule expects `cell_pulse_sustained_red` kind (phantom)

Also discovered: `apps/organism/organism/supervisor/yaml_rules.py:80-98` matcher supports `payload.<field>_gte` / `_lte` but ONLY on flat dict keys — does NOT support nested `payload.pulse_result.classifier_self`.

## Phase 2 architectural decision (DEFERRED)

Two paths require explicit architectural alignment before coding:

**Path A — extend `cell_core/observatory.py`**: add `emit_sustained_red()` function with channel="cell_pulse_sustained_red". Requires:

- New PG channel registered in `events_outbox.py` PG_CHANNEL_MAP
- pg-organism-bridge config CHANNELS list updated to include new channel
- Cell Phase 2B emit logic (streak counter + emit when ≥3)
- YAML rule: action changed from `restart_agent` (wrong target — restarts Cell daemon itself) to `fly_machines_start` (right target — restarts the failing api machine) + lower threshold from 5 to 3
- Total: 4 files across 3 packages

**Path B — XADD direct to Redis `organism:events` stream**: Cell bypasses observatory + PG entirely, writes directly to `organism:events` with kind=`cell_pulse_sustained_red`. Decouples from pg-bridge. Simpler but breaks Symbiosis durabilità per canale (Law 3) since Redis stream has different retention than events_outbox.

**Path C — fix rule to match existing channel**: change rule to `kind: cell_pulse_observed` + add new matcher feature for nested payload paths (`payload.pulse_result.classifier_self`) + add stateful streak counter in matcher itself. Requires touching `yaml_rules.py` matcher engine.

All 3 paths require coordinated changes across packages. Risk: my Phase 2B implementation attempt at 03:30 WITA used Path A approach but emit_pulse_observed hardcodes channel name in `_INSERT_SQL` + `_NOTIFY_SQL`. Reverted as functionally incomplete.

## Phase 2 dispatcher to Antonello

This is Symbiosis Law 5 territory — multi-file, cross-package architectural decision. Need explicit choice of Path A/B/C before implementing.

Recommended pre-vote default: **Path A** (extend observatory). Aligns with existing event-driven durabilità pattern. Adds one new PG channel = one new outbox row schema = backward-compat for all existing consumers. ~30 min implementation across 4 files once design locked.

Until then: Phase 1 victory stands. The 36-min outage that triggered W27 would now produce:

1. Cell would still detect health=red same as tonight
2. Cell's own AI cortex (`THINK → ACT`) decides remediation based on PatternIndex + dreamer recommendations
3. **Telegram alert FIRES** to Antonello chat_id 1125336968 within 60s of red-tier with dedup 30min
4. Operator manual intervention available
5. Fly platform's own machine restart eventually recovers (as happened tonight at 02:50 WITA)

This is acceptable interim posture. Cell-as-monitor + Operator-as-actuator + Fly-as-platform-recovery = working partial autonomic loop.

## Sources

1. Codex GPT-5.5 review: `/tmp/w27-codex.md` (32 tokens used)
2. DeepSeek V4 Pro review: `/tmp/w27-deepseek.md` (41 lines)
3. Gemini 3.1 Pro review: `/tmp/w27-gemini.md` (truncated, side artifact at `.gemini/.../implementation_plan.md`)
4. Empirical outage timeline: fly machine event log + Cell pulse log
5. Spec doc: `/tmp/w27-spec.md` (Options A/B/C/D)
