---
date: 2026-06-09
domain: operations
client_case: none
sources:
  - https://docs.exa.ai/concepts/exa-search-works
  - https://exa.ai/pricing
  - https://exa.ai/privacy-policy
  - https://exa.ai/blog/zdr-search-engine
  - https://github.com/exa-labs/exa-mcp-server
  - apps/bali-intel-scraper/scripts/exa_scraper.py (existing internal Exa cron)
  - apps/bali-intel-scraper/config/exa_queries.json
panel:
  - DeepSeek V4 Pro (reasoning_effort=high) — FULL response
  - Claude Opus 4.8 — FAILED (MAX weekly limit, reset 2026-06-12)
  - Gemini 3.1 Pro (agy) — FAILED (OAuth re-login required, headless timeout)
  - Codex GPT-5.5 — FAILED (node not in ssh PATH / stdin hang)
note: panel degraded to 1/4 live LLM (DeepSeek) + 2 deep-research subagents. Infra failures, not refusals.
---

# Exa usage policy for Nuzantara — when & how to use exa.ai neural search

> **TL;DR** — Exa is **already in our stack** (cron scraper, ~510/1000 free req/mo).
> Interactive Exa-MCP is a **complement, not a new capability**, and only for
> **non-PII, public-data, non-freshness-critical** discovery. PII/OSINT → never.
> Indonesian law/KBLI/visa → Gemini-grounded + NotebookLM stay authoritative.

## 0. The correction that started this

Exa was assumed "new". It is NOT. `apps/bali-intel-scraper/scripts/exa_scraper.py`
runs **17 fixed semantic queries daily at 03:00 WITA** on the **same free tier**
(~510/1000 requests/month consumed) feeding NB-INTEL. Any interactive Exa-MCP call
**shares that one 1,000-req/month budget**. This reframes the whole decision:
the question is coordination + sovereignty, not "should we adopt Exa".

## 1. Verified facts (research subagent, dogfooded via Exa itself)

- **What it is**: API-first NEURAL/embeddings search for agents. Edge = semantic
  long-tail discovery + clean LLM-ready markdown content + find-similar +
  `category` (company/people/news) + `deep` mode + Websets (verify+enrich lists).
  Retrieval primitive — you bring your own LLM.
- **Privacy (DECISIVE)**: default endpoint **logs queries**; Privacy Policy
  (2025-11-03) says queries are *"used to improve our products... including by
  training and fine-tuning models"* and *"you should not input personal
  information"*. **Zero-Data-Retention exists but is ENTERPRISE-ONLY** — NOT on
  free/standard PAYG. → A query to default Exa is **retained + trainable**.
- **Freshness is WEAK**: ~24% FreshQA, multi-hour index lag,
  `startCrawlDate`/`endCrawlDate` **silently ignored** since Apr 2026.
- **Pricing**: free 1,000 req/mo (no card); then ~$7/1k search, +$1/1k contents,
  deep $12–15/1k, Websets/Agent $0.025–$2/run. Heavy 50–100 result run ≈ $0.05–0.20.
- **Technical gotchas (verified vs official docs)**:
  - `category=company|people` **reject** `excludeDomains` + all date filters → **400**.
    (`includeDomains` IS allowed for company; people = LinkedIn-only.)
  - `includeText`/`excludeText` accept **one string, ≤5 words** only.
  - MCP `web_search_advanced_exa` exposes filters; `web_search_exa` is basic.
    Our currently-connected connector only has the **basic** + `web_fetch_exa`.

## 2. GREEN-LIST — when an agent SHOULD reach for Exa

1. **Semantic / long-tail PUBLIC-web discovery** that keyword/Google buries —
   "papers/repos/sites like this", fuzzy conceptual queries. Best-in-class. Mode:
   `web_search_advanced_exa`, no category or `category=news`.
2. **find-similar on a known competitor URL** (e.g. a Seminyak villa platform) to
   surface non-obvious similar sites — **only if the URL has no client/OSINT subject**.
3. **Company due-diligence / market mapping on PUBLIC, NON-CLIENT companies**
   (potential partners, competitor landscape) → `category=company` (+ Websets to
   verify+enrich into a structured table). **Never our client's own company.**
4. **Opening a brand-new `research/<domain>/` area NOT covered by NB-INTEL** — a
   single `deep` call (≤10 results, contents on) to seed the brief. For a
   second jurisdiction (Singapore/Estonia) where Gemini-grounded lacks coverage.
5. **Clean markdown extraction from an already-verified-safe URL** when the free
   `WebFetch` is blocked by the page → `web_fetch_exa`. Try free WebFetch FIRST.
6. **Non-Indonesia regulatory/long-tail English research** as a *complement*,
   never the citation of record.

## 3. RED-LIST — when Exa MUST NOT be used

1. **Any query containing client PII or an OSINT subject's name** — KTP, NPWP,
   passport, akta, full client names, any real person under investigation.
   Fatal Law-2 violation: the query string + params are logged and trainable.
   (e.g. the Surya/BTV case → **never** Exa; local-only on the Pro.)
2. **Freshness-critical questions** — "latest visa fee Sept 2026", "today's BPOM
   change", "breaking Bali zoning news". Multi-hour lag + 24% FreshQA = worse than
   free Google. Use Gemini-grounded / live source.
3. **KBLI / visa / normativa / Indonesian business law** — Gemini-grounded is
   authoritative (Claude hallucinates law); NB-INTEL/NB-1 hold curated ground truth.
   Exa adds noise, not authority.
4. **Anything already covered by the daily cron scraper's 17 queries** — wastes
   the shared quota (duplication).
5. **Queries satisfiable by free `WebSearch`/`WebFetch`** — zero-cost first; Exa
   only if free returns nothing useful AND the query fits a green-list bullet.
6. **Lists of real people, even from public data** — "all Bali notaries",
   "immigration officers". OSINT enrichment on individuals = sovereignty breach
   (queries logged). Use the local Playwright browser MCP if truly unavoidable.

## 4. QUOTA coordination (stay on free tier — never trigger paid)

Cron scraper ≈ 510/mo. Free tier = 1,000/mo. Interactive budget = ~490 headroom.

Guardrail (local counter `~/.nuzantara/exa_usage_YYYY-MM.json`, WITA month):
- Before any interactive Exa call the wrapper checks:
  - `daily_interactive_calls < 15` (reset 00:00 WITA), AND
  - `month_total + cron_reserved(550) < 950`.
- Last 5 days of month: block interactive if `month_total > 900` (preserve cron buffer).
- **Paid tier never armed**: no Exa payment key is loaded on the machine. Hitting
  the cap = hard block + log, not an auto-upgrade. (Per CLAUDE.md: paid = Zero's
  explicit authorization, and even then PII boundary holds.)

## 5. PII GUARD — enforceable pre-hook (the load-bearing control)

Every Exa-bound call passes a local `pii_guard` **before** the request leaves the Mac:
- **Denylist** (daily-synced from the Postgres client table, read-only role): all
  client names, company names, KTP/NPWP/passport numbers. Partial tokenized match → block.
- **Regex**: Indonesian KTP (16 digit), NPWP (15 digit / new format), passport
  (letter + 7–9 digit), email. Match → block.
- **Active-OSINT-subject**: if the session context has named an OSINT target,
  temporarily add that name to the denylist for the session.
- **Fail → hard error**: agent must fall back to local Ollama on non-Exa data.

This is the one piece worth **building** (a small wrapper/hook), because the whole
green-list is only safe if PII egress is mechanically impossible, not just promised.
Aligns with §7 "Hooks enforce what prompts cannot".

## 6. DUPLICATION verdict (panel split — recorded honestly)

- **DeepSeek V4 Pro: NET NO** — cron scraper already harvests the high-value
  long-tail; Gemini-grounded + NotebookLM cover authority; interactive Exa adds
  marginal discovery scope while spending shared budget + recurring PII risk.
- **Deep-research subagent: NET YES (narrow)** — interactive ad-hoc semantic
  discovery (mid-session, dynamic queries) is a real capability the *cron* (fixed
  17 queries) cannot do; value is in green-list #1/#3/#4 specifically.

**Synthesis / my call**: **Conditional YES, tightly scoped.** Interactive Exa earns
its place ONLY for green-list #1 (semantic discovery), #3 (public-company DD), and
#4 (new-domain seeding) — i.e. discovery the cron can't reach. Everywhere else it's
NO (NB/Gemini authoritative, or free tools first). So: keep it, gate it hard, don't
let it become a reflex.

## 7. Decision for the MCP install (the original question)

- **Do NOT blind-`claude mcp add`** a 3rd Exa server. We already have the basic
  `web_search_exa` + `web_fetch_exa` connector loaded, plus the cron SDK client.
  Adding `web_search_advanced_exa` as a 3rd entry risks active-active confusion
  (our cicatrix family) and the step's own instruction says "uninstall first".
- **If** we want the filter surface (`category`, `includeDomains`, single-string
  `includeText`), prefer **one** clean install of the official exa-mcp-server with
  `?tools=web_search_advanced_exa`, and **remove/disable** the basic connector so
  there's exactly one Exa MCP. Otherwise keep what we have.
- The skill should be adopted **only with a Law-2 clause prepended** (RED-LIST #1/#6
  verbatim) — the upstream skill pushes "LinkedIn/people/company research" with no
  PII guard, which is unsafe for our client book as-written.

## 8. The thing easy to get wrong

Treating Exa's `deep` mode as a substitute for Gemini-grounded when drafting a visa
SOP or KBLI memo. Exa's Indonesian-language corpus is weak and its freshness is
useless for frequently-updated regulation → confident, obsolete, legally-harmful
advice. Exa discovers; NB + Gemini-grounded adjudicate Indonesian law.

---
_Panel ran on Pro via ssh. 3/4 LLM failed on infra (Claude MAX weekly cap, Gemini
OAuth re-login, Codex node-PATH/stdin) — not refusals. DeepSeek + 2 deep-research
subagents carried the verdict. Re-run full 4-LLM after 2026-06-12 (Claude reset) +
`agy`/`codex` re-auth on Pro if a tie-break is wanted on §6._
