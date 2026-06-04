---
date: 2026-06-04
domain: operations/agent-craft
sources: NB-AGENTS (6d449787, 157 sources), proposed-agents spec files (worktree s13-guard)
generated_by: nb-curator
---

# NB Patterns — Document Intake Unified System
## Ground-truth da NB-AGENTS + analisi spec agenti proposti

---

## 1. NB-AGENTS: Pattern confermati per pipeline multi-stadio

### 1.1 Agente vs Funzione per stadio (CONFERMATO con correzione)

**NB-AGENTS ground-truth** (citazioni 1-5, 27 fonti):

> "Use deterministic functions for routing and validation, and reserve agents exclusively for cognitive tasks."

Applicazione agli stadi proposti (classify / extract / validate / route):

| Stadio | Tipo raccomandato | Perché |
|---|---|---|
| **Classify** | Agente (LLM) | Richiede giudizio visivo + testo — input ambiguo, chiuso set noto (8 tipi) |
| **Extract** | Agente (LLM locale) | Parsing contestuale, multi-pagina, confidence per campo |
| **Validate** | **Funzione deterministica** | Invariants (NIK 16 cifre, modal ≥ threshold, KBLI chiuso) — milliseconds, audit log, identico ogni run |
| **Route** | **Funzione deterministica** | Routing basato su tipo classificato + business rules statiche — MAI LLM |

**Correzione architetturale**: l'architettura proposta (1 orchestratore + 4 stadi tutti "agenti") va raffinata — Validate e Route dovrebbero essere **validator scripts** (Python/shell deterministic), non subagent LLM. Il NB cita esplicitamente: "Validators are code, not prose" e "shift from governance-as-approval to governance-as-code."

### 1.2 HITL Gate pattern (CONFERMATO con schema preciso)

NB-AGENTS descrive la struttura pull-based queue derivata dallo spec WR2 (citazione 12, 14, 15):

```
State machine: drafted → [adversarial_gate] → needs_human_edit | reviewed → published | rejected | ignored
```

**Regole chiave confermate**:
- **Pull-based, non push**: il sistema scrive in una queue JSON; il reviewer (Adit/Ari/Surya) apre quando pronto. MAI Telegram autonomo al reviewer.
- **Max retry = 2** prima di `needs_human_edit` — non loop infiniti.
- **Adversarial gate pre-HITL**: prima che il documento vada all'umano, un "devil's advocate" subagent cerca falle (per doc intake: OCR low-confidence, field mismatch, statutory threshold). Blocca se trova critical.
- **`ignored` NON è segnale di apprendimento** — potrebbe essere "reviewer occupato" non "documento cattivo".
- **Schema campi obbligatori**: `needs_human_edit_reason`, `retry_count`, `critic_report`, `flagged_at`.

### 1.3 Idempotency + Dedup (CONFERMATO)

NB-AGENTS cita il pattern del sistema escalations (citazione 17) come riferimento esatto:

- **`INSERT OR IGNORE` / upsert** a livello database: re-run della stessa pipeline → stesso stato finale, zero duplicati. Implementato in `events_outbox` e `escalations.sqlite` con `INSERT OR IGNORE`.
- **Dedup euristico prima degli LLM** (citazione 16): URL canonical + Levenshtein ≤ 3 sul titolo. Costa ~$0, LLM semantic query per similarità è anti-pattern (costo alto, non necessario).
- **Idempotenza come hard rule** (citazione 18, 19): "same input → same output, no random-walk drift = bug". Il pipeline deve essere deterministico a parità di input.
- **Content-hash per file immagini**: corollario non citato esplicitamente ma derivabile — hash SHA256 del file binario come chiave di dedup prima di invocare OCR (evita re-OCR dello stesso documento).

### 1.4 Anti-pattern confermati (CRITICI)

| Anti-pattern | Evidenza NB-AGENTS | Impatto |
|---|---|---|
| **Peer-to-peer subagent handoff** | "Never let subagents communicate directly peer-to-peer. Decentralized topologies amplify errors 17.2×" (cit. 2, 7, 8) | Pipeline rompe su ogni errore intermedio |
| **Over-orchestration di pipeline sequenziale** | "Sequential tasks perform up to 70% worse when over-orchestrated" (cit. 1, 2) | Overhead senza beneficio se il flow è A→B→C lineare |
| **Tool output hallucination** | "Agents fall into trap of remembering document contents from context window rather than invoking a read tool" (cit. 21, 22) | Estrazione basata su testo inventato, non OCR reale |
| **Brief stale premise** | "Orchestrator must run mandatory empirical pre-brief sweep" (cit. 23-25) | 4 incidenti in 24h con halt — verificare stato reale prima di dispatch |
| **Race condition su shared dir** | "Multiple agents in shared directory overwrite files" (cit. 26, 27) — worktree isolation fix | Intake JSON sovrascritto da run parallelo |

---

## 2. NB-1 (Codebase/Arch): Non raggiungibile

Query su NB-1 (UUID f6ecd115) ha restituito `NOT_FOUND`. UUID potrebbe essere parziale nel routing table. Backup NB-9 Research Lab anch'esso NOT_FOUND. **Gap**: pattern da codebase nativa (events_outbox, migration_manager, outbox.py) erano invece citati indirettamente da NB-AGENTS via la sua fonte NB-1 capture — i pattern idempotenza di cui sopra (INSERT OR IGNORE, outbox drain) sono già stati estratti con citazioni.

---

## 3. Agenti proposti: Cosa riusare

### 3.1 `document-intake-classifier` — **CUORE del sistema, riusare integralmente**

Spec completo e production-ready. Punti chiave riusabili:
- **PII boundary esplicita e verificata**: cloud OCR (Gemini tier in `ocr_dispatcher_service.py`) è anti-reference esplicito. `qwen2.5vl:7b` locale ONLY via `ollama_client.py` diretto.
- **Document type catalog** (8 tipi + `unknown`): chiuso e completo per il dominio Bali Zero.
- **Confidence threshold 0.60**: coerente con CLAUDE.md evidence scoring (`<0.15` ABSTAIN, `0.15-0.60` CAUTIOUS, `>0.60` NORMAL).
- **OCR-all-pages come hard rule**: direksi page 2-3 akta — già in spec.
- **Output**: intake JSON + Telegram digest PII-masked. Questo è esattamente il formato "review queue item" che il HITL gate consuma.

**Cosa aggiungere** per il sistema unificato: campo `source_channel` (whatsapp / drive / email) e `content_hash` per dedup upstream.

### 3.2 `client-onboarding-orchestrator` — **Orchestratore di SECONDO livello, non del sistema intake**

Riusabile per la fase post-intake (da "docs classif icati" a "onboarding completo"). NON è l'orchestratore del pipeline di intake stesso — è il workflow di business che consuma l'output dell'intake.

Logica riusabile:
- **Checklist-as-state**: ogni onboarding è un file JSON con step `pending/done/blocked/needs_review`. Pattern applicabile anche all'intake queue (ogni documento è un item con stato).
- **Handoff chain**: dispatch `document-intake-classifier` → consuma intake JSON → dispatch `compliance-deadline-sentinel`. Questo è esattamente il pattern "orchestratore chiama worker, worker ritorna JSON strutturato, orchestratore avanza stato."
- **`blocked_by[]` + `missing[]` explicitness**: ogni blocco ha una lista esplicita di cosa manca — riusabile per il HITL gate ("review pending because: type_confidence < 0.60 on field X").

**Non sovrapporre**: questo agente non va confuso con l'intake orchestrator — opera su scala cliente (giorni/settimane), non su scala documento (secondi/minuti).

### 3.3 `company-docs-consistency-auditor` — **Stadio VALIDATE specializzato, riusare come plugin**

Questo è la materializzazione del pattern "validator script" citato da NB-AGENTS — ma implementato come agente LLM (Opus) perché i check K2/K3 richiedono grounding normativo (Perpres DPI, PP 5/2021), non solo invarianti deterministici.

**Distinzione critica** dall'architettura proposta:
- I check K1/K4/K5/K6 (name match, director match, domicile) = **funzioni deterministiche** (string comparison, set diff). Possono essere validator scripts.
- I check K2/K3/K7/K8 (modal threshold, KBLI PMA eligibility, tax coherence) = **agente LLM** perché richiedono lookup normativo contestuale.

Questo suggerisce che lo stadio `validate` del sistema unificato è **ibrido**: prima validator scripts (fast, $0, deterministic) → poi agente specializzato per i check normativi se il documento è di tipo `akta_pendirian` o `nib`.

**Anti-pattern in spec**: l'agente chiama DeepSeek per math arrears (OK per de-identified numbers). Il sistema unificato deve propagare questo pattern: math su soli numeri anonimizzati, mai identità cliente a LLM cloud.

---

## 4. Verdetto architetturale

### CONFERMATO dall'NB:
- Orchestratore centrale con subagent stateless (NON peer-to-peer) — il pattern è consolidato e ben documentato con metriche di errore (17.2× amplification su decentralized).
- HITL gate pull-based con state machine esplicita — non chat interrupt.
- Idempotency via DB upsert + content hash — già implementato in codebase (events_outbox pattern riusabile).

### CORREZIONE suggerita dall'NB:
- **Stadio Validate NON è un agente LLM uniforme** — split in: (a) validator scripts deterministic per invarianti (NIK length, name match, presence check) e (b) agente normativo per check legali (KBLI, modal, DPI). Riduce costo e aumenta affidabilità.
- **Stadio Route è una funzione, non un agente** — routing table statica (tipo documento → destinazione ops) non giustifica LLM.
- **Dedup avviene PRIMA di OCR**, non dopo — content hash del file binario come gate di ingresso, prima di invocare qwen2.5vl.

### ANTI-PATTERN critico da evitare nel design:
Il rischio più alto identificato da NB-AGENTS per questo specifico sistema è il **"tool output hallucination"** durante l'estrazione: l'agente "ricorda" il contenuto del documento dal context window invece di re-invocare il tool OCR. Il validator post-extract deve verificare che ogni campo estratto abbia un `source_page` reale e una `confidence` da OCR call live, non da contex buffer.

---

## 5. Spec agenti esistenti riusabili — mappa

| Componente sistema unificato | Agente/modulo riusare | Come |
|---|---|---|
| Ingestion + OCR + Classify | `document-intake-classifier` | Integralmente, aggiungere `source_channel` + `content_hash` |
| Validate normativi (akta/NIB) | `company-docs-consistency-auditor` | Come plugin opzionale post-classify per tipi `akta_pendirian`/`nib` |
| Validate invarianti | Nuovo validator script | Funzione Python deterministica (K1/K4/K5/K6 equivalenti) |
| HITL queue | Pattern da WR2 queue schema | `human-review-queue.json` con state machine — stesso schema |
| Business onboarding workflow | `client-onboarding-orchestrator` | Consumatore dell'intake output, non parte del pipeline stesso |
| Compliance clock post-intake | `compliance-deadline-sentinel` | Triggered da onboarding orchestrator, non da intake direttamente |

