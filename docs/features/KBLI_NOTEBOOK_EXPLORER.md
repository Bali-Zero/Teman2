# KBLI 2025 Notebook Explorer

**Last Updated: 2026-03-22**

**Status:** Production-Ready (Prototype v1)
**Date:** 2026-02-05
**Owner:** Nuzantara Intelligence Team

## 🎯 Overview

The KBLI Notebook Explorer is a specialized workspace designed for deep regulatory research on Indonesian business classifications (KBLI). It bridges the gap between the latest statistical standards (**BPS 7/2025**) and regulatory frameworks (**PP 28/2025**).

## 🏗️ Architecture

### Backend (`apps/backend-rag`)

- **Router:** `backend.app.routers.kbli_notebook`
- **Data Sources:**
  - **Knowledge Graph (PostgreSQL):** Stores complex relationships (KBLI -> Licenses, KBLI -> Sector).
  - **Vector Database (Qdrant):** Collection `kbli_unified` (Hybrid Search) for semantic matching.
- **Logic:**
  - `/search`: Semantic search for codes and industries.
  - `/inspect/{code}`: Deep graph traversal to find risk profiles, SLAs, and specific obligations.
  - `/chat`: Context-aware agentic interface specialized in KBLI.

### Frontend (`apps/mouth`)

- **Route:** `/kbli-explorer`
- **UI Paradigm:** 3-panel professional workspace.
  - **Source Panel:** Contextual documents.
  - **Notebook Canvas:** Conversational stream with interactive citations.
  - **Graph Inspector:** Data-dense visualization of KBLI metadata.
- **Palette:** _Nocturnal Luxury_ (Obsidian #050507, Champagne Gold #D4B483).

## 🧪 Testing & Quality

- **Integration Tests:** `tests/api/test_kbli_notebook.py`
- **Quality Gates:**
  - Zero nulls for critical metadata (`pma_status`, `licensing_status`).
  - Validated cross-sector mapping (Verified against BPS 2025 restructuring).

## 🚀 Deployment

- **Backend:** Part of the standard Fly.io deployment.
- **Frontend:** Deployed on Vercel.
- **Access:** Currently configured as a specialized internal/pro-user tool (Lead Magnet ready).

## 📝 Maintenance

- Ingestion scripts are located in `scripts/ingestion/` (e.g., `import_kbli_kg.py`).
- To update the data, rerun the ingestion pipeline after updating the `kbli_2025_reference.json` ground truth.
