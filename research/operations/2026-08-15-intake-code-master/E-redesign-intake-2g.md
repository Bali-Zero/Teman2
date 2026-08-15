---
title: "Intake Code Master — E: Intake 2G redesign, strangler plan, risks, costs, STOP"
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

# Deliverable E — Intake di seconda generazione (redesign)

> Vincoli di sangue mantenuti: mai name-only auto-commit (strong-id o quarantena) · ogni scrittura autonoma dietro doppio consenso (flag specifico AND master) con audit reversibile e kill-switch · PII locale, output Law 2 · ogni wave di scrittura ha manifest, batch_id, rollback provato · la quarantena resta uno stato terminale ONESTO.
> Malattie che il design DEVE curare (da A–D): libro chiavi povero/asimmetrico (C-29, D.1) · retention-vs-recovery (C-01, A.8-3) · falle d'ingresso e infra-down-as-content (C-02, C-24) · frammentazione root/config (C-09, C-20) · gate che non gate-ano (C-04, C-07) · nessun loop di apprendimento (D.2 asse 7).

---

## E.1 Tesi

Il sistema attuale è una **pipeline** giusta con **tre memorie sbagliate**: (1) la memoria del documento è il blob caldo (che muore a 7 giorni), (2) la memoria dell'identità è il CRM (povero, e su Pro senza `companies`), (3) la memoria delle decisioni umane è una tabella (`intake_corrections`) che nessuno rilegge. La seconda generazione non riscrive la pipeline: **le dà tre memorie durevoli** — un **archivio freddo replayable**, un **ledger d'identità progressivo**, un **libro delle correzioni che governa gate ed eval** — e mette davanti a ogni scrittura un **policy engine dichiarativo** con conformance guilt+innocence.

---

## E.2 Architettura

```
 Ingressi (contratto unico IngressEnvelope)          Memorie durevoli               Decisione & scrittura
 ┌───────────┐ ┌──────┐ ┌───────┐ ┌────────┐         ┌───────────────────┐         ┌───────────────────────┐
 │ WA mirror │ │Drive │ │Dropbox│ │Portale*│ ──────▶ │ COLD ARCHIVE      │◀──────  │ Replay Driver         │
 └───────────┘ └──────┘ └───────┘ └────────┘         │ (blob immutabile   │         │ (re-OCR/re-route a    │
        │ enqueue (intake_key)                        │  + derivati)       │         │  costo marginale)     │
        ▼                                             └───────────────────┘         └───────────────────────┘
 ┌──────────────────────────────┐   stage payload      ┌───────────────────┐         ┌───────────────────────┐
 │ intake_queue (v2, invariato) │ ───────────────────▶ │ intake_stage_out  │         │ POLICY ENGINE (gates) │
 │  lease/SKIP LOCKED/DLQ       │                      │ (tabella figlia)  │         │  YAML + conformance   │
 └──────────────────────────────┘                      └───────────────────┘         │  guilt+innocence      │
        │ classify → extract → validate → route                                     └──────────┬────────────┘
        ▼                                                                                       │ verdetto
 ┌──────────────────────────────┐   candidati          ┌───────────────────┐   ┌────────────────▼──────────────┐
 │ resolve_entity (fase 4)      │ ◀─────────────────── │ IDENTITY LEDGER   │   │ writer (plan/execute/rollback) │
 │  strong-id ⟂ hint ⟂ dossier  │                      │ (chiavi+prov+liv.)│◀──│  + OUTBOX delivery             │
 └──────────────────────────────┘                      └───────────────────┘   └────────────────────────────────┘
        │ proposal (routing_key)                              ▲                              │
        ▼                                                     │ conferme umane / commit      ▼
 ┌──────────────────────────────┐                      ┌───────────────────┐   ┌────────────────────────────────┐
 │ /review (priorità per valore)│ ────────────────────▶│ CORRECTIONS BOOK  │──▶│ EVAL HARNESS + tripwire SLO    │
 └──────────────────────────────┘                      └───────────────────┘   └────────────────────────────────┘
```
`*Portale` = canale nuovo (E.7), stesso contratto d'ingresso.

### Componenti e contratti

| Componente | Cosa cambia rispetto a oggi | Contratto |
|---|---|---|
| **IngressEnvelope** | unifica `enqueue()` per WA/Drive/Dropbox/(portale, mail): `source, source_ref, blob_hash, sender_hint{phone E.164, folder_path, client_id_hint}, received_by (lower), pipeline_version` | idempotente per `intake_key`; **normalizzazione E.164 all'ingresso** (C-26); `received_by` sempre `NULLIF(lower(x),'')` (C-18) |
| **Cold Archive** | il blob non è più "cache": è archiviato in `~/.nuzantara/intake-archive/<sha256[0:2]>/<sha256>` (immutabile, dedup per hash) + derivati (`pages.png` ridotte, `ocr.json`) — retention SOLO su derivati e solo per righe **senza** proposal viva né commit non consegnato (cura C-01) | `archive_put(blob) → sha256`; `archive_get(sha256)`; `archive_gc(policy)`; misura: oggi 24,5 GB orfani furono il problema (2026-06-28) → GC per hash orfano, non per età |
| **intake_stage_out** | `stage_output` esce da `intake_queue` in tabella figlia `(queue_id, stage, payload jsonb, created_at)` | riduce bloat/IO (C-06, asse 4); il worker scrive `payload` per stage; la coda tiene solo puntatori |
| **Identity Ledger** | tabella `identity_keys(entity_type, entity_id, key_kind, key_value_norm, level, provenance, source_ref, verified_at, batch_id)` — livelli `L0 declared` (CRM legacy/backfill), `L1 observed` (estratto da doc), `L2 confirmed` (commit umano), `L3 corroborated` (≥2 doc indipendenti) — GATE-11 diventa una riga, non un JSON in `custom_fields`; unione di `clients` E `companies` (cura C-29 con lettura anche di `clients.nib/company_name`) | `resolve_entity` legge il ledger (indice `(key_kind,key_value_norm)`), non le colonne sparse; **solo L2/L3 abilitano AUTO_ATTACH**; L0/L1 ⇒ LINK_CANDIDATE |
| **Policy Engine** | i gate (LEVA-1/2/3, direct-phone, nameid, funnel, sender≠subject, GATE-11, suppression pv) diventano regole YAML valutate da un motore puro (`policy.evaluate(ctx) → verdict, reasons`) con registry in `infra/guard-conformance/` (guilt+innocence obbligatori per OGNI regola) | i flag restano AND-chain (specifico AND master) letti a **call-time** da un solo `runtime_config()` (cura C-20); il verdetto è serializzato nella proposal (`commit_gate.reasons[]`) |
| **Writer + Outbox** | `execute_commit` invariato nella TX; la delivery Pro→Fly diventa una riga `intake_outbox` scritta nella stessa TX e drenata da un consumer idempotente (`idempotency_key`) con backoff e DLQ (cura C-08); `rollback` riporta sempre a `review_pending` (C-05) e marca le corrections `rolled_back` (C-15); enricher con CAS per colonna (C-14) e canonicalizzatori unici (C-16) | outbox = SKIP LOCKED, stati `pending/sent/failed/dead`, mai perde un evento |
| **/review 2** | priorità per valore atteso (asse 5): `blob_present`, decision vicino soglia, doc_type "chiave", cliente con pratica aperta; paginazione SQL; `blob_present` nel payload; vista admin per sorgente | stesso RBAC own-chat; gate = SOTTOINSIEME della coda visibile (C-04) |
| **Corrections Book + Eval** | `intake_corrections` diventa la sorgente del golden set (`eval/intake/`), del report settimanale (precisione per doc_type/campo) e delle proposte di patch prompt/regole (FASE 6 ridotta) | nessuna auto-modifica di regole: le patch sono PR |
| **Auto-misura** | SLO per stage (p50/p95 durata, tasso transiente), tripwire drift: `quarantine_rate`, `zero_candidate_rate`, `all_pages_empty_rate` (C-02), `blob_present_rate` (C-01), `companies_rows>0` (C-29), `orphans_done_without_proposal` (C-07), `worker_log_inode_exists` (C-03) — un solo report giornaliero + TG solo su soglia | segnalatore, non attuatore (famiglia #2) |

### Data model (delta)

```sql
CREATE TABLE intake_stage_out (queue_id BIGINT REFERENCES intake_queue(id) ON DELETE RESTRICT, stage TEXT, payload JSONB, created_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY (queue_id, stage));
CREATE TABLE identity_keys (id BIGSERIAL PRIMARY KEY, entity_type TEXT CHECK (entity_type IN ('client','company')), entity_id BIGINT NOT NULL, key_kind TEXT CHECK (key_kind IN ('passport','kitas','npwp','nib','akta','phone','drive_folder')), key_value_norm TEXT NOT NULL, level SMALLINT CHECK (level BETWEEN 0 AND 3), provenance JSONB NOT NULL, source_ref TEXT, verified_at TIMESTAMPTZ, batch_id TEXT, UNIQUE (key_kind, key_value_norm, entity_type, entity_id));
CREATE INDEX ON identity_keys (key_kind, key_value_norm);
CREATE TABLE intake_outbox (id BIGSERIAL PRIMARY KEY, kind TEXT, idempotency_key TEXT UNIQUE, payload JSONB, status TEXT CHECK (status IN ('pending','sent','failed','dead')), attempts INT DEFAULT 0, next_visible_at TIMESTAMPTZ DEFAULT now(), last_error TEXT);
ALTER TABLE intake_commit_audit DROP CONSTRAINT …proposal_id_fkey, ADD … ON DELETE RESTRICT;  -- C-22
```
Stati: `intake_queue` invariato (v2); proposal invariato + `commit_gate.reasons[]`; outbox 4 stati; ledger `level` 0–3 monotono (mai retrocede se non per rollback con `batch_id`).

---

## E.3 Ragionamento a dossier (oltre il mandato)

`resolve_entity` oggi giudica un documento alla volta. Il **dossier** = gruppo coerente `(sender_phone | folder_path | blob-cluster near-dup)`: se in un dossier esiste ≥1 documento con strong-id L2/L3 e i restanti sono `LINK_CANDIDATE` sullo stesso cliente con nome concordante, la proposta è "attach del dossier" (un solo click umano per N documenti; l'auto-attach resta vietato ai membri senza strong-id proprio — l'invariante non si tradisce, ma il costo umano scende da N a 1). Misura di partenza: 4.542 righe con `sender_phone`; il dossier medio si stima da `SELECT sender_phone, count(*) … GROUP BY 1` (da eseguire in wave 0).

---

## E.4 Migrazione strangler (nessun big bang)

Ogni wave: branch dedicato, manifest `research/operations/intake-2g/waves/W<n>.json` con `{files:[{path,sha256}], flags, sql_migrations, prove_live:[…], rollback:[…], stop:[…]}`, PROVE-LIVE misurato sul sistema vivo, kill-switch per flag, rollback documentato ed eseguito almeno una volta in dry-run.

| Wave | Contenuto | Convivenza | PROVE-LIVE | Rollback |
|---|---|---|---|---|
| **W0 — Misura & tripwire** (nessuna scrittura dati) | **prima di tutto: rianimare la sorgente WhatsApp (C-30, `npm ci` + bridge dal clone `-deploy`) e un liveness ESTERNO ai bridge (`whatsapp_message_context` senza righe per 6h in orario d'ufficio ⇒ P0)**; report giornaliero con le 8 metriche di E.2 "Auto-misura"; sonda inode log; `blob_present` nel payload `/queue`; fix C-13 liveness; sweeper: avanzare su eccezione permanente (C-31); sync `companies` (decisione refresh) | additivo | il report gira 7 giorni; `blob_present_rate` e `all_pages_empty_rate` compaiono nel TG | disabilita plist |
| **W1 — Stop the bleeding** | retention esclude review/committed-not-delivered (C-01); classify transiente (C-02); rollback→review_pending (C-05); `_LIVE_STATUSES` (C-07) e sentinel armato report-only; log rotation worker (C-03); pusher con sorgenti = reader (C-04) | stessi file, comportamento più conservativo | `blob_present_rate` smette di calare (misurato W0→W1); zero nuove quarantene all-empty durante un Ollama-down PROVOCATO in staging (`nuzantara_test`); sentinel invia 1 report | revert PR + kickstart worker |
| **W2 — Cold Archive + stage_out** | `archive_put` all'enqueue (nuove righe); backfill hash→archive per i 366+ blob presenti; `intake_stage_out` scritta in doppio (old+new) per 2 settimane, lettura dal nuovo dietro flag `INTAKE_STAGE_OUT_V2` | doppia scrittura, lettura switchabile | diff 0 fra `stage_output` e `intake_stage_out` su un campione 1% giornaliero; `pg_size` di `intake_queue` non cresce | flag off, tabella resta |
| **W3 — Identity Ledger** | popolamento L0 da `clients/companies` (prod→local sync incluso), L1 dai `stage_out` storici, L2 dai 308 commit; `resolve_entity` legge il ledger dietro flag `INTAKE_LEDGER_RESOLVE`; GATE-11 = level<2 ⇒ LINK | shadow: per 2 settimane il ledger propone, la decisione resta quella vecchia; si loggano le DIVERGENZE | divergenze ≤1% sui casi AUTO_ATTACH; ≥ +N LINK_CANDIDATE su doc company (oggi 0 per C-29) | flag off |
| **W4 — Policy Engine** | regole YAML + conformance CI per ogni gate; il vecchio codice resta il "golden" e il motore gira in shadow con `verdict_old==verdict_new` misurato | shadow → cutover per gate, uno alla volta | 0 divergenze su 30 giorni di proposal reali riprodotte offline (`nuzantara_test`) | cutover inverso per gate |
| **W5 — Outbox delivery** | `intake_outbox` nella TX di commit; consumer drena; il push sincrono resta finché l'outbox non ha consegnato 100 documenti reali | doppio percorso con dedup per `idempotency_key` | tasso `pushed` sui NUOVI commit ≥95%; retry dei 40 `identity_unresolved` dopo backfill phone | flag off; il sync resta |
| **W6 — /review 2 + dossier** | ordinamento per valore, dossier view, vista admin per sorgente | stessa API, parametri opzionali | tempo mediano di decisione ↓ (misurato su `intake_commit_audit.committed_at − claimed_at`), % approve su ghost = 0 | UI flag |
| **W7 — Eval & Corrections loop** | `eval/intake/` con golden set incrementale, backtest gate su ogni PR che tocca `extract.py`/prompt/modello; report settimanale precisione | additivo | primo backtest pubblicato con numeri per doc_type | — |
| **W8 — Tier-2 OCR MLX + Replay** | driver di replay dal Cold Archive; OCR compatto MLX in shadow vs qwen2.5vl sul golden set; cutover se precision ≥ baseline e docs/ora ×2 | shadow | numeri del backtest | modello precedente |
| **W9 — Canali nuovi** | portale upload (stesso `IngressEnvelope`), mail | additivo | 10 upload reali end-to-end in review | disattiva canale |

Convivenza esplicita: fino a W4 incluso il worker VECCHIO decide; i nuovi organi osservano e misurano. Fino a W2 nessuna nuova tabella è letta in produzione. Nessuna wave rimuove codice: la rimozione è una wave a parte, dopo 30 giorni di flag-on.

---

## E.5 Rischi mappati sulle 10 famiglie di cicatrici

| Famiglia | Dove il design potrebbe riammalarsi | Anticorpo strutturale |
|---|---|---|
| #1 HOME-fork | il replay driver e i nuovi cron come script HOME; il worker su `~/nuzantara-deploy` | tutto sotto `infra/launchagents/` + `declared-pairs.json`; il worker legge da un checkout aggiornato da `pro-git-pull.sh`; test `lint_home_fork --check` in CI |
| #2 Esiste≠Armato | tripwire e sentinel "verdi" che non scrivono; outbox consumer fermo; **la sorgente stessa (C-30: 6 bridge in crash-loop 2 giorni, supervisor verde, allarme che viveva DENTRO il bridge)** | ogni organo scrive heartbeat nel DB (`intake_heartbeat(organ, ts, ok)`), il report giornaliero legge SOLO da lì; `outbox.pending age p95` è una metrica con soglia |
| #3 Guard over/under-match | regole YAML con predicati stringa (doc_type LIKE, reason_text.startswith — vedi `auto_attach.py:575`) | ogni regola in `infra/guard-conformance/registry.json` con guilt E innocence; predicati su ENTITÀ (enum doc_type, method enum), mai substring |
| #4 Secret in clear | env-file del reader/outbox con token; plist `.bak` in `~/Library/LaunchAgents` | secrets solo in Keychain (`_read_keychain` come il pusher), `secrets_permissions_audit --fix` in W0, niente `.bak` con env |
| #5 Sibling-race | wave parallele che toccano `routing.py`/`writer.py` | una wave = un worktree = un PR; lease-check hot-zone; regola "arm means freeze" |
| #6 Phantom citation | manifest di wave con file:sha256 scritti a mano | il manifest è GENERATO da script (`sha256sum`) e verificato in CI contro il tree; PROVE-LIVE con comando+output nel manifest |
| #7 KeepAlive | outbox consumer e replay driver come one-shot sotto KeepAlive | consumer = loop bloccante nel wrapper; replay = StartInterval; `lint_plist_keepalive` |
| #8 Network flap | outbox verso Fly; sync `companies` via proxy | retry+backoff+DLQ nell'outbox; `InterfaceError` catturato; sync idempotente riavviabile |
| #9 Schema drift | `intake_stage_out` vs `stage_output` letti da lettori diversi; ledger vs `custom_fields.identity_backfill` | doppia scrittura + diff giornaliero fino al cutover; un solo `read_stage_output()` importato da tutti; migrazione con `-- === ROLLBACK ===` |
| #10 Split-brain | replay driver e outbox consumer avviati anche su Mini | `assigned_node` in `system_settings`, graceful-exit se `hostname≠node`; flock come il pusher |
| W96 (orfana) | test del ledger/outbox contro `nuzantara_dev` | `TEST_DSN_ENV_VARS` guard già esistente + attestazione book per le nuove suite |

---

## E.6 Modello dei costi

| Voce | Stima | Base |
|---|---|---|
| Compute locale (Pro 48GB) | +1 processo outbox (idle), +1 replay driver a finestre notturne; OCR tier-2 MLX 0,9–7B in RAM accanto a qwen2.5vl 7B: ~10–14 GB aggiuntivi in finestra replay | `ollama ps` oggi: qwen2.5vl 7B + qwen3.5 9B; misurare docs/ora in W8 prima di promettere |
| Disco | Cold Archive: 366 blob WA presenti + nuovi ingressi (~stima da `document_instances.byte_size` medio × ingressi/giorno); GC per hash orfano | i 24,5 GB del 2026-06-28 erano ORFANI, non archivio: l'archivio cresce solo con documenti referenziati |
| Cloud gated | zero per default; Gemini OCR resta opt-in `operator[business]` (PENDING-ARMS:204) | Law 2/6 |
| Ore operatore | W0–W1: ~2 sessioni; W2–W5: 1 sessione/wave + 2 settimane di shadow ciascuna; W6–W9: 1 sessione/wave; decisioni Zero: 4 (revive-stub 951 WA, purge residui test, gate on/off, sync companies) | stime, non impegni |
| Refuter cross-family | 1 round per wave (`codex exec gpt-5.6-terra`, sol solo su W3/W4) | flat-sub |

---

## E.7 Piano di test e rollout, con condizioni di STOP

- **Test per wave**: unit (fakes) + integrazione su `nuzantara_test` + conformance guilt/innocence per ogni regola nuova + mutation spot-check su C-01/C-02/C-05 (la cura deve far rosso il test rimuovendola).
- **Rollout**: flag-on su Pro solo dopo shadow ≥14 giorni con divergenza ≤1%; kickstart del worker in finestra notturna; PROVE-LIVE = comando + output nel manifest della wave.
- **STOP (qualsiasi wave)**: (1) un AUTO_ATTACH/auto_routed su cliente sbagliato (anche 1) ⇒ flag off + rollback batch; (2) `blob_present_rate` in calo dopo W1; (3) `pending age p95` outbox > 24h; (4) divergenza shadow > 1% su AUTO_ATTACH; (5) qualsiasi test che punti a `nuzantara_dev`; (6) un secret in chiaro nel manifest o in `~/Library/LaunchAgents/*.bak`; (7) worker `dead` rate > 0,5% delle righe/giorno.

---

## E.8 Cosa NON costruirò e perché

- **Un nuovo runtime di coda** (Procrastinate/River/pgmq): il nostro contratto v2 è già lease-correct e testato (`test_kill9_reclaim_no_job_lost`, `test_exactly_once_two_workers_100_jobs`); cambiare spina = rischio #9 senza guadagno.
- **Un modello ML che decide l'attach**: viola l'invariante «strong-id o quarantena»; l'ML (Splink) serve solo offline per il libro chiavi e per stimare la precisione.
- **Cloud OCR di default**: Law 2/6; resta opt-in `operator[business]`.
- **Un big-bang di reprocess dei 24.790 review_pending / 27.599 quarantine**: senza archivio freddo è distruttivo (A.8-3) e senza chiavi è inutile (D.1: 0,04%).
- **Una UI di review nuova da zero**: `/review` funziona; cambiano ordinamento, payload e dossier.
- **Auto-patch di prompt/regole dal loop di correzioni**: le patch sono PR con refuter, non commit automatici (famiglia #2/#6).
- **Rifare Station 1/2 «come prima»**: misurate morte; ritornano solo tramite Cold Archive (replay a costo marginale) e Ledger (chiavi in più).
- **Un sync bidirezionale prod↔local del CRM**: solo prod→local per `companies/clients` (read-only role), come oggi per il resto; la scrittura verso Fly resta l'outbox di delivery.

## Adversarial review

Cross-family refuters (generator ≠ grader): **Codex GPT-5.6 terra** (`codex exec --sandbox read-only`) and **Kimi K3** (`kimi -m kimi-code/k3 -p`), both ordered to destroy the dossier on the worktree, plus two Sonnet anchor-verifiers. Result: 0 findings fell; the weakened items and their on-disk re-verification are recorded in [F-verbale-refuter.md](F-verbale-refuter.md). Refuter transcripts: session scratchpad `refuter-codex-terra.md`, `refuter-kimi-k3.md`.
