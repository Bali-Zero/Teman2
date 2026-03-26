# NotebookLM Capability Matrix — What We Can Actually Do

**Date:** 2026-03-24
**MCP Server:** `notebooklm-mcp-cli` v0.5.3 (update available: v0.5.5)
**Account:** antonellosiano@gmail.com
**Notebooks:** 57 total (50 owned, 7 shared)

---

## Executive Summary

NotebookLM via MCP is a **production-grade knowledge oracle** with 9 studio artifact types, deep research, cross-notebook queries, conversation memory, notes, tags, pipelines, batch operations, and full sharing. It is NOT a toy -- the answers are citation-rich, deeply grounded, and domain-aware. For Bali Zero, it is the only system that can answer complex Indonesian regulatory questions with inline source citations from actual government documents (PP 28/2025, KBLI annexes, BPJPH regulations).

**Key finding:** Single notebook queries return expert-level answers with 20-30+ inline citations in ~15-25 seconds. Cross-notebook queries aggregate across 3-4 notebooks in ~45-60 seconds. Quality is consistently high -- on par with a senior consultant who has read all the source documents.

---

## 1. NOTEBOOK MANAGEMENT

### notebook_list

- **What:** Lists all notebooks with IDs, titles, source counts, ownership, sharing status, timestamps
- **Limits:** max_results param, default 100
- **Real data:** 57 notebooks returned instantly. Shows owned vs shared_with_me distinction.
- **BZ use:** Inventory of our knowledge base. We have rich coverage: Indonesian regulation (KBLI, visas, LKPM, tax), Bali-specific (zoning, moratorium, villas), our codebase (Nuzantara infra), and client case studies.

### notebook_get

- **What:** Returns notebook details + full list of sources with IDs and titles
- **Real data:** Our restaurant notebook has 22 sources (web URLs, PDFs, images, generated text). Infrastructure notebook has 16 text sources.
- **BZ use:** Map notebook content programmatically. Critical for building routing logic.

### notebook_describe

- **What:** AI-generated summary + suggested topics (markdown)
- **Real data:** Returns a rich 1-paragraph summary identifying key themes, technologies, and domain concepts. Suggested_topics often empty.
- **BZ use:** Auto-generate notebook catalog descriptions. Could feed into our knowledge graph.

### notebook_create / notebook_delete / notebook_rename

- **What:** CRUD for notebooks
- **BZ use:** Programmatic creation of domain-specific notebooks (per client, per regulation, per project).

---

## 2. QUERYING (The Core Power)

### notebook_query ⭐ PRIMARY CAPABILITY

- **What:** Ask a question against one notebook's sources. Returns answer + conversation_id + citations + full source references
- **Limits:** Timeout default 120s (configurable via env). Supports conversation_id for follow-ups.
- **REAL TEST 1 — Restaurant regulations (22 sources):**
  - Query: "What are the requirements for opening a restaurant in Bali as a foreigner?"
  - Response: ~2,500 words, 32 inline citations, 10 sources used, structured with headers, tables, step-by-step procedures
  - Covered: KBLI 56101, 100% foreign ownership, IDR 2.5B paid-up capital, 12-month lock-up, IDR 10B total investment, OSS RBA licensing by seating capacity, RDTR zoning, PBG building permits, halal certification, waste regulations
  - **Quality: EXCEPTIONAL.** More complete than any single web search or consultant briefing.
- **REAL TEST 2 — KBLI technical (18 sources, government PDFs):**
  - Query: "KBLI codes for restaurant businesses and risk classifications"
  - Response: Detailed breakdown of 56101, 56102, 56103, 56104, 56109, 56702 with risk levels, licensing requirements, and specific document requirements per code
  - Pulled directly from PP Nomor 28 Tahun 2025 annexes (scanned government PDFs!)
  - **Quality: EXCELLENT.** Reads OCR'd government documents accurately.
- **REAL TEST 3 — Codebase architecture (16 source files):**
  - Query: "Current architecture of the agentic RAG orchestrator"
  - Response: Detailed breakdown of 7 manager classes, ReAct pattern, LLM gateway fallback cascade, evidence scoring thresholds, verification service
  - Referenced specific file paths, class names, dataclass fields (max_steps=3), and configuration values
  - **Quality: EXCELLENT for code comprehension.** Better than searching the codebase manually.
- **FOLLOW-UP TEST:** Using conversation_id, asked "What about halal certification deadline?" -- maintained full context, gave nuanced answer distinguishing PMA deadline (Oct 2024, already passed) from UMK/import deadline (Oct 2026)
- **BZ use:** This is the killer feature. Each notebook becomes a specialized expert. Route client questions to the right notebook and get consultant-grade answers with citations.

### chat_configure ⭐ GAME CHANGER

- **What:** Set per-notebook chat personality, goal (default/learning_guide/custom), custom prompt (max 10,000 chars), response length (shorter/default/longer)
- **REAL TEST:** Configured infrastructure notebook with "You are a senior platform engineer... include file paths, class names, architectural patterns"
  - Result: Dramatically improved technical depth. Named specific files (a2a_service.py, launcher.py), methods (dispatch_fallback), constants (HEARTBEAT_INTERVAL=30s), and architecture patterns.
- **BZ use:** Configure each notebook for its audience:
  - Client-facing notebooks: "You are Zantara, a friendly business advisor. Answer in the client's language."
  - Internal tech notebooks: "You are a senior engineer. Include file paths and code references."
  - Regulatory notebooks: "Always cite the specific regulation number (PP, Permen, UU) and article."

### cross_notebook_query ⭐ FEDERATION

- **What:** Query multiple notebooks simultaneously, get per-notebook answers with citations
- **Limits:** Select by name (comma-separated), by tags, or all=True. Rate limits apply for all.
- **REAL TEST:** Queried 4 notebooks about restaurant requirements
  - 3/4 succeeded (one shared notebook failed due to name parsing -- commas in titles cause splitting issues)
  - Each notebook contributed unique perspective: Restaurant Guide gave complete setup steps, KBLI notebook gave technical risk classifications, LKPM notebook correctly said "this isn't in my sources" (honest abstention!)
  - **Quality: VERY GOOD.** The aggregation shows which notebooks know what.
- **GOTCHA:** Notebook names with commas break the comma-separated parser. Use notebook IDs instead for reliable routing.
- **BZ use:** Build a "consultation router" -- when a client asks a complex question, query 3-5 relevant notebooks in parallel, then synthesize. This is our competitive advantage.

---

## 3. SOURCES

### source_add (Unified)

- **Types supported:** `url` (web pages, YouTube), `text` (pasted content), `drive` (Google Drive docs/slides/sheets/pdf), `file` (local file upload: PDF, text, audio)
- **Bulk:** `urls` param accepts a list for batch URL ingestion
- **Wait mode:** `wait=True` blocks until source is fully processed (up to 120s)
- **BZ use:** Automate knowledge ingestion. When our intel scraper publishes a new article, auto-add it to the relevant notebook.

### source_get_content

- **What:** Get raw indexed text from any source (no AI processing). Fast.
- **REAL TEST:** Retrieved Federation v3 Phase 2 source -- 4,172 chars, full text, instant response.
- **BZ use:** Export notebook contents for other systems. Feed into our RAG pipeline or knowledge graph.

### source_describe

- **What:** AI summary + keyword chips for a single source
- **REAL TEST:** Got rich summary of restaurant investment report with 5 keyword tags (Penanaman Modal Asing, OSS RBA, RDTR, Halal, AI F&B)
- **BZ use:** Auto-classify and tag sources. Feed keywords into our tagging system.

### source_list_drive / source_sync_drive

- **What:** List sources with freshness status, sync stale Drive documents
- **REAL TEST:** Our infra notebook has 0 Drive sources (all text uploads). Would be useful for notebooks linked to Google Drive folders.
- **BZ use:** Keep regulatory notebooks fresh when government docs on Drive are updated.

### source_rename / source_delete

- **What:** Standard CRUD. Delete requires confirm=True (irreversible).

---

## 4. STUDIO ARTIFACTS (9 Types) ⭐ CONTENT MACHINE

### Artifact Types Available:

| Type            | Output              | Formats/Options                                                                                                                        | BZ Use Case                                     |
| --------------- | ------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| **audio**       | Podcast MP3/MP4     | deep_dive, brief, critique, debate / short, default, long                                                                              | Client-facing podcast from regulatory briefings |
| **video**       | Video MP4           | explainer, brief / classic, whiteboard, kawaii, anime, watercolor, retro_print, heritage, paper_craft                                  | Social media content from intel articles        |
| **infographic** | PNG                 | landscape, portrait, square / sketch_note, professional, bento_grid, editorial, instructional, bricks, clay, anime, kawaii, scientific | One-pagers for client reports                   |
| **slide_deck**  | PDF or PPTX         | detailed_deck, presenter_slides / short, default                                                                                       | Pitch decks from notebook content               |
| **report**      | Markdown/Google Doc | Briefing Doc, Study Guide, Blog Post, Create Your Own                                                                                  | Auto-generated client briefing docs             |
| **flashcards**  | JSON/MD/HTML        | easy, medium, hard                                                                                                                     | Team training on Indonesian regulations         |
| **quiz**        | JSON/MD/HTML        | N questions, easy/medium/hard                                                                                                          | Client compliance assessments                   |
| **data_table**  | CSV/Google Sheets   | requires description                                                                                                                   | Extract structured data from regulatory docs    |
| **mind_map**    | JSON                | custom title                                                                                                                           | Visualize complex regulatory landscapes         |

### studio_create

- **Requires:** confirm=True (safety gate)
- **Language:** BCP-47 codes (en, id, it, etc.)
- **Focus prompt:** Optional text to steer content generation
- **After creation:** Poll studio_status for completion

### studio_revise

- **What:** Revise individual slides in an existing slide deck. Creates NEW artifact (non-destructive).
- **BZ use:** Iterative refinement of client presentations.

### download_artifact

- **What:** Download to local file. Supports all 9 types.
- **Formats:** Audio (MP3/MP4), Video (MP4), Slides (PDF/PPTX), Infographic (PNG), Report (MD), Data Table (CSV), Quiz/Flashcards (JSON/MD/HTML), Mind Map (JSON)

### export_artifact

- **What:** Export to Google Docs (reports) or Google Sheets (data tables)
- **BZ use:** Auto-export briefing docs to client Drive folders.

### Existing Artifacts Found:

- Restaurant notebook: 1 infographic + 2 slide decks (completed)
- Infrastructure notebook: 1 mind map (completed)

---

## 5. DEEP RESEARCH ⭐ WEB INTELLIGENCE

### research_start

- **What:** Search web or Google Drive for NEW sources to add to a notebook
- **Modes:**
  - `fast`: ~30 seconds, ~10 sources found
  - `deep`: ~5 minutes, ~40 sources found (web only)
- **Source:** `web` (Google search) or `drive` (Google Drive search)
- **Can create new notebook** if notebook_id not provided

### research_status

- **What:** Poll research progress. Supports compact mode (token-efficient).
- **Params:** poll_interval (default 30s), max_wait (default 300s)

### research_import

- **What:** Import discovered sources into notebook. Can select specific indices.
- **Workflow:** research_start -> poll research_status -> research_import

### BZ Use Cases:

1. **Regulatory monitoring:** Weekly deep research on "KBLI 2025 changes" / "Indonesia visa regulation updates" / "Bali zoning regulation 2026"
2. **Competitive intel:** Research competitors and import findings into intel notebooks
3. **Client prep:** Before a consultation, fast-research the client's specific industry to populate a temporary notebook

---

## 6. NOTES (In-Notebook Knowledge)

### note (create/list/update/delete)

- **What:** Create and manage notes within notebooks. Notes are like bookmarks or annotations.
- **REAL TEST:** Found 1 note in infrastructure notebook -- "Sessione 2026-03-23 CRM Refactor" with detailed session notes including backend/frontend changes.
- **BZ use:**
  - Store session summaries inside notebooks as context for future queries
  - Pin key findings or decisions
  - Create "instruction notes" that influence how queries are answered (notes ARE sources)

---

## 7. TAGS (Smart Routing)

### tag (add/remove/list/select)

- **What:** Tag notebooks for smart selection. Select finds notebooks relevant to a query via tag matching.
- **Current state:** 0 tags configured (unused!)
- **BZ use — CRITICAL TO IMPLEMENT:**
  ```
  "visa,immigration,KITAS,KITAP" -> Visa notebooks
  "kbli,licensing,oss,business-setup" -> Business setup notebooks
  "tax,npwp,pph,ppn,coretax" -> Tax notebooks
  "property,zoning,rdtr,pbg" -> Property notebooks
  "tech,backend,frontend,infrastructure" -> Codebase notebooks
  "intel,competitor,market" -> Intelligence notebooks
  ```
  Then use `tag select "how to open a restaurant"` to auto-route to relevant notebooks.

---

## 8. BATCH OPERATIONS

### batch (query/add_source/create/delete/studio)

- **What:** Apply operations across multiple notebooks at once
- **Actions:**
  - `query`: Same question to multiple notebooks (like cross_notebook_query but different interface)
  - `add_source`: Add same URL to multiple notebooks
  - `create`: Create multiple notebooks at once
  - `delete`: Delete multiple notebooks (confirm required)
  - `studio`: Generate same artifact type across multiple notebooks
- **Selection:** By names, tags, or all=True
- **BZ use:**
  - When a new regulation is published, add it to ALL relevant notebooks in one call
  - Generate audio briefings for ALL regulatory notebooks in batch
  - Query all notebooks tagged "visa" about a specific change

---

## 9. PIPELINES (Automation)

### pipeline (list/run)

- **Built-in pipelines (3):**
  1. `ingest-and-podcast`: Add URL source -> query for summary -> generate audio podcast (3 steps)
  2. `research-and-report`: Add URL source -> generate briefing doc report (2 steps)
  3. `multi-format`: Generate audio + report + flashcards from a notebook (3 steps)
- **Custom pipelines:** User-defined (not yet configured)
- **BZ use:**
  - `ingest-and-podcast` on every new intel article -> auto-generate podcast episode
  - `research-and-report` on competitor URLs -> auto-generate competitive briefings
  - `multi-format` on regulatory notebooks -> audio + report + flashcards for team training

---

## 10. SHARING & COLLABORATION

### notebook_share_invite / notebook_share_batch

- **What:** Invite collaborators by email (viewer or editor role). Batch supports multiple recipients.
- **REAL TEST:** "Bali's Villa Apocalypse" notebook is publicly shared.

### notebook_share_public

- **What:** Enable/disable public link access
- **REAL TEST:** Confirmed public link active with URL

### notebook_share_status

- **What:** Get sharing settings, collaborators list, access level
- **BZ use:** Share regulatory briefing notebooks with clients. Make intel reports public for marketing.

---

## 11. GOTCHAS, LIMITS & WORKAROUNDS

### Known Issues (from real testing):

1. **Cross-notebook name parsing:** Comma-separated names break on notebook titles containing commas. **WORKAROUND:** Always use notebook IDs, not names.
2. **Shared notebook queries:** Querying some shared_with_me notebooks returns "API error (code 5): unknown". May be permission-related.
3. **Auth fragility:** Cookie-based auth can expire (3-15s latency on re-auth). Federation v3 already has fallback for this.
4. **No tag configuration:** Currently 0 tags -- massive missed opportunity for smart routing.

### Limits Discovered:

- Max sources per notebook: ~50 (observed up to 70 on shared notebooks)
- Source types: URL, text (pasted), Google Drive (doc/slides/sheets/pdf), local file (PDF, text, audio)
- Custom prompt max: 10,000 characters
- Query timeout: 120s default (configurable)
- Research deep mode: ~5 minutes, ~40 sources
- Research fast mode: ~30 seconds, ~10 sources

### Non-Obvious Tricks:

1. **Notes ARE queryable sources.** Creating a note with key facts/instructions effectively "injects" knowledge into the notebook's context. Use this to add domain rules that influence all future answers.
2. **chat_configure transforms quality.** A well-written custom prompt (10,000 chars!) dramatically improves answer relevance and format. This is the equivalent of a system prompt for each notebook.
3. **conversation_id enables multi-turn.** Follow-up questions maintain full context, enabling drilling-down into complex topics across multiple queries.
4. **source_get_content is a knowledge exporter.** You can programmatically extract all indexed content from any notebook and feed it into other systems (our RAG pipeline, knowledge graph, etc.).
5. **Batch + tags = smart broadcast.** Tag notebooks by domain, then use batch operations to apply changes across domains.
6. **research_start can create notebooks.** No need to create first -- just provide a title and it creates + populates in one shot.
7. **Studio slides support PPTX export.** Not just PDF -- actual editable PowerPoint files. Combined with studio_revise for per-slide editing.
8. **Data table + export_artifact = structured extraction to Google Sheets.** Extract tables from regulatory PDFs directly into spreadsheets.

---

## 12. STRATEGIC RECOMMENDATIONS FOR BALI ZERO

### Immediate Actions (This Week):

1. **Tag all 57 notebooks** by domain (visa, kbli, tax, property, tech, intel, client). This unlocks smart routing.
2. **Configure chat_configure** on the 10 most-used notebooks with domain-appropriate custom prompts.
3. **Update notebooklm-mcp to v0.5.5** (`uv tool upgrade notebooklm-mcp-cli`).

### Short Term (This Month):

4. **Build a query router** in the backend that:
   - Classifies incoming questions by domain (using existing IntentClassifier)
   - Selects relevant notebooks via `tag select`
   - Queries 2-3 notebooks in parallel via `cross_notebook_query`
   - Synthesizes answers with citations from multiple notebooks
5. **Auto-ingest intel articles** into domain notebooks via `source_add` when the scraper publishes
6. **Generate weekly audio briefings** for the team via `studio_create(artifact_type="audio", audio_format="brief")`

### Medium Term (Next Quarter):

7. **Client-specific notebooks:** Create a notebook per major client, populate with their documents, configure with client-aware prompt. This becomes their personal AI advisor.
8. **Regulatory monitoring pipeline:** Weekly `research_start(mode="deep")` on key topics, auto-import relevant sources, generate delta reports.
9. **Training content factory:** Use `multi-format` pipeline to auto-generate flashcards + quizzes for team onboarding on Indonesian regulations.
10. **Public knowledge sharing:** Share regulatory briefing notebooks publicly -> content marketing + SEO.

### Architecture Integration:

```
Client Question
     |
     v
Intent Classifier (existing)
     |
     v
Tag Select (NotebookLM tags)
     |
     v
[Notebook 1] [Notebook 2] [Notebook 3]  (parallel queries)
     |            |            |
     v            v            v
Citation-Rich Answers (per notebook)
     |
     v
Synthesizer (Claude/Gemini)
     |
     v
Final Answer with Multi-Source Citations
     |
     v
Zantara Response (channel-appropriate format)
```

---

## Appendix: Notebook Inventory by Domain

### Indonesian Regulations & Compliance (16 notebooks)

- Indonesia Restaurant Investment and Regulatory Guide 2026 (22 sources)
- Indonesian Foreign Investment, Real Estate, and Taxation Compliance Guide (21 sources)
- Procedure Avanzate e Casi Speciali Visti Indonesia 2025 (18 sources)
- Bali Governor Instruction: Moratorium on Chain Store Permits (21 sources)
- Moratoria sulle Licenze Commerciali per i Negozi Moderni a Bali (28 sources)
- Moratoria sulle Licenze per i Negozi Moderni a Bali (16 sources)
- Guida Completa LKPM 2025 (2 notebooks, 6 sources each)
- KBLI classifications (4 notebooks)
- Various regulatory notebooks (tax, BPJS, criminal law, labor reform, forestry)

### Bali-Specific Intelligence (6 notebooks)

- Bali's Villa Apocalypse: The 2026 Regulatory Intelligence Report (shared, public)
- Bali's Era of Zero Tolerance
- Due Diligence: Progetto Ristorante Cemagi Bali 2026
- Corporate Compliance and Zoning Defense Strategy
- Protocollo di Compliance Strategica Casa Blanca Bali
- Strategie di Licenza per Gelaterie a Bali 2026

### Nuzantara Platform (2 notebooks)

- Infrastruttura e Deployment di Nuzantara: CI/CD e Containerization (16 sources) ⭐
- BZ - Strategia & Core 2026 (6 sources)

### Client Cases (3 notebooks)

- Indonesian Tax Compliance Strategy for Margherita Fabiani
- Cetak Biru Operasional Zantara CRM Asya
- Nuzantara Prime Menjangan Development Framework

### General Knowledge (shared, 4 notebooks)

- The World Ahead 2025/2026 (70 sources each)
- Shakespeare Complete Plays (45 sources)
- Genome Science (36 sources)

### Empty/Unused (5 notebooks)

- 4 untitled empty notebooks + 1 fishery (0 sources)
- **Recommendation:** Delete these to keep inventory clean.
