---
date: 2026-07-17
reviewer: Fable 5
model: claude-fable-5
role: final-amendment-gate
invocation_result: success
model_proof: "modelUsage contained only claude-fable-5; contextWindow 1000000"
spec_sha256: 6d9fe3832e2acd639108bde06578b22577c68c01e1d0d5fba1e6160d03ecdfd4
verdict: GO-88
client_data: none
repository_access: read-only
---

# Final verdict

**GO — confidence 88.**

All five prior-gate items are closed in the amended specification with falsifiable acceptance gates, and the amendments introduce no new blocking failure mode. Two non-blocking residuals are noted under Amendment closure (4 and 5); both are already fenced by the spec's own phase ordering and remain implementation-plan work, not spec defects. This verdict operates entirely inside the spec's own approval boundary (section 20): it endorses the document as a decision record, not any deployment.

# Amendment closure

**RB1 (schedule-run uniqueness across generations) — CLOSED.** Verified in spec text: section 7.3 now mandates a generation-independent deterministic run key (`(workload_name, scheduled_for)`), stores `ownership_generation` only as a mutable claim attribute "never as part of logical-run identity," and requires a unique constraint or idempotency ledger that blocks both a restarted scheduler and a post-cutover/rollback new owner from enqueuing the same logical run. The business-identity requirement is met by the `effect_key` rule ("derives from stable business identity and effect purpose… never from a queue row, attempt number, or ownership generation"). Adoption-or-audited-cancellation of pending unclaimed runs is bound into the cutover transaction itself (section 13 steps 4-5), and the time-of-check window is closed because `draining` (section 7.2) forbids new scheduled runs before the inventory. The cross-generation dedupe test exists: G12's schedule-class fixture enqueues a future run, cuts over before it is due, requires exactly one logical run and at most one business-identity effect, and repeats the scenario across reverse-cutover rollback. All three closure conditions are satisfied.

**Amendment 2 (claim-guard arming gated on heartbeat/build floor) — CLOSED.** Section 7.2 states the guard "is not armed merely because its migration exists"; arming is a gated ownership transition requiring every live owner heartbeat to meet the compatibility build floor, with stale or missing heartbeats failing closed, and the same evidence re-required at cutover. Phase 1 sequences arming after the heartbeat floor is met, its exit gate requires a heartbeat inventory with no live build below the floor, and G2 exercises both the pre-compatibility SQL rejection and the promotion-gate rejection of an old build. The rolling-release lockout failure mode identified by the prior gate is addressed at spec level.

**Amendment 3 (runtime enforcement of the second-durable-subscriber guard) — CLOSED.** Section 8.2 requires the runtime dispatcher and the `subscribe()` registration path to consume the catalog at startup and registration time and fail closed on uncataloged durable subscriptions, explicitly excluding bypass via naming convention, dynamic registration, or in-process handler lists. Phase 1 carries the matching work item, and G5 adds the falsifiable test: a direct runtime `subscribe()` bypass must fail startup or registration. Verified fact: the real registration surface exists at `apps/backend-rag/backend/services/events/event_bus.py:244` (`def subscribe(...)`), and the global-ack semantics the guard protects (`consumed_at`/`consumer_id`, including the `_stale_skip` acknowledgement at `outbox.py:391`) match the spec's description, so the enforcement point is anchored to real code, not a hypothetical.

**Amendment 4 (reconcile Fly governance artifacts and stale Qdrant claims) — CLOSED, one non-blocking residual.** Phase 2's first bullet orders reconciliation "before creating the app": replace stale fixed-app-count statements with a current inventory plus the approved companion target, and record Qdrant as external where that is the deployed reality. Verified fact that the targeted staleness exists and is exactly what the amendment names: `.claude/rules/infrastructure.md` asserts "ONLY 3 apps (nuzantara-rag, nuzantara-qdrant, nuzantara-postgres)" while `apps/backend-rag/fly.toml:40` records `QDRANT_URL` as a secret pointing at Qdrant Cloud (external), and the root project CLAUDE.md section 11 claims "Fly.io 2 apps" — three mutually inconsistent governance statements the reconciliation step must collapse into one inventory. Residual (non-blocking): the spec describes the artifacts generically rather than enumerating file paths; the implementation plan must enumerate them, but the reconciliation obligation and its ordering are falsifiable as written.

**Amendment 5 (companion release_command policy and deployment order) — CLOSED, one non-blocking residual.** Phase 2 now names the policy as a constrained disjunction — the companion either skips migrations or uses the same advisory-locked migration runner — and fixes the order: deploy the primary app and verify schema compatibility before promoting the companion. Verified fact: the primary's `release_command` at `apps/backend-rag/fly.toml:15-18` is the advisory-locked `backend.db.migrate apply-all` runner plus `schema_audit`, so both named options are grounded in the deployed reality and either eliminates the double-migration/schema-skew failure mode when combined with the ordering rule. Residual (non-blocking): the binary choice between the two options is deferred to the Phase 2 implementation plan; since both are safe and the spec forbids any third option, this is acceptable at decision-record level.

# New blockers

None.

Three candidate failure modes were examined and rejected as blockers. First, a potential arming deadlock (heartbeats required before heartbeats exist) does not arise: the compatibility release that adds fencing checkpoints to legacy claim paths is what introduces the heartbeats, and arming is sequenced after that release is fleet-wide — this is the intended ordering, not a cycle. Second, the fail-closed runtime `subscribe()` guard could halt `api`/`rag` startup if an existing subscription were left uncataloged at Phase 1 rollout; this is the designed fail-visible behavior, is caught by the CI catalog rule before deploy, and Phase 1's "retain current behavior" exit forces the catalog to enumerate current subscribers first — implementation risk, not a spec defect. Third, under the new unique run key, a run explicitly cancelled at cutover cannot later be re-enqueued unless the uniqueness constraint excludes cancelled rows; because cancellation is an explicit audited operator decision (the default path is adoption), a skipped run is a visible choice rather than silent loss — an implementation detail for the Phase 2-3 plan, not a blocking failure.

# Final authorization boundary

This gate ran strictly read-only and confers no execution authority of its own. Per section 20 of the specification, a GO here supports owner approval of the document as a decision record, which authorizes **only the creation of an implementation plan for Phases 0-2**. It does not authorize production deployment, companion-app creation, job cutover, claim-guard arming, event schema migration, service extraction, or deletion of any rollback path; each later phase requires its preceding falsifiable exit gates (G1-G17 as mapped per phase) to pass first. The owner (Antonello) retains the final approval gate; until that approval the status remains `reviewed-draft` and implementation remains unauthorized. The two non-blocking residuals recorded above (enumerating the governance artifacts for the Phase 2 reconciliation, and resolving the release_command disjunction) must be settled inside the Phase 2 implementation plan before the companion app is created or promoted.
