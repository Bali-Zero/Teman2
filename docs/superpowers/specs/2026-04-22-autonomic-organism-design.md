# Nuzantara Autonomic Organism — Design

**Date**: 2026-04-22
**Author**: Claude Opus 4.7 (1M context) + Antonello Siano
**Status**: Design approved, awaiting implementation plan
**Red-team validators**: Gemini 3.1 Pro, DeepSeek Reasoner, Claude Sonnet 4.6 (3 convergent)

## 1. Vision

A software "organism" living on the Nuzantara codebase 24/7, executing four P1 capabilities autonomously:

1. **Auto-repair** (<5min detection + action + notify) — when a guardian/cron/deploy fails, the organism detects, correlates, decides, repairs or isolates, notifies Telegram. No more silent-failure hours like core-guardian on 2026-04-18.

2. **Auto-expansion on new code** — when `apps/foo/` is born with maturity signals (pyproject/package.json + README + non-WIP branch + >24h age + no `.organism_ignore`), the organism adopts it in a **probationary 7d** regime (heartbeat-only), then escalates to full-watch (guardian, lint, test wiring, pre-commit, heartbeat, dashboard entry).

3. **Auto-cleanup** — log rotation >30d, cache eviction, `[gone]` branch cleanup, zombie plist/script removal, consolidation of 7 redundancies already mapped in audit 2026-04-19, dead-code detection via `vulture` fed to Guardian V5.

4. **Auto-robustness** — Guardian V5 Learn proposes new rules → Consiglio v1 deliberates (3/4 votes required) → YAML rule added via auto-opened PR by the Supervisor (L2 auto-merge if CI green). Feedback loop Learn → YAML reduces LLM calls over time.

**Cardinal principle**: the organism **augments**, does not **prerequisite**. Every guardian keeps an autonomous fallback (`local_emergency_mode`) if the Supervisor is down >5min. Introducing the organism MUST NOT create a SPOF worse than the 8 broken guardians of today.

**Explicit non-goals** (YAGNI):
- Replacing the 35 existing guardians. The organism is a **layer above**, not a rewrite.
- "Smart" decisions for every event. 85% goes through hardcoded YAML; Claude CLI is last resort.
- Multi-cloud orchestration, dynamic scaling, complex canary deploys. Nuzantara is 2 machines + Fly.io — overkill is death.

## 2. Architecture

```
┌─────────────────── Guardian Layer (existing, emit events) ───────────────────┐
│  system_doctor · log_anomaly · zombie_hunter · core_guardian · drive_watchdog │
│  cron_guardian · seo_guardian_cell · fly_watcher · guardian_v5_learn · ...    │
│         ↓ emit_event(severity, source, kind, payload, correlation_id)          │
└───────────────────────────────────────────────────────────────────────────────┘
                                        ↓
┌─────────────────── Event Bus (Redis stream: organism:events) ─────────────────┐
│  • consumer group: organism-supervisor                                         │
│  • double-write JSONL mirror /var/log/organism/events.jsonl (Redis-down safe) │
│  • Redis replica Pro→Air (read-only, Sentinel quorum=2, no auto-failover)    │
└───────────────────────────────────────────────────────────────────────────────┘
                                        ↓
┌─────────────────── Supervisor (stateless daemon, launchd on Pro) ─────────────┐
│  1. consume events from stream                                                 │
│  2. hydrate IncidentContext from Redis (TTL 10min, key=correlation_id)        │
│  3. DECIDE via 3-tier:                                                         │
│     L0: YAML rules (0ms, ~85%)                                                 │
│     L1: Ollama classifier qwen3.5:9b async (pre-processing, never blocking)   │
│     L2: Claude CLI (last resort, max 3/min, cache 10min per key)              │
│     L3: Consiglio v1 (irreversible decisions only, 3/4 votes)                 │
│  4. check Circuit Breaker (target cooldown 15min, max 2 tries)                │
│  5. check mutex lock:remediation:<target> (TTL 5min)                          │
│  6. check blackout flag (~/tmp/organism-pause.flag)                           │
│  7. dispatch Actuator (asyncio.subprocess), write audit trail                 │
│  8. write IncidentContext back to Redis + JSONL backup                         │
└───────────────────────────────────────────────────────────────────────────────┘
                                        ↓
┌─────────────────── Actuator Layer (idempotent micro-processes) ───────────────┐
│  restart-agent · rollback-deploy · cleanup-log · adopt-module · patch-lint    │
│  notify-telegram · consolidate-redundancy · propose-yaml-rule · quarantine    │
│  ── each 50-150 LOC, dry-run flag, WAL local pre-execute, emit done event ── │
└───────────────────────────────────────────────────────────────────────────────┘
                                        ↓
┌────────────── Audit & Observability (organism:audit stream + dashboard) ──────┐
│  • HTTP :1819 /health /stats /pause /resume (filesystem token auth)           │
│  • metrics → Prometheus → existing Telegram notifier                          │
│  • JSONL backup persistent for replay + post-mortem                           │
└───────────────────────────────────────────────────────────────────────────────┘
```

### Components

**1. Event Bus** — Redis stream `organism:events` + local JSONL mirror.

Event schema:
```json
{
  "ts": "2026-04-22T10:30:00Z",
  "severity": "critical|error|warning|info",
  "source": "guardian.system_doctor",
  "kind": "cron_agent_failure|disk_fill|deploy_rollback|new_module",
  "payload": {"sanitized": "structured_only"},
  "correlation_id": "uuid4",
  "is_actuation": false,
  "host": "Pro|Air"
}
```

**2. Supervisor** — single Python daemon, **stateless by design**: all state lives on Redis (IncidentContext TTL 10min, keys per entity). Restart-safe by construction. Launchd on Pro, manual fallback on Air.

**3. Actuator** — folder `apps/organism/actuators/*.py`, one per action, ~100 LOC each. Contract:
- `--dry-run` mandatory
- Idempotent (calling twice = calling once)
- WAL local pre-execute (`/var/log/organism/wal/<actuator>-<uuid>.json`)
- Emits `organism:events` with `is_actuation=true` on completion (success/failure)

**4. Safety layer** (distributed, not a single module):
- Circuit Breaker (15min/target cooldown)
- Distributed Mutex (Redis lock TTL 5min)
- Blackout flag (file + HTTP endpoint)
- "Always human" whitelist hardcoded in code (not YAML)
- `local_emergency_mode` fallback for every guardian (if Supervisor down >5min)

### Design choices vs rejected alternatives

| Choice | Rejected alternative | Why |
|---|---|---|
| Custom stateless Python Supervisor | LangGraph (Gemini suggested) | LangGraph adds heavy dependency for a loop that's 200 LOC in Python; Redis reuse is more honest. LangGraph returns useful for Phase 4 auto-expansion (adoption workflow). |
| Redis Sentinel quorum=2 (fail-close) | Sentinel quorum=1 auto-failover | 2-node Sentinel creates split-brain. Quorum=2 disables auto-failover — the only thing worse than Redis down is Redis in split-brain during a rollback. |
| Ollama qwen3.5:9b as async pre-classifier | Ollama in critical path | 30-120s latency unacceptable for MTTD <90s; stays async to enrich Claude CLI context. |
| Cooldown hardcoded in CODE | Cooldown in YAML | A loop could modify YAML to bypass itself. Code = runtime-immutable. |

## 3. Phases & Migration path (4-5 days, parallel waves)

Each wave = 1 real day, 3-4 Opus tmux sessions on isolated worktrees (as done for 2026-04-22 wave 1/2). Each session produces 1 independent PR, L2 auto-merge when CI green.

### Wave 0 — Foundations (day 1, sequential)

Single Opus session, ~4h. Single branch `feat/organism-foundations`.

- **PR-W0.1** — `emit_event()` helper Python + Redis stream `organism:events` + JSON schema validator + local JSONL mirror. 150 LOC + 15 tests.
- **PR-W0.2** — Wire `emit_event()` in `system_doctor.py` / `log_anomaly_detector.py` / `zombie_hunter.py` (fixes the 3 blind spots from audit 2026-04-19 by construction: they now always emit).
- **PR-W0.3** — Guardian `local_emergency_mode`: Supervisor heartbeat check + fallback to pre-organism autonomous behavior if consumer group lag >5min. MANDATORY before touching any other guardian.
- **PR-W0.4** — Blackout flag (`~/tmp/organism-pause.flag`) + HTTP `:1819 /pause /resume /health` with filesystem-token auth. Zero LLM, zero Actuator. Control panel only.

**Checkpoint W0**: 4 PRs merged, 3 guardians emit events, local fallback ready, control panel active. The organism exists but is "brainless" — perfect for testing the bus without risk.

### Wave 1 — Supervisor skeleton + base Actuators (day 2, 3 parallel sessions)

- **PR-W1.A** — `apps/organism/supervisor/` stateless daemon: consume stream, hydrate IncidentContext from Redis, L0 YAML rule matcher, audit trail writer. NO LLM calls, NO Actuator dispatch (shadow mode: logs "would dispatch X"). ~600 LOC + 30 tests.
- **PR-W1.B** — `apps/organism/actuators/` base: `restart-agent`, `cleanup-log`, `notify-telegram`. 3 idempotent actuators with mandatory `--dry-run`, local WAL, emit done event. ~300 LOC + 20 tests.
- **PR-W1.C** — Safety primitives: Circuit Breaker (Redis key `cb:target:<id>`), Distributed Mutex (`lock:remediation:<target>` TTL 5min), Actuator self-loop guard (flag `is_actuation=true` ignored by L0 rules). ~200 LOC + 15 tests.

**Checkpoint W1**: Supervisor runs in **shadow mode** on Pro (launchd). Reads real events, decides, LOGS decisions, does NOT act. Observed for 24h before Wave 2.

### Wave 2 — LLM brain + Consiglio (day 3, 3 parallel sessions)

- **PR-W2.A** — L2 Claude CLI integration: `invoke_claude(template, slots)` with structured templates (never free-form payload), hardcoded rate limit 3/min, Redis decision cache `decision_cache:<hash>` TTL 10min, fallback to "defer to human" on quota/timeout. ~250 LOC + 20 tests.
- **PR-W2.B** — L1 Ollama async classifier: `qwen3.5:9b` classifies new burst into buckets ("hardware", "deploy", "dependency"), result written to IncidentContext to enrich L2 prompt. 150 LOC + 10 tests.
- **PR-W2.C** — L3 Consiglio v1 integration for **irreversible decisions only** (main rollback, propose YAML rule auto-merge). 3/4 votes required, else human escalation via Telegram. Reuses existing Consiglio v1 live since 2026-04-16. ~100 LOC wire + 10 tests.

**Checkpoint W2**: Supervisor moves from shadow → **active mode** for **safe Actuators only** (restart-agent, cleanup-log, notify-telegram). 48h observation before Wave 3. Public metrics on `:1819 /stats`.

### Wave 3 — Auto-expansion + Auto-cleanup (day 4, 3 parallel sessions)

- **PR-W3.A** — Actuator `adopt-module`: triggered via git post-commit hook on merge to `main`, check maturity signals (pyproject/package.json + README + non-WIP branch + >24h + no `.organism_ignore`), probationary 7d regime (heartbeat-only), then full-watch. ~250 LOC + 20 tests.
- **PR-W3.B** — Actuator `cleanup-*` suite: log rotation >30d, cache eviction, branch-gone removal, zombie plist detection + removal (reuses `commit-commands:clean_gone`), dead code `vulture` scan as Guardian input. ~200 LOC + 15 tests.
- **PR-W3.C** — Actuator `consolidate-redundancy`: executes the 7 merges already mapped in audit 2026-04-19 (heartbeat consolidation, compliance pipeline, nb-batch already done). Idempotent, each merge = 1 autonomous PR. ~150 LOC + 10 tests.

**Checkpoint W3**: 10 total Actuators active. The organism now cleans, consolidates, adopts new modules.

### Wave 4 — Auto-robustness + Gauntlet test (day 5, 2 parallel sessions + QA)

- **PR-W4.A** — Actuator `propose-yaml-rule`: when Guardian V5 Learn generates a candidate rule → Supervisor calls Consiglio v1 → if 3/4 OK → opens auto PR with new rule + test + changelog entry. L2 auto-merge if CI green. Feedback loop Learn → YAML → fewer LLM calls next time. ~200 LOC + 15 tests.
- **PR-W4.B** — Gauntlet test suite: 10 intentional kill scenarios (8 from red-team + 2 custom). Manually executed on isolated Pro+Air staging. Success criterion: all 10 pass <15min without human intervention, complete audit trail.

### Gauntlet scenarios (final, 10)

1. Break guardian (`system_doctor` intentional crash)
2. Corrupt crontab (inject invalid line)
3. Intentional deploy bug (push broken code to main)
4. Disk fill 90% (/data volume)
5. Push broken code (tsc error)
6. **Redis down 5min** (during rollback in progress)
7. **Pro-Air network partition** (pf block, simulates mDNS offline)
8. **Clock skew Air +5min** (ntpd off + date set)
9. **Claude CLI rate-limit** (simulated quota exhaust)
10. **Poison pill event** (malformed/infinite payload in stream)

### Migration order (from convergent red-team)

1. **`log_anomaly_detector`** (ideal canary: passive, already logs, failure = known silence)
2. **`zombie_hunter`** (emit-only for 2 weeks before dispatch)
3. **`system_doctor`** (has inline repair logic → replace with emit event + external Actuator)
4. **`guardian_v5_learn`** (last: rule generator, errors propagate)
5. **NOT in wave 1-4**: guardians touching direct DB (`drive_watchdog` DB ops), OAuth auth (`drive_token_watchdog`)

## 4. Safety rail, KPI, rollback

### Safety rail (layered defense)

**Layer 1 — Event sanitization** (prompt injection prevention)
- Every event payload passes through `sanitize_payload()`: strip shell metacharacters, max 2KB, mandatory JSON-escape, never raw log content
- Claude CLI receives ONLY structured templates with typed slots: `{action: "restart_guardian", guardian_id: X, failure_count: N}` — never free-form
- DENY list hardcoded in code: if payload contains patterns like `IGNORE PREVIOUS`, `</system>`, `rm -rf`, immediate quarantine + Telegram

**Layer 2 — Action whitelist/blacklist** (hardcoded in code, not YAML)
- Whitelist auto-dispatch: `restart-agent`, `cleanup-log`, `notify-telegram`, `adopt-module`, `quarantine`, `propose-yaml-rule`, `consolidate-redundancy`, `patch-lint`
- "ALWAYS HUMAN" (hardcoded blacklist): `restart-supervisor`, `rollback-deploy` on main, `drop-table`, `revoke-credential`, `fly ssh exec`, any Actuator with `--force` or `--irreversible`
- For blacklisted actions: Telegram notify + explicit wait via `/resume?action_id=X` on HTTP endpoint

**Layer 3 — Circuit Breaker + Mutex**
- Cooldown 15min/target, max 2 tries → QUARANTINE + escalation
- Mutex `lock:remediation:<target>` TTL 5min, drops events for locked target
- `is_actuation=true` flag ignored by rule matchers (prevents Actuator→Actuator feedback loop)

**Layer 4 — Blackout period** (DeepSeek critical insight)
- `~/tmp/organism-pause.flag` + HTTP `POST :1819/pause?minutes=30`
- Max expiration 2h (hardcoded, no `--forever`)
- During pause: events queued but no Actuator dispatch, ONLY monitor + audit
- `/resume` resumes, re-evaluates queued events with current freshness

**Layer 5 — Guardian local fallback** (Claude-red critical insight)
- Every guardian calls `supervisor_heartbeat_check()` every cycle
- If consumer group lag >5min → `local_emergency_mode`: guardian reverts to pre-organism autonomous behavior for critical actions
- When Supervisor returns online, re-emits events with `handled_locally=true` for audit (does not re-execute actions)
- **MANDATORY**: without this, the organism creates a SPOF worse than current blind guardians

**Layer 6 — Autonomous Ops L2 compliance**
- PR auto-merge only if: CI green + feature branch only + no prod DB schema touch + no CLAUDE.md Golden Rules touch
- Never `git push --force` on main (hardcoded in pre-commit)
- Never skip hooks (`--no-verify`)
- Claude OAuth MAX only via `claude` CLI shell out (Golden Rule #13 enforced in `llm/claude_oauth_client.py` — strips `ANTHROPIC_API_KEY` from env before spawn)

### KPI (7 metrics, dashboard `:1819 /stats`)

| Metric | Target | Formula | Alert threshold |
|---|---|---|---|
| MTTD (Mean Time To Detect) | <90s | `ts_event_emit - ts_failure_actual` (estimated from log) | >3min |
| MTTR (Mean Time To Repair) | <5min | `ts_action_complete - ts_event_emit` | >10min |
| Autonomy Ratio | 85/10/5 (YAML/LLM/human) | Tag on every decision in audit | LLM >30% = missing rules |
| False Positive Rate | <5% | Actions manually reversed / total | >10% |
| Circuit Breaker Trips | <3/day | Count of QUARANTINE events | >10/day = systemic issue |
| Event Bus Lag | <1s | `XLEN organism:events` pending | >100 events pending |
| Consiglio Dissent Rate | <30% | Non-unanimous 3/4 votes | >50% = rules too ambiguous |

**Weekly auto-report** (Actuator `weekly-report`, cron Sunday 08:00 WITA): posted in Telegram + committed to `docs/organism/weekly/YYYY-MM-DD.md` with dashboard link + KPI trend.

### Rollback plan

**Per-wave rollback** (from section 3 checkpoints):
- Wave 0-2: `touch ~/tmp/organism-pause.flag` = global pause <1s, guardians autonomous
- Wave 3-4: disable individual Actuator via `SADD organism:config:actuators_disabled <name>`

**Full rollback** (scenario: organism causes more problems than it solves)
1. `launchctl unload ~/Library/LaunchAgents/com.nuzantara.organism.supervisor.plist`
2. `redis-cli DEL organism:events organism:audit organism:config:*` (audit persisted on JSONL disk)
3. Guardians enter `local_emergency_mode` automatically after 5min (no intervention needed)
4. Unwind PR: each Actuator has its introduction PR → atomic `git revert`
5. Total rollback time: <10min, zero data loss (JSONL backup + Redis AOF)

### Accepted residual risks

| Risk | Probability | Impact | Mitigation | Accepted? |
|---|---|---|---|---|
| Redis master down + AOF corruption | Low | High | Local JSONL mirror + Postgres audit backup | ✅ |
| Pro-Air split-brain | Medium | High | Sentinel quorum=2 (disables auto-failover) + Postgres lease file | ✅ |
| Claude CLI quota exhaust | Medium | Medium | 3-tier fallback to YAML/Ollama, 10min cache, hardcoded 3/min rate limit | ✅ |
| Action loop | Low | High | Cooldown + mutex + `is_actuation` flag + hardcoded whitelist | ✅ |
| Prompt injection via log | Medium | High | Slot-only templates, hardcoded deny-list, sanitized payload | ✅ |
| Supervisor OOM | Low | Medium | Stateless design, Redis is the store, launchd auto-restart | ✅ |
| Guardian cascade (false adopt) | Low | Low | 7d probationary heartbeat-only, `.organism_ignore` opt-out | ✅ |

## 5. Success criterion — Gauntlet test

5 intentional kills simultaneously on staging Pro+Air:
1. Break guardian
2. Corrupt crontab
3. Intentional deploy bug
4. Disk fill 90%
5. Push broken code

+ 5 infrastructural scenarios (added from red-team):
6. Redis down 5min
7. Pro-Air network partition
8. Clock skew Air +5min
9. Claude CLI rate-limit
10. Poison pill event

**Success = all 10 scenarios**: organism detects, correlates, decides, repairs/isolates, notifies, documents decision in audit trail. <15min total, ZERO human intervention. Complete audit on `organism:audit` stream + JSONL backup.

## 6. Total budget

- **Time**: 4-5 days of real work (wave 0 sequential + waves 1-4 parallel with 3 Opus tmux sessions each)
- **LOC**: ~3000 production + ~170 test
- **PRs**: ~20, all atomic, L2 auto-merge
- **Cost LLM**: zero Anthropic (Golden Rule #13 enforced); DeepSeek ~$0.10 for Consiglio over 5 days (10-15 deliberations max)
- **Risk**: low — shadow mode for 24h after each wave, local fallback by construction, rollback <10min

## 7. References

- Audit automations 2026-04-19: `memory/project_automations_audit_2026_04_19.md`
- Golden Rule #13 (zero Anthropic paid): `CLAUDE.md §Cost constraint`
- Autonomous Ops L2 contract: `AUTONOMOUS_OPS.md`
- Guardian V5 Learn: `memory/guardian-v5-learn.md`
- Consiglio v1: `memory/consiglio-v1.md`
- Red-team validators outputs: `/tmp/redteam-{gemini,deepseek,claude}.md` (3 LLM convergent)
