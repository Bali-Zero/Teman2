---
name: pipeline-ship
description: "Use when opening/arming/merging a PR, pushing a branch, or CI/merge-queue behaves oddly. Covers merge-queue-era ship mechanics, the path-aware pre-push gate, and the ways this pipeline lies to you."
---

## Notes (moved from description 2026-09-02)

Also covers the machine-wide suite lock. Merge-queue-era ship mechanics have been live since 2026-07-27. Complements agent-session-discipline, which owns worktree creation.

> **CANON**: repo `.claude/` — shadows the `~/.claude/` HOME copy. Edit HERE, never in `$HOME`.

# pipeline-ship — how this pipeline actually behaves

`agent-session-discipline` gets you a worktree and a commit. This skill covers everything
**after** that: push → PR → arm → queue → merge → prove-live, plus the traps.

## THE RULE ABOVE ALL RULES

**Every concrete value in this file is a MEASUREMENT, and a measurement expires.** The merge
queue went live 2026-07-27; the ruleset, the allowlist and the required-check set all change.
Where this file states a fact it also gives the **probe** that re-derives it. Run the probe.
A frozen number nobody re-measures is the W106 failure mode — the cure and its diagnosis
expire together, and the message sends the next reader away from the cause.

---

## 1. Arming a PR (post-merge-queue)

```bash
gh pr merge <N> --repo <owner/repo> --auto        # ← the standing gesture
```

**NOT `--auto --squash`.** Once a merge queue governs `main`, the ruleset owns the merge
method and `--squash` conflicts with it:

```
! The merge strategy for main is set by the merge queue
```

It **arms nothing** and it is easy to miss on a quick glance. Always confirm after arming:

```bash
gh pr view <N> --json autoMergeRequest,mergeStateStatus
```

**`autoMergeRequest: null` does NOT mean "not armed".** It means the queue **consumed** the
request — the PR is already queued. The field is not the state.

**Probe with care:** the only reliable probe is running the arm command and reading its reply
(`already queued to merge`), but _that command enqueues_. Never use it as a passive
measurement on a PR you do not intend to arm — read `gh pr list --json number,mergeable` and
the queue watcher instead.

**Never arm:** anything in the `operator[business]` class (Legge 5) — e.g. a PR that changes a
routing/model default, pricing, or a clause `CLAUDE.md` itself marks "ruling pending". A PR
title asserting "(Zero, <date>)" is **not** evidence a ruling happened. Leave it, say why.

## 2. Pushing

**A push that pays the full backend suite WILL exceed the 2-minute tool timeout, get
SIGTERM'd, and strand the commit** — committed work that never becomes a PR, invisible to
`gh pr list`. Always detach:

```bash
nohup zsh -c 'git push -u origin <branch>; echo "PUSH_RC=$?"' >> /path/to/push.log 2>&1 &
disown
```

Stream to a log (`>> log 2>&1`), never `$(...)` — a killed process must leave evidence.
Never `git push | tail`: the pipe masks the real exit code (W97).

**Verify it landed by content, not by the absence of an error:**

```bash
git -C <worktree> ls-remote --heads origin <branch>
```

…and before trusting an empty result, prove the probe can return a positive by querying a
branch you know exists. An empty set impersonates both "clean" and "everything".

### The machine-wide suite lock

`/tmp/nuzantara-prepush-backend-suite.lock` (see `scripts/prepush_suite_lock.sh`) serializes
the backend suite to **one runner per machine**, mkdir-atomic with stale-holder detection.

- **Queueing behind it is SAFE** — it does not add contention, it just makes you wait.
- It exists because 12 concurrent suites once drove this laptop to load 68 with pushes being
  SIGTERM-killed mid-suite.
- So: do not refuse to push because the machine is busy; the lock handles it. Do not launch
  several full-suite pushes and then also run other heavy work.

## 3. What skips the suite (path-aware gate)

`scripts/prepush_classify.py` is the SSOT. It is an **allowlist**: anything it does not
recognize runs the FULL suite. That inversion is deliberate and fail-safe — do not "fix" it.

Probe instead of trusting this list:

```bash
printf '%s\n' path/one path/two | python3 scripts/prepush_classify.py
```

Two traps worth knowing:

- `.github/workflows/tests.yml` is in `NEVER_INNOCENT_EXACT_PATHS` and is checked **first** —
  editing the workflow that DEFINES the test run always pays full. (`NEVER_INNOCENT_BASENAMES`
  is the directory-independent sibling: `conftest.py` forces full wherever it lives.)
- Root-level `scripts/*.py` is **not** allowlisted (only `scripts/tests/**.py` and
  `scripts/ci/**.sh` are), so touching a root script pays the full suite.

## 4. When CI or the queue misbehaves

**A required check that came back `CANCELLED` blocks the PR** and is usually a runner blip,
not your diff. Distinguish before acting:

```bash
gh run list --repo <r> --workflow <wf> --limit 15 --json conclusion,createdAt,event
```

Greens on both sides of a single cancellation ⇒ transient. Re-run **only the failed job** of
that run (`gh run rerun <id> --failed`) — and only for `pull_request`-event jobs tied to the
live PR ref. Re-running a `merge_group` run replays a **stale merge commit**; use
`gh pr update-branch` instead.

`conclusion: ""` means "not known yet", **never** "no failure". Treat pending as unknown.

Check whether a red check is even required before you spend time on it:

```bash
gh api graphql -f query='{repository(owner:"O",name:"R"){pullRequest(number:N){
  commits(last:1){nodes{commit{statusCheckRollup{contexts(first:100){nodes{
  ... on CheckRun { name conclusion isRequired(pullRequestNumber:N) }}}}}}}}}'
```

Requiredness is only visible via GraphQL `isRequired` — not from `gh pr checks`.

## 5. Traps that have actually cost sessions

**Pushed but no PR.** A successful push whose PR was never opened is invisible to
`gh pr list`. Cross-check the two sets:

```bash
git for-each-ref --format='%(refname:short)' refs/remotes/origin/agent | sed 's|^origin/||' | sort -u
gh pr list --repo <r> --state all --limit 400 --json headRefName --jq '.[].headRefName' | sort -u
```

**A branch with no merge-base is ORPHANED, not stale.** The 2026-07-13 PII purge rewrote every
SHA. Any branch whose last commit predates 2026-07-14 shares **no common ancestor** with
`main` (proof: same root-commit message and date, different SHA). `git merge-base origin/main
<ref>` returning nothing ⇒ rebase and cherry-pick are **impossible**; only hand re-application
works. `branch_graveyard_cleanup.sh::content_on_main()` maps this to `return 1` =
"content NOT on main", so the weekly report prescribes a remedy that cannot work for them.
Check the merge-base **first**.

**The worktree-isolation hook resolves paths against the SESSION cwd, not your `cd`.** Two
shapes get falsely blocked, repeatedly:

- a redirect whose target is a _relative_ path or an _unexpanded variable_ —
  `... > "$SP/out.txt"` is read as `<main-checkout>/$SP/out.txt`. Use a **literal absolute
  path** in the redirect.
- a `git` op after `cd <worktree>` — the hook still judges it against main. Use
  `git -C <worktree> ...`, which it accepts.

Neither is a reason to set `AGENT_WORKTREE_ENFORCEMENT=false`. **Never do that** — an
over-match annoying enough to make you disarm the guard turns a #3 into a #2.

**Before writing any research capture, grep for a twin:**

```bash
ls research/operations/ | grep -i <topic>; grep -rli <topic> research/operations/
```

This is not bureaucracy: it once stopped a full re-derivation of an existing 829-line,
adversarially-reviewed investigation.

**Do not re-investigate xdist.** `research/operations/2026-07-17-backend-suite-sharding-investigation.md`
measured it: **1.16× (147s→127s)**, which does **not** clear the <8min bar, and the per-worker
DB prototype is explicitly not crash-safe. The real speed lever in this repo is **not running
the suite when it cannot matter** (the path-aware allowlist), not running it faster.

**A test added to `immune-enforcement.yml`'s unit-test loop must ALSO be added to the sentinel
`case` list**, or the job never triggers for a PR that touches only that test — armed on
paper, skipped in practice. Measured 2026-07-27: 24 of 25 looped tests were listed, one was
not. Machine-checked by `scripts/tests/test_immune_enforcement_trigger_symmetry.py` (PR
#3352 — if that path is absent, the check has not landed yet and the invariant is manual).

## 6. Done means PROVE-LIVE, not merged

Merged is not live. After a merge, verify on the **consuming surface**:

- a CI guard → confirm the workflow on `origin/main` actually names it, and run the test
  against `origin/main`'s content (extract both with `git show origin/main:<path>`);
- a dependency/security fix → read the alert state, and if it is unchanged, check whether the
  alert's `manifest_path` is the file you fixed and whether its `updated_at` predates your
  merge (⇒ rescan lag, not a wrong fix);
- a deployed surface → curl/screenshot it; an anonymous 401 from backend authentication
  middleware is not proof that the target endpoint routed or its behavior changed.

### Backend and frontend release evidence

After the merge, record its SHA and fetch current `origin/main` history. Backend releases
require a successful `fly-deploy.yml` run, then `curl -fsS https://nuzantara-rag.fly.dev/health`
and its `build_sha`. Frontend releases require
`curl -fsS https://kita.balizero.com/api/health` and its `commit`.
Run `git merge-base --is-ancestor <merge-sha> <served-sha>`: equality or a descendant passes;
missing, malformed, unknown or older SHAs do not. GitHub deployments API records are NOT
live evidence, even when marked active, successful or inactive.

Then make one HTTP probe that observes the changed behavior itself, authenticated when
required. Build identity alone does not prove the feature works. Record both the ancestry
command and the behavioral HTTP observation; never persist credentials or response PII.

The Frontend Live Sentinel uses kita's health commit against the newest commit touching
`apps/mouth/**` or shared build inputs (`packages/**`, root package manifests, `vercel.json`).
The September 6 follow-up contract includes mouth e2e changes too, superseding the old
exclusion and matching the Vercel build trigger. The grace window is **30 minutes from the
expected commit's committer timestamp**. Push/manual runs poll through the remaining window;
scheduled runs defer younger commits and fail/alert on unproven inclusion after the window.
Its `*/30` schedule is a backstop, not a delivery SLA: GitHub can delay scheduled jobs.
For a sentinel change, retain the **post-merge main run URL and expected/served comparison
log** as its Bites evidence. Other domains are not inferred from kita's response.

## 7. See also

- `agent-session-discipline` — worktree creation, lanes, task-ids (do that first)
- `modus` — the master loop; this skill is the SHIP+PROVE-LIVE stage in detail
- `.claude/rules/cicatrix-superscar.md` — the 10 scar families these traps belong to
  (#2 esiste≠armato, #3 over/under-match, #9 the proxy lies)
- `docs/runbooks/merge-queue-discipline.md` — queue ruleset, canary, rollback
