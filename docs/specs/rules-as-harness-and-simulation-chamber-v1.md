# Rules-as-Harness + Simulation Chamber — v1 (DESIGN artifact)

Date: 2026-07-06 · Author: Fable 5 · Mandate: Zero ("né io né tu ci fidiamo di 'cambio di
abitudini' — regole imposte, ma che non affoghino Fable 5; camera di simulazione identica alla
realtà; il Bali Zero Lab esiste — teatro o reale?")

## 0. The Lab verdict first (grounded this session, 2026-07-06)

The Autonomous Lab is **a real organ, half-dead** — not pure theater:

- REAL: `apps/autonomous-lab` (Next.js control-plane dashboard, merged #1543), migration 124
  (`autonomous_lab_runs` idempotent queue + `autonomous_lab_events_outbox`, FOR UPDATE SKIP
  LOCKED), state/receipt stores in `apps/backend-rag/backend/services/autonomous_lab/`, a
  3-machine placement contract (`docs/runbooks/autonomous-lab-runtime-placement.md`: M5 cockpit,
  Pro runtime, Mini scheduler, unknown hosts fail closed), research docs 2026-06-16.
- DEAD: both Pro LaunchAgents (`com.balizero.autonomous-lab{,-runner}`) point into
  `.worktrees/ops-autonomous-runner/` — reaped >10 days ago → exit 127 every tick. Already an
  operator-gated PENDING-ARMS line ("repoint-or-retire", 3 cron exit-127 su Pro).
- Its WRITTEN mission is exactly the chamber Zero asks for: "watch AI research, model releases…
  turn fresh signals into bounded experiment candidates; **test them in isolated prod-like
  contexts**; surface only decision-grade proposals."

**Verdict: resurrect, don't rebuild.** The chamber = Lab runtime revived + a golden-task suite
+ an experiment contract (below). Repoint decision stays operator-gated (it's his ledger line).

## 1. Principle: three enforcement tiers (the "don't drown Fable" calibration)

| Tier | Mechanism | When | Fable cost |
|---|---|---|---|
| **T-BLOCK** | hook/CI exit≠0 | mechanical, objectively checkable, scar-backed | zero (only fires on violation) |
| **T-GATE** | CI check on the ARTIFACT (PR) | quality contracts provable from file content | zero in-session; visible at PR |
| **T-NUDGE** | SessionStart/threshold hook injection | judgment calls where blocking would drown | one line of context |

Anti-drowning rules: a new rule ships ONLY as the weakest tier that still bites (W83-W85 lesson:
three consecutive over-matches from ONE over-eager guard); every new T-BLOCK needs guilt AND
innocence tests (guard-conformance registry, #1973) AND a Lab dry-run on recorded sessions before
going live; every rule has a kill switch env; rules fire on THRESHOLDS, not on every action.

## 2. The rules to impose (from the 2026-07-06 workflow review)

### R1 — Generator≠grader on research/audit deliverables → T-GATE
New/changed `research/**/*.md` in a PR must carry frontmatter `adversarial_review:` naming
seat ≠ author (e.g. `glm-5.2`, `codex`, `deepseek-v4-pro`, `gemini-3.1-pro`) + a `## Adversarial
review` section with the refuter's surviving objections (or "none survived, N raised"). CI job
(pattern-check, stdlib) on paths `research/**`. Exemptions: `research/regulatory/*-delta.json`
(machine-produced), files with frontmatter `adversarial_review: exempt-<reason>` (visible, greppable).
Enforces: feedback_always_review_spec_with_4_llm + verify-template as path-of-least-resistance.

### R2 — Delegation floor for Gear-3 mandates → T-NUDGE (upgrade of dispatch_nudge)
Existing `dispatch_nudge.py` fires at >500 transcript lines + 0 Agent calls. Upgrade: also count
Workflow calls; lower threshold when the session declared GEAR 3 (greppable in transcript); nudge
text names the concrete missed move ("5 independent reads done inline — fan out"). Stays a nudge:
blocking here would drown exactly the judgment Fable exists for.

### R3 — Normativa answers need a ground-truth pass → T-NUDGE now, T-GATE later
Detecting "regulatory claim in chat" mechanically is over-match bait (W72/W73 family — B211/KITAS
substring traps). Now: SessionStart reminder line when NB-INTEL/regulatory files are hot in the
mandate. Later (Lab-tested): T-GATE on `apps/mouth` regulatory content PRs requiring `nb_verified:`
frontmatter. NLM is the verifier of FACTS; agy is width/search — roles stay as settled.

### R4 — Arsenal liveness is empirical, continuous → shipped as `scripts/arsenal_probe.py`
(companion PR, spec `docs/specs/arsenal-probe-v1.md`): healer runs it 4h on Mini; proprioception
reads freshness+verdict; transitions → Telegram. Kills the silent 2-deep cascade class.

### R5 — Background-first for >30s externals → T-NUDGE
Already modus doctrine (ASYNC cross-cutting). Enforcement candidate once Lab can replay sessions:
PostToolUse counter on foreground Bash >120s wall → nudge. Not worth a blocking hook.

## 3. The Simulation Chamber (Lab v2) — experiment contract

An **experiment** is a row in `autonomous_lab_runs` with:
- `candidate`: seat/model/rule/hook under test (e.g. "grok-4-code as council refuter",
  "R1 gate regex v2", "glm-5.2 as standing PR reviewer").
- `suite`: golden tasks — versioned dir `lab/golden/` (NEW, small): ~10-15 canonical Nuzantara
  tasks with falsifiable acceptance each (KBLI answer vs NB ground-truth; PR-diff review with
  seeded bugs (guilt) + clean diff (innocence); regulatory delta classification vs labeled
  history; carousel brief vs brand constitution checks; a W-series scar-regression each).
- `isolation`: worktree + sandboxed runner on Pro (existing placement contract), NEVER prod
  writes, NEVER PII in fixtures (synthetic client_ids only).
- `receipt`: per-task pass/fail + evidence tail → `autonomous_lab_events_outbox` → dashboard;
  a no-signal tick still writes a receipt (its own W81 rule, already in the runbook).
- `verdict`: decision-grade proposal (adopt / reject / retune) — operator decides (Legge 5).

First three experiments queued when the chamber breathes:
1. **Grok week** (super-premium expires in ~7 days): grok-4/Code as (a) council refuter on 5
   recorded councils, (b) realtime-X OSINT lane for competitor/regulatory chatter. GROK_API_KEY
   already in env.master.
2. **R1 gate dry-run** on the last 20 research PRs (would it have fired right?).
3. **GLM standing-reviewer** on 10 recent merged PRs vs their actual review outcomes.

## 4. Sequencing (small PRs, each provable)

1. PR-A (this session): arsenal_probe + proprioception/healer wiring + runbook. [companion worktree]
2. PR-B (this session): this spec + the 5 deep-research reports (documents only).
3. PR-C (next): R1 CI gate + guard-conformance registration (guilt/innocence fixtures).
4. PR-D (next): dispatch_nudge upgrade (R2) — hooks are live-folded via sanctioned installer only.
5. Lab resurrection: operator decides repoint-or-retire on the existing ledger line; if GO,
   a Pro-resident session re-creates the runner worktree from origin/main and re-arms the two
   plists; golden suite lands as PR-E with the first experiment (Grok, time-boxed).

## §Solo-operatore

- Lab repoint-or-retire GO (existing PENDING-ARMS line) — the chamber depends on it.
- Grok: confirm super-premium scope + whether API credits are included (key exists in env.master;
  research report will detail entitlements).
- R1 exemption policy blessing (which research paths, if any, are exempt by default).
