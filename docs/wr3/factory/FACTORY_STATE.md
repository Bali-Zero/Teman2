# Zantara Video Factory — Current State

- updated_at_utc: `2026-08-31T00:14:37Z`
- machine: `Air-M5`; Flow dispatch, ArcFace, media QA, and eventual ffmpeg work route to Pro.
- branch: `agent/air-m5/wr3/zantara-video-factory-v3`
- worktree: `/Users/balizero/nuzantara/.worktrees/wr3-zantara-video-factory-v3`
- objective: operate one resumable WR3-based factory whose stages remain coherent while every creative decision can produce a materially different result.
- factory_phase: `E13_M02_V05_CLIP_QA_REQUIRED`
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

`M02` resolves the identity-preserving scene-start gate. It does not reopen the closed four-variant sweep: `M02-v05` is a separately authorized method canary that reuses the narrative beat while changing the scene-start construction and motion metaphor. The workflow-backed MP4 has now been recovered without regeneration; content and identity QA remain open.

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
- identity, motion, composition, lip-sync, and native-audio content QA: `NOT_RUN`
- canary verdict: unset

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
- `docs/wr3/factory/episodes/s01e13-residency-permit/cinematic-research.md`

## Completed Gates

- `BOOT_AUDIT`
- `EDITORIAL_COUNCIL_WAVE_1`
- `EDITORIAL_CONSOLIDATION`
- `EDITORIAL_SOURCE_PASS`
- `EDITORIAL_COUNCIL_WAVE_2`
- `EDITORIAL_FINAL_CURATION`
- `E13_PILOT_TOPIC_APPROVAL`
- `E13_CREATIVE_LOCK`
- `E13_F01_V01_REVIEW`
- `E13_F01_V02_REVIEW`
- `E13_SCENE_START_PIPELINE_REPAIR`
- `E13_F01_V03_STILL_GATE`
- `E13_F01_V04_PRE_RENDER_GATE`
- `E13_F01_V04_STILL_GATE`
- `E13_F01_FAMILY_DECISION`
- `E13_M01_DUAL_REFERENCE_STILL_GATE`
- `E13_M02_IDENTITY_PRESERVE_EDIT_GATE`
- `E13_M02_V05_PRE_RENDER_GATE`
- `E13_M02_V05_VIDEO_GENERATION`
- `E13_M02_V05_MEDIA_RECOVERY`
- `E13_M02_V05_STRUCTURAL_MEDIA_QA`

## Earliest Open Gate

`E13_M02_V05_CLIP_QA_REQUIRED`

The scene-start transfer problem is solved and the existing workflow-backed asset is recovered. No creative conclusion is valid until the actual clip passes identity and content QA.

The next bounded action is:

1. do not generate, retry, extend, or upscale;
2. run multi-frame real ArcFace identity measurement on the recovered MP4;
3. inspect motion, composition, accidental text/UI/borders/reflections, and the intended inertia-stop metaphor;
4. inspect native audio and lip sync, then measure its levels under the existing gate;
5. set the first honest canary verdict;
6. review and activate the cross-pair gateway fix separately before any future workflow-aware recovery.

Do not open `f02`–`f06`, submit another M02/f01 generation, enter legal scripting, publish, deploy, or send outward messages before this gate resolves.

## Verification and Resume Reads

- `docs/wr3/factory/episodes/s01e13-residency-permit/context-snapshot.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/creative-lock.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/probe-plan.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/f01-family-decision.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m02-v05-generation-result.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/cinematic-research.md`
- `docs/superpowers/specs/2026-08-31-zantara-e13-creative-divergence-design.md`
- `docs/superpowers/plans/2026-08-31-zantara-e13-camera-probe-plan.md`

## Definition of Done for the Current Gate

- `[x]` stable-step/divergent-output design persisted
- `[x]` root and first child creative signatures recorded with the historical M02 timing limitation disclosed
- `[x]` one-shot probe runner and scene-start lineage contracts implemented
- `[x]` v01–v04 fully accounted and reviewed
- `[x]` no retry hidden as retrieval or QA recovery
- `[x]` f01 closed honestly without selecting a decorative or wrong-identity result
- `[x]` identity-preserving scene-start method passes all gates
- `[x]` exactly one M02-v05 video generation completed and its Flow IDs are durable
- `[x]` workflow-aware, no-resubmit media recovery path implemented and tested
- `[x]` existing M02-v05 MP4 recovered and structural media properties verified
- `[ ]` live FlowKit gateway rejects mismatched workflow/media pairs and returns identifiers derived from the selected payload
- `[ ]` one scene-first f01 canary clip passes identity, motion, composition, audio, and technical QA
- `[ ]` winning cinematic grammar selected
- `[ ]` legal grounding and final script completed
- `[ ]` human-reviewed episode master staged; publication remains a separate manual action
