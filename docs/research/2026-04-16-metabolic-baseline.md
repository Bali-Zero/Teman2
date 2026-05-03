# Metabolic Baseline T0 — 2026-04-16

> SYMBIOSIS Pillar 7: "Without metrics, 'grows' is an opinion."
> This is T0. Every future measurement is compared against these numbers.

## Snapshot

| Metric | Value | Unit | Direction | Source |
|--------|-------|------|-----------|--------|
| **M1 TTR** | 869.00 | pulses | Lower is better | cell_pulse_log (PG) — 1 episode of 869 consecutive non-green pulses |
| **M2 DO** | 2.2092 | edges/node | Higher is better | kg_nodes=113,854, kg_edges=251,522 (PG Fly) |
| **M3 IA** | 1.00 | ratio (0-1) | Higher is better | 888 endogenous (cron+pulse), 0 exogenous (no Claude sessions in 24h window) |
| **M4 FE** | 0.01 | ratio (0-1) | Lower is better | 9 escalations / 888 total actions |

## Timestamp

- **Calculated at:** 2026-04-15T19:38:27Z (UTC) / 2026-04-16 03:38 WITA
- **Machine:** Air (antonellosiano@Nuzantara-9)
- **PG source:** Fly tunnel on localhost:15432

## Methodology

### M1 — Time-to-Resolution (TTR)
Counts contiguous runs of `health_status != 'green'` in `cell_pulse_log`.
Each run = one "episode". TTR = mean(episode_lengths).
**Observation:** 1 massive episode of 869 pulses indicates the cell has been in a sustained degraded state. This is expected — the cell runs `check_health` every 60s and the backend has been occasionally returning slow responses (3000-3500ms).

### M2 — Ontological Density (DO)
`COUNT(kg_edges) / COUNT(kg_nodes)` from PostgreSQL.
**Observation:** 2.2092 means on average each KG node has ~2.2 relationships. This is below the 2.5 target for a mature knowledge graph. The 4 subgraphs (Company, Visa, Property, Tax) have varying density.
**Note:** Values differ from CLAUDE.md (108,068/242,827=2.247) because the KG has grown since last documentation update. Updated numbers: 113,854 nodes, 251,522 edges.

### M3 — Autonomy Index (IA)
`endogenous_count / (endogenous + exogenous)`.
- Endogenous: cron JSONL (`status=ok`) + cell pulse actions (`action_taken IS NOT NULL`)
- Exogenous: MOS sessions started in last 24h
**Observation:** IA=1.0 because no Claude Code sessions were started on Air in the last 24h window. The 888 endogenous actions are from cron jobs and cell pulse checks. This will normalize when measured across both machines.

### M4 — Escalation Frequency (FE)
`escalation_count_24h / total_actions_24h`.
**Observation:** 9 escalations out of 888 total actions = 0.01 (1%). Very low — most DLQ autopilot escalations in `escalations_pro.jsonl` are older than 24h.

## Known Limitations

1. **TTR is pulse-based, not time-based**: A "pulse" is ~60s, so 869 pulses ≈ 14.5 hours. Future: add TTR_minutes = TTR * pulse_interval.
2. **IA skewed on single machine**: Air has all cron actions but no recent Claude sessions. True IA requires aggregation across Air+Pro. Future: federation sync of metrics.
3. **DO lacks per-subgraph breakdown**: Need to add subgraph column queries to the collector. Future: `kg_nodes.entity_type` GROUP BY.
4. **FE denominator varies**: More cron jobs = lower FE even if escalation count stays same. This is intentional — a busier organism with same escalation count is handling more load.

## Next Measurement

- **T+7:** 2026-04-23 — first weekly comparison
- **T+30:** 2026-05-16 — first monthly comparison (EMA meaningful)

## Storage

- SQLite: `~/.agent/decisions/organism_metrics.db`
- Redis: `organism:metrics` stream (4 entries per snapshot)
- Cron log: `~/logs/cron/metabolic-rollup.jsonl`
- State: `~/.agent/decisions/state/metabolic_rollup.last.json`
