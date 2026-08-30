# Zantara E13 Identity-Preserving Scene-Start R&D Plan

**Episode:** S01E13 — _What Your Residency Permit Does Not Come With_
**Current gate:** `E13_M02_V05_GATEWAY_PAIR_BINDING_REVIEW`
**Purpose:** preserve exact Zantara identity in a clean portrait story world before any further Flow video spend.

## Operating Principle

The pipeline remains stable; the generated result does not.

- Stable: immutable episode thesis, canonical wardrobe, raster contract, one-face ArcFace gate, no-retry rule, receipts, spend cap, and human publication boundary.
- Divergent: each new creative method receives its own method ID, child seed, model family, and visual hypothesis.
- Diagnostic discipline: this gate holds the approved v04 atrium composition constant where possible so identity transfer is the only variable under test.
- No hidden rerolls: one image submission per method. A failed method closes; it does not silently mutate its prompt and try again.

## Shared Unlock Contract

Every candidate must satisfy all of the following before it can become a video start image:

1. exactly one detected face;
2. real ArcFace `buffalo_l` cosine `>= 0.600` against the canonical A007 embedding;
3. opaque `720x1280` portrait raster produced through center-cover only, without padding, mirroring, blurred fill, or synthetic extension;
4. edge-to-edge limestone-atrium story world from frame one;
5. no raw portrait box, black bars, seam, reflected or inverted panel, duplicate person, text, label, UI, or technical overlay;
6. canonical ivory silk blouse with restrained gold embroidery;
7. immutable lineage from source references through generated media ID, normalized raster SHA-256, identity-gate SHA-256, and final authorization artifact;
8. one submission and one retrieval only; failure never causes an automatic resubmit.

Only the highest-scoring candidate that passes every item may unlock one eight-second f01 video canary. If no candidate passes, the episode remains at this gate.

## Method M01 — Flow Dual Identity Reference

**Hypothesis:** a frontal serious anchor plus a canonical close-up supplies enough facial geometry to lift the clean v04-style scene from cosine `0.558037` to at least `0.600` without constraining the atrium composition.

Inputs, uploaded to one fresh Flow project:

- A007 frontal serious anchor — primary identity and expression reference;
- A002 three-quarter close-up — secondary facial-geometry reference.

Execution contract:

- extend the scene-start context and manifest from one anchor lineage to an ordered, verified two-reference lineage;
- require both reference media IDs to belong to the same fresh project and bind both local SHAs in the receipt;
- submit one native portrait image request with both media IDs in `character_media_ids`;
- preserve the approved spatial brief, wardrobe, single-person constraint, and negative exclusions;
- run deterministic raster QA, then real ArcFace, then visual composition review.

This is the first benchmark because it keeps generation and eventual video start inside the same Flow project and preserves broad compositional freedom.

## Method M02 — Identity-Only Edit of v04

**Hypothesis:** an independent image-editing model can preserve the already successful v04 composition while changing only face identity and immediately connected hair geometry.

Inputs:

- normalized v04 scene-start raster, SHA-256 `afaf0482a2c631d84d77aa9276586cf447b046314da52ca21c67b95d7782efa5`;
- A007 frontal serious anchor;
- A002 three-quarter close-up anchor.

Edit boundary:

- preserve atrium, pose, framing, wardrobe, lighting, body geometry, and edge-to-edge world;
- replace only facial identity and immediately connected hair geometry;
- do not extend, crop creatively, relight, redesign, duplicate, mirror, add panels, or add text;
- return one opaque portrait raster;
- upload the passing edited raster to a fresh Flow project only after local raster, identity, and composition gates pass.

This method is deliberately model-independent from the Flow image generation used for v04. It is not a prompt variation of M01.

## Comparison and Video Canary

Candidates are compared in this order:

1. all-or-nothing shared unlock contract;
2. ArcFace cosine, with no rounding around `0.600`;
3. visual identity consistency across eyes, nose, jawline, hairline, and apparent age;
4. preservation of the approved composition and walking-ready body pose;
5. absence of artifacts likely to amplify during image-to-video generation.

If both pass, select the stronger identity score unless the visual review finds a material face or scene artifact. The selected generated media ID — never raw A007 — becomes the explicit start image for exactly one f01 canary. The runner must validate project, video, media, frame SHA, gate SHA, and authorization lineage before the network call.

## Explicit Non-Goals

- no fifth f01 camera idea;
- no f02–f06 generation;
- no legal script or spoken claim;
- no raw A007 opening;
- no padding, reflection, split-frame, or outpainting workaround;
- no retry loop;
- no publication, deployment, upload to a social platform, or outward message.

## Definition of Done

- [x] M01 multi-reference lineage is fail-closed and test-covered.
- [x] M01 produces exactly one normalized and identity-scored candidate.
- [x] M02 produces exactly one normalized and identity-scored candidate.
- [x] both results have hash-bound receipts and independent method lineages.
- [x] M02 passes every shared gate and M01 closes without a hidden retry.
- [x] only the passing M02 result unlocks one f01 video canary generation.
- [ ] the canary passes identity, motion, composition, audio, and technical QA before the cinematic grammar is selected.
