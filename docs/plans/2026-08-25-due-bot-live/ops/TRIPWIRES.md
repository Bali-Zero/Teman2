# TRIPWIRES.md — every automatic action, and why it fires (F11, lane B7)

> Machine-readable source of truth:
> `apps/backend-rag/backend/services/client_bot/tripwires.py`. This document is a rendering of
> it for human review — `test_tripwires.py` checks the registry's internal consistency (every
> `wired` metric is real, every named plane has a kill switch), not that this markdown table is
> byte-identical to the registry. If you edit `tripwires.py`, re-render this table by hand in
> the same PR.

## The business/technical split, and why it exists

The team lead's framing for this lane: _"The tripwires must be tied to BUSINESS invariants, not
just technical ones — a bot that answers fast and wrongly is worse than one that is down."_
Every row below is tagged. **Technical** tripwires answer "is it up and fast" — the class any
infra dashboard already covers. **Business** tripwires answer "is it correct and safe" — a
wrong price, an uncited claim, a CRM mutation with no confirmation, a cross-client RBAC leak. A
bot can be green on every technical row and still be doing active harm on a business one; that
is the exact failure mode ASSEMBLY-LINE's "one inversion" warns about, applied to alerting
instead of to merge counts.

## Client bot + codex broker leg

15 rows — entries 1-13 are F3/Sol §2.5 VERBATIM, plus 3 B7 additions the frozen research didn't
tabulate.

**⚠️ rows and the QUOTA classification's arming condition.** B2a's first attempt at splitting
AUTH_DEAD/QUOTA/POLICY_BLOCKED apart (stderr-regex matching) was refuted — 12 findings from a
cross-family refuter, all reproduced, all traced to one design defect (a single stderr can match
two classes; matching spans a whole multi-line blob; prose can't be reliably classified by
vocabulary). It was replaced by
`docs/plans/2026-08-25-due-bot-live/SPEC-codex-error-classification.md`, which states plainly:
"This stays dark until a REAL codex exec quota event and a REAL policy block have been observed
and their exact stderr recorded here... no caller may take an irreversible action on it" until
then. The two ⚠️ rows above (`codex.quota_exhausted`, `codex.quota_fallback_ratio`) read that
still-advisory classification — log and observe them, but do not treat their thresholds as
confident enough to drive an unattended automatic action until the spec's arming condition is
met. `codex.auth_dead` is NOT gated this way: it reads a different, pre-existing,
empirically-anchored classifier (one already-tested pattern), not the refuted split.
`codex.cli_version_mismatch` is also unaffected — it reads `wa_codex_daemon.py`'s own
deterministic version-pin guard, unrelated to the contested stderr classifier, and is the one
INTERNAL-class condition reliable enough to page on today.

| id                              | metric                                                       | threshold                                 | kind         | automatic action                                                                        |
| ------------------------------- | ------------------------------------------------------------ | ----------------------------------------- | ------------ | --------------------------------------------------------------------------------------- |
| `codex.heartbeat_stale`         | `codex_broker_heartbeat_age_seconds`                         | > 45s                                     | technical    | Mark host offline; direct to Gemini                                                     |
| `codex.queue_growing`           | `codex_broker_queue_depth`                                   | >= 1 waiting                              | technical    | Bypass Codex for subsequent messages                                                    |
| `codex.exec_slow`               | `codex_exec_seconds`                                         | p90 > 12s over >=20 jobs                  | technical    | Do not arm / revert to Gemini                                                           |
| `codex.route_slow`              | `client_bot_codex_route_seconds`                             | p95 > 15s, 3 consecutive 15-min windows   | technical    | Disable active Codex routing; keep shadow                                               |
| `codex.consecutive_failures`    | `codex_consecutive_failures`                                 | >= 3                                      | technical    | Open seat breaker 5 min; half-open with 1 canary                                        |
| `codex.auth_dead`               | `codex_auth_dead_total`                                      | >= 1                                      | technical    | Latch seat offline; operator alert (switchboard item 4)                                 |
| `codex.quota_exhausted` ⚠️      | `codex_quota_exhausted_total`                                | >= 1                                      | technical    | Cooldown seat; alert with evidence                                                      |
| `codex.quota_fallback_ratio` ⚠️ | `codex_quota_fallback_total / codex_eligible_requests_total` | >5%/7d (n>=50), or 2 exhausted windows/7d | technical    | **Produce owner packet** → `packets/QUOTA-WALL-STAGE2-PACKET.template.md`               |
| `codex.output_invalid_ratio`    | `codex_output_invalid_total / codex_jobs_total`              | >1%/100 jobs, or 2 consecutive            | technical    | Quarantine CLI/model/schema combo                                                       |
| `codex.secret_canary_hit`       | `codex_secret_canary_hits_total`                             | > 0                                       | **business** | GLOBAL codex-leg kill (`CLIENT_BOT_CODEX_BROKER_ENABLED=false`); P0                     |
| `codex.fence_violation`         | `codex_fence_violation_or_double_completion_total`           | > 0                                       | technical    | Disable active leg; no affected output may send                                         |
| `ingress.ack_latency`           | `webhook_ack_latency_seconds`                                | p95 > 200ms, 5 min                        | technical    | Page ingress issue; shed LLM work from request path                                     |
| `fallback.failure_ratio`        | `fallback_provider_failure_total / ..._requests_total`       | >1%/30min (n>=100)                        | technical    | Disable bot auto-replies; human handoff only                                            |
| `codex.canary_probe_silent`     | `codex_canary_probe_age_seconds`                             | > 900s                                    | technical    | Cooldown seat; alert — heartbeat alone doesn't prove generation works                   |
| `codex.cli_version_mismatch`    | `codex_cli_version_mismatch_total`                           | >= 1                                      | technical    | Page operator — CLI/config drift, NOT AUTH_DEAD/QUOTA; `codex login` fixes nothing here |

⚠️ = gated by `requires_arming_condition` (see note below the table) — the QUOTA classification
these two read is advisory, not yet armed for automatic action.

## Client bot — business invariants (B7 additions closing the gap above)

| id                                       | metric                                          | threshold                   | automatic action                                                                                     |
| ---------------------------------------- | ----------------------------------------------- | --------------------------- | ---------------------------------------------------------------------------------------------------- |
| `client.unsupported_claim_escape`        | `client_policy_unsupported_claim_escape_total`  | > 0 in golden/shadow        | Block promotion                                                                                      |
| `client.price_not_in_pricingtool`        | `client_bot_price_not_in_pricingtool_total`     | > 0, or >=2/1h same surface | 1st: P0 page. 2nd in 1h: auto-flip that surface's send flag off                                      |
| `client.citation_integrity_fail`         | `client_bot_citation_integrity_fail_total`      | > 0 in golden/shadow        | Block promotion                                                                                      |
| `client.handoff_creation_failing`        | `client_bot_handoff_creation_failed_total`      | > 0                         | Page owner — ClientHandoffService itself is unhealthy                                                |
| `client.handoff_context_carryover_low` ⓘ | `..._context_missing_total / ..._created_total` | > 20%/7d, n>=5              | Weekly digest (PASS/FAIL/INSUFFICIENT_DATA); 3 FAIL weeks feeds the MANDATE.md kill-criterion review |
| `client.synthetic_probe_silent`          | `client_bot_synthetic_probe_age_seconds`        | > 900s                      | Auto-flip that surface's send flag off; page owner (dead-man switch)                                 |

ⓘ **`client.handoff_context_carryover_low` can go quiet instead of red** — with fewer than 5
handoffs in a week (including exactly 0), the ratio is undefined and the digest must report
INSUFFICIENT_DATA, never "100% healthy." An INSUFFICIENT_DATA week neither counts toward nor
resets the 3-week kill-criterion clock. Team-lead review finding (2026-08-25): this is the
family-#2 failure ("green because nothing was measured") the repo's own cicatrix rules already
name — silence must not read as a passing grade.

## Team bot (NAMING CONTRACT — `apps/team-bot/` doesn't exist yet, B3 implements)

| id                                  | metric (planned)                                            | threshold     | kind         | automatic action                                                                 |
| ----------------------------------- | ----------------------------------------------------------- | ------------- | ------------ | -------------------------------------------------------------------------------- |
| `team.confirmation_bypass`          | `team_bot_mutation_without_confirmation_total`              | > 0           | **business** | Freeze `TEAM_BOT_MUTATIONS_ENABLED`; P0 — F6's state machine has a hole          |
| `team.rbac_scope_leak`              | `team_bot_rbac_scope_leak_total`                            | > 0           | **business** | Freeze mutations + read tools; P0 — UU PDP-class incident                        |
| `team.idempotency_double_execution` | `team_bot_idempotency_double_execution_total`               | > 0           | **business** | Freeze mutations; P0 — action executed twice against production CRM              |
| `team.auto_failback`                | `team_bot_failover_event_total{outcome=auto_failback}`      | > 0           | **business** | Freeze `TEAM_BOT_FAILOVER_AUTO_ENABLED`; P0 — F9's "no automatic failback" broke |
| `team.tool_output_degradation`      | `team_bot_json_parse_fail_total / team_bot_tool_call_total` | >10%/50 calls | technical    | Fall back that tool to fixed no-tool reply                                       |
| `team.replication_lag`              | `team_bot_replication_lag_seconds`                          | > 60s         | technical    | Pro enters read-only mode                                                        |

## Promotion sequences (both, verbatim from the mandate / research capture)

**Client bot** (Sol §2.5): `synthetic probe → shadow against recorded fixtures → production
shadow, no send → owner-only allowlist → 5% eligible WA traffic → 25% → one surface at a time`.
Each step requires zero fence violations, zero secret canary hits, zero unsupported regulatory
claims, and acceptable latency.

**Team bot** (research §5.5, owner switchboard item 7): `ingress/audit → shadow intent/tool
selection → fixed replies to owner → allowlisted staff, read tools → R2 writes → R3 practice
open → automatic failover`.

## The recorded F9 dissent this table defers to

Kimi's refutation (research §7, "Tailscale Funnel failover") argues the Funnel design is
dev/demo-grade for a production Meta webhook and proposes a Fly dumb-forwarder-over-tailnet as
the more sovereign v1. The mandate ships Funnel and keeps the dissent alive as evidence-gated:
if `webhook_ack_latency_seconds` or Funnel-specific availability evidence accumulates against
it in production, that evidence is exactly what fills
`packets/FUNNEL-PIVOT-PACKET.template.md` — this is not yet a tripwire with an automatic action
because Funnel isn't live yet; it becomes one the moment F9 ships past shadow.
