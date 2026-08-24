# METRICS.md — I DUE BOT instrumentation (F11, lane B7)

> MANDATE.md F11: _"Metrics are first-class or the bot 'works' unfalsifiably."_
> This document explains WHAT is instrumented and WHY; the metrics themselves are code —
> `apps/backend-rag/backend/services/client_bot/observability.py` — not this file. If this
> document and that module ever disagree, the module is right; re-read it before trusting a
> table here (superscar #1, HOME-fork class, applies to doc/code pairs too).

## Why business metrics get their own column

A bot that is fast and available can still be **wrong** — a hallucinated price, an uncited
regulatory claim, a CRM mutation nobody confirmed. None of those show up on a technical
dashboard (uptime, latency, error rate). `tripwires.py` tags every tripwire `business` or
`technical` for exactly this reason; the table below carries the same tag so a reader scanning
metrics can see which ones a green infra dashboard would still miss.

## BOT A — client bot (wired: `observability.py`)

| Metric                                                                     | Type      | Labels                   | Kind      | What it answers                                                                                                                                          |
| -------------------------------------------------------------------------- | --------- | ------------------------ | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `client_bot_gate_verdict_total`                                            | Counter   | surface, verdict, reason | business  | Every FinalPolicyGate outcome — the core instrument. A wrong-and-fast bot shows up here as ALLOW volume with a bad reason distribution, not as downtime. |
| `client_bot_gate_eval_seconds`                                             | Histogram | surface                  | technical | Gate-only latency (excludes provider generation time).                                                                                                   |
| `client_bot_containment_total`                                             | Counter   | surface                  | technical | ALLOW with no handoff. NOT the product KPI alone — see next row.                                                                                         |
| `client_bot_resolution_total`                                              | Counter   | surface                  | technical | Best-effort: ALLOW with no follow-up in the service window. Honestly approximate.                                                                        |
| `client_bot_handoff_created_total`                                         | Counter   | surface                  | business  | Durable handoff row created (F10 gate for the "l'ho passato" copy).                                                                                      |
| `client_bot_handoff_creation_failed_total`                                 | Counter   | surface                  | business  | Handoff attempt did NOT durably create a row — the degraded "puoi richiedere" path fired.                                                                |
| `client_bot_handoff_context_carryover_total` / `..._context_missing_total` | Counter   | surface                  | business  | **The mandate's own stated KPI**: "context carry-over to the consultant is the product bar." Read the missing/created ratio, not raw handoff volume.     |
| `client_bot_price_not_in_pricingtool_total`                                | Counter   | surface                  | business  | A price reached the gate not sourced from a frozen PricingTool snapshot. Non-zero = a client could receive an invented number.                           |
| `client_bot_citation_integrity_fail_total`                                 | Counter   | surface                  | business  | Uncited / mis-cited / unused-evidence regulatory claim reached the gate.                                                                                 |
| `client_bot_response_latency_seconds`                                      | Histogram | surface                  | technical | End-to-end webhook-ack → send, per surface (F11's p95 instrument).                                                                                       |
| `client_bot_synthetic_probe_age_seconds`                                   | Gauge     | surface                  | business  | Dead-man switch (ASSEMBLY-LINE §7 pattern): seconds since a synthetic end-to-end probe last succeeded on this surface.                                   |
| `webhook_ack_latency_seconds`                                              | Histogram | surface                  | technical | Time to the 200 ack (F9 — the ack path must contain no LLM/CRM/PricingTool work).                                                                        |
| `client_policy_unsupported_claim_escape_total`                             | Counter   | surface                  | business  | A golden/shadow-judged-unsupported claim passed the gate as ALLOW anyway. The single metric closest to "answers fast and wrongly."                       |
| `fallback_provider_failure_total` / `..._requests_total`                   | Counter   | surface                  | technical | Gemini-leg (fallback of last resort) failure ratio.                                                                                                      |

## F3 codex broker leg (wired: `observability.py`, Sol §2.5 names verbatim)

| Metric                                                         | Type                                 | Labels  | Kind                                                             |
| -------------------------------------------------------------- | ------------------------------------ | ------- | ---------------------------------------------------------------- |
| `codex_broker_heartbeat_age_seconds`                           | Gauge                                | seat    | technical                                                        |
| `codex_broker_queue_depth`                                     | Gauge                                | seat    | technical                                                        |
| `codex_exec_seconds`                                           | Histogram                            | seat    | technical                                                        |
| `client_bot_codex_route_seconds`                               | Histogram                            | surface | technical                                                        |
| `codex_consecutive_failures`                                   | Gauge (current streak, not lifetime) | seat    | technical                                                        |
| `codex_auth_dead_total`                                        | Counter                              | seat    | technical                                                        |
| `codex_quota_exhausted_total`                                  | Counter                              | seat    | technical                                                        |
| `codex_quota_fallback_total` / `codex_eligible_requests_total` | Counter                              | seat    | technical                                                        |
| `codex_output_invalid_total` / `codex_jobs_total`              | Counter                              | seat    | technical                                                        |
| `codex_secret_canary_hits_total`                               | Counter                              | seat    | **business** (a secret leak is business harm, not an SRE signal) |
| `codex_fence_violation_or_double_completion_total`             | Counter                              | seat    | technical                                                        |
| `codex_canary_probe_age_seconds`                               | Gauge                                | seat    | technical                                                        |

`AUTH_DEAD` vs `QUOTA` distinction depends on `CodexExecQuotaError`/`CodexExecPolicyBlockedError`
landing from lane B2a (branch `agent/mini-pro2/duebot/b2-broker`, not yet merged into
`feature/due-bot` as of this writing) — see the owner switchboard packet, item 4.

## BOT B — team bot (NAMING CONTRACT ONLY — not code yet)

`apps/team-bot/` does not exist (B3's file ownership). The names below are frozen so B3
implements them verbatim in `apps/team-bot/team_bot/observability.py` rather than inventing
names under time pressure — they are NOT registered Prometheus collectors today.

| Metric (planned name)                          | Type      | Labels               | Kind                                     | Source                                                                                     |
| ---------------------------------------------- | --------- | -------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------ |
| `team_bot_mutation_without_confirmation_total` | Counter   | tool                 | **business**                             | F6 — should be structurally impossible; non-zero means the state machine itself has a hole |
| `team_bot_rbac_scope_leak_total`               | Counter   | tool                 | **business**                             | F5/F7 — a CRM row reached/mutated outside `assigned_to` scope (UU PDP-class incident)      |
| `team_bot_idempotency_double_execution_total`  | Counter   | tool                 | **business**                             | F6 — a confirmed action executed twice                                                     |
| `team_bot_failover_event_total`                | Counter   | outcome              | **business** for `outcome=auto_failback` | F9 states "no automatic failback" as an architectural invariant                            |
| `team_bot_tool_call_total`                     | Counter   | tool, outcome        | technical                                | outcome ∈ success\|json_parse_fail\|schema_fail\|arg_invalid                               |
| `team_bot_json_parse_fail_total`               | Counter   | tool                 | technical                                | Kimi FM5 (language-drift breaking JSON)                                                    |
| `team_bot_repeated_call_total`                 | Counter   | tool                 | technical                                | Kimi FM3 (loop detector hits)                                                              |
| `team_bot_enum_translation_fail_total`         | Counter   | tool                 | technical                                | Kimi FM1/FM5 (non-English enum emitted)                                                    |
| `team_bot_confirm_total`                       | Counter   | action_type, outcome | technical                                | outcome ∈ confirmed\|expired\|cancelled                                                    |
| `team_bot_confirm_timeout_total`               | Counter   | action_type          | technical                                | Informational — expiry is by design; investigate only on a baseline spike                  |
| `team_bot_tool_seconds`                        | Histogram | tool                 | technical                                | p95 per tool                                                                               |
| `team_bot_identity_reject_total`               | Counter   | reason               | technical                                | Unknown/unverified/wrong-`phone_number_id` — F7                                            |
| `team_bot_replication_lag_seconds`             | Gauge     | —                    | technical                                | Mini→Pro state replication                                                                 |

## Reading this catalogue

- **`observability.py`'s `__all__` is the ground truth for what is registered today.** This
  table is maintained by hand; `test_observability.py` proves the module is internally
  consistent, not that this markdown table matches it verbatim.
- **`tripwires.py` is what turns a metric into an action.** A metric existing here with no
  corresponding row in `tripwires.py` is instrumented but not alarmed — acceptable for
  exploratory/diagnostic metrics, not for anything in the "business" column above.
- **`kill_switches.py` + `KILL-SWITCHES.md`** name the single-gesture off for every plane a
  tripwire's automatic action can flip.
