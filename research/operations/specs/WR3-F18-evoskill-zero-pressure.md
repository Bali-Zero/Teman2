# WR3-F18 — evoskill loop runs but proposes nothing: zero pressure by dataset construction

> **Status: SPEC READY — NOT EXECUTED.** This is a docs-only finding. The fix
> (curriculum rebuild OR cron suspension) is a deliberate operator decision —
> no code/SQL/cron change is shipped by this spec.
>
> Date: 2026-06-12 · Family: WR3 feature-debt (sibling: WR3-F20, WR3-F21) ·
> Audit source: Fable-5 system audit 2026-06-11 (finding F18) ·
> Index: `WR3-DEBT-INDEX.md`.

## 1. Context

The agent-library EvoSkill evolver is wired and HEALTHY at the infrastructure
level, but it produces **zero proposals every run** — not because the loop is
broken, but because its training dataset cannot generate failure pressure.

Verified on disk:

- **Loop engine** `vendor/evoskill/src/loop/runner.py`:
  - `:319` pass bar — `status = "[OK]" if avg_score >= 0.8 else "[FAIL]"`,
    and a sample only becomes a failure when `avg_score < 0.8` (`:323`).
  - `:326-328` — `if len(failures) == 0:` → logs
    `"-> All samples passed, no proposal needed"` and `continue`s. No
    failures ⇒ no proposer invocation ⇒ no proposal, by design.
- **Scorer** `vendor/evoskill/src/cli/shared.py`:
  - `make_scorer` at `:229`.
  - The DeepSeek branch `max_tokens` bug that previously truncated judge
    output WAS at `:208-209` and is **now fixed**
    (`max_tokens=2000`, `reasoning_effort="low"`). The stale `max_tokens=16`
    values still present at `:142` and `:168` are in the **non-DeepSeek
    branches** and are intentional — not in scope here.
- **Config** `agent-library/.evoskill/config.toml` —
  `[scorer] type = "llm"`, `model = "deepseek-v4-pro"`,
  `[harness] name = "deepseek"`, `model = "deepseek-v4-pro"`.
- **Seed dataset** `agent-library/.evoskill/data/seed-patterns.csv` — synthetic
  scar→pattern rows (the config comment itself states it "produces zero or
  near-zero proposals on first --dry-run"). The base program maps these
  patterns at ~100% accuracy, so `avg_score >= 0.8` on every sample ⇒
  `len(failures) == 0` ⇒ **0 proposals BY CONSTRUCTION**.
- **Cron** `com.balizero.agent-library-evolver.weekly` (Pro), Sunday 03:00 WITA.
  Plist `infra/launchd/com.balizero.agent-library-evolver.weekly.plist`,
  wrapper `scripts/agent-library-evolver-run.sh`.

So the evolver is the inverse of the F20/F21 disease: there the artifact is
"armed but inactive". Here the loop **runs and exits cleanly** — the curriculum
is simply empty of anything the base program fails, so there is nothing to
learn.

## 2. Why this matters

A Voyager-style self-improvement loop whose dataset the base program already
solves at 100% is **self-improvement theater**: it consumes a weekly cron slot,
a DeepSeek judge call, and an evolver run, and graduates nothing — while the
operator's mental model is "the skill library is evolving each Sunday". The
loop infrastructure is genuinely healthy (this is its strength and its trap:
green every week, learns nothing).

Two secondary contour issues found in the same audit (NOT the root cause, but
record them so they don't masquerade as the cause later):

- `TELEGRAM_BOT_TOKEN` is **absent from the evolver wrapper env** → any alert
  the wrapper would emit is **skipped silently** (failure of the evolver would
  be invisible — same "green cron, no signal" family as F21).
- An unresolved **weekly-vs-daily double-LaunchAgent** ambiguity for the
  evolver (which schedule is authoritative is not settled in the plist set).

## 3. Phantom-citation warning (record, do NOT repeat)

Project memory previously cited the scorer at `vendor/evoskill/cli/scorer.py` —
that path is **ENOENT**. The real scorer lives at
`vendor/evoskill/src/cli/shared.py:229` (`make_scorer`). Any future work on
F18 must use the `src/cli/shared.py` path; the `cli/scorer.py` reference is a
hallucinated artifact and must not be re-cited (this is exactly the
file:line-hallucination class the FASE-0 STADIO-0 gate exists to prevent).

## 4. Fix options (operator picks; nothing shipped here)

- **(a) Build a real curriculum** — replace `seed-patterns.csv` with examples
  the **base program FAILS**, drawn from real cicatrix scars (the file already
  carries dozens of TRAUMA/ANTIBODY entries that map cleanly to the 9 patterns).
  When the base program scores `< 0.8` on genuinely hard cases, `len(failures)`
  becomes non-zero and the proposer fires for real. This is a **dataset change
  only** — no `runner.py` code change, no schema change.
- **(b) Suspend the evolver cron** until a real curriculum exists (Fable-5's own
  recommendation). Honest "off" beats green-but-empty: it removes the false
  "we're evolving" signal and the weekly DeepSeek spend until there is real
  pressure to learn from.
- **Optional, orthogonal to (a)/(b):** lower the `0.8` pass bar at
  `runner.py:319` if 0.8 is judged too lenient for the real curriculum — but
  this is a tuning knob, NOT a fix on its own (a too-easy dataset stays
  pressure-free at any threshold).

## 5. Guardrails

- **Do NOT execute autonomously.** Choosing (a) vs (b) is an operator decision
  about whether the evolver should run at all right now. Drafting a real
  curriculum from scars is a content task that should be reviewed before it
  becomes the judge's ground truth (a bad curriculum trains the wrong lessons).
- If (a) is chosen, the new `seed-patterns.csv` should itself be panel-reviewed
  (the curriculum becomes the scorer's authority — a poisoned curriculum is
  worse than an empty one).
- F18 is **independent** of the F20/F21 dead-supervisor blocker: the evolver
  infra is healthy and the fix is dataset/scheduling, not an upstream pipeline
  repair.
- The two contour issues (missing `TELEGRAM_BOT_TOKEN`, weekly-vs-daily
  double-LaunchAgent) are worth closing alongside whichever option is picked,
  but neither is the root cause and neither blocks the decision.

## 6. Reference

- Loop: `vendor/evoskill/src/loop/runner.py` (`:319` pass bar, `:326-328`
  no-proposal `continue`).
- Scorer: `vendor/evoskill/src/cli/shared.py` (`make_scorer` `:229`; fixed
  DeepSeek branch `:205-211`; stale-but-intentional `max_tokens=16` at
  `:142`/`:168`).
- Config: `agent-library/.evoskill/config.toml`.
- Seed: `agent-library/.evoskill/data/seed-patterns.csv`.
- Cron: `com.balizero.agent-library-evolver.weekly`, plist
  `infra/launchd/com.balizero.agent-library-evolver.weekly.plist`, wrapper
  `scripts/agent-library-evolver-run.sh`.
- Audit: Fable-5 system audit 2026-06-11, finding F18.
- Phantom citation avoided: `vendor/evoskill/cli/scorer.py` (ENOENT) — real
  path is `src/cli/shared.py:229`.
