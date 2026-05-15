# Zantara Visual Dataset v1

Official local seed dataset for Zantara photo and video production.

## Status

- Approved single images: 40 (19 v1-seed + 21 QA-promoted/generated 2026-05-16)
- Studio identity anchors: 7 (A001-A007)
- Pose/expression references split from collages: 15
- Extended poses (Codex-generated, img2img anchor-locked): 4 (left/right profile, fullbody, seated)
- Controlled lighting variants: 4 (side-light L/R, high-key white, dark gray editorial)
- Outfit variants: 2 studio variants plus office/full-body wardrobe extensions
- Jewelry/hair variants: 4 (no earrings, pearl studs, hair behind ears, loose low bun)
- Bali-context hero anchors: 4 (rice terrace, office blazer, temple courtyard, banyan)
- Priority queue QA: 20/20 approved, plus 1 extra front slight-smile anchor
- Rejected assets: 8 (source rejections + generated identity/outfit drift)
- Collages kept only under `reference_only/`

## Folder Contract

- `approved/anchors/` - highest-trust face identity references (studio gray).
- `approved/anchors-bali-context/` - reserved for non-Codex/FlowKit context anchors after QA; currently no approved files.
- `approved/anchors-bali-context-codex/` - Codex-generated Bali Zero context hero anchors (rice terrace, office blazer, temple courtyard, banyan).
- `approved/lighting-codex/` - controlled light variants after identity QA.
- `approved/outfits-codex/` - alternate outfit variants after identity QA.
- `approved/jewelry-hair-codex/` - jewelry and hair-control variants after identity QA.
- `approved/poses/` - single-frame pose/expression crops split from source collages.
- `approved/poses-extended-codex/` - Codex-generated extended poses (left/right profile, fullbody, seated) using img2img anchor-lock.
- `generated_candidates/` - provenance and QA review only; do not train directly from this folder.
- `ingredients/` - convenience copies for Google Flow / Veo / image-to-video ingredients.
- `reference_only/collages/` - original grids; never train directly on these.
- `rejected/` - excluded files with reasons in `metadata/rejected_assets.csv` and `metadata/manifest.json`.
- `metadata/captions.csv` and `metadata/captions.jsonl` - per-image captions.
- `prompts/generation_queue_v1.csv` - controlled prompt queue for completing the 40-80 image production set.
- `prompts/production_priority_queue_v1.csv` - first 20 shots to generate before expanding the library.
- `voice/VOICE_INGREDIENT_V1.md` - voice target, recording script, and Veo prompt line.
- `generated_candidates/candidate_qa_v1.csv` - candidate-to-approved mapping and QA scores.

## Identity Lock

Zantara v1 is an adult Indonesian woman with warm medium skin tone, dark almond-shaped eyes, defined cheekbones, subtle natural makeup, sharp black eyeliner, and long straight black hair parted in the center.

The ivory silk blouse with delicate gold floral embroidery is the v1 hero look, not a permanent uniform. Gold hoop earrings are the current default anchor detail, not a lifetime lock.

Use `approved/anchors/zan_v1_a001_primary_3q_bust_anchor.png` and `approved/anchors/zan_v1_a002_primary_3q_face_closeup_anchor.png` as the main identity references.

## Hard Rules

- Do not use collage files as direct training images.
- Do not mix in the rejected JPEGs; they drift from the official face.
- Do not overweight duplicate images; `riri.png` is a byte-identical duplicate of `zan2.png`.
- Every generated addition must be a single image with a caption row before entering `approved/`.
- Studio gray is the identity lab, not the whole brand world. Production candidates should add Bali Zero contexts after face QA.
