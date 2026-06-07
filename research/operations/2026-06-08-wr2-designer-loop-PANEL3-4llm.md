---
date: 2026-06-08
domain: operations
panel: panel-3-go-no-go
subject: WR2 designer loop — after NB-1/2/3 fixes, post-orchestrator NB-1 math correction
predecessors:
  - research/operations/2026-06-07-wr2-designer-loop-gonogo-4llm-panel.md   # panel #1 NO-GO (5 defects)
  - research/operations/2026-06-07-wr2-designer-loop-REPANEL-4llm.md        # panel #2 NO-GO (NB-1/2/3)
panelists: [gemini-3.1-pro (red-team), codex-gpt5.5 (engineering), deepseek-v4-pro (logic), claude-opus-4.8 (synthesis/arbiter)]
panel_outputs: [/tmp/panel3-gemini.md, /tmp/panel3-codex.md, /tmp/panel3-deepseek.md]
verdict: GO-WITH-CONDITIONS
commits: [ee0fa443b (NB-1/2/3 first pass), a76c390c9 (NB-1 math fix + NB-4 + EXDEV)]
sources:
  - scripts/wr2_html_renderer/critic_signals.py
  - scripts/wr2_html_renderer/designer_loop.py
  - scripts/wr2_html_renderer/composer.py
  - scripts/wr2_html_renderer/renderer.py
---

# Panel #3 Go/No-Go — WR2 designer loop

## Verdict: **GO-WITH-CONDITIONS** (for wiring the loop CODE to the live pipeline)

The blocking math defect the panel found is **closed and empirically verified**; the
remaining conditions are Phase-3 WIRING tasks, not loop-code defects. Loop stays
standalone — NOT wired, NOT auto-publishing (Legge 5).

- **Gemini (red-team): NO-GO** → its top blocker (NB-1 metric unsound) was REAL and is now fixed.
- **DeepSeek (logic): NO-GO** → independently found the SAME NB-1 normalization contradiction. Fixed.
- **Codex (engineering): GO-WITH-CONDITIONS** → conditions met (working tree committed) or deferred to Phase-3.
- **Claude (synthesis/arbiter): GO-WITH-CONDITIONS** — after fixing NB-1 math and committing NB-4/EXDEV.

4/4 LLMs alive (Claude OAuth, Gemini agy, Codex gpt-5.5 NO 401, DeepSeek v4-pro real model).
Asymmetric-adversarial. Every load-bearing file:line re-verified on disk by the arbiter,
AND the NB-1 fix was verified EMPIRICALLY (not just by unit test).

## The blocker the panel caught (and the orchestrator's arbitration)

**NB-1 metric was mathematically unsound** — found independently by Gemini AND DeepSeek,
on different vendors, with the same root cause. Codex MISSED it (it reviewed integration,
not the normalization math) and would have GO'd a broken metric. This is the asymmetric
panel working as designed: redundant adversarial coverage caught what one reviewer missed.

Root cause (re-verified on disk, `critic_signals.py:200-219` pre-fix):
`_local_variance_saliency` divided by the image's OWN max (`/ local_var.max()`). The scrim
lever scales background luminance by factor c, hence local variance by c², but the per-image
max ALSO scales by c² → they cancel → the `0.5*bg_var` term is **invariant to the scrim**.
Half the NB-1 metric was dead: the scrim could never move it. Compounding (DeepSeek): the
absolute `BUSY_BAND_ABS_FLOOR=0.08` was compared against this per-image-RELATIVE value →
not comparable across heroes.

The synthetic NB-1 tests passed anyway because the OTHER half (the `0.5*luminance` term) DID
drop with the scrim, and the test heroes were luminance-dominated. On a real TEXTURED busy
hero — the exact case the deadlock hits — the dead variance half would keep the metric above
the floor → deadlock persists. A mis-solve, not a close.

**Arbiter fix (commit a76c390c9):** `_local_variance_saliency(normalize=False)` for the
background path → ABSOLUTE variance of luminance-in-0..1 (0..~0.25), ×4-rescaled to 0..1 to
share the luminance term's range. Both halves now strictly decrease with the scrim AND sit on
an absolute scale the floor can gate. Legacy `saliency_map`/band-selection keeps normalize=True
(relative is correct for ranking bands within one image).

**Empirical verification (orchestrator, not unit test):** textured busy hero, bottom-band
busyness as the scrim darkens: `0.2565 → 0.2119 → 0.1643 → 0.1333 → 0.0940 → 0.0620` —
strictly monotonic, crosses 0.08 → the gate is now satisfiable. Flat-bright hero not
over-flagged.

## Other findings (arbitrated)

| Finding | By | On-disk verdict | Disposition |
|---|---|---|---|
| NB-1 normalize/scrim-invariant | Gemini+DeepSeek | REAL, confirmed + empirically fixed | **CLOSED** (a76c390c9) |
| NB-4 fail-open (best_png could be brand-rejected) | worktree/Codex | REAL — best_verified_png split implemented | **CLOSED** (a76c390c9, 4 tests) |
| EXDEV cross-device os.replace crash | Codex | REAL — shutil.move fallback added | **CLOSED** (a76c390c9; caveat: catches broad OSError) |
| `ee0fa443b` ≠ on-disk (NB-4 uncommitted) | Codex | REAL — 0 vs 8 occurrences of best_verified_png | **CLOSED** (committed a76c390c9) |
| NB-3 over-blocks dark/flat heroes | Gemini | numbers exact (`renderer.py:361` bright_frac>0.4 ∧ spread>40) BUT this is the PRE-EXISTING anti-Canva hero gate, not introduced by NB-3; NB-3 correctly gates on res.ok | Non-blocker — Phase-3 threshold tuning vs real heroes |
| NB-2 temp-dir race | (assessed) | safe (per-call mkdtemp + finally rmtree + sync move) | CLOSED |
| NB-3 res.ok gating | Codex | correct promotion contract | CLOSED |

## Conditions to clear before/at Phase-3 wiring (NOT loop-code defects)
1. Phase-3 controller MUST assert ALL of {`WR2_VISION_REQUIRED=1`, `use_vision=True`,
   `vision_critic` configured, `brand_verifier` configured} — else cheap-only or no-brand
   convergence is reachable (DeepSeek + Codex).
2. Phase-3 controller MUST catch per-slide `render_fn` exceptions (a mkdtemp/copy/os.replace
   failure currently aborts the caller — `designer_loop.py` awaits render directly) and treat
   them as a slide render failure, not a crash.
3. Add a per-carousel paid-vision budget/cache (worst case 6 Claude calls/slide × N slides).
4. Log real-hero bottom-band busyness on the first live carousels before fully trusting the
   `BUSY_BAND_ABS_FLOOR=0.08` value (tuned on synthetic + verified monotonic; real-hero scale
   should match the 0..1 normalization but confirm), and tune `_hero_visible_in_png`
   thresholds (`renderer.py:361`) against real dark/cinematic heroes if any are wrongly rejected.
5. Require `result.converged and final_png and final_png.exists()` before marking a slide
   `rendered`; refuse the carousel unless every slide is converged with no required gate degraded.

## Method honesty
Panel ran 4/4 alive. Raw outputs on disk: /tmp/panel3-{gemini,codex,deepseek}.md (50/33/54
lines). The Gemini↔Codex disagreement on NB-1 was resolved by READING THE CODE and RUNNING AN
EMPIRICAL MONOTONICITY TEST, not by majority vote — and the minority-of-one (Codex GO) was the
one that missed the real defect, vindicating the asymmetric design. The arbiter wrote the NB-1
math fix itself (localized, precise) rather than re-dispatching. Loop remains standalone; wiring
is Phase 3, which the conditions above gate.
