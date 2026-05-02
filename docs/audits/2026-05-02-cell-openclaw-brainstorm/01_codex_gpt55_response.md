## Q1 — Cell-core as automation substrate

### Verdict
CONCUR con il reasoning di Claude Opus.

### Reasoning (max 300 parole)
Selective delegation is the right cut. The briefing already separates automations into 7 LLM-in-loop jobs, 8 observability/sensor jobs, 15 ingestion pipelines, and 10 maintenance jobs. Cell-core adds value when an automation repeatedly does sense->think->act->reflect, benefits from Genome memory, adapts cadence through Homeostasis, or can share learned procedures/scars through HGT. That fits system-doctor, seo-guardian, fact-checker, tech-orchestrator, gap-scanner, kg-builder, research, intel-scraper, and war-room style flows.

It does not fit most cron/LaunchAgent jobs whose job is deterministic ETL, backup, snapshot, cleanup, heartbeat, or one-shot publishing. Wrapping those in PulseLoop/Genome/HGT would add state, Redis/SQLite dependencies, debugging surface, and failure modes without improving decisions.

Promotion threshold: promote only if all are true: recurring non-deterministic judgment, observable outcome feedback, cross-run memory changes future behavior, bounded actuation, and cadence or tool choice benefits from adaptation. A weaker threshold is enough for a partial cell wrapper: LLM classification/enrichment plus scars/outcome tracking, but no autonomous action.

### Disagreements (se PARTIAL/DISAGREE)
None material.

### Missed cases (se ne hai)
The `apps/evaluator/seo_cell` pattern matters: cron-driven single-pulse cells are a better migration model than daemons for many jobs. Also consider an "observed shell" tier: non-cell automations emit pulse-like metrics/events to organism/observatory without importing cell-core.

### Risk callouts
Biggest risk is coupling operational reliability to biological abstractions. Keep maintenance/backup/healthcheck paths independent, require idempotent actions, and prevent HGT from auto-promoting unsafe skills into production workflows.

## Q2 — OpenClaw placement

### Verdict
PARTIAL con il reasoning di Claude Opus.

### Reasoning (max 300 parole)
The direction is right: OpenClaw should be reserved for cheap-frontier, always-on, multi-tool reasoning, not for big-context Claude/Codex/Gemini jobs. The proposed candidates mostly match that: fact-checker, tech-orchestrator, seo-guardian-observe, gap-scanner, and HGT coordinator can require repeated judgment, tool use, and cheap model routing.

The three conditions are close but too rigid. Cross-call state does not need to live in OpenClaw; it can live in PG, Qdrant, Genome, or EventBus. The real gate is whether durable state changes future decisions. I would use four gates: H24 or high-frequency reasoning, multi-step tool loop, durable decision memory, and bounded/autonomous action surface with budget caps.

Cost of $10-15/month is plausible only with strict call ceilings, short contexts, loop limits, and fallback discipline. The measured per-call costs are tiny, but agentic retries, long contexts, Telegram chatter, and tool loops can dominate.

### Disagreements (se PARTIAL/DISAGREE)
Add `system-doctor` as a candidate if it moves beyond reporting into multi-log triage, hypothesis ranking, and bounded remediation suggestions. Treat `gap-scanner` as OpenClaw only if it plans follow-up probes; deterministic scans plus LLM labeling should stay shell. Keep HGT coordinator out of the critical write path: it should propose, audit, and quarantine conflicts, not directly merge skills.

### Missed cases (se ne hai)
Conversation-trainer and daily-ops may qualify later if they become persistent, tool-using loops. Today they sound more like scheduled LLM synthesis unless proven otherwise.

### Risk callouts
Primary risks: runaway loops, duplicate actions, noisy Telegram routing, hidden cost drift, and degraded debuggability versus shell scripts. Require per-agent budgets, trace IDs, max-steps, replayable decisions, and kill switches.

## Q3 — Intel Scraper and War Room 2.0

### Verdict
PARTIAL con il reasoning di Claude Opus.

### Reasoning (max 300 parole)
Intel Scraper: concur. Cell-core partial is appropriate because it has recurring classification/enrichment, state in Qdrant/EventBus, and useful scars such as bad source, duplicate pattern, enrichment failure, or SEO validation drift. OpenClaw should stay NO for the main path: the pipeline is explicitly linear, LLM optional, and non-gating. A shell/orchestrated DAG is more debuggable.

War Room 2.0: concur directionally. The mapping to cell-organism is coherent: Trend-Hunter as sensor, Research/Consiglio as reasoner, Drafter/Publisher as act, Validator as SafetyGate, Measurer/Learner as reflection, and future L1-L4 as connector/dream/mature. But implement this as module-boundary cell semantics, not a wholesale rewrite of the 14-module pipeline.

The three OpenClaw insertions are mostly right: L1 Connector cross-dossier thesis, M14 Learner night loop, and cheap Trend-Hunter pre-filter. They are cheap-frontier, repeated, stateful, and tool-using enough to justify OpenClaw. Keeping Consiglio, Drafter, and Visual direct is correct because their value comes from deliberate model diversity, Claude tone quality, and Imagen-specific generation.

### Disagreements (se PARTIAL/DISAGREE)
For Intel Scraper, allow a narrow OpenClaw exception only for anomaly triage outside the main daily path: source failures, contradictory classifications, or repeated enrichment gaps. For WR2, consider Research retrieval planning as a fourth possible OpenClaw point if it dynamically chooses Qdrant/web/KG probes before Consiglio.

### Missed cases (se ne hai)
Review Gate Telegram should remain a hard human gate, but OpenClaw could prepare concise reviewer diffs and risk notes. Layout QA may benefit from browser/vision automation, but not necessarily OpenClaw unless it loops across fixes.

### Risk callouts
WR2 risks are publication-path latency, legal/tone drift, HGT poisoning across dossiers, duplicated state between Qdrant/EventBus/KG/Genome, and accidental bypass of Legge 5. Intel Scraper risks are making optional LLM steps gating and losing deterministic replayability.
