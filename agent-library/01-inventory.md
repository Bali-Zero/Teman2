# Agent Library — Inventory (auto-generated 2026-05-16 08:17 WITA)

<!-- regenerate: python3 agent-library/_generate-inventory.py -->
<!-- DO NOT hand-edit — changes will be overwritten -->

**Snapshot**: 16 Claude subagents · 35 agentic crons / 106 infra crons (141 total launchd) · 25 skills · 14 cross-tool entries

## Quick index

| Name | Type | Model | Tools |
|---|---|---|---|
| client-case-quote-generator | subagent | opus | Read, Write, Edit, Bash, WebFetch |
| competitor-monitor | subagent | sonnet | Read, Write, Bash, WebFetch |
| deep-researcher | subagent | opus | Read, Write, Bash, WebFetch, WebSearch |
| devils-advocate | subagent | sonnet | Read, Bash, WebFetch |
| email-template-builder | subagent | sonnet | Read, Write, Edit, Bash, Glob, Grep |
| nb-curator | subagent | sonnet | Read, Write, Bash, Glob, Grep |
| regulatory-watcher | subagent | sonnet | Read, Write, Bash, WebFetch |
| wr2-brief-interpreter | subagent | sonnet | Read, Glob, Grep, Bash, WebFetch |
| wr2-critic | subagent | opus | Read, Write, Glob, Grep, Bash |
| wr2-design-architect | subagent | opus | Read, Write, Edit, Glob, Grep, Bash, Skill, Agent, WebFetch |
| wr2-external-bench | subagent | opus | Read, Write, Bash, WebFetch, WebSearch |
| wr2-ig-metrics-analyst | subagent | sonnet | Read, Write, Bash, Glob, Grep |
| wr2-image-prompt-author | subagent | opus | Read, Glob, Grep |
| wr2-layout-composer | subagent | sonnet | Read, Write, Edit, Glob, Grep, Bash |
| wr2-storyboarder | subagent | sonnet | Read, Glob, Grep, Bash |
| yield-optimizer | subagent | sonnet | Read, Bash |
| Nuzantara project identity, stack, golden rules and owner pr | cursor-rule | — | — |
| FastAPI backend rules — Python patterns, async, imports, tes | cursor-rule | — | — |
| Next.js frontend rules — TypeScript, Tailwind, App Router pa | cursor-rule | — | — |
| Deploy rules — Fly.io backend, Vercel frontend, Dockerfile c | cursor-rule | — | — |
| KBLI 2025 rules — Indonesian business classification codes, | cursor-rule | — | — |
| backend-deploy | gemini-skill | — | — |
| batch-processor | gemini-skill | — | — |
| crm-data-extraction | gemini-skill | — | — |
| db-query | gemini-skill | — | — |
| frontend-qa | gemini-skill | — | — |
| git-commit-helper | gemini-skill | — | — |
| nuzantara-domain-knowledge | gemini-skill | — | — |
| ocr-document-reader | gemini-skill | — | — |
| prompt-enhancer | gemini-skill | — | — |
| browser | skill | — | — |
| canva-apply | skill | — | — |
| canva-reset-template | skill | — | — |
| drive-upload | skill | — | — |
| federation-dispatch | skill | — | — |
| fly-cost-calculator | skill | — | — |
| AVTF Loop | skill | — | — |
| nuzantara-code-quality | skill | — | — |
| nuzantara-crm-operations | skill | — | — |
| nuzantara-db-migration | skill | — | — |
| nuzantara-debug-production | skill | — | — |
| Nuzantara Debug Assistant | skill | — | — |
| nuzantara-deploy-full | skill | — | — |
| Nuzantara Deployment | skill | — | — |
| nuzantara-flowkit-flow-generation | skill | — | — |
| nuzantara-kg-operations | skill | — | — |
| nuzantara-llm-test | skill | — | — |
| nuzantara-monitoring | skill | — | — |
| nuzantara-parallel-dev | skill | — | — |
| nuzantara-send-email | skill | — | — |
| nuzantara-spec-driven-dev | skill | — | — |
| nuzantara-tdd | skill | — | — |
| nuzantara-vector-search | skill | — | — |
| software-architecture | skill | — | — |
| wr2-carousel-pipeline | skill | — | — |

## Claude Code subagents

### client-case-quote-generator

- **Model**: opus
- **Tools**: Read, Write, Edit, Bash, WebFetch
- **Description**: Generates a Bali Zero internal-print A4 PDF client quote (visa/property/tax/regulatory) covering cost, timeline, risk, d
- **File**: `/Users/nuzantara/.claude/agents/client-case-quote-generator.md`

### competitor-monitor

- **Model**: sonnet
- **Tools**: Read, Write, Bash, WebFetch
- **Description**: Monthly digest of Bali Zero's three direct competitors (Lets Move Indonesia, Emerhub, Flado) on web + Instagram. Detects
- **File**: `/Users/nuzantara/.claude/agents/competitor-monitor.md`

### deep-researcher

- **Model**: opus
- **Tools**: Read, Write, Bash, WebFetch, WebSearch
- **Description**: Multi-LLM deep research agent for client cases and policy questions. Coordinates Claude Opus (synthesis), Gemini 3.1 Pro
- **File**: `/Users/nuzantara/.claude/agents/deep-researcher.md`

### devils-advocate

- **Model**: sonnet
- **Tools**: Read, Bash, WebFetch
- **Description**: Red-team contrarian agent. Receives a finished dossier/research/quote/strategy and tries to DESTROY its assumptions. Sys
- **File**: `/Users/nuzantara/.claude/agents/devils-advocate.md`

### email-template-builder

- **Model**: sonnet
- **Tools**: Read, Write, Edit, Bash, Glob, Grep
- **Description**: Generates Brevo HTML email templates compliant with `bali-zero-brand` surface=email-template. Hardcoded `from=zantara@ba
- **File**: `/Users/nuzantara/.claude/agents/email-template-builder.md`

### nb-curator

- **Model**: sonnet
- **Tools**: Read, Write, Bash, Glob, Grep
- **Description**: NotebookLM inventory steward. Recommends which NB(s) to query for a given question, detects inventory gaps (e.g., "no NB
- **File**: `/Users/nuzantara/.claude/agents/nb-curator.md`

### regulatory-watcher

- **Model**: sonnet
- **Tools**: Read, Write, Bash, WebFetch
- **Description**: Daily watcher over NB-INTEL family + web for new Indonesian regulations (Permenkumham, PMK, PP, Perpres, UU, Peraturan B
- **File**: `/Users/nuzantara/.claude/agents/regulatory-watcher.md`

### wr2-brief-interpreter

- **Model**: sonnet
- **Tools**: Read, Glob, Grep, Bash, WebFetch
- **Description**: MUST BE USED by wr2-design-architect at Step 2 of every carousel run. Use IMMEDIATELY when orchestrator passes a topic +
- **File**: `/Users/nuzantara/.claude/agents/wr2-brief-interpreter.md`

### wr2-critic

- **Model**: opus
- **Tools**: Read, Write, Glob, Grep, Bash
- **Description**: MUST BE USED by wr2-design-architect at Step 5 of every carousel run as the mandatory quality gate. Use IMMEDIATELY afte
- **File**: `/Users/nuzantara/.claude/agents/wr2-critic.md`

### wr2-design-architect

- **Model**: opus
- **Tools**: Read, Write, Edit, Glob, Grep, Bash, Skill, Agent, WebFetch
- **Description**: MUST BE USED for every Bali Zero WR2 editorial carousel. Use IMMEDIATELY when user says "design a carousel for [topic]",
- **File**: `/Users/nuzantara/.claude/agents/wr2-design-architect.md`

### wr2-external-bench

- **Model**: opus
- **Tools**: Read, Write, Bash, WebFetch, WebSearch
- **Description**: Monthly external benchmark for Bali Zero IG carousel design. Researches state-of-the-art editorial IG carouseli from 12
- **File**: `/Users/nuzantara/.claude/agents/wr2-external-bench.md`

### wr2-ig-metrics-analyst

- **Model**: sonnet
- **Tools**: Read, Write, Bash, Glob, Grep
- **Description**: Weekly analyst that reads Instagram engagement metrics (from `_ig-metrics-scraper.py` output) + carousel attributes (dom
- **File**: `/Users/nuzantara/.claude/agents/wr2-ig-metrics-analyst.md`

### wr2-image-prompt-author

- **Model**: opus
- **Tools**: Read, Glob, Grep
- **Description**: Authors original, vivid, editorial image-gen prompts for each hero slide of a WR2 carousel. Reads brief + storyboard + s
- **File**: `/Users/nuzantara/.claude/agents/wr2-image-prompt-author.md`

### wr2-layout-composer

- **Model**: sonnet
- **Tools**: Read, Write, Edit, Glob, Grep, Bash
- **Description**: MUST BE USED by wr2-design-architect at Step 4 of every carousel run. Use IMMEDIATELY after storyboarder returns slides.
- **File**: `/Users/nuzantara/.claude/agents/wr2-layout-composer.md`

### wr2-storyboarder

- **Model**: sonnet
- **Tools**: Read, Glob, Grep, Bash
- **Description**: MUST BE USED by wr2-design-architect at Step 3 of every carousel run. Use IMMEDIATELY when brief-interpreter returns its
- **File**: `/Users/nuzantara/.claude/agents/wr2-storyboarder.md`

### yield-optimizer

- **Model**: sonnet
- **Tools**: Read, Bash
- **Description**: Weekly CRM scanner that connects AI to revenue. Identifies clients with renewal/upgrade potential (KITAS expiring, busin
- **File**: `/Users/nuzantara/.claude/agents/yield-optimizer.md`

## Cross-tool agents

- **Nuzantara project identity, stack, golden rules and owner pr** (cursor-rule) — `.cursor/rules/00-always.mdc`
- **FastAPI backend rules — Python patterns, async, imports, tes** (cursor-rule) — `.cursor/rules/01-backend.mdc`
- **Next.js frontend rules — TypeScript, Tailwind, App Router pa** (cursor-rule) — `.cursor/rules/02-frontend.mdc`
- **Deploy rules — Fly.io backend, Vercel frontend, Dockerfile c** (cursor-rule) — `.cursor/rules/03-deploy.mdc`
- **KBLI 2025 rules — Indonesian business classification codes, ** (cursor-rule) — `.cursor/rules/04-kbli.mdc`
- **backend-deploy** (gemini-skill) — `/Users/nuzantara/.gemini/skills/backend-deploy/SKILL.md`
- **batch-processor** (gemini-skill) — `/Users/nuzantara/.gemini/skills/batch-processor/SKILL.md`
- **crm-data-extraction** (gemini-skill) — `/Users/nuzantara/.gemini/skills/crm-data-extraction/SKILL.md`
- **db-query** (gemini-skill) — `/Users/nuzantara/.gemini/skills/db-query/SKILL.md`
- **frontend-qa** (gemini-skill) — `/Users/nuzantara/.gemini/skills/frontend-qa/SKILL.md`
- **git-commit-helper** (gemini-skill) — `/Users/nuzantara/.gemini/skills/git-commit-helper/SKILL.md`
- **nuzantara-domain-knowledge** (gemini-skill) — `/Users/nuzantara/.gemini/skills/nuzantara-domain-knowledge/SKILL.md`
- **ocr-document-reader** (gemini-skill) — `/Users/nuzantara/.gemini/skills/ocr-document-reader/SKILL.md`
- **prompt-enhancer** (gemini-skill) — `/Users/nuzantara/.gemini/skills/prompt-enhancer/SKILL.md`

## Cron-agents

_Prefix breakdown: com.balizero=73 · com.nuzantara=51 · com.cell=1 · com.matagaruda=16_

### Agentic crons (35) _(call an LLM)_

| Label | Schedule | Script | Catalog note |
|---|---|---|---|
| com.balizero.bz-daily-visual-pipeline | daily@05:30 | `bz-daily-visual-pipeline.sh` | — |
| com.balizero.codex-spalla-calibrate | weekly[d0]@06:00 | `spalla-calibrate.sh` | — |
| com.balizero.competitor-monitor.monthly | daily@09:00 | `competitor-monitor-run.sh` | — |
| com.balizero.intel-lake-nb-pusher.15min | every 15min | `intel-lake-nb-pusher-cron.sh` | — |
| com.balizero.nlm-bridge | run-at-load | `uvicorn` | NLM HTTP Bridge: FastAPI server (port 18790) wrapping NotebookLM. Allows Fly.io |
| com.balizero.post-publish-poller | run-at-load | `post_publish_poller.py` | Post-publish poller: checks for newly published articles, triggers translation a |
| com.balizero.regulatory-watcher.daily | daily@07:00 | `regulatory-watcher-run.sh` | — |
| com.balizero.translate.hourly | daily@*:30 | `translate-articles.py` | Hourly article translation: translate new MDX articles to Indonesian, Italian, R |
| com.balizero.wr2.canva-oauth-watchdog | every 6h | `wr2-canva-oauth-watchdog.sh` | — |
| com.balizero.wr2.canva-renderer | every 5min | `wr2_canva_apply.py` | — |
| com.balizero.wr2.external-bench.monthly | weekly[d1]@07:00 | `wr2-external-bench-run.sh` | — |
| com.balizero.wr2.ig-metrics-analyst.weekly | weekly[d1]@06:07 | `wr2-ig-metrics-analyst-run.sh` | — |
| com.balizero.wr2.ig-scraper.daily | daily@03:00 | `_ig-metrics-scraper.py` | — |
| com.balizero.wr2.reflexion.weekly | weekly[d0]@02:30 | `_reflexion-synthesis.py` | — |
| com.balizero.wr2.voyager.weekly | weekly[d0]@02:00 | `_voyager-curriculum.py` | — |
| com.balizero.yield-optimizer.weekly | weekly[d0]@04:00 | `yield-optimizer-run.sh` | — |
| com.matagaruda.daily-briefing | daily@07:00 | `run_daily_briefing.py` | — |
| com.matagaruda.nlm-expander.weekly | weekly[d0]@09:00 | `run_nlm_expander.py` | — |
| com.matagaruda.weekly-digest | weekly[d0]@08:00 | `run_weekly_digest.py` | — |
| com.nuzantara.claude-config-sync | every 1h | `claude-config-sync.sh` | — |
| com.nuzantara.codex-autofix-ci | daily@*:15 | `nightly-autofix-ci.sh` | — |
| com.nuzantara.codex-coverage-improver | daily@03:00 | `nightly-coverage-improver.sh` | — |
| com.nuzantara.codex-openclaw-analysis | daily@07:15 | `openclaw-analysis.sh` | — |
| com.nuzantara.codex-overnight-feeder | daily@21:30 | `overnight-queue-feeder.sh` | — |
| com.nuzantara.codex-overnight-runner | daily@22:00 | `overnight-runner.sh` | — |
| com.nuzantara.codex-research-actor | daily@06:00 | `daily-research-actor.sh` | — |
| com.nuzantara.codex-spark-alarm | every 2min | `spark-alarm.sh` | — |
| com.nuzantara.codex-spark-harvester | every 3min | `spark-completion-harvester.sh` | — |
| com.nuzantara.codex-spark-loop | run-at-load | `spark-loop.sh` | — |
| com.nuzantara.memory-sync-bidirectional | every 5min | `memory-sync-bidirectional.sh` | — |
| com.nuzantara.nb-intel-delta-watcher.hourly | every 1h | `nb-intel-delta-watcher.sh` | — |
| com.nuzantara.prime-tunnel | run-at-load | `config-prime.yml` | Cloudflared tunnel: persistent tunnel to prime.balizero.com for 3D map service. |
| com.nuzantara.sentinel | run-at-load | `nuzantara-sentinel.py` | Nuzantara Sentinel: 4-tier self-healing automation monitor. Classifies failures |
| com.nuzantara.sentinel-meta-watchdog | every 10min | `sentinel_meta_watchdog.sh` | — |
| com.nuzantara.zombie-hunter | every 60s | `zombie-hunter.sh` | Zombie process hunter: kills orphaned Python/Node processes that consume resourc |

### Infrastructure crons (106) _(no LLM)_

| Label | Schedule | Script | Catalog note |
|---|---|---|---|
| com.balizero.client-value-predictor | daily@09:00 | `client-value-predictor.sh` | Client value predictor: ML scoring of client lifetime value based on practice hi |
| com.balizero.competitor-signal-router.weekly | weekly[d1]@06:30 | `competitor_signal_router.py` | — |
| com.balizero.cron-log-sentinel | run-at-load | `cron_log_sentinel.py` | — |
| com.balizero.domain-mesh.foundations.daily | daily@04:00 | `domain-mesh-foundations-cron.sh` | — |
| com.balizero.indexing-sweep.daily | daily@00:30 | `daily_indexing_cron_wrapper.sh` | — |
| com.balizero.intel-dedup-gateway | run-at-load | `intel_dedup_gateway.py` | — |
| com.balizero.intel-lake-router.5min | every 5min | `intel-lake-router-cron.sh` | — |
| com.balizero.intel-lake.outbox-drain.minute | every 60s | `intel-lake-outbox-drain.py` | — |
| com.balizero.intel-lake.shadow-validate.6h | every 6h | `intel-lake-shadow-validate.sh` | — |
| com.balizero.intel-radar-daily-digest | daily@18:00 | `intel_radar_daily_digest.py` | — |
| com.balizero.intel.nightly | daily@01:00 | `zsh` | Intel nightly scraper: orchestrates bali-intel-scraper for overnight news/regula |
| com.balizero.meta-dispatcher | run-at-load | `meta_dispatcher.py` | — |
| com.balizero.nb-curator.mode-c.weekly | weekly[d1]@05:00 | `run-nb-curator-mode-c.sh` | — |
| com.balizero.nuzantara-drive-sync | daily@06:00;daily@18:00 | `nuzantara-drive-sync.sh` | — |
| com.balizero.observatory | run-at-load | `observatory.py` | — |
| com.balizero.observatory-export | every 60s | `observatory_export.py` | — |
| com.balizero.observatory-server | run-at-load | `serve.py` | — |
| com.balizero.post-publish-webhook | run-at-load | `post_publish_webhook.py` | Post-publish webhook server (port 7788): receives Vercel deploy notifications, t |
| com.balizero.regulatory-watcher.fix-b-verify | daily@07:15 | `regulatory-watcher-fix-b-verify.sh` | — |
| com.balizero.renewal-alerts | daily@08:00 | `renewal-alerts.sh` | Renewal alerts: check all client visa/permit expiry dates, send alerts for upcom |
| com.balizero.research-sentinel | run-at-load | `research_sentinel.py` | — |
| com.balizero.seo-cell.28d-check | daily@04:00 | `seo-cell-28d-check.sh` | — |
| com.balizero.seo-cell.daily | daily@19:30 | `seo-cell-daily.sh` | — |
| com.balizero.setup-team.daily | daily@06:00 | `setup-team-cron.sh` | — |
| com.balizero.sota.m13-checkpoint | daily@09:00 | `wr2-cron-wrapper.sh` | — |
| com.balizero.sota.m13-collect | on-demand | `wr2-cron-wrapper.sh` | — |
| com.balizero.sota.m13-monthly | daily@04:30 | `wr2-cron-wrapper.sh` | — |
| com.balizero.sota.m13-weekly | weekly[d0]@06:00 | `wr2-cron-wrapper.sh` | — |
| com.balizero.wa-audit-bot | run-at-load | `bot.py` | — |
| com.balizero.wa-mirror | run-at-load | `index.js` | — |
| com.balizero.wr2.canva-apply | on-demand | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.canva-gc.weekly | weekly[d1]@04:30 | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.canva-lease-watchdog | every 10min | `wr2_canva_lease_watchdog.py` | — |
| com.balizero.wr2.canva-token-watchdog | daily@09:00 | `wr2_canva_token_watchdog.py` | — |
| com.balizero.wr2.connector | daily@04:00 | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr2.daily-metrics | daily@06:00 | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.deploy-puller | every 1h | `wr2-deploy-pull.sh` | — |
| com.balizero.wr2.dossier-compiler | daily@04:30 | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr2.draft-generator | on-demand | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.fact-checker | on-demand | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.fact-extractor | on-demand | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.hardening | on-demand | `wr2-hardening-chain.sh` | — |
| com.balizero.wr2.image-generator | on-demand | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.learner-nightly | daily@03:00 | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr2.measurer | on-demand | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr2.newsletter | weekly[d1]@09:00 | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr2.oracle | weekly[d0]@22:30 | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr2.pg-proxy | run-at-load | `fly-pg-proxy-wrapper.sh` | — |
| com.balizero.wr2.pg-queue-sync | every 10min | `wr2-pg-queue-sync.sh` | — |
| com.balizero.wr2.plist-watchdog | every 15min | `wr2_plist_watchdog.sh` | — |
| com.balizero.wr2.queue-server | run-at-load | `_damar-queue-server.py` | — |
| com.balizero.wr2.sla-worker | on-demand | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr2.strategos | weekly[d0]@22:00 | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr2.supervisor | run-at-load | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.supervisor-watchdog | run-at-load | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.topic-selector | daily@05:10 | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.trend-hunter | on-demand | `wr2-cron-wrapper.sh` | — |
| com.cell.metabolic-rollup | daily@23:45 | `metabolic_rollup_pro.sh` | — |
| com.matagaruda.bridge.adaptive | every 60s | `matagaruda-bridge.sh` | Mata Garuda bridge — bidirectional Pro<->Fly nerve. Pulls bridge_outbox events f |
| com.matagaruda.gap.consumer | every 10min | `matagaruda-gap-consumer.sh` | Mata Garuda gap consumer — reads nexus:gaps stream (currently 552 entries), disp |
| com.matagaruda.invalidation-sweep | daily@04:13 | `mata_garuda_invalidation_sweep_wrapper.sh` | — |
| com.matagaruda.kg-linker | every 1h | `bash` | — |
| com.matagaruda.kita-feed | daily@05:00 | `bash` | — |
| com.matagaruda.nlm-feeder-stream.hourly | every 1h | `zsh` | — |
| com.matagaruda.public-channel | daily@02:15;daily@06:15;daily@10:15;daily@14:15…+2 | `bash` | — |
| com.matagaruda.reg-alert.30min | every 30min | `run_regulation_alert.py` | — |
| com.matagaruda.sentinel.hourly | every 1h | `run_sentinel_cell.py` | — |
| com.matagaruda.unmapped-audit.daily | daily@09:00 | `mata_garuda_unmapped_audit_wrapper.sh` | — |
| com.matagaruda.watcher.daily | daily@06:00 | `mata-garuda-watcher.sh` | Mata Garuda watcher: monitors KG data freshness and alerts if entities become st |
| com.matagaruda.wr-topic | weekly[d3]@08:00;weekly[d6]@08:00 | `bash` | — |
| com.matagaruda.wr2-bridge | every 1h | `bash` | — |
| com.nuzantara.automap-server | run-at-load | `automap_server.py` | Automap server: automation mapping service that tracks all running automations a |
| com.nuzantara.automap-telegram | run-at-load | `automap_telegram.py` | Automap Telegram bot: sends automation status updates and alerts to Telegram. |
| com.nuzantara.automap-watchdog | run-at-load | `automap_watchdog.py` | Automap watchdog: monitors automap-server and automap-telegram health, restarts |
| com.nuzantara.automations-reference | daily@23:15 | `generate-automations-all.sh` | Nightly doc generator: scans live system state (crontab, launchctl, registry, se |
| com.nuzantara.cell-observatory | run-at-load | `bash` | — |
| com.nuzantara.cell-observatory-prune | daily@04:00 | `bash` | — |
| com.nuzantara.cell-observatory-selfcheck | every 5min | `bash` | — |
| com.nuzantara.cleanup-2026-05-16-ttl-sentinel | daily@08:35 | `restore-federation-alert-mode.sh` | — |
| com.nuzantara.cost-advisor-daily-cap | daily@08:00 | `bash` | — |
| com.nuzantara.cost-advisor-weekly | weekly[d1]@07:00 | `bash` | — |
| com.nuzantara.cpu-monitor | every 10min | `cpu-monitor.sh` | — |
| com.nuzantara.disk-monitor | every 10min | `disk-monitor.sh` | Disk usage monitor: check root disk >85%, log dir >500MB, single log >50MB. Aler |
| com.nuzantara.dlq-autopilot | every 30min | `launch_dlq_autopilot.sh` | DLQ Autopilot: processes dead-letter-queue entries autonomously. Pipeline: prefl |
| com.nuzantara.federation-alert-dispatcher | run-at-load | `bash` | — |
| com.nuzantara.fly-restart-loop-detector | every 15min | `fly-restart-loop-detector.sh` | — |
| com.nuzantara.heartbeat-bridge | run-at-load | `launch_heartbeat_bridge.sh` | — |
| com.nuzantara.launchagent-state-bridge | run-at-load | `launchagent-state-bridge.py` | LaunchAgent state bridge: reads launchctl list output and writes state files for |
| com.nuzantara.launchd-env-loader | every 12h | `launchd_env_loader.sh` | — |
| com.nuzantara.login-healthcheck | every 5min | `login-healthcheck.sh` | — |
| com.nuzantara.nb-mitochondrial-monitor.daily | daily@02:30 | `python` | — |
| com.nuzantara.openclaw-children-watchdog | every 5min | `openclaw-children-watchdog.sh` | — |
| com.nuzantara.openclaw-logrotate | daily@03:00 | `openclaw-logrotate.sh` | — |
| com.nuzantara.organism.control-panel | run-at-load | `python3` | — |
| com.nuzantara.organism.scheduled-tick | daily@*:00 | `python3` | — |
| com.nuzantara.organism.supervisor | run-at-load | `python3` | — |
| com.nuzantara.outbox-prune.daily | daily@03:15 | `outbox-prune.sh` | — |
| com.nuzantara.outbox-prune.weekly | weekly[d0]@04:30 | `outbox_prune.py` | — |
| com.nuzantara.pg-organism-bridge | run-at-load | `pg-to-organism-bridge.py` | — |
| com.nuzantara.pg-organism-bridge-watchdog | every 5min | `pg-organism-bridge-watchdog.sh` | — |
| com.nuzantara.pg-proxy-cluster-recheck-oneshot | daily@08:10 | `bash` | — |
| com.nuzantara.secrets-sync-mini | daily@04:30 | `secrets-sync-cron.sh` | — |
| com.nuzantara.sentinel-aggregate | every 5min | `sentinel-aggregate.py` | — |
| com.nuzantara.skills-bridge-consumer | daily@06:00;daily@06:05;daily@06:10;daily@06:15…+188 | `skills_bridge_consumer.py` | — |
| com.nuzantara.supervisor-liveness-watchdog | every 10min | `supervisor_liveness_watchdog.sh` | — |
| com.nuzantara.vector-reindex-check | weekly[d1]@09:00 | `vector-reindex-check.py` | Vector reindex checker: detects if Qdrant collections have drifted from source d |

## Skills

- **browser** — Use for ANY browser interaction: reading pages, clicking, filling forms, navigating, verifying deplo (`browser.md`)
- **canva-apply** — Apply pending Canva operations from the War Room. Reads canva_pending.json; if status is "pending", (`canva-apply.md`)
- **canva-reset-template** — Reset the Bali Zero carousel master template DAHE6lx1lf8 to a clean state. Replaces all text element (`canva-reset-template.md`)
- **drive-upload** — Upload files or streams to Google Drive via rclone. Use when saving archives, backups, exfiltrated d (`drive-upload.md`)
- **federation-dispatch** — Use when the user explicitly orders dispatch via ai-dispatch.sh (gemini, codex, deepseek, claude-cli (`federation-dispatch.md`)
- **fly-cost-calculator** — Use when calculating Fly.io costs, comparing machine configurations, or evaluating the cost impact o (`fly-cost-calculator.md`)
- **AVTF Loop** — Autonomous UX/A11y/Quality loop — scans, fixes, commits (`nuzantara-avtf.md`)
- **nuzantara-code-quality** — Use when running automated code quality, static analysis, security scanning, lint/ruff, SonarQube in (`nuzantara-code-quality.md`)
- **nuzantara-crm-operations** — Use when the user asks about Nuzantara CRM — managing clients, tracking interactions, analyzing cust (`nuzantara-crm-operations.md`)
- **nuzantara-db-migration** — Use when creating, running, or debugging Alembic migrations for the Nuzantara RAG system (PostgreSQL (`nuzantara-db-migration.md`)
- **nuzantara-debug-production** — Use when debugging a live Nuzantara production issue — Sentry error drill-down, Fly.io logs (`fly lo (`nuzantara-debug-production.md`)
- **Nuzantara Debug Assistant** — Debug production issues on Fly.io with evidence scoring and RAG (`nuzantara-debug.md`)
- **nuzantara-deploy-full** — Use for a full Nuzantara production deploy — backend (Fly.io nuzantara-rag), frontend (Vercel mouth/ (`nuzantara-deploy-full.md`)
- **Nuzantara Deployment** — Deploy Nuzantara backend to Fly.io with full checks (`nuzantara-deploy.md`)
- **nuzantara-flowkit-flow-generation** — Use when generating Imagen 4 / Veo 3 images and videos for Bali Zero (WR2 carousel hero, IG reel, di (`nuzantara-flowkit-flow-generation.md`)
- **nuzantara-kg-operations** — Use for Nuzantara Knowledge Graph work — GraphRAG 2.0/6.0, 108K nodes / 243K edges, Louvain clusteri (`nuzantara-kg-operations.md`)
- **nuzantara-llm-test** — Use when testing the Nuzantara multi-LLM gateway — comparing Claude OAuth, Gemini, Codex, DeepSeek, (`nuzantara-llm-test.md`)
- **nuzantara-monitoring** — Use when checking Nuzantara observability stack — Prometheus metrics, Sentry error tracking, Langfus (`nuzantara-monitoring.md`)
- **nuzantara-parallel-dev** — Use when launching 2+ Claude Code sessions in parallel on Nuzantara (Pro or Air) with tmux + git wor (`nuzantara-parallel-dev.md`)
- **nuzantara-send-email** — Use when sending any email from the Nuzantara/Zantara system — reports, invoices, notifications, CRM (`nuzantara-send-email.md`)
- **nuzantara-spec-driven-dev** — Use when implementing a Nuzantara feature with spec-driven methodology — write spec first, validate (`nuzantara-spec-driven-dev.md`)
- **nuzantara-tdd** — Apply Test-Driven Development (TDD) methodology with Red-Green-Refactor cycle for all code implement (`nuzantara-tdd.md`)
- **nuzantara-vector-search** — Use for Nuzantara Qdrant operations — semantic search, embedding generation (bge-m3, nomic-embed-tex (`nuzantara-vector-search.md`)
- **software-architecture** — Apply Clean Architecture, SOLID principles, and Domain-Driven Design patterns when designing or refa (`software-architecture.md`)
- **wr2-carousel-pipeline** — Use the existing WR2 (War Room 2.0) Bali Zero pipeline to produce a carousel — drafter (Opus 4.7 OAu (`wr2-carousel-pipeline.md`)

## Drift warnings

**Orphaned plists (script not on disk):**
- `com.balizero.wr2.plist-watchdog`

