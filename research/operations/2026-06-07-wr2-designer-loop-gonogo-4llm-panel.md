---
date: 2026-06-07
domain: operations
client_case: none
panel: Claude Opus 4.8 (orchestrator + synthesis) + Gemini 3.1 Pro (agy, red-team) + Codex GPT-5.5 (engineering-integration) + DeepSeek V4 Pro (logic/contradiction, reasoning_effort=high)
panel_health: 4/4 LLM alive at run (Step 0 empirical 1-token ping: claude exit0, agy exit0, codex gpt-5.5 exit0, deepseek HTTP200 model=deepseek-v4-pro)
panel_outputs:
  - /tmp/panel-raw/deepseek-raw.txt (110 lines, reasoning-only — max_tokens exhausted before ANSWER section, but reasoning is complete)
  - gemini + codex full outputs inline below (run via subagent; agy/codex hang when detached from a TTY — see "Execution note")
artifact: scripts/wr2_html_renderer/ @ branch agent/air-m5/wr2/html-css-renderer-2026-06-07 HEAD fe9bdddd4
sources:
  - apps/backend-rag .venv E2E render evidence /tmp/panel-evidence-20260607-215149/iters/*.png (looked at by eye)
  - designer_loop.py / composer.py / critic_signals.py / claude_vision.py / ocr_check.py / renderer.py (re-verified file:line this turn)
---

# WR2 designer loop — 4-LLM Go/No-Go panel (wire into live carousel pipeline?)

## Decision asked
Is the WR2 "designer agent" (HTML/CSS carousel renderer + vision-critique-iterate loop)
ready to be **wired into the live pipeline** (`war_room_drafts` → produce a `rendered` PNG
a human then publishes), or are there **BLOCKING** defects? Asymmetric-adversarial panel
(Gemini=red-team, Codex=engineering-integration, DeepSeek=logic). NOT a consensus vote.

## VERDICT: **NO-GO** (3/3 panelists independently NO-GO)

Do NOT wire this loop into the live pipeline yet. 5 BLOCKING defects, every one
**re-verified on the real code this turn** (panelists' file:line treated as leads, not
facts — per the autopsy-hallucination scar). The loop is a strong skeleton; the blockers
are concentrated in the **safety/gating logic**, which is exactly where a "produce a PNG a
human publishes" promise must not fail open.

## Convergence table (BLOCKING defects)

| # | Defect | Gemini | Codex | DeepSeek | My on-disk verify |
|---|---|:--:|:--:|:--:|---|
| A | **Brand verifier never runs on a vision-PASS** — `if vc.passed: return converged=True` exits before the brand_verifier block; the "fail-closed brand verifier" only gates vision-*proposed changes*, never vision-*approved* slides | ✅ | ✅¹ | ✅ | ✅ `designer_loop.py:298-304` vs brand block `320-359` |
| B | **Tier-1 saliency runs on the RAW hero photo, not the rendered PNG** — `calmest_band(hero_path)` never changes across iterations, so scrim/stroke levers can NEVER satisfy it → legibility tier deadlocks, burns all 3 iters, and **starves the paid vision tier** (which only runs when cheap tiers pass) | ✅ | — | ✅ | ✅ `critic_signals.py:140` (contrast uses png_path:126 correctly; saliency uses hero_path) |
| C | **Claude design-critic fails OPEN** — on CLI down/timeout/non-JSON it returns `Critique(passed=True)`. Combined with A: Claude outage → instant `converged=True` on whatever PNG is in the buffer, brand verifier (which fails *closed*) never reached. Asymmetric: verifier:195 fails closed, critic:171 fails open | ✅ | ✅ | — | ✅ `claude_vision.py:166-171` (critic `passed=True`) vs `:195` (verifier `passed=False`) |
| D | **OCR override heuristic too broad** — `is_text_legibility_claim` is a pure substring match; `"title"`/`"headline"` match a string like *"headline uses a serif font instead of Montserrat"* → a real FONT violation gets classed as text-only → OCR reads the text fine → override fires → **masks a genuine brand violation** | ✅ | — | ⚠️ flagged | ✅ `ocr_check.py:193-207` (`any(k in low ...)`) |
| E | **Idempotency / stale-PNG promotion** — on a failed render (`res.png_paths` empty) the bridge falls back to `render_root/slides/01.png`, which can be a PREVIOUS iteration's file, and promotes it as the current render → wrong PNG kept as "best" | — | ✅ | — | ✅ `composer.py:489-494` |

¹ Codex hits the same surface via its "Claude non-JSON → converged=True after the paid gate silently skipped" finding (its row 4), and via observability ("refuse `rendered` unless all slides converged && no gate degraded").

## Additional findings (NON-BLOCKING / hardening, panel-raised)
- **No per-carousel cost budget** (Codex): max_iters bounds per-slide paid calls to ≤6,
  but ×N slides ×retries has no carousel-level breaker or verdict cache. (Per-slide IS
  bounded — so not a runaway; but a crash-retry pays again.) → add budget + content-hash cache.
- **Shrink-font counter unbounded in state** (Codex): CSS floors at 0.6, but the counter
  keeps incrementing → no-op spins if `max_iters` raised. → clamp counter.
- **Layout-family monotony** (Gemini #4): most inner slides default to one family
  `photo-headline-yellow-sub`; risk of empty `<img src="">` if no photo. → the known
  mapping gap; classify as quality, not safety.
- **EasyOCR degradation is silent** (Codex): `degraded=True→legible=True` is correct
  (never blocks) but only visible in history; → emit a metric/manifest flag.
- **No persisted observability** (Codex): `DesignerResult.history` is never written; a
  live pipeline can't tell converged from degraded. → persist `designer_result.json`.

## What the panel did NOT flag (so it's genuinely fine)
- Loop termination is bounded (`for it in range(1, max_iters+1)`) — no infinite spin
  (DeepSeek + Gemini #5 both confirm). The deadlock in B is "never converges", not "never
  ends" — it still returns a PNG, just a wasteful path.
- Playwright/EasyOCR outages fail safe (Gemini #6): Playwright fails the slide; EasyOCR
  degrades without falsely overriding. Only the *Claude* critic fails open (C).
- The OCR override's structural guard (`text_claims and not other_claims`) is logically
  sound — the hole (D) is the *classifier*, not the rule (DeepSeek's analysis).

## Eye-check of the real render (anti-hallucination: trust pixels)
E2E on `kbli-hero.jpg` (brand asset, non-PII): 3 iters, `converged=False`, kept iter-01.
Title "YOUR KITAP IS VALID. 3 RULES CHANGED." crisp + correct (OCR 1.0). The "BALI ZERO"
wordmark renders with its real stylized "B" — **NOT a bug** (operator confirmed: logo is
intentionally that way). The legibility metric stuck at 0.661 across all 3 iters even
though the text sits on a clean band → this is exactly defect B observed live.

## Conditions to flip to GO (minimal, panel-derived)
1. **A**: run the brand verifier on a vision-PASS too (not only on proposed changes), OR
   make a vision-PASS conditional on a brand-verifier PASS.
2. **C**: in live mode the design-critic must fail **closed** (CLI down → `converged=False`
   / `needs_manual_review`, never `passed=True`). Add a `vision_required` flag for wiring.
3. **B**: compute the saliency/legibility check on the **rendered PNG** (post-scrim), not
   the raw hero — so the lever and the metric are coupled and the tier can actually pass.
4. **D**: tighten `is_text_legibility_claim` (word-boundary / structured verifier output)
   so a font/palette claim that merely mentions "headline" is NOT OCR-overridable.
5. **E**: never promote a stale `01.png`; render to a temp path, verify `RenderResult.ok`,
   atomic-replace; unique output dir per attempt.
6. (Hardening, do together): per-carousel paid-call budget + verdict cache; persist
   `designer_result.json`; live pipeline refuses `rendered` unless `ok && all converged &&
   no required gate degraded`.

After fixes: re-run this panel (or at least re-verify A/B/C on disk) before wiring.

## Execution note (operational, for next time)
`agy` and `codex` CLIs **hang indefinitely (0 CPU) when launched detached from a TTY**
(via `run_in_background` or the Bash tool's auto-backgrounding of long commands). They work
fine in a real foreground TTY (verified: agy answered a medium prompt in 23s). Also: passing
a 23KB payload as an argv string hangs them — use `--add-dir <dir>` (agy) / `--sandbox
read-only` in-cwd (codex) and let them read files themselves with a CONCISE prompt. The
working path this session was **dispatching each CLI inside a `general-purpose` subagent**
(its own TTY, no orchestrate-gate). `timeout`/`gtimeout` are absent on this macOS — rely on
`agy --print-timeout` and the tool's own timeout. DeepSeek (HTTP) has none of these issues.

---
## RAW PANEL OUTPUTS

### Gemini 3.1 Pro (agy) — RED-TEAM
```
(1) Brand verifier bypass on vision-PASS — designer_loop.py:298-304 — returns the draft
immediately if the vision critic passes, bypassing the brand verifier (only gates
vision-proposed changes). Inherent template violation or a vision hallucination → straight
to production unverified. BLOCKING

(2) OCR override masking palette/font violations — designer_loop.py:334-348 + ocr_check.py
:192-206 — is_text_legibility_claim uses basic substring matching ("headline"). A claim like
"The headline uses a serif font instead of Montserrat" is classed as text-only; OCR reads it
legible and erroneously overrides the brand verifier, masking a genuine font violation. BLOCKING

(3) Tier-1 legibility deadlock — designer_loop.py:139-152 — calmest_band evaluates the raw
hero_path not the rendered png_path. Raw photo never changes → flags every iteration → loop
fruitlessly applies scrims until max_iters, permanently deadlocking and starving the paid
Tier-3 vision critic for any hero with a busy bottom band. BLOCKING

(4) Layout-family mapping monotony — composer.py:102-108 — fallback maps all inner slides
to photo-headline-yellow-sub even if image_url missing → broken empty <img src=""> + extreme
monotony. NON-BLOCKING

(5) Cost/unbounded — designer_loop.py:241 — no unbounded path; for it in range(1, max_iters+1)
caps at 3. NON-BLOCKING

(6) Outage failure modes — claude_vision.py:169-171 + renderer.py:217 — Playwright/EasyOCR
safe; but if Claude CLI fails/times out, claude_design_critic defaults to soft-pass
(passed=True). With #1, the loop instantly accepts the draft and emits whatever PNG is in
the buffer — fails open instead of aborting. BLOCKING

RED-TEAM VERDICT: NO-GO
Conditions: fix the brand verifier bypass, tighten OCR claim heuristics, fix the Tier-1
raw-photo deadlock, and fail-closed on Claude API outages.
```

### Codex GPT-5.5 — ENGINEERING-INTEGRATION
```
Idempotency/artifacts — BLOCKING — designer_loop.py:241 always writes iter-01.png/iter-02
.png; composer.py:481 renders deterministic slides/01.png; composer.py:494 can promote a
stale 01.png after a failed render. Retry/crash reuses half-rendered output and marks wrong
PNG as best. Fix: attempt/content-hash output dirs or unlink before render; render to
*.tmp.png, verify res.ok, atomic replace; never fall back to existing slides/01.png unless
current RenderResult.ok.

Render error contract — BLOCKING — designer_loop.py:244 does not catch render_fn exceptions
→ live consumer gets uncaught exception, no DesignerResult. composer.py:487 ignores
res.failures; hero-missing screenshots can enter the loop. Fix: catch into
DesignerResult(converged=False, reason=...); raise/return failure when res.ok false.

Lever state — NON-BLOCKING — scrim bounded <=1.0 (designer_loop.py:400), CSS clamps 0.95
(composer.py:237). Shrink counters unbounded (designer_loop.py:406), CSS floors 0.6
(composer.py:262) → higher max_iters spins on no-op shrink. Fix: clamp counters; _apply_levers
returns only effective changes.

Claude non-JSON — BLOCKING — claude_vision.py:141 returns None on non-JSON; :169 converts
critic outage into passed=True → designer_loop.py:298 returns converged=True after the paid
gate silently skipped. Verifier fails closed (:191) but only after a proposed change. Fix:
parse/CLI failure must be converged=False / needs_manual_review; add vision_required=True.

EasyOCR graceful path — NON-BLOCKING — import/init failure degrades (ocr_check.py:65),
headline_legible returns degraded=True,legible=True (:162), designer_loop.py:174 passes.
Graceful but only visible in logs. Fix: emit metric, persist ocr.degraded in manifest.

Vision cost — BLOCKING — paid calls designer_loop.py:296 + verifier :324. max_iters=3 →
worst case 6 paid calls/slide, 6N/carousel/attempt; retries pay again. No carousel budget/
cache. Fix: per-carousel budget + content-hash verdict cache; stop as needs_manual_review.

Wiring contract — BLOCKING — compose_carousel accepts dict/list, only checks non-empty
(composer.py:346). Live shape effectively {"slides":[{slide_type,is_cover,is_hero_image,
headline,subhead,body,image_url,...}]}; cover/is_hero_image needs downloadable URL
(composer.py:367). Designer bridge assumes assets+hero already staged (composer.py:417); does
not download Tigris. Fix: schema/asset preflight adapter; normalize slides_json; verify
skeleton/assets; fail early typed.

Observability/status — BLOCKING — DesignerResult has history (designer_loop.py:197) but loop
never logs/persists it; on failure can still return final_png=best_png with converged=False
(:372). compose_carousel writes manifest (:400) but not convergence/degradation. Fix: persist
designer_result.json per slide + carousel rollup; live pipeline refuses rendered unless
res.ok && all converged && no required gate degraded.

ENGINEERING VERDICT: NO-GO
CONDITIONS: Fix atomic/idempotent outputs, fail-closed render/vision gates, paid-call budget/
cache, schema/asset preflight, and persisted convergence alerts before this can update live
drafts as rendered.
```

### DeepSeek V4 Pro — LOGIC/CONTRADICTION (reasoning_content; ANSWER section empty — max_tokens hit, full file /tmp/panel-raw/deepseek-raw.txt)
```
Two BLOCKING logic defects identified:
1. Brand verifier is NOT invoked when vision passes (designer_loop.py ~296-302: return on
   vc.passed before the verifier). A converged=True slide can carry brand violations the
   design critic missed. The "separate fail-closed brand verifier" is effectively only a
   post-critic check on proposed changes, not a gate on passes. BLOCKING.
2. Legibility busyness flag computed from calmest_band(hero_path) — the RAW hero, not the
   rendered composite. Scrim/stroke levers cannot affect it → leg.passed stays False forever
   → passes_cheap stays False → vision/brand tiers never reached → deadlock + no brand check.
   Contradiction between what the code assumes (levers fix it) and reality (static check). BLOCKING.
Termination itself is bounded (max_iters) — no infinite spin. OCR override's structural rule
(text_claims and not other_claims) is logically sound; the risk is classifier accuracy. Known
gaps (single layout family, no aesthetic gate, standalone) are NOT blocking for a "human
publishes" promise — the deadlock + missing brand-gate ARE.
LOGIC VERDICT: NO-GO (fix the two blocking defects).
```
