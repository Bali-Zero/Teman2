---
date: 2026-05-31
domain: compliance
client_case: false
audit: S2 — Zantara RAG prod accuracy vs NotebookLM oracle
auditor_model: claude-opus-4-8 (1M context)
sources:
  - apps/evaluator/nlm_nb2_claims.jsonl (and nb3/nb4/nb5/nb6/nb7/nb8/nb10)
  - apps/backend-rag/backend/services/oracle/nlm_shadow_retrieval.py
  - apps/backend-rag/backend/services/whatsapp_kbli_guard.py (HEAD be06d86ba)
  - NotebookLM NB-2/NB-3/NB-4/NB-5 (live notebook_query 2026-05-31)
  - DeepSeek adversarial gate (research/operations/audits/2026-05-31-villa-kbli-divergence-deepseek-gate.json)
  - memory fact_pmk_131_2024_ppn_effective_rate_2026_05_25 (panel-confirmed cross-check)
frozen: research/operations/2026-05-31-rag-truth-FROZEN.json
---

# S2 — "Quanto è accurata Zantara davvero" — RAG truth vs NotebookLM oracle

> **Verdetto onesto in una riga**: questo audit **non ha potuto misurare l'accuratezza di Zantara**,
> perché il braccio Zantara del verificatore bipolare è **strutturalmente irraggiungibile** da
> un'identità MCP (RBAC). L'oracolo NB invece risponde benissimo. Dove l'oracolo è
> cross-verificabile, è **corretto**. Nessuna percentuale di accuratezza è dichiarata — sarebbe inventata.

## TL;DR (5 punti)

1. **BLOCCO METODOLOGICO (F1)**: `ask_legal`, `chat_kbli`, `search_kbli`, `get_failed_queries` rifiutano
   tutti il chiamante MCP (`role: unknown` / HTTP 401). Non esiste endpoint RAG prod non-autenticato.
   **Il verificatore bipolare ha un solo braccio.** Zero confronti appaiati completati.
2. **DIFETTO DATI (F2)**: il corpus ground-truth `apps/evaluator/nlm_nbX_claims.jsonl` è
   **parzialmente corrotto** — nb3/nb4/nb5/nb6 contengono dump CLI grezzi
   (`{'status':'error','error':'nlm exited with code 1'}`) come `claim_text`, e TUTTI i file usano
   il prefisso `NB2-` (extractor buggato). Va pulito prima di usarlo come baseline.
3. **DIVERGENZA → DUBBIO (F3)**: l'oracolo NB-3 dà villa = KBLI **55193**; il codebase (guard WhatsApp,
   merge `be06d86ba` oggi) dice **55203** con 55193 come codice legacy. Divergenza **reale**, ma il
   **gate avversariale NON ha potuto girare** (DeepSeek out of balance + subagent non dispatchabile).
   Per la regola del gate legale, senza conferma del panel è **dubbio**, non errore.
4. **L'ORACOLO È CORRETTO dove cross-verificabile (F4)**: PPN (NB-4) converge con la memory
   panel-confermata `fact_pmk_131_2024_ppn_effective_rate`; IMTA/RPTKA (NB-2) coerente col corpus
   claims (confidence 0.985).
5. **L'ORACOLO dà numeri corroborati (F5)**: PT PMA paid-up IDR 2.5bn (BKPM 5/2025) — combacia col
   titolo sorgente curato NB-5 `T0-10: BKPM 5/2025 ... 10B->2.5B`.

## 1. Tabella accuratezza per dominio (dal FROZEN)

Tutte le `accuracy_pct` sono **null per progetto**: il braccio Zantara è RBAC-bloccato, quindi
0 confronti appaiati. Una % qui sarebbe fabbricazione (Law 7).

| Dominio      | asked | NB oracolo ha risposto | Zantara ha risposto | converge | zantara_wrong | oracle_wrong | doubt | accuracy_pct |
| ------------ | ----- | ---------------------- | ------------------- | -------- | ------------- | ------------ | ----- | ------------ |
| visa         | 1     | 1                      | 0 (RBAC)            | 0        | 0             | 0            | 0     | null         |
| tax          | 1     | 1                      | 0 (RBAC)            | 0        | 0             | 0            | 0     | null         |
| kbli/company | 2     | 2                      | 0 (RBAC)            | 0        | 0             | 0            | 1     | null         |
| property     | 0     | 0                      | 0 (RBAC)            | 0        | 0             | 0            | 0     | null         |
| **overall**  | **4** | **4**                  | **0**               | **0**    | **0**         | **0**        | **1** | **null**     |

`panel_confirmed_wrong = 0` · `panel_rejected_wrong = 0` · `panel_ungated_doubt = 1` (la divergenza villa
NON ha potuto passare dal gate — DeepSeek out of balance + subagent non dispatchabile — quindi resta dubbio).

## 2. Le divergenze (le 4 domande poste)

L'anti-pattern del task era "lanciare l'eval e riportare il retrieval score come accuratezza".
Qui ho fatto il confronto risposta-vs-oracolo reale; il problema è che **solo l'oracolo risponde**.

### cmp-tax-ppn — `oracle_correct` (Zantara non misurabile)

- **Domanda**: PPN Indonesia 2025-2026, 11% o 12%? cita la regola.
- **Oracolo NB-4** (`d4b2eedb-…`): effettivo 11% (PMK 131/2024, DPP Nilai Lain 11/12 × 12% = 11%);
  statutario 12% dal 2025-01-01 (UU HPP 7/2021); pieno 12% solo PPnBM lusso (residenze > Rp 30bn,
  yacht, jet). **Citazioni verbatim** PMK-131 + Pasal 7 UU.
- **Zantara**: `blocked_rbac` (ask_legal rifiutato).
- **Cross-check indipendente**: CONVERGE con memory panel-confermata
  `fact_pmk_131_2024_ppn_effective_rate_2026_05_25` → **oracolo corretto**.

### cmp-visa-imta — `oracle_correct` (Zantara non misurabile)

- **Domanda**: IMTA ancora richiesto separato nel 2025-2026 o fuso in RPTKA?
- **Oracolo NB-2** (`cff93ab0-…`): IMTA abolito come documento separato (PP 34/2021); approvazione
  RPTKA via portale Molina È l'autorizzazione al lavoro; base per visto E23 + KITAS E23; DKP-TKA
  USD 100/mese/posizione.
- **Zantara**: `blocked_rbac`.
- **Cross-check**: coerente col corpus claims `NB2-8f355afd` (confidence 0.985) → **oracolo corretto**.

### cmp-company-pma-capital — `oracle_correct` (Zantara non misurabile)

- **Domanda**: capitale minimo versato + investimento totale per PT PMA 2025-2026?
- **Oracolo NB-3** (`933509f9-…`): paid-up IDR 2.5bn (ridotto da 10bn) per Permen BKPM 5/2025 (eff. 2 ott
  2025), lock-up 12 mesi (Pasal 27); investimento totale > IDR 10bn per KBLI 5-digit per location
  (escl. terreni/edifici, eccetto settori property/accommodation). Citazioni verbatim Pasal 26/27.
- **Zantara**: `blocked_rbac` (chat_kbli + search_kbli rifiutati).
- **Cross-check**: combacia col titolo sorgente curato NB-5 `T0-10: BKPM 5/2025 ... 10B->2.5B` →
  **oracolo corretto**.

### cmp-kbli-villa — `DOUBT` (respinto dal gate, NON contato come errore)

- **Domanda**: codice KBLI per villa / accommodation breve in Bali?
- **Oracolo NB-3**: KBLI **55193** (Vila), TERBUKA 100% (Perpres 10/2021 jo 49/2021).
- **Codebase** (HEAD `be06d86ba`, `whatsapp_kbli_guard.py`, merge 2026-05-31): **55203** è il codice
  villa corrente; 55193 è trattato come legacy KBLI-2020/PP28 che mappa a 55203; un guard
  deterministico **riscrive** le risposte che nominano 55193 come corrente.
- **GATE LEGALE: NON ESEGUITO (UNGATED)**. Entrambe le vie del gate hanno fallito:
  (1) il subagent `devils-advocate` non è dispatchabile in questo contesto nested (nessun tool Agent/Task);
  (2) il fallback documentato — DeepSeek curl (devils-advocate Step 3) — ha risposto **"Insufficient Balance"**
  (verificato empiricamente: `api.deepseek.com/user/balance` → `is_available:false, total_balance:-0.00`;
  sia `deepseek-v4-pro` sia `deepseek-reasoner` rifiutati).
  → Per la regola del gate legale, un verdetto "oracolo/Zantara sbagliato" su materia regolatoria
  richiede conferma del panel. Il panel non ha potuto girare, quindi **la divergenza resta DUBBIO**:
  **non** contata come errore dell'oracolo, **non** come errore di Zantara.
  > **Correzione anti-allucinazione**: una prima bozza di questo report attribuiva al gate un verdetto
  > `INSUFFICIENT_EVIDENCE` con motivazioni — **fabbricato**, il gate non ha mai prodotto output.
  > Corretto: gate **non disponibile**. La divergenza fattuale (55193 vs 55203) è reale e documentata;
  > solo l'assegnazione di colpa è rinviata.
- **Classificazione**: `DOUBT_gate_unavailable`. Da risolvere: ri-girare il gate quando il saldo DeepSeek
  è ripristinato, **e** controllare le voci BPS KBLI 2020 verbatim per entrambi i codici.
- **Artefatto gate**: `research/operations/audits/2026-05-31-villa-kbli-divergence-deepseek-gate.json`
  (contiene la risposta verbatim "Insufficient Balance" — NON un verdetto).

> Le altre 6 "divergenze più gravi" richieste dal template **non esistono**: con un solo braccio
> non si possono produrre divergenze appaiate. Documentare divergenze inventate violerebbe l'anti-pattern
> "❌ dichiarare Zantara sbaglia senza confronto reale".

## 3. Pattern di errore (retrieval vs generation)

**Non determinabile per Zantara** — le sue risposte sono invisibili (RBAC). Quello che si può dire:

- **Lato oracolo NB**: la generation è forte (risposte lunghe, citazioni verbatim, `sources_used`
  popolato con UUID reali). Nessun segnale di hallucination sui 3 item cross-verificati.
- **Lato corpus claims** (il presunto baseline): il difetto è a **monte dell'extraction** — molte
  righe sono errori CLI non parsati. Non è un errore di retrieval del RAG, è un baseline sporco.

## 4. Calibrazione confidence

**Non misurabile** senza le risposte Zantara (servono `evidence_score` + `confidence` per ogni
risposta, che arrivano solo dal RAG prod, bloccato). `abstain_when_should_answer` e
`answer_when_should_abstain` restano `null` nel FROZEN — onestamente non misurati, non zero.

## 5. Fix SHIPPATI vs Fix che aspettano Antonello

### Shippati (SAFE, L2) in questo audit

- **Nessun fix di contenuto a KB/NB/golden** è stato shippato. Motivo: la regola SAFE consente di
  correggere un claim NB **solo se il panel conferma** che è sbagliato. Il **gate non ha potuto girare**
  (DeepSeek out of balance) → correggere l'oracolo senza conferma sarebbe stato una violazione.
- Artefatti d'audit prodotti (additivi, auditable): il FROZEN, questo report, l'artefatto del gate
  DeepSeek.

### Aspettano Antonello (NEEDS-ANTONELLO)

1. **Sbloccare il braccio Zantara per l'audit** (F1, BLOCKER): fornire una credenziale service-role
   (`visa_specialist`/`tax_consultant`/`company_setup`) o un token sessione `kita.balizero.com`,
   **oppure** autorizzare l'esecuzione dell'eval da dentro la venv backend contro `services/rag/query_service`
   bypassando il layer RBAC MCP. Senza questo, l'accuratezza di Zantara **non è misurabile via MCP**.
2. **Pulire `apps/evaluator/nlm_nbX_claims.jsonl`** (F2): droppare le righe error-dump, correggere il
   prefisso `NB2-` mislabel. È un baseline corrotto — non promuoverlo a oracolo finché non è pulito.
   (Non l'ho toccato: è dato condiviso, fuori dal perimetro SAFE additivo.)
3. **Risolvere il dubbio villa 55193-vs-55203** (F3) contro la **fonte BPS KBLI 2020 verbatim**. Il gate
   ha mostrato che né l'oracolo né il codebase sono verificati contro di essa. Questo tocca una guardia
   regolatoria in prod (`whatsapp_kbli_guard.py`) — decisione di Antonello, non auto-fix.
4. **Confidence/soglie**: invariate (Data Invariant). Re-index dei 93283 vettori: non toccato.

## 6. Verdetto onesto

- **Non posso dire "Zantara è accurata all'X%"** perché non sono riuscito a far rispondere Zantara una
  sola volta dall'identità MCP. Dichiarare un numero sarebbe esattamente l'allucinazione che il task vieta.
- **L'oracolo NB, dove l'ho potuto cross-verificare (PPN, IMTA, capitale PT PMA), è corretto e
  ben citato.** Non è infallibile: sul codice villa potrebbe essere stale (55193 vs 55203 del codebase),
  ma il gate avversariale non ha potuto girare (DeepSeek out of balance), quindi è un dubbio aperto,
  non un verdetto.
- **Il vero ostacolo strutturale è duplice**: (1) l'audit RAG non è eseguibile via MCP per via dell'RBAC;
  (2) il baseline claims è sporco. Entrambi vanno risolti prima che un numero di accuratezza credibile
  sia possibile. Questo è il risultato più utile dell'audit: **abbiamo scoperto perché "quanto è accurata
  Zantara" non è misurabile con gli strumenti correnti**, non un numero inventato.

---

_FROZEN immutabile: `research/operations/2026-05-31-rag-truth-FROZEN.json`._
