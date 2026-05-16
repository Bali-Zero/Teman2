# Zantara Generated Candidate QA v1

Generated at WITA: 2026-05-16T05:08:27.650079+08:00

## Result

- Priority shots QA approved: 20/20
- Extra generated anchors QA approved: 1
- Candidate image files retained for provenance: 21
- Approved caption rows: 40
- Training source of truth: use files under `approved/` plus `metadata/captions.csv`; do not train from `generated_candidates/` directly.

## QA Gate

- Face identity checked visually against A001/A002/A005 anchors.
- Single subject, no collage/grid outputs.
- No visible text/logo/watermark.
- Outfit, jewelry, hair and Bali context variants kept only after identity pass.
- Three generated drift assets were moved out of `approved/` into `rejected/identity-drift/`.

## Files

- `candidate_qa_v1.csv` - row-level QA and approved-path mapping.
- `candidate_qa_v1.json` - same mapping for tools.
- `contact_sheet_generated_candidates.png` - visual review sheet for generated candidates.
- `../contact_sheets/approved_v1_contact_sheet.png` - official approved visual sheet.
