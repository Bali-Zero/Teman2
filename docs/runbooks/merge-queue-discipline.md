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
| Enforcement                                                  | `disabled` (queue is configured, not yet gating merges)                                                                                                                                                                                                                                                 |
| Rule                                                         | single `merge_queue` rule — see canonical body in `scripts/ci/setup_merge_queue_ruleset.sh`                                                                                                                                                                                                             |
| Required status checks on `main` (classic branch protection) | **25** contexts, `strict: false`                                                                                                                                                                                                                                                                        |
| IaC                                                          | `scripts/ci/setup_merge_queue_ruleset.sh --status\|--enable\|--disable\|--apply`                                                                                                                                                                                                                        |
| Watcher                                                      | `.github/workflows/merge-queue-watch.yml` — polls every 10 min for ejections + armed-but-stuck PRs (GraphQL; `merge_group`'s Actions trigger does not deliver the `destroyed` action, so event-based ejection detection does not exist — verified against GitHub's own Actions-trigger docs 2026-07-27) |

The ruleset existing with `enforcement: disabled` is intentional, not an oversight: the rule content
is live and reviewable _before_ it starts gating anything. Flipping it on is the **Activation**
section below — a deliberate, sequenced act, never a side effect of running `--apply`.

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
type expands beyond `merge_queue`): **25 contexts**, `strict: false` (merge is allowed once checks
pass on the PR's own base, not necessarily on the very latest `main` — this is exactly the race the
merge queue exists to close once enforcement flips to `active`).

This list is long and changes as CI grows; do not hand-copy it into this doc — it goes stale
immediately and the live query above is the source of truth. The 2026-07-26 PR-latency report's
measured "25 required status contexts on main" corroborates the count as of this writing.

`strict=false` today means a PR can merge against a base that is no longer `main`'s tip. **This is
the specific race the queue closes** — not a separate future improvement, the headline reason for
§STATUS above.

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
2. **PR-B merged.** The sibling PR that makes all 25 required-check workflows `merge_group`-ready
   (they must fire correctly on the synthetic queue-branch event, not only on `pull_request`) must
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

If the rollup shows **fewer contexts than the 25 required** (§2) and none of the missing ones are
red — they are simply absent — this is the "required check never reported" class, not a red check to
chase. `merge-queue-watch.yml` distinguishes this case explicitly in its alert text.

### Step 2 — Re-run vs investigate

- **Flaky test** (e.g., Playwright timeout): `gh run rerun <run_id> --failed`
- **Real regression**: rebase against latest `main`, push fix
- **CI infrastructure** (runner outage): wait or trigger admin merge per §5

### Step 3 — Remove from queue if blocking other PRs

```bash
gh pr ready <N> --undo            # convert to draft → removed from queue
# fix → push → gh pr ready <N>    # re-queue when green
```

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
