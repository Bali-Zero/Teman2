---
date: 2026-09-10
domain: operations
client_case: none
sources:
  - workflow wf_08272c52-202 — 12-modality read-only sweep, 14 agents, 82 findings
  - workflow wf_842ff2d4-0ad — 27 adversarial verdicts, 6 late-modality readers, 1 judge, 5 red-team attacks
  - scripts/pg.sh read-only checks on prod Postgres, 2026-09-10
  - orchestrator gate (Fable 5.1, Pro session, 2026-09-10)
---

# Program board — 2026-09-10 (Pro)

Five Fable 5.1 sessions, three waves, one queue for Zero. The mandate files next to this README are ready to paste into a fresh `claude` session. Each carries its own ground truth, and each tells the session to re-derive that ground truth before acting.

## How this board was produced

Two workflows and a final gate ran on Pro on 2026-09-10. **Workflow 1 (sweep)** sent 12 modality readers through the organism: ci-hook-churn, daemon-fleet, doc-canon-drift, escalations-dlq, harness-gate, memory-mos, merge-queue, pending-arms, prod-surface, program-state, proprioception and scars. They produced 82 findings, which a synthesizer distilled into five diseases and nine candidate sessions (C1–C9), and a critic listed the gaps. **Workflow 2 (verify + judge)** ran every candidate through three lenses (evidence-real, leverage-overstated, feasibility-one-session), for 27 verdicts. It added 6 late readers for ground the sweep had missed (data-plane, fly-cost, wa-bot-runtime, mini-fleet, secrets-security, tests-deps-backup), then handed everything to one judge, which re-verified the load-bearing numbers on Pro and proposed six sessions. A red-team attacked each of the six mandates by re-running their commands. Last, the orchestrator (Fable) gated the result: it checked the WhatsApp question against prod and overrode the judge wherever the two disagreed. Token cost: ~1.59M for the sweep, ~0.7M+ for verify + judge. Precedence where sources disagree: the gate beats the red-team, and the red-team's live re-run beats the judge's snapshot. Every number carries the time it was measured; numbers that drift hourly say "re-measure at start".

## The five diseases

1. **Sensors get built but never armed, and now the armed ones get silenced.** The auditor has no schedule, the scar census feeds a runner nothing calls, the TTL cron deletes nothing, and the re-armer did nothing on 1879 of 1880 ticks. A persisting P0 was muted for a week while its organ reported `ok`.
2. **Append-only stores have no way to close.** The ledger went from 401 to 802 rows in 29 days, the escalation bus has 190 of 218 rows pending, and 306,884 processed memory rows are never deleted.
3. **Guards judge a proxy instead of the entity**, so each fix creates the opposite defect: 9+ scars on one guard file. It is contained for now; the guard's fuzz harness passes 445/445.
4. **The doors lie, because every countable claim is hand-written.** "176 daemons", 115 MCP tools documented against 162 actual, and six INDEX.md "core tables" that don't exist in prod.
5. **Alert channels are undifferentiated.** One chronic job produced 20 of the 21 HIGH escalations, one broken probe accounts for half the bus, and Zero's real queue is short but buried.

## The sessions

| ID | Session | Wave | Machine | One line | Operator items |
|---|---|---|---|---|---|
| [S1](S1-arm-the-armer.md) | ARM THE ARMER (C1 + C9's pre-push gate) | 1 | Pro | The merge-queue re-armer did nothing on 1879 of 1880 ticks: its GraphQL query exceeds GitHub's resource limit and it exits 0 anyway | 2 |
| [S2](S2-custody.md) | CUSTODY (late reads: secrets + restore drill) | 1, parallel with S1 | Pro | The secrets audit never looks in `~/nuzantara/.secrets` and never runs; the restore drill has been red since 09-01 because the workflow never creates a role the dump needs | 4 |
| [S3](S3-arm-the-auditors.md) | ARM THE AUDITORS (C5 + C6 + one C7 probe) | 2, parallel with S4; plists wait for #6101 | Pro | proprioception is unscheduled, the cost guard unloaded, and the scar census feeds an orphan while CI reads a different registry | 3 |
| [S4](S4-reaper-and-signal.md) | THE REAPER AND THE SIGNAL (C2 + C8 + L1 residue) | 2, parallel with S3 | Pro (+ one hand edit on Mini) | The ledger doubled with no way to close rows, 20 of 21 HIGH come from one job, and a persisting P0 was muted for a week while its sentinel said ok | 5 |
| [S5](S5-brain-that-can-forget.md) | A BRAIN THAT CAN FORGET (C3) | 3, after Zero's retention ruling | Pro | TTL is set on 0 of ~15,800 memories, so the nightly sweep deletes nothing; ~1,450 OSINT rows ride every backup | 3 |

## Sequencing rules

- **Every session** runs on a Fable 5.1 seat that Zero picks manually, at max effort, on Pro, with one worktree per PR. Subagents are pinned: sonnet reads and implements, haiku does grunt work, opus is used only for a final gate.
- **Wave 1: S1 and S2 in parallel, now.** Their files don't overlap. S1 is not a hard prerequisite for anyone (auto-merge is on and sessions arm at PR open), but it makes every later PR cheaper.
- **Wave 2: S3 and S4 in parallel, once S1's query fix is live** (six clean ticks). S3 writes no plist until #6101 (one tree on Pro; open, DIRTY and armed at 13:35Z) has merged or closed. Until then it ships its non-plist PRs.
- **Wave 3: S5, only after Zero answers queue item 1**, and never alongside S4. Both change closure semantics, so a number moved by one would be blamed on the other.
- **Shared surfaces, one rule each:**
  - `PENDING-ARMS.md` (`merge=union`): append on a branch cut from a fresh origin/main, check the diff is +N/-0, and never hand-resolve the file or rebase onto it.
  - launchd: a new job is a canon plist under `infra/launchagents/` whose paths name `/Users/nuzantara/nuzantara/...`. Live-only edits get reverted by the healer's home-fork refresh, and nobody edits crontab when a plist will do.
  - `scripts/tg_notify.py` belongs to S4 alone (29 top-level callers).
  - `scripts/proprioception.py` is off-limits while #6054 is open.
- **Operator items get filed and never waited on.** S5 is the only session gated on Zero.

## Folded, dropped, and why

- **L1, "the channel is dark", is not a session.** The judge ranked it first on a real reading: zero WhatsApp inbound webhooks since 2026-09-03, and a sentinel reporting `ok`. The orchestrator then checked prod. PRs #5486 (merged 2026-09-01T08:02Z) and #5494 (12:43Z) carried out Zero's ruling to put the human line on every surface: every client-facing invitation moved from the bot's Meta line (`SUPPORT_WHATSAPP`) to the human line (`CLIENT_CONTACT_WHATSAPP`). Inbound dropped from 2–30 a day to 2 on 09-02 and zero from 09-03, which is exactly what the ruling should do. The Fly endpoint answers correctly (403 on a wrong verify token, 401 "Invalid signature" on an unsigned POST) and logged zero processing errors through 09-02. The red-team also showed that the judge's "business=False predicate" doesn't exist: the sentinel classifies correctly, and the real silencer is the shared alert gateway's mute ladder. The surviving part moved into S4 as a hard deliverable: a persisting P0 re-raises on a schedule or lands in the digest, and a sentinel never reports `ok` while its condition is dead. Instagram (dark 35 days) and "what is the bot line for now" go to Zero's queue. L1's post_publish_queue finding (63 failed, 3 dead) goes to the grunt lane.
- **C4, PARSE DON'T MATCH, was killed on evidence.** `infra/claude-hooks/guard_fuzz_harness.py` reports ALL 445 PASS with 0 unexplained mismatches. The repo and installed copies of the guard are byte-identical, every scar in its chain is fixed with a test, and bashlex isn't installed. Swapping 29 regexes in a 1549-line fleet-wide PreToolUse gate for a hand-rolled parser would open a bigger hole than it closes. Revisit only if a new over/under-match scar lands, and then as a shadow parser behind the 445-case parity harness, never as a hot cutover.
- **C9, CI TOPOLOGY, was folded.** Three of its seven fixes had already merged (#6029, #5676). The 27-vs-13 required-context discrepancy doesn't exist: there are 13 live and 13 in `contexts.json`, and the "27" is a stale sentence. Its pre-push floor gate went to S1; the advisory-label lint and the stale sentence went to the grunt lane.
- **C7, THE DOORS STOP LYING, was mostly folded.** One advisory re-derivation probe went to S3; its first consumer is INDEX.md's six phantom tables. Door self-dates, the MCP tool count and the superscar path lint went to the grunt lane. The wave-2 issues (#5316–5321 and #5323; #5322 is a merged PR, not an issue) become a `gh issue close` chore. VADEMECUM's dead pointers go to Zero.
- **C6 was folded into S3, with its payload redirected.** MANIFEST.json is stale (66 entries, 2 armed, top entry W87 against a corpus reaching W131), but its only consumer is orphaned. New gates go into `verify_the_verifiers_gates.yaml`, which is what CI reads.
- **C8 was folded into S4.** It is the same disease as C2. One correction: the weekly digest is built but not armed. Installing it is a re-arm, but reading the escalation bus needs new code.
- **Cut from S3 so it fits in five PRs:** the MANIFEST/census generator and the `automation_catalog.json` regeneration.
- **Grunt lane (sonnet implements, haiku does the mechanical edits):** headless_zombies' exact-set membership check; docs_sync's app count (the lever is `git ls-files apps/`, not README presence); dependency rot (10 open Dependabot alerts, 5 of them high; 33 outdated npm packages in apps/mouth; three duplicate py/log-injection CodeQL findings, probably from one sink); #5601–5604; the per-PR test failures on required-check-red PRs; post_publish_queue's retry path; the two items cut from S3.
- **Not now:**
  - The Fly drive process group is scaled to 2 with only 1 started. The judge's one-line fly.toml comment is out, because fly.toml is off-limits; high availability is Zero's cost/risk call.
  - The nuzantara-postgres v0.2.0 → v0.2.1 image update is a scheduled ops action, not a session.
  - The 11 dead arsenal seats: run the arsenal probe first, since one probe bug is likelier than ten outages.

## Zero's queue

PII-free. Each item says which session it gates or which session files it.

1. **RETENTION WINDOWS (gates S5; launch S5 only after you answer).** Recommended default: (a) processed `raw_observations` older than 30 days are purgeable; (b) `osint_sensitive` rows older than 7 days are purgeable, so a nightly backup carries at most a week of them, while existing backups age out under the current prune cron; (c) unresolved memories older than 90 days are archived, not deleted. Reply "default" or give your own numbers.
2. **MEMORY.md CAP (S5).** The documented 2,560 B nucleus and the coded 25,600 B alert limit differ by 10×. Which one is authoritative?
3. **`~/.claude` DOTFILES REPO (S5).** It has no remote, yet it holds the memory save path and the SessionStart wiring for three machines, with no review and no CI. Does it get a remote?
4. **THE WHATSAPP BOT LINE AFTER #5494 (S4).** Every client-facing surface now names the human line, and the bot's Meta line has had zero inbound since 09-03, as expected. What is the bot line for now: retire it, keep it as a quiet fallback, or advertise it again? Your answer decides how the throughput sentinel gets re-baselined; S4 makes the sentinel honest but won't re-baseline it. Optional one-minute proof: send one message to the bot line from your own phone. If it lands, the Meta → Fly path works end to end.
5. **INSTAGRAM.** Dark for 35 days on the same receiver. Was it retired on purpose, or should it be restored?
6. **`.secrets` CREDENTIALS (S2 files it).** The modes had been loosened; the orchestrator session corrected them by hand at ~21:05 WITA on 2026-09-10 (4 of 7 files). Whether to rotate depends on whether the second local account ever read them, and checking that needs audit-log access that only you have.
7. **SECOND LOCAL ACCOUNT (S2 files it).** `zantara-codex` is a member of `staff` on Pro. Keep it or retire it? That account, not the file modes, is the real blast radius.
8. **GITHUB SECRET SCANNING (S2 files it).** Alert #7 (Telegram bot token, open since 2026-01-19) and alert #1 (GCP service-account key, open since 2026-01-07). Rotate them at BotFather and in the GCP Console; a session resolves the alerts only after the rotation.
9. **GOOGLE MAPS KEY.** The /prime 3D map has been dead for every visitor since 2026-08-29 because the key expired. Rotation happens in the GCP Console, GUI only.
10. **NOTEBOOKLM.** Auth has been dead since 2026-08-14. Run `nlm login --clear` on the single NotebookLM account (profile `default`); interactive, GUI only.
11. **DEVELOPER_EMAILS, PR #6081.** The PR moves the developer grant off the gate that runs SQL. It needs your UU PDP boundary call, not more code.
12. **ADMIN_EMAILS.** One flat allowlist stands in for five authorization decisions (CRM, HR, portal, accounting, staff_auth). Split it or not? The sweep also claimed a pilot grant opened four unrelated systems to a staff member, but its own source doesn't back that up; treat it as unestablished.
13. **DEPENDABOT #5528/#5529 (S1 files it).** Merge them, or widen the auto-merge author allowlist. S1 won't touch the allowlist.
14. **REQUIRED-CONTEXT PROMOTIONS (S1, S3).** Anything they add lands advisory-only; promoting it is your call, since branch protection is your file. The live count is 13 contexts.
15. **THE 221 OPERATOR-GATED LEDGER ROWS (S4).** S4's digest sorts them by class, so rule on classes rather than rows. Also decide how long resolved ledger and bus rows are kept before archival.
16. **ORGAN RETIREMENT (S3).** S3 produces a provably-dead manifest for the frozen organs (WR2, mata_garuda, wr2control, SOTA m13). You sign off; no session retires anything on its own.
17. **95 ZERO-ROW PRODUCTION TABLES.** Each one is either pre-launch by design (GARUDA is flag-gated), a silently broken writer, or dead schema superseded by another table. Only you can classify them; after that, a sonnet lane drops the dead ones or files the broken writers.
18. **DUPLICATE BACKUP CRONS (S2 files it).** The 03:00 and 03:20 jobs write the same filename pattern to the same Postgres backup folder, doubling the dump load and the storage. Removing a backup cron is your call.
19. **"176 DAEMON" in `~/.claude/CLAUDE.md` (S3 reports).** That figure is true only under the broadest of three greps. S3 will report the correct derivation; only you edit that file.
20. **VADEMECUM.md:413-414.** It cites `PRICING_REFERENCE.md` and `VISA_TYPES_REFERENCE.md`, and neither exists. The pricing SSOT is `MEMORY_PRICING_CORPUS.md`. Confirm the replacements so the pointers get fixed rather than invented.
21. **M5 SessionStart hooks (S4 files it).** S4 prunes the four dead hooks on Pro and Mini by hand. M5 is your machine: do it yourself, or say "do it".
