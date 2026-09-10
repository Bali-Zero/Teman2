# S2 — CUSTODY

**One line:** The secrets audit never looks inside `~/nuzantara/.secrets` and has never run on a schedule. The restore drill has been red since 2026-09-01 because the workflow never creates the database role the dump needs, and its next automatic run is 2026-10-01.

**Wave 1 · Pro · runs in parallel with S1** (disjoint files). Built from two late reads: secrets-security and the restore drill from tests-deps-backup. Operator items: 4.

## Mandate prompt — paste everything below this line into a fresh `claude` session

SEAT AND CONTRACT
You are a Fable 5.1 session that Zero chose manually, running at max effort on Pro (`nuzantara@Nuzantara`, repo `~/nuzantara`). You own this mandate end to end: review → merge → arm → deploy → prove-live. The codeowner does not merge, review or deploy. Pin every subagent's model in the Agent call: `sonnet` for readers and implementers, `haiku` for grunt work, `opus` only for a final on-disk gate. An unpinned subagent inherits your model. Builder Contract: every PR gets its own worktree from `scripts/agent_start.py`, cut from a fresh origin/main. One PR, one concern, ≤~400 net lines. Every PR body carries a `Bites:` line naming the consumer and the observation that proves the change is live. Arm auto-merge when you open the PR; from then on the branch is frozen. Push, create and merge are three separate commands. Never rerun a red check until you know why it is red. Three reds for the same cause → suspend and write the spec. A fix-of-a-fix stops at depth 1. Reaching a Claude model through a paid per-token Anthropic endpoint is banned as an entity: use the `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN` only, and refuse any tool, MCP server or cron that needs `ANTHROPIC_API_KEY`, `from anthropic import Anthropic`, a renamed variable, a wrapper or a Bedrock/Vertex route. PII is an output boundary: no PR body, log, alert, memory, ledger row or report carries client PII or OSINT in cleartext. Off-limits files: `zantara_core.py`, `fly.toml`, `.env*`, `apps/bali-intel-scraper/backend/db/migrations/env.py`. Never edit Zero's own files: `~/.claude/CLAUDE.md`, branch protection, required-context lists. File operator items as a PENDING-ARMS row with the exact ask, and never wait on them.

MISSION
Make the two custody guards actually guard. The detector for scar family #4 must look where the secrets are and must run on a schedule. The backup restore drill must pass this week, not on 2026-10-01. Credentials and backups are the two things that can't be recovered if they go wrong.

GROUND (judge 13:03–13:06Z, red-team about an hour later, re-checked by the board editor at ~13:35Z; re-run all of it first)
- `stat -f '%Sp %N' ~/nuzantara/.secrets/*` → six files `-rw-------` and one `-r--------`; `stat -f '%Sp' ~/nuzantara/.secrets` → `drwx------`. The modes are correct right now because a late reader found them loosened and the orchestrator session that gated this program then ran chmod 600/400 (files) and 700 (directory) by hand at ~21:05 WITA on 2026-09-10. That is why 4 of the 7 inodes show `ctime` 2026-09-10T21:05:04 (`stat -f 'ctime=%Sc %N' -t '%Y-%m-%dT%H:%M:%S' ...`) while the other 3 show March/April ctimes. A manual, unarmed fix drifts again. Your job is the detector, its schedule and the drill, not the chmod.
- `dseditgroup -o checkmember -m zantara-codex staff` → `yes`. There is a second local account on this machine.
- `grep -n -A13 '_DEFAULT_ROOT_RELATIVE_PATHS' scripts/secrets_permissions_audit.py` → eleven roots (`~/.ssh`, `~/.claude`, `~/.claude-acct2`, `~/.kimi-code`, `~/.qwen`, `~/.openclaw`, `~/.config`, `~/.fly`, `~/scripts`, `~/Library/LaunchAgents`, `~/.nuzantara-cron`) plus a `~/.env*` glob. `~/nuzantara` is not among them, so the audit is blind to a directory literally named `.secrets`.
- Don't scan the whole tree: `python3 scripts/secrets_permissions_audit.py --no-default-roots --root ~/nuzantara --json` returned ~108.6 KB of hits across every `.worktrees/*` copy of `.env.example`, `.secrets.baseline`, and workflow files with "secret" or "token" in their names. Those are false positives, and a daily schedule over that root would cry wolf from day one.
- `crontab -l | grep -c secrets_permissions_audit` → 0; `grep -rl secrets_permissions_audit ~/Library/LaunchAgents/ | wc -l` → 0. It has never been scheduled.
- `gh run list -R Bali-Zero/Teman2 --workflow restore-drill.yml --limit 4 --json conclusion,createdAt,event,databaseId` → 2026-09-01 failure (run 33489946782, still the latest at 13:35Z), 2026-08-01 success, 2026-07-13 failure, 2026-07-01 success. The cron is monthly, so the next automatic attempt is 2026-10-01.
- The cause: `grep -c 'backend_rag_v2\|CREATE ROLE\|--no-owner' .github/workflows/restore-drill.yml` → 0. The service container provisions only `POSTGRES_USER: drill`, so the dump's `ALTER ... OWNER TO backend_rag_v2` aborts with `role "backend_rag_v2" does not exist`. psql exits 3 before the Level-5 verifier (`scripts/ci/restore_drill_verify.py`) runs. `git log -1 --format='%h %cd' --date=short -- .github/workflows/restore-drill.yml` → `55a05e9401 2026-08-29`.
- Secret scanning: alert #7 (`telegram_bot_token`, open since 2026-01-19) and alert #1 (`google_gcp_api_key_bound_service_account`, open since 2026-01-07). Query them only through a projection, `gh api "repos/Bali-Zero/Teman2/secret-scanning/alerts?state=open" --jq 'map({n:.number,t:.secret_type,c:.created_at})'`, because the raw API response contains the secret itself.
- The launchd canon is moving. PR #6101 ("one tree on Pro", still open at 13:35Z) repoints plists from `nuzantara-deploy` to `/Users/nuzantara/nuzantara`, and the healer's home-fork refresh copies repo canon over live edits. A new plist must be a canon file.
- Provenance: this evidence came from late reads done outside the wf1 sweep. wf1.json has no `secrets-security` modality, so don't go looking for one.

DISEASE
Scar family #4, with its own detector unarmed twice over: wrong scan roots and no schedule. On top of that, superscar #2 on the recovery guarantee: the one automated proof that backups can be restored has been red for over a week, and its alert landed in a channel already flooded with chronic HIGHs.

SCOPE IN
1. Add `~/nuzantara/.secrets` (the directory, NOT the whole `~/nuzantara` tree) to the default roots. Add a test that fails without it. Guilty case: a deliberately loosened file inside a scratch directory shaped like `.secrets` gets caught. Innocent cases: a 0600 file there is clean, and `.env.example` elsewhere in the tree is never flagged. Any wider root later needs an exclude list for `.worktrees/**`, `*.env.example` and `.secrets.baseline` first; that isn't part of this PR.
2. Schedule the audit as a LaunchAgent: a canon plist under `infra/launchagents/` whose ProgramArguments name `/Users/nuzantara/nuzantara/scripts/...`, never a `.worktrees/` path and never `nuzantara-deploy`. Use a plist rather than crontab: `crontab -l | crontab -` is a non-atomic read-modify-write on a 275-line table that other sessions also edit. Findings alert through the existing gateway (`scripts/tg_notify.py`) and never name a credential file, only the directory and a count. Kickstart it once and prove a real run today.
3. Fix `restore-drill.yml`: either create the `backend_rag_v2` role in the service container before the restore, or restore with `--no-owner` / strip the ALTER OWNER statements, whichever matches the file's own precedent. Then run it via `workflow_dispatch` in this session.
4. Prove the drill reaches and passes the Level-5 verifier. psql exiting 0 is not enough.
5. Make the drill's failures loud through the existing channel: a red drill appends one row to `shared/escalations_pro.jsonl` (the §14 bus). S4 builds the digest reader for that bus; don't create a second channel.

SCOPE OUT
Don't rotate any credential. Don't resolve the two secret-scanning alerts before Zero rotates the underlying tokens; resolving them first would hide a live key. Don't touch the `zantara-codex` account or its groups. Don't touch the duplicate Postgres backup crons (the 03:00 and 03:20 jobs write the same filename pattern into the same folder); file them instead. Don't touch memory.db or its backups (S5) or the internals of `scripts/tg_notify.py` (S4).

OPERATOR BOUNDARY
Four items, all filed, none blocking: rotating the Google service-account/combined-env credentials, the Telegram bot token and the GCP API key; retiring the second local account; ruling on whether that account ever read the `.secrets` credentials (that needs audit-log access, which only Zero has); the duplicate backup crons.

METHOD
First hour: run `python3 scripts/agent_start.py --help`, then create one worktree per PR, e.g. `python3 scripts/agent_start.py --lane infra --task-id custody-audit-roots` (branch `agent/nuzantara/infra/custody-audit-roots`; `sec` is not a known lane). Re-run every GROUND command. Read `scripts/secrets_permissions_audit.py` in full, especially `reachable_by` and the `--fix` path, and read `restore-drill.yml` in full. Find the abort line with `gh run view 33489946782 --log | grep -n -m5 'backend_rag_v2\|ERROR'`, and never paste restored rows. Check `gh pr view 6101 --json state` before writing the plist. Only then write.
Expect 3 PRs: audit roots + tests; audit schedule; drill role fix + escalation row.

BITES (each with its proving command)
- Bite 1. Consumer: the audit tool. `python3 scripts/secrets_permissions_audit.py --json` reports a finding inside the `.secrets` root while a scratch file is loosened, and comes back clean once it isn't. Paste both runs, redacted to directory and count.
- Bite 2. Consumer: launchd. `launchctl list | grep -i secrets` shows the loaded label, and the job's own log shows one completed run today started by launchd (`launchctl kickstart`), not by your shell.
- Bite 3. Consumer: GitHub Actions. `gh run list -R Bali-Zero/Teman2 --workflow restore-drill.yml --limit 2 --json conclusion,createdAt,event` shows a `workflow_dispatch` SUCCESS created today.
- Bite 4. Consumer: the Level-5 verifier. That run's log contains `restore_drill_verify.py`'s own pass output.
- Bite 5. Consumer: the escalation bus. A test proves a red drill appends exactly one row, with no data content.

RISK CONTROLS
Never `cat` a secret. Probe presence with `${VAR:+SET}` only, and never `printenv`. No credential filename goes into an alert, log or PR body; name the directory at most. Never commit anything from `.secrets/`. If the first scheduled run flags a loosened file or a `.bak` sibling, fix the live file AND the `.bak`, because a backup inherits the exposure. If you find evidence that another account actually read a credential, stop and escalate. PENDING-ARMS appends: use a branch cut from a fresh origin/main, check that `git diff origin/main -- .claude/skills/modus/PENDING-ARMS.md` is +N/-0, and never hand-resolve or rebase onto it.

STOP CONDITIONS
Stop and file a row if the drill fix needs new prod-adjacent secrets, if you get three reds for the same cause, if the drill passes psql but fails Level-5 for a DATA reason (that is a backup-integrity finding: escalate it, never paper over it), or if removing a backup cron starts to look necessary.
