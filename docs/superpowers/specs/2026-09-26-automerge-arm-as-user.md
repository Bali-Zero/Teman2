# SPEC — arm whitelisted PRs as a user via a PAT

date: 2026-09-26 · owner: next infra/auto-merge lane · status: **PARKED, pre-implementation**
origin: council review of `agent/air-m5/infra/automerge-pat-0926` (Builder Contract rule 1 —
"a fix-of-a-fix stops at depth 1 … write the spec"). Single commit, two independent councils
(Codex, Gemini Pro) both BLOCK; a same-shape retry is refused by the contract.

**Status: normative for whoever resumes this lane.** Implementation is a separate PR, after this
spec is read. Where the resumed branch and this spec disagree, say which is wrong in the PR, not
silently in code.

## 0. Problem

`.github/workflows/auto-merge-whitelist.yml` arms auto-merge on whitelisted PRs using
`GITHUB_TOKEN`. `gh pr merge --auto` with that token sets `autoMergeRequest` with
`enabledBy: github-actions` — but that arm **never enters the merge queue**. Measured: PRs
#7098/#7099/#7104/#7119 sat five days with zero queue events under an app-token arm, while a
human re-arm queued each immediately. The workflow's own verdict step read the dead arm as
"armed" and stayed green — scar family #2, esiste≠armato, in a workflow whose whole job is to
arm.

## 1. Ruling honored

RULED 2026-09-26 (Zero), quoted from the parked branch's own commit `5ed364d073`:

> An arm this workflow made with GITHUB_TOKEN set autoMergeRequest (enabledBy github-actions) and
> never entered the merge queue: #7098/#7099/#7104/#7119 sat five days with zero queue events,
> while a human re-arm queued each at once. The verdict step read that dead arm as armed and
> stayed green. The arm step now uses AUTOMERGE_PAT (GITHUB_TOKEN fallback when absent), drops a
> prior github-actions arm before re-arming as the PAT owner, and the verdict reads both queue
> fields plus the enabler: an arm by github-actions is red. The PAT value reaches one step whose
> body only runs gh pr merge; workflow-level permissions are empty.

Whoever resumes this lane honors the ruling by keeping the outcome (a whitelisted PR is armed as a
real user identity and actually enters the merge queue, and a dead `github-actions` arm is
diagnosed as red rather than accepted) — not by reproducing the parked branch's mechanism, which
two independent councils showed does not deliver that outcome safely.

## 2. What the parked branch does (for orientation, not as a starting diff)

One commit, `5ed364d073`, on `agent/air-m5/infra/automerge-pat-0926`, touching
`.github/workflows/auto-merge-whitelist.yml` and `scripts/tests/test_auto_merge_whitelist.py`:

- The "Enable auto-merge" step's `GH_TOKEN` env becomes `secrets.AUTOMERGE_PAT ||
secrets.GITHUB_TOKEN`.
- On finding a prior arm with `enabledBy: github-actions`, the same step runs
  `gh pr merge --disable-auto` (using the PAT) before re-arming with `gh pr merge --auto
--match-head-commit`.
- The "Verify the arm reaches the merge queue" step reads `autoMergeRequest.enabledBy.login` and
  `mergeQueueEntry` via a GraphQL query piped through `jq`, and treats an `armed-by:github-actions`
  result as red; anything else falls through a catch-all branch.
- `test_auto_merge_whitelist.py` grows `test_the_pat_value_reaches_one_step_whose_body_only_calls_
gh_pr_merge`, `test_no_expression_is_interpolated_into_any_run_body`, and
  `test_token_permissions_are_empty_at_workflow_level` as the confinement guards for the PAT.

## 3. Council findings (verbatim-summarized, severity, file:line)

### Codex (`council-b/out-codex.txt`)

| #   | Severity | Location                                         | Finding                                                                                                                                                                                                                                                                                                                                                                                                   |
| --- | -------- | ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1  | MAJOR    | `auto-merge-whitelist.yml:248`                   | A stale run disarms a valid arm. Run A reads `armed-by:github-actions`; a new commit lands and run B correctly arms as the PAT owner; run A (still executing against the old state) then disarms B's arm. Run A's own re-arm then fails because it uses `--match-head-commit` against the OLD sha, leaving the PR disarmed. The final verify step goes red and reports the damage but does not repair it. |
| C2  | MAJOR    | `auto-merge-whitelist.yml:250`                   | The PAT is used beyond the single authorized command. When a `github-actions` arm is found, the workflow runs `gh pr merge --disable-auto` **with the PAT**, contradicting the explicit constraint "nothing but `gh pr merge --auto`" — the destructive disarm mutation from C1 is also attributed to the PAT-holding step.                                                                               |
| C3  | MINOR    | `scripts/tests/test_auto_merge_whitelist.py:301` | The PAT-confinement test only recognizes a fixed set of literal `gh …` invocations. Verified in-memory that adding `command gh api /user`, a Python one-liner printing `GH_TOKEN`, or `gh pr merge … --admin` still passes — the test does not prove the declared invariant (no exfiltration, no operation beyond arming).                                                                                |

### Gemini Pro (`council-b/out-gemini-pro.txt`)

| #   | Severity | Location                                                                                                                                      | Finding                                                                                                                                                                                                                                                                                      |
| --- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| G1  | MAJOR    | `auto-merge-whitelist.yml:265-270` ("Verify the arm reaches the merge queue")                                                                 | GraphQL eventual-consistency race: the verify step's read query can hit a stale replica immediately after the arm step's mutation, seeing `autoMergeRequest`/`mergeQueueEntry` as `null` → `jq` returns `"none"` → the catch-all `exit 1`s. Flaky false-red on a perfectly valid arm.        |
| G2  | MAJOR    | `scripts/tests/test_auto_merge_whitelist.py`, `test_the_pat_value_reaches_one_step_whose_body_only_calls_gh_pr_merge` (regex `(?:^            | [;&                                                                                                                                                                                                                                                                                          | (`])\s*gh\s+(\S+\s+\S+)`) | The regex only checks the character immediately preceding `gh`. `if gh api graphql…`, `{ gh auth… }`, or `FOO=bar gh issue…` are preceded by a space/letter/bracket the character class does not cover, so an illicit `gh` invocation in the PAT step passes undetected. |
| G3  | MAJOR    | `scripts/tests/test_auto_merge_whitelist.py`, `test_no_expression_is_interpolated_into_any_run_body` (check `if "        run: \|\n" in step`) | The injection guard is a literal string match on the `run: \|` block-scalar form. A single-line `run: echo "${{ github.event.pull_request.title }}"` or an alternate block scalar (`run: >`, `run: \|-`) is invisible to the check and would pass with an interpolated expression inside it. |

### Kimi (`council-b/out-kimi.txt`)

| #   | Severity  | Location                                                                                      | Finding                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| --- | --------- | --------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| K1  | **MAJOR** | `auto-merge-whitelist.yml:276` (jq query) and `:295-297` (green branch)                       | The green catch-all accepts any bot arm, not just a user's. The GraphQL query fetches `enabledBy{login}` but never `__typename`, so the ONLY red case is the literal string `armed-by:github-actions` — everything else, including `armed-by:dependabot`, is green. Concrete scenario: a whitelisted dependabot PR is armed by `@dependabot merge` (an app-token arm, the same class already proven dead on #7098/#7099/#7104/#7119); the next trigger reads `armed-by:dependabot` (not the literal `github-actions`) and the verdict is green, though the PR is neither queued nor armed by a user. |
| K2  | MINOR     | `auto-merge-whitelist.yml:276,284`                                                            | `mergeQueueEntry.state` is fetched but never read — `.mergeQueueEntry != null` alone yields `"queued"` even for a `LOCKED`/`UNMERGEABLE` entry.                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| K3  | MINOR     | `auto-merge-whitelist.yml:248,287`; test pin `scripts/tests/test_auto_merge_whitelist.py:336` | The dead-arm literal `github-actions` is corroborated by in-repo evidence (`scripts/fleet_dashboard.py:351-366`) but never checked against the live API — a spelling drift (`github-actions[bot]`) would silently fall into K1's green catch-all.                                                                                                                                                                                                                                                                                                                                                    |

Where councils agree (Codex C2 / Gemini G2-G3 on PAT confinement; Codex C1 / Kimi K1 on the green
catch-all being too permissive), that is the strongest signal for where a redesign must start:
the verify step's discrimination between "armed by a real user" and "armed by anything else with
write access" is the load-bearing property, and every council found a way through it.

## 4. Acceptance criteria (falsifiable, one per numbered finding above)

1. **AC-C1/K1.** A test asserts the verify step's GraphQL read includes `enabledBy{__typename
login}` (or equivalent) and the verdict is GREEN only on `mergeQueueEntry` in a live queued
   state OR `enabledBy.__typename == "User"` (optionally pinned to an expected login via a repo
   variable) — RED on any Bot-enabled arm (`github-actions`, `dependabot`, or any other bot login),
   not only the one hardcoded string.
2. **AC-C1 (stale-run disarm).** A test with two interleaved runs (A reads an old state, B arms
   correctly in between, A resumes) asserts A does NOT disarm B's valid arm — e.g. by having the
   disarm/re-arm sequence check the PR's current head/enabler immediately before mutating, inside
   a single atomic step, or by serializing per-PR so a stale run is discarded before it mutates.
3. **AC-C2.** A test asserts the PAT (`AUTOMERGE_PAT`) is referenced in the environment of no more
   than one step, and that step's `run:` body contains only `gh pr merge --auto …` — no
   `--disable-auto` or any other `gh` subcommand reachable with that token. Any repair/disarm
   mutation this redesign still needs must run with `GITHUB_TOKEN` in a separate step.
4. **AC-C3/G2.** A test proves the PAT-confinement guard cannot be defeated by any of: an
   additional `gh api …` call, a non-`gh`-prefixed command that reads the token from the
   environment (e.g. a `python -c` one-liner), or a `gh` invocation preceded by a shell operator
   the current regex's character class does not cover. The guard must parse the step's full
   script structure (arguments, variables, redirections) rather than grep a fixed literal set.
5. **AC-G3.** A test proves the injection guard (`test_no_expression_is_interpolated_into_any_
run_body` or its successor) catches a `${{ }}` expression in a single-line `run:` and in `run:
   > `/`run: |-`block-scalar forms, not only`run: |`.
6. **AC-G1.** A test or a documented workflow change proves the verify step tolerates GraphQL
   read-after-write replication lag — e.g. a bounded retry before concluding `"none"` — so a valid
   arm does not go red on a stale replica read. (Acceptable to demonstrate via a fixture that
   simulates one stale read followed by a consistent one, if a live-lag repro is impractical.)
7. **AC-K2.** A test asserts the verdict distinguishes `mergeQueueEntry.state` values (e.g. only
   `QUEUED`/`AWAITING_CHECKS`/`MERGING` count as green) rather than treating any non-null entry as
   queued.
8. **AC-K3.** A test asserts the `github-actions` (or whatever bot logins are red) literal(s) are
   checked against a live or fixture-derived value rather than hardcoded with no verification path
   — at minimum, a comment or test documents where the spelling was last confirmed against the
   API and how to re-confirm it.

AC-C1/K1 and AC-C2 are the two highest-priority items — they are where independent councils
converged. A redesign that resolves them and leaves the others as follow-up rows is an acceptable
partial ship, provided the follow-ups are ledgered (see §6).

## 5. Non-goals

- Redesigning the whitelist selection logic upstream of arming (which PRs qualify) — untouched by
  the council review and out of scope here.
- The Dependabot SHA-bump floor exemption — that is the sibling parked branch, covered by
  `2026-09-26-dependabot-floor-exemption.md`.
- Prescribing PAT vs. GitHub App installation token as the long-term identity source — either is
  acceptable if the acceptance criteria pass; the council findings are about behavior, not about
  which credential type is used.

## 6. Where the branch is

- Worktree: `.worktrees/infra-automerge-pat-0926`
- Branch: `agent/air-m5/infra/automerge-pat-0926` (unpushed)
- Commit: `5ed364d073`
- On resume: rebase on fresh `origin/main` first. Given two independent councils (Codex, Gemini
  Pro) plus Kimi each found MAJOR-or-worse issues with non-overlapping detail, treat the single
  commit as a reference for what NOT to reuse as-is rather than a base to patch forward from.
