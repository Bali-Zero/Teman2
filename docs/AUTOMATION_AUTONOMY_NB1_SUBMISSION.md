# Automation Autonomy System v3.3 — NB-1 Oracle Validation Submission

**Date:** 2026-03-31
**Submitted by:** Claude Code (orchestrator)
**Full plan:** `docs/AUTOMATION_AUTONOMY_SYSTEM_V3_3.md`
**Validation request:** NB-1 Oracle (Ground Truth notebook)

---

## Executive Summary

The Automation Autonomy System v3.3 is a 4-tier self-healing loop running on the Pro/Air machine pair (M4 Pro 48GB + M4 16GB). It monitors 31 scheduled jobs, detects failures, and escalates through tiers without human intervention: Tier 0 (gateway health), Tier 1 (exponential backoff retry), Tier 2 (Aider auto-fix for deterministic patterns), Tier 3 (DLQ + Claude Code task file), Tier 4 (Zero direct alert).

The system is currently in production with a known critical defect: the DLQ has 41 live entries, with `comfyui_server` and `seo_auto_fixer` at 162 autopilot attempts each, caused by missing TERMINAL state enforcement. Phase 0 is marked URGENT.

The plan has been reviewed across 3 rounds by 3 independent AI agents (Codex SRE, Gemini Architecture, DeepSeek Reasoning), incorporating 23+ findings. Round 3 resulted in GO WITH CONDITIONS from all three reviewers. The 4 Round 3 conditions have been incorporated into v3.3. The plan spans 4 phases (12 days elapsed, 7 days net), covering emergency stabilization (Phase 0), decision tree hardening (Phase 1), security hardening (Phase 2), documentation automation (Phase 3), and DLQ intelligence upgrade (Phase 4).

Key architectural decisions include: per-machine JSONL escalation files eliminating cross-machine write conflicts, HALT-on-registry-mismatch replacing silent warn-and-continue, LLM constrained to classify-only role with explicit enforcement guard, and phase transition matrix using `raise ValueError` (never `assert`) as a security-critical gate.

---

## 5 Critical Architecture Decisions for NB-1 Validation

### ADR-1: Circuit Breaker State File — Single Writer Per File

**Decision:** Each state JSON file has one designated writer identified by a `_writer` field. Cross-process writes go through message-passing (JSONL append for escalations; file-per-job for sentinel state). Enforcement is via code review only — not at runtime.

**Question for NB-1:** Is the single-writer pattern consistent with how `sentinel_lib/circuit_breaker.py` currently manages concurrent access? Are there existing patterns in the codebase that contradict or confirm this approach?

---

### ADR-2: TERMINAL State — Hard Stop

**Decision:** A job reaching `max_attempts` transitions to `TERMINAL`. It is never automatically re-processed. Removal requires explicit human action via `dlq_autopilot.py clear <job_id>`. The previous `abandoned` status that allowed re-entry to the processing loop is eliminated.

**Question for NB-1:** Does the current `dlq_autopilot.py` processing loop in the codebase have any path other than `updated_queue.append(entry)` that would allow a TERMINAL entry to re-enter processing? Confirm whether the proposed TERMINAL guard as the first condition in `process_entry()` is consistent with the surrounding code structure.

---

### ADR-3: escalations — Per-Machine JSONL (REVISED v3.3)

**Decision:** `shared/escalations_pro.jsonl` (Pro only) and `shared/escalations_air.jsonl` (Air only) replace the single `shared/escalations.jsonl`. Each file uses `O_APPEND` for local atomicity. Entries must remain under 4096 bytes (PIPE_BUF on macOS) — entries with long stack traces must be truncated to 2000 characters before append. Readers merge both files in-memory, filtering `status != "resolved"`, sorted by `ts`.

**Question for NB-1:** Are there any existing consumers of `shared/escalations.json` or `shared/escalations.jsonl` in the codebase (MCP tools, dashboard scripts, Air-side automation) that would break under the per-machine file rename? Confirm migration path via `scripts/migrate_escalations.py` is complete.

---

### ADR-7: Registry Integrity = HALT Gate (NEW v3.3)

**Decision:** SHA256 mismatch on `job_registry.json` halts all Sentinel processing. Resume requires human creation of `~/.agent/decisions/REGISTRY_OVERRIDE`. Progressive escalation: T+30min second Telegram CRITICAL; T+4h email to zero@balizero.com. Max halt duration: 24h, then auto-resume with WARNING. `REGISTRY_HALT` marker file includes `_halt_started_at` timestamp. On Air, if REGISTRY_HALT activates during a legitimate git pull window (Pro committed, Air hasn't pulled), false halt auto-resolves within 5 minutes via post-commit hook.

**Question for NB-1:** Is the `load_registry()` function in `nuzantara-sentinel.py` the correct and only entry point for registry loading? Are there other code paths that read `job_registry.json` directly that would bypass this HALT gate?

---

### ADR: `_set_phase()` — `raise ValueError`, never `assert` (Round 3 addition)

**Decision:** The phase transition guard in `_set_phase()` uses `raise ValueError(f"Invalid phase transition: {current} → {new}")` — not `assert`. Python `assert` is a no-op under `-O` optimization. Since this gate controls which repair actions are applied to jobs affecting 5000+ clients, it must be a real exception.

**Question for NB-1:** Are there existing patterns in `sentinel_lib/` or `circuit_breaker.py` that use `assert` for security-critical gates? If so, do they also need to be converted to `raise ValueError`?

---

## Risk Register (Complete — R1 through R18)

| ID  | Risk                                                                             | Severity | Likelihood | Phase |
| --- | -------------------------------------------------------------------------------- | -------- | ---------- | ----- |
| R1  | Infinite healing loop (CONFIRMED IN PROD)                                        | CRITICAL | CONFIRMED  | 0     |
| R2  | Healing loop — PID lock missing                                                  | HIGH     | HIGH       | 0     |
| R3  | Registry integrity corruption by AI agent — silent proceed                       | CRITICAL | MEDIUM     | 0     |
| R4  | TOCTOU race in circuit_breaker.py                                                | HIGH     | LOW        | 0     |
| R5  | Command injection via path traversal + null/newline bypass                       | HIGH     | LOW        | 2     |
| R6  | escalations cross-machine interleaved writes                                     | HIGH     | MEDIUM     | 2     |
| R7  | Escalation alert flooding (2016 messages/week)                                   | MEDIUM   | HIGH       | 1     |
| R8  | HEALING_DISABLED has no effect in LaunchAgent                                    | MEDIUM   | CONFIRMED  | 0     |
| R9  | Sub-daily job dedup broken (idempotency token)                                   | MEDIUM   | HIGH       | 1     |
| R10 | LLM executor introduces non-determinism                                          | MEDIUM   | MEDIUM     | 4     |
| R11 | \_failure_timestamps unbounded growth                                            | LOW      | HIGH       | 1     |
| R12 | Watchdog absolute cutoff fires at wrong time after restart                       | LOW      | LOW        | 1     |
| R13 | OpenClaw jobs classified as REMOTE repair — clogs manual backlog                 | LOW      | CONFIRMED  | 0     |
| R14 | preclassify_jobs.py causes false HALT via N2 mechanism                           | MEDIUM   | HIGH       | 0     |
| R15 | Recovered job shows stale phase=T3 indefinitely                                  | LOW      | HIGH       | 4     |
| R16 | dlq clear command referenced in ADR/criteria but unimplemented                   | MEDIUM   | CONFIRMED  | 0     |
| R17 | Air not updated when Phase 0 deployed on Pro only                                | HIGH     | MEDIUM     | 0     |
| R18 | REGISTRY_HALT false-positive blocks entire Sentinel including live critical jobs | HIGH     | MEDIUM     | 0     |

---

## NB-1 Validation Request

**Primary question:** Validate that the 5 architecture decisions above (ADR-1, ADR-2, ADR-3, ADR-7, and the `assert→ValueError` requirement) are consistent with the existing `sentinel_lib` codebase patterns and operational constraints documented in NB-1.

**Specific verification checklist for NB-1:**

1. Confirm `sentinel_lib/circuit_breaker.py` single-writer assumption holds in production code (ADR-1)
2. Confirm `dlq_autopilot.py` `process_entry()` has no hidden re-processing path for TERMINAL/abandoned entries (ADR-2)
3. Identify all consumers of `shared/escalations.json` or `shared/escalations.jsonl` that need migration (ADR-3)
4. Confirm `load_registry()` is the only registry read path in `nuzantara-sentinel.py` — no bypass routes (ADR-7)
5. Identify any existing `assert` usage in security-critical paths in `sentinel_lib/` that should be converted to `raise ValueError`
6. Verify R18 escalation timer logic (T+30min, T+4h, T+24h auto-resume) does not conflict with existing Telegram alert patterns in `sentinel_lib/alerter.py`
7. Confirm that the Air REGISTRY_HALT false-positive scenario (git pull window) is correctly handled by the 5-minute post-commit hook — no edge case where Air pull succeeds but checksum still mismatches

**Full plan for reference:** `docs/AUTOMATION_AUTONOMY_SYSTEM_V3_3.md`
