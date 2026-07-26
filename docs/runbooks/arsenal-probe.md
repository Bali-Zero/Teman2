# Arsenal Probe — seat liveness runbook

Date: 2026-07-06 · Spec: `docs/specs/arsenal-probe-v1.md` · Tool: `scripts/arsenal_probe.py`

## Why it exists

The multi-LLM quota cascade (claude → agy → codex → ollama, plus glm/deepseek council seats)
can silently thin to 2-deep: Codex OAuth dies with a quiet 401 `token_revoked`, agy is
GUI-keychain-bound (dead under sshd/launchd), GLM can 401/1211/529, DeepSeek runs out of balance
(402). Every one of these has ALREADY happened (superscar #2, Esiste≠Armato at the arsenal
level; audit 2026-05-24 found the cascade 2-deep with nobody noticing). A weekly empirical
health-ping was recommended 2026-05-24 and never armed — this tool is that arming, done heavier.

## What it does

One run live-probes every AI seat reachable from this machine (claude, glm, kimi, agy, codex,
deepseek, ollama, nlm — thread-parallel, per-seat timeouts) and classifies each by OUTPUT
CONTENT (never exit code alone) into: `LIVE · AUTH_DEAD · CONTEXT_AUTH · QUOTA_DEAD ·
BALANCE_DEAD · MODEL_ERR · SHED · TIMEOUT · CRED_UNAVAILABLE · NOT_INSTALLED · UNKNOWN_ERR`.

Outputs:

- `~/.organism/arsenal/last.json` (report; previous kept as `prev.json`; transitions computed)
- `~/.organism/last_seen/<machine>.arsenal_probe.json` (heartbeat sidecar, healer-compatible)
- stdout table (`--table`), full JSON (`--json`), or one line (`--quiet`)

Credential values are never printed, logged, or reported (scrub layer; scar #4).

## How it is armed (no 177th daemon — W84)

- **Mini (primary)**: the healer wrapper (`infra/healer/healer-run.sh`, 4h loop) refreshes the
  probe when the report is ≥20h old (≈1 live probe/day, preserving the healer's
  "healthy tick ≈ zero LLM cost" promise) and reads `transitions` EVERY tick: a NEW persistent
  death (AUTH/BALANCE/MODEL/UNKNOWN) → ACTIONABLE + direct Telegram to Zero.
- **Proprioception**: `arsenal_seats` wrap entry (`--read-last`, no live calls) DIVERGEs on
  persistent deaths in the last report; `guardian_freshness` flags the report stale >26h on Mini.
- **On demand, any machine**: `python3 scripts/arsenal_probe.py --table` (M5/Pro give the
  GUI-context truth — agy/keychain seats can be LIVE here and CONTEXT_AUTH under sshd; both
  truths are real, per-context).

## Reading a report

- `CONTEXT_AUTH` / `CRED_UNAVAILABLE` / `NOT_INSTALLED` = host/context limitation, not seat
  death — the seat may be LIVE elsewhere. Never strict-fails.
- `QUOTA_DEAD` / `SHED` / `TIMEOUT` = transient; alarm-worthy only as trend.
- `AUTH_DEAD` / `BALANCE_DEAD` / `MODEL_ERR` = persistent and fixable — almost always
  operator-gated:

| Seat dead               | Cure (operator unless noted)                                                                                                                                 |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| codex AUTH_DEAD         | interactive `codex login` on that machine                                                                                                                    |
| claude AUTH/QUOTA       | `claude auth status`; window cap → wait reset or switch slot                                                                                                 |
| glm AUTH_DEAD           | re-copy token from a live keychain (see memory `discovery_glm_mini_seat_armed_fable_model_leak_2026_07_06`)                                                  |
| glm MODEL_ERR           | config drift — launch from repo cwd or pin `--model glm-5.2` (fable-5[1m] leak)                                                                              |
| deepseek BALANCE_DEAD   | top-up at platform.deepseek.com                                                                                                                              |
| agy AUTH_DEAD (GUI ctx) | interactive `agy` login in a live session                                                                                                                    |
| nlm AUTH_DEAD           | `nlm login` on Pro (recurs ~monthly)                                                                                                                         |
| kimi AUTH_DEAD          | `kimi login` on that machine (device-code flow — authorize the printed URL/code from a kimi.com-logged browser; Allegro subscription, seat added 2026-07-19) |

## Selftest / CI

`python3 scripts/arsenal_probe.py --selftest` — classifier table on canned provider outputs,
scrub check, blind-scan guard (0 seats probed → exit 2). CI: `scripts/tests/test_arsenal_probe.py`
in `immune-enforcement.yml` (offline, guilt+innocence per classifier).
