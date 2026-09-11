---
title: "Program board — 2026-09-10 · PARABELLUM battle windows"
date: 2026-09-10
adversarial_review: codex
---

# Program board — 2026-09-10 · PARABELLUM battle windows

This board was produced by the **Fable 5.1 imperator window with Zero**. It decides the windows, the teams and the specs and appoints a Dux for each window; it never fans out and never implements.

**Recorded deviation (Codex rounds 2–3, F2).** Doctrine seats the staff room as Fable 5.1 **and Astra** with Zero, and appointing a Dux takes both imperators (`docs/architecture/dual-consul/army-map.md` §1bis; `docs/rules/RULINGS.md`, PARABELLUM). **Two-imperator approval was NOT met for wave 1:** Astra's co-signature was not obtained, and wave 1 (S1, S2) opened on Zero's decision on 2026-09-10 (~22:55 WITA). Before wave 2 opens, Zero either runs an Astra reading of this board **at a named commit hash** (a Codex `gpt-6-astra` window at effort `xhigh`; the hash and Astra's objections are recorded in the ledger row and in this README when done) or records the waiver in that ledger row. No later reading retroactively covers wave 1: it covers waves 2 and 3 only. **The colour was picked outside doctrine too:** `army-map.md:38` has Zero pick the colour with Fable **and Astra**; for wave 1 Zero picked BLUE with Fable only (final gate 2026-09-11, C4).

Each S-file is one battle window written against the seven-section spec (`.claude/skills/modus/battle-window-spec.md`): one mandate, one organ, one worktree, at most two or three windows at once.

**Colour is picked BEFORE the window opens — by Zero with Fable and Astra (`army-map.md:38`; wave 1: with Fable only, the deviation above) — and the opening command follows it.** An undeclared mission is BLUE.
- **BLUE:** Zero opens a fresh `claude --model claude-opus-5` window at effort `xhigh` and pastes the file. Dux Opus 5 `xhigh`, implementer Sonnet 5, reviewer an independent Codex seat, gate a fresh Opus 5 `xhigh` session outside the chain, release by the Dux.
- **ORANGE:** Zero opens a Codex window on the Sol seat — army-map §1bis names it "Sol (`gpt-5.6-sol`) `xhigh`"; the map names the seat, not a command line — and pastes the file. Every other seat is re-resolved from §1bis, the table's only copy.
- **No colour fallback.** A dead seat suspends the mission; it never changes colour. Before executing, the window states colour, Dux role, mandate id and worktree path.

## How this board was produced

- **Sweep** (Pro, 2026-09-10): 12 modality readers, 82 findings, distilled into five diseases and nine candidates (C1–C9); a critic listed the gaps. ~1.59M tokens.
- **Verify + judge:** 27 verdicts (9 candidates × 3 lenses), 6 late readers, one judge re-verifying the load-bearing numbers on Pro. ~0.7M+ tokens.
- **After the judge:** a red-team re-ran every mandate's commands; the orchestrator gated the result and checked the WhatsApp question against prod; an independent Codex seat (`gpt-5.6-sol`) graded three rounds, REWORK each time; a fresh Opus 5 gate then returned PASS-WITH-CONDITIONS (§ Adversarial review).
- **Precedence:** the gate beats the red-team; the red-team's live re-run beats the judge's snapshot.

## The five diseases

1. **Sensors built but never armed, and armed ones silenced.** The auditor has no schedule; the TTL cron deletes nothing; the re-armer did nothing on 1879 of 1880 ticks; a persisting P0 was muted for a week while its organ reported `ok`.
2. **Append-only stores cannot close.** Ledger 401 → 802 rows in 29 days; escalation bus 190 of 218 rows pending; 306,884 processed memory rows never deleted.
3. **Guards judge a proxy, not the entity.** Contained for now: the guard fuzz harness passes 445/445.
4. **The doors lie, because countable claims are hand-written:** "176 daemons", 115 MCP tools documented vs 162 actual, six INDEX.md "core tables" absent from prod.
5. **Alert channels are undifferentiated.** One chronic job produced 20 of 21 HIGH escalations; Zero's real queue is short but buried.

## The windows

| ID | Window · organ | Wave | Host | Colour | Dux | One line | Operator items |
|---|---|---|---|---|---|---|---|
| [S1](S1-arm-the-armer.md) | ARM THE ARMER · `scripts/queue_shepherd.py` | 1 (opened ~22:55 WITA) | Pro | BLUE | Opus 5 `xhigh` | The re-armer's candidate query exceeds GitHub's resource limit and it exits 0 | 1 |
| [S2](S2-custody.md) | CUSTODY · the credential-custody detector | 1 (opened ~22:55 WITA) | Pro | BLUE | Opus 5 `xhigh` | The secrets audit never looks in `~/nuzantara/.secrets` and has no schedule | 4 |
| [S3](S3-arm-the-auditors.md) | ARM THE AUDITOR · proprioception | 2 | Pro | BLUE (default) | Opus 5 `xhigh` | The auditor runs only when typed, and INDEX.md's core tables go unchecked | 0 |
| [S4](S4-reaper-and-signal.md) | THE SIGNAL · alert gateway + weekly digest | 2 | Pro | BLUE (default) | Opus 5 `xhigh` | A persisting P0 went silent for a week, and the digest is built but unarmed | 3 |
| [S5](S5-brain-that-can-forget.md) | A BRAIN THAT CAN FORGET · MOS store, mechanism only | 3 | Pro | BLUE (default) | Opus 5 `xhigh` | TTL is set on 0 of ~15,800 memories; this window ships the dry-run tool and installs the inert worker, S5b cuts | 1 |

## Sequencing

- **Concurrency:** two or three windows at a time, each in its own worktree; never two on the same path.
- **Wave 1: S1 and S2** (opened ~22:55 WITA). An optional third is the queued RESTORE DRILL (red since 09-01, next cron 10-01) once its own file exists.
- **Wave 2: S3 and S4** open only when (a) S1's shepherd PR is **MERGED**, (b) Pro has pulled it (puller rc=0), (c) the staff room has acked the S1 window's six-clean-ticks checkpoint, and (d) the Astra reading or its waiver is recorded. An armed PR still runs the old re-armer, so "armed" is not the trigger. Inside wave 2, S3's probe waits for #6054 (open at 15:40Z); #6101 merged 2026-09-10T14:24Z.
- **Wave 3: S5**, mechanism only (dry-run tool plus the inert worker installed on HOME; no direct write to the live DB). **Opens when** S3's and S4's code PRs are MERGED and the retention question is on Zero's queue (item 2 — it is), before or after the ruling itself. **S5b — THE CUT** opens only after Zero's retention ruling is recorded in the ledger and S5's PR is merged. Neither runs alongside the queued REAPER window.

## Sibling contract — summary

| Shared surface | Owner | Touched by | Rule |
|---|---|---|---|
| `.claude/skills/modus/PENDING-ARMS.md` (`merge=union`, ignored by GitHub's mergeability — modus SKILL.md:193) | Shared lockfile; structure owner: the queued REAPER window | All windows | Rows only in each window's final, separate, ledger-only PR, cut from a fresh origin/main after its code PRs merge. Open it only when no other open PR touches the file; diff +N/-0. DIRTY → the freeze rule below |
| `scripts/tg_notify.py` | S4 | S1, S2 (callers) | CLI, API and state format frozen; the p0 change is tier-scoped |
| `infra/launchagents/` canon | #6101 (merged) | S2, S3 (one new plist each) | Exec paths name `/Users/nuzantara/nuzantara`; bootstrap from canon; no crontab |
| `scripts/proprioception.py` | #6054, then S3 | S3 | The probe PR waits until #6054 has merged |
| `infra/home-fork/declared-pairs.json` | S5b, one entry | S5b | Edited only after the sha256 proof of the HOME worker copy |

Apart from the ledger the windows share no writable file: S1 the shepherd, S2 the audit script, S3 proprioception plus INDEX.md:71, S4 the gateway plus the digest, S5 the worker plus the purge tool.

**The freeze rule (every window).** Once auto-merge is armed the branch is read-only (Builder Contract rule 1).
- **Real DIRTY** on an armed PR: close it with a comment naming the successor, cut a fresh branch from origin/main carrying the same content (cherry-pick), then push, create and arm the successor as three separate commands.
- **Phantom DIRTY** (GitHub reports DIRTY and the queue still accepts it — `autoMergeRequest` still set): the queue cures it by merging. Judge the diff first; never disarm.
- **Never** `--disable-auto` → merge origin/main → push → re-arm.

**Checkpoint delivery (every window; `docs/architecture/dual-consul/army-map.md:81-90`).** A file written is published, not delivered, and the sender owns the wake-up.
1. Publish with `scripts/fleet_mail.sh local broadcast --key S1-checkpoint --ttl 24 "$STATE"` (S2–S5 likewise); the file name it prints in parentheses is the envelope id.
2. Wake-up: `SendMessage` the same text, quoting the envelope id, to the staff-room Claude window (today `website-03`). **On ORANGE** the Dux Sol has no `SendMessage`: it takes the Codex-peer route (`army-map.md:85-86`) — Zero, who opened the staff-room window, is told which mailbox file to point it at.
3. **The staff room's duty:** ack with key `S1-ack` (S2–S5 likewise) in the Pro mailbox, or a session reply, within 15 minutes of wall clock, quoting the same envelope id back (`army-map.md:87`: `received` is recorded against the same hash). An ack without the id does not count.
4. No ack → one retry with the same text and id, then a `BLOCKED: undelivered` ledger row and the window suspends — never a silent wait. S1's wave-2 trigger travels the same way.

## Queued windows

The staff room opens each one; each needs its own seven-section file first, and the staff room opens a ledger row when it schedules it.

1. **QUEUE SIBLINGS (Mini)** (split from S1). `scripts/queue_unstick.py` and `scripts/queue_stall_classifier.py` (notifier `scripts/queue_stall_notify.py`) on Mini. Input: what S1's pack notes they need.
2. **S5b — THE CUT** (split from S5). Opens after Zero's retention ruling is recorded in the ledger and S5's PR is merged. Owns everything irreversible: backup, pause, `--apply`, VACUUM, ttl on save in `~/.claude/scripts/mem`, the declared-pair widening PR, the ledger. (The HOME worker `cp` is S5's live consumer, not S5b's.) **Gate coverage:** the gate signs the dry-run before `--apply` AND re-reads the post-apply state (per-class counts == predicted, `PRAGMA integrity_check` ok) before success is reported. **Backup:** into the existing `~/.claude/backups/` under a `memory_*.db` name, so the existing C2.14 prune removes it after 30 days; `chmod 600` explicitly (the directory is 0755 today); the archive is a table inside memory.db, never a dated cleartext file. **Rollback:** quiescence = compression daemon paused AND no `mem` writes AND no capture-hook writes. `~/.claude/hooks/mos_capture_post_tool.py`, `mos_capture_stop.py` and `mos_capture_session_end.py` INSERT into `raw_observations` from every live Claude session even while the daemon is paused, with no kill switch, so a delta is the expected case. `.restore` only if `max(id)` of BOTH `memories` and `raw_observations` is unchanged since the backup; otherwise export both deltas (ids above each table's backup max) to the scratch dir, restore, re-insert them. The "next morning" backup proof belongs here.
3. **RESTORE DRILL** (split from S2). Red since 2026-09-01: the service container never creates `backend_rag_v2`, so psql exits 3 before the Level-5 verifier runs. Fix: create the role or restore with `--no-owner`, `workflow_dispatch`, prove a Level-5 pass; a red drill alerts through a transport that exists inside Actions.
4. **IMMUNE REGISTRY** (C6, split from S3). Executable scar gates in `scripts/verify_the_verifiers_gates.yaml`, each proven to fail on synthetic re-injection. MANIFEST.json is not regenerated: its only consumer is orphaned.
5. **ORGAN CENSUS** (split from S3). A provably-dead manifest (organ id, heartbeat age, log error class only); conversation tables never proposed for a drop (five-year retention); the "176 daemon" derivation.
6. **THE REAPER** (C2, split from S4). Owns the ledger's structure: a growth gate distinct from `--ratchet`, a sidecar proof-of-armed keyed by row hash, auto-close and a reconciler.
7. **SIGNAL TRIAGE** (C8's bus half, split from S4). The bus's terminal state, fingerprint extraction and fingerprint-scoped downgrade, the `login_healthcheck` diagnosis, the seven leaked fixture rows.
8. **SENTINEL HONESTY** (L1 residue). The throughput sentinel stops hardcoding `status="ok"`. Waits on THE REAPER.
9. **PRE-PUSH FLOOR GATE** (C9, split from S1). `.husky/pre-push` refuses a floor-2 push without a brief, re-baselined after #6100. Fleet-wide hook.
10. **MEMORY GUARD** (split from S5). A MEMORY_INDEX cap check that can fire: extend `scripts/memory/mos_recall_sessionstart.py` or fix and register `scripts/harness/harness_lifecycle_guard.py`. Waits on IMMUNE REGISTRY.
11. **R1 DESIGN + R2 ENGINE — RESEARCH OS** (mandate 7, staff room Fable + Astra 2026-09-11). Seven-section files in [`R-research-os.md`](R-research-os.md): one tranche, P04-surface decisions → P06 NAGA claim ledger slice 2; the 23 packets stay a roadmap. Opens after Zero rules Z1–Z4 of that file (scope, bounded production writes, colour, veto). R2 releases only after R1 merged.

## Gear-1 one-liners (the former grunt lane)

No sixth program and no shared lane (Codex round 2, F3). Each item is ONE Gear-1 PR cut from a fresh origin/main by the Dux that owns the nearest organ, after that window's own PRs; an item with no live owner is queued.

| Item | Owner |
|---|---|
| `headless_zombies` exact-set membership (a probe in `scripts/proprioception.py`) | S3's Dux, after its probe PR and #6054 |
| Load the cost guard (two canon plist copies: pick one first) | queued → ORGAN CENSUS |
| Plist linter's two ExpatError snapshots (dead organs) | queued → ORGAN CENSUS |
| docs_sync app count (lever: `git ls-files apps/`); MANIFEST/census generator; `automation_catalog.json` regeneration | queued → ORGAN CENSUS |
| Door self-dates, the MCP count, the superscar path lint | queued → ORGAN CENSUS |
| The C9 label lint and its stale sentence | queued → PRE-PUSH FLOOR GATE |
| Dead SessionStart hooks on Pro and Mini (machine-local, back up first) | queued → MEMORY GUARD |
| post_publish_queue's retry path (63 failed, 3 dead) | queued (no owning window yet) |
| #5601–5604 | queued (no owning window yet) |
| Dependency rot: 10 Dependabot alerts (5 high), 33 outdated npm packages in apps/mouth, three py/log-injection findings | queued; **not a one-liner** — needs its own window file |
| Wave-2 issues #5316–5321 and #5323 (#5322 is a merged PR): `gh issue close` citing the probe | S3's Dux, after its probe lands |
| Per-PR test failures on required-check-red PRs; arming CLEAN PRs | each PR's own release owner, never another window |

## Doctrine gaps found while writing

- **Stale paths in the spec.** It names `scripts/mandate_budget.py` and `scripts/lane_check.py`; the live files are `infra/codex-hooks/mandate_budget.py` and `infra/claude-hooks/lane_check.py`. The windows cite the real paths.
- **Ledger DIRTY cure vs. freeze.** modus SKILL.md:193 cures a union DIRTY with a local `git merge origin/main`; Builder Contract rule 1 freezes an armed branch. The windows apply the freeze rule above: the local-merge cure only ever touches a branch that was never armed.
- **`--squash` drift.** modus SKILL.md:100 still prescribes `gh pr merge --auto --squash` (standing rule 2026-06-25). `docs/runbooks/merge-queue-discipline.md:274-278` (measured on PR #3347) and `scripts/queue_shepherd.py:819-821` record that the queue rejects every strategy flag and `--squash` arms nothing. The windows use bare `--auto`; modus line 100 needs its own fix PR.

## Folded, dropped, and why

The gate's decisions, unchanged; rework destinations in *italics*.
- **L1, "the channel is dark", is not a session.** Zero WhatsApp inbound since 2026-09-03 is what Zero's ruling produces: PRs #5486 (2026-09-01T08:02Z) and #5494 (12:43Z) moved every client invitation from the bot's Meta line (`SUPPORT_WHATSAPP`) to the human line (`CLIENT_CONTACT_WHATSAPP`). The Fly endpoint answers correctly (403 on a wrong verify token, 401 on an unsigned POST). The real silencer is the gateway's mute ladder. *Gateway half → S4; sentinel half → SENTINEL HONESTY.* Instagram and the bot line → Zero's queue.
- **C4, PARSE DON'T MATCH, killed on evidence:** `infra/claude-hooks/guard_fuzz_harness.py` ALL 445 PASS, repo and installed guard byte-identical, bashlex not installed. Revisit only on a new over/under-match scar, as a shadow parser behind the 445-case harness.
- **C9, CI TOPOLOGY, folded:** three of seven fixes already merged (#6029, #5676); 13 contexts are live. *Pre-push gate → PRE-PUSH FLOOR GATE.*
- **C7, THE DOORS STOP LYING, mostly folded:** *one re-derivation probe → S3, inside proprioception, consumed by the scheduled run.* The rest → the Gear-1 table; VADEMECUM's dead pointers → Zero.
- **C6 → IMMUNE REGISTRY. C8 → digest in S4, bus half in SIGNAL TRIAGE.**
- **Not now:** the Fly drive group (fly.toml off-limits; HA is Zero's cost call); the nuzantara-postgres image update (scheduled ops); the 11 dead arsenal seats (run the arsenal probe first).

## Zero's queue

PII-free. Each item names the window it gates or the window that files it.

0. **ASTRA READING OR WAIVER (gates wave 2).** Astra reads this board at a named commit, or you waive it in the ledger row. It covers waves 2–3 only, never wave 1 (recorded deviation, top).
1. **COLOUR PER MISSION.** Picked with Fable and Astra before a window opens; BLUE if undeclared. Fixed at mission start.
2. **RETENTION WINDOWS (gates S5b).** Default: (a) processed `raw_observations` older than 30 days purgeable; (b) `osint_sensitive` rows older than 7 days purgeable, existing backups age out under the 30-day prune; (c) unresolved memories older than 90 days archived, not deleted. Reply "default" or give numbers.
3. **MEMORY.md CAP (MEMORY GUARD).** Documented 2,560 B vs coded 25,600 B: which is authoritative?
4. **`~/.claude` DOTFILES REPO (S5 files it).** No remote, yet it holds the memory save path and the SessionStart wiring for three machines. Give it a remote?
5. **THE WHATSAPP BOT LINE AFTER #5494 (SENTINEL HONESTY).** Retire, quiet fallback, or advertise again?
6. **INSTAGRAM.** Dark for 35 days: retired on purpose, or restore?
7. **`.secrets` CREDENTIALS (S2 files it).** Modes were loosened; the orchestrator corrected 4 of 7 by hand at ~21:05 WITA. Rotation depends on whether the second local account read them; only you have the audit-log access. Any future live finding's chmod is yours too: S2 reports, it never fixes.
8. **SECOND LOCAL ACCOUNT (S2 files it).** `zantara-codex` is in `staff` on Pro. Keep or retire?
9. **GITHUB SECRET SCANNING (S2 files it).** Alerts #7 (Telegram bot token) and #1 (GCP service-account key): rotate first, resolve after.
10. **GOOGLE MAPS KEY.** The /prime 3D map is dead since 2026-08-29 (key expired); rotation is in the GCP Console.
11. **NOTEBOOKLM.** Auth dead since 2026-08-14: `nlm login --clear` on the single account (profile `default`).
12. **DEVELOPER_EMAILS, PR #6081.** The UU PDP boundary call; the PR needs your decision, not code.
13. **ADMIN_EMAILS.** One flat allowlist for five authorization decisions: split it?
14. **DEPENDABOT #5528/#5529 (S1 files it).** Merge them, or widen the auto-merge author allowlist.
15. **REQUIRED-CONTEXT PROMOTIONS (IMMUNE REGISTRY, PRE-PUSH FLOOR GATE).** Their checks land advisory; promotion is yours. 13 live contexts today.
16. **THE 221 OPERATOR-GATED LEDGER ROWS (S4's digest sorts them).** Rule by class; decide how long resolved rows are kept.
17. **ORGAN RETIREMENT (ORGAN CENSUS).** You sign; no window retires an organ.
18. **95 ZERO-ROW PRODUCTION TABLES.** Pre-launch, broken writer, or dead schema: only you can classify.
19. **DUPLICATE BACKUP CRONS (RESTORE DRILL files it).** The 03:00 and 03:20 jobs write the same pattern.
20. **"176 DAEMON" in `~/.claude/CLAUDE.md` (ORGAN CENSUS reports the derivation).** Only you edit that file.
21. **VADEMECUM.md:413-414.** Two cited docs don't exist; the pricing SSOT is `MEMORY_PRICING_CORPUS.md`. Confirm the replacements.
22. **M5 SessionStart hooks.** Pro and Mini are pruned by hand; M5 is yours: do it, or say "do it".

## Adversarial review

**Seat:** Codex `gpt-5.6-sol`, independent of the author chain. **Round 1 — REWORK (all six):** role and authority conflicted with PARABELLUM (Fable as implementer, no Dux/colour); `agent_start.py` prints `WORKTREE_READY` and cannot change the caller's cwd; the "disjoint files" claim was false because every window appends to the `merge=union` ledger; S1–S5 were program-sized; S2 could touch `.env*`; S5's proofs did not falsify. Applied in v2 (Dux/colour/mission id declared, captured `$WT`, ledger rows only in a final ledger-only PR, programs split into queued windows).

**Round 2 — REWORK (all six), 17 findings, staff-room dispositions:**

| # | Finding | Disposition | Where |
|---|---|---|---|
| F1 | ORANGE opened `claude-opus-5` | Applied: the colour is chosen before opening; BLUE → `claude --model claude-opus-5` `xhigh`, ORANGE → a Codex window on the Sol seat as §1bis names it | README, all S-files |
| F2 | Dux appointed without Astra | Applied as a recorded deviation; Astra reading or waiver gates wave 2 | README, all S-files |
| F3 | Grunt lane bypasses the format | Applied: grunt lane removed; Gear-1 one-liner table with owners or queued | README |
| F4 | Wave 2 opened on "armed" | Applied: MERGED + pulled (rc=0) + six clean ticks reported | README, S1, S3, S4 |
| F5 | DIRTY recipe violated the freeze | Applied: real DIRTY → close + successor from fresh origin/main; phantom DIRTY → the queue cures it; never disarm-merge-push-rearm | README, all S-files |
| F6 | S1 was not one organ | Applied: S1 = `queue_shepherd.py` on Pro only; QUEUE SIBLINGS (Mini) queued | README, S1 |
| F7 | Ancestor proof fails on squash | Applied: blob-equality content proof (superscar #9, `content_on_main()`) | S1–S5 |
| F8 | `--auto` without `--squash` | **Rejected:** the queue rejects every strategy flag (`merge-queue-discipline.md:274-278`, PR #3347; `queue_shepherd.py:819-821`). Codex's citation is accurate about modus SKILL.md:100, which does say `--auto --squash`; that line is stale (Doctrine gaps) | all |
| F9 | Checkpoint commands did not run | Applied: `scripts/fleet_mail.sh local broadcast --key S1-checkpoint --ttl 24 "$STATE"` (S2–S5 likewise); no placeholder left in any command | all S-files |
| F10 | S2 interval undefined, hardcoded counts | Applied: `StartInterval` 3600; same-minute agreement with `find` | S2 |
| F11 | S3 sequence impossible in one PR | Applied: schedule → probe → separate INDEX.md PR → ledger | S3 |
| F12 | S4 pytest path did not exist | Applied: `~/nuzantara/.venv/bin/python3 -m pytest` (pytest 9.0.3, verified on Pro) | S1–S5 |
| F13 | Mute ceiling unnumbered; zero-baseline rollback | Applied: at most once per 6 h, at least once per 24 h; rollback on >4 re-raises/24 h per key | S4 |
| F14 | S5 did not fit 8 h | Applied: S5 = mechanism; S5b — THE CUT queued | README, S5 |
| F15 | S5 contradicted its DELETE ban | Applied: probe insert/delete only on a scratch copy; S5b gate re-reads the post-apply state | README, S5 |
| F16 | Sensitive copies without lifecycle | Applied: `~/.claude/backups/` under C2.14's prune, explicit `chmod 600`, archive table not a file | README, S5 |
| F17 | Rollback could lose valid rows | Applied: quiescence by max(id); delta export before `.restore` | README, S5 |

**Round 3 — REWORK (all six), on v3 `b701479b33`:** 15 RESOLVED, 2 PARTIAL (F2, F17), 3 new blockers; F8 not reopened. Staff-room dispositions, all applied:

| # | Finding | Disposition | Where |
|---|---|---|---|
| B1 | Checkpoints published, not delivered (army-map.md:81-90) | Four steps: publish + envelope id, `SendMessage` wake-up, ack within 15 min, one retry, then `BLOCKED: undelivered`; S1's wave-2 trigger is the ack | README, every S-file §6, S1 §4/§7, S3/S4 Wave rows |
| B2 | S2 authorized a live chmod on credentials | Detect and report only; no `--fix`; the chmod is Zero's (Builder Contract rule 5); only the `mktemp` fixture is chmod'ed | S2 §2, §4, §6, §7; README queue item 7 |
| B3 | S5's worker had no live consumer | The HOME worker `cp` + sha256 proof + the daemon's next run moved from S5b into S5; inert without a ruling file | README, S5 |
| F2 | A later reading ≠ two-imperator approval | Wave 1 recorded as not approved by both; the Astra reading is at a named commit and covers waves 2–3 only | README, every S-file header |
| F17 | Quiescence ignored `raw_observations` | `.restore` only if `max(id)` of BOTH tables is unchanged, else both deltas exported and re-inserted; the three capture hooks named | README, S5 |

**Final gate 2026-09-11 (Opus 5, fresh):** PASS-WITH-CONDITIONS C1–C7; C2–C6 applied in v5, C1 in the S2 window, C7 done. Headless session on `adbd2a86e7`; receipt `https://github.com/Bali-Zero/Teman2/pull/6104#issuecomment-5621804838`; verdict text in `evidence/2026-09/agent-nuzantara-docs-fable-max-sessions-0910-66f337b2/gate-verdict-2026-09-11.md`.

| # | Condition | Disposition | Where |
|---|---|---|---|
| C1 | S2 does not name Mini's `com.nuzantara.secrets-perms-sweep` (runs the audit with `--fix`) as a consumer | Sent to the running S2 window, before its roots PR is armed | S2 window |
| C2 | `Bites:` on every PR, not every code PR | Applied; a ledger-only PR names `scripts/pending_arms_report.py` and its next run listing the rows | every S-file §7 |
| C3 | Ack not bound to the envelope id; no ORANGE wake-up route | Applied: id quoted in message and ack; Codex-peer route via Zero | README, every S-file §6 |
| C4 | Colour picked without Astra | Recorded deviation extended; the colour line reworded | README |
| C5 | S5: no named ruling file, `$BK` unassigned, no wave-3 trigger | Applied: `ruling.yml` + `--ruling`, `BK=` defined, wave-3 and S5b triggers | README, S5 |
| C6 | `$TITLE`/`$BODY` only in S1; stale `agent_start.py` line | Applied: defined in every release line; `:2174` (grep on origin/main `a8a1d71cb0`) | S1–S5 |
| C7 | #6104 not armed at gate time | Done by the release owner | — |
