# Dual Consul Harness: common contract v4

**Design:** Astra and Fable; consolidated from the owner's accepted v4 plan, 2026-09-06.
**Implementation status:** initial synthetic slice; operational qualification and fleet activation remain separate.

This contract defines one governance layer with two native consul integrations and route-specific adapters. Either consul may lead a mission; the other reviews the frozen artifact. A model, account, runtime, or role change confers no authority and preserves no review automatically. Environment permissions and the owner's scope, interruption, and revocation remain effective. This design adds no mandatory human reapproval or general CI gate.

## Reuse and ownership

Autonomous Lab owns mission state and lifecycle. Research OS owns canonical intents, attempts, handoffs, evidence, and receipts. The existing conductor owns binding discovery and registry integration. There is no second scheduler or parallel canonical ledger.

Reuse the [Research OS canonical contracts](../../../research/operations/specs/evidence-to-action-freeze-2026-08-15/CONTRACTS.md) unchanged. Add route-specific data through versioned reverse-DNS extensions. An extension cannot weaken canonical semantics, become an authorization, or acquire release-gate authority by itself. Canonical semantic changes follow the existing freeze-change protocol.

PostgreSQL is authoritative for mission ownership, scoped grants, expiry, revocation, and monotonically increasing fencing versions. Redis is auxiliary. A trusted executor under a distinct service identity rechecks the grant, current owner and fence, exact resource, action, and input immediately before every effect. The model process receives no general service credentials. Hooks, worktree conventions, and a local lease check alone do not establish this boundary.

An ownership claim succeeds only if its authoritative transaction succeeds. Renewal, takeover, cancellation, and resume never restore a stale owner or expired grant. Tests of simulated ownership are identified as synthetic tests, not evidence of a deployed distinct-identity executor.

## Admission and binding evidence

A binding records requested and observed model, provider and route, runtime version, host, authentication-context digest, effective configuration digest, supported schema, tested capabilities, evidence references, and expiry. Capability eligibility is computed for the specific mission; configured or participation-observed does not imply effects-qualified.

| Identity assurance  | Evidence                                               | Exact-model requirement                            |
| ------------------- | ------------------------------------------------------ | -------------------------------------------------- |
| `response_observed` | Native response metadata matches the requested binding | May satisfy the identity requirement while current |
| `request_observed`  | Requested/resolved alias seen on the request wire only | Insufficient                                       |
| `unknown`           | Effective identity absent or unverified                | Insufficient                                       |

These are observation levels, not cryptographic model signatures. Self-assertions, commit trailers, and session links do not authenticate a model. A historical report of metadata is distinguished from original metadata inspected during qualification.

Cache discovery by runtime version, configuration, host, and authentication context, with an explicit expiry. Revalidate after a relevant change. A mission demanding a hard output, total-consumption, tool, identity, or cancellation bound is ineligible when the adapter cannot enforce that requirement; never silently lower the requirement.

## Execution, outcomes, and review

Record an `ActionIntent`, scoped authorization through the existing grant and receipt contracts, and an immutable started `ExecutionAttempt`. Record the actual result separately through `OperationalReceipt`. A local action journal may project `pending`, `started`, `confirmed`, and `reconcile_required`; these names do not redefine canonical closed enums. Journal entries bind action, exact resource, input, and idempotency key.

Text completeness is separate: `complete`, `incomplete`, or `unknown`, based on provider termination evidence. Missing finish metadata means unknown completeness; short length or HTTP 200 does not prove completion. Truncated text is incomplete. An uncertain consequential effect requires reconciliation against the remote system where possible. A local timeout proves neither remote cancellation nor absence of an effect. Replay requires authoritative status/idempotency checks, not an optimistic retry.

A review receipt binds the artifact/tree hash, actual input packet, effective binding/configuration, tool/runtime versions, and evidence set. Material changes invalidate it. The reviewer must be independent of the artifact's generator; receipt construction is not evidence that a review occurred. Resolve disagreements in at most two cycles, suspend the disputed point, and continue independent work.

Resume the same native mission/session only after fresh authorization, ownership/fence, configuration, and input checks. Do not reuse sessions across unrelated missions. Native compaction is context management, not company memory authority. Keep transactional state, working context, episodes, and documentary knowledge separate; retrieved prose and summaries remain untrusted evidence.

## Adapter surface and economy

Each adapter implements discovery, mission admission, invocation, checkpoint/handoff, and cancellation through the existing contracts. Native runtimes retain their own session and tool semantics. Cancellation reports local interruption and remote cancellation separately.

Use one lead, a narrow review packet, and at most four workers: a ceiling, not a target. Admit native delegation only when observable and controllable under that ceiling. Avoid repeated unchanged discovery and context reads. Preserve provider-native usage counters with unknown fields explicit; reasoning already included in output is never added again. An output-token limit is not a total-spend limit, and hiding reasoning does not save generated tokens.

Share executor conformance tests. Add focused adapter fixtures for incompatible parameters, identity gaps, incomplete/unknown responses, excluded fields, and late responses. Run bounded real smoke tests on introduction or relevant changes, not on every PR or every host. Preserve `change_map`, `impact_map`, and advisory exclusions from `merge_group`. Delete tests only for demonstrated redundancy or lack of useful coverage; do not relocate a general harness suite into every PR.

## First slice and rollout boundaries

The first slice connects a synthetic mission through the existing `AutonomousLabWorker(stage_nodes=...)` lifecycle, uses a narrow synthetic grant, binds a review receipt to a frozen packet, and rejects an expired or superseded owner. PostgreSQL parent/lease locks serialize resource, packet hash, owner, epoch, expiry, and revocation checks with a same-database synthetic receipt effect. Canonical `ActionIntent.input_revision_hash` binds the artifact, effective input, configuration, evidence, toolchain, builder, and reviewer identifiers; `VerificationReceipt` targets the exact intent hash. Extensions remain observational.

Acceptance evidence must distinguish the successful path, stale-owner refusal, changed-artifact refusal, and revoked-authority refusal. Synthetic reviewer identifiers exercise independence checks but do not claim an actual model performed a semantic review. Pure adapter admission/normalization fixtures establish only their tested rules. This increment does not qualify remote effects, native launch/resume/cancellation, a distinct-service-identity boundary, provider entitlement, or production reliability.

The [implementation evidence and reproduction commands](../../../evidence/dual-consul-v4/implementation/README.md) identify the opt-in consumer, real PostgreSQL proof, and remaining activation boundaries.

Activation progresses through local development, shadow without external effects, staging, an authorized canary, and operations. Each transition requires versioned bindings, comparable metrics, evidence for the required capabilities, and rollback to the prior binding. Rollback does not revive revoked ownership or authorization. Pro hosts the authoritative broker; Air-M5 remains a thin client; Mini runs executors only where required and qualified. Host eligibility is verified independently, never inferred from another host's configuration.

## Design provenance

The [evidence manifest](../../../evidence/dual-consul-v4/design/manifest.json) verifies three Fable assistant text blocks from native session `433c29dd-e09f-4070-b1e9-a8da0136970c`, with `message.model=claude-fable-5-1` and runtime `2.1.261`. The final response accepts the design with five corrections. This is historical design review, not review of the implementation.

[Astra](astra-native.md), [Claude](claude-native.md), and the [five adapters](adapters.md) specify their own surfaces. Selected original tool outputs preserve the other-family contributions and their metadata. Four original answer hashes match the packet; Gemini's selected response has its own computed hash because its original stdout bytes are unavailable. Remaining observation gaps are explicit. No consultation is presented as a comparable benchmark.
