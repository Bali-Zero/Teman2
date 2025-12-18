# 🚀 Nuzantara Ultra Hybrid - Feature Documentation

*System Version: v5.4 (Deployed: Dec 2025)*

This document details the "Ultra Hybrid" architecture improvements implemented in Phase A and Phase B.

---

## 1. 🧠 Quality Routing (Fast / Pro / DeepThink)

The system now intelligently routes user queries to the most appropriate model tier based on complexity and intent.

### Tiers Definition
| Tier | Model | Trigger Intent | Cost/Speed | Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **⚡ FAST** | `Gemini 2.0 Flash` | `greeting`, `casual`, `identity`, `business_simple` | Low / <2s | Saluti, info generali, domande rapide. |
| **🌟 PRO** | `Gemini 1.5 Pro` | `business_complex`, `pro_keywords` (requisiti, costi) | Med / <8s | Procedure visti, tasse, setup aziendale standard. |
| **🧠 DEEP THINK** | `Gemini 1.5 Pro` (+ Reasoning Prompt) | `strategy`, `analysis`, `risk`, `comparison` | High / <20s | Analisi rischi, confronti strategici (PMA vs PT), piani complessi. |

### Implementation
- **Classifier:** `IntentClassifier` (Pattern-based) detects intent.
- **Orchestrator:** `AgenticRAGOrchestrator` selects the model and injects specialized system prompts (e.g., "Deep Think Mode").

---

## 2. 🔎 Ultra Reranking

Retrieval quality has been boosted by a 2-stage process: **Hybrid Search + Cross-Encoder Reranking**.

### Architecture
1.  **Retrieval:** Fetch top `4 * k` candidates using Qdrant (Vector Search).
2.  **Reranking:** Re-order candidates using **ZeroEntropy (zerank-2)** or **Jina v2**.
3.  **Selection:** Return top `k` semantically relevant documents.

### Configuration
- **Provider:** Configurable via `RERANKER_PROVIDER` (defaults to `zeroentropy` if key present).
- **Fallback:** Automatic fallback to Jina -> Local CrossEncoder if API fails.
- **Key:** `ZERANK2_API_KEY` (Fly.io Secret).

---

## 3. 📚 Standard Evidence Pack & Output

Responses for business domains are now structured and verifiable.

### Standard Templates
Queries regarding **Visa**, **Tax**, and **Company Setup** trigger enforced Markdown templates:
- **Tables:** For Costs, Requirements, Timelines.
- **Checklists:** For mandatory documents.

### Citations (Evidence Pack)
Every claim is backed by a source.
- **Format:** Inline `[1]` markers.
- **Footer:** Structured "Sources" section with Titles and URLs.
- **Data Flow:** `VectorSearchTool` returns structured JSON (`content` + `metadata`) to allow precise citation generation.

### 📊 Verification Score (Confidence Metric)
The system calculates a "Verification Score" (0-100) based on source relevance and retrieval density.

| Score | Confidence Level | Visual Indicator | Meaning |
| :--- | :--- | :--- | :--- |
| **80-100** | **High** | 🟢 Green | Verified by multiple high-quality sources (e.g., official regulations). |
| **50-79** | **Medium** | 🟡 Yellow | Supported by documents but with potential ambiguity or indirect references. |
| **<50** | **Low** | 🔴 Red / Hidden | Low confidence; system relies on general knowledge (warns user). |

### 🖼️ UI Visualization (Citation Card)
The Frontend renders an interactive **Citation Card** below the answer:

```tsx
// Visual Representation
--------------------------------------------------
|  [Message Content...]                          |
|  ...according to regulation 12.                |
|                                                |
|  Verification Score: 92 (High)                 |
|  --------------------------------------------  |
|  📄 VISA_Guidelines_2024.pdf                   |
|     "Article 12 guarantees..."                 |
|  📄 TAX_Law_Article_5.pdf                      |
|     "Monthly reporting occurs on..."           |
--------------------------------------------------
```
- **Interactive:** Tapping a source expands the full snippet.
- **Micro-animations:** Smooth fade-in on load.


---

## 4. 🛡️ Privacy & Security

### PII Redaction
All logs are sanitized before storage/output.
- **Emails:** Replaced with `[EMAIL]`.
- **Phones:** Replaced with `[PHONE]` (supports Intl and ID formats).
- **Utility:** `utils.privacy_redaction.py`.

---

## 5. 📊 Continuous Evaluation

A "Gold Standard" dataset allows regression testing.
- **Script:** `tests/evaluation/evaluate_rag.py`.
- **Metrics:** Fact Retrieval Score (0-100), Latency.
