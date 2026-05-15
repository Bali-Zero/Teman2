# Dataset Card - Zantara Visual Dataset v1

## Purpose

This is the official seed dataset for Zantara character consistency across Bali Zero photo, video, Google Flow, Veo, Imagen, and editorial production.

## Source Material

The dataset was built from seven local user-provided reference files on `/Users/nuzantara/Desktop/`. Two collage files were split into single-frame crops. Two high-resolution single portraits became anchors. Two generated JPEGs were rejected for identity drift. One duplicate PNG was rejected.

## Approved Use

- Character identity lock for synthetic Zantara production.
- Pose, expression, crop, angle, and lighting reference.
- Ingredient/reference upload to video and image generation tools.
- Internal production QA.

## Not Approved

- Direct training on collage/grid images.
- Client-facing publication of raw dataset structure.
- Treating rejected files as alternate identities.
- Using this as evidence about any real person.

## Current Gaps (updated 2026-05-16)

Resolved 2026-05-16 (promoted from Codex generated_candidates after QA):
- ✅ High-resolution front-facing neutral anchor (A005, A006 slight smile, A007 serious)
- ✅ High-resolution left/right profiles (P001, P004, img2img-locked, no drift)
- ✅ Full-body standing (P002, with extended wardrobe: black trousers + pumps)
- ✅ Half-body seated (P003)
- ✅ Controlled lighting variants: side-light left/right, high-key white, dark gray editorial (L001-L004)
- ✅ Bali-context anchors: rice terrace golden (BALI-001), office blazer (BALI-002), temple courtyard (BALI-005), banyan cinematic (BALI-006)
- ✅ Outfit variants beyond ivory blouse: charcoal blouse (O001), black blazer studio (O002), office blazer (BALI-002), black trousers + pumps (P002)
- ✅ Jewelry-light variants: no earrings (J001), pearl studs (J002)
- ✅ Hair-control variants: hair behind ears (H001), loose low bun (H002)
- ✅ Priority queue: 20/20 shots mapped to approved assets in `generated_candidates/candidate_qa_v1.csv`

Still missing:
- Missing voice ingredient `.wav` file for spoken Veo 3.1 clips (script ready at `voice/VOICE_INGREDIENT_V1.md`, needs recording).
- Optional expansion only, not blocking v1: beach wide, mangrove, gamelan macro environment, eyes-closed high-res studio anchor, and more episode-specific wardrobe.

Generated candidates are retained under `generated_candidates/` for provenance and QA traceability. Train/reference from `approved/` and `metadata/captions.csv`, not directly from `generated_candidates/`.

## Acceptance Gate For New Images

New images can enter `approved/` only if they preserve face shape, eye shape, hairline, skin texture, and single-subject framing. Outfit, jewelry, and background may vary, but only after the face passes QA against the anchor pair. Reject blur, plastic skin, identity drift, deformed hands, visible text, or collage outputs.
