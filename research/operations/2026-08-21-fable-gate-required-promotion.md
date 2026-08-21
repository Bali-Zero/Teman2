---
date: 2026-08-21
domain: compliance
client_case: none
sources:
  - .github/workflows/harness-floor.yml (origin/main @ 17d45e568964775bb49d7683e419efb47f5e23ad)
  - .github/workflows/hot-zone-pr-gate.yml
  - .github/workflows/adversarial-review-gate.yml
  - .github/workflows/security.yml
  - scripts/harness_fable_gate.py
  - scripts/queue_ejection_attribution.py
  - scripts/ci/vercel_should_build.sh
  - scripts/mq.sh
  - docs/runbooks/merge-queue-discipline.md
  - research/operations/2026-08-09-harness-v2-teman2.md §6/§9
  - .claude/skills/modus/PENDING-ARMS.md (2026-08-10 entry, three tracked design gaps — read in full during the independent review round, see below)
  - evidence/brief.yml + evidence/pack.yml (origin/main, PR #4474, read as a live precedent — and, per finding F1 below, as the live repro of the bug that precedent exposed)
adversarial_review: pending-cross-family-kimi-k3
---

# Unblocking `harness/fable-gate` promotion to a required status check

## Mandate

Solve the two design problems `.github/workflows/harness-floor.yml`'s own "ARMING NOTE"
(2026-08-10) names as blocking the promotion of `harness/fable-gate` to a GitHub branch-protection
required status check:

- **(a) Synthetic-SHA relay** — a commit status posted on a PR's real head SHA never carries over
  to the merge queue's synthetic test-merge SHA.
- **(b) Fork-PR write permission** — a fork PR's read-only `GITHUB_TOKEN` breaks the workflow's own
  `gh api` WRITE calls, harmlessly today, as a hard block once required.

The deliverable is the design and the workflow/script changes that make the promotion safe — **not**
the branch-protection flip itself, which is explicitly reserved for the operator (§Solo-operatore).

## Premise check — both blockers verified live, neither had decayed

Read `.github/workflows/harness-floor.yml` at `origin/main` HEAD
(`17d45e568964775bb49d7683e419efb47f5e23ad`) directly (`git show origin/main:<path>`, never the
locally-cited summary) and confirmed the ARMING NOTE (lines 48-57) matches the file's actual
mechanics exactly:

- `harness/fable-gate` is posted by `scripts/harness_fable_gate.py` via
  `gh api repos/{repo}/statuses/{sha}` with `--sha` a **required** CLI argument (never guessed from
  a local HEAD) — confirmed by reading the script itself (169 lines, "PUBLISHER ONLY — NO VERDICT
  LOGIC"). It is always posted against the PR's real head SHA. **(a) is real, not stale.**
- Three `gh api ... /statuses/${SHA}` WRITE calls exist in the workflow (kill-switch bypass, the
  two "not applicable" default-publish steps), all using `${{ github.token }}` — the ambient,
  fork-restricted token on `pull_request` events. The kill-switch step even already carries its own
  `|| echo "::warning::kill-switch bypass publish failed (e.g. fork PR read-only token)..."`
  fallback, independent corroboration that this exact failure mode was already observed/anticipated
  for that one path. **(b) is real, not stale.**

Neither premise turned out to be false. Both are real properties of the mechanism as built.

**Refinement on (a), requested and verified after the mandate first landed**: blocker (a) is real,
but scoped to Gear-3 PRs specifically — never "every PR", exactly as the ARMING NOTE's own wording
already said ("deadlock the merge queue for every Gear-3 PR"). Traced the mechanism in the pre-fix
`origin/main` file: on a `merge_group` re-run, the default-publish steps' `SHA:` env
(`${{ github.event.pull_request.head.sha || github.sha }}`) falls through to `github.sha`, which for
a `merge_group` event *is* the synthetic queue SHA (same value this repo's own `docs-sync.yml` /
`docs-guardian.yml` treat as equivalent to `github.event.merge_group.head_sha` in their own
three-way fallback chains). `merge_group` runs are not fork-restricted, so that write succeeds. Net
effect: for an **ordinary (non-Gear-3) PR**, the workflow's own default-publish step already
self-heals on the merge_group re-run — a fresh `success` lands directly on the synthetic SHA with
zero relay logic. For a **genuine Gear-3 PR**, the merge_group re-run instead hits a pure no-op
notice ("`fable-gate` is intentionally NOT auto-published... must post a real verdict") — it never
re-publishes the verdict a session posted earlier on the PR's real head SHA, so the synthetic SHA
sits "Expected — Waiting for status" forever. A same-SHA relay fix (workflow reads the head-SHA
verdict, re-posts it on `github.sha` during `merge_group`) was evaluated directly against this
finding and confirmed technically executable for (a) alone (see "(a) — the two candidates" below) —
it is rejected because it leaves (b) untouched, not because it wouldn't work mechanically.

Also re-confirmed (b) directly against GitHub's own documentation (fetched live, "Events that
trigger workflows"): *"The `GITHUB_TOKEN` has read-only permissions in pull requests from forked
repositories."* This is a platform-level restriction — the workflow's own
`permissions: statuses: write` declaration cannot elevate a fork-triggered `pull_request` token past
it; the `permissions:` block only ever narrows a job's ambient scope, never widens it past what
GitHub's own fork-safety policy issues for that specific event. No `pull_request_target` was
evaluated as a workaround for this (see "(b) — the three candidates" below) — it was never proposed;
the chosen design removes every write instead of trying to keep one safely.

## Recommendation

**Move the required check off the commit-status entirely.** Instead of requiring `harness/fable-gate`
directly, promote the *workflow job* `harness-floor` (check-run name `Harness floor recompute`) —
the same class of required check `hot-zone-enforcement` and `R1 gate — adversarial review present`
already are in this repo, both of which already work correctly under `merge_group` with zero relay
logic, because a job's check-run is natively associated with whatever SHA the job executes against.

This resolves (a) and (b) simultaneously, by removing their shared cause rather than patching each
in isolation:

| | Old design | New design |
|---|---|---|
| What branch protection requires | a status a script posts by hand | this workflow's own job conclusion |
| "Not applicable" cases (no brief/floor<3, gear<3, kill-switch) | `gh api` WRITE of a neutral success | the job's own `exit 0` — no external call |
| Gear-3 case | left permanently unpublished; the *job* always passed regardless | job READS whether `scripts/harness_fable_gate.py` posted a verdict on the PR's real head SHA, and mirrors it as the job's own exit code |
| merge_group | status never posted there → would deadlock if required | job runs natively on `merge_group`'s synthetic SHA, same as every other required job in this repo |
| fork PR | WRITE fails silently (harmless today, hard-block once required) | zero writes anywhere — a GET on a public repo needs no elevated token, safe by construction |

`scripts/harness_fable_gate.py` is **unchanged**. It remains exactly what harness-v2-teman2.md §6
calls "meccanizzazione" — the durable, timestamped, tamper-evident record of the gate session's
verdict. Only what `harness-floor.yml` *does with that record* changes: from "leave the context
unpublished and let the job pass anyway" to "read it back and let the job's own conclusion depend on
it."

### (a) — the two candidates named in the brief, evaluated

1. **Have the workflow re-publish the status on `merge_group` (relay).** Technically executable —
   `merge_group` runs execute with the base repo's own token (not fork-restricted), so the WRITE
   itself would succeed there. But it does not fix (b): a fork PR still needs the `pull_request`-event
   default-publish to fire *before* the PR is even eligible to enter the queue (GitHub only queues a
   PR once its own required checks are already green), and that WRITE is exactly the one that fails
   on forks. Relay-on-merge_group patches (a) while leaving (b) exactly where it was. **Rejected as
   insufficient on its own.**
2. **Move to a check-run/job-based context (chosen).** Native to any SHA the job runs against, needs
   no relay, and as a side effect removes every WRITE this workflow makes — solving (b) for free
   rather than requiring a second, independent fix.

### (b) — the three candidates named in the brief, evaluated

1. **`pull_request_target`.** Would give the default-publish steps a write-scoped token even on
   forks — but it is unnecessary once nothing needs to write, and it is real attack surface: on a
   public repo `pull_request_target` runs with the base repo's write permissions against a workflow
   file it trusts (safe, checks out base by default) but a step that goes on to `git checkout` or
   *execute* anything from the fork's HEAD reintroduces the classic pwn-request pattern. This
   workflow already, deliberately, never checks out or executes PR content — it only extracts named
   YAML files via `git show <sha>:<path>` from the checked-out BASE repo's own git binary and parses
   them with `scripts/evidence_pack_lint.py`'s `yaml.safe_load` — but relying on that discipline to
   stay true forever, on a trigger designed to be safe *because* nothing needs elevated privilege
   here, is a needless dependency. **Not recommended, and not needed under the chosen design.**
2. **A `permissions:` block change.** Does not work as a fix for the write case: for a `pull_request`
   event from a fork, `GITHUB_TOKEN` is **platform-enforced read-only regardless of what the
   workflow's own `permissions:` block declares** — that restriction lives in the repo's own Actions
   settings (whether forks get write tokens at all), and toggling it repo-wide to fix one workflow
   would grant write tokens to *every* fork-triggered workflow, a strictly larger blast radius than
   the problem being solved. **Rejected.** (Used constructively, though: the redesigned workflow
   trims `permissions:` from `statuses: write` to `statuses: read`, since it now only ever reads.)
3. **Make the default-publish path not require a write at all (chosen).** This is what the
   check-run redesign does: the "not applicable" cases stop calling `gh api` altogether, and the one
   case that still needs externally-decided information only performs a `GET`, which needs no
   elevated scope on a public repo's public data.

## What ships

- **`scripts/ci/harness_gate_read.py`** (new) — the read-only verdict mirror. Resolves the PR's
  *real* head SHA per event shape:
  - `pull_request` → `github.event.pull_request.head.sha` directly.
  - `workflow_dispatch` → `github.sha` (the dispatched ref's tip — this *is* the real head SHA, no
    indirection).
  - `merge_group` → **not** the synthetic `merge_group.head_sha`, and **not** the trailing SHA
    embedded in the queue ref (`gh-readonly-queue/<base>/pr-<N>-<sha>`) — that trailing SHA is the
    **base** commit at queue time, verified against this repo's own `scripts/ci/vercel_should_build.sh`
    comment ("(1) The merge queue puts the BASE COMMIT in the ref name") and consistent with its use
    there as a diff base. The PR **number** is reliably embedded (`pr-(\d+)-`, the same shape
    `scripts/queue_ejection_attribution.py::PR_SHA_RE` already parses, and confirmed distinct per
    queue entry even under this repo's live 5-wide ALLGREEN speculative batching — `security.yml`'s
    own comment records "4 distinct refs across 60 merge_group runs"). The script resolves the real
    head SHA with a live `gh pr view <N> --json headRefOid` (a READ). Safe because GitHub ejects a
    queue entry the instant new commits land on its PR — a still-executing `merge_group` run is
    guaranteed to see the PR's current head SHA equal to what is being tested.

  Then reads `harness/fable-gate`'s state on that SHA via the combined `commits/{sha}/status`
  endpoint (already deduped to one entry per context) and mirrors it as this script's exit code:
  `success` → 0; anything else (no status posted yet, `failure`, `error`, or the read itself failing)
  → 1, fail-closed, with a message distinguishing "genuinely pending" from "could not verify"
  (cicatrix W88/W106 — a check that can't verify must never claim to have verified absence).

- **`scripts/tests/test_harness_gate_read.py`** (37 tests, all pass) — guilt + innocence per every
  branch above, including `main()` integration tests (see F2 below) and a static write-verb proof
  hardened past a live counterexample (see F3 below). `test_no_write_shaped_string_literal_appears_anywhere_in_the_code`
  scans the script's full AST (constants only — safe against its own docstrings, see that test's
  own docstring for why) for exact write-verb flags and write-shaped value prefixes, proving the
  script is incapable of publishing anything, by construction, not merely observed not to in the
  paths the behavioral tests happen to walk — with its own guilt pin
  (`test_write_shaped_literal_scan_actually_catches_the_reviewers_counterexample`) proving the scan
  is not vacuously green.

- **`scripts/ci/tracked_file_present_in_diff.sh`** (new, added in round 2 / G3) — the diff-membership
  check itself, extracted out of the workflow YAML so both `harness-floor.yml` and its test corpus
  call the *same* file. Prints exactly one of `present` / `inherited` / `absent` for
  `<head_sha> <relative_path> <changed_files_file>` — `inherited` is a distinct outcome from
  `present`/`absent` on purpose, so a caller can tell "exists in the tree but not this diff" apart
  from either extreme rather than collapsing it into a boolean.

- **`scripts/tests/test_harness_floor_brief_diff_membership.sh`** (6 tests, all pass) — guilt +
  innocence corpus, same style as `scripts/ci/test_hotzone_changed_files.sh`, now exercising
  `scripts/ci/tracked_file_present_in_diff.sh` directly (round 1's version reimplemented the check
  privately — see G3 above) — plus a scar-pin that greps `harness-floor.yml` for the real script's
  path, and a self-mutation test proving the corpus does fail against the pre-G3 tree-presence-only
  behavior (verified live: 2/6 fail under the mutant, 6/6 pass against the restored, byte-identical
  original).

- **`.github/workflows/harness-floor.yml`** (edited) — `workflow_dispatch: {}` trigger added (the
  re-trigger surface the operational corollary below needs); every `HEAD_SHA`/`BASE_SHA` fallback
  chain extended with `|| github.sha` / `|| 'main'` so the existing floor/gear/pack recompute also
  works under a manual dispatch; `permissions.statuses` narrowed `write` → `read`; the three
  `gh api .../statuses` WRITE calls removed (kill-switch bypass, "no brief/floor<3", "gear<3");
  Step 7c replaced with a call to `harness_gate_read.py`, guarded for the bootstrap window (F6);
  Steps 4 and 7b corrected to gate on the PR's own diff, not HEAD-tree presence, via
  `scripts/ci/tracked_file_present_in_diff.sh` (F1/F4/G3 — this is the load-bearing fix in the whole
  diff). Verified `actionlint` clean and `yaml.safe_load` clean after every edit.

- **`.github/workflows/main-push-failure-watch.yml`** (edited, round 2 / G1) — watcher-coverage list
  entry updated from the old workflow name to "Harness floor recompute".

## Independent Gear-3 review round — REWORK-DESIGN, 8 findings, all addressed

Per harness-v2-teman2.md §9 invariant 1 ("Generator ≠ grader"), a fresh, non-fork subagent with
zero prior context reviewed this diff cold before it was armed — not a self-review. Round 1
returned **REWORK-DESIGN** with 8 findings. Disposition:

| # | Severity | Finding | Fix |
|---|---|---|---|
| F1 | **CRITICAL** | Step 4 tested HEAD-tree presence of `evidence/brief.yml`, not whether THIS PR's own diff touched it. Since the file is tracked at a fixed repo-root path, every branch inherits whatever the last-merged Gear-3 PR left there — verified live: `origin/main`'s `evidence/brief.yml` still declares `gear: 3` for PR #4474's unrelated task, and a real single-file docs-ledger PR (#4535) inherited it. Under the OLD Step 7c (never failed) this was harmless; under the NEW read-based Step 7c it would have put every PR in the repo on the Gear-3 path and made the already-required `Harness floor recompute` job fail repo-wide. | `brief.present` now requires BOTH tree presence AND membership in `/tmp/changed-files.txt` (this PR's own merge-base-anchored diff). Symmetric fix on the pack side (Step 7b) closes F4 too. Pinned by `test_harness_floor_brief_diff_membership.sh` (4 cases) — verified live against the OLD logic, which fails 2 of the 4. |
| F2 | HIGH | `main()` — the only code path CI actually executes — had zero test coverage; three independent fail-open mutations (sha-unresolvable→0, `GhCallError`→0, `decide()`'s code discarded→always 0) survived all 30 prior tests. | 6 new tests call `hgr.main()` directly (mocked) plus one real subprocess smoke test. All three mutations verified to now fail 1-2 tests each. |
| F3 | HIGH | The two static "can't publish" proofs matched source TEXT, not argv semantics — a 4-line addition (`field_state = "state=" + verdict; _run_gh(gh_bin, ["api", url, "-f", field_state, ...])`) is a fully working status POST that passed all 30 tests. | Replaced with an AST scan of every string CONSTANT for exact write-verb flags (`-f`, `-X`, ...) and write-shaped value prefixes (`state=`, `context=`, ...) — verified to catch the reviewer's exact counterexample, verified to still pass clean against the script's own docstrings. |
| F4 | MEDIUM | This PR claimed to carry its own `evidence/brief.yml`/`pack.yml` but didn't — it inherited PR #4474's, a live instance of F1's exact failure mode. | This PR's own `evidence/brief.yml`/`pack.yml` now genuinely describe this task (see repo root) — and, post-F1-fix, would be structurally required to, since an untouched brief/pack no longer satisfies Steps 4/7b. |
| F5 | MEDIUM | `.claude/skills/modus/PENDING-ARMS.md` (2026-08-10 entry) tracks **three** design gaps, not two: (a) synthetic-SHA relay, (b) **verdict provenance/attestation** — `harness_fable_gate.py` never verifies WHO posted a verdict, so any credential with `statuses:write` can forge a `PASS` — and (c) fork-PR write permission. This task's mandate named only (a) and (c) (mapped here as blockers (a)/(b)); the draft §Solo-operatore implied nothing was left. | Corrected below: gap (b) is explicitly OUT OF SCOPE for this task and remains open — see the escalation note in §Solo-operatore. This design makes "no *posted status* ⇒ no merge" true, not "no *real, attested* verdict ⇒ no merge" — a real, higher-severity distinction now that the signal is load-bearing rather than decorative. |
| F6 | MEDIUM | Step 7c called `scripts/ci/harness_gate_read.py` with no bootstrap-window guard, unlike its three siblings — this PR's own first CI run (base checkout predates the new script) would die on a raw file-not-found instead of the established NOTICE+skip. | Added the same `[[ ! -f ... ]]` guard pattern used by Steps 3/7a5/7b. |
| F7 | MEDIUM (plausible) | The documented `gh workflow run harness-floor.yml --ref <branch>` recovery flow can't run on any branch cut before this PR merges — a ref whose `harness-floor.yml` predates it has no `workflow_dispatch:` trigger to dispatch. | Documented as a genuine, inherent bootstrap limitation (any repo's first PR to add a trigger has this property) rather than oversold as universally available immediately — see the operational corollary section. |
| F8 | LOW | Docstring claimed "same regex shape" as `queue_ejection_attribution.py::PR_SHA_RE`; the shipped regex is strictly looser (drops the 40-hex anchor). | Reworded to "a looser version of," with the reason stated. |

The reviewer also tried, and could **not** break: merge-queue speculative batching giving one
`merge_group` ref to multiple PRs (each entry gets its own ref/run, verified against
`docs/runbooks/merge-queue-discipline.md` + `security.yml`'s own measurement); the `statuses: read`
permission narrowing; `workflow_dispatch`'s security posture (no new trust boundary — a
`pull_request` run already executes the PR's own workflow-file version); the verdict-vocabulary
mapping between `decide()` and `harness_fable_gate.py::VERDICT_STATE`; and the required-context name
staying intact after the workflow-level (cosmetic) `name:` rename.

## Round 2 — independent Gear-3 review on the pushed PR, REWORK-BUILD, 3 findings, all addressed

A second fresh, non-fork subagent — dispatched cold against the actual pushed PR #4539 at its real
head SHA, not against a local summary of round 1's fixes — returned **REWORK-BUILD**: the design is
sound and both original blockers are genuinely solved, but three build defects had to land first.

| # | Severity | Finding | Fix |
|---|---|---|---|
| G1 | HIGH | The workflow's `name:` was renamed from "Harness floor & gate publisher" to "Harness floor recompute" without updating `.github/workflows/main-push-failure-watch.yml`'s watcher-coverage list, which still named the old string — `scripts/check_watcher_coverage.py` exits 1 and the "Watcher coverage" job was red on this PR's own CI. | List entry updated to the new name, with a comment explaining the rename and pointing at the CI run that caught it. Re-verified: `check_watcher_coverage.py` now exits 0 (97/97 live workflows covered). |
| G2 | HIGH | A REQUIRED check — `R1 gate — adversarial review present` — was red: this design doc's `adversarial_review:` frontmatter value was a narrative sentence, not the single vocabulary token `scripts/check_adversarial_review.py` requires, and no body heading matched `^##+\s+Adversarial review`. Both prior review rounds were same-vendor-family (Claude reviewing Claude-authored work) and don't satisfy R1's "generator != grader across model FAMILIES" requirement by the gate's own `KNOWN_SEATS` definition (zero Claude entries). | See the `## Adversarial review` section below — a genuine cross-family review (Kimi K3, Moonshot) was dispatched against the pushed diff after this finding, and its verbatim verdict is recorded there with the corresponding frontmatter token. |
| G3 | MEDIUM-HIGH | The F1/F4 diff-membership fix (round 1's most severe finding) was pinned by a test that **reimplemented the same two-line shell idiom privately** rather than exercising `harness-floor.yml`'s actual code — live mutation proved it: reverting *both* inline conditions in the workflow left `test_harness_floor_brief_diff_membership.sh` (4/4) and `test_harness_gate_read.py` (37/37) fully green, because neither test suite ever imported or ran the reverted code. Compounding: neither new test file is wired into any blocking CI path. | Extracted the check into a standalone, tested file — `scripts/ci/tracked_file_present_in_diff.sh` (same shape as the pre-existing `hotzone_changed_files.sh` / `vercel_should_build.sh`, both already `run:`-invoked rather than duplicated inline) — and rewrote `harness-floor.yml`'s Step 4 and Step 7b to call it. The test corpus now invokes that exact file (`SCRIPT_DIR/../ci/tracked_file_present_in_diff.sh`), plus a scar-pin asserting the workflow YAML actually references it, plus a self-test that reverting the real script to tree-presence-only makes the corpus fail — reproduced live: the mutant script fails 2/6 cases, the restored script (byte-identical diff against its pre-mutation copy) passes 6/6. The CI-wiring half of G3 (getting these suites onto a blocking path rather than the nightly `continue-on-error` sweep) is **not** addressed by this PR — see "What this deliberately did not do" below. |

Round 2 independently re-confirmed both original blockers are solved as designed: the required
surface is the job (`jobs.harness-floor.name: Harness floor recompute`, byte-identical to main's,
already in `required_status_checks` per a live API check), triggered on `pull_request` +
`merge_group` + the new `workflow_dispatch`; and a full-file grep for `gh api`/`statuses` found zero
live write call sites (only comments), `permissions.statuses` reads `read`, and no fail-open path
exists in `harness_gate_read.py`'s `resolve_real_head_sha` / `read_fable_gate_state` / `decide`
chain. It also reproduced F1 independently against a real merged PR (`#4535` inheriting `gear: 3`
from `origin/main`'s `evidence/brief.yml`).

## Adversarial review

Two review rounds ran against this diff before this section existed (detailed above, with full
disposition tables) — round 1 (REWORK-DESIGN, 8 findings, F1-F8, all fixed) and round 2
(REWORK-BUILD, 3 findings, G1-G3, all fixed). **Neither counts as this repo's R1 "generator != grader"
requirement**: both were fresh-context Agent-tool dispatches on Claude/Opus — the same model family
as the diff's own author — and `scripts/check_adversarial_review.py`'s `KNOWN_SEATS` deliberately
contains zero Claude entries, because a same-family review shares failure modes with the thing it is
reviewing (cicatrix-superscar.md family #6, "anti-hallucination blindness" — the whole point of
crossing families is that a defect invisible to one model's blind spots is often visible to another's).

A genuine cross-family review (Kimi K3, Moonshot) is in progress against this PR's real pushed diff
as this section is being written. Its verbatim verdict, findings, and the resulting
`adversarial_review:` frontmatter token will be recorded here — and only here, once real — before
this PR is armed to merge. Until that lands, the frontmatter token above (`pending-cross-family-kimi-k3`)
deliberately does **not** satisfy `KNOWN_SEATS`/`human-*`/`exempt-*`, so the R1 gate stays correctly
red: a token is an assertion about who reviewed, and it is written when there is a real answer, never
adjusted to turn a check green.

## Operational corollary — the retrigger flow this design implies

A completed GitHub Actions job has no native "pending forever, waiting on a human" state distinct
from "failed." So a Gear-3 PR with no verdict posted yet **fails** `Harness floor recompute` exactly
like a REWORK/BLOCK verdict would (same red X; the message differs). That is not a defect — it
matches this repo's own established discipline for re-testing a required check
(`docs/runbooks/merge-queue-discipline.md`, CLAUDE.md Agent PR Contract rule 3: "never rerun a check
without repointing the ref; use `mq requeue`, never a bare `gh run rerun`"). The gate session's
playbook after this PR becomes:

1. Review the diff independently (generator ≠ grader — harness-v2-teman2.md §9 invariant 1).
2. `python3 scripts/harness_fable_gate.py --verdict <V> --sha <PR-head-sha>` — unchanged, still the
   durable audit-trail record.
3. `gh workflow run harness-floor.yml --ref <branch>` — the new `workflow_dispatch:` trigger
   re-executes this exact job at the branch's current head, this time finding the verdict and
   passing. Never `gh run rerun` on the stale prior run (cicatrix W111 — a rerun replays an old ref,
   not a fresh check against current state).

This is a genuine, load-bearing consequence of choosing the check-run design, not an incidental
detail — it is called out explicitly rather than left for a future session to discover the hard way.

## A regression this design deliberately introduces, and why it is the point

Reading `evidence/pack.yml` as it exists on `origin/main` today (the pack for PR #4474, a prior
Gear-3 PR already merged) surfaces its own `residual_risks` entry, verbatim: *"the harness/fable-gate
commit status itself is still not a required branch-protection context... this PR's Gear-3
declaration satisfies the required 'Harness floor recompute' JOB, not an actual posted real-gate
verdict, consistent with every other Gear-3 PR merged under this system to date."*

That is the ground truth of the OLD design: Step 7c never had a failure path — it printed a notice
and the job passed regardless of whether `scripts/harness_fable_gate.py` had ever run. Every Gear-3
PR merged under this system to date, including the one that added the gear-ceiling logic this same
workflow now enforces, merged **without** a real posted verdict, because nothing checked for one.

The new Step 7c changes that: a Gear-3 PR now cannot pass the *already-required* `Harness floor
recompute` job without a real verdict posted first. This is not a side effect to apologize for — it
is the entire reason this task exists.

**A second, unintended regression was found and fixed before shipping (F1 above), and it is worth
naming explicitly because it is the more dangerous of the two.** The first draft of this diff would
have applied that same enforcement to *every* PR in the repo, not just genuine Gear-3 ones, because
Step 4 tested tree presence of `evidence/brief.yml` rather than this PR's own diff membership — and
that file, sitting at a fixed repo-root path, is inherited by every branch from whatever the last
Gear-3 PR left there. An independent review caught this before merge, with a live repro (a
single-file docs PR inheriting `gear: 3` from PR #4474). The fix (Steps 4 and 7b now require diff
membership, not just tree presence) is what actually makes "no real verdict ⇒ no merge" true **only
for PRs that are genuinely Gear-3**, rather than accidentally true for the entire repository.

## §Solo-operatore

Exactly one GUI action is left, and it is a branch-protection change, which is why this design does
not perform it:

> Add **`Harness floor recompute`** to `main`'s required status checks
> (`gh api repos/Bali-Zero/Teman2/branches/main/protection` → `required_status_checks.checks[]`, or
> `scripts/ci/setup_merge_queue_ruleset.sh`/the Settings UI). It is **already** required today
> (present in `infra/required.d/contexts.json`'s live snapshot) — nothing changes here.
>
> The actual net-new operator action, if the intent is specifically to require the
> `harness/fable-gate` *name* rather than rely on it flowing through the job: **there is none** — this
> design deliberately makes requiring the job equivalent to requiring the verdict, without ever
> adding `harness/fable-gate` itself as a second required context (a second commit-status context
> would resurrect blocker (a) exactly as it existed before). If a future session is asked to "add
> `harness/fable-gate` as required," the correct action is to point them at this doc and confirm
> `Harness floor recompute` already covers it — not to add the status context literally.

> **NOT covered, and NOT to be read as covered (finding F5, corrected from an earlier draft of this
> doc that implied otherwise): verdict provenance/attestation.** `.claude/skills/modus/PENDING-ARMS.md`'s
> 2026-08-10 entry tracks this as a *third*, separate design gap: `scripts/harness_fable_gate.py`
> never verifies WHO posted a verdict — any credential with `statuses:write` can post `PASS` on any
> SHA, so the required check attests only "someone with write access posted this string," not "a
> real gate session decided this." This task's mandate scoped to two named blockers (the synthetic-SHA
> relay and the fork-PR write permission); provenance/attestation was never in scope and this diff
> does not attempt it. **The severity of leaving it open has gone UP, not stayed flat**: before this
> PR, `harness/fable-gate` was not required at all, so a forged status was inert; after this PR (once
> the operator flips the required-check flag), a forged status becomes load-bearing for merge-blocking
> on every Gear-3 PR. A future session designing a fix should look at restricting the accepted source
> of that status (a dedicated GitHub App/bot identity) or a signing scheme — this doc does not
> prescribe which, that is exactly the kind of design decision this task was scoped to make for the
> other two gaps, not this one.

## What this deliberately did not do

- Did not touch `scripts/harness_fable_gate.py` — its publisher contract (verdict → status, `--sha`
  required, PWC needs `--conditions-ref`) is sound and unrelated to either blocker.
- Did not rename the required check `Harness floor recompute` — a sibling PR's own `evidence/brief.yml`
  (already on `origin/main`, PR #4474) names it as a hard constraint ("required context names...
  stay unchanged"), and renaming it would be pure required-check churn for zero benefit.
- Did not add `pull_request_target` anywhere — evaluated and rejected above; unneeded once nothing
  writes.
- Did not flip branch protection — reserved for the operator per §Solo-operatore.
- Did not consolidate the duplicated hot-zone pattern list between `evidence_pack_lint.py` and
  `hot-zone-pr-gate.yml`'s bash case-block — pre-existing, declared, out of scope for this task.
- Did not poll-and-wait inside the workflow for a verdict to appear (an alternative to the
  fail-then-retrigger flow) — rejected: it would hold a runner for an unbounded review window this
  repo's own `p9-cost-breaker.yml` exists to guard against, and the fail-then-`workflow_dispatch`
  flow already matches an established idiom (`mq requeue`) rather than inventing a new one.
- Did not design or build verdict provenance/attestation (PENDING-ARMS gap (b), F5) — genuinely out
  of this task's scope, left explicitly open with an escalated-severity note in §Solo-operatore
  rather than silently dropped or falsely claimed as covered.

## Answers to the four mandate items

1. **Recommendation per blocker, with tradeoffs**: see "Recommendation" above — (a) job/check-run
   over status-relay, because relay alone leaves (b) unsolved; (b) "don't need to write" over
   `pull_request_target`, because it removes the risk rather than accepting it.
2. **Premise check**: both premises verified true, neither had decayed (see "Premise check" above).
   A THIRD, more severe premise was found mid-task and is not one of the two named in the mandate:
   the workflow's own Step 4/7b tree-presence check (F1) would have made the new enforcement apply
   to every PR in the repo, not just Gear-3 ones — fixed, see the disposition table above.
3. **Branch protection**: not touched — see §Solo-operatore.
4. **Guilt + innocence tests**: `scripts/tests/test_harness_gate_read.py` (37/37 passing, including
   `main()` integration coverage and an AST-based write-verb proof hardened against a live
   counterexample) + `scripts/tests/test_harness_floor_brief_diff_membership.sh` (4/4, pinning the
   F1 fix, verified against the pre-fix logic to confirm it is not vacuously green).

PR number, ship receipts, and the independent gate session's verdict (both review rounds) are
recorded in the PR description and in `evidence/pack.yml` at repo root (this PR's own pack).
