---
date: 2026-06-04
domain: operations
study: doc-intake-unified
phase: 4.4 — ENTITY RESOLUTION & ROUTING
client_case: false
sources:
  - research/operations/doc-intake-unified/01-system-study.md
  - research/operations/doc-intake-unified/01d-destinations.md
  - research/operations/doc-intake-unified/03-panel-review.md
  - apps/backend-rag/backend/app/modules/crm/models.py (live read 2026-06-04)
  - /Users/nuzantara/.claude/agents/document-intake-classifier.md (intake JSON shape)
panel_fixes_received:
  - C4 (P1, false-merge risk) — entity-resolution hardening
  - C2 (P0) — exactly-once / proposal idempotency (consumed here at routing layer)
  - C3 (P1) — per-field HITL (consumed: per-field confidence drives routing-confidence)
---

# FASE 4.4 — Entity Resolution & Routing

> SCOPE: dato un documento **classificato + estratto** (intake JSON da PARTE 3),
> (a) associarlo al **cliente** giusto (entity resolution),
> (b) produrre una **proposta-di-routing** verso le destinazioni D1/D2/D3/interactions.
>
> **L'agente NON scrive mai su DB/Drive.** Emette una *routing proposal*; la review-queue
> (PARTE 5) la approva e SOLO ALLORA esegue i write. Questo è il confine duro che recepisce
> C2 (commit path singolo, serializzato, replayabile) e D1-RBAC.

---

## 0. Posizione nella pipeline

```
[PARTE 3: classify+extract] --intake JSON--> [PARTE 4.4: ENTITY RES + ROUTE]
                                                        |
                                            emette ROUTING PROPOSAL (no write)
                                                        |
                                                        v
                                          [PARTE 5: review-queue]
                                       auto-commit (alta soglia) | HITL
                                                        |
                                       ESEGUE i write: D1 / D2 / interactions
                                                        |
                                                  [D3 auditor consuma]
```

Entity-resolution e routing sono **deterministici e read-only** sul DB: leggono `clients`
per fare il match, ma producono solo una proposta. Nessun `INSERT/UPDATE` parte da qui —
chiude il finding C2/C7 (verify = firma umana + diff + evidence pointer, NON solo stato).

---

## 1. INPUT — contratto da PARTE 3

L'input è l'**intake JSON** prodotto dal `document-intake-classifier` (PARTE 3). Forma
verificata (agent spec, Step 5). Per ogni documento il blocco rilevante per il match è:

```jsonc
{
  "client_slug": "marta-reyes",          // hint NON autoritativo (slug suggerito dal classifier)
  "generated_at": "2026-06-04T...+08:00",
  "generated_by": "document-intake-classifier",
  "source": {                             // ⟵ AGGIUNTA RICHIESTA a PARTE 3 (provenance, vedi §6)
    "channel": "whatsapp|drive|zoho",
    "ref": "whatsapp_message_context.id=... | drive_file_id=... | zoho msg+att id",
    "sender_phone_raw": "+62 821-...",    // SOLO per channel=whatsapp (E.164 grezzo)
    "sender_email": "...",                // SOLO per channel=zoho
    "blob_sha256": "....",                // per idempotenza (C1/C2)
    "media_path": "/Users/nuzantara/wa-mirror-media/<phone>/<file>"
  },
  "documents": [
    {
      "file": "akta-page1.jpg",
      "type": "passport|ktp|kitas|npwp|nib|akta_pendirian|skt_skdp|oss_cert|unknown",
      "type_confidence": 0.91,
      "pages_ocrd": 4,
      "fields": {
        // per-field {value, confidence, source_page}; array per direksi/komisaris
        "passport_number": {"value":"YB1234567","confidence":0.93,"source_page":1},
        "full_name":       {"value":"MARTA REYES","confidence":0.9,"source_page":1},
        "nationality":     {"value":"ESP","confidence":0.95,"source_page":1},
        "birth_date":      {"value":"1989-03-21","confidence":0.88,"source_page":1},
        "kitas_number":    {"value":"2C11JE1234-X","confidence":0.8,"source_page":1}
        // ...
      },
      "low_confidence_fields": ["modal_disetor"],
      "needs_review": true
    }
  ],
  "summary": {"total": 5, "needs_review": 2, "ocr_failed": 0}
}
```

**Match-relevant fields per tipo** (l'estrattore già li produce — agent catalog):

| doc type | identity keys utili al match |
|---|---|
| passport | `passport_number`, `full_name`, `nationality`, `birth_date` |
| kitas | `kitas_number`, `full_name`, `sponsor` |
| ktp | `nik`, `full_name`, `birth_date` (+ birth_place) |
| npwp | `npwp_number`, `registered_name` |
| nib / akta / oss | `company_name`, `nib`, direksi[] (→ company match, non individual) |

> **Mancanza schema da segnalare (NON bloccante):** la tabella `clients`
> (verificata live 2026-06-04, `models.py:25-60`) ha `full_name, phone, whatsapp,
> nationality, passport_number, email, tax_id` ma **NON ha `birth_date` né
> `kitas_number` come colonne**. La fix C4 del panel chiede birth_date + nazionalità
> come discriminanti: la **nazionalità c'è**, la **birth_date NO**. Vedi §3.4 — il
> match birth-date si appoggia a `custom_fields` JSON (oggi spesso vuoto) → in pratica
> oggi opera come *tie-breaker quando disponibile*, non come blocking key, finché non si
> aggiunge `clients.birth_date` (debito schema, raccomandato a PARTE 5/build).

---

## 2. OUTPUT — contratto ROUTING PROPOSAL

Una riga in `document_routing_proposal` (tabella nuova, DB-backed, **scritta dall'agente,
NON è un write di destinazione**: è la coda che PARTE 5 legge). Formato JSON del payload:

```jsonc
{
  "proposal_id": "uuid",
  "created_at": "2026-06-04T...",
  "created_by": "doc-intake-entity-router",
  "pipeline_version": "intake-v1",        // C1: include version per riprocessamento
  "idempotency_key": "<blob_sha256>:<doc_index>:intake-v1",  // C2: exactly-once

  "intake_ref": {                         // puntatore all'intake JSON di PARTE 3
    "file": "research/crm/intake/2026-06-04-marta-reyes-intake.json",
    "doc_index": 0,
    "blob_sha256": "...."
  },

  "document": {
    "type": "passport",
    "type_confidence": 0.91,
    "category": "immigration",            // mappato da type (§4.2)
    "fields_digest": { ... },             // PII-masked digest dei campi (NO raw NIK in chiaro nei log)
    "needs_field_review": true            // ereditato da PARTE 3 (C3: per-field)
  },

  // (a) ENTITY RESOLUTION — esito match
  "entity_resolution": {
    "decision": "AUTO_ATTACH | LINK_CANDIDATE | NO_MATCH | AMBIGUOUS",
    "client_id": 412,                     // best match (null se NO_MATCH)
    "match_score": 0.97,
    "signals": [                          // i segnali concordi (C4: servono ≥2 per auto)
      {"key":"passport_number","kind":"exact","weight":1.0,"client_id":412},
      {"key":"nationality","kind":"exact","weight":0.3,"client_id":412},
      {"key":"name_jw","kind":"fuzzy","score":0.94,"weight":0.5,"client_id":412}
    ],
    "candidates": [                       // top-N per HITL disambiguation
      {"client_id":412,"full_name":"M****a R****s","score":0.97},
      {"client_id":889,"full_name":"M****o R****z","score":0.71}
    ],
    "reason": "passport exact + nationality concordant (2 signals) ≥ auto threshold",
    "phone_owner_risk": false             // C4: il phone può essere agente/familiare
  },

  // (b) ROUTING — destinazioni proposte (NON eseguite)
  "routing": {
    "D1_crm_documents": {
      "action": "INSERT documents",
      "endpoint": "POST /api/crm/clients/{client_id}/documents",
      "payload": {                        // pronto al commit, post-approval
        "client_id": 412,
        "practice_id": null,              // risolto se 1 sola pratica aperta compatibile
        "family_member_id": null,
        "document_type": "passport",
        "document_category": "immigration",
        "file_name": "412_marta-reyes/01_Immigration/passport.pdf",
        "expiry_date": "2031-05-02",
        "ocr_status": "completed",
        "ocr_extracted_data": { ... }     // PII resta locale; payload non loggato in chiaro
      }
    },
    "D2_drive": {
      "action": "upload+rename",
      "target_folder": "01_Immigration",  // da CATEGORY_TO_FOLDER
      "target_path": "412_marta-reyes/01_Immigration/passport.pdf",
      "client_folder_id": "clients.google_drive_folder_id (o CREATE se assente)",
      "writes_back_to_D1": ["file_id","google_drive_file_url"]
    },
    "interactions": {
      "action": "INSERT interactions",
      "payload": {
        "client_id": 412,
        "interaction_type": "whatsapp",   // = source.channel
        "channel": "whatsapp",
        "note": "doc ricevuto via whatsapp (passport) 2026-06-04",
        "extracted_entities": {"doc_type":"passport","blob_sha256":"..."}
      }
    },
    "D3_auditor": {
      "action": "notify-consumer",        // solo se type ∈ {akta,nib,npwp,oss,skt}
      "intake_json": "research/crm/intake/2026-06-04-marta-reyes-intake.json",
      "trigger": "enqueue company-docs-consistency-auditor (read-only)"
    }
  },

  // (c) GATE per PARTE 5
  "commit_gate": {
    "auto_commit_eligible": false,        // true SOLO se entity AUTO_ATTACH ∧ no needs_field_review
    "requires_human": true,
    "review_reasons": ["entity LINK_CANDIDATE (score 0.84 < auto 0.92)",
                       "field modal_disetor low-confidence"]
  },

  "status": "proposed"                    // proposed→approved→committed→done | rejected | dead
}
```

**Confini del payload (recepisce B1/B2 + C6):**
- `fields_digest` e ogni linea di log/Telegram sono **PII-masked** (`NIK 3271******1234`).
- `ocr_extracted_data` (PII piena) resta nel payload DB **locale** e non viene mai loggato
  in chiaro, mai inviato a RAG/Qdrant (B1), NotebookLM/cloud (B2), né incluso in alcun
  prompt LLM cloud. Nessun CoT grezzo persistito (C6) — solo `reason` strutturato + signals.

---

## 3. ALGORITMO ENTITY RESOLUTION (doc → cliente)

Recepisce integralmente la fix panel **C4** (P1, alto rischio false-merge). Principio
guida: **DEFAULT = LINK_CANDIDATE (proposta), MAI auto-attach** sotto soglia altissima
con ≥2 segnali concordi.

### 3.1 Normalizzazione (pre-match, obbligatoria — C4 "E.164 senza normalizzazione fallisce")

| chiave | normalizzazione |
|---|---|
| **phone** | strip spazi/`-`/`()`; se inizia `0` → `+62`+resto; se manca `+` e inizia `62` → `+62..`; output **E.164** canonico. Match contro `clients.phone` E `clients.whatsapp` (entrambi normalizzati a runtime). |
| **passport_number** | upper, strip spazi, rimuovi `<` MRZ-filler. |
| **kitas_number** | upper, strip spazi/`-`. |
| **npwp** | solo cifre (16); confronta normalizzato (15-old → pad). |
| **nik** | solo cifre (16). |
| **name** | upper, strip accenti, collassa spazi; tokenizza (per JW su nome+cognome separati). |
| **nationality** | mappa a ISO-3 (ESP/IDN/USA) — discriminante secondario. |
| **birth_date** | ISO `YYYY-MM-DD` (parse da formati misti OCR). |

### 3.2 STRONG KEYS — exact-match PRIMA (deterministico, peso 1.0)

In ordine, ogni hit è un **segnale forte**:
1. `passport_number` exact ↔ `clients.passport_number`
2. `kitas_number` exact ↔ `clients.custom_fields->>'kitas_number'` (oggi in JSON; col dedicata = debito)
3. `npwp` exact ↔ `clients.tax_id`
4. `nik` exact ↔ `clients.custom_fields->>'nik'`
5. `phone` E.164 exact ↔ `clients.phone` / `clients.whatsapp`

> **C4 caveat phone:** il phone è un **WEAK strong-key**. Il numero che invia su WhatsApp
> può essere **agente / familiare / consulente**, NON il cliente. Quindi:
> - phone-match da SOLO ⇒ MAI auto-attach. Imposta `phone_owner_risk=true`.
> - phone-match vale come segnale **solo se concorde con un secondo segnale** (nome JW alto
>   o un'altra strong key). Da solo ⇒ `LINK_CANDIDATE` con candidato = titolare del numero.

### 3.3 FUZZY — Jaro-Winkler sul nome, MAI da solo (C4 "Wayan/Made omonimi")

Se nessuna strong key risolve univocamente, calcola **Jaro-Winkler** tra `full_name`
normalizzato e `clients.full_name`. Soglia `jw ≥ 0.90`.

**Vincoli anti-false-merge (C4):**
- Jaro-Winkler sul **solo nome NON è mai sufficiente** per auto-attach. Nomi balinesi
  (Wayan/Made/Komang/Ketut) collassano omonimi.
- Il match fuzzy **deve essere bloccato (blocking) per discriminanti concordi**:
  - **+ nationality** concordante (obbligatorio se presente nel doc), E
  - **+ birth_date** concordante (se disponibile su entrambi i lati), E
  - **+ client_type** coerente (passport/ktp→individual; akta/nib→company).
- Senza almeno UN discriminante concorde oltre al nome ⇒ resta `LINK_CANDIDATE`/`AMBIGUOUS`.

### 3.4 SCORING e SOGLIE (decision matrix)

Score = somma pesata dei segnali concordi sullo stesso `client_id`:

| segnale | peso |
|---|---|
| strong key exact (passport/kitas/npwp/nik) | **1.0** |
| phone E.164 exact | 0.6 (ma vedi caveat: non-sufficiente da solo) |
| name Jaro-Winkler (≥0.90) | 0.5 × jw |
| nationality concordante | 0.3 |
| birth_date concordante | 0.4 |
| client_type coerente | 0.1 |

**Decisione (recepisce C4 — "soglia altissima + 2 segnali concordi"):**

| condizione | decision | gate |
|---|---|---|
| ≥1 strong-key exact **E** ≥2 segnali concordi totali **E** score ≥ **0.92** | **AUTO_ATTACH** | auto-commit eligible (se anche no field-review) |
| qualunque match con 0.70 ≤ score < 0.92 **OPPURE** un solo segnale **OPPURE** solo-phone **OPPURE** solo-nome-JW | **LINK_CANDIDATE** | → HITL (PARTE 5) |
| ≥2 candidati entro Δscore ≤ 0.08 (collisione omonimi) | **AMBIGUOUS** | → HITL con top-N candidates |
| nessun candidato score ≥ 0.70 | **NO_MATCH** | → HITL "nuovo lead?" (create-from-OCR, gap #10) |

**Regole dure C4 sempre attive:**
- DEFAULT = `LINK_CANDIDATE`. `AUTO_ATTACH` è l'eccezione, non la regola.
- AUTO_ATTACH **vietato** se l'unico segnale è phone OR nome-JW (anche con score alto fittizio).
- AUTO_ATTACH **vietato** se `phone_owner_risk=true` e non c'è una strong-key indipendente.
- Company docs (akta/nib/npwp-badan/oss) matchano contro `client_type='company'` /
  `company_documents` / `client_company_links`, MAI contro individui (evita cross-merge).

---

## 4. ROUTING — mappa destinazioni (da 01d)

L'agente **non scrive**: prepara i payload pronti. PARTE 5 esegue dopo approvazione.

### 4.1 Destinazioni e azioni

| Dest | Azione proposta | Endpoint / target | Chi esegue |
|---|---|---|---|
| **D1 CRM `documents`** | `INSERT` row | `POST /api/crm/clients/{client_id}/documents` | review-queue (PARTE 5), MAI l'agente, MAI DB diretto |
| **D1b `practices.documents` / `practice_required_documents`** | append JSON / satisfy checklist | `POST /api/crm/practices/{practice_id}/documents/add` | review-queue, solo se `practice_id` risolto |
| **D2 Drive ordinato** | upload file rinominato + write-back file_id→D1 | folder `<id>_<nome>/<subfolder>` | review-queue (lo stesso handler D1 fa folder+DB in sync) |
| **interactions** | `INSERT` provenance event | tabella `interactions` (client_id, interaction_type=channel) | review-queue |
| **D3 auditor** | notify-consumer (read-only) | enqueue `company-docs-consistency-auditor` con intake JSON | trigger post-commit, solo company docs |
| **B1 RAG/Qdrant** | — | **VIETATO (PII firewall)** | nessuno |
| **B2 NotebookLM/cloud** | — | **VIETATO (PII/OSINT sovranità Law 2)** | nessuno |

### 4.2 CATEGORY_TO_FOLDER (da `services/crm/documents.py:214`)

`document_category` (derivato dal `type`) → subfolder Drive:

| doc type | category | subfolder Drive |
|---|---|---|
| passport, kitas, ktp, skt_skdp | immigration | **01_Immigration** |
| akta_pendirian, nib, oss_cert | pma | **02_Company** |
| npwp | tax | **03_Tax** |
| (family/dependent doc) | family | **04_Family** |
| unknown / altro | other | **99_Misc** |

> Mapping verificato vs 01d: `family→04 · immigration→01 · pma→02 · tax→03 · other→99`,
> default `99_Misc`. Il `document_category` del payload guida sia D1 (`documents.document_category`)
> sia D2 (subfolder).

### 4.3 Practice resolution (opzionale, best-effort)

Se il cliente risolto ha **esattamente 1 pratica aperta** il cui `practice_required_documents`
include il tipo di documento → proponi `practice_id`. Se 0 o ≥2 pratiche compatibili →
`practice_id=null` (resta a D1 client-level; la review-queue può assegnarla a mano). Mai
forzare una practice ambigua.

### 4.4 D3 auditor — trigger condizionato

Notifica `company-docs-consistency-auditor` SOLO quando `type ∈ {akta_pendirian, nib,
npwp(badan), oss_cert, skt_skdp}` e il cliente è `company`. L'auditor è **read-only
consumer** dell'intake JSON (cross-check akta↔NIB↔NPWP K1-K8); non è un write target.
Trigger **post-commit** (dopo che D1 ha la row), per cross-check su stato consolidato.

---

## 5. IDEMPOTENZA & STATO (recepisce C2/C1)

- `idempotency_key = <blob_sha256>:<doc_index>:<pipeline_version>`. UNIQUE su
  `document_routing_proposal`. Re-ingest dello stesso blob con stessa pipeline_version =
  no-op (proposta già esistente). Cambio `pipeline_version` ⇒ nuova proposta → permette
  riprocessamento dopo upgrade modello (C1: il `dead` con stesso hash NON si auto-scarta in
  silenzio).
- Stato proposta: `proposed → approved → committed → done | rejected | dead`. Claim atomico
  in PARTE 5 (`FOR UPDATE SKIP LOCKED` — pattern già in repo, cf. `replay_outbox_throttled.py`).
- Il commit path (D1/D2/interactions) è **singolo, serializzato, replayabile** (C2/Codex):
  un solo worker review-queue committa; in caso di crash post-D2-pre-D1, il write-back
  file_id è idempotente (upsert su `documents.file_id` per stesso idempotency_key).

---

## 6. PROVENANCE (interactions) — recepisce gap #11/§01d

Ogni doc routato genera UN evento `interactions`:
`interaction_type = source.channel` (whatsapp|email|drive), `channel` idem, `note` PII-masked
("doc ricevuto via whatsapp (passport) <data>"), `extracted_entities` = {doc_type, blob_sha256,
proposal_id}. Popola la tabella `interactions` oggi quasi-vuota (01d). È loggato **dopo** il
commit D1 (un solo evento per doc effettivamente archiviato, non per proposta).

> **Richiesta a PARTE 3:** l'intake JSON deve includere il blocco `source{channel, ref,
> sender_phone_raw|sender_email, blob_sha256, media_path}` — oggi l'agent spec non lo emette.
> È la sola aggiunta upstream necessaria perché entity-res (phone/email→client) e provenance
> funzionino.

---

## 7. INTERFACCE (dichiarazione formale)

**INPUT** — `intake JSON` (PARTE 3), file `research/crm/intake/<date>-<slug>-intake.json`
+ blocco `source{}` aggiunto. Per-doc: `type`, `type_confidence`, `fields{value,confidence,
source_page}`, `needs_review`. PII piena ammessa nel file (resta locale).

**OUTPUT** — `routing proposal` (questo modulo), riga in `document_routing_proposal`
(DB-backed, locale): `entity_resolution{decision,client_id,match_score,signals[],candidates[]}`
+ `routing{D1,D2,interactions,D3}` payload-ready + `commit_gate{auto_commit_eligible,
requires_human,review_reasons}` + `idempotency_key` + `status`. **Nessun write di
destinazione**: lo esegue PARTE 5 dopo approvazione.

**CONFINI** — read-only su `clients` per il match; write SOLO sulla coda proposte; PII mai
in RAG/Qdrant/NotebookLM/cloud/CoT-log; log/Telegram PII-masked.

---

## Sintesi

1. Entity-resolution e routing sono **deterministici e read-only sul DB**: leggono `clients`
   per il match, emettono una **routing proposal**, e NON scrivono mai su D1/D2/interactions —
   quello lo fa PARTE 5 dopo approvazione (chiude C2: commit path singolo/serializzato).
2. **Match (C4 recepito):** strong-key exact PRIMA (passport/kitas/npwp/nik/phone-E.164),
   poi Jaro-Winkler sul nome — **mai da solo**, bloccato da nationality + birth_date + client_type.
3. **Phone = weak key:** può essere agente/familiare; da solo ⇒ mai auto-attach (`phone_owner_risk`).
4. **DEFAULT = LINK_CANDIDATE.** AUTO_ATTACH solo con ≥1 strong-key + ≥2 segnali concordi + score ≥ 0.92.
   Altrimenti coda HITL (PARTE 5); omonimi entro Δ0.08 ⇒ AMBIGUOUS con top-N.
5. **Routing:** D1 `documents` via `POST /api/crm/clients/{id}/documents`; D2 Drive
   `<id>_<nome>/<subfolder>` via CATEGORY_TO_FOLDER (immigration→01/pma→02/tax→03/family→04/other→99);
   interactions = provenance; D3 auditor = consumer read-only (solo company docs).
6. **Idempotenza C1/C2:** `idempotency_key = blob_sha256:doc_index:pipeline_version` (riprocessabile su upgrade modello).
7. **PII firewall B1/B2:** nessun campo cliente in Qdrant/NotebookLM/cloud; log mascherati; no CoT grezzo (C6).
8. **Debito schema segnalato:** `clients` non ha `birth_date`/`kitas_number` come colonne (oggi
   in `custom_fields` JSON) e manca una fuzzy-lib (jellyfish/rapidfuzz) nel venv — entrambi da
   risolvere a build-time perché il discriminante C4 birth_date sia *blocking* e non solo tie-breaker.
