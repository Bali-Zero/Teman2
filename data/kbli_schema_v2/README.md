# KBLI 2025 Schema-v2 (5-layer provenance)

Built by `scripts/kbli_schema_v2_populate.py` from OSS ground-truth + FINAL_CLEAN reuse + research L4.
- `KBLI_2025_SCHEMA_V2.json` (17MB, gitignored — regenerable) — 2422 records, 5 layers.
- `_l3_gaps*.json` — **0 gaps as of 2026-06-23.** The L3 editorial backlog is closed: all 1559
  five-digit codes carry a grounded English `intel_2026` block in the live navigator
  (`apps/mouth/data/KBLI_2025_FINAL_CLEAN.json`), delivered via PRs #1612 / #1614 / #1645.
  The historical worklists `_l3_gaps_core.json` (287) + `_l3_gaps_noncore.json` (768) = 1055
  were a stale 2026-06-19 snapshot that was never truthed after the work landed (scar #2
  "green that lies"); they have been recomputed against live state — all 1055 are now non-mute,
  so all three files are `[]`. Re-running the populator regenerates `_l3_gaps.json` from
  current reuse and will keep it empty unless a code is ever blanked.

Layers: L0 OSS-truth · L1 normalized (title_en separate) · L2 national compliance · L3 editorial (LOW) · L4 Bali bans.
L4 needs_human_review queue: 11 codes (renumbered ban-codes, candidate bridge — NOT auto-decided).
