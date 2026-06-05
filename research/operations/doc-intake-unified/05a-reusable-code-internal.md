---
date: 2026-06-04
domain: operations
client_case: doc-intake-unified
sources:
  - apps/backend-rag/backend/services/workflow/queue.py
  - apps/backend-rag/backend/services/events/outbox.py
  - apps/backend-rag/backend/services/crm/drive_poll_service.py
  - apps/backend-rag/backend/app/routers/crm_enhanced.py
  - apps/backend-rag/backend/llm/ollama_client.py
  - apps/backend-rag/backend/services/wa_copilot/identity_resolver.py
  - apps/backend-rag/backend/services/intel/intel_staging_service.py
  - apps/backend-rag/backend/app/utils/crm_utils.py
---

# 05a — Reusable Internal Code for Unified Document-Intake

Caccia al codice riusabile dentro il repo Nuzantara (Pro, `~/Desktop/nuzantara`)
per costruire il sistema document-intake unificato senza reinventare.
Letti i file reali (non grep superficiale). Verdetti: massimizzare riuso.

## Tabella sintetica

| Mattone | Codice esistente | File:riga | Verdetto |
|---|---|---|---|
| 1. CODA SKIP LOCKED + lease + retry + DLQ | `workflow_jobs` queue PG-only (dequeue/heartbeat/ack/fail/retry) | `services/workflow/queue.py:62-214` | **FORKARE-E-ADATTARE** (template quasi perfetto) |
| 1b. Variante con visibility_at esplicito | legal ingest worker | `services/ingestion/legal_full_ingestion_worker.py:50-62` | **RIUSABILE-DIRETTO** (pattern alternativo) |
| 1c. Outbox replay/ack/prune (at-least-once) | `events_outbox` | `services/events/outbox.py:180-470` | **RIUSABILE-DIRETTO** (per event-emit, NON per work-queue) |
| 1d. DLQ vero | NON esiste a livello DB-row; solo `dlq_autopilot.py` (launchd-job DLQ su file json) | `scripts/dlq_autopilot.py` | **NON ESISTE per work-items, COSTRUIRE** (terminal `failed` c'è) |
| 2. POLL ADAPTER (cursor + circuit breaker + dispatch) | Drive poller con `DriveCircuitBreaker` + page_token in system_settings | `services/crm/drive_poll_service.py:34-360` | **FORKARE-E-ADATTARE** (generalizzabile) |
| 3. OCR LOCALE strict (qwen2.5vl think:false) | blocco Ollama-local in `_gemini_ocr` (Attempt 1) | `app/routers/crm_enhanced.py:88-123` | **FORKARE-E-ADATTARE** (estrai solo Attempt 1) |
| 3b. Vision call generica | `ollama_chat` / `ollama_generate` con `think:False` | `llm/ollama_client.py:65-260` | **RIUSABILE-DIRETTO** |
| 3c. pdf→image | PyMuPDF (`fitz`) già usato | `core/parsers.py:264-376` | **RIUSABILE-DIRETTO** (fitz, NO pdftoppm/sips nel repo) |
| 4. ENTITY RESOLUTION doc→cliente | multi-signal resolver (phone_e164, lid_map, team_email, trgm fuzzy name) | `services/wa_copilot/identity_resolver.py:97-320` | **RIUSABILE-DIRETTO** (riusare quasi as-is) |
| 4b. phone normalize | `normalize_phone_e164` (lib `phonenumbers`) | `services/crm/client_core.py` | **RIUSABILE-DIRETTO** |
| 5. REVIEW QUEUE / HITL | intel staging+voting (file json, Telegram approve/reject) | `services/intel/intel_staging_service.py:88-367` + `intel_approval_service.py:34-244` | **FORKARE-E-ADATTARE** |
| 5b. RBAC access gate | `verify_client_access` (admin/assigned tuple + 403/404) | `app/utils/crm_utils.py:108-160` | **RIUSABILE-DIRETTO** |
| 5c. Inbox list pattern (filtri+RBAC owner) | `workspace_inbox.feed` | `app/routers/workspace_inbox.py:42-104` | **FORKARE-E-ADATTARE** |

---

## 1. CODA — FOR UPDATE SKIP LOCKED + lease + retry + DLQ → FORKARE-E-ADATTARE

**Il sistema ce l'ha già, ed è ottimo.** `services/workflow/queue.py` (214 righe) è una
work-queue Postgres-only senza Redis/Celery, progettata per Fly auto_stop. Riusa quasi tutto:

- **Dequeue atomico SKIP LOCKED** (`_dequeue_one`, riga 62-80): CTE `SELECT … FOR UPDATE
  SKIP LOCKED LIMIT 1` + `UPDATE … SET status='in_progress', visible_at=NOW()+15min,
  retry_count=retry_count+1 RETURNING …`. Questo è ESATTAMENTE il pattern lease+claim cercato.
- **Lease = visibility timeout** (`VISIBILITY_TIMEOUT_MINUTES=15`, riga 26): il "lease" è
  `visible_at` nel futuro; un altro worker non lo ripesca finché non scade.
- **Heartbeat** (`_heartbeat`, riga 83 + `_run_heartbeat`, riga 159): estende `visible_at`
  ogni 120s durante job lunghi (LLM/OCR stall) → previene doppia esecuzione. Cruciale per OCR
  multi-pagina che può durare >120s.
- **Retry con backoff** (`_fail_job`, riga 104): `new_status = "failed" if retry_count >=
  MAX_RETRIES(3) else "pending"`, e su retry rimette `visible_at=NOW()+1min`. Backoff fisso 1min.
- **Worker loop** (`run_worker`, riga 190): poll ogni 5s, `spawn()` per non bloccare il dequeue.

**Cosa adattare**: rinominare `workflow_jobs`→`document_intake_jobs`, payload = {file_id, source,
mime}, `chain_id`→`adapter`/`doc_type`. Aggiungere colonna `dlq` o tabella `intake_dlq` perché
il **DLQ vero NON esiste** (vedi sotto).

**Variante alternativa** `legal_full_ingestion_worker.py:50-62`: stesso SKIP LOCKED ma usa
`visibility_at` con interval parametrico (`SET visibility_at = NOW() + $1::interval`) e filtra
`WHERE status NOT IN ('complete','failed') AND visibility_at <= NOW()`. Pattern equivalente,
utile se serve visibility timeout configurabile per-job.

**DLQ — NON ESISTE per work-items, COSTRUIRE.** Due cose chiamate "DLQ" nel repo, nessuna serve:
- `queue.py` ha solo status terminale `failed` (riga 111) — niente tabella DLQ, niente replay
  da failed, niente diagnosi. Item morto = riga `failed` lasciata lì.
- `scripts/dlq_autopilot.py` (689 righe) è un DLQ **per LaunchAgent jobs falliti** (file
  `~/.agent/dlq.json`, lock fcntl, diagnosi LLM, escalation Telegram). NON è row-level, NON
  riusabile per doc-items. Concettualmente ispirante (auto-diagnosi LLM dei fail) ma off-scope.
- `events/outbox.py` (`replay_unconsumed`/`acknowledge`/`prune_consumed`, riga 180-470) è
  at-least-once **per eventi pub/sub** (EventBus PG NOTIFY), NON per work-queue con esecuzione.
  Riusabile se l'intake deve EMETTERE eventi a valle, non per la coda di lavoro stessa.

→ **Verdetto blocco 1**: forka `queue.py` come motore coda. Aggiungi tabella DLQ
(`status='failed'` → move row to `intake_dlq` con `last_error`, `attempts`, `failed_at`) — ~40
righe nuove. Tutto il resto (claim/lease/heartbeat/retry) è gratis.

---

## 2. POLL ADAPTER pattern → FORKARE-E-ADATTARE (generalizzabile come template)

`services/crm/drive_poll_service.py` (669 righe) è un poller PRODUZIONE completo, ottimo da
generalizzare come base-class adapter per WhatsApp/Zoho:

- **Cursor persistente in `system_settings`** (riga 261-273): `SELECT value FROM system_settings
  WHERE key='drive_poll_page_token'`; first-run inizializza via `get_start_page_token()`; salva
  sempre `new_token` anche se 0 changes (riga 285). → Generalizza la key: `<adapter>_poll_cursor`.
- **Circuit breaker riusabile** (`DriveCircuitBreaker`, riga 34-98): stati closed/open/half-open,
  `failure_threshold=3`, `recovery_timeout=300s`, alert Telegram su open. È una classe
  autonoma, parametrizzabile — **estraibile in `services/common/circuit_breaker.py`** e
  condivisa da tutti gli adapter. `.call(fn, on_open)` ritorna None se open (skip silenzioso).
- **Changes API + diff** (`_do_poll_drive_changes`, riga 241+): `list_changes_since(page_token)`
  → `{changes, new_page_token}`; loop su changes con skip di removed/trashed/folder.
- **Dispatch idempotente** (`_dispatch_ocr_by_folder`, enqueue Guardian "idempotente, repeated
  Drive changes collapse into one", riga 158): già pensa alla dedup. Sostituisci il dispatch OCR
  con `enqueue_workflow()` della coda blocco 1 → adapter scrive in coda invece di OCR diretto.

**Cosa adattare**: astrarre `poll_<source>_changes()` in un `BasePollAdapter` con hook
`read_cursor()/fetch_changes(cursor)/save_cursor()/dispatch(change)`; le subclass WhatsApp/Zoho
implementano `fetch_changes`. Il circuit breaker e la persistenza cursor sono già riutilizzabili
1:1. ~80% del codice è generalizzabile.

---

## 3. OCR LOCALE strict → FORKARE-E-ADATTARE (estrarre solo l'Attempt-1 local)

La funzione `_gemini_ocr` in `crm_enhanced.py:74-220` è multi-tier (Ollama → Gemini CLI →
Gemini API). Per intake **strict local-only** forka SOLO il primo blocco:

- **Attempt 1 Ollama qwen2.5vl:7b** (riga 88-123): `is_ollama_available("qwen2.5vl:7b")` →
  `base64.b64encode(image_data)` → POST `{settings.ollama_url}/api/chat` con
  `messages=[{role:user, content:prompt, images:[image_b64]}]`, `stream:False`,
  `options={temperature:0.1, num_predict:512}`. Ritorna `message.content`. **Questo è il
  pezzo local-only riusabile** — copialo, butta gli Attempt 2/3 (Gemini = cloud, vietato strict).
- Nota: questo blocco fa POST httpx diretto e NON passa per `ollama_client.py` (anti-pattern
  client effimero riga 99 `_httpx.AsyncClient`). Meglio rifattorizzare su `ollama_chat`.

**Vision call generica** `llm/ollama_client.py:65-260`: `ollama_chat`/`ollama_generate`/
`ollama_chat_kg` con **`think:False`** (riga 82/149/221, INVARIANTE per Qwen3.5) e client httpx
persistente (`_get_client`, riga 42). → **RIUSABILE-DIRETTO**: aggiungi un `images` kwarg a
`ollama_chat` e usalo per il vision OCR invece del POST inline. Risolve anche golden-rule #10.

**pdf→image**: NON c'è `pdftoppm`/`sips`/`pdf2image` nel repo. C'è **PyMuPDF (`fitz`)** già
importato in `core/parsers.py:264-376` (text extract + OCR scanned via Tesseract se presente).
→ **RIUSABILE-DIRETTO** per rasterizzare PDF→PNG prima di mandare a qwen2.5vl (`page.get_pixmap()`).
Ricorda regola CLAUDE.md §13: OCR multi-page SEMPRE tutte le pagine (directors pag 2-3 akta),
timeout 120s per >3 pagine.

---

## 4. ENTITY RESOLUTION doc→cliente → RIUSABILE-DIRETTO

`services/wa_copilot/identity_resolver.py` (859 righe) è il matcher cliente già rodato
(S1.3 identity resolver). Multi-signal con confidenze, idempotente:

- **Signal #1 phone_e164** (riga 97): `normalize_phone_e164(raw)` → `SELECT … WHERE
  phone_normalized IN ($1,$2)`, fallback `LIKE '%'||$1`. conf 0.95.
- **Signal #2 lid_map** (riga 152): `whatsapp_lid_phone_map.jid_phone` JOIN `clients`. conf 0.90.
- **Signal #3 team_email** (riga 183): `LOWER(email)=LOWER($1) AND active=true`. conf 1.00.
- **Signal #4 fuzzy name** (`resolve_drive_folder`, riga 287): `_parse_label_name()` estrae nome
  da label → `SELECT id, full_name, similarity(full_name,$1) AS sim FROM clients WHERE
  full_name % $1 ORDER BY sim DESC LIMIT 2`. **Fuzzy = pg_trgm `%`/`similarity()` lato SQL**,
  con margin-guard via top-2 e cache per-batch. conf 0.70+.

**IMPORTANTE — niente rapidfuzz/jellyfish nel venv.** Verificato `ls .venv/site-packages`:
presente solo **`phonenumbers` (9.0.29)**. Il fuzzy matching NON usa lib Python — usa
**pg_trgm** (`similarity()`, operatore `%`) direttamente in Postgres. → Riusa quel pattern,
NON introdurre rapidfuzz.

→ **Verdetto**: per doc→cliente riusa `resolve_phone_e164` (se il doc ha telefono),
`resolve_drive_folder`/`_parse_label_name`+trgm (se hai un nome estratto dall'OCR), e
`normalize_phone_e164` (`crm/client_core.py`). La struttura `ResolveResult`/`ResolverMetrics`
(dataclass con client_id+method+confidence) è il modello dati da riusare per il match doc→client.
Migration `166_reconcile_client_email_duplicates.sql` è solo reconcile dati, non logica match.

---

## 5. REVIEW QUEUE / HITL → FORKARE-E-ADATTARE (+ RBAC riusabile diretto)

Due pattern HITL esistono, scegli per UX:

**(a) File-based staging + Telegram voting** — `intel_staging_service.py` (367+ righe) +
`intel_approval_service.py`:
- `save_staging_item`/`load_staging_item`/`list_pending_items` (riga 88-330): coda su file json
  con `status ∈ {pending, approved, published, rejected}`, `check_duplicate`, `archive_item`
  (approved/rejected/published).
- Voting Telegram (`intel_approval_service.send_approval_notification`, riga 34; keyboard
  `intel:approve:…` / `intel:reject:…`, riga 214-244; `_save_voting_status` con
  `votes={approve:[],reject:[]}`, required_votes N/M). → Pattern "lista item + approva/correggi"
  COMPLETO ma file-based; forka se vuoi review via Telegram (coerente con OSINT Law 2 local).

**(b) DB-backed list + RBAC** — `workspace_inbox.py:42-104`:
- `feed()`: SELECT con filtri (channel/client_id/direction/limit) + JOIN clients + owner-gate
  `_require_inbox_owner`. → Template "lista item da revisionare". Forka cambiando la tabella
  sorgente in `document_intake_jobs WHERE status='needs_review'` + endpoint approve/correct.

**RBAC riusabile diretto** — `app/utils/crm_utils.py:108-160` `verify_client_access`:
- Ritorna `(has_access, assigned_to)`, admin sempre OK (`is_crm_admin`), 404 se client
  inesistente, 403 se non-admin senza accesso. Usato in 17 file. → **RIUSABILE-DIRETTO** per
  gating "chi può approvare il doc match per il cliente X". Combina con admin-list CLAUDE.md §13
  (zero@/antonellosiano@/asya@).

→ **Verdetto**: per la review-queue del doc-intake conviene il pattern **(b) DB-backed**
(coerente con la coda blocco 1: `status='needs_review'` è solo un altro stato della stessa
tabella `document_intake_jobs`), riusando `verify_client_access` per il gate e la shape di
`workspace_inbox.feed` per il list endpoint. Il voting Telegram (a) è opzionale se serve
approvazione mobile asincrona.

---

## Sintesi riuso (massimizza riuso, minimizza codice nuovo)

1. **Coda**: forka `workflow/queue.py` interamente (SKIP LOCKED + lease via visible_at +
   heartbeat 120s + retry MAX=3 backoff 1min). UNICO codice nuovo: tabella/colonna DLQ (~40 righe).
2. **Adapter**: generalizza `drive_poll_service.py` in `BasePollAdapter`; estrai
   `DriveCircuitBreaker` in `services/common/` e condividilo (cursor in system_settings 1:1).
3. **OCR**: estrai SOLO l'Attempt-1 Ollama qwen2.5vl di `_gemini_ocr` (crm_enhanced.py:88-123),
   rifattorizzandolo su `ollama_chat`+`think:False`; PDF→PNG via `fitz` (già in parsers.py).
4. **Match**: riusa `wa_copilot/identity_resolver.py` (phone_e164 + trgm fuzzy name) +
   `normalize_phone_e164`. ATTENZIONE: fuzzy = pg_trgm SQL, NON rapidfuzz (non nel venv;
   solo `phonenumbers` presente).
5. **HITL**: `status='needs_review'` come stato della stessa coda; list endpoint clona
   `workspace_inbox.feed`; gate con `verify_client_access` (riusabile diretto). Telegram
   voting (intel_approval_service) opzionale.

**Codice realmente NUOVO da scrivere**: tabella DLQ + move-on-fail; astrazione BasePollAdapter
(thin); refactor `ollama_chat(images=...)`; glue endpoint review approve/correct. Tutto il
resto è fork/riuso diretto. Stima: ~70% riuso, ~30% glue nuovo.
