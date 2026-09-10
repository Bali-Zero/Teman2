---
title: "S2 — CUSTODY · battle window"
date: 2026-09-10
adversarial_review: codex
---

# S2 — CUSTODY · battle window

| Field | Value |
|---|---|
| Mandate id | **S2** |
| Colour | **BLUE** (the default). Chosen before the window opens; no fallback between colours. |
| Dux role | Opus 5 `xhigh` on BLUE (Sol `gpt-5.6-sol` `xhigh` on ORANGE), appointed by the staff room (Fable 5.1 with Zero; Astra reading pending — README). Dux and release owner. |
| Worktree / branch | `agent/nuzantara/infra/s2-custody`, created by the command in §1 |
| Wave | 1, in parallel with S1 |
| Opening | The opening follows the colour. BLUE: Zero opens a fresh `claude --model claude-opus-5` window at effort `xhigh` and pastes this file. ORANGE: a Codex window on the Sol seat as army-map §1bis names it ("Sol (`gpt-5.6-sol`) `xhigh`"). The first message restates colour, Dux role, mandate id and worktree path, then executes. |

Opened 2026-09-10 ~22:55 WITA on the v2 text; the v3 corrections below were sent to the running window by the staff room.

## 1. Mandate

S2 · BLUE · **organ: the credential-custody detector** — `scripts/secrets_permissions_audit.py` and the schedule this window gives it. **Gear:** 2 expected (CI's floor wins). **Host:** Pro. The restore drill is another organ: a queued window (README).

**Objective:** the detector looks inside `~/nuzantara/.secrets` and runs every 3600 s. **What success changes:** the next loosened credential file is caught by a machine within one audit interval — at most 60 minutes plus one run's duration — not by a late reader.

**Worktree:** `cd ~/nuzantara && WT=$(python3 scripts/agent_start.py --lane infra --task-id s2-custody | awk '/^WORKTREE_READY /{print $2}') && echo "$WT"`. The broker prints one `WORKTREE_READY` line followed by the path and cannot change your cwd (`scripts/agent_start.py:2166-2172`), so every later command is `git -C "$WT" …` or `cd "$WT" && …`; `--list` recovers the path. One live worktree at a time: `--release s2-custody` after a PR merges, then a fresh origin/main. `sec` is not a known lane. **Base sha:** record `git -C "$WT" rev-parse HEAD` at open.

**Ground** (judge 13:03–13:06Z, red-team ~1 h later, editor re-check ~13:35Z, staff room ~15:40Z; re-run all of it):
- **File modes.** `stat -f '%Sp' ~/nuzantara/.secrets ~/nuzantara/.secrets/*` → directory `drwx------`, six files `-rw-------`, one `-r--------`. They are correct only because the orchestrator applied chmod 600/400 and 700 by hand at ~21:05 WITA after a late reader found them loosened (4 of 7 inodes carry that ctime). `find ~/nuzantara/.secrets -type f | wc -l` → 7; `find ~/nuzantara/.secrets -type f -perm +077 | wc -l` → 0.
- **Default roots.** `scripts/secrets_permissions_audit.py:71` `_DEFAULT_ROOT_RELATIVE_PATHS` → eleven roots plus a `~/.env*` glob; `~/nuzantara` is not among them.
- **The guilt fixture is absolved today.** On origin/main, a 0644 file in a fresh `mktemp -d` `.secrets` directory reports 0 findings: the reachability test (`scripts/secrets_permissions_audit.py:369-376`) absolves a file whose parent chain is closed. The JSON carries `files_traversed` as ONE total across roots, not per root (scratch run, 2026-09-10).
- **No schedule.** `crontab -l | grep -c secrets_permissions_audit` → 0; no LaunchAgent.
- **Whole-tree noise.** `--no-default-roots --root ~/nuzantara --json` → ~108.6 KB of false hits from `.worktrees/*` templates, `.secrets.baseline` and workflow names.
- **Second account.** `dseditgroup -o checkmember -m zantara-codex staff` → `yes`.
- **Secret scanning.** Alerts #7 (Telegram bot token) and #1 (GCP service-account key), queried only through a projection: `gh api "repos/Bali-Zero/Teman2/secret-scanning/alerts?state=open" --jq 'map({n:.number,t:.secret_type,c:.created_at})'`. The raw response contains the secret.
- **#6101** (launchd canon) merged 2026-09-10T14:24Z, so the schedule PR is unblocked.

## 2. Owned perimeter

- **Writable:** `scripts/secrets_permissions_audit.py`; `scripts/tests/test_secrets_permissions_audit.py`; one new canon plist `infra/launchagents/com.nuzantara.secrets-permissions-audit.plist` (to be created: `StartInterval` 3600 unless the window records a reason to differ, no `KeepAlive`, clean under `scripts/lint_plist_keepalive.py`).
- **chmod** only under `~/nuzantara/.secrets` (correct today) and on the audit's own log and state files. Never `--fix` anywhere else.
- **`.env*` — explicit read-only exception.** The detector `stat`s `.env*` files for their MODE only. It never opens them, never chmods them, never fixes them; the off-limits rule still holds for their content. Their modes are REPORTED and escalated to Zero as a ledger row (directory and mode class only).
- **Forbidden:** the restore-drill workflow (queued); memory.db and its backups (S5/S5b); `scripts/tg_notify.py` (S4); the `zantara-codex` account and its groups; crontab (plist only).
- **Shared:** `infra/launchagents/` (convention owner #6101, merged; S3 adds a different plist); the ledger (§3).
- `.lane-check.json`'s `scope_globs` only decides whether a check applies (`infra/claude-hooks/lane_check.py`; the spec's `scripts/` path is stale). VERIFY and the gate compare changed paths against this list by hand.
- **Bans:** no Claude model through a paid per-token Anthropic endpoint (any alias, wrapper, Bedrock or Vertex route; only the `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN`). No client PII or OSINT in cleartext. Off-limits: `zantara_core.py`, `fly.toml`, `.env*` (content), `apps/bali-intel-scraper/backend/db/migrations/env.py`. Zero's files never edited. Operator items filed, never waited on.

## 3. Sibling contract

Frozen before BUILD. Changes go to the staff room through Zero.

- **Launchd canon.** ProgramArguments name `/Users/nuzantara/nuzantara/scripts/secrets_permissions_audit.py`; the healer's home-fork refresh reverts live-only edits, so the canon is the change. S3 adds a different plist in the same directory: no shared lines, both bootstrapped from canon, neither touches crontab.
- **The gateway (S2 consumes S4).** Findings go through `tg_notify.py`'s frozen surface: `--tier p0 --source secrets-audit --dedup-key secrets-audit:secrets-dir` for `.secrets`; `--tier digest --source secrets-audit --dedup-key secrets-audit:env-modes` for `.env*` mode reports. Alert text carries directory, count and mode class only — never a filename's contents.
- **The ledger — the one surface all windows share.** `.claude/skills/modus/PENDING-ARMS.md` carries `merge=union`, which GitHub's mergeability ignores (modus SKILL.md:193); #6080 and #6081 went DIRTY that way today. Serialize: rows ONLY in one final, separate, ledger-only PR, cut from a fresh origin/main after this window's code PRs merged. Open it only when `gh pr list --state open --limit 200 --json number,files --jq '[.[]|select(any(.files[];.path==".claude/skills/modus/PENDING-ARMS.md"))|.number]'` prints `[]` and `git -C "$WT" diff origin/main -- .claude/skills/modus/PENDING-ARMS.md` is +N/-0.
- **Freeze.** Once armed, the branch is read-only (Builder Contract rule 1). A **real** DIRTY on an armed PR: close it with a comment naming the successor, cut a fresh branch from origin/main, cherry-pick the same content, then push, create and arm the successor as three separate commands. A **phantom** DIRTY (GitHub reports DIRTY while `gh pr view "$PR" --json autoMergeRequest` still shows it armed): judge the diff, then let the queue cure it. Never `--disable-auto`, merge origin/main, push and re-arm.

## 4. Acceptance

- **Negative (innocence):** a 0600 file and a 0400 file in a scratch `.secrets`-shaped directory are clean; a `.env.example` elsewhere is never flagged; a `.env*` finding produces one report line and zero chmod calls (a test asserts no mode change).
- **Integration (guilt, on a fixture, never on the live directory):** `SCR="$(mktemp -d)/.secrets"; mkdir -p "$SCR"; : > "$SCR/probe.json"; chmod 644 "$SCR/probe.json"; python3 scripts/secrets_permissions_audit.py --no-default-roots --root "$SCR" --json`. On origin/main it reports 0 findings (Ground); on the branch exactly one. After `chmod 600 "$SCR/probe.json"` the same command is clean. Tests: `cd "$WT" && ~/nuzantara/.venv/bin/python3 -m pytest scripts/tests/test_secrets_permissions_audit.py -q`, including one proving the default roots contain `~/nuzantara/.secrets` that fails without the change.
- **Production observation** (label `com.nuzantara.secrets-permissions-audit`, to be created):
  1. Content proof after the puller — blobs, not ancestry (superscar #9, `scripts/branch_graveyard_cleanup.sh::content_on_main()`), with `$WT` on the PR's final head: `[ "$(git -C ~/nuzantara rev-parse HEAD:scripts/secrets_permissions_audit.py)" = "$(git -C "$WT" rev-parse HEAD:scripts/secrets_permissions_audit.py)" ] && echo live`.
  2. `launchctl list | grep -c com.nuzantara.secrets-permissions-audit` → 1. `launchctl print gui/$(id -u)/com.nuzantara.secrets-permissions-audit | grep -E '^\s*(runs|last exit code) ='` shows runs ≥ 1 and exit 0. Always this projection: the full print dumps the job's environment.
  3. **Agreement in the same minute.** The run's file count for the `~/nuzantara/.secrets` root (a per-root field the roots PR adds) equals `find ~/nuzantara/.secrets -type f | wc -l`, and its findings under that root equal `find ~/nuzantara/.secrets -type f -perm +077 | wc -l` (group or other bits set; the legitimate 0400 file is not one). A true finding on the live directory is the detector PASSING, not the window failing: file it, don't hide it.
  4. The next scheduled run, at most 60 minutes plus run time later, agrees again.

  Fixture success never stands in for this observation.

## 5. Team

Every seat comes from the colour table (`docs/architecture/dual-consul/army-map.md` §1bis, its only copy).

- **BLUE:** Dux and release owner, this window (Opus 5 `xhigh`). Implementer Sonnet 5, pinned in every Agent call (`model: "sonnet"`); supports on Haiku 4.5 (`model: "haiku"`); an unpinned child inherits the Dux's model. Adversarial reviewer: an independent Codex seat outside the chain (`.claude/scripts/codex-spalla.sh`; `docs/codex/CODEX_SPALLA.md`), reading the frozen diff itself. Final on-disk gate: a FRESH Opus 5 `xhigh` session outside the chain, commissioned by this top-level Dux (modus SKILL, "Gate commission depth"); it only signs.
- **Routing floor:** two code PRs, so one lane (e.g. roots and tests) goes through Kimi or GLM, prepare-only, own worktree — not Codex, so the reviewer stays cross-family.
- **ORANGE**, only if declared before opening: every seat from §1bis. A dead seat suspends the mission.
- Record each seat's effective model, effort and thread id in `brief.yml` at start.

## 6. Appetite and stop-loss

- **Budget:** 5 h, 2 adversarial rounds, 1.5M tokens, declared as `appetite:` in `brief.yml`; `spend:` in `pack.yml` (`scripts/evidence_pack_lint.py` rule 14).
- **Deadline:** open + 5 h. ONE mission deadline, owned by the root mandate and read through `infra/codex-hooks/mandate_budget.py` (the spec's `scripts/mandate_budget.py` does not exist). The staff room may renew it once; on expiry the mission suspends.
- **Limits:** three reds for one cause → suspend; fix-of-a-fix depth 1; at most 2 children, depth 1, 1 continuation hop; adapter tool ceiling with no ship reserve (N = 0) — a capped child checkpoints and returns, shipping is the Dux's; child active time reported separately.
- **Checkpoints:** `scripts/fleet_mail.sh local broadcast --key S2-checkpoint --ttl 24 "$STATE"`, where `$STATE` is one line of state with no PII. `local` is Pro; the staff room reads the Pro mailbox.
- **Stop and escalate if:** evidence that another account read a credential; any fix would touch `.env*`; a useful alert would need a filename; three reds for the same cause.

## 7. Evidence and release

- **Evidence:** `cd "$WT" && python3 scripts/ci/evidence_paths.py --ref "$(git rev-parse --abbrev-ref HEAD)"` names the directory. `brief.yml`: gear, appetite, team with thread ids, four timestamped sibling outputs (open PRs' paths, `python3 scripts/agent_start.py --list`, `ListAgents`, `scripts/fleet_mail.sh local --list`). `pack.yml` alongside. Every code PR carries `Bites:`.
- **Release**, three separate commands: `git -C "$WT" push -u origin HEAD`; `cd "$WT" && gh pr create --title "$TITLE" --body-file "$BODY"`; `gh pr merge "$PR" --auto` at once (`$PR` = the number `gh pr create` printed). Bare `--auto`: the queue rejects every strategy flag (`docs/runbooks/merge-queue-discipline.md:274-278`; `scripts/queue_shepherd.py:819-821`). At Gear 2 or above, the `harness/fable-gate` success must sit on the real head sha.
- **Gate receipt:** a PR comment with mission id, colour, HEAD sha, gate thread id, commands with exit codes, verdict; re-checked against the current HEAD before posting. Publish: `HEAD=$(gh pr view "$PR" --json headRefOid --jq .headRefOid)`, then `python3 scripts/harness_fable_gate.py --verdict PASS --sha "$HEAD" --description "$RECEIPT"` (`$RECEIPT` = the receipt comment's short reference, ≤140 characters). PASS-WITH-CONDITIONS needs `--conditions-ref`.
- **Merge order:** (1) roots PR; (2) schedule PR; (3) the ledger-only PR: rotation of the Google service-account and combined-env credentials, the Telegram bot token and the GCP key; the second local account; whether it read the credentials; the `.env*` mode findings. No backend path.
- **Deploy:** puller, then install the canon plist per #6101's convention and `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.secrets-permissions-audit.plist`, then `launchctl kickstart -k gui/$(id -u)/com.nuzantara.secrets-permissions-audit` once.
- **Rollback trigger:** scheduled runs raise findings outside `.secrets` that are not real exposures, or send more than one alert per interval → `launchctl bootout gui/$(id -u)/com.nuzantara.secrets-permissions-audit`, then a revert PR from a fresh origin/main.

## Adversarial review

**Seat:** Codex `gpt-5.6-sol`, outside the author chain.

**Round 1 — REWORK.** Doctrine conflict with PARABELLUM → Dux, colour, mission id declared. `agent_start.py` cannot change cwd → `$WT` captured. `merge=union` ledger → rows only in a final ledger-only PR. S2 mixed two organs → the restore drill is queued. `.env*` could be chmod'ed → report-only. The guilt fixture used the default roots → `--no-default-roots --root "$SCR"`.

**Round 2 — REWORK.** Findings on this file:
- **F1 applied:** the Opening row follows the colour.
- **F2 applied:** the Dux role names the pending Astra reading.
- **F5 applied:** §3 freeze rule replaces disarm → merge → push → re-arm.
- **F7 applied:** blob-equality content proof in §4.
- **F8 rejected:** bare `--auto` stays (`merge-queue-discipline.md:274-278`; `queue_shepherd.py:819-821`); modus SKILL.md:100's `--squash` is stale (README).
- **F9 applied:** checkpoints use `local broadcast`; labels and PR numbers are real values or named shell variables.
- **F10 applied:** `StartInterval` 3600, so one interval is ≤ 60 min + run time; the hardcoded "7 files, 0 findings" became same-minute agreement with `find`; the `.env*` read-only exception is explicit. The ruling's "mode not 600" oracle would count the legitimate 0400 file, so the oracle counts group/other bits (`-perm +077`), the same correction the staff room sent the running window.
- **F12 applied:** tests run with `~/nuzantara/.venv/bin/python3 -m pytest`.
