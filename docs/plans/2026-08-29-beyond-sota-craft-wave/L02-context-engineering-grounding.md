---
date: 2026-08-29
domain: operations
plan: beyond-sota-craft-wave
lane: "02 — Context engineering & grounding"
source_report: research/operations/2026-08-28-beyond-sota-context-engineering-grounding.md (PR #5177 branch)
status: SPEC-FINAL
---

# L02 — Context engineering & grounding

## Mission

The write side of grounding (typed scar corpus, staleness-honest receptors, hook-automated
memory capture) is ahead of everything surveyed; the read side is unbudgeted and silently
exploded. Falsifying number: the auto-injected surface **5x'd in seven days to 774,156 bytes
(~190-220K tokens)** — the 2026-08-21 audit measured ~148-155 KB (~42-44K tokens) with the scar
body and archive NOT in the prompt; seven days later the harness loads the whole `.claude/rules/`
directory. The only armed budget guard is `scripts/tests/test_superscar_budget.py`
(`BYTE_BUDGET = 14_000`), watching one file at **13,986 bytes** — 1.8% of the payload it believes
it bounds. `cicatrix-scars-archive.md`'s own header still says "not auto-loaded per session"
while it loads in full. This lane's three PRs move the two scar bodies to cold storage, attest
what a session actually receives, hard-cap the repomap, and build ScarBench — without deleting
the failure-memory asset the organism uniquely possesses.

## Ground to load (orchestrator first reads)

- `docs/scars/cicatrix-scars.md` [exists, 296,243 bytes] and
  `docs/scars/cicatrix-scars-archive.md` [exists, 397 KB — header line 3: "not auto-loaded per
  session", contradicted by measured injection]
- `.claude/rules/cicatrix-superscar.md` [exists, 13,986 bytes — the bridge that STAYS injected]
- `scripts/tests/test_superscar_budget.py` [exists, 8.6 KB — `BYTE_BUDGET = 14_000` at line 47;
  also runs a completeness check: every `W\d+[a-z]?` token cited in the superscar must have a
  real heading-body somewhere in `cicatrix-scars.md`/`-archive.md` — moving the bodies changes
  where that check must look]
- `scripts/lint_scar_number_collision.py` [exists, 11 KB — `DEFAULT_FILE =
"docs/scars/cicatrix-scars.md"` hardcoded at line 68; MUST be repointed if the file moves]
- `.claude/commands/scar.md` [exists — the `scar` skill/command that appends to
  `cicatrix-scars.md`; also references the fixed path and must be repointed]
- `scripts/build_repomap.sh` [exists, 8.5 KB, executable — target band at line 16 ("Target:
  4-20kB"); WARN (stderr only, not a failure) at line 233-234 when output exceeds 30,720 bytes;
  live file `~/.nuzantara-repomap.txt` (HOME, not repo) is currently 42,846 B, already over its
  own warn band — confirms the report's "recidiva-lite" claim]
- `docs/scars/` [proposed — `git mv` target for the two scar bodies]
- `scripts/tests/test_injected_surface_budget.py` [proposed]
- ScarBench (PR-3) has no existing home under `scripts/` — resolve the exact path during BUILD
  and record the choice in the PR body
- Superscar families #1 (HOME-fork — the repomap's live file is HOME-tracked, separate from the
  repo script) and #2 (esiste≠armato — the archive header's stale promise)

## PR-1: `chore(context): scar re-cold-storage + injected-surface attestation`

**Files**: `docs/scars/` [proposed, `git mv` target], `scripts/lint_scar_number_collision.py`
[exists, repoint], `scripts/tests/test_injected_surface_budget.py` [proposed], plus repoint
`.claude/commands/scar.md` [exists] and `scripts/tests/test_superscar_budget.py`'s completeness
grep [exists] to the new path
**Gear**: 2
**Build**:

- `git mv docs/scars/cicatrix-scars.md docs/scars/cicatrix-scars.md` and same for
  `cicatrix-scars-archive.md` — out of the auto-injected `.claude/rules/` directory; the 14 KB
  superscar bridge (`cicatrix-superscar.md`) STAYS in `.claude/rules/` with its own budget
- Repoint all 4 tools found this session: `scripts/lint_scar_number_collision.py`
  (`DEFAULT_FILE`), `.claude/commands/scar.md` (append target), the completeness grep in
  `scripts/tests/test_superscar_budget.py`, and the superscar bridge's own footer pointers to the
  new `docs/scars/` paths
- Add `scripts/tests/test_injected_surface_budget.py`: assembles the exact auto-load set (global
  CLAUDE.md + project CLAUDE.md + every `.claude/rules/*.md`), sums bytes, asserts the total is
  ≤ the ruled budget (report proposes 120,000 bytes — **a Zero ruling, not a decision made
  here**; use a named constant updatable in one line once ruled), and pins the membership list so
  a new file entering `.claude/rules/` must be budgeted in
- Per adversarial finding (survives, both reports): a CI reconstruction cannot observe what the
  harness actually delivered at runtime — the CI test is a **structural proxy**, not proof of
  live delivery. Add a companion SessionStart self-probe line (e.g. in
  `proprioception_sessionstart.sh`) that prints the byte-sum a live session actually received, so
  drift without a repo diff is visible in transcripts — label the two checks "structural
  attestation" vs "delivery attestation" distinctly
- Update the archive header ("not auto-loaded per session") to match reality once the move lands
  **Acceptance**: guilt fixture = a synthetic `.claude/rules/*.md` file added without a budget
  entry (CI test must fail); innocence fixture = the post-move state with only the superscar
  bridge present (must pass at ≤ the ruled budget). The assertion runs against a NAMED INTERIM
  constant of 120,000 bytes (the report's proposal), explicitly marked INTERIM pending Zero's
  ruling — the needs-ruling item below stays open; changing it to the ruled value must be a
  one-line edit. `scar query W76` must still resolve after the move (grep target, not auto-load).
  **Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6; final on-disk gate =
  orchestrator (Opus 5 xhigh)
  **Arming / prove-live**: armed when a fresh headless session's transcript shows the delivery
  self-probe reporting a total ≤ the ruled budget, AND
  `scripts/tests/test_injected_surface_budget.py` passes in CI on `origin/main`
  **Conflicts / order**: Wave 1, first in this lane. L10's superscar-family prune (separate lane)
  touches the same scar-corpus files and must wait for this PR to merge. Requires an
  **ALIGN-FLEET step**: refresh the repomap's HOME-fork twin's live copy on Pro after merge
  (`lint_home_fork.py` if the pair is declared) so Pro/Mini do not diverge.

## PR-2: `fix(repomap): rank-truncate to hard 20 KB cap`

**Files**: `scripts/build_repomap.sh` [exists, 8.5 KB] — the report does not name additional
files; if a companion Python ranking helper is needed, keep it inside this same script or a new
file under `scripts/` and document the choice in the PR body
**Gear**: 1
**Build**:

- Replace the stderr-only WARN (lines 233-234, fires at >30,720 bytes) with an in-generator
  **truncation by rank**: keep the highest-signal symbols (existing aider/ctags PageRank-style
  ordering) up to a hard 20 KB (20,480-byte) cap, drop the rest instead of warning-and-passing
- Preserve the existing WARN for the <1 KB "suspiciously small" case — unrelated failure mode
- Add a `repomap_size` probe to an existing proprioception-style receptor so a future overrun
  surfaces as a boundary-report line, not silently as stderr again (family-W55 antidote: "signal
  emitted != signal seen")
  **Acceptance**: guilt fixture = a synthetic symbol set rendering >20 KB uncapped (must truncate,
  not warn-and-pass); innocence fixture = a set already under the cap (unchanged). Live probe:
  `wc -c ~/.nuzantara-repomap.txt` ≤ 20,480 after the next 15-min cron tick; probe goes red if not.
  **Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6; final on-disk gate =
  orchestrator (Opus 5 xhigh)
  **Arming / prove-live**: armed when `com.nuzantara.repomap.15min` has run at least once post-merge
  on Pro/Mini and `wc -c` on the live file confirms ≤20,480; this is a HOME-fork-adjacent artifact
  (family #1) — verify the cron-invoked copy matches the repo script, not just the repo file
  **Conflicts / order**: Wave 1, independent of PR-1 (different file); may run in parallel.

## PR-3: `feat(eval): scarbench v0`

**Files**: not named by the report — propose `scripts/eval/scarbench.py` or
`scripts/scarbench.py` and record the final choice in the PR body, plus fixtures [proposed]
**Gear**: 2
**Build**:

- For each of the ~99 scars, mechanically derive a query from its TRAUMA paragraph (never
  hand-write plausible queries — the anti-reward-hacking guardrail); gold = its W-number+family
- Evaluate recall@k + citation precision under three configurations: full-injection (pre-PR-1
  baseline), bridge-only (post-PR-1), and grep-cascade (`scar query`/grep workflow)
- Hold out the 20 newest scars from tuning to prevent overfitting to the benchmark itself
- Stretch goal only (not required): reuse the harness over the 1,681 memory files (query = the
  file's own frontmatter description; gold = the file itself)
  **Acceptance**: the PR body includes one table — recall@3 for {full-injection, bridge-only,
  grep-cascade} on the 99-scar set. Harness guilt case: a mechanically-derived query that trivially
  matches its own gold scar by lexical overlap only (recall@1 >95% signals degenerate derivation,
  not working retrieval — flag as a known limitation, do not hide it)
  **Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6; final on-disk gate =
  orchestrator (Opus 5 xhigh)
  **Arming / prove-live**: armed when the benchmark runs end-to-end and its output table is
  reproducible on `origin/main` (re-run and confirm the numbers match the PR body, not just that
  the script exits 0)
  **Conflicts / order**: Wave 1. Depends on PR-1 (needs both pre-move full-injection and post-move
  bridge-only configurations to compare) — sequence after PR-1; may run parallel with PR-2.

## Needs-ruling carried (Zero only — this spec does NOT decide these)

1. **The context budget itself**: how much of every window doctrine may spend is a safety
   (scars visible) vs capability (context room) trade-off. The report's 120 KB figure is a
   recommendation — precedent: the ~17 KB MEMORY.md target was explicitly ruled 14/8. PR-1 must
   not hardcode 120,000 as final.
2. **Seat memory unification** (later-wave, not built here, but adjacent to this lane): whether
   MEMORY may be shared fleet-wide across per-seat config dirs, and read-only vs write for
   headless lanes. Do not pre-empt by symlinking memory paths in this lane.
3. **Publishing doctrine content publicly** (de-forking global CLAUDE.md into the public repo) —
   a later-wave recommendation, not part of this lane, requires a content audit only Zero can
   authorize.

## Suspend & ledger rules

Rule 8 (`CLAUDE.md` §2): a PR red three times for the SAME cause SUSPENDS — one PENDING-ARMS
line naming the cause, branch left alive, no fourth round. Fix-of-a-fix stops at depth 1. Every
BUILT-but-not-yet-ARMED step (e.g. `git mv` merged but the ALIGN-FLEET repomap refresh not yet
run on Pro/Mini) gets one row in `.claude/skills/modus/PENDING-ARMS.md` naming the artifact, the
missing arming step, and a named owner (never a bare `operator`).

## Out of scope

- R2 (JIT scar-retrieval hook), R4 (read-side memory automation + seat unification), R5
  (doctrine SSOT de-fork), R6 (`valid_until` frontmatter) — in the report's roadmap, not this
  lane's three PRs.
- Deleting or summarizing scar content — PR-1 relocates, never deletes or compresses bodies.
- Changing the superscar bridge's own content or budget threshold, beyond repointing footer
  pointers to `docs/scars/`.
- L10's superscar-family prune — a separate lane; this spec only sets the sequencing dependency.
