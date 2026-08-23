---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 03 — WR3 and FlowKit Activation

**Wave:** 0
**Unlocks:** Work Packet 11
**Risk:** medium operational risk, zero-credit activation, no publication
**Execution mode:** Pro is the render host; Air-M5 is the control surface

## Session prompt

You are the execution session responsible for proving that WR3 can complete a typed, traceable, zero-spend activation path through FlowKit up to—but never including—a Veo submission. This is an activation and contract-repair packet, not a redesign of WR3 editorial judgment or a paid production pilot.

You are not alone in the codebase. Create a dedicated worktree, declare the files you will own, preserve concurrent work, and never reset or revert unrelated changes. Do not merge, deploy, publish, or enable a production handoff without explicit owner approval. Never send PII or protected OSINT into Flow/Veo.

## Mission

Make the following statement empirically true:

> From Air-M5, the operator can see whether the Pro gateway, Chrome extension, Flow session, and credits are separately healthy; exercise one approved non-sensitive episode through a typed no-spend dispatch simulation; prove that budget and authority gates fail before Veo; receive a complete simulated workflow trace and manifest fixture; and hand the paid pilot to Packet 11.

## Live baseline to refresh before editing

- The WR3 supervisor is installed and has been alive, but recent telemetry contains fixtures rather than complete production episodes.
- The WR2-to-WR3 emitter is feature-flagged off.
- The router declares `wr2_episode_published`, while the supervisor prompt builder does not recognize that channel; arming the route can therefore produce an acknowledged no-op.
- FlowKit's gateway process can be alive while `extension_connected=false`; the credits endpoint then returns 503.
- The current cost contract and observed client cost disagree. Runtime estimates must use live credits and the actual per-clip charge.
- Air-M5 already has a persistent tunnel to Pro ports 8100 and 9222, but the operator must manually load the unpacked extension and open/refresh Google Flow. Browser automation must not bypass Chrome's protected extension page.

Record the refreshed process state, endpoint responses, route flags, recent episode directories, complete/incomplete manifest counts, and available credits without exposing tokens.

## File ownership

Primary ownership is limited to:

- `scripts/wr3_supervisor.py`
- `scripts/wr3_companion_dispatcher.py`
- `scripts/wr3_flowkit_client.py`
- `docs/wr3/contracts/_router.yaml`
- WR3 cost/companion contract files directly required to remove the credit mismatch
- new or existing focused tests under `scripts/tests/test_wr3_*`
- a new activation runbook under `docs/wr3/`

The session may inspect but must not redesign WR3 skills, WR2 editorial planning, post assembly, or publication code. Changes to shared event schemas require the Packet 04 contract or an adapter local to WR3.

## Inputs and frozen contracts

- `IntelEvent` for the trigger and delivery receipt.
- Exact `ContentObject` for topic, creative, claim, risk, and sensitivity bindings.
- `MediaManifest` fixture for every simulated output.
- `WorkflowRun` as an immutable coordination snapshot only; it cannot authorize an action or stand in for an `ExecutionAttempt` or terminal `OperationalReceipt`.
- Green/amber/red plus sensitivity policy: the dry run uses only public green or wholly synthetic inputs; no NEXUS-derived material.
- Human publication gate remains mandatory.

## Deliverables

1. A four-dimensional health response: `gateway_process`, `browser_extension`, `flow_session`, and `credits`, each with a timestamp and actionable failure reason.
2. An explicit handler for `wr2_episode_published` that invokes the intended companion dispatcher or rejects before ACK; unknown channels never succeed silently.
3. One source of truth for runtime cost: observed/live credit price, estimated clip count, reserve, hard ceiling, spent credits, and reason for variance.
4. Idempotent dispatch keyed by content object and episode ID.
5. A complete simulated `WorkflowRun` revision chain and `MediaManifest` fixture, including injected failures and retries, with an explicit `simulated=true` marker and zero real media claims.
6. A safe operator runbook for Air-M5 tunnel checks, manual Chrome extension load, Flow session verification, dispatch, monitoring, stop, and rollback.
7. A no-spend dry run that exercises every step except Veo submission and proves from before/after credit observations that it consumed zero credits.
8. A typed handoff contract for Packet 11's paid pilot. It requires an exact `RequestedActionSpec`, `ActionItem`, `ActionIntent`, unexpired effect-specific `ApprovalReceipt`, immutable started `ExecutionAttempt`, and terminal `OperationalReceipt` before any paid submission.

## Non-goals

- Do not change topic discovery, script style, shot aesthetics, or the WR3 agent roster.
- Do not turn on the general WR2-to-WR3 feature flag.
- Do not install heavy services or rendering tools on Air-M5.
- Do not automate `chrome://extensions` or browser sign-in.
- Do not submit any Veo job, spend credits, create a real execution attempt, or publish to any external platform in this packet.

## Implementation sequence

1. Snapshot the live topology and distinguish gateway health from render readiness.
2. Reproduce the unrecognized-channel path with a fixture and make the test fail.
3. Repair dispatch so every accepted channel has one typed handler and one terminal receipt.
4. Unify cost accounting around live/observed credits and fail closed when credits are unavailable.
5. Add idempotency and replay tests without any real submission.
6. Run the no-spend dry run from Air-M5 through the Pro tunnel.
7. Pause for the operator's manual extension/Flow action if required.
8. Prove that the Veo boundary rejects a missing or mismatched canonical action chain and that the no-spend path consumed zero credits.
9. Freeze the paid-pilot handoff for Packet 11, including exact authority bindings, retry policy, maximum spend, expected receipt types, and the manual publish stop.

## Golden set and adversarial cases

At minimum cover:

- recognized WR3 channel;
- `wr2_episode_published` channel;
- unknown channel;
- duplicate delivery/replay;
- gateway up, extension down;
- extension up, Flow session expired;
- credits unavailable;
- credits lower than estimated reserve;
- simulated clip transient failure and bounded retry;
- manifest incomplete;
- attempted red/sensitive content dispatch;
- any paid submission or retry without the exact canonical action chain.

## Tests and evaluation

- Focused supervisor/router/companion contract tests.
- Cost-ceiling tests using at least two possible empirical per-clip prices.
- Idempotence and outbox replay tests.
- Dry-run E2E with zero Flow spend.
- Negative tests proving that no real submission or `ExecutionAttempt` can start in Packet 03.
- Independent inspection of the typed trace, simulated asset hashes, claim bindings, manifest completeness, and before/after credit proof.

## Shadow, canary, and exit criteria

Shadow all WR2 handoff events without submission for at least one normal operating window. Packet 03 has no paid canary; Packet 11 owns the first paid pilot after Packets 12 and 18. The global handoff flag stays off.

The cost ceiling is a hard invariant for every future submission and retry, independent of estimator quality. Estimator accuracy is reportable only after a preregistered `MetricProfile` covers at least ten accepted clips across at least three distinct Packet 11 jobs. Before that floor, report `insufficient_evidence`. Packet 03 may validate only price discovery, arithmetic, and fail-closed behavior; it cannot validate the estimator. An explained variance never waives the ceiling.

Exit only when:

- no recognized route resolves to a no-op;
- duplicate delivery causes zero Flow jobs;
- health reports identify the failing layer correctly;
- every simulated job and retry is rejected before spend when authority or budget bindings are absent or wrong;
- the dry run consumes zero credits and yields a valid simulated workflow trace and manifest fixture;
- the Packet 11 handoff names the exact canonical action chain and a predeclared hard credit ceiling for every future submission and retry;
- no external publication occurs;
- an independent reviewer issues `PASS` or `PASS_WITH_LIMITS`.

## Rollback

Keep the handoff feature flag off, preserve the old manual dispatch command, and make every new handler disableable. If the dry run reaches the Veo boundary, changes credits, loses identity/claim integrity, or produces incomplete simulated receipts, stop the run, retain sanitized traces for diagnosis, and restore the previous route table without deleting run history.

## Reviewer handoff

Provide the independent reviewer with the before/after route matrix, sanitized endpoint-health output, cost calculation, test output, simulated manifest and asset hashes, the Packet 11 paid-pilot handoff, before/after credit evidence, and statements proving that no Veo job, credit spend, or publication occurred.
