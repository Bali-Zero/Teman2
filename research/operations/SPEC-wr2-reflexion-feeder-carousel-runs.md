---
date: 2026-06-25
domain: compliance
client_case: WR2 self-improvement loop — feed the starved Reflexion analyst (carousel_runs writer)
sources:
  - scripts/wr2_reflexion_synthesis.py:65 _db_path → ~/.claude/projects/-Users-nuzantara/memory/wr2-episodic.db (Pro) — fetch_last_7_days() reads carousel_runs JOIN slide_states
  - skills/bali-zero-brand/_state-schema.sql:9 carousel_runs (topic_slug, domain NOT NULL, layout_families_used JSON, slide_count, hero_count, body_case_chosen, critic_overall_verdict, instagram_published_at) + :33 slide_states (run_id FK, slide_index, layout_family, state, is_hero_image)
  - scripts/wr2_html_render_apply.py:347 _log_ledger_best_effort (savepoint-isolated, best-effort, idempotent on draft_id) called :454 right after release_lease_permanent (draft → rendered) — the exact twin to imitate
  - _proposed-amendments/2026-06-23-ig-insights-insufficient-data.md — analyst's own diagnosis: "carousel_runs has 0 rows. If the pipeline populated this it provides structural attributes WITHOUT manual tagging. Current state: pipeline does not write to the DB." 8/11 amendments are insufficient-data.
  - cron com.balizero.wr2.reflexion.weekly: Weekday 0 (Sunday) 02:30 WITA — when the fed data would be read.
---

# SPEC — Feed the WR2 Reflexion loop: a best-effort carousel_runs writer

## Problem (grounded on disk, 2026-06-25)

The WR2 Reflexion loop (`wr2_reflexion_synthesis.py`, cron Sun 02:30) reads
`carousel_runs JOIN slide_states` from `wr2-episodic.db` to correlate engagement
with carousel attributes and propose skill/layout amendments. **The table has 0
rows.** The analyst's own report names the cause: "the pipeline does not write to
the DB." Result: 8 of 11 weekly runs die on "insufficient-data" — the loop is
**armed but starved** (superscar #2 / TAC "F-nutrimento 🔴").

Two data sources could feed it: (a) manual Damar tagging of published carousels
(human-dependent, never done), or (b) the structural attributes the render
pipeline ALREADY computes per run. This spec does (b) — the auto-sustaining path
the analyst explicitly flags as the "secondary unblock, no dependency on manual
tagging."

## Goal

When a draft reaches `rendered` (the moment the render pipeline knows
hero_count, slide_count, layout_families, body_case, critic verdict, domain),
persist one `carousel_runs` row + N `slide_states` rows — so the next weekly
Reflexion run reads real structural data instead of an empty table.

## Acceptance criteria (falsifiable)

1. After ONE fresh `rendered` carousel, `SELECT count(*) FROM carousel_runs` ≥ 1
   and a matching `SELECT count(*) FROM slide_states WHERE run_id = <that id>` = slide_count.
2. The written row has NON-NULL `domain`, `slide_count`, `hero_count`,
   `layout_families_used`, `critic_overall_verdict` (the fields the analyst reads).
3. A write FAILURE (locked db, bad schema, missing field) NEVER fails the render:
   the draft still reaches `rendered`/`rendered_shadow` and `drive_url` is set.
   (Same guarantee as `_log_ledger_best_effort`: savepoint-isolated, broad except.)
4. Idempotent: re-rendering the same draft does not create duplicate run rows
   (UPSERT on a natural key — topic_slug + a draft/run identifier).
5. `wr2_reflexion_synthesis.fetch_last_7_days()` returns ≥1 run when run within 7
   days of the write (the real consumer sees the data). Measured by invoking it.
6. Zero PII: only structural/editorial attributes (domain, layout, counts,
   verdict) — no client identifiers. `domain` is the carousel topic class, not a client.

## Design (imitate the existing ledger twin)

### Where it writes
A new `_log_carousel_run_best_effort(conn, draft_id, slides, result, domain)` in
`wr2_html_render_apply.py`, called at line ~454 immediately after
`_log_ledger_best_effort` — same call site, same best-effort contract.

### What it writes
- `carousel_runs`: topic_slug (from draft), domain (from brief_json), started_at /
  completed_at, slide_count = len(slides), hero_count = sum(is_hero_image),
  layout_families_used = JSON distinct layout_family, body_case_chosen,
  critic_overall_verdict (from the designer-loop result), drive_url.
- `slide_states`: one row per slide (slide_index, layout_family, is_hero_image,
  state='rendered', image_seed if present).

### How it's isolated (the non-negotiable)
- **Best-effort, savepoint-isolated**, broad `except` → log a warning, never raise.
  Modeled byte-for-byte on `_log_ledger_best_effort` (the proven pattern).
- **Separate DB**: `wr2-episodic.db` is SQLite on the Pro filesystem, NOT the Fly
  Postgres the render transaction uses. So this is a SECOND connection, opened and
  closed inside the best-effort fn — it cannot poison the main render transaction
  even on total failure. (This is SAFER than the topic_type_log twin, which shares
  the pg conn.)
- **Schema-create-if-missing**: run `_state-schema.sql`'s CREATE TABLE IF NOT
  EXISTS at the top of the writer so a fresh/missing db self-heals.

### Backfill (companion, separate one-shot — NOT in the render path)
A standalone `scripts/wr2_backfill_carousel_runs.py` that imports the 64 historical
`past/*/metadata.json` carousels (which DO carry domain/tone/layout) into
`carousel_runs`, so the loop has mass from day 1 instead of accumulating from zero.
Engagement is absent on historical rows (acceptable — structural attrs are the gap).

## Out of scope
- Manual Damar tagging (human-dependent; this spec removes the dependency).
- Engagement backfill on historical carousels (no IG metrics for them).
- Changing the Reflexion analyst itself (it works; it's just reading an empty table).
- Writing to Fly Postgres (the episodic db is deliberately local SQLite).

## Risk / blast radius
- Touches `wr2_html_render_apply.py` — the render critical path (L2). MITIGATED by
  the best-effort + separate-connection design: the writer literally cannot fail
  the render (worst case = a logged warning + an empty table, i.e. today's status quo).
- The backfill script is one-shot, read-only on `past/`, write-only on the episodic
  db — zero pipeline impact.

## Open questions for the council
1. Natural key for idempotency: topic_slug alone collides across re-runs of the same
   topic. Use (topic_slug + rendered date) or carry the draft UUID into carousel_runs
   (schema has no draft_id column — add one, or encode in topic_slug)?
2. Should the writer fire on `rendered_shadow` too (shadow renders are real
   structural data) or only canonical `rendered`?
3. body_case_chosen: post the de-uppercase fix (#1728) most bodies are now mixed —
   is this field still meaningful, or should it record per-slide actual case?
