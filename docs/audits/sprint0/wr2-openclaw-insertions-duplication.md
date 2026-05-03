# WR2 OpenClaw insertions — duplicate detection vs cron-agent-python — Sprint 0 Track B3

**Date:** 2026-05-02 · **Author:** Sprint 0 Air session (Claude Opus 4.7 1M)
**Reference:** brainstorm 2026-05-02 round 2 § "3 OpenClaw insertions WR2 vs intel-feed-processor"

## The 3 OpenClaw insertions proposed in round 1

| # | Name | Purpose (round 1) | Proposed model |
|---|---|---|---|
| 1 | **L1 Connector cross-dossier thesis** | Multi-tool reasoning to connect dossiers across topics (query Qdrant + web search + synthesis) | Kimi K2.6 via OpenClaw |
| 2 | **Learner M14 feedback loop nightly** | Reflective learning: ingest M13 metrics, generate skills/scars deltas | DeepSeek-Reasoner via OpenClaw |
| 3 | **Trend-Hunter intake pre-filter** | Cheap fanout filter on raw signals before they reach Consiglio | MiniMax M2.7 via OpenClaw |

DeepSeek round 2 raised the question: are these 3 *already* implemented by
existing live components — `cron-agent-python intel-radar`,
`intel-feed-processor`, `connector` LaunchAgent, `dossier-compiler`?

## Empirical answer (per insertion)

### Insertion #1 — L1 Connector cross-dossier thesis

**Existing live component:** `com.balizero.wr2.connector` LaunchAgent (cron
04:00 WITA daily) → invokes `backend.services.cognitive.connector_cli` →
`ConnectorOrchestrator.run()` which uses `ClaudeCLIRunner` to call **Claude
CLI subprocess** (NOT OpenClaw) for cross-dossier reasoning. Inserts into
`cross_dossier_theses` table.

**Round-2 ground truth:**

| Aspect | LaunchAgent today | OpenClaw insertion proposal |
|---|---|---|
| LLM | Claude CLI subprocess (OAuth Max) | Kimi K2.6 via OpenClaw |
| Cost | $0 (Claude Max plan, banned ANTHROPIC_API_KEY) | OpenClaw routing → Kimi cost |
| Cadence | Cron daily 04:00 | "On demand" via Lobster workflow |
| Persistence | DB INSERT into `cross_dossier_theses` (mig 114) | (proposed) DB INSERT same |
| State | Symbiosis Confrontation pillar | Same |

**Verdict — DUPLICATE in spirit but DIFFERENT in implementation.** The
existing LaunchAgent already does cross-dossier thesis generation via
Claude CLI. Going through OpenClaw + Kimi K2.6 would:
- Add a paid LLM call where today we have a free Claude Max subscription
  (violates global cost rule "no Anthropic paid API" — but Kimi != Anthropic,
  so technically OK; still adds cost).
- Add OpenClaw as a runtime dependency (a SPOF — DeepSeek round 2 risk).

**Recommendation:** **DISMISS the OpenClaw insertion**. Keep the existing
LaunchAgent. Re-evaluate when OpenClaw v2026.4.29 + Knowledge Agents
v12.1.0 are stable on Pro (Sprint 4+).

### Insertion #2 — Learner M14 feedback loop nightly

**Existing live component:** `com.balizero.wr2.learner-nightly` LaunchAgent
(cron 03:00 WITA daily) → invokes `backend.services.learner.learner_cli` →
M14 retrain pipeline reading `m13_retrain_log` and producing skills/scars.

**Round-2 ground truth:**

| Aspect | LaunchAgent today | OpenClaw insertion proposal |
|---|---|---|
| LLM | Claude CLI subprocess for skills/scars classification | DeepSeek-Reasoner via OpenClaw |
| Cost | $0 | DeepSeek API ~$0.01/run (allowed under cost rule) |
| Cadence | Cron nightly 03:00 | Cron nightly via OpenClaw scheduler (24-job queue, currently frozen) |
| Persistence | INSERT into `m13_retrain_log`, skills/scars files | Same |
| State | Symbiosis Reflection pillar | Same |

**Verdict — DUPLICATE.** Same component. Same cadence. Same persistence.
The OpenClaw insertion would just route through Kimi/DeepSeek instead of
Claude CLI — a value choice, not a feature gap.

**Recommendation:** **DISMISS the OpenClaw insertion.** The LaunchAgent
runs reliably today. Maybe Sprint 7 (hybrid runtime fact-checker /
tech-orchestrator / daily-ops) is the right place to revisit IF DeepSeek
shows clearly better quality on M14 skill extraction — but a benchmark
needs to be run first, not assumed.

### Insertion #3 — Trend-Hunter intake pre-filter

**Existing live component:** `com.balizero.wr2.trend-hunter` LaunchAgent
(every 2h) → invokes `backend.services.intel.trend_hunter.cli` →
`backend.services.intel.dossier_repository.insert_trend_signal` (INSERT
into `trend_signals` table, mig 113). The current pipeline inserts EVERY
trend signal regardless of confidence; downstream Consiglio reads them.

**The OpenClaw insertion proposal**: a *pre-filter* between Trend-Hunter
and Consiglio that uses MiniMax M2.7 to cull low-confidence signals
before they reach the Council deliberation.

**Round-2 ground truth:**

| Aspect | Pipeline today | OpenClaw insertion proposal |
|---|---|---|
| Filter logic | None (all signals reach Consiglio) | LLM filter at confidence < 0.6 |
| Cost | $0 (Consiglio runs anyway) | MiniMax M2.7 ~$0.005/signal |
| Trade-off | Consiglio cost grows with signal volume | Pre-filter cost vs Consiglio cost saving |

**Verdict — NOT DUPLICATE; this is a NEW CAPABILITY.** Today's pipeline has
no pre-filter; if signal volume becomes the bottleneck, this insertion
would add value. But:

- DeepSeek round 2 added a **recall safety guard**: confidence <0.6
  signals MUST still reach Consiglio (so the pre-filter is a *deprioritise*,
  not a *cull*). That changes the cost calculus to "tag low-confidence
  for batch deferral" instead of "drop low-confidence".
- Symbiosis Confrontation pillar wants every signal to be *seen* by some
  cell, even if it's deferred. Hard-cull violates that.

**Recommendation:** **KEEP the proposal but redesign as a confidence-tag,
not a pre-filter cull.** This becomes Sprint 5 work IF and only IF
empirical metrics show Consiglio is overwhelmed (signal/Consiglio_call
ratio > X). Until then, no insertion.

## Summary table

| Insertion | Verdict | Action |
|---|---|---|
| #1 L1 Connector | **DUPLICATE** | DISMISS — existing LaunchAgent uses Claude CLI subprocess |
| #2 Learner M14 | **DUPLICATE** | DISMISS — existing LaunchAgent uses Claude CLI subprocess |
| #3 Trend pre-filter | NEW capability, but **NOT YET NEEDED** | DEFER until Consiglio overload is empirically observed; then redesign as confidence-tag, not cull |

**Net round-2 deltas:**
- Round 1 said: "3 OpenClaw insertions Sprint 5"
- Round 2 says: "**0 OpenClaw insertions Sprint 5** (defer all 3)". Sprint 5
  is then freed up for the **kg-cell + research-cell + gap-scanner-cell**
  promotion work that was originally planned for Sprint 6.

The brainstorm round 2 sprint list still shows Sprint 5 = "OpenClaw
insertions WR2"; that's **stale**. The handoff doc (D3 wrap) updates the
Sprint 5 scope.

## Risk callouts

- **Quality drift**: if Kimi K2.6 cross-dossier theses are empirically
  better than Claude CLI's, dismissing insertion #1 forfeits that quality.
  Mitigation: run a 1-week A/B (Sprint 4 or 5) before the final dismiss.
  Not blocking Sprint 0 → Sprint 4 work.
- **OpenClaw v2026.4.29 unfreezes the scheduler** (Track A4) and the 24
  frozen jobs include something that *would* invoke an LLM-task
  subprocess. Track A5 disable plan covers this.
- **Lobster workflows reference these insertions** somewhere: grep across
  `~/.openclaw/workspace/workflows/*.lobster` to confirm they don't.
  (Pro is SSH-unreachable at audit time; Sprint 0 follow-up.)

## References

- `apps/backend-rag/backend/services/cognitive/connector_cli.py` (existing L1 Connector)
- `apps/backend-rag/backend/services/cognitive/connector.py` (ConnectorOrchestrator)
- `apps/backend-rag/backend/services/learner/learner_cli.py` (existing M14)
- `apps/backend-rag/backend/services/intel/trend_hunter/__init__.py` (existing Trend-Hunter)
- `apps/backend-rag/backend/services/intel/dossier_repository.py` (`insert_trend_signal`)
- `apps/backend-rag/backend/db/migrations_v2/113_intel_radar_findings.sql` (`trend_signals` trigger)
- `apps/backend-rag/backend/db/migrations_v2/114_cognitive_layer_tables.sql` (`cross_dossier_theses` trigger)
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/03b_deepseek_round2.md` § "3 OpenClaw insertions"
