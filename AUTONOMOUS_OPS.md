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

**Level 1 — active since 2026-04-21**
**Level 2 — target same-day activation once guardrails land (see §"Activation gates")**

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
- Browser QA after deploy (screenshot kita/my/prime/mail/calendar/drive/knowledge/zantara per `CLAUDE.md §10`)
- Local venv, pytest, npm, docker builds (no push)

### Requires confirmation
- `git push origin main` direct (bypassing PR) — branch protection blocks it anyway in L2
- `git push --force`, `git push --force-with-lease` (any branch)
- `git reset --hard` on a tracked branch that has already been pushed
- `fly ssh console` with DDL/DML that is not `ADD COLUMN IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` / `UPDATE ... WHERE <pk>`
- Any `DELETE / DROP / TRUNCATE / UPDATE without WHERE` on prod DB
- Adding a new Fly app, new cron (OpenClaw or GH Actions scheduled), new paid external provider
- Editing `fly.toml`, `.env.production`, top-level `package.json`, `alembic/env.py`, `zantara_core.py`
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

**Additional autonomous actions on top of L1:**

- `gh pr merge --auto --squash` immediately after opening a PR. GitHub holds the
  merge until CI is green; if CI stays red for >2h, Telegram alert fires.
- After merge to `main` triggers `fly-deploy.yml`: Claude polls deployment
  status, waits for `post-deploy-health` to complete, then runs browser QA on
  `kita.balizero.com` and the other 7 subdomains.
- If `post-deploy-health` auto-rollbacks (workflow already does this), Claude
  does not retry blindly — it investigates, reports, and asks before
  re-attempting.
- Telegram notifier posts to Zero's chat every time a deploy completes,
  successfully or not, with PR link + health check summary + rollback status.

**Still requires confirmation at L2:**
- Same list as L1 (force push, destructive DB ops, new apps/providers, critical
  config files, guardrail changes).
- Re-running a failed deploy after auto-rollback — Claude must diagnose first.

---

## Guardrails that make this safe

| Guardrail | Status | Notes |
|---|---|---|
| GitHub branch protection on `main`: require CI green + disable force push | **ACTIVATION GATE for L2** | `gh api` configured in task #5 |
| `fly-deploy.yml`: pre-deploy-gate → migrations → deploy → health → auto-rollback | ✅ Active (see `.github/workflows/fly-deploy.yml`) | Sibling job catches upstream crash (scar 2026-04-18) |
| `deploy-failure-alert` sends Telegram on any deploy failure | ✅ Active | Covers crash before health check |
| Daily `pg_dump` → Tigris | ✅ Active | `~/scripts/fly-pg-backup.sh`, retention 30d |
| Monthly restore drill | ⚠️ Manual, not yet automated | Ticket to add cron later |
| `PreToolUse` hook blocks edits to `fly.toml`, `.env.production`, `package.json` | ✅ Active in `~/.claude/settings.json` | |
| Hotfix audit log `shared/hotfix_audit.jsonl` + Telegram notifier | **ACTIVATION GATE for L2** | Task #8 |
| Post-deploy browser QA automated | **ACTIVATION GATE for L2** | Task #7 |
| MOS auto-save for decisions | ✅ Active | `~/.claude/scripts/mos-auto-save.sh` |
| Federation orchestrator + Consiglio v1 red-team on architectural changes | ✅ Implemented, triggered case-by-case | Not blocking gate yet |

---

## Activation gates

**To promote from L1 to L2, the following must all be true:**
- [x] `AUTONOMOUS_OPS.md` exists and is referenced in `CLAUDE.md §2`
- [ ] `git push`, `gh pr *`, `gh workflow *`, `gh run *` are in `allow` in `~/.claude/settings.json`
- [ ] GitHub branch protection on `main` blocks force push + requires CI green
- [ ] Hotfix audit log + Telegram notifier deployed
- [ ] Post-deploy browser QA script exists and is invoked after every merge

When all boxes are checked, this document's "active level" line is updated and
committed. Claude re-reads on next session start.

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

- **2026-04-21** — File created by Claude at Zero's request. Level 1 active
  immediately. Level 2 target: same day once activation gates close.
