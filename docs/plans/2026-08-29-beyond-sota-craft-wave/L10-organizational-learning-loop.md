---
date: 2026-08-29
domain: operations
plan: beyond-sota-craft-wave
lane: "10 — Organizational learning loop"
source_report: research/operations/2026-08-28-beyond-sota-organizational-learning-loop.md (PR #5177 branch)
status: SPEC-FINAL
---

# L10 — Organizational learning loop

## Mission

Cure the meta-pattern: "a lesson captured is a lesson armed." Capture and compression are ahead of
everything surveyed (a push-injected, CI-budgeted, guilt/innocence-guarded scar corpus);
follow-through is behind, reproducing Google's measured postmortem disease almost line for line.
Falsifying numbers (2026-08-28): PENDING-ARMS **280 TECH-DEBT rows overdue of 441 open**; the
ledger's own overdue-alarm sentinel had **never fired once** before W120 found it reading the
wrong key; monthly scar capture declined 56 (May) → 18 (August); the superscar bridge sits at
**13,986/14,000 bytes** — 14 bytes of headroom; `infra/workflows/modus-bench.js` has been dormant
since 2026-07-07. These PRs close the loop between "a cure was written about" and "a cure is
running."

## Ground to load (orchestrator first reads)

- `scripts/pending_arms_report.py` [exists] — emits `"class"` (~line 1003) and `tech_debt_overdue`
  (~line 851); `scripts/tests/test_organism_digest_pending_arms.py` [exists] already exercises
  digest/ledger integration — the new ratchet test should be additive, not a replacement.
- `scripts/organism_digest.py` [exists] — the ≤15-line digest reader PR-1's row-naming extends.
- `.claude/skills/modus/PENDING-ARMS.md` [exists] — the ledger itself; use `pending_arms_report.py
--json` for counts, do not read the file in full.
- `.claude/rules/cicatrix-superscar.md` [exists] — verified this session at exactly 13,986 bytes,
  confirming the report's number precisely.
- `scripts/tests/test_superscar_budget.py` [exists] — existing byte-budget (≤14,000 B) +
  completeness (every `W\d+` token resolves to a real heading) guard; PR-3 must keep this green.
- `.claude/rules/cicatrix-scars.md`, `cicatrix-scars-archive.md` [exist] — the full corpus.
- `infra/scar-gates/MANIFEST.json`, `scripts/lint_scar_number_collision.py`,
  `scripts/lint_retracted_claims.py` + `infra/retracted-claims/registry.json`,
  `infra/guard-conformance/registry.json` + `check_guard_conformance.py`,
  `.github/workflows/check-cicatrix-scar-pointers.yml` [all exist] — sibling antidotes, context
  only, not touched by this wave.
- `.claude/commands/scar.md`, `scripts/scar_query.py` [exist] — capture-layer tooling, unmodified.
- `infra/workflows/modus-bench.js` [exists] — dormant since 2026-07-07; not modified here (R6's
  bench-heartbeat is a later-wave item).
- `scripts/proprioception.py` [exists, 1424 lines] — probe pattern (`probe_home_fork_scripts`
  ~line 546, `probe_guardian_freshness` ~line 698) is the template PR-2's new probe follows;
  `infra/home-fork/declared-pairs.json` [exists] is the closest sibling config.
- External (not in this repo) memory: "the global `~/.claude/CLAUDE.md` is a HOME-fork — three
  copies, three answers" (2026-08-23) — the ground truth PR-2 responds to; not a repo artifact.

## PR-1: feat(ledger): pending-arms overdue ratchet + digest row-naming + reporter schema self-test

**Files**: `scripts/pending_arms_report.py` [exists, extend], `scripts/tests/test_pending_arms_ratchet.py`
[proposed], `scripts/organism_digest.py` [exists, extend].
**Gear**: 2
**Build**:

- Extend `pending_arms_report.py` with a `--budget`/ratchet mode: a JSON snapshot of the current
  TECH-DEBT-overdue count, compared against the last committed snapshot. The count may not
  increase without an explicit override line in the PR (same pattern as tg-gateway
  `grandfathered.json`).
- Extend `organism_digest.py` to name the **10 oldest** TECH-DEBT-overdue rows explicitly (the
  reporter already computes the count; this closes the gap to "an operator can see which rows").
- Add a reporter schema self-test: assert the digest's parser reads the exact keys
  `pending_arms_report.py --json` emits live — the W120 class, closed for good.
- Guilt+innocence fixtures for the ratchet itself (family #3: a ratchet is a guard, needs both
  directions tested). Keep at or under ~300 lines.

**Acceptance**: guilt = synthetic ledger with one additional overdue row beyond the last snapshot →
ratchet RED. Innocence = same delta with an explicit override line present → ratchet GREEN. Digest
test = a live `organism_digest.py` run names 10 real rows. Schema self-test = rename a key in a
fixture copy of the reporter's output → digest parser test RED. Commands: `python3
scripts/pending_arms_report.py --budget --check` plus the new suite under `scripts/tests/`.
**Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6 (non-Anthropic); final gate =
orchestrator (Opus 5 xhigh).
**Arming / prove-live**: armed once the ratchet + schema self-test run in CI on every PR touching
`pending_arms_report.py`, and a live digest run names real rows (not a fixture).
**Conflicts / order**: `pending_arms_report.py` is shared with lane L13's PR-3 (an
`operator[secret]` ager). **This PR merges FIRST**; L13's PR-3 rebases on it, not the reverse.

## PR-2: feat(proprioception): canon-block comparator for global CLAUDE.md

**Files**: a new probe inside `scripts/proprioception.py` [exists — extend, following the existing
`probe_*` pattern] + its config **[proposed — the source report names no file; resolve by
following the `probe_home_fork_scripts` / `declared-pairs.json` pairing convention already in this
file]**; tests under `scripts/tests/`.
**Gear**: 2
**Build**:

- New probe reads marked canon blocks (e.g. `<!-- CANON:<id>:<sha16> -->`) inside the global
  `~/.claude/CLAUDE.md` on each machine, hashes each block, cross-compares via the fleet's existing
  publish/read channel (the mechanism `claude_seat_quota.py` already uses with `--publish`/`--read`).
- Targets a control-plane file outside this repo; the probe code itself is read-only, in-repo, run
  from the checkout — never a fourth fork of the file it watches (the family #1 risk the source
  report names explicitly for this PR).
- Compare at BLOCK level only — legitimate per-machine divergence outside marked canon blocks must
  not trigger a false alarm.
- On divergence: P1 line in every session's startup digest on every machine, per proprioception's
  existing "never silent" contract.
- Register via the existing dispatch-table pattern (`"home_fork_scripts": probe_home_fork_scripts`)
  rather than inventing a parallel mechanism.

**Acceptance**: guilt = a synthetic divergent canon block on one machine's fixture copy → a P1 line
within one probe cycle. Innocence = identical blocks across all fixture copies → silent. Commands:
run the new probe against a fixture directory tree standing in for the 3 machines (never the
operator's real `~/.claude/CLAUDE.md` in CI).
**Seats**: implementer = Sonnet 5; refuter = Codex GPT-5.6 or Kimi K3; final gate = orchestrator
(Opus 5 xhigh).
**Arming / prove-live**: armed once the probe runs as part of a normal `proprioception.py` pass and
a real canon-block hash is published from at least one live machine; full 3-machine
cross-comparison is a post-merge prove-live step, not merge-blocking.
**Conflicts / order**: treat with family #1 care — read-only, vendored in-repo, never a write path.

## PR-3: docs(cicatrix): prune superscar MEMBRI to restore ≥1.5 KB headroom

**Files**: `.claude/rules/cicatrix-superscar.md` [exists, 13,986/14,000 bytes — 14 bytes of
headroom, verified this session].
**Gear**: 1
**Build**:

- **Sequencing**: this file's byte budget is also touched by lane L02's cold-storage PR. **L02
  merges first**; re-measure free bytes with `wc -c .claude/rules/cicatrix-superscar.md` after that
  merge before deciding how much MEMBRI text needs trimming here.
- Shorten MEMBRI lines to the file's own 3-8-word convention without losing any W-token that
  resolves elsewhere — the file's own header: "Più di 1-2 frasi qui È un corpo: sta nel file
  sbagliato."
- Every displaced word must leave its W-token resolvable per `test_superscar_budget.py`'s
  completeness check; never delete a W-token reference, only shorten surrounding prose.
- Target: restore at least 1,500 bytes of headroom (≤12,486 bytes).

**Acceptance**: `test_superscar_budget.py` GREEN with the file at or under 14,000 bytes **and** at
least 1,500 bytes of measured headroom. The completeness half must still pass — every W-token
displaced by pruning still resolves. Commands: `python3 -m pytest
scripts/tests/test_superscar_budget.py -q` and `wc -c .claude/rules/cicatrix-superscar.md`.
**Seats**: implementer = Sonnet 5 (mechanical prose editing); refuter = Kimi K3; final gate =
orchestrator (Opus 5 xhigh) — Gear 1, gate check lightweight but never skipped.
**Arming / prove-live**: armed once `test_superscar_budget.py` is green in CI on the merged PR;
prove-live is the CI run itself.
**Conflicts / order**: **blocked on lane L02's cold-storage PR merging first**.

## Needs-ruling carried (Zero only — this spec does NOT decide these)

1. **p7 harvester promotion policy** (R7): converting shadow proposals into enforced gates changes
   who writes law — only Zero can grant that, one rule at a time. Not part of this wave.
2. **FixIt-sweep quota allocation** (R1's roadmap companion, not this spec's PR-1): a monthly sweep
   of the 10 oldest rows consumes real session window; the feature-velocity-vs-debt trade is a
   business call. <report's recommendation: 1 sweep/month, cap 1 session>.
3. **Batch retirement semantics for PENDING-ARMS**: 280 overdue rows will not all be armed; a
   written "WON'T-ARM with reason X" rule changes the ledger's meaning and needs Zero's signature
   once, in the ledger header.
4. **W78's operator-deskilling countermeasure** (a proposed "what I decided autonomously" digest):
   changes what Zero reads daily — cadence and format are his to set; the loop can only propose.

## Suspend & ledger rules

A PR red for the SAME cause three times gets no fourth round: SUSPEND with one PENDING-ARMS line
naming the cause, branch left alive, move to the next PR. A fix-of-a-fix chain stops at depth 1 —
a wrong correction means the surface is under-specified, write the spec, don't open a third PR.
Every built-but-not-armed step (PR-2's fleet-wide 3-machine cross-comparison, a post-merge step)
gets one PENDING-ARMS row naming the artifact, the missing arming step, and the owner.

## Out of scope

- Any change to `infra/workflows/modus-bench.js` or its dormancy (later-wave R6 item).
- Promoting `p7-lesson-harvester.yml` proposals to enforced gates (needs-ruling #1).
- The antidote-liveness lint (R2), replay-drill battery (R4), and third-strike class-audit lint
  (R5) from the source report's §5 — real recommendations, none promoted to this wave.
- Writing to `~/.claude/CLAUDE.md` on any machine — PR-2's probe is strictly read-only.
