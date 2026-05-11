# Canva Apply — Image Residue Cleanup (Phase 0 extension)

**Date**: 2026-05-08
**Author**: Antonello + Claude Opus 4.7
**Sub-project**: SP-1 of "Canva apply quality fixes (Badung Horeka run 2026-05-08)"
**Sibling SPs**: SP-2 (body-text resolution diagnosis), SP-3 (TEMPLATE_SLOTS deprecation) — separate specs.

## Problem

The Badung Horeka carousel run (draft `a3fd4007-52a6-47cc-be54-8452d8b2d530`, applied via `wr2_canva_desktop_apply.py` 2026-05-08 09:13 WITA) shipped 3 visually wrong slides:

- **Slide 3** "41% — One Number Changes Everything" → shows Bangkok / Kuala Lumpur / Dubai skylines (template residue from a prior carousel).
- **Slide 5** "Organic Waste: No Longer Someone Else's Problem" → shows construction site + mangrove + two men holding "HUKUM PERLINDUNGAN LINGKUNGAN UU NO. 26/2007" / "SHGB SERTIFIKAT HAK GUNA BANGUNAN" placards (residue from a property/legal carousel).
- **Slide 7** "You Now Have A Reporting Duty" → shows calendar timeline July 2025 / Feb 2026 / Mar 2026 / Apr 2026 with "Bingin Beach demolished / Coastal-setback law / Rice fields criminal offense / Kura-Kura sealed" notes (residue from a land-law carousel).

Root cause: the `canva-apply` skill Phase 0 (PRE-RESET) wipes only **richtext** elements (`width >= 30`), not **image_frame** elements. Hero slides in Phase A overwrite their image_frame with the freshly-generated Codex PNG, but non-hero slides (where `is_hero_image=False` and no `upload-asset-from-url` op is emitted) leave the image_frame untouched — so the asset from the previous carousel persists.

## Goal

Extend the `canva-apply` skill Phase 0 (and Phase C, defense-in-depth) to wipe ALL `image_frame` elements with a transparent placeholder, so every run starts and ends with a known-blank master template across BOTH text and image surfaces.

## Non-goals

- Fixing body-text-missing on 7/11 slides (separate SP-2).
- Dropping `TEMPLATE_SLOTS` hardcoded list (separate SP-3, pure cleanup).
- Re-designing the master template `DAHE6lx1lf8` to remove the cover-left black panel (template-design problem, fix in Canva UI, not in code).
- Adding a `clear_image` op type in `pending_builder.slides_to_operations()` — Phase 0 wipe in the skill is sufficient and centralizes the behavior.

## Architecture

```
Pending JSON construction (build_canva_pending in pending_builder.py)
    └─ NEW: pending["image_placeholder_url"] = IMAGE_PLACEHOLDER_TRANSPARENT_URL
       (Tigris-hosted transparent 1×1 PNG, ~66 bytes, public-readable)

Skill execution (canva-apply.md)
    Phase 0 — PRE-RESET (extended)
    ├─ start-editing-transaction → live template map
    ├─ Wipe richtext (width >= 30) to " "  [unchanged]
    ├─ NEW: Upload transparent placeholder ONCE → asset_id_blank
    ├─ NEW: Enumerate ALL image_frame across all pages
    ├─ NEW: For each image_frame: update_fill with asset_id_blank
    └─ commit

    Phase A — APPLY (unchanged)
    ├─ Hero slides overwrite asset_id_blank with hero asset (from upload-asset-from-url op)
    └─ Non-hero slides: image_frame stays transparent → template background visible

    Phase C — POST-RESET (extended, defense-in-depth)
    ├─ Wipe richtext (existing)
    └─ NEW: Wipe image_frame to asset_id_blank (reuse if same skill session,
       else upload again)
```

**Components touched**:

| File                                                                  | Modification                                                                                           |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `~/.claude/skills/canva-apply.md`                                     | Phase 0 + Phase C: add image_frame enumeration + update_fill loop                                      |
| `apps/backend-rag/backend/services/canva_renderer/pending_builder.py` | Add `IMAGE_PLACEHOLDER_TRANSPARENT_URL` constant; expose in `build_canva_pending()` return dict        |
| Tigris (one-time upload)                                              | Upload `transparent-1x1.png` to `nuzantara-warroom-images/warroom/template-assets/transparent-1x1.png` |

No changes to `wr2_canva_desktop_apply.py` (it's content-agnostic about the pending JSON keys).

## Data flow

The full sequence per run:

1. **Builder** writes `canva_pending.json` with `image_placeholder_url` field populated from the new constant.
2. **Skill Phase 0** reads pending JSON, calls `start-editing-transaction`, builds live map.
3. **Skill Phase 0** runs richtext wipe (existing).
4. **Skill Phase 0** uploads `image_placeholder_url` once via `upload-asset-from-url`, saves `asset_id_blank`.
5. **Skill Phase 0** enumerates every `image_frame` element across all pages, builds a list of `(page_index, element_id)`.
6. **Skill Phase 0** calls `perform-editing-operations` with one `update_fill` per image_frame, all with `asset_id=asset_id_blank`.
7. **Skill Phase 0** commits.
8. **Skill Phase A** runs unchanged — hero slides overwrite the blank asset on their image_frame, non-hero slides leave the blank in place.
9. **Skill Phase A** commits.
10. **Skill Phase B** duplicates the master via `resize-design`.
11. **Skill Phase C** repeats step 4-7 (re-uploads placeholder if `asset_id_blank` lost across transactions, else reuses).
12. **Skill Phase C** commits.

**Critical points**:

- **Idempotency of placeholder upload**: the asset is uploaded ONCE per skill run if possible (cached in skill scope between Phase 0 and Phase C). If Canva MCP requires a new upload per transaction, accept the 2× upload cost — it's 66 bytes each, negligible.
- **Hero priority**: Phase A processes hero slides AFTER Phase 0 wipe → hero asset_id overwrites asset_id_blank on their image_frame. Order is sequential, no race condition.
- **image_frame filter**: in `start-editing-transaction` response, filter elements where `type == "image_frame"`. Skip overlay layers, decorative shapes, text containers.

## Error handling

| Scenario                                                    | Behavior                                                                                                                                                               |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Transparent PNG upload fails in Phase 0                     | Log `⚠️ image-wipe upload failed: <reason>`. Proceed with richtext-only wipe. Image bleed persists for this run, but text content is correct. Telegram notify warning. |
| `update_fill` fails on a single image_frame                 | Log `🪂 image-wipe skip page {N} elem {id[:12]}: {err}`. Continue with remaining image_frames.                                                                         |
| `>50%` of image_frame `update_fill` fail                    | Abort Phase 0 with `ERROR phase0_image_wipe_failed: {n_failed}/{n_total}`. Do NOT proceed to Phase A on a partially-wiped master.                                      |
| Canva MCP doesn't expose `image_frame` type as expected     | Skill falls back to a name-based regex on element type (`image                                                                                                         | frame | placeholder`). If still nothing matches, log `⚠️ no image_frame elements found — skipping image wipe` and proceed (degrades to current behavior). |
| Hero slide's image_frame doesn't get overwritten in Phase A | Frame stays transparent → slide hero appears without image. Operator-visible but non-catastrophic. Fix is in the existing role_index resolution code, not this SP.     |
| Phase C image wipe fails (after Phase A/B succeed)          | Log warning, do NOT abort run. Master template ends with hero image of current run still on its frame → next run's Phase 0 cleans it (auto-healing).                   |

**Threshold note**: the `>50%` abort threshold counts the TOTAL Phase 0 ops failed (richtext + image combined). If richtext wipe succeeds 100/100 but image wipe fails 0/30, total fail rate is 23% → continue.

## Testing

| Layer                            | Test                                                                                                                                                                                                                         | Mode                       |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| Unit (`pending_builder.py`)      | `test_build_canva_pending_exposes_image_placeholder_url` — assert `pending["image_placeholder_url"]` equals the Tigris constant                                                                                              | pytest, no I/O             |
| Unit (skill behavior, simulated) | NOT written. The skill is markdown prose interpreted by Claude. Coverage via live E2E.                                                                                                                                       | N/A                        |
| Live E2E                         | Re-run Badung Horeka draft `a3fd4007-...` with skill updated. Visual check: slide 3 (41% number) → no Bangkok/KL/Dubai skyline; slide 5 (organic waste) → no mangrove/SHGB; slide 7 (reporting duty) → no calendar timeline. | Manual, inspect PDF export |
| Regression                       | Re-run a previously-applied draft (e.g. Golden Visa `de69f035-...`) with skill updated. Verify hero slides still show their correct images.                                                                                  | Manual                     |
| Asset preflight                  | One-shot before first deploy: `curl -sI https://nuzantara-warroom-images.fly.storage.tigris.dev/warroom/template-assets/transparent-1x1.png` must return `200`, `Content-Type: image/png`, `Content-Length: ~66`.            | One-shot bash              |

**Acceptance criteria** (operator-validable):

1. Re-export Badung Horeka PDF post-fix.
2. Slide 3, 5, 7 show template background (uniform dark navy) — NOT skyline / mangrove / calendars.
3. Slide 1, 4, 8, 11 hero images present and on-topic (Codex-generated).
4. Slide 2, 6, 9, 10 non-hero, non-image: typography only on template background.

## Rollout

1. Upload `transparent-1x1.png` to Tigris (one-shot).
2. Edit `pending_builder.py` to expose constant.
3. Edit `~/.claude/skills/canva-apply.md` to extend Phase 0 + Phase C.
4. Commit on `feat/wr2-manual-topic-override-2026-05-08` branch (or new branch).
5. Re-build pending JSON for Badung Horeka draft (rerun `pending_builder` against the existing slides_json).
6. Re-run `wr2_canva_desktop_apply.py --draft-id a3fd4007-...`.
7. Visually verify PDF export.
8. If pass → merge PR.

## Risks

| Risk                                                                          | Mitigation                                                                                                    |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Canva MCP `update_fill` semantics differ from text replace_text               | Test on a single image_frame in Phase 0 first; if behavior unexpected, fall back to no-op skip                |
| Transparent placeholder visible as a "broken image" icon in Canva editor      | Acceptable for editor view — operator only inspects exported PDF/PNG, where transparent renders as background |
| Master template ends up partially-wiped if Phase 0 commits but Phase A aborts | Existing Phase 0/C cycle already handles this — next run's Phase 0 starts clean. No regression.               |
| Tigris asset URL changes (renamed bucket, key rotation)                       | Constant lives in code, single source of truth. Update + redeploy if URL changes.                             |

## Open questions

None — all resolved during brainstorm. Sibling SPs (SP-2 body-text diagnosis, SP-3 TEMPLATE_SLOTS deprecation) tracked separately.

## References

- Output PDF showing the bug: `~/Downloads/WR2 Automation standard (6).pdf` (12 pages, 21.6 MB)
- Cicatrix scar (related, not duplicate): `pending_builder.py:38-66` — TEMPLATE_SLOTS suffix drift
- Skill being modified: `~/.claude/skills/canva-apply.md` (146 lines, last touched PR #506)
- Pending builder: `apps/backend-rag/backend/services/canva_renderer/pending_builder.py`
- Apply runner: `apps/backend-rag/backend/services/canva_renderer/runbooks/APPLICA_WAR_ROOM.md`
