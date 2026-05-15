# Shot List v1

## Already Covered By Current Seed

- Three-quarter right high-resolution bust anchor.
- Three-quarter right close-up anchor.
- Front-facing neutral, serious, slight smile, soft smile, open smile.
- Gaze down and lateral gaze.
- Chin-high confident expression.
- Left and right profile.
- Rear hair/outfit view.
- Full-body standing and half-body seated.
- Side-light left/right, high-key white, and dark gray editorial lighting.
- Charcoal blouse and black blazer studio variants.
- No-earrings, pearl-stud, hair-behind-ears, and loose-low-bun variants.
- Bali contexts: rice terrace, office interior, temple courtyard, and banyan cinematic.

## Priority Batch Status

`prompts/production_priority_queue_v1.csv` has been executed and QA-mapped:

1. Priority shots approved: 20/20.
2. Extra front slight-smile anchor approved: 1.
3. Candidate-to-approved mapping: `generated_candidates/candidate_qa_v1.csv`.
4. Candidate review sheet: `generated_candidates/contact_sheet_generated_candidates.png`.
5. Approved review sheet: `contact_sheets/approved_v1_contact_sheet.png`.

Next expansion should use the longer `prompts/generation_queue_v1.csv` only after the voice ingredient is recorded or an episode requires a missing environment.

## QA Rubric

- 5/5 identity: same face structure, eye shape, skin tone, hairline.
- 5/5 production quality: sharp, realistic skin texture, no artifacts.
- 5/5 controllability: single pose/expression/crop only.
- 5/5 wardrobe/context control: outfit, jewelry, and background are intentional, not accidental drift.

Anything below 18/20 stays in `rejected/` or `reference_only/`.
