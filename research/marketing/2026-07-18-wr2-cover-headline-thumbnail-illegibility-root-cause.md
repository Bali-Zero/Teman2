---
date: 2026-07-18
domain: marketing
client_case: none — WR2 growth loop SPRINT B (fix REFUTED by measurement; root cause found)
adversarial_review: codex
sources:
  - scripts/wr2_html_renderer/composer.py (_wrap_headline_sentence_aware ~849 — cover-photo-gated ALWAYS-ON wrap + BOUNDED FONT-SHRINK to _HEADLINE_FIT_FLOOR_PX=60; :1628 " / "->br pre-fit; :1668 fit call; :1671 de-orphan; :1810 fit !important inject; :1942/:1947,:2048 fill-before-lever)
  - scripts/wr2_html_renderer/composer.py:327-331 (1080x1350 canvas + the 150px/7.2x thumbnail assumption), skills/bali-zero-brand/layouts/cover-photo.md:49 (content anchored bottom 270px), _base.css:67 (overflow:hidden clips)
  - scripts/wr2_html_renderer/claude_vision.py:82,118,158 (critic lever menu; critic prompt declares a ~110px grid thumbnail)
  - scripts/wr2_html_renderer/designer_loop.py:474(deferral is a silent continue),781(progress = lever-state change, not DOM/pixel),1047,976 (no CSS-suppression signal)
  - scripts/wr2_draft_generator.py:1207,1222,1317 (standard normalizer forces slide-1 cover, discards layout_family)
  - prod DB war_room_drafts.slides_json via scripts/pg.sh (nuzantara_readonly) — query embedded below (reproducible)
  - LIVE Pro ~/logs/wr2-html-apply.log 2026-07-14 / 07-16 / 07-18 05:37 (designer-loop "caption-sized hook" composition-debt WARNINGs)
---

# WR2 cover headlines are illegible at IG thumbnail because the renderer SHRINKS ~83% of them to its 60px floor

**The fix this sprint set out to build was REFUTED by measurement, and the measurement found the real
cause.** The plan (from the previous R capture) was: the vision critic can't grow an undersized
hero-cover headline because its lever menu excludes `grow_font target=heading` — so open the menu and
add an overflow guard. That was built, hardened through **three** adversarial rounds — and then
measured against production: **it would fire on 2 of 111 measured headlines (~1.8%)**. It does not
cure the reported defect. What the measurement found instead is the actual mechanism, upstream of the
critic entirely. (Both the finding AND this write-up were adversarially reviewed by Codex `sol`; the
numbers below are the corrected, reproducible ones — see §Adversarial review for what the first draft
got wrong.)

## The measured root cause

`composer.py::_wrap_headline_sentence_aware` runs for the cover headline under the `elif cover_family:`
branch of `_fill_placeholders` (`plan.family == "cover-photo"`, and only when the `_rebalance_wrap`
lever is not set). Its contract is a **bounded font-shrink**: *"pick the LARGEST single font at which
EVERY sentence fits on its own line, shrinking from the 84px base only as far as needed, never below
`floor_px`"* — `_HEADLINE_FIT_FLOOR_PX = 60`. When it shrinks, `_fill_placeholders` injects
`.heading,.headline,.statement,h1{font-size:<fit>px !important}` (:1810); later rules change color/
weight, not `font-size`, and the lever style (if any) is injected after with equal `.heading`
specificity + `!important` so it would win — but no lever ships (see below), so the fit rule reaches
the DOM.

**Measurement (reproducible).** Cover slide = ordinality-1 of `slides_json`; the standard normalizer
forces slide-1 to cover and discards `layout_family` (`wr2_draft_generator.py:1207/1222/1317`), so
pipeline-produced decks are ~100% on this path (manual/legacy can pin `photo-fullbleed` to bypass — 2
of 115 do). Query + method:

```sql
-- cover instances on the fit path (frequency-weighted, NOT de-duplicated):
SELECT COALESCE(s->>'headline', s->>'heading')
FROM war_room_drafts d,
  LATERAL jsonb_array_elements(CASE WHEN jsonb_typeof(d.slides_json)='array'
          THEN d.slides_json ELSE d.slides_json->'slides' END) WITH ORDINALITY AS t(s, ord)
WHERE ord = 1 AND d.slides_json IS NOT NULL
  AND COALESCE(s->>'headline', s->>'heading') IS NOT NULL
  AND COALESCE(NULLIF(TRIM(s->>'layout_family'),''),'cover-photo') = 'cover-photo';
```
Each headline is then run through the real pre-fit chain (`" / "`→`<br>` for the cover-photo family,
`composer.py:1628`) and `_wrap_headline_sentence_aware` in **pipeline order** (fit BEFORE de-orphan).
Result over **n=113 cover instances** (sum-checked):

| Fit size the renderer chose | Instances | Share |
|---|---|---|
| **60px — the FLOOR** | **94** | **83.2%** |
| 61-83px | 12 | 10.6% |
| no shrink (renders at 84px base) | 7 | 6.2% |

**~83% of production cover instances are rendered at the shrink floor.** IG-grid downscale: the
composer assumes a 150px grid cell → ~7.2× → 60px renders **~8.3px**; the critic prompt instead
declares a ~110px grid → ~9.8× → 60px = **~6.1px** (the two constants disagree — itself worth fixing).
Either way it is illegible, and the conclusion is *stronger* at 110px. Note the corollary: even the
84px base renders only ~8.6px at a 110px grid, so "just raise the floor to 84px" is NOT automatically
thumbnail-legible — the cure has to target a genuinely legible size, not merely un-shrink.

**So the "caption-sized hook" is the OUTPUT of the fit policy, not a missing lever.** The policy trades
thumbnail legibility for sentence integrity ("every sentence on its own line"), and at the floor it
loses that trade on ~83% of covers — exactly the un-fixable composition debt the designer-loop logs
on real decks (2026-07-14 23:29, 07-16 05:42, 07-18 05:37).

## Why the built fix is refuted (and why shipping it would be worse than not shipping)

The lever was narrowed (correctly — defect 3 below) to defer whenever the renderer had already made a
measured fit decision. Consequence on the measured headlines: it **defers 94.6%** of the time (the
renderer already fit-decided), **skips 3.6%** (too wide to reach the 100px legible floor), and grows
only **~1.8%** (short hooks at the base). Shipping the critic-prompt half alone would be a **net
negative**: today the critic logs an honest *"No lever in the current set can grow the headline
itself"* and the loop records real composition debt; open the menu without curing the cause and the
critic proposes `grow_font target=heading`, the renderer defers via a **silent `continue`**
(`composer.py:474`) — the designer loop counts a lever-state change as progress
(`designer_loop.py:781`), not a DOM/pixel change, and nothing signals that the CSS was suppressed. An
honest "can't fix this" complaint becomes a **silent no-op** (cicatrix #2 "esiste ≠ armato": a lever
that exists and does nothing is worse than a missing one — it stops anyone from looking).

**Disposition: nothing shipped code-wise, capture only.** The guard is sound (22 tests green) but it
protects a lever whose prompt won't ship — shipping it as "substrate" would be dead code that *looks
like* protection (cicatrix #2 again). Its design is preserved here for the real fix; the code is
reverted. If the real fix later needs a per-lever guard, its shape is documented below.

## The defect chain (three real defects found before any of it reached prod)

Each is a reusable trap; the guard design is the substrate the REAL fix will reuse:

1. **The guard measured the wrong TEXT** (Codex `sol` red-team round 1, reproduced + quantified on
   disk). It measured the RAW headline, but the renderer ships a **de-orphaned** one:
   `_deorphan_numbers_in_headline` glues a numeral to its noun with a literal `&nbsp;`, an
   **unbreakable run** the browser can never soft-wrap. Counterexample `NEW 2026 REQUIREMENTS CHANGE
   NOW`: guard authorized **108px** (widest raw line `REQUIREMENTS`, 8.509em); the real unbreakable
   unit `2026&nbsp;REQUIREMENTS` (11.332em) renders **1223.9px vs a 921.6px budget — 33% overflow**,
   and overflows even at the 100px floor (1133.2px). Sound cap `floor(921.6/11.332)=81px` < floor ⇒
   skip.
2. **The guard measured the wrong WRAP** (implementer self-review). It reproduced `_balance_headline`,
   but the shipped cover wrap is `_wrap_headline_sentence_aware`, different break points. Cure: also
   bound on the **widest unbreakable token** (`shipped.replace("<br>"," ").split()` — an `&nbsp;`
   contains no literal space, so a glued run is ONE token) — a **wrap-independent** bound the browser
   can never violate.
3. **The lever would have overridden a measured fit** (grader, following defect 2). `_fill_placeholders`
   (fit inject) runs BEFORE `_apply_levers_to_html` (`:1942→:1947`, `:2048…`); both insert before
   `</head>`, the two `.heading` selectors have equal specificity, both `!important` ⇒ the later rule
   (the lever) wins. A grow would have silently defeated the mechanism keeping long headlines in the
   box, and multiplied line count (vertical, unbounded by the width guard). Cure: defer when
   `_wrap_headline_sentence_aware` returns non-None `font_px` — which then revealed the 94.6% deferral
   and refuted the fix.

**Reusable guard shape** (for the real fix): `fit_cap_px = floor(_COVER_BOX_WIDTH_PX * _WRAP_SAFETY /
binding_em)`, `binding_em = max(widest_wrapped_line_em, widest_unbreakable_token_em)` on the SHIPPED
(de-orphaned) text, skip below the legible floor. **Still missing even from this shape** (Codex round
2): a **vertical / max-lines** bound (content is anchored bottom 270px per `cover-photo.md:49`;
`overflow:hidden` clips per `_base.css:67`; ~12 lines would overflow) and an **indivisible-single-word**
bound (a word wider than the box can't be broken — e.g. a 2384px token at 84px).

## Recommendation — the real cure (NEXT B, Zero-gated)

**Re-tune the cover headline fit policy so thumbnail legibility is a hard bound, not the residual.**
Today the fit shrinks to whatever keeps every sentence on its own line, floor 60px. Alternative: make
a **thumbnail-legible minimum the hard constraint** (chosen against the *real* grid factor — reconcile
the composer's 150px vs the critic's 110px first; at 110px even 84px is only ~8.6px, so the legible
floor is likely *above* today's 84px base and implies fewer words per cover, an editorial input) and
let a long sentence **wrap across lines** instead of shrinking below it (sentence integrity yields,
not size). The step-3 fallback already calls `_balance_headline` at the floor, so the wiring exists —
but the re-tune MUST add the two guards defect-chain flags: a **max-lines/vertical** bound (or the
title clips) and an **indivisible-token** bound (or one long word overflows horizontally).

**Why Zero-gated:** a brand/editorial trade-off (sentence integrity vs headline size vs word count),
blast radius **~83% of covers** — every one re-renders differently. Needs render QA on a real deck +
Zero's brand call, not an autonomous merge. **Atteso:** cover hooks legible in the IG grid (the
slide's entire job — earn the tap) instead of ~83% shipping at ~6-8px effective.

## Checklist

- [x] Reproduce the reported defect's mechanism on real production data (n=113 cover instances, query above).
- [x] Build + adversarially harden the lever/guard (3 defects found and cured before merge).
- [x] MEASURE the fix against production before shipping → ~1.8% ⇒ refuted, capture-only (code reverted).
- [ ] (Zero-gated) Re-tune the fit policy: reconcile the grid factor (composer 150 vs critic 110);
      thumbnail-legible floor as the hard bound; sentence integrity yields to wrapping; ADD max-lines/
      vertical + indivisible-token guards. Requires render QA on a real deck + Zero's brand call.
- [ ] Never re-open `grow_font target=heading` in the critic prompt without curing the fit policy AND
      adding a `heading_grow_deferred` telemetry signal — else the renderer defers ~95% and the lever
      is a silent no-op.

## Adversarial review

Reviewed by Codex `gpt-5.6-sol` (high effort), generator≠grader. The measurement AND this write-up were
attacked; the load-bearing conclusion held, the headline number was corrected:

- **"83% of covers" — CADE as originally stated, STANDS after re-measure at 83.2%.** Real method
  defects Codex caught, all fixed above: (a) the first draft measured **distinct** headlines (n=111)
  but wrote "83% of covers" — wrong denominator; re-measured frequency-weighted over cover **instances**
  (n=113). (b) It skipped the `" / "`→`<br>` pre-fit transform (`composer.py:1628`) — now applied. (c)
  The numbers weren't reproducible on disk — the SQL + method are now embedded. (d) 93/111 was 83.8%,
  not "83%" — the corrected instance figure is 94/113 = **83.2%**. The finding survives the correction.
- **Thumbnail math — STANDS-WITH-CORRECTION.** 8.3px isn't a stable grid figure; the critic's own
  ~110px grid gives 6.1px (conclusion stronger). Corrected + the "84px is not automatically legible"
  corollary added.
- **"Do not ship" — STANDS.** Codex confirmed the deferral is a silent `continue` the loop doesn't
  detect as a non-change; corrected the deferral/skip figures to 94.6% / 3.6%. Kept the "no dead-code
  substrate" call (stricter than Codex's "keep it disarmed") — a guard for an unshipped lever is
  cicatrix #2.
- **The cure — STANDS-WITH-CORRECTION.** Direction implementable (`_balance_headline` fallback exists),
  but Codex flagged it is incomplete without a vertical/max-lines bound (content anchored bottom 270px,
  `overflow:hidden` clips) and an indivisible-single-word bound — both now in the recommendation.
- **Defect chain — STANDS.** All three defects' numbers re-verified on disk (108px, 11.332em, 1223.9px
  vs 921.6; CSS precedence fill-before-lever). One terminology fix: it's the two `.heading` selectors
  that have equal specificity, not "the selector-lists".
