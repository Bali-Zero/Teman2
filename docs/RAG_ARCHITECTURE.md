# 🧠 Nuzantara Agentic RAG Architecture

> **Version:** 1.0
> **Status:** Production Ready
> **Engine:** Google Gemini 2.5 Pro
> **Vector DB:** Qdrant

## 1. 🏗️ System Overview

The Nuzantara RAG (Retrieval-Augmented Generation) system is an advanced **Agentic RAG** architecture designed to provide high-precision, context-aware answers for business, legal, and tax queries in the Indonesian context.

Unlike traditional RAG systems that simply retrieve and summarize, this system uses a **ReAct (Reason-Act-Observe)** loop, allowing the AI to dynamically decide *if* it needs to search, *which* tools to use, and *how* to synthesize information from multiple sources.

### Core Capabilities
-   **Multi-Step Reasoning:** Can break down complex queries into logical steps.
-   **Intelligent Routing:** Automatically directs queries to the most relevant knowledge base (Visa, Tax, Legal, etc.).
-   **Tool Use:** Can perform calculations, database lookups, and visual analysis in addition to text retrieval.
-   **Self-Correction:** Evaluates the quality of retrieved information and can refine its search strategy.

---

## 2. 🧩 Architecture Layers

The system is built on a modular, layered architecture:

```mermaid
graph TD
    User[User Query] --> API[API Layer /agentic-rag/query]
    API --> Orch[Agentic Orchestrator (ReAct Loop)]
    
    subgraph "Orchestration Layer"
        Orch --> Router[Intelligent Query Router]
        Orch --> Tools[Tool Executor]
    end
    
    subgraph "Routing Intelligence"
        Router -- "Phase 1: Keyword" --> Domain[Domain Detection]
        Router -- "Phase 2: Semantic" --> SubDomain[Sub-Collection Selection]
        Router -- "Phase 3: Confidence" --> Fallback[Fallback Chain Agent]
    end
    
    subgraph "Retrieval Layer"
        Fallback --> Search[Search Service]
        Search --> Qdrant[(Qdrant Vector DB)]
        Search --> Rerank[Reranker Service (Optional)]
    end
    
    subgraph "Generation Layer"
        Orch --> Gemini[Gemini 2.5 Pro]
    end
```

---

## 3. 🧭 Intelligent Query Routing

The routing system (`services/query_router.py`) is the brain of the retrieval process. It operates in three phases to ensure maximum relevance:

### Phase 1: Keyword Matching (Fast Path)
Instantly detects high-signal keywords to assign a primary domain.
-   **VISA:** `visa`, `kitas`, `immigration`
-   **TAX:** `tax`, `pajak`, `pph`, `vat`
-   **LEGAL:** `law`, `regulation`, `contract`
-   **KBLI:** `kbli`, `business code`, `oss`
-   **PROPERTY:** `villa`, `land`, `lease`

### Phase 2: Domain Scoring & Sub-Routing
Refines the selection within a domain.
-   *Example:* A tax query might be routed to `tax_genius` (calculations) or `tax_updates` (news) based on context.

### Phase 3: Confidence & Fallback Chains
Calculates a confidence score (0.0 - 1.0).
-   **High (>0.7):** Queries only the primary collection.
-   **Medium (0.3 - 0.7):** Queries primary + 1 fallback.
-   **Low (<0.3):** Queries primary + up to 3 fallbacks.

| Primary Collection | Typical Fallback Chain |
| :--- | :--- |
| `visa_oracle` | `legal_architect` → `tax_genius` |
| `kbli_eye` | `legal_architect` → `tax_genius` |
| `tax_genius` | `tax_updates` → `legal_architect` |
| `property_knowledge` | `legal_architect` → `property_listings` |

---

## 4. 📚 Knowledge Collections

The system manages 17+ specialized vector collections in Qdrant (including aliases):

| Collection Name | Purpose | Doc Count | Notes |
| :--- | :--- | :--- | :--- |
| **`visa_oracle`** | Immigration & Visas | ~1,612 | Visa types, requirements, procedures |
| **`kbli_eye`** | Business Classification | ~8,886 | Alias: `kbli_unified` |
| **`kbli_unified`** | KBLI Master | ~8,886 | Primary KBLI collection |
| **`tax_genius`** | Taxation | ~895 | Tax laws, rates, treaties |
| **`tax_updates`** | Tax News | ~895 | Alias: `tax_genius` |
| **`legal_architect`** | Corporate Law | ~5,041 | Alias: `legal_unified` |
| **`legal_unified`** | Legal Master | ~5,041 | Primary legal collection |
| **`legal_updates`** | Regulatory News | ~5,041 | Alias: `legal_unified` |
| **`property_knowledge`** | Real Estate | ~29 | Alias: `property_unified` |
| **`bali_zero_team`** | Internal Knowledge | ~22 | Team profiles, roles |
| **`bali_zero_pricing`** | Service Pricing | ~29 | Official Bali Zero prices |
| **`zantara_books`** | Knowledge Base | ~8,923 | General documents |
| **`cultural_insights`** | Cultural Context | 0 | Indonesian cultural knowledge |

---

## 5. 🛠️ Agent Tools

The Agentic Orchestrator has access to a suite of tools beyond just vector search:

1.  **`VectorSearchTool`**: The primary tool for retrieving semantic context from Qdrant.
2.  **`DatabaseQueryTool`**: Performs structured SQL queries on the PostgreSQL database (e.g., "Find client X").
3.  **`CalculatorTool`**: Handles complex financial or tax calculations to ensure arithmetic accuracy.
4.  **`VisionTool`**: Analyzes uploaded documents (PDFs) or images using Gemini Vision.
5.  **`PricingTool`**: Retrieves current official pricing for Bali Zero services.
6.  **`WebSearchTool`**: (Predisposed) For retrieving real-time information from the web.

---

## 6. 🚀 Request Flow (The "Life of a Query")

1.  **Reception:** User sends a query to `/api/agentic-rag/query`.
2.  **Orchestration Start:** `AgenticRAGOrchestrator` initializes the ReAct loop.
3.  **Thought:** The LLM analyzes the query. *"User wants to know the tax rate for a PT PMA in Bali."*
4.  **Action:** LLM decides to use `VectorSearchTool`.
5.  **Routing:** `QueryRouter` identifies `tax_genius` as the primary collection with `legal_architect` as fallback.
6.  **Retrieval:** `SearchService` queries Qdrant, retrieves chunks, and (optionally) reranks them.
7.  **Observation:** The tool returns the relevant tax regulation chunks.
8.  **Synthesis:** The LLM combines the retrieved data with its internal knowledge to generate a comprehensive answer.
9.  **Response:** The final answer is sent back, including source citations.

---

## 7. ⚙️ Technical Stack

-   **Language:** Python 3.11+
-   **Framework:** FastAPI 0.104.1
-   **LLM:** Google Gemini (via `google-generativeai>=0.5.0`)
-   **Vector DB:** Qdrant (Async Client `>=1.12.0`)
-   **Embeddings:** `sentence-transformers==2.7.0` (local, free)
-   **Chunking:** Semantic Recursive Chunking (Size: 500, Overlap: 50)
-   **Reranker:** `ms-marco-MiniLM-L-6-v2` (Cross-Encoder)
-   **Frontend:** Next.js 16.0.8, React 19.2.1, Tailwind CSS 4

---

*Auto-generated documentation based on source code analysis.*
