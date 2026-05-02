# Codex 3/5 criterion — runtime ownership for the 14 cell candidates

**Date:** 2026-05-02 · **Author:** Sprint 0 Air session
**Reference:** brainstorm 2026-05-02 round 2 § "Codex 3/5 criterio quantitativo"

Codex round 2 proposed a 3/5 quantitative criterion to decide each
cell's primary runtime: OpenClaw if 3+ of 5 OC criteria; cron-agent-python
if 3+ of 5 cron criteria; **hybrid** (cron-agent trigger + OpenClaw
sub-step) if both score 3+.

## Codex 5 OpenClaw criteria

A task is "OpenClaw-shaped" if 3+/5 of:

1. **Multi-turn session** — the work proceeds across multiple agent
   invocations with shared state.
2. **2+ tools/MCP chained** — the task invokes 2+ tools per run (web_search,
   exec, MCP, etc.).
3. **Persistent memory matters for future decisions** — observation feed
   changes downstream behaviour.
4. **Human channel/review** — Telegram/voice/browser is in the loop
   (review gate, approval, escalation).
5. **Bounded action with budget cap + max steps + kill switch + fallback**
   — explicit safety envelope.

## Codex 5 cron-agent-python criteria

A task is "cron-agent-shaped" if 3+/5 of:

1. **Schedule deterministic** — runs on a fixed cron, no triggering signal.
2. **Input/output replayable** — given the same input, same output (within tolerance).
3. **SLA operativo** — must run within a deadline (e.g. before 09:00 daily report).
4. **Single-purpose** — one well-defined verb per run.
5. **High frequency or independence from gateway** — runs more often than
   OpenClaw can comfortably handle, OR doesn't need any agent runtime.

## Per-cell scoring

### #1 system-doctor-cell (L1)

| OpenClaw criteria | Match? | cron-agent-python criteria | Match? |
|---|---|---|---|
| Multi-turn session | no — single check | Schedule deterministic | yes (every 4h) |
| 2+ tools chained | sometimes (telegram + db) | Replayable | yes |
| Persistent memory | no | SLA | partial (bounded latency) |
| Human channel | only on alert | Single-purpose | yes |
| Bounded budget | yes | High frequency | yes |
| **Score** | **2/5** | **Score** | **5/5** |

**Verdict: cron-agent-python primary.** Stays where it is.

### #2 seo-guardian-cell

| OC | yes (multi-turn weekly observation) | cron | yes (every 40min) |
| ... | 1/5 | ... | 5/5 |

**Verdict: cron-agent-python primary.**

### #3 fact-checker-cell

| OC | 1/5 (single fetch+reason) | cron | 5/5 |

**Verdict: cron-agent-python primary.**

### #4 tech-orchestrator-cell

| OC | **3/5** (multi-tool, persistent state, human escalation on HIGH) | cron | 4/5 (deterministic, replayable, single-purpose, hourly) |

**Verdict: HYBRID** — cron-agent-python trigger + OpenClaw sub-step
when `task.tool_count >= 3 OR risk_level == 'HIGH'`. Sprint 7 work.

### #5 conversation-trainer-cell

| OC | 1/5 | cron | 5/5 |

**Verdict: cron-agent-python primary.**

### #6 daily-ops-cell

| OC | 0/5 | cron | 5/5 (daily 08:00, replayable, SLA, single-purpose) |

**Verdict: cron-agent-python primary.**

### #7 crm-cell ⭐ NEW

| OC | 2/5 (multi-tool, sometimes review) | cron | 4/5 (mixed schedule + event-driven) |

**Verdict: cron-agent-python primary** with EventBus-driven sub-tasks.
Sprint 3 consolidates 13 CRM auto into one cell.

### #8 intel-scraper-cell (light)

| OC | 1/5 (single tool — Claude CLI enricher) | cron | 5/5 (03:00 daily, replayable, SLA, single-purpose, runs at fixed time) |

**Verdict: cron-agent-python primary** (with intel-radar hourly + intel
feed processor every 2h as sub-strategies). NOTE: round 2 DeepSeek
flagged intel-radar as Sprint 8 candidate for OpenClaw migration via
Knowledge Agents. That's a sub-cell migration, not the main cell.

### #9 hgt-coordinator-cell ⭐ NEW (L2)

| OC | **5/5** (multi-turn for propose, multi-tool, persistent state, human review at merge, bounded budget) | cron | 1/5 (event-driven, not scheduled) |

**Verdict: OpenClaw primary.** Kimi K2.6 via OpenClaw is the natural
fit — propose-only quarantine, human review gate. This is the **only**
cell where OpenClaw is the primary runtime.

### #10 gap-scanner-cell (L2)

| OC | 1/5 (Ollama local, no MCP needed) | cron | 5/5 (weekly, deterministic, single-purpose, low frequency) |

**Verdict: cron-agent-python primary** (Ollama).

### #11 kg-cell (L2)

| OC | 2/5 (sometimes multi-tool when KG auto-expansion fires) | cron | 5/5 (every 6h, replayable, single-purpose) |

**Verdict: cron-agent-python primary** + Fly backend HTTP call.

### #12 research-cell (L2)

| OC | 1/5 (NotebookLM call only) | cron | 5/5 (staggered Mon-Fri 02:10-02:50) |

**Verdict: cron-agent-python primary** (NotebookLM is the substrate, not OC).

### #13 war-room-organism (L3)

The whole organism contains 9 cognitive + 4-7 operational organelle, each
with its own runtime. The organism-as-a-whole has no single runtime.

Per-organelle scoring already in §B2 audit. Most organelle are LaunchAgent +
DB triggers (event-driven via EventBus, no agent runtime needed). The
**3 OpenClaw insertions of round 1 are dismissed** (Track B3 verdict).

**Verdict: LaunchAgent primary, EventBus-driven** (no OpenClaw needed
for the organelle layer; OC stays in the developer layer for Lobster
workflows + Telegram channel).

### #14 mata-garuda-cell ⭐ NEW (L4.5)

| OC | 2/5 (multi-tool meta-research, sometimes review) | cron | 5/5 (19 LaunchAgents on staggered schedules) |

**Verdict: LaunchAgent primary.** Like war-room-organism, this is a
federation of LaunchAgents not a single agent process.

## Summary table

| # | Cell | Primary runtime | Hybrid sub-step? |
|---|---|---|---|
| 1 | system-doctor-cell | cron-agent-python | — |
| 2 | seo-guardian-cell | cron-agent-python | — |
| 3 | fact-checker-cell | cron-agent-python | — |
| 4 | tech-orchestrator-cell | cron-agent-python | **OpenClaw** when task.tool_count ≥3 OR risk=HIGH |
| 5 | conversation-trainer-cell | cron-agent-python | — |
| 6 | daily-ops-cell | cron-agent-python | — |
| 7 | crm-cell | cron-agent-python + EventBus | — |
| 8 | intel-scraper-cell (light) | cron-agent-python + OpenClaw cron wrapper | OpenClaw for intel-radar (Sprint 8) |
| 9 | hgt-coordinator-cell ⭐ | **OpenClaw** | — |
| 10 | gap-scanner-cell | cron-agent-python (Ollama) | — |
| 11 | kg-cell | cron-agent-python + Fly HTTP | — |
| 12 | research-cell | cron-agent-python + NotebookLM | — |
| 13 | war-room-organism | LaunchAgent + EventBus | — |
| 14 | mata-garuda-cell ⭐ | LaunchAgent | — |

**Quantitative outcome:**
- 11/14 cells have cron-agent-python (or LaunchAgent for federations) as primary
- 1/14 (hgt-coordinator) has OpenClaw as primary
- 1/14 (tech-orchestrator) is hybrid
- 1/14 (intel-scraper light) has a sub-cell (intel-radar) that may migrate to OpenClaw in Sprint 8

This **strongly validates** the round 2 brainstorm 4/4 unanime Opzione C
("split clean"): OpenClaw is the right home for the rare interactive
multi-turn case, not the scheduled batch grind.

## Risk callouts

- **Reliability inversion** (Codex risk): if we move a stable cron-agent-python
  strategy to OpenClaw before fixing the OC scheduler (frozen since
  2026-04-30), we lose SLA. Mitigation: only intel-radar is candidate for
  OC migration, and only AFTER Track A4 upgrade verifies the scheduler
  unfreeze. Sprint 8.
- **Single-host SPOF**: OpenClaw has no federation; cron-agent-python
  must remain functional even if OpenClaw is down. The 11/14 primary
  cron-agent-python verdict ALREADY ensures this.
- **Cost drift**: OpenClaw multi-model fallback could multiply LLM calls
  if a cell's task hits a fallback chain repeatedly. Mitigation: per-cell
  budget cap declared in cell definition (admission test Law 5
  bounded-action requirement).

## References

- `docs/cell-core/cognitive-levels-matrix.md` (the 14 cells)
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/01b_codex_round2.md` § "3/5 quantitative criterion"
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md` § "Q2 unanimous Opzione C"
- `docs/audits/sprint0/wr2-openclaw-insertions-duplication.md` (Track B3 — 3 round-1 insertions dismissed)
