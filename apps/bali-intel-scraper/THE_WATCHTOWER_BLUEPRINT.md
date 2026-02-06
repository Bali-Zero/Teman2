# The Watchtower: Corporate & Legal Intelligence Blueprint (2026)

> **Vision:** Transform `bali-intel-scraper` from a reactive news aggregator into "The Watchtower" — a proactive, entity-centric Intelligence Agency that monitors the heartbeat of Indonesian Corporate Law and Market Dynamics.

---

## 1. Strategic Shift: From "Feed" to "Graph"
Current state: `Scrape -> Score -> Summarize -> Publish`.
**Target state:** `Monitor -> Resolve Entity -> Update Graph -> Predict Impact -> Alert`.

In 2026, Intelligence is not about *flow*, it's about *state*. We don't just want to know "a new law passed"; we want to know "How does this specific PDF change the risk profile for KBLI 62019 (AI Development)?".

### Core Philosophy
1.  **Entity First:** Every article is just a signal updating the state of an Entity (Company, Person, Regulation, KBLI Code).
2.  **GraphRAG:** Use Graph Retrieval-Augmented Generation to understand hidden connections (e.g., "This new tax law references a 2024 decree that affects only Foreign Investment Companies in Bali").
3.  **Active Inference:** The system should generate questions ("Does this apply to KITAS holders?") and spawn agents to answer them.

---

## 2. Architecture Components

### A. The Sentinel (Collection & Monitoring)
*Upgrade to `unified_scraper.py`*

-   **Deep Web Monitors:** specialized scrapers for **OSS (Online Single Submission)** and **AHU (General Law Administration)** to detect changes in licensing requirements, not just news.
-   **Vision-First Document Parser:** Indonesian regulations are often scanned PDFs. Use Gemini Pro Vision / Claude 3.5 Sonnet to OCR and structure these documents immediately into Markdown/JSON.
-   **Change Detection (The Delta):** Hash specific regulatory pages. When the hash changes, trigger a "Diff Analysis" agent to spot exactly what changed (even if it's one removed clause).

### B. The Cortex (Knowledge Graph & Logic)
*New Layer on top of `Qdrant`*

-   **KBLI Knowledge Base:** A dedicated graph node for every KBLI code.
    -   *Structure:* `{ code: "62019", risk_score: "High", linked_regs: ["Permen-12-2025"], allowed_foreign_ownership: "100%" }`.
    -   *Logic:* When a news item mentions "Software Development", the system auto-maps it to KBLI 62019 and flags all connected entities.
-   **Legal Entity Resolution:** Disambiguate "PT GoTo" from "Gojek" and "Tokopedia" to treat them as a unified corporate group in the graph.

### C. The Oracle (Prediction & Reporting)
*Evolution of `article_deep_enricher.py`*

-   **Impact Simulation:** "Simulate the impact of Regulation X on a generic Digital Nomad." The output is a step-by-step risk assessment, not just a summary.
-   **Competitor Radar:** Track specific competitors. If "Competitor A" opens a new branch (detected via job posting or news), update their node in the graph.

---

## 3. Implementation Roadmap (Q1-Q2 2026)

### Phase 1: KBLI & Legal Structuring (The Foundation)
-   [ ] **Action:** Create `data/kbli_database.json` (or distinct Qdrant collection) with all current KBLI codes and their metadata.
-   [ ] **Action:** Enhance `smart_extractor.py` to regex-match KBLI codes (e.g., `\d{5}`) and regulation IDs (e.g., `Permen \d+/\d+`).
-   [ ] **Action:** Build "Legal Diff" tool: A script that takes two versions of a law text and outputs the material changes.

### Phase 2: Graph Integration (The Brain)
-   [ ] **Action:** Implement a lightweight Graph structure (NetworkX or Neo4j-lite) linking `Article <-> Entity <-> Regulation`.
-   [ ] **Action:** Update `intel_pipeline.py` to query the Graph during Enrichment. *("Claude, writing this summary, note that this law contradicts the 2024 decree linked in our graph.")*

### Phase 3: The Watchtower Dashboard (The UI)
-   [ ] **Action:** A dedicated view in `admin-dashboard` showing "Risk Heatmap" by Sector (KBLI).
-   [ ] **Action:** "Watchlist" feature: User subscribes to "Visa Regulations"; AI proactively pushes alerts only when *state* changes.

---

## 4. Immediate "Quick Wins" for Bali-Intel-Scraper

1.  **Legal Document Parsing:** Add a specialized `legal_parser.py` in `scripts/` that handles PDF downloads from JDIH sites, converts to text, and extracts key clauses.
2.  **KBLI Tagger:** Add a step in `professional_scorer.py` or `enricher` that explicitly asks the LLM: *"Which KBLI codes are most impacted by this news? List them."*
3.  **Competitor Watch:** Add a list of target companies to `config/competitors.json`. If they are mentioned, flag as `CRITICAL` priority regardless of score.

---

> *"The ultimate form of intelligence is not knowing everything that happened, but understanding what it means for the future."*
