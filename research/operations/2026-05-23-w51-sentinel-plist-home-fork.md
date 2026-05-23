---
date: 2026-05-23
domain: operations
loop: NB-automations-hardening W51
status: shipped (plist patched + daemon reloaded); empirical 60% escalation reduction observed live
---

# W51 — `nuzantara-sentinel` plist exec'd HOME fork (May-18 ↔ Apr-30, missed 4 Phase features)

## TL;DR

`com.nuzantara.sentinel.plist:23` hardcoded `/Users/nuzantara/scripts/nuzantara-sentinel.py`
(HOME fork, Apr-30, 37643 bytes). Repo copy at `/Users/nuzantara/Desktop/nuzantara/scripts/`
(May-18, 38413 bytes) was 9 commits ahead including Phase 0/1/2/4 sentinel hardening. Fix:
plist patched via `plutil -replace ProgramArguments`, daemon reloaded. **Empirical post-reload:
escalations/run dropped 10 → 4 (60% reduction), duration 12.9s → 3.0s (75% faster).**

Same family as W50 (dlq_autopilot wrapper exec'd HOME fork). **W51 also surfaced systemic
scope: 84 of 167 launchagent plists (50%) exec scripts from `~/scripts/` instead of repo.**

## Empirical evidence

```
$ ls -la /Users/nuzantara/scripts/nuzantara-sentinel.py \
        /Users/nuzantara/Desktop/nuzantara/scripts/nuzantara-sentinel.py
-rwxr-xr-x  ... 37643 Apr 30 04:05 /Users/nuzantara/scripts/nuzantara-sentinel.py
-rwxr-xr-x  ... 38413 May 18 21:11 /Users/nuzantara/Desktop/nuzantara/scripts/nuzantara-sentinel.py

$ diff /Users/nuzantara/scripts/... /Users/nuzantara/Desktop/nuzantara/scripts/... | wc -l
183

$ git log --oneline -10 -- scripts/nuzantara-sentinel.py
6c73265ad fix(lint): ruff UP/SIM modernization + unused import cleanup (#720)
9a6e1642b feat(nlm): Sprint 2 CEP + truth_dashboard + freshness UUID + sentinel ARCH-9 + activation wrappers
e9be3970a fix(email): change Brevo sender from zantara@ to zero@balizero.com
60e89f645 feat(sentinel): Phase 4 — DLQ intelligence upgrade (D4.1/D4.2/D4.3)
c80e23592 feat(sentinel): Phase 2 — security hardening + per-machine escalation JSONL
3dcedeb2f feat(sentinel): Phase 1 — decision tree hardening + observability + timestamp fixes
9e25403a5 feat(sentinel): Phase 0 — DLQ TERMINAL state + circuit-breaker TOCTOU fix + registry HALT gate
0bd9a548e feat(cell): add FlyEffector — restart/scale via Machines API
17669060c feat(sentinel): force HALF_OPEN on circuits stuck OPEN > 2h
```

Sentinel HOME copy missed 9 commits including:
- Phase 0 (DLQ TERMINAL state + circuit-breaker TOCTOU)
- Phase 1 (decision tree hardening + observability)
- Phase 2 (security hardening + per-machine escalation JSONL)
- Phase 4 (DLQ intelligence upgrade)

## Empirical impact post-W51

```
Pre-W51 (HOME, Apr-30):
  === Sentinel done: 49 checked, 39 healthy, 10 escalated, 0 suppressed in 12.9s ===

Post-W51 (REPO, May-18):
  === Sentinel done: 49 checked, 39 healthy, 4 escalated, 0 suppressed in 3.0s ===
```

**6 fewer escalations per run** (60% reduction). **75% faster execution**. New decision-tree
logic now visible in stderr:

```
WARNING qdrant_snapshot: phase advance to T4 rejected: Invalid phase transition for
  'qdrant_snapshot': T0 → T4. Expected next: T1
```

This is Phase 1 "decision tree hardening" in action — the HOME copy was silently allowing
invalid state transitions.

## Systemic scope

```
$ ls ~/Library/LaunchAgents/com.{balizero,nuzantara,cell,matagaruda}*.plist | wc -l
167
$ for p in ~/Library/LaunchAgents/com.{balizero,nuzantara,cell,matagaruda}*.plist; do
    if grep -q "/Users/nuzantara/scripts/" "$p"; then echo "$(basename $p)"; fi
  done | wc -l
84
```

**84 / 167 plists (50%) exec scripts from `~/scripts/` (HOME).** This is a structural
desync class, not a single-script bug. Examples observed:

| Plist | HOME path | Risk |
|---|---|---|
| `com.balizero.audit-launchd.daily.plist` | `audit-launchd-daily.sh` | unknown drift |
| `com.balizero.bz-daily-visual-pipeline.plist` | `bz-daily-visual-pipeline.sh` + `cron-runner.sh` | high (pipeline) |
| `com.balizero.crm-guardian-cli-worker.plist` | `crm-guardian-cli-worker.sh` | high (worker) |
| `com.balizero.intel-lake-router.5min.plist` | `intel-lake-router-cron.sh` | high (5min cadence) |
| `com.balizero.regulatory-watcher.daily.plist` | `regulatory-watcher-run.sh` | high (regulatory) |
| `com.balizero.wa-mirror-*.plist` × 5 | `wa-mirror-attention-*.py` | high (WA capture) |
| ... 73 more | ... | unknown |

## Fix shipped (W51)

`~/Library/LaunchAgents/com.nuzantara.sentinel.plist` (backup at `.pre-w51-2026-05-23`):

```diff
- <string>/Users/nuzantara/scripts/nuzantara-sentinel.py</string>
+ <string>/Users/nuzantara/Desktop/nuzantara/scripts/nuzantara-sentinel.py</string>
```

Applied via `plutil -replace ProgramArguments -json ...`. Plist mode restored 0400. Daemon
reloaded via `launchctl bootout/bootstrap`. PID 12763 ran successfully (last exit 0).

## Verification plan

**Already verified live (post-reload at 16:08 WITA)**: escalations 10→4, duration 12.9s→3.0s.

**24h follow-up**:
- Sentinel error log entries: should show new Phase-1 logic ("phase advance to TN rejected:
  Invalid phase transition") instead of bare "status=stale, error=" cascade.
- DLQ side-effect: TERMINAL state should now be honored properly (Phase 0 feature). Cross-check
  `~/logs/dlq_autopilot.log` for any new state-machine consistency.

## Deferred W52-W60 candidates (systemic)

1. **Bulk audit of 84 HOME-fork plists**: enumerate which scripts have repo copies (deletable
   HOME) vs which are HOME-only (need to migrate to repo). Use file-hash comparison.
2. **Identify HIGH-impact subset first**: any plist with cadence ≤ 10min, OR any plist
   touching production state (DB, fly, telegram, drive). Sentinel was already in this set.
3. **W50-style wrapper migration pattern**: for each HOME plist, either (a) edit plist to
   point at repo (W51 pattern) or (b) write wrapper that exec's repo (W50 pattern).
4. **CI lint**: forbid new plists/wrappers from referencing `~/scripts/` or `/Users/nuzantara/scripts/`.
5. **Secrets hygiene**: `com.nuzantara.sentinel.plist` carries `TELEGRAM_BOT_TOKEN` in plain
   text (line 14). Separate W-N task — migrate to environment file source.

## Lessons

- **plist `ProgramArguments` is the silent SSOT for deploy path** (mirrors W50 wrapper-script
  observation). Either pattern hides drift the same way.
- **Single-symbol fix (HOME→repo path) had 60% escalation drop**. Empirical impact of
  HOME-fork drift is not just cosmetic — Sentinel was making materially worse decisions for
  3+ weeks because Phase 0/1/2/4 features were absent.
- **HOME forks pre-date the May-19 repo consolidation**. Anything dated < May-19 in
  `~/scripts/` is suspect. Anything dated < repo-equivalent is definitely stale.
- **plutil patch + launchctl reload** is the cleanest plist-edit recipe; restore mode 0400
  after edit so future agents see "protected" signal.
- **Backup BEFORE patch** (`cp X X.pre-w51-2026-05-23`) is non-negotiable — quick rollback
  on regression.
- **Empirical-first validation**: I confirmed pre-W51 baseline (10 escalations, 12.9s) BEFORE
  patching, then verified post-W51 in the same session. Without baseline, "4 escalations"
  is meaningless.
- **Family**: deploy-path desync (HOME-fork drift, plist or wrapper as SSOT). Two cases this
  week alone (W50 + W51); 82 more known candidates.

## Reference

- Plist patched: `~/Library/LaunchAgents/com.nuzantara.sentinel.plist`
- Backup: `~/Library/LaunchAgents/com.nuzantara.sentinel.plist.pre-w51-2026-05-23`
- HOME fork (legacy, candidate for deletion W52+): `~/scripts/nuzantara-sentinel.py` (Apr-30)
- Repo script (now active): `scripts/nuzantara-sentinel.py` (May-18)
- W50 sibling pattern: `docs/infra/launchagents/launch_dlq_autopilot.sh` (wrapper variant)
- Systemic audit (deferred W52+): 84/167 launchagent plists exec from `~/scripts/`
