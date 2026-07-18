---
date: 2026-07-18
domain: marketing
client_case: none — WR2 growth loop SPRINT R
adversarial_review: codex
sources:
  - research/2026-06-07-design-critic-loop-sota.md (§4 OCR round-trip incl. thumbnail-downscale, §5 geometry lint overlap/off-grid/DOM-overflow, §7 cheap→VLM cascade — the render-QA SOTA, already researched)
  - research/2026-06-07-html-css-carousel-renderer-sota.md (Dim.4 web-font determinism + document.fonts.ready readiness gate:309,354; Dim.5:374 hero placement)
  - scripts/wr2_html_renderer/ocr_check.py:118 (OCR round-trip gate — BUILT, but reads the FULL-SIZE PNG, no thumbnail downscale)
  - scripts/wr2_html_renderer/renderer.py:209,266-278 (document.fonts.check('800 16px Montserrat') → W99 BRAND FONT NOT LOADED hard gate)
  - scripts/wr2_html_renderer/critic_signals.py:274 (geometry lint — only near-empty + bottom-edge ink; no overlap/off-grid/DOM-overflow)
  - scripts/wr2_html_renderer/designer_loop.py:568,573,682,584 (OCR Tier-1.5 called each iter but passes without OCR on no-headline/critic-None/degraded; :584 heading lever is SHRINK-only)
  - scripts/wr2_html_renderer/composer.py:347,354,421,499 (heading grow clamp (100,150) applies ABSOLUTE px; cover fit/wrap computed at 84px — clamp bounds font size, NOT box overflow)
  - scripts/wr2_html_renderer/claude_vision.py:82,95,118,158,297 (lever menu excludes heading; prompt "not merely small at thumbnail scale"; but target is a FREE STRING and the parser filters only the lever NAME, not the target)
  - apps/backend-rag/backend/tests/unit/scripts/test_wr2_html_render_apply.py:2079,2084 (a test ALREADY exercises grow_font target=heading + asserts grown heading stays largest)
  - scripts/wr2_draft_generator.py:333,422 (generator already caps headline ≤6 words / ≤60 chars — a copy/template co-cause is possible)
  - LIVE Pro (ssh this session, NOT reproducible from repo): com.balizero.wr2.html-apply.plist WR2_VISION_REQUIRED=1; launchctl daemon loaded exit 0; EasyOCR+torch importable in .venv-wr2-html; ~/logs/wr2-html-apply.log designer-loop WARNINGs through 2026-07-18 05:37
---

# WR2 render/visual-QA: research done, build PARTIAL — the live growth lever is the un-grown hero headline

**Two findings, one sprint — both rewritten after a Codex adversarial CADE (see §Adversarial
review; the pre-review draft over-claimed "gate-complete" and "the clamp already bounds
overflow").** (1) A *constraint result*: the render/visual-QA SOTA is **already researched** (the
2026-06-07 pair) — do NOT re-research it — but the **build is a PARTIAL subset** of that research,
and the built gates are **armed-live** (verified by ssh to the Pro this session) though not
all-blocking. (2) The *actionable* result: production hero-photo covers recurrently ship with a
headline too small for the Instagram grid thumbnail; the armed critic detects it and reports it
cannot fix it, because the critic's lever menu + prompt steer it away from `grow_font
target=heading` — a composer↔critic inconsistency, with the renderer's `heading:(100,150)` grow
clamp lying dormant. Fixing it needs a fit/overflow guard the original draft wrongly assumed free.

## Finding 1 — render-QA research is done; the build is a partial, armed subset (constraint)

**This started as a proposed SPRINT R** ("SOTA for a deterministic visual-QA gate — font-load,
overflow, contrast, placeholder — before `drafted`"). GROUND falsified the *research* half:

- **The render-QA SOTA is already researched (2 true twins).** `research/2026-06-07-design-critic-
  loop-sota.md` covers the cheap-deterministic-gates→VLM cascade (§4 OCR round-trip *including a
  thumbnail-downscale pass*; §5 geometry lint for overlap/off-grid/DOM-overflow; §7 FrugalGPT-style
  cascade). `research/2026-06-07-html-css-carousel-renderer-sota.md` covers web-font determinism +
  the `document.fonts.ready` readiness gate (Dim.4:309,354; Dim.5:374 is hero placement, not font
  readiness — a citation the first draft got wrong). *(Correction: the three 2026-07-18 captures —
  selection, metrics, fact-check — are NOT render-QA twins; they were twins of this session's
  EARLIER R attempts. So this is the render-QA question's 2nd encounter, not a "4th twin".)*
- **The build is a PARTIAL subset of that research — NOT "gate-complete".** Built and present:
  the font-load hard gate (`renderer.py:266-278`), an OCR round-trip (`ocr_check.py`), local
  per-region contrast. **Under-built vs the research:** the OCR reads the **full-size** PNG only
  (`ocr_check.py:118`) — the research's *thumbnail-downscale* OCR (the exact IG-grid legibility
  oracle) is NOT built; the geometry lint catches only near-empty + bottom-edge ink
  (`critic_signals.py:274`), not the overlap/off-grid/DOM-overflow the research specifies. So there
  IS a narrow unbuilt surface here — see the convergence in the recommendation.
- **The built gates are ARMED-LIVE — scoped honestly.** Verified **by ssh to the Pro this session
  (not reproducible from the repo)**: `WR2_VISION_REQUIRED=1` on the live plist (so the daemon takes
  the `run_designer_loop` per-slide path, not the fast `compose_carousel` path); `launchctl` shows
  the daemon loaded, last exit 0; EasyOCR + torch import cleanly in the live `.venv-wr2-html`; and
  `~/logs/wr2-html-apply.log` shows the designer-loop firing on real decks with per-slide vision
  critiques **through 2026-07-18 05:37 this morning**. **What this does NOT prove** (Codex, correctly):
  importability ≠ reader initialization ≠ a per-deck OCR *verdict*; the OCR tier is called each
  iteration (`designer_loop.py:682`) but passes without OCR on no-headline / `ocr_critic is None` /
  degraded (`:568,:573`); and the vision path is not an absolute block — it accepts up to
  `WR2_MAX_WEAK_SLIDES=1` weak slide per carousel. "Armed" = invoked code path + live config + deps
  importable + the enclosing loop provably firing — NOT a per-deck OCR-fired receipt, NOT all-blocking.

**Recommendation 1.** Do NOT re-research the render-QA cascade (the 06-07 pair is authoritative).
The remaining work is a NARROW BUILD gap, and it *converges with Finding 2*: the single unbuilt
gate that most matters is the **thumbnail-downscale OCR pass** — it is exactly the objective oracle
that would catch a thumbnail-illegible headline. Build that, and it becomes the verifier the
Finding-2 fix needs.

## Finding 2 — the live growth lever: hero-cover headline sits dormant-un-grown (composer↔critic split)

The same live logs expose a recurring defect the loop flags but does not fix. On hero-photo cover
slides the designer-loop repeatedly logs (real decks, 2026-07-14 23:29 · 2026-07-16 05:42 ·
**2026-07-18 05:37**):

> *"Headline styled as a small, thin centered caption (~28% of canvas width) rather than a dominant
> hook — will not survive Instagram grid thumbnail scale… No lever in the current set (grow_font is
> scoped to subhead/body) can grow the headline itself."*

and accepts the slide as "composition debt (not CSS-fixable)". Root cause (verified on disk):

- **The renderer CAN grow the headline.** `composer.py:354` defines `"heading": (100, 150)` (title
  grows from 84px base to 150px), `:347` documenting it as the intended hierarchy-inversion fix
  ("grow the TITLE (grow_font target=heading), whose clamp stays the largest"). A test already
  exercises this path and asserts the grown heading stays largest
  (`test_wr2_html_render_apply.py:2079,2084`).
- **But the critic is steered away from it.** `claude_vision.py:82` lists `grow_font # target:
  subhead|body` (heading omitted) and `:158` says grow only "AT FULL OPEN SIZE (not merely small at
  thumbnail scale)" — the exact IG failure mode is excluded. The only heading-targeted proposer is
  `designer_loop.py:584`, `shrink_font` (shrink-only, on OCR fail).
- **So it is DORMANT config, not a dead capability** (Codex correction — the first draft said
  "un-growable / no proposer ever"). The lever `target` is a free string and the parser filters only
  the lever NAME, not the target (`claude_vision.py:95,297`), so the VLM *could* already emit
  `heading` by ignoring the prompt; no *deterministic* producer emits it, and the prompt actively
  discourages it. In practice the heading is never grown for the thumbnail problem.

**Recommendation 2 (the next SPRINT B) — corrected for the overflow risk the first draft missed.**
Align the critic's lever menu + prompt with the renderer's heading clamp AND add the fit guard:
(a) add `heading` to the `grow_font` targets (`claude_vision.py:82,158`) and permit it for
**thumbnail-scale** illegibility, not only full-open size; (b) **do NOT assume the (100,150) clamp
is overflow-safe** — it bounds the font px, not the resulting box: the grow applies absolute
100–150px (`composer.py:421`) while cover wrap/fit is computed at 84px (`composer.py:499`), and the
geometry lint does not catch horizontal/top overflow. The B MUST add a re-fit/re-wrap at the
proposed size + a DOM bounding-box overflow check and/or the thumbnail-downscale OCR from Finding 1;
(c) keep the hierarchy guard (subhead capped under title; title stays largest — already tested);
(d) note 150px is not a universal thumbnail guarantee (at the ~110px cover context the critic prompt
also cites, `150×110/1080 ≈ 15px`), and the generator already caps headlines ≤6 words / ≤60 chars
(`wr2_draft_generator.py:333,422`) — so **investigate whether caption-style templating or copy
length is a co-cause** before assuming the lever alone suffices. Behavior change to the critic ⇒
generator≠grader (Sonnet implementer + Codex red-team) + tests on SHORT and LONG hooks with a
thumbnail-legibility assertion. **Atteso:** hero covers stop shipping thumbnail-illegible hooks as
accepted "composition debt" — with an overflow guard so the cure doesn't push the title off-canvas.

## Anti-twin note (so the next session doesn't re-walk this)

Render/critic/renderer SOTA = the two 2026-06-07 files (authoritative — don't re-research). This
sprint's *new* surface: (i) the render-QA BUILD is a partial subset of that research (missing
thumbnail-downscale OCR + full geometry lint); (ii) the `grow_font`-heading composer↔critic
inconsistency. Both feed one next B. Everything else is verification, not new research.

## Adversarial review

Reviewed by Codex `gpt-5.6-sol` (high effort), generator≠grader — the author did not grade it.
The draft was **rewritten**, not merely tuned:

- **Finding 1 — VERDICT: CADE.** The "already-researched" half held, but "gate-complete" and
  "armed/firing" were over-claimed. Sustained defects: (1) the OCR reads the full-size PNG only
  (`ocr_check.py:118`) — the research's thumbnail-downscale pass is unbuilt; the geometry lint is
  near-empty/bottom-ink only (`critic_signals.py:274`), not the researched overlap/off-grid/DOM-
  overflow → **"gate-complete" retracted**, reframed as a partial subset with a named build gap.
  (2) importability ≠ reader-init ≠ per-deck OCR verdict; the OCR tier can pass without running
  (`designer_loop.py:568,573`); the vision path allows 1 weak slide (`WR2_MAX_WEAK_SLIDES=1`) →
  **"armed" scope tightened + live claims explicitly attributed to this-session ssh** (Codex is
  repo-sandboxed and cannot see them; they are real tool outputs, not hallucinated, but not
  repo-reproducible). (3) the three 2026-07-18 captures are not render-QA twins → **"4th twin"
  corrected to the 2 true 06-07 twins**; Dim.4 vs Dim.5 citation fixed.
- **Finding 2 — VERDICT: STANDS-WITH-CORRECTION.** The composer↔critic inconsistency is real and
  actionable. Corrections applied: (1) "un-growable / no proposer ever" → **"dormant config"** (free-
  string `target`, parser filters only the lever name, a test already exercises heading-grow). (2)
  **the overflow-safety claim was WRONG and is retracted** — the clamp bounds font px, not box
  overflow (`composer.py:421` abs px vs `:499` fit-at-84px); the B now REQUIRES a re-fit/DOM-bbox/
  thumbnail-OCR guard. (3) added that 150px is not a universal thumbnail guarantee and that copy
  length / caption templating may be a co-cause (`wr2_draft_generator.py:333,422`). Hierarchy risk
  confirmed LOW.

**Net:** the sprint's value is a corrected constraint-result (render-QA research done, build partial-
but-armed) plus one sharp, de-risked next B (the dormant heading-grow lever, gated by the unbuilt
thumbnail-downscale OCR). generator≠grader caught an overflow bug the naive fix would have shipped.
