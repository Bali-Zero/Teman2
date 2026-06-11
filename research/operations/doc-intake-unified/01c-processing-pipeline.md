---
date: 2026-06-04
domain: operations
client_case: false
study: doc-intake-unified FASE 1 — processing pipeline (OCR → type → fields)
sources:
  - apps/backend-rag/backend/services/documents/ocr_dispatcher_service.py
  - apps/backend-rag/backend/app/routers/crm_enhanced.py
  - apps/backend-rag/backend/app/routers/crm_enhanced_documents.py
  - apps/backend-rag/backend/services/crm_guardian/ocr.py
  - apps/backend-rag/backend/services/multimodal/pdf_vision_service.py
  - apps/backend-rag/backend/services/rag/vision_rag.py
  - apps/backend-rag/backend/migrations/migration_061_documents_ocr_status.sql
  - /Users/nuzantara/.claude/agents/document-intake-classifier.md
---

# 01c — Existing Document-Processing Pipeline (OCR → type → fields)

**Question:** what already exists to process a document (OCR → type → fields), and how does it fit a future automatic intake?

**TL;DR:** A full OCR→classify→extract→CRM-write pipeline ships **in production** today, anchored on
`ocr_dispatcher_service.dispatch_ocr_by_folder`. It is **Ollama-first but cloud-tainted**: every OCR/Vision
handler falls back to Gemini CLI → Gemini API (Google servers) on local failure. The strict-local intake agent
exists only as a **prompt spec** (not wired). For the unified intake we reuse the *routing/extraction structure*
and the `documents` OCR-status schema, but we MUST NOT call the existing dispatcher/handlers for PII docs —
their cloud fallback is a UU-PDP leak surface. The missing piece is a **strict-local extraction service** (no
Gemini tier) plus an automatic ingest trigger.

---

## 1. `ocr_dispatcher_service.py` — the central router (PRODUCTION)

`apps/backend-rag/backend/services/documents/ocr_dispatcher_service.py` (399 lines).

**What it does:** `dispatch_ocr_by_folder(...)` (line 133) routes an uploaded Drive file to the right OCR handler.
Two tiers:
- **Tier 1 — filename/folder keyword match** (lines 170–299): free, no API. Detects passport/visa/nib/npwp/company_profile
  by filename substrings (`passport`, `kitas/kitap/visa/...`, `nib/berusaha/oss`, `npwp`, `company profile`...).
- **Tier 2 — content classifier fallback** (lines 301–399): when filename gives no signal, calls
  `_auto_classify_content(file_id)` then re-routes via `handler_map` (lines 337–346) if confidence ≥ 0.70
  (`_CONTENT_CONFIDENCE_THRESHOLD`, line 28). Recognized-but-unhandled types (akta/spt/faktur/bukti_potong/contract/family)
  return `{"dispatched": False}` — Phase-2 handlers not yet shipped (lines 332–336, 393–399).

The docstring at **line 301–306 explicitly names the cascade "Ollama qwen2.5vl:7b → Gemini CLI → Gemini API"** — i.e.
the classifier itself can reach cloud. The actual handlers + classifier live in `crm_enhanced.py` (lazy-imported at line 156–164).

After a successful handler it optionally fires the CRM Knowledge-Graph linker (`_kg_link_after_ocr`, lines 41–130),
gated by `CRM_KG_ENABLED` (off by default). KG linking is fully fire-and-forget (all exceptions swallowed).

**Used in production? YES.** Callers (non-test, main checkout):
- `app/routers/crm_enhanced_documents.py:23,164,311,841` — CRM document upload endpoints (router registered:
  `app/setup/router_registration.py:52,197,558`).
- `services/crm/drive_poll_service.py:245,564` — Drive auto-poll ingest (the "Drive Upload → OCR → auto-populate" path).
- `services/portal/_mixins/documents.py:566,574` — Portal client uploads.
- `app/modules/crm/company_router.py:913,918` — company doc uploads.
- `services/documents/crm_drive_backfill_service.py:140,142` — backfill sweep.
The wrapper `_dispatch_ocr_by_folder` is defined in `crm_enhanced.py:861`.

## 2. The OCR engine — `_gemini_ocr` in `crm_enhanced.py` (CLOUD-TAINTED)

`apps/backend-rag/backend/app/routers/crm_enhanced.py:74` `async def _gemini_ocr(image_data, mime_type, prompt)`.
This is the single shared OCR call used by EVERY handler (`_auto_ocr_passport:244`, `_auto_ocr_visa`,
`_auto_ocr_nib`, `_auto_ocr_npwp:577`, `_auto_ocr_company_profile:672`, `_auto_classify_content:834`).

3-tier cascade (docstring lines 77–80):
1. **Ollama `qwen2.5vl:7b`** (local, free) — lines 88–123. ✅ LOCAL.
2. **Gemini CLI** via `shutil.which("gemini")`, `--yolo`, writes image to `/tmp` then `gemini -p` — lines 125–190.
   ⚠️ **CLOUD**: image bytes leave the box to Google.
3. **Gemini API** `gemini-2.5-flash` via `genai_client.generate_content` (`inline_data` base64) — lines 192–219.
   ⚠️ **CLOUD + paid path**.

So whenever local Ollama is down/empty, **passport/KTP/NPWP/akta images and their extracted PII go to Google** —
UU-PDP violation surface. The function name itself ("gemini_ocr") encodes the cloud bias.

**Where extracted fields land (CRM injection, point 5):** handlers write directly into `clients` and `documents`:
- `crm_enhanced.py:93` `UPDATE clients SET ... ` (passport_number etc., built at lines 53–55, 338, 463).
- `documents` OCR status: `UPDATE documents SET ocr_status='completed', ocr_completed_at=NOW(), ocr_extracted_data=$1`
  at lines 394–422, 518–520, 597–599, 719–720. Upload sets `ocr_status='pending'`
  (`crm_enhanced_documents.py:174,320`); status read endpoint `get_client_ocr_status` at
  `crm_enhanced_documents.py:467`. There is **no `POST /api/clients` create-from-OCR** — handlers UPDATE an existing
  client row only (auto-create of a new client from a doc does NOT exist yet).

## 3. `crm_guardian/ocr.py` — text extractor for the L1 summary worker (PARTLY CLOUD-TAINTED)

`apps/backend-rag/backend/services/crm_guardian/ocr.py` (~770 lines). Module docstring (lines 1–12):
"used by the **gemini CLI worker** to feed Gemini with content before generating L1 summaries."

The **extraction cascade itself is 100% local** (lines 8–15):
1. `pdfminer.six` native text layer (`_extract_pdfminer:257`)
2. rasterize (`pypdfium2`) + `tesseract -l ind+eng` (`_tesseract_ocr_png:317`, bin line 53)
3. if tesseract confidence < 0.4 → local Ollama `qwen2.5vl:7b` vision (`_qwen25vl_extract:387`, model const line 58).
Health probe at `check_health:132`. Cache table `crm_guardian_file_content_cache` (migration 181). Has an explicit
**Anti-PII note (lines 24–26)**: text rows live on Fly PG alongside `clients.ai_summary`.

**The taint is downstream, not in this file:** `extract_file_content` (line 436) has **no in-repo caller** (the
consumer is the crm-guardian L1 summary cron worker that hands the extracted text to **Gemini for L1 summary
generation**). So the OCR step is local, but the *text it produces is then shipped to Gemini* for summarization
(`summary_queue.py` + L1 prompts under `services/crm_guardian/prompts/`). For PII docs that summary step is a leak.

## 4. `document-intake-classifier` agent — SPEC ONLY, not wired (CONFIRMED)

`/Users/nuzantara/.claude/agents/document-intake-classifier.md` (9.2 KB, `model: sonnet`, `isolation: worktree`,
tools Read/Write/Bash/Glob). It is a **prompt/markdown agent, not executable code** — nothing dispatches it
automatically.

**Step 1 — Receive input** (line 62–): input is (a) a directory of images/PDFs, (b) explicit paths, or (c) a
WhatsApp media reference resolved to a local path first. It enumerates files; it does NOT subscribe to any queue,
webhook, Drive poll, or wa-mirror event. **Confirmed: not attached to any automatic trigger.**

Critically, the agent's own "Hard rules" (lines ~27–55) already encode the PII boundary: OCR runs **ONLY** on local
`qwen2.5vl:7b`, **never** cloud; no DB mutation (produces a review-queue JSON, ops commits); OCR all pages; vision
model `qwen2.5vl:7b` only. Its "Existing infrastructure" section (verified 2026-06-03) **explicitly lists the
dispatcher and crm_guardian as anti-references** ("MUST NOT route through either of those cloud-tainted paths") and
says to reuse only `llm/ollama_client.py`, direct `ollama run`, local tesseract, and migration_061 schema.

## 5. `multimodal/pdf_vision_service.py` & `rag/vision_rag.py` — ACTIVE, Ollama-first + Gemini fallback (CLOUD-TAINTED)

- **`PDFVisionService`** (`services/multimodal/pdf_vision_service.py:33`): primary local Ollama `qwen2.5vl:7b`
  (`_analyze_via_ollama:146`), **fallback Gemini** `gemini-2.0-flash-lite` (`_analyze_via_gemini`, line 44/129).
  Notable: it logs `"⚠️ [CROSS-BORDER] ... Document image will be sent to Google servers"` at line 125 — the cloud
  leak is acknowledged in-code. **Active:** registered in `app/setup/app_factory.py:452`; called from
  `core/parsers.py:210,266` (PDF parsing) and `services/portal/document_processing.py:201–277` (portal passport box).
- **`VisionRAGService`** (`services/rag/vision_rag.py:45`): same shape — Ollama-first
  (`_vision_via_ollama:206`, model `qwen2.5vl:7b`) + **Gemini fallback** `gemini-2.0-flash-lite`
  (`_vision_via_gemini:237`). **Active:** registered `app_factory.py:451`; used by the agentic RAG toolset
  `services/rag/agentic/tools.py:29,339`. This is RAG document Q&A, not identity-doc intake — but same cloud taint.

---

## Classification: local vs cloud

### (a) Local, reusable primitives
| Component | Path:line | Note |
|---|---|---|
| Local vision client | `backend/llm/ollama_client.py` (`is_ollama_available`, `think:false`) | only sanctioned PII vision path |
| qwen2.5vl:7b vision call | `crm_enhanced.py:88–123`, `crm_guardian/ocr.py:387` (`_qwen25vl_extract`) | reuse the Ollama branch ONLY |
| pdfminer text layer | `crm_guardian/ocr.py:257` `_extract_pdfminer` | free, no OCR, fully local |
| tesseract ind+eng | `crm_guardian/ocr.py:317` `_tesseract_ocr_png` (bin :53) | local printed-text first pass |
| extraction-result cache | `crm_guardian/ocr.py` cache (migration 181) | local PG cache, reusable |
| Tier-1 keyword routing | `ocr_dispatcher_service.py:170–299` | pure string logic, no cloud — fully reusable |
| confidence gate (0.70) | `ocr_dispatcher_service.py:28,324` | reusable policy |
| documents OCR-status schema | `migration_061_documents_ocr_status.sql` (`ocr_status`/`ocr_completed_at`/`ocr_extracted_data`) | reuse as the intake state table |
| field→clients/documents writers | `crm_enhanced.py:93,338,394–422,518,597,719` | reusable AFTER human verify; today auto-write |

### (b) Cloud-tainted — DO NOT use for PII
| Component | Path:line | Why |
|---|---|---|
| `_gemini_ocr` Tier 2/3 | `crm_enhanced.py:125–219` | Gemini CLI + Gemini API send image+PII to Google |
| dispatcher Tier-2 classifier | `ocr_dispatcher_service.py:301–312` → `_auto_classify_content` → `_gemini_ocr` | classifier routes through cloud cascade |
| crm_guardian L1 summary step | `crm_guardian/summary_queue.py` + L1 prompts (consumer of `extract_file_content`) | local OCR text shipped to Gemini for summary |
| PDFVisionService Gemini fallback | `pdf_vision_service.py:129` (logs `[CROSS-BORDER]`) | image → Google on local fail |
| VisionRAGService Gemini fallback | `vision_rag.py:237` | image → Google on local fail |

### (c) What's missing for unified intake
1. **A strict-local extraction service** = the dispatcher's routing + handlers but with the Gemini tiers **deleted/disabled**
   (a `local_only=True` mode, or a new `local_ocr_service` calling only the Ollama/tesseract/pdfminer branches). The
   intake-classifier agent's own spec says it'll adopt the dispatcher's local tier "if a future refactor makes it
   callable WITHOUT the Gemini fallback" — that refactor is the deliverable.
2. **An automatic ingest trigger** wired to the local service. Today only Drive-poll/portal/upload hit the
   cloud-tainted dispatcher; the local agent has no auto-trigger. Unified intake needs a source→local-OCR→review-queue
   bridge (Drive/WhatsApp/email — see sibling studies 01a/01b).
3. **Auto-create client from doc.** Handlers only `UPDATE` an existing client; there's no create-from-OCR. Unified
   intake of a *new* lead's docs has no landing row.
4. **A human-review queue + verify-before-commit step** (the agent designs the JSON shape; no DB-backed queue exists).
5. **PII masking in logs/Telegram** is specced in the agent but not enforced by the production handlers (they log
   passport numbers, e.g. `crm_enhanced.py:99`).

## Reuse verdict for the unified intake
- **Keep & reuse:** Tier-1 keyword router, confidence gate, the `documents.ocr_status/ocr_extracted_data` schema,
  the local Ollama/tesseract/pdfminer extractors, the local cache, and the per-type field maps + clients/documents
  writers (behind a human-verify gate).
- **Fork & strip:** clone the handler logic minus `_gemini_ocr` Tier 2/3 → a `local_only` OCR path. Never call
  `_gemini_ocr`, the dispatcher Tier-2 classifier, PDFVisionService/VisionRAGService cloud fallbacks, or the
  crm_guardian L1 summary step for identity/PII documents.
- **Build new:** auto-ingest trigger, create-from-OCR, review queue, PII-masked logging.
