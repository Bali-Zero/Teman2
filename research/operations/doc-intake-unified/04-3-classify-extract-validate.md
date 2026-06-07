---
date: 2026-06-04
domain: operations
study: doc-intake-unified
phase: 4 — PART 3/5 — CLASSIFY → EXTRACT → VALIDATE (the technical core)
client_case: false
scope: i 3 stadi di elaborazione, TUTTI LOCALI (PII mai cloud — Law 2)
sources:
  - research/operations/doc-intake-unified/01-system-study.md
  - research/operations/doc-intake-unified/02a-external-sota.md
  - research/operations/doc-intake-unified/02b-nb-validation-rules.md
  - research/operations/doc-intake-unified/03-panel-review.md
  - live: MODEL_TOPOLOGY.json + ollama list + ocr_dispatcher_service.py + crm_enhanced.py (Pro, 2026-06-04)
panel_fixes_recepiti:
  - C3 (confidence PER-CAMPO e per-tipo, non doc-level 0.60 flat)
  - C6 (no CoT grezzo del classify = PII; solo rationale strutturato + model/version/hash)
---

# FASE 4 — PARTE 3/5: CLASSIFY → EXTRACT → VALIDATE

> Questo è il **cuore tecnico** del document-intake unificato. Tre stadi, **tutti
> locali**: nessun byte di PII lascia la macchina (Law 2 / UU-PDP). Riceve un item dalla
> coda intake (PARTE 2 orchestrator), produce un **JSON intake strutturato** che è il
> contratto verso PARTE 4 (routing) e PARTE 5 (HITL).

---

## 0. Posizione nel sistema + contratto di confine

```
 PARTE 2 (orchestrator/coda)                PARTE 4 (routing)
        │                                          ▲
        │ INPUT: {blob_path, type_hint, ...}       │ OUTPUT: intake JSON
        ▼                                          │
 ┌──────────────────────────────────────────────────────────┐
 │  PARTE 3 — STRICT-LOCAL PROCESSING CORE                   │
 │                                                          │
 │  [1] CLASSIFY   pre-process img → OCR qwen3-vl:8b →       │
 │                 doc-type + confidence                    │
 │  [2] EXTRACT    SEA-LION-32B → campi canonici per-tipo,  │
 │                 confidence PER-CAMPO (mai inventare)     │
 │  [3] VALIDATE   regole NB deterministiche per-tipo →     │
 │                 pass/warn/fail per regola                │
 │                                                          │
 │  ZERO tier Gemini. ZERO cloud. ZERO CoT grezzo salvato.  │
 └──────────────────────────────────────────────────────────┘
                            │
                            ▼ PARTE 5 (HITL) legge needs_review_fields[]
```

### 0.1 INPUT (da PARTE 2 — orchestrator/coda)

L'orchestratore consegna a PARTE 3 **un item già de-duplicato** (SHA-256 + phash, C1) e
con un **lease atomico** (`FOR UPDATE SKIP LOCKED`, C2). Il contratto di ingresso:

```jsonc
{
  "intake_id": "uuid",            // chiave coda, idempotency key
  "blob_path": "/Users/nuzantara/wa-mirror-media/<phone>/<file>",  // file LOCALE su disco
  "blob_hash": "sha256:...",      // già calcolato da PARTE 2 (dedup + idempotenza)
  "mime_type": "image/jpeg|application/pdf",
  "source": "whatsapp|drive|zoho",
  "type_hint": "passport|akta|null",  // Tier-1 keyword router (filename/folder/subject) — può essere null
  "client_id_hint": 1234,         // se PARTE 2 ha già risolto (WA media_stored_path), altrimenti null
  "pipeline_version": "intake-v1" // PARTE della dedup-key composta (C1): permette ri-OCR post model-upgrade
}
```

> **Nota C1**: `pipeline_version` è parte della chiave di dedup a monte. PARTE 3 lo
> **propaga** in output così un upgrade modello (es. qwen3-vl:8b → :12b) genera un nuovo
> record processabile invece di essere scartato in silenzio come "hash già visto".

### 0.2 OUTPUT (verso PARTE 4 routing + PARTE 5 HITL) — **CONTRATTO**

Vedi §5 per lo schema verbatim completo. In sintesi:
`{type, type_confidence, fields{value, confidence, source_page, raw_span}, validation_results[{rule, level, message}], needs_review_fields[], processing_meta{...}, status}`.

---

## 1. STADIO 1 — CLASSIFY

**Obiettivo**: da `blob_path` → testo OCR pulito + **tipo documento** con confidence.
Modello via `MODEL_TOPOLOGY.json` → `get_role("ocr_vision")` = `qwen3-vl:8b`
(upgrade da qwen2.5vl:7b: più robusto su basso-contrasto e foto WhatsApp).

### 1.1 Pre-processing pipeline immagine (il 70%→92% OCR)

La ricerca SOTA (02a, Docling/IDP) e l'evidenza pratica indicano che il pre-processing
porta l'accuratezza OCR da ~70% (foto WhatsApp grezza) a ~92%. Pipeline deterministica
**prima** di toccare il VLM, tutta locale (OpenCV + Pillow, $0):

| # | Step | Tecnica | Perché |
|---|---|---|---|
| 1 | **Decode + page split** | PDF → pagine raster 1:1 (pypdfium2/pdf2image); image → 1 pagina | OCR per-pagina; `source_page` nel contratto |
| 2 | **Grayscale** | `cv2.cvtColor(BGR2GRAY)` | Rimuove rumore cromatico; VLM non ha bisogno del colore per il testo |
| 3 | **CLAHE contrast** | `cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))` | Contrast-Limited Adaptive Histogram Eq — recupera testo su sfondi a basso contrasto (e-KITAS, akta scansionate male) |
| 4 | **Deskew** | stima angolo via `cv2.minAreaRect` su contorni testo / Hough; rotazione affine | Foto WhatsApp inclinate → MRZ/righe storte rompono l'OCR |
| 5 | **Denoise (light)** | `cv2.fastNlMeansDenoising` solo se rumore stimato > soglia | Rimuove grana JPEG senza sfumare i caratteri piccoli (NIK/NIB) |
| 6 | **Upscale 300 DPI** | upscale a lato lungo ≥ ~2400px (bicubic / Real-ESRGAN x2 se disponibile, altrimenti bicubic) | I VLM leggono molto meglio testo a 300dpi-equivalente; cifre piccole (NPWP 16) |
| 7 | **Binarize (condizionale)** | Sauvola/adaptive threshold **solo** per documenti ad alto contrasto testo-su-bianco (NIB/OSS printout) | NON binarizzare foto a colori con ologrammi (KITAS) — distrugge il volto/foto |

**Implementazione**: nuovo `intake/preprocess.py`, funzione pura
`preprocess(blob_path, mime) -> list[PreprocessedPage]` dove ogni pagina porta
`{page_no, image_bytes_png, applied_steps[], quality_score}`. `quality_score` (blur var
di Laplacian + contrasto stimato) diventa un segnale: pagina sotto-soglia → flag
`low_image_quality` che PARTE 5 vede.

> **PII**: le immagini pre-processate sono temporanee, **mai** scritte fuori dallo store
> locale cifrato (C6). Cancellate a fine intake; solo `applied_steps` + `quality_score`
> sono persistiti (no PII).

### 1.2 OCR + classificazione (qwen3-vl:8b, zero-shot + CoT)

Una **singola chiamata VLM per pagina** fa OCR (estrae il testo) **e** propone il
doc-type, zero-shot con chain-of-thought (02a: zero-shot VLM raggiunge accuratezza
production-grade senza training di template). Tipi:
`akta | ktp | passport | nib | npwp | kitas | sk | oss | unknown`.

Prima della chiamata VLM, **riusa il Tier-1 keyword router** già in produzione
(`ocr_dispatcher_service.dispatch_ocr_by_folder`, righe 170-308): se `type_hint` o le
keyword filename/folder matchano (passport/visa/nib/npwp/company_profile), il tipo è
**pre-assegnato con alta priorità** e il VLM serve solo a confermare (0 cloud, 0 costo
inferenza extra). Il VLM è il fallback per `type_hint=null`.

**Gate confidence classify (C3)**: il vecchio gate doc-level flat 0.70/0.60 è
**abbandonato**. Per il *tipo* usiamo una soglia **per-tipo**:

| doc_type | classify-confidence min (auto) | sotto soglia |
|---|---|---|
| passport, kitas, npwp, nib | **0.85** (alto rischio, identità/fiscale/legale) | → review queue, type marcato `uncertain` |
| akta, sk, oss | 0.75 | → review |
| ktp | 0.80 | → review |
| unknown | n/a | → sempre HITL (tipo non riconosciuto) |

### 1.3 C6 — niente CoT grezzo salvato (PII firewall sui sottoprodotti)

Il prompt CoT del classify ragiona **su PII visibile** (numeri passaporto, NIK, nomi).
Il ragionamento grezzo del modello **NON viene mai persistito**. Persistiamo solo:

```jsonc
"classify_rationale": {
  "decision": "passport",
  "signals": ["MRZ-like two-line block", "ICAO photo zone", "field 'date of expiry'"],  // strutturato, NO valori PII
  "model": "qwen3-vl:8b",
  "model_version": "<ollama-digest>",
  "pipeline_version": "intake-v1",
  "ocr_text_hash": "sha256:..."   // hash, NON il testo
}
```

L'OCR-text completo (che contiene PII) vive **solo** nello store locale cifrato e viene
passato in-process a EXTRACT; non finisce in log, Telegram, né nel JSON di output.

### 1.4 Fork STRICT-LOCAL del motore OCR (no tier Gemini)

`_gemini_ocr` (`crm_enhanced.py:74`) oggi è una cascata 3-tier: (1) Ollama qwen2.5vl →
(2) Gemini CLI → (3) Gemini API. Su Ollama down, **PII va a Google**. PARTE 3 introduce
`intake/local_ocr.py::local_ocr(image, prompt) -> str` che è il **fork strict-local**:

```
Attempt 1: Ollama qwen3-vl:8b           (get_role("ocr_vision"))
Attempt 2: pdfminer.six (solo PDF testuale, no immagini)   — locale
Attempt 3: tesseract OCR ind+eng        — locale
   ── se TUTTI falliscono → status="ocr_failed", item → DLQ (C2), MAI Gemini.
```

I tier Gemini CLI/API (righe 126-220 di `crm_enhanced.py`) sono **rimossi dal fork**.
Riuso: la struttura del prompt, il parsing JSON, lo schema di ritorno. Path Gemini resta
disponibile **solo** per contenuti esplicitamente non-PII (fuori da questo intake).

---

## 2. STADIO 2 — EXTRACT

**Obiettivo**: dal testo OCR (in-process da CLASSIFY) → **campi canonici per-tipo**, con
**confidence per-campo**, ragionando sull'OCR. Modello via
`get_role("intake_extraction")` = `aisingapore/Qwen-SEA-LION-v4-32B-IT:q4_k_m` (già
pullato sul Pro, 19GB, verificato live 2026-06-04). SEA-LION è SEA-fluent →
ragiona meglio su bahasa/akta/NIB di un modello generico.

### 2.1 Estrazione schema-driven per-tipo

Per ogni doc_type, uno **schema canonico** (derivato verbatim dai blocchi "Campi da
estrarre" di 02b §2.x). SEA-LION riceve: OCR-text + lo schema JSON target del tipo + la
regola d'oro. Output: ogni campo con `{value, confidence, source_page, raw_span}`.

**Regola d'oro (mai inventare — C6-aligned)**: se un campo non è presente o illeggibile,
SEA-LION ritorna `value: null` + `confidence: 0.0` + `flag: "not_found"`. **Vietato
allucinare un valore plausibile.** Il prompt lo impone esplicitamente
("Return null for any field you cannot read verbatim from the text. Never guess.").

Schemi canonici (sintesi — campi completi in 02b §2):

| doc_type | campi canonici chiave |
|---|---|
| **akta** | nomor_akta, tanggal_akta, nama_notaris, nomor_sk_kemenkumham, tanggal_sk, nama_pt, modal_dasar_idr, modal_disetor_idr, kbli_codes[], shareholders[], direksi[], komisaris[], domisili_zona |
| **nib** | nib (13), kbli_codes[], risiko_usaha, status_nib, tanggal_terbit, nama_perusahaan |
| **npwp** | npwp_raw, npwp_format, npwp_normalized (16), npwp_type |
| **kitas** | nomor_dokumen, kitas_code, legacy_code_flag, nama, tanggal_lahir, berlaku_sampai |
| **passport** | passport_number, surname, given_names, nationality, date_of_birth, date_of_expiry |
| **ktp** | nik (16), nama, tempat_tanggal_lahir, alamat (campi base; struttura interna = gap NB, §2.6) |
| **sk** | nomor_sk, tanggal_sk, jenis_sk (pendirian/perubahan/PERBAIKAN), nama_pt, document_number(=nomor_sk) |
| **oss** | nib_ref, kbli_codes[], jenis_perizinan, tanggal_terbit |

### 2.2 Confidence per-campo (C3) — calibrazione

La confidence per-campo combina due segnali (non solo il logit del modello):

1. **model self-confidence** — SEA-LION emette un punteggio per-campo (prompt lo richiede).
2. **format-prior** — se il valore matcha il pattern atteso del campo (es. NIB = `^\d{13}$`)
   la confidence è confermata/alzata; se non matcha, è abbassata e il campo è candidato HITL.

Questo accoppia EXTRACT e VALIDATE: un NIB di 12 cifre **non** è "alta confidence con
errore di formato" — è basso-confidence-per-format-mismatch, va in review.

---

## 3. STADIO 3 — VALIDATE

**Obiettivo**: applicare le **regole NB deterministiche** (02b) ai campi estratti.
Per-regola → `level ∈ {pass, warn, fail}` + messaggio. **Nessun LLM qui**: regole pure
(regex, confronti numerici, date), auditabili e riproducibili. L'unico ramo non-statico è
la **KBLI foreign-ownership che è DINAMICA** (vedi §3.2).

### 3.1 Tabella regole di validazione per-tipo

| doc_type | regola | controllo | level su violazione | fonte 02b |
|---|---|---|---|---|
| **nib** | lunghezza NIB | `^\d{13}$` (esatto 13 cifre) | **fail** | §2.2 |
| nib | status | `status_nib ∈ {aktif,nonaktif,ditangguhkan}` | warn se non-aktif | §2.2 |
| nib | kbli cross-akta | kbli_codes(nib) ⊆ kbli_codes(akta) | warn (mismatch OSS) | §2.2/§3 |
| **npwp** | formato 16 cifre | post 01/07/2024: `^\d{16}$` | **fail** se ≠16 e ≠15 | §2.3 |
| npwp | legacy 15→16 | se 15 cifre → normalizza con "0" iniziale, level **warn** (legacy) | warn | §2.3 |
| npwp | tipo coerente | npwp_type ∈ {pribadi_wni,pribadi_wna,badan,cabang} | warn | §2.3 |
| **ktp** | NIK 16 cifre | `^\d{16}$` | **fail** | §2.3/§2.6 |
| **passport** | validità ≥ 6 mesi | `validity_months_remaining ≥ 6` | **fail** (<6: REJECT), **warn** (6–12: KITAS 1y non fattibile) | §2.5 |
| passport | scadenza futura | `date_of_expiry > today` | **fail** | §2.5 |
| **kitas** | E-code valido | `kitas_code ∈ {E23,E28A,E28B,E28C,E28D,E33E,E33F,E33G}` | **fail** | §2.4 |
| kitas | codici obsoleti | `code ∈ {C312,C313,C314}` → `legacy_code_flag=true` | **warn** (pre-2023 obsoleto) | §2.4 |
| kitas | KITAS ≤ passport | `berlaku_sampai ≤ passport.date_of_expiry` (Pasal 190 Ayat 3) | **fail** | §2.4 |
| **akta** | modal disetor (PMA) | `modal_disetor_idr ≥ 2_500_000_000` | **fail** | §2.1 |
| akta | modal dasar | `modal_dasar_idr ≥ 10_000_000_000` | **warn** | §2.1 |
| akta | nome PT | `nama_pt` inizia con `"PT "` | warn | §2.1 |
| akta | SK presente | `nomor_sk_kemenkumham` non-null (entità perfezionata) | **warn** (akta senza SK = non perfezionata) | §2.1 |
| akta | data SK ≥ akta | `tanggal_sk ≥ tanggal_akta` | warn | §2.1 |
| akta | azionisti ≥ 2 | `len(shareholders) ≥ 2` | warn | §2.1 |
| akta | domicilio zona | `domisili_zona == komersial` | **fail** se residenziale | §2.1 |
| **akta/nib/oss** | KBLI 5 cifre | ogni kbli `^\d{5}$` | warn | §2.1/§2.2 |
| **akta/nib** | KBLI foreign-ownership | **DINAMICO** → §3.2 (query live, no cache statica) | warn/fail per status | §3 |
| **sk** | versioning | jenis_sk=PERBAIKAN → **link**, non fonde (§3.3) | info | §2.1/C5 |

> **Soglia per-tipo (C3) anche su VALIDATE**: un campo che fallisce un controllo
> `fail` su tipo ad alto rischio (passport/nib/kitas/npwp) forza l'intero documento in
> review anche se gli altri campi sono alti; un `warn` su tipo a basso rischio passa con
> flag. La decisione finale auto-commit/HITL è di PARTE 5, ma PARTE 3 fornisce il
> materiale per-campo + per-regola che la rende deterministica.

### 3.2 KBLI foreign-ownership — DINAMICA, query live (NO cache statica)

02b §3 è esplicito: la DNI (Daftar Negatif Investasi) **cambia** — KBLI 73100 era
TERBUKA (Perpres 10/2021) → TERBATAS max 49% (BPS 7/2025 + Perpres 14/2024). Una cache
statica produrrebbe validazioni **sbagliate** dopo ogni aggiornamento normativo.

Quindi VALIDATE **non** hardcoda lo status. Per ogni `kbli_code` estratto:

1. **query live** alla tabella KBLI canonica del backend (payload flat: `kode_kbli`,
   `pma_status`, `kategori_risiko` — Data Invariant §9 del CLAUDE.md). Questa è la
   sorgente di verità mantenuta dal sistema KBLI esistente.
2. status risolto → `TERBUKA` (pass), `TERBATAS` (warn + cap%: cross-check con
   `shareholders[].persentase` WNA ≤ cap), `TERTUTUP` (**fail**: 0% WNA).
3. se il `kode_kbli` **non è nella tabella** o è stale → **non indovinare**:
   `level: warn`, flag `kbli_status_unresolved`, → NB-3/NB-6 edge-case query (offline,
   fuori hot-path) come da 02b §5 "[NB Query] (solo edge case)".

> Mai una mappa `{73100: "TERBUKA"}` nel codice. Il valore di status arriva sempre da
> una lookup live. È la differenza tra una regola e un bug latente a scadenza.

### 3.3 Versioning SK ↔ PERBAIKAN (C5) — link, non fonde

SK originale e SK-PERBAIKAN (correzione) hanno **byte diversi** → il dedup SHA-256 (PARTE
2) **non** li collassa, correttamente. VALIDATE li **linka** su
`(doc_type, client_id, document_number)` ed emette un `version_link`:

```jsonc
"version_link": {
  "document_number": "<nomor_sk>",
  "relation": "supersedes|superseded_by|original",
  "validity_state": "active|superseded",
  "linked_intake_ids": ["..."]   // l'altra versione, se nota
}
```

Recependo C5: aggiungiamo `validity_state` (supersession) — il record master con il
puntatore all'ultima versione verificata è materializzato in PARTE 4 (routing), ma PARTE
3 fornisce il link e lo stato. Le versioni **non sono mai fuse**.

---

## 4. Pseudocodice orchestrazione PARTE 3 (deterministico, single-path)

```python
async def process_intake(item: IntakeItem) -> IntakeResult:
    meta = ProcessingMeta(pipeline_version=item.pipeline_version)

    # ── STADIO 1: CLASSIFY ───────────────────────────────────────────
    pages = preprocess(item.blob_path, item.mime_type)          # local, OpenCV
    ocr_text, classify = await classify_doc(                    # qwen3-vl:8b local
        pages, type_hint=item.type_hint, tier1_keywords=router_keywords(item)
    )
    meta.classify_rationale = strip_pii(classify.rationale)     # C6: no raw CoT
    if classify.confidence < per_type_classify_threshold(classify.doc_type):
        return IntakeResult(status="needs_review", type=classify.doc_type,
                            type_confidence=classify.confidence, meta=meta,
                            needs_review_fields=["__type__"])

    # ── STADIO 2: EXTRACT ────────────────────────────────────────────
    schema = CANONICAL_SCHEMA[classify.doc_type]
    fields = await extract_fields(ocr_text, schema)             # SEA-LION-32B local
    #   each field: {value|null, confidence, source_page, raw_span}; never invent

    # ── STADIO 3: VALIDATE ───────────────────────────────────────────
    results = []                                                # deterministic rules
    for rule in VALIDATION_RULES[classify.doc_type]:
        results.append(rule.apply(fields, kbli_lookup=live_kbli_status))  # §3.2 live
    version_link = build_version_link(classify.doc_type, fields)          # §3.3

    # ── per-field/per-type gating (C3) → needs_review_fields ─────────
    needs_review = compute_review_fields(fields, results, classify.doc_type)
    status = "needs_review" if needs_review else "validated"

    return IntakeResult(type=classify.doc_type, type_confidence=classify.confidence,
                        fields=fields, validation_results=results,
                        version_link=version_link, needs_review_fields=needs_review,
                        processing_meta=meta, status=status)
```

Nessun ramo agent↔agent, nessuna negoziazione (02a "15-tool trap"; 03 verdetto unanime).
Un solo path serializzato e replayabile (C2).

---

## 5. CONTRATTO JSON DI OUTPUT (verbatim — verso PARTE 4 + PARTE 5)

```jsonc
{
  "intake_id": "uuid",
  "blob_hash": "sha256:...",
  "pipeline_version": "intake-v1",
  "source": "whatsapp|drive|zoho",
  "client_id_hint": 1234,

  "type": "akta|ktp|passport|nib|npwp|kitas|sk|oss|unknown",
  "type_confidence": 0.0,

  "fields": {
    "<canonical_field_name>": {
      "value": "string|number|null",
      "confidence": 0.0,
      "source_page": 1,
      "raw_span": "verbatim OCR substring (local-only; redactable before any non-PII sink)",
      "flag": null
    }
  },

  "validation_results": [
    {
      "rule": "nib_length_13|npwp_format_16|passport_validity_6m|kitas_le_passport|modal_disetor_min|kbli_foreign_ownership|...",
      "level": "pass|warn|fail",
      "message": "human-readable reason",
      "fields_involved": ["nib"],
      "rule_source": "02b §2.2"
    }
  ],

  "version_link": {
    "document_number": "string|null",
    "relation": "original|supersedes|superseded_by|null",
    "validity_state": "active|superseded|null",
    "linked_intake_ids": []
  },

  "needs_review_fields": ["__type__", "modal_disetor_idr", "..."],

  "status": "validated|needs_review|ocr_failed|dead",

  "processing_meta": {
    "ocr_model": "qwen3-vl:8b",
    "ocr_model_version": "<ollama-digest>",
    "extract_model": "aisingapore/Qwen-SEA-LION-v4-32B-IT:q4_k_m",
    "extract_model_version": "<ollama-digest>",
    "preprocess_steps": ["grayscale","clahe","deskew","upscale300"],
    "image_quality_score": 0.0,
    "ocr_text_hash": "sha256:...",
    "classify_rationale": {
      "decision": "passport",
      "signals": ["mrz_block","icao_photo_zone","field_date_of_expiry"],
      "model": "qwen3-vl:8b"
    },
    "processed_at": "2026-06-04T00:00:00+08:00",
    "all_local": true
  }
}
```

> **PII boundary nel contratto**: `fields[].raw_span` e `value` contengono PII e
> rimangono **locali** (D1 CRM Postgres locale / Drive ordinato locale, mai B1 RAG/B2
> NotebookLM). `processing_meta` è **PII-free by construction** (hash, non testo;
> signals strutturati, non valori) → è l'unica parte loggabile/Telegram-abile (C6).

---

## 6. MODEL_TOPOLOGY.json — ruoli da aggiungere

PARTE 3 richiede 2 nuovi `roles` (oggi assenti: esiste solo `vision: qwen2.5vl:7b`). Da
aggiungere (no model-id hardcoded nel codice, sempre `get_role(...)`):

```jsonc
"roles": {
  "ocr_vision":        "qwen3-vl:8b",                               // CLASSIFY (upgrade da qwen2.5vl:7b)
  "intake_extraction": "aisingapore/Qwen-SEA-LION-v4-32B-IT:q4_k_m" // EXTRACT (già pullato sul Pro)
}
```

**Stato empirico modelli (Pro, `ollama list` 2026-06-04)**:
- ✅ `aisingapore/Qwen-SEA-LION-v4-32B-IT:q4_k_m` — **già presente** (19GB, pull 3h fa).
- ⚠️ `qwen3-vl:8b` — **NON ancora pullato** (presente solo `qwen2.5vl:7b`). Azione build
  PARTE successiva: `ollama pull qwen3-vl:8b`. Fallback transitorio sicuro: `qwen2.5vl:7b`
  (resta strict-local) finché qwen3-vl:8b non è warm. RAM Pro 48GB regge SEA-LION-32B
  (~19GB) + qwen3-vl:8b (~6-8GB) ma **non in parallelo a freddo**: serializzare
  CLASSIFY→EXTRACT (lo fa già il single-path §4) o keep_alive selettivo.

---

## 7. Cosa si RIUSA vs cosa si FORKA vs cosa è NUOVO

| Componente | Azione | Riferimento |
|---|---|---|
| Tier-1 keyword router (filename/folder) | **RIUSA** | `ocr_dispatcher_service.py:170-308` |
| Schema `ocr_status`/parsing JSON ritorno | **RIUSA** | dispatcher + crm_enhanced |
| `_gemini_ocr` cascata 3-tier | **FORKA strict-local** (drop tier 2-3 Gemini) | `crm_enhanced.py:74-220` |
| Ollama qwen-vl branch (attempt 1) | **RIUSA come base del fork** | `crm_enhanced.py:88-121` |
| pdfminer + tesseract (ind+eng) | **RIUSA** | `crm_guardian/ocr.py` |
| Gate confidence doc-level flat 0.70/0.60 | **SOSTITUISCI** con per-campo/per-tipo (C3) | dispatcher `_CONTENT_CONFIDENCE_THRESHOLD` |
| Pre-processing immagine (CLAHE/deskew/upscale) | **NUOVO** | `intake/preprocess.py` |
| EXTRACT SEA-LION schema-driven per-tipo | **NUOVO** | `intake/extract.py` |
| VALIDATE regole NB deterministiche | **NUOVO** | `intake/validate.py` (regole da 02b) |
| KBLI foreign-ownership live lookup | **RIUSA** tabella KBLI canonica | Data Invariant §9 |
| classify_rationale PII-stripped (C6) | **NUOVO** | `intake/classify.py` |

---

## Verdetto PARTE 3

I 3 stadi sono **tutti locali, deterministici nel commit-path, zero cloud per PII**.
CLASSIFY usa qwen3-vl:8b dietro un pre-processing che porta l'OCR a ~92%; EXTRACT usa
SEA-LION-32B (già sul Pro) schema-driven con confidence per-campo e regola d'oro
anti-allucinazione; VALIDATE applica le regole NB verbatim (02b) con la KBLI
foreign-ownership **dinamica via query live**. I fix panel sono recepiti: **C3**
(soglie per-campo e per-tipo, più severe per passport/nib/kitas/npwp) e **C6** (nessun
CoT grezzo persistito — solo rationale strutturato + model/version/hash). Il JSON di
output è il contratto stabile verso PARTE 4 (routing) e PARTE 5 (HITL).
