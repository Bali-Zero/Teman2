---
date: 2026-06-04
domain: operations/agent-craft
sources: NB-AGENTS (6d449787, 157 sources), proposed-agents spec files (worktree s13-guard)
generated_by: nb-curator
adversarial_review: codex
adversarial_review_note: "Key added 2026-08-02. Scope = the 2026-08-02 RETRACTED 17.2x citation ONLY (see the Adversarial review section at the end). The 2026-06-04 body is a dated record and was NOT re-reviewed."
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
| **Peer-to-peer subagent handoff** | ~~"Never let subagents communicate directly peer-to-peer. Decentralized topologies amplify errors 17.2×" (cit. 2, 7, 8)~~ ⚠️ **CITAZIONE RITIRATA 2026-08-02** — vedi §1.4-nota | Pipeline rompe su ogni errore intermedio |
| **Over-orchestration di pipeline sequenziale** | "Sequential tasks perform up to 70% worse when over-orchestrated" (cit. 1, 2) | Overhead senza beneficio se il flow è A→B→C lineare |
| **Tool output hallucination** | "Agents fall into trap of remembering document contents from context window rather than invoking a read tool" (cit. 21, 22) | Estrazione basata su testo inventato, non OCR reale |
| **Brief stale premise** | "Orchestrator must run mandatory empirical pre-brief sweep" (cit. 23-25) | 4 incidenti in 24h con halt — verificare stato reale prima di dispatch |
| **Race condition su shared dir** | "Multiple agents in shared directory overwrite files" (cit. 26, 27) — worktree isolation fix | Intake JSON sovrascritto da run parallelo |

> **§1.4-nota — CITAZIONE RITIRATA 2026-08-02 (l'anti-pattern resta, la sua evidenza no).** Verificato
> alla fonte su arXiv:2512.08296v3: il **17.2× è di `Independent`**, che il paper (§3.1) definisce come
> agenti paralleli con `Ω=synthesis_only`, cioè **senza alcun coordinamento**. Il peer-to-peer è
> `Decentralized` (`C={(aᵢ,aⱼ):∀i,j,i≠j}`, debate rounds, consenso) e **non** è la topologia misurata
> peggio. La riga qui sopra attribuisce a Decentralized un numero che non gli appartiene — ed è la
> forma più netta dell'errore, perché da qui è passata in `05-final-spec.md` come motivazione del
> "no swarm". In più il paper, dopo i controlli, **non trova supporto statisticamente significativo**
> per l'amplificazione d'errore come meccanismo (Table 4: β̂=0.014, CI [−0.047, 0.074], p=0.658;
> interazione β̂=0.022, CI [−0.023, 0.067], p=0.332) e attribuisce il divario fra architetture a
> _"efficiency (Ec) and overhead (O%), rather than error propagation per se"_. p=0.658 = **non
> supportato**, non "smentito".
>
> **Cosa resta in piedi**: l'anti-pattern «orchestratore centrale, subagent stateless, niente handoff
> peer-to-peer» è una **scelta di questo repo** (isolamento di contesto, un solo proprietario dello
> stato, auditabilità) e regge da sola. **Non ripristinare la citazione — in nessuna forma,
> nemmeno indebolita.** ⚠️ Terza generazione dell'errore (2026-08-02): una stesura precedente di
> questa stessa nota ripiegava su «ma il paper comunque ranka Centralized sopra Independent».
> È vero come coppia (0.463 > 0.370) ed è **irrilevante** qui: `Independent` non è peer-to-peer.
> Il peer-to-peer del paper è `Decentralized`, che sulla Table 5 Success Rate: `Decentralized 0.477 > SAS 0.466 > Centralized 0.463 > Hybrid 0.452 > Independent 0.370`
> è il **PIÙ ALTO**, e il paper scrive _"no single architecture dominates"_. Questo paper non
> sostiene la regola no-peer in nessun verso.

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
- Orchestratore centrale con subagent stateless (NON peer-to-peer) — ~~il pattern è consolidato e ben documentato con metriche di errore (17.2× amplification su decentralized)~~ ⚠️ **la parte fra tilde è RITIRATA 2026-08-02**: il 17.2× è di `Independent` (nessun coordinamento), non di `Decentralized` (peer-to-peer), e il paper non lo sostiene come meccanismo causale — vedi §1.4-nota. **Il verdetto resta**, su basi di repo (isolamento di contesto, un solo proprietario dello stato) **e solo su quelle** — il ranking del paper NON lo sostiene: il suo peer-to-peer (`Decentralized`) è il più alto in Table 5 Success Rate: `Decentralized 0.477 > SAS 0.466 > Centralized 0.463 > Hybrid 0.452 > Independent 0.370`.
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

---

## Adversarial review

**Scope**: the **2026-08-02 retraction of the 17.2× citation only** (the §1.4 anti-pattern row and the §4 verdict line). The 2026-06-04 body is a dated record and was not re-reviewed — this key does not certify it.

**Seat**: Codex `gpt-5.6-sol`, effort `xhigh`, fresh context, read-only, cross-family (generator = Claude Opus 5; grader ≠ generator).

**How this file got here**: it was not in the original scope. The reviewer falsified the claim that only *live agent surfaces* still carried the citation, by pointing at `00-INDEX.md` — which calls `05-final-spec.md` a **"SPEC FINALE ESEGUIBILE"** a dev/agent builds from, and `05c-nb-patterns.md` its **ground truth**. Neither is archaeology, so both are corrected rather than ledgered.

**What was wrong** — the claim is RETRACTED; do not restore it (verified at source on arXiv:2512.08296v3, §3.1 / §4.3 / Table 4):

1. **Wrong topology.** 17.2× measures `Independent` (§3.1: parallel, `Ω=synthesis_only`, *no coordination*). Peer-to-peer is `Decentralized` (`C={(aᵢ,aⱼ):∀i,j,i≠j}`, debate rounds, consensus) and is **not** ranked worst. `05c` asserted the number *of* Decentralized — the conflation in its purest form, and the route by which it became the spec's "no swarm" rationale.
2. **Unsupported as a cause.** §4.3 narrates error propagation; Table 4 of the same paper reports β̂=0.014, CI [−0.047, 0.074], p=0.658 (interaction β̂=0.022, CI [−0.023, 0.067], p=0.332) and §4.3 concludes the gap is better explained by *"efficiency (Ec) and overhead (O%), rather than error propagation per se"*. **p=0.658 = unsupported, not disproved.**

**What did NOT change**: the architectural decision (central orchestrator, stateless subagents, no swarm). It stands on repo grounds — context isolation, one auditable state owner — **and on those alone**. ⚠️ 2026-08-02, third generation: this line first read "plus the paper's benchmark ranking (`Centralized` > `Independent`)". That pair is true (0.463 > 0.370) and irrelevant — `Independent` is not peer-to-peer. Table 5 Success Rate: `Decentralized 0.477 > SAS 0.466 > Centralized 0.463 > Hybrid 0.452 > Independent 0.370`; peer-to-peer is `Decentralized`, the HIGHEST, and the paper states *"no single architecture dominates"*. The paper supports this rule in neither direction. Only the citation was withdrawn.

**Limits**: the reviewer had no internet access and could not check the paper itself; the §3.1/§4.3/Table 4 quotations were fetched by the author and given to it as claims. Single seat — Kimi quota-dead, GLM unreachable on this machine at the time.
