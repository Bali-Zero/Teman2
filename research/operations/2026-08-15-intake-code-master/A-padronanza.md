---
title: "Intake Code Master — A: mastery (state machines, keys, flags, levers, writer, /review, roots, 6 questions)"
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

# Deliverable A — Padronanza del sistema INTAKE

> Candidatura Code Master INTAKE · 2026-08-15 · READ-ONLY (nessuna scrittura su DB intake / CRM / Fly / plist / worker) · PII-free.
> Ogni `file:line` è stato riletto sul checkout `~/nuzantara` (HEAD `f6dfda994`) nel turno in cui è stato scritto; ogni numero porta il comando che lo ha misurato. DB = LOCALE `nuzantara_dev` (Pro, `127.0.0.1:5432`), sessioni con `PGOPTIONS='-c default_transaction_read_only=on'`.

Convenzione path: `svc/` = `apps/backend-rag/backend/services/intake/`, `rt/` = `apps/backend-rag/backend/app/routers/`.

---

## A.1 Le due macchine a stati

### `intake_queue` (stato + stage, contratto v2)

| Elemento | Dove | Cosa dice |
|---|---|---|
| Stati claimabili | `svc/worker.py:91-100` `CLAIMABLE_STATUSES` | `pending, ocr_done, extracted, validated` (+ `classify/extract/validate/route` in-flight non claimabili) |
| Transizioni | `svc/worker.py:102-107` `STAGE_TRANSITIONS` | `pending→classify→ocr_done`, `ocr_done→extract→extracted`, `extracted→validate→validated`, `validated→route→done` |
| Terminali | `svc/worker.py:37-40` docstring; `chk_iq_status` (m224 `db/migrations_v2/224_intake_flow_v2.sql:32-33`) | `done` (successo), `dead` (attempts esauriti / poison); il CHECK ammette anche `review_pending/review_claimed/routed/rejected/duplicate` (legacy v1, oggi usati solo da `intake_archive_abort.sh` che scrive `rejected` su 175.429 righe drive) |
| Claim | `svc/worker.py:606-674` `_claim_with_inbound` | `UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED)` con lease `lease_owner/lease_expires_at`; ORDER BY drain-oriented (validated prima, pending ultimo; whatsapp prima di drive) |
| Lease-only | `svc/worker.py:450-466` `_fail(transient=True)` | rilascia il lease senza bruciare `attempts`; il fallimento definitivo scrive `dead` + `last_error` mascherato (`mask_pii` `svc/worker.py:130-143`) |
| Errore transiente | `svc/worker.py:146` `TransientStageError`; alzato SOLO da `svc/stages.py:239` su `_TRANSIENT_HTTPX_ERRORS` (`svc/stages.py:83`) | è l'unico ponte "infra giù ≠ documento cattivo" |
| Reaper | `svc/worker.py:289-312` | `review_claimed` con `lease_expires_at < now()` → `review_pending` |

Misura viva (`psql … -c "SELECT status,count(*) FROM intake_queue GROUP BY 1"`): `rejected 175.429 · done 77.646 · dead 99 · review_pending 11` (gli 11 sono residui test W96 `pipeline_version test-5b/test-r6`).

### `document_routing_proposal`

| Stato | Chi lo scrive | Riferimento |
|---|---|---|
| `review_pending` | `route_stage` (default) | `svc/routing.py:1396-1613`, INSERT `ON CONFLICT (routing_key) DO NOTHING` `:1501` |
| `quarantine` / `duplicate` | `route_stage` (LEVA-1 quarantena; LEVA-3 dedup wall) | m235 `db/migrations_v2/235_routing_proposal_quarantine_autorouted.sql:36-41` |
| `review_claimed` | `POST /{id}/claim` | `rt/intake_review.py:750`, SQL steal/renew `:780-801` |
| `routed` | `advance_proposal` dentro la TX di `execute_commit` | `svc/writer.py:1061-1095` (azzera lease + claim_token) |
| `auto_routed` | LEVA-2 auto-attach (commit di sistema) | `svc/writer.py:1074-1077` docstring; `svc/auto_attach.py:781-932` |
| `rejected` | `POST /{id}/reject` | `rt/intake_review.py:1222` |
| `superseded` | reprocess/reroute (m226) | `scripts/intake_reprocess_backlog.py:240-245, 309-329` |
| `dead` | previsto dal CHECK, nessuno scrittore vivo trovato (grep `status = 'dead'` su proposal: 0 in `svc/`) | m212 `db/migrations_v2/212_intake_unified.sql:94` |

Rollback (`svc/writer.py:1298-1310`): `routed→review_claimed`, `auto_routed→review_pending`.

Misura viva: `quarantine 27.599 · superseded 25.778 · review_pending 24.790 · rejected 678 · duplicate 252 · auto_routed 219 · routed 85 · review_claimed 0`
(`SELECT status,count(*) FROM document_routing_proposal GROUP BY 1`).
Decisioni tra i `review_pending`: `NO_MATCH 10.875 · LINK_CANDIDATE 10.229 · AMBIGUOUS 3.335 · AUTO_ATTACH 351`.

---

## A.2 Le tre chiavi di idempotenza

| Chiave | Formula | Unicità | Dove |
|---|---|---|---|
| `intake_key` | `sha256(source\|source_ref\|blob_hash\|pipeline_version)` | `uq_iq_intake_key` (m212 `:61`) | `svc/enqueue.py:58` `compute_intake_key`; INSERT `ON CONFLICT (intake_key) DO NOTHING` `:164`; a monte `document_instances ON CONFLICT (blob_hash, pipeline_version)` `:127` |
| `routing_key` | `"rk:" + sha256(queue_id\|doc_index\|pipeline_version)[:48]` | `uq_rp_routing_key` (m212 `:96`) | `svc/routing.py:1197` `_make_routing_key`; è la ragione per cui ogni "reprocess" deve BUMPARE `pipeline_version` (`scripts/intake_reprocess_backlog.py:20-24`) |
| `intake_idempotency_key` | `"ik:" + sha256(source\|source_ref\|blob_hash\|doc_index\|pipeline_version)` | `uq_documents_intake_key` UNIQUE per `(client_id, key)` (m217 `db/migrations_v2/217_intake_commit_audit.sql:36-45`) — MAI globale sul contenuto: lo stesso blob può legittimamente vivere su due clienti | `svc/writer.py:214-231` |

Perché tre e non una: la prima dedup l'INGRESSO (stessa media ri-sweepata), la seconda dedup la PROPOSTA (un solo verdetto per doc per versione di pipeline), la terza dedup il COMMIT (re-approve = no-op). Sono ortogonali per costruzione: cambiare `pipeline_version` rigenera 1 e 2 ma il commit su un cliente resta idempotente per `(client_id, key)`.

---

## A.3 Flag AND-chain e mappa env (call-time vs import-time)

### Doppio consenso (chi scrive deve avere ENTRAMBI)

```
INTAKE_WRITER_ENABLED  (master)   svc/writer.py:97-108   letto a CALL-TIME
   AND
INTAKE_AUTO_ATTACH_ENABLED           svc/auto_attach.py:129-140  (LEVA-2 strong-id ⟂ phone)
INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED  svc/auto_attach.py:145-158 (direct-chat)
INTAKE_NAMEID_AUTO_ATTACH_ENABLED        svc/auto_attach.py:160-176 (strong-id + nome, senza phone)
```
`execute_commit` rifiuta senza master (`svc/writer.py:886`); il router chiama `execute_commit(plan, conn, dry_run=not writer_enabled())` (`rt/intake_review.py:1176-1177`) → un reader senza master fa solo `dry_run` audit.

### Stato reale dei flag (misurato, non dedotto)

| Processo | Sorgente | Valori |
|---|---|---|
| Worker (pid 1518, `~/nuzantara-deploy`) | plist `~/Library/LaunchAgents/com.nuzantara.intake-worker.plist` (byte-identico a `infra/launchagents/`) | `INTAKE_WRITER_ENABLED=true`, `INTAKE_AUTO_ATTACH_ENABLED=true`, `INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED=true`, `INTAKE_NAMEID_AUTO_ATTACH_ENABLED=true`, `INTAKE_DEDUP_WALL_ENABLED=true`, `INTAKE_QUARANTINE_ENABLED=true`, `INTAKE_CONCURRENCY=3`, `INTAKE_OLLAMA_MAX_INFLIGHT=1`, `INTAKE_EXTRACT_TIMEOUT=90`, `INTAKE_LEASE_TTL_SECONDS=900` |
| Reader (uvicorn :18795) | env-file 0600 `~/.cell-bridge-state/intake-review-reader.env` (4 chiavi: `API_KEYS, INTAKE_REVIEW_DATABASE_URL, INTAKE_WRITER_ENABLED, JWT_SECRET_KEY` — `cut -d= -f1`) | `INTAKE_WRITER_ENABLED=1` ⇒ le approvazioni umane COMMITTANO (308 audit `committed`) |
| Fly `nuzantara-rag` | `fly secrets list` (solo nomi/digest) | `INTAKE_WRITER_ENABLED`, `INTAKE_GATE_USE_MIRROR`, `INTAKE_REVIEW_WORKER_URL`, `INTAKE_GATE_DISABLED` presenti; `INTAKE_GATE_DISABLED` e `INTAKE_WRITER_ENABLED` hanno lo STESSO digest `d8c5ac2e11c8e492` ⇒ stesso valore (non leggibile read-only) |

### Import-time (fotografati all'avvio del processo — un cambio richiede restart) vs call-time

| Import-time | Riga |
|---|---|
| `INTERNAL_PHONE_NUMBERS`/`_PREFIXES` da `BZ_INTERNAL_PHONE_NUMBERS` | `svc/auto_attach.py:106` |
| `_FUNNEL_MIN_DOCS=8`, `_FUNNEL_MIN_DISTINCT_TYPES=5`, `_NAME_MATCH_MIN_RATIO=0.5` | `svc/auto_attach.py:457-461` |
| `OLLAMA_URL` (`INTAKE_OLLAMA_URL`/`OLLAMA_URL`), `OCR_PAGE_TIMEOUT_SECONDS=120` | `svc/classify.py:95, 111` |
| `OLLAMA_BASE_URL`, `_GENERATE_TIMEOUT_SECONDS=INTAKE_EXTRACT_TIMEOUT` (default 300, plist 90) | `svc/extract.py:62, 65` |
| `_TRANSIENT_HTTPX_ERRORS` | `svc/stages.py:83` |
| **Call-time**: `writer_enabled()`, i 3 flag auto-attach, `INTAKE_DEDUP_WALL_ENABLED` (`svc/routing.py:180-182`), `INTAKE_QUARANTINE_ENABLED` (`svc/routing.py:133-135`), `INTAKE_REVIEW_SOURCES` (`rt/intake_review.py:75`), `INTAKE_GATE_DISABLED`/`INTAKE_GATE_USE_MIRROR` (`svc/gate_evaluator.py:60, 194`), `QDRANT_URL/QDRANT_API_KEY` (`svc/validate_rules.py:83-86`) | |

---

## A.4 Le tre LEVE di auto-attach (chokepoint unico)

Chokepoint: `svc/routing.py:1322-1393` `_try_auto_attach_after_route`, invocato SOLO se `effective_status == "review_pending"` (`:1337`), dopo la soppressione per `pipeline_version` (`:1349-1361`, insieme `AUTO_ATTACH_SUPPRESSED_PIPELINE_VERSIONS={"v2.3-drive-autocreate"}` `:84`, match esatto o prefisso `:` — perché il batch autocreate conia le card DAI documenti stessi: corroborare contro di esse sarebbe auto-conferma circolare).

| Leva | Funzione | Prova richiesta | Guardie in-TX |
|---|---|---|---|
| LEVA-2 strong-id ⟂ phone | `try_auto_attach` → `_try_auto_attach_inner` `svc/auto_attach.py:752, 781-932` | decisione `AUTO_ATTACH` (strong-id concorde con transport hint) | `_strong_id_still_owned` `:312-392` (revalidator `FOR UPDATE` `:249-272`), advisory lock per valore, `_fresh_vs_locked_divergence` `:841` |
| direct-phone | `try_direct_phone_auto_attach` `:935-1059` | chat 1:1, target da `sender phone` (`reason_text.startswith("sender phone")` `:575`), anti-funnel (≥8 doc/≥5 tipi ⇒ stop `:630-644`), concordanza nome ≥0.5 | lock; **manca** `_fresh_vs_locked_divergence` (0 riferimenti tra `:935-1059`) |
| name+id | `try_nameid_auto_attach` → `_try_nameid_auto_attach_inner` `:1062, 1087-1239` | strong-id + nome soggetto, nessun phone | come LEVA-2 (`:1142`) |

GATE-11: `svc/routing.py:816` — un candidato strong-id con `id_verified is False` (provenienza `custom_fields.identity_backfill.<col>.verified`, letta `:389, :419`) degrada a `LINK_CANDIDATE`: una chiave backfillata non è prova finché un documento indipendente non la conferma. Promozione lato enricher `svc/client_enricher.py:349-403`.

---

## A.5 Writer: plan / execute / rollback + CAS

| Fase | Riga | Invarianti |
|---|---|---|
| `plan_commit` | `svc/writer.py:300-542` | READ-ONLY; rifiuta se proposal non in `review_pending/review_claimed` (`:454`); P0#3 validazione categoria/pratica |
| `execute_commit` | `:817-997` | UNA TX: `documents` UPSERT (`write_client_document :729-811`), append pratica, enrichment su SAVEPOINT, `intake_corrections` (`_record_commit_corrections :661-723`, saltate se `blob_hash` non è 64 hex `:668`), `advance_proposal`, audit (`_write_audit :1410-1454`, salva `plan.to_dict()`) |
| `rollback_commit` | `:1224-1407` | NON gated dal flag (escape hatch); DELETE `documents`, riapre proposal (`:1298-1310`), de-enrichment CAS (`_revert_document_enrichment :1101-1218`) contro `intake_commit_audit.plan.enriched_columns` — mai revert cieco |

Audit misurato: `rejected 548 · committed 308 · dry_run 59 · blocked(dry) 45 · blocked 9 · rolled_back 3` (`SELECT outcome,dry_run,count(*) FROM intake_commit_audit GROUP BY 1,2`).

---

## A.6 Il percorso `/review` end-to-end

```
Browser kita (apps/mouth/src/app/(workspace)/review/page.tsx:285  GET /api/intake/review/queue?status=review_pending&limit=50)
  → Fly nuzantara-rag  backend/app/rag_proxy.py:68,118-140  (prefisso ESATTO /api/intake/review → proxy_intake_review_request :199)
  → Cloudflare Tunnel (LaunchAgent com.nuzantara.cloudflared-intake-review)
  → Pro uvicorn 127.0.0.1:18795  backend/app/intake_review_reader.py  (NoStorePII → BridgeAuth → HybridAuth)
  → router rt/intake_review.py  (11 endpoint: /queue :363, /document-categories :494, /clients/search :517,
    /clients/{id}/practices :567, /{id}/blob :606, /{id} :656, /claim :750, /release :836, /recover :919,
    /approve :1100, /reject :1222)
  → Postgres LOCALE nuzantara_dev (pool min1/max3, statement_timeout 8s)
```
Blob: `GET /{id}/blob` legge dal filesystem del Pro sotto root gestite (`_review_blob_roots :86`, containment `:114-137`), 404 `"Blob not on disk"` `:629`, MIME allowlist + `nosniff` + CSP sandbox `:637-649`. La UI ripiega sull'OCR (`page.tsx:733-763`).

RBAC own-chat: `_reviewer_identity` fail-closed `:140-152`; `_require_own_chat_or_admin :158-199` (non-admin: `received_by.lower() == caller.lower()`); lista `/queue` con `WHERE p.status=$1 AND q.source=ANY($2) AND ($3::boolean OR q.received_by=$4)` `:426-437` (senza `lower()` — vedi C).

Approve (`:1100-1219`): claim attivo (`_require_active_claim :986`) → `plan_commit` → `execute_commit(dry_run=not writer_enabled())` `:1176-1177` → dopo la TX, delivery Pro→Fly (`svc/crm_delivery.py`, `svc/crm_push.py`), `_delivery_aware_status :1352`.

---

## A.7 Le tre radici di codice (misurate)

| Radice | Chi ci gira | Prova |
|---|---|---|
| `~/nuzantara-deploy` (CLONE git separato, auto-pulled, `origin` = Teman2) | worker (pid 1518, `WorkingDirectory` del plist; `lstart` 13/8 21:09:46 = reboot del Pro). HEAD del clone `9104b6584` alla prima misura → `79d1e42ce` alle 18:43 (fetch 18:13), 1 dietro `origin/main 0e638a3a1`; il processo esegue ciò che ha importato all'avvio | `launchctl print gui/501/com.nuzantara.intake-worker` (`path`, `pid=1518`, `runs=1`, `state=running`), `ps -o lstart= -p 1518`, `git -C ~/nuzantara-deploy rev-parse HEAD` |
| `~/nuzantara` (main checkout) | reader (`scripts/intake_review_reader_run.sh:32-33` `MAIN_REPO_ROOT`, fallback venv `:221`), sweeper, liveness, gate-pusher | plist reader/liveness/gate-pusher `infra/launchagents/` |
| `~/scripts/*` (HOME fork, byte-identici al repo al 15/8) | `dropbox-intake-sync.sh`, `intake-blob-retention-run.sh`, `intake-gate-pusher-run.sh` | `cmp` repo↔HOME = identici (misura in Fase GROUND) |
| Env-file fuori repo | `~/.cell-bridge-state/intake-review-reader.env` (writer flag), `~/.wa-mirror.env` (`WA_MIRROR_CRM_WRITE_KEY`, `BZ_INTERNAL_PHONE_NUMBERS`, `INTAKE_CRM_PUSH_*`), `~/nuzantara-deploy/apps/backend-rag/.env` (Qdrant) | `cut -d= -f1` (nomi soltanto) |

Il worker legge `TransientStageError`, i flag e le costanti dalla COPIA deploy: un fix su `~/nuzantara` non cura il worker finché il clone non viene aggiornato e il job non viene riavviato (famiglia #1).

---

## A.8 Le sei domande di verifica

**1. Perché `worker.py` installa l'alias `__main__` → modulo canonico?**
`svc/worker.py:67-88` `_install_canonical_main_alias(__name__, __package__, sys.modules)`. Lanciato con `python -m backend.services.intake.worker`, il file viene eseguito come `__main__`; senza alias `svc/stages.py` importa `backend.services.intake.worker.TransientStageError` da una SECONDA copia del modulo, quindi la classe alzata da `stages.py:239` non è la stessa che `worker.py:541` cattura (`except TransientStageError`) → un timeout Ollama viene trattato come errore del documento e BRUCIA `attempts` fino a `dead`. Prova storica nel DB: 35 righe `dead` con `TransientStageError('stage=extract infra unreachable: ReadTimeout')` datate 2026-06-25→07-07 (`SELECT count(*) FROM intake_queue WHERE status='dead' AND last_error LIKE '%TransientStageError%'`), fix in `8352f3852` (#2100) del 2026-07-07.

**2. Ollama giù: percorso esatto di un doc e stato terminale.**
- Stage `classify`: `svc/classify.py:496` e `:514` catturano `(httpx.HTTPError, asyncio.TimeoutError, Exception)` per pagina → `text=""`, `via="empty"` (`:458`); `classify_document` senza testo → `unknown/0.0`; **la stage NON alza mai `TransientStageError`** (l'unico raise è in `stages.py:239` e classify non propaga l'eccezione). Il job avanza a `ocr_done` con OCR vuoto.
- `extract`: `unknown` non è schematizzato → campi vuoti (`svc/stages.py:173-188`, `_NEEDS_STAGE_OUTPUT` `:79`); se invece Ollama cade QUI, `httpx.ConnectError` propaga → `stages.py:239` → transiente (nessun attempt bruciato); un `ReadTimeout` è convertito in envelope nullo `skipped: model_timeout` (`svc/extract.py:2135-2160`) e NON è transiente.
- `validate` → `route`: `unknown` + `<20` char OCR ⇒ LEVA-1 **`quarantine`** (proposal) e la coda va **`done`**. Stato terminale onesto ma FALSO NEGATIVO: il documento sembra illeggibile mentre era l'infra a mancare. Misura: fra le 1.310 quarantene WhatsApp, 831 hanno TUTTE le pagine `via=empty` (query su `stage_output->'classify'->'ocr_text_per_page'`), distribuite a raffiche (98/105 il 28/7, 49/52 il 10/8, 38/39 il 12/8) — firma compatibile con finestre di indisponibilità, non con documenti bianchi. Non posso provare la causa per riga: il log del worker è scritto su un inode UNLINKED (C-03); il finding è C-02.

**3. Dove vive l'UNICA copia dell'OCR dei blob evicted, e quale flag la distruggerebbe.**
In `intake_queue.stage_output->'classify'->'ocr_text_per_page'` (+ `->'extract'->'fields'`). La retention (`scripts/intake_blob_retention.py:56-62, 128-137`) cancella i BYTE dei blob di code terminali dopo 7 giorni; solo 594/25.400 blob della coda review erano su disco a luglio (SKILL) e oggi 366/5.888 nella coda WhatsApp (misura in C-01). Il flag distruttivo è **`--reprocess`** (`scripts/intake_reprocess_backlog.py:3647-3651`) che esegue `REPROCESS_RESET_SQL` con `stage_output = '{}'::jsonb` (`:248-260`, riga `:256`); il commento `:262-268` lo dichiara ("97.7% of these rows' blobs are retention-evicted, so the saved OCR/extract fields are the ONLY copy"). Le modalità `--reroute-drive-folder / --reroute-npwp / --reroute-identity-backfill` (`:3652-3676`) usano `REROUTE_DRIVE_FOLDER_RESET_SQL` (`:331-343`) che NON tocca `stage_output` e riprende da `validated`. Bloccato da test: `backend/tests/scripts/test_intake_reprocess_backlog.py:1388-1403` (asserisce `"stage_output" not in sql` per il reroute e `in` per il reprocess). Anche `PRIORITY_RETRY_RESET_SQL` (`:511-523`, usato dai `--retry-*`) azzera `stage_output`.

**4. Invariante di `intake_proposal_health_sentinel.py` e stato di armamento.**
Invariante: una coda `done` deve avere ≥1 proposal viva (`_LIVE_STATUSES = review_pending, review_claimed, routed, rejected` `scripts/intake_proposal_health_sentinel.py:55`); altrimenti il documento è un ORFANO (mai in `/review`). Report-only di default, `--heal` (`:195`) rianima l'ultima `superseded`. Armamento reale: **NON armato**. Prima stesura: «`grep -rl … infra/launchagents ~/Library/LaunchAgents` = 0» — FALSA come evidenza (refuter Kimi): il grep trova `infra/launchagents/_snapshot-live/com.nuzantara.intake-proposal-health-sentinel.plist` (snapshot, non installato) e un plist sotto `~/Library/LaunchAgents/.disabled-codex-cleanup-20260708/` (disabilitato). La prova giusta è lo stato di attivazione: `launchctl print gui/501/com.nuzantara.intake-proposal-health-sentinel` → `Could not find service … in domain for user gui: 501`, e il ledger PENDING-ARMS `:181` («HOME-only script genuinely deleted, NOT resurrected»). Conclusione invariata, evidenza corretta. Eseguito il suo `COUNT_SQL` a mano (read-only): riporterebbe `superseded_orphans=28.199` (131 veri) e `no_proposal=23.930` — vedi C-07. Il sentinel conta separatamente `superseded_orphans` e `no_proposal` (`:57-77`, `COUNT_SQL`), quindi la classe «done senza alcuna proposal» È vista — ma solo se qualcuno lo esegue. Nota: `_LIVE_STATUSES` omette `auto_routed/quarantine/duplicate` ⇒ conterebbe come `superseded_orphans` righe che orfane non sono (falso positivo di design, vedi C-07). Misura orfani veri: 23.930 righe `done` senza alcuna proposal (23.907 stub-routed `{"stub": true}`), di cui 951 WhatsApp e 22.979 Drive; 131 righe `done` con SOLE proposal `superseded`.

**5. Perché la coda review mostra ~11 elementi contro ~35,8k di backlog (non è un bug).**
Tre scope diversi che qualcuno confonde:
- `intake_queue.status='review_pending'` = **11** (residui test W96): è la colonna SBAGLIATA — la review vive nelle PROPOSAL.
- Proposal `review_pending` totali = **24.790**; ma il reader mostra solo `source ∈ INTAKE_REVIEW_SOURCES` (default `("whatsapp",)` `rt/intake_review.py:71-77`) ⇒ **5.888**; un non-admin vede solo `received_by == proprio email` (`:426-437`) ⇒ per utente 25…1.534.
- Le 27.599 `quarantine` + 252 `duplicate` + 25.778 `superseded` NON sono in coda (stati parcheggiati/terminali onesti). Il «~35,8k» è il conteggio di LUGLIO delle proposal `review_pending` (35.779, `research/operations/2026-07-18-intake-station1-2-rescue-recall.md:33`); oggi sono 24.790 perché i reroute m227/m248 hanno marcato `superseded` le vecchie (25.778 superseded totali) — stessa entità, data diversa.
Quindi «11» è la trappola del proxy (colonna di coda), «35,8k» è il backlog totale delle proposal (a luglio; 24.790 oggi), la vista umana è 5.888 (admin, solo WhatsApp) e da 25 a 1.534 per own-chat. Precisazione: la restrizione per sorgente è una SCELTA di default (`_DEFAULT_REVIEW_SOURCES`), non un bug in sé — «non è un bug» vale per la discrepanza dei conteggi; la sua conseguenza (gate che conta ciò che il reader non mostra; 18.902 Drive invisibili a ogni umano) è invece registrata come difetto in C-04/C-27.

**6. Perché `received_by IS NULL` è admin-only per costruzione.**
`_require_own_chat_or_admin` `rt/intake_review.py:158-199` confronta `received_by.lower() == caller.lower()` solo per non-admin (`:188-192`); un `NULL` non è uguale a nessuna email ⇒ nessun non-admin passa; la lista usa `($3::boolean OR q.received_by = $4)` `:428` — `NULL = $4` è NULL ⇒ falso ⇒ solo l'admin (`$3=true`) vede la riga. `received_by` è popolato dallo sweeper (`scripts/wa_mirror_intake_sweeper.py:600` `received_by=r["team_member_email"]`) e dal backfill (`svc/routing.py:1286-1319`, `lower(c.assigned_to)`); i documenti della linea business condivisa/Drive pre-backfill restano NULL ⇒ admin-only. Misura: `received_by IS NULL` fra i `review_pending` WhatsApp = 1, `''` = 43 (la stringa vuota è ugualmente invisibile ai non-admin, ma NON è NULL: il gate-pusher li scarta con `received_by IS NOT NULL` + F3).

---

## A.9 Stato certificato dei test (eseguiti in questa sessione, DB isolato)

```
cd apps/backend-rag && PYTHONPATH=. .venv/bin/python -m pytest backend/tests/services/intake \
  backend/tests/scripts/test_intake_reprocess_backlog.py backend/tests/routers/test_intake_review.py \
  backend/tests/unit/app/test_rag_proxy_intake_split.py -q -o addopts=""
→ 823 passed, 8 skipped, 53 warnings in 25.68s
cd ~/nuzantara && PYTHONPATH=. apps/backend-rag/.venv/bin/python -m pytest \
  scripts/tests/test_intake_gate_count_pusher.py scripts/tests/test_intake_dsn_guard_covers_every_var.py -q
→ 8 passed
```
`conftest.py:39-54` ha forzato `TEST_DATABASE_URL`/`INTAKE_TEST_DSN` = `nuzantara_test` (guardia W96 fail-closed).

## Adversarial review

Cross-family refuters (generator ≠ grader): **Codex GPT-5.6 terra** (`codex exec --sandbox read-only`) and **Kimi K3** (`kimi -m kimi-code/k3 -p`), both ordered to destroy the dossier on the worktree, plus two Sonnet anchor-verifiers. Result: 0 findings fell; the weakened items and their on-disk re-verification are recorded in [F-verbale-refuter.md](F-verbale-refuter.md). Refuter transcripts: session scratchpad `refuter-codex-terra.md`, `refuter-kimi-k3.md`.
