# Layout proposals — lifecycle

This directory holds **candidate** layout-family proposals produced automatically by
`scripts/wr2_reflexion_synthesis.py` (the weekly WR2 Reflexion cron, Sunday 02:30 WITA), plus
any manually-drafted proposals. It is the repo-canonical write target for layout-scoped
lessons — see the audit that identified the gap: `research/operations/2026-07-14-wr2-deep-audit.md`
§10 Wave-4 item 16.

## Why this dir exists

Before 2026-07-14, the synthesis prompt promised a `suggested_destination` value of
`layouts/_proposed/<name>.md` for `category="layout"` lessons, but no code ever created this
directory or wrote to it — the destination was aspirational prose with zero write logic behind
it. `_write_layout_proposal()` in `wr2_reflexion_synthesis.py` closes that gap.

## Lifecycle

1. **proposed** — a file lands here, named `<iso-week>-<slug-or-name>.md`, containing the
   lesson text, confidence, motivating run IDs, and a suggested addition (drafted text for a
   new/modified layout family). Nothing here is read by the live rendering pipeline
   (`scripts/wr2_html_renderer/composer.py` only reads the sibling `layouts/*.md` files, never
   this subdirectory) — a proposal here has **zero production effect** until promoted.
2. **operator review** — Antonello (or a session acting as operator per
   `feedback_no_operator_lane_io_sono_te_2026_07_06`) reads the proposal, checks it against the
   brand constitution and the existing layout family pool, and decides accept/reject/rework.
3. **merged into the library** — on accept, the reviewer authors or edits the corresponding
   `skills/bali-zero-brand/layouts/<name>.md` (+ `_base.css` if a new CSS class is needed) and
   deletes the proposal file from this directory. On reject, the proposal file is deleted with
   a one-line note in the commit message (or left for `>90d` staleness sweep — see
   `cicatrix-superscar.md` #2 "Esiste≠Armato" for why stale-but-unswept surfaces are a known
   disease pattern to avoid recreating here).

## What this is NOT

- Not a second layout library — the render engine never reads this directory.
- Not auto-mergeable — every promotion is a human/operator decision (Legge 5 territory: brand
  taste is a business decision, not something the cron self-approves).
