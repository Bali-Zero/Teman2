---
date: 2026-06-04
domain: operations
study: doc-intake-unified
client_case: false
---

# doc-intake-unified — INDEX

Studio di pianificazione: fonte documento cliente → OCR locale → CRM/Drive automatico,
unificato su un dispatcher source-agnostic con coda `ocr_status='pending'` e firewall PII.

## FASE 1 — System study (mappatura empirica) — [x] COMPLETA

- [x] `01a-whatsapp-source.md` — fonte WhatsApp (wa-mirror): file su disco, coda
      `ocr_status`, evento EventBus, 0 processati.
- [x] `01b-drive-zoho-sources.md` — Drive (Changes API attivo, Mini-only) + Zoho
      (API integrata, nessun intake).
- [x] `01c-processing-pipeline.md` — pipeline OCR→classify→extract→CRM in produzione,
      cloud-tainted; primitive locali riusabili.
- [x] `01d-destinations.md` — destinazioni D1 CRM / D2 Drive / D3 auditor + boundary
      PII B1 RAG / B2 NotebookLM.
- [x] `01-system-study.md` — **SINTESI**: architettura attuale, tabella stato/riuso,
      GAP per WA/Drive/Zoho, punto di convergenza, 3 problemi noti, key numbers.

## FASE 2 — Design + build — [ ] da fare

(da pianificare a valle della sintesi 01)

## FASE 3 — Proposta architettura + red-team panel — [x] COMPLETA

- [x] `03-proposed-architecture.md` — proposta sintetica (~400 parole): 3 fonti → 1
      coda (dedup SHA-256) → 1 orchestratore deterministico + 4 stadi (classify/extract/
      validate/route) → HITL 0.60 → versioning SK↔PERBAIKAN + entity resolution.
- [x] `03-panel-review.md` — red-team 2/3 panelist (DeepSeek V4 Pro + Codex GPT-5.5;
      Gemini agy FAIL OAuth). Verdetto UNANIME: 1 orchestratore deterministico, no swarm.
      7 findings convergenti (C1 dedup byte insufficiente, C2 coda non exactly-once,
      C4 entity-resolution false-merge i piu critici).

## FASE 4.5 — Human-in-the-loop & Evolver hook — [x] COMPLETA

- [x] `04-5-hitl-evolver.md` — review-gate per-campo/per-doc_type (recepisce fix C3);
      interfaccia team = **CRM web** kita.balizero.com vista "Documenti da verificare"
      (esiste gia, RBAC riusabile, correzione strutturata PII-safe) + Telegram come
      *notifier* deep-link (non editor); schema `intake_corrections` (coppia
      ai_value/human_value = segnale errore, solo Postgres locale); gancio evolver =
      nuovo step `intake-corrections-digest` nel context-gathering di
      `agent-library-evolver-run.sh` (PROPONE prompt/regola/soglia -> draft PR, mai
      auto-apply; volume-gated >=30 corr/sett, no-op sotto soglia).

## FASE 4 — Design parti + INTEGRATION CHECK — [x] COMPLETA

- [x] `04-1-ingestion-dedup.md` — P1: 3 fonti → coda unica (dedup composito C1, exactly-once C2).
- [x] `04-2-queue-orchestrator.md` — P2: orchestratore deterministico, lease/heartbeat/retry/DLQ.
- [x] `04-3-classify-extract-validate.md` — P3: 3 stadi locali (qwen3-vl:8b + SEA-LION-32B + regole NB).
- [x] `04-4-entity-routing.md` — P4: entity-resolution C4 + routing proposal (read-only, no write).
- [x] `04-5-hitl-evolver.md` — P5: review-gate per-campo (C3) + evolver hook volume-gated.
- [x] `04-0-integration-check.md` — **INTEGRATION**: matrice giunzioni P1→P2→P3→P4→P5.
      Verdetto **GAP**: parti architetturalmente concordi ma contratti dato-per-dato NON
      combaciano. 1 PASS (P4→P5 chi-scrive), 4 GAP (2 grossi: forma payload P3→P4,
      idempotency-key). 12 contraddizioni (X1-X12): tabella coda con 3 nomi
      (`intake_queue`/`intake_job`/`document_instances`), `pipeline_version` 3 tipi
      (VARCHAR/INT/str), `source` enum (`wa` vs `whatsapp`), `source_ref` TEXT vs JSONB,
      PK BIGSERIAL vs uuid, blocco `source{}` provenance richiesto da P4 ma non emesso da
      P3 (dati esistono in P1, si perdono). Fix = unificazione contratti, NO ridisegno.

## FASE 5 — Riuso (caccia codice) + SPEC FINALE ESEGUIBILE — [x] COMPLETA

- [x] `05a-reusable-code-internal.md` — codice interno riusabile (queue.py, drive_poll,
      crm_enhanced OCR, identity_resolver, verify_client_access). ~70% riuso.
- [x] `05b-reusable-libs-oss.md` — lib OSS local/\$0 (Docling, Procrastinate/pgqueuer,
      RapidFuzz/Splink, ImageHash/xxhash, PyMuPDF). Tabella adozione.
- [x] `05c-nb-patterns.md` — ground-truth NB-AGENTS: validate SPEZZATO (script+agente),
      HITL pull-not-push, dedup pre-OCR, anti tool-hallucination.
- [x] `05d-reusable-repos-github.md` — repo app clonabili (text-extract-api, paperless-gpt,
      wa-dokumen-extractor, docling) + licenze MIT vs GPL.
- [x] `05e-reusable-repos-infra.md` — repo infra (pgqueuer/raquel/splink/instructor/
      ollama-instructor) per i 5 pilastri. Licenze load-bearing.
- [x] `05-final-spec.md` — **SPEC FINALE ESEGUIBILE (DRAFT)**: architettura consolidata
      (chiude X1-X12), schema DB unico (migration 206 + 207 clients), i 5 stadi con
      provenienza-codice (copia/forka/installa/nuovo), build plan a 7 fasi incrementali,
      tabella licenze (MIT/Apache vendorabile vs GPL/AGPL solo-studiare), 10 rischi.
      Recepisce panel C1-C7 + correzioni NB. Da qui un dev/agente PARTE A COSTRUIRE.
