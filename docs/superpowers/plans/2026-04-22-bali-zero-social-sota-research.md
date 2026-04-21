# Bali Zero Social SOTA 2026 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a living research system — Fase 0 (10 days intensive shot) + Loop 90d rolling — that produces a playbook, persona engine, and M13 feedback loop that WR2 reads as live configuration.

**Architecture:** 3 layers (Telemetry / Knowledge Acquisition / Synthesis) × 5 modules (telemetry_bootstrap, empirical_ig, benchmark_competitor, literature_synthesis, consiglio_playbook), integrated into existing WR2 pipeline at 3 injection points (editorial_config.py, Council deliberation persona input, M13FeedbackLoop).

**Tech Stack:** Python 3.11+, FastAPI, asyncpg, httpx, Ahrefs MCP, NotebookLM MCP, Playwright MCP, Claude Max OAuth CLI, Gemini 3.1 Pro CLI, Codex GPT-5.4 CLI, DeepSeek Reasoner API (audited exception), Ollama local (qwen2.5vl:7b + gemma4:26b), Grafana Cloud free tier, Postgres Fly (existing), launchd on Pro.

**Spec:** `docs/superpowers/specs/2026-04-22-bali-zero-social-sota-research-design.md`

---

## File Structure

### New files (28 total)

**Research artifacts (output, not code):** 12 files in `research/sota-social-2026-v1/` created by tasks 3-22.

**Backend services (code):**
- `apps/backend-rag/backend/services/measurer/ig_graph_sensor.py` — IG Graph API sensor for Bali Zero's own account
- `apps/backend-rag/backend/services/measurer/brevo_stats_client.py` — Brevo newsletter stats fetch
- `apps/backend-rag/backend/services/measurer/m13_feedback_loop.py` — closes post→measure→retrain loop
- `apps/backend-rag/backend/services/war_room/editorial_config.py` — playbook-driven config (cadence, format mix, persona weights)
- `apps/backend-rag/backend/services/council/persona_models.py` — Persona dataclass + loader
- `apps/backend-rag/backend/services/research/__init__.py` — new module umbrella
- `apps/backend-rag/backend/services/research/classifier_client.py` — wraps Claude/Gemini classify calls
- `apps/backend-rag/backend/services/research/literature_agent.py` — NotebookLM + Gemini Deep Research orchestration
- `apps/backend-rag/backend/services/research/persona_inference.py` — NotebookLM comment-based persona builder
- `apps/backend-rag/backend/services/research/consiglio_orchestrator.py` — 4-LLM deliberation for playbook synthesis
- `apps/backend-rag/backend/services/research/competitor_ingest.py` — Google Sheet → competitor_corpus.json
- `apps/backend-rag/backend/services/research/empirical_ig_analyzer.py` — classify 25 own posts
- `apps/backend-rag/backend/services/research/format_matrix_builder.py` — 294-cell matrix generator

**Cron scripts (launchd triggered):**
- `scripts/m13_collect_post_metrics.py` — every 6h
- `scripts/m13_weekly_report.py` — Sunday 06:00 WITA
- `scripts/m13_monthly_retrain.py` — 1st of month 04:30 WITA
- `scripts/m13_checkpoint.py` — days 30/60/90

**Launchd plists:**
- `infra/launchagents/com.balizero.sota.m13-collect.plist`
- `infra/launchagents/com.balizero.sota.m13-weekly.plist`
- `infra/launchagents/com.balizero.sota.m13-monthly.plist`
- `infra/launchagents/com.balizero.sota.m13-checkpoint.plist`

**Migration:** `apps/backend-rag/backend/db/migrations_v2/128_m13_feedback.sql` — tables for post_metrics_history + retrain_log.

**Tests:** matching `_test.py` in `apps/backend-rag/backend/tests/unit/services/{measurer,war_room,council,research}/`.

**Team runbook:** `docs/runbooks/competitor-scrape-manual.md` for 25h team-member work.

### Modified files (4 total)
- `apps/backend-rag/backend/services/council/tone_council.py` — accept persona input
- `apps/backend-rag/backend/services/council/cli_runners.py` — add Consiglio orchestrator mode
- `apps/backend-rag/backend/services/publisher/orchestrator.py` — integrate M13 metric callback
- `apps/backend-rag/backend/app/routers/` — NEW `research.py` router for Telegram kill switches (`/research pause` etc.)

---

## Progress Tracker

Planned tasks split across 4 files for readability. Execute in order:

1. **Task 0** — Open questions resolution (below, this file)
2. **Fase 0 — Days 1-10** (see `2026-04-22-bali-zero-social-sota-research-phase0.md`)
3. **Loop 90 days infrastructure** (see `2026-04-22-bali-zero-social-sota-research-loop.md`)
4. **WR2 integration + Grafana + final smoke** (see `2026-04-22-bali-zero-social-sota-research-integration.md`)

---

## Task 0: Resolve open questions (Zero-blocking)

**Files:** No code yet — this is a human decision task.

**Why first:** Five questions in the spec are prerequisites. Answering them defines concrete values used downstream (team member name, OAuth tokens, Grafana URL, UTM fix scope, demographics strategy).

- [ ] **Step 1: Open spec and read "Open questions" section**

Run: `less docs/superpowers/specs/2026-04-22-bali-zero-social-sota-research-design.md` and navigate to line 308.

Expected: 5 numbered questions visible.

- [ ] **Step 2: Answer Q1 (team member)**

Post in Telegram to Zero:
```
"SOTA Fase 0 task 0 — chi del team può dedicare 25h (spalmate 5gg lavorativi
= 5h/gg) a scrape manuale 18 account competitor × 15 post IG? Opzioni:
Krisna / Adit / Ari / altro? Runbook dettagliato pronto."
```

Record answer in `docs/superpowers/plans/open-questions-log.md`:
```markdown
## Q1 — Team member
**Assigned:** <name>
**Availability window:** <dates>
**Approval:** <Telegram message URL or timestamp>
```

- [ ] **Step 3: Answer Q2 (Grafana instance)**

Run:
```bash
# Check if we already have a Grafana Cloud account
grep -r "grafana" apps/backend-rag/backend/ .github/ infra/ 2>/dev/null | grep -v node_modules | head
ls -la ~/.grafana 2>/dev/null
cat ~/.nuzantara-secrets.env 2>/dev/null | grep -i grafana
```

Expected: either find existing instance creds (capture URL+key) OR nothing (create new Cloud free account).

Record in `open-questions-log.md`:
```markdown
## Q2 — Grafana
**Instance:** <existing URL | NEW Cloud free}
**URL:** https://<tenant>.grafana.net
**API key location:** ~/.nuzantara-secrets.env key=GRAFANA_CLOUD_API_KEY
```

If NEW: register at https://grafana.com/auth/sign-up/create-user (free tier 10k metrics), save API key.

- [ ] **Step 4: Answer Q3 (IG Graph API token)**

Run:
```bash
grep -r "IG_GRAPH_API\|INSTAGRAM_TOKEN\|META_GRAPH" \
    ~/.nuzantara-secrets.env \
    apps/backend-rag/.env.example \
    2>/dev/null
```

Expected: find token or confirm absent.

If token exists: verify validity:
```bash
source ~/.nuzantara-secrets.env
curl -sS "https://graph.facebook.com/v20.0/me?access_token=$IG_GRAPH_API_TOKEN" | jq .
```

Expected output: JSON with `"id"` field, no `"error"` key. Token valid.

If token missing or expired: trigger fresh OAuth flow at https://developers.facebook.com/tools/explorer/ using Bali Zero Business Manager. Record new token in `~/.nuzantara-secrets.env`:
```bash
echo 'export IG_GRAPH_API_TOKEN="<new-token>"' >> ~/.nuzantara-secrets.env
echo 'export IG_BUSINESS_ACCOUNT_ID="<numeric-id>"' >> ~/.nuzantara-secrets.env
```

Record in `open-questions-log.md`:
```markdown
## Q3 — IG Graph API
**Token status:** valid | renewed YYYY-MM-DD
**Business account ID:** <numeric>
**Token expires:** <YYYY-MM-DD from Graph API response>
```

- [ ] **Step 5: Answer Q4 (CRM UTM fix scope)**

Read the CRO audit:
```bash
less docs/cro/2026-04-19-funnel-audit.md
```

Find the UTM section (grep `UTM` inside). The spec commits to fixing UTM as part of telemetry_bootstrap — confirm scope is:
1. Fix UTM builder in WR2 publisher
2. Backfill `clients.utm_source` from GA4 export (last 90 days)
3. Add UTM validation to CRO audit cron

Record in `open-questions-log.md`:
```markdown
## Q4 — CRM UTM fix
**Decision:** IN-SCOPE Fase 0 day 1 (telemetry_bootstrap)
**Sub-scope:**
  - Fix `utm_builder.py` (missing source/medium/campaign enforcement)
  - Backfill `clients.utm_source` from GA4 last 90d (script one-shot)
  - Add validator to existing CRO cron
**Estimated dev time:** 4h (stays inside day 1 budget)
```

- [ ] **Step 6: Answer Q5 (Phyllo substitute)**

The spec proposes Socialblade + NotJustAnalytics free tier (covers engagement + growth + qualitative persona, NOT age/gender). Decision criteria:
- If Zero accepts 3/5 dimensions: stay arsenal-only ($0)
- If Zero wants demographics: add $30 Phyllo 1-month

Post to Zero in Telegram:
```
"SOTA task 0 Q5: demografici (age/gender/geo) dei 8 influencer expat — ok
senza? combo gratis (Socialblade + NotJustAnalytics + NotebookLM) copre
3/5 dimensioni. Oppure vuoi +$30 Phyllo 1 mese per precisione demografica?"
```

Record answer.

- [ ] **Step 7: Commit open questions log**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add docs/superpowers/plans/open-questions-log.md ~/.nuzantara-secrets.env
# Note: secrets.env is gitignored — record only decisions in open-questions-log.md
git add docs/superpowers/plans/open-questions-log.md
git commit -m "$(cat <<'EOF'
docs(sota): resolve 5 open questions from research design spec

- Q1 team member: <name>, window <dates>
- Q2 Grafana: <existing|new-cloud-free>
- Q3 IG Graph API: token <status>, expires <date>
- Q4 CRM UTM fix: in-scope day 1 (4h)
- Q5 Phyllo: <declined|approved-30usd>

Unblocks Fase 0 day 1. Plan files:
docs/superpowers/plans/2026-04-22-bali-zero-social-sota-research*.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review (run after all three phase files written)

1. **Spec coverage check:** each of the 12 deliverables in spec line 125-138 has at least one task creating it. Each of the 7 gates has a verification step. M13 three triggers (6h/weekly/monthly) each have a dedicated task.
2. **Placeholder scan:** no `TBD`, `TODO`, `implement later`, `fill in`, `similar to task N`, or un-defined function references.
3. **Type consistency:** `Persona` class signature same across `persona_models.py`, `deliberation.py`, `consiglio_orchestrator.py`. `IGGraphSensor.read()` return type identical everywhere it's called.

---

## Execution Handoff

Tasks 1-50+ are split across 3 companion plan files for readability. Start by executing Task 0 above, then proceed to the phase-0 file.

Next files to write:
- `docs/superpowers/plans/2026-04-22-bali-zero-social-sota-research-phase0.md` (Fase 0 Days 1-10)
- `docs/superpowers/plans/2026-04-22-bali-zero-social-sota-research-loop.md` (Loop 90d cron infrastructure)
- `docs/superpowers/plans/2026-04-22-bali-zero-social-sota-research-integration.md` (WR2 hooks + Grafana + final smoke)
