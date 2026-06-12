# Connectome — the empirical map of Nuzantara's arteries

> INDEX.md maps the **organs** (apps, packages, services). This directory maps the
> **edges** — every producer→consumer artery: PG LISTEN/NOTIFY channels, queues and
> their drainers, the launchd fleet on all machines, GitHub workflows and what they
> gate, file-sync daemons, HOME-fork double-files, webhooks, Claude hooks, MCP servers.
>
> Why it exists: the recurring disease class of this organism is **edges dying
> silently** (scars W55, W62, W64, W67, W70, W71 — orphan listeners, green crons that
> do nothing, suppressed alerts, drifted deployed copies). Organs get audited; edges
> only got discovered when they bled. This census + verifier closes that gap.

## Layout

- `edges/*.yaml` — one file per domain, censused 2026-06-13 by an 8-agent read-only
  fan-out, every load-bearing claim re-verified on disk in-session. Each edge:
  `id, kind, machine, producer, consumer, status, notes` + optional `probe`.
- `scripts/verify_connectome.py` — re-walks the probes and reports
  **REGRESSED** (declared healthy, now failing — the alarm), **RECOVERED**
  (census stale — update it), CONFIRMED / STATIC / SKIPPED.

Companion narrative: `research/operations/2026-06-13-organism-connectome-fable5.md`
(the same-day TAC by a sibling session — diagnosis prose, disease ranking). This
directory is the machine-readable counterpart meant to STAY true over time.

## Status vocabulary

| status | meaning |
|---|---|
| ALIVE / ARMED / GATING / SCHEDULED_ALIVE / IDENTICAL | healthy at census |
| LOOPING | W67 signature: KeepAlive + crash respawn |
| DEAD / RED | persistent failure on schedule |
| STALE | runs but its work item ages (blocked sync, undrained queue) |
| ORPHAN_PRODUCER / ORPHAN_CONSUMER | one side of the edge does not exist |
| DISARMED | exists, loaded, no trigger |
| LYING_BY_PRESENCE | on disk, looks installed, not loaded |
| NEUTRALIZED | wired but a kill-switch/missing backend makes it a no-op |
| BY_DESIGN_OFF | deliberately off, with a documented decision |
| UNKNOWN | could not verify (e.g. machine unreachable) — never guessed |

## Running the verifier

```bash
cd ~/Desktop/nuzantara
apps/backend-rag/.venv/bin/python scripts/verify_connectome.py            # local + ssh probes
apps/backend-rag/.venv/bin/python scripts/verify_connectome.py --no-ssh   # local only
apps/backend-rag/.venv/bin/python scripts/verify_connectome.py --json /tmp/connectome.json
```

Exit 1 ⇔ at least one REGRESSED edge.

**Cron (authorized by Antonello 2026-06-13):** `com.nuzantara.verify-connectome`
via `infra/launchagents/install_verify_connectome.sh` —
daily 07:30 WITA on the Pro (runtime home `~/Desktop/nuzantara-deploy`) and
weekly Monday 08:30 on M5 (covers m5-local edges the Pro cannot probe).
Wrapper `scripts/verify_connectome_run.sh` writes the alive-signal
`~/.agent/decisions/state/verify_connectome.json` (deadman-family convention)
and sends one Telegram alert per run when any edge is REGRESSED.

## Maintenance rules

1. **New automation ⇒ new edge.** Any new LaunchAgent, workflow, queue, webhook or
   sync daemon gets an entry here in the same PR (same spirit as
   `scripts/automation_catalog.json`, but edge-centric and probe-backed).
2. **RECOVERED verdicts mean the census is stale** — update the edge's `status`,
   don't ignore them.
3. Statuses are census-time observations, not promises. The probe is the truth.
4. Census refresh: re-run the 8-domain fan-out quarterly or after major surgery
   (machine decommission, pipeline cutover).
