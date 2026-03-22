# Google/Gemini Ecosystem — Federation Integration Map

> Generated: 2026-03-23 | For: Nuzantara Federation v3
> Context: Zero created SEO Guardian by leveraging Gemini's native access to GA4 + GSC

---

## Current Integrations (Already in Arsenal)

| # | Product | Integration | Status |
|---|---------|------------|--------|
| 1 | **Gemini CLI** | Native CLI, MCP: nuzantara-mcp | Installed, active |
| 2 | **GA4 Analytics** | MCP server (ga4-analytics) | Active, property 505466833 |
| 3 | **Google Search Console** | MCP server (google-search-console, 19 tools) | Active, SA auth |
| 4 | **Google Drive** | NuzMCP tools (5) + SA auth | Active |
| 5 | **Google Sheets** | NuzMCP tools (4) + SA auth | Active |
| 6 | **Antigravity IDE** | Installed, OpenClaw bridge skill | Active |
| 7 | **Google Maps Platform** | Gemini ext (disabled), OpenClaw skill (goplaces) | Partial |

---

## Tier 1 — HIGH PRIORITY (Direct Business Value)

| # | Product | What It Does | API | MCP | Automate | Priority |
|---|---------|-------------|-----|-----|----------|----------|
| 8 | **Gemini API / AI Studio** | LLM inference, grounding, code exec, context caching | Yes (REST + SDK) | Via @ai-sdk/google | Yes | **HIGH** |
| 9 | **NotebookLM** | AI notebooks, audio overview, podcast gen | Alpha (Enterprise), unofficial (35 MCP tools) | **Yes** (`notebooklm-mcp-cli`) | Yes | **HIGH** |
| 10 | **Google Ads API** | Campaign management, keyword research, performance data | Yes (REST) | Community | Yes | **HIGH** |
| 11 | **Google Business Profile** | Business listing, reviews, posts, analytics | Yes (REST) | Community | Yes | **HIGH** |
| 12 | **Google Trends** | Search trends, regional interest, related topics | Unofficial (pytrends) | Community | Yes | **HIGH** |
| 13 | **Vertex AI Agent Builder** | Build, deploy, manage AI agents with grounding | Yes (REST + SDK) | No | Yes | **HIGH** |
| 14 | **Google Calendar** | Scheduling, events, reminders | Yes (REST) | Already have (Gemini ext) | Yes | **HIGH** |
| 15 | **Gmail** | Email management, search, send | Yes (REST) | Already have (Gemini ext) | Yes | **HIGH** |

---

## Tier 2 — MEDIUM PRIORITY (Operational Value)

| # | Product | What It Does | API | MCP | Automate | Priority |
|---|---------|-------------|-----|-----|----------|----------|
| 16 | **BigQuery** | Serverless data warehouse, SQL analytics | Yes (REST + SDK) | Community MCP | Yes | **MED** |
| 17 | **Looker Studio** | Dashboard, data viz, reporting | Yes (Embed + REST) | No | Limited | **MED** |
| 18 | **Firebase Auth** | User authentication, SSO | Yes (Admin SDK) | No | Yes | **MED** |
| 19 | **Firebase Firestore** | NoSQL document database | Yes (Admin SDK) | Community MCP | Yes | **MED** |
| 20 | **Cloud Document AI** | OCR, document parsing, form extraction | Yes (REST) | No | Yes | **MED** |
| 21 | **Google Cloud Run** | Serverless containers | Yes (REST + gcloud) | No | Yes | **MED** |
| 22 | **Cloud Functions** | Serverless functions (event-driven) | Yes (REST + gcloud) | No | Yes | **MED** |
| 23 | **Google Translate API** | Translation, language detection | Yes (REST + SDK) | No | Yes | **MED** |
| 24 | **Google Vision AI** | Image analysis, OCR, labels, faces | Yes (REST) | No | Yes | **MED** |
| 25 | **Speech-to-Text** | Audio transcription, streaming | Yes (REST) | No | Yes | **MED** |
| 26 | **Text-to-Speech** | Audio synthesis, voice cloning | Yes (REST) | No | Yes | **MED** |
| 27 | **Google Contacts** | Contact management | Yes (People API) | No | Yes | **MED** |
| 28 | **Google Forms** | Form creation, response collection | Yes (REST) | No | Yes | **MED** |
| 29 | **YouTube Data API** | Video metadata, search, channels, playlists | Yes (REST) | Community | Yes | **MED** |
| 30 | **Google Docs** | Document creation, editing | Yes (REST) | Via Workspace ext | Yes | **MED** |
| 31 | **Google Pub/Sub** | Messaging, event streaming | Yes (REST + SDK) | No | Yes | **MED** |
| 32 | **Google Tasks** | Task management | Yes (REST) | No | Yes | **MED** |
| 33 | **Apps Script** | Workspace automation, macros, triggers | Yes (REST + Script) | No | Yes | **MED** |
| 34 | **Tag Manager** | Marketing tags, tracking management | Yes (REST) | No | Yes | **MED** |
| 35 | **Firebase Genkit** | AI framework for Node.js, Go (flows, tools, evals) | Yes (SDK) | No | Yes | **MED** |

---

## Tier 3 — LOW PRIORITY (Nice to Have)

| # | Product | What It Does | API | MCP | Automate | Priority |
|---|---------|-------------|-----|-----|----------|----------|
| 36 | **Gemini App** (consumer) | Chat UI, image gen, Gems, extensions | No public API | No | Browser only | **LOW** |
| 37 | **Google Colab** | Jupyter notebooks in cloud | Yes (Colab API) | No | Limited | **LOW** |
| 38 | **IDX** | Cloud IDE by Google | No API | No | No | **LOW** |
| 39 | **Google Meet** | Video conferencing | Yes (REST) | No | Limited | **LOW** |
| 40 | **Google Keep** | Notes, lists | No public API | No | No | **LOW** |
| 41 | **Google Sites** | Website builder | No API | No | No | **LOW** |
| 42 | **Google Chat** (Workspace) | Team messaging | Yes (REST + Bot API) | No | Yes | **LOW** |
| 43 | **Dialogflow CX** | Conversational AI platform | Yes (REST + SDK) | No | Yes | **LOW** |
| 44 | **Chrome Extensions** | Browser extension platform | Yes (Chrome API) | N/A | Yes | **LOW** |
| 45 | **Google Earth Engine** | Geospatial analysis | Yes (REST + Python) | No | Yes | **LOW** |
| 46 | **Mandiant** | Threat intelligence | Yes (REST) | No | Yes | **LOW** |
| 47 | **Firebase Hosting** | Static web hosting + CDN | Yes (gcloud + SDK) | No | Yes | **LOW** |
| 48 | **Firebase Cloud Messaging** | Push notifications | Yes (Admin SDK) | No | Yes | **LOW** |
| 49 | **Vertex AI Model Garden** | Model marketplace (PaLM, Gemma, Llama, etc.) | Yes (REST) | No | Yes | **LOW** |
| 50 | **Google Natural Language** | Entity analysis, sentiment, syntax | Yes (REST) | No | Yes | **LOW** |
| 51 | **Vertex AI Search** | Enterprise search with grounding | Yes (Discovery Engine) | No | Yes | **LOW** |
| 52 | **reCAPTCHA Enterprise** | Bot detection, fraud prevention | Yes (REST) | No | Yes | **LOW** |
| 53 | **Google Wallet** | Digital passes, loyalty cards | Yes (REST) | No | Yes | **LOW** |
| 54 | **Google Places (New)** | Place details, photos, reviews | Yes (REST) | OpenClaw goplaces | Yes | **LOW** |

---

## Key Insight: Gemini as Meta-Gateway

Il punto chiave che hai scoperto col SEO Guardian: **Gemini ha accesso nativo** a molti servizi Google senza bisogno di API keys separate:

```
Gemini CLI/App → accesso diretto a:
├── Google Search (grounded)
├── GA4 Analytics (via extension/MCP)
├── Google Search Console (via extension/MCP)
├── Google Workspace (Gmail, Drive, Calendar, Docs)
├── Google Maps
├── YouTube
└── ... potenzialmente ogni prodotto Google
```

Questo significa che **Gemini è il punto di ingresso naturale** per tutto l'ecosistema Google nella federation. Non serve integrare ogni servizio singolarmente — Gemini CLI con le giuste estensioni è già il meta-gateway.

---

## NotebookLM — Deep Dive

### Cosa hai già nel codebase
- `auth_notebooklm.py` — Login Playwright con persistent context
- `debug_notebooklm.py` — Debug headless login
- `create_bundles.py` — Bundle codebase files per upload (6 bundles)
- `tmp_notebooklm/` — 11 file pre-bundled
- `google_bridge.py` (NuzMCP) — Tool `upload_to_notebooklm_tool`
- `notebooklm_cache_service.py` — Redis cache per Q&A
- `data/notebooklm_responses/` — 640 Q&A templates (6 domini)
- `scripts/caching/master_pipeline.py` — 5-fase caching pipeline

### Opzione consigliata: `notebooklm-mcp-cli`
```bash
uv tool install notebooklm-mcp-cli
nlm login          # One-time browser auth
nlm setup add claude-code  # Auto-configures .mcp.json → 35 tools
```
Sostituisce i fragili script Playwright con 35 MCP tools stabili.

### Enterprise API (Alpha)
- Endpoint: `discoveryengine.googleapis.com`
- CRUD notebooks + sources + audio overview
- **NO query/converse** nell'API ufficiale
- Richiede Gemini Enterprise license

### Standalone Podcast API (No license needed)
```bash
POST https://discoveryengine.googleapis.com/v1/projects/{PROJECT}/locations/global/podcasts
```
Genera podcast da testo/immagini/audio. Solo `Podcast API User` IAM role.

---

## Gemini CLI Extensions — Stato Attuale

| Extension | Status | Tools |
|-----------|--------|-------|
| advanced-seo-mcp | Disabled | SEO analysis |
| co-researcher | Disabled | 15 research skills (systematic review, peer review, etc.) |
| google-maps-platform | Disabled | Google Maps APIs |
| google-workspace | Disabled | Gmail, Calendar, Drive, Docs |
| google-workspace-inbox | Disabled | Email inbox management |

**Tutte disabilitate.** Abilitando `google-workspace` e `co-researcher` si aggiungono ~20+ tools al Gemini CLI.

---

## Action Items per Federation v3

### Quick Wins (this week)
1. **Abilita Gemini extensions** `google-workspace` + `co-researcher` → +20 tools gratis
2. **Installa `notebooklm-mcp-cli`** → +35 tools, ritira script Playwright
3. **Aggiungi Google Ads MCP** → competitor keyword intelligence
4. **Aggiungi Google Business Profile** → review monitoring

### Medium Term (2 weeks)
5. Integra Google Trends API (pytrends) come MCP tool o NuzMCP module
6. Abilita `google-maps-platform` extension (già installata)
7. BigQuery per analytics warehouse (se i volumi crescono)

### Long Term (1 month)
8. Vertex AI Agent Builder per agenti production-grade
9. NotebookLM Enterprise API quando esce da alpha
10. Podcast API per generare audio briefing automatici

---

## Conteggio Finale

| Categoria | Count |
|-----------|-------|
| Prodotti Google mappati | **54** |
| Già integrati | 7 |
| Con API pubblica | 42 |
| Con MCP (ufficiale o community) | 12 |
| Automatizzabili | 48 |
| Alta priorità non ancora integrati | 8 |

**Totale touchpoint Google sfruttabili: 54** (di cui 48 automatizzabili)
