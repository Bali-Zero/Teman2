# Healer organ — autonomous cure loop (Mini-Pro2)

Born 2026-07-06 on Zero's GO ("guaritore in loop e piena autonomia"). Converts the three
receptor-only organs (proprioception, PENDING-ARMS ledger, escalations board) into a
**self-acting** loop: launchd fires every 4h; a deterministic pre-check costs zero LLM tokens
when the organism is healthy; only actionable findings spawn a headless Sonnet-5 session that
cures in-perimeter items (worktree → PR → auto-merge → prove-live → ledger) and Telegram-alerts
Zero for everything operator-gated.

## Pieces

| Piece | Canon | Live (Mini) |
|---|---|---|
| Wrapper (pre-check, trampoline, watchdog, heartbeat, Telegram) | `infra/healer/healer-run.sh` | `~/scripts/healer-run.sh` |
| Standing mandate (perimeter, rules, budget) | `infra/healer/HEALER-MANDATE.md` | `~/scripts/HEALER-MANDATE.md` |
| LaunchAgent (StartInterval 14400) | `infra/launchagents/com.nuzantara.healer.4h.plist` | `~/Library/LaunchAgents/` |

All three are declared pairs in `infra/home-fork/declared-pairs.json` (machines=mini) —
`lint_home_fork.py --check` and proprioception watch the live↔canon sha.

## Safety rails

- **Kill switch**: `HEALER_ENABLED=false` in `~/.nuzantara-healer.env` (or plist env). Next tick exits instantly.
- **Anti-overlap**: pidfile lock — a long session never stacks with the next tick.
- **Anti-loop**: `HEALER_RUN=1` exported; wrapper refuses to nest; mandate forbids the healer touching itself.
- **Wall-clock watchdog**: session hard-killed after `HEALER_MAX_WALL_S` (default 3300s).
- **Perimeter (mandate, tassativo)**: IN = infra/, scripts/, docs/, ledger, Mini-local organs,
  declared-pair HOME sync. OUT = backend-rag/mouth code (merge=deploy), hooks/guardrails,
  workflows, migrations, secrets values, publish, remote machines (read-only probes only),
  the healer itself, modus. Max 3 PR/tick.
- **Cure-quality floor**: if the claude tier is degraded (quota/auth), the healer does NOT
  cascade cures to weaker models — heartbeat `degraded` + Telegram + exit.
- **Observability**: heartbeat sidecar `~/.organism/last_seen/mini.healer.json` EVERY run
  (idle runs included: `status=ok note=idle`); session logs in `~/logs/healer/`;
  Telegram to Zero only when it acted, alerted, or degraded.

## Operations

- Manual tick: `ssh mini 'bash ~/scripts/healer-run.sh'` (trampoline-safe under ssh).
- Watch: `ssh mini 'tail -20 ~/logs/healer/healer.log; cat ~/.organism/last_seen/mini.healer.json'`.
- Disable: `ssh mini 'echo HEALER_ENABLED=false >> ~/.nuzantara-healer.env'`.
- Re-enable: remove that line; next tick resumes.
- Uninstall: `launchctl bootout gui/$(id -u)/com.nuzantara.healer.4h` + remove plist.

## Design notes

- The 4h loop is affordable because idle ticks never spawn an LLM: the pre-check is
  `pending_arms_report.py --strict` (exit≠0 = overdue tech-debt) + `proprioception.py --json
  --no-fetch` (DIVERGED count) + the escalations hook (non-empty stdout = fresh HIGH entries).
- Repo freshness on Mini is guaranteed by the existing `com.nuzantara.git-pull-main.5min` cron —
  the healer always reads a fresh ledger.
- W84: the wrapper re-execs via the ssh-localhost trampoline (`~/.ssh/id_local_trampoline`,
  `from="127.0.0.1,::1"` restricted) when launchd's TCC denies `~/Desktop` — same pattern as
  the regulatory watcher (#1987).
- The proprioception "daily cron" firebreak (PENDING-ARMS 2026-07-02) is SUPERSEDED by this
  organ: the healer runs proprioception every tick, with a brain attached to act on it.
