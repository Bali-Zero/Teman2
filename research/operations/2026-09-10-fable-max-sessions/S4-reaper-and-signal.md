# S4 — THE REAPER AND THE SIGNAL

**One line:** The ledger doubled to 802 rows in 29 days with no way to close rows, 20 of the 21 HIGH escalations ever written come from one chronic job, and a persisting P0 went quiet for up to a week behind the alert gateway's mute ladder while its sentinel reported `ok`.

**Wave 2 · Pro, plus one hand edit on Mini · runs in parallel with S3.** Built from C2, C8 and what survived of L1. Operator items: 5.

## Mandate prompt — paste everything below this line into a fresh `claude` session

SEAT AND CONTRACT
You are a Fable 5.1 session that Zero chose manually, running at max effort on Pro (`nuzantara@Nuzantara`, repo `~/nuzantara`). You own this mandate end to end: review → merge → arm → deploy → prove-live. The codeowner does not merge, review or deploy. Pin every subagent's model in the Agent call: `sonnet` for readers and implementers, `haiku` for grunt work, `opus` only for a final on-disk gate. An unpinned subagent inherits your model. Builder Contract: every PR gets its own worktree from `scripts/agent_start.py`, cut from a fresh origin/main. One PR, one concern, ≤~400 net lines. Every PR body carries a `Bites:` line naming the consumer and the observation that proves the change is live. Arm auto-merge when you open the PR; from then on the branch is frozen. Push, create and merge are three separate commands. Never rerun a red check until you know why it is red. Three reds for the same cause → suspend and write the spec. A fix-of-a-fix stops at depth 1. Reaching a Claude model through a paid per-token Anthropic endpoint is banned as an entity: use the `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN` only, and refuse any tool, MCP server or cron that needs `ANTHROPIC_API_KEY`, `from anthropic import Anthropic`, a renamed variable, a wrapper or a Bedrock/Vertex route. PII is an output boundary: no PR body, log, alert, memory, ledger row or report carries client PII or OSINT in cleartext. Off-limits files: `zantara_core.py`, `fly.toml`, `.env*`, `apps/bali-intel-scraper/backend/db/migrations/env.py`. Never edit Zero's own files: `~/.claude/CLAUDE.md`, branch protection, required-context lists. File operator items as a PENDING-ARMS row with the exact ask, and never wait on them.

MISSION
Give the ledger and the escalation bus a way to close rows. Make the signal honest: a persisting P0 never goes silent, and a sentinel never reports ok while its condition is dead.

GROUND (judge 13:02–13:07Z, red-team about an hour later, re-checked by the board editor at ~13:35Z; re-run all of it)
The signal:
- The WhatsApp bot line is quiet on purpose; the orchestrator verified this on prod. #5486 and #5494 (merged 2026-09-01, on Zero's ruling) moved every client-facing invitation from `SUPPORT_WHATSAPP` (the bot's Meta line) to `CLIENT_CONTACT_WHATSAPP` (the human line). Inbound fell to zero from 09-03, and the Fly endpoint is alive. This is the ruling working, not an outage.
- The sentinel classifies correctly: `dead_channel` ignores business hours by design and maps to p0, and 49 tests pass on origin/main. But every tick ends with `_heartbeat("ok", note=...)`, a hardcoded status. At 13:21Z it read `"status": "ok"`, note `condition=dead_channel business=False alerted=False`.
- The real silencer is the shared gateway. `scripts/tg_notify.py` applies `REPEAT_LADDER_H = [TG_DEDUP_HOURS (6), 24, 72, 168]` to every tier, p0 included. In `~/.organism/tg_spool/state.json` at 13:32Z, the key `wa-bot:throughput:dead-channel` showed count 277, streak 4, first sent 2026-09-03T09:31Z, last sent 2026-09-07T15:34Z, which means muted until about 2026-09-14T15:34Z. The sibling keys `bot-broken` and `inbound-stale` are also at streak 4. Twenty-nine top-level scripts call tg_notify, `queue_shepherd.py` among them.
The stores:
- `python3 scripts/pending_arms_report.py --json --ref origin/main` → total 802, of which 533 are overdue tech debt and 221 overdue operator-gated rows. The JSON total is the number CI consumes (`grep -c '^- opened'` → 786 counts something else), so pin that convention in every PR body. The file uses `merge=union`, runs to 1943 lines and 3.0 MB, and has doubled in 29 days; 16.9% of recent commits touch nothing but it. `--ratchet`/`--ratchet-selftest` already gate OVERDUE rows in `check-ledger-no-silent-loss.yml`, so a growth gate has to be a different one.
- The bus, `shared/escalations_pro.jsonl` (git-tracked), has 218 rows, 190 of them pending. Of the 21 HIGH rows, 20 come from `healer_pro_tick`; `login_healthcheck` accounts for half the bus. Rows have no fingerprint field, and `healer_pro_tick` summaries concatenate several unrelated issues. Seven pytest-fixture rows leaked in on 2026-08-09.
- The digest is built but not armed. `infra/launchd/com.nuzantara.escalations-digest.weekly.plist` (Sundays 09:07) is missing from `~/Library/LaunchAgents`, and `launchctl list | grep -c escalations-digest` → 0. `scripts/escalations_suppressed_digest.py` reads only `escalation_cooldown.json` and `alert_dedup.json`; it has no code path for the bus, the ledger or the gateway state.
- Four SessionStart hooks (tmux-briefing, active-context-read, memory-leak-check, nuz-sync-check) emit 0 bytes and are wired only in the machine-local `~/.claude/settings.json`. #6080, #6081 and #6101 are all DIRTY and all touch the ledger.

DISEASE
Every append-only store here has an armed write path and a manual close path, so the bookkeeping only grows. A gate stops ledger rows being lost; nothing stops the file growing. The same disease on the read side teaches readers to skim past HIGH, and a persisting P0 turns into silence while the organ reports ok.

SCOPE IN (must-ship first; whatever the budget can't reach, file as PENDING-ARMS rows with owner and cause, never drop silently)
Lane (a), the signal. No ledger contention:
1. A persisting P0 never goes silent. In `tg_notify.py`, tier-scoped and additive: p0 re-raises on a bounded cadence (e.g. never muted beyond 24 h, never the 168 h rung), or at minimum every muted p0 key lands in the next digest. Tests: a p0 entry at streak ≥4 re-sends within the bound (fails on origin/main, passes after), and the digest and log tiers keep their ladder.
2. An honest sentinel: the throughput sentinel's heartbeat status reflects its condition (`organism_heartbeat` accepts any status string), pinned by a unit test. Don't re-baseline what counts as a dead bot line; that waits on Zero.
3. The digest. (3a) Install the canon plist as it is and kickstart one real run. (3b) New code, in its own PR: a reader for `shared/escalations_pro.jsonl` covering pending HIGH by job, operator-gated ledger rows by class, and muted p0 keys from the gateway state (key, count and dates only).
4. The bus: first a fingerprint-extraction function (its own small PR), then a terminal state plus a fingerprint-scoped downgrade. A chronic fingerprint drops to NORMAL, while a NEW fingerprint in the same organ still goes to HIGH. Tests for both directions.
Lane (b), the ledger. Append-only:
5. A growth gate distinct from `--ratchet`: total rows (or bytes) may not grow without a stated reason. A synthetic over-limit ledger fails it; the real one passes.
6. Closure: a machine-checkable proof-of-armed in an out-of-band sidecar keyed by row hash (never retrofit the 802 rows), an auto-close pass, and a scheduled reconciler with one real run today.
If time allows: (7) diagnose `login_healthcheck`'s `has_token=false` (it flaps), then fix it or retire it with a reason; (8) remove the seven fixture rows (a tracked file, so a PR); (9) retire the four dead hooks on Pro and Mini. Item 9 is a machine-local hand edit with NO PR path: run `cp ~/.claude/settings.json ~/.claude/settings.json.bak-20260910` first, say so in your report, and measure the SessionStart bytes before and after. M5 is Zero's; file it.

SCOPE OUT
Adjudicating any operator-gated row. Per-entry ledger files. Changing merge=union together with anything else. Re-baselining the sentinel, Meta Business Manager, credential rotation. `queue_shepherd.py` (S1), `proprioception.py` (S3), memory.db (S5).

OPERATOR BOUNDARY
Five items, filed, none blocking: the 221 operator-gated rows (digested by class); how long resolved ledger and bus rows are kept before archival; a credential, if login_healthcheck needs one; what the bot line is for after #5494 (this decides the sentinel's baseline); the M5 hooks.

METHOD
First hour: run `python3 scripts/agent_start.py --help`, then create one worktree per PR, e.g. `--lane ops --task-id p0-never-silent` (branch `agent/nuzantara/ops/p0-never-silent`). Re-run GROUND, and use `gh pr list --state open --search 'ledger OR escalations OR tg_notify'` to check for peers. Read tg_notify's dedup block and `scripts/tests/test_tg_notify_identity_ladder.py`, the end of the sentinel, `check_ledger_no_silent_loss.py`, the digest script and `dlq_autopilot.py`. Before you change a heartbeat status, find every generic reader of `~/.organism/last_seen/`, so that an honest non-ok shows up as one digest line and not a HIGH on every tick. After merge, prove the live LaunchAgents run the merged files (`launchctl print gui/501/<label> | grep -A3 'arguments = {'`), including any HOME copy of tg_notify in `infra/home-fork/declared-pairs.json`.

BITES
- Bite 1. Consumer: the gateway. The new p0 test fails on origin/main and passes on your branch, and the dead-channel entry re-sends within your bound or shows up in the digest.
- Bite 2. Consumer: the sentinel. After one launchd tick, its heartbeat no longer pairs `condition=dead_channel` with `status=ok`.
- Bite 3. Consumer: the digest. `launchctl list | grep -c escalations-digest` → 1, and one real run lists the HIGH classes and the muted p0 keys, as counts and keys only.
- Bite 4. Consumer: the bus. HIGH drops below 21, and a test proves that a new `healer_pro_tick` fingerprint still goes to HIGH.
- Bite 5. Consumer: CI. The growth gate fails on a synthetic over-limit ledger and passes on the real one.
- Bite 6. Consumer: `pending_arms_report.py`. The total drops by the rows your closure pass closed, each listed by identifier.
- Bite 7. Consumer: every future session. SessionStart bytes before and after, per machine.

RISK CONTROLS
PENDING-ARMS.md: re-read it from disk right before you write, append on a branch cut from a fresh origin/main, check that `git diff origin/main -- .claude/skills/modus/PENDING-ARMS.md` is +N/-0, and never hand-resolve or rebase onto it. tg_notify changes stay additive and tier-scoped, with tests proving the other tiers are unchanged. No alert storms: an honest red is one visible line, not a page per tick. The gateway state stores `last_text` (message fragments); never copy it anywhere. Email, if any, goes `from=zantara@balizero.com` via Brevo. Never echo a credential.

STOP CONDITIONS
Stop and file a row if a closure would mean adjudicating an operator-gated row, if changing merge=union starts to look necessary, if you get three reds for the same cause, if the digest would need PII, or if the P0 fix can't be tier-scoped.
