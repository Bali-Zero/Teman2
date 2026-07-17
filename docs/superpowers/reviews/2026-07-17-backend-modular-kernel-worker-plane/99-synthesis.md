---
date: 2026-07-17
status: adjudicated-final-draft
spec_status: reviewed-draft
original_panel_verdicts:
  fable_5: GO-WITH-CHANGES-82
  gemini_3_1_pro: GO-WITH-CHANGES-85
  glm_5_2: NO-GO-72
final_gate: Fable-GO-96-formatted-integrity
implementation: not-authorized
client_data: none
---

# Panel synthesis and finding disposition

## Outcome

The council did not approve the original cutover contract. It did preserve the
core decision: harden the modular monolith incrementally, move durable work out
of HTTP lifespans, and reject a microservice or broker rewrite. Every blocking
finding was accepted in substance and the spec was revised before owner review.

| Seat                                  | Original verdict     | What the review established                                                                             |
| ------------------------------------- | -------------------- | ------------------------------------------------------------------------------------------------------- |
| Fable 5, architecture judge           | GO-WITH-CHANGES, 82% | The direction is proportionate, but legacy claim paths and reverse cutover must participate in fencing. |
| Gemini 3.1 Pro, constructive reviewer | GO-WITH-CHANGES, 85% | The worker needs an infrastructure-visible health contract, a late fence, and absolute resource limits. |
| GLM 5.2, adversarial refuter          | NO-GO, 72%           | Generic exactly-once, global-ack fan-out, and same-app least privilege were false assumptions.          |

Fable then gated the revised draft twice. Its first recheck was
`GO-WITH-CHANGES, 85%`: all original panel findings were closed, but the
generation-bearing schedule key could duplicate one future run across cutover.
After that key, guard-arming order, runtime subscription enforcement, Fly
governance reconciliation, and release ordering were amended, the final
amendment gate returned **GO, 88%**, with no new blocker. After the mandatory
repository formatter changed only Markdown layout, Fable reread the exact
formatted spec at SHA-256
`2d1746b92067af1533d14c59f4751e623203941584c978a15ebe27b839a82e92` and
returned **GO, 96%** on semantic integrity, again with no blocker.

The result is a `reviewed-draft`, not an approved design. The owner may approve
creation of a Phase 0-2 implementation plan; no production mutation or cutover
is authorized by these documents.

## Evidence rechecked by the orchestrator

- The pinned router-import command produces 67 sorted paths, not 61, with
  SHA-256
  `4002789a56196bd8cdce5440c1c596191f4e349ae6a91cb7e9f3d8ca8d24991a`.
- `apps/backend-rag/backend/services/workflow/queue.py` claims the pilot queue
  with `FOR UPDATE SKIP LOCKED` and a visibility timestamp; it has no ownership
  generation, lease owner, or lease-expiry column today.
- `apps/backend-rag/backend/services/events/outbox.py` has one global
  `consumed_at`, limits replay selection by age, and acknowledges stale payloads
  to suppress replay.
- `infra/eventbus/subscriber.py` drains only the current consumer's PEL and has
  no `XAUTOCLAIM`/`XCLAIM`; its Redis idempotency check currently fails open.
- Fly's official configuration reference supports top-level health checks for
  non-public processes, while its secrets documentation says app secrets are
  available on every Machine in the app. This supports an internal probe and a
  companion app for a real credential boundary:
  [Fly app configuration](https://fly.io/docs/reference/configuration/),
  [Fly app secrets](https://fly.io/docs/apps/secrets/).

## Finding-by-finding disposition

| Review finding                                                                          | Disposition                           | Spec amendment                                                                                                                                                                                                                                    |
| --------------------------------------------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Fable B1: new fencing does not bind the legacy claim path                               | **Accepted**                          | Phase 1 installs dynamic fencing and kill switches in every legacy path before activation. A database claim function/trigger also rejects pre-compatibility SQL that omits owner/generation; G2 tests both generations of code.                   |
| Fable B2 / Gemini B1: rollback reactivates a stale generation                           | **Accepted**                          | Rollback is now a reverse database cutover: drain, increment generation again, assign the legacy owner dynamically, and complete a canary within SLO.                                                                                             |
| Fable F1 / GLM I3: the 61-file ratchet is not reproducible                              | **Accepted**                          | Recounted as 67 with an exact command, sorted baseline, and output hash in sections 1.2 and G7.                                                                                                                                                   |
| Fable F2: table ownership has no executable gate                                        | **Accepted**                          | Added a schema-introspected ownership manifest, migration lint, expiring exceptions, and G16.                                                                                                                                                     |
| Fable F3: one owner conflicts with valid internal concurrency                           | **Accepted**                          | I1 now defines an owner as one workload grant/generation; the catalog controls concurrency within that grant.                                                                                                                                     |
| Fable F4: worker budget is relative only                                                | **Accepted**                          | Phase 2 and G9/G14 now set initial hard limits: 1 GB VM, 60-second readiness, 750 MiB steady/850 MiB peak RSS, and eight DB connections.                                                                                                          |
| Gemini B2: worker needs a Fly deployment health contract                                | **Partially accepted**                | The operational requirement is valid; the assertion that every Fly worker deployment inherently requires a check is too broad. The spec adds a private `:9091/ready` top-level check plus build-SHA heartbeat and makes both a CI promotion gate. |
| Gemini I1: generation can change while an external call is in flight                    | **Accepted**                          | Added a late fence, `draining` mode, provider-timeout barrier, effect state machine, and G15.                                                                                                                                                     |
| Gemini I2: concurrent Redis reclaims can contend                                        | **Accepted**                          | Section 8.3 requires one reclaimer per group or a leader lock plus jitter.                                                                                                                                                                        |
| Gemini I3: same image can eagerly import RAG dependencies                               | **Accepted with scope**               | The base worker entrypoint may not eagerly import application factories, routers, Qdrant clients, or inference models. Workload adapters may load needed dependencies lazily only within their measured profile.                                  |
| GLM B1: exactly-once is false without provider support                                  | **Accepted**                          | The spec no longer promises universal exactly-once. Each irreversible handler is provider-idempotent, reconcilable, or non-reconcilable; ambiguous non-reconcilable outcomes block and require audited resolution.                                |
| GLM B1 proposed pre-flight dedup insert as a universal correction                       | **Rejected as sufficient**            | A unique row prevents concurrent attempts but cannot distinguish a crash before send from a crash after send. The ledger is retained, but only provider idempotency, reconciliation, or explicit `outcome_unknown` resolves ambiguity.            |
| GLM B2: global-ack outbox loses a second subscriber before Phase 5                      | **Accepted**                          | A checked event catalog blocks the second durable subscriber until per-subscription receipts exist; G5 tests both the guard and later independent receipts.                                                                                       |
| GLM B3: same-app least privilege is unenforceable                                       | **Accepted**                          | Worker placement changed from another process group in the existing Fly app to a companion Fly app using the same immutable image and coordinated release, a scoped DB role, and a grant audit.                                                   |
| GLM I1: durable stale events are acknowledged away                                      | **Accepted**                          | Phase 0 replaces global age/ack-drop for durable events with per-event recovery SLOs and quarantine/DLQ; G17 proves it.                                                                                                                           |
| GLM I2: Redis reclaim is a live defect, not Phase 5 work                                | **Accepted**                          | Reclaim and fail-closed irreversible idempotency moved to Phase 0 and G6.                                                                                                                                                                         |
| Final Fable RB1: generation-bearing schedule key duplicates a future run across cutover | **Accepted and closed**               | Logical run and effect identities are generation-independent; cutover adopts or audits cancellation of pending runs; G12 tests cutover and rollback between enqueue and execution.                                                                |
| Final Fable A2: guard arming can lock out a legitimate old binary                       | **Accepted and closed**               | Arming now requires the same fleet heartbeat/build floor as cutover.                                                                                                                                                                              |
| Final Fable A3: CI-only fan-out guard misses runtime registration                       | **Accepted and closed**               | Runtime dispatcher and `subscribe()` fail closed against the catalog; G5 tests direct bypass.                                                                                                                                                     |
| Final Fable A4/A5: Fly governance and companion release mechanics drift                 | **Accepted and closed at spec level** | Phase 2 must reconcile the infrastructure inventory before app creation and choose a constrained migration policy with primary-first deployment.                                                                                                  |

## Revised architecture in plain language

The website and API remain one product. The code remains one repository and one
backend image. Long jobs move into a separate, non-public worker app so they
cannot freeze web traffic and so they receive a narrower database key. The
database decides who owns each job; configuration flags alone do not. During a
move, the old owner stops taking work, finishes or exposes uncertain sends, and
only then hands a new generation to the worker. Rollback performs the same
handoff in reverse and must actually complete a canary job.

Events with several listeners do not share one global "done" flag. Messages to
external providers are not called exactly-once unless the provider or a
reconciliation query can prove that. If the system cannot know whether a send
happened, it stops automatic retry and shows an auditable uncertain state.

## Residual risks and explicit trade-offs

- A companion Fly app adds one coordinated deployment target. Digest equality
  and build-SHA gates trade a small amount of CI complexity for a real secret
  boundary.
- The initial worker budgets are hard falsification thresholds, not capacity
  forecasts. If the workflow pilot cannot meet them, Phase 2 fails and the spec
  must be amended openly.
- Non-reconcilable providers can force manual resolution. That is slower but
  safer than silently duplicating a client-visible action.
- Table grant design and event classification are substantive Phase 0-1 work;
  this is why approval authorizes planning only, not deployment.
- The Phase 2 plan must enumerate the governance files it reconciles and choose
  whether the companion skips migrations or uses the advisory-locked runner.

## Review integrity

- All four Fable runs reported only `claude-fable-5`, one-million-token
  context, successful completion, no fallback, and no permission denial. The
  final run reviewed spec SHA-256
  `2d1746b92067af1533d14c59f4751e623203941584c978a15ebe27b839a82e92`.
- Gemini was explicitly selected as `Gemini 3.1 Pro (High)` and completed with
  exit code 0. Because its headless repository tool wrapper denied commands,
  the complete spec and brief were supplied in the prompt; it made no edits.
- GLM runtime evidence reported only `glm-5.2`, 200,000-token context,
  successful completion, no fallback, and no permission denial.
- Git state was unchanged by every read-only model review run. No client data,
  credentials, or paid per-token endpoint was used.

## Review artifacts

- [Fable 5 original architecture review](01-fable-5-architecture-judge.md)
- [Gemini 3.1 Pro constructive review](02-gemini-3.1-pro-constructive.md)
- [GLM 5.2 adversarial review](03-glm-5.2-adversarial.md)
- [Fable 5 revised-spec gate](04-fable-5-revised-gate.md)
- [Fable 5 final amendment gate](05-fable-5-final-amendment-gate.md)
- [Fable 5 formatted-spec integrity gate](06-fable-5-formatted-spec-integrity-gate.md)
