---
date: 2026-06-07
domain: operations
panel: re-panel-go-no-go
subject: WR2 designer loop — AFTER the 5 blocking fixes (commit 12f75905c)
predecessor: research/operations/2026-06-07-wr2-designer-loop-gonogo-4llm-panel.md
panelists: [gemini-3.1-pro (red-team), codex-gpt5.5 (engineering), deepseek-v4-pro (logic), claude-opus-4.8 (synthesis)]
panel_outputs: [/tmp/repanel-gemini.md, /tmp/repanel-codex.md, /tmp/repanel-deepseek.md]
verdict: NO-GO
sources:
  - scripts/wr2_html_renderer/designer_loop.py
  - scripts/wr2_html_renderer/critic_signals.py
  - scripts/wr2_html_renderer/claude_vision.py
  - scripts/wr2_html_renderer/ocr_check.py
  - scripts/wr2_html_renderer/composer.py
  - scripts/wr2_html_renderer/renderer.py
---

# RE-PANEL Go/No-Go — WR2 designer loop, after fixes A-E

## Verdict: **NO-GO** (for live-wiring to `war_room_drafts`)

- **Gemini (red-team): NO-GO**
- **Codex (engineering): NO-GO**
- **DeepSeek (logic): GO-WITH-CONDITIONS** (config-level: brand verifier mandatory + `WR2_VISION_REQUIRED=1`; found no code-level contradiction)
- **Claude (synthesis): NO-GO** — the 5 original defects ARE closed, but fixes B and E
  introduced/left **3 NEW blocking defects**, all re-verified on disk this turn.

The 4-LLM health-check passed 4/4 (Claude OAuth, Gemini agy, Codex gpt-5.5 — **no 401**,
DeepSeek v4-pro HTTP 200, real model not the flash-alias). Asymmetric-adversarial roles,
not consensus. Every file:line below was **re-verified on disk by the orchestrator** (the
panelists' citations are leads, not facts — autopsy-hallucination scar).

## What the fixes DID close (the original 5 — confirmed)

The previous NO-GO's 5 defects are genuinely fixed (19/19 offline tests, re-run by the
orchestrator this turn, exit 0):
- **A** brand verifier now gates a vision-PASS (`designer_loop.py:349-377` — verifier runs
  on `png_path` BEFORE `return converged=True`; block → keep-best-and-stop).
- **C** vision critic fails closed under `WR2_VISION_REQUIRED` (`claude_vision.py:123-204`);
  `_run_claude_json` catches `OSError`; brand verifier always fails closed.
- **D** `is_text_legibility_claim` word-boundary + `NEGATIVE_CLAIM_KEYWORDS` veto
  (`ocr_check.py:193+`) — "serif font" → False, "clipped" → True.
- **A+D logic**: DeepSeek confirmed the OCR-override + fail-open-vision combination CANNOT
  let a brand-violating slide converge (a font/palette block is non-overridable → loop
  breaks). Logically consistent.
- **B/E** partially (see below).

## NEW BLOCKING defects (the re-panel's finding) — re-verified on disk

### NB-1 — Fix B introduced a functional DEADLOCK on hero slides (Gemini)
`critic_signals.py:146-161` + `designer_loop.py:190-203`. Fix B switched the busyness
metric to the RENDERED PNG (`calmest_band(png_path)`), which is correct in principle, but
the rendered PNG has the **white headline burned into the bottom band**. White text on a
darkening scrim = high local luminance variance → the bottom band reads as busy. The gate
(`designer_loop.py:193`) is *relative* (`busyness[bottom] > min(busyness)*1.5`), so it does
NOT hang forever (max_iters=3 — Codex & DeepSeek correctly verified termination). The real
harm is subtler: the scrim lever darkens the background but **cannot remove the text's own
variance**, so on a genuinely busy hero the check may never clear within 3 iterations → the
loop spins the cheap tier and **never reaches the paid vision tier** for that slide. It
terminates, but starved. *Gemini verified "does it make useful progress" = NO; Codex/DeepSeek
verified "does it terminate" = YES. Both correct, different question.* **This is a regression
introduced by fix B itself.**

### NB-2 — Fix E race: every slide renders to `slides/01.png` (Gemini + Codex)
`composer.py:479-480` (the code's OWN comment): *"render_html_files writes PNG to
(render_root/slides)/f'{enum_idx:02d}.png' where enum_idx is the 1-based position in the
list → always '01' here."* `make_slide_render_fn` renders a 1-element list per slide, so the
renderer always writes `render_root/slides/01.png`, then `produced.replace(png_path)` moves
it. If the live pipeline processes slides **concurrently on the same `render_root`**, they
collide on `01.png` before the `.replace` → silent slide swap/corruption. The 19 tests are
sequential standalone, so they don't surface it. Blocking for any parallel live driver.

### NB-3 — Fix E ignores `RenderResult.ok` (Codex)
`renderer.py:285` appends `png_paths` BEFORE `renderer.py:292-294` records the hero-visibility
`failures`; `.ok` = `not failures AND heroes_placed == heroes_expected` (`renderer.py:74-76`).
`composer.py:495` promotes on `if not res.png_paths` — so a render that wrote a PNG but
**failed the hero-placement gate** (heroes_placed ≠ heroes_expected) has non-empty `png_paths`
and gets promoted anyway. The anti-Canva contract (`.ok`) is bypassed. Correct gate:
`if not res.ok or not res.png_paths`. Re-verified on disk.

## Non-blocking (carried forward, do not gate live-wiring on these)
- Stale destination `iter-XX.png` in a reused `out_dir` could be critiqued on a failed retry
  (Codex `designer_loop.py:292`) — close alongside NB-3 (unlink/atomic-replace).
- `run_designer_loop` doesn't catch `render_fn` exceptions; trial brand verifier called without
  `trial_png.is_file()` check (Codex `designer_loop.py:295,395`) — graceful-degradation polish.
- Paid vision cost bounded at **6 Claude CLI calls/slide** worst-case (3×[critic+verifier]) —
  Codex wants a carousel-level budget/cache before live (not blocking, but wire it in Phase 3).
- `WR2_VISION_REQUIRED` alone is insufficient: Phase 3 must assert ALL of
  {`WR2_VISION_REQUIRED=1`, `use_vision=True`, `vision_critic` set, `brand_verifier` set} —
  else cheap-only or no-brand convergence is still reachable (DeepSeek + Codex agree).
- Layout-family mapping incomplete; monotony; no aesthetic pre-gate — known, deferred.

## Conditions to flip to GO (next iteration)
1. **NB-1**: rethink the hero busyness metric so the scrim lever can actually satisfy it —
   e.g. measure busyness on the scrim/background layer EXCLUDING the text glyph region, or
   gate on background-band variance only. (The metric must move when the lever moves, without
   the text's own variance dominating.)
2. **NB-2**: give each slide a unique render target (render into a per-slide/per-attempt temp
   dir, or pass the real enum index) so concurrent slides never collide on `01.png`. Then
   atomic-replace into `png_path`.
3. **NB-3**: gate promotion on `res.ok` (not just `res.png_paths`) so a hero-placement failure
   never promotes.
4. Phase-3 controller asserts the 4 vision/brand preconditions above; add a per-carousel paid-
   call budget.
5. Re-run this panel after NB-1..3; expected GO or GO-WITH-CONDITIONS.

## Method honesty
Panel ran 4/4 LLMs alive (≥2 non-Claude vendors). Raw outputs on disk: `/tmp/repanel-gemini.md`,
`/tmp/repanel-codex.md`, `/tmp/repanel-deepseek.md` (DeepSeek's verdict line was truncated by
max_tokens=4000 but its body argued GO-WITH-CONDITIONS on config grounds, no code contradiction).
The orchestrator independently re-verified NB-1/2/3 on disk before recording them — the
Gemini↔Codex/DeepSeek disagreement on fix B was resolved by reading the code, not by vote.
Loop remains standalone — NOT wired. Wiring stays Phase 3, re-gated by the next panel.
