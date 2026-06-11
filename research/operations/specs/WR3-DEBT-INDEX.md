# WR3 Feature-Debt Index — F18 / F20 / F21

> **Status: SPECS READY — NOT EXECUTED.** This index links three WR3 audit
> findings, each documented as a standalone spec. All fixes are
> **operator-decided**; these are docs only. One file so any session/machine
> finds the whole debt cluster from a single entry point.
>
> Date: 2026-06-12 · Audit source: Fable-5 system audit 2026-06-11 ·
> Cicatrix: `.claude/rules/cicatrix-scars.md` W74.

## The three findings

| ID | One-line | Spec | Severity |
|---|---|---|---|
| **F18** | EvoSkill loop runs but proposes nothing — **zero pressure by dataset construction** (seed-patterns.csv solved at ~100% ⇒ `len(failures)==0` ⇒ no proposal). Infra HEALTHY. | [`WR3-F18-evoskill-zero-pressure.md`](WR3-F18-evoskill-zero-pressure.md) | P2 STRUCTURAL |
| **F20** | Manifest validator is **dead code, incompatible with the only real manifest** (16/18 mandatory fields missing, `critic_verdict="PASS-WITH-NOTES"` not in enum). Wired into no pipeline/CI. | [`WR3-F20-manifest-validator-incompatible.md`](WR3-F20-manifest-validator-incompatible.md) | P2 STRUCTURAL |
| **F21** | Reflexion weekly cron is **theater** — an 816-byte declared stub `sys.exit(0)`s every Sunday, synthesizing nothing. `wr3/_proposed/` empty, no `lessons.md`. | [`WR3-F21-reflexion-cron-theater.md`](WR3-F21-reflexion-cron-theater.md) | P2 STRUCTURAL |

## Cross-cutting note — the shared upstream blocker

**F20 and F21 share one disease: "armed but inactive / green but empty."**

- **F20**: a validator exists but no producer emits a schema-valid manifest, and
  the validator is wired into nothing.
- **F21**: a reflexion synthesizer exists (as a stub) but synthesizes nothing,
  and its cron is green every Sunday regardless.

Both are gated by the **same dead upstream pipeline**:
`com.balizero.wr3.supervisor` is **FAILED, exit=78**, with **zero new episodes
in 12 days**. Consequences for ordering:

- **F20** — wiring `validate_manifest()` into a dead supervisor changes nothing
  observable; there are no fresh episodes to validate.
- **F21** — even a faithful port of the real WR2 reflexion synthesizer would
  emit nothing, because there is **no input corpus** until episodes flow again.

**Therefore: revive `com.balizero.wr3.supervisor` (exit=78) FIRST.** F20 and F21
are downstream of it. Fixing either before the supervisor produces
green-but-still-empty results.

**F18 is INDEPENDENT** of the supervisor blocker — the evolver infrastructure is
healthy; its fix is a **dataset/scheduling decision** (rebuild the curriculum
from real scars, or suspend the cron), not an upstream pipeline repair.

## Phantom-citation guardrail (recorded)

While auditing F18, project memory's reference to
`vendor/evoskill/cli/scorer.py` was found to be **ENOENT**. The real scorer is
`vendor/evoskill/src/cli/shared.py:229` (`make_scorer`). Do not re-cite the
phantom path. (This is the file:line-hallucination class the FASE-0 STADIO-0
gate exists to prevent — see cicatrix W74 GOTCHA.)

## Guardrails (apply to all three)

- **Nothing is executed by these specs.** The actual fixes (curriculum rebuild
  vs cron suspension for F18; deterministic builder vs relaxed validator for
  F20; WR2-pattern port for F21) are deliberate operator decisions.
- Each spec carries its own `Status: SPEC READY — NOT EXECUTED`, Context, Why,
  Fix-options, and Guardrails sections (W38b style).
