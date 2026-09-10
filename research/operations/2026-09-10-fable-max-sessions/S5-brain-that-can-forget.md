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
| Dux role | Opus 5 `xhigh` on BLUE (Sol `gpt-5.6-sol` `xhigh` on ORANGE), appointed by the staff room (Fable 5.1 with Zero; Astra reading pending — README). Dux and release owner. |
| Worktree / branch | `agent/nuzantara/db/s5-memory-lifecycle`, created by the command in §1 |
| Wave | 3. Never alongside the queued REAPER window: both change closure semantics. |
| Opening | The opening follows the colour. BLUE: Zero opens a fresh `claude --model claude-opus-5` window at effort `xhigh` and pastes this file. ORANGE: a Codex window on the Sol seat as army-map §1bis names it ("Sol (`gpt-5.6-sol`) `xhigh`"). The first message restates colour, Dux role, mandate id and worktree path, then executes. |

## 1. Mandate

S5 · BLUE · **organ: the MOS memory store** — `~/.claude/memory.db`, its compression worker (repo `scripts/mos-plus-compression-worker.py`, run live by `com.balizero.mos-plus.compression` from the HOME copy `~/scripts/mos-plus-compression-worker.py`), the nightly TTL sweep (cron C2.15) and the `mem` save path. **This window ships the MECHANISM only.** Everything irreversible — backup, pause, `--apply`, VACUUM, the HOME `cp`, ttl on save, the declared-pair PR — belongs to the queued window **S5b — THE CUT** (README), which opens after Zero's retention ruling. **Gear:** 3 by triage (the tool it ships is the instrument of an irreversible cut); CI's floor never lowers it; Evidence Pack required. **Host:** Pro only.

**Objective:** the worker's ttl logic and a retention tool `scripts/memory/mos_retention_purge.py` (to be created) whose dry-run per-class counts, on a verified scratch copy of the live DB, are signed by an independent gate. **What success changes:** S5b can cut the moment Zero rules, on signed numbers rather than on a generator's own SQL. Nothing live changes in S5.

**The ruling is an input, not a precondition.** The tool reads a ruling file; with none it refuses `--apply`. A ttl backfill on existing rows counts as a DELETE (C2.15 deletes every expired row that same night) and belongs to S5b. Default proposed to Zero: processed raw_observations older than 30 days purgeable; osint_sensitive rows older than 7 days purgeable; unresolved memories older than 90 days archived, not deleted.

**Worktree:** `cd ~/nuzantara && WT=$(python3 scripts/agent_start.py --lane db --task-id s5-memory-lifecycle | awk '/^WORKTREE_READY /{print $2}') && echo "$WT"`. The broker prints one `WORKTREE_READY` line followed by the path and cannot change your cwd (`scripts/agent_start.py:2166-2172`): every later command is `git -C "$WT" …` or `cd "$WT" && …`; `--list` recovers the path. One live worktree at a time, `--release` between PRs. `mos` is not a known lane. **Base sha:** record `git -C "$WT" rev-parse HEAD` at open.

**Ground** (counts 13:05Z, schema and crontab ~13:35Z, backups ~15:40Z; re-read all of it, never printing row content):
- **Counts** (memories, ttl set, superseded, raw_observations, processed, osint): `15842|0|0|313956|306884|1452`.
- **Schema** (`sqlite3 ~/.claude/memory.db ".schema memories" ".schema raw_observations"`): `memories` has `id INTEGER PRIMARY KEY AUTOINCREMENT`, `created_at`, `type` ∈ {decision, discovery, fact, pattern, unresolved}, `ttl_days`, `superseded_by`; `raw_observations` has `captured_at`, `payload_json`, `osint_sensitive`, `compressed_to_memory_id`, `discarded_at`.
- **C2.15** (daily 05:00 UTC): `DELETE FROM memories WHERE ttl_days IS NOT NULL AND julianday("now") - julianday(created_at) > ttl_days`. It matches zero rows and still reports ok; a bare sqlite3 DELETE prints nothing, so counts need `SELECT changes();`.
- **C2.13** (daily 04:00 UTC) `cp`s the live DB to `~/.claude/backups/memory_YYYYMMDD.db`. **C2.14** (Sundays 05:00 UTC) runs `find ~/.claude/backups -name "memory_*.db" -mtime +30 -delete`; it does not match the `-shm`/`-wal` sidecars (present for three dates today). `~/.claude/backups` is mode 0755; the backup files are 0600.
- **The save path has no PR path.** `~/.claude/scripts/mem` inserts only (session_id, type, content, importance) and has no database-path override; `git -C ~/.claude remote -v` is empty.
- **Live writer.** `lsof ~/.claude/memory.db` shows `com.balizero.mos-plus.compression` executing the HOME copy. Its declared pair has `machines: []`; widen it to `["pro"]` only once the fixed file is copied and sha256-identical (S5b).

## 2. Owned perimeter

- **Writable (repo only):** `scripts/mos-plus-compression-worker.py` and `scripts/tests/test_mos_plus_compression_worker.py`; `scripts/memory/mos_retention_purge.py` (to be created) and its tests — dry-run by default, `--db` path flag (to be created), `--apply` refuses without a ruling file.
- **Read-only on live state:** `sqlite3 ~/.claude/memory.db ".backup …"` into a scratch directory, `.schema`, `count(*)` and `max(id)` queries. No other access to the live DB.
- **Forbidden:** any write, DELETE, ttl update or VACUUM on `~/.claude/memory.db`; the HOME worker copy; `~/.claude/scripts/mem`; pausing the compression LaunchAgent; `infra/home-fork/declared-pairs.json` (all S5b); existing backups in `~/.claude/backups/`; the recall and lifecycle guards and any `settings.json` (queued MEMORY GUARD); M5 and Mini; PENDING-ARMS structure; printing `payload_json` or any row content, ever.
- **Shared:** the ledger (§3).
- `.lane-check.json`'s `scope_globs` only decides whether a check applies (`infra/claude-hooks/lane_check.py`; the spec's `scripts/` path is stale). VERIFY and the gate compare changed paths against this list by hand.
- **Bans:** no Claude model through a paid per-token Anthropic endpoint (any alias, wrapper, Bedrock or Vertex route; only the `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN`). No client PII or OSINT in cleartext. Off-limits: `zantara_core.py`, `fly.toml`, `.env*`, `apps/bali-intel-scraper/backend/db/migrations/env.py`. Zero's files never edited.

## 3. Sibling contract

Frozen before BUILD. Changes go to the staff room through Zero.

- **Predicates.** The tool's per-class predicates are exactly the ruling file's, recorded by sha256 in the evidence pack. `--dry-run` prints per-class counts; `--apply` prints `changes()` per class and exits non-zero on any mismatch with the gate-signed dry-run.
- **Archive, not delete.** Rows ruled "archive" move to an archive TABLE inside memory.db — never a dated cleartext file — and never reach a DELETE. The FTS triggers (`memories_ad`) stay consistent; the recall hook and `mem query` keep working.
- **C2.15 keeps its shape.** A row gets a ttl only if its class was ruled purgeable.
- **No other window writes memory.db**, and S5 writes it not at all.
- **The ledger — the one surface all windows share.** `.claude/skills/modus/PENDING-ARMS.md` carries `merge=union`, which GitHub's mergeability ignores (modus SKILL.md:193). Serialize: rows ONLY in one final, separate, ledger-only PR, cut from a fresh origin/main after the code PR merged. Open it only when `gh pr list --state open --limit 200 --json number,files --jq '[.[]|select(any(.files[];.path==".claude/skills/modus/PENDING-ARMS.md"))|.number]'` prints `[]` and `git -C "$WT" diff origin/main -- .claude/skills/modus/PENDING-ARMS.md` is +N/-0.
- **Freeze.** Once armed, the branch is read-only (Builder Contract rule 1). A **real** DIRTY on an armed PR: close it with a comment naming the successor, cut a fresh branch from origin/main, cherry-pick the same content, then push, create and arm the successor as three separate commands. A **phantom** DIRTY (GitHub reports DIRTY while `gh pr view "$PR" --json autoMergeRequest` still shows it armed): judge the diff, then let the queue cure it. Never `--disable-auto`, merge origin/main, push and re-arm.

## 4. Acceptance

Every check that inserts, updates or deletes runs on a **scratch copy**, never on the live DB. Make one with `SCR=$(mktemp -d); sqlite3 ~/.claude/memory.db ".backup '$SCR/mem.db'"; chmod 600 "$SCR/mem.db"; sqlite3 "$SCR/mem.db" "PRAGMA integrity_check;"` → ok. The copy is sensitive: `rm -rf "$SCR"` before the session ends, and log the deletion in the pack.

- **Negative:** `--apply` with no ruling file exits non-zero, and `select count(*) from memories` on the scratch copy is the same before and after. If the tool's dry-run and the gate's own counts disagree on any class, `--apply` refuses.
- **Integration (scratch only):** `cd "$WT" && ~/nuzantara/.venv/bin/python3 -m pytest scripts/tests/test_mos_plus_compression_worker.py -q` plus the tool's tests pass. Then, on `$SCR/mem.db` with a test ruling file: a probe row written through the worker's ttl logic (via `--db`) gets a non-null `ttl_days` for a purgeable class and NULL otherwise; `sqlite3 "$SCR/mem.db" "delete from memories where content='ttl-probe'; select changes();"` → 1 after the probe was inserted there with that content. The live DB gets no DELETE in S5.
- **Production observation:**
  1. Content proof after the puller — blobs, not ancestry (superscar #9, `scripts/branch_graveyard_cleanup.sh::content_on_main()`), `$WT` on the PR's final head: `[ "$(git -C ~/nuzantara rev-parse HEAD:scripts/memory/mos_retention_purge.py)" = "$(git -C "$WT" rev-parse HEAD:scripts/memory/mos_retention_purge.py)" ] && echo live`.
  2. On a fresh scratch copy of the live DB, `python3 ~/nuzantara/scripts/memory/mos_retention_purge.py --db "$SCR/mem.db"` (the deployed tool, dry-run) prints per-class counts, and the gate — independently, with its own SQL on the same copy — reproduces them and signs them.
  3. Nothing live moved: `shasum -a 256 ~/scripts/mos-plus-compression-worker.py` is unchanged from open, and `lsof ~/.claude/memory.db` still shows only the compression daemon and normal readers.

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
- **Checkpoints:** `scripts/fleet_mail.sh local broadcast --key S5-checkpoint --ttl 24 "$STATE"`, where `$STATE` is one line of state with no PII. `local` is Pro; the staff room reads the Pro mailbox.
- **Backup first — documented here, executed by S5b.** The pack carries this procedure for S5b; S5 runs none of it.
  1. Destination: the EXISTING `~/.claude/backups/`, never a new directory. Name it `memory_presurgery_$(date -u +%Y%m%dT%H%M%SZ).db` so C2.14's `memory_*.db` prune deletes it: deletion date = its mtime + 30 days, at the next Sunday 05:00 UTC run. Record that date in the pack and in S5b's ledger row.
  2. `sqlite3 ~/.claude/memory.db ".backup '$BK'"` (the online backup API, never `cp` of a live database), then `chmod 600 "$BK"` explicitly: the directory is 0755 today, and `mkdir -m` would not fix an existing directory.
  3. `sqlite3 "$BK" "PRAGMA integrity_check;"` → ok; per-table counts match; record `select max(id) from memories` on the backup as the backup's max id.
  4. The archive is a table inside memory.db (§3), so the cut creates no other copy.
- **Stop and escalate if:** a change would write the live DB; a scratch copy lands inside a repo or a synced folder; osint content already sits in a repo file (report where, never what); three reds on one cause.

## 7. Evidence and release

- **Evidence:** `cd "$WT" && python3 scripts/ci/evidence_paths.py --ref "$(git rev-parse --abbrev-ref HEAD)"` names the directory for `brief.yml` (gear, appetite, team with thread ids, four timestamped sibling outputs: open PRs' paths, `python3 scripts/agent_start.py --list`, `ListAgents`, `scripts/fleet_mail.sh local --list`) and `pack.yml` (at Gear 3: the signed dry-run counts, the test ruling file's hash, the scratch-copy deletion log, the S5b backup and rollback procedures). Every code PR carries `Bites:`.
- **Release**, three separate commands: `git -C "$WT" push -u origin HEAD`; `cd "$WT" && gh pr create --title "$TITLE" --body-file "$BODY"`; `gh pr merge "$PR" --auto` at once (`$PR` = the number `gh pr create` printed). Bare `--auto`: the queue rejects every strategy flag (`docs/runbooks/merge-queue-discipline.md:274-278`; `scripts/queue_shepherd.py:819-821`). The `harness/fable-gate` success must sit on the real head sha.
- **Gate receipt:** a PR comment with mission id, colour, HEAD sha, gate thread id, commands with exit codes, verdict; re-checked against the current HEAD before posting. Publish: `HEAD=$(gh pr view "$PR" --json headRefOid --jq .headRefOid)`, then `python3 scripts/harness_fable_gate.py --verdict PASS --sha "$HEAD" --description "$RECEIPT"` (`$RECEIPT` = the receipt comment's short reference, ≤140 characters).
- **Merge order:** (1) the mechanism PR (worker ttl logic + dry-run tool); (2) the gate signs the production dry-run (§4); (3) the ledger-only PR: the `~/.claude` remote question. Everything after that is S5b.
- **Rollback trigger (S5):** the deployed tool's dry-run disagrees with the gate's counts, or any live-DB write is traced to this window → revert PR from a fresh origin/main.
- **Rollback procedure for S5b (documented here).** Quiescence = compression daemon paused AND no `mem` writes, checked by `select max(id) from memories` before and after the cut. `.restore` from the backup only if the live max id is still the backup's max id. Otherwise export the delta rows (id above the backup's max id) to a scratch directory, restore, re-insert them, and re-run `PRAGMA integrity_check`.

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
