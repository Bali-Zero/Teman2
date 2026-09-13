---
title: "S5 — A BRAIN THAT CAN FORGET · battle window (mechanism)"
date: 2026-09-10
adversarial_review: codex
---

# S5 — A BRAIN THAT CAN FORGET · battle window (mechanism)

| Field | Value |
|---|---|
| Mandate id | **S5** |
| Colour | **BLUE** unless Zero declares ORANGE before the window opens. No fallback between colours. |
| Dux role | Opus 5 `xhigh` on BLUE (Sol `gpt-5.6-sol` `xhigh` on ORANGE), appointed by the staff room (Fable 5.1 with Zero; the Astra reading of this board at a named commit, or Zero's waiver, is pending — README). Dux and release owner. |
| Worktree / branch | `agent/nuzantara/db/s5-memory-lifecycle`, created by the command in §1 |
| Wave | 3. Opens when S3's and S4's code PRs are MERGED and the retention question is on Zero's queue (README). Never alongside the queued REAPER window: both change closure semantics. |
| Opening | The opening follows the colour. BLUE: Zero opens a fresh `claude --model claude-opus-5` window at effort `xhigh` and pastes this file. ORANGE: a Codex window on the Sol seat as army-map §1bis names it ("Sol (`gpt-5.6-sol`) `xhigh`"). The first message restates colour, Dux role, mandate id and worktree path, then executes. |

## 1. Mandate

S5 · BLUE · **organ: the MOS memory store** — `~/.claude/memory.db`, its compression worker (repo `scripts/mos-plus-compression-worker.py`, run live by `com.balizero.mos-plus.compression` from the HOME copy `~/scripts/mos-plus-compression-worker.py`), the nightly TTL sweep (cron C2.15) and the `mem` save path. **This window ships the MECHANISM only.** Everything irreversible — backup, pause, `--apply`, VACUUM, ttl on save, the declared-pair widening — belongs to the queued window **S5b — THE CUT** (README), which opens after Zero's retention ruling. The one live change here is the HOME worker `cp`, the mechanism PR's consumer. **Gear:** 3 by triage (the tool it ships is the instrument of an irreversible cut); CI's floor never lowers it; Evidence Pack required. **Host:** Pro only.

**Objective:** the worker's ttl logic and a retention tool `scripts/memory/mos_retention_purge.py` (to be created) whose dry-run per-class counts, on a verified scratch copy of the live DB, are signed by an independent gate. **What success changes:** S5b can cut the moment Zero rules, on signed numbers rather than on a generator's own SQL. The only live change is the HOME worker copy; with no ruling file its ttl logic writes NULL, so nothing is deleted.

**The ruling is an input, not a precondition.** The ruling file is `evidence/2026-09/agent-nuzantara-db-s5-memory-lifecycle-de478768/ruling.yml` (to be created, in this branch's evidence directory: `python3 scripts/ci/evidence_paths.py --ref agent/nuzantara/db/s5-memory-lifecycle` prints it). S5 writes it with the default below, marked `status: proposed`, and records its sha256 in the pack. The tool and the worker read a ruling only through an explicit `--ruling` flag (to be created); the daemon's plist passes none, so the live worker stays inert. `--apply` refuses without a ruling file or with one still `proposed`. A ttl backfill on existing rows counts as a DELETE (C2.15 deletes every expired row that same night) and belongs to S5b. Default proposed to Zero: processed raw_observations older than 30 days purgeable; osint_sensitive rows older than 7 days purgeable; unresolved memories older than 90 days archived, not deleted.

**Worktree:** `cd ~/nuzantara && WT=$(python3 scripts/agent_start.py --lane db --task-id s5-memory-lifecycle | awk '/^WORKTREE_READY /{print $2}') && echo "$WT"`. The broker prints one `WORKTREE_READY` line followed by the path and cannot change your cwd (`scripts/agent_start.py:2174`): every later command is `git -C "$WT" …` or `cd "$WT" && …`; `--list` recovers the path. One live worktree at a time, `--release` between PRs. `mos` is not a known lane. **Base sha:** record `git -C "$WT" rev-parse HEAD` at open.

**Ground** (counts 13:05Z, schema and crontab ~13:35Z, backups ~15:40Z; re-read all of it, never printing row content):
- **Counts** (memories, ttl set, superseded, raw_observations, processed, osint): `15842|0|0|313956|306884|1452`.
- **Schema** (`sqlite3 ~/.claude/memory.db ".schema memories" ".schema raw_observations"`): `memories` has `id INTEGER PRIMARY KEY AUTOINCREMENT`, `created_at`, `type` ∈ {decision, discovery, fact, pattern, unresolved}, `ttl_days`, `superseded_by`; `raw_observations` has `captured_at`, `payload_json`, `osint_sensitive`, `compressed_to_memory_id`, `discarded_at`.
- **C2.15** (daily 05:00 UTC): `DELETE FROM memories WHERE ttl_days IS NOT NULL AND julianday("now") - julianday(created_at) > ttl_days`. It matches zero rows and still reports ok; a bare sqlite3 DELETE prints nothing, so counts need `SELECT changes();`.
- **C2.13** (daily 04:00 UTC) `cp`s the live DB to `~/.claude/backups/memory_YYYYMMDD.db`. **C2.14** (Sundays 05:00 UTC) runs `find ~/.claude/backups -name "memory_*.db" -mtime +30 -delete`; it does not match the `-shm`/`-wal` sidecars (present for three dates today). `~/.claude/backups` is mode 0755; the backup files are 0600.
- **The save path has no PR path.** `~/.claude/scripts/mem` inserts only (session_id, type, content, importance) and has no database-path override; `git -C ~/.claude remote -v` is empty.
- **Live writer.** `lsof ~/.claude/memory.db` shows `com.balizero.mos-plus.compression` executing the HOME copy: `StartInterval` 1800, no `KeepAlive`, `RunAtLoad` false — a fresh process per run — logging to `~/logs/mos-plus-compression.log`. At ~15:40Z the HOME copy's sha256 equalled the origin/main blob, so a `cp` after the merge carries only this PR's diff. Its declared pair has `machines: []`; widening to `["pro"]` is S5b's.
- **Other writers.** `~/.claude/hooks/mos_capture_post_tool.py`, `mos_capture_stop.py` and `mos_capture_session_end.py` INSERT into `raw_observations` from every live Claude session, whether or not the daemon runs; none has a kill switch. `raw_observations.id` is `INTEGER PRIMARY KEY AUTOINCREMENT`.

## 2. Owned perimeter

- **Writable (repo only):** `scripts/mos-plus-compression-worker.py` and `scripts/tests/test_mos_plus_compression_worker.py`; `scripts/memory/mos_retention_purge.py` (to be created) and its tests — dry-run by default, `--db` and `--ruling` flags (to be created; the worker gets the same `--ruling`), `--apply` refuses without a ruling file or on a `proposed` one; the ruling file above.
- **One live write:** `~/scripts/mos-plus-compression-worker.py`, for a single `cp` of the merged repo file after the puller (direct administration, logged in the pack), with the pre-cp copy saved first as `~/scripts/mos-plus-compression-worker.py.pre-s5`.
- **Read-only on live state:** `sqlite3 ~/.claude/memory.db ".backup …"` into a scratch directory, `.schema`, `count(*)` and `max(id)` queries. No other access to the live DB.
- **Forbidden:** any direct write, DELETE, ttl update or VACUUM on `~/.claude/memory.db` (the worker's normal compression writes continue); any other edit of the HOME worker; `~/.claude/scripts/mem`; pausing the compression LaunchAgent; `infra/home-fork/declared-pairs.json` (all S5b); existing backups in `~/.claude/backups/`; the recall and lifecycle guards and any `settings.json` (queued MEMORY GUARD); M5 and Mini; PENDING-ARMS structure; printing `payload_json` or any row content, ever.
- **Shared:** the ledger (§3).
- `.lane-check.json`'s `scope_globs` only decides whether a check applies (`infra/claude-hooks/lane_check.py`; the spec's `scripts/` path is stale). VERIFY and the gate compare changed paths against this list by hand.
- **Bans:** no Claude model through a paid per-token Anthropic endpoint (any alias, wrapper, Bedrock or Vertex route; only the `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN`). No client PII or OSINT in cleartext. Off-limits: `zantara_core.py`, `fly.toml`, `.env*`, `apps/bali-intel-scraper/backend/db/migrations/env.py`. Zero's files never edited.

## 3. Sibling contract

Frozen before BUILD. Changes go to the staff room through Zero.

- **Predicates.** The tool's per-class predicates are exactly those of the file passed with `--ruling`, recorded by sha256 in the evidence pack; every dry-run in §4 passes the default ruling file explicitly. `--dry-run` prints per-class counts; `--apply` prints `changes()` per class and exits non-zero on any mismatch with the gate-signed dry-run.
- **Archive, not delete.** Rows ruled "archive" move to an archive TABLE inside memory.db — never a dated cleartext file — and never reach a DELETE. The FTS triggers (`memories_ad`) stay consistent; the recall hook and `mem query` keep working.
- **C2.15 keeps its shape.** A row gets a ttl only if its class was ruled purgeable.
- **No other window writes memory.db**, and S5 never writes it directly: the copied worker keeps writing it as before, with `ttl_days` NULL until a ruling file exists.
- **The ledger — the one surface all windows share.** `.claude/skills/modus/PENDING-ARMS.md` carries `merge=union`, which GitHub's mergeability ignores (modus SKILL.md:193). Serialize: rows ONLY in one final, separate, ledger-only PR, cut from a fresh origin/main after the code PR merged. Open it only when `gh pr list --state open --limit 200 --json number,files --jq '[.[]|select(any(.files[];.path==".claude/skills/modus/PENDING-ARMS.md"))|.number]'` prints `[]` and `git -C "$WT" diff origin/main -- .claude/skills/modus/PENDING-ARMS.md` is +N/-0.
- **Freeze.** Once armed, the branch is read-only (Builder Contract rule 1). A **real** DIRTY on an armed PR: close it with a comment naming the successor, cut a fresh branch from origin/main, cherry-pick the same content, then push, create and arm the successor as three separate commands. A **phantom** DIRTY (GitHub reports DIRTY while `gh pr view "$PR" --json autoMergeRequest` still shows it armed): judge the diff, then let the queue cure it. Never `--disable-auto`, merge origin/main, push and re-arm.

## 4. Acceptance

Every check that inserts, updates or deletes runs on a **scratch copy**, never on the live DB. Make one with `SCR=$(mktemp -d); sqlite3 ~/.claude/memory.db ".backup '$SCR/mem.db'"; chmod 600 "$SCR/mem.db"; sqlite3 "$SCR/mem.db" "PRAGMA integrity_check;"` → ok. The copy is sensitive: `rm -rf "$SCR"` before the session ends, and log the deletion in the pack.

- **Negative:** `--apply` with no ruling file, or with the `proposed` default, exits non-zero, and `select count(*) from memories` on the scratch copy is the same before and after. If the tool's dry-run and the gate's own counts disagree on any class, `--apply` refuses.
- **Integration (scratch only):** `cd "$WT" && ~/nuzantara/.venv/bin/python3 -m pytest scripts/tests/test_mos_plus_compression_worker.py -q` plus the tool's tests pass. Then, on `$SCR/mem.db` with a test ruling file: a probe row written through the worker's ttl logic (via `--db`) gets a non-null `ttl_days` for a purgeable class and NULL otherwise; `sqlite3 "$SCR/mem.db" "delete from memories where content='ttl-probe'; select changes();"` → 1 after the probe was inserted there with that content. The live DB gets no DELETE in S5.
- **Production observation:**
  1. Content proof after the puller — blobs, not ancestry (superscar #9, `scripts/branch_graveyard_cleanup.sh::content_on_main()`), `$WT` on the PR's final head: `[ "$(git -C ~/nuzantara rev-parse HEAD:scripts/memory/mos_retention_purge.py)" = "$(git -C "$WT" rev-parse HEAD:scripts/memory/mos_retention_purge.py)" ] && echo live`; repeat with `scripts/mos-plus-compression-worker.py`.
  2. On a fresh scratch copy of the live DB, `python3 ~/nuzantara/scripts/memory/mos_retention_purge.py --db "$SCR/mem.db" --ruling ~/nuzantara/evidence/2026-09/agent-nuzantara-db-s5-memory-lifecycle-de478768/ruling.yml` (the deployed tool, dry-run, the default ruling passed explicitly) prints per-class counts, and the gate — independently, with its own SQL on the same copy — reproduces them and signs them.
  3. **Live consumer.** `cp ~/scripts/mos-plus-compression-worker.py ~/scripts/mos-plus-compression-worker.py.pre-s5 && cp ~/nuzantara/scripts/mos-plus-compression-worker.py ~/scripts/mos-plus-compression-worker.py`, then `[ "$(cat ~/scripts/mos-plus-compression-worker.py | shasum -a 256)" = "$(git -C ~/nuzantara show HEAD:scripts/mos-plus-compression-worker.py | shasum -a 256)" ] && echo home-live`. The daemon starts a fresh process every 1800 s, so its next run executes the new file: `launchctl print gui/$(id -u)/com.balizero.mos-plus.compression | grep -E '^\s*(runs|last exit code) ='` shows `runs` incremented with exit 0, and `~/logs/mos-plus-compression.log` has a line newer than the cp. Inert: `sqlite3 ~/.claude/memory.db "select count(*) from memories where ttl_days is not null;"` → still 0 (a read-only count).

  Fixture success never stands in for this observation.

## 5. Team

Every seat comes from the colour table (`docs/architecture/dual-consul/army-map.md` §1bis, its only copy).

- **BLUE:** Dux and release owner, this window (Opus 5 `xhigh`). Implementer Sonnet 5, pinned in every Agent call (`model: "sonnet"`); supports on Haiku 4.5 (`model: "haiku"`); an unpinned child inherits the Dux's model. Adversarial reviewer: an independent Codex seat outside the chain (`.claude/scripts/codex-spalla.sh`; `docs/codex/CODEX_SPALLA.md`), reading the frozen diff itself. Final on-disk gate: a FRESH Opus 5 `xhigh` session outside the chain, commissioned by this top-level Dux (modus SKILL, "Gate commission depth").
- **Independence on the numbers.** The gate re-runs the dry-run itself on the verified scratch copy and signs the per-class counts. The generator's SQL is never its own check, and the gate never runs `--apply`.
- **Routing floor:** one lane (the purge tool's tests) goes through Kimi or GLM, prepare-only, own worktree — not Codex.
- **ORANGE**, only if declared before opening: every seat from §1bis. A dead seat suspends the mission.
- Record effective model, effort and thread ids in `brief.yml` at start.

## 6. Appetite and stop-loss

- **Budget:** 8 h, 2 rounds, 2.5M tokens, declared as `appetite:` in `brief.yml`; `spend:` in `pack.yml` (`scripts/evidence_pack_lint.py` rule 14).
- **Deadline:** open + 8 h. ONE mission deadline, owned by the root mandate and read through `infra/codex-hooks/mandate_budget.py` (the spec's `scripts/mandate_budget.py` does not exist). The staff room can renew it once; on expiry the mission suspends.
- **Limits:** three reds on one cause → suspend; fix-of-a-fix depth 1; at most 2 children, depth 1, 1 hop; N = 0 ship reserve — a capped child checkpoints and returns; child active time reported separately.
- **Checkpoints — published, then delivered** (`docs/architecture/dual-consul/army-map.md:81-90`: a file written is published, not delivered; the sender owns the wake-up):
  1. Publish: `scripts/fleet_mail.sh local broadcast --key S5-checkpoint --ttl 24 "$STATE"` (`$STATE` = one line of state, no PII; `local` is Pro). Record the file name it prints in parentheses as the envelope id.
  2. Wake up: `SendMessage` the same text, quoting the envelope id, to the staff-room Claude window Zero names when he opens this window (today `website-03`). On ORANGE the Dux Sol has no `SendMessage`: it tells Zero, who opened the staff-room window, which mailbox file to point that window at (the Codex-peer route, `army-map.md:85-86`).
  3. Ack: the staff room answers with key `S5-ack` in the Pro mailbox, or a session reply, within 15 minutes of wall clock, quoting the same envelope id back (`army-map.md:87`). An ack without the id does not count.
  4. No ack → one retry with the same text and envelope id; still none → a `BLOCKED: undelivered` ledger row and the mission suspends. Never a silent wait.
- **Backup first — documented here, executed by S5b.** The pack carries this procedure for S5b; S5 runs none of it.
  1. Destination: the EXISTING `~/.claude/backups/`, never a new directory: `BK=~/.claude/backups/memory_presurgery_$(date -u +%Y%m%dT%H%M%SZ).db`. The `memory_*.db` name puts it under C2.14's prune: deletion date = its mtime + 30 days, at the next Sunday 05:00 UTC run. Record that date in the pack and in S5b's ledger row.
  2. `sqlite3 ~/.claude/memory.db ".backup '$BK'"` (the online backup API, never `cp` of a live database), then `chmod 600 "$BK"` explicitly: the directory is 0755 today, and `mkdir -m` would not fix an existing directory.
  3. `sqlite3 "$BK" "PRAGMA integrity_check;"` → ok; per-table counts match; record `select max(id) from memories` and `select max(id) from raw_observations` on the backup as the two backup max ids.
  4. The archive is a table inside memory.db (§3), so the cut creates no other copy.
- **Stop and escalate if:** a change would make the worker write a non-null ttl or delete a row without a ruling file; the daemon's first run on the new file exits non-zero; a scratch copy lands inside a repo or a synced folder; osint content already sits in a repo file (report where, never what); three reds on one cause.

## 7. Evidence and release

- **Evidence:** `cd "$WT" && python3 scripts/ci/evidence_paths.py --ref "$(git rev-parse --abbrev-ref HEAD)"` names the directory for `brief.yml` (gear, appetite, team with thread ids, four timestamped sibling outputs: open PRs' paths, `python3 scripts/agent_start.py --list`, `ListAgents`, `scripts/fleet_mail.sh local --list`) and `pack.yml` (at Gear 3: the signed dry-run counts, the test ruling file's hash, the scratch-copy deletion log, the HOME cp log with pre- and post-cp sha256, the S5b backup and rollback procedures). **Every PR** carries `Bites:` (Builder Contract rule 2): the mechanism PR names the compression daemon's next run on the copied HOME worker (sha256 == repo blob); the ledger-only PR names `scripts/pending_arms_report.py`, observed as `python3 scripts/pending_arms_report.py --json --ref origin/main` listing the new row after the merge.
- **Release**, three separate commands: `git -C "$WT" push -u origin HEAD`; `cd "$WT" && gh pr create --title "$TITLE" --body-file "$BODY"`; `gh pr merge "$PR" --auto` at once (`$TITLE` and `$BODY` = the Dux's title and body file; `$PR` = the number `gh pr create` printed). Bare `--auto`: the queue rejects every strategy flag (`docs/runbooks/merge-queue-discipline.md:274-278`; `scripts/queue_shepherd.py:819-821`). The `harness/fable-gate` success must sit on the real head sha.
- **Gate receipt:** a PR comment with mission id, colour, HEAD sha, gate thread id, commands with exit codes, verdict; re-checked against the current HEAD before posting. Publish: `HEAD=$(gh pr view "$PR" --json headRefOid --jq .headRefOid)`, then `python3 scripts/harness_fable_gate.py --verdict PASS --sha "$HEAD" --description "$RECEIPT"` (`$RECEIPT` = the receipt comment's short reference, ≤140 characters).
- **Merge order:** (1) the mechanism PR (worker ttl logic + dry-run tool); (2) after the puller, the HOME worker `cp`, its sha256 proof and the daemon's next run (§4 step 3); (3) the gate signs the production dry-run (§4 step 2); (4) the ledger-only PR: the `~/.claude` remote question. Everything after that is S5b.
- **Rollback trigger (S5):** the daemon's run on the new file exits non-zero, a non-null ttl appears without a ruling file, or the deployed tool's dry-run disagrees with the gate's counts → `cp ~/scripts/mos-plus-compression-worker.py.pre-s5 ~/scripts/mos-plus-compression-worker.py`, then a revert PR from a fresh origin/main.
- **Rollback procedure for S5b (documented here).** Quiescence = compression daemon paused AND no `mem` writes AND no capture-hook writes. The three capture hooks (§1 Ground) INSERT into `raw_observations` from every live Claude session — the S5b window's own tool calls included — and have no kill switch, so expect a delta. `.restore` from `$BK` (§6) only if `max(id)` of BOTH `memories` and `raw_observations` still equals the backup's; otherwise export both deltas (rows with id above each table's backup max) to a scratch directory, restore, re-insert them, and re-run `PRAGMA integrity_check`.

## Adversarial review

**Seat:** Codex `gpt-5.6-sol`, outside the author chain.

**Round 1 — REWORK.** Doctrine conflict with PARABELLUM → Dux, colour, mission id declared. `agent_start.py` cannot change cwd → `$WT` captured. `merge=union` ledger → rows only in a final ledger-only PR. S5 was gated and startable at once, gave up independence on the irreversible step, and had three proofs that did not falsify (a relative placeholder backup path, a DELETE with no `changes()`, a global count) → fixed in v2, then split in v3.

**Round 2 — REWORK.** Findings on this file:
- **F1 applied:** the Opening row follows the colour.
- **F2 applied:** the Dux role names the pending Astra reading.
- **F5 applied:** §3 freeze rule replaces disarm → merge → push → re-arm.
- **F7 applied:** blob-equality content proof in §4.
- **F8 rejected:** bare `--auto` stays (`merge-queue-discipline.md:274-278`; `queue_shepherd.py:819-821`); modus SKILL.md:100's `--squash` is stale (README).
- **F9 applied:** checkpoints use `local broadcast`; the backup path is a real destination.
- **F12 applied:** tests run with `~/nuzantara/.venv/bin/python3 -m pytest`.
- **F14 applied:** S5 = worker ttl logic + dry-run tool + tests + gate-signed counts on a scratch copy; backup, pause, `--apply`, VACUUM, HOME `cp`, ttl on save, declared pair and ledger → queued S5b — THE CUT; the "next morning" backup proof moved there.
- **F15 applied:** the probe insert/delete runs on a `mktemp -d` scratch copy; the live DB gets no DELETE. S5b's gate re-reads the post-apply state (README).
- **F16 applied:** backup in the existing `~/.claude/backups/` under C2.14's prune (verified in crontab), explicit `chmod 600` (directory is 0755), archive as a table; no `$HOME/memory-surgery`.
- **F17 applied:** quiescence by `max(id)`; `.restore` only if unchanged, otherwise delta export and re-insert.

**Round 3 — REWORK** (on v3 `b701479b33`; 15 RESOLVED, 2 PARTIAL, 3 new blockers). On this file:
- **Blocker 1 applied:** §6 checkpoints are published, woken by `SendMessage`, acked within 15 minutes, retried once, then `BLOCKED: undelivered`.
- **Blocker 3 applied:** the HOME worker `cp` moved from S5b into S5 as the mechanism PR's live consumer. §2 allows that one write; §4 step 3 proves sha256 == repo blob, the daemon's next run (`StartInterval` 1800, fresh process per run) and inertness (no non-null ttl); `Bites:` names the daemon run. S5b keeps backup, pause, `--apply`, VACUUM, ttl on save and the declared-pair widening.
- **F17 partial → applied:** the three capture hooks write `raw_observations` while the daemon is paused, so `.restore` needs `max(id)` of BOTH tables unchanged, otherwise both deltas are exported and re-inserted. The backup records both max ids.
- **F2 partial → applied:** the Astra reading is of this board at a named commit; it covers waves 2 and 3 only (README).

**Final gate 2026-09-11 (Opus 5, fresh):** PASS-WITH-CONDITIONS C1–C7; C2–C6 applied in v5, C1 in the S2 window, C7 done. On this file: C2 (`Bites:` on every PR, §7), C3 (envelope id quoted in message and ack, ORANGE route, §6), C5 (the `ruling.yml` path, `--ruling` passed explicitly in every dry-run, `BK=` defined in §6 before first use, the Wave row's opening trigger), C6 (`$TITLE`/`$BODY` defined, `agent_start.py:2174`).
