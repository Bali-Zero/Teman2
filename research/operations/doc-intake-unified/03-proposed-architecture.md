---
date: 2026-06-04
domain: operations
study: doc-intake-unified
phase: 3 — PROPOSED ARCHITECTURE
client_case: false
sources:
  - research/operations/doc-intake-unified/01-system-study.md
  - research/operations/doc-intake-unified/02a-external-sota.md
---

# FASE 3 — Architettura Proposta (sintesi)

## Convergenza: 1 coda unica
Le 3 fonti convergono su **una sola coda intake** prima di qualsiasi lavoro pesante.
- **WhatsApp**: consumer Node/Python *sul Pro* (DB locale `nuzantara_dev`) drena
  `whatsapp_message_context` dove `ocr_status='pending' AND media_stored_path NOT NULL
  AND media_type IN ('document','image')`.
- **Drive**: `drive_poll_service` (Changes API) re-enabled con leader-election Pro+Mini.
- **Zoho**: nuovo poll `list_emails(is_unread)` → `get_attachment()` bytes.

Ogni item, prima dell'enqueue, calcola **SHA-256 dei byte** → tabella `intake_content_hash`
(UNIQUE). Hash già visto = duplicato esatto cross-source (stesso PDF da WA *e* email) →
scartato pre-OCR. Stato coda esplicito: `pending→ocr→classified→extracted→review→routed→done|dead`.

## 1 orchestratore deterministico + 4 stadi (tool ristretti ≤5)
Un **solo orchestratore deterministico** (no swarm peer-to-peer: evita il 15-tool-trap,
tool-accuracy <80%, e resta auditabile per un'agenzia visa/tax regolata) guida 4 stadi:
1. **classify** — qwen3-vl locale, zero-shot + CoT, su 8 tipi (akta/KTP/passport/NIB/NPWP/KITAS/SK/OSS).
2. **extract** — SEA-LION locale, per-field confidence. (Docling-MLX opzionale come layer struttura tabelle.)
3. **validate** — regole NB deterministiche: **NIB 13 cifre**, **NPWP 16 cifre**, **modal disetor ≥ Rp 2,5 mld**, **KITAS E-codes** (E23/E28/E31/…).
4. **route** — scrive su 3 destinazioni.

## Human-in-the-loop + versioning + entity resolution
- **HITL gate a confidenza 0.60**: per-field. Sopra → candidato auto-commit; sotto →
  riga **review queue** con motivo + campi incerti. Correzioni umane = few-shot feedback.
- **Versioning SK↔PERBAIKAN**: NON fusi. Linkati per `(doc_type, client_id, document_number)`
  e versionati. Il dedup SHA-256 non li collassa (byte diversi) — è un layer separato.
- **Entity resolution doc→cliente**: phone **E.164** → match esatto **passport/KITAS**
  → **Jaro-Winkler** sul nome. Sotto soglia score → HITL, mai auto-merge.

## Vincoli architetturali (hard)
- **PII 100% locale**: fork `local_only` del dispatcher — i tier Gemini CLI/API di
  `_gemini_ocr` e il summary L1 crm_guardian sono **rimossi** dal path PII. Solo
  pdfminer→tesseract(ind+eng)→qwen2.5vl/qwen3-vl/SEA-LION.
- **No DB mutation diretta**: route scrive in una **review queue DB-backed**; il commit
  su `documents`/`clients` avviene solo post-verify (gate 0.60 o human).
- **Modelli via `MODEL_TOPOLOGY.json`**: nessun model-id hardcoded.

## Risoluzione dei 2 split-brain
- **wa-mirror locale/Fly**: il consumer WhatsApp gira *sul Pro contro il DB locale*
  (mai Fly) — chiude gli 8.355 eventi unconsumed senza violare Law 2.
- **Dispatcher cloud-tainted**: **fork local-only** è l'unico path per i doc PII;
  il path Gemini resta solo per contenuti non-PII espliciti.

## Audit
Agente audit = **event-log append-only**, osserva il bus, **mai nel hot-path** (no coupling).
