# LEARN — shadow lesson harvester (P7 FASE-6 safe slice)

This is the **safe half** of the LEARN loop that P7 (`research/operations/specs/P7-learn-close-the-loop.md`) designs. It **proposes**; it does **not** apply.

## The paradox it respects (P7 §0)

Closing a self-modifying LEARN loop is *more* dangerous than leaving it open **when the verifier is imperfect** (P1): a wrong lesson becomes a permanent hook that blocks correct code. The resolution is to **decouple proposal from application** — the loop may close on *generating* candidate rules, but adoption stays gated + reversible (shadow-mode + human-gate + kill-switch).

This slice implements ONLY the proposal generator. There is **no code path** here that activates a rule, edits `settings.json`, or writes a hook.

## What `lesson_harvester.py` does

Reads the cicatrix scar ledger (`.claude/rules/cicatrix-scars.md`) — the rich, already-abundant **objective** signal that breaks the starvation cascade (§3.3) — and classifies each scar:

| bucket | meaning | gate |
|---|---|---|
| **rejected** | no objective external anchor (commit / PR / CI run / failing test / exit code) | **G1** — breaks the hallucination echo-chamber: a lesson must be anchored to a *verifiable event*, not agent interpretation |
| **mechanical candidate** | anchored AND part of a pattern recurring ≥3 times (W-numbers / families) | **G4** — only recurring patterns become candidates for an executable antibody (via `scar_replay`), then SHADOW → human-gate → enforcement |
| **consultive** | anchored but single-occurrence | **G4** — routed to the judgment pipeline (a checklist), never a hook |

Output: `proposals/lesson-proposals.json` + `.md` — **shadow proposals only**.

## Gates (falsifiable, Symbiosis Law 7)

- **G1** objective anchor — `--self-test` + `test_g1_*`
- **G2** proposal ≠ application — the report declares `_enforcement: none`; the source has no write sink besides its own artifacts and no state-mutating subprocess (`test_g2_*`)
- **G3** reversibility — `LESSON_HARVESTER_OFF=1` → no-op (`test_g3_kill_switch_noop`)
- **G4** recurrence threshold ≥3 — `test_g4_*`

## Usage

```bash
python3 agent-library/learn/lesson_harvester.py            # write shadow report
python3 agent-library/learn/lesson_harvester.py --check    # CI: fail if report stale
python3 agent-library/learn/lesson_harvester.py --self-test
LESSON_HARVESTER_OFF=1 python3 agent-library/learn/lesson_harvester.py   # kill-switch
```

## Deferred (NOT in this slice)

The *application* half — promoting a mechanical candidate to an active rule — is intentionally out of scope. It requires the shadow-period observation, zero-false-positive gate, and human-gate of P7 §3.4. Also deferred: repairing the upstream evoskill/reflexion blockers (§3.6), and the regression-on-history test (§3.5) that a candidate must pass before promotion. This slice is the **proposal substrate** those steps consume.
