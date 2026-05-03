# Local AI Automations — Ollama-First Pattern

**Date:** 2026-03-08
**Commit:** `0f602c259`
**Deploy:** v2383 Fly.io Singapore

## Architecture

All AI-powered automations follow the **Ollama-first** pattern:

```
Request → Try Ollama (local, free) → Success? → Return
                                   → Fail?    → Try Gemini API → Return
```

**Production (Fly.io):** Ollama not available → always Gemini fallback.
**Development (Pro M4):** Ollama available → local processing, $0.00, private.

## Local Model Roster

| Model            | Ollama Tag         | Size  | Role                                       |
| ---------------- | ------------------ | ----- | ------------------------------------------ |
| Gemma 4 26B MoE  | `gemma4:26b`       | 17GB  | KG extraction, JSON output, agentic tasks  |
| Qwen 3.5 9B      | `qwen3.5:9b`       | 6.6GB | Fast classification, titles, short tasks   |
| DeepSeek R1 32B  | `deepseek-r1:32b`  | 19GB  | Heavy reasoning, war-room, CELL            |
| Qwen 2.5 VL 7B   | `qwen2.5vl:7b`    | 6.0GB | Vision OCR (passport, PDF, documents)      |

**Total:** ~49GB on 48GB M4 Pro (models loaded on demand, not all at once).

## Core Client

**File:** `backend/llm/ollama_client.py`

```python
from backend.llm.ollama_client import (
    ollama_chat,        # Async chat API
    ollama_generate,    # Async generate API
    is_ollama_available, # Check model availability
    MODEL_FAST,         # "qwen3.5:9b"
    MODEL_HEAVY,        # "deepseek-r1:32b"
    MODEL_JSON,         # "gemma4:26b"
)
```

### Critical: `think: false`

Qwen 3.5 has thinking mode ON by default on Ollama. Without `"think": false`
in the payload, responses are empty — all token budget is consumed by internal
reasoning. The `ollama_client.py` handles this automatically.

## Automation Details

### 1. Conversation Title Generator

| Property    | Value                                                  |
| ----------- | ------------------------------------------------------ |
| **File**    | `backend/services/crm/conversation_title_generator.py` |
| **Model**   | qwen3.5:9b (local) → Gemini Flash (fallback)           |
| **Trigger** | First user message in new conversation                 |
| **Latency** | 772ms avg (local), ~300ms (Gemini)                     |
| **Cost**    | $0.00 local, ~$0.000003 Gemini                         |

Generates concise professional titles (max 50 chars) for chat conversations.
Supports Italian, English, Indonesian language detection.

### 2. PDF Vision / Document OCR

| Property    | Value                                                     |
| ----------- | --------------------------------------------------------- |
| **File**    | `backend/services/multimodal/pdf_vision_service.py`       |
| **Model**   | qwen2.5vl:7b vision (local) → Gemini Vision (fallback)    |
| **Trigger** | PDF upload for analysis (passports, invoices, legal docs) |
| **Latency** | 13.2s warm / 63s cold (local), ~3s (Gemini)               |
| **Cost**    | $0.00 local                                               |

Analyzes PDF pages using vision models. Extracts tables, text, and structured
data from business documents, passports, and KBLI tables.

**Privacy benefit:** When Ollama is available, passport and CRM documents
never leave the local machine.

### 3. Vision RAG (Multi-Modal Document Search)

| Property    | Value                                                 |
| ----------- | ----------------------------------------------------- |
| **File**    | `backend/services/rag/vision_rag.py`                  |
| **Model**   | qwen2.5vl:7b vision (local) → Gemini Vision (fallback) |
| **Trigger** | RAG queries that involve visual document elements       |
| **Cost**    | $0.00 local                                           |

Processes PDFs extracting both text and visual elements (tables, charts,
diagrams, forms). Each visual element is classified and described by the
vision model, then made searchable alongside text content.

### 4. Birthplace Enrichment (CRM)

| Property    | Value                                                   |
| ----------- | ------------------------------------------------------- |
| **File**    | `backend/services/crm/birthplace_enrichment_service.py` |
| **Model**   | qwen3.5:9b (local only, no fallback)                    |
| **Trigger** | Cron job at 22:00 WITA (Bali time)                      |
| **Batch**   | 10 clients per run                                      |
| **Cost**    | $0.00                                                   |

Enriches client birthplace data with cultural context: famous people,
historical events, local specialties, conversation starters for Zantara.
Runs only when Ollama is available (skips gracefully on Fly.io).

## Services NOT Changed (by design)

| Service             | Current Provider         | Why Not Changed               |
| ------------------- | ------------------------ | ----------------------------- |
| Article Composer    | Claude CLI Opus 4.6      | User excluded ("Intoccabile") |
| Intent Classifier   | Pattern-based (regex)    | Already zero API cost         |
| Personality Service | Oracle Cloud self-hosted | Already optimized             |
| KG Extraction       | Gemini free tier         | Future optimization candidate |

## OpenRouter Models (Cloud Fallback)

For services that need cloud LLM (when both Ollama and Gemini unavailable):

| Tier     | Model ID               | Use Case                |
| -------- | ---------------------- | ----------------------- |
| Powerful | `qwen/qwen3.5-27b`     | Complex reasoning       |
| Fast     | `qwen/qwen3.5-35b-a3b` | Quick responses         |
| Context  | 262,144 tokens         | Up from 40,960 (Qwen 3) |

**File:** `backend/services/llm_clients/openrouter_client.py`

## Monitoring

### Check Ollama Status (local dev)

```bash
curl http://localhost:11434/api/tags | python3 -m json.tool
```

### Check Service Behavior in Production

```bash
fly logs --app nuzantara-rag | grep -i "ollama\|vision\|title"
```

Expected production behavior: Ollama unavailable → Gemini fallback used.

### Live Test Script

```bash
cd apps/backend-rag
PYTHONPATH=. python backend/scripts/test_ollama_vs_gemini.py
```

Runs 10 title generation tests (IT/EN/ID) comparing Ollama vs Gemini
side-by-side with timing and quality comparison.

## Cost Impact

| Service               | Before (monthly est.) | After (monthly est.) |
| --------------------- | --------------------- | -------------------- |
| Title generation      | ~$0.50 (Gemini)       | $0.00 (local)        |
| PDF Vision OCR        | ~$2.00 (Gemini)       | $0.00 (local)        |
| Birthplace enrichment | ~$0.30 (Gemini)       | $0.00 (local)        |
| **Total saved**       |                       | **~$2.80/month**     |

Note: Cost savings are modest because usage is low. The primary benefit is
**privacy** (documents stay local) and **independence** from API availability.
