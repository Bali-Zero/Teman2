---
date: 2026-05-23
domain: operations
client_case: NB automations hardening — W22 programmatic launchd inventory audit (panel-consensus follow-up)
sources: 5
---

# W22: launchd mass audit — 61/115 plists unhealthy (53% degraded inventory)

## Context

Loop iteration 22, executed AFTER panel review (Gemini + Codex + DeepSeek) of
W11→W21. Panel consenso 3/3 (`/tmp/w11-w21-brief.md` + transcripts in
session log):

> "NO kickstart blind on all 115 plists — too risky for non-idempotent
> entries. Build PROGRAMMATIC matrix per plist with last_fire,
> exit_code, log signature analysis (Fatal Python / Operational / TCC
> noise / silence), mtime delta vs schedule."
> — Gemini + Codex + DeepSeek convergent

Also resolved BEFORE W22 per panel unanimous priority: `gh auth` fixed
(unset GITHUB_TOKEN env var blocked keyring auth) + **PR #823 opened**
for the 21-commit W1→W21 loop.

## Audit script

`~/scripts/audit_launchd_crons.py` (~150 lines, stdlib only). Per
plist surfaces:

- `launchctl print` state + last exit code
- StandardErrorPath: total lines, noise lines (W19+ TCC patterns),
  real_error lines (Fatal Python / Traceback / OperationalError /
  InterruptedError / ModuleNotFound / etc.)
- StandardOutPath mtime as proxy for "alive" (NOT kickstart — read-only)
- Schedule expectation: `StartInterval` or `StartCalendarInterval` →
  expected interval in seconds
- `*sh -lc` anti-pattern flag
- Health verdict + diagnosis list

Read-only. No kickstart. No mutations.

## Findings — 2026-05-23 01:20 WITA snapshot

| Metric                                       | Value                    |
| -------------------------------------------- | ------------------------ |
| Total plists                                 | **115**                  |
| Healthy                                      | 54                       |
| **Unhealthy**                                | **61 (53%)**             |
| With `*sh -lc` antipattern (still after W21) | **16** (all balizero/\*) |
| With real_errors > 0                         | **35**                   |
| With high_noise (W21 silent-dead signal)     | 2                        |
| Never fired / not loaded                     | 0                        |

Confirms DeepSeek's prediction: "if reg-alert was silently dead for 6
days, COUNT how many other crons may be silently dead behind their noise."

## P0 — critical (real_errors > 100)

| Plist                                               | Real errors | Notes                              |
| --------------------------------------------------- | ----------- | ---------------------------------- |
| `com.balizero.wr2.supervisor-watchdog.plist`        | **2797**    | Likely loop crash                  |
| `com.matagaruda.bridge.adaptive.plist`              | **1372**    | InterruptedError pattern           |
| `com.balizero.guardrails-daemon.plist`              | **528**     | Recently-shipped Wave 2 daemon?    |
| `com.balizero.wr2.canva-lease-watchdog.10min.plist` | **265**     | TimeoutError raised                |
| `com.matagaruda.gap.consumer.plist`                 | **176**     | CLAUDE_CODE_OAUTH_TOKEN_1 timeouts |

## P1 — high (10-100 real_errors)

| Plist                                               | Real errors | Notes                                                       |
| --------------------------------------------------- | ----------- | ----------------------------------------------------------- |
| `com.balizero.wa-mirror-attention-classifier.plist` | 69          | STALE + NONZERO_EXIT=1 (wa-mirror degraded)                 |
| `com.balizero.wa-mirror-auto-promote.plist`         | 61          | Same family                                                 |
| `com.balizero.observatory-server.plist`             | 56          | FileNotFoundError: favicon.ico path                         |
| `com.balizero.wa-mirror-attention-realtime.plist`   | 35          | Same wa-mirror family                                       |
| `com.cell.organism.plist`                           | 22          | **STILL broken** (despite 2026-05-22 cicatrix resurrection) |
| `com.balizero.post-publish-poller.plist`            | 15          | TimeoutExpired                                              |
| `com.balizero.wr2.topic-selector.plist`             | 13          | httpcore.ReadTimeout                                        |
| `com.balizero.client-value-predictor.plist`         | 10          | TimeoutExpired                                              |
| `com.balizero.profile-monitor-wrapper.plist`        | 10          | **ModuleNotFoundError: asyncpg** (deps issue)               |
| `com.balizero.wr2.connector.plist`                  | 10          | TBD                                                         |
| `com.balizero.wr2.sla-worker.plist`                 | 10          | TBD                                                         |

Plus singletons with `ModuleNotFoundError: playwright`
(`wr2.image-generator`), `FileNotFoundError: psql`
(`sota.m13-monthly`), `sota.m13-collect` with `Fatal Python error:
error evaluating path` (same root cause as W21 reg-alert — `*sh -l`
breaking Python init).

## P2 — STALE crons (potentially silent-dead, mtime > 2× expected interval)

| Plist                                                | Last activity | Expected       | Multiplier                   |
| ---------------------------------------------------- | ------------- | -------------- | ---------------------------- |
| `com.balizero.competitor-monitor.monthly.plist`      | 13.2d ago     | daily (86400s) | 13× — dead since 2026-05-10  |
| `com.balizero.regulatory-watcher.fix-b-verify.plist` | 8.7d ago      | daily          | 8.7× — dead since 2026-05-14 |
| `com.balizero.nuzantara.disk-watchdog.plist`         | 3.1d ago      | daily          | 3.1× — last fired 2026-05-20 |

## P3 — LC antipattern only (cosmetic, no real errors)

13 balizero plists still use `/bin/{bash,zsh} -lc` but produce no real
errors. Migration to W21 generic wrapper is **opportunistic** (would
de-risk future TCC-induced silent failures like W21 reg-alert) but
NOT urgent.

## Lessons (panel echo)

- **Codex was right**: "Il vero bug è aver inferito salute da log
  puliti." 53% of inventory was degraded under the assumption "if log
  has noise, it's probably noise we know about". W22 disproves this.
- **DeepSeek was right**: "Hai verificato che TUTTI i plist siano stati
  effettivamente migrati (11 su quanti totali?)" — answer revealed:
  16 balizero plists still use `*sh -lc`, plus 35 with real_errors
  unrelated to W21 scope.
- **Gemini was right**: the audit script she suggested becomes the
  systematic dashboard going forward. Should be scheduled.

## Open questions for W23+

1. **Priority queue**: 5 P0 plists deserve individual root-cause analysis
   (similar to W21 reg-alert). Order: supervisor-watchdog (2797!) →
   bridge.adaptive (1372, same matagaruda family I just touched) →
   guardrails-daemon (528, recent ship) → canva-lease-watchdog (265) →
   gap.consumer (176, our own from W8).

2. **Schedule the audit script** as a launchd cron itself? Daily 02:00
   WITA, emits Telegram alert on `unhealthy_delta > 0` (new unhealthy
   plist since last run). Risk: meta-recursion (audit cron uses
   audit-friendly wrapper). Worth the safety net.

3. **Branch + PR strategy**: W22 patch lands on existing PR #823? Or
   open separate PR? My instinct: W22 is the natural epilogue of
   W1→W21 ("survey + identify weaknesses = done; here's the full
   inventory") so it belongs in PR #823.

## Sources

1. Panel review brief `/tmp/w11-w21-brief.md` (W11→W21)
2. Panel synthesis 3/3 convergent: NO kickstart-blind, BUILD matrix
3. `~/scripts/audit_launchd_crons.py` (this iteration ship)
4. `research/operations/audits/2026-05-23-launchd-audit-snapshot.json`
   (2122-line JSON snapshot)
5. Empirical run 2026-05-23 01:20 WITA: 115 plists, 61 unhealthy
