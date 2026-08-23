---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 11 — WR3 Video Foundry

**Wave:** 2
**Depends on:** Packets 03, 04, 06, 12, and 18
**Feeds:** Packets 13 and 14
**Risk:** high cost and media-quality risk; external publication is manual

## Session prompt

You own WR3 as an industrial production service. The Conductor supplies the editorial lock; WR3 reliably turns it into a cost-bounded, rights-aware, identity-consistent, claim-grounded video package. Do not make WR3 an autonomous topic or narrative authority.

You are not alone in the codebase. Work in a dedicated worktree, declare exact files and asset directories, preserve concurrent work, and never delete or overwrite existing episode artifacts. Do not spend Flow credits or publish without explicit owner authorization. No PII or protected OSINT enters Veo or another cloud model.

## Mission

Produce repeatable platform-ready video variants from one locked `ContentObject`, with a complete `MediaManifest`, durable workflow state, bounded retries and credits, independent quality gates, and a manual publication stop.

## Baseline to refresh

Packet 03 must have proved connectivity, typed dispatch, idempotency, fail-closed budget/authority gates, and a zero-spend dry run. It does not authorize or execute a paid pilot. Recheck those gates, then inventory complete versus incomplete historical episodes, cost per accepted clip, retry causes, identity scores, audio/transcript/LUFS results, manifest completeness, variant success, and manual interventions.

Relevant primary paths include:

- `scripts/wr3_render_episode.py`
- `scripts/wr3_supervisor.py`
- `scripts/wr3_flowkit_client.py`
- `scripts/wr3_episode_manifest.py`
- `scripts/wr3_arcface_verify.py`
- `scripts/wr3_veo_audio_extract.py`
- `scripts/wr3_ffmpeg_wrapper.py`
- WR3 prompt/gate/telemetry/reflexion code and focused tests
- `docs/wr3/contracts/**`

Do not own topic discovery, NAGA truth, public publishing, or the operator's final creative decision.

## Inputs and frozen contracts

- Exact operator-approved `ContentObject` with topic and Creative Lock plus full `{risk_class, sensitivity}` classification.
- Exact reviewed claim and evidence references.
- `MediaManifest` and immutable `WorkflowRun` coordination snapshots.
- For every paid Flow/Veo submission: exact `RequestedActionSpec`, `ActionItem`, `ActionIntent`, unexpired effect-specific `ApprovalReceipt`, immutable started `ExecutionAttempt`, and terminal `OperationalReceipt`.
- Packet 03 health and live-credit budget contract.
- Green/amber/red policy; red content cannot enter cloud rendering.
- Only public, policy-approved minimized input may enter Veo. Any distinct lower-sensitivity output requires a purpose- and destination-bound `SanitizationReceipt` indexed by the exact output hash. Editorial, Topic Lock, or Creative Lock approval never authorizes spend.

## Deliverables

1. One typed episode input contract and immutable `media_script_lock`/`media_shot_lock` specializations, each with exact hashes and a separate canonical `ApprovalReceipt` using the corresponding registered subject kind.
2. Shot-to-claim bindings and asset intent preserved through Veo prompts, clips, assembly, captions, and variants.
3. Durable state machine for dispatch, retry, repair, assembly, critic, staging, and terminal failure.
4. Per-shot budget reservation, actual credit accounting, bounded retry policy, and circuit breaker.
5. Complete `MediaManifest`: prompt/model/tool versions, asset hashes, rights, identity references, timeline, transcript, subtitles, audio metrics, quality receipts, and variants.
6. Independent gates for claim/legal fidelity, identity, cliche/brand, transcript match, sync, LUFS, safe zones, licenses, and manifest completeness.
7. Deterministic assembly first; LLM diagnosis only for ambiguous failures.
8. Explicit degradation policy: a variant may fail while a valid master survives; a broken master is a hard fail.
9. Manual publish staging with no outward side effect.
10. Exact action-chain enforcement around every paid submission and retry. A retry is a new numbered `ExecutionAttempt`; an existing approval covers it only when the exact bounded retry policy, inputs, maximum spend, authorized effects, and expiry already bind that retry. Otherwise a new `ActionIntent` and approval are required.

## Non-goals

- Do not let WR3 choose topics or rewrite locked claims without a new approval.
- Do not optimize for maximum episode volume.
- Do not install rendering infrastructure on Air-M5.
- Do not treat `gateway_process=true` as render readiness.
- Do not permit unlimited retries or estimate credits from stale contract constants.
- Do not publish to TikTok, Instagram, YouTube, or Facebook.

## Implementation sequence

1. Freeze ten historical/synthetic episode briefs and classify failures from existing artifacts.
2. Normalize script, shot, and manifest contracts with Packet 04 adapters.
3. Make every state transition durable and idempotent.
4. Bind claims and creative intent to shots and output timestamps.
5. Enforce the exact Packet 12 action chain, budget reservation, per-attempt receipt, retry, and circuit-breaker logic before the first paid invocation.
6. Integrate deterministic and independent quality gates on final assets.
7. Shadow dry-run ten episodes without spend.
8. With an exact unexpired action approval, canary one short episode, then a small diverse batch only if every paid submission and retry remains a named, bounded effect within the authorized total ceiling.
9. Record operator interventions and outcome telemetry hooks.

## Golden set and adversarial cases

Include ten episodes spanning presenter, b-roll, regulatory numbers, bilingual terms, native audio, fallback audio, multiple transitions, a failed variant, and a complete hard-fail case.

Adversarial cases:

- duplicate dispatch;
- live credits lower than reserved budget;
- partial clip completion and restart;
- wrong identity with good aesthetic quality;
- transcript semantically altered while WER appears acceptable;
- claim changed after shot lock;
- red/sensitive input;
- sensitivity missing or lowered without a valid destination-specific `SanitizationReceipt`;
- editorial or Creative Lock approval incorrectly presented as spend approval;
- retry outside the approved input, effect, retry-count, expiry, or credit bindings;
- missing license;
- same anchor silently reused as a generated result;
- three variants succeed and one fails;
- master assembly fails.

## Tests and exit criteria

- contract/state/idempotency/replay tests;
- cost ceiling and retry property tests;
- identity, transcript, sync, loudness, safe-area, and manifest tests;
- privacy, classification-axis, sanitization, and red-content rejection tests;
- missing/mismatched action-chain tests, including content approval mistaken for spend approval and retry outside exact bindings;
- restart-from-every-state simulation;
- complete E2E dry run and authorized paid canary.

Exit only when duplicate jobs are zero; every paid invocation and retry has a unique immutable started attempt plus typed terminal receipt bound to an exact unexpired action approval; every accepted asset has provenance, rights, and both classification axes; any lower-sensitivity derivative has a valid destination-specific sanitization receipt; actual spend stays within the authorized ceiling; all critical claims remain bound and supported; the master and required variants meet declared gates; every degradation is explicit; recovery works from injected failures; an independent critic passes the final media; and publication remains manual.

## Rollback

Keep the previous manual production path and all feature flags. Stop new submissions on credit, identity, privacy, or manifest anomalies. Preserve partial assets and workflow history; never delete them to make a retry appear clean. Roll back consumers without altering locked input objects.

## Reviewer handoff

Provide episode input hashes, state trace, credit ledger, clip/variant hashes, full manifest, independent gate results, failure injection report, operator interventions, and proof of the manual publish stop.
