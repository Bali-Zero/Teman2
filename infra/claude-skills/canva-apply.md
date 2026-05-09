---
name: canva-apply
description: Apply pending Canva operations from the War Room. Reads canva_pending.json; if status is "pending", FIRST validates the master template is structurally compatible (Phase -1), THEN resets the master back to blank (Phase 0), THEN edits the master with the new carousel content, duplicates it into the Carousel folder, writes the new design URL to carousel_canva.json, and marks the pending as applied.
---

# Canva Apply — validate → pre-reset → edit → duplicate cycle

## Path resolution

Resolve the output dir from `WR2_OUTPUT_ROOT` env var. If unset, fall back to `/Users/nuzantara/Desktop/nuzantara/apps/war-room/output/canva` (legacy). Strip any trailing slash. Use the resolved path for all subsequent file I/O. The plist `com.balizero.wr2.canva-apply.plist` exports `WR2_OUTPUT_ROOT` to match the writer side (`scripts/wr2_canva_desktop_apply.py`).

Read the file `${WR2_OUTPUT_ROOT}/canva_pending.json`. If it does not exist, print `✅ No pending Canva` and stop. If its `status` field is already `applied`, print `✅ Already applied` and stop.

If `status` is `pending`, execute this exact sequence via the MCP Canva tools (all prefixed `mcp__claude_ai_Canva__*`). Do NOT pause for confirmation between steps — the existence of `canva_pending.json` with `status=pending` is the explicit consent for the whole flow. Do not open TodoWrite.

## Phase -1 — PRE-VALIDATE master template (NEW 2026-05-10)

Before touching anything, sanity-check that the master at `template_design_id` is structurally compatible with the renderer's assumptions. This catches the failure mode from PR #565 (DAHJLYRn_3E had only 2/12 pages with richtext slots) BEFORE Phase 0 wipes anything.

V1. Call `start-editing-transaction` on `template_design_id` with `user_intent="phase -1 validate master structural compatibility"`. Save as `transaction_id_validate`.

V2. From the response, count:
   - `live_pages` = total pages
   - `eligible_richtexts` = richtext elements across all pages with `width >= 30`

V3. If `live_pages < 11` OR `eligible_richtexts < 18`:
   - Call `cancel-editing-transaction` with `transaction_id_validate` (NOT commit).
   - Abort with: `ERROR phase_minus_1_failed: master {template_design_id} has live_pages={live_pages} eligible_richtexts={eligible_richtexts}, requires >=11 pages and >=18 richtexts. Run scripts/wr2_validate_master.py and pick a different master.`
   - Do NOT proceed to Phase 0 — wiping a structurally-broken master wastes a transaction round-trip and yields nothing useful.

V4. Otherwise, call `cancel-editing-transaction` with `transaction_id_validate` (we have what we need; the actual edits happen in fresh transactions in Phase 0 and Phase A). Log `✅ Phase -1 OK: live_pages={live_pages} eligible_richtexts={eligible_richtexts}`.

## Phase 0 — PRE-RESET master template

The master template may carry residual text from prior runs that completed Phase A+B but failed or skipped Phase C reset. To guarantee every run starts from a known-blank master, we wipe ALL text BEFORE applying the new carousel content.

1. Read the pending JSON. Extract `template_design_id`, `folder_id`, `operations`, `topic`, `slides_count`.

2. Call `start-editing-transaction` on `template_design_id` with `user_intent="phase 0 pre-reset master template to blank"`. Save as `transaction_id_prereset`.

3. From the response, enumerate **EVERY richtext element across ALL pages** with `width >= 30` (excludes bullet markers / glyphs that are part of the layout). Build the full list of `(page_index, element_id)` pairs.

4. Call `perform-editing-operations` with:
   - `transaction_id = transaction_id_prereset`
   - `user_intent="reset all richtext to blank before applying new carousel"`
   - `pages=[1..live_pages]`
   - `operations`: one `{"type":"replace_text","element_id":<id>,"text":" ","page_index":<page>}` per every richtext element you enumerated. Use a single space `" "`, not empty string.

5. Call `commit-editing-transaction` with `transaction_id_prereset`. Master template is now blank-text. Save `prereset_count` = number of elements wiped.

## Phase A — Edit the master template with the new carousel

6. Call `start-editing-transaction` on `template_design_id` AGAIN with `user_intent="apply carousel text and image replacements"`. Save the returned `transaction_id`.

   **From the response, build a LIVE TEMPLATE MAP:**
   - `live_pages` = total pages in the response
   - For each page, sort richtext elements with `width >= 30` by **`top` position ASCENDING** (topmost = heading, next = body, then decorative). The `top` coordinate is the visual hierarchy: heading is always at the top of the page, body below it. Then assign:
     - `role_index = 0` for the TOP-MOST richtext (the heading slot)
     - `role_index = 1` for the second-from-top (body / subhead slot)
     - `role_index = 2..N` for remaining richtexts in top-asc order (decorative / source / footer / bullets-text)
   - Each entry: `(element_id, role_index, type, top, height, width)`
     - `type` is `richtext` or `image_frame`
   - Save this map.

   **CRITICAL — top-position role**: do NOT use height-descending (the body box can be taller than the heading because it accommodates more lines, breaking heading/body assignment). Use `top` ascending so the visually topmost element is always heading.

   **NOTE on body box height (2026-05-10 audit):** the master template `DAHJEkWpkzY` has body containers sized 33-58px on pages 2-10. Body text >2 lines may visually overflow into the heading region of the page below in the rendered PDF (bug visible in DAHJNOjr5MM). This is a master-design issue, NOT a skill issue. Do not try to compensate with text truncation in Phase A — preserve the Council's editorial output verbatim. The fix lives in Canva UI (resize body containers to ~200-250px height) or in the Council prompt (cap body length).

   **Adaptive page clamping:** drop ops with `page_index > live_pages` and log `🪂 dropped op: page {N} > live_pages {live_pages}`.

7. For each op in `operations` where `type == "upload-asset-from-url"` OR `type == "insert-overlay-from-url"` (and op survives clamping), call `upload-asset-from-url`. Upload each unique URL only ONCE and reuse the `asset_id`.

8. **Adaptive element_id remap.** For each `replace_text` op:
   - Look up `op.element_id` in the live template map for `op.page_index`. If found exact: use as-is.
   - If NOT found: pick the richtext on `page_index` with the same role_index as the original op had in the pending — first replace_text on a page targets `role_index=0` (heading), second targets `role_index=1` (body). Use the matched live `element_id`. Log `🔄 remap page {N}: {old_id[:12]}... → {new_id[:12]}... (role={role_index})`.
   - If page has no matching role: drop the op with `🪂 dropped op: no role match on page {N}`.

   For each image op (`update_fill` / `insert_fill` / former `upload-asset-from-url`):
   - If `element_id` exists in live map → use as-is.
   - If `element_id == null` → use the page's first `image_frame` element on that `page_index`.
   - If page has NO `image_frame` → fallback: `insert_fill` at full-bleed (left=0, top=0, width=page_width, height=page_height) with the asset_id from step 7. Log `🆕 insert_fill page {N}: full-bleed`.

9. Call `perform-editing-operations` with:
   - `transaction_id` from step 6
   - `user_intent="apply carousel replacements"`
   - `pages=[1..live_pages]`
   - `operations` = the remapped+clamped array from step 8, transformed:
     - `{"type":"upload-asset-from-url",...}` → `{"type":"update_fill","element_id":<remapped>,"asset_type":"image","asset_id":<from step 7>,"alt_text":"carousel hero image"}`
     - `{"type":"insert-overlay-from-url",...}` → `{"type":"insert_fill","page_id":<page id>,"asset_type":"image","asset_id":<legibility-armor asset_id>,"alt_text":"legibility armor gradient","left":0,"top":0,"width":<page_width>,"height":<page_height>,"opacity":1.0}`
     - `{"type":"replace_text",...}` → forwarded with remapped element_id.

   No pre-wipe needed in this phase: Phase 0 already cleared the canvas.

10. Call `commit-editing-transaction` with the `transaction_id` from step 6.

At this point the master template contains the NEW carousel content (heading + body in correct slots, hero images on hero pages, all decorative residue from prior runs already wiped by Phase 0).

## Phase B — Duplicate the edited master into the Carousel folder

11. Call `resize-design` on `template_design_id` (same dimensions) to duplicate. Save the NEW `design_id` — this is the carousel we deliver.

12. Call `move-item-to-folder` with `item_id=<new design_id>`, `folder_id` from the pending JSON, `user_intent="move carousel to Carousel folder"`. If 404, retry once; if still fails, log and proceed.

## Phase C — Reset master template AGAIN (defense-in-depth)

Phase 0 cleared at the start; Phase A re-edited; the duplicate has the carousel content. Now wipe the master AGAIN so it ends each run blank. This protects against the next run's Phase 0 finding non-blank state if this run's Phase 0 → C cycle is somehow interrupted.

13. Call `start-editing-transaction` on `template_design_id`. Save as `transaction_id_postreset`.

14. Enumerate richtext with `width >= 30` across all pages.

15. Call `perform-editing-operations`: replace all enumerated richtexts with `" "`. Save `postreset_count`.

16. Call `commit-editing-transaction` with `transaction_id_postreset`.

## Phase D — Persist outputs

17. Write `${WR2_OUTPUT_ROOT}/carousel_canva.json` with:
   ```json
   {
     "design_id": "<new design_id from step 11>",
     "design_url": "https://www.canva.com/design/<new design_id>/edit",
     "view_url": "https://www.canva.com/design/<new design_id>/view",
     "topic": "<topic from pending>",
     "slides_count": <slides_count from pending>,
     "live_pages": <live_pages observed in step 6>,
     "content_tier": "<content_tier from pending>",
     "hero_slide_indices": <hero_slide_indices array from pending>,
     "transaction_id": "<from step 6>",
     "prereset_transaction_id": "<from step 2>",
     "prereset_count": <n elements wiped in Phase 0>,
     "postreset_transaction_id": "<from step 13>",
     "postreset_count": <n elements wiped in Phase C>,
     "remaps_applied": <count of remap log lines>,
     "ops_dropped": <count of dropped ops>,
     "applied_at": "<ISO-8601 timestamp now>",
     "status": "applied"
   }
   ```

18. Update the pending JSON: set `status` → `"applied"`, add `applied_at` and `transaction_id`, write back.

Respond with: `APPLIED <new_design_id> | PRERESET <p> | REMAPS <r> | DROPPED <d> | POSTRESET <q>`. On failure: `ERROR <short reason>`.

## Hard rules

- **Phase -1 (validate) is MANDATORY**. If validate fails, abort BEFORE Phase 0. Wiping a structurally-broken master is wasted work.
- **Phase 0 is MANDATORY**. Always pre-reset before applying. If Phase 0 commit fails, abort the whole flow with `ERROR phase0_failed: <reason>` — do NOT attempt Phase A on a dirty master.
- The master `template_design_id` must end each run **blank** (only images, no text). Phase C is mandatory. If Phase B succeeds but Phase C fails, surface the error but don't retry Phase A/B.
- Keep the English text from `operations` verbatim. Do not translate.
- Do not pop up TodoWrite — single deterministic flow.
- **Auto-approval**: never pause for confirmation before any MCP tool call.
- **No follow-up questions**: on ambiguity, make the safe default and log it. Never end the run with an open question.
- **Adaptive flow**: NEVER abort because of page-count mismatch or stale element_ids. Always remap and clamp dynamically. Cancel only on:
  - `commit-editing-transaction` error
  - `resize-design` error (Phase B)
  - More than 50% of operations dropped (template completely wrong)

## WR2 multi-tier carousel support

Carousels vary by tier:
- **breaking** (≤7 slides) — short, urgent
- **explainer** (8-10 slides) — analytical
- **deep** (11+ slides clamped to template max) — dossier

`slides_count` ranges 5..template-max. Live page count drives ops applied. Slides beyond `live_pages` are silently dropped.

## Idempotency

If `status="applied"` in pending JSON, do nothing. If Phase -1, 0, or A fails mid-way, the transaction auto-aborts and the template stays in whatever state it was — the next run starts with Phase -1 again, which forces a clean slate regardless. This is the design intent of the validate-first sequence.
