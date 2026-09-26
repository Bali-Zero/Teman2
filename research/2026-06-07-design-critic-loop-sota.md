---
date: 2026-06-07
domain: marketing
topic: Autonomous "design critic" loop for rendered carousel slides (vision-look + measured-signals + levers + iterate)
sources:
  - https://arxiv.org/abs/2604.05839   # Vision-Guided Iterative Refinement for Frontend Code Generation (ICLR'26 RSI workshop)
  - https://arxiv.org/pdf/2412.16829   # Visual Prompting with Iterative Refinement for Design Critique Generation
  - https://arxiv.org/pdf/2509.16779   # Improving UI Generation Models from Designer Feedback
  - https://arxiv.org/pdf/2510.05571   # EvoPresent / PresAesth — self-improving aesthetic agents for slides
  - https://arxiv.org/pdf/2603.00155   # EfficientPosterGen — poster gen with violation detection
  - https://arxiv.org/pdf/2001.05424   # Scout — layout-quality model (misalignment/imbalance/density)
  - https://iterative-img-gen.github.io/   # Iterative Refinement Improves Compositional Image Generation (critic/editor/verifier)
  - https://arxiv.org/html/2503.12271v1 # Reflect-DiT — VLM verify-reflect loop
  - https://arxiv.org/abs/2509.10704    # Maestro — self-critique + verifier + MLLM-as-judge pairwise self-evolution
  - https://www.arxiv.org/pdf/2508.04732 # LumiGen — LVLM closed-loop visual critic
  - https://github.com/LAION-AI/aesthetic-predictor       # CLIP→aesthetic linear predictor
  - https://github.com/christophschuhmann/improved-aesthetic-predictor # CLIP+MLP aesthetic score
  - https://github.com/idealo/image-quality-assessment   # NIMA (aesthetic + technical)
  - https://github.com/xuebinqin/U-2-Net                 # U^2-Net salient object detection
  - https://github.com/jwagner/smartcrop.js              # content-aware crop / focal point
  - https://patents.google.com/patent/US6711291          # automatic text placement via saliency mask grid-search
  - https://www.smashingmagazine.com/2023/08/designing-accessible-text-over-images-part1/ # text-over-image techniques
  - https://m2.material.io/design/color/text-legibility.html # scrim opacity guidance
  - https://github.com/sanalabs/auto-text-size           # binary-search auto font fit
  - https://kizu.dev/fit-to-width/                       # fit-to-width text technique
  - https://arxiv.org/html/2501.17178v2                  # Tuning LLM-judge for 1/1000 cost
  - https://arxiv.org/pdf/2407.18370                     # Cascaded Selective Evaluation (Trust-or-Escalate)
  - https://onlinelibrary.wiley.com/doi/abs/10.1111/cgf.13010 # Kita — aesthetic rating of color palettes
---

# SOTA: Autonomous Design-Critic Loop for Rendered Carousel Slides

**Question this answers:** our naive plan is `vision-look + measured-contrast + adjustment-levers + iterate`. What is MISSING from that, based on real 2024-2026 prior art? Short answer: a lot of *cheap objective signals that should gate the expensive VLM*, a *richer rubric than "contrast"*, a *pairwise "is the new one better?" judge* (not just absolute scoring), a *verifier that protects brand/intent from the editor*, and *explicit convergence/cost machinery*. Details below, per-dimension, then a LEVERS table, an EXPANDED LOOP SPEC, and the WHAT-WE-WERE-MISSING list.

---

## 1. Vision-LLM as a design/UI critic (loop structure + rubrics)

The pattern we want is now a small but real research genre. Four reference loops:

- **Vision-Guided Iterative Refinement for Frontend Code Generation** ([2604.05839](https://arxiv.org/abs/2604.05839), ICLR'26 Recursive-Self-Improvement workshop). A VLM is a *visual critic* on the **rendered** webpage (not the code), emits **structured feedback**, which a secondary "critic" consolidates into one critique that drives a code edit + re-render. **+17.8% over 3 refinement cycles** on WebDev-Arena real queries; a single LLM pass is materially worse. Key takeaways for us: (a) critique the *render*, not the source; (b) **3 cycles** was the sweet spot; (c) a *consolidation* step between raw critique and edit reduces thrash.
- **Visual Prompting with Iterative Refinement for Design Critique Generation** ([2412.16829](https://arxiv.org/pdf/2412.16829), Gemini-1.5-Pro / GPT-4o). The VLM outputs **design comments + bounding boxes** that *localize* each comment to an image region; the loop iteratively refines both the text and the boxes with few-shot examples. Closed 50% of the gap to human-expert critique. Takeaway: **force the critic to ground every comment in a bbox/region** — un-grounded "make it pop" feedback is the failure mode.
- **Maestro** ([2509.10704](https://arxiv.org/abs/2509.10704)) — two innovations we are NOT currently planning: (1) **self-critique → verifier**: critic agents emit "interpretable edit signals", and a separate **verifier agent integrates them *while preserving user intent*"; (2) **self-evolution via MLLM-as-judge head-to-head**: it doesn't just score one image, it runs **pairwise comparisons** between candidates and keeps the winner. That tournament structure is more robust than absolute 1-10 scoring (which drifts).
- **Reflect-DiT** ([2503.12271](https://arxiv.org/html/2503.12271v1)) and **LumiGen** ([2508.04732](https://www.arxiv.org/pdf/2508.04732)): explicit **verify → reflect → adjust** loops with a VLM "visual critic" closing the loop; LumiGen splits into prompt-parsing vs visual-feedback modules. **Iterative Refinement Improves Compositional Image Generation** ([site](https://iterative-img-gen.github.io/), [2601.15286](https://arxiv.org/pdf/2601.15286)) formalizes the canonical 4 roles: **T2I-generator → VLM-critic → image-editor → verifier**, with a *test-time budget of 16 steps* and the finding that **iterative beats parallel** sampling for the same budget. Failure modes named: *imperfect critic feedback* and *editor execution errors* — both argue for objective gates that don't depend on the VLM being right.

**Rubric dimensions that recur across these + slide/poster work:** task/brief-fidelity (does the slide say what the brief wanted), **legibility**, **aesthetic quality**, visual **hierarchy**, **layout/alignment**, **color**, and *code/structure* quality. Loop structure consensus: **bounded N iterations (3-16)**, prefer **iterative over parallel**, **localize feedback to regions**, and **separate the editor from a verifier** that guards intent.

## 2. Text-over-image legibility & placement — beyond one contrast ratio

A single whole-region WCAG number is the weakest part of our plan. SOTA does three things we don't:

**(a) Saliency — find the busy part to AVOID.** The textbook method (US patent [US6711291](https://patents.google.com/patent/US6711291) "automatic text placement in digital images") builds a **saliency mask**, then **grid-searches** rectangles of the text-block size and picks the region of **minimum cumulative saliency** (least busy) that also has acceptable size and distance from salient objects. Tools that give you the saliency map cheaply:
- **OpenCV `cv2.saliency`** — `StaticSaliencySpectralResidual_create()` and `StaticSaliencyFineGrained_create()` return a float saliency map in milliseconds, zero ML deps ([OpenCV saliency demo repo](https://github.com/ivanred6/image_saliency_opencv)).
- **U^2-Net** ([xuebinqin/U-2-Net](https://github.com/xuebinqin/U-2-Net)) — learned salient-object detection; the tiny `u2netp.pth` is **4.7 MB**, good enough to mask the subject so text dodges it.
- **smartcrop.js** ([jwagner/smartcrop.js](https://github.com/jwagner/smartcrop.js)) — content-aware crop that ranks crops by an importance function and **boosts face regions**; <20 ms per image. Use it not only to crop but to read out the **focal point** so the layout knows where the hero subject is.

**(b) Local, not global, contrast + remedies.** Compute contrast **per text region (and ideally per line)** against the *actual pixels under the text*, then apply a remedy ladder rather than failing. The practitioner SOTA ([Smashing Magazine, 2023](https://www.smashingmagazine.com/2023/08/designing-accessible-text-over-images-part1/), [Material text-legibility](https://m2.material.io/design/color/text-legibility.html)):
- **Scrim/overlay gradient** — semi-transparent layer; Material's empirical bands: **dark scrim 20-40% opacity, light scrim 40-60%**, tuned to content. Drive the opacity *from the measured local luminance* (darker/busier bg → higher opacity) instead of a fixed value.
- **Strip/box behind text** ("highlight technique") — a guaranteed-contrast rectangle; most reliable, costs the most "design cleanliness".
- **Background blur / frosted-glass** behind the text block — reduces busyness without darkening the whole image.
- **Text-shadow vs stroke/outline** — shadow for soft separation, stroke for hard separation on high-frequency backgrounds (this is the per-letter remedy when a scrim isn't enough). The "Legibility Armor" already in our brand tokens is exactly this family — the loop should *choose among* shadow/stroke/scrim per-slide, not apply one statically.
- **Color flip** — switch white↔dark text based on the region's mean luminance (the standard light-on-dark / dark-on-light decision).
- **Copy-space placement** — move the text to a naturally clear area (this is where saliency from (a) feeds in).

**Key gap:** WCAG contrast is *necessary but not sufficient* over photos — high-frequency texture can satisfy 4.5:1 on average yet still be unreadable. That's why §4 (OCR round-trip) matters as the *true* legibility oracle.

## 3. Aesthetic / quality scoring models (an objective "does it look pro" gate)

Yes — usable, cheap, runnable locally, and they give a number to gate on:
- **NIMA** ([idealo/image-quality-assessment](https://github.com/idealo/image-quality-assessment)) — Google's Neural Image Assessment, **two heads: aesthetic + technical** quality, CNN transfer-learned on AVA. Outputs a score distribution → mean is your gate.
- **LAION aesthetic predictor** ([LAION-AI/aesthetic-predictor](https://github.com/LAION-AI/aesthetic-predictor)) and the **improved** MLP version ([christophschuhmann/improved-aesthetic-predictor](https://github.com/christophschuhmann/improved-aesthetic-predictor)) — a linear/MLP head on a **CLIP embedding**; trained on AVA + Simulacra + LAION-Logos. Sub-second on CPU once CLIP is loaded.
- **VLM-as-aesthetic-judge** — EvoPresent's **PresAesth** ([2510.05571](https://arxiv.org/pdf/2510.05571)) is a multi-task RL model trained on **2,000 slide pairs of varying aesthetic level** to do *reliable aesthetic scoring, defect adjustment, and comparative feedback*. The transferable idea: the aesthetic judge should also tell you *which defect* to fix, and should support **comparative (pairwise) feedback**, not just an absolute score. EvoPresent also reports a real **trade-off between visual design and content** — guard against the loop beautifying a slide into saying less.

Practical stance for us: use NIMA *or* the CLIP-aesthetic predictor as a **cheap absolute pre-gate** ("is this in the acceptable aesthetic band at all?"), and reserve the VLM for *diagnostic* + *pairwise* judgment.

## 4. OCR round-trip readability check (the strongest objective legibility signal)

This is the highest-value gate we are missing. Run OCR on the **rendered PNG** and check the title/CTA text comes back **verbatim** with high confidence; if OCR can't read it, a thumb-scrolling human won't either. It's used in production UI testing to "validate dynamically rendered text" and detect text baked into graphics ([OCR-powered UI test](https://serhat-ozdursun.medium.com/from-pixels-to-insights-how-i-built-an-ocr-powered-ui-test-in-typescript-fee96207d4c3)). Engines:
- **Tesseract (pytesseract)** — fastest on clean, CPU-only; gives per-word confidence.
- **EasyOCR** — slower but better on **stylized fonts / low-quality / multi-line** ([Tesseract vs EasyOCR](https://ironsoftware.com/csharp/ocr/blog/ocr-tools/easyocr-vs-tesseract/)) — closer to "is this legible to a human under noise".

Metric: **OCR round-trip score = normalized edit-distance between intended title string and OCR output**, plus min per-word confidence. A failed round-trip is a *hard* fail that fires a legibility lever (scrim↑ / size↑ / reposition) *before* spending a VLM call. Run it **at the IG render scale and again at a downscaled thumbnail size** — feed thumbnail simulates the feed; if it survives downscale-then-OCR, hierarchy is real.

## 5. Layout / composition critics (balance, whitespace, alignment, hierarchy)

Objective layout scoring predates the VLM era and is cheap because we *own the DOM/box geometry* (we don't need to infer boxes from pixels):
- **Scout** ([2001.05424](https://arxiv.org/pdf/2001.05424)) formalizes a **layout-quality model** with concrete sub-scores — **misalignment, imbalance, density** — plus per-group **size / balance (even margins) / alignment (count of shared edges)** scores. Because we render from HTML, we can compute these directly from element bounding boxes (no CV).
- **EfficientPosterGen** ([2603.00155](https://arxiv.org/pdf/2603.00155)) adds **violation detection** — explicitly checking for layout *rule violations* (overflow, overlap, off-grid, crowding) as a discrete pass, semantic-aware. This maps cleanly to a deterministic "lint" over our rendered layout.
- VLM rubric for *editorial* composition (from the critique papers + design canon): **rule-of-thirds / focal placement, visual balance, whitespace sufficiency & consistent gutters, grid alignment, visual hierarchy (clear primary→secondary→tertiary), reading-order flow, color harmony**.
- **Color harmony** can be scored, not just eyeballed: Kita & Miyata's model ([CGF 2016](https://onlinelibrary.wiley.com/doi/abs/10.1111/cgf.13010)) rates a palette against human preference; rule-based harmony (complementary/triadic/analogous) + a Random-Forest classifier hits ~80% ([Frontiers 2022](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2022.945951/full)). For a *fixed brand palette* this mostly becomes: "did we stay inside the palette and keep the accent ratio sane" — a deterministic check, not a model.

**Gap:** our plan has no *geometry-level* layout lint at all. We render HTML, so misalignment/overflow/overlap/whitespace are *free, exact* signals that should run before any pixel analysis.

## 6. The LEVERS — full menu, cheap → expensive

Cheap = pure CSS/DOM re-render of the **same** hero photo (Playwright, ~seconds). Expensive = regenerate the hero image (Flow/Nano-Banana, minutes + credits).

| Lever | Cheap / Expensive | When to pull | Source / basis |
|---|---|---|---|
| Scrim/overlay **opacity** (driven by local luminance) | Cheap | Local contrast or OCR round-trip fails | Material 20-40%/40-60% bands ([link](https://m2.material.io/design/color/text-legibility.html)) |
| **Text-color flip** (white↔dark) | Cheap | Region mean-luminance on wrong side | Smashing / Material |
| **Stroke** weight+color / **text-shadow** | Cheap | Per-letter/high-frequency bg defeats scrim | Smashing (Legibility Armor family) |
| **Background blur / frosted box** behind text | Cheap | Busy bg, want photo visible not darkened | Smashing |
| **Text reposition / anchor** to least-salient region | Cheap | Saliency says current spot is busy | US6711291 grid-search; OpenCV/U²-Net |
| **Font-size auto-fit** (binary search) | Cheap | Overflow/underflow, or thumbnail-OCR fails | auto-text-size ([link](https://github.com/sanalabs/auto-text-size)), fitty, ~10 iters |
| **Line-break / wrap point** (`text-wrap: balance`, fit-to-width) | Cheap | Ragged/orphan lines, awkward wrap | [fit-to-width](https://kizu.dev/fit-to-width/), CSS `text-wrap:balance` |
| **Photo crop / focal-point shift** (smartcrop) | Cheap (same asset) | Subject collides with text zone | [smartcrop.js](https://github.com/jwagner/smartcrop.js) |
| **Photo brightness/darken (CSS filter)** | Cheap | Whole-image too bright/dark for text | Smashing overlay |
| **Gradient direction / position** of scrim | Cheap | Text band needs the dark end where text is | Material gradient scrim |
| **Layout-family swap** (different brand template) | Cheap-ish | Hierarchy/balance lint fails structurally | Scout / our tokens.json layout families |
| **Strip/solid box behind text** | Cheap | Last-resort guaranteed contrast | Smashing "highlight" |
| **Regenerate hero image** (new prompt/seed) | **Expensive** | No CSS lever fixes it; subject wrong/ugly; aesthetic score below floor | Maestro/Reflect-DiT regenerate path |
| **Edit hero image** (inpaint/relight) | **Expensive** | Local fix (darken one corner, remove distractor) | iterative-img-gen editor role |

The dividing principle from all the image-loop papers: **exhaust the cheap CSS levers on the existing pixels before touching the generator.** Our renderer is HTML/CSS → almost every legibility/layout fix is on the cheap side, which is a big advantage their pixel-only pipelines didn't have.

## 7. Convergence & cost control

How the loops stop, and how they avoid burning VLM calls:
- **Bounded iterations.** Frontend-RSI used **3 cycles**; compositional-gen used a **16-step budget** and found *iterative > parallel* for the same budget. Pick a small cap (3-4 for a slide).
- **Score threshold + no-improvement stop.** Stop when the gate score clears a threshold OR fails to improve vs the previous iteration (plateau). Maestro's **pairwise MLLM-judge** ("is iteration *n* better than *n-1*?") is the robust stop signal — keep the best-so-far, stop when a new candidate doesn't beat it. Absolute 1-10 scores drift; **pairwise is more reliable**.
- **Cascade cheap→expensive evaluation** (this is the cost answer). FrugalGPT-style cascades and **Cascaded Selective Evaluation / "Trust-or-Escalate"** ([2407.18370](https://arxiv.org/pdf/2407.18370)) run a **weak/cheap judge first, escalate to the strong model only when confidence is low**, with provable human-agreement guarantees. **Tuning LLM-judge for 1/1000 cost** ([2501.17178](https://arxiv.org/html/2501.17178v2)) shows simple ensemble + task-specific criteria injection reach ~85% accuracy cheaply. Mapping to us: **deterministic + tiny-model gates first** (geometry lint, local contrast, OCR round-trip, NIMA/CLIP-aesthetic) and **only call the expensive VLM critic when those pass but something still feels off, or for the final pairwise "ship it?" judgment.** On a clean slide you may spend **zero** VLM calls.
- **Human-in-the-loop terminal gate.** Consistent with Bali Zero's Legge-5 (no auto-publish): the loop converges to a *proposed* slide + a one-line rationale; Antonello's "anteprima → dici cosa cambiare → re-render 2s" is the final stop. The loop's job is to make sure what's presented already passes every objective gate.

## EXPANDED LOOP SPEC (ordered cheap → expensive)

```
INPUT: brief + chosen layout-family + hero image + brand tokens (palette/fonts/Legibility-Armor)
state.best = none

repeat up to N=4:
  RENDER  HTML/CSS → PNG (Playwright)         # cheap, seconds

  # ---- TIER 0: deterministic, free (we own the DOM) ----
  G0 geometry lint (Scout/EfficientPosterGen): overflow? overlap? off-grid?
       misalignment / imbalance / density score; whitespace & gutter consistency
  G0 brand lint: colors ∈ palette? accent ratio sane? fonts correct?
       → if violation: pull cheap lever (size auto-fit, wrap-balance, layout-swap, recolor) → re-render

  # ---- TIER 1: cheap CV, sub-second ----
  G1 saliency map (OpenCV spectral-residual / U²-Net-p) → least-salient mask
       focal point (smartcrop) → does hero subject collide with text zone?
       → if collision: reposition text / shift crop → re-render
  G1 LOCAL contrast per text region & per line vs actual pixels under text (WCAG)
       → if < threshold: ladder = color-flip → scrim opacity (from local luminance)
         → stroke/shadow → frosted box → strip  → re-render

  # ---- TIER 2: cheap-ish objective oracles ----
  G2 OCR round-trip (tesseract fast; easyocr if stylized) at full + thumbnail scale
       title/CTA verbatim? per-word confidence ok?
       → if fail: scrim↑ / size↑ / reposition (legibility levers) → re-render
  G2 aesthetic floor: NIMA mean OR CLIP/LAION-aesthetic score ≥ brand floor
       → if below floor AND cheap levers exhausted: flag for image regen (Tier 4)

  # ---- TIER 3: the VLM critic (only if Tiers 0-2 pass but uncertain, or final pass) ----
  G3 VLM design critic on the RENDER, feedback grounded in bounding boxes:
       rubric = brief-fidelity, hierarchy, balance/whitespace, rule-of-thirds/focal,
                color harmony, legibility sanity, "looks professional?"
     VERIFIER step (separate, Maestro-style): translate critique → edit signals
       WHILE PRESERVING BRAND/INTENT (reject edits that break palette/voice/brief)
       → apply chosen levers → re-render

  # ---- ACCEPT / STOP ----
  PAIRWISE judge (Maestro): is this render better than state.best?
       if yes: state.best = this
  STOP if: all gates pass AND (score ≥ threshold OR no improvement vs last iter)

  # ---- TIER 4: EXPENSIVE, last resort ----
  if no cheap lever resolves a hard fail (ugly/irrelevant/unfixable subject):
       regenerate or inpaint hero image (Flow/Nano-Banana) → restart loop (budget-capped)

OUTPUT: state.best PNG + per-gate scorecard + one-line rationale → human review (Legge 5, no auto-publish)
```

Design rules baked in: **localize every critique to a region** (§1), **separate editor from a brand-protecting verifier** (Maestro), **pairwise "better-than-best" as the stop signal** (more reliable than absolute scores), **exhaust cheap CSS levers before image regen**, and **VLM is the last and rarest call**, not the first.

## WHAT WE WERE MISSING (the high-value delta)

Our naive plan = `vision-look + measured-contrast + levers + iterate`. Prior art says we omitted:

1. **OCR round-trip as the real legibility oracle.** Contrast ratio is necessary-not-sufficient over photos; OCR-readability (esp. at *thumbnail* scale) is the closest objective proxy for "a human can read it." Cheapest high-signal gate we had no plan for.
2. **Saliency / focal-point detection.** We never decide *where* text should go — SOTA places text in the **least-salient** region (grid-search over a saliency map; OpenCV/U²-Net/smartcrop). "Reposition text" is itself a lever, and the cheapest fix for many legibility fails.
3. **Per-region / per-line local contrast, not one whole-region average** — and a **remedy ladder** (color-flip → scrim-opacity-from-luminance → stroke/shadow → frosted box → strip) instead of a single binary pass/fail.
4. **Geometry-level layout lint** (misalignment / imbalance / density / overflow / overlap / off-grid / whitespace) — *free* for us because we render from HTML, yet entirely absent from our plan. (Scout, EfficientPosterGen violation-detection.)
5. **A real aesthetic gate** (NIMA / CLIP-LAION-aesthetic) to objectively answer "does this look professional" as a cheap pre-filter — and to *trigger image regen* when no CSS lever can save an ugly hero.
6. **A separate verifier that protects brand/intent from the editor** (Maestro). Without it, an autonomous critic will happily drift off-palette / off-voice / off-brief while "improving" the slide. Also guard the **design↔content trade-off** EvoPresent observed (don't beautify into saying less).
7. **Pairwise "is the new render better than the best-so-far" judgment** as the convergence signal — more stable than absolute 1-10 scores, which drift across iterations.
8. **Cascade cost discipline:** deterministic + tiny-model gates first; the expensive VLM only when cheap gates pass-but-uncertain or for the final ship/no-ship — potentially **zero** VLM calls on a clean slide. We had "iterate" but no cost gate, no plateau-stop, no escalation rule.
9. **Bounded budget + plateau stop** (3-4 iters; iterative beats parallel for a fixed budget) and a **best-so-far snapshot** so iteration can never make the output worse than a previous step.
10. **Grounded critique (bounding boxes).** Force the VLM to attach every comment to a region; un-grounded "make it pop" feedback is the documented failure mode and produces lever-thrash.
11. **The full cheap-lever menu** beyond scrim/stroke: **font-size auto-fit (binary search), `text-wrap:balance`/fit-to-width line-breaking, smartcrop focal shift, CSS brightness filter, gradient-direction, layout-family swap** — most of our wins are cheap CSS re-renders, which our HTML/CSS pipeline makes far easier than the pixel-only loops in the literature.
