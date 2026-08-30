---
date: 2026-08-29
domain: operations
plan: beyond-sota-craft-wave
lane: "09 — Multi-agent orchestration, fleet & cost/quota routing"
source_report: research/operations/2026-08-28-beyond-sota-multi-agent-orchestration-fleet-routing.md (PR #5177 branch)
status: SPEC-FINAL
---

# L09 — Multi-agent orchestration, fleet & cost/quota routing

## Mission

Cure the meta-pattern: "capability scales infinitely with parallelism." The organism spawns
parallel agents (`fork`, `tmux` panes) as if zero-cost, ignoring host limits (pty exhaustion) and
provider session/weekly caps. Falsifying numbers: W98 — a 13-lane Fable-5 panel died within 2-3
minutes on a session-limit collision (the panel's own refuter found the headline conflated two
caps and three seats: launch 1 died on one seat's session limit; a separate 3%/91% quota pair was
probed on a third, unburned seat); W96 — 13 of 14 parallel lanes failed with `fork failed: Device
not configured` (ENXIO) at 31/511 ptys in use — 94% of ptys were free, so the refuter marks the
cause UNDETERMINED, not proven pty exhaustion; cron OAuth tokens lack `user:profile` scope so
automation is quota-blind by construction; ~86% of a measured 7-day output-token budget was
invisible reasoning. These PRs make fan-out and effort dispatch respect physical and provider
limits instead of assuming infinite compute.

## Ground to load (orchestrator first reads)

- `FLEET_TOPOLOGY.json` [exists] — 5 MAX seats (A1-A5) + one Team-premium seat `AZ`
  (slot 6). This file labels `AZ` "GATE PRIMARY" for the **final on-disk gate role**
  (Opus 5 xhigh at VERIFY) specifically — a different claim from "the Team seat is cascade-last-
  resort for general BUILD dispatch" (Zero's 2026-08-23 ruling, per this repo's global memory). Do
  not conflate the two when building PR-1: the seat-state ledger governs BUILD/implementer cascade
  order only, not the VERIFY gate's dedicated allowance.
- `scripts/tests/test_claude_oauth_slot6_coverage.py` **[report claims — NOT found anywhere on
  origin/main; this repo's global memory cites it as enforcing "5 MAX before slot 6", but a
  full-tree search this session found no such file]** — flag this discrepancy to the operator
  rather than building on an assumed-existing test.
- `infra/launchagents/wrappers/claude-cascade.sh` [exists] — the cross-family cascade (Claude OAuth
  → Gemini `agy` → Kimi K3 → Codex → Ollama); a live HOME-fork twin exists outside the repo — run
  ALIGN-FLEET after merging any change here.
- `scripts/seat_build.sh` [exists, 462 lines] — **already implements** `--tier`/`--gear`/`--effort`
  with per-tier ceilings and a dynamic gate (`enforce_effort_cap()`, ~lines 143-170: e.g.
  codex/luna capped at medium, codex/sol at xhigh/max requires `--gear 3`). PR-3 EXTENDS this, does
  not rebuild it.
- `scripts/tests/test_seat_build.sh`, `test_seat_build_tiers.sh` [exist] — the new
  `test_seat_build_effort.sh` must be additive, not a collision.
- `scripts/claude_seat_quota.py`, `scripts/arsenal_probe.py` [exist] — quota/liveness probing; cron
  tokens 403 against `claude_seat_quota.py`'s `user:profile`-scoped read.
- `scripts/evidence_pack_lint.py` [exists] — `compute_floor()` (~line 623) is the single source of
  truth for a diff's Gear floor; `.github/workflows/harness-floor.yml` [exists] already consumes it
  via `--print-floor`.
- `.claude/skills/modus/SKILL.md` [exists] — already documents `xhigh` as coding/agentic default,
  `max` opt-in-only on declared Gear-3; PR-3 must not contradict this.
- `.claude/skills/modus/AMENDMENTS.md` [exists] — the W98/W96/W5/W90 entries.
- **Open conflict**: PR #5048 is reported DIRTY on exactly `scripts/seat_build.sh` — the
  orchestrator's first act on PR-3 is `gh pr view 5048 --json state,title,mergeable` and to
  reconcile before touching that file (not run in this session).

## PR-1: feat(fleet): seat-state ledger + cascade pre-dispatch check

**Files**: `scripts/lib/seat_state.sh` [proposed], `infra/launchagents/wrappers/claude-cascade.sh`
[exists, integration point], `scripts/tests/test_seat_state.sh` [proposed].
**Gear**: 2
**Build**:

- New `seat_state.sh`: reads the most recent `arsenal_probe.py` sidecar (or `claude_seat_quota.py`
  cache) per seat, exposes `seat_is_live(seat)` / `seat_is_exhausted(seat)`.
- Explicit staleness cutoff — this session's boot found a 22h-old TIMEOUT snapshot injected as
  current panic; a stale ledger entry must resolve to UNKNOWN, never silently LIVE or EXHAUSTED.
- Wire into `claude-cascade.sh` as a pre-dispatch check: skip a known-exhausted seat without a
  fresh live-probe call.
- General BUILD/implementer cascade tries the 5 MAX seats (A1-A5) in FLEET_TOPOLOGY order before
  ever falling to `AZ`; the final-gate role's dedicated `AZ` allowance is a separate, already-ruled
  concern this PR must not disturb.
- An UNKNOWN (stale) entry gets exactly one fresh probe before being treated as exhausted.

**Acceptance**: guilt = seed an exhausted-seat entry → cascade skips it, dispatches to next seat.
Innocence = fresh live-seat entry → used normally, first in order. Staleness = entry older than
cutoff → treated as UNKNOWN, re-probed (exit code 2). Commands: `bash scripts/tests/test_seat_state.sh`.
**Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6 (non-Anthropic); final gate =
orchestrator (Opus 5 xhigh).
**Arming / prove-live**: armed once `claude-cascade.sh` calls `seat_state.sh` on every dispatch and
a dry-run shows an exhausted seat actually skipped.
**Conflicts / order**: none against other lanes; lands before PR-2, which consumes it.

## PR-2: feat(fleet): fleet_burst — account-sharded headless fan-out

**Files**: `scripts/fleet_burst.sh` [proposed], `scripts/tests/test_fleet_burst.sh` [proposed],
`.github/workflows/fleet-burst-tests.yml` [proposed — added at build time: a `.sh` corpus has no
consumer in this repo otherwise, since `scripts-tests-sweep.yml` collects only `test_*.py` and is
`continue-on-error`, so wave-2 rule 3 puts the executor in this same PR].
**Gear**: 2 as drafted, but the CI-recomputed floor for the diff as built is **3** — that workflow
file is a hot-zone path, and the floor is computed from the diff, never chosen. Build to Gear 3
(council journal + `xhigh`): `evidence_pack_lint.py --print-floor` is the authority, not this line.
**Correction (2026-08-31, measured while building)**: PR-1 landed at `scripts/lib/seat_state.sh`,
not `scripts/seat_state.sh` as this file's prose implies elsewhere.
**Build**:

- Deprecate `fork`/`tmux`-pane fan-out for >2 parallel Opus/Fable-class lanes (the W98/W96 shape);
  `fleet_burst.sh` dispatches each lane as a headless `claude -p` process.
- Each lane maps 1:1 to a distinct, verified-live seat via PR-1's `seat_state.sh` — never two lanes
  sharing one seat.
- Concurrency ceiling ≤3 simultaneous spawns — a precaution, not a proven fix: the refuter found
  W96's ENXIO occurred with 94% of ptys free, cause undetermined; record as a standing caveat.
- Sterile config per lane: distinct `CLAUDE_CONFIG_DIR` and output directory, so one lane's crash
  cannot corrupt another's state (the W98 zero-bytes-on-disk mode).
- Never auto-select Fable (manual-only, CLAUDE.md §5, RULED 2026-08-20); default Sonnet 5 or Opus
  5 per task shape; refuse a caller-supplied `--model claude-fable-5` with a clear error.
- Each lane writes incremental output as it progresses, not only at exit.

**Acceptance**: guilt = request 5 lanes with only 3 live seats → refuses or queues the extra 2,
never double-maps a seat. Innocence = 3 lanes, 3 live seats, `--dry-run` → one distinct seat per
lane, ≤3 concurrent spawns, sterile config/output dirs verifiably distinct. Commands:
`bash scripts/tests/test_fleet_burst.sh --dry-run`.
**Seats**: implementer = Sonnet 5; refuter = Codex GPT-5.6 or Kimi K3; final gate = orchestrator
(Opus 5 xhigh).
**Arming / prove-live**: armed once a live 3-lane dry-run shows one seat per lane, correct
concurrency cap, isolated output; prove-live via a real 2-3 lane burst checked for cross-contamination.
**Conflicts / order**: depends on PR-1 landing first.

## PR-3: feat(effort): bind dispatch effort to compute_floor

**Files**: `scripts/seat_build.sh` [exists — extend, do not rebuild], `scripts/tests/test_seat_build_effort.sh`
[proposed, additive to existing test files].
**Gear**: 2 (+needs-ruling)
**Build**:

- First act: reconcile PR #5048 on this exact file before editing.
- Today `seat_build.sh` only CAPS effort at high tiers when `--gear` is given; `EFFORT` defaults to
  the hardcoded literal `"medium"` (~line 253) regardless of gear.
- Add: when `--effort` is omitted but `--gear` is given, derive the default from the floor —
  floor-1 → `medium`; floor-3 → `xhigh` (matches modus doctrine: `xhigh` is the coding/agentic
  default, `max` is Gear-3-adjudication-only).
- Explicit `--effort` always overrides the derived default; log which path was taken in the JSON
  report `seat_build.sh` already writes.
- Floor-2's default is NOT specified by the source report or existing doctrine — do not invent one.
  Ship floor-2 in NOTICE/advisory mode: log the derived value, do not enforce it, pending ruling.

**Acceptance**: guilt = a floor-1 diff, no `--effort` flag, resolves to `medium` — and the test
proves this is floor-driven, not the pre-existing hardcoded default (mutate the hardcoded default
in a fixture copy, confirm the floor-driven path still resolves correctly). Innocence = a floor-3
diff, no flag, derives `xhigh`; same diff with `--effort=low` resolves to `low`, logged as an
explicit override. Commands: `bash scripts/tests/test_seat_build_effort.sh`.
**Seats**: implementer = Sonnet 5; refuter = Codex GPT-5.6 sol (non-Anthropic, given this touches
effort/cost policy); final gate = orchestrator (Opus 5 xhigh).
**Arming / prove-live**: armed once a live floor-1 and floor-3 dispatch (no explicit `--effort`)
show the derived values in the JSON report. Floor-2 stays advisory-only until ruled.
**Conflicts / order**: blocked on resolving PR #5048's state on `scripts/seat_build.sh` first.

## Needs-ruling carried (Zero only — this spec does NOT decide these)

- **Keychain Proxy Daemon** (report §7, verbatim): "Deploying a local daemon that automatically
  unlocks and warms the interactive Anthropic keychain profile every 45 minutes requires Zero's
  explicit GO for security/physical desktop reasons." <report's proposal: `scripts/quota_proxy.py`
  - a launchd plist, ~300 lines, Gear 3> — not part of this wave.
- **Default effort for floor-2 diffs** (PR-3): the report's R2 only specifies floor-1 → `medium`;
  no floor-2 default is named. <this spec's placeholder proposal for Zero: floor-2 → `high`,
  matching the existing `codex/terra` per-tier cap — a suggestion, not a decision>. PR-3 ships with
  floor-2 logged-only until ruled.

## Suspend & ledger rules

A PR red for the SAME cause three times gets no fourth round: SUSPEND with one PENDING-ARMS line
naming the cause, branch left alive, move to the next PR. A fix-of-a-fix chain stops at depth 1 —
a wrong correction means the surface is under-specified, write the spec, don't open a third PR.
Every built-but-not-armed step (PR-3's floor-2 advisory state; any part of PR-2 blocked on PR-1)
gets one PENDING-ARMS row naming the artifact, the missing arming step, and the owner.

## Out of scope

- The Local Quota Proxy Daemon (needs-ruling) — not built this wave.
- Any RouteLLM/FrugalGPT-style dynamic classifier (source report §4, a future direction only).
- Any change to `FLEET_TOPOLOGY.json`'s account roster or `AZ`'s final-gate allowance — this lane
  touches general BUILD/implementer dispatch only.
- Touching `claude-cascade.sh`'s live HOME-fork twin directly — that is an ALIGN-FLEET step after
  merge, not part of PR-1's own diff.
