# Agent Library — Inventory (auto-generated 2026-06-02 20:51 WITA)

<!-- regenerate: python3 agent-library/_generate-inventory.py -->
<!-- DO NOT hand-edit — changes will be overwritten -->

**Snapshot**: 35 Claude subagents · 52 agentic crons / 138 infra crons (190 total launchd) · 60 skills · 0 cross-tool entries

## Quick index

| Name | Type | Model | Tools |
|---|---|---|---|
| backend-verifier | subagent | — | Bash, Read, Grep, Glob… |
| client-case-quote-generator | subagent | opus | Read, Write, Edit, Bash, WebFetch |
| competitor-monitor | subagent | sonnet | Read, Write, Bash, WebFetch |
| deep-researcher | subagent | opus | Read, Write, Bash, WebFetch, WebSearch |
| devils-advocate | subagent | sonnet | Read, Bash, WebFetch |
| email-template-builder | subagent | sonnet | Read, Write, Edit, Bash, Glob, Grep |
| flow-flowkit-operator | subagent | sonnet | Read, Write, Edit, Bash, Glob, Grep, WebFetch |
| frontend-browser | subagent | — | Read, Bash, WebFetch |
| hr-companion | subagent | — | — |
| mcp-health | subagent | — | Bash, Read, Grep, Glob |
| nb-curator | subagent | sonnet | Read, Write, Bash, Glob, Grep |
| regulatory-watcher | subagent | sonnet | Read, Write, Bash, WebFetch |
| spalla-review | subagent | — | Read, Grep, Glob, Bash… |
| wr2-brief-interpreter | subagent | sonnet | Read, Glob, Grep, Bash, WebFetch |
| wr2-critic | subagent | opus | Read, Write, Glob, Grep, Bash |
| wr2-design-architect | subagent | opus | Read, Write, Edit, Glob, Grep, Bash, Skill, Agent, WebFetch |
| wr2-external-bench | subagent | opus | Read, Write, Bash, WebFetch, WebSearch |
| wr2-ig-metrics-analyst | subagent | sonnet | Read, Write, Bash, Glob, Grep |
| wr2-image-prompt-author | subagent | opus | Read, Glob, Grep |
| wr2-layout-composer | subagent | sonnet | Read, Write, Edit, Glob, Grep, Bash |
| wr2-storyboarder | subagent | sonnet | Read, Glob, Grep, Bash |
| wr3-audio-asset-producer | subagent | sonnet | Read, Write, Bash, Glob |
| wr3-b-roll-curator | subagent | sonnet | Read, Bash, WebFetch |
| wr3-brief-interpreter | subagent | sonnet | Read, Glob, Grep, Bash, WebFetch |
| wr3-clip-renderer | subagent | sonnet | Read, Write, Bash, Glob |
| wr3-critic | subagent | opus | Read, Write, Bash, Glob, Grep |
| wr3-design-architect | subagent | opus | Read, Write, Bash, Glob, Grep, Agent, Skill |
| wr3-editorial-bench | subagent | opus | Read, Write, Bash, WebFetch, WebSearch |
| wr3-post-assembler | subagent | sonnet | Read, Write, Bash, Glob |
| wr3-pre-render-gatekeeper | subagent | sonnet | Read, Write, Bash, Glob, Grep |
| wr3-reflexion-synth | subagent | sonnet | Read, Write, Bash, Glob |
| wr3-script-editor | subagent | sonnet | Read, Write, Bash, Glob, Grep |
| wr3-shot-director | subagent | opus | Read, Write, Bash, Glob, Grep, Skill |
| wr3-yt-metrics-analyst | subagent | sonnet | Read, Write, Bash, Glob, Grep |
| yield-optimizer | subagent | sonnet | Read, Bash |
| browser | skill | — | — |
| canva-apply | skill | — | — |
| canva-reset-template | skill | — | — |
| drive-upload | skill | — | — |
| federation-dispatch | skill | — | — |
| fly-cost-calculator | skill | — | — |
| nuzantara-code-quality | skill | — | — |
| nuzantara-debug-production | skill | — | — |
| Nuzantara Debug Assistant | skill | — | — |
| nuzantara-parallel-dev | skill | — | — |
| nuzantara-spec-driven-dev | skill | — | — |
| nuzantara-tdd | skill | — | — |
| software-architecture | skill | — | — |
| wr2-carousel-pipeline | skill | — | — |
| canva-reset-template | skill | — | — |
| federation-dispatch | skill | — | — |
| fly-cost-calculator | skill | — | — |
| AVTF Loop | skill | — | — |
| nuzantara-code-quality | skill | — | — |
| nuzantara-crm-operations | skill | — | — |
| nuzantara-db-migration | skill | — | — |
| nuzantara-debug-production | skill | — | — |
| Nuzantara Debug Assistant | skill | — | — |
| Nuzantara Deployment | skill | — | — |
| nuzantara-kg-operations | skill | — | — |
| nuzantara-llm-test | skill | — | — |
| nuzantara-monitoring | skill | — | — |
| nuzantara-parallel-dev | skill | — | — |
| nuzantara-vector-search | skill | — | — |
| agent-session-discipline | skill | — | — |
| _external-bench-video-2026-05 | skill | — | — |
| wr3-cortex-readme | skill | — | — |
| wr3-voyager-curriculum | skill | — | — |
| wr3-audio-asset-producer | skill | — | — |
| wr3-b-roll-curator | skill | — | — |
| wr3-brief-interpreter | skill | — | — |
| wr3-brief-interpreter-legal-claim-extraction-templates | skill | — | — |
| wr3-brief-interpreter-nb-routing-domain-map | skill | — | — |
| wr3-clip-renderer | skill | — | — |
| companion-mode-spec | skill | — | — |
| wr3-critic | skill | — | — |
| wr3-design-architect | skill | — | — |
| wr3-editorial-bench | skill | — | — |
| wr3-post-assembler | skill | — | — |
| wr3-pre-render-gatekeeper | skill | — | — |
| wr3-reflexion-synth | skill | — | — |
| wr3-script-editor | skill | — | — |
| wr3-shot-director | skill | — | — |
| wr3-yt-metrics-analyst | skill | — | — |
| 2026-05-22-yt-insights-insufficient-data | skill | — | — |
| browser | skill | — | — |
| canva-apply | skill | — | — |
| drive-upload | skill | — | — |
| karpathy-discipline | skill | — | — |
| nuzantara-deploy | skill | — | — |
| nuzantara-flowkit-flow-generation | skill | — | — |
| nuzantara-send-email | skill | — | — |
| regulatory-ingest | skill | — | — |
| skill-catalog | skill | — | — |
| wr2-carousel-pipeline | skill | — | — |

## Claude Code subagents

### backend-verifier

- **Model**: (not set)
- **Tools**: Bash, Read, Grep, Glob…
- **Description**: Use when need to verify Nuzantara backend health, run pytest, check Fly deploy status, audit router/service registration
- **File**: `/Users/nuzantara/.claude/agents/backend-verifier.md`

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

### flow-flowkit-operator

- **Model**: sonnet
- **Tools**: Read, Write, Edit, Bash, Glob, Grep, WebFetch
- **Description**: Use for ad-hoc Google Flow / Veo 3.1 video production via FlowKit (NOT the autonomous WR3 cron pipeline — that's wr3-des
- **File**: `/Users/nuzantara/.claude/agents/flow-flowkit-operator.md`

### frontend-browser

- **Model**: (not set)
- **Tools**: Read, Bash, WebFetch
- **Description**: Use when need to QA frontend after deploy — visit kita.balizero.com / my / prime / mouth / web subdomains, verify HTTP s
- **File**: `/Users/nuzantara/.claude/agents/frontend-browser.md`

### hr-companion

- **Model**: (not set)
- **Tools**: (not set)
- **Description**: (missing)
- **File**: `/Users/nuzantara/.claude/agents/hr-companion.md`

### mcp-health

- **Model**: (not set)
- **Tools**: Bash, Read, Grep, Glob
- **Description**: Use when need to verify 8+ MCP servers reachable, audit MCP integrity hash baseline, diagnose failed-connection reports.
- **File**: `/Users/nuzantara/.claude/agents/mcp-health.md`

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

### spalla-review

- **Model**: (not set)
- **Tools**: Read, Grep, Glob, Bash…
- **Description**: Use for code review co-pilot (alternative to devils-advocate). Read PR diff, comment constructively on architecture, nam
- **File**: `/Users/nuzantara/.claude/agents/spalla-review.md`

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

### wr3-audio-asset-producer

- **Model**: sonnet
- **Tools**: Read, Write, Bash, Glob
- **Description**: MUST BE USED by wr3-design-architect at Step 7+8 AFTER wr3-clip-renderer completes (Veo audio nativo primary path) OR IN
- **File**: `/Users/nuzantara/.claude/agents/wr3-audio-asset-producer.md`

### wr3-b-roll-curator

- **Model**: sonnet
- **Tools**: Read, Bash, WebFetch
- **Description**: Use when wr3-clip-renderer 5.7 execute_fallback or 8.5 b_roll_curator_search triggers. On-demand fallback agent — invoke
- **File**: `/Users/nuzantara/.claude/agents/wr3-b-roll-curator.md`

### wr3-brief-interpreter

- **Model**: sonnet
- **Tools**: Read, Glob, Grep, Bash, WebFetch
- **Description**: MUST BE USED by wr3-design-architect at Step 1 of every WR3 episode run. Use IMMEDIATELY when orchestrator dispatches wi
- **File**: `/Users/nuzantara/.claude/agents/wr3-brief-interpreter.md`

### wr3-clip-renderer

- **Model**: sonnet
- **Tools**: Read, Write, Bash, Glob
- **Description**: MUST BE USED by wr3-design-architect at Step 5 ONLY after wr3-pre-render-gatekeeper returns PASS. Use IMMEDIATELY after
- **File**: `/Users/nuzantara/.claude/agents/wr3-clip-renderer.md`

### wr3-critic

- **Model**: opus
- **Tools**: Read, Write, Bash, Glob, Grep
- **Description**: MUST BE USED by wr3-design-architect at Step 11 as MANDATORY quality gate. Use IMMEDIATELY after wr3-post-assembler emit
- **File**: `/Users/nuzantara/.claude/agents/wr3-critic.md`

### wr3-design-architect

- **Model**: opus
- **Tools**: Read, Write, Bash, Glob, Grep, Agent, Skill
- **Description**: MUST BE USED for every Bali Zero WR3 video episode. Use IMMEDIATELY when user says "produce WR3 episode for [topic]", "r
- **File**: `/Users/nuzantara/.claude/agents/wr3-design-architect.md`

### wr3-editorial-bench

- **Model**: opus
- **Tools**: Read, Write, Bash, WebFetch, WebSearch
- **Description**: Real deep-research pipeline 2026-05-22, multi-LLM cascade agy+Claude+DeepSeek, monthly cron 1st Monday 07:00 WITA via La
- **File**: `/Users/nuzantara/.claude/agents/wr3-editorial-bench.md`

### wr3-post-assembler

- **Model**: sonnet
- **Tools**: Read, Write, Bash, Glob
- **Description**: MUST BE USED by wr3-design-architect at Step 9-10-12 when ALL assets ready (clips/ + audio/ + license-report.json). Use
- **File**: `/Users/nuzantara/.claude/agents/wr3-post-assembler.md`

### wr3-pre-render-gatekeeper

- **Model**: sonnet
- **Tools**: Read, Write, Bash, Glob, Grep
- **Description**: MUST BE USED by wr3-design-architect at Step 4 BEFORE any Veo credit spend. Use IMMEDIATELY after wr3-shot-director retu
- **File**: `/Users/nuzantara/.claude/agents/wr3-pre-render-gatekeeper.md`

### wr3-reflexion-synth

- **Model**: sonnet
- **Tools**: Read, Write, Bash, Glob
- **Description**: Weekly cron Sunday 02:30 WITA via LaunchAgent com.balizero.wr3.reflexion.weekly.plist. Reads last 7 days episodes from a
- **File**: `/Users/nuzantara/.claude/agents/wr3-reflexion-synth.md`

### wr3-script-editor

- **Model**: sonnet
- **Tools**: Read, Write, Bash, Glob, Grep
- **Description**: MUST BE USED by wr3-design-architect at Step 2 of every WR3 episode run. Use IMMEDIATELY after wr3-brief-interpreter wri
- **File**: `/Users/nuzantara/.claude/agents/wr3-script-editor.md`

### wr3-shot-director

- **Model**: opus
- **Tools**: Read, Write, Bash, Glob, Grep, Skill
- **Description**: MUST BE USED by wr3-design-architect at Step 3 of every WR3 episode run. Use IMMEDIATELY after script_freeze passes (Ste
- **File**: `/Users/nuzantara/.claude/agents/wr3-shot-director.md`

### wr3-yt-metrics-analyst

- **Model**: sonnet
- **Tools**: Read, Write, Bash, Glob, Grep
- **Description**: Weekly cron Monday 06:00 WITA via LaunchAgent com.balizero.wr3.yt-metrics.weekly.plist. Reads YouTube Analytics API + IG
- **File**: `/Users/nuzantara/.claude/agents/wr3-yt-metrics-analyst.md`

### yield-optimizer

- **Model**: sonnet
- **Tools**: Read, Bash
- **Description**: Weekly CRM scanner that connects AI to revenue. Identifies clients with renewal/upgrade potential (KITAS expiring, busin
- **File**: `/Users/nuzantara/.claude/agents/yield-optimizer.md`

## Cross-tool agents

_(none found)_

## Cron-agents

_Prefix breakdown: com.balizero=107 · com.nuzantara=60 · com.cell=2 · com.matagaruda=21_

### Agentic crons (52) _(call an LLM)_

| Label | Schedule | Script | Catalog note |
|---|---|---|---|
| com.balizero.bz-daily-visual-pipeline | daily@05:30 | `bz-daily-visual-pipeline.sh` | — |
| com.balizero.cicatrix-rotation.monthly | daily@04:00 | `cicatrix-rotation.py` | — |
| com.balizero.claude-settings-watcher | on-demand | `claude-settings-change-alert.sh` | — |
| com.balizero.codex-spalla-calibrate | weekly[d0]@06:00 | `spalla-calibrate.sh` | — |
| com.balizero.competitor-monitor.monthly | daily@09:00 | `competitor-monitor-run.sh` | — |
| com.balizero.crm-guardian-cli-worker | every 5min | `crm-guardian-cli-worker.sh` | — |
| com.balizero.guardrails-daemon | run-at-load | `guardrails.py` | — |
| com.balizero.intel-lake-nb-pusher.15min | every 15min | `intel-lake-nb-pusher-cron.sh` | — |
| com.balizero.mos-plus.compression | every 10min | `mos-plus-compression-worker.py` | — |
| com.balizero.mos-plus.qdrant-indexer | every 30min | `mos-plus-qdrant-indexer.py` | — |
| com.balizero.nlm-bridge | run-at-load | `uvicorn` | NLM HTTP Bridge: FastAPI server (port 18790) wrapping NotebookLM. Allows Fly.io |
| com.balizero.nuzantara.log-size-watchdog | every 1h | `log_size_watchdog.sh` | — |
| com.balizero.post-publish-poller | run-at-load | `post_publish_poller.py` | Post-publish poller: checks for newly published articles, triggers translation a |
| com.balizero.regulatory-watcher.daily | daily@07:00 | `regulatory-watcher-run.sh` | — |
| com.balizero.translate.hourly | daily@*:30 | `translate-articles.py` | Hourly article translation: translate new MDX articles to Indonesian, Italian, R |
| com.balizero.wa-mirror-attention-classifier | every 5min | `wa-mirror-enrichment-wrapper.sh` | — |
| com.balizero.wa-mirror-attention-digest | daily@18:00 | `wa-mirror-enrichment-wrapper.sh` | — |
| com.balizero.wa-mirror-attention-realtime | every 10min | `wa-mirror-enrichment-wrapper.sh` | — |
| com.balizero.wa-mirror-strategic-recap | every 3h | `wa-mirror-strategic-recap-updater.py` | — |
| com.balizero.wr2.canva-oauth-watchdog | every 6h | `wr2-canva-oauth-watchdog.sh` | — |
| com.balizero.wr2.external-bench.monthly | weekly[d1]@07:00 | `wr2-external-bench-run.sh` | — |
| com.balizero.wr2.ig-metrics-analyst.weekly | weekly[d1]@06:07 | `wr2-ig-metrics-analyst-run.sh` | — |
| com.balizero.wr2.ig-scraper.daily | daily@03:00 | `_ig-metrics-scraper.py` | — |
| com.balizero.wr2.reflexion.weekly | weekly[d0]@02:30 | `_reflexion-synthesis.py` | — |
| com.balizero.wr2.voyager.weekly | weekly[d0]@02:00 | `_voyager-curriculum.py` | — |
| com.balizero.wr2.worktree-gc.daily | daily@00:00 | `wr2_worktree_gc.py` | — |
| com.balizero.wr3.reflexion.weekly | weekly[d0]@02:30 | `_reflexion-synthesis.py` | — |
| com.balizero.yield-optimizer.weekly | weekly[d0]@04:00 | `yield-optimizer-run.sh` | — |
| com.matagaruda.classifier.adaptive | every 5min | `matagaruda-classifier-worker.sh` | — |
| com.matagaruda.daily-briefing | daily@07:00 | `run_daily_briefing.py` | — |
| com.matagaruda.ner.adaptive | every 5min | `matagaruda-ner-worker.sh` | — |
| com.matagaruda.nlm-expander.weekly | weekly[d0]@09:00 | `run_nlm_expander.py` | — |
| com.matagaruda.nlm-feeder-stream.hourly | every 1h | `matagaruda-nlm-feeder-stream.sh` | — |
| com.matagaruda.weekly-digest | weekly[d0]@08:00 | `run_weekly_digest.py` | — |
| com.nuzantara.archive-empty-sessions.daily | daily@04:00 | `archive-empty-sessions.sh` | — |
| com.nuzantara.branch-cleanup.weekly | weekly[d1]@08:00 | `branch_graveyard_cleanup.sh` | — |
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

### Infrastructure crons (138) _(no LLM)_

| Label | Schedule | Script | Catalog note |
|---|---|---|---|
| com.balizero.agent-library-evolver.weekly | weekly[d0]@03:00 | `agent-library-evolver-run.sh` | — |
| com.balizero.audit-launchd.daily | daily@02:00 | `audit-launchd-daily.sh` | — |
| com.balizero.client-value-predictor | daily@09:00 | `client-value-predictor.sh` | Client value predictor: ML scoring of client lifetime value based on practice hi |
| com.balizero.competitor-signal-router.weekly | weekly[d1]@06:30 | `competitor_signal_router.py` | — |
| com.balizero.cron-log-sentinel | run-at-load | `cron_log_sentinel.py` | — |
| com.balizero.curiosity.weekly | weekly[d0]@20:00 | `curiosity-batch.sh` | — |
| com.balizero.domain-mesh.foundations.daily | daily@04:00 | `domain-mesh-foundations-cron.sh` | — |
| com.balizero.fly-cost-alert.weekly | weekly[d1]@09:00 | `fly-cost-alert.sh` | — |
| com.balizero.indexing-sweep.daily | daily@00:30 | `daily_indexing_cron_wrapper.sh` | — |
| com.balizero.intel-dedup-gateway | run-at-load | `intel_dedup_gateway.py` | — |
| com.balizero.intel-lake-router.5min | every 5min | `intel-lake-router-cron.sh` | — |
| com.balizero.intel-lake.e2e-probe.6h | daily@00:30;daily@06:30;daily@12:30;daily@18:30 | `intel-lake-probe-cron.sh` | — |
| com.balizero.intel-lake.outbox-drain.minute | every 60s | `intel-lake-outbox-drain.py` | — |
| com.balizero.intel-lake.shadow-validate.6h | every 6h | `intel-lake-shadow-validate.sh` | — |
| com.balizero.intel-radar-daily-digest | daily@18:00 | `intel_radar_daily_digest.py` | — |
| com.balizero.intel.nightly | daily@01:00 | `zsh` | Intel nightly scraper: orchestrates bali-intel-scraper for overnight news/regula |
| com.balizero.l5-2-phase2b-trigger | daily@09:00 | `l5_2_phase2b_trigger_wrapper.sh` | — |
| com.balizero.meta-dispatcher | run-at-load | `meta_dispatcher.py` | — |
| com.balizero.nb-curator.daily | daily@04:00 | `nb-curator-daily.sh` | — |
| com.balizero.nextdns-tamper-detect.weekly | weekly[d1]@01:00 | `bash` | — |
| com.balizero.nuzantara-drive-sync | daily@06:00;daily@18:00 | `nuzantara-drive-sync.sh` | — |
| com.balizero.nuzantara.disk-watchdog | daily@09:00 | `disk_watchdog.sh` | — |
| com.balizero.observatory | run-at-load | `observatory.py` | — |
| com.balizero.observatory-export | every 60s | `observatory_export.py` | — |
| com.balizero.observatory-server | run-at-load | `serve.py` | — |
| com.balizero.post-publish-webhook | run-at-load | `post_publish_webhook.py` | Post-publish webhook server (port 7788): receives Vercel deploy notifications, t |
| com.balizero.profile-monitor-wrapper | run-at-load | `wrapper.py` | — |
| com.balizero.qdrant.daemon | run-at-load | `qdrant-daemon-wrapper.sh` | — |
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
| com.balizero.wa-dashboard-m1 | run-at-load | `server.cjs` | — |
| com.balizero.wa-intelligence-incremental | every 5min | `zsh` | — |
| com.balizero.wa-lid-refresh | daily@03:15 | `curl` | — |
| com.balizero.wa-mirror | run-at-load | `index.js` | — |
| com.balizero.wa-mirror-auto-promote | every 5min | `wa-mirror-auto-promote-leads.py` | — |
| com.balizero.wa-mirror-launcher | run-at-load | `supervise-launcher.sh` | — |
| com.balizero.wa-viewer | run-at-load | `run.sh` | — |
| com.balizero.wr2.canva-apply | on-demand | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.canva-gc.weekly | weekly[d1]@04:30 | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.canva-lease-watchdog | every 10min | `wr2_canva_lease_watchdog.py` | — |
| com.balizero.wr2.canva-renderer | every 5min | `wr2-canva-renderer-wrapper.sh` | — |
| com.balizero.wr2.canva-token-watchdog | daily@09:00 | `wr2_canva_token_watchdog.py` | — |
| com.balizero.wr2.carousel-dispatcher | run-at-load | `wr2-carousel-dispatcher-wrapper.sh` | — |
| com.balizero.wr2.connector | daily@04:00 | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr2.daily-metrics | daily@06:00 | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.deploy-puller | every 1h | `wr2-deploy-pull.sh` | — |
| com.balizero.wr2.dossier-compiler | daily@04:30 | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr2.draft-generator | on-demand | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.e2e-probe.daily | daily@04:00 | `wr2-probe-cron.sh` | — |
| com.balizero.wr2.fact-checker | on-demand | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.fact-extractor | on-demand | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.hardening | every 6h | `wr2-hardening-chain.sh` | — |
| com.balizero.wr2.image-generator | on-demand | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.learner-nightly | daily@03:00 | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr2.measurer | every 6h | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr2.newsletter | weekly[d1]@09:00 | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr2.oracle | weekly[d0]@22:30 | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr2.pg-proxy | run-at-load | `fly-pg-proxy-wrapper.sh` | — |
| com.balizero.wr2.pg-queue-sync | every 10min | `wr2-pg-queue-sync.sh` | — |
| com.balizero.wr2.plist-watchdog | every 15min | `wr2_plist_watchdog.sh` | — |
| com.balizero.wr2.queue-server | run-at-load | `_damar-queue-server.py` | — |
| com.balizero.wr2.sla-worker | every 30min | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr2.strategos | weekly[d0]@22:00 | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr2.supervisor | run-at-load | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.supervisor-watchdog | run-at-load | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.telegram-gate | run-at-load | `wr2-telegram-gate-wrapper.sh` | — |
| com.balizero.wr2.topic-selector | daily@05:10 | `wr2-script-wrapper.sh` | — |
| com.balizero.wr2.trend-hunter | every 2h | `wr2-cron-wrapper.sh` | — |
| com.balizero.wr3.editorial-bench.monthly | daily@07:00 | `wr3-editorial-bench-run.sh` | — |
| com.balizero.wr3.supervisor | run-at-load | `wr3-supervisor-wrapper.sh` | — |
| com.balizero.wr3.yt-metrics.weekly | weekly[d1]@06:07 | `wr3-yt-metrics-run.sh` | — |
| com.cell.metabolic-rollup | daily@23:45 | `metabolic_rollup_pro.sh` | — |
| com.cell.organism | run-at-load | `launch_cell.sh` | Cell organism: autonomous PulseLoop agent. Sense→Think→Act→Reflect→Dream→Mature. |
| com.matagaruda.bridge.adaptive | every 60s | `matagaruda-bridge.sh` | Mata Garuda bridge — bidirectional Pro<->Fly nerve. Pulls bridge_outbox events f |
| com.matagaruda.consumer-lag.check | every 30min | `matagaruda-consumer-lag-check.sh` | — |
| com.matagaruda.gap.consumer | every 10min | `matagaruda-gap-consumer.sh` | Mata Garuda gap consumer — reads nexus:gaps stream (currently 552 entries), disp |
| com.matagaruda.invalidation-sweep | daily@04:13 | `mata_garuda_invalidation_sweep_wrapper.sh` | — |
| com.matagaruda.kg-linker | every 1h | `matagaruda-cron-tcc-safe.sh` | — |
| com.matagaruda.kita-feed | daily@05:00 | `matagaruda-cron-tcc-safe.sh` | — |
| com.matagaruda.pel-cleaner.weekly | weekly[d0]@04:00 | `matagaruda-pel-cleaner.sh` | — |
| com.matagaruda.public-channel | daily@02:15;daily@06:15;daily@10:15;daily@14:15…+2 | `matagaruda-cron-tcc-safe.sh` | — |
| com.matagaruda.redis-split-brain.check | every 30min | `matagaruda-redis-split-brain-check.sh` | — |
| com.matagaruda.reg-alert.30min | every 30min | `matagaruda-cron-tcc-safe.sh` | — |
| com.matagaruda.sentinel.hourly | every 1h | `matagaruda-cron-tcc-safe.sh` | — |
| com.matagaruda.unmapped-audit.daily | daily@09:00 | `mata_garuda_unmapped_audit_wrapper.sh` | — |
| com.matagaruda.watcher.daily | daily@06:00 | `mata-garuda-watcher.sh` | Mata Garuda watcher: monitors KG data freshness and alerts if entities become st |
| com.matagaruda.wr-topic | weekly[d3]@08:00;weekly[d6]@08:00 | `matagaruda-cron-tcc-safe.sh` | — |
| com.matagaruda.wr2-bridge | every 1h | `matagaruda-cron-tcc-safe.sh` | — |
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
| com.nuzantara.gh-auth-healthcheck.weekly | weekly[d1]@07:00 | `gh-auth-healthcheck.sh` | — |
| com.nuzantara.heartbeat-bridge | run-at-load | `launch_heartbeat_bridge.sh` | — |
| com.nuzantara.launchagent-state-bridge | run-at-load | `launchagent-state-bridge.py` | LaunchAgent state bridge: reads launchctl list output and writes state files for |
| com.nuzantara.launchd-env-loader | every 12h | `launchd_env_loader.sh` | — |
| com.nuzantara.login-healthcheck | every 5min | `login-healthcheck.sh` | — |
| com.nuzantara.nb-mitochondrial-monitor.daily | daily@02:30 | `python` | — |
| com.nuzantara.openclaw-children-watchdog | every 5min | `openclaw-children-watchdog.sh` | — |
| com.nuzantara.openclaw-logrotate | daily@03:00 | `openclaw-logrotate.sh` | — |
| com.nuzantara.openclaw-whatsapp-bridge | run-at-load | `run_openclaw_whatsapp_bridge.sh` | — |
| com.nuzantara.openclaw-whatsapp-tunnel | run-at-load | `run_openclaw_whatsapp_tunnel.sh` | — |
| com.nuzantara.openclaw.guardian-board | daily@08:30 | `guardian-board-report` | — |
| com.nuzantara.organism.control-panel | run-at-load | `python3` | — |
| com.nuzantara.organism.scheduled-tick | daily@*:00 | `python3` | — |
| com.nuzantara.organism.supervisor | run-at-load | `organism-supervisor-wrapper.sh` | — |
| com.nuzantara.outbox-prune.daily | daily@03:15 | `outbox-prune.sh` | — |
| com.nuzantara.outbox-prune.weekly | weekly[d0]@04:30 | `outbox_prune.py` | — |
| com.nuzantara.pg-organism-bridge | run-at-load | `pg-to-organism-bridge.py` | — |
| com.nuzantara.pg-organism-bridge-watchdog | every 5min | `pg-organism-bridge-watchdog.sh` | — |
| com.nuzantara.pg-proxy-cluster-recheck-oneshot | daily@08:10 | `bash` | — |
| com.nuzantara.repomap.15min | every 15min | `build_repomap.sh` | — |
| com.nuzantara.secrets-sync-mini | daily@04:30 | `secrets-sync-cron.sh` | — |
| com.nuzantara.sentinel-aggregate | every 5min | `sentinel-aggregate.py` | — |
| com.nuzantara.skills-bridge-consumer | daily@06:00;daily@06:05;daily@06:10;daily@06:15…+188 | `skills_bridge_consumer.py` | — |
| com.nuzantara.supervisor-liveness-watchdog | every 10min | `supervisor_liveness_watchdog.sh` | — |
| com.nuzantara.vector-reindex-check | weekly[d1]@09:00 | `vector-reindex-check.py` | Vector reindex checker: detects if Qdrant collections have drifted from source d |
| com.nuzantara.workspace-event-bridge-sheets-import | every 15min | `workspace-event-bridge-sheets-import.sh` | — |
| com.nuzantara.worktree-gc-universal.daily | daily@00:30 | `worktree_gc_universal.py` | — |

## Skills

- **browser** — Use for ANY browser interaction: reading pages, clicking, filling forms, navigating, verifying deplo (`browser.md`)
- **canva-apply** — Apply pending Canva operations from the War Room. Reads canva_pending.json; if status is "pending", (`canva-apply.md`)
- **canva-reset-template** — Reset the Bali Zero carousel master template DAHE6lx1lf8 to a clean state. Replaces all text element (`canva-reset-template.md`)
- **drive-upload** — Upload files or streams to Google Drive via rclone. Use when saving archives, backups, exfiltrated d (`drive-upload.md`)
- **federation-dispatch** — Use when the user explicitly orders dispatch via ai-dispatch.sh (gemini, codex, deepseek, claude-cli (`federation-dispatch.md`)
- **fly-cost-calculator** — Use when calculating Fly.io costs, comparing machine configurations, or evaluating the cost impact o (`fly-cost-calculator.md`)
- **nuzantara-code-quality** — Use when running automated code quality, static analysis, security scanning, lint/ruff, SonarQube in (`nuzantara-code-quality.md`)
- **nuzantara-debug-production** — Use when debugging a live Nuzantara production issue — Sentry error drill-down, Fly.io logs (`fly lo (`nuzantara-debug-production.md`)
- **Nuzantara Debug Assistant** — Debug production issues on Fly.io with evidence scoring and RAG (`nuzantara-debug.md`)
- **nuzantara-parallel-dev** — Use when launching 2+ Claude Code sessions in parallel on Nuzantara (Pro or Air) with tmux + git wor (`nuzantara-parallel-dev.md`)
- **nuzantara-spec-driven-dev** — Use when implementing a Nuzantara feature with spec-driven methodology — write spec first, validate (`nuzantara-spec-driven-dev.md`)
- **nuzantara-tdd** — Apply Test-Driven Development (TDD) methodology with Red-Green-Refactor cycle for all code implement (`nuzantara-tdd.md`)
- **software-architecture** — Apply Clean Architecture, SOLID principles, and Domain-Driven Design patterns when designing or refa (`software-architecture.md`)
- **wr2-carousel-pipeline** — Use the existing WR2 (War Room 2.0) Bali Zero pipeline to produce a carousel — drafter (Opus 4.7 OAu (`wr2-carousel-pipeline.md`)
- **canva-reset-template** — Reset the Bali Zero carousel master template DAHE6lx1lf8 to a clean state. Replaces all text element (`canva-reset-template.md`)
- **federation-dispatch** — Use when the user explicitly orders dispatch via ai-dispatch.sh (gemini, codex, deepseek, claude-cli (`federation-dispatch.md`)
- **fly-cost-calculator** — Use when calculating Fly.io costs, comparing machine configurations, or evaluating the cost impact o (`fly-cost-calculator.md`)
- **AVTF Loop** — Autonomous UX/A11y/Quality loop — scans, fixes, commits (`nuzantara-avtf.md`)
- **nuzantara-code-quality** — Use when running automated code quality, static analysis, security scanning, lint/ruff, SonarQube in (`nuzantara-code-quality.md`)
- **nuzantara-crm-operations** — CRM operations Bali Zero — clients, practices, drive folders, compliance tracking. Use when user men (`nuzantara-crm-operations.md`)
- **nuzantara-db-migration** — PostgreSQL migration patterns Nuzantara (Fly Postgres + Alembic + migrations_v2 SQL). Use when user (`nuzantara-db-migration.md`)
- **nuzantara-debug-production** — Use when debugging a live Nuzantara production issue — Sentry error drill-down, Fly.io logs (`fly lo (`nuzantara-debug-production.md`)
- **Nuzantara Debug Assistant** — Debug production issues on Fly.io with evidence scoring and RAG (`nuzantara-debug.md`)
- **Nuzantara Deployment** — Deploy Nuzantara backend to Fly.io with full checks (`nuzantara-deploy.md`)
- **nuzantara-kg-operations** — Use for Nuzantara Knowledge Graph work — GraphRAG 2.0/6.0, 108K nodes / 243K edges, Louvain clusteri (`nuzantara-kg-operations.md`)
- **nuzantara-llm-test** — Use when testing the Nuzantara multi-LLM gateway — comparing Claude OAuth, Gemini, Codex, DeepSeek, (`nuzantara-llm-test.md`)
- **nuzantara-monitoring** — Use when checking Nuzantara observability stack — Prometheus metrics, Sentry error tracking, Langfus (`nuzantara-monitoring.md`)
- **nuzantara-parallel-dev** — Use when launching 2+ Claude Code sessions in parallel on Nuzantara (Pro or Air) with tmux + git wor (`nuzantara-parallel-dev.md`)
- **nuzantara-vector-search** — Use for Nuzantara Qdrant operations — semantic search, embedding generation (bge-m3, nomic-embed-tex (`nuzantara-vector-search.md`)
- **agent-session-discipline** — Use at session start when working on a feature/fix that involves code changes. Creates an isolated w (`SKILL.md`)
- **_external-bench-video-2026-05** —  (`_external-bench-video-2026-05.md`)
- **wr3-cortex-readme** — WR3 skill cortex root README — directory map, lifecycle states, entry points. (`README.md`)
- **wr3-voyager-curriculum** — WR3 Voyager skill library curriculum — incremental skill graduation pipeline. Tracks proposed skills (`_voyager-curriculum.md`)
- **wr3-audio-asset-producer** — WR3 audio-asset-producer skill cortex — operational heuristics, on-tone examples, lessons growth sur (`SKILL.md`)
- **wr3-b-roll-curator** — WR3 b-roll-curator skill cortex — operational heuristics, on-tone examples, lessons growth surface. (`SKILL.md`)
- **wr3-brief-interpreter** — WR3 brief-interpreter skill cortex — operational heuristics, on-tone examples, lessons growth surfac (`SKILL.md`)
- **wr3-brief-interpreter-legal-claim-extraction-templates** — WR3 brief-interpreter domain-specific resource — legal-claim-extraction-templates.md (`legal-claim-extraction-templates.md`)
- **wr3-brief-interpreter-nb-routing-domain-map** — WR3 brief-interpreter domain → NotebookLM routing map (authoritative). Domain NBs only (NB-2..NB-7). (`nb-routing-domain-map.md`)
- **wr3-clip-renderer** — WR3 clip-renderer skill cortex — operational heuristics, on-tone examples, lessons growth surface. L (`SKILL.md`)
- **companion-mode-spec** — Voice register, hook patterns, and example translations for the wr3-design-architect `companion_from (`companion-mode-spec.md`)
- **wr3-critic** — WR3 critic skill cortex — operational heuristics, on-tone examples, lessons growth surface. Loaded b (`SKILL.md`)
- **wr3-design-architect** — WR3 design-architect skill cortex — operational heuristics, on-tone examples, lessons growth surface (`SKILL.md`)
- **wr3-editorial-bench** — WR3 editorial-bench skill cortex — operational heuristics, on-tone examples, lessons growth surface. (`SKILL.md`)
- **wr3-post-assembler** — WR3 post-assembler skill cortex — operational heuristics, on-tone examples, lessons growth surface. (`SKILL.md`)
- **wr3-pre-render-gatekeeper** — WR3 pre-render-gatekeeper skill cortex — operational heuristics, on-tone examples, lessons growth su (`SKILL.md`)
- **wr3-reflexion-synth** — WR3 reflexion-synth skill cortex — operational heuristics, on-tone examples, lessons growth surface. (`SKILL.md`)
- **wr3-script-editor** — WR3 script-editor skill cortex — operational heuristics, on-tone examples, lessons growth surface. L (`SKILL.md`)
- **wr3-shot-director** — WR3 shot-director skill cortex — operational heuristics, on-tone examples, lessons growth surface. L (`SKILL.md`)
- **wr3-yt-metrics-analyst** — WR3 yt-metrics-analyst skill cortex — operational heuristics, on-tone examples, lessons growth surfa (`SKILL.md`)
- **2026-05-22-yt-insights-insufficient-data** —  (`2026-05-22-yt-insights-insufficient-data.md`)
- **browser** — Use when you need to drive a real browser — read a page's text/HTML, click, fill a form, navigate, s (`SKILL.md`)
- **canva-apply** — Apply pending Canva operations from the War Room. Reads canva_pending.json (status=pending), validat (`canva-apply.md`)
- **drive-upload** — Upload files or streams to Google Drive via rclone. Use when saving archives, backups, exfiltrated d (`drive-upload.md`)
- **karpathy-discipline** — Use BEFORE any feature implementation, refactor, bug fix, or non-trivial code change. Applies 4 Karp (`SKILL.md`)
- **nuzantara-deploy** — Use when deploying Nuzantara backend to Fly.io (nuzantara-rag) or frontend to Vercel — runs the CLAU (`SKILL.md`)
- **nuzantara-flowkit-flow-generation** — Use when generating images (Nano Banana Pro) or Veo video reels for Bali Zero content (WR2/WR3 carou (`SKILL.md`)
- **nuzantara-send-email** — Use when sending any email from the Nuzantara/Zantara system — reports, invoices, notifications, CRM (`nuzantara-send-email.md`)
- **regulatory-ingest** — Indonesian regulatory ingest pipeline — Permenkumham, PMK, PP, Perpres, UU, Peraturan BKPM, Permenak (`regulatory-ingest.md`)
- **skill-catalog** — Use when a user request does NOT match any currently-loaded skill — BEFORE answering "I don't have a (`SKILL.md`)
- **wr2-carousel-pipeline** — Use when running the WR2 (War Room 2.0) Bali Zero Instagram carousel pipeline — making a "carousel", (`SKILL.md`)

## Drift warnings

**Missing YAML frontmatter:**
- `/Users/nuzantara/.claude/agents/hr-companion.md`

**Orphaned plists (script not on disk):**
- `com.balizero.wr2.canva-renderer`
- `com.balizero.wr3.editorial-bench.monthly`
- `com.balizero.wr3.supervisor`
- `com.balizero.wr3.yt-metrics.weekly`
- `com.nuzantara.cleanup-2026-05-16-ttl-sentinel`
- `com.nuzantara.workspace-event-bridge-sheets-import`

