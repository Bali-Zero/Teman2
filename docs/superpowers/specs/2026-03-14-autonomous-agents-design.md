# Autonomous Self-Growing Agents

**Date:** 2026-03-14
**Status:** APPROVED
**Scope:** Reusable autonomous agent pattern + SEO Guardian (first prototype)

---

## Problem

Nuzantara has powerful tools (MCP, OpenClaw cron, GSC/GA4 APIs, KBLI indexer) but they only execute when a human triggers them. There's no system that:

- Continuously observes data sources for opportunities
- Takes low-risk actions autonomously
- Measures impact of those actions
- Learns from results and human corrections

## Solution: Autonomous Agent Pattern

### Core Cycle

```
OBSERVE → DECIDE → ACT → MEASURE → LEARN
   ↑                                  |
   └──────────────────────────────────┘
```

Each agent runs as OpenClaw cron jobs (not a new framework), stores state in files (not a database), and uses existing MCP tools for actions.

### Autonomy Model

Risk-based decision making:

| Risk Level | Autonomy                            | Example                                        |
| ---------- | ----------------------------------- | ---------------------------------------------- |
| **LOW**    | Fully autonomous                    | Submit indexing batch, update meta description |
| **MEDIUM** | Auto-execute + confirm via Telegram | Add FAQ schema, modify article metadata        |
| **HIGH**   | Approval required before execution  | Edit article body, remove page, change URL     |

### Memory Architecture

File-based, per agent, synced via Syncthing between Pro/Air:

```
~/.openclaw/workspace/autonomous/<agent-name>/
├── config.yaml           # Identity, data sources, risk thresholds, schedule
├── memory.jsonl          # Append-only: every action + measured result
├── patterns.json         # Learned rules extracted from memory.jsonl
├── corrections.jsonl     # Human feedback (permanent overrides)
├── state.json            # Runtime state (last run, current metrics, baseline)
└── decisions.log         # Human-readable decision log for audit
```

### config.yaml Template

```yaml
agent:
  name: "<agent-name>"
  version: "1.0"
  description: "<what this agent does>"

observe:
  sources:
    - type: "script" # Python script with structured JSON output
      path: "<path>"
      args: ["--mode", "report"]
    - type: "mcp" # MCP tool called by Claude inside the cron prompt (not shell CLI)
      call: "nuzantara-mcp.<tool>"
    - type: "file" # Read state from file
      path: "<path>"

decide:
  risk_levels:
    LOW: ["<action1>", "<action2>"]
    MEDIUM: ["<action3>", "<action4>"]
    HIGH: ["<action5>", "<action6>"]
  max_actions_per_run:
    LOW: 10
    MEDIUM: 3

act:
  tools:
    - "<Python script (shell) or MCP tool (called by Claude in cron prompt)>"
  dry_run: false # Set true for testing

measure:
  delay_hours: 48
  metrics: ["<metric1>", "<metric2>"]

learn:
  min_samples: 5
  confidence_threshold: 0.7
  human_override: true # corrections.jsonl always takes priority

delivery:
  channel: "telegram"
  to: "1125336968"
  report_format: "markdown"
```

### How to Add a New Agent

1. Create directory `~/.openclaw/workspace/autonomous/<name>/`
2. Copy and adapt `config.yaml` with agent-specific sources, risk levels, tools
3. Create 2-3 cron jobs in OpenClaw (observe, measure, weekly-learn)
4. Cron prompt follows the same schema: load state → check corrections → observe → decide → act(low) → confirm(medium) → log

### What This Pattern Is NOT

- **Not a custom framework** — runs as OpenClaw cron + JSONL files
- **Not a database** — file-based, Syncthing-synced
- **Not ML** — "patterns" are statistical rules (e.g., "FAQ schema → +15% CTR"), not trained models
- **Not multi-agent** — each agent is independent; weekly-report handles coordination

---

## SEO Guardian Agent (First Prototype)

### Data Sources

| Source                    | Access Method                                                    | Frequency |
| ------------------------- | ---------------------------------------------------------------- | --------- |
| **Google Search Console** | `seo_guardian_core.py` (SA as siteOwner)                         | Daily     |
| **GA4**                   | Analytics Data API (property `505466833`)                        | Daily     |
| **KBLI Indexing State**   | `apps/evaluator/indexing_state.json`                             | On-demand |
| **Articles Published**    | `apps/bali-intel-scraper/data/published_articles.json` + git log | On-demand |
| **Qdrant KBLI**           | MCP `search_kbli` for content validation                         | On-demand |

### OBSERVE (daily 07:00 WITA)

1. GSC: query performance (impressions, clicks, CTR, position) last 7 days
2. GSC: pages with high impressions / zero clicks (CTR opportunities)
3. GA4: bounce rate per landing page, avg session duration
4. Indexing status: KBLI pages indexed vs pending
5. GSC coverage errors: 404, soft 404, crawl errors

### DECIDE (risk classification)

| Action                                     | Risk   | Autonomy                 |
| ------------------------------------------ | ------ | ------------------------ |
| Submit batch URL for indexing (≤50)        | LOW    | Autonomous               |
| Update meta title/description on KBLI page | LOW    | Autonomous               |
| Report anomalous CTR                       | LOW    | Autonomous (report only) |
| Add FAQ schema JSON-LD to pages            | MEDIUM | Auto + Telegram confirm  |
| Modify article metadata                    | MEDIUM | Auto + Telegram confirm  |
| Create redirect                            | MEDIUM | Auto + Telegram confirm  |
| Edit article body content                  | HIGH   | Approval required        |
| Remove/redirect pages                      | HIGH   | Approval required        |
| Change URL structure                       | HIGH   | Approval required        |

### ACT (available tools)

- `apps/evaluator/kbli_indexing_submit.py` — batch Google Indexing API submission
- `apps/evaluator/articles_indexing_submit.py` — articles submission
- MCP `compose_article` / `publish_article` — new content (called by Claude inside cron prompt)
- MCP `search_kbli` — content validation (called by Claude inside cron prompt)
- Git commit on `apps/mouth/` — metadata/schema changes

### MEASURE (48h post-action)

- CTR delta on modified pages
- Average position delta
- New pages indexed (GSC coverage)
- Errors introduced (404, console errors)

### LEARN

- After 5+ samples per action type → extract pattern into `patterns.json`
- Example: `{"action": "add_faq_schema", "avg_ctr_delta": "+15%", "confidence": 0.82, "sample_size": 12}`
- Human corrections in `corrections.jsonl` always override learned patterns
- Example: `{"rule": "never_touch", "scope": "/lifestyle/*", "reason": "owner preference", "date": "2026-03-14"}`

### Cron Schedule

| Job                    | Schedule          | Purpose                              |
| ---------------------- | ----------------- | ------------------------------------ |
| `seo-guardian-observe` | Daily 07:00 WITA  | OBSERVE + DECIDE + ACT (low risk)    |
| `seo-guardian-measure` | Daily 07:30 WITA  | MEASURE actions from previous days   |
| `seo-guardian-weekly`  | Monday 08:00 WITA | Weekly report + LEARN pattern update |

### Prompt Structure

Each cron prompt follows this flow:

1. **Context injection**: read `state.json` and `patterns.json`
2. **Corrections gate**: read `corrections.jsonl` — human rules override any decision
3. **Action plan**: generate plan with risk level per action
4. **Execution**: execute LOW risk only, request Telegram confirmation for MEDIUM
5. **Logging**: write every action to `memory.jsonl` with timestamp and expected outcome

---

## Agent Roadmap

| Priority   | Agent               | Data Sources                             | LOW Risk Actions               | HIGH Risk Actions                              |
| ---------- | ------------------- | ---------------------------------------- | ------------------------------ | ---------------------------------------------- |
| **Tier 1** | SEO Guardian        | GSC, GA4, indexing state                 | Submit indexing, update meta   | Edit content, remove pages                     |
| **Tier 2** | Content Engine      | Published articles, GSC, competitors     | Suggest topics, draft outline  | Publish article, modify live content           |
| **Tier 2** | Compliance Sentinel | Visa expiry, KBLI changes, regulations   | Alert deadlines, weekly report | Modify client status, send client notification |
| **Tier 3** | CRM Predictor       | Client interactions, journeys, revenue   | Score leads, alert inactivity  | Modify client stage, send communication        |
| **Tier 3** | Infra Guardian      | Fly.io metrics, Qdrant stats, error logs | Restart services, scale down   | Scale up (cost), deploy, DB migration          |

Each agent follows the same pattern and directory structure. New agents are added by creating a directory, adapting `config.yaml`, and adding cron jobs.

---

## Implementation Order

### Phase 1: Infrastructure (30 min)

- Create `~/.openclaw/workspace/autonomous/seo-guardian/` directory
- Write `config.yaml`, initial `state.json`, empty `patterns.json`
- Create `corrections.jsonl` with base rules

### Phase 2: OBSERVE Script (60 min)

- Refactor `seo_guardian_core.py`: add `argparse` CLI with `--mode report` flag
- Add structured JSON output serialization (currently only logger output)
- Add GA4 metrics via Analytics Data API (bounce rate, session duration per page)
- Fix `published_articles.json` path to `apps/bali-intel-scraper/data/published_articles.json`
- Output → updated `state.json` + `opportunities.json`
- Test: manual run, verify JSON output

### Phase 3: DECIDE + ACT Logic (45 min)

- New script: `apps/evaluator/seo_guardian_agent.py`
- Reads `state.json` + `patterns.json` + `corrections.jsonl`
- Classifies actions by risk, executes LOW, prepares MEDIUM for confirmation
- Writes every action to `memory.jsonl`
- Test: dry-run mode (log actions without executing)

### Phase 4: MEASURE (30 min)

- Script that compares pre/post metrics (from `memory.jsonl` + GSC)
- Updates `memory.jsonl` with measured result
- After 5+ samples per action type → updates `patterns.json`

### Phase 5: OpenClaw Cron Jobs (15 min)

- `seo-guardian-observe`: daily 07:00 WITA
- `seo-guardian-measure`: daily 07:30 WITA
- `seo-guardian-weekly`: Monday 08:00 WITA (report + learn)

### Phase 6: Validation (30 min)

- Full run: observe → decide → act (dry-run)
- Verify Telegram delivery
- Verify memory/state files written correctly
- Activate cron, monitor first real run

---

## Guardrails

- **Max actions per run**: 10 LOW + 3 MEDIUM (hardcoded in config)
- **Dry-run mode**: `--dry-run` flag on every script
- **Kill switch**: `state.json` contains `"paused": true` → agent does nothing
- **Corrections override**: `corrections.jsonl` rules have absolute priority over any learned pattern
- **Git safety**: every change is an atomic commit, never `--force`, never amend
- **Rollback per action**: every action in `memory.jsonl` includes `git_sha` → `git revert`

## Rollback

| Component                      | How to undo                                                       |
| ------------------------------ | ----------------------------------------------------------------- |
| Agent directory                | `rm -rf ~/.openclaw/workspace/autonomous/seo-guardian/`           |
| Cron jobs                      | Disable 3 jobs in `~/.openclaw/cron/jobs.json` (`enabled: false`) |
| Agent script                   | `seo_guardian_agent.py` is new, just don't execute it             |
| SEO changes made by agent      | Every action in `memory.jsonl` has `git_sha` → `git revert`       |
| `seo_guardian_core.py` changes | Additive (new output mode), backward compatible                   |
