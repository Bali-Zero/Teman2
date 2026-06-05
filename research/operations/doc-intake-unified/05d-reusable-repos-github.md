# 05d — Reusable GitHub Repos for Doc-Intake Pipeline (WhatsApp/email → OCR → fields → CRM)

**Date:** 2026-06-04
**Domain:** operations / doc-intake-unified
**Scope:** Repo-applicazioni (NON librerie pip) clonabili e leggibili, da cui adattare interi pezzi per Bali Zero. Stack target: WhatsApp via Baileys (come wa-mirror Nuzantara), OCR locale (`qwen2.5vl:7b` Ollama), estrazione campi → CRM Postgres.
**Sources:** ricerca web GitHub 2026-06-04 (vedi link inline). Stelle/licenze verificate via WebFetch sui repo principali.

---

## TL;DR — i 5 repo più utili per noi

1. **CatchTheTornado/text-extract-api** (3.1k★, MIT) — il blueprint architetturale più vicino a noi: FastAPI + Celery + Redis + Ollama vision. Copiare l'intero pattern worker async + OCR-strategy-pluggable + LLM-transform-to-JSON.
2. **paperless-ngx** (PYTHON/Django, ~25k★, GPL-3) — il **consumer folder-watcher + classifier neural + custom fields**. Oro per il pattern "watch cartella → OCR → classifica → tagga → storage".
3. **icereed/paperless-gpt** (2.4k★, MIT, Go) — **OCR-via-vision-LLM + human-review UI** + Ollama nativo. La review UI (React) e il prompt-template-engine sono i pezzi più riusabili.
4. **katanaml/sparrow** (5.2k★, GPL-3) — **schema-based extraction + validation automatica** con Vision LLM locale (Ollama/MLX). Copiare il validatore schema→JSON.
5. **classyid/wa-dokumen-extractor-bot** (42★, MIT) — piccolo ma **identico al nostro use-case**: bot WhatsApp che estrae KTP/KK/Ijazah/SIM via reply-command. Pattern trigger + routing per tipo-documento.

Bonus dominio Indonesia: cluster repo **KTP/NPWP OCR** (sotto) per parsing regex dei campi KTP/NPWP specifici.

---

## Tabella repo

| Repo | URL | ★ | Licenza | Pezzo copiabile | Rilevanza |
|---|---|---|---|---|---|
| **text-extract-api** | github.com/CatchTheTornado/text-extract-api | 3.1k | MIT | `text_extract_api/` Celery tasks + OCR-strategy plugin pattern (`easyocr`/`minicpm_v`/`llama_vision`) + LLM-transform post-OCR + Redis cache | ⭐⭐⭐⭐⭐ Blueprint async pipeline Ollama. Quasi sovrapponibile al nostro stack. |
| **paperless-ngx** | github.com/paperless-ngx/paperless-ngx | ~25k | GPL-3.0 | `src/documents/consumer.py` (folder-watch), `src/documents/classifier.py` (NN auto-tag), custom_fields, parsers | ⭐⭐⭐⭐⭐ Consumer + classifier + storage pattern maturo (11k+ commit, Django). |
| **paperless-gpt** | github.com/icereed/paperless-gpt | 2.4k | MIT | `ocr.go`+`app_llm.go`+`llm_client.go` (OCR-via-vision multi-provider), `web-app/` React human-review UI, prompt templates Go | ⭐⭐⭐⭐⭐ Review UI + Ollama nativo + field/tag suggestion engine. |
| **katanaml/sparrow** | github.com/katanaml/sparrow | 5.2k | GPL-3.0 | Sparrow Parse (vision LLM→JSON), validatore schema automatico, Sparrow UI, agents (Prefect) | ⭐⭐⭐⭐ Schema+validation locale (Ollama/Qwen/DeepSeek). GPL = attenzione licenza. |
| **wa-dokumen-extractor-bot** | github.com/classyid/wa-dokumen-extractor-bot | 42 | MIT | `main.py` — routing per comando (`ktp`/`kk`/`ijazah`/`sim`), `query_*_extractor` per tipo doc, media download Neonize | ⭐⭐⭐⭐ Use-case identico (doc Indonesia via WA). Piccolo = leggibile in 1h. OCR via Google Apps Script (da sostituire con Ollama). |
| **docling** (IBM/LF AI) | github.com/docling-project/docling | 60.9k | MIT | API `DocumentConverter().convert()` → Markdown/JSON con layout/table-structure; local/air-gapped | ⭐⭐⭐⭐ Layer PDF→struttura PRIMA dell'LLM (akta multi-pagina, tabelle). Libreria ma app-grade. |
| **ShafqaatMalik/llm-based-invoice-ocr** | github.com/ShafqaatMalik/llm-based-invoice-ocr | low | (check) | FastAPI + Gradio dual-mode (OCR vs vision diretta) | ⭐⭐⭐ Esempio compatto OCR+LLM, UI Gradio per review veloce. |
| **mohammedmanalodi/Invoice-Data-Extractor** | github.com/mohammedmanalodi/Invoice-Data-Extractor | low | (check) | PaddleOCR → LLM parse → JSON+CSV | ⭐⭐⭐ Reference pulito PaddleOCR→LLM→DB. |
| **RiccardoTOTI/LLM-PDF-Extractor** | github.com/RiccardoTOTI/LLM-PDF-Extractor | low | (check) | FastAPI + NuExtract LLM, estrazione campi da **JSON template** | ⭐⭐⭐ Template-driven field extraction (definisci schema, LLM riempie). |
| **ballerine-io/ballerine** | github.com/ballerine-io/ballerine | high | (check, AGPL?) | Workflow orchestration KYC, on-prem, adaptive journeys | ⭐⭐⭐ Orchestrazione KYC self-hosted enterprise. Pesante; pattern workflow utile, non da clonare intero. |
| **PetrJoe/Self-Hosted-KYC-Verification-Platform** | github.com/PetrJoe/Self-Hosted-KYC-Verification-Platform | low | (check) | FastAPI modular: OCR-validation passport/ID + decision engine, no external deps | ⭐⭐⭐ Modulare, self-hosted, decision-engine riusabile. |
| **icereed paperless-AIssist** (discussion) | github.com/paperless-ngx/paperless-ngx/discussions/12252 | — | — | Pattern: separate text/vision model + type-specific custom fields + Ollama Vision | ⭐⭐ Idee config, non repo standalone. |

### Cluster dominio Indonesia (KTP/NPWP — regex/parsing campi)

| Repo | URL | Pezzo copiabile |
|---|---|---|
| arakattack/ocr-ktp | github.com/arakattack/ocr-ktp | Flask + EasyOCR/Tesseract, parsing campi KTP |
| YukaLangbuana/KTP-OCR | github.com/YukaLangbuana/KTP-OCR | OCR KTP open-source, regex NIK/nama/alamat |
| vindruid/ocr_indonesia | github.com/vindruid/ocr_indonesia | KTP+SIM via Detectron2 (layout detection) |
| aksarakan/example-python | github.com/aksarakan/example-python | API OCR KTP **+ NPWP** |
| michaelwong753/OCR-KTP-Passport_Web | github.com/michaelwong753/OCR-KTP-Passport_Web | KTP + **Passaporto** indonesiano Tesseract LSTM |

> Questi NON sono da clonare interi (vecchi, Tesseract). Servono per **rubare le regex/heuristics di parsing dei campi KTP/NPWP** post-OCR. La nostra OCR sarà `qwen2.5vl:7b`, ma il mapping "riga → campo NIK/NPWP/alamat" è già risolto qui.

---

## Note di adattamento per Bali Zero (dove agganciare cosa)

### 1. Trigger / media-download WhatsApp — riusare il NOSTRO Baileys (wa-mirror)
Non serve un nuovo bot: la `wa-mirror` di Nuzantara è già Baileys e già riceve i media. Il pezzo mancante è il **download del media binario + routing**. Pattern di riferimento:
- Baileys `downloadMediaMessage()` + `createWriteStream` (vedi WhiskeySockets/Baileys README) — stream, mai full-buffer in memoria.
- `wa-dokumen-extractor-bot/main.py` mostra il **routing per tipo documento** (reply-command) e l'orchestrazione "media → OCR → format → response". Da adattare: invece di reply-command manuale, classificare automaticamente.

### 2. Consumer / pipeline async — copiare text-extract-api o paperless-ngx
- **text-extract-api** è il match migliore per il NOSTRO stack: FastAPI + Celery + Redis + Ollama. Il pattern `OCR-strategy pluggable` (una classe per engine) ci permette di mettere `qwen2.5vl:7b` come strategia e tenere fallback. Il `LLM-transform post-OCR` (prompt → JSON strutturato) è esattamente il nostro step "estrai campi".
- **paperless-ngx** `consumer.py` se vogliamo il modello **folder-watch** (es. email→cartella→consume) invece di event-driven. Il `classifier.py` (NN che impara dai doc già taggati) è interessante per auto-classificare tipo-documento man mano che il CRM cresce.

### 3. Estrazione campi schema-driven — sparrow o LLM-PDF-Extractor
- **sparrow**: definisci JSON schema dei campi (es. KTP: nik:str, nama:str, alamat:str), il vision-LLM estrae, il validatore **rigetta output malformati**. Questo risolve il problema "LLM ritorna JSON sporco". Attenzione GPL-3.
- **LLM-PDF-Extractor** (NuExtract): più leggero, template-driven, MIT-friendly da verificare.

### 4. Human-in-the-loop review — paperless-gpt UI
- `paperless-gpt/web-app/` (React/TS) mostra suggerimenti AI side-by-side con i dati, editabili prima dell'apply, batch ops. È esattamente la coda "AI estrae, umano corregge i campi" richiesta. MIT. Da adattare per scrivere sul nostro CRM Postgres invece che su paperless-ngx.
- Confidence-driven routing (review solo sotto soglia): pattern descritto in AWS-IDP e Microsoft content-processing-accelerator (concetto, non codice da clonare — sono cloud-only).

### 5. PDF complessi (akta multi-pagina, tabelle) — docling come pre-layer
Per i documenti societari (akta) multi-pagina con tabelle (direttori a pag 2-3, cf. CLAUDE.md OCR rule), **docling** converte PDF→Markdown/JSON preservando reading-order e table-structure PRIMA di passare all'LLM. Riduce allucinazioni su tabelle. Local/air-gapped = compatibile Law 2.

---

## Da diffidare (escludere)
- **AWS Accelerated IDP**, **Microsoft content-processing-accelerator**, **AWS Nova Act**: cloud-only (Textract/Azure AI Foundry). Utili solo come **reference concettuale** per il pattern confidence-driven HITL. NON clonabili local.
- **FaceOnLive/OpenKYC, DoubangoTelecom KYC SDK**: focus face-liveness/anti-spoofing, non doc-field-extraction. Fuori scope (noi non facciamo biometria).
- Cluster KTP-OCR Tesseract: vecchi, accuracy bassa vs vision-LLM moderno. Usare SOLO per regex parsing, non come engine.
- **ballerine**: enterprise pesante (orchestrazione risk-decisioning). Overkill per intake doc; valutare solo se serve workflow KYC formale.

## Verifica licenze prima del riuso di codice
- MIT (riuso libero): text-extract-api, paperless-gpt, docling, wa-dokumen-extractor-bot.
- **GPL-3 (copyleft — attenzione a linkare nel nostro backend)**: paperless-ngx, sparrow. Si possono **leggere e re-implementare il pattern**, ma copiare codice GPL nel backend proprietario Nuzantara obbliga al copyleft. Per sparrow/paperless: studiare l'architettura, riscrivere.
- Da verificare empiricamente prima di copiare: ballerine (probabile AGPL), i repo invoice "low-star" (spesso senza LICENSE → default = all-rights-reserved, NON copiabili).

---

_Sources: github.com/CatchTheTornado/text-extract-api · github.com/paperless-ngx/paperless-ngx · github.com/icereed/paperless-gpt · github.com/katanaml/sparrow · github.com/classyid/wa-dokumen-extractor-bot · github.com/docling-project/docling · github.com/whiskeysockets/Baileys · cluster KTP-OCR (arakattack/ocr-ktp, YukaLangbuana/KTP-OCR, vindruid/ocr_indonesia, aksarakan/example-python, michaelwong753/OCR-KTP-Passport_Web) · KYC (ballerine-io/ballerine, PetrJoe/Self-Hosted-KYC-Verification-Platform)._
