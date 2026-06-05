---
date: 2026-06-04
domain: operations
study: doc-intake-unified
phase: 3 — RED-TEAM PANEL REVIEW
client_case: false
panelists:
  - DeepSeek V4 Pro (deepseek-v4-pro, max_tokens 4000) — RESPONDED
  - Codex GPT-5.5 (xhigh, sota-architecture-loop + memory grounding) — RESPONDED
  - Gemini 3.1 Pro (agy) — FAILED (OAuth scaduto, auth timeout) — 2/3 panel
sources:
  - research/operations/doc-intake-unified/03-proposed-architecture.md
---

# FASE 3 — Red-Team Panel Review (2/3 panelist)

Panel multi-LLM adversariale sull architettura proposta. **DeepSeek V4 Pro** e
**Codex GPT-5.5** hanno risposto; **Gemini agy ha fallito per OAuth scaduto**
(auth timeout 30s) — panel a 2 voci, asimmetrico-adversariale, NON consensus.

---

## A. La proposta (verbatim)

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

---

## B. Review verbatim

### B.1 — DeepSeek V4 Pro

**Design flaws, failure mode e rischi**

- **Dedup solo su byte identical**: Non cattura duplicati con ricompressione o metadati diversi. Inoltre, se un documento va in stato `dead` e serve ri-OCR dopo un aggiornamento del modello, lo stesso hash viene scartato in silenzio, impedendo il riprocessamento. Necessita di una chiave composta (hash + versione pipeline) o coda di retry esplicita.

- **Entity resolution fragile**: E.164 esatto fallisce senza normalizzazione (prefisso +62 assente, spazi). Passaporto/KITAS senza strip e lower-case produce falsi negativi. Jaro-Winkler sul solo nome (senza data di nascita né blocco su `doc_type`) fonde clienti con nomi simili (es. “Wayan” molto comune a Bali) → alto rischio di merge errati e PII mismatch.

- **Saturazione HITL**: La soglia 0.60 a livello documento manda in review l’intero intake per un singolo campo a bassa confidenza, creando collo di bottiglia. Meglio instradare a HITL solo i campi sotto-soglia, validando automaticamente il resto.

- **Assenza di gestione guasti**: Manca coda di retry per errori transitori (OCR, chiamate a Google Drive/Zoho) e circuit breaker. Il consumer WhatsApp su DB locale (Pro) è single point of failure e non scala.

- **Versioning senza merge**: SK ↔ PERBAIKAN linkati ma non fusi generano duplicati logici; serve un record master con puntatore all’ultima versione verificata.

**Verdetto sulla tensione chiave**

L’orchestratore deterministico a stadi con tool ristretti (≤5 per stadio) è **nettamente superiore** all’alternativa multi-agente. Multipli agenti dialoganti introdurrebbero non-determinismo, loop incontrollati, costi imprevedibili e difficoltà di audit, mentre la pipeline composta segue le best practice SOTA per intake documentale governato da regole e soglie di confidenza, garantendo tracciabilità, idempotenza e bassa latenza.

---

### B.2 — Codex GPT-5.5

Verdetto: tieni 1 orchestratore deterministico. Multi-agent dialogante solo come red-team offline/simulazione, mai come runtime controller. Per PII locale, audit, replay, idempotenza e commit post-verify, lo swarm aumenta entropia: doppie decisioni, tool leakage, conflitti di stato, spiegazioni non riproducibili.

Flaws/rischi principali:

- Dedup byte SHA-256 non basta: stesso documento ricompresso/scansionato sfugge; stesso byte puo essere legittimo per piu pratiche/clienti. Serve \`blob_hash\` + \`normalized_text_hash\` + \`visual/phash\` + tabella \`document_instances\` per source/client/workflow.
- Stato coda: \`pending->ocr...\` manca claim atomico, lease timeout, retry budget, poison-pill, crash recovery e exactly-once routing. Ogni stage deve scrivere output versionato e idempotency key.
- OCR prima/dopo dedup: dedup solo pre-OCR perde duplicati semantici; dedup post-OCR rischia PII retention. Retention policy e encrypted local store obbligatori.
- Classify CoT locale: non salvare CoT grezzo con PII. Salva solo rationale strutturato/minimo, confidence, model/version/hash.
- HITL 0.60 fisso: per NPWP/NIB/KITAS meglio soglie per campo/doc_type; documenti fiscali e legal entity sotto-soglia piu conservativi.
- Entity resolution: phone E.164 puo essere agente/familiare/consultant, non cliente. Nome Jaro-Winkler senza data nascita/passport country genera false merge. Default: link candidate, non attach.
- Versioning SK/PERBAIKAN: bene non fonderli, ma serve stato di supersession/validity period e conflitto tra versioni.
- Route queue: definire \`verify\` come firma umana + diff campi + evidence pointer, non solo stato.

Scelta chiave: orchestratore deterministico con 4 stage ristretti. Gli agenti multipli possono produrre review concorrenti, ma il commit path deve restare singolo, serializzato e replayabile.

---

## C. Sintesi findings convergenti

I due panelist convergono fortemente. Findings ordinati per criticita:

**C1 — Dedup SHA-256 byte e insufficiente (CONVERGENTE, P0).**
Entrambi: lhash dei byte non cattura ricompressioni/ri-scansioni dello stesso documento (duplicato semantico sfugge) e, viceversa, lo stesso blob puo essere legittimo per piu pratiche/clienti. Inoltre (DeepSeek) un doc in stato \`dead\` con stesso hash viene scartato in silenzio, bloccando il ri-OCR dopo un upgrade modello. Fix: chiave composta \`blob_hash\` + \`normalized_text_hash\` + \`phash\` (visivo) + tabella \`document_instances\` (per source/client/workflow) + chiave dedup che include la **versione pipeline** per permettere riprocessamento.

**C2 — Coda priva di semantica exactly-once (CONVERGENTE, P0).**
Codex: mancano claim atomico, lease/visibility-timeout, retry budget, poison-pill/DLQ, crash recovery, idempotency key per-stage. DeepSeek: manca coda di retry per errori transitori (OCR, Drive, Zoho) + circuit breaker; il consumer WhatsApp single-process sul Pro e SPOF e non scala. Fix: \`FOR UPDATE SKIP LOCKED\` + lease-timeout + retry budget + dead-state esplicito + ogni stage scrive output versionato con idempotency key.

**C3 — HITL gate a soglia fissa documento-level e sbagliato (CONVERGENTE, P1).**
Entrambi: 0.60 globale manda in review lintero documento per un singolo campo basso (collo di bottiglia). Fix: soglia **per-campo e per-doc_type**, validando automaticamente i campi sopra-soglia; soglie piu conservative per NPWP/NIB/KITAS e documenti fiscali/legal-entity.

**C4 — Entity resolution ad alto rischio di false-merge (CONVERGENTE, P1).**
Entrambi: E.164 senza normalizzazione robusta (prefisso +62 mancante, spazi) fallisce; il phone puo appartenere ad agente/familiare/consultant, non al cliente. Jaro-Winkler sul solo nome (senza data nascita / passport country / blocco per doc_type) fonde clienti omonimi (Wayan/Made comunissimi a Bali). Fix: default **link-candidate, mai auto-attach**; aggiungere data di nascita + nazionalita passaporto come discriminanti; passaporto/KITAS con strip+normalize.

**C5 — Versioning SK/PERBAIKAN incompleto (CONVERGENTE, P2).**
Entrambi approvano il non-fondere, ma serve stato di **supersession / validity-period** + record master con puntatore allultima versione verificata + gestione conflitto tra versioni.

**C6 — PII retention nei sottoprodotti (solo Codex, P1).**
Non salvare il CoT grezzo del classify (contiene PII); persistere solo rationale strutturato minimo + confidence + model/version/hash. Dedup post-OCR e retention policy + store locale cifrato obbligatori.

**C7 — Definizione di \`verify\` (solo Codex, P2).**
Il gate \`verify\` non e solo uno stato: deve essere firma umana + diff dei campi + evidence pointer.

---

## D. Verdetto sulla TENSIONE CHIAVE (orchestratore vs agenti)

**Unanime (2/2): UN orchestratore deterministico con 4 stadi a tool ristretti.**

- **DeepSeek**: lorchestratore deterministico e *nettamente superiore*; gli agenti
  dialoganti introducono non-determinismo, loop incontrollati, costi imprevedibili e
  difficolta di audit. La pipeline a regole+soglie segue le best-practice SOTA per
  intake documentale governato, garantendo tracciabilita, idempotenza, bassa latenza.
- **Codex**: *tieni 1 orchestratore deterministico*. Multi-agent dialogante SOLO come
  red-team offline/simulazione, **mai come runtime controller**. Per PII locale, audit,
  replay, idempotenza e commit post-verify lo swarm aumenta lentropia (doppie decisioni,
  tool leakage, conflitti di stato, spiegazioni non riproducibili). Il **commit path deve
  restare singolo, serializzato e replayabile**.

**Conclusione**: la raccomandazione SOTA della proposta (1 orchestratore deterministico,
stadi <=5 tool, no swarm) e confermata da entrambi i panelist senza riserve. La sfumatura
aggiunta da Codex: agenti multipli sono ammessi solo *fuori dal hot-path* (es. review
concorrenti, red-team) ma il path di commit resta singolo e serializzato — coerente con
laudit-agent append-only gia previsto in proposta. La vera fragilita NON e la scelta
orchestratore (corretta) ma i **dettagli di idempotenza** (C1/C2) e **entity-resolution**
(C4), che vanno irrobustiti prima del build.
