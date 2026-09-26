---
date: 2026-06-04
domain: operations
study: doc-intake-unified
phase: 4.5 — HUMAN-IN-THE-LOOP & EVOLVER HOOK
client_case: false
sources:
  - research/operations/doc-intake-unified/03-panel-review.md   # C3 fix recepito
  - research/operations/doc-intake-unified/01d-destinations.md   # D1/D2/D3 routing target
  - apps/backend-rag/backend/app/routers/workspace_inbox.py      # CRM web precedent
  - apps/mouth/src/app/(workspace)/inbox/page.tsx                # CRM web frontend ESISTE
  - scripts/agent-library-evolver-run.sh                         # evolver hook target
  - .claude/rules/cicatrix-scars.md                              # evolver context source
---

# FASE 4.5 — Human-in-the-Loop Gate & Evolver Hook

Pezzo 5/5 del sistema document-intake unificato. Definisce **(1)** il gate dove un
umano del team verifica/corregge i campi a bassa confidenza estratti dall AI, e
**(2)** il GANCIO (oggi inesistente) con cui le correzioni umane, accumulando volume,
alimentano l evolver settimanale esistente per migliorare l agente.

Posizione nel flusso:

```
PARTE 3 (extract+validate) --> needs_review_fields[] + proposta_routing (PARTE 4)
                                          |
                                   [ 04.5 — REVIEW GATE ]
                          per-field, per-doc_type confidence gate
                           /                              \
            tutti i campi >= soglia              >=1 campo < soglia
                    |                                     |
            auto-commit routing                  REVIEW QUEUE (DB)
            (esegui PARTE 4)                      mostra SOLO i campi incerti
                                                          |
                                              umano (Adit/Ari/Surya) verifica
                                               approva / corregge i campi
                                                          |
                                          +---------------+----------------+
                                          v                                v
                              ESEGUI routing PARTE 4         REGISTRA correzione
                              (D1 CRM + D2 Drive)            (intake_corrections)
                                                                     |
                                                          [ EVOLVER HOOK — async, weekly ]
                                                          digest correzioni --> evolver
                                                          --> PROPONE prompt/regola/modello
                                                          --> draft PR (mai auto-apply)
```

---

## 0. INTERFACCE (contratto — dichiarate per primo)

### IN (da PARTE 3 + PARTE 4)
Un singolo `intake_item` arriva al gate con questa forma logica:

```jsonc
{
  "intake_id": "uuid",                  // PK coda intake (FASE 3, stato=extracted)
  "content_hash": "sha256...",          // dedup key (C1)
  "doc_type": "nib",                    // dal classify (PARTE 3)
  "source": "whatsapp|drive|zoho",
  "fields": {                           // estratto AI con confidence per-campo (C3)
    "nib_number":   { "value": "1234567890123", "confidence": 0.91 },
    "company_name": { "value": "PT BALI ZERO",  "confidence": 0.55 },
    "npwp":         { "value": "00.123...",      "confidence": 0.42 }
  },
  "needs_review_fields": ["company_name", "npwp"],  // <-- PARTE 3, gia calcolato per-field/per-doc_type
  "routing_proposal": {                 // <-- PARTE 4, NON ancora eseguito
    "d1_crm": { "client_id": 412, "client_match_method": "passport_exact",
                "client_match_score": 1.0, "practice_id": 98,
                "document_category": "pma", "document_type": "nib" },
    "d2_drive": { "folder_path": "412_PT BALI ZERO/02_Company", "rename_to": "NIB_1234567890123.pdf" }
  },
  "entity_resolution": {                // C4: link-candidate, mai auto-attach se sotto soglia
    "status": "candidate|confirmed", "candidate_client_ids": [412, 511]
  }
}
```

> **Contratto chiave**: PARTE 3 decide *quali* campi sono incerti (`needs_review_fields`,
> soglia per-campo/per-doc_type — fix C3). PARTE 4 decide *dove* andrebbe scritto
> (`routing_proposal`) ma **non scrive**. 04.5 e l unico punto che autorizza la scrittura.

### OUT (decisione umana → 2 effetti)
1. **trigger esecuzione routing** — un evento/chiamata che da il via libera a PARTE 4
   (write D1 CRM + D2 Drive) con i valori *post-verifica*.
2. **record correzione** — una riga in `intake_corrections` per ogni campo toccato
   dall umano (anche \"approvato senza modifica\" = segnale positivo). Consumato async
   dall evolver, mai nel hot-path.

```jsonc
// OUT decisione
{
  "intake_id": "uuid",
  "verdict": "approved|corrected|rejected",
  "verified_by": "adit@balizero.com",
  "verified_at": "2026-06-04T09:00:00Z",
  "final_fields": { "company_name": "PT BALI ZERO SUKSES", "npwp": "00.123.456.7-901.000" },
  "field_outcomes": [                   // -> intake_corrections (per evolver)
    { "field": "company_name", "ai_value": "PT BALI ZERO", "human_value": "PT BALI ZERO SUKSES",
      "ai_confidence": 0.55, "outcome": "corrected" },
    { "field": "npwp",         "ai_value": "00.123...",     "human_value": "00.123.456.7-901.000",
      "ai_confidence": 0.42, "outcome": "corrected" }
  ],
  "execute_routing": true               // -> trigger PARTE 4
}
```

---

## 1. REVIEW-GATE DESIGN (recepisce C3)

**Principio C3 (panel, P1)**: il gate NON e doc-level flat a 0.60. E **per-campo e
per-doc_type**. I campi sopra soglia si auto-committano; solo i campi sotto soglia
vanno in coda, e la coda mostra **quei campi**, non l intero documento.

### 1.1 Soglie per-campo/per-doc_type
Tabella di policy versionata (config, non hardcoded — coerente con MODEL_TOPOLOGY.json):

| doc_type | campo | soglia auto-commit | nota |
|---|---|---|---|
| nib | nib_number | 0.85 | regex 13-cifre valida -> bypass se cifre OK |
| npwp | npwp | 0.90 | fiscale: conservativo (panel C3) |
| kitas | kitas_index / E-code | 0.90 | legal-entity: conservativo |
| akta | modal_disetor | 0.90 | >= Rp 2,5 mld validato a regola |
| passport/ktp | nome, numero | 0.80 | PII identita |
| * (default) | * | 0.75 | |

> Regola: se una **validazione deterministica** (NIB 13 cifre, NPWP 16 cifre, modal
> >= 2,5 mld, E-code in whitelist) **passa**, il campo e auto-committabile anche con
> confidence appena sotto soglia (la regola e piu forte del modello). Se la regola
> **fallisce**, il campo va SEMPRE in review a prescindere dalla confidence. Questo
> aggancia il `validate` stage di PARTE 3 al gate.

### 1.2 Cosa entra in coda
Una `intake_item` entra in review se:
- `needs_review_fields` non vuoto (>=1 campo sotto soglia E senza regola che lo salvi), **OPPURE**
- `entity_resolution.status == \"candidate\"` (C4: client match ambiguo -> umano sceglie il cliente, mai auto-merge), **OPPURE**
- una validazione deterministica e fallita (es. NIB non-13-cifre).

Se nessuna condizione e vera -> **auto-commit**: esegui PARTE 4 senza umano, e
registra comunque un record `outcome=auto_committed` (serve all evolver come
campione negativo/baseline: \"qui NON serviva umano\").

### 1.3 Stato coda (estende la macchina-stati FASE 3)
`...extracted -> review_pending -> review_claimed -> {routed | rejected}`
- `review_claimed`: lease atomico (`FOR UPDATE SKIP LOCKED` + lease_timeout, riuso fix C2)
  cosi due reviewer non lavorano lo stesso item.
- timeout lease -> torna `review_pending`.
- `rejected` -> dead-state con motivo (non si perde, l evolver lo legge).

---

## 2. SCELTA INTERFACCIA TEAM (motivata)

Il team che verifica (Adit/Ari/Surya) **non lavora dal Pro**: Windows/telefono.
Servono raggiungerli dove gia sono. Tre opzioni valutate:

| Opz | Canale | Pro | Contro |
|---|---|---|---|
| **(a)** | Vista \"Da verificare\" nel **CRM web** kita.balizero.com | CRM web **ESISTE GIA** (apps/mouth, `(workspace)/inbox` precedent, auth+RBAC gia presenti); mostra campi editabili + anteprima doc + cliente candidato; la correzione e *strutturata* (input per-campo) -> dataset evolver pulito; nessun nuovo canale da mantenere | richiede una nuova pagina + 2 endpoint backend; team deve aprire il browser |
| (b) | **Telegram** bottoni approva/correggi | zero-friction su telefono; precedente WR2 review-gate | Telegram NON e buono per *correggere* testo per-campo (15 campi = chat illeggibile); PII in chat cloud viola Law 2 (B2: client doc fuori dal Pro); buono solo per approve binario, non per editing |
| (c) | dashboard **wa-mirror :7790** | gia esiste, locale | localhost-only sul Pro -> il team da Windows/telefono NON la raggiunge; e una vista OSINT, non un editor CRM |

### SCELTA: **(a) CRM web — vista \"Documenti da verificare\"**, motivazione:
1. **L infrastruttura esiste** (apps/mouth, auth team, RBAC `assigned_to`, pattern inbox).
   Aggiungo una pagina `(workspace)/intake-review` e 2 endpoint, non un canale nuovo.
2. **La correzione e strutturata per-campo** — esattamente la forma di cui l evolver
   ha bisogno (coppia ai_value/human_value pulita). Telegram darebbe testo libero sporco.
3. **PII-safe (Law 2 / boundary B2)**: il CRM web e gia il luogo dove i client doc
   vivono; non esce nulla verso cloud LLM. Telegram porterebbe NIK/passport in chat.
4. **RBAC riusabile**: a differenza di workspace_inbox (owner-only zero@), la review
   queue deve essere visibile al **team assegnatario** del cliente candidato
   (`verify_client_access`: team vede solo i propri clienti; admin vede tutto). Item
   con cliente ancora non risolto (C4 candidate) -> visibili agli admin (zero/asya/antonello).

**Complemento (non sostituto)**: **Telegram come notifier**, non come editor. Quando
un item entra in `review_pending`, un ping Telegram al reviewer assegnato con
**deep-link** `https://kita.balizero.com/intake-review/<intake_id>` + i soli nomi-campo
incerti (NO valori PII). Bottone unico \"Apri\". Cosi si ha lo zero-friction di (b) per
*sapere* che c e lavoro, e la struttura di (a) per *farlo*. Approve-secco binario via
bottone Telegram ammesso SOLO per item senza PII e senza correzioni (es. \"doc gia in
CRM, conferma duplicato?\").

### Endpoint backend (nuovi, minimal)
- `GET  /api/crm/intake-review` — lista item `review_pending` filtrata per RBAC
  (team: clienti assegnati; admin: tutti + candidate-non-risolti). Ritorna solo i
  `needs_review_fields` + anteprima.
- `POST /api/crm/intake-review/{intake_id}/resolve` — body = OUT-decisione (sez. 0).
  Effetto: (1) scrive `intake_corrections`, (2) emette trigger routing PARTE 4 con
  `final_fields`, (3) avanza stato a `routed`/`rejected`. Idempotente su `intake_id`
  (riuso idempotency key C2). RBAC: `verify_client_access` sul client_id risolto.

> **Ordine garantito (requisito task)**: il routing PARTE 4 (write CRM/Drive) parte
> **solo** dentro `resolve` per gli item in review, oppure dal ramo auto-commit per
> gli item sopra-soglia. Mai prima della decisione umana per item in coda.

---

## 3. SCHEMA `intake_corrections` (seme dell auto-miglioramento)

Ogni campo toccato (o esplicitamente approvato) = una riga. E il **dataset di errore**:
coppia (estratto_AI, valore_corretto) + metadati per diagnosi.

```sql
CREATE TABLE intake_corrections (
    id              BIGSERIAL PRIMARY KEY,
    intake_id       UUID        NOT NULL,          -- FK coda intake
    content_hash    TEXT        NOT NULL,          -- dedup/traceability (C1)
    doc_type        TEXT        NOT NULL,          -- nib|npwp|kitas|...
    field_name      TEXT        NOT NULL,          -- company_name|npwp|...
    source          TEXT        NOT NULL,          -- whatsapp|drive|zoho
    -- segnale di errore
    ai_value        TEXT,                          -- cosa ha estratto l AI (PII: vedi nota)
    human_value     TEXT,                          -- valore corretto dall umano
    ai_confidence   REAL,                          -- confidence del modello su quel campo
    outcome         TEXT        NOT NULL,          -- approved|corrected|rejected|auto_committed
    -- diagnosi per evolver
    model_id        TEXT,                          -- quale modello (da MODEL_TOPOLOGY)
    model_version   TEXT,
    stage           TEXT,                          -- classify|extract|validate
    rule_passed     BOOLEAN,                       -- la validazione deterministica passo?
    -- provenance
    verified_by     TEXT        NOT NULL,
    verified_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_corrections_digest ON intake_corrections (doc_type, field_name, outcome);
CREATE INDEX idx_corrections_recent ON intake_corrections (verified_at);
```

**PII discipline (boundary B1/B2, panel C6)**: `ai_value`/`human_value` possono
contenere PII (numeri passaporto, NIK). La tabella vive **solo sul Postgres locale
del Pro** (mai Fly, mai cloud). L evolver NON riceve i valori grezzi: legge un
**digest aggregato + redatto** (sez. 4.2), non la colonna PII. Retention: i valori
grezzi si possono troncare/hash dopo 90gg, conservando solo le metriche aggregate.

---

## 4. EVOLVER HOOK (il gancio — onesto: oggi NON esiste)

> **Onesta**: il pezzo auto-migliorante NON esiste oggi. Qui progetto **solo il gancio**.
> Si attiva **solo quando c e volume reale di correzioni**. Zero dati = niente da imparare:
> il digest sotto-soglia produce un no-op esplicito, l evolver non propone nulla.

### 4.1 Cosa esiste gia (target del gancio)
`scripts/agent-library-evolver-run.sh` gira **settimanale** (LaunchAgent
`com.balizero.agent-library-evolver.weekly`, domenica 03:00 WITA). Pipeline reale:
1. **Context gathering**: `mem query` + `git log` + slice di `.claude/rules/cicatrix-scars.md` (riga 251-253).
2. Redazione PII del context (riga 301: fail se troppo piccolo).
3. EvoSkill / DeepSeek V4 Pro propone migliorie skill.
4. **Evidence-lint + entailment** gate (riga 468/487) — scarta proposte non supportate.
5. **Apre DRAFT PR** (riga 538, `gh pr create --draft`, \"Human review required before merge\").
   **Non auto-applica mai.** Esattamente il contratto richiesto: PROPONE -> PR.

> Quindi il gancio NON va costruito da zero: basta **aggiungere una fonte di context**
> al passo 1 (un \"corrections digest\"), e l intero apparato gate+PR esiste gia.

### 4.2 Il gancio: `intake-corrections-digest`
Nuovo step nel context-gathering (passo 1 dello script), feature-flagged e
volume-gated:

```
# pseudo, dentro la sezione context dello script evolver
N = SELECT count(*) FROM intake_corrections
    WHERE outcome=corrected AND verified_at > now() - interval 7 days;
if N < MIN_CORRECTIONS_VOLUME (default 30):
    echo \"intake-corrections: N<soglia (N=$N) — niente segnale, skip\"   # NO-OP onesto
else:
    emit digest REDATTO:
      per (doc_type, field_name):
        - n_corrected, n_approved, n_total, correction_rate
        - mean ai_confidence sui corretti  (i corretti ad alta confidence = AI sicura E sbagliata = peggiore)
        - top pattern d errore TASSONOMIZZATO, non valori grezzi
          (es. \"npwp: AI omette il blocco -901.000\" / \"company_name: manca suffisso PT/sukses\")
        - stage colpevole (classify/extract/validate) + rule_passed distribution
```

Il digest e **aggregato e PII-redatto** (conta + tassonomia, non NIK/passport). Entra
nel context bundle accanto alle cicatrici. **Si tratta strutturalmente come una cicatrice
di dominio**: \"ecco dove l intake sbaglia ripetutamente\".

### 4.3 Cosa l evolver puo proporre (PR, mai auto-apply)
Dato il digest, EvoSkill puo proporre — ognuna come change in PR draft:
1. **Prompt migliore** per lo stage `extract`/`classify` di un `doc_type` specifico
   (es. \"per npwp, includi sempre il suffisso .000 a 3 cifre finali\") -> edit del prompt
   nel doc-intake agent (analogo a come oggi evolve le skill in `agent-library/`).
2. **Regola di validazione nuova** (es. \"company_name deve iniziare con PT/CV\") ->
   proposta di aggiungere una regola deterministica al `validate` stage (che, una volta
   approvata, sposta quel campo da review ad auto-commit -> meno carico umano).
3. **Cambio modello / soglia per un doc_type** (es. \"npwp ha correction_rate 40% con
   modello X a soglia 0.90 -> prova modello Y o alza soglia a 0.95\") -> edit a
   MODEL_TOPOLOGY.json / tabella soglie sez. 1.1.

Tutte e tre passano per evidence-lint + entailment + **draft PR + review umana**
(Antonello/Zero). Coerente con il contratto \"PROPONE -> PR, non auto-applica\".

### 4.4 Loop di chiusura
```
intake -> AI estrae -> umano corregge -> intake_corrections (volume)
   ^                                              |
   |                                       [weekly evolver]
   |                                      digest -> proposta -> DRAFT PR
   |                                              |
   +------ Antonello merge la PR (prompt/regola/soglia migliore) ----+
```
Il miglioramento e **misurabile**: la `correction_rate` per (doc_type, field) deve
**scendere** dopo una PR mergiata. Se non scende in 2-3 settimane, la PR successiva
lo vede nel digest (la cicatrice persiste) — auto-diagnostica.

---

## 5. Attivazione graduale (onesta sul \"oggi vs domani\")

| Fase | Cosa e VERO oggi | Cosa si attiva |
|---|---|---|
| **Ora** | review-gate + CRM web view + `intake_corrections` write | HITL pienamente operativo; correzioni si accumulano |
| **Dopo N>=30/sett correzioni** | digest produce segnale | gancio evolver ON: digest entra nel context weekly |
| **Dopo 1a PR mergiata** | prompt/regola migliorata | correction_rate scende -> loop chiuso, verificabile |

Finche il volume e sotto soglia, il gancio e un **no-op esplicito loggato** — nessuna
proposta fabbricata da dati insufficienti (anti-hallucination: niente segnale, niente claim).

---

## 6. Dipendenze verso le altre parti

- **PARTE 3** deve emettere `needs_review_fields` per-campo/per-doc_type (fix C3) +
  confidence per-campo + esito `validate` (rule_passed). Senza, il gate 04.5 non sa
  cosa mostrare.
- **PARTE 4** deve esporre il routing come **proposta eseguibile differita** (non
  scrivere subito): 04.5 chiama l esecuzione dentro `resolve` o nel ramo auto-commit.
- **FASE 3 coda** fornisce la macchina-stati + lease atomico (C2) che 04.5 estende con
  `review_pending/review_claimed`.
- **Evolver esistente** (`agent-library-evolver-run.sh`) e il consumatore: unica
  modifica = aggiungere lo step `intake-corrections-digest` al context-gathering,
  volume-gated. Tutto il resto (gate, draft PR) gia c e.
