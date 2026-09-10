# S5 — A BRAIN THAT CAN FORGET

**One line:** `ttl_days` and `superseded_by` are set on 0 of ~15,800 memories, so the nightly TTL sweep deletes nothing and reports success, while ~1,450 `osint_sensitive` rows ride every nightly backup in cleartext.

**Wave 3 · Pro only · launch ONLY after Zero answers queue item 1 (retention), and never in parallel with S4.** Built from C3. Operator items: 3.

## Mandate prompt — paste everything below this line into a fresh `claude` session

SEAT AND CONTRACT
You are a Fable 5.1 session that Zero chose manually, running at max effort on Pro (`nuzantara@Nuzantara`, repo `~/nuzantara`). You own this mandate end to end: review → merge → arm → deploy → prove-live. The codeowner does not merge, review or deploy. Pin every subagent's model in the Agent call: `sonnet` for readers and implementers, `haiku` for grunt work, `opus` only for a final on-disk gate. An unpinned subagent inherits your model. Builder Contract: every PR gets its own worktree from `scripts/agent_start.py`, cut from a fresh origin/main. One PR, one concern, ≤~400 net lines. Every PR body carries a `Bites:` line naming the consumer and the observation that proves the change is live. Arm auto-merge when you open the PR; from then on the branch is frozen. Push, create and merge are three separate commands. Never rerun a red check until you know why it is red. Three reds for the same cause → suspend and write the spec. A fix-of-a-fix stops at depth 1. Reaching a Claude model through a paid per-token Anthropic endpoint is banned as an entity: use the `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN` only, and refuse any tool, MCP server or cron that needs `ANTHROPIC_API_KEY`, `from anthropic import Anthropic`, a renamed variable, a wrapper or a Bedrock/Vertex route. PII is an output boundary: no PR body, log, alert, memory, ledger row or report carries client PII or OSINT in cleartext. Off-limits files: `zantara_core.py`, `fly.toml`, `.env*`, `apps/bali-intel-scraper/backend/db/migrations/env.py`. Never edit Zero's own files: `~/.claude/CLAUDE.md`, branch protection, required-context lists. File operator items as a PENDING-ARMS row with the exact ask, and never wait on them.

MISSION
Wire the memory organ's reap path so it can actually forget, under the retention windows Zero has ruled, and stop copying OSINT-flagged rows into every nightly backup. Part of this work has NO pull-request path. Say so plainly rather than pretending it went through review.

THE RULING (paste Zero's answer here before you start; if it's empty, do the repo half only and stop before any DELETE)
Default recommended to Zero: processed raw_observations older than 30 days are purgeable; osint_sensitive rows older than 7 days are purgeable; unresolved memories older than 90 days are archived, not deleted.
Zero's answer: ______

GROUND (judge 13:05Z, red-team about an hour later, re-checked by the board editor at ~13:35Z; the tables grow hourly, so re-read every number)
- `sqlite3 ~/.claude/memory.db` counting memories, ttl-set, superseded, raw_observations, processed and `osint_sensitive=1` → `15842|0|0|313956|306884|1452` at 13:05Z (memories were at 15,846 an hour later).
- The C2.15 cron (`crontab -l | grep -A1 'C2.15'`) runs `DELETE FROM memories WHERE ttl_days IS NOT NULL AND julianday("now")-julianday(created_at) > ttl_days` daily at 05:00 UTC. It matches zero rows, and its wrapper reports `{"status":"ok","exit_code":0}`: a permanent no-op that reports green.
- `grep -n 'ttl_days\|INSERT INTO memories' ~/.claude/scripts/mem` → the save path inserts only `(session_id, type, content, importance)`.
- `MEMORY_INDEX.md` is 444,400 B, 17.8× its 24,985 B cap. Corrections to carry forward: the sessions↔memories key space is 100% disjoint, and backups are ~19–20 rolling under an existing prune cron.
- Existing guards: `scripts/memory/mos_recall_sessionstart.py` (tracked) prints `⚠️ MEMORY.md {bytes}B > 2560B`. It warns and never blocks, so extend it. `scripts/harness/harness_lifecycle_guard.py` also exists, but it is registered in 0 of 4 settings.json files, watches MEMORY.md instead of MEMORY_INDEX.md, and hardcodes a `-Users-balizero-Desktop-nuzantara` path that doesn't exist on Pro. The machine-local `~/.claude/scripts/alzheimer-hook.sh` alerts at 25,600; 2,560 vs 25,600 is Zero's call.
- The live writer. `lsof ~/.claude/memory.db` shows it held open by `com.balizero.mos-plus.compression`. `launchctl print gui/501/com.balizero.mos-plus.compression` shows it runs `/Users/nuzantara/scripts/mos-plus-compression-worker.py`, a HOME copy, not the repo file. `infra/home-fork/declared-pairs.json` declares that pair with `machines: []` and a note: widen it to `["pro"]` only once the fixed file has actually been copied onto Pro and re-verified sha256-identical.
- No PR path: `git -C ~/.claude remote -v` → empty, and `~/.claude/scripts/mem` isn't in the Nuzantara repo.

DISEASE
Superscar #2 on the organism's own memory. MOS was designed to prune itself, the pruning was never wired, and the nightly sweep has deleted nothing since it was created while reporting success each night. Downstream, that becomes an output-boundary exposure under UU PDP and SYMBIOSIS Law 2: every nightly backup copies the osint_sensitive rows in cleartext.

SCOPE IN — split by path, and be honest about which is which
A) REPO-SHIPPABLE (PR → review → arm → merge → prove-live):
1. Fix the reaper and ttl logic in `scripts/mos-plus-compression-worker.py`. After merge, make the daemon run the merged file: find its path with `launchctl print`, compare the live HOME copy against the merged repo copy with `shasum -a 256`, `cp` over it if they differ, and re-run `python3 scripts/lint_home_fork.py --check`. Only once the hashes match, widen the declared pair to `["pro"]` in a follow-up PR, as its own note says. Merging on its own changes nothing the daemon runs.
2. A MEMORY_INDEX cap check that can actually fire: extend `mos_recall_sessionstart.py`, or fix and register `harness_lifecycle_guard.py` with a path derived at runtime. The SessionStart wiring lives in the machine-local `~/.claude/settings.json`, so changing it counts as direct administration (Pro only).
3. Make doc and code agree on the MEMORY.md cap once Zero has ruled which number is authoritative.
B) DIRECT ADMINISTRATION (no PR path; label it that way in your report):
4. A dated backup first: `sqlite3 ~/.claude/memory.db ".backup '<dated path outside any repo or synced folder>'"`. Use the online backup API, because a plain `cp` of a database with a live writer can capture a torn copy. Then `PRAGMA integrity_check` must return `ok` and the row counts must match. `chmod 600` the backup, since it holds the same OSINT, and record when it will itself be deleted under the same ruling.
5. Pause the compression daemon, purge the classes Zero ruled purgeable by PREDICATE, VACUUM, then restart the daemon and prove it runs again.
6. ttl in two gated halves. 6a is safe and forward-only: the `mem` save path sets ttl_days by type for new rows. 6b is the trap: backfilling ttl_days on existing rows schedules deletes, because C2.15 DELETEs every row whose ttl has expired that same night, with no gate. So no backfill on any class Zero ruled "archive" (unresolved memories) unless the reaper first archives that class instead of deleting it. Before backfilling live, dry-run the cron's exact predicate against the backup and paste the counts it WOULD delete.
7. The next backup stops carrying osint_sensitive rows older than the ruled window. Existing backups age out under the current prune cron; don't rewrite or delete them.

SCOPE OUT
Any DELETE before the ruling block is filled in. M5's and Mini's settings.json (Pro only; file the rest). Dead-hook pruning (S4). PENDING-ARMS, the escalation bus, proprioception, queue_shepherd. Printing payload_json or any row content, ever.

OPERATOR BOUNDARY
Three items, filed in the first minute; the repo half never waits on them: the retention ruling (it gates B and should already be answered at launch); which MEMORY.md cap is authoritative (gates item 3); whether `~/.claude` gets a git remote so this half can ever go through review.

METHOD
First hour: run `python3 scripts/agent_start.py --help`, then `python3 scripts/agent_start.py --lane db --task-id memory-lifecycle` (branch `agent/nuzantara/db/memory-lifecycle`; `mos` is not a known lane). Re-run GROUND and identify the live writer. Take and verify the backup BEFORE anything else. Then the repo PRs, then the direct half: every purge runs first as a dry-run count, then as the real predicate. Prove cron behaviour now by invoking the exact C2.15 command by hand, never by waiting for the next nightly run. Expect 2–3 repo PRs plus a labelled direct-administration section in your report.

BITES (each with its proving command)
- Bite 1. Consumer: the C2.15 cron. Its exact command, run by hand after the ruling, reports a NON-ZERO count on a class ruled purgeable, which is impossible today. Paste before and after.
- Bite 2. Consumer: the save path. Run `mem save fact "probe" 7`, then `sqlite3 ~/.claude/memory.db "select count(*) from memories where ttl_days is not null;"` → non-zero.
- Bite 3. Consumer: the database. `ls -la ~/.claude/memory.db` after purge + VACUUM, next to the pre-purge size.
- Bite 4. Consumer: the next backup. `sqlite3 <newest-backup> "select count(*) from raw_observations where osint_sensitive=1;"` counts only rows inside the ruled window, next to the same query on an older backup. Counts only.
- Bite 5. Consumer: the guard. Overshoot the cap in a scratch copy and the guard fires; under the cap it stays silent.
- Bite 6. Consumer: the daemon. After the surgery it is running, its log shows a tick newer than your VACUUM, and the file it runs is sha256-identical to the merged repo copy.

RISK CONTROLS
This is irreversible data surgery with no reviewer, so your own SQL is the only check. Delete by predicate, never by inspection: you never read rows to decide what goes. The PII output boundary is hard: osint_sensitive rows may be counted, hashed, deleted or quarantined, but never printed or pasted into a PR body, log, memory or report, and payload_json is never printed. Never VACUUM against the live writer. Never `git checkout --` over an uncommitted fix; back it up with `cp` first.

STOP CONDITIONS
Stop and escalate if the ruling block is still empty when you reach a DELETE (do the repo half and stop), if the backup fails `integrity_check` or its counts don't match, if the compression daemon can't be paused and restarted safely, if you get three reds for the same cause, or if you find osint_sensitive content already transcribed into a repo file (report where it is, never what it says).
