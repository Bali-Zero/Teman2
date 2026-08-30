# AUTONOMOUS OPS CONTRACT

> **Claude MUST read this at every session start.** Referenced in `CLAUDE.md §2`.
> If an action appears under "autonomous" for the active Level, Claude proceeds
> **without asking the user**. If under "requires confirmation", Claude MUST ask
> in chat. If unlisted, default is "requires confirmation" (conservative).
>
> The user (Antonello / Zero) is not a developer and explicitly does not want
> to review code changes. His veto is NOT the safety layer — the guardrails
> below are. This contract exists because a pre-declared, version-controlled
> policy is safer than ad-hoc per-action prompts.

---

## Active level

**Level 2 — active since 2026-06-11**
(Level 1 was active earlier same day; promoted to L2 once all activation gates closed.)
(re-certified 2026-06-11 by Antonello after the Fable-5 system audit F04;
the SessionStart staleness hook was fixed the same day to read this declared
date — not the file mtime, which any edit silently reset, masking the lapse.)
(re-certified 2026-07-19 by Antonello — routine 30-day refresh; Level 2 unchanged.)

If today's date is >30 days after "active since" without a refresh commit,
Claude falls back to conservative mode and pings the user to re-certify.

---

## Level 1 — Autonomous from branch to PR, user veto on merge boundary

### Autonomous — Claude proceeds WITHOUT asking

- `git commit`, `git push`, `git push --set-upstream` (any branch except `main` directly)
- `gh pr create`, `gh pr comment`, `gh pr review`, `gh pr edit`
- `gh workflow run`, `gh run rerun`, `gh run watch`
- Read-only `fly logs`, `fly status`, `fly ssh console -C "<read-only cmd>"`
- Edit/Write on code, tests, migrations (SQL v2), docs, workflows under `.github/`
- Browser QA after deploy (screenshot kita/my/prime/mail/calendar/drive/knowledge/zantara per `CLAUDE.md §11` Deploy Lifecycle Post-deploy QA)
- Local venv, pytest, npm, docker builds (no push)

### Requires confirmation

- `git push origin main` direct (bypassing PR) — branch protection blocks it anyway in L2
- `git push --force`, `git push --force-with-lease` (any branch)
- `git reset --hard` on a tracked branch that has already been pushed
- `fly ssh console` with DDL/DML that is not `ADD COLUMN IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` / `UPDATE ... WHERE <pk>`
- Any `DELETE / DROP / TRUNCATE / UPDATE without WHERE` on prod DB
- Adding a new Fly app, new cron (OpenClaw or GH Actions scheduled), new paid external provider
- Editing `fly.toml`, `.env.production`, top-level `package.json`, `apps/bali-intel-scraper/backend/db/migrations/env.py` (corrected 2026-08-21 — `alembic/env.py` names no file here), `zantara_core.py`
  (already blocked structurally by the `PreToolUse` hook in `~/.claude/settings.json`)
- Merging a PR whose CI is red (branch protection blocks it anyway in L2)
- Disabling a guardrail hook or lowering branch protection

### End-of-action rules (mandatory after every autonomous action)

1. One-line result message to the user (what changed, where, link if applicable).
2. If the action wrote to prod state (deploy, DB, external API): verify live, report evidence.
3. If a new pattern/decision emerged: `mem save decision|discovery|fact ...`.
4. Never narrate intent without doing. No "I was about to...". Act, then summarize.

---

## Level 2 — Autonomous to deploy and post-deploy verification

> **No "I'll leave the merge to you at CI green".** Arming `--auto` IS the merge
> decision and it is autonomous at L2. Writing "I'll leave the merge to you" on a
> normal feature PR is being _more conservative than this contract_ — don't.
> `--auto` is the professional move precisely because it cannot force a red merge:
> GitHub holds the PR until required checks pass, so branch protection stays the
> safety layer above Claude. Confirmed by Antonello 2026-06-25. (Exception: the
> "Still requires confirmation" list below — guardrail/contract/critical-config
> changes, migrations without a green dry-run, force push, destructive DB ops —
> still merge by the operator.)

**Additional autonomous actions on top of L1:**

- `gh pr merge --auto --squash` immediately after opening a PR. GitHub holds
  the merge until required status checks are green (branch protection enforces
  this — Claude cannot merge a red PR even if it tries). If CI stays red for
  > 2h, Telegram alert fires.
- After merge to `main` triggers `fly-deploy.yml`: Claude invokes
  `scripts/post-deploy-verify.sh <PR_NUMBER>` which polls the workflow run,
  waits for `post-deploy-health` to complete, probes `/health` on
  `nuzantara-rag`, and posts the outcome to Zero's Telegram chat.
- Browser QA after green health: Claude opens `kita.balizero.com` and
  (if relevant to the PR scope) the other 7 subdomains, takes screenshots,
  checks console for errors, and saves a QA note to MOS.
- If `post-deploy-health` auto-rollbacks (workflow already does this), Claude
  does NOT retry blindly — it investigates, reports, and asks the user before
  re-attempting.
- Hotfix notifier: any `fly ssh console -C` with DDL/DML, `fly secrets set`,
  or `fly machines restart/destroy/stop` is auto-logged to
  `shared/hotfix_audit.jsonl` AND posted to Zero's Telegram in real-time,
  without asking for confirmation. The Telegram message IS the visibility
  layer that replaces the confirmation prompt.

**Still requires confirmation at L2:**

- Same list as L1 (force push, destructive DB ops _without_ WHERE clause,
  new Fly app/cron/external provider, critical config files, guardrail
  changes).
- Re-running a failed deploy after auto-rollback — Claude must diagnose first.

## Operational procedure — the L2 flow step-by-step

When Claude receives a non-trivial task that will ship to prod:

1. Work in a `git worktree` off `origin/main` (not in the user's working tree).
2. Commit locally with descriptive message.
3. `git push -u origin <branch>` — no confirmation.
4. `gh pr create` with summary + why + test plan — no confirmation.
5. `gh pr merge --auto --squash` — GitHub waits for CI green, then merges.
6. `bash scripts/post-deploy-verify.sh <PR_NUMBER>` in background. It polls
   `fly-deploy.yml`, probes `/health`, posts Telegram on completion.
7. When the post-deploy verify returns green, Claude runs browser QA for the
   relevant subdomains (per `CLAUDE.md §11` Deploy Lifecycle Post-deploy QA).
8. Claude saves a `decision` memory in MOS: what shipped, which PR, which
   fly-deploy run, health state.
9. One-line summary to the user with all the relevant links.

If any step fails: Claude stops, investigates, reports. Does NOT auto-rollback
or auto-retry. Zero's Telegram is already notified by the failure path.

---

## Schema-change discipline (DB) — frozen state during 2026-04 stabilisation

The migration runner is being consolidated. Until the strategy is fully
delivered, all agents — Claude included — must follow
these rules. They are **part of the autonomy contract**: violating them
counts as "modifying shared state without confirmation" and is out of
scope for L2.

> The strategy document this paragraph used to cite (a `2026-04-25` migrations
> review under `docs/reviews/`) has never existed in this repository and no file
> of that name exists anywhere in the tree. Retracted on 2026-08-31 rather than
> replaced: there is nothing to replace it with, and a plausible-looking
> substitute would be the same defect with a working link. The rules below stand
> on their own — they are the contract, not a summary of a document.

| Rule                                                                                                     | Why                                                                                                                                            |
| -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **No `SQLModel.metadata.create_all()` in prod or CI paths.** Test scratch fixtures only.                 | CI bootstraps schema differently from prod — `apps/backend-rag/scripts/ci_bootstrap_schema.py` exists as a workaround, not as a path forward.  |
| **All schema changes are SQL files in `apps/backend-rag/backend/db/migrations_v2/NNN_name.sql`.**        | Single source of truth. Forward DDL above the `-- === ROLLBACK ===` marker, rollback DDL below.                                                |
| **No new `apps/backend-rag/backend/migrations/apply_migration_NNN.py` without explicit human approval.** | Python migrations run _post-deploy_ in `fly-deploy.yml` and can leave the new image live but degraded. Convert to SQL or surface to Antonello. |
| **Do not rename or delete files in `migrations_v2/` once they have been applied to prod.**               | The runner tracks `migration_number` — renaming creates orphans; deleting silently corrupts state.                                             |
| **`PYTHONPATH=. python -m backend.db.migrate apply-all --dry-run` must pass before merge.**              | Catches syntax errors and ordering issues before they reach the deploy job.                                                                    |

**Recovery:** if a migration fails _before_ deploy, stop and fix the SQL
file. If a migration fails _after_ deploy (Python apply_migration_NNN
post-deploy job), roll back the app via `fly releases` and open an
incident — never apply a fix manually via `fly ssh` console without a
follow-up migration.

The legacy `_schema_versions` vs `schema_migrations` tracking-table
duplication is being unified in a follow-up PR. Until then, do not
write to either table directly outside the runner.

---

## Guardrails that make this safe

| Guardrail                                                                        | Status                                                       | Notes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GitHub branch protection on `main`: require CI green + disable force push        | ✅ Active (2026-04-21) · required set re-measured 2026-08-08 | **26** required contexts — including `Backend Tests (Python)` and `Frontend Tests (Next.js) (mouth, true)`, which this row wrongly described as absent until 2026-08-08. `enforce_admins=true`, `allow_force_pushes=false`, `strict=false`, no required reviewers. Required checks come **only** from classic branch protection; the `merge-queue-main` ruleset contributes `merge_queue` and nothing else. **This count is a MEASUREMENT and it expires — re-derive it, never quote it from here:** `gh api repos/Bali-Zero/Teman2/branches/main/protection/required_status_checks --jq '.contexts'`. Deliberately NOT required: the `Test Summary` umbrella, `Evaluator Critical Tests`, `Shared Core Package Tests`, `Frontend Tests (Next.js) (admin-dashboard, false)` — see L2.1 below. |
| `fly-deploy.yml`: pre-deploy-gate → migrations → deploy → health → auto-rollback | ✅ Active (see `.github/workflows/fly-deploy.yml`)           | Sibling job catches upstream crash (scar 2026-04-18)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `deploy-failure-alert` sends Telegram on any deploy failure                      | ✅ Active                                                    | Covers crash before health check                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| Daily `pg_dump` → Tigris                                                         | ✅ Active                                                    | `~/scripts/fly-pg-backup.sh`, retention 30d                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| Monthly restore drill                                                            | ⚠️ Manual, not yet automated                                 | Ticket to add cron later                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `PreToolUse` hook blocks edits to `fly.toml`, `.env.production`, `package.json`  | ✅ Active in `~/.claude/settings.json`                       |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| Hotfix audit log `shared/hotfix_audit.jsonl` + Telegram notifier                 | ✅ Active (2026-04-21)                                       | `~/.claude/scripts/hotfix-notify.sh` wired into `PostToolUse` Bash hook                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| Post-deploy health + Telegram notifier                                           | ✅ Active (2026-04-21)                                       | `scripts/post-deploy-verify.sh <PR_NUMBER>`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| Post-deploy browser QA (kita + 7 subdomains)                                     | ✅ Active (manual invocation by Claude)                      | Per `CLAUDE.md §11` Deploy Lifecycle. No dedicated script — Claude uses `mcp__claude-in-chrome__*` directly                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| MOS auto-save for decisions                                                      | ✅ Active                                                    | `~/.claude/scripts/mos-auto-save.sh`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| Federation orchestrator + Consiglio v1 red-team on architectural changes         | ✅ Implemented, triggered case-by-case                       | Not blocking gate yet                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |

---

## Activation gates

**To promote from L1 to L2, the following must all be true:**

- [x] `AUTONOMOUS_OPS.md` exists and is referenced in `CLAUDE.md §2`
- [x] `git push`, `gh pr *`, `gh workflow *`, `gh run *` are in `allow` in `~/.claude/settings.json`
- [x] GitHub branch protection on `main` blocks force push + requires CI green (2 required checks active **as of 2026-04-21**: "E2E Tests (Playwright)", "MCP Server Tests" — the set has grown to 26 since; this line is the historical gate record, the Guardrails row above is the current state)
- [x] Hotfix audit log + Telegram notifier deployed
- [x] Post-deploy verify script + browser QA pattern documented

All gates closed 2026-04-21. L2 active.

### Next evolution — L2.1 (audited 2026-08-08)

- [x] Fix pre-existing main red: Backend Tests (Python) + Frontend Tests (Next.js) (mouth)
      — the **April-baseline** red is gone: 7 consecutive completed `tests.yml` runs on `main`
      (push + schedule) had both suites `success` — runs `31191329103`, `31191947694`,
      `31193920821`, `31199357765`, `31200063796`, `31201042279`, `31203107670`. It was cured
      **before** this audit, not by it; which change cured it was not established here.
      **Caveat, and it is the point:** `main` went red again _during_ this audit —
      run `31211274124` (19:23Z), `Backend Tests (Python)`, failing step `pip-audit`,
      `pypdf 6.14.2` / CVE-2026-71852. That is a **different, external** red: the same
      `headSha b81c7b0` passed at 18:40Z and failed at 19:18Z with no code change between,
      because the failing input is a live vulnerability-advisory lookup, not the diff. Fix in
      flight as PR #3780 (`pypdf` → 6.15.0). Read the run-ID list above as a measurement with
      a timestamp, never as a standing property of `main`.
- [x] Promote both to required status checks on `main`
      — **found already required**, not performed by this audit. Both context strings match the
      job names `tests.yml` actually emits (`backend-tests` → `Backend Tests (Python)`;
      `frontend-tests` is a matrix, so its leg reports as `Frontend Tests (Next.js) (mouth, true)`),
      and both are reported on the `merge_group` ref too — `tests.yml` carries a `merge_group:`
      trigger, so a required context cannot silently go unreported inside the queue.
- [ ] Automated monthly pg_dump restore drill — **still open**, untouched by this audit.

**Residual gap (operator decision, not yet taken).** Three suites `tests.yml` runs are still
outside the required set: `Evaluator Critical Tests`, `Shared Core Package Tests`, and the
`Frontend Tests (Next.js) (admin-dashboard, false)` matrix leg. A PR can regress any of them and
still auto-merge. One context closes all three: `Test Summary`, which `needs:` all six suites,
runs `if: always()`, reads the real `needs.*.result` values and calls `core.setFailed` when any
is `failure`/`cancelled` (a `skipped` job counts as satisfied, so it cannot deadlock a
path-filtered PR). It was made honest on 2026-07-20 and is deliberately still not required.

**Open question this audit did NOT settle — enforcement, as distinct from configuration.** The
PENDING-ARMS line opened 2026-07-27 (PR #3227 merged with required checks not green) is still
open. Two of its three candidate causes are now excluded — no ruleset supersedes the contexts,
and no configured context string fails to match an emitted check-run name — leaving
auto-merge-against-a-superseded-head. Note also that its own prescribed proof ("re-run the
measurement on the next merged SHA") is **not a sound probe under a merge queue**: the gate is
evaluated on the queue ref, while the merge commit accumulates _post-merge_ push-triggered runs,
which the 13 non-`tests.yml` required workflows cancel on the next push by design
(`cancel-in-progress: ${{ github.event_name != 'merge_group' }}` is `true` for a push to `main`).
Measured 2026-08-08 on four recent merges: two read 0/26 not-green, two read 3/26, and the
difference tracks _when the sample was taken_, not gate behaviour. Only an adversarial canary
decides this.

---

## How Claude discovers this document

1. `CLAUDE.md §2` (Behavior Rules) contains a pointer.
2. `~/.claude/projects/-Users-nuzantara/memory/MEMORY.md` has a one-line index
   entry linking to `reference_autonomous_ops.md`.
3. `~/.claude/settings.json` `SessionStart` hook runs
   `head -80 AUTONOMOUS_OPS.md` so every new session prints the active level.
4. If this file is missing or the "active since" date is stale (>30 days) and
   there has been no refresh commit, Claude falls back to conservative mode and
   asks the user to re-certify.

---

## Change log

- **2026-08-08** — L2.1 audited. **Nothing was promoted: both targets were found already
  required**, and the Guardrails row claiming otherwise had been wrong for an unknown
  stretch — this file, not the configuration, was the stale artifact. Corrected here: 26
  required contexts, `Backend Tests (Python)` and `Frontend Tests (Next.js) (mouth, true)`
  among them, both also reported on the `merge_group` ref.
  **Enforcement was proven adversarially**, not assumed: canary PR #3781 (one test file,
  closed and branch-deleted after the observation) was armed for auto-merge _after_ a
  required context had already gone red, and GitHub held it — `state: OPEN`,
  `mergedAt: null`, `mergeStateStatus: BLOCKED`, sustained across repeated sampling.
  Two limits stated plainly: the red came from `pip-audit`, not from the canary
  assertion, so the canary's own mechanism never ran; and this tests the steady state,
  **not** the race that the 2026-07-27 PENDING-ARMS line recorded (#3227's checks
  cancelled two seconds before its merge) — that line stays open. Settled in passing:
  all 26 required contexts reported on a single-test-file PR, so none sits mute behind a
  `paths:` filter. Method note worth keeping: the probe that line prescribes (re-measure
  required contexts on the next merged SHA) is **not sound under a merge queue** — the
  merge commit accumulates post-merge runs that most required workflows cancel by design;
  two of four sampled merges read "3 not green" purely as a function of when the sample
  was taken. Still open and NOT closed by this audit: the monthly restore drill, the three
  unrequired suites (see L2.1 above), and enforcement-under-race.
- **2026-07-19** — Re-certified by Antonello (routine 30-day refresh after the
  2026-06-11 certification lapsed). Level 2 unchanged.
- **2026-04-21** — File created by Claude at Zero's request. Level 1 active
  immediately. Level 2 promoted same day once activation gates closed:
  branch protection live on `main`, hotfix Telegram notifier live,
  post-deploy verify script live, `gh pr merge --auto --squash` wired into
  default flow.
