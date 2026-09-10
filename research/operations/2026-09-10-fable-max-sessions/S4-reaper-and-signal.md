---
title: "S4 — THE SIGNAL · battle window"
date: 2026-09-10
adversarial_review: codex
---

# S4 — THE SIGNAL · battle window

The file name is kept for continuity. The reaper half of the old mandate is a queued window of its own (README).

| Field | Value |
|---|---|
| Mandate id | **S4** |
| Colour | **BLUE** unless Zero declares ORANGE before the window opens. No fallback between colours. |
| Dux role | Opus 5 `xhigh` on BLUE (Sol `gpt-5.6-sol` `xhigh` on ORANGE), appointed by the staff room (Fable 5.1 with Zero; Astra reading pending — README). Dux and release owner. |
| Worktree / branch | `agent/nuzantara/ops/s4-the-signal`, created by the command in §1 |
| Wave | 2, in parallel with S3. Opens only after S1's shepherd PR is MERGED, pulled on Pro (puller rc=0), the S1 window has reported six clean ticks, and the Astra reading or its waiver is recorded (README). |
| Opening | The opening follows the colour. BLUE: Zero opens a fresh `claude --model claude-opus-5` window at effort `xhigh` and pastes this file. ORANGE: a Codex window on the Sol seat as army-map §1bis names it ("Sol (`gpt-5.6-sol`) `xhigh`"). The first message restates colour, Dux role, mandate id and worktree path, then executes. |

## 1. Mandate

S4 · BLUE · **organ: the alert path** — the shared gateway `scripts/tg_notify.py` plus its weekly digest (`scripts/escalations_suppressed_digest.py`, launched by `infra/launchd/com.nuzantara.escalations-digest.weekly.plist`, label `com.nuzantara.escalations-digest.weekly`). **Gear:** 2 expected; tg_notify has 29 top-level callers, and if CI floors the change at 3 an Evidence Pack is required. **Host:** Pro.

**Objective — the mute ceiling, numbered:** a p0 key at streak ≥ 4 re-raises **at most once per 6 h and at least once per 24 h** while its condition persists; it also lands in the digest, and the digest is armed. **What success changes:** a condition such as the WhatsApp dead-channel alert can no longer vanish for a week behind the mute ladder.

**Worktree:** `cd ~/nuzantara && WT=$(python3 scripts/agent_start.py --lane ops --task-id s4-the-signal | awk '/^WORKTREE_READY /{print $2}') && echo "$WT"`. The broker prints one `WORKTREE_READY` line followed by the path and cannot change your cwd (`scripts/agent_start.py:2166-2172`): every later command is `git -C "$WT" …` or `cd "$WT" && …`, and `--list` recovers the path. One live worktree at a time, `--release` between PRs. **Base sha:** record `git -C "$WT" rev-parse HEAD` at open.

**Ground** (13:02–13:32Z; re-run all of it):
- **The WhatsApp bot line is quiet by Zero's ruling, not by outage.** PRs #5486 and #5494 (2026-09-01) moved every client invitation to the human line; inbound has been zero since 09-03 and the Fly endpoint is alive. The disease is the silence, not the quiet.
- **One mute ladder for every tier.** `scripts/tg_notify.py` `REPEAT_LADDER_H` (default rungs `TG_DEDUP_HOURS` (6), 24, 72, 168) covers p0 too. In `~/.organism/tg_spool/state.json` at 13:32Z, key `wa-bot:throughput:dead-channel` stood at count 277, streak 4, first sent 2026-09-03T09:31Z, last sent 2026-09-07T15:34Z: muted until ~2026-09-14T15:34Z. Siblings `bot-broken` and `inbound-stale` also at streak 4.
- **The digest is built, not armed.** Its plist is in canon (Sundays 09:07, running `scripts/escalations_digest_cron.sh`) but absent from `~/Library/LaunchAgents`; `launchctl list | grep -c escalations-digest` → 0. The script reads only `escalation_cooldown.json` and `alert_dedup.json`.
- **The bus.** `shared/escalations_pro.jsonl`: 218 rows, 190 pending, 21 HIGH (20 from `healer_pro_tick`).
- **The ledger.** `python3 scripts/pending_arms_report.py --json --ref origin/main` → 802 total, 221 operator-gated and overdue.

## 2. Owned perimeter

- **Writable:** `scripts/tg_notify.py`, `scripts/escalations_suppressed_digest.py`, `scripts/escalations_digest_cron.sh` and their tests (`scripts/tests/test_tg_notify_*`, the digest's tests); installing — not editing — the canon digest plist.
- **Read-only:** `shared/escalations_pro.jsonl`; `pending_arms_report.py --json` output; `~/.organism/tg_spool/state.json` — keys, counts and dates only; its `last_text` field holds message fragments and is never copied anywhere.
- **Forbidden:** the throughput sentinel (queued SENTINEL HONESTY); the bus's structure, terminal states and fingerprints (queued SIGNAL TRIAGE); PENDING-ARMS structure and ledger gates (queued REAPER); SessionStart hooks (queued MEMORY GUARD).
- **Shared:** tg_notify, called by S1, S2 and ~27 other scripts (§3); the ledger.
- `.lane-check.json`'s `scope_globs` only decides whether a check applies (`infra/claude-hooks/lane_check.py`; the spec's `scripts/` path is stale). VERIFY and the gate compare changed paths against this list by hand.
- **Bans:** no Claude model through a paid per-token Anthropic endpoint (any alias, wrapper, Bedrock or Vertex route; only the `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN`). No client PII or OSINT in cleartext. Off-limits: `zantara_core.py`, `fly.toml`, `.env*`, `apps/bali-intel-scraper/backend/db/migrations/env.py`. Zero's files never edited. Operator items filed, never waited on.

## 3. Sibling contract

Frozen before BUILD. Changes go to the staff room through Zero.

- **The gateway surface is frozen:** the CLI (`--tier {p0,digest,log}`, `--source`, `--dedup-key`), `notify(tier, source, text, dedup_key)`, its return values, and the spool and state file formats. The change is tier-scoped and additive: p0 gains the ceiling; digest and log keep their ladder unchanged, and tests prove it. S1 and S2 rely on this surface and change nothing in it.
- **HOME copies.** If `infra/home-fork/declared-pairs.json` declares a HOME copy of tg_notify, prove it byte-identical after the merge.
- **The digest's output contract:** job names, dedup keys, counts and dates. Never `last_text`, row content or a client identifier.
- **The ledger — the one surface all windows share.** `.claude/skills/modus/PENDING-ARMS.md` carries `merge=union`, which GitHub's mergeability ignores (modus SKILL.md:193); #6080 and #6081 went DIRTY that way. Serialize: rows ONLY in one final, separate, ledger-only PR, cut from a fresh origin/main after the code PRs merged. Open it only when `gh pr list --state open --limit 200 --json number,files --jq '[.[]|select(any(.files[];.path==".claude/skills/modus/PENDING-ARMS.md"))|.number]'` prints `[]` and `git -C "$WT" diff origin/main -- .claude/skills/modus/PENDING-ARMS.md` is +N/-0.
- **Freeze.** Once armed, the branch is read-only (Builder Contract rule 1). A **real** DIRTY on an armed PR: close it with a comment naming the successor, cut a fresh branch from origin/main, cherry-pick the same content, then push, create and arm the successor as three separate commands. A **phantom** DIRTY (GitHub reports DIRTY while `gh pr view "$PR" --json autoMergeRequest` still shows it armed): judge the diff, then let the queue cure it. Never `--disable-auto`, merge origin/main, push and re-arm.

## 4. Acceptance

- **Negative:** a test holds a p0 entry at streak ≥ 4: it re-sends once 24 h have passed since its last send and does not re-send when fewer than 6 h have passed. It fails on origin/main and passes on the branch. A second test shows a digest-tier entry at streak 4 stays muted exactly as before.
- **Integration:** `cd "$WT" && ~/nuzantara/.venv/bin/python3 -m pytest scripts/tests/test_tg_notify_identity_ladder.py -q` passes together with the new tests. A dry run of the digest over a scratch copy of `state.json` and the bus lists the muted p0 keys and the HIGH count per job.
- **Production:**
  1. Content proof after the puller — blobs, not ancestry (superscar #9, `scripts/branch_graveyard_cleanup.sh::content_on_main()`), `$WT` on the PR's final head: `[ "$(git -C ~/nuzantara rev-parse HEAD:scripts/tg_notify.py)" = "$(git -C "$WT" rev-parse HEAD:scripts/tg_notify.py)" ] && echo live`.
  2. If the dead-channel condition still persists, the `wa-bot:throughput:dead-channel` last-send timestamp in `state.json` advances within 24 h of the merge, and the next send is at least 6 h later. Paste keys and timestamps only, before and after.
  3. `launchctl list | grep -c com.nuzantara.escalations-digest.weekly` → 1, and one real run started by `launchctl kickstart -k gui/$(id -u)/com.nuzantara.escalations-digest.weekly` delivers a digest listing HIGH by job from the bus, the muted p0 keys, and the count of overdue operator-gated ledger rows by class.

  Fixture success never stands in for these observations.

## 5. Team

Every seat comes from the colour table (`docs/architecture/dual-consul/army-map.md` §1bis, its only copy).

- **BLUE:** Dux and release owner, this window (Opus 5 `xhigh`). Implementer Sonnet 5, pinned in every Agent call (`model: "sonnet"`); supports on Haiku 4.5 (`model: "haiku"`); an unpinned child inherits the Dux's model. Adversarial reviewer: an independent Codex seat outside the chain (`.claude/scripts/codex-spalla.sh`; `docs/codex/CODEX_SPALLA.md`), reading the frozen diff itself. Final on-disk gate: a FRESH Opus 5 `xhigh` session outside the chain, commissioned by this top-level Dux (modus SKILL, "Gate commission depth"); it only signs.
- **Routing floor:** two code PRs, so the digest lane goes through Kimi or GLM, prepare-only, own worktree — not Codex.
- **ORANGE**, only if declared before opening: every seat from §1bis. A dead seat suspends the mission.
- Record each seat's effective model, effort and thread id in `brief.yml` at start.

## 6. Appetite and stop-loss

- **Budget:** 6 h, 2 rounds, 2M tokens, declared as `appetite:` in `brief.yml`; `spend:` in `pack.yml` (`scripts/evidence_pack_lint.py` rule 14).
- **Deadline:** open + 6 h. ONE mission deadline, owned by the root mandate and read through `infra/codex-hooks/mandate_budget.py` (the spec's `scripts/mandate_budget.py` does not exist). The staff room may renew it once; on expiry the mission suspends.
- **Limits:** three reds for the same cause → suspend; fix-of-a-fix depth 1; at most 2 children at depth 1, 1 continuation hop; adapter tool ceiling with no ship reserve (N = 0) — a capped child checkpoints and returns, shipping is the Dux's; child active time reported separately.
- **Checkpoints:** `scripts/fleet_mail.sh local broadcast --key S4-checkpoint --ttl 24 "$STATE"`, where `$STATE` is one line of state with no PII. `local` is Pro; the staff room reads the Pro mailbox.
- **Stop and return to the staff room if:** the fix cannot be tier-scoped; any non-p0 tier changes behaviour; the digest would need PII to be useful; three reds for the same cause.

## 7. Evidence and release

- **Evidence:** `cd "$WT" && python3 scripts/ci/evidence_paths.py --ref "$(git rev-parse --abbrev-ref HEAD)"` returns the directory for `brief.yml` (gear, appetite, team with thread ids, four timestamped sibling outputs: open PRs' paths, `python3 scripts/agent_start.py --list`, `ListAgents`, `scripts/fleet_mail.sh local --list`) and `pack.yml`. Every code PR carries `Bites:`.
- **Release**, three separate commands: `git -C "$WT" push -u origin HEAD`; `cd "$WT" && gh pr create --title "$TITLE" --body-file "$BODY"`; `gh pr merge "$PR" --auto` at once (`$PR` = the number `gh pr create` printed). Bare `--auto`: the queue rejects every strategy flag (`docs/runbooks/merge-queue-discipline.md:274-278`; `scripts/queue_shepherd.py:819-821`). At Gear 2 or 3 the `harness/fable-gate` success must sit on the real head sha.
- **Gate receipt:** a PR comment with mission id, colour, HEAD sha, gate thread id, commands with exit codes, verdict; re-checked against the current HEAD before posting. Publish: `HEAD=$(gh pr view "$PR" --json headRefOid --jq .headRefOid)`, then `python3 scripts/harness_fable_gate.py --verdict PASS --sha "$HEAD" --description "$RECEIPT"` (`$RECEIPT` = the receipt comment's short reference, ≤140 characters).
- **Merge order:** (1) the gateway PR — a fleet-wide deploy, since every caller picks it up through the puller; (2) the digest PR; (3) the ledger-only PR: the 221 operator-gated rows by class, the retention of resolved rows, what the bot line is for after #5494.
- **Deploy:** the puller, then each caller's next run. For the digest: `launchctl bootstrap` the canon plist, then kickstart it.
- **Rollback trigger:** more than 4 re-raises for one key within 24 h, or any digest- or log-tier key re-sending sooner than it did before the merge (compare against the pre-merge ladder in `state.json`). A pre-merge baseline of zero p0 sends never triggers a rollback by itself: re-raising a muted p0 is the point. Either trigger means a revert from a fresh origin/main.

## Adversarial review

**Seat:** Codex `gpt-5.6-sol`, outside the author chain.

**Round 1 — REWORK.** Doctrine conflict with PARABELLUM → Dux, colour, mission id declared. `agent_start.py` cannot change cwd → `$WT` captured. `merge=union` ledger → rows only in a final ledger-only PR. S4 was a program (gateway, sentinel, digest, bus schema, growth gate, reconciler) with vacuous "HIGH drops below 21" checks → narrowed to gateway plus digest; the rest queued.

**Round 2 — REWORK.** Findings on this file:
- **F1 applied:** the Opening row follows the colour.
- **F2 applied:** Dux role and Wave row name the pending Astra reading.
- **F4 applied:** the Wave row requires MERGED + pulled + six clean ticks, not "armed".
- **F5 applied:** §3 freeze rule replaces disarm → merge → push → re-arm.
- **F7 applied:** blob-equality content proof in §4.
- **F8 rejected:** bare `--auto` stays (`merge-queue-discipline.md:274-278`; `queue_shepherd.py:819-821`); modus SKILL.md:100's `--squash` is stale (README).
- **F9 applied:** checkpoints use `local broadcast`; the digest label is its real value.
- **F12 applied:** `~/nuzantara/.venv/bin/python3 -m pytest` (verified on Pro: Python 3.14.7, pytest 9.0.3; worktrees carry no `.venv`).
- **F13 applied:** ceiling numbered (≤ once per 6 h, ≥ once per 24 h); rollback on > 4 re-raises per key in 24 h or an earlier non-p0 re-send; a zero baseline never triggers on its own.
