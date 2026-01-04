# SCRAPER IMPROVEMENT PLAN - STATUS: COMPLETED

> **UPDATE (Jan 4, 2026):** This plan has been fully executed.
> See **[docs/operations/INTEL_SCRAPER_ARCHITECTURE.md](docs/operations/INTEL_SCRAPER_ARCHITECTURE.md)** for the live documentation.

---

## ✅ 1. Estrazione "Unbreakable" con Llama
**Status:** IMPLEMENTED (`smart_extractor.py`)
- Fallback logic: CSS -> Trafilatura -> Newspaper -> Llama 3.2.
- Handles broken layouts without code changes.

## ✅ 2. Pre-Scoring in Tempo Reale
**Status:** IMPLEMENTED (`unified_scraper.py` + `ollama_scorer.py`)
- Scoring happens *before* full extraction.
- Filters out "Noise" (<40 score) to save resources.

## ✅ 3. Deduplica Semantica
**Status:** IMPLEMENTED (`unified_scraper.py` class `SemanticDeduplicator`)
- Uses `all-MiniLM-L6-v2` (Local embedding).
- Checks Qdrant `balizero_articles` collection.
- Threshold 0.85 for duplicate detection.

---
*Original plan preserved below for history*

## 1. Analisi dello Stato Attuale (Legacy)
...