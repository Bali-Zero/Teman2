# Scar-Replay Antibody Harness

> The redesigned `agent-library-evolver`. Turns the organism's lived production
> failures (`cicatrix-scars.md`) into deterministic replay probes, and asks an
> LLM to generate an **executable antibody** that prevents each failure class.
> A loop that self-improves for real — measured by counterfactual prevention,
> not a vanity benchmark.

Design: 3-LLM council 2026-06-04 (DeepSeek V4 Pro + GPT-5.5 + Gemini 3.1).
Decision record: `memory/decision_evolver_scar_replay_harness_2026_06_04.md`.

## Why this replaced the old evolver

The previous evolver optimized a **saturated toy benchmark** — classify a scar
into 1 of 9 patterns. DeepSeek-v4-pro solves that at **100% baseline**, so
`no_improvement_limit` fired after 3 zero-delta iterations and `proposals_passed`
was **0 by mathematical construction**, every run, forever. It never promoted a
single skill. It was a $0.04/week no-op that produced a vanity `exit 0`.

The owner's reframe (verbatim, 2026-06-03): *"imparare = ricordare + averne
esperienza"* — to learn = to remember **and to have lived experience**. Measuring
`proposals_passed > 0` is the wrong thing when the task has no headroom.

## The core idea

A **scar is a failure that already happened** — so a replay of it has guaranteed
headroom: the **baseline fails by construction**. Learning means producing a
guard/preflight/cleanup/fallback (real code) that makes the replay pass.

```
error (32h prod-stale drift) → memory (.md with WHY) → cicatrix scar
   → [THIS HARNESS] → executable antibody, tested against the replay + variants
   → different behavior GUARANTEED before the next identical error
```

### The anti-overfit firewall (council, unanimous)

The candidate LLM sees **only the incident SUMMARY + the antibody contract**. It
never sees the fixture code, the assertion, or the hidden variants. Final scoring
is **local executable behavior**, never an LLM judgment. This is what stops the
model from learning to *paraphrase* cicatrix prose (memorization) instead of
producing a *functional* defense (learning).

## The gate (what "promoted" means)

An antibody is `promoted` (counts toward `effective_antibodies`) only if **all**:

1. **baseline_failed** — without the antibody, the replay reproduces the failure
   (real headroom; a stale probe that no longer fails is retired, not "passed").
2. **original_passed** — the antibody makes the original replay pass.
3. **all_variants_passed** — it generalizes to N hidden mutations of the same
   failure family (different branch name, subdir cwd, concurrent lock, …).

The real metric (Law 7, numbers first):
```
effective_antibodies = fail_before_pass_after − regressions − overbroad_blocks
```
Never `proposals_passed > 0`. In daily mode two extra counters separate
free vigilance from paid evolution: `vigilance_pass` (stored antibodies that
still hold, $0) and `evolved_new_or_stale` (probes that needed the LLM).

## Files

| File | Role |
|---|---|
| `scar_replay.py` | engine: key-resolution, DeepSeek proposal call, the gate runner, cleanup |
| `scar_probes.py` | concrete probes compiled from cicatrix scars (currently: `shared_worktree_git_ops`) |
| `test_scar_replay.py` | mechanics test, **zero network** — proves baseline fails & a correct antibody promotes & an empty one does not |
| `scar-replay-run.sh` | operational wrapper: worktree-isolation hard-guard, graceful degradation, alert-only-when-human-needed |

## Induce it (no waiting for cron)

```bash
# online, real DeepSeek, all probes (~$0.003–0.01 per probe)
bash scar-replay-run.sh

# one family
bash scar-replay-run.sh --family shared_worktree_git_ops

# degraded mode (DeepSeek down / no key): replay-only, never crashes, never alerts
bash scar-replay-run.sh --offline

# DAILY mode — vigilance + evolve-on-novelty (the cron default).
# Every day: replay the stored antibodies for FREE (offline) to confirm they
# still hold; call DeepSeek (~$0.003) ONLY for a probe that is NEW (never
# promoted) or STALE (its stored antibody no longer passes). ~$0/day at
# steady state; alerts only when a probe regresses.
bash scar-replay-run.sh --daily

# reap evolver-owned scories (stale evolver/* branches, old telemetry) — dry-run
bash scar-replay-run.sh --cleanup
bash scar-replay-run.sh --cleanup --apply
```

First proven prod induction (2026-06-04 01:54 WITA, Pro):
`effective_antibodies=1, original_passed=true, variants_passed=3/3, cost_usd=0.0033`.
DeepSeek generated — from the summary alone — a worktree-isolation antibody that
creates a detached isolated worktree and aborts rather than drift the shared tree.

## Symbiosis self-healing (verified in prod, not asserted)

- **Key resolution** (Law 4): `env → ~/.nuzantara-secrets.env → ~/.openclaw/workspace/.env.master → offline`.
  No key is **"offline replay only"**, never "broken". Auto-recovers the
  documented vault drift. *Observed: `recovered from .env.master (vault drift)`.*
- **Graceful degradation** (Law 4): DeepSeek unreachable → `--offline` re-runs the
  last known antibodies; clean exit, no alert.
- **Worktree isolation** (closes the structural debt): probes run in ephemeral
  `mktemp` sandboxes; the wrapper refuses to even `cd` inside the shared deploy
  worktree. The harness never does git-ops in a directory another job depends on.
- **Alert only when a human is needed** (Law 5): a successful or zero-antibody run
  is **silent**. Alerts fire ONLY when a probe goes **stale** (a previously-fixed
  failure class regressed) or the harness crashes — the genuine human-decision
  conditions.

## Grow the loop: add a new probe from a scar

Every future cicatrix entry can become an antibody. To add one, in `scar_probes.py`:

```python
my_probe = Probe(
    family="some_failure_family",
    incident_summary=(
        "What went wrong, in plain prose. NO fix. NO mention of the variants. "
        "This is ALL the candidate LLM sees."
    ),
    contract=(
        "The env vars your antibody receives, and exactly what it must guarantee. "
        "Be precise — this is the antibody's API."
    ),
    build_fixture=_build_original,      # set up pre-error state + run risky op (with/without antibody)
    assert_outcome=_assert_original,    # PURE LOCAL check — exit code / file state, never an LLM
    variants=[
        ("mutation_name", _build_variant),   # hidden generalization checks
    ],
)
```

Then add it to `all_probes()`. Run `test_scar_replay.py` first (hand-write an
oracle antibody to confirm the baseline fails and a correct fix promotes) BEFORE
spending on DeepSeek. The mechanics test is your free correctness gate.

### Rule of thumb for a good probe

- The **baseline must genuinely fail** — if it passes, the failure class is
  already solved and the probe is theater. Retire it.
- The **assertion must be executable and local** — exit code, HEAD branch, file
  presence, a side-effect constraint. Never "ask an LLM if this looks right".
- The **variants must be hidden from the summary** — they test generalization,
  not recall.
