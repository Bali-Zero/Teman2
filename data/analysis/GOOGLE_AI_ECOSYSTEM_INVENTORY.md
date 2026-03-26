# Google/Gemini AI Ecosystem Inventory (March 2026)

**Purpose:** Comprehensive mapping of all Google products/apps for AI federation integration
**Last Updated:** 2026-03-23
**Total Touchpoints Identified:** 72

---

## Legend

- **API:** Yes = full REST/gRPC API | Limited = restricted/alpha | No = no API
- **MCP:** Official = Google-managed MCP server | Community = third-party MCP | No = none found
- **Automation:** Full = complete programmatic control | Partial = some features | No = manual only
- **Priority for Nuzantara:** HIGH = immediate value for Bali Zero BI platform | MED = useful mid-term | LOW = niche/future

---

## TIER 1 -- CORE AI MODELS & PLATFORMS

| #   | Product                                              | What It Does                                                | API                  | MCP                     | Automation | Priority | Notes                                                                                                            |
| --- | ---------------------------------------------------- | ----------------------------------------------------------- | -------------------- | ----------------------- | ---------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
| 1   | **Gemini API** (ai.google.dev)                       | Core LLM API (3.1 Pro, Flash, Flash Lite)                   | Yes                  | Official (Vertex AI)    | Full       | **HIGH** | Already using via backend RAG. 2M token context.                                                                 |
| 2   | **Google AI Studio** (aistudio.google.com)           | Visual prompt playground, grounding, code exec              | Yes (via Gemini API) | No                      | Full (API) | **HIGH** | Grounding with Google Search, Maps grounding, code execution sandbox, URL context. March 2026 major UI overhaul. |
| 3   | **Vertex AI** (cloud.google.com)                     | Enterprise ML platform (Model Garden, training, deployment) | Yes                  | Official                | Full       | MED      | Agent Engine GA. Sessions + memory bank GA. Overkill for current scale but future-ready.                         |
| 4   | **Vertex AI Agent Builder**                          | Build, scale, govern AI agents in production                | Yes                  | Official                | Full       | MED      | ADK 2.0 Alpha with graph-based workflows. Tool governance. Cloud API Registry.                                   |
| 5   | **Agent Development Kit (ADK)**                      | Open-source multi-agent framework (Python, Java, TS)        | Yes (framework)      | Yes (McpToolset)        | Full       | **HIGH** | Model-agnostic. Native MCP integration. Could replace custom LangGraph orchestrator.                             |
| 6   | **Gemini CLI** (github.com/google-gemini/gemini-cli) | Terminal AI agent with Gemini                               | Yes (CLI)            | Yes (native MCP client) | Full       | **HIGH** | Already installed. FastMCP integration. Environment sanitization for MCP.                                        |
| 7   | **Gemini Code Assist**                               | AI coding assistant (VS Code, JetBrains)                    | Limited              | No                      | Partial    | LOW      | Free tier available. "Finish Changes" + "Outlines" features. Less relevant with Claude Code.                     |
| 8   | **Gemini Nano**                                      | On-device inference (Android, Chrome)                       | Yes (ML Kit GenAI)   | No                      | Partial    | LOW      | 32K tokens. Offline capable. Relevant only for mobile client apps.                                               |
| 9   | **Gemini Live API**                                  | Real-time streaming multimodal (audio/video/text)           | Yes (WebSocket)      | No                      | Full       | MED      | Low-latency voice+video. Could power real-time client consultations.                                             |

---

## TIER 2 -- AI AGENTS & SPECIALIZED AI PRODUCTS

| #   | Product                              | What It Does                                                | API                     | MCP                            | Automation | Priority | Notes                                                                                                 |
| --- | ------------------------------------ | ----------------------------------------------------------- | ----------------------- | ------------------------------ | ---------- | -------- | ----------------------------------------------------------------------------------------------------- |
| 10  | **Gemini Deep Research**             | Autonomous multi-step research agent                        | Yes (Gemini API)        | No                             | Full       | **HIGH** | Plans, searches, synthesizes reports with citations. Coming to NotebookLM and Search.                 |
| 11  | **Jules** (AI Coding Agent)          | Autonomous code debugging/optimization (GitHub integration) | Limited (AI Pro/Ultra)  | No                             | Partial    | LOW      | 73% task completion. Less relevant with Claude Code + Codex.                                          |
| 12  | **Project Mariner**                  | Browser automation agent (web tasks)                        | Limited (Ultra only)    | No                             | Partial    | MED      | 10 concurrent browser tasks. Travel booking, research, data entry. US only.                           |
| 13  | **NotebookLM** (notebook.google.com) | AI-powered research notebook with source grounding          | Yes (Enterprise API GA) | Community (notebooklm-mcp-cli) | Full       | **HIGH** | Already using for SEO Guardian. Enterprise API is GA for notebooks + sources. Podcast generation API. |
| 14  | **NotebookLM Enterprise**            | Org-managed NotebookLM with API                             | Yes (GA)                | Community                      | Full       | **HIGH** | Create/manage notebooks programmatically. Add sources via API.                                        |
| 15  | **LearnLM**                          | Education-optimized Gemini models                           | Yes (via Gemini API)    | No                             | Full       | LOW      | Fine-tuned for learning. Niche for Bali Zero unless training clients.                                 |
| 16  | **Dialogflow CX / CX Agent Studio**  | Conversational AI agents with flow design                   | Yes (v3, v3beta1)       | Official (Customer Experience) | Full       | MED      | Next-gen CX Agent Studio with Gemini. Could replace custom WhatsApp/Telegram adapters.                |
| 17  | **A2A Protocol** (Agent-to-Agent)    | Open protocol for inter-agent communication                 | Yes (v0.3)              | Complementary to MCP           | Full       | **HIGH** | Google-led, Linux Foundation. HTTP/SSE/JSON-RPC + gRPC. 100+ company support. ADK native integration. |
| 18  | **Whisk**                            | Image generation + animation (Veo 3)                        | Limited (consumer)      | No                             | No         | LOW      | Static images to 8s video. Creative tool.                                                             |
| 19  | **Flow**                             | AI filmmaking suite (text/ingredients/frames to video)      | Limited                 | No                             | Partial    | LOW      | Video creation/editing. Announced I/O 2025.                                                           |

---

## TIER 3 -- GENERATIVE MEDIA APIs

| #   | Product                         | What It Does                                        | API                              | MCP                 | Automation | Priority | Notes                                                          |
| --- | ------------------------------- | --------------------------------------------------- | -------------------------------- | ------------------- | ---------- | -------- | -------------------------------------------------------------- |
| 20  | **Imagen 4**                    | Photorealistic image generation (95% text accuracy) | Yes (Gemini API + Vertex AI)     | Official (Genmedia) | Full       | MED      | Available in AI Studio. Good for content/marketing automation. |
| 21  | **Veo 3 / 3.1**                 | Video generation (1080p, 60s, with audio/dialogue)  | Yes (Vertex AI, paid Gemini API) | Official (Genmedia) | Full       | MED      | Text-to-video with sound. Vertex AI Model Garden.              |
| 22  | **Lyria 2/3**                   | AI music generation (30s tracks with cover art)     | Limited (consumer)               | No                  | No         | LOW      | Music from text descriptions or photo/video.                   |
| 23  | **Google Cloud Text-to-Speech** | Speech synthesis (220+ voices, 40+ languages)       | Yes                              | No                  | Full       | MED      | Indonesian language support. Could power voice responses.      |
| 24  | **Google Cloud Speech-to-Text** | Speech recognition (125 languages)                  | Yes                              | No                  | Full       | MED      | Indonesian language support. Transcription for client calls.   |

---

## TIER 4 -- GOOGLE WORKSPACE (already partially integrated)

| #   | Product                          | What It Does                       | API                                   | MCP                          | Automation | Priority | Notes                                                                                                                 |
| --- | -------------------------------- | ---------------------------------- | ------------------------------------- | ---------------------------- | ---------- | -------- | --------------------------------------------------------------------------------------------------------------------- |
| 25  | **Gmail**                        | Email                              | Yes (Gmail API)                       | Official + Community         | Full       | **HIGH** | Already have MCP (claude.ai Gmail). Also in Google Workspace MCP.                                                     |
| 26  | **Google Drive**                 | File storage & management          | Yes (Drive API)                       | Official + Community         | Full       | **HIGH** | Already integrated via SA. MCP available. Gemini side panel for Q&A.                                                  |
| 27  | **Google Sheets**                | Spreadsheets                       | Yes (Sheets API)                      | Official + Community         | Full       | **HIGH** | Already integrated (sheets_service.py). Gemini builds entire spreadsheets from NL.                                    |
| 28  | **Google Calendar**              | Calendar & scheduling              | Yes (Calendar API)                    | Official + Community         | Full       | **HIGH** | Already have MCP (claude.ai Google Calendar). calendar.balizero.com.                                                  |
| 29  | **Google Docs**                  | Document editing                   | Yes (Docs API)                        | Official + Community         | Full       | MED      | Gemini writes docs from multiple sources. MCP available.                                                              |
| 30  | **Google Slides**                | Presentations                      | Yes (Slides API)                      | Official + Community         | Full       | LOW      | Gemini creates slides with auto-layout.                                                                               |
| 31  | **Google Chat** (Workspace)      | Team messaging                     | Yes (Chat API)                        | Official (in Workspace MCP)  | Full       | MED      | Granular OAuth (Jan 2026). Channel scaffold exists in backend.                                                        |
| 32  | **Google Meet**                  | Video conferencing                 | Yes (Meet API GA + Media API preview) | Community                    | Full       | MED      | Transcripts, recordings, real-time media access. Auto-artifacts.                                                      |
| 33  | **Google Forms**                 | Form creation & responses          | Yes (Forms API)                       | Community (in Workspace MCP) | Full       | MED      | Useful for client intake automation.                                                                                  |
| 34  | **Google Contacts** (People API) | Contact management                 | Yes (People API v1)                   | Community (in Workspace MCP) | Full       | MED      | CRM sync potential. Replaced old Contacts API.                                                                        |
| 35  | **Google Tasks**                 | Task management                    | Yes (Tasks API GA)                    | Community (in Workspace MCP) | Full       | MED      | Keep is migrating to Tasks. Simple task tracking.                                                                     |
| 36  | **Google Keep**                  | Notes                              | Limited (no public API)               | No                           | No         | LOW      | No official API. Being merged with Tasks.                                                                             |
| 37  | **Google Sites**                 | Website builder                    | Limited                               | No                           | Partial    | LOW      | Minimal API. Not relevant for Nuzantara.                                                                              |
| 38  | **Google Workspace CLI (gws)**   | Unified CLI for all Workspace APIs | Yes (CLI)                             | Yes (native MCP)             | Full       | **HIGH** | Released March 2026. JSON output + MCP support + auto-auth. Covers Drive, Gmail, Calendar, Sheets, Docs, Chat, Admin. |
| 39  | **Google Apps Script**           | Workspace automation (JavaScript)  | Yes (Apps Script API)                 | No                           | Full       | MED      | Browser-based IDE. Triggers, add-ons, web apps. Pre-integrated with 100+ Google services.                             |

---

## TIER 5 -- ANALYTICS, MARKETING & BUSINESS

| #   | Product                     | What It Does                  | API                        | MCP                                            | Automation | Priority | Notes                                                                                                   |
| --- | --------------------------- | ----------------------------- | -------------------------- | ---------------------------------------------- | ---------- | -------- | ------------------------------------------------------------------------------------------------------- |
| 40  | **Google Analytics (GA4)**  | Web analytics                 | Yes (GA4 Data API)         | Official (open-source) + **Already installed** | Full       | **HIGH** | Already have ga4-analytics MCP. Property 505466833.                                                     |
| 41  | **Google Search Console**   | SEO monitoring & indexing     | Yes (Search Console API)   | **Already installed** (19 tools)               | Full       | **HIGH** | Already have GSC MCP. SA auth. Site owner on balizero.com.                                              |
| 42  | **Google Ads**              | Advertising platform          | Yes (Ads API v23+)         | Community                                      | Full       | MED      | Monthly release cadence since Jan 2026. AI-powered audience building. Performance Max reporting.        |
| 43  | **Google Tag Manager**      | Tag management                | Yes (GTM API v2)           | Community (CLI tools)                          | Full       | MED      | Container, workspace, tag management. OAuth + SA auth.                                                  |
| 44  | **Google Business Profile** | Business listing management   | Yes (Business Profile API) | Community                                      | Full       | **HIGH** | Critical for Bali Zero local SEO. Location management, reviews, posts.                                  |
| 45  | **Google Trends**           | Search trend analysis         | Limited (Alpha API)        | No                                             | Partial    | MED      | Official API launched July 2025 but still alpha with restricted access. Third-party scrapers available. |
| 46  | **Looker Studio**           | BI dashboards & visualization | Yes (Looker Studio API)    | No (BigQuery MCP for data)                     | Full       | MED      | Asset management API. Best paired with BigQuery.                                                        |
| 47  | **BigQuery**                | Petabyte-scale data warehouse | Yes                        | Official                                       | Full       | MED      | GA4 export target. SQL analytics. MCP Toolbox for Databases.                                            |

---

## TIER 6 -- CLOUD INFRASTRUCTURE & COMPUTE

| #   | Product                            | What It Does                        | API | MCP                   | Automation | Priority | Notes                                                                   |
| --- | ---------------------------------- | ----------------------------------- | --- | --------------------- | ---------- | -------- | ----------------------------------------------------------------------- |
| 48  | **Google Cloud Run**               | Serverless containers               | Yes | Official              | Full       | MED      | 2nd gen recommended. Alternative to Fly.io for backend.                 |
| 49  | **Google Cloud Functions**         | Serverless functions                | Yes | Via Cloud Run MCP     | Full       | MED      | Event-driven. Good for webhooks, Pub/Sub handlers.                      |
| 50  | **Google Pub/Sub**                 | Real-time messaging/event streaming | Yes | Official              | Full       | MED      | Async messaging between services. Push to Cloud Run/Functions.          |
| 51  | **Google Compute Engine**          | VMs                                 | Yes | Official              | Full       | LOW      | IaaS. Not needed with current Fly.io setup.                             |
| 52  | **Google Kubernetes Engine (GKE)** | Managed Kubernetes                  | Yes | Official              | Full       | LOW      | Container orchestration. Overkill for current scale.                    |
| 53  | **Google Cloud Storage**           | Object storage                      | Yes | Open-source MCP       | Full       | LOW      | Alternative to Tigris/S3.                                               |
| 54  | **Google Cloud SQL**               | Managed PostgreSQL/MySQL/SQL Server | Yes | Official (3 variants) | Full       | MED      | Alternative to Fly.io Postgres. MySQL, PostgreSQL, SQL Server variants. |
| 55  | **AlloyDB**                        | PostgreSQL-compatible database      | Yes | Official              | Full       | LOW      | Enterprise-grade. Overkill for current scale.                           |
| 56  | **Firestore**                      | NoSQL document database             | Yes | Official              | Full       | LOW      | Already using PostgreSQL + Qdrant.                                      |
| 57  | **Spanner**                        | Global distributed database         | Yes | Official              | Full       | LOW      | Enterprise-grade globally distributed. Not needed.                      |
| 58  | **Bigtable**                       | NoSQL wide-column store             | Yes | Official              | Full       | LOW      | Analytics/IoT workloads. Not needed.                                    |
| 59  | **Cloud Logging**                  | Centralized log management          | Yes | Official              | Full       | MED      | Could replace current logging setup.                                    |
| 60  | **Cloud Monitoring**               | Observability                       | Yes | Official              | Full       | MED      | Alternative to current health check scripts.                            |

---

## TIER 7 -- AI/ML SPECIALIZED APIs

| #   | Product                             | What It Does                               | API                         | MCP | Automation | Priority | Notes                                                                                                                         |
| --- | ----------------------------------- | ------------------------------------------ | --------------------------- | --- | ---------- | -------- | ----------------------------------------------------------------------------------------------------------------------------- |
| 61  | **Google Cloud Document AI**        | Document parsing with OCR (200+ languages) | Yes                         | No  | Full       | **HIGH** | Indonesian document processing. 25 years of OCR research. Custom processors. Already have tesseract MCP but this is superior. |
| 62  | **Google Cloud Vision AI**          | Image labeling, OCR, face detection        | Yes (REST + RPC)            | No  | Full       | MED      | Label detection, landmark detection, OCR. Complementary to Document AI.                                                       |
| 63  | **Google Cloud Translation**        | Translation (200+ languages)               | Yes (v2 Basic, v3 Advanced) | No  | Full       | **HIGH** | Indonesian-English critical for Bali Zero. NMT backend. Client libraries in Python, Go, Node, Java.                           |
| 64  | **Google Cloud Natural Language**   | Text analysis (entity, sentiment, syntax)  | Yes                         | No  | Full       | MED      | Entity extraction, sentiment analysis. Could enhance RAG pipeline.                                                            |
| 65  | **Google Cloud Translate (Gemini)** | Gemini-powered translation in AI Studio    | Yes (via Gemini API)        | No  | Full       | **HIGH** | Context-aware translation superior to standalone API.                                                                         |

---

## TIER 8 -- DEVELOPMENT TOOLS & IDEs

| #   | Product                            | What It Does                                   | API             | MCP                               | Automation | Priority | Notes                                                                                                                             |
| --- | ---------------------------------- | ---------------------------------------------- | --------------- | --------------------------------- | ---------- | -------- | --------------------------------------------------------------------------------------------------------------------------------- |
| 66  | **Antigravity IDE**                | Agent-first IDE (Gemini 3.1 Pro + multi-model) | No (local app)  | Yes (MCP config support)          | Partial    | **HIGH** | Already installed + configured. 76.2% SWE-bench. Multi-agent Manager Surface. Free.                                               |
| 67  | **Firebase Studio** (formerly IDX) | Cloud IDE with Gemini                          | Yes (web-based) | No                                | Partial    | LOW      | Being sunset March 2027. Avoid new investment.                                                                                    |
| 68  | **Firebase Genkit**                | Open-source AI app framework (JS, Go, Python)  | Yes (framework) | No                                | Full       | MED      | One SDK for multiple LLMs. Built-in RAG, tool use, agents. Hot reloading. OpenTelemetry.                                          |
| 69  | **Google Colab**                   | Jupyter notebooks with GPU                     | Yes             | Official (MCP Server, March 2026) | Full       | **HIGH** | New Colab MCP server allows any AI agent to use Colab as remote runtime. GPU access. execute_code, create notebooks, pip install. |

---

## TIER 9 -- PLATFORMS & ECOSYSTEMS

| #   | Product                                       | What It Does                               | API                    | MCP                                     | Automation | Priority | Notes                                                                                                                  |
| --- | --------------------------------------------- | ------------------------------------------ | ---------------------- | --------------------------------------- | ---------- | -------- | ---------------------------------------------------------------------------------------------------------------------- |
| 70  | **Google Maps Platform**                      | Geocoding, Places, Routes, Maps JS         | Yes (full suite)       | Official (Grounding Lite + Code Assist) | Full       | **HIGH** | Already using (Prime Intelligence, Maps API key configured). Routes API is next-gen. Grounding with Maps in AI Studio. |
| 71  | **YouTube Data API v3**                       | Video management, search, analytics        | Yes                    | Community                               | Full       | MED      | 10K daily quota. Upload, metadata, comments. MCP server available.                                                     |
| 72  | **Firebase** (Auth, FCM, Hosting)             | App infrastructure (auth, push, hosting)   | Yes                    | Open-source MCP (Gemini CLI ext)        | Full       | MED      | FCM for push notifications. Auth for SSO. Free hosting tier.                                                           |
| 73  | **Chrome Extensions API / DevTools Protocol** | Browser automation & extension development | Yes (CDP)              | Official (Chrome DevTools MCP)          | Full       | **HIGH** | Already using claude-in-chrome. CDP powers Puppeteer/Playwright. Chrome DevTools MCP for agent debugging.              |
| 74  | **Google Earth Engine**                       | Geospatial analysis at planetary scale     | Yes (Earth Engine API) | No                                      | Full       | LOW      | Environmental/land use analysis. Niche for property intelligence.                                                      |

---

## TIER 10 -- SECURITY & THREAT INTELLIGENCE

| #   | Product                                                | What It Does                                      | API           | MCP                     | Automation | Priority | Notes                                            |
| --- | ------------------------------------------------------ | ------------------------------------------------- | ------------- | ----------------------- | ---------- | -------- | ------------------------------------------------ |
| 75  | **Google Threat Intelligence (Mandiant + VirusTotal)** | Threat intelligence, IOC lookup, malware analysis | Yes (GTI API) | Official (Security MCP) | Full       | LOW      | Enterprise security. Dev kit available (Python). |
| 76  | **Google Security Operations (Chronicle)**             | SIEM, security analytics                          | Yes           | Official                | Full       | LOW      | Threat detection. Enterprise focus.              |
| 77  | **Managed Service for Apache Kafka**                   | Message streaming                                 | Yes           | Official                | Full       | LOW      | Event streaming at scale.                        |

---

## TIER 11 -- PROTOCOLS & STANDARDS (Google-led)

| #   | Product                           | What It Does                                     | API           | MCP           | Automation | Priority | Notes                                                              |
| --- | --------------------------------- | ------------------------------------------------ | ------------- | ------------- | ---------- | -------- | ------------------------------------------------------------------ |
| 78  | **A2A Protocol** (Agent-to-Agent) | Open inter-agent communication standard          | Yes (v0.3)    | Complementary | Full       | **HIGH** | HTTP/SSE/JSON-RPC + gRPC. ADK native. Linux Foundation governance. |
| 79  | **MCP Toolbox for Databases**     | Unified database tool interface                  | Yes           | Yes (toolbox) | Full       | MED      | Works with BigQuery, Cloud SQL, AlloyDB, Spanner, Firestore.       |
| 80  | **Developer Knowledge API**       | Machine-readable access to Google developer docs | Yes (preview) | Official      | Full       | MED      | Canonical gateway to all Google documentation.                     |
| 81  | **gcloud CLI MCP**                | Cloud Platform CLI as MCP server                 | Yes           | Open-source   | Full       | MED      | Full GCP management via MCP.                                       |

---

## SUMMARY: What Nuzantara Already Has vs. Should Add

### Already Integrated (8)

| Product               | Integration Point                             |
| --------------------- | --------------------------------------------- |
| Gemini API            | backend-rag (Gemini 3 Flash + RAG)            |
| GA4 Analytics         | ga4-analytics MCP (property 505466833)        |
| Google Search Console | google-search-console MCP (19 tools, SA auth) |
| Google Drive          | SA integration (sheets_service.py, Drive API) |
| Google Sheets         | Backend router + service                      |
| Google Calendar       | claude.ai Google Calendar MCP                 |
| Gmail                 | claude.ai Gmail MCP                           |
| Google Maps           | Prime Intelligence (Maps JS API)              |
| Gemini CLI            | ai-dispatch.sh (explore, search)              |
| Antigravity IDE       | Configured with MCP + skills                  |
| Chrome DevTools       | claude-in-chrome MCP                          |
| OCR                   | ocr-tesseract MCP                             |
| NotebookLM            | SEO Guardian notebook (manual)                |

### HIGH Priority Additions (12)

| Product                         | Why                                                            | Effort            |
| ------------------------------- | -------------------------------------------------------------- | ----------------- |
| **Google Workspace CLI (gws)**  | Unified CLI for ALL workspace + native MCP + auto-auth         | Low (npm install) |
| **NotebookLM Enterprise API**   | Programmatic notebook creation, source management, podcast gen | Medium            |
| **Google Business Profile API** | Local SEO critical for Bali Zero (reviews, posts, listings)    | Medium            |
| **Agent Development Kit (ADK)** | Replace custom LangGraph with Google's multi-agent framework   | High              |
| **A2A Protocol**                | Inter-agent communication standard for federation              | Medium            |
| **Google Cloud Document AI**    | Superior to tesseract for Indonesian document processing       | Medium            |
| **Google Cloud Translation**    | ID-EN translation pipeline for content + client comms          | Low               |
| **Gemini Deep Research**        | Automated competitive intelligence + regulatory research       | Low (API call)    |
| **Google Colab MCP**            | GPU runtime for ML tasks, accessible from any agent            | Low               |
| **Google AI Studio grounding**  | Search + Maps grounding for factual responses                  | Low (API param)   |
| **Imagen 4 API**                | Content marketing image generation                             | Low (API call)    |
| **Veo 3 API**                   | Video content generation for marketing                         | Medium            |

### MED Priority Additions (15)

| Product                             | Why                                                    |
| ----------------------------------- | ------------------------------------------------------ |
| Google Ads API                      | Paid marketing automation when ready to scale          |
| Google Tag Manager API              | Marketing tag management                               |
| Google Docs API (via Workspace MCP) | Document generation for client deliverables            |
| Google Chat API                     | Complete channel coverage (scaffold exists)            |
| Google Meet API                     | Client meeting transcripts + recordings                |
| BigQuery                            | Analytics warehouse for GA4 export                     |
| Looker Studio                       | BI dashboards for client reporting                     |
| Cloud Run                           | Alternative serverless compute to Fly.io               |
| Firebase Genkit                     | Multi-LLM SDK for backend services                     |
| TTS/STT APIs                        | Voice interface for KBLI/client support                |
| Cloud Natural Language              | Entity/sentiment extraction for RAG                    |
| Google Forms                        | Client intake automation                               |
| YouTube Data API                    | Video content management                               |
| Dialogflow CX                       | Enterprise conversational AI (replace custom adapters) |
| Cloud Logging + Monitoring          | Observability upgrade                                  |

---

## OFFICIAL GOOGLE MCP SERVERS (Complete List, March 2026)

### Remote (Google-Managed)

1. AlloyDB for PostgreSQL
2. BigQuery
3. Bigtable
4. Cloud Resource Manager
5. Cloud SQL for MySQL
6. Cloud SQL for PostgreSQL
7. Cloud SQL for SQL Server
8. Compute Engine (GCE)
9. Developer Knowledge API
10. Firestore
11. Google Maps (Grounding Lite)
12. Google Security Operations
13. Kubernetes Engine (GKE)
14. Spanner
15. Customer Experience Agent Studio
16. Managed Service for Apache Kafka
17. Pub/Sub
18. Vertex AI
19. Vertex AI Search
20. Cloud Logging
21. Cloud Monitoring

### Open-Source (Google-Published)

1. Google Workspace (Docs, Sheets, Slides, Calendar, Gmail) -- Gemini CLI extension
2. Firebase -- Gemini CLI extension
3. Cloud Run -- Gemini CLI extension
4. Go language support
5. Google Analytics
6. MCP Toolbox for Databases
7. Google Cloud Storage
8. Genmedia (Imagen + Veo)
9. GKE (open-source variant)
10. Google Cloud Security
11. gcloud CLI
12. Google Cloud Observability
13. Flutter/Dart
14. Google Maps Platform Code Assist
15. Chrome DevTools
16. Google Colab

---

## Google AI Product Timeline (Key 2025-2026 Launches)

| Date     | Product/Feature                                               |
| -------- | ------------------------------------------------------------- |
| Apr 2025 | A2A Protocol announced (Google + 100 partners)                |
| May 2025 | Google I/O: Veo 3, Imagen 4, Gemini Ultra, Flow, LearnLM      |
| Jun 2025 | A2A joins Linux Foundation                                    |
| Jul 2025 | Google Trends API (alpha)                                     |
| Sep 2025 | NotebookLM Enterprise API (pre-GA)                            |
| Nov 2025 | Antigravity IDE announced (with Gemini 3)                     |
| Jan 2026 | Google Ads API v23 (monthly cadence begins)                   |
| Jan 2026 | Google Chat granular OAuth consent                            |
| Feb 2026 | A2A Protocol v0.3 (gRPC support)                              |
| Mar 2026 | Google Workspace CLI (gws) released                           |
| Mar 2026 | Google Colab MCP Server released                              |
| Mar 2026 | Google AI Studio major UI overhaul + Playground               |
| Mar 2026 | Official Google MCP support announcement (21+ remote servers) |
| Mar 2026 | ADK Python 2.0 Alpha (graph-based workflows)                  |
| Mar 2026 | Gemini Deep Research API available                            |
| Mar 2026 | Veo 3.1 on paid Gemini API                                    |
| Mar 2026 | Imagen 4 GA in Gemini API + AI Studio                         |

---

## Sources

- [Google MCP GitHub Repo](https://github.com/google/mcp)
- [Google Cloud MCP Supported Products](https://docs.cloud.google.com/mcp/supported-products)
- [Announcing Official MCP Support](https://cloud.google.com/blog/products/ai-machine-learning/announcing-official-mcp-support-for-google-services)
- [Google AI Studio Update March 2026](https://www.androidsage.com/2026/03/19/google-ai-studios-biggest-update-yet/)
- [ADK Documentation](https://google.github.io/adk-docs/)
- [A2A Protocol](https://a2a-protocol.org/latest/)
- [Google Workspace CLI](https://github.com/googleworkspace/cli)
- [Colab MCP Server Announcement](https://developers.googleblog.com/announcing-the-colab-mcp-server-connect-any-ai-agent-to-google-colab/)
- [NotebookLM Enterprise API](https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks)
- [Gemini CLI MCP Docs](https://geminicli.com/docs/tools/mcp-server/)
- [Google AI Products List 2026](https://hiringhello.com/blog/complete-list-of-google-ai-products-experiments-2026-summaries-launch-info)
- [Google AI Ecosystem Overview](https://masterconcept.ai/blog/the-google-ai-ecosystem-from-2025-foundations-to-the-2026-ai-frontier/)
- [Gemini Deep Research API](https://ai.google.dev/gemini-api/docs/deep-research)
- [Firebase Genkit](https://genkit.dev/)
- [Antigravity IDE](https://developers.googleblog.com/build-with-google-antigravity-our-new-agentic-development-platform/)
- [Google Workspace MCP Community](https://github.com/taylorwilsdon/google_workspace_mcp)
- [NotebookLM MCP CLI](https://github.com/jacob-bd/notebooklm-mcp-cli)
- [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Google Maps Platform](https://developers.google.com/maps/documentation)
- [YouTube Data API v3](https://developers.google.com/youtube/v3)
