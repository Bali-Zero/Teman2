---
date: 2026-06-04
domain: operations
client_case: false
sources:
  - https://github.com/docling-project/docling
  - https://huggingface.co/ibm-granite/granite-docling-258M-mlx
  - https://modal.com/blog/8-top-open-source-ocr-models-compared
  - https://github.com/procrastinate-org/procrastinate
  - https://github.com/janbjorge/pgqueuer
  - https://moj-analytical-services.github.io/splink/index.html
  - https://github.com/rapidfuzz/RapidFuzz
  - https://ekzhu.github.io/datasketch/
  - https://github.com/JohannesBuchner/imagehash
  - https://pymupdf.readthedocs.io/en/latest/about.html
  - https://pdfmux.com/blog/pymupdf-vs-pdfplumber/
---

# 05b — Reusable OSS Libraries for Unified Document-Intake (Bali Zero)

**Scope**: deep research for mature, open-source, 2026-current libraries to bolt onto the unified document-intake system **instead of writing code from scratch**.
**HARD constraints**: must run LOCAL on Mac Apple Silicon, $0, offline, PII-safe (NO cloud calls). Libraries that phone home / require API keys are flagged and rejected.

---

## TL;DR decision table

| Esigenza | Lib consigliata | Install | Maturita | Adottare |
|---|---|---|---|---|
| 1. Image pre-processing (deskew/CLAHE/denoise/upscale) | **OpenCV** (`cv2`) core + **scikit-image** for filters | `pip install opencv-python-headless scikit-image` | OpenCV 4.11+, de-facto standard, massive maint | **SI** (compose recipe, ~40 LOC — no all-in-one lib worth it) |
| 2. OCR documenti locali (tabelle, indonesiano) | **Docling** (IBM) as full pipeline + **Granite-Docling-258M MLX** model; keep **qwen3-vl** as VLM fallback | `pip install docling` (auto-picks MLX model on Apple Silicon) | LF AI & Data project, Apache-2.0, v2.46+, very active | **SI** (pipeline completa, vale moltissimo) |
| 3. Worker queue su Postgres (SKIP LOCKED, retry, DLQ) | **Procrastinate** (LISTEN/NOTIFY + SKIP LOCKED, native asyncpg) | `pip install procrastinate` | v3.8.1 (apr 2026), 1.3k star, 111 release | **SI** (non riscrivere il broker) |
| 4. Entity resolution (nome+tel+passaporto -> cliente) | **RapidFuzz** (scoring/soglie) + **Splink** (probabilistic linkage se servono blocking+pesi) | `pip install rapidfuzz splink` | RapidFuzz 3.14+ C++ veloce; Splink usato da ABS Census 2026 | **SI** (RapidFuzz subito; Splink se il volume cresce) |
| 5. Content-hash + perceptual hash (dedup) | **xxhash** (byte-exact) + **ImageHash** (phash near-dup img) + **datasketch** (MinHash LSH near-dup testo) | `pip install xxhash ImageHash datasketch` | tutti maturi, manutenuti | **SI** (tre primitive ortogonali, banali da usare) |
| 6. PDF -> immagini + estrazione | **PyMuPDF** (`fitz`) render+text; **pdfplumber** solo per tabelle vettoriali | `pip install pymupdf pdfplumber` | PyMuPDF leader perf (180 pg/s), AGPL caveat | **SI** (PyMuPDF default; vedi nota licenza) |

---

## 1. Document image pre-processing

**Non esiste una lib "document scan cleanup in una chiamata" matura e $0** che valga adottare come dipendenza pesante. Le soluzioni one-call serie (Dynamsoft) sono commerciali. La ricetta standard 2026 e una composizione di ~40 righe su **OpenCV + scikit-image**:

- **Deskew**: grayscale -> Gaussian blur -> Otsu threshold -> dilate text-lines -> `cv2.minAreaRect` median angle -> `cv2.warpAffine` (no-crop). Pattern canonico, stabile da anni.
- **CLAHE contrast**: converti in LAB, applica `cv2.createCLAHE(clipLimit, tileGridSize)` sul canale L. Migliora contrasto locale senza amplificare rumore.
- **Denoise**: `cv2.fastNlMeansDenoising` (luminance) o filtri scikit-image (`skimage.restoration`, median).
- **Upscale**: per documenti, `cv2.resize` INTER_CUBIC e sufficiente; super-resolution ML (Real-ESRGAN) e overkill e pesante — sconsigliato salvo scan a bassa DPI.

**Verdetto**: SI, ma come **recipe interna riusabile** (un modulo `preprocess.py`), non cercando un wrapper magico. Tutto offline, zero cloud.

---

## 2. OCR locale per documenti (tabelle, documenti indonesiani)

Tre tool open-source dominano il PDF->markdown/struct 2026: **MarkItDown** (MS, veloce/superficiale), **Docling** (IBM, lento/strutturalmente ricco), **Marker** (Datalab, GPU-hungry, accuracy-first).

### Docling (IBM) — RACCOMANDATO come pipeline
- Progetto LF AI & Data Foundation (nato IBM Research Zurich). Apache-2.0. `pip install docling`, attivissimo (v2.46+).
- **Pipeline completa**: layout analysis, table structure (preserva topologia tabelle), reading order, math/code, export Markdown/HTML/JSON. NON e solo un wrapper OCR.
- **MLX su Apple Silicon**: il modello **Granite-Docling-258M** ha una build MLX dedicata (`ibm-granite/granite-docling-258M-mlx`, Apache-2.0). Docling **sceglie automaticamente** la versione MLX quando gira su Mac. Emette DocTags (grammatica strutturale LLM-friendly) -> tabelle preservate con coordinate.
- 100% locale, offline, zero cloud. PII-safe.

### Alternative OCR pure (engine, non pipeline)
- **PaddleOCR (PP-StructureV3)**: fortissimo su table recognition/formule/handwriting; alta accuracy carattere e throughput nei benchmark 2026. Ottimo se servono solo le tabelle.
- **Surya** (Datalab): 90+ lingue, layout/multi-colonna, e il motore dietro Marker.
- **dots.ocr**: vince per character accuracy nei benchmark 2026, ma piu giocattolo/research come pipeline.
- **Tesseract**: maturo, ma debole su tabelle e layout complessi — solo fallback testo semplice.

**Verdetto**: SI, **Docling come pipeline primaria** (auto-MLX su Mac, gestisce tabelle nativamente, indonesiano OK via VLM multilingue). Tieni **qwen3-vl locale come fallback VLM** per scan rumorosi/manoscritti. PaddleOCR opzionale se vuoi un engine tabelle dedicato. Tutto offline.

---

## 3. Worker queue / job processing su Postgres

Esistono lib mature che danno SKIP LOCKED + lease + retry **senza scriverlo a mano**. Il repo Bali Zero usa gia asyncpg + Postgres + un pattern outbox (EventBus LISTEN/NOTIFY), quindi il fit e naturale.

### Procrastinate — RACCOMANDATO
- v3.8.1 (apr 2026), 1.3k star, 111 release, Python 3.10+, Postgres 13+.
- Usa **LISTEN/NOTIFY + FOR UPDATE SKIP LOCKED**, native **asyncpg**, sync+async, **periodic tasks, retries, task locks**. Broker = Postgres (zero infra extra).
- Caveat: **DLQ non e un primitivo first-class** — i job falliti dopo max retry restano marcati `failed` (gestibili via query), non una coda separata. Per Bali Zero e accettabile (DLQ = view su stato failed + alert).

### pgqueuer — alternativa solida
- v1.0.2 (mag 2026), 1.5k star. AsyncpgDriver / AsyncpgPoolDriver, cron ricorrenti che sopravvivono a restart, retry con backoff via custom executor. Piu minimalista; anch'esso senza DLQ esplicito.

### arq / dramatiq
- **arq**: broker Redis, non Postgres — introduce una dipendenza infra in piu, scartato (vincolo: stare su Postgres esistente).
- **dramatiq**: pensato per Redis/RabbitMQ; broker PG non first-class. Scartato.

**Verdetto**: SI, **Procrastinate** (fit asyncpg+PG nativo, retry+lock+periodic pronti). Implementa DLQ come thin view sui job `failed` + replay manuale — NON riscrivere il broker.

---

## 4. Entity resolution / fuzzy matching nomi

### RapidFuzz — RACCOMANDATO per scoring/soglie
- v3.14+, C++, ~40% piu veloce dei concorrenti (2500 pair/s single-thread vs 1600 jellyfish). MIT-style, mantenuto attivamente.
- Perfetto per "match nome+telefono+passaporto -> cliente" con soglie: WRatio/token_set_ratio su nomi, exact/normalized su passaporto+telefono. Componi uno score pesato + threshold.
- **jellyfish**: utile solo per matching fonetico (Soundex/Metaphone/Jaro-Winkler) sui nomi; piu lento, niente fuzzy generale. Usalo come feature aggiuntiva, non come motore.

### Splink — se serve probabilistic linkage scalabile
- Probabilistic record linkage (Fellegi-Sunter), term-frequency adjustments, blocking, gira in DuckDB su laptop (1M record ~1 min). Usato da Australian Bureau of Statistics per il Census 2026 — molto maturo.
- Adotta Splink **quando** il dataset cresce e serve blocking + pesi appresi; per il volume attuale Bali Zero, RapidFuzz + regole deterministiche (passaporto/telefono come chiavi forti) bastano.

### dedupe / recordlinkage
- **dedupe**: non scala oltre ~2M record (limiti memoria) — non necessario qui, ma usabile.
- **recordlinkage**: meno mantenuto/documentato; preferire Splink.

**Verdetto**: SI — **RapidFuzz subito** (scoring+soglie), **Splink in riserva** per quando il volume giustifica linkage probabilistico. jellyfish opzionale per fonetica nomi.

---

## 5. Content-hash + perceptual hash (dedup)

Tre primitive **ortogonali**, tutte mature e $0/offline:

- **xxhash**: hash byte-exact ultra-veloce -> dedup file identici / idempotency key d'ingestione. `pip install xxhash`.
- **ImageHash** (phash/dhash/average): near-duplicate immagini via Hamming distance su perceptual hash. Standard de-facto (`JohannesBuchner/imagehash`), maturo. Per "stesso documento ri-fotografato".
- **datasketch** (MinHash + LSH): near-duplicate **testo** a scala (OCR output quasi-identico). Maturo, usato in data-mining/ML.

(Per immagini, in alternativa `imagededup` di idealo impacchetta phash+CNN, ma ImageHash da solo basta e pesa meno.)

**Verdetto**: SI a tutte e tre — banali da integrare, ognuna copre un asse diverso (byte-exact / immagine-percettiva / testo-percettivo).

---

## 6. PDF -> immagini + estrazione

### PyMuPDF (fitz) — RACCOMANDATO default
- Leader prestazioni 2026: ~180 pagine/s text extract (8-12x pdfplumber), rendering pagina->immagine ad alta fedelta, estrazione immagini embedded, layout data. Un solo tool per render + testo + immagini.
- **Caveat licenza**: **AGPL-3.0**. Per uso interno Bali Zero (non distribuito come SaaS pubblico, gira sui Mac di Zero) e accettabile; va tenuto presente se mai esposto come servizio di rete a terzi.

### pdfplumber — solo tabelle vettoriali
- MIT, char-level layout, ottimo per **estrarre tabelle da PDF vettoriali** (non scansionati) su batch piccoli. Lento. Usalo mirato dove le tabelle sono testo vero, non immagine.

### pdf2image / pdfminer
- **pdf2image**: render fedele pagina->PNG ma richiede `poppler` di sistema e NON estrae testo — PyMuPDF copre lo stesso caso senza la dipendenza esterna. Ridondante.
- **pdfminer.six**: motore sotto pdfplumber; non usarlo diretto.

**Verdetto**: SI — **PyMuPDF default** (render+text+immagini in un tool), **pdfplumber mirato** per tabelle vettoriali. Per PDF scansionati il flusso e PyMuPDF render -> pre-processing (sez.1) -> Docling/OCR (sez.2).

---

## Note di sovranita (Law 2 / PII)
Tutte le librerie sopra girano 100% locali e offline. Nessuna richiama cloud. Granite-Docling MLX e qwen3-vl sono modelli locali. Da diffidare e **rifiutare** in questo dominio: qualunque wrapper "OCR/parse" che richieda API key (Textract, Mistral OCR API, Azure DI, Google Document AI, MarkItDown+LLM-cloud). Verificare sempre che il pacchetto non apra connessioni in fase di parsing.

## Sintesi adozione (priorita)
1. PyMuPDF + recipe OpenCV/scikit-image (preprocess) — fondamenta intake.
2. Docling (auto-MLX) come OCR-pipeline, qwen3-vl fallback.
3. Procrastinate come worker-queue su Postgres esistente.
4. RapidFuzz per entity-resolution (Splink in riserva).
5. xxhash + ImageHash + datasketch per i tre assi di dedup.
