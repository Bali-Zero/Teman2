---
title: "S3 — ARM THE AUDITOR · battle window"
date: 2026-09-10
adversarial_review: codex
---

# S3 — ARM THE AUDITOR · battle window

| Field | Value |
|---|---|
| Mandate id | **S3** |
| Colour | **BLUE** unless Zero declares ORANGE before the window opens. No fallback between colours. |
| Dux role | Opus 5 `xhigh` on BLUE (Sol `gpt-5.6-sol` `xhigh` on ORANGE), appointed by the staff room (Fable 5.1 with Zero; the Astra reading of this board at a named commit, or Zero's waiver, is pending — README). Dux and release owner. |
| Worktree / branch | `agent/nuzantara/ops/s3-arm-the-auditor`, created by the command in §1 |
| Wave | 2, in parallel with S4. Opens only after S1's shepherd PR is MERGED, pulled on Pro (puller rc=0), the staff room has acked S1's six-clean-ticks checkpoint, and the Astra reading or its waiver is recorded (README). |
| Opening | The opening follows the colour. BLUE: Zero opens a fresh `claude --model claude-opus-5` window at effort `xhigh` and pastes this file. ORANGE: a Codex window on the Sol seat as army-map §1bis names it ("Sol (`gpt-5.6-sol`) `xhigh`"). The first message restates colour, Dux role, mandate id and worktree path, then executes. |

## 1. Mandate

S3 · BLUE · **organ: proprioception** — script `scripts/proprioception.py`, report `~/.nuzantara-proprioception/last.json`, receptor `scripts/hooks/proprioception_sessionstart.sh`. **Gear:** 2 expected (CI's floor wins). **Host:** Pro. Scar gates, the organ census, the cost guard and the plist linter belong to queued windows (README).

**Objective:** proprioception runs on a schedule and carries ONE re-derivation probe whose first subject is INDEX.md's core-table list. **What success changes:** a P1 divergence reaches the next session's boot whether or not anyone typed the auditor's name, and one hand-written countable claim is re-derived by a machine.

**Worktree:** `cd ~/nuzantara && WT=$(python3 scripts/agent_start.py --lane ops --task-id s3-arm-the-auditor | awk '/^WORKTREE_READY /{print $2}') && echo "$WT"`. The broker prints one `WORKTREE_READY` line followed by the path and cannot change your cwd (`scripts/agent_start.py:2174`): every later command is `git -C "$WT" …` or `cd "$WT" && …`, and `--list` recovers the path. One live worktree at a time: `--release` after each PR merges, then a fresh origin/main. **Base sha:** record `git -C "$WT" rev-parse HEAD` at open.

**Ground** (judge 13:04–13:06Z, red-team ~1 h later, editor ~13:35Z, staff room ~15:40Z; re-derive — counts moved within one day, repo_divergent 4→11, LaunchAgents 71→76):
- **Not scheduled.** `ls ~/Library/LaunchAgents | grep -ci propriocep` → 0; `crontab -l | grep -ci propriocep` → 0.
- **The receptor is the mechanical consumer.** It prints a one-line heartbeat for a fresh report and goes LOUD when `last.json` is missing or older than 48 h (test override `PROPRIOCEPTION_REPORT_PATH`).
- **CLI.** `python3 scripts/proprioception.py --help` → `[--json] [--fleet] [--no-report] [--no-fetch] [--tags TAGS] [--probes PROBES] [--strict] [--selftest]`; the report is written unless `--no-report`.
- **No invocation field.** `last.json`'s top-level keys are `config_sha, config_source, machine, probes, probes_expected, probes_run, repo_head, runner_blob, runner_version, schema, summary, ts, unwatched_classes`: nothing says who ran it, and its mtime proves nothing about launchd.
- **Phantom tables.** INDEX.md:71 lists fifteen core tables; six (articles, crm_clients, crm_practices, messages, routing_stats, failed_queries) return exists=false against prod `information_schema.tables` (via `scripts/pg.sh`).
- **Existing pattern.** `scripts/check_autonomous_ops_staleness.py` already re-derives a claim for one file.
- **Blocking PRs.** #6101 (launchd canon) merged 2026-09-10T14:24Z. #6054 (edits `scripts/proprioception.py` for the child calibration receptor) was open at 15:40Z.

## 2. Owned perimeter

- **Writable:**
  - one new canon plist `infra/launchagents/com.nuzantara.proprioception.plist` (to be created; label `com.nuzantara.proprioception`), which also sets the env var `PROPRIOCEPTION_INVOKED_BY=launchd` (to be created; not a credential);
  - `scripts/proprioception.py`, only after #6054 merged, only for the new probe, its registration, and one additive top-level report key `invoked_by` read from that env var (to be created);
  - the probe's tests under `scripts/tests/`;
  - INDEX.md, only the table list on line 71, only in its own PR.
- **Forbidden:** `scripts/verify_the_verifiers_gates.yaml`, `infra/scar-gates/MANIFEST.json`, the decommission manifest, the cost-guard plist, the `_snapshot-live` plists (queued windows or Gear-1 items); `scripts/tg_notify.py` (S4); crontab; changing any existing probe's output; a credential in a plist — if the probe needs a prod DB credential launchd lacks, stop.
- **Shared:** `infra/launchagents/` (convention owner #6101; S2 adds a different plist); `scripts/proprioception.py` (owned by #6054 until it merges); INDEX.md (the atlas: the named line only); the ledger (§3).
- `.lane-check.json`'s `scope_globs` only decides whether a check applies (`infra/claude-hooks/lane_check.py`; the spec's `scripts/` path is stale). VERIFY and the gate compare changed paths against this list by hand.
- **Bans:** no Claude model through a paid per-token Anthropic endpoint (any alias, wrapper, Bedrock or Vertex route; only the `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN`). No client PII or OSINT in cleartext. Off-limits: `zantara_core.py`, `fly.toml`, `.env*`, `apps/bali-intel-scraper/backend/db/migrations/env.py`. Zero's files never edited (`~/.claude/CLAUDE.md` and its daemon count, branch protection, required contexts). Operator items filed, never waited on.

## 3. Sibling contract

Frozen before BUILD. Changes go to the staff room through Zero.

- **Plist.** Exec path `/Users/nuzantara/nuzantara/scripts/proprioception.py`. A live-only edit is reverted by the healer's home-fork refresh: the canon is the change.
- **#6054 and the probe.** The probe PR opens only after #6054 merges and is built from a fresh origin/main. While #6054 is open, comment on it (coordination, not a race) and ship only the schedule.
- **Report schema.** The probe emits the existing finding shape (id, severity, DIVERGED/OK, fix line), so the receptor needs no change. `invoked_by` is additive at top level; a test proves every existing probe's output is unchanged and the receptor still passes `scripts/tests/test_proprioception_receptor_ranking.sh`.
- **Neighbours.** S4 changes nothing proprioception reads; S2 shares only the plist directory.
- **The ledger — the one surface all windows share.** `.claude/skills/modus/PENDING-ARMS.md` carries `merge=union`, which GitHub's mergeability ignores (modus SKILL.md:193); #6080 and #6081 went DIRTY that way. Serialize: rows ONLY in one final, separate, ledger-only PR, cut from a fresh origin/main after the code PRs merged. Open it only when `gh pr list --state open --limit 200 --json number,files --jq '[.[]|select(any(.files[];.path==".claude/skills/modus/PENDING-ARMS.md"))|.number]'` prints `[]` and `git -C "$WT" diff origin/main -- .claude/skills/modus/PENDING-ARMS.md` is +N/-0.
- **Freeze.** Once armed, the branch is read-only (Builder Contract rule 1). A **real** DIRTY on an armed PR: close it with a comment naming the successor, cut a fresh branch from origin/main, cherry-pick the same content, then push, create and arm the successor as three separate commands. A **phantom** DIRTY (GitHub reports DIRTY while `gh pr view "$PR" --json autoMergeRequest` still shows it armed): judge the diff, then let the queue cure it. Never `--disable-auto`, merge origin/main, push and re-arm.

## 4. Acceptance

Four PRs in order; each one's observation is made before the next opens. Attribution to launchd always uses `launchctl print gui/$(id -u)/com.nuzantara.proprioception | grep -E '^\s*(runs|last exit code) ='` — `runs` incremented since your previous read, last exit 0 — never the report's mtime. Always this projection: the full print dumps the job's environment.

1. **Schedule PR** (plist only; #6101 is merged).
   - Production: after the puller, blob proof of the plist (below), install from canon, `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.proprioception.plist`; `launchctl list | grep -c com.nuzantara.proprioception` → 1; `launchctl print gui/$(id -u)/com.nuzantara.proprioception | grep -A3 'arguments = {'` names the main checkout; after the next scheduled run, `runs` went up with exit 0 and `last.json`'s `ts` matches that run; the next session's SessionStart receptor prints a fresh-report line.
2. **Probe PR** (after #6054), registering the probe (proposed id `index_core_tables`, to be created) and `invoked_by`.
   - Negative: on a scratch copy of the INDEX.md list with one invented table the probe reports DIVERGED; on the corrected list, OK. A report older than 48 h makes the receptor LOUD (`scripts/tests/test_proprioception_receptor_ranking.sh`).
   - Integration: `cd "$WT" && ~/nuzantara/.venv/bin/python3 -m pytest scripts/tests -q -k index_core_tables` passes, and `cd "$WT" && python3 scripts/proprioception.py --probes index_core_tables --json` names the six missing tables.
   - Production: the next scheduled run shows the probe **DIVERGED** with `invoked_by` = `launchd`, and `launchctl print` shows `runs` incremented with exit 0.
3. **INDEX.md correction PR** (line 71 only), separate. Production: the next scheduled run shows the probe **OK**.
4. **Ledger-only PR**, only if the window filed anything.

**Content proof** after each merge — blobs, not ancestry (superscar #9, `scripts/branch_graveyard_cleanup.sh::content_on_main()`), `$WT` on that PR's final head: `[ "$(git -C ~/nuzantara rev-parse HEAD:scripts/proprioception.py)" = "$(git -C "$WT" rev-parse HEAD:scripts/proprioception.py)" ] && echo live`, and the same with `infra/launchagents/com.nuzantara.proprioception.plist` and `INDEX.md` for their PRs. Fixture success never stands in for these observations.

## 5. Team

Every seat comes from the colour table (`docs/architecture/dual-consul/army-map.md` §1bis, its only copy).

- **BLUE:** Dux and release owner, this window (Opus 5 `xhigh`). Implementer Sonnet 5, pinned in every Agent call (`model: "sonnet"`); supports on Haiku 4.5 (`model: "haiku"`); an unpinned child inherits the Dux's model. Adversarial reviewer: an independent Codex seat outside the chain (`.claude/scripts/codex-spalla.sh`; `docs/codex/CODEX_SPALLA.md`), reading the frozen diff itself. Final on-disk gate: a FRESH Opus 5 `xhigh` session outside the chain, commissioned by this top-level Dux (modus SKILL, "Gate commission depth"); it only signs.
- **Routing floor:** three code PRs, so one lane (e.g. the probe's tests) goes through Kimi or GLM, prepare-only, own worktree — not Codex.
- **ORANGE**, only if declared before opening: every seat from §1bis. A dead seat suspends the mission.
- Record each seat's effective model, effort and thread id in `brief.yml` at start.

## 6. Appetite and stop-loss

- **Budget:** 5 h, 2 rounds, 1.5M tokens, declared as `appetite:` in `brief.yml`; `spend:` in `pack.yml` (`scripts/evidence_pack_lint.py` rule 14). Steps 2–4 of §4 each wait for a scheduled run: set the plist's interval so they fit, and record the choice.
- **Deadline:** open + 5 h. ONE mission deadline, owned by the root mandate and read through `infra/codex-hooks/mandate_budget.py` (the spec's `scripts/mandate_budget.py` does not exist). Only the staff room renews it, once; on expiry the mission suspends.
- **Limits:** three reds for one cause → suspend; fix-of-a-fix depth 1; at most 2 children, depth 1, 1 continuation hop; adapter tool ceiling with no ship reserve (N = 0); child active time reported separately.
- **Checkpoints — published, then delivered** (`docs/architecture/dual-consul/army-map.md:81-90`: a file written is published, not delivered; the sender owns the wake-up):
  1. Publish: `scripts/fleet_mail.sh local broadcast --key S3-checkpoint --ttl 24 "$STATE"` (`$STATE` = one line of state, no PII; `local` is Pro). Record the file name it prints in parentheses as the envelope id.
  2. Wake up: `SendMessage` the same text, quoting the envelope id, to the staff-room Claude window Zero names when he opens this window (today `website-03`). On ORANGE the Dux Sol has no `SendMessage`: it tells Zero, who opened the staff-room window, which mailbox file to point that window at (the Codex-peer route, `army-map.md:85-86`).
  3. Ack: the staff room answers with key `S3-ack` in the Pro mailbox, or a session reply, within 15 minutes of wall clock, quoting the same envelope id back (`army-map.md:87`). An ack without the id does not count.
  4. No ack → one retry with the same text and envelope id; still none → a `BLOCKED: undelivered` ledger row and the mission suspends. Never a silent wait.
- **Stop and return to the staff room if:** #6054 is still open when the schedule is proven (comment on it, ship nothing more); the probe needs a credential inside launchd; the receptor would have to change; three reds for the same cause.

## 7. Evidence and release

- **Evidence:** `cd "$WT" && python3 scripts/ci/evidence_paths.py --ref "$(git rev-parse --abbrev-ref HEAD)"` prints the directory for `brief.yml` (gear, appetite, team with thread ids, four timestamped sibling outputs: open PRs' paths, `python3 scripts/agent_start.py --list`, `ListAgents`, `scripts/fleet_mail.sh local --list`) and `pack.yml`. **Every PR** carries `Bites:` (Builder Contract rule 2): the schedule and probe PRs name the scheduled run (§4 steps 1–2); the INDEX.md PR names the scheduled run showing the probe OK (§4 step 3); the ledger-only PR names `scripts/pending_arms_report.py`, observed as `python3 scripts/pending_arms_report.py --json --ref origin/main` listing the new rows after the merge.
- **Release**, three separate commands: `git -C "$WT" push -u origin HEAD`; `cd "$WT" && gh pr create --title "$TITLE" --body-file "$BODY"`; `gh pr merge "$PR" --auto` at once (`$TITLE` and `$BODY` = the Dux's title and body file; `$PR` = the number `gh pr create` printed). Bare `--auto`: the queue rejects every strategy flag (`docs/runbooks/merge-queue-discipline.md:274-278`; `scripts/queue_shepherd.py:819-821`). At Gear 2 and above the PR needs a `harness/fable-gate` success on its real head sha.
- **Gate receipt:** a PR comment with mission id, colour, HEAD sha, gate thread id, commands with exit codes, verdict; re-checked against the current HEAD before posting. Publish: `HEAD=$(gh pr view "$PR" --json headRefOid --jq .headRefOid)`, then `python3 scripts/harness_fable_gate.py --verdict PASS --sha "$HEAD" --description "$RECEIPT"` (`$RECEIPT` = the receipt comment's short reference, ≤140 characters).
- **Merge order:** (1) schedule PR; (2) probe PR, after #6054; (3) INDEX.md correction PR, after the DIVERGED observation; (4) ledger-only PR, if anything was filed. No backend path.
- **Deploy:** the puller, then `launchctl bootstrap` of the canon plist, then one `launchctl kickstart -k gui/$(id -u)/com.nuzantara.proprioception`; later PRs ride the puller.
- **Rollback trigger:** the scheduled run exits non-zero twice, runs longer than its own interval, or the new probe floods the receptor with P1s → `launchctl bootout gui/$(id -u)/com.nuzantara.proprioception` plus a revert PR from a fresh origin/main.

## Adversarial review

**Seat:** Codex `gpt-5.6-sol`, outside the author chain.

**Round 1 — REWORK.** Doctrine conflict with PARABELLUM → Dux, colour, mission id declared. `agent_start.py` cannot change cwd → `$WT` captured. `merge=union` ledger → rows only in a final ledger-only PR. S3 spanned five PRs and several organs, and its probe had no mechanical consumer → narrowed to proprioception; the scheduled run and receptor are the consumer.

**Round 2 — REWORK.** Findings on this file:
- **F1 applied:** the Opening row follows the colour.
- **F2 applied:** Dux role and Wave row name the pending Astra reading.
- **F4 applied:** the Wave row requires MERGED + pulled + six clean ticks, not "armed".
- **F5 applied:** §3 freeze rule replaces disarm → merge → push → re-arm.
- **F7 applied:** blob-equality content proofs in §4.
- **F8 rejected:** bare `--auto` stays (`merge-queue-discipline.md:274-278`; `queue_shepherd.py:819-821`); modus SKILL.md:100's `--squash` is stale (README).
- **F9 applied:** checkpoints use `local broadcast`; the label and probe id are real (proposed) values, not placeholders.
- **F11 applied:** schedule PR → probe PR (DIVERGED, attributed via `launchctl print` and `invoked_by`, not mtime) → separate INDEX.md PR (OK) → ledger-only PR; §4 and merge order agree. The report had no invocation field (verified), so the probe PR adds `invoked_by`.
- **F12 applied:** tests run with `~/nuzantara/.venv/bin/python3 -m pytest`.

**Round 3 — REWORK** (on v3 `b701479b33`; 15 RESOLVED, 2 PARTIAL, 3 new blockers). On this file:
- **Blocker 1 applied:** §6 checkpoints are published, woken by `SendMessage`, acked within 15 minutes, retried once, then `BLOCKED: undelivered`. The Wave row waits for the staff room's ack of S1's checkpoint, not for a published file.
- **F2 partial → applied:** the Astra reading is of this board at a named commit; it covers waves 2 and 3 only (README).

**Final gate 2026-09-11 (Opus 5, fresh):** PASS-WITH-CONDITIONS C1–C7; C2–C6 applied in v5, C1 in the S2 window, C7 done. On this file: C2 (`Bites:` on every PR, the INDEX.md and ledger-only PRs included, §7), C3 (envelope id quoted in message and ack, ORANGE route, §6), C6 (`$TITLE`/`$BODY` defined, `agent_start.py:2174`).
