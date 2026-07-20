# Merge Queue Discipline — Bali Zero / Nuzantara

> Owner: @Balizero1987 · Shipped: feat/merge-queue-rulesets-2026-05-24 · SOTA L3 wave.
>
> Sister doc: [`research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md`](../../research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md)
> Closes pattern: 17% PR rebase-manual (wave 2026-05-24 ex: #823, #815, #835-cherry, #805-cherry).

> **RETIRED 2026-07-17**: `scripts/setup_merge_queue_rulesets.sh` has been deleted — dead automation
> (0 GitHub Rulesets live on this repo, 0 consumers; GitHub Rulesets are not available on user-owned
> repos, so `--apply` could never durably succeed here). This runbook is kept for historical/conceptual
> reference (§1 rationale, the required-checks table, and the generic `gh pr` procedures still apply);
> every instruction below that names the script is dead — do not attempt to run it. The separate
> `scripts/merge_train.py` coordinator (polls classic branch protection every 180s) is UNRELATED and
> remains live — it was never gated by Rulesets and is untouched by this retirement.

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

---

## 2. Required status checks (enforced today)

Empirical snapshot of `GET /repos/Balizero1987/Teman2/branches/main/protection`
captured 2026-05-24 by `setup_merge_queue_rulesets.sh --dry-run`:

| Check name                         | Workflow file                    | Notes                        |
| ---------------------------------- | -------------------------------- | ---------------------------- |
| `E2E Tests (Playwright)`           | `.github/workflows/tests.yml`    | mouth Playwright suite       |
| `MCP Server Tests`                 | `.github/workflows/tests.yml`    | nuzantara-mcp + advanced     |
| `Frontend Tests (Next.js) (mouth)` | `.github/workflows/tests.yml`    | vitest + Lighthouse          |
| `Detect Secrets`                   | `.github/workflows/security.yml` | detect-secrets baseline diff |

All four MUST be green before merge queue accepts a PR.

`strict=false` today (allows merge if checks pass on the PR base, not on latest main).
**RETIRED**: the `--apply` script that would have flipped this to `strict=true` once merge queue
was enabled (closing the stale-base race documented above) has been removed — see banner at top.

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

---

## 4. Path-restriction rulesets

Enforced via CODEOWNERS + branch protection `require_code_owner_reviews: true`
(previously intended to be set by the now-**RETIRED** `--apply` script — see banner at top;
verify current live config directly via `gh api repos/Balizero1987/Teman2/branches/main/protection`
if this needs reconfirming). Critical paths:

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
the PR timeline, queryable via `gh api repos/.../events`.

---

## 6. Procedure: PR stuck in merge queue

Symptom: PR shows "Queued for merge" but never advances after >15min.

### Step 1 — Identify the failing check

```bash
gh pr view <N> --json statusCheckRollup --jq '.statusCheckRollup[] | select(.conclusion != "SUCCESS")'
```

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

## 7. Rollback (disable merge queue)

If merge queue causes more friction than it removes:

```bash
# Disable merge queue, keep CODEOWNERS + path-restriction in place.
gh api -X PATCH repos/Balizero1987/Teman2/branches/main/protection \
  --field 'required_status_checks[strict]=false' \
  ...  # RETIRED: setup_merge_queue_rulesets.sh --rollback no longer exists (script deleted);
       # construct the PUT payload manually per the branch-protection API docs if ever needed.
```

CODEOWNERS file remains active even with merge queue disabled (it's a separate
mechanism).

---

## 8. Smoke plan after `--apply` (RETIRED — script removed)

> The `--apply` script this section assumed is gone (see banner at top); 0 GitHub Rulesets are
> live on this repo today. Kept below for historical/conceptual reference only.

After enabling merge queue, the next 3 routine PRs become the smoke test:

1. **Docs-only PR** (cron `docs/auto-sync-*`): should auto-merge via whitelist
   workflow within 5min of all checks green.
2. **Dependabot patch PR**: same — should land via auto-merge.
3. **Manual feature PR touching `apps/backend-rag/backend/services/`** (non-billing):
   should require manual approval but merge once approved.

Failure mode to watch for: if **any** PR sits >30min "Queued for merge" with all
checks green, suspect a strict-mode race — check `gh pr checks <N>` for stale checks
against an older base SHA.

---

## 9. Owner sign-off checklist (RETIRED — script removed)

> `scripts/setup_merge_queue_rulesets.sh` has been deleted (see banner at top). This checklist is
> kept for historical/conceptual reference only — do not attempt the steps below.

Before running `bash scripts/setup_merge_queue_rulesets.sh --apply`:

- [ ] PR with CODEOWNERS + runbook + script + auto-merge workflow has been **reviewed** by Antonello.
- [ ] `gh api repos/Balizero1987/Teman2/branches/main/protection` snapshot saved
      to `research/operations/audits/2026-05-24-pre-merge-queue-protection.json` (for rollback).
- [ ] Next 24h is **not** a feature-freeze period (deploy window OK).
- [ ] Antonello is available for the 30min after `--apply` to handle any blocked PR.

After `--apply`:

- [ ] First docs-sync PR auto-merges (smoke 8.1).
- [ ] First dependabot PR auto-merges (smoke 8.2).
- [ ] Manual PR requires owner approval (smoke 8.3).
- [ ] No PR blocked >30min on "Queued" without ongoing investigation.

If any smoke fails: the rollback used to be `bash scripts/setup_merge_queue_rulesets.sh --rollback`
— **RETIRED**, script removed. Diagnose offline and roll back branch protection manually via the
`gh api -X PATCH .../protection` call in §7.
