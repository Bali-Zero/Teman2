---
date: 2026-06-04
domain: operations
study: doc-intake-unified
phase: 4.0 — INTEGRATION CHECK (giunzioni P1→P2→P3→P4→P5)
client_case: false
sources:
  - research/operations/doc-intake-unified/04-1-ingestion-dedup.md
  - research/operations/doc-intake-unified/04-2-queue-orchestrator.md
  - research/operations/doc-intake-unified/04-3-classify-extract-validate.md
  - research/operations/doc-intake-unified/04-4-entity-routing.md
  - research/operations/doc-intake-unified/04-5-hitl-evolver.md
verdict: GAP — le 5 parti NON si incastrano as-is. 7 contraddizioni bloccanti.
---

# FASE 4 — PARTE 0/5 — INTEGRATION CHECK

> Verifica che i contratti tra le 5 parti combacino. **Le parti sono state scritte in
> parallelo, ognuna ha inventato il proprio naming.** Il risultato è internamente coerente
> dentro ogni documento ma **NON si incastra alle giunzioni**: tabelle con 3 nomi diversi,
> 3 tipi diversi per `pipeline_version`, 2 vocabolari per `source`, e un cambio di forma
> radicale del payload tra P3 (per-documento) e P4 (batch multi-doc). Va fatto un passo
> di **unificazione contratti** prima di costruire.

---

## 1. MATRICE GIUNZIONI (PASS/GAP)

| Giunzione | Cosa passa | Verdetto | Motivo sintetico |
|---|---|---|---|
| **P1 → P2** | `intake-item` v1.0 / `IntakeItem` enqueue | ⚠️ **GAP** | Stessa idea, ma nome tabella diverso (`intake_queue`+`document_instances` vs `intake_job`), `source` enum diverso (`wa` vs `whatsapp`), `source_ref` TEXT vs JSONB, `pipeline_version` VARCHAR vs INT. Campi core (blob_hash, source, pipeline_version) presenti in entrambi ✓ ma con tipi/forme incompatibili. |
| **P2 → P3** | `StageContext` in-process | ⚠️ **GAP** | P2 promette `classify(StageContext)->StageOutput` con `StageContext{job_id, file_path, mime_type, doc_type, fields}`. P3 dichiara `process_intake(IntakeItem)` con input `{intake_id, blob_path, blob_hash, type_hint, client_id_hint}`. Nomi campo non combaciano (`file_path` vs `blob_path`, `job_id` vs `intake_id`, `doc_type` vs `type_hint`). Il pattern (funzione in-process deterministica) combacia ✓; la firma NO. |
| **P3 → P4** | intake JSON | 🛑 **GAP GROSSO** | P3 emette JSON **per-singolo-documento** (`{intake_id, type, fields{}, validation_results[], version_link, needs_review_fields[]}`). P4 si aspetta un JSON **batch multi-documento** (`{client_slug, documents[], source{}, summary{}}`). Forma radicalmente diversa + P4 chiede un blocco `source{channel,ref,sender_phone_raw,sender_email,blob_sha256,media_path}` che **P3 NON emette** (P3 ha solo `source: "whatsapp"` stringa). Naming campi diverso (`needs_review_fields` vs `low_confidence_fields`, `type_confidence` vs ok). |
| **P4 → P5** | routing proposal + decisione umana → esecuzione | ✅ **PASS (logica)** / ⚠️ naming | La catena "P4 PROPONE (read-only) → P5 APPROVA → P5 ESEGUE il write" è **coerente e concorde in tutti e 3 i doc** (P4 §0/§7, P5 §0/§2). Chi-esegue-il-write è **univoco: PARTE 5** (review-queue), MAI l'agente P4, MAI DB diretto. Unico attrito: P4 chiama la tabella `document_routing_proposal`, P5 la chiama `routing_proposal` inline + stati `proposed→approved→committed` (P4) vs `review_pending→review_claimed→routed` (P5) — due macchine-stati per lo stesso oggetto. |
| **Idempotency-key** | chiave dedup/exactly-once | 🛑 **GAP** | **3 formule diverse, non allineate.** P1: `source\|source_ref\|blob_hash\|pipeline_version`. P2: UNIQUE `(blob_hash, pipeline_version)` (no source/ref!). P3: `sha256(blob_hash\|pipeline_version\|stage)` (per-stadio). P4: `blob_sha256:doc_index:pipeline_version`. P5: "riuso idempotency key C2" (non specifica). Non c'è UNA chiave canonica che attraversa il sistema. |

**Riepilogo**: 1 PASS (logica P4→P5), 4 GAP (di cui 2 grossi: P3→P4 forma payload, idempotency-key).

---

## 2. CONTRADDIZIONI DA RISOLVERE (lista numerata)

### 🛑 X1 — Nome tabella coda: `intake_queue` vs `intake_job` (+ `document_instances`)
- **P1**: due tabelle, `intake_queue` (lavoro) + `document_instances` (registro blob immutabile).
- **P2**: una tabella, `intake_job` (con `UNIQUE(blob_hash, pipeline_version)` inline, niente registro blob separato).
- **P3/P5**: parlano genericamente di "coda intake" / `intake_id`, agnostici sul nome.
- **Conflitto reale**: P1 ha un modello a 2 tabelle (necessario per "stesso blob legittimo per più clienti", C1) che P2 **non recepisce** (P2 ha solo `intake_job` con UNIQUE su blob+pipeline, che **vieta** lo stesso blob per due clienti — contraddice direttamente la decisione C1 di P1).
- **Da decidere**: si adotta il modello 2-tabelle di P1 (`document_instances` + `intake_queue`)? Allora P2 deve riscrivere lo schema `intake_job` → `intake_queue` e togliere la UNIQUE `(blob_hash,pipeline_version)` (sostituendola con l'`idempotency_key` di P1 che include source+ref, permettendo multi-cliente).

### 🛑 X2 — `pipeline_version`: VARCHAR(32) vs INT vs stringa "intake-v1"
- **P1**: `VARCHAR(32)`, valore es. `'ocr-v3-qwen2.5vl-2026.06'`.
- **P2**: `INT`, "bump → riprocessabile".
- **P3/P4**: stringa `"intake-v1"`.
- **Conflitto**: tipo incompatibile (INT vs stringa). L'`idempotency_key` di P1/P4 concatena `pipeline_version` come testo → se P2 lo tiene INT, le chiavi non combaciano.
- **Da decidere**: unificare su `VARCHAR(32)` con un valore canonico (es. `'intake-v1'` o `'ocr-v3-qwen2.5vl-2026.06'`). Scartare l'INT di P2.

### 🛑 X3 — Enum `source`: `wa|drive|zoho` (P1) vs `whatsapp|drive|zoho` (P2/P3/P4/P5)
- **P1** usa `'wa'` (CHECK constraint + `source_ref='wmc:'||id`).
- **P2/P3/P4/P5** usano `'whatsapp'`.
- **Conflitto**: il CHECK constraint di P1 `source IN ('wa','drive','zoho')` rifiuterebbe le righe che il resto del sistema produce con `'whatsapp'`. Bug a runtime garantito.
- **Da decidere**: standardizzare su `'whatsapp'` (4 doc su 5 lo usano; più leggibile). Correggere P1.

### 🛑 X4 — `source_ref`: TEXT (P1) vs JSONB (P2)
- **P1**: `source_ref TEXT` con encoding string (`'zoho:msg:att'`, `'wmc:123'`, `'drive:fileId'`).
- **P2**: `source_ref JSONB` (`{"message_context_id":123}`, `{"drive_file_id":"..."}`).
- **Conflitto**: forma di serializzazione diversa per la stessa colonna. L'`idempotency_key` di P1 concatena `source_ref` come stringa — se è JSONB l'ordine chiavi non è stabile → chiavi non deterministiche.
- **Da decidere**: TEXT con encoding canonico `<source>:<id>[:<subid>]` (deterministico, concatenabile in chiave). Scartare JSONB.

### 🛑 X5 — Forma payload P3→P4: per-documento (P3) vs batch multi-doc (P4)
- **P3** output = **un JSON per un singolo blob** (`{intake_id, blob_hash, type, type_confidence, fields{}, validation_results[], version_link, needs_review_fields[], status, processing_meta}`).
- **P4** input = **un JSON batch per un cliente** con `{client_slug, documents:[{file, type, fields{}, low_confidence_fields[], needs_review}], source{}, summary{total,needs_review}}`.
- **Conflitto strutturale**: P4 itera `documents[]` (batch) ma P3 emette singoli. Inoltre i nomi campo differiscono dentro `documents[]`: P4 vuole `low_confidence_fields` (P3 dà `needs_review_fields`), P4 vuole `needs_review` bool (P3 dà `status` enum), P4 si aspetta `fields.passport_number.value` ma con confidence — ok — però P3 ha anche `raw_span`/`source_page` che P4 ignora.
- **Da decidere**: o (a) P4 consuma N JSON singoli di P3 (rimuovere il wrapper batch+`client_slug`+`summary` da P4), oppure (b) introdurre un aggregatore esplicito tra P3 e P4. (a) è più semplice e coerente con la coda 1-job-1-blob di P1/P2.

### 🛑 X6 — Blocco `source{}` richiesto da P4 ma NON emesso da P3
- **P4 §1/§6** richiede esplicitamente: *"l'intake JSON deve includere il blocco
  `source{channel, ref, sender_phone_raw|sender_email, blob_sha256, media_path}` — oggi
  l'agent spec non lo emette"*. Serve per entity-resolution (phone/email→client) e provenance.
- **P3 §5** emette solo `"source": "whatsapp|drive|zoho"` (stringa) + `client_id_hint`. **NON** emette sender_phone/sender_email/media_path.
- **MA**: questi dati **esistono in P1**! Il `routing_hints{sender_email, subject, wa_message_id, drive_file_id}` + `blob.path` del contratto P1 li ha. Si perdono perché P3 non li propaga.
- **Da decidere**: P3 deve **passare-attraverso** il blocco provenance da P1 (sender_phone/email + media_path + source_ref) nel suo output. È il fix che chiude la giunzione P3→P4. (P3 li riceve dal `routing_hints` di P1 ma oggi non li ri-emette.)

### ⚠️ X7 — Idempotency-key non canonica (3 formule)
Vedi tabella §1. Quattro formule diverse:
- P1: `source\|source_ref\|blob_hash\|pipeline_version`  (enqueue dedup)
- P2: `UNIQUE(blob_hash, pipeline_version)`  (no source → vieta multi-cliente, contraddice C1)
- P3: `sha256(blob_hash\|pipeline_version\|stage)`  (per-stadio, scopo diverso — OK come sub-key)
- P4: `blob_sha256:doc_index:pipeline_version`  (routing proposal)
- **Allineabili?** SÌ. P3 è ortogonale (idempotenza per-stadio interna, legittima). Le altre vanno unificate su **UNA chiave d'intake**:
  `intake_key = sha256(source | source_ref | blob_hash | pipeline_version)`
  - P2 deriva la sua UNIQUE da questa (non da `blob_hash,pipeline_version` da solo → così multi-cliente è permesso).
  - P4 deriva `idempotency_key = intake_key + ':' + doc_index` (per gestire più doc estratti dallo stesso blob, se mai).
  - P3 tiene la sua per-stadio `sha256(intake_key|stage)`.

### ⚠️ X8 — Doppia macchina-stati per la routing proposal
- **P4** stati: `proposed → approved → committed → done | rejected | dead`.
- **P5** stati coda: `review_pending → review_claimed → {routed | rejected}` (estende la state-machine intake).
- **Conflitto soft**: stesso oggetto (la proposta da approvare) ha due vocabolari di stato. Non bloccante ma confonde. P5 mappa `approved≈routed`, `proposed≈review_pending`? Non dichiarato.
- **Da decidere**: una sola macchina-stati per la proposta. Suggerito: P5 possiede gli stati (`review_pending→review_claimed→routed|rejected`) e P4 li adotta invece di `proposed/approved/committed`.

### ⚠️ X9 — Nome tabella proposta: `document_routing_proposal` (P4) vs `routing_proposal` / inline (P5)
- P4 §2: tabella `document_routing_proposal`.
- P5 §0 IN: campo annidato `routing_proposal` dentro l'`intake_item`; non nomina la tabella.
- **Da decidere**: confermare `document_routing_proposal` come tabella unica; P5 la legge.

### ⚠️ X10 — `client_id_hint` (P1/P2/P3) vs `client_slug` (P4) vs `client_id` risolto
- P1/P2/P3 propagano `client_id_hint` (BIGINT, suggerimento di fonte, non autoritativo, C4-safe).
- P4 input usa `client_slug` (stringa, es. `"marta-reyes"`) come hint — **un'altra rappresentazione** dello stesso concetto.
- **Da decidere**: P4 deve consumare `client_id_hint` (intero) coerente con P1-P3, non `client_slug`. L'`AUTO_ATTACH`/`LINK_CANDIDATE` di P4 produce poi il `client_id` autoritativo.

### ⚠️ X11 — `blob_hash` formato: hex grezzo (P1/P2) vs `sha256:...` prefissato (P3/P4)
- P1/P2: `CHAR(64)` hex puro (`9f86d081...`).
- P3: `"blob_hash": "sha256:..."` (con prefisso).
- P4: `blob_sha256` (nome diverso, valore hex).
- **Da decidere**: hex grezzo a 64 char senza prefisso, nome unico `blob_hash` ovunque (P4 rinomina `blob_sha256`→`blob_hash`). Coerenza con l'`idempotency_key` concatenata.

### ℹ️ X12 — `needs_review` naming a valle
- P3: `needs_review_fields[]` (lista nomi campo).
- P4 dentro `documents[]`: `low_confidence_fields[]` + `needs_review` (bool) + `needs_field_review` (nella proposal).
- P5 IN: `needs_review_fields[]` (concorda con P3 ✓).
- **Da decidere**: standardizzare su `needs_review_fields[]` (lista) come fa P3/P5. P4 elimina `low_confidence_fields`/`needs_field_review`, usa `needs_review_fields`.

---

## 3. CHI ESEGUE IL WRITE — risolto (NON ambiguo)

La catena è **coerente e concorde** in P4 e P5:
- **P4** è esplicitamente **read-only** sul DB: legge `clients` per il match, scrive SOLO
  una riga in `document_routing_proposal` (la coda di proposte). Mai `documents`/`clients`/Drive.
- **P5** è **l'unico punto che autorizza ed esegue il write** verso D1 (CRM `documents`),
  D2 (Drive), `interactions`. Lo fa **dentro `POST /api/crm/intake-review/{id}/resolve`**
  (HITL) o nel ramo auto-commit (sopra-soglia, ma sempre via review-queue worker).
- Quindi: **P4 PROPONE → P5 APPROVA → P5 ESEGUE**. La frase "P4 esegue" nel task è
  **imprecisa**: P4 non esegue mai. Esegue sempre PARTE 5. ✅ Nessuna ambiguità reale,
  i due doc sono allineati su questo punto (è la cosa che funziona meglio nell'integrazione).

---

## 4. NAMING DA UNIFICARE (tabella di decodifica)

| Concetto | P1 | P2 | P3 | P4 | P5 | **CANONICO proposto** |
|---|---|---|---|---|---|---|
| Tabella coda lavoro | `intake_queue` | `intake_job` | "coda" | — | "coda intake" | **`intake_queue`** |
| Registro blob immutabile | `document_instances` | (assente) | — | — | — | **`document_instances`** (adottare) |
| Tabella proposta routing | — | — | — | `document_routing_proposal` | `routing_proposal` | **`document_routing_proposal`** |
| Tabella correzioni HITL | — | — | — | — | `intake_corrections` | **`intake_corrections`** |
| PK riga coda | `queue_id` | `id`/`job_id` | `intake_id` (uuid) | — | `intake_id` (uuid) | **`intake_id`** (decidere: BIGINT vs UUID! P1/P2 BIGSERIAL, P3/P5 uuid) |
| Enum source | `wa\|drive\|zoho` | `whatsapp\|...` | `whatsapp\|...` | `whatsapp\|...` | `whatsapp\|...` | **`whatsapp\|drive\|zoho`** |
| Tipo pipeline_version | VARCHAR(32) | INT | str | str | — | **VARCHAR(32)** |
| Tipo source_ref | TEXT | JSONB | — | — | — | **TEXT** (`<src>:<id>`) |
| Hash blob | `blob_hash` hex | `blob_hash` hex | `blob_hash` `sha256:` | `blob_sha256` | `content_hash` | **`blob_hash`** hex64 |
| Path file locale | `blob_path` | `file_path` | `blob_path` | `media_path` | — | **`blob_path`** |
| Hint cliente | `client_id_hint` | — | `client_id_hint` | `client_slug` | — | **`client_id_hint`** (BIGINT) |
| Campi da rivedere | — | — | `needs_review_fields[]` | `low_confidence_fields[]`+`needs_review` | `needs_review_fields[]` | **`needs_review_fields[]`** |
| Stati proposta | — | — | — | `proposed→approved→committed` | `review_pending→review_claimed→routed` | **`review_pending→review_claimed→routed\|rejected`** |

> ⚠️ **Conflitto-tipo PK non risolvibile per naming**: P1/P2 usano `BIGSERIAL` (intero),
> P3/P5 usano `uuid`. Va deciso UNO. Raccomandato: **BIGSERIAL** interno (`intake_id BIGINT`)
> + eventuale uuid pubblico se serve esporlo. P3/P5 vanno corretti.

---

## 5. RACCOMANDAZIONE DI CHIUSURA

Le 5 parti sono **architetturalmente concordi** (1 coda locale sul Pro, 1 orchestratore
deterministico, stadi locali, P4 read-only, P5 unico writer, evolver volume-gated) — i fix
panel C1-C7 sono recepiti ovunque. **Ma i contratti dato-per-dato NON combaciano**: vanno
fatti convergere prima di scrivere codice. Ordine di fix consigliato:

1. **X3/X2/X4/X11** (naming/tipi atomici: source, pipeline_version, source_ref, blob_hash) — meccanico, 1 pass.
2. **X1** (modello tabelle: adottare P1 2-tabelle, P2 riscrive `intake_job`→`intake_queue`, togliere la UNIQUE che vieta multi-cliente). Decisione di design, sblocca C1.
3. **X7** (idempotency-key canonica `sha256(source|source_ref|blob_hash|pipeline_version)`) — deriva da X1.
4. **X5+X6** (giunzione P3→P4: P4 consuma JSON singoli + P3 propaga il blocco `source{}`/provenance da P1). La più sostanziale.
5. **X8/X9/X10/X12** (allineamento P4↔P5: una macchina-stati, `client_id_hint`, `needs_review_fields`).

Con questi 5 step le 5 parti si incastrano. **Nessun ridisegno architetturale necessario —
solo unificazione di contratti.**
