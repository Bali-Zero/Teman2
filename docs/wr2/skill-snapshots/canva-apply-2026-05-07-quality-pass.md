---
name: canva-apply
description: Apply pending Canva operations from the War Room. Reads canva_pending.json; if status is "pending", edits the master template in-place, duplicates it into the Carousel folder, wipes the master template back to blank, writes the new design URL to carousel_canva.json, and marks the pending as applied.
---

# Canva Apply — atomic edit → duplicate → reset cycle

Read the file `/Users/nuzantara/Desktop/nuzantara/apps/war-room/output/canva/canva_pending.json`. If it does not exist, print `✅ No pending Canva` and stop. If its `status` field is already `applied`, print `✅ Already applied` and stop.

If `status` is `pending`, execute this exact sequence via the MCP Canva tools (all prefixed `mcp__claude_ai_Canva__*`). Do NOT pause for confirmation between steps — the existence of `canva_pending.json` with `status=pending` is the explicit consent for the whole flow. Do not open TodoWrite.

## Phase A — Edit the master template in place

1. Read the pending JSON. Extract `template_design_id`, `folder_id`, `operations`, `topic`, `slides_count`.

2. Call `start-editing-transaction` on `template_design_id` with `user_intent="apply carousel text and image replacements"`. Save the returned `transaction_id`.

   **From the response, build a LIVE TEMPLATE MAP:**
   - `live_pages` = total pages in the response (e.g. 9, 11, 12 — DO NOT assume 11)
   - For each page, sort richtext elements by **height DESCENDING** (tallest = heading, ties broken by `top` ascending). Then assign:
     - `role_index = 0` for the TALLEST richtext (the heading slot)
     - `role_index = 1` for the second-tallest (body / subhead slot)
     - `role_index = 2..N` for remaining richtexts in height-desc order (decorative / source / footer)
   - Each entry: `(element_id, role_index, type, height, top, width)`
     - `type` is `richtext` or `image_frame`
   - Save this map for STEP 3 below.

   **CRITICAL — height-based role**: do NOT use order-of-appearance in the JSON response (which is z-order, not visual hierarchy). Use the geometric `height` of the element as the primary sort key. Example for a typical page: heading height ≈ 55-77pt, subhead ≈ 38-50pt, body ≈ 30-38pt, decorative ≈ 26-30pt, bullet markers width<10pt (skip these).

   **Adaptive page clamping:** the pending JSON may reference pages 1..N where N may exceed `live_pages`. ANY operation with `page_index > live_pages` must be DROPPED with a log line `🪂 dropped op: page {N} > live_pages {live_pages}`. Continue with operations for pages 1..live_pages only. Do NOT abort the transaction for this reason.

3. For each op in `operations` where `type == "upload-asset-from-url"` OR `type == "insert-overlay-from-url"` (and op survives clamping above), call `upload-asset-from-url` with the given `url`, a short `name` like `"carousel-<template_design_id>"`, and `user_intent="carousel asset"`. Upload each unique URL only ONCE and reuse the `asset_id`. The legibility-armor gradient URL appears on every hero slide — upload it ONCE and reuse the same `asset_id` across every `insert_fill` op below.

4. **Adaptive element_id remap:** the pending JSON contains element_ids that were captured at template-build time and may NOT exist in the current live template (template revisions, manual edits, etc). Apply this remap before calling `perform-editing-operations`:

   For each `replace_text` op:
   - Look up `op.element_id` in the live template map for `op.page_index`.
   - **If found exact**: use as-is.
   - **If NOT found**: pick the richtext on `page_index` with same role_index as the original op had in the pending — i.e. first replace_text on a page targets `role_index=0` (headline), second targets `role_index=1` (body). Use the matched live `element_id`. Log `🔄 remap page {N}: {old_id[:12]}... → {new_id[:12]}... (role={role_index})`.
   - **If page has no matching role**: drop the op with `🪂 dropped op: no role match on page {N}`.

   For each image op (`update_fill` / `insert_fill` / former `upload-asset-from-url`):
   - If `element_id` exists in live map → use as-is.
   - If `element_id == null` → use the page's first `image_frame` element on that page_index.
   - **If page has NO `image_frame` element (e.g. pages 11/12 in current template are text-only)** → fall back to `insert_fill` at full-bleed coordinates (left=0, top=0, width=page_width, height=page_height) using the asset_id from step 3. This way hero text-page closers still get a visual layer instead of blank background. Log `🆕 insert_fill page {N}: no image_frame, full-bleed insert`.
   - Only as last resort drop with log if even insert_fill fails.

5. **Phase A.5 — PRE-WIPE template decorative residue.** The DAHE6lx1lf8 master template carries 8-11 richtext blocks per page where only 1-3 are heading/body editorial slots; the rest are decorative display-accent baked-in placeholders ("OLD GRANDFATHERED APPROVALS", "AUDIT WINDOW IS OPEN", "TIER-A: PRIORITY SECTORS", etc.) that survive runs unless explicitly wiped. Without this step, the duplicate produced in Phase B inherits stale template text mixed with the new editorial content (the "Frankenstein" failure mode).

   For each page `i` in `1..live_pages` that has ANY operation in the remapped+clamped array from step 4, build a wipe-decorative op set:
   - From the live template map, list richtext elements where `type == richtext` AND `width >= 30` (this excludes bullet markers / glyph elements with `width < 10`).
   - SKIP elements with `role_index == 0` (heading) and `role_index == 1` (body) on that page — these will be overwritten by the editorial ops in step 6 anyway. Wiping them with " " first then overwriting wastes one ops cycle and sometimes desyncs Canva's text shaping.
   - For all remaining richtext (role_index >= 2 — decorative, source labels, footer text), emit one `{"type":"replace_text","element_id":<id>,"text":" ","page_index":i}`.
   - Prepend these wipe ops to the operations array for that page, so they run BEFORE the editorial replacements.

   Result: heading and body ARE overwritten directly by editorial ops (preserving Canva's text-shaping pass on first write). Decorative slots are blanked and stay blank. Bullet markers / narrow glyphs are NEVER touched (their width < 30 filter excludes them).

   Pages with NO ops in the pending array are NOT pre-wiped — they will be handled by Phase C reset at the end. Pre-wipe scope = exactly the pages the carousel will use.

6. Call `perform-editing-operations` with:
   - `transaction_id` from step 2
   - `user_intent="apply carousel replacements"`
   - `pages=[1..live_pages]` (the actual range, NOT hardcoded 1..11)
   - `operations` = the pre-wipe ops from step 5 PREPENDED to the remapped+clamped array from step 4, transformed as follows:
     - `{"type":"upload-asset-from-url",...}` → `{"type":"update_fill","element_id":<remapped>,"asset_type":"image","asset_id":<from step 3>,"alt_text":"carousel hero image"}` (MCP op name is `update_fill`, not `replace_image`)
     - `{"type":"insert-overlay-from-url",...}` → `{"type":"insert_fill","page_id":<from pages response>,"asset_type":"image","asset_id":<legibility-armor asset_id>,"alt_text":"legibility armor gradient","left":0,"top":0,"width":<page_width>,"height":<page_height>,"opacity":1.0}`
     - `{"type":"replace_text",...}` → forwarded with remapped element_id.

   Op order matters: pre-wipe replace_text(" ") must come BEFORE editorial replace_text per page. MCP applies ops in array order within a single page batch.

7. Call `commit-editing-transaction` with the `transaction_id`.

At this point the master template (`template_design_id`) contains the edited carousel for the available pages.

## Phase B — Duplicate the edited template

8. Call `resize-design` on `template_design_id` (same dimensions) to duplicate. Pass `title=<topic from pending JSON, truncated to 80 chars>` so the duplicate inherits a meaningful name (e.g. "Indonesia Cracks Down on Sham Investor Visas — ITAS Holders…") instead of the generic template title "WR2 Automation standard". Save the NEW `design_id` — this is the carousel we deliver.

9. Call `move-item-to-folder` with `item_id=<new design_id>`, `folder_id` from the pending JSON, and `user_intent="move carousel to Carousel folder"`. If it fails with 404, retry once; if it still fails, log the error and proceed (non-blocking — the duplicate still exists, just not filed).

## Phase C — Reset the master template back to blank

Now that the duplicate is safely in the Carousel folder, we wipe the master template so the next run starts from a known-empty state.

10. Call `start-editing-transaction` again on the same `template_design_id`. Save the new `transaction_id_reset`.

11. From the reset transaction's response, enumerate text elements across ALL pages (whatever live_pages is — don't hardcode 11). **Apply the same width filter as Phase A.5**: skip elements with `width < 30` (bullet markers / glyphs / decorative dots). Build the full list of `(page_index, element_id)` pairs for the wipeable richtexts only.

12. Call `perform-editing-operations` with:

- `transaction_id = transaction_id_reset`
- `user_intent="reset master template to blank"`
- `pages=[1..live_pages]`
- `operations`: one `{"type":"replace_text","element_id":<id>,"text":" ","page_index":<page>}` per every wipeable richtext you enumerated. Use a single space `" "` (not empty string) — some Canva layouts auto-restore a placeholder when given an empty string.

13. Call `commit-editing-transaction` with `transaction_id_reset`.

Do NOT touch image elements during reset. Only text ops. Images stay put so slide layouts survive between runs.

## Phase D — Persist outputs

14. Write `/Users/nuzantara/Desktop/nuzantara/apps/war-room/output/canva/carousel_canva.json` with:

```json
{
  "design_id": "<new design_id from step 8>",
  "design_url": "https://www.canva.com/design/<new design_id>/edit",
  "view_url": "https://www.canva.com/design/<new design_id>/view",
  "topic": "<topic from pending>",
  "slides_count": <slides_count from pending>,
  "live_pages": <live_pages observed in step 2>,
  "content_tier": "<content_tier from pending: breaking|explainer|deep>",
  "hero_slide_indices": <hero_slide_indices array from pending>,
  "transaction_id": "<from step 2>",
  "template_reset_transaction_id": "<from step 10>",
  "template_reset_count": <n text elements wiped in step 12>,
  "prewipe_count": <n richtext elements wiped pre-editorial in step 5>,
  "remaps_applied": <count of remap log lines>,
  "ops_dropped": <count of dropped ops>,
  "applied_at": "<ISO-8601 timestamp now>",
  "status": "applied"
}
```

15. Update the pending JSON: set `status` → `"applied"`, add `applied_at` and `transaction_id`, write it back to the same path.

Respond with: `APPLIED <new_design_id> | RESET <count> | PREWIPE <p> | REMAPS <r> | DROPPED <d>` on full success, or `ERROR <short reason>` on failure.

## Hard rules

- The master `template_design_id` must end each run **blank** (only images, no text). Phase C is mandatory. If Phase B succeeds but Phase C fails, surface the error but don't retry Phase A/B — we already have the duplicate.
- Keep the English text from `operations` verbatim. Do not translate.
- Do not pop up TodoWrite — this is a single deterministic flow.
- **Auto-approval**: never pause to ask for confirmation before any MCP tool call. The pending JSON on disk is the full authorization.
- **No follow-up questions**: on ambiguity, make the safe default (skip non-critical step, log in the ERROR message, still write partial `carousel_canva.json`). Never end the run with an open question.
- **Adaptive flow**: NEVER abort the transaction because of page-count mismatch or stale element_ids. Always remap and clamp dynamically. Cancel only on:
  - `commit-editing-transaction` error
  - `resize-design` error (Phase B)
  - More than 50% of operations dropped (template completely wrong)

## WR2 multi-tier carousel support

WR2 carousels vary by tier:

- **breaking** (≤7 slides) — short, urgent
- **explainer** (8-10 slides) — analytical
- **deep** (11+ slides clamped to template max) — dossier

The pending JSON's `slides_count` may be anywhere from 5 to template-max. The live template page count drives the actual ops applied. Slides beyond `live_pages` are silently dropped (their content does not appear in the carousel).

## Idempotency

If you find `status="applied"` in the pending JSON, do nothing. If Phase A fails mid-way (e.g. commit fails), the transaction auto-aborts and the template stays dirty — that's fine, the next `/canva-apply` run re-attempts from scratch. Do not try to recover partial Phase-A state.
