# L5.2 Phase 2b auto-trigger runbook

> One-shot LaunchAgent that auto-analyzes Phase 2a monitor-mode data after
> 7 days and opens Phase 2b PR if metrics are GREEN.

## Components

| File                                                         | Purpose                                                                                                                               |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/ci/l5_2_phase2b_auto_analyzer.py`                   | Reads `hot-zone-enforcement` workflow runs, computes health metrics, opens Phase 2b PR if GREEN, escalates via Telegram if YELLOW/RED |
| `scripts/ci/l5_2_phase2b_trigger_wrapper.sh`                 | Daily-fired wrapper that gates on TARGET_DATE=2026-06-02 and self-unloads the LaunchAgent post-run                                    |
| `infra/launchagents/com.balizero.l5-2-phase2b-trigger.plist` | LaunchAgent, daily 09:00 WITA                                                                                                         |

## Install

```bash
cp infra/launchagents/com.balizero.l5-2-phase2b-trigger.plist \
   ~/Library/LaunchAgents/

launchctl bootstrap "gui/$(id -u)" \
   ~/Library/LaunchAgents/com.balizero.l5-2-phase2b-trigger.plist
```

## Verify

```bash
# Confirm loaded
launchctl list | grep l5-2-phase2b

# Next-fire check (should show ProgramArguments + StartCalendarInterval)
launchctl print "gui/$(id -u)/com.balizero.l5-2-phase2b-trigger" | head -20

# Manual gate dry-run (will print "gate: today=... < target=2026-06-02 — skip"
# until 2026-06-02):
bash scripts/ci/l5_2_phase2b_trigger_wrapper.sh
```

## Lifecycle

```
2026-05-26 (today, Phase 2a + 3 merged)
   │
   │  Daily cron fires 09:00 WITA, gate exits silently
   ▼
2026-06-02 09:00 WITA  ◀── TARGET_DATE
   │
   │  Wrapper detects gate open → runs analyzer
   │  Analyzer fetches 7d hot-zone-enforcement runs via gh API
   │  Computes metrics → verdict GREEN/YELLOW/RED
   │
   ├── GREEN  → auto-opens Phase 2b PR + Telegram alert
   ├── YELLOW → Telegram escalation + manual review needed
   └── RED    → Telegram escalation + DO NOT promote
   │
   │  Wrapper writes sentinel ~/.agent/l5-2-phase2b-fired.sentinel
   │  Wrapper self-unloads LaunchAgent via launchctl bootout
   ▼
Cron is gone (one-shot complete)
```

## Health metrics + thresholds

Defined in `l5_2_phase2b_auto_analyzer.py`:

| Metric                         | Threshold | Verdict if breached                     |
| ------------------------------ | --------- | --------------------------------------- |
| Distinct PRs touching hot-zone | ≥ 3       | YELLOW (insufficient data)              |
| Fatal workflow errors          | ≤ 0       | RED                                     |
| Lint migration replay success  | ≥ 100%    | RED                                     |
| Redis check success rate       | ≥ 50%     | YELLOW (CI often can't reach Pro Redis) |

## Logs

- `~/logs/l5-2-phase2b-trigger.log` — daily wrapper output
- `~/logs/l5-2-phase2b-trigger.error.log` — stderr
- `~/logs/l5-2-phase2b-analyzer/phase2b-analysis-*.md` — markdown reports
- `~/logs/l5-2-phase2b-analyzer/run-*.log` — full analyzer stdout/stderr

## Cancel before fire (if Phase 2b plan changes)

```bash
launchctl bootout "gui/$(id -u)/com.balizero.l5-2-phase2b-trigger"
rm ~/Library/LaunchAgents/com.balizero.l5-2-phase2b-trigger.plist
```

## Re-arm (if first attempt didn't ship for some reason)

```bash
rm ~/.agent/l5-2-phase2b-fired.sentinel
cp infra/launchagents/com.balizero.l5-2-phase2b-trigger.plist \
   ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" \
   ~/Library/LaunchAgents/com.balizero.l5-2-phase2b-trigger.plist
```

## Tested locally

```bash
$ bash scripts/ci/l5_2_phase2b_trigger_wrapper.sh
[2026-05-26T22:08:48+08:00] gate: today=2026-05-26 < target=2026-06-02 — skip
$ echo $?
0
```

## What the analyzer's auto-PR does

If verdict=GREEN, the analyzer:

1. Reads `.github/workflows/hot-zone-pr-gate.yml`
2. Replaces all `continue-on-error: true` with `continue-on-error: false`
3. Creates a new worktree via `scripts/agent_start.py`
4. Commits + pushes the change
5. Opens a PR with metrics summary + manual follow-up instructions to add
   `hot-zone-enforcement` to `required_status_checks.contexts` (10 contexts total)

The PR still requires manual approve + merge — Antonello stays in the loop
for the actual production change. The analyzer just removes the toil of
opening the PR.

## Reference

- Phase 2a PR: #888 (merged 2026-05-26)
- Phase 3 PR: #889 (merged 2026-05-26)
- Spec handoff: `research/operations/L5.2-phase2-3-4-prompts.md`
