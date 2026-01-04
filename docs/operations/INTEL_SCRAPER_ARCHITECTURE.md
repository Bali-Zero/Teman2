# BALI ZERO INTEL SCRAPER v2 - ARCHITECTURE

**Status:** ✅ PRODUCTION (Implemented Jan 2026)
**Cost Model:** "Zero Cost" (Local Llama + Qdrant + Existing Subscriptions)

## 🌟 Overview

The Bali Zero Intel Scraper v2 is a resilient, intelligent acquisition pipeline designed to feed the Nuzantara knowledge base without incurring API costs for every article. It replaces brittle CSS selectors with AI-driven extraction and simple hash matching with semantic deduplication.

## 🏗️ Core Components

### 1. Smart Extractor (The "Unbreakable" Layer)
**File:** `apps/bali-intel-scraper/scripts/smart_extractor.py`

A 4-layer fallback system ensures content is extracted even if website layouts change.

| Priority | Method | Technology | Cost | Speed | Reliability |
|:---|:---|:---|:---|:---|:---|
| **1** | **CSS Selectors** | `BeautifulSoup` | $0 | ⚡️ <0.1s | ⚠️ Brittle |
| **2** | **Heuristic** | `Trafilatura` | $0 | ⚡️ <0.5s | ⭐ High |
| **3** | **Parser** | `Newspaper3k` | $0 | ⚡️ <1.0s | ⭐ High |
| **4** | **AI Fallback** | **Llama 3.2 (Local)** | $0 | 🐢 ~5-10s | 🛡️ **Unbreakable** |

**Logic:** If structured methods fail (return empty/short text), the raw HTML is fed to a local LLM with the prompt: *"Extract ONLY the main article content..."*.

### 2. Semantic Deduplicator
**File:** `apps/bali-intel-scraper/scripts/unified_scraper.py` (Class: `SemanticDeduplicator`)

Prevents "same news, different source" redundancy using vector similarity.

*   **Model:** `all-MiniLM-L6-v2` (Runs locally, ~80MB RAM).
*   **Database:** Qdrant (Local Docker container).
*   **Threshold:** > 0.85 similarity = Duplicate.
*   **Workflow:**
    1.  Generate embedding for Title + Summary.
    2.  Query Qdrant `balizero_articles` collection.
    3.  If match found -> Skip download.
    4.  If no match -> Upsert vector + content hash.

### 3. Pre-Scoring (The "Noise Filter")
**File:** `apps/bali-intel-scraper/scripts/ollama_scorer.py`

Filters irrelevant content *before* resource-intensive processing.

*   **Engine:** Ollama (Llama 3.2:3b).
*   **Criteria:**
    *   **CRITICAL (80-100):** Visas, Laws, Taxes.
    *   **STRATEGIC (50-79):** Tourism trends, Property.
    *   **NOISE (<40):** Gossip, Sports, General News.
*   **Action:** Articles with score < 40 are discarded immediately.

## 🔄 Data Pipeline Flow

```mermaid
graph TD
    A[Fetch Index Page] --> B{Pre-Scorer (Llama)};
    B -- Score < 40 --> C[Discard 🗑️];
    B -- Score >= 40 --> D{Semantic Dedup (Qdrant)};
    D -- Similarity > 0.85 --> C;
    D -- Unique --> E{Smart Extractor};
    E -- CSS Success --> F[Save to /data/raw];
    E -- CSS Fail --> G[Trafilatura/Newspaper];
    G -- Success --> F;
    G -- Fail --> H[Llama 3.2 Extraction];
    H --> F;
```

## 🚀 Usage

```bash
# Run the full pipeline
python apps/bali-intel-scraper/scripts/unified_scraper.py --categories immigration business --limit 20

# Options
--no-semantic   # Disable Qdrant dedup (use SHA-256 only)
--min-score 50  # Increase strictness of pre-filter
```

## 🛠️ Requirements

*   **Ollama:** Running locally (`ollama serve`) with `llama3.2:3b` pulled.
*   **Qdrant:** Running via Docker (`localhost:6333`).
*   **Python Libs:** `sentence-transformers`, `qdrant-client`, `playwright`, `trafilatura`.

---
*Documented: Jan 4, 2026*
