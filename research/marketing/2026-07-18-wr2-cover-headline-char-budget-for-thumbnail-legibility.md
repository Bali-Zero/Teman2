---
date: 2026-07-18
domain: marketing
client_case: WR2-pipeline
adversarial_review: codex
sources:
  - https://www.truefuturemedia.com/articles/instagram-carousel-strategy-2026
  - https://futuristicmarketingservices.com/Blogs/graphic-designing/instagram-carousel-design-guide/
  - https://postnitro.ai/blog/post/instagram-carousel-post
  - https://carouselli.com/blog/instagram-carousel-best-practices
  - internal:scripts/wr2_html_renderer/composer.py (cover geometry constants, measured 2026-06-10)
  - internal:research/marketing/2026-07-18-wr2-cover-headline-thumbnail-illegibility-root-cause.md (n=113 prod measurement)
---

# WR2 SPRINT R — a cover-headline CHARACTER budget for thumbnail legibility (the editorial input the Zero-gated fit-policy cure needs)

## The frontier question

The just-closed SPRINT B proved that **83.2% of production cover headlines (n=113)** shrink to the
`_HEADLINE_FIT_FLOOR_PX=60` floor → ~6-8px at IG-grid thumbnail → illegible. The B ledgered the real
cure (re-tune the fit policy) as **Zero-gated**, because it needs an editorial trade-off: *how few words
can a cover carry so the fit policy never has to shrink below a thumbnail-legible size?* That editorial
number did not exist. This R derives it — in **characters, not words** — and shows it is inseparable from
the fit-floor decision.

## What the external SOTA says (and why it under-constrains us)

2026 IG-carousel authorities converge on a cover-headline rule of **5–8 words** (some say "under 8–10"),
as the single largest text on the slide, communicating the promise + a curiosity gap; and a **~40px
minimum font on a 1080-wide canvas** for phone-legible-without-zoom
([TrueFuture](https://www.truefuturemedia.com/articles/instagram-carousel-strategy-2026),
[Futuristic Marketing](https://futuristicmarketingservices.com/Blogs/graphic-designing/instagram-carousel-design-guide/),
[PostNitro](https://postnitro.ai/blog/post/instagram-carousel-post),
[Carouselli](https://carouselli.com/blog/instagram-carousel-best-practices)).

Two reasons this rule is **not directly usable** for Bali Zero:

1. **The 40px floor is a full-screen-mobile floor, not a grid-thumbnail floor.** Our problem surface is
   the feed/profile GRID, where the 1080px canvas downscales ~7.2× (composer's 150px assumption) to
   ~9.8× (the critic's ~110px assumption). A 40px-on-canvas headline is ~4-5px at grid scale — the
   composer's own comment already sets the *thumbnail-legible* target ~2.5× higher, at
   `_GROW_CLAMP_PX["heading"][0] = 100px` on canvas (`composer.py:354`, "the title grows ABOVE its 84px
   base, stays the largest"). Caveat (Codex R1): 100px is the min of the *optional* `grow_heading` lever,
   not a universal declared floor — the always-on title base is 84px and the fitter's own floor is 60px.
   It is the code's declared legible TARGET, and the 60-vs-100 gap is a design tension, not a contradiction.
2. **Regulatory words are ~2× longer than the general-English word the SOTA benches assume.** Covers say
   `IMMIGRATION`, `REGULATION`, `REQUIREMENTS`, `DEPORTATION`, `INDONESIA` (10-12 chars each). A "5-word"
   regulatory headline can be 55+ characters; a "5-word" lifestyle headline is ~30. **The binding budget
   is CHARACTERS, not words** — the word-count heuristic silently over-permits regulatory copy.

## The derivation (pipeline's own em-model, this turn)

Cover geometry, re-grepped on disk (`composer.py`): line budget = `_COVER_BOX_WIDTH_PX 960 × _WRAP_SAFETY
0.96 = 921.6px`; per-char advance = the measured `_UPPER_EM_WIDTH` table (avg `_EM_WIDTH_DEFAULT=0.74`,
reproduces real browser widths within ~0.7%). Characters-per-line = `921.6 / (font_px × 0.74)`:

| font px | chars/line | 2 lines | 3 lines | grid legibility |
|--------:|-----------:|--------:|--------:|---|
| 60 (current floor) | 20.8 | 41.5 | 62.3 | ~6-8px — **illegible** |
| 84 (base) | 14.8 | 29.7 | 44.5 | ~8.6-11.7px — marginal |
| **100 (code's own legible-title floor)** | **12.5** | **24.9** | **37.4** | ~13-14px — legible |
| 120 | 10.4 | 20.8 | 31.1 | comfortable |

**The cover-copy budget** — this is an *expected* capacity from the avg-em (0.74) model, **NOT a hard
geometric max** (Codex R1). The real gate is per-glyph: `W`=1.184em, `I`=0.339em, so `IIIIII IIIIII…` at
34 chars wraps to 2 lines while `WWW WWW…` at 35 chars wraps to 5 — which is exactly why the code
abandoned char-count wrapping (`composer.py:482`). Use the budget as an **editorial TARGET**, gate on the
real `_estimate_text_width_px`:
- **≤ 25 chars (incl. spaces) → ~2 lines** at a legible ~100px — the clean, aesthetic cover.
- **≤ 37 chars → ~3 lines** — the editorial ceiling; ~5-6 regulatory words. NB: there is **no `max_lines`
  in the fitter today**, so dense copy silently produces 4+ lines (Codex: the 49-char headline → 4 lines
  at 100px) — a real max-lines guard is part of the cure, and the "3-line vertical wall" is a *target*,
  not something the current code enforces.

## The measured reality — why capping copy ALONE won't work

Running the pipeline's real `_wrap_headline_sentence_aware` on five actual regulatory headlines, **every
one renders SUB-LEGIBLE** — including short ones:

| headline | chars | fit font | lines |
|---|---:|---:|---:|
| `NEW IMMIGRATION RULES` | 21 | **64px** | 1 |
| `TAX DEADLINE 1 AUGUST` | 21 | **68px** | 1 |
| `OVERSTAY MEANS DEPORTATION` | 26 | **60px** | 1 |
| `PP 45/2024 REPLACES PP 28/2019` | 30 | **60px** | 2 |
| `NEW INDONESIA IMMIGRATION REGULATION TAKES EFFECT` | 49 | **60px** | 3 |

`NEW IMMIGRATION RULES` is only 21 chars / 3 words — **inside** the SOTA budget — yet renders at 64px
because the fit policy keeps it on **one line** and shrinks, rather than wrapping to more lines where it
could clear 100px. **This is the coupling:** the current fit policy **shrinks-before-word-wrap** — Codex
R1 confirmed the ordering on disk (split on `. ! ?` → shrink each clause to the floor → pixel-wrap ONLY as
a last resort, `composer.py:767,810,827`). So a **copy cap alone cannot** rescue legibility while that
bias holds (the 21-char/64px case proves it). The reverse is weaker and Codex correctly flagged my
overclaim: a wrap/target-raise lever alone would trigger the existing wrap fallback *earlier* and is **not
refuted in general** — but on its own it produces overflow / 4-line covers on dense copy (the 49-char
headline → 4 lines at 100px; `OVERSTAY MEANS DEPORTATION` returns 60px/1L yet measures 1086px > the 921.6
budget, i.e. it overflows the function's own budget even at the floor). Hence the two levers are best set
**together** — a sensible editorial+policy coupling, **not a proven mathematical necessity**.

## THE RECOMMENDATION (actionable)

**Adopt a two-lever, jointly-set cover rule; expected result: covers legible at grid-thumbnail scale
without the 83% floor-collapse.** The word-budget and the fit-floor are ONE decision, not two:

1. **Editorial cap (this R's number):** target cover headline **≤ 37 chars incl. spaces (≤ 25 for a clean
   2-line cover)**, ~5-6 regulatory words. Because "5-8 words" over-permits long regulatory terms, express
   the human-facing rule in **characters** — but **gate compose on the per-glyph `_estimate_text_width_px`**,
   not raw char count (per-glyph reality, Codex R1): reject/re-prompt when the headline can't hold the
   legible target across ≤3 lines. Char-count is the brief guideline; the estimator is the gate.
2. **Fit-policy re-tune (the ledgered Zero-gated cure) — NOT a one-line floor bump.** Codex R1 proved that
   naively setting `_HEADLINE_FIT_FLOOR_PX=100` is incoherent: `_max_fit_font` iterates `base(84)→floor`,
   so `floor=100` is an EMPTY range → the fit returns the raw size and `NEW IMMIGRATION RULES` renders
   100px/1L at ~1420px (gross overflow). The real cure must: (a) define a legible **target font ≥ the 84px
   base** (raise the base, or add a distinct target constant); (b) **word-wrap at the target BEFORE
   shrinking**, not after; (c) drop the `≤3-word` no-op escape when the title exceeds the budget (today
   `OVERSTAY MEANS DEPORTATION` returns 60px/1L but measures 1086px > 921.6 → overflow); (d) add a real
   **`max_lines`** guard (none exists today); (e) gate on the **per-glyph** estimator, char budget as
   editorial target only. The 60-vs-100 gap is the concrete **design tension** (always-on shrink floor vs
   the optional `grow_heading` lever's legible min) — the fit policy tolerates titles the grow policy
   would call illegible.

The copy cap alone is insufficient (proven: 21-char/64px); the floor/wrap re-tune alone overflows on dense
copy — so they are best set together. Zero's call is the *value* of the legible target (brand: how big must
a cover read on the grid) + render-QA on a real deck; this R supplies the coupled copy budget for whichever
target Zero picks (table generalizes: `expected_chars ≈ 1245 / target_px × lines` — expected capacity, not
a hard max).

## Checklist (for the Zero-gated cure PR, when armed)

- [ ] Reconcile the grid factor first (composer 150px vs critic 110px) — the legible-target value depends on it.
- [ ] Define a legible **target font ≥ the 84px base** (raise base or add a target constant) — do NOT set `_HEADLINE_FIT_FLOOR_PX=100` (empty `_max_fit_font` range, Codex R1).
- [ ] **Word-wrap at the target BEFORE shrinking**; shrink only as last resort (invert today's order).
- [ ] Drop the `≤3-word` no-op escape when the title exceeds the budget (else `OVERSTAY…`-class overflow).
- [ ] Add a real **`max_lines`** guard (none exists today; the fallback can emit 4+ lines).
- [ ] Gate compose on the **per-glyph** `_estimate_text_width_px`, with ≤37 chars as the editorial target only.
- [ ] Render-QA on a real deck; confirm 0% floor-collapse on a fresh n≥30 cover sample.

## Adversarial review

Codex GPT-5.6 `sol` (high effort, read-only, generator≠grader), 2026-07-18. Verdict: **"aritmetica
promossa; diagnosi shrink-before-wrap promossa; '37 caratteri è il massimo' e 'basta portare il floor a
100' respinte."** Per-claim:

1. **Formula `1245/floor×lines` — STANDS-WITH-CORRECTION.** `921.6/0.74 = 1245.405…`, table recomputed
   exact. Correction (incorporated): it is *expected* capacity, not `max_chars` — the real model is
   per-glyph; the code itself abandoned char-count wrapping (`composer.py:478,482,508`). Relabelled
   throughout to `expected_chars` / editorial target.
2. **"code's own legible floor is 100px" — STANDS-WITH-CORRECTION.** `_GROW_CLAMP_PX["heading"]=(100,150)`
   verified (`composer.py:348-354`), but it is the *optional* `grow_heading` lever's min (`:421`), not a
   universal title floor (base 84, fit floor 60). Softened to "declared legible TARGET".
3. **"60 sits 40% below 100" — STANDS-WITH-CORRECTION.** Math correct; but the two are distinct paths
   (always-on shrink floor vs optional critic lever) → "design tension", not "contradiction". Reworded.
4. **5-headline fit table — STANDS-WITH-CORRECTION.** No number invented (all fit-px/line-counts
   reproduced). Caveat added: the *function output* is 60px/1L, not proof of the browser render —
   `OVERSTAY MEANS DEPORTATION` overflows the 921.6 budget at 60px (1086px) because `_balance_headline`
   abandons wrapping for ≤3-word titles (`composer.py:561,565`); the browser may soft-wrap.
5. **Coupling thesis — STANDS-WITH-CORRECTION.** The central causal claim (shrink-before-word-wrap;
   `NEW IMMIGRATION RULES` → 64px not 2 lines) CONFIRMED on disk (`composer.py:767,810,827`). Overclaim
   corrected: "neither lever alone suffices" is true for the *copy cap* (proven) but NOT proven for the
   floor/wrap lever in general, and there is **no hard 3-line wall** (no `max_lines` in the fitter). Now
   framed as a sensible coupling, not a mathematical necessity.
6. **Recommendation `≤37 chars / floor 60→100` — CADE (as shipped), rebuilt.** 37 chars ≠ a 3-line
   guarantee (per-glyph counterexamples); and `floor=100` with `base=84` is an EMPTY `_max_fit_font`
   range → overflow, not legibility. The recommendation + checklist were rewritten to Codex's cure shape
   (target font ≥ base, wrap-before-shrink, drop the ≤3-word escape on overflow, real `max_lines`,
   per-glyph gate). The ≤37-char number survives **only as the editorial target**, which is this R's
   contribution; the code-cure remains Zero-gated.

Not verifiable from `composer.py` (Codex flagged, sourced elsewhere in-capture): the `83.2% / n=113`
figure (the prod-measurement B, cross-referenced), the ~110px grid factor (the critic source), and any
vertical wall (needs a browser render).
