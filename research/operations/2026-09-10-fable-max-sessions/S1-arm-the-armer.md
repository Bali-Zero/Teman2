---
title: "S1 — ARM THE ARMER · battle window"
date: 2026-09-10
adversarial_review: codex
---

# S1 — ARM THE ARMER · battle window

| Field | Value |
|---|---|
| Mandate id | **S1** |
| Colour | **BLUE** (the default). Chosen before the window opens; no fallback between colours. |
| Dux role | Opus 5 `xhigh` on BLUE (Sol `gpt-5.6-sol` `xhigh` on ORANGE), appointed by the staff room (Fable 5.1 with Zero; two-imperator approval was not met for wave 1, and no later Astra reading covers it — README). Dux and release owner. |
| Worktree / branch | `agent/nuzantara/ops/s1-arm-the-armer`, created by the command in §1 |
| Wave | 1, in parallel with S2 |
| Opening | The opening follows the colour. BLUE: Zero opens a fresh `claude --model claude-opus-5` window at effort `xhigh` and pastes this file. ORANGE: a Codex window on the Sol seat as army-map §1bis names it ("Sol (`gpt-5.6-sol`) `xhigh`"). The first message restates colour, Dux role, mandate id and worktree path, then executes. |

Opened 2026-09-10 ~22:55 WITA on the v2 text; the v3 corrections below were sent to the running window by the staff room.

## 1. Mandate

S1 · BLUE · **organ: `scripts/queue_shepherd.py` on Pro only** (LaunchAgent `com.nuzantara.queue-shepherd`, every 10 minutes). **Gear:** 2 expected; CI recomputes the floor and the floor wins. **Host:** Pro. The Mini siblings (`scripts/queue_unstick.py`, `scripts/queue_stall_classifier.py` with its notifier `scripts/queue_stall_notify.py`) belong to the queued QUEUE SIBLINGS (Mini) window; this window only NOTES in its pack what they would need.

**Objective:** the re-armer reads its candidates, reports CANNOT-VERIFY with a non-ok heartbeat when it can't, and stops re-arming a PR that went red three times for the same cause. **What success changes:** a GitHub degradation no longer looks like "nothing to do".

**Worktree:** `cd ~/nuzantara && WT=$(python3 scripts/agent_start.py --lane ops --task-id s1-arm-the-armer | awk '/^WORKTREE_READY /{print $2}') && echo "$WT"`. The broker prints one `WORKTREE_READY` line followed by the path and cannot change your cwd (`scripts/agent_start.py:2166-2172`), so every later command is `git -C "$WT" …` or `cd "$WT" && …`; `python3 scripts/agent_start.py --list` recovers the path. One live worktree at a time: a second PR starts after the first merged (`python3 scripts/agent_start.py --release s1-arm-the-armer`, then a fresh origin/main). **Base sha:** record `git -C "$WT" rev-parse HEAD` at open (origin/main was `9b2af5160c` when this was written).

**Ground** (judge 13:02–13:09Z, red-team ~1 h later; re-derive in the first hour and quote your own numbers):
- Dead ticks: `grep -c 'rearmed=0 cancelled=0' ~/logs/queue-shepherd.err.log` against `grep -c '^tick complete' ~/logs/queue-shepherd.err.log` → 1879/1880, then 1880/1881; both grow every 10 minutes.
- `tail -6` of that log → `CANNOT-VERIFY rearm candidates: gh api graphql failed rc=1: gh: HTTP 502`, then `tick complete: rearmed=0 cancelled=0 dry_run=False`.
- Cause: query complexity, not the rate limit. 4741/5000 points remained during a 502, and the error read `Resource limits for this query exceeded`. Plain `gh pr list` stayed healthy (46 open, 0 UNKNOWN).
- Flags: `python3 scripts/queue_shepherd.py --help` → `[--tick] [--report] [--dry-run]`, no `--json`. `--dry-run` alone prints usage and exits 1. `--tick --dry-run` reproduces the 502 but reported `cancelled=6` for runs the live janitor skips: a dry-run tick is not a live tick.
- Deploy path: the LaunchAgent runs from `~/nuzantara`, which `com.nuzantara.git-pull-main.15min` keeps at origin/main.
- #6100 (merged 12:55Z) requires the fable-gate verdict from Gear 2 up; Mini's `gate-verdict-missing` stalls are that rule at work, not a shepherd bug.

## 2. Owned perimeter

- **Writable:** `scripts/queue_shepherd.py` and `scripts/tests/test_queue_shepherd.py`.
- **Forbidden:**
  - the Mini siblings and their `*_cron.sh` wrappers (queued QUEUE SIBLINGS window);
  - `scripts/tg_notify.py` (S4); `.husky/pre-push` (queued PRE-PUSH FLOOR GATE);
  - `.github/workflows/**`, including the auto-merge author allowlist;
  - any PR of another window or author: arming or merging those is outside this perimeter.
- **Shared:** `.claude/skills/modus/PENDING-ARMS.md`, a lockfile (§3).
- `.lane-check.json`'s `scope_globs` only decides whether a check applies (`infra/claude-hooks/lane_check.py`; the spec's `scripts/` path is stale). VERIFY and the gate compare changed paths against this list by hand.
- **Bans:**
  - Never reach a Claude model through a paid per-token Anthropic endpoint (any alias, wrapper, Bedrock or Vertex route). Only the `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN`.
  - No client PII or OSINT in cleartext in any PR body, log, alert, memory, ledger row or report.
  - Off-limits: `zantara_core.py`, `fly.toml`, `.env*`, `apps/bali-intel-scraper/backend/db/migrations/env.py`.
  - Zero's files are never edited: `~/.claude/CLAUDE.md`, branch protection, required contexts. Operator items are filed, never waited on.

## 3. Sibling contract

Frozen before BUILD. Changes go to the staff room through Zero, never window-to-window.

- **The gateway (S1 consumes S4).** The shepherd keeps calling `tg_notify.py` through `--tier`, `--source`, `--dedup-key`; S4 freezes that surface. CANNOT-VERIFY uses one stable key (`queue-shepherd:cannot-verify`): one alert per outage, not per tick.
- **The heartbeat (S1 produces it).** New status strings (e.g. `error` on CANNOT-VERIFY) go through `scripts/lib/heartbeat.py`, which accepts any string. No schema change.
- **Mini.** Nothing here changes what Mini runs. The pack records what the siblings would need (for example the classifier's own checkSuites × checkRuns query) as input for the queued window.
- **The ledger — the one surface all windows share.** `.claude/skills/modus/PENDING-ARMS.md` carries `merge=union`, which GitHub's mergeability ignores (modus SKILL.md:193); #6080 and #6081 went DIRTY that way today. Serialize: rows ONLY in one final, separate, ledger-only PR (one row per operator item), cut from a fresh origin/main after this window's code PR merged. Open it only when `gh pr list --state open --limit 200 --json number,files --jq '[.[]|select(any(.files[];.path==".claude/skills/modus/PENDING-ARMS.md"))|.number]'` prints `[]` and `git -C "$WT" diff origin/main -- .claude/skills/modus/PENDING-ARMS.md` is +N/-0.
- **Freeze.** Once armed, the branch is read-only (Builder Contract rule 1).
  - A **real** DIRTY on an armed PR: close it with a comment naming the successor, cut a fresh branch from origin/main, cherry-pick the same content, then push, create and arm the successor as three separate commands.
  - A **phantom** DIRTY (GitHub reports DIRTY while `gh pr view "$PR" --json autoMergeRequest` still shows it armed): judge the diff, then let the queue cure it by merging.
  - Never `--disable-auto`, merge origin/main, push and re-arm.

## 4. Acceptance

- **Negative:** a unit test injects a failing `gh api graphql` and asserts CANNOT-VERIFY, a non-ok heartbeat and a non-zero exit. A second test gives a PR three reds from ONE cause: it is not re-armed and is marked suspended; three reds from three different causes leave it eligible.
- **Integration:** `cd "$WT" && ~/nuzantara/.venv/bin/python3 -m pytest scripts/tests/test_queue_shepherd.py -q` passes, and `cd "$WT" && python3 scripts/queue_shepherd.py --tick --dry-run` completes the candidate read with no 502 and logs how many candidates it examined.
- **Production observation:**
  1. Puller: `tail -5 ~/logs/pro-git_pull_main/run.log` and `cat ~/.organism/last_seen/pro.git_pull_main.json` show a recent rc=0 and status ok.
  2. Content proof — a squash merge leaves no ancestor to test, so compare blobs (superscar #9, `scripts/branch_graveyard_cleanup.sh::content_on_main()`), with `$WT` still on the PR's final head: `[ "$(git -C ~/nuzantara rev-parse HEAD:scripts/queue_shepherd.py)" = "$(git -C "$WT" rev-parse HEAD:scripts/queue_shepherd.py)" ] && echo live`.
  3. Six consecutive scheduled `tick complete` lines (~60 minutes), each with an examined count and none saying CANNOT-VERIFY. Report them through the §6 checkpoint procedure; the staff room's ack of that report is one of wave 2's triggers.

  `rearmed=0` is legitimate only next to an examined count. A PR ejected for a non-INFRA reason is never auto-rearmed by design (#6099 was ejected with `reason=merged`). Fixture success never stands in for this observation.

## 5. Team

Every seat comes from the colour table (`docs/architecture/dual-consul/army-map.md` §1bis, its only copy).

- **BLUE:**
  - **Dux and release owner:** this window, Opus 5 `xhigh`.
  - **Implementer:** Sonnet 5, pinned in every Agent call (`model: "sonnet"`); supports on Haiku 4.5 (`model: "haiku"`). An unpinned child inherits the Dux's model.
  - **Adversarial reviewer:** an independent Codex seat outside the contribution chain (`.claude/scripts/codex-spalla.sh`; `docs/codex/CODEX_SPALLA.md`), reading the frozen diff itself, never a summary.
  - **Final on-disk gate:** a FRESH Opus 5 `xhigh` session outside the chain, commissioned by this top-level Dux (modus SKILL, "Gate commission depth"). It only signs.
- **Routing floor:** S1 ships one code PR plus the ledger-only PR. If the Dux splits the code into two PRs, army-map §3 step 5 routes one lane through Kimi or GLM (prepare-only, own worktree), not Codex, so the reviewer stays cross-family.
- **ORANGE**, only if declared before opening: every seat from §1bis. A dead seat suspends the mission.
- Record each seat's effective model, effort and thread id in `brief.yml` at start.

## 6. Appetite and stop-loss

- **Budget:** 6 h, 2 adversarial rounds, 2.5M tokens. Declare `appetite: {wall_clock_hours: 6, adversarial_rounds: 2, tokens: 2500000}` in `brief.yml`; report `spend:` in `pack.yml` (rule 14 of `scripts/evidence_pack_lint.py` fails an unacknowledged overrun).
- **Deadline:** open + 6 h. ONE mission deadline, owned by the root mandate and read through `infra/codex-hooks/mandate_budget.py` (the spec's `scripts/mandate_budget.py` does not exist). Continuations inherit it; the staff room may renew it once, explicitly. On expiry the mission suspends.
- **Limits:** three reds for one cause → suspend and write the spec; fix-of-a-fix depth 1; at most 2 children, depth 1; at most 1 continuation hop.
- **Adapter tool ceiling, no ship reserve (N = 0):** a child at its cap checkpoints and returns the remaining work; shipping is the Dux's and comes out of this budget. Child active time is reported apart from wall clock.
- **Checkpoints — published, then delivered** (`docs/architecture/dual-consul/army-map.md:81-90`: a file written is published, not delivered; the sender owns the wake-up):
  1. Publish: `scripts/fleet_mail.sh local broadcast --key S1-checkpoint --ttl 24 "$STATE"` (`$STATE` = one line of state, no PII; `local` is Pro). Record the file name it prints in parentheses as the envelope id.
  2. Wake up: `SendMessage` the same text and envelope id to the staff-room Claude window Zero names when he opens this window (today `website-03`).
  3. Ack: the staff room answers with key `S1-ack` in the Pro mailbox, or a session reply, within 15 minutes of wall clock.
  4. No ack → one retry with the same text and envelope id; still none → a `BLOCKED: undelivered` ledger row and the mission suspends. Never a silent wait.
- **Stop and file a row if:** the query fix needs a change on GitHub's side; three reds for the same cause; you want to widen the allowlist or arm someone else's PR; a change would alter what a required context means.

## 7. Evidence and release

- **Evidence:** `cd "$WT" && python3 scripts/ci/evidence_paths.py --ref "$(git rev-parse --abbrev-ref HEAD)"` names the directory for `pack.yml` and `brief.yml`. `brief.yml` holds gear, appetite, team with thread ids, and four timestamped sibling outputs: open PRs' changed paths, `python3 scripts/agent_start.py --list`, `ListAgents`, `scripts/fleet_mail.sh local --list`. The pack also carries the Mini-sibling notes (§3).
- Every code PR body carries a `Bites:` line naming the consumer and the observation.
- **Release**, three separate commands: `git -C "$WT" push -u origin HEAD`; `cd "$WT" && gh pr create --title "$TITLE" --body-file "$BODY"`; `gh pr merge "$PR" --auto` at once. `$TITLE` and `$BODY` are the Dux's title and body file; `$PR` is the number `gh pr create` printed. Bare `--auto`: the queue rejects every strategy flag, `--squash` included (`docs/runbooks/merge-queue-discipline.md:274-278`; `scripts/queue_shepherd.py:819-821`). Confirm with `gh pr view "$PR" --json autoMergeRequest,mergeStateStatus`. At Gear 2 and above, `Harness floor recompute` stays red until a `harness/fable-gate` success sits on the real head sha.
- **Gate receipt:** a PR comment with mission id, colour, HEAD sha, gate thread id, commands with exit codes, and verdict, re-checked against the current PR HEAD before posting (a changed head voids it). Publish: `HEAD=$(gh pr view "$PR" --json headRefOid --jq .headRefOid)`, then `python3 scripts/harness_fable_gate.py --verdict PASS --sha "$HEAD" --description "$RECEIPT"`, with `$RECEIPT` the receipt comment's short reference (≤140 characters). PASS-WITH-CONDITIONS requires `--conditions-ref`.
- **Merge order:** (1) the shepherd PR; (2) the ledger-only PR, carrying the Dependabot ruling for #5528/#5529 and any promotion request. No backend paths.
- **Deploy path:** puller (≤15 minutes), then the next tick (≤10 minutes).
- **Rollback trigger:** a tick re-arms a PR the classifier marks CODE, CONFLICT or MANUAL, or two consecutive ticks error after the merge. Revert through a PR cut from a fresh origin/main.
- **Wave note:** wave 2 opens only after this PR is MERGED, pulled on Pro (puller rc=0) and the staff room has acked this window's six-clean-ticks checkpoint (§4, §6). "Armed" is not enough: an armed PR still runs the old re-armer.

## Adversarial review

**Seat:** Codex `gpt-5.6-sol`, outside the author chain.

**Round 1 — REWORK.** Doctrine conflict with PARABELLUM (Fable implementing; no Dux, colour or mission id) → declared. `agent_start.py` cannot change the caller's cwd → `$WT` captured and used everywhere. The `merge=union` ledger made "disjoint files" false → rows only in a final ledger-only PR. S1 carried 4–5 PRs and other authors' PRs → narrowed.

**Round 2 — REWORK.** Findings on this file:
- **F1 applied:** the Opening row follows the colour.
- **F2 applied:** the Dux role names the pending Astra reading.
- **F4 applied:** wave note and §4 step 3 — merged + pulled + six clean ticks.
- **F5 applied:** §3 freeze rule replaces disarm → merge → push → re-arm.
- **F6 applied:** perimeter = `scripts/queue_shepherd.py` and its test; the Mini siblings are the queued QUEUE SIBLINGS (Mini) window, noted in the pack only.
- **F7 applied:** blob-equality content proof replaces `merge-base --is-ancestor`.
- **F8 rejected:** bare `gh pr merge "$PR" --auto` stays. The queue rejects every strategy flag (`merge-queue-discipline.md:274-278`, measured on PR #3347; `queue_shepherd.py:819-821`). modus SKILL.md:100 does say `--auto --squash`, but that line predates the queue (README, Doctrine gaps).
- **F9 applied:** checkpoints use `local broadcast`; no placeholder remains in any command.
- **F12 applied:** tests run with `~/nuzantara/.venv/bin/python3 -m pytest`.

**Round 3 — REWORK** (on v3 `b701479b33`; 15 RESOLVED, 2 PARTIAL, 3 new blockers). On this file:
- **Blocker 1 applied:** §6 checkpoints are published, woken by `SendMessage`, acked within 15 minutes, retried once, then `BLOCKED: undelivered`; the wave-2 trigger (§4 step 3, §7 wave note) is the staff room's ack.
- **F2 partial → applied:** the Dux role says two-imperator approval was not met for wave 1 and no later reading covers it.
