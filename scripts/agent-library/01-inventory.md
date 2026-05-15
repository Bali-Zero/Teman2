# Agent Library — Inventory (auto-generated 2026-05-15 08:49 WITA)

<!-- regenerate: python3 agent-library/_generate-inventory.py -->
<!-- DO NOT hand-edit — changes will be overwritten -->

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
| KBLI 2025 rules — Indonesian business classification codes,  | cursor-rule | — | — |
| backend-deploy | gemini-skill | — | — |
| batch-processor | gemini-skill | — | — |
| crm-data-extraction | gemini-skill | — | — |
| db-query | gemini-skill | — | — |
| frontend-qa | gemini-skill | — | — |
| git-commit-helper | gemini-skill | — | — |
| nuzantara-domain-knowledge | gemini-skill | — | — |
| bali-zero-business-overview | gemini-skill | — | — |
| company-licensing-kbli | gemini-skill | — | — |
| example_reference | gemini-skill | — | — |
| immigration-and-visas | gemini-skill | — | — |
| kbli-2025-casistica-specialistica | gemini-skill | — | — |
| legal-properties | gemini-skill | — | — |
| nuzantara-user-personas | gemini-skill | — | — |
| tax-reporting | gemini-skill | — | — |
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
- **bali-zero-business-overview** (gemini-skill) — `/Users/nuzantara/.gemini/skills/nuzantara-domain-knowledge/references/bali-zero-business-overview.md`
- **company-licensing-kbli** (gemini-skill) — `/Users/nuzantara/.gemini/skills/nuzantara-domain-knowledge/references/company-licensing-kbli.md`
- **example_reference** (gemini-skill) — `/Users/nuzantara/.gemini/skills/nuzantara-domain-knowledge/references/example_reference.md`
- **immigration-and-visas** (gemini-skill) — `/Users/nuzantara/.gemini/skills/nuzantara-domain-knowledge/references/immigration-and-visas.md`
- **kbli-2025-casistica-specialistica** (gemini-skill) — `/Users/nuzantara/.gemini/skills/nuzantara-domain-knowledge/references/kbli-2025-casistica-specialistica.md`
- **legal-properties** (gemini-skill) — `/Users/nuzantara/.gemini/skills/nuzantara-domain-knowledge/references/legal-properties.md`
- **nuzantara-user-personas** (gemini-skill) — `/Users/nuzantara/.gemini/skills/nuzantara-domain-knowledge/references/nuzantara-user-personas.md`
- **tax-reporting** (gemini-skill) — `/Users/nuzantara/.gemini/skills/nuzantara-domain-knowledge/references/tax-reporting.md`
- **ocr-document-reader** (gemini-skill) — `/Users/nuzantara/.gemini/skills/ocr-document-reader/SKILL.md`
- **prompt-enhancer** (gemini-skill) — `/Users/nuzantara/.gemini/skills/prompt-enhancer/SKILL.md`

## Cron-agents

### Agentic crons _(call an LLM)_

| Label | Schedule | Script |
|---|---|---|
| com.balizero.codex-spalla-calibrate | daily@06:00 | `spalla-calibrate.sh` |
| com.balizero.competitor-monitor.monthly | daily@09:00 | `competitor-monitor-run.sh` |
| com.balizero.nlm-bridge | on-demand | `uvicorn` |
| com.balizero.regulatory-watcher.daily | daily@07:00 | `regulatory-watcher-run.sh` |
| com.balizero.yield-optimizer.weekly | daily@04:00 | `yield-optimizer-run.sh` |

### Infrastructure crons _(no LLM)_

| Label | Schedule | Script |
|---|---|---|
| com.balizero.bz-daily-visual-pipeline | daily@05:30 | `bash` |
| com.balizero.client-value-predictor | daily@09:00 | `bash` |
| com.balizero.competitor-signal-router.weekly | daily@06:30 | `set` |
| com.balizero.cron-log-sentinel | on-demand | `set` |
| com.balizero.domain-mesh.foundations.daily | daily@04:00 | `bash` |
| com.balizero.indexing-sweep.daily | daily@00:30 | `bash` |
| com.balizero.intel-dedup-gateway | on-demand | `set` |
| com.balizero.intel-lake-nb-pusher.15min | every 15min | `bash` |
| com.balizero.intel-lake-router.5min | every 5min | `bash` |
| com.balizero.intel-lake.outbox-drain.minute | every 60s | `bash` |
| com.balizero.intel-lake.shadow-validate.6h | every 6h | `bash` |
| com.balizero.intel-radar-daily-digest | daily@18:00 | `set` |
| com.balizero.intel.nightly | daily@01:00 | `zsh` |
| com.balizero.meta-dispatcher | on-demand | `set` |
| com.balizero.nb-curator.mode-c.weekly | daily@05:00 | `bash` |
| com.balizero.nuzantara-drive-sync | calendar×2 | `nuzantara-drive-sync.sh` |
| com.balizero.observatory-export | every 60s | `python3` |
| com.balizero.observatory-server | on-demand | `python3` |
| com.balizero.observatory | on-demand | `set` |
| com.balizero.post-publish-poller | on-demand | `python3` |
| com.balizero.post-publish-webhook | on-demand | `python3` |
| com.balizero.regulatory-watcher.fix-b-verify | daily@07:15 | `regulatory-watcher-fix-b-verify.sh` |
| com.balizero.renewal-alerts | daily@08:00 | `bash` |
| com.balizero.research-sentinel | on-demand | `set` |
| com.balizero.seo-cell.28d-check | daily@04:00 | `bash` |
| com.balizero.seo-cell.daily | daily@19:30 | `bash` |
| com.balizero.setup-team.daily | daily@06:00 | `bash` |
| com.balizero.sota.m13-checkpoint | daily@09:00 | `wr2-cron-wrapper.sh` |
| com.balizero.sota.m13-collect | on-demand | `wr2-cron-wrapper.sh` |
| com.balizero.sota.m13-monthly | daily@04:30 | `wr2-cron-wrapper.sh` |
| com.balizero.sota.m13-weekly | daily@06:00 | `wr2-cron-wrapper.sh` |
| com.balizero.translate.hourly | daily@*0:30 | `python3` |
| com.balizero.wr2.canva-apply | on-demand | `wr2-script-wrapper.sh` |
| com.balizero.wr2.canva-gc.weekly | daily@04:30 | `wr2-script-wrapper.sh` |
| com.balizero.wr2.canva-lease-watchdog | every 10min | `source` |
| com.balizero.wr2.canva-oauth-watchdog | every 6h | `bash` |
| com.balizero.wr2.canva-renderer | every 5min | `source` |
| com.balizero.wr2.canva-token-watchdog | daily@09:00 | `source` |
| com.balizero.wr2.connector | daily@04:00 | `wr2-cron-wrapper.sh` |
| com.balizero.wr2.daily-metrics | daily@06:00 | `wr2-script-wrapper.sh` |
| com.balizero.wr2.deploy-puller | every 1h | `bash` |
| com.balizero.wr2.dossier-compiler | daily@04:30 | `wr2-cron-wrapper.sh` |
| com.balizero.wr2.draft-generator | on-demand | `wr2-script-wrapper.sh` |
| com.balizero.wr2.external-bench.monthly | daily@07:00 | `bash` |
| com.balizero.wr2.fact-checker | on-demand | `wr2-script-wrapper.sh` |
| com.balizero.wr2.fact-extractor | on-demand | `wr2-script-wrapper.sh` |
| com.balizero.wr2.hardening | on-demand | `wr2-hardening-chain.sh` |
| com.balizero.wr2.ig-metrics-analyst.weekly | daily@06:07 | `bash` |
| com.balizero.wr2.ig-scraper.daily | daily@03:00 | `python` |
| com.balizero.wr2.image-generator | on-demand | `wr2-script-wrapper.sh` |
| com.balizero.wr2.learner-nightly | daily@03:00 | `wr2-cron-wrapper.sh` |
| com.balizero.wr2.measurer | on-demand | `wr2-cron-wrapper.sh` |
| com.balizero.wr2.newsletter | daily@09:00 | `wr2-cron-wrapper.sh` |
| com.balizero.wr2.oracle | daily@22:30 | `wr2-cron-wrapper.sh` |
| com.balizero.wr2.pg-proxy | on-demand | `fly-pg-proxy-wrapper.sh` |
| com.balizero.wr2.pg-queue-sync | every 10min | `bash` |
| com.balizero.wr2.plist-watchdog | every 15min | `bash` |
| com.balizero.wr2.queue-server | on-demand | `python3` |
| com.balizero.wr2.reflexion.weekly | daily@02:30 | `python` |
| com.balizero.wr2.sla-worker | on-demand | `wr2-cron-wrapper.sh` |
| com.balizero.wr2.strategos | daily@22:00 | `wr2-cron-wrapper.sh` |
| com.balizero.wr2.supervisor-watchdog | on-demand | `wr2-script-wrapper.sh` |
| com.balizero.wr2.supervisor | on-demand | `wr2-script-wrapper.sh` |
| com.balizero.wr2.topic-selector | daily@05:10 | `wr2-script-wrapper.sh` |
| com.balizero.wr2.trend-hunter | on-demand | `wr2-cron-wrapper.sh` |
| com.balizero.wr2.voyager.weekly | daily@02:00 | `python` |

## Skills

- **browser** — Use for ANY browser interaction: reading pages, clicking, filling forms, navigating, verifying deplo (`browser.md`)
- **canva-apply** — Apply pending Canva operations from the War Room. Reads canva_pending.json; if status is "pending",  (`canva-apply.md`)
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
- **nuzantara-llm-test** — Use when testing the Nuzantara multi-LLM gateway — comparing Claude OAuth, Gemini, Codex, DeepSeek,  (`nuzantara-llm-test.md`)
- **nuzantara-monitoring** — Use when checking Nuzantara observability stack — Prometheus metrics, Sentry error tracking, Langfus (`nuzantara-monitoring.md`)
- **nuzantara-parallel-dev** — Use when launching 2+ Claude Code sessions in parallel on Nuzantara (Pro or Air) with tmux + git wor (`nuzantara-parallel-dev.md`)
- **nuzantara-send-email** — Use when sending any email from the Nuzantara/Zantara system — reports, invoices, notifications, CRM (`nuzantara-send-email.md`)
- **nuzantara-spec-driven-dev** — Use when implementing a Nuzantara feature with spec-driven methodology — write spec first, validate  (`nuzantara-spec-driven-dev.md`)
- **nuzantara-tdd** — Apply Test-Driven Development (TDD) methodology with Red-Green-Refactor cycle for all code implement (`nuzantara-tdd.md`)
- **nuzantara-vector-search** — Use for Nuzantara Qdrant operations — semantic search, embedding generation (bge-m3, nomic-embed-tex (`nuzantara-vector-search.md`)
- **software-architecture** — Apply Clean Architecture, SOLID principles, and Domain-Driven Design patterns when designing or refa (`software-architecture.md`)
- **wr2-carousel-pipeline** — Use the existing WR2 (War Room 2.0) Bali Zero pipeline to produce a carousel — drafter (Opus 4.7 OAu (`wr2-carousel-pipeline.md`)

## Drift warnings

**Orphaned plists (script not on disk):**
- `com.balizero.competitor-signal-router.weekly`
- `com.balizero.cron-log-sentinel`
- `com.balizero.intel-dedup-gateway`
- `com.balizero.intel-radar-daily-digest`
- `com.balizero.meta-dispatcher`
- `com.balizero.observatory`
- `com.balizero.research-sentinel`
- `com.balizero.wr2.canva-lease-watchdog`
- `com.balizero.wr2.canva-renderer`
- `com.balizero.wr2.canva-token-watchdog`
