# Zantara Video Factory — Current State

- updated_at_utc: `2026-09-02T02:17:46Z`
- machine: `Air-M5`; Flow dispatch, ArcFace, media QA, and eventual ffmpeg work route to Pro.
- branch: `agent/air-m5/wr3/zantara-video-factory-v3`
- worktree: `/Users/balizero/nuzantara/.worktrees/wr3-zantara-video-factory-v3`
- objective: operate one resumable WR3-based factory whose stages remain coherent while every creative decision can produce a materially different result.
- factory_phase: `CANARY_DESIGN_APPROVAL_REQUIRED`
- season_gate: `TOPIC_APPROVAL_REQUIRED`; only `C07` is approved as a bounded pilot.
- episode_queue: `[S01E13]`
- topic: `What Your Residency Permit Does Not Come With`
- thesis: `Continuity of movement, discontinuity of rights.`
- publication_allowed: `false`
- control_plane: `scripts/cli/factory`; persisted episode state is separate from this R&D probe ledger.

## Creative Operating Rule

- The state machine, gates, evidence formats, and safety thresholds stay stable.
- Creative conclusions do not. Each authorized reasoning pass receives the immutable episode context plus diagnosed failure evidence, then receives a fresh child seed and must produce a new spatial or temporal idea.
- Mechanical prompt expansion, retrieval, hashing, raster checks, and identity measurement use no creative reasoning pass.
- A failed result may change the next creative input, but it never triggers an automatic retry.
- A fifth variant is not a disguised reroll: it requires a diagnosed failure, a new declared axis, and an explicit child creative seed.
- Every future child signature must be recorded in the originality ledger before a paid generation call. M02-v05 was backfilled after generation and is retained as an explicit historical process gap, not rewritten as a pre-spend gate.

## Episode Lock

- creative_seed_id: `9fc9b711-be3b-45f8-9de0-fe4a7c99264e`
- identity: exact `A007`
- canonical wardrobe: ivory silk blouse with restrained gold embroidery
- format: native vertical `9:16`, `720x1280`, `24 fps`, `8 s`, native audio
- grammar: apparent oner through motivated occlusion and match-on-action; motion → compression → stasis; warm certainty → mixed ambiguity → neutral clarity; dry footstep/click/latch sound motifs with J/L bridges.
- banned shortcuts: airports, passport/stamp imagery, literal labelled doors, floating documents, generated text, technical overlays, tourist-postcard Bali filler, and silent reuse of an old hero or start frame.
- factual boundary: camera probes contain no implementation-specific legal claim. Legal grounding and final scripting remain downstream gates.

## f01 Original Four-Variant Sweep — Closed Without Winner

The four predeclared f01 variants are exhausted. Two clips and two scene-start stills were generated; there were zero automatic retries.

| Variant | Paid artifact                                      | Identity                       | Creative result | Diagnosis                                                                        |
| ------- | -------------------------------------------------- | ------------------------------ | --------------- | -------------------------------------------------------------------------------- |
| `v01`   | one video, 10 credits                              | avg `0.692833`, min `0.635646` | FAIL            | fake camera UI, technical labels, bars, and reference-presentation framing       |
| `v02`   | one video, 10 credits                              | avg `0.656854`, min `0.597734` | FAIL            | raw portrait opening plus inverted lower panel and hard seam                     |
| `v03`   | one generated still, zero measured debit; no video | `0.282873`                     | REJECT          | clean scene, wrong woman                                                         |
| `v04`   | one generated still, zero measured debit; no video | `0.558037`                     | REJECT          | clean scene and canonical wardrobe, but below the exact `0.600` unlock threshold |

Accounting at f01 closure:

- Flow credits: `12530` before v04 still and `12530` after.
- measured video-probe spend: `20` of the authorized `240` credit cap.
- image generation calls: `2`.
- video generation calls: `2`.
- automatic retries: `0`.
- v04 video generation calls: `0`.
- uploads, publications, deployments, and outward messages: `0`.

Latest v04 evidence:

- Flow project: `afab29a9-f27f-4cd7-9953-3dee4a441df2`
- Flow video shell: `6c6a8cb0-17aa-48e6-90c2-d7b1dfda22dd`
- uploaded A007 media: `3b2029b3-762f-47b8-a17c-31e9b7b68400`
- generated still media: `29dd6ddf-e6d5-4ab7-aa64-75cfdcf9fa35`
- normalized still on Pro: `/Users/nuzantara/nuzantara/apps/war-room/output/episode/s01e13-residency-permit-probes-f01-v04/assets/f01-v04-scene-start.png`
- normalized still SHA-256: `afaf0482a2c631d84d77aa9276586cf447b046314da52ca21c67b95d7782efa5`
- raster/composition: PASS; one visible person, coherent edge-to-edge world, no text/UI/bars/seam/reflected duplicate.
- real ArcFace: one face, cosine `0.558037281036377`, verdict `REJECT`.
- no video scene was created and no v04 video was submitted.

Canonical decision files:

- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/f01-v04-rejection.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/f01-family-decision.json`

## Identity-Preserving Scene-Start R&D — Resolved

Two materially different methods were tested once each, with no automatic retry:

| Method                                                     | Paid artifact                                         | Identity                    | Decision                            |
| ---------------------------------------------------------- | ----------------------------------------------------- | --------------------------- | ----------------------------------- |
| `M01` Flow dual-reference scene generation                 | one generated image; no video                         | one face, cosine `0.499623` | `HARD_FAIL`; closed                 |
| `M02` identity-preserving edit of the approved composition | one generated image, then one authorized video canary | one face, cosine `0.789691` | scene start `PASS`; video generated |

`M02` resolved the identity-preserving scene-start gate. It did not reopen the closed four-variant sweep: `M02-v05` was a separately authorized method canary whose recovered MP4 received a final `FAIL` and was rejected by the operator on 2026-09-02.

The M02-v05 creative pass is now registered as child seed `4ac7cfe1-1a72-5c7e-a6a3-c0a367d0022b`. Its deterministic comparison against the root reports ten material differences, including five conceptual and five cinematic axes, with description Jaccard `0.1`. This is a post-generation backfill: it proves the stored signatures differ under the current policy, but it did not protect the historical spend. The linked receipt preserves that limitation and makes pre-spend registration mandatory for every future child.

## M02-v05 Existing Video — Recover, Never Regenerate

- generation status: `SUCCESSFUL`
- generation calls: `1`
- automatic retries: `0`
- project: `08c2c96a-7983-4f8b-a41e-b3afe3a68e3b`
- video shell: `648a1e43-fae8-4d2a-a825-f6a2c31225b0`
- scene: `84bab0e9-5b86-497f-bb7f-d989f505dce3`
- workflow: `806283d2-a2f8-477d-a327-2a29d313d331`
- output media: `b8f6f600-5093-4edf-bcb3-e5383df76c3e`
- Flow status: project `COMPLETED`; media `MEDIA_GENERATION_STATUS_SUCCESSFUL`
- retrieval status: `RECOVERED`; no regeneration and no retry.
- MP4 on Pro: `/Users/nuzantara/nuzantara/apps/war-room/output/episode/s01e13-residency-permit-probes-m02-video-canary/clips/105.mp4`
- operator copy: `/Users/balizero/Desktop/What Your Residency Permit Does Not Come With.mp4`
- MP4 SHA-256: `bce06c5371dd96b0d63a4cc98b09f9ab41473c4a65f400d58b4ea9cda016bfe9`; size `3118995` bytes.
- structural media QA: `PASS`; H.264 `720x1280`, `24 fps`, `8.000 s`, AAC stereo `48 kHz`.
- visual/identity QA: `FAIL`; ArcFace average `0.629521`, minimum `0.549607` below hard floor `0.55`; composition and visual no-overlay checks pass, but locked-camera motion and the intended inertia-stop metaphor fail.
- native-audio QA: `FAIL`; silent subject and structural A/V sync pass, but raw loudness `-17.8 LUFS`, true peak `-0.16 dBTP`, quiet-room-tone match, and timbre continuity fail.
- canary verdict: `FAIL`; operator decision: `REJECT`; automatic retry remains forbidden.

The recovery client is implemented and tested to require exact project/workflow/media matching, accept only an encoded payload or an allowlisted Google media URL, validate the MP4 in a durable staging file, and publish the destination atomically. Recovery contains no generation call. A persistent non-blocking file lock serializes the full recovery state transition, and the receipt endpoint is restricted to the literal loopback FlowKit gateway on port `8100`.

The general FlowKit client now also persists a no-resubmit receipt at every paid dispatch boundary, locks real-mode shot and pack execution, treats an unavailable post-dispatch response as ambiguous rather than retryable, validates the local gateway before I/O, and downloads signed media only through capped, manually validated redirects. These local contracts are covered by the complete WR3 script suite; they do not change the separate live-gateway activation blocker below.

The current live gateway handler is still not trusted as proof of arbitrary workflow/media tuples. Review found that it could select a media object by `media_id` while independently accepting a different `workflow_id`, then echo the requested identifiers. A fail-closed fix and cross-pair regression tests exist in the separate FlowKit repository as local Pro commit `ff56766` on branch `codex/fix-exact-workflow-media-binding`; it remains unmerged and inactive. This is retained infrastructure debt, but it no longer blocks QA of the already recovered immutable MP4.

Current measured accounting:

- live Flow credits before M02-v05: `12530`
- live Flow credits after M02-v05: `12520`
- observed global account-balance change around M02-v05: `10`
- submitted/accounted M02-v05 clip cost: `10`
- submitted/accounted video-probe spend: `30` of the authorized `240` credit cap
- video generation calls across the pilot: `3`
- automatic retries: `0`
- publications, deployments, and outward messages: `0`

The historical M02-v05 ledger row used the old `20`-credit client default. The contemporaneous global account balance moved by `10`, matching the explicit `10`-credit clip-cost parameter, but a balance delta is an account-wide observation rather than workflow-specific billing proof. The runner and client now propagate the explicit clip-cost parameter into the ledger and label the live delta with this global scope.

Canonical result:

- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m02-v05-generation-result.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m02-v05-originality-link.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m02-v05-visual-identity-qa.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m02-v05-native-audio-qa.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m02-v05-canary-verdict.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m02-v05-operator-decision.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/cinematic-research.md`

## M03-v06 Zero-Spend Redesign — Awaiting Human Approval

- declared axis: `ONE INPUT, ONE CIRCUIT`; Zantara presses one unlabelled brass switch, one of four practical lights activates, and the other three remain dark.
- camera: rigid fixed three-quarter 50 mm tableau; stationary reach, press, withdraw, hold; exact A007 remains unobstructed and near-frontal.
- originality: pre-spend `PASS`; seed `849da09a-e9fc-5caf-9567-7e9ffcf8fc6a`; signature `9f12f8f0b4a65d13a3523971b4dee52107ea63c550f7713882463c114951e3fa`; ledger sequence `3`.
- independent pre-render verdict: `PASS` for design eligibility only.
- current redesign spend: `0`; generation jobs, retries, extensions, and upscales: `0`.
- future ceiling only after explicit approval and fresh live preflight: exactly one canary, maximum `10` Flow credits, no retry, extension, or upscale; projected episode accounting `40/240`.
- Flow dispatch, clip rendering, and any authorization artifact remain closed.
- canonical files: `originality-m03-v06-{request,receipt}.json`, `m03-v06-canary-design.json`, and `m03-v06-independent-pre-render-gate.json` in the episode directory.

## Completed Gates

- editorial: `BOOT_AUDIT`; both council waves; consolidation, source pass, final curation; `E13_PILOT_TOPIC_APPROVAL`; `E13_CREATIVE_LOCK`.
- f01: v01/v02 review; scene-start repair; v03/v04 still gates; v04 pre-render; family decision.
- M01/M02: dual-reference still gate; identity-preserve edit gate; M02-v05 pre-render, generation, recovery, structural, visual/identity, and native-audio QA.
- decisions: `E13_M02_V05_CANARY_REJECTED`; `E13_M03_V06_ORIGINALITY_PRESPEND_GATE`; `E13_M03_V06_PRE_RENDER_DESIGN_GATE`.

## Earliest Open Gate

`CANARY_DESIGN_APPROVAL_REQUIRED`

The rejected M02-v05 is closed. M03-v06 is original, bounded, and pre-render eligible, but this does not authorize spend. The next action is human review of the design. Do not call Flow, generate, retry, extend, upscale, normalize or replace audio, open `f02`–`f06`, enter legal scripting, publish, deploy, or send outward messages before an exact authorization resolves this gate. Any future dispatch also requires a fresh live balance check, the daily circuit breaker, and authorization bound to the reviewed design hash.

## Verification and Resume Reads

- `docs/wr3/factory/episodes/s01e13-residency-permit/context-snapshot.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/creative-lock.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/probe-plan.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/f01-family-decision.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m02-v05-generation-result.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m03-v06-canary-design.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m03-v06-independent-pre-render-gate.json`

## Definition of Done for the Current Gate

- `[x]` stable-step/divergent-output design persisted
- `[x]` root and first child creative signatures recorded with the historical M02 timing limitation disclosed
- `[x]` v01–v04 fully accounted and reviewed
- `[x]` no retry hidden as retrieval or QA recovery
- `[x]` f01 closed honestly without selecting a decorative or wrong-identity result
- `[x]` identity-preserving scene-start method passes all gates
- `[x]` exactly one M02-v05 video generation completed and its Flow IDs are durable
- `[x]` workflow-aware, no-resubmit media recovery path implemented and tested
- `[x]` existing M02-v05 MP4 recovered and structural media properties verified
- `[x]` visual/identity and native-audio QA executed against the immutable recovered MP4
- `[x]` first honest canary verdict recorded as `FAIL` with zero new Flow spend
- `[x]` failed M02-v05 canary rejected by the operator with no automatic retry
- `[x]` M03-v06 design registered for originality and independently cleared for human review with zero spend
- `[ ]` live FlowKit gateway rejects mismatched workflow/media pairs and returns identifiers derived from the selected payload
- `[ ]` one scene-first f01 canary clip passes identity, motion, composition, audio, and technical QA
- `[ ]` winning cinematic grammar selected
- `[ ]` legal grounding and final script completed
- `[ ]` human-reviewed episode master staged; publication remains a separate manual action
