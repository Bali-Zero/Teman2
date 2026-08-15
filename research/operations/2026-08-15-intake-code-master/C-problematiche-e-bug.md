---
title: "Intake Code Master — C: 31 findings (bugs, debt, spec, ops, policy)"
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

# Deliverable C — Problematiche e bug

> Path: `svc/` = `apps/backend-rag/backend/services/intake/`, `rt/` = `apps/backend-rag/backend/app/routers/`, `rd/` = `apps/backend-rag/backend/app/`. Ogni riga verificata su `~/nuzantara` HEAD `f6dfda994` nel turno di scrittura; ogni numero misurato su `nuzantara_dev` LOCALE in sola lettura (`PGOPTIONS='-c default_transaction_read_only=on' psql -h 127.0.0.1 -U nuzantara -d nuzantara_dev`). Nessun test qui proposto punta a `nuzantara_dev`: i test guilt+innocence indicati sono a forma di SQL/asserzione pura o con DB `nuzantara_test`.
>
> Categorie: **BUG** bug di codice · **DEBT** debito strutturale · **SPEC** gap spec→realtà (`research/operations/doc-intake-unified/`) · **OPS** rischio operativo/deploy · **POLICY** violazione policy (PII, model topology, flag).
> Ordinati per severità. `★` = candidato-novità (non ho letto la answer key; è la mia stima).

---

## C-01 ★ P1 · DEBT/SPEC — La retention cancella i blob dei documenti ANCORA in review: 93,8% della coda WhatsApp è senza file

**Sintomo.** Il reviewer apre `/review`, la prima pagina (50 più vecchi) ha **0/50** blob su disco; il preview va in 404 `"Blob not on disk"` e la UI ripiega sull'OCR (`apps/mouth/src/app/(workspace)/review/page.tsx:733-763`). Approvare un ghost produce un `documents` locale senza byte ⇒ delivery `missing_blob` (45 audit).

**Causa root.** `scripts/intake_blob_retention.py:56-62` `_TERMINAL_STATUSES=("done","routed","rejected","duplicate","dead")` e la query `:128-137` selezionano per **stato della CODA** senza mai guardare `document_routing_proposal`. Ma OGNI proposal in review vive su una coda già `done`: `SELECT q.status,p.status,count(*) … WHERE p.status IN ('review_pending','review_claimed') GROUP BY 1,2` → `done | review_pending | 24790` (100%). Il docstring `:17-18` promette «NEVER touches a blob whose status is non-terminal (pending/ocr/extracted/review_*)» — ma `review_*` non è mai uno stato di coda del contratto v2 (`svc/worker.py:102-107`): la promessa è vuota per costruzione. `INTAKE_BLOB_TTL_DAYS=7` (plist) e la coda review WA ha `min(created_at)=2026-06-12`.

**Misura.**
```
# blob presenti fra i review_pending WhatsApp (5.888)
psql … -At -c "SELECT q.blob_path FROM document_routing_proposal p JOIN intake_queue q ON q.id=p.queue_id WHERE p.status='review_pending' AND q.source='whatsapp'" | awk '{ if (system("test -e \""$0"\"")==0) p++; else m++ } END {print p, m}'
→ present=366 missing=5522
# oldest 50 (ORDER BY p.created_at ASC = pagina 1 della UI): present=0 missing=50
# più vecchi di 7gg: 5540/5888
```
Ultimo run retention (`~/logs/intake-blob-retention.err.log`, 15/8 04:30): `252080 candidates, 133 blobs unlinked`.

**Blast radius.** Correttezza dell'attach (il reviewer decide su OCR senza vedere il documento), continuità (delivery `missing_blob`), recovery (A.8-3: l'OCR salvato è l'unica copia). Non tocca PII/sicurezza.

**Severità.** P1: rende inservibile per il 94% la superficie umana attorno a cui ruota tutta la spec FASE 5.

**Prova guilt+innocence** (test puro, senza DB, sulla forma della SQL — stesso stile di `backend/tests/scripts/test_intake_reprocess_backlog.py:1388-1403`):
- guilt: `assert "document_routing_proposal" in RETENTION_SELECT_SQL and "review_pending" in RETENTION_SELECT_SQL` (oggi fallisce: la query non nomina la tabella).
- innocence: una riga `done` con proposal `routed` + `crm_push.status='pushed'` più vecchia del TTL resta candidata (la cura non ferma la retention legittima).
- integrazione (`nuzantara_test`): 2 code `done` >TTL, una con proposal `review_pending`, una con `rejected` → `reclaim(apply=False)` deve contare 1 candidato.

**Cura minima.** Nella SELECT: `AND NOT EXISTS (SELECT 1 FROM document_routing_proposal p WHERE p.queue_id=q.id AND p.status IN ('review_pending','review_claimed'))` + escludere `routed/auto_routed` non ancora consegnati (`crm_push.status <> 'pushed'`). Aggiungere `blob_present: bool` al payload di `/queue` (C-25).

---

## C-02 ★ P1 · BUG — Ollama giù nello stage `classify` diventa "documento vuoto" e finisce in quarantena: 831/1.310 quarantene WhatsApp hanno TUTTE le pagine `via=empty`

**Sintomo.** Raffiche di quarantene nei giorni di indisponibilità (`updated_at::date`): 28/7 **98/105**, 10/8 **49/52**, 12/8 **38/39**, 29/7 55/65 — quarantene con OCR a zero su documenti che, per distribuzione, non possono essere tutti bianchi.

**Causa root.** `svc/classify.py:496` e `:514` catturano `(httpx.HTTPError, asyncio.TimeoutError, Exception)` per pagina e proseguono con `text=""`, `via="empty"` (`:458`); `_run_classify_stage :1188-1235` non alza; `classify_document` restituisce `unknown/0.0`; a valle LEVA-1 (`svc/routing.py:128` `QUARANTINE_MIN_OCR_CHARS=20`, `:165`) parcheggia in `quarantine` e la coda va `done`. `TransientStageError` esiste (`svc/stages.py:83, 237-241`) ma nessuna eccezione arriva a `stages.py` da questo stage. Lo stage `extract` invece propaga `ConnectError` (transiente) — asimmetria fra stage.

**Misura.**
```
WITH q AS (SELECT q.id, p.status pstatus, (SELECT count(*) FROM jsonb_array_elements(COALESCE(q.stage_output->'classify'->'ocr_text_per_page','[]'::jsonb)) e) pages,
 (SELECT count(*) FROM jsonb_array_elements(COALESCE(q.stage_output->'classify'->'ocr_text_per_page','[]'::jsonb)) e WHERE e->>'via'='empty') empty_pages
 FROM intake_queue q JOIN document_routing_proposal p ON p.queue_id=q.id WHERE q.source='whatsapp' AND q.status='done' AND p.status IN ('quarantine','review_pending'))
SELECT pstatus, count(*), count(*) FILTER (WHERE pages>0 AND empty_pages=pages) FROM q GROUP BY 1;
→ quarantine | 1310 | 831 ;  review_pending | 5888 | 141
```
Non posso attribuire la causa riga per riga: il log del worker è illeggibile (C-03). Onestà: una parte degli 831 può essere davvero illeggibile; la firma a raffiche e il codice che ingoia `ConnectError` bastano per la colpevolezza del meccanismo, non per il conteggio esatto.

**Blast radius.** Correttezza (falsi negativi: documenti veri parcheggiati come noise), continuità (nessun retry: la coda è `done`), costo umano (il recover manuale `POST /{id}/recover` `rt/intake_review.py:919` è per singolo id).

**Severità.** P1: perdita silenziosa di documenti cliente durante ogni finestra di manutenzione Ollama; e la quarantena "onesta" smette di essere onesta.

**Prova.** guilt: `ocr_pages([page])` con `_ollama_vision` che alza `httpx.ConnectError` → oggi ritorna `[{"via":"empty"}]`; la cura deve alzare `TransientStageError` (o un marker che `stages.py:237` traduce). innocence: `_ollama_vision` che risponde `""` (pagina davvero vuota) → resta `via="empty"` e la quarantena resta legittima. Terzo caso: `ReadTimeout` su UNA pagina di 3 → transiente (non "pagina vuota").

**Cura minima.** In `ocr_pages` separare `_TRANSIENT_HTTPX_ERRORS` (`svc/stages.py:83`) dal resto: su ConnectError/ConnectTimeout/RemoteProtocolError ri-alzare; su ReadTimeout della pagina, marcare `via="timeout"` e far decidere allo stage (≥1 pagina timeout ⇒ transiente). LEVA-1 deve rifiutare la quarantena quando `all(via in ("empty","timeout"))` e `n_pages>0` con `error` di infra.

---

## C-03 ★ P1 · OPS — Il log del worker è scritto su un inode CANCELLATO: 10,4 MB di stderr invisibili, nessun post-mortem possibile

**Sintomo.** `~/logs/intake-worker.launchd.err.log` e `.out.log` non esistono (`ls`, `stat` → No such file), ma il processo li tiene aperti: `lsof -p 1518 | grep intake-worker.launchd` → fd `1u` (out, 0 byte) e `2u` (err, **10.454.250 byte**), `find ~/logs -inum 156783841` → nessun risultato. Processo partito `gio 13 ago 21:09:46 2026` (`ps -o lstart= -p 1518`).

**Causa root.** Il plist (`launchctl print gui/501/com.nuzantara.intake-worker` → `stderr path = /Users/nuzantara/logs/intake-worker.launchd.err.log`) apre i log all'avvio; qualcosa li ha rimossi dopo (un janitor di `~/logs`, non identificato: `crontab -l | grep logs` non mostra un rotatore; **non lo so** — per scoprirlo cercherei `find ~/logs -delete|-mtime` nei plist/`~/scripts` e nel `newsyslog.d`). launchd non riapre i file (nessun `SIGHUP`-reopen; il processo scrive nell'inode orfano).

**Blast radius.** Diagnosi (C-02 non attribuibile), disco (10 MB non reclamabili finché il processo vive), famiglia #2 "verde che mente": tutto ciò che il worker dice dal 13/8 è perduto.

**Severità.** P1 operativa (osservabilità zero del componente più critico); nessun impatto dati.

**Prova.** Sonda: `[ -e "$(launchctl print gui/$UID/com.nuzantara.intake-worker | awk -F'= ' '/stderr path/{print $2}')" ] || echo "LOG UNLINKED"`. innocence: dopo restart, il file esiste e la sonda tace.

**Cura minima.** (i) `launchctl kickstart -k gui/$UID/com.nuzantara.intake-worker` (operator[control-plane], NON eseguito qui); (ii) rotazione con `copytruncate` (newsyslog `-J`/`logrotate copytruncate`) o wrapper che logga via `logging.handlers.WatchedFileHandler`; (iii) aggiungere alla liveness una riga "log path esiste".

---

## C-04 ★ P1 · SPEC/OPS — Il gate INTAKE conta documenti che il reviewer NON PUÒ vedere: coda-gate (tutte le sorgenti) ≠ coda-review (solo WhatsApp)

**Sintomo.** Un membro non-admin ha 47–83 proposal Drive `review_pending` conteggiate dal gate ma invisibili in `/review`.

**Causa root.** `scripts/intake_gate_count_pusher.py:114-129` conta per `received_by` senza filtro `source`; il reader mostra solo `INTAKE_REVIEW_SOURCES` default `("whatsapp",)` (`rt/intake_review.py:71-77`); l'env-file del reader non imposta `INTAKE_REVIEW_SOURCES` (`cut -d= -f1 ~/.cell-bridge-state/intake-review-reader.env` → 4 chiavi, nessuna è quella). Il gate blocca con `any(count>0)` (`svc/gate_evaluator.py:235`).

**Misura** (email redatte alla prima lettera, conteggi per sorgente):
```
SELECT split_part(lower(q.received_by),'@',1), q.source, count(*) FROM document_routing_proposal p JOIN intake_queue q ON q.id=p.queue_id
WHERE q.received_by IS NOT NULL AND p.status IN ('review_pending','review_claimed') GROUP BY 1,2;
→ a*** drive 47 / whatsapp 1534 · a***.f*** drive 53 / whatsapp 1212 · k*** drive 76 / whatsapp 773 · v*** drive 83 / whatsapp 338 · s*** drive 38 / whatsapp 637 · d*** drive 26 / whatsapp 674 · r*** drive 16 · d*** drive 2 · r*** drive 1 …
```
Su Fly: `fly secrets list -a nuzantara-rag` mostra `INTAKE_GATE_DISABLED` **presente**, con digest identico a `INTAKE_WRITER_ENABLED` (`d8c5ac2e11c8e492`) ⇒ stesso valore, non leggibile in sola lettura. Backend: `require_gate_cleared` è DEFINITO in `rd/deps/gate.py:66` (opt-in per rotta, `Depends(require_gate_cleared)`, docstring `:13-26`) ma fuori dai test è NOMINATO solo nel commento di `rt/intake_gate.py:10` (grep fuori da `tests/`) ⇒ nessuna rotta business è gate-ata lato server; il muro è la `GateScreen` del frontend (`apps/mouth/src/app/(workspace)/layout.tsx:374`, con bypass admin).

**Blast radius.** Due mondi: se `INTAKE_GATE_DISABLED` è truthy il gate è teatro (famiglia #2); se falsy, 9 utenti sono in muro con debiti che non possono estinguere (Drive) e comunque con 1.534 doc di cui il 94% ghost (C-01). In entrambi i casi il numero pushato a Fly (`upserted=21`, log Fly 15/8 09:54) non descrive la coda umana.

**Severità.** P1 (prodotto/operativo), non dati.

**Prova.** guilt: test puro che importa la costante delle sorgenti del pusher e quella del reader e asserisce che siano lo STESSO oggetto/valore (oggi il pusher non ha una costante di sorgente ⇒ fallisce). innocence: con `INTAKE_REVIEW_SOURCES=whatsapp,drive` entrambi contano drive.

**Cura minima.** Il pusher filtra `q.source = ANY(review_sources())` importando la stessa funzione del router (`_review_sources`), e il payload del gate riporta la sorgente. Decidere (Zero, business) se `INTAKE_GATE_DISABLED` resti.

---

## C-05 P2 · BUG (latente) — Il rollback di un commit umano crea uno ZOMBIE `review_claimed` con lease NULL: né reaper, né steal-claim, né lista lo raggiungono

**Causa root.** `advance_proposal` azzera `lease_owner/lease_expires_at/claim_token` (`svc/writer.py:1082-1092`); `rollback_commit` riporta `routed→review_claimed` (`:1298-1310`) SENZA ripristinare un lease. Il reaper esige `lease_expires_at < now()` (`svc/worker.py:307-308`, NULL ⇒ falso); lo steal-claim esige `lease_expires_at < $5` o `lease_owner = $2` (`rt/intake_review.py:788-793`, NULL ⇒ falso); la UI lista solo `status=review_pending` (`page.tsx:285`) — l'API ammette `?status=review_claimed` (`rt/intake_review.py:367-369`), quindi un admin che SA cosa cercare lo vede; `recover` copre solo `quarantine/duplicate` (`:919-980`). Unica uscita: `release` admin force (`:836`) su una lista che nessuna UI mostra.

**Misura.** Oggi 0 zombie (`review_claimed_total=0`); i 3 `rolled_back` in audit sono finiti `review_pending` (via `auto_routed`). Latente ma deterministico.

**Blast radius.** Correttezza/continuità: il documento sparisce dalla superficie umana di default (UI) dopo un rollback di approvazione umana; recuperabile solo da un admin che interroghi l'API a mano.

**Prova.** guilt (`nuzantara_test`): approve reale (proposal→`routed`, lease NULL) → `rollback_commit` → `reap_expired_review_claims`==0 → `POST /claim` da un altro utente → 409. innocence: rollback di `auto_routed` → `review_pending` → claimabile.

**Cura minima.** In `rollback_commit`: `WHEN 'routed' THEN 'review_pending'` (una proposal riaperta è di nessuno), oppure `lease_expires_at = now()` così il reaper la libera al prossimo tick. In più (refuter Kimi): NESSUN monitor conta questa classe — né il sentinel né `--report-*` interrogano `status='review_claimed' AND lease_expires_at IS NULL`; aggiungere quella riga al sentinel (C-07) chiude il buco anche per gli zombie storici.

---

## C-06 P2 · DEBT — Il reader carica in RAM l'INTERA coda review (12 MB di OCR) e fa N+1 lookup per ogni pagina da 50

**Causa root.** `rt/intake_review.py:426-437` seleziona tutte le righe (`q.stage_output` incluso), poi filtra `decision` in Python (`:448`) e per OGNI riga superstite `await _load_candidate_clients(conn, candidate_ids)` (`:450-451`), infine pagina `items[offset:offset+limit]` (`:484-485`) — nel percorso UI di default (nessun filtro `decision`) il lookup gira sull'intera coda.

**Misura.** Query base (admin, whatsapp): `Execution Time: 91 ms` ma `pg_size_pretty(sum(pg_column_size(q.stage_output)))` = **12 MB** per 5.888 righe; `_load_candidate_clients` (`:331-343`) salta le righe senza candidati (`if not client_ids: return []`), quindi i round-trip sono ~3.859 (LINK 2.209 + AMBIGUOUS 1.641 + AUTO 9; NO_MATCH 2.029 saltate — `SELECT p.entity_resolution->>'decision',count(*) … source='whatsapp' AND status='review_pending'`) per servire 50 card; pool `statement_timeout 8s` per statement.

**Blast radius.** Latenza/UX, pressione sul reader (Pro), transito di OCR PII (interno, ma inutile) per ogni refresh.

**Severità.** P2.

**Prova.** guilt: test che conta le chiamate a `_load_candidate_clients` con 200 righe fake e `limit=50` (oggi 200). innocence: con `offset=0,limit=50` il risultato è identico.

**Cura minima.** `LIMIT/OFFSET` in SQL con `decision` filtrata in SQL (`entity_resolution->>'decision' = $5`), proiettare `stage_output` solo per i campi necessari (`->'extract'->'fields'`, `doc_type`), un solo `WHERE id = ANY($1)` per i candidati della pagina.

---

## C-07 ★ P2 · SPEC — Nessun tripwire ARMATO sui 23.907 documenti `done` mai passati per `/review` (stub) e sui 131 orfani da superseded; il sentinel che li vedrebbe esiste (conta le due classi separatamente) ma non è armato e ha una definizione di "vivo" sbagliata

**Misura.**
```
done senza proposal 23.930 (23.907 con route stub={"stub":true}); drive 22.979 · WhatsApp 951; done con SOLE superseded 131
```
(`SELECT q.source, count(*) FROM intake_queue q LEFT JOIN document_routing_proposal p ON p.queue_id=q.id WHERE q.status='done' AND p.id IS NULL GROUP BY 1`.)
Il sentinel (`scripts/intake_proposal_health_sentinel.py:57-77` `COUNT_SQL`) riporta DUE conteggi distinti — `superseded_orphans` (done + ≥1 proposal + nessuna in `_LIVE_STATUSES`) e `no_proposal` (done + zero proposal, «legacy no-proposal … reported separately») — quindi il tripwire per gli stub esiste nel codice; ma `_LIVE_STATUSES` `:55` esclude `auto_routed/quarantine/duplicate` ⇒ ogni `done` la cui unica proposal è `auto_routed`/`quarantine`/`duplicate` entra in `superseded_orphans`, e nessun plist lo esegue. **Prova ESEGUITA** (il `COUNT_SQL` del sentinel, verbatim, read-only, 15/8): `superseded_orphans = 28.199` · `no_proposal = 23.930`; con `_LIVE_STATUSES` esteso a `auto_routed/quarantine/duplicate` → `superseded_orphans = 131`. Cioè: armato com'è, il sentinel griderebbe 28.199 orfani di cui **28.068 falsi** (99,5%) — un allarme che nessuno leggerebbe (W116) — e con `--heal` (default `source='whatsapp'`, `ORPHAN_IDS_SQL :84-96`) rianimerebbe l'ultima `superseded` di code legittimamente `auto_routed` che ne hanno una (post-reroute è la norma) — `HEAL_SQL :99-114` è guardata dallo STESSO `_LIVE_STATUSES` — creando un gemello `review_pending` di un documento già attaccato. `--revive-stub` (`scripts/intake_reprocess_backlog.py:543-555`) esiste, dry-run; 270 righe portano `v2.1-stub-revive` e risultano ancora stub (misura precedente in questa sessione).

**Blast radius.** Continuità: documenti cliente persi in silenzio (951 WA); qualità dei report.

**Severità.** P2 (storico noto per la parte drive; nuovo il fatto che il sentinel darebbe verdetti sbagliati se armato).

**Prova.** guilt: sentinel su una coda `done` con proposal `quarantine` → oggi la conta orfana. innocence: coda `done` con `review_pending` → 0.

**Cura minima.** `_LIVE_STATUSES += ("auto_routed","quarantine","duplicate")`; plist `StartInterval 3600` report-only con TG; e la decisione (Zero) su `--revive-stub` per le 951 WA.

---

## C-08 P2 · SPEC/OPS — La consegna Pro→Fly non ha un ciclo di riparazione: 241/304 documenti committati non sono in Kita

**Misura.** Due denominatori, dichiarati: (a) `intake_commit_audit` `outcome='committed'` = **308** righe (308 `doc_id` distinti); `plan->'crm_push'->>'status'`: `pushed 65 · missing_blob 45 · identity_unresolved 40 · rejected 55 ("Client not found", pre-bridge) · denied_rbac 8 · server_error 5 · too_large 2 · no_token 1 · none 87` (somma 308). (b) `documents WHERE intake_proposal_id IS NOT NULL` = **304** (4 `doc_id` dell'audit non esistono più: 2 hanno un audit `rolled_back`, 2 sono spariti altrimenti); di questi 304, `file_id IS NOT NULL` = **63** = esattamente i 63 `pushed` ancora presenti (`JOIN documents d ON d.id=a.doc_id … status='pushed'` = 63). Quindi **241 = 304 − 63**: non deriva da «65 pushed» ma dal `file_id` (l'id Kita che solo una delivery riuscita scrive).
`--report-undelivered` (`scripts/intake_reprocess_backlog.py:3970-3979`) è read-only; nessun job riprova; `DELIVERY_FAILED_STATUS` è solo un'etichetta.

**Blast radius.** Il valore d'uso della FASE 5 (il documento nel CRM) è mancante nel 79% dei casi; il reviewer crede di aver "consegnato".

**Severità.** P2 (spec `06-fase5-hitl-writer-design.md` prevede la delivery come parte del commit).

**Cura minima.** Un retry idempotente (per `idempotency_key`) sui soli stati transienti (`server_error`, `no_token`, `identity_unresolved` dopo backfill phone), con budget; `missing_blob` è irreparabile (C-01) e va detto in UI.

---

## C-09 P2 · OPS (famiglia #1) — Tre radici di codice + tre depositi di env: il worker gira da un clone separato indietro di 1 commit, il reader ha un fallback che esegue il main checkout

**Causa root.** Worker: `WorkingDirectory ~/nuzantara-deploy` (plist). Il clone È auto-pulled (runbook `docs/runbooks/runtime-dev-checkout-split.md:3-8`; HEAD `9104b6584` alla prima misura, `79d1e42ce` alle 18:43 dopo un fetch delle 18:13 — 1 commit dietro `origin/main 0e638a3a1`), ma il PROCESSO worker (pid 1518, `runs=1`, `lstart` 13/8 21:09:46 = reboot del Pro) esegue i moduli caricati all'avvio: due giorni di pull non lo toccano finché nessuno fa `kickstart`; reader: `scripts/intake_review_reader_run.sh:32-33, 221-223` (`MAIN_REPO_ROOT` fallback venv), env-file `~/.cell-bridge-state/…`; retention/gate-pusher/dropbox da `~/scripts/*` (oggi byte-identici, ma per accidente non per contratto); Qdrant da `~/nuzantara-deploy/apps/backend-rag/.env`; roster telefoni da `~/.wa-mirror.env`.

**Blast radius.** Un fix su `TransientStageError` (C-02) mergiato su main arriva nel clone da solo ma NON cura il worker finché qualcuno non fa `kickstart` (nessun organo lo riavvia al cambio di HEAD); due processi (worker/reader) possono girare su due versioni del contratto di stato (famiglia #9).

**Severità.** P2 (rischio, non guasto). **Prova.** `cmp` HOME↔repo + `git -C ~/nuzantara-deploy rev-parse HEAD` vs `origin/main` come check di liveness. **Cura minima.** dichiarare le coppie in `infra/home-fork/declared-pairs.json`; il worker legge il repo via `INTAKE_REPO_ROOT` già presente nel plist — allinearlo a un checkout gestito da `pro-git-pull.sh`.

---

## C-10 P2 · SPEC/POLICY — Lo stage `validate` dipende dal Qdrant CLOUD (Law 6): env mancante = poison → `dead`; errore HTTP non transiente

**Causa root.** `svc/validate_rules.py:83-86` alza `RuntimeError("QDRANT_URL / QDRANT_API_KEY not set")`; è un errore "del documento" per il worker (non in `_TRANSIENT_HTTPX_ERRORS`) ⇒ 5 tentativi ⇒ `dead`. `HTTPStatusError` (429/5xx dal cloud) idem.

**Misura.** 26 righe `dead` con `QDRANT_URL / QDRANT_API_KEY not set` (26/6→7/7). Che sia CLOUD non è dedotto dal codice ma dall'env del clone che il worker esegue: `grep '^QDRANT_URL=' ~/nuzantara-deploy/apps/backend-rag/.env | sed …` (solo host, mai il valore intero) → `…us-east4-0.gcp.cloud.qdrant.io`.

**Blast radius.** Continuità sotto disconnessione (che per SYMBIOSIS Law 6 è «stato naturale»); un pool KBLI dev/prod diverso può dare verdetti diversi.

**Severità.** P2. **Cura minima.** Qdrant assente/irraggiungibile ⇒ `kbli_check: "skipped"` registrato (non failure); `HTTPStatusError 429/5xx` e `ConnectError` ⇒ transiente; il check KBLI resta advisory (oggi `validate` non blocca il routing).

---

## C-11 P2 · POLICY — Due roster di telefoni interni; uno è HARD-CODED in un repo PUBBLICO

**Causa root.** `scripts/wa_mirror_intake_sweeper.py:92-110` `_INTERNAL_PHONES_BUILTIN` (letterali) vs `svc/auto_attach.py:106` da `BZ_INTERNAL_PHONE_NUMBERS` (env `~/.wa-mirror.env`); divergenza documentata in `svc/contact_autocreate.py:9-18`. Il repo è pubblico: `gh repo view --json nameWithOwner,visibility,isPrivate` → `{"isPrivate":false,"nameWithOwner":"Bali-Zero/Teman2","visibility":"PUBLIC"}` (misurato in sessione). Nota: il sweeper rilegge la parte ENV del roster a ogni chiamata (`_internal_phones()` `:105-115`) — il problema qui sono i letterali `_INTERNAL_PHONES_BUILTIN` `:92-104`, non il momento di lettura.

**Blast radius.** PII di staff in chiaro su GitHub (Law 2, minimizzazione); due sorgenti di verità ⇒ un numero nuovo aggiunto a una sola.

**Severità.** P2 policy. **Cura minima.** Un solo loader (`svc/contact_autocreate.py`) da env/Keychain; rimuovere i letterali; test che nessun file in `scripts/` contenga `+62`+8 cifre fuori da fixture.

---

## C-12 P2 · OPS/POLICY (W96) — Residui di test nel DB operativo inquinano i conteggi e i log ogni giorno

**Misura.** `intake_queue.status='review_pending'` = 11 (pv `test-5b/test-r6`), `blob_path LIKE '/tmp/5atest%'` = 83, `source_ref LIKE 'test/eo/%' AND status='rejected'` = 600, `dead` con `poison stage=…` = 37 (**righe drive/wa REALI** uccise dall'handler di `backend/tests/services/intake/test_intake_worker.py:380` girato contro `nuzantara_dev`, 23/6→14/7); la retention logga ogni notte `blob_path outside managed blob roots: /tmp/5atest-*.pdf`.

**Blast radius.** Ogni report che conta `review_pending` sulla coda legge 11 fantasmi (è la fonte della domanda «~11 vs 35,8k», A.8-5); 37 documenti cliente veri sono `dead` per un test.

**Severità.** P2 (dati). La guardia conftest esiste dal 28/7 (`backend/tests/conftest.py:39-54`); i residui no.

**Cura minima.** Manifest delle righe (`pipeline_version LIKE 'test-%'`, `blob_path LIKE '/tmp/5atest%'`, `source_ref LIKE 'test/eo/%'`) → decisione Zero: purge o `pipeline_version='test-quarantined'`; per i 37 `dead` poison: reset a `pending` con `pipeline_version` bumped (blob presenti?) — misura prima.

---

## C-13 P3 · BUG — La liveness del reader considera VIVO un 5xx

**Causa root.** `scripts/intake_review_reader_liveness.sh:139` `if [[ "$CODE" =~ ^[1-5][0-9][0-9]$ ]]` (probe `:113-116`, `curl … "%{http_code}"` su `/`). Un reader con pool DB morto risponde 500 su `/` ⇒ «ALIVE».
**Prova (ESEGUITA, mondo finto — W107).** Copia dello script + stub `BaseHTTPRequestHandler` che risponde sempre `500` su `127.0.0.1:18977`, `HOME` puntato a una dir vuota (nessun `tg_notify.py`, nessun plist ⇒ nessun Telegram possibile), `PROBE_PORT=18977`:
```
stub code: 500
[…] probe: http://127.0.0.1:18977/ -> code=500 plist_present=0
[…] OK: reader ALIVE (http 500)      rc=0
```
innocence (dal codice, `:136-138`): 401/404 restano vivi — voluto. (Il refuter Codex ha corretto la prima stesura di questa prova, che citava `python -m http.server`: quello risponde 200/404, non 500.)
**Cura minima.** `^[1-4][0-9][0-9]$` + probe di un endpoint che tocca il DB (`/api/intake/review/document-categories` con token di servizio) atteso 200/401.

---

## C-14 P3 · BUG (latente) — Fill-only dell'enricher è check-then-act senza CAS: due commit concorrenti sullo stesso cliente con valori DIVERSI si sovrascrivono

**Causa root.** lettura `svc/client_enricher.py:292-303`, decisione `:324-343`, `UPDATE clients SET … WHERE id = $1` `:424` senza `AND passport_number IS NULL/''`; l'advisory lock è per VALORE (`:412-421`), quindi due valori diversi non si serializzano.
**Prova.** guilt: test sulla forma SQL (`"WHERE id = $" in sql and "passport_number IS NULL" not in sql`); integrazione a due connessioni su `nuzantara_test`. innocence: singolo commit scrive.
**Cura minima.** CAS per colonna: `passport_number = CASE WHEN COALESCE(passport_number,'')='' THEN $x ELSE passport_number END` (o `WHERE` per-colonna e `RETURNING`).

---

## C-15 P3 · BUG (latente) — Il rollback non annulla le `intake_corrections`: etichette "approved" fantasma nel dataset di feedback

**Causa root.** `execute_commit` scrive `intake_corrections` nella stessa TX (`svc/writer.py:661-723`); `rollback_commit :1224-1407` non le tocca (grep `intake_corrections` fra 1224-1407: 0). **Misura.** 0 corrections su code con audit `rolled_back` (i 3 rollback erano `auto_routed`); latente. **Cura.** `UPDATE intake_corrections SET outcome='rolled_back' WHERE queue_id=$1 AND blob_hash=$2 AND outcome='approved'` nella stessa TX del rollback.

---

## C-16 P3 · DEBT — Estrazione: il 32% dei valori `passport_no` ha forma spazzatura e nessun gate li ferma prima del libro chiavi

**Misura.** Su 77.563 righe `done` con `extract`: `passport_no` presente 7.679; dopo `_normalize_id` **2.430 >12 char** (righe MRZ), **2.359 non alfanumerici**, 13 <6; canonici `[A-Z0-9]{6,12}` 5.231. `_clean_passport_number` (`svc/extract.py:917-924`) è applicato solo dal path label (`:1245, :1337`), non da `_coerce_field` (`:551-619`); `validate_rules._check_passport` (`:155-159`) registra un failure e basta; `_match_person_strong` (`svc/routing.py:371-431`) usa `_normalize_id` (`:288-297`, nessuna lunghezza); l'enricher scrive via `_clean_str` (`svc/client_enricher.py:219`), diversamente da npwp (`_npwp_digits` 15/16 `:230`).
**Innocenza misurata.** I 34 passaporti finora scritti dall'enricher sono tutti canonici (`plan->'payload'->'extracted_fields'` dei 34 audit con `enriched_columns ∋ passport_number` → 34/34 `^[A-Z0-9]{6,12}$`); nessun cliente ha `passport_number` <6 o >16. Il rischio è latente: basta un approve senza correzione su una riga MRZ.
**Due canoni oggi in conflitto** (refuter Codex+Kimi): `svc/validate_rules.py:39` `_PASSPORT_RE = ^[A-Z0-9]{6,9}$` mentre `svc/extract.py:922` accetta `[A-Z0-9]{6,12}` — un valore di 10–12 char passa il cleaner del path label e viene poi marcato malformed da `validate`; `_match_person_strong` (`svc/routing.py:381`) passa da `_normalize_passport` (`:300-310`), wrapper di `_normalize_id`, senza lunghezza. **Cura minima.** UN solo `canonical_passport()` (scelta da fare UNA volta: 6–9 se si segue ICAO 9303 per il campo passaporto MRZ, altrimenti dichiarare perché 12) usato da `_coerce_field`, `_check_passport`, `_match_person_strong` e `ENRICHMENT_MAP`; test guilt (riga MRZ ⇒ scartata) + innocence (`X 123456` ⇒ `X123456`).

---

## C-17 P3 · DEBT — Asimmetria: `try_direct_phone_auto_attach` non ha il check di divergenza fresh-vs-locked

**Causa root.** `_fresh_vs_locked_divergence` è invocato in `_try_auto_attach_inner` (`svc/auto_attach.py:841`) e nel path nameid (`:1142`), mai fra `:935-1059`. Il path direct-phone rivaluta la concordanza in-TX (`evaluate_direct_phone_concordance :517-690`) ma non confronta il candidato "fresco" con quello lockato. **Severità.** P3 (difesa in profondità mancante, non bug provato). **Cura.** stessa chiamata dopo il lock.

---

## C-18 P3 · BUG (latente) — Confronto `received_by` senza `lower()` nella lista `/queue`; e la stringa vuota è un terzo stato non documentato

**Causa root.** `rt/intake_review.py:430` `AND ($3::boolean OR q.received_by = $4)` (mentre `_require_own_chat_or_admin :188-192` e il gate `svc/gate_evaluator.py:100` usano `lower()`); lo sweeper scrive `team_member_email` raw (`scripts/wa_mirror_intake_sweeper.py:600`). **Misura.** case-mismatch oggi 0; `received_by=''` = 43 righe review_pending WA (invisibili ai non-admin come i NULL, ma NON scartate come i NULL dal docstring `:24`). **Cura.** `lower(q.received_by) = lower($4)` + `NULLIF(received_by,'')` alla scrittura.

---

## C-19 P3 · SPEC — Il commento del reader dice il contrario di ciò che fa: «approvals stay dry-run regardless of inherited env» ma è `setdefault`, e l'env vivo dice `1`

**Causa root.** `rd/intake_review_reader.py:159-161`; `scripts/intake_review_reader_run.sh:15-16, 105-109` (default 0, override dall'env-file 0600 → `INTAKE_WRITER_ENABLED=1`). 308 commit reali confermano che il reader scrive. **Blast radius.** Chi legge il codice crede il reader innocuo (famiglia #6/#9: la doc mente). **Cura.** riscrivere il commento: «default dry-run; l'env-file 0600 può armarlo — vedi WARNING in run.sh».

---

## C-20 P3 · DEBT/BUG (latente) — Costanti fotografate all'import: soglie funnel/nome, URL e timeout Ollama; il roster telefoni è un'UNIONE snapshot+env (le aggiunte passano, le RIMOZIONI no); il reprocess script eredita l'env DELLO SCRIPT, non del worker

**Correzione (refuter Kimi).** La prima stesura dava il roster come import-time puro: sbagliato a metà. `svc/auto_attach.py:106-108` fotografa `INTERNAL_PHONE_NUMBERS/PREFIXES` all'import, ma `_internal_phone_config()` `:111-117` ritorna `frozenset((*INTERNAL_PHONE_NUMBERS, *env_numbers))` — UNIONE dello snapshot con una rilettura dell'env, chiamata per messaggio da `_is_internal_sender_phone` (`:125`). Conseguenza: un numero AGGIUNTO all'env dopo l'avvio è onorato; un numero RIMOSSO (dipendente uscito) resta «interno» fino al restart del worker — il difetto è l'opposto di quello che avevo scritto, e la cura è la stessa (nessuno snapshot).
**Causa root (resto).** `svc/auto_attach.py:457-461`; `svc/classify.py:95, 111`; `svc/extract.py:62, 65`; `svc/stages.py:83`. Le modalità `--auto-attach-*` di `scripts/intake_reprocess_backlog.py` importano `auto_attach` nel processo dello script ⇒ soglie/roster potenzialmente diversi da quelli del worker (plist). Contro-esempio nel repo stesso: `scripts/wa_mirror_intake_sweeper.py:105-115` `_internal_phones()` rilegge l'env a ogni chiamata — è il pattern giusto (a parte i letterali, C-11). **Cura.** loader a call-time (come i flag) o un `runtime_config()` unico letto una volta per job.

---

## C-21 P3 · DEBT — `--reprocess` non ha un guard a runtime contro la distruzione dell'unica copia OCR: solo un test lo tiene a bada

**Causa root.** `REPROCESS_SELECT_SQL` (`scripts/intake_reprocess_backlog.py:231-238`) seleziona 10.875 NO_MATCH + unknown; `REPROCESS_RESET_SQL :256` azzera `stage_output`; nessun check `blob_path exists` prima del reset (il test `test_intake_reprocess_backlog.py:1388-1403` protegge il reroute, non vieta il reprocess). **Cura.** in `--reprocess`: escludere (o degradare a route-only) le righe il cui blob non è su disco, e loggare `N of M skipped: blob evicted`.

---

## C-22 P3 · DEBT — Audit e proposal sono cancellabili a cascata da un DELETE sulla coda

**Causa root.** `document_routing_proposal.queue_id … ON DELETE CASCADE` (m212 `:85`), `intake_commit_audit.proposal_id … ON DELETE CASCADE` (m217 `:52`), mentre `intake_queue.instance_id` è `RESTRICT` (`:32`). Un `DELETE FROM intake_queue` (nessuno oggi lo fa, ma nessuna guardia lo vieta) porta via anche la traccia di commit. **Cura.** `ON DELETE RESTRICT` sull'audit (o trigger che vieta il DELETE su code con audit).

---

## C-23 P3 · DEBT — `invalidate_crm_stats()` dentro la TX di commit

**Causa root.** `svc/writer.py:1055` `await invalidate_crm_stats()  # F32` (in `_append_practice_document`, chiamata dentro la TX di `execute_commit`). L'invalidazione precede il COMMIT: un lettore concorrente può ripopolare la cache col valore vecchio; se la TX poi fallisce, si è invalidato per niente. Impatto NON misurato (finestra = durata residua della TX; per questo P3 e non P2). **Cura.** invalidare dopo il commit (nel router `rt/intake_review.py` dopo `execute_commit`), o registrare un `after_commit` hook.

---

## C-24 P3 · SPEC — Entry leak WhatsApp residuo: 29 media inbound senza riga di coda (2 negli ultimi 30 giorni)

**Misura** con il predicato dello sweeper (`scripts/wa_mirror_intake_sweeper.py:528-538`): `inbound_media_total 8.760 · senza coda 29 · ultimi 30gg 2 · gruppi 11`. Il numero della SKILL (~3.084) è stantio: la falla è quasi chiusa; restano 29 da spiegare — TUTTI e 29, inclusi gli 11 di gruppo: la prima stesura li dava per «soppressione voluta», ma il docstring dello sweeper (`:15` «Group media is intentionally still enqueued for OCR/HITL review») e il loop (`:590-604`, `else: group_media += 1` poi `enqueue(...)` per tutti) dicono che i media di gruppo VENGONO accodati (è solo l'hint identità che viene soppresso) — corretto dal refuter Kimi. Candidato causale: lo stallo del watermark su eccezione per-riga (C-31); oggi non attivo (watermark 153.245 = max id media). **Cura.** un contatore nel report giornaliero (`--review-backlog-report`) con questa query.

---

## C-25 P3 · SPEC/UX — La UI carica i 50 PIÙ VECCHI e il payload non dice se il blob esiste

**Causa root.** `page.tsx:285` `?status=review_pending&limit=50` senza offset; `ORDER BY p.created_at ASC` (`rt/intake_review.py:431`); nessun campo `blob_present` nel dict item (`:457-479`). Effetto: pagina 1 = 0/50 blob (C-01). Inoltre (refuter Kimi): l'API espone `status=quarantine|duplicate` (`:366-371`, «LEVA-1 noise tab / LEVA-3 tab») e `/recover` (`:919`), ma `page.tsx` chiede SOLO `status=review_pending` (`:285`) e non chiama mai `recover` (`grep -n "quarantine\|duplicate\|recover" page.tsx` → 0 hit sulle chiamate): i 27.599 documenti parcheggiati da LEVA-1 e i 252 da LEVA-3 sono recuperabili solo via API. **Cura.** `blob_present` (`_resolve_review_blob_path(...) is not None`) + ordinamento "con blob prima" o filtro `?with_blob=1`; tab quarantine/duplicate nella UI con `recover`.

---

## C-26 P3 · OPS — Anti-funnel: confronto cifre grezze senza normalizzare `0…`→`62…`

**Causa root.** `svc/auto_attach.py:636-640` `regexp_replace(q.sender_phone,'[^0-9]','','g') = regexp_replace($1,…)`. **Innocenza misurata.** tutti i 4.542 `sender_phone` in coda sono in forma `+…` (`SELECT CASE WHEN sender_phone LIKE '+%' …` → `plus 4542`), quindi oggi il confronto è coerente; latente se un produttore scrive `08…`. **Cura.** normalizzare a E.164 al momento dell'enqueue (`svc/enqueue.py`) e nel confronto.

---

## C-27 P3 · SPEC — `INTAKE_REVIEW_SOURCES` nasconde 18.902 proposal Drive `review_pending` da OGNI superficie umana

**Misura.** review_pending totali 24.790 − WhatsApp 5.888 = 18.902 Drive (`SELECT q.source,count(*) … p.status='review_pending' GROUP BY 1`). Per disegno (F… «keeps the queue honest», `rt/intake_review.py:65-77`), ma combinato con C-04 e con l'assenza di una vista admin per sorgente, quel backlog è raggiungibile solo dagli script (`--review-backlog-report`). Più forte di quanto scritto in prima stesura (refuter Kimi): anche un `?source=drive` ESPLICITO ritorna `{"total": 0, "items": []}` se la sorgente non è nell'allowlist (`:400-404`) — nessun parametro API supera l'env. Categoria POLICY/SPEC (scelta di default deliberata), non BUG. **Cura.** vista admin `?source=drive` esplicita (allowlist per RUOLO, non per processo) + contatore in `/queue` (`total_by_source`).

---

## C-28 P3 · OPS — `INTAKE_GATE_DISABLED` e `INTAKE_WRITER_ENABLED` su Fly hanno lo stesso valore (digest identico): un solo `fly secrets set` li ha probabilmente armati insieme

Non leggibile in sola lettura (`fly secrets list` espone solo digest). Se il valore è `true`: il gate Fly è spento (C-04) e `INTAKE_WRITER_ENABLED=true` sul processo Fly è inerte solo perché il router `/review*` viene proxato al Pro (`rd/rag_proxy.py:12-18`, `proxy_intake_review_request :199-210`) e Fly non ha le tabelle intake — ma un giorno senza `INTAKE_REVIEW_WORKER_URL` il fallback (`:207-210` `base = get_intake_review_worker_url()` / `if not base:` … «Inert until the tunnel is configured — fall back to the RAG path») esporrebbe il router sul rag process CON writer armato contro un DB privo di schema (fallirebbe rumorosamente, non silenziosamente). **Cura.** `fly secrets unset INTAKE_WRITER_ENABLED` (operator[credentials]) e documentare `INTAKE_GATE_DISABLED` nel ledger.

---


## C-29 ★ P1 · DEBT/OPS — La gamba COMPANY dell'entity resolution è morta per costruzione sul Pro: la tabella `companies` locale ha 0 righe (prod ne ha 1.784)

**Sintomo.** Nessun documento societario (NIB/akta/SK/NPWP company) può mai ottenere un candidato strong-id o fuzzy company: 952 righe `done` con `doc_type` societario e 222 con `nib` estratto sono state instradate contro una tabella vuota.

**Causa root.** `svc/routing.py:462-483` `_match_company_strong` (`FROM companies WHERE REGEXP_REPLACE(nib,…)`) e `:498, :517, :540` (npwp company / akta) leggono SOLO `companies`; il fuzzy company (`_match_fuzzy_name(conn, "companies", "company_name", name)`, `:684`) idem. Sul DB del worker: `SELECT count(*) FROM companies` → **0**; `pg_stat_user_tables` → `companies | 0 live`. In PROD (`bash scripts/pg.sh -At -c "SELECT count(*) FROM companies"`, ruolo read-only) → **1.784**. Le chiavi societarie che ESISTONO localmente stanno altrove: `clients.company_name` 427 e `clients.nib` 291 (alive) — e il matcher non le guarda.

**Misura.**
```
psql … -c "SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE relname IN ('companies','clients','practices','documents')" → companies 0 · clients 33(*) · documents 9 · practices 0   (*) n_live_tup stimato; count(*) clients = 12.544
psql … -c "SELECT count(*) FROM intake_queue q WHERE q.status='done' AND (q.stage_output->'classify'->>'doc_type') IN ('nib','akta_pendirian','npwp_company','sk_kemenkumham','oss','company_npwp','akta')" → 952
psql … -c "SELECT count(*) FROM intake_queue q WHERE q.status='done' AND (q.stage_output->'extract'->'fields' ? 'nib_number' OR … ? 'nib')" → 222
```

**Blast radius.** Correttezza (tutti i doc societari finiscono NO_MATCH/LINK per nome persona o restano in review); il rescue m227 e ogni futura leva su documenti PT PMA sono ciechi; famiglia #9 (lo schema c'è, i dati no).

**Severità.** P1 per la classe "documenti società" (che è il core business PT PMA di Bali Zero); nessun rischio di attach sbagliato (fail-closed: 0 candidati).

**Prova.** guilt: test d'integrazione (`nuzantara_test`) — `companies` vuota + `clients` con `nib` = X → `resolve_entity` su un doc con `nib_number=X` produce 0 candidati (oggi); la cura deve produrre un candidato `clients` con method `nib`. innocence: con `companies` popolata il candidato company resta. Sonda operativa: `SELECT count(*) FROM companies` nel report giornaliero (`--review-backlog-report`) con alert a 0.

**Cura minima.** (i) sync `companies` nel refresh locale (`scripts/nuz_db_refresh.sh` prende SOLO il DB che ha `public.clients`: verificare che il dump includa `companies` — 0 righe suggerisce un restore parziale o una tabella mai popolata localmente); (ii) far leggere a `_match_company_strong`/fuzzy anche `clients.nib`/`clients.company_name` come fallback (le chiavi vive stanno lì); (iii) tripwire "tabella di matching vuota" all'avvio del worker (log WARN + heartbeat degraded).

---

## C-30 ★ P0 · OPS (LIVE) — Il WhatsApp mirror — la SORGENTE primaria dell'intake — è morto da 2 giorni: 6/6 bridge in crash-loop su `ERR_MODULE_NOT_FOUND 'pino'`, zero righe in 48h, nessun P0

Trovato di sbieco alle 18:45 misurando l'innocenza di C-31 (il watermark del sweeper coincideva col `max(id)` dei media… fermo al 13/8).

**Sintomo.** `whatsapp_message_context`: ultima riga `2026-08-13 13:03:26`; righe nelle ultime 48h = **0**; media negli ultimi 7 giorni = 876 (≈125/giorno) ⇒ il silenzio non è fisiologico.
```
SELECT max(created_at), count(*) FILTER (WHERE created_at > now()-interval '48 hours'),
       count(*) FILTER (WHERE media_stored_path IS NOT NULL AND created_at > now()-interval '7 days') FROM whatsapp_message_context;
```
**Causa root (misurata, non dedotta).** `bash ~/scripts/wa-mirror-launcher/status.sh` → 6 bridge linkati 🔴 DEAD (1 non-linkato STOPPED); coda di `/tmp/wa-mirror-logs/<name>.log` (1,0 kB, riscritto ogni ~60 s):
```
Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'pino' imported from /Users/nuzantara/nuzantara/apps/wa-mirror/dist/bridge/index.js
Node.js v26.5.0
```
`~/nuzantara/apps/wa-mirror/node_modules` esiste ma contiene SOLO `.ignored .vite .package-lock.json` (0 pacchetti; `stat` dir → `2026-08-13T04:26:33`), mentre `package.json:23` dichiara `"pino": "^9.5.0"` e `package-lock.json` è del 9/8. I bridge girano dal MAIN checkout (`~/scripts/wa-mirror-launcher/_lib.sh:6` `WA_MIRROR_DIR="$HOME/nuzantara/apps/wa-mirror"`) — famiglia #1 — e vengono rilanciati ogni 60 s da `apps/wa-mirror/scripts/supervise-launcher.sh` (pid 1495, `lstart` 13/8 21:09:46 = reboot del Pro), che li vede morire e «continua». Cronologia: node_modules svuotata 13/8 04:26 (processi già in RAM continuano) → ultima riga 13/8 13:03 → reboot 21:09 → da allora crash-loop. Chi ha svuotato la dir non l'ho trovato in questa sessione (nessun `rm`/`prune` su `node_modules` in crontab/plist/`~/scripts` che coincida con le 04:26; il `pro-git-pull.log` non nomina wa-mirror).

**Perché nessuno ha suonato.** L'unico allarme di questa classe vive DENTRO il bridge (`tg_spool` archivio: `source=wa-mirror-bridge`, chiavi `wa-bridge:down:<name>` / `loggedout:<name>`, ultimo 12/8) — «l'allarme condivide il modo di guasto della cosa che riporta» (W108); il supervisor non conta i figli; `wa-mirror-attention-realtime` scrive `{"alerted": 0, "messages": 0, …}` ogni 10 minuti da due giorni senza escalation; il sweeper logga «no new media» e tace. Nessuna riga P0 mirror-related nel `tg_spool` dal 12/8 (misurato leggendo `archive-p0.jsonl` + `pending.jsonl` per `source/key/text`).

**Blast radius.** L'intake WhatsApp NON RICEVE nulla dal 13/8 13:03: ogni documento cliente inviato via WhatsApp da giovedì è nel telefono dell'operatore e in nessun sistema; CRM lead-autocreate, gate counts, review queue, tutto a valle legge un mondo fermo. È il P0 vivo di questo dossier.

**Azione presa in sessione.** UNA notifica P0 via gateway: `scripts/tg_notify.py --tier p0 --source intake-code-master-audit --dedup-key wa-mirror:all-bridges-dead:err-module-not-found` → `tg_notify: sent` (18:47). NESSUNA riparazione: `npm ci` nel main checkout è una scrittura fuori mandato (read-only + worktree discipline).

**Cura minima (chi ha le mani).** `cd ~/nuzantara/apps/wa-mirror && npm ci` (lock del 9/8) → `bash ~/scripts/wa-mirror-launcher/status.sh` → 6 🟢; poi (strutturale) i bridge dal clone `-deploy` come il worker, e un liveness ESTERNO al bridge: `count(*) FROM whatsapp_message_context WHERE created_at > now()-interval '6 hours' = 0` in orario d'ufficio ⇒ P0 (stesso pattern del liveness #3682 «conta la riga specchiata, non il PID»).

---

## C-31 P3 · BUG (latente) — Il watermark del sweeper si CONGELA per sempre su un'eccezione per-riga permanente (`break` senza avanzare)

**Causa root.** `scripts/wa_mirror_intake_sweeper.py:579-588` (eccezione nell'upsert telefono CRM) e `:604-609` (eccezione in `enqueue()`): `break` senza `max_done = max(max_done, rid)` — il commento dice «Do NOT advance past a transient failure — retry next tick», giusto per i transienti; ma un guasto PERMANENTE su UNA riga (violazione di vincolo, riga malformata che `enqueue` rifiuta) ferma il watermark lì e affama TUTTI i media successivi, per sempre e in silenzio. Le righe strutturalmente rotte (`:563`) e con blob mancante (`:568`) invece avanzano (`continue`) — la classe è stata vista a metà. Watermark persistito solo se `max_done > watermark` (`:616-617`, file `~/.cell-bridge-state/wa_mirror_sweep_last_id.txt`).

**Innocenza misurata (oggi non è fermo).** watermark file = `153245`; `max(id)` media in `whatsapp_message_context` = `153245`; righe sopra il watermark = 0. (Ma vedi C-30: sopra non arriva più niente.)

**Prova.** guilt: test con `enqueue` che alza `ValueError` per il rid N e succede per N+1 → dopo 3 tick il watermark è ancora N−1 e N+1 non è mai stato accodato. innocence: eccezione transiente al primo tick, successo al secondo → watermark avanza al secondo.

**Cura minima.** Distinguere transiente/permanente: su eccezione non-transiente (`ValueError`, `asyncpg.IntegrityError`) loggare, contare `poison += 1`, AVANZARE; su `asyncpg.PostgresConnectionError`/`OSError` `break`; contatore `poison` nel log di fine tick e in `--review-backlog-report`. Segnalato dal refuter Kimi K3, verificato su disco (righe sopra) e da un secondo verificatore indipendente (Explore/Sonnet).

---

## Riepilogo

| ID | Sev | Cat | Titolo breve | Stato prova |
|---|---|---|---|---|
| C-01 | P1 | DEBT/SPEC | retention vs review: 5.522/5.888 ghost | misurato |
| C-02 | P1 | BUG | Ollama giù ⇒ quarantena falsa (831/1.310) | misurato + codice |
| C-03 | P1 | OPS | log worker su inode cancellato | misurato |
| C-04 | P1 | SPEC/OPS | gate conta ciò che la review non mostra | misurato |
| C-05 | P2 | BUG lat. | zombie review_claimed post-rollback | codice, 0 oggi |
| C-06 | P2 | DEBT | reader carica 12 MB + ~3,9k lookup per pagina | misurato |
| C-07 | P2 | SPEC | 23.907 stub / 131 orfani senza tripwire ARMATO; sentinel = 28.199 orfani di cui 28.068 falsi | misurato + COUNT_SQL eseguito |
| C-08 | P2 | SPEC/OPS | delivery senza retry: 241/304 non in Kita | misurato |
| C-09 | P2 | OPS #1 | tre radici, clone worker −1 | misurato |
| C-10 | P2 | SPEC/POLICY | validate dipende dal cloud | 26 dead |
| C-11 | P2 | POLICY | telefoni staff hard-coded in repo pubblico | codice |
| C-12 | P2 | OPS/W96 | residui test + 37 dead da poison | misurato |
| C-13 | P3 | BUG | liveness accetta 5xx | codice + prova eseguita (stub 500 ⇒ ALIVE) |
| C-14 | P3 | BUG lat. | fill-only senza CAS | codice |
| C-15 | P3 | BUG lat. | rollback non tocca corrections | codice, 0 oggi |
| C-16 | P3 | DEBT | 32% passport_no spazzatura, nessun gate | misurato; 34/34 innocenti |
| C-17 | P3 | DEBT | direct-phone senza divergence check | codice |
| C-18 | P3 | BUG lat. | received_by senza lower(); `''` | codice, 0 oggi |
| C-19 | P3 | SPEC | commento reader mente | codice + env |
| C-20 | P3 | DEBT/BUG lat. | costanti import-time; roster = unione, rimozioni non propagano | codice |
| C-21 | P3 | DEBT | `--reprocess` senza guard runtime | codice |
| C-22 | P3 | DEBT | audit cancellabile a cascata | DDL |
| C-23 | P3 | DEBT | invalidazione cache in-TX | codice |
| C-24 | P3 | SPEC | entry leak residuo 29 (gruppi inclusi, non voluti) | misurato |
| C-25 | P3 | UX | UI: 50 più vecchi, niente `blob_present` | misurato |
| C-26 | P3 | OPS lat. | anti-funnel senza E.164 | 4.542/4.542 innocenti |
| C-27 | P3 | SPEC | 18.902 Drive invisibili | misurato |
| C-28 | P3 | OPS | secret Fly gemelli | digest |
| C-29 | P1 | DEBT/OPS | `companies` locale = 0 righe: gamba company morta | misurato (prod 1.784) |
| C-30 | **P0** | OPS LIVE | WA mirror morto dal 13/8: 6/6 bridge crash-loop `pino`, 0 righe/48h, nessun P0 | misurato + log + P0 inviato |
| C-31 | P3 | BUG lat. | sweeper: watermark congelato su eccezione per-riga permanente | codice; oggi non fermo |

Correzioni post-refuter (Codex GPT-5.6 terra + Kimi K3, verbale in `F-verbale-refuter.md`): C-13/B19 riga `:80→:139` (unico anchor sbagliato di ~120 su C, 40 su B); C-08 aritmetica 308 vs 304 spiegata; C-07 titolo «nessun tripwire» → «nessun tripwire ARMATO» + prova eseguita (28.199 falsi); C-20 roster = unione (rimozioni non propagano); C-24 gruppi = accodati per disegno; A.8-4 evidenza grep corretta; A.8-2/A.8-4 cross-ref; 932→951; C-16 due canoni; C-25 tab quarantine/duplicate assenti; C-27 `?source=` esplicito ignorato; C-05 nessun monitor. Aggiunti C-30 (trovato misurando l'innocenza di C-31) e C-31 (segnalato da Kimi).

Cose che ho cercato e NON ho trovato (onestà): zombie `review_claimed` reali (0); case-mismatch `received_by` (0); passaporti spazzatura persistiti dall'enricher (0/34); `sender_phone` in forma `0…` (0); righe con `dead` proposal (0 scrittori).

## Adversarial review

Cross-family refuters (generator ≠ grader): **Codex GPT-5.6 terra** (`codex exec --sandbox read-only`) and **Kimi K3** (`kimi -m kimi-code/k3 -p`), both ordered to destroy the dossier on the worktree, plus two Sonnet anchor-verifiers. Result: 0 findings fell; the weakened items and their on-disk re-verification are recorded in [F-verbale-refuter.md](F-verbale-refuter.md). Refuter transcripts: session scratchpad `refuter-codex-terra.md`, `refuter-kimi-k3.md`.
