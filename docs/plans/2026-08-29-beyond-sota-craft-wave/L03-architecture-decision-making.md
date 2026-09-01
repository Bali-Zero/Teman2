---
date: 2026-08-29
domain: operations
plan: beyond-sota-craft-wave
lane: "03 — Architecture & design decision-making"
source_report: research/operations/2026-08-28-beyond-sota-architecture-decision-making.md (PR #5177 branch)
status: SPEC-FINAL
---

# L03 — Architecture & design decision-making

## Mission

The organism is ahead of every surveyed system on how a decision is _argued_ (measured
grounding, cross-family asymmetric councils, a CI lint rejecting unwarranted deliberation,
per-finding adversarial dispositions) and behind a 2011-era baseline on what happens to a
decision _afterwards_. Falsifying numbers: the formal ADR organ
(`docs/ARCHITECTURE_DECISION_RECORDS.md`) has had **0 commits since 2026-06-01**; decisions live
scattered across **≥6 locations** with no status/supersedes/revisit machinery; `docs/adr/`
holds one file whose number **collides** with ADR-006 in the main doc; the governing
`sota-architecture-loop` skill cites an evidence file
(`research/operations/2026-05-30-sota-ai-architecture-methodology.md`) that **never existed** —
confirmed this session, `find` returns nothing for that path; SYMBIOSIS Law 5 ("l'organismo
propone, non decide") contradicts `CLAUDE.md` §2 ("sessions ARE the operator") on who decides
structure; the only hard number on over-convening is "70% of Agent dispatches are graders"
(`evidence_pack_lint.py:645`) — the organism cannot count its own over-convening while already
producing the raw data. This lane's three PRs build a decision registry, cure the phantom
citation with a citation-integrity lint, and instrument council yield.

## Ground to load (orchestrator first reads)

- `.claude/skills/sota-architecture-loop/SKILL.md` [exists, 13 KB — the phantom citation sits
  near the top: "Fonti + verifica in
  `research/operations/2026-05-30-sota-ai-architecture-methodology.md`", right after the
  frontmatter/CANON banner; `find . -iname "2026-05-30-sota-ai-architecture-methodology*"`
  returns nothing on this tree — re-grep the live text before editing, the line number may drift]
- `docs/ARCHITECTURE_DECISION_RECORDS.md` [exists, 14 KB — 11 ADRs, ADR-001…011, "Last Updated
  2026-02-26"]; `docs/adr/` [exists — 1 file, `ADR-006-nb-mitochondrial-monitor-bootstrap-json.md`,
  whose number collides with ADR-006 "Abstract Channel Pattern" in the main doc]
- `docs/decisions/` [exists — holds `2026-05-03-codex-spalla-architecture.md`, 7.3 KB, the only
  decision memo with a real Status/Supersedes/Related header; `registry.yaml` will live here]
- `docs/decisions/registry.yaml`, `scripts/lint_decision_registry.py`,
  `scripts/lint_doctrine_citations.py`, `scripts/council_yield_report.py` [all proposed]
- `evidence/pack.yml` [exists, 23 KB — top-level keys include `brief_ref`, `plan_ref`, `lanes`,
  `seat_diversity`/`_note`, `diff`, `receipts`, `pii_scan`/`_note`, `dissent`; PR-3's `council:`
  block is a NEW top-level key, additive only]
- `infra/organ-conformance/genes.json` [exists, 23 KB] and `infra/guard-conformance/` [exists —
  `check_guard_conformance.py` 18 KB + `registry.json` 92 KB; the guilt+innocence pattern PR-2
  must follow]
- `.claude/skills/modus/AMENDMENTS.md` [exists, 52 KB — 2 of 42 entries mention "council"] and
  `.claude/skills/modus/PENDING-ARMS.md` [exists, 2.2 MB]
- CI reads the **origin/main** version of every linted file — re-verify the phantom citation's
  exact text against `origin/main`, not this worktree, before writing the fix

## PR-1: `docs(decisions): decision registry v0 — schema, backfill, collision+coverage lint`

**Files**: `docs/decisions/registry.yaml` [proposed], `scripts/lint_decision_registry.py`
[proposed] + test [proposed]
**Gear**: 2
**Build**:

- Schema per entry: monotonic `D-NNN`, `status: proposed|accepted|superseded-by|postponed
(revisit_by)`, `door: one-way|two-way`, `evidence:` (path to the dossier/disposition table),
  `contradicts:`
- Backfill: the 6 inline `RULED` blocks in `CLAUDE.md`, the 11 legacy ADRs (ADR-006 collision
  resolved by renumbering the `docs/adr/` file, not the older/larger main doc), the 2026-05-03
  codex-spalla memo, and `2026-08-28-case-code-design.md` as a worked specimen
- Lint enforces: reused `D-NNN` is a hard fail (W40/W128-class antidote applied to decision
  numbers); every `evidence:` path must resolve on `origin/main`; a Gear-3 dossier missing a row
  is a NOTICE in wave 1 (fail-closing is needs-ruling item 2, not built here)
- Mark ADR-001 ("Gemini primary LLM") `superseded-by:` the 2026-07-25/08-20 routing rulings in
  `CLAUDE.md` §5 — per the adversarial disposition (rejected objection #2): this RECORDS an
  already-replaced decision's status, it does not make a new business decision
  **Acceptance**: guilt fixture = two registry entries sharing the same `D-NNN` (must fail red);
  innocence fixture = a fully-backfilled registry with unique numbers and every `evidence:` path
  resolving (must pass green). Live check: ADR-001 carries `superseded-by:` in the backfilled file.
  **Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6 (non-Anthropic,
  generator≠grader); final on-disk gate = orchestrator (Opus 5 xhigh)
  **Arming / prove-live**: armed when `scripts/lint_decision_registry.py` runs in CI against
  `origin/main`'s `registry.yaml` and the guilt/innocence pair both resolve as expected
  **Conflicts / order**: Wave 1. Independent of PR-2 (different files); may run in parallel. This
  lane's PR-3 (council block) touches the same linted surface as L01's PRs and may only start
  after **L01 is fully merged** (cross-lane dependency, team-lead-specified).

## PR-2: `chore(doctrine): citation-integrity lint + cure the sota-architecture-loop phantom`

**Files**: `scripts/lint_doctrine_citations.py` [proposed] + test [proposed], one edit to
`.claude/skills/sota-architecture-loop/SKILL.md` [exists] near its opening lines
**Gear**: 1-2
**Build**:

- Before editing: re-grep `.claude/skills/sota-architecture-loop/SKILL.md` on `origin/main` for
  the exact phantom line — confirmed this session as "Fonti + verifica in
  `research/operations/2026-05-30-sota-ai-architecture-methodology.md`" near the top; do not
  trust a cached line number, locate it fresh
- Build the lint: resolve every `research/...`/`docs/...` path cited in skills, `CLAUDE.md`, and
  `SYMBIOSIS.md` against `git ls-tree origin/main`; unresolved path = CI red. Innocence
  requirement: a path inside a code block/example (not a citation) must NOT trigger the lint
- Cure: replace the phantom citation with (a) a real, verified-existing source, or (b) an honest
  statement that the loop's three axioms are institutional practice with no backing research
  file, if no substitute exists — never fabricate a plausible path to pass the lint
- Per adversarial finding (survives): do NOT cite THIS spec or the source dossier as the
  replacement citation — circular (the cure citing the report that found the defect makes the
  lint's green self-fulfilling). Cite a durable, independently-checkable source, or none.
  **Acceptance**: guilt fixture = the pre-cure phantom path (lint must be red); innocence fixture =
  a code-block-only path mention that is not a citation (must stay green) plus the post-cure
  skill text (must be green)
  **Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6; final on-disk gate =
  orchestrator (Opus 5 xhigh)
  **Arming / prove-live**: armed when the lint runs in CI on `origin/main` and is green on the
  cured skill file
  **Conflicts / order**: Wave 1. Independent of PR-1 — both may run in parallel branches.

## PR-3: `feat(evidence): council block in pack.yml + council_yield_report.py`

**Files**: `evidence/pack.yml` schema addition [exists, additive top-level `council:` key],
`scripts/council_yield_report.py` [proposed]
**Gear**: 2
**Build**:

- Add a structured `council:` block to `evidence/pack.yml`: `seats:`, `family_mix:` (declared
  heterogeneity per family-exclusion doctrine), `findings:`, `applied:`/`rejected:` counts,
  `est_tokens:` — auto-extracted from the disposition tables dossiers already produce (the
  `## Adversarial review` sections in all three source reports of this panel are the template)
- `council_yield_report.py` aggregates design-changing findings per seat across historical packs
- A council block recording **0 applied** findings auto-emits an AMENDMENTS candidate row
  (antidote to "the misfire log was silent while misfiring")
- R4's blind-judge concept is out of scope here (see Out of scope) — this PR only instruments
  yield, it does not change how the gate reads reviews
  **Acceptance**: `council_yield_report.py` runs successfully on ≥5 historical packs/dossiers with
  disposition tables (the three 2026-08-28 beyond-SOTA lane reports' `## Adversarial review`
  sections are valid inputs though they predate the schema — the script must fall back to parsing
  the existing markdown disposition-table shape); a synthetic 0-applied council in the new schema
  emits the AMENDMENTS candidate line
  **Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6; final on-disk gate =
  orchestrator (Opus 5 xhigh)
  **Arming / prove-live**: armed when the report runs against `origin/main` history and its output
  is reproducible; probe = re-run and confirm identical aggregate numbers
  **Conflicts / order**: Wave 2. **Depends on L01 being fully merged first** (L03-PR-3 touches the
  same `evidence/pack.yml` + `evidence_pack_lint.py` surface L01's three PRs modify). Do not open
  this branch until L01's PR-1/2/3 are all on `origin/main`.

## Needs-ruling carried (Zero only — this spec does NOT decide these)

1. **Who decides structure**: SYMBIOSIS Law 5 ("le decisioni strutturali passano da Zero …
   l'organismo propone, non decide") vs `CLAUDE.md` §2 ship-lifecycle ownership. One sentence
   from Zero settles which text governs structural decisions. This spec does not resolve the
   contradiction; PR-1's registry only records decisions, it does not adjudicate this conflict.
2. **Registry bindingness**: may a missing registry row BLOCK a Gear-3 merge, or stay advisory?
   A friction/business trade-off. PR-1 ships NOTICE-only for missing rows; escalating to a fail
   is out of scope pending this ruling.
3. **Blind gate as default** (R4, not built in this lane): changing the final on-disk gate's
   reading procedure touches a surface Zero personally ruled three times (2026-07-25 / 08-19 /
   08-20). Not part of this lane's three PRs.

## Suspend & ledger rules

Rule 8 (`CLAUDE.md` §2): a PR red three times for the SAME cause SUSPENDS — one PENDING-ARMS
line naming the cause, branch left alive, no fourth round. Fix-of-a-fix stops at depth 1. Every
BUILT-but-not-yet-ARMED step (e.g. `registry.yaml` merged but not yet consulted by any live
session) gets one row in `.claude/skills/modus/PENDING-ARMS.md` naming the artifact, the missing
arming step, and a named owner (never a bare `operator`).

## Out of scope

- R4 (blind-judge protocol / seat anonymization before the gate reads) — touches the final-gate
  reading procedure itself; needs-ruling item 3, not part of this lane's three PRs.
- R5 (premortem seat + door/non-goals dossier fields), R6 (SYMBIOSIS-CONFORMANCE.yaml) — in the
  report's roadmap, not this lane's three assigned PRs.
- Renumbering/restructuring the 11 legacy ADRs beyond the single ADR-006 fix and ADR-001 status
  update named in PR-1.
- Any change to `evidence_pack_lint.py`'s gear floor/ceiling — PR-3's `council:` field is
  additive only, it does not touch `compute_ceiling()`.
