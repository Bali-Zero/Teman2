# Zantara Video Factory — Current State

- updated_at_utc: `2026-09-02T04:20:58Z`
- machine: `Air-M5`; Flow dispatch, ArcFace, media QA, and eventual ffmpeg work route to Pro.
- branch: `agent/air-m5/wr3/zantara-video-factory-v3`
- worktree: `/Users/balizero/nuzantara/.worktrees/wr3-zantara-video-factory-v3`
- objective: operate one resumable WR3-based factory whose stages remain coherent while every creative decision can produce a materially different result.
- factory_phase: `OWNER_VISUAL_REVIEW_REQUIRED`
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
- root canonical wardrobe: ivory silk blouse with restrained gold embroidery; explicitly superseded for the owner-authorized M04/M05 child by the `Midnight Petrol Column` outfit lock.
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

## M03-v06 Authorized Canary — Ambiguous Dispatch, No Resubmit

- declared axis: `ONE INPUT, ONE CIRCUIT`; Zantara presses one unlabelled brass switch, one of four practical lights activates, and the other three remain dark.
- camera: rigid fixed three-quarter 50 mm tableau; stationary reach, press, withdraw, hold; exact A007 remains unobstructed and near-frontal.
- originality: pre-spend `PASS`; seed `849da09a-e9fc-5caf-9567-7e9ffcf8fc6a`; signature `9f12f8f0b4a65d13a3523971b4dee52107ea63c550f7713882463c114951e3fa`; ledger sequence `3`.
- independent pre-render verdict, live Flow preflight, and design-hash-bound operator authorization: `PASS`; authorized envelope was exactly one job, maximum `10` credits, zero retry/extension/upscale/extra image generation.
- a supplemental execution-only seeded request produced `IDEMPOTENT_REPLAY`; the originality ledger hash remained `91093002743974527626f859ded33f54bdaa843b2075eb5dc26f308593aad7fd`. Design hash `3b27de1b2b370b02188178811763703d4a967a9d9fb59e98aa6efa748ac1b27f` did not change.
- the charged dispatch boundary was crossed exactly once. Flow IDs: project `fdc15b64-a422-4ca0-9a1a-9fb5bd7575d9`, video `1fced626-0607-4db6-a870-1afa1eab7bcb`, scene `acc74ab1-4bcd-4d9b-bac6-74e6630acc24`, anchor media `668bc5f5-b211-4fd7-aa1f-6d3138485666`.
- submit result: ambiguous `HTTP 403`; exact-ID recovery observed scene `PENDING` with no workflow, media, URL, or MP4. No second generation call was made.
- accounting observation: Flow balance `12550 → 12550`, delta `0`, and no new credit-ledger row; exact charge remains formally ambiguous because the dispatch boundary was crossed.
- QA: not run because no MP4 exists. Retries, extensions, upscales, extra image generations, assembly, publication, deployment, and outward messages: `0`.
- canonical result: `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m03-v06-flow-dispatch-result.json` (SHA-256 `e2818feb7f34d4c0b9f7c42f53be673b509f75f719c77d9448183cd779840d22`).

## M03-v06 Tier Rebound — Generated, Then Rejected by Owner

- The original `403` was diagnosed as a paygate mismatch: the Ultra account requires `PAYGATE_TIER_TIER1P5`.
- One corrected generation completed: Flow balance `12550 → 12540`, observed delta `10` credits; no automatic retry.
- Flow IDs: project `1c2ad889-75ee-4e37-a074-823ac79125f9`, video `d3c3e6dd-dcb6-4a5c-ae2b-f80292983cee`, scene `f5f80ddf-19f2-4a98-a954-d1c897caced0`, workflow `330a5e71-ac1b-43d4-bd0f-f8371f6764b1`, media `21e2f741-34b8-4065-ba69-7bed92d50590`.
- The owner rejected the result as visibly composited because the raw A007 portrait had been used as the start image. It is ineligible for recovery, extension, upscale, assembly, publication, or reuse.
- Canonical rejection: `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m03-v06-owner-visual-rejection.json`.

## M04-v07 and M05-v08 — Outfit-First Full-Scene Rebuild

- Owner-authorized child wardrobe: `Midnight Petrol Column` — full-length midnight-petrol sculptural crepe jumpsuit, asymmetric folded shoulder, antique-brass waist bar, brushed-gold hoops, one brass cuff, black square-toe ankle boots, and a low polished ponytail.
- Replacement contract: A007 is identity conditioning only. It may never be a start frame, crop, plate, background, edit target, wardrobe reference, lighting reference, or source-pixel layer.
- M04 generated one coherent full-scene keyframe but failed identity: one face, ArcFace cosine `0.500372`; no video was submitted.
- M05 changed the bounded synthesis method to identity-first full-scene generation while preserving the approved outfit and scene lock.
- M05 keyframe passed: one coherent edge-to-edge scene, full outfit visible, no collage/cutout/seam, one face, ArcFace cosine `0.7776427269`.
- Exactly one M05 Veo 3.1 Fast native-audio video was generated. Flow balance `12540 → 12530`, observed delta `10` credits; retries `0`.
- M05 MP4 on Pro: `/Users/nuzantara/nuzantara/apps/war-room/output/episode/s01e13-residency-permit-probes-m05-v08-imagegen-full-scene/clips/m05-v08-single-switch.mp4`; SHA-256 `9375f9c881add2860783bd1c10937557ffcc0b40e9dca92f55bb7c4a9897406d`; H.264 `720x1280`, `24 fps`, `8.0 s`, native AAC stereo `48 kHz`.
- Video identity passed on all five sampled frames: one face, average `0.688065`, minimum `0.651252`.
- The owner's primary requirement passed: Zantara, body, wardrobe, light, perspective, and environment were authored together as a new full scene rather than composited from the anchor.
- Strict composition verdict remains `FAIL` only because the bottom-most lamp activates instead of the specified second-from-bottom lamp. No reroll was made.
- Accounted episode spend after M05: `50/100` credits under the owner-raised operating ceiling. Publications, deployments, and outward sends remain `0`.

## Completed Gates

- editorial: `BOOT_AUDIT`; both council waves; consolidation, source pass, final curation; `E13_PILOT_TOPIC_APPROVAL`; `E13_CREATIVE_LOCK`.
- f01: v01/v02 review; scene-start repair; v03/v04 still gates; v04 pre-render; family decision.
- M01/M02: dual-reference still gate; identity-preserve edit gate; M02-v05 pre-render, generation, recovery, structural, visual/identity, and native-audio QA.
- decisions: `E13_M02_V05_CANARY_REJECTED`; `E13_M03_V06_OWNER_VISUAL_REJECTION`; `E13_M04_V07_IDENTITY_FAIL`; `E13_M05_V08_KEYFRAME_PASS`; `E13_M05_V08_VIDEO_OWNER_REQUIREMENT_PASS_STRICT_COMPOSITION_FAIL`.

## Earliest Open Gate

`OWNER_VISUAL_REVIEW_REQUIRED`

The owner can now review the recovered M05-v08 MP4. The no-collage, new-outfit, new-scene, and identity requirements pass. The only strict shot-spec defect is which of the four lamps activates. Do not reroll, extend, upscale, assemble, publish, deploy, or send outward until the owner accepts the clip or requests a new bounded child variant.

## Verification and Resume Reads

- `docs/wr3/factory/episodes/s01e13-residency-permit/context-snapshot.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/creative-lock.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/probe-plan.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/f01-family-decision.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m02-v05-generation-result.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m03-v06-canary-design.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m03-v06-independent-pre-render-gate.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m03-v06-flow-authorization.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m03-v06-flow-dispatch-result.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m03-v06-owner-visual-rejection.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m04-v07-child-creative-outfit-lock.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m04-v07-keyframe-identity-composition-gate.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m05-v08-keyframe-identity-composition-gate.json`
- `docs/wr3/factory/episodes/s01e13-residency-permit/probes/executions/m05-v08-video-identity-composition-gate.json`

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
- `[x]` M03-v06 design authorized, normalized by idempotent originality replay, dispatched exactly once, and stopped without resubmission on ambiguous `403`
- `[x]` corrected M03-v06 tier rebound generated once and was rejected explicitly for visible anchor-first compositing
- `[x]` owner-approved outfit-first replacement contract recorded with A007 restricted to identity conditioning
- `[x]` M04-v07 coherent full-scene keyframe rejected before video on identity threshold
- `[x]` M05-v08 coherent full-scene keyframe passed identity and anti-collage gates
- `[x]` exactly one M05-v08 video generated, recovered, and structurally verified with zero retry
- `[x]` M05-v08 video identity passed; owner primary no-collage requirement passed
- `[ ]` owner accepts the M05-v08 clip despite the lamp-index deviation, or authorizes a materially new bounded child variant
- `[ ]` live FlowKit gateway rejects mismatched workflow/media pairs and returns identifiers derived from the selected payload
- `[ ]` one scene-first f01 canary clip passes identity, motion, composition, audio, and technical QA
- `[ ]` winning cinematic grammar selected
- `[ ]` legal grounding and final script completed
- `[ ]` human-reviewed episode master staged; publication remains a separate manual action
