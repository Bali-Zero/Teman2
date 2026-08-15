---
title: "Intake Code Master — D: dead levers + external SOTA on 7 axes"
date: 2026-08-15
domain: operations
client_case: none (intake system audit, aggregate counts only, PII-redacted; no client names/phones/ids beyond client_id/proposal_id integers)
author: Claude Fable 5 interactive session (Pro) — candidacy dossier, READ-ONLY mandate
sources:
  - worktree .worktrees/docs-intake-code-master-0815 @ f6dfda994 (code read file:line in-turn; svc/rt/rd path conventions in README)
  - local nuzantara_dev Postgres 127.0.0.1:5432 (SELECT-only, default_transaction_read_only=on; W87 — never the prod MCP)
  - one prod read via scripts/pg.sh (readonly role) for the `companies` count
  - live process/plist/log state on Pro (launchctl print, ps, lsof, stat) — measured 2026-08-15
  - research/operations/doc-intake-unified/* + 2026-06-27/28, 2026-07-18 intake reports + modus PENDING-ARMS + /intake SKILL
  - external SOTA (D): URLs listed per axis, WebSearch 2026-08-15
adversarial_review: kimi-k3
---

# Deliverable D — Deep research (interna + SOTA esterna)

> Data ricerca: 2026-08-15. Fonti esterne verificate via WebSearch nel turno di scrittura (URL in fondo a ogni asse). Interna: file:line su `~/nuzantara` HEAD `f6dfda994`.

---

## D.1 Interna — quali leve sono state MISURATE morte, e perché

| Leva | Dove misurata | Numero | Perché è morta | Cosa la resusciterebbe (dati nuovi) |
|---|---|---|---|---|
| **Station 2 — ri-ricerca OCR-name/strong-id senza re-OCR** (25,4k zero-candidate) | `research/operations/2026-07-18-intake-station1-2-rescue-recall.md:99-102` | ~9 doc (0,04%) | fase-4 aveva già eseguito strong-id + fuzzy ≥0,40 correttamente; il soggetto NON è nel CRM («313 passports, 1 kitas, 62 company_names, 173 folder_id su 11.748 clienti», `:91-93`) | solo un libro chiavi più ricco (backfill verificato, GATE-11) — non un altro matcher |
| **Station 1 — re-OCR** | `:103-107` | 594/25.400 blob su disco (2,3%); «0 of the 594 are stubs» | la retention TTL=7d ha cancellato la materia prima (C-01 la sta cancellando ANCORA oggi: 5.522/5.888 WA review) | re-fetch Drive per `file_id` (24k download + 24k vision ≈ 1,2–1,7 giorni fleet, `2026-06-27-39k-drive-ocr-backlog-sovereign-pipeline.md:124`) — ma per un tetto ~0,1% se il CRM non ha le chiavi |
| **Station 0 — dedup/junk su metadati** | `:108-110`, `scripts/intake_station0_report.py` | 2.355 righe (9%) verso stato terminale | igiene, non recovery | è viva ma dry-run: manca solo l'apply (decisione) |
| **Folder-provenance m227** (unica che funziona) | `:59-82` | +1.231 candidati (5,1%), 1.005 LINK_CANDIDATE, precisione 19/20 | tetto strutturale: 88,5% dei folder-segment nominano entità assenti dal CRM (`:84-93`) | catalogare i ~1.215 person-folder senza cliente («ops intelligence», `:93-95`) |
| **LEVA-2 auto-attach strong-id⟂phone** su 48 storiche | `.claude/skills/modus/PENDING-ARMS.md:344` | 0 commit / 48 (41 senza sender phone — 38 Drive; 5 segnali discordi; 2 telefono condiviso) | la gamba telefono è STRUTTURALMENTE assente per Drive/Dropbox — «not a broken gate» | LEVA-3 name+id (shippata) e chiavi CRM |
| **npwp m248** | `scripts/intake_reprocess_backlog.py:345-352` | 3/131 match; 0 nel pool 0-candidati | 291 clienti con npwp; i doc con npwp hanno già candidati folder/fuzzy | — |
| **`--reroute-identity-backfill`** (batch-C 6 scritture) | `PENDING-ARMS.md:556` | 25 proposal con snapshot `entity_resolution` STANTIO | il reroute non era stato costruito; e anche rifatto, GATE-11 lo cappa a LINK_CANDIDATE | flag ora esiste (`intake_reprocess_backlog.py:3668-3676`), non risulta applicato |
| **Sentinel orfani** | `PENDING-ARMS.md:181` | plist «genuinely deleted, NOT resurrected» | HOME-only script morto (famiglia #1) | riarmare come StartInterval report-only con `_LIVE_STATUSES` corretto (C-07) |
| **Refinery panel (SEA-LION 32B reviewer)** | `2026-06-27-39k-…:60` («~80% noise as a reviewer, 25-45s warm»); `ollama list` oggi senza SEA-LION | disarmato | modello assente e rumoroso | non riproporre |
| **Cloud OCR Gemini opt-in** | `PENDING-ARMS.md:204` `operator[business]` | mai deciso | Law 2 / UU PDP: serve la decisione di Zero | consenso per-cliente + DPA (vedi Law 2 note in `CLAUDE.md §14`) |
| **Park-by-default (`INTAKE_REVIEW_LOOP_RETIRED`)** | `PENDING-ARMS.md:344` | +~260 righe/giorno pending-for-nobody | doveva atterrare DOPO LEVA-3; non risulta atterrata: `review_pending` continua a crescere (24.790 oggi) | decisione + implementazione (E.4 wave 1) |

**Il libro chiavi OGGI (misura 2026-08-15, non il numero di luglio).** `clients` locali 12.544 (alive 2.322): `passport_number` 2.049 totali / **1.508 alive** (lunghezze 6–16, 0 sotto 6, 20 gruppi duplicati), `kitas_number` 109, `npwp` 15/16 cifre 291, `google_drive_folder_id` 2.224, `phone` 1.607; **`companies` locale = 0 righe** (prod 1.784 — C-29). Il report di luglio (313/1/62/173) è stantio: il libro è cresciuto (backfill + autocreate + refresh), ma la gamba company è vuota sul DB del worker. Comando: `SELECT count(*) FROM clients WHERE deleted_at IS NULL AND length(regexp_replace(coalesce(passport_number,''),'[\s.\-/]','','g'))>=6` ecc.

Domanda-guida: chi ripropone Station 1/2 «così com'erano» ha fallito. Le UNICHE due leve con recall misurato >1% sono (a) provenienza-cartella e (b) chiavi CRM (backfill+GATE-11). Il redesign (E) deve quindi puntare all'**arricchimento verificato del libro chiavi** e all'**archivio freddo** che rende Station 1 di nuovo possibile a costo marginale.

Cosa prevedeva la spec e cosa manca (gap spec→realtà): `doc-intake-unified/06-fase5-hitl-writer-design.md` prevede delivery come parte del commit (oggi 241/304 non consegnati, C-08); FASE 6 «evolver» sulle `intake_corrections` mai costruita (684 righe/174 code già raccolte, `SELECT count(*), count(DISTINCT queue_id) FROM intake_corrections`).

---

## D.2 Esterna — SOTA sui 7 assi (con verdetto)

### Asse 1 — Pipeline documentali OSS (paperless-ngx e derivati LLM)

**Cosa hanno risolto meglio di noi.** paperless-ngx (3.0.x, agosto 2026) ha un modello a `consume`-folder/mail-watch + tag/correspondent/document-type con **suggerimenti** e ora funzioni LLM **opt-in, disabilitate di default** (suggestion, chat, similar-doc via RAG/FAISS, backend OpenAI o **Ollama locale**, con auto-queue dell'indicizzazione e configurazione chunk/context). Il review è "accetta/correggi il suggerimento" inline, e le correzioni alimentano il classificatore (matching automatico + rete neurale sui tag). Il punto forte è il **feedback loop chiuso per default** e la separazione netta fra "documento archiviato" (immutabile) e "metadati suggeriti" (mutabili).

**Verdetto: ADATTARE.** Non sostituire la nostra coda (Postgres-nativa, lease-correct, PII-local — già misurato in `2026-06-27-39k…:50-60`), ma copiare tre idee: (i) suggerimento≠decisione con **accept-as-label** in un click; (ii) l'archivio è indipendente dal blob "caldo" (paperless conserva l'originale + archive PDF); (iii) l'LLM è **opt-in per funzione** con backend Ollama. Scartare la parte "consume folder" (abbiamo tre adapter propri).

Fonti: https://docs.paperless-ngx.com/ · https://github.com/paperless-ngx/paperless-ngx/pull/10319 · https://releasebot.io/updates/paperless-ngx · https://technotim.com/posts/paperless-ngx-local-ai/ · https://tailscale.com/blog/paperless-ngx-local-ai-document-search

### Asse 2 — Entity resolution / record linkage

**Stato dell'arte.** Splink (MoJ UK, Python, backend SQL — DuckDB/Postgres/Spark) implementa **Fellegi-Sunter con EM** e **term-frequency adjustments** (il peso di un match dipende da quanto è raro il valore: un cognome comune vale meno) più comparison-level personalizzabili; usato per censimenti (ABS 2026 PES). Il modello dà un **match weight** additivo per colonna, interpretabile e calibrabile con "clerical review" campionata.

**Il nostro problema esatto — «corroborare non basta quando il libro delle chiavi è vuoto».** Nessun modello probabilistico crea informazione: se il CRM ha 1.508 passaporti su 2.322 clienti vivi (misura A) e 88% dei folder nominano entità assenti, il recall è tappato dai DATI, non dal matcher. La risposta SOTA non è "un matcher migliore" ma un **identity graph progressivo**: ogni conferma umana e ogni documento committato aggiunge un nodo/arco con provenienza e livello di verifica (esattamente ciò che GATE-11 + enricher fanno in embrione). Splink serve per il *linkage massivo iniziale* (backfill A: prod↔local con TF-adjust su nome/telefono/nazionalità) e per **stimare la precisione** senza ground truth (EM + clerical sample), non per il routing in linea.

**Verdetto: ADATTARE.** Splink (DuckDB, locale, free) per (a) dedup del libro clienti (20 dup-group passaporti misurati), (b) linkage folder-segment→cliente con TF-adjust invece di `pg_trgm` a soglia fissa 0,70; il **routing in linea resta deterministico** (strong-id o quarantena, invariante di sangue). Scartare: ML end-to-end che decide l'attach.

Fonti: https://moj-analytical-services.github.io/splink/topic_guides/theory/fellegi_sunter.html · https://moj-analytical-services.github.io/splink/topic_guides/comparisons/term-frequency.html · https://github.com/moj-analytical-services/splink · https://www.robinlinacre.com/probabilistic_linkage/

### Asse 3 — OCR/estrazione a tier e modelli locali Apple Silicon

**Stato dell'arte 2026.** Tier: (1) **text-layer nativo** (PDF/DOCX: costo ~0, già nel nostro `preprocess`/`via=textlayer`); (2) OCR classico/specializzato compatto: **PaddleOCR-VL 1.5/1.6 (0,9B)** in testa a OmniDocBench v1.5 (94,5%), **DeepSeek-OCR** (più veloce e accurato in benchmark luglio 2026, MoE, −30-40% costo/pagina), **olmOCR-2 7B** (82,4 su olmOCR-Bench; quantizzato MLX 6-bit 6,4 GB), **GOT-OCR2**; (3) **vision-LLM generalista** (Qwen2.5-VL 7B/32B, Qwen3-VL) per comprensione/estrazione schema. Su Apple Silicon **MLX** dà il throughput più alto (studio comparativo MLX/MLC/Ollama/llama.cpp, arXiv 2511.05502); server locali come oMLX servono VLM+OCR+embedding con batching continuo. Il nostro `qwen2.5vl:7b` via Ollama è "tier 3 usato come tier 2": costoso per pagina, e con `INTAKE_OLLAMA_MAX_INFLIGHT=1`.

**Verdetto: ADOTTARE (a tier).** Tier 1 già c'è; introdurre Tier 2 con un OCR compatto MLX (PaddleOCR-VL o olmOCR-2-MLX; provare entrambi su un golden set NOSTRO — asse 7) come **primo passaggio** e riservare qwen2.5vl/Qwen3-VL a classify/estrazione schema e a pagine dove Tier 2 dà confidenza bassa. Requisiti Law 6: tutto locale, nessun cloud. Costo: RAM Pro 48GB regge un OCR 0,9-7B + un VLM 7B; misurare `docs/ora` prima (asse 7). Scartare: OCR SaaS.

Fonti: https://arxiv.org/pdf/2510.14528 · https://github.com/opendatalab/OmniDocBench · https://huggingface.co/richardyoung/olmOCR-2-7B-1025-MLX-6bit · https://github.com/allenai/olmocr · https://arxiv.org/pdf/2511.05502 · https://github.com/jundot/omlx · https://www.spheron.network/blog/best-open-source-ocr-vlm-self-host-gpu-cloud-2026/ · https://prince-arora-aws.medium.com/experiments-benchmarking-local-ocr-models-on-a-scanned-table-in-a-pdf-document-7ab519c717dd

### Asse 4 — Code/orchestrazione su Postgres

**Stato dell'arte.** Tutti i job-queue Postgres seri usano `FOR UPDATE SKIP LOCKED` (River, Procrastinate, pgmq, pg-boss, graphile-worker); il **rischio documentato 2026 è il bloat** (UPDATE+DELETE ⇒ dead tuple ⇒ autovacuum starvation, "death spiral" a 800 job/s; River issue #59). Benchmark neutrale (hardbyte): pgque 39,9k job/s event-bus, pgmq 11,3k con anti-scaling oltre certi worker; **transactional outbox** = scrivere l'evento nella stessa TX del dato e drenarlo con un consumer idempotente; DLQ esplicita e retry con backoff.

**Cosa abbiamo già.** La nostra coda È questo pattern (`svc/worker.py:606-674`), con lease, backoff transiente, DLQ (`dead`), idempotency a tre chiavi. Le mancanze reali: (i) `stage_output` JSONB fino a 12 MB per 5.888 righe nella stessa tabella della coda ⇒ bloat e I/O inutile (C-06); (ii) nessun **outbox** per la delivery Pro→Fly (C-08: il push è un side-effect post-TX senza retry); (iii) nessuna metrica di `dead tuple`/vacuum sulla coda.

**Verdetto: ADATTARE (non sostituire).** Tenere il nostro worker; separare `stage_output` in tabella figlia (`intake_stage_output(queue_id, stage, payload)`), aggiungere `intake_outbox` per delivery/eventi (drenato con SKIP LOCKED, idempotente per `idempotency_key`), monitorare `n_dead_tup` su `intake_queue`. Procrastinate/River: **scartare** (nuovo runtime per zero guadagno funzionale; il nostro contratto v2 è già lease-correct e testato: `test_kill9_reclaim_no_job_lost`, `test_exactly_once_two_workers_100_jobs`).

Fonti: https://github.com/hardbyte/postgresql-job-queue-benchmarking · https://procrastinate.readthedocs.io/en/stable/discussions.html · https://dev.to/shrsv/power-up-your-go-apps-using-postgresql-as-a-job-queue-with-river-2e3g · https://github.com/NikolayS/PgQue · https://www.techplained.com/postgres-as-queue

### Asse 5 — Human-in-the-loop: UX e priorità della coda

**Stato dell'arte.** Uncertainty sampling (mostrare prima i casi vicini alla frontiera di decisione), combinato con **stratified sampling** sulla distribuzione di produzione e **adversarial sampling** sui failure mode noti; Label Studio mostra per primi i task a punteggio più basso a ogni retrain; costi di annotazione −30/60% riportati. La coda non è FIFO: è una **priority queue con budget**.

**Cosa abbiamo.** FIFO per `created_at ASC` (`rt/intake_review.py:431`), 5.888 item di cui il 94% ghost; nessuna priorità per valore atteso; nessun campionamento.

**Verdetto: ADOTTARE.** Ordinare per **valore atteso della decisione umana**: (1) `blob_present` (C-25) AND (2) `decision ∈ {LINK_CANDIDATE, AMBIGUOUS}` con score vicino alla soglia (0,40–0,70) AND (3) doc_type "attivante" (passport/kitas/npwp: sblocca chiavi) AND (4) recency del cliente (pratica aperta). Aggiungere una **corsia di campionamento** (5% random) per misurare la precisione dell'automa (asse 7). Scartare: active learning con retraining di un modello proprietario di attach (invariante: mai name-only auto-commit).

Fonti: https://docs.humansignal.com/guide/active_learning · https://labelyourdata.com/articles/active-learning-machine-learning · https://kili-technology.com/blog/2026-data-labeling-guide-for-enterprises-build-high-performing-ai-with-expert-data · https://arxiv.org/pdf/2507.02593

### Asse 6 — Dedup contenutistico (pHash, MinHash/LSH)

**Stato dell'arte.** pHash/dHash (ImageHash) per immagini (robusto a resize/compress), MinHash+LSH (datasketch) per testo (shingle → Jaccard), sempre con **verifica finale** (Hamming esatta sui candidati LSH). Costo trascurabile.

**Cosa abbiamo.** `document_instances.phash`/`text_hash` con indici (m212 `:24-26`) mai popolati come leva; `near_dup_of` in coda; LEVA-3 dedup wall (`svc/routing.py:180-182`) lavora su blob_hash esatto e candidati. Station 0 ha misurato 2.152 dup esatti.

**Verdetto: ADOTTARE.** Popolare `phash` (imagehash) al classify (costo ms) e `text_hash` MinHash sull'OCR; una `duplicate` "near" con `near_dup_of` + soglia (Hamming ≤ 6, Jaccard ≥ 0,9) — stato terminale onesto, revocabile. Non serve nulla di più pesante.

Fonti: https://yorko.github.io/2023/practical-near-dup-detection/ · https://www.systemdesigner.net/technology/perceptual-hashing · https://arxiv.org/pdf/2102.08942 · https://ssojet.com/compare-hashing-algorithms/phash-vs-lsh

### Asse 7 — Eval harness con ground truth incrementale

**Stato dell'arte.** Backtest su **documenti di riferimento reali con estrazioni verificate** (golden set) prima di ogni cambio (modello, prompt, few-shot); ground truth sintetica per scala (RIKER: generare documenti da verità nota; MINEA: "needle" iniettati) quando l'annotazione umana manca; scoring di groundedness/completezza; regressione misurata, mai "sembra meglio".

**Cosa abbiamo.** 684 `intake_corrections` (174 code) = ground truth umana GIÀ raccolta e mai consumata; `--quality-sample` read-only; 823 test unitari ma zero eval di qualità estrattiva; il refinery pilot morto.

**Verdetto: ADOTTARE.** Un `eval/intake/` con: (a) golden set incrementale = ogni `intake_corrections` `outcome IN (approved, corrected)` (PII-locale, mai in repo: solo `blob_hash`+campi hashati/redatti); (b) runner che rilancia classify/extract sui blob ancora presenti e calcola precision/recall per campo e per doc_type; (c) gate "no regressione" su cambio di modello/prompt; (d) sintetici (needle) per i doc_type con <20 esempi. È la FASE 6 «evolver» che la spec prometteva, ridotta al minimo misurabile.

Fonti: https://medium.com/alan/lessons-from-running-an-llm-document-processing-pipeline-in-production-33d87f99cdb1 · https://arxiv.org/html/2404.04068v2 · https://arxiv.org/html/2603.08274v1 · https://alopatenko.github.io/LLMEvaluation/

---

## D.3 Matrice comparativa

| Asse | Noi oggi | SOTA | Verdetto | Vincolo Law 6/free-first |
|---|---|---|---|---|
| 1 Pipeline OSS | coda propria PG, review su Kita, feedback raccolto ma inerte | paperless-ngx: suggerimento≠decisione, LLM opt-in Ollama, archivio immutabile | ADATTARE (3 idee) | ok (Ollama) |
| 2 Record linkage | strong-id esatto + pg_trgm 0,70/0,40 | Fellegi-Sunter + TF-adjust (Splink) + identity graph | ADATTARE (Splink offline per libro chiavi; routing resta deterministico) | DuckDB locale |
| 3 OCR a tier | textlayer + qwen2.5vl per tutto | PaddleOCR-VL/olmOCR-2 MLX tier 2 + VLM tier 3 | ADOTTARE | MLX locale |
| 4 Coda PG | SKIP LOCKED + lease + DLQ (già SOTA) | idem + outbox + bloat-watch | ADATTARE (outbox, split payload) | ok |
| 5 HITL priorità | FIFO oldest-first, ghost 94% | uncertainty/valore atteso + campionamento | ADOTTARE | ok |
| 6 Dedup | blob_hash esatto; phash/text_hash mai popolati | pHash + MinHash/LSH | ADOTTARE | ok |
| 7 Eval | 823 unit test, 0 eval qualità | golden set incrementale + backtest + sintetici | ADOTTARE | dati PII locali |

**Da SCARTARE e perché.** Docling/MinerU/Unstructured come spina (già misurato: la spina c'è, `2026-06-27-39k…:60`); Procrastinate/River (runtime nuovo, zero guadagno); OCR SaaS/cloud (Law 2/6, `PENDING-ARMS.md:204` operator[business]); ML che decide l'attach (invariante); Station 1/2 rifatte senza nuovi dati (D.1).

## Adversarial review

Cross-family refuters (generator ≠ grader): **Codex GPT-5.6 terra** (`codex exec --sandbox read-only`) and **Kimi K3** (`kimi -m kimi-code/k3 -p`), both ordered to destroy the dossier on the worktree, plus two Sonnet anchor-verifiers. Result: 0 findings fell; the weakened items and their on-disk re-verification are recorded in [F-verbale-refuter.md](F-verbale-refuter.md). Refuter transcripts: session scratchpad `refuter-codex-terra.md`, `refuter-kimi-k3.md`.
