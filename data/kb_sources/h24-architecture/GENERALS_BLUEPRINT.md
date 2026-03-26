# THE GENERALS BLUEPRINT — Nuzantara h24 Autonomous System

**Version:** 2.0 (2026-02-14)
**Architect:** Claude Opus 4.6
**Status:** Operational Design

---

## Design Rationale

The existing architecture defines 5 generals (Coding, Intelligence, Antigravity, Marketing, Perplexity) in the backend code, while Zan's memory uses different names (Kodex, Gravity, Sentinel, Vox, Flash). This blueprint **unifies and rationalizes** the two into one definitive roster.

**Key decisions:**

- **Perplexity General is ELIMINATED.** Perplexity subscription expires ~23 Feb and will not be renewed. Its fact-checking role is absorbed by Sentinel (Gemini 3 Pro + brave-search MCP + browser automation).
- **Flash is ADDED** as a dedicated frontline agent. It was missing from the backend code but exists in the OpenClaw config and is critical for <5s lead response.
- **Names follow Zan's naming** (Kodex, Gravity, Sentinel, Vox, Flash) because they're already in the running system. Backend code will be updated to match.

---

## General #0: ZAN (The Gateway)

| Field              | Value                                                                  |
| ------------------ | ---------------------------------------------------------------------- |
| **Emoji**          | :om:                                                                   |
| **Purpose**        | "Il cervello. Smista tutto, risponde ai clienti, coordina i generali." |
| **Primary Model**  | Sonnet 4.5 (via OpenClaw)                                              |
| **Fallback Model** | Opus 4.6 (complex), Gemini 3 Pro (unlimited context)                   |
| **Mac**            | **Air** (always-on gateway)                                            |
| **RAM Usage**      | ~2GB (OpenClaw process + plugins)                                      |

### Autonomy

| Action                              | Autonomous? | Notes                                      |
| ----------------------------------- | ----------- | ------------------------------------------ |
| Respond to client WhatsApp/Telegram | YES         | Uses KB, pricing reference, visa reference |
| Spawn sub-agent                     | YES         | Any general, via `sessions_spawn`          |
| Create CRM entry                    | YES         | Via Auto CRM Service                       |
| Escalate to Zero                    | YES         | Telegram notification                      |
| Approve payments                    | **NEVER**   | Financial rule: only Zero                  |
| Deploy code                         | **NO**      | Delegates to Gravity                       |

### Triggers

- WhatsApp message received (any DM)
- Telegram message received (any DM)
- Webchat message received
- Webhook from Pro Mac
- Cron: heartbeat every 30 min (built-in)

### Tools

- `web_search`, `web_fetch` (brave-search MCP)
- `exec` (shell commands on Air)
- `sessions_spawn` (spawn generals)
- `cron` (schedule events)
- `memory_search` (LanceDB semantic search)
- `file_read`, `file_write` (workspace)
- `telegram`, `whatsapp`, `imessage` (messaging)
- `voice_call` (Twilio)
- `nodes_run` (execute on Pro via node system)

### Talks To

All generals + Zero (escalation)

---

## General #1: KODEX (The Builder)

| Field              | Value                                                                 |
| ------------------ | --------------------------------------------------------------------- |
| **Emoji**          | :crossed_swords:                                                      |
| **Purpose**        | "Codice che funziona, test che passano, deploy che non crasha."       |
| **OpenClaw ID**    | `coding-general`                                                      |
| **Primary Model**  | Sonnet 4.5                                                            |
| **Fallback Model** | Opus 4.6 (complex architecture)                                       |
| **Mac**            | **Air** (spawned by Zan) + **Pro** (heavy tasks via SSH/cursor agent) |
| **RAM Usage**      | ~1.5GB (OpenClaw sub-agent)                                           |

### Autonomy

| Action                                 | Autonomous? | Notes                                             |
| -------------------------------------- | ----------- | ------------------------------------------------- |
| Fix typos, minor refactors (Level 1)   | YES         | Auto-commit, auto-push                            |
| Bug fixes, utility functions (Level 2) | YES         | Create branch, open PR                            |
| DB migrations, architecture (Level 3)  | NO          | Draft PR, request Zero review                     |
| Run tests                              | YES         | `PYTHONPATH=. pytest`                             |
| Deploy to production                   | NO          | Delegates to Gravity                              |
| Delegate to Cursor Agent               | YES         | `cursor agent --model cursor-ultra` for IDE tasks |

### Triggers

- `generals_tasks` with `task_type='code'` (database polling)
- Sentry error alert (immediate)
- New GitHub Issue
- PR review request
- Cron: daily 12:00 WITA (tech debt scan)

### Tools

- `exec` (shell: git, pytest, ruff, mypy)
- `file_read`, `file_write` (code editing)
- `cursor agent` CLI (IDE-aware coding on Air)
- SSH to Pro for heavy compute
- GitHub CLI (`gh`)
- `generals_memory` (read/write shared state)
- `generals_locks` (file-level resource locking)

### Talks To

- **Zan** (receives tasks, reports status)
- **Gravity** (requests deployment after code ready)
- **Sentinel** (receives context for domain-specific code)

---

## General #2: GRAVITY (The Orchestrator)

| Field              | Value                                                                      |
| ------------------ | -------------------------------------------------------------------------- |
| **Emoji**          | :milky_way:                                                                |
| **Purpose**        | "Il sistema gira. Se non gira, lo faccio girare. Se non posso, ti avviso." |
| **OpenClaw ID**    | `antigravity-general`                                                      |
| **Primary Model**  | Gemini 3 Pro (unlimited, good for log analysis)                            |
| **Fallback Model** | Sonnet 4.5                                                                 |
| **Mac**            | **Both** (monitors both, deploys from Air)                                 |
| **RAM Usage**      | ~1GB                                                                       |

### Autonomy

| Action                                    | Autonomous? | Notes                               |
| ----------------------------------------- | ----------- | ----------------------------------- |
| Health check (Fly.io, Qdrant, PostgreSQL) | YES         | Every 30 min                        |
| Restart Fly.io machine                    | YES         | If health check fails               |
| Rollback deployment                       | YES         | Immediate on crash detected         |
| Clean expired locks                       | YES         | Every 5 min                         |
| Deploy new code                           | YES         | Only if tests pass + Kodex approves |
| Force deploy without tests                | **NEVER**   |                                     |
| Delete production data                    | **NEVER**   |                                     |
| Restart Pro OpenClaw                      | YES         | Via SSH if unresponsive             |

### Triggers

- Cron: every 30 min (deep health check)
- Cron: every 5 min (lock cleanup)
- Deploy failure event
- Database lock timeout
- Disk space warning (>85%)
- Kodex requests deployment

### Tools

- `fly` CLI (deploy, status, logs, ssh)
- `exec` (system commands: disk, memory, processes)
- SSH to Pro (`ssh nuzantara@192.168.0.17`)
- `generals_locks` (lock management)
- `curl` (health endpoint checks)
- `gh` CLI (GitHub status, actions)
- Vercel CLI (frontend deploy verification)

### Talks To

- **Zan** (reports system status, escalates critical issues)
- **Kodex** (receives deploy requests, reports deploy status)
- **Sentinel** (shares system metrics for analysis)

---

## General #3: SENTINEL (The Strategist)

| Field              | Value                                                                                          |
| ------------------ | ---------------------------------------------------------------------------------------------- |
| **Emoji**          | :satellite:                                                                                    |
| **Purpose**        | "Conosco le leggi, monitoro i competitor, verifico i fatti. Nessuno mente sotto il mio watch." |
| **OpenClaw ID**    | `intelligence-general`                                                                         |
| **Primary Model**  | Gemini 3 Pro (unlimited, 2M context for documents)                                             |
| **Fallback Model** | Opus 4.6 (complex reasoning)                                                                   |
| **Mac**            | **Air** (spawned by Zan)                                                                       |
| **RAM Usage**      | ~1GB                                                                                           |

### Autonomy

| Action                            | Autonomous? | Notes                              |
| --------------------------------- | ----------- | ---------------------------------- |
| Web research                      | YES         | brave-search + web_fetch           |
| Scrape competitor sites           | YES         | Playwright MCP                     |
| Update Knowledge Base (Qdrant)    | YES         | Via ingestion scripts              |
| Generate market reports           | YES         | Saved to `memory/reports/`         |
| Verify claims from other generals | YES         | Cross-reference sources            |
| Modify business pricing           | **NEVER**   | Only Zero via PRICING_REFERENCE.md |
| Send external communications      | **NO**      | Only internal reports              |

### Triggers

- Cron: daily 08:00 WITA (morning intelligence briefing)
- Cron: every 6h (competitor watch)
- User research request (via Zan)
- Market anomaly detected (price changes, regulation updates)
- Fact-check request from Vox or Kodex

### Tools

- `web_search` (brave-search MCP)
- `web_fetch` (URL content extraction)
- `playwright` (browser automation for scraping)
- `file_read`, `file_write` (reports, KB updates)
- `memory_search` (semantic recall)
- Bali Intel Scraper (`apps/bali-intel-scraper/`)
- PostgreSQL queries (Knowledge Graph: 56K nodes, 161K edges)
- Qdrant queries (7 collections, 58K vectors)

### Talks To

- **Zan** (receives research requests, delivers reports)
- **Kodex** (provides domain context for code)
- **Vox** (fact-checks marketing claims, provides trend data)

**Note:** Sentinel absorbs the Perplexity General's role entirely. It has the same capabilities (web search, fact-checking, citation) plus access to the full Knowledge Graph and Vector DB.

---

## General #4: VOX (The Voice)

| Field              | Value                                                                    |
| ------------------ | ------------------------------------------------------------------------ |
| **Emoji**          | :mega:                                                                   |
| **Purpose**        | "Trasformo i dati in storie. Il mondo deve sapere che Bali Zero esiste." |
| **OpenClaw ID**    | `marketing-general`                                                      |
| **Primary Model**  | Sonnet 4.5 (best for creative writing)                                   |
| **Fallback Model** | Gemini 3 Pro (unlimited for long content)                                |
| **Mac**            | **Air** (spawned by Zan)                                                 |
| **RAM Usage**      | ~1GB                                                                     |

### Autonomy

| Action                   | Autonomous? | Notes                      |
| ------------------------ | ----------- | -------------------------- |
| Draft blog posts         | YES         | Via Article Composer API   |
| Draft social media posts | YES         | Saved as drafts            |
| Publish to blog (GitHub) | YES         | If confidence >0.95        |
| Post to social media     | NO          | Draft only, Zero approves  |
| SEO optimization         | YES         | Keywords, meta tags        |
| Create graphics/images   | YES         | Via image generation tools |
| Email campaigns          | NO          | Zero approves              |

### Triggers

- Cron: 09:00, 15:00, 21:00 WITA (social pulse check, 3x/day)
- Cron: midnight WITA (content calendar sync)
- New blog post published (promote it)
- Sentinel reports trending topic relevant to Nuzantara
- New feature shipped by Kodex (write launch post)

### Tools

- Article Composer API (`POST /api/article-composer/compose`)
- `file_read`, `file_write` (content drafts)
- `web_search` (trend monitoring)
- GitHub CLI (publish blog posts)
- `memory_search` (recall past campaigns)
- OpenAI image generation (skill)

### Talks To

- **Zan** (receives content requests)
- **Sentinel** (requests fact-checking, gets trend data)

---

## General #5: FLASH (The Frontline)

| Field              | Value                                               |
| ------------------ | --------------------------------------------------- |
| **Emoji**          | :zap:                                               |
| **Purpose**        | "Rispondo in 2 secondi. Se non so, passo a chi sa." |
| **OpenClaw ID**    | `frontline-general`                                 |
| **Primary Model**  | Gemini Flash (unlimited, <2s response)              |
| **Fallback Model** | Haiku 4.5 (fast, cheap)                             |
| **Mac**            | **Air** (always-ready, minimal resources)           |
| **RAM Usage**      | ~500MB                                              |

### Autonomy

| Action                           | Autonomous? | Notes                                      |
| -------------------------------- | ----------- | ------------------------------------------ |
| Answer FAQ (visa types, pricing) | YES         | From KB, reference docs                    |
| Triage incoming messages         | YES         | Classify and route                         |
| Respond to simple queries        | YES         | <5 second response time                    |
| Handle complex queries           | NO          | Escalates to Zan or Sentinel               |
| Give pricing                     | YES         | ONLY from PricingTool/PRICING_REFERENCE.md |
| Schedule appointments            | NO          | Escalates to Zan                           |

### Triggers

- Direct invocation by Zan (for triage/quick response)
- WhatsApp webhook (first-response before Zan processes)
- High-volume periods (load balancing)

### Tools

- `PRICING_REFERENCE.md` (read-only)
- `VISA_TYPES_REFERENCE.md` (read-only)
- `memory_search` (FAQ lookup)
- Response templates (pre-built for common questions)

### Talks To

- **Zan** (escalates complex queries)
- **Kodex** (escalates technical questions)
- **Sentinel** (escalates research questions)
- **Vox** (escalates marketing questions)

---

## Summary Table

| #   | Name     | Emoji            | Model        | Mac     | Autonomy                | Key Metric     |
| --- | -------- | ---------------- | ------------ | ------- | ----------------------- | -------------- |
| 0   | Zan      | :om:             | Sonnet 4.5   | Air     | Gateway                 | Uptime >99.9%  |
| 1   | Kodex    | :crossed_swords: | Sonnet 4.5   | Air+Pro | High                    | Tests passing  |
| 2   | Gravity  | :milky_way:      | Gemini 3 Pro | Both    | Critical                | System healthy |
| 3   | Sentinel | :satellite:      | Gemini 3 Pro | Air     | Medium                  | Reports/day    |
| 4   | Vox      | :mega:           | Sonnet 4.5   | Air     | High draft, Med publish | Content/week   |
| 5   | Flash    | :zap:            | Gemini Flash | Air     | High (FAQ only)         | Response <5s   |

---

## What Changed from v1.0

| Aspect         | v1.0 (Backend Code)                                  | v2.0 (This Blueprint)              | Why                            |
| -------------- | ---------------------------------------------------- | ---------------------------------- | ------------------------------ |
| Names          | coding/intelligence/antigravity/marketing/perplexity | Kodex/Sentinel/Gravity/Vox/Flash   | Align with running system      |
| Perplexity     | Dedicated general                                    | **ELIMINATED**                     | Sub expiring, Sentinel absorbs |
| Flash          | Not defined                                          | **ADDED**                          | Critical for <5s lead response |
| Models         | Generic                                              | Specific per general               | Cost optimization              |
| Mac assignment | Not specified                                        | Explicit per general               | Resource management            |
| Cursor Agent   | Not mentioned                                        | Kodex can delegate                 | Leverage $200/mo subscription  |
| Kimi 2.5       | Not mentioned                                        | Available for Kodex (long context) | Don't waste $20/mo             |
