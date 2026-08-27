# Merge Queue Discipline — Bali Zero / Nuzantara

> Owner: @Balizero1987 · Shipped: feat/merge-queue-rulesets-2026-05-24 · SOTA L3 wave.
> Reactivated: pipeline-v2 mandate, 2026-07-27 (org unlock — see status banner below).
>
> Sister docs: [`research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md`](../../research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md) ·
> [`research/operations/2026-07-26-ci-pr-latency-the-excursus-is-cheap-the-slots-are-not.md`](../../research/operations/2026-07-26-ci-pr-latency-the-excursus-is-cheap-the-slots-are-not.md)
> (that report explicitly recommended AGAINST a merge queue on 2026-07-26 — correctly, for the repo
> that existed at that moment. Its own reasoning was the ownership fact below, which changed the
> next day. Read it for the PR-latency argument, not for the merge-queue verdict.)
> Closes pattern: 17% PR rebase-manual (wave 2026-05-24 ex: #823, #815, #835-cherry, #805-cherry).

---

## STATUS: ACTIVE (org unlock 2026-07-27)

**What changed and why the old verdict flipped.** GitHub Rulesets — the mechanism a merge queue is
built on — are unavailable on repositories owned by a personal **User** account; they require an
**Organization**-owned repository. This repo was `Balizero1987/Teman2` (`owner.type: User`) from
creation through 2026-07-26, which is why the original `setup_merge_queue_rulesets.sh` was deleted
2026-07-17 as unrunnable dead automation, and why the 2026-07-26 PR-latency report listed a merge
queue under "explicitly not recommended." **On 2026-07-27 the repo moved to org `Bali-Zero`**
(verified live: `gh api repos/Bali-Zero/Teman2 --jq '{owner:.owner.login,type:.owner.type}'` →
`{"owner":"Bali-Zero","type":"Organization"}`). `Balizero1987/Teman2` now resolves only via GitHub's
own redirect — never hardcode it in new code; resolve the slug live (`gh repo view --json
nameWithOwner`), as `scripts/ci/setup_merge_queue_ruleset.sh` does.

**Live state, verified at time of writing:**

| Fact                                                         | Value                                                                                                                                                                                                                                                                                                   |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ruleset                                                      | id `19779175`, name `merge-queue-main`, created 2026-07-27                                                                                                                                                                                                                                              |
| Enforcement                                                  | `active` (flipped 2026-07-27 ~01:00Z; proof: first queue-merged SHA `7aab65b1ee`, 25/25 required contexts SUCCESS, 0 cancelled)                                                                                                                                                                         |
| Rule                                                         | single `merge_queue` rule — see canonical body in `scripts/ci/setup_merge_queue_ruleset.sh`                                                                                                                                                                                                             |
| Required status checks on `main` (classic branch protection) | **26** contexts, `strict: false` (was 25 on 2026-07-27 — the count moves as CI grows; re-measure, never cite)                                                                                                                                                                                           |
| IaC                                                          | `scripts/ci/setup_merge_queue_ruleset.sh --status\|--enable\|--disable\|--apply`                                                                                                                                                                                                                        |
| Watcher                                                      | `.github/workflows/merge-queue-watch.yml` — polls every 10 min for ejections + armed-but-stuck PRs (GraphQL; `merge_group`'s Actions trigger does not deliver the `destroyed` action, so event-based ejection detection does not exist — verified against GitHub's own Actions-trigger docs 2026-07-27) |

**Enforcement is ACTIVE as of 2026-07-27 (~01:00Z).** The ruleset previously existed with
`enforcement: disabled` so the rule content could be live and reviewable _before_ it started gating
anything — that review-then-flip sequence is documented in the **Activation** section below, which
now doubles as the record of what was followed and the re-enable procedure after a rollback (§7). The
flip itself was a deliberate, sequenced act, never a side effect of running `--apply`.

---

## 1. Why merge queue?

Multi-agent waves (Claude Opus, Codex, Gemini, Subhi, autonomous cron PRs) land
patches in parallel against `main`. Without serialization:

- Two PRs both pass CI on stale `main`, the second merge silently breaks the first.
- A 4th-LLM panel rebase becomes "rescue PR" (cf. PR #845/#848/#849 in this wave).
- Agentic CI-tampering: a rogue agent could merge a workflow change that disables
  `Detect Secrets`, then the next PR slips a secret through (arXiv 2605.07135).

GitHub merge queue solves both:

1. Re-runs required checks on a synthetic "test PR" against the **current HEAD of main**
   so two valid-against-stale-main PRs cannot collide.
2. Combined with CODEOWNERS + path-restricted rulesets, agents cannot land changes
   to `/.github/workflows/`, `/fly.toml`, migrations, auth, billing, or pricing
   without explicit @Balizero1987 review.

This is unchanged from the original rationale — only the _availability_ fact changed.

---

## 2. Required status checks (enforced today via classic branch protection)

Live count, re-measurable any time via `gh api repos/Bali-Zero/Teman2/branches/main/protection --jq
'.required_status_checks.checks[].context'` (or `scripts/ci/setup_merge_queue_ruleset.sh --status`,
which prints the _effective_ rules including any ruleset-level required checks once the queue rule
type expands beyond `merge_queue`): **26 contexts**, `strict: false` (merge is allowed once checks
pass on the PR's own base, not necessarily on the very latest `main` — this is exactly the race the
merge queue now closes, enforcement having flipped to `active` on 2026-07-27).

This list is long and changes as CI grows; do not hand-copy it into this doc — it goes stale
immediately and the live query above is the source of truth. It was **25** when this section was
written on 2026-07-27, corroborated by the 2026-07-26 PR-latency report's own measurement, and **26**
one day later: the drift is the normal case, not an anomaly, which is why the query and not the
number is what this section is really telling you to use.

Two properties of the list that are NOT re-derivable from its length, and that decide whether a
given check can ever be added to it:

- **A required context that needs a repository secret is impassable for Dependabot**, whose runs do
  not receive them. `Snyk Docker Security` cannot be made required for this reason — it needs
  `SNYK_TOKEN`. Anything guarding a secret-dependent job has to alarm instead of gate.
- **A workflow-level `continue-on-error` does not keep a job's own check green** — the check stays
  red while the _run_ concludes `success`. So "the run is green" is not evidence that every required
  context inside it passed; read the contexts.

`strict=false` today means a PR can merge against a base that is no longer `main`'s tip. **This is
the specific race the queue closes** — not a separate future improvement, the headline reason for
§STATUS above.

---

## 2bis. Required vs advisory checks — reinstatement rule

Zero ruled on 2026-08-27 that main's required status checks be cut from 27 to 9 — applied live the
same day. Within the hour the reinstatement rule fired twice, on two real catches, bringing live
required back to **11**:

- `actionlint — workflow schema + expression gate` — reinstated after PR #5050 shipped a new job
  with `timeout-minutes: 5`, under the repo's own 10-minute checkout-budget floor
  (`scripts/lint_workflow_timeout_floor.py`). Only a required actionlint run would have caught this
  before merge.
- `Every guard proves guilt AND innocence` — reinstated after PR #5045 registered 3 new hooks that
  were never entered into `infra/guard-conformance/registry.json` (superscar family #3's own C1
  discipline: no guard without a guilt+innocence pair on record).

**The rule**: a check demoted from required to advisory on 2026-08-27 is reinstated to required —
by anyone, no further ruling needed — the moment either of two things happens:

1. **Main Red Breaker** — the advisory workflow goes red on `main` itself (not merely on a PR).
2. **A real catch** — the advisory check is the one that would have (or did) stop a genuine defect
   from landing, the way actionlint and guard-conformance just did.

Everything else stays advisory (non-required, non-blocking, still runs and still reports) for **30
days from 2026-08-27, through 2026-09-26**. At that date each surviving advisory context gets an
explicit call: reinstate, or rule it advisory-permanent. Ledger: `.claude/skills/modus/PENDING-ARMS.md`
(opened 2026-08-27, "16 advisory contexts under 30-day reinstatement watch").

As with §2 above: **do not hand-copy the live required-context list into this doc.** The count here
(11, up from the 9 first applied) is already the second number this rule has produced in one day —
re-measure with the query in §2, or read `infra/required.d/contexts.json`
(`scripts/ci/snapshot_required_contexts.py` regenerates it).

**Re-adding a context to required** (the reinstatement mechanism, whether triggered by this rule or
by any future ruling):

```bash
gh api -X PATCH repos/Bali-Zero/Teman2/branches/main/protection/required_status_checks \
  --input <file>
```

`<file>` is a JSON body using the `checks` form, one object per context:

```json
{
  "strict": false,
  "checks": [
    {
      "context": "actionlint — workflow schema + expression gate",
      "app_id": -1
    }
  ]
}
```

`app_id: -1` matches any app reporting that context name (GitHub Actions included) — this repo does
not pin a specific app id here. After the PATCH lands, regenerate the snapshot
(`python3 scripts/ci/snapshot_required_contexts.py --branch main --out infra/required.d/contexts.json`)
in the same PR so the checked-in file and live protection never drift apart.

**Trap, measured 2026-08-27**: `--input <file>` reads `<file>` from the **filesystem of the machine
running `gh`**, not from wherever the JSON was drafted. Zero's first attempt at this PATCH from M5
failed with `unexpected end of JSON input` — the body file existed on Pro, not on M5, so `gh` read an
empty/nonexistent path and sent an empty body. Same class as cicatrix-superscar #1 (HOME-fork drift):
the payload has to be physically present on the machine issuing the command, `scp`/sync it over first
or write it fresh on that machine — do not assume a path is shared across the fleet just because the
repo is.

---

## 3. Whitelist: auto-merge eligible patterns

The workflow `.github/workflows/auto-merge-whitelist.yml` auto-enables
`gh pr merge --auto --squash` when ALL conditions hold:

1. **Branch name matches** one of:
   - `^docs/auto-sync-.*` (docs-sync.yml cron PRs)
   - `^dependabot/(pip|npm_and_yarn)/.*` (empirical dependabot branch shape)
   - `^chore/fmt-.*` (formatter cron — currently unused, reserved)
2. **Author is** `dependabot[bot]`, `github-actions[bot]`, or a designated bot.
3. **Diff does NOT touch** any path owned by @Balizero1987 in CODEOWNERS
   (workflows, fly.toml, migrations, auth, billing, pricing, launchagents).

If any check fails, the workflow exits silently; Antonello reviews manually.

**Anti-pattern guard**: the workflow itself is owned by @Balizero1987 in CODEOWNERS,
so a malicious PR cannot modify the whitelist to widen its scope.

This mechanism is orthogonal to queue activation: whether an armed PR merges directly (today) or
joins the queue first (post-flip), the whitelist still decides _who gets automerge armed at all_.

---

## 4. Path-restriction rulesets (CODEOWNERS — separate mechanism from the merge-queue ruleset)

Enforced via CODEOWNERS + branch protection `require_code_owner_reviews: true`. This is a
**different** GitHub mechanism from the `merge-queue-main` Ruleset in the status banner above — this
section is about _who must review a path_, not about _serializing merges_. Verify current live
config directly via `gh api repos/Bali-Zero/Teman2/branches/main/protection` if this needs
reconfirming. Critical paths:

| Path                                                                    | Owner                      | Why locked                            |
| ----------------------------------------------------------------------- | -------------------------- | ------------------------------------- |
| `/.github/workflows/`                                                   | @Balizero1987              | anti agentic-injection (CI silencing) |
| `/.github/dependabot.yml`                                               | @Balizero1987              | controls auto-PR cadence              |
| `/fly.toml`, `/apps/backend-rag/fly.toml`                               | @Balizero1987              | prod deploy config                    |
| `/apps/backend-rag/backend/db/migrations_v2/`                           | @Balizero1987              | irreversible schema changes           |
| `/apps/backend-rag/backend/app/auth/`                                   | @Balizero1987              | auth middleware + JWT                 |
| `/apps/backend-rag/backend/services/{invoicing,pricing,billing}/`       | @Balizero1987              | financial correctness                 |
| `/infra/launchagents/`                                                  | @Balizero1987              | cron / daemon config                  |
| Subhi lane `/apps/mouth/src/app/(blog\|marketing\|tax-calendar)/`, etc. | @SubBZ2026 + @Balizero1987 | co-review                             |

Full list: see `.github/CODEOWNERS`.

---

## Activation sequence (the order this must happen in — do not skip or reorder)

1. **Drain.** Confirm no PR is actively mid-merge-race against `main` (`gh pr list --search
"is:open"` review; the point is to flip enforcement at a quiet moment, not to reach literal zero
   open PRs — open PRs are fine, they will simply start entering the queue once armed).
2. **PR-B merged.** The sibling PR that makes all required-check workflows `merge_group`-ready
   (**26** as measured 2026-08-10 — re-derive via the §2 live query before citing, this count
   moves as CI grows) (they must fire correctly on the synthetic queue-branch event, not only on
   `pull_request`) must
   be on `main` _before_ enforcement flips. Flipping first would mean the queue immediately blocks
   on required checks that never report against a `merge_group` event — the exact "required check
   produces ZERO jobs blocks the PR forever" trap (cicatrix scar
   `discovery_required_check_zero_jobs_blocks_pr_forever_2026_07_25`), now at the whole-queue scale
   instead of one PR.
3. **Flip.** `scripts/ci/setup_merge_queue_ruleset.sh --enable`, at a quiet moment (per step 1) —
   this is a single whole-object PUT that sets `enforcement: active` and prints the effective rules
   before and after, so the flip is visible and auditable in the run's own output, not just trusted.
4. **Canary — three shapes, in order, on the live queue:**
   - **C1 — innocuous solo.** One trivial, low-risk PR (e.g. a docs-only change) armed with
     `gh pr merge --auto --squash`. Confirm it enters the queue, the synthetic check run fires and
     reports, and it merges. This is the "does the mechanism work at all" gate.
   - **C2 — injected failure.** A PR deliberately carrying a failing check (or a required check
     forced red) enters the queue. Confirm it gets **ejected**, `merge-queue-watch.yml`'s next poll
     (≤10 min) reports it as an EJECTED finding if it's still open, and no other queued PR is
     corrupted by the ejection. This is the "does the safety mechanism the queue exists for actually
     fire" gate — the entire point of §1's rationale, unverified until this step runs for real.
   - **C3 — two simultaneous entries.** Two independent PRs armed close together. Confirm the second
     one's required checks run against the _first one's_ result, not against stale `main` — this is
     the specific race from §1 made concrete and observed, not just argued.

     Note that this no longer looks like strict serialization. `max_entries_to_build` was **1** when
     this runbook was first written, so C3's expected shape was "positions 1 and 2, one building at a
     time". It is now **5** (raised 2026-07-27 after the queue sat at 6 waiting entries with nothing
     merged for 51 minutes — the serial setting caps the repo at roughly 3 PRs/hour). What you should
     see instead is up to five entries `AWAITING_CHECKS` **simultaneously**, each built speculatively
     on top of its predecessors. Speculation does not weaken the property C3 exists to verify: entry
     2 is still built on entry 1's merge result, and if entry 1 is ejected, entries built on it are
     rebuilt rather than merged. What changes is only how many are in flight while you watch.

5. **Gradual re-open.** Widen from canary-only PRs to the general `gh pr merge --auto --squash`
   population per the whitelist (§3) and manual arms alike. Watch `merge-queue-watch.yml` and
   `Main-push Failure Watch` (see below) closely through this window — they are the two automated
   eyes on a mechanism that has never run in this repo in anger before.

If any canary shape fails: **do not proceed to the next shape.** Roll back (see Rollback below),
diagnose with the failed run's own output plus `--status`, fix forward, and restart the canary
sequence from C1 — a partially-validated queue is not a validated queue.

---

## Session discipline

**`gh pr merge --auto --squash` remains THE standing gesture** for every eligible PR (per
`feedback_arm_automerge_default_not_leave_to_operator` — arm at PR-open, always). What it _means_
changes at the Activation flip: today it merges directly once checks are green; post-flip it means
**"add to the queue when green"** — the PR still merges automatically and unattended, just with one
extra safe stop (the synthetic re-check against current `main`) in between. This is a strictly safer
default, not a new manual step — nothing about the ship-lifecycle-ownership rule changes.

**Post-Activation correction (measured live, 2026-07-27, PR #3347):** once the queue governs `main`,
`gh pr merge --auto --squash` errors — `! The merge strategy for main is set by the merge queue` — and
arms nothing (`autoMergeRequest` stays unset). The `--squash` flag now conflicts with the ruleset's own
merge method (`MERGE`, not squash) instead of being redundant with it. The standing command is the bare
**`gh pr merge --auto`** (no `--squash`); the queue's own configured strategy decides how the commit
lands. Anyone still typing `--squash` from muscle memory gets a silent no-op, not an error worth missing
— always confirm with `gh pr view <N> --json autoMergeRequest,mergeStateStatus` after arming.

**Fork-PR exception — read before arming automerge on anything not from this repo's own branches.**
This is a **public** repository, and `merge_group` (like `pull_request_target`, unlike plain
`pull_request`) runs with repository secrets available to the check run. A fork PR that has not been
independently reviewed could carry a workflow-level exploit that only manifests once it's running
with secrets in hand. **Never arm `--auto` on a fork-originated PR without an independent review
first** — this is a documented threat boundary, not a hypothetical; treat it the same way
`ai-pr-review.yml` + CODEOWNERS already treat `.github/workflows/` changes, because the mechanism
that makes it dangerous is the same one (agentic/hostile CI tampering, arXiv 2605.07135, §1 above).

**Post-arm commits remain orphaned — unchanged lesson.** Per
`lesson_any_commit_after_arming_automerge_is_orphaned_2026_07_25`: once `--auto` is armed, a
subsequent push to the same branch does not get folded into the queued/merging attempt — everything
must be committed _before_ arming. The queue does not change this; if anything it raises the stakes,
since a PR can now sit queued (not just "green and about to merge") for longer before the orphan
becomes visible.

---

## After arming: watch, don't poll

Measured 2026-08-21: 54% of a PR-session's output tokens were spent AFTER `gh pr create` — hand-polling
CI — and 14% of all Bash calls were `gh pr checks/view/run`. **The rule: arm `gh pr merge --auto N`
(nude, per §Session discipline above), then hand it to `scripts/pr_watch.sh N` in a background task or
`Monitor`, and move on.** Never loop `gh pr checks` by hand waiting for green.

```bash
gh pr merge --auto 4321          # arm, nude
scripts/pr_watch.sh 4321         # background/Monitor — do the next thing meanwhile
```

It emits one line per event (`#N MERGED <ts>`, `#N CLOSED`, `#N REQUIRED-FAILING: <names>` once per
new failing set, `#N MISSING-REQUIRED: <contexts>`, `#N EJECTED-FROM-QUEUE`) and a final `ALL_DONE` /
`TIMEOUT`. Multiple PRs in one call are watched together; it exits only once every one of them is
terminal.

**Never read `autoMergeRequest` to decide "still armed" (W118)** — it reads null/false both while a
PR is healthily queued and after the queue has ejected it, indistinguishably (the same trap `mq
watch` avoids by tracking the armed SHA instead). `pr_watch.sh` uses GraphQL `isInMergeQueue` +
`mergeQueueEntry{state position}` instead, which is what makes `EJECTED-FROM-QUEUE` a real signal.

**`MISSING-REQUIRED` is the skipped-matrix-job scar** — `comm -23 <(required contexts) <(reported
names)` against the FULL reported-name set (not just required-flagged ones), because a skipped
matrix job's suffixed required context never shows up under any name at all (§2's "required check
never reported" class; scar `discovery_skipped_matrix_job_never_emits_its_required_contexts`).

**Re-running a check by hand never uses `gh run rerun` on a stale ref (W111)** — it replays the OLD
merge commit; `gh pr update-branch` first, or use `mq requeue` / `queue_rearm.sh --apply`. **One
scoped exception, measured 2026-08-21:** when the red is an external commit status on an UNCHANGED
head SHA (a Gear-3 gate verdict posted after the run finished) and the workflow checks out a pinned
base SHA rather than a merge ref, `gh run rerun` on the original `pull_request` run is the only
instrument that clears the rollup — see §6septies.

Test: `scripts/tests/test_pr_watch.sh` (fake `gh`, no network). `mq watch` is the post-arm drift
guard for one PR against its armed SHA; `pr_watch.sh` is the terminal-state watcher for one or many
PRs, replacing the hand-poll loop — neither reimplements the other.

---

## 5. Override procedure (owner admin)

When merge queue blocks a legitimate hotfix and CI infrastructure itself is broken:

```bash
# 1. Verify the PR is genuinely safe (read diff, run failing check locally).
gh pr view <N> --json files,statusCheckRollup

# 2. Admin merge (bypass merge queue + protected branch).
gh pr merge <N> --admin --squash --delete-branch
```

`--admin` requires admin permission on the repo. **Use sparingly**: every override
should be followed up with a fix to the broken check (open issue / PR).

Audit trail: every admin merge generates a `Merged via admin override` event in
the PR timeline, queryable via `gh api repos/Bali-Zero/Teman2/events`.

---

## 6. Procedure: PR stuck in merge queue

Symptom: PR shows "Queued for merge" but never advances after >15min — or, since 2026-07-27,
`merge-queue-watch.yml` pages an ARMED-STUCK or EJECTED finding directly (check that first; it polls
every 10 minutes and has already been proven against live data to catch exactly this class).

### Step 1 — Identify the failing check

```bash
gh pr view <N> --json statusCheckRollup --jq '.statusCheckRollup[] | select(.conclusion != "SUCCESS")'
```

If the rollup shows **fewer contexts than required** (§2 — **26** as measured 2026-08-10, run the
live query there, do not cite this number) and none of the missing ones are
red — they are simply absent — this is the "required check never reported" class, not a red check to
chase. `merge-queue-watch.yml` distinguishes this case explicitly in its alert text.

### Step 2 — Classify the red BEFORE touching it: INFRA or CODE

This is the step that decides everything after it, and getting it wrong in the cheap direction —
re-running until it passes — turns the queue into a machine that retries until green, i.e. a
disarmed gate that still looks armed (cicatrix superscar #2). **A code red gets fixed, never
retried.**

- **INFRA red** — the diff is not at fault. Retry is legitimate. Signature, measured live
  2026-07-27: `Tests & Coverage` failed inside `E2E Tests (Playwright)` during _Initialize
  containers_, before any step ran —
  `Get "https://registry-1.docker.io/v2/": context deadline exceeded`, three back-offs, all timing
  out. Every sibling job green. Grep the failing run's log for
  `registry-1.docker.io|Docker pull failed|context deadline exceeded|no space left on device|Runner has received a shutdown signal`.
  Frequency measured over 100 `merge_group` runs: **1**. Live fragility, not an epidemic.
- **CODE red** — anything else. Rebase on `main`, fix, push. Do not `gh run rerun`.
- **CANCELLED** — terminal and easy to misread as "still running". It is **not automatically an
  infra red**: a job killed by its own `timeout-minutes` also reports `cancelled`, and that is a
  SYSTEMATIC failure that retrying will reproduce forever. Separate the two before retrying —
  see §6ter, which is the shape that actually bit this repo on 2026-07-27/28.

`gh run rerun <run_id> --failed` is the right gesture in the INFRA case and in the
EXTERNAL-STATUS case (§6septies), and note the trap before using it: **`rerun` replays the OLD merge
commit**, so on a branch that has since fallen behind it re-tests a stale base — `gh pr
update-branch` first (`lesson_gh_run_rerun_replays_the_stale_merge_commit_2026_07_27`).

## 6bis. Queue parameters, and the one knob NOT to turn

Live values on ruleset `19779175`, read 2026-07-27 (re-read them, do not trust this list — the point
of writing them down is to have something to diff against):

| parameter                           | value      |
| ----------------------------------- | ---------- |
| `grouping_strategy`                 | `ALLGREEN` |
| `max_entries_to_build`              | 5          |
| `max_entries_to_merge`              | 4          |
| `min_entries_to_merge`              | 1          |
| `min_entries_to_merge_wait_minutes` | 2          |
| `check_response_timeout_minutes`    | 90         |
| `merge_method`                      | `SQUASH`   |

```bash
gh api /repos/Bali-Zero/Teman2/rulesets/19779175 \
  --jq '.rules[]|select(.type=="merge_queue")|.parameters'
```

### DO NOT flip `ALLGREEN` → `HEADGREEN`

It reads like a throughput knob and it is not. In GitHub's own words, `HEADGREEN` is the
**"Only merge non-failing pull requests" setting DISABLED**: _"pull requests that have failed
required checks can be added to a group as long as the last pull request in the group has passed
required checks."_ That does not reduce collateral — **it lets a pull request whose required checks
are RED into `main`.** `ALLGREEN` means _"all pull requests must satisfy required checks to be
merged"_, which is the whole reason the queue was worth enabling.

This was considered as a cure for the INFRA-ejection class above and **rejected on 2026-07-27** after
reading the documentation rather than reasoning from the API enum name. Recorded here because the
wrong inference is the natural one: a session that reasons "HEADGREEN sounds like a laxer _grouping_
rule, so it should reduce blast radius" arrives at weakening the merge gate. The real cure for that
class is upstream — make the E2E container pull robust, or stop letting a page-load smoke block
merges — plus the re-arm tool in §6 Step 2.

---

## 6ter. The clone can eat the whole job budget — and the kill reads as `cancelled`

This is what the queue was actually dying of on 2026-07-27, and it looked exactly like flakiness.

`fetch-depth: 0` on this repo downloads **2,289 MB**. On a slow runner that alone outlives the job:

| required gate                                 | `timeout-minutes` | time spent IN the checkout |
| --------------------------------------------- | ----------------- | -------------------------- |
| `R1 gate — adversarial review present`        | 5                 | 297 s of 300 s             |
| `P6 parallelize-hypothesis falsifiable gates` | 10                | 597 s of 600 s             |
| `Prove hooks bite only the guilty`            | 10                | 598 s of 600 s             |

Every step after the checkout reads `skipped`, the job is killed, the conclusion is **`cancelled`**,
and a `cancelled` REQUIRED check **ejects the entry** — leaving the PR `OPEN` + `MERGEABLE` with the
auto-merge request consumed and nothing to put it back (§6 Step 2b).

**Why it reads as flakiness and not as a systematic fault:** in a healthy parallel group the SAME
checkouts finish in 59–60 s. The failures are the tail of that distribution, 5–10× the ~61 s mean.
Nothing is "sometimes broken" — the budget is simply too close to the cost, so runner variance
decides. A retry that happens to land on a fast runner "fixes" it and teaches the wrong lesson.

**Cure — a partial clone.** `filter: blob:none` fetches all commits and trees and defers blobs until
something reads them: **23.3 MB in 21 s** instead of 2,289 MB. Keep `fetch-depth: 0`; the two are
independent (depth = how much history, filter = whether file contents come along).

```yaml
- uses: actions/checkout@v5
  with:
    fetch-depth: 0
    filter: blob:none
```

Measured after: 297 s → 26 s, 597 s → 23 s, and an entire `merge_group` where 11 gates checked out
in 23–28 s with zero cancellations.

Do not trust a count written here — counts rot. Ask the tree which workflows still pay full price:

```bash
comm -23 <(grep -rl 'fetch-depth: 0' .github/workflows/ | xargs -n1 basename | sort) \
         <(grep -rl 'filter: blob:none' .github/workflows/ | xargs -n1 basename | sort)
```

Anything that comes out of that command AND produces a **required** context is a live ejection
risk, not merely slow.

> **A green run does not prove the flag took effect.** An `actions/checkout` input that the action
> does not recognise is **silently ignored** — no warning, no failure, just a normal full clone. So
> never accept the check mark as evidence; the proof is the string `--filter=blob:none` in the
> _Fetching the repository_ log line of the run itself.

**When adding a new required workflow**: if it checks out with `fetch-depth: 0`, it must carry
`filter: blob:none`, or it arrives with a ~40× handicap against its own timeout on day one.

---

## 6quater. Dependabot: PRs that share a lock file must be armed ONE AT A TIME

Arming several Dependabot PRs together looks like throughput and produces the opposite. Group them
by the files they touch first:

```bash
for n in <numbers>; do
  echo -n "  #$n "; gh pr view $n --repo Bali-Zero/Teman2 --json files --jq '[.files[].path]|join(" ")'
done
```

On this repo they fall into two families that overlap totally inside and not at all across:

- **npm** — every PR touches the single hoisted root `package-lock.json`.
- **pip** — every PR touches `apps/backend-rag/requirements*.lock.txt`.

Two PRs from the same family cannot both be in flight: the first to merge makes the second
`CONFLICTING`, and if they are queued together the second is ejected. One from each family
concurrently is safe. Verified the hard way on 2026-07-27 — three armed at once, one came back
`UNMERGEABLE` over shared lock lines.

Two traps while measuring this:

- **`mergeable` has three values.** Right after any merge to `main` every open PR reads `UNKNOWN`
  while GitHub recomputes. Filtering `== "MERGEABLE"` at that moment reports a false-clean set;
  filtering `!= "CONFLICTING"` reports a false-dirty one. Wait for the value to leave `UNKNOWN`.
- **The PR body is truncated on large group PRs.** A group titled "32 updates" listed only 13
  `from X to Y` pairs, so a major-version scan over the body silently covered under half of them.
  Read the **diff**, not the narration.

---

## 6quinquies. Ledger PRs (`.claude/skills/modus/PENDING-ARMS.md`): `mergeable: false` is a lie

`.gitattributes` declares `.claude/skills/modus/PENDING-ARMS.md merge=union` — a built-in git driver
that resolves by keeping both sides' lines, exactly right for an append-only registry. **GitHub's
mergeability computation does not apply `.gitattributes` merge drivers**: it runs a plain three-way
merge and reports `mergeable: false` / `mergeStateStatus: DIRTY` on a PR that touches this file even
when both sides are perfectly union-mergeable. Measured on PR #3527 (same base `04b3eb38e`, same head
`aa7d97029`): GitHub said `dirty`, `git merge --no-commit` succeeded cleanly in **both** directions.

**The documented server-side fix does not work here either** — `gh pr update-branch` fails with
`"Cannot update PR branch due to conflicts"` on exactly this class of PR.

**A `dirty`/`false` reading on a ledger-touching PR is expected, not a real conflict.** The only path:

```bash
git -C <worktree> merge origin/main    # local merge, NOT gh pr update-branch
git -C <worktree> push
```

Two things NOT to do when you see this:

- Do not hunt for a conflict that does not exist — burns a cycle for nothing.
- Do not hand-edit the ledger to "resolve" it. That drops the other side's open rows — precisely the
  loss `merge=union` exists to prevent. Verify after any ledger merge that the open-row count did not
  drop: `python3 scripts/pending_arms_report.py --json` before and after, compare `counts.total`.

---

## 6sexies. `mq.sh` — the queue-ops wrapper (Merge-OS v2 Wave 0)

`scripts/mq.sh` wraps `scripts/queue_doctor.py` and `gh`; it never reimplements either. Spec:
`research/operations/2026-08-10-merge-os-v2-submission-system.md` §3/§4 Wave 0. State lives at
`~/.nuzantara-mq/armed/<PR>.json` (dir mode 0700), overridable via `MQ_STATE_DIR`/`MQ_REPO`.

| Verb                               | Does                                                                                                                                                                                                                            |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `mq status [--all\|PR...]`         | Wraps `queue_doctor.py` — the three-queue snapshot (§ merge queue, pre-push lock, P0 spool), verbatim output                                                                                                                    |
| `mq why-red <PR>`                  | Name/bucket/link of every non-passing **required** check, plus any required-by-branch-protection check `gh` never reported at all (the "required check never reported" class, §6 Step 1 above)                                  |
| `mq arm <PR>`                      | Records the current head SHA to the state file, then bare `gh pr merge <PR> --auto` — **never `--squash`**, which silently arms nothing once the queue governs `main` (§Session discipline above, PR #3347)                     |
| `mq watch <PR> [--timeout-mins N]` | The **post-arm watcher** — see below. Default ceiling 120 min, polls every 60s                                                                                                                                                  |
| `mq requeue <PR>`                  | `--disable-auto` then re-arm — the standing cure for a queue ejection (§6 Step 2b above)                                                                                                                                        |
| `mq dequeue <PR>`                  | `--disable-auto` and drop the local state file (does **not** remove an already-building queue entry — see the `--disable-auto` no-op trap at §Step 3b above; use the GraphQL `dequeuePullRequest` mutation there for that case) |
| `mq handoff`                       | `mq status` output + every armed-state file, paste-ready for a session handoff                                                                                                                                                  |

**The post-arm-watcher rule (spec §3, Codex F13):** "no push after arm" cannot be a preflight
guarantee — `mq arm` returns before any future push could happen, so it cannot see one. `mq watch`
is what enforces it: it records nothing itself, only reads the SHA `mq arm` already wrote, and on
every poll compares it against the PR's live head. A mismatch means someone pushed to an armed
branch (§Session discipline above: "post-arm commits remain orphaned") — `mq watch` dequeues
(`--disable-auto`) and alerts loudly rather than let a stale queued attempt merge. It exits `0` on
`MERGED`, `4` on `CLOSED`, `3` on a detected head-move (after dequeuing), `2` on reaching its
ceiling with no verdict (an honest NO-VERDICT, never a fabricated "clean").

Tests: `scripts/tests/test_mq_sh.sh` (fake `gh` on `PATH`, no network).

---

## 6septies. The red is an external commit status, not the code

A job that reads a commit status on the head SHA — the Gear-3 `harness/fable-gate` verdict is the
one in this repo — fails identically whether the verdict is REWORK or simply **not posted yet**.
Once the gate session posts it, the job has to run again, and the obvious gesture is the wrong one.

**Do not use `gh workflow run --ref`.** A `workflow_dispatch` run creates its check-run in a
DIFFERENT CHECK SUITE from the `pull_request` event's, and it does not enter the PR's
`statusCheckRollup` **at all** — it is an absent entry, not a superseded one. Measured on #4543:
the rollup holds exactly ONE `Harness floor recompute` entry and it points at the `pull_request`
run; the dispatch run appears nowhere in it. So the dispatch goes green while the PR stays BLOCKED.
This deadlocked #4543. (#4549 hit the same PENDING red but was cured by a rerun without ever taking the dispatch path — measured: 9 `pull_request` runs on its branch, **zero** `workflow_dispatch`. It is a second confirmation of the REMEDY, not of the deadlock.)

**Use `gh run rerun <the original pull_request run id>`.** Find it with:

```bash
gh run list --branch <branch> --workflow <file>.yml --json databaseId,event,headSha,conclusion
```

and take the row whose `event` is `pull_request` and whose `headSha` is the PR's current head. Same
SHA, same suite, verdict now posted — the rollup clears.

**Why this does not repeal W111.** W111's hazard is a run whose ref RESOLVES THROUGH A MOVING BASE;
its own incident was #3463 replayed against `refs/pull/3463/merge` — a pull-request merge ref, so
"reruns are only dangerous on merge_group" is false. The exception here is not "pull_request reruns
are safe"; it is that on the `pull_request` path _this_ workflow checks out
`github.event.pull_request.base.sha` — a PINNED SHA — and never `refs/pull/N/merge`, so there is no
moving ref for the rerun to resolve differently.

Read the expression **per branch**, not as a whole. In full it is
`github.event.merge_group.base_sha || github.event.pull_request.base.sha || 'main'`, and that third
branch IS a moving ref — it is the one `workflow_dispatch` falls through to. So the expression as a
whole is not "pinned"; only the branch a `pull_request` rerun takes is. **Before copying this to
another workflow, read that workflow's `ref:` — and read the branch YOUR event takes.**

And the honest limit: a rerun replays the ORIGINAL event payload, so the base checkout — and with
it the versions of the helper scripts the job executes — stays frozen at PR-event time. A rerun
will not pick up a base-side fix that landed on main since; only a new `pull_request` event will.
Pinning makes the staleness deterministic; it does not make the rerun current.

**Diagnostic trap.** While diagnosing, `gh pr checks` and `gh api …/check-runs` will appear to
contradict each other. The cause is **pagination**, not the filter: the endpoint returns 30 rows by
default and a PR head here carries ~55-63 check-runs. Measured on `76edf60e2` — no `per_page`:
`returned=30 failures=0`; `filter=all` with no `per_page`: **still** `returned=30 failures=0`;
`filter=all&per_page=100`: `returned=55 failures=1`. So `per_page=100` (or `--paginate`) is
mandatory; `filter=all` alone reports zero failures on a head that has one. `filter=all` does a
different job — it re-adds attempts superseded _within_ their own suite. Then compare
`check_suite.id`, which is the field that actually explains the disagreement.

**Do not classify by job name, and do not classify from a snapshot.** An empty `conclusion` is
_"not yet known"_, never _"no failure"_ — #3326 was read while `in_progress`/`conclusion=∅` and
filed as "ejected with ZERO failures"; at terminal state it was `failure`. Read the terminal state,
and if it is not terminal yet, come back.

Tooling, so the classification is not re-derived by hand each time:

```bash
scripts/ci/queue_rearm.sh              # dry-run: who is orphaned, and of which class
scripts/ci/queue_rearm.sh --apply      # re-arm ONLY the INFRA/CANCELLED class
```

The verdict logic is a separate pure function (`scripts/ci/queue_rearm_classify.sh`) with a
mutation-tested guilt+innocence corpus: unanimity (one non-infra failure forbids the retry even
among nine infra ones), no concluding from an unfinished run, and an empty probe result fails
closed rather than reading as clean.

### Step 2b — After an ejection, the auto-merge request is GONE

When a required check goes red the queue removes **that** pull request and recreates the temporary
branches for the remaining entries without it (GitHub's documented behaviour — groupmates are
_rebuilt_, not evicted; the collateral is wasted CI time). The ejected PR is left `OPEN` +
`MERGEABLE` + `CLEAN` with `autoMergeRequest: null`, and **nothing puts it back**. Re-arm it.

> **`autoMergeRequest: null` does not mean "not armed".** The queue _consumes_ the request when it
> accepts the PR, so a healthy queued PR reads `null` too. The probe is the COMMAND, not the field:
> `gh pr merge <N> --auto --squash` answering `already queued` means armed
> (`lesson_automergerequest_goes_null_when_the_queue_accepts_the_pr_2026_07_27`). Reading the field
> alone will have you "re-arming" PRs that are already in the queue, and calling the arm command as
> a _measurement_ enqueues them — the probe changes the world.

### Step 3 — Remove from queue if blocking other PRs

```bash
gh pr ready <N> --undo            # convert to draft → removed from queue
# fix → push → gh pr ready <N>    # re-queue when green
```

#### Step 3b — When you need to PUSH to a queued branch (measured 2026-08-05)

A queued branch is **protected**: every push is rejected with

```
remote: error: GH006: Protected branch update failed
remote: - A pull request for this branch has been added to a merge queue.
```

This is the shape that bites: an adversarial review lands _after_ the PR was
enqueued, finds a real defect, and the version already in the queue — the one
with the defect — merges while you are still typing the fix. Dequeue first,
push second, re-arm third.

**`gh pr merge <N> --disable-auto` does NOT dequeue.** It prints
`! Pull request ... is already queued to merge` and **exits 0** — a no-op that
reads like a success. Verified live: the entry stayed at `pos=1`.

The one that works:

```bash
PRID=$(gh pr view <N> --repo <owner/repo> --json id -q .id)
gh api graphql -f query='mutation($id:ID!){ dequeuePullRequest(input:{id:$id}){ clientMutationId } }' -f id="$PRID"
git push                                  # now accepted
gh pr merge <N> --auto --repo <owner/repo>  # re-arm
```

The input field is **`id`**, not `pullRequestId` — the obvious guess returns
`argumentNotAccepted`. Confirm with the queue itself, never with the exit code:

```bash
gh api graphql -f query='{ repository(owner:"<owner>", name:"<repo>") { mergeQueue(branch:"main") { entries(first:20){nodes{position state pullRequest{number}}} } } }' \
  --jq '.data.repository.mergeQueue.entries.nodes[] | "pos=\(.position) \(.state) #\(.pullRequest.number)"'
```

---

---

## 7. Rollback (disable the merge queue)

```bash
scripts/ci/setup_merge_queue_ruleset.sh --disable
```

One PUT, same canonical rule body, `enforcement: disabled`. Prints the effective rules before and
after so the rollback is verifiable from the command's own output.

**Honest consequence, state it to whoever asks "is it safe":** disabling re-opens today's pre-queue
window — the stale-base race from §1 is back until the queue is re-enabled. This is a deliberate
trade, not a free action: **use it only on a genuine queue malfunction** (the canary sequence catching
a real problem, or a live incident), then fix forward and re-run the Activation sequence from C1, not
from wherever it broke — a queue that failed a canary needs the _whole_ canary re-validated, not just
the shape that failed.

CODEOWNERS + branch-protection required-checks (§2, §4) remain active even with the queue disabled —
those are separate mechanisms, this rollback does not touch them.

---

## Main-push Failure Watch — keep it running through the trust-building window

`.github/workflows/main-push-failure-watch.yml` ("Main-push Failure Watch") already exists in this
repo as the generic watcher for any push-triggered or schedule-triggered workflow run on `main`
(task #23, superscar #2 "Esiste ≠ Armato"). It is not new, and this runbook does not modify it — it
is called out here because **it is the second half of the queue's proof of correctness**: the queue
re-validates a PR on a synthetic branch before merge, but the actual push to `main` that follows is a
_separate_ run, and only Main-push Failure Watch is watching that one.

**Keep both watchers — `merge-queue-watch.yml` and Main-push Failure Watch — running with no change
in posture for at least 30 days after the Activation flip.** Retire the elevated attention (not the
workflow itself, which stays permanently per its own charter) only after confirming **zero
divergence** between what the queue approved and what actually ran on `main` afterward — i.e., no
queue-approved SHA ever produced a Main-push Failure Watch alert in that window. A single divergence
resets the 30-day clock: it means the synthetic queue-branch check and the real `main` push are
observably not equivalent, which is precisely the trust question this window exists to answer.

---

## Known residual (documented, not solved here)

`merge-queue-watch.yml` polls every 10 minutes; it cannot alert on its own death (a dead `schedule`
trigger produces silence, not a failure signal — cf. cicatrix superscar #2, "esiste ≠ armato").
Liveness of the watcher itself is checked opportunistically: GitHub's own workflow-failure emails
(if the run itself throws before reaching Step 4), and a manual `--status` probe
(`scripts/ci/setup_merge_queue_ruleset.sh --status`, or `gh run list --workflow=merge-queue-watch.yml
--limit 5` to confirm recent runs exist at all). Building a watcher-for-the-watcher is out of scope
here — noted as a real gap, not quietly assumed away.

---

## Baseline organ (Wave 1)

Merge-OS v2 Wave 1 (`research/operations/2026-08-10-merge-os-v2-submission-system.md` §4 —
"the baseline organ (7 days, NO behavior change)"). This organ changes nothing about how PRs
are gated, run, or merged — it only _records_ what already happened, once per UTC day, so
Wave 2's "−X% billed/PR" acceptance criterion has a measured denominator instead of a guess
(spec §1: "savings claim ... unknown until the baseline organ runs").

**What it records**, into `~/.nuzantara-mq/baseline/YYYY-MM-DD.json` on Pro:

- billed minutes per PR (see allocation rule below)
- queue transit p50/p95 for PRs merged that day (auto-merge `enabledAt` → `mergedAt`, via
  GraphQL `autoMergeRequest.enabledAt`; a PR whose `enabledAt` cannot be read lands in
  `transit_unmeasured_prs`, never guessed)
- ejection count by class (INFRA/CODE — FLAKE stays 0 by construction until Wave 4's
  differential-flake verdict exists as ground truth) and by author class (human/agent/bot)
- slot utilization: the day's total runner-minutes against a fixed weekly-capacity constant
  (`≈97k slot-min/wk ≈ 48%` — round-3 system-wide measurement, 2026-08-09/10 window; a
  snapshot, not re-measured live by this organ)

Heal-drift frequency (also named in spec §4 Wave 1) is intentionally NOT recorded — it is a
property of the heal-as-PR mechanism (spec §2.2), which is Wave 3 and does not exist yet.

**Declared attribution rule** (spec §4, Codex CONFIRMED-DEFECT F6): GitHub's Actions
billing/usage endpoints report aggregate usage only, never a per-PR ledger. "Billed
minutes/PR" is computed as per-run billable minutes (`GET .../actions/runs/{id}/timing`)
summed over every run attached to a PR — its own `pull_request`-event runs plus any
`merge_group`-event run it was a member of. A `merge_group` run covering N member PRs
divides its minutes **evenly** across the N (the even-split option the spec declares
acceptable, as opposed to attributing the full amount to each). Membership is parsed
best-effort from the run's `head_branch`/`display_title`; when it cannot be derived, or a
`pull_request`-event run has an empty `pull_requests[]` (a known GitHub API gap for
fork-origin runs), the minutes are never dropped — they land in
`unattributed_group_minutes` / `unattributed_pr_minutes` respectively (scar family #2,
"esiste ≠ armato" — no silent caps).

For this public repository the timing endpoint's billable OS buckets are present but zero.
The organ therefore falls back to the same response's `run_duration_ms` and records the
choice under `timing_sources.run_duration`; this is effective runner consumption, not a
monetary charge. Private-repo non-zero billable buckets still win. A zero-billable response
without `run_duration_ms` is recorded explicitly as `billable_zero_without_duration` (the
normal shape for a skipped run), never inferred to carry hidden duration.

The runs census is independently fail-visible. The organ compares the unique run IDs fetched
across every `--paginate` page with GitHub's `total_count`. If GitHub stops at its server-side
cap, the record carries `run_collection.complete=false` plus a numeric shortfall in
`errors[]`; exactly 1,000 fetched runs can no longer masquerade as the whole day.

**Fail-visible by construction**: every `gh` API denial, timeout, or unparseable response is
appended to the record's `errors[]` array. A record is always written — even a total-failure
day — but `errors[]` non-empty makes the probe (and the wrapper that invokes it) exit
non-zero, so a failed night is never mistaken for a quiet one.

**Built, not armed** (scar family #2): `scripts/queue_baseline_probe.py` +
`infra/launchagents/wrappers/queue-baseline.sh` +
`infra/launchagents/com.nuzantara.queue-baseline.plist.template` land in this PR, but the
plist is a template, not installed. Installing it on Pro (`launchctl bootstrap`) and
verifying the first live receipt is a separate ALIGN-FLEET step tracked in
`.claude/skills/modus/PENDING-ARMS.md`. Wave 1's own acceptance criterion — 7 consecutive
daily records, each carrying billed/PR computed via the attribution rule above — cannot be
satisfied until that arming happens.
