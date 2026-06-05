---
date: 2026-06-04
domain: operations
study: doc-intake-unified
phase: 4 — DESIGN (part 2/5) — QUEUE & ORCHESTRATOR
client_case: false
sources:
  - research/operations/doc-intake-unified/01-system-study.md
  - research/operations/doc-intake-unified/01a-whatsapp-source.md
  - research/operations/doc-intake-unified/01c-processing-pipeline.md
  - research/operations/doc-intake-unified/03-proposed-architecture.md
  - research/operations/doc-intake-unified/03-panel-review.md
  - apps/backend-rag/backend/db/migrations_v2/185_wa_mirror_v2_lid_session_history_ocr.sql
  - .claude/rules/cicatrix-scars.md (W61 retry-storm, W62/W63 worktree, P0-3 KeepAlive)
panel_fixes_addressed:
  - C2 (P0) exactly-once queue semantics — PRIMARY SCOPE
  - C1 (P0) dedup pipeline-version key — consumed via idempotency
  - C6 (P1) PII retention in stage byproducts
---

# FASE 4 — PARTE 2/5 — Queue & Orchestrator (deterministico)

> Scope: l'**orchestratore deterministico** che prende dalla coda intake e fa passare
> ogni documento per `classify → extract → validate → route`. Recepisce il fix panel
> **C2 (P0)**: la coda non ha semantica exactly-once. Questo documento progetta claim
> atomico, lease/heartbeat, retry budget+backoff, poison-pill/DLQ, idempotency-key
> per-stadio, e rende il worker WhatsApp (SPOF single-process sul Pro) resiliente
> **senza** cadere nella retry-storm di W61.

Verdetto panel ereditato (unanime 2/2): **1 orchestratore deterministico, NO swarm**.
Gli stadi sono **funzioni deterministiche** invocate in-process, non agenti che dialogano
a runtime. Il commit path resta singolo, serializzato, replayabile.

---

## 0. Posizione nel sistema (chi sta sopra e sotto)

```
 PARTE 1 (ingestion)            PARTE 2 (questo doc)                 PARTE 3            PARTE 4
 ────────────────────          ───────────────────────────         ─────────         ─────────
 WA consumer (Pro local)  ──┐
 Drive poll (leader-elect)──┼─► ENQUEUE ─► intake_job (coda) ─► ORCHESTRATOR LOOP ─► classify ─┐
 Zoho poll               ──┘   (dedup C1)   pending→...→done     (claim/lease/retry)   extract  │
                                                                  ▲          │          validate │
                                                                  └──────────┘          ──────── │
                                                                  stage funcs deterministiche    │
                                                                                          route ─┘
                                                                                       (PARTE 4)
```

- **PARTE 1** popola `intake_job` (enqueue). Non esegue lavoro pesante.
- **PARTE 2** (questo doc) possiede la coda, lo state-machine, il worker-loop, lease/retry/DLQ.
- **PARTE 3** fornisce `classify()/extract()/validate()` come **moduli Python locali** (no cloud, Law 2).
- **PARTE 4** fornisce `route()` (review-queue DB-backed + commit post-verify su `documents`/`clients`).

---

## 1. Schema coda — `intake_job` (nuova tabella, DB locale `nuzantara_dev`)

La coda esistente `whatsapp_message_context.ocr_status` è **source-specific** e non ha
i campi per exactly-once. Il fix C2 richiede una **coda intake dedicata, source-agnostic**.
`whatsapp_message_context.ocr_status` resta come *flag di stato sorgente* (display dashboard),
ma la macchina a stati vive in `intake_job`.

```sql
CREATE TABLE intake_job (
  id               BIGSERIAL PRIMARY KEY,
  -- ── identità sorgente (contratto PARTE 1) ──
  source           TEXT NOT NULL CHECK (source IN ('whatsapp','drive','zoho')),
  source_ref       JSONB NOT NULL,          -- es. {"message_context_id":123} | {"drive_file_id":"..."} | {"zoho_msg_id":"...","attachment_id":"..."}
  file_path        TEXT NOT NULL,           -- path assoluto locale del file (Law 2: mai byte in DB)
  mime_type        TEXT,
  -- ── dedup (fix C1: chiave include la pipeline version) ──
  blob_hash        TEXT NOT NULL,           -- SHA-256 dei byte
  pipeline_version INT  NOT NULL,           -- bump → riprocessabile anche se blob_hash identico
  -- ── stato (macchina a stati §2) ──
  state            TEXT NOT NULL DEFAULT 'pending',
  stage            TEXT,                    -- ultimo stadio completato: NULL|classify|extract|validate|route
  -- ── exactly-once / lease (fix C2) ──
  lease_owner      TEXT,                    -- worker_id che ha il lock
  lease_expires_at TIMESTAMPTZ,             -- oltre questo istante il job è ri-claimabile
  attempts         INT NOT NULL DEFAULT 0,  -- retry budget
  max_attempts     INT NOT NULL DEFAULT 5,
  next_visible_at  TIMESTAMPTZ NOT NULL DEFAULT now(), -- backoff: non claimabile prima di questo istante
  -- ── osservabilità / errori ──
  last_error       TEXT,                    -- PII-masked (§6)
  stage_output     JSONB DEFAULT '{}'::jsonb, -- output versionato per-stadio + idempotency key
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- ── idempotenza enqueue (C1): stesso blob+pipeline = stesso job ──
  UNIQUE (blob_hash, pipeline_version)
);

-- Indice claim: solo job pronti, ordinati per priorità FIFO, lease scaduto incluso.
CREATE INDEX idx_intake_claimable ON intake_job (next_visible_at, id)
  WHERE state IN ('pending','processing');
```

Nota C1: la UNIQUE `(blob_hash, pipeline_version)` rende l'enqueue **idempotente** e
riprocessabile (bump `pipeline_version` dopo upgrade modello → nuova riga, niente
"scarto silenzioso del dead" segnalato da DeepSeek). Il dedup semantico (phash /
normalized_text_hash) è un **layer separato** descritto in PARTE 1/PARTE 4 — qui basta
che la coda non blocchi il riprocessamento legittimo.

---

## 2. State-machine

```
                    enqueue (PARTE 1)
                          │
                          ▼
                     ┌─────────┐
        ┌───────────►│ pending │
        │ lease      └────┬────┘
        │ scaduto         │ claim (FOR UPDATE SKIP LOCKED)
        │ (worker morto)  ▼
        │            ┌────────────┐  heartbeat ogni H sec
        └────────────┤ processing ├──────────────────────┐
                     └─────┬──────┘                       │ stadio FAIL (transient)
        stadi OK (tutti 4) │                              ▼
                           ▼                    attempts < max ?
                     ┌──────────┐                ├─ sì → backoff → pending (next_visible_at)
       route =       │   done   │                └─ no → dead (DLQ)
       auto-commit   └──────────┘
                           │ route ⇒ confidence < soglia (PARTE 3/4)
                           ▼
                  ┌──────────────┐   human fix (PARTE 4)
                  │ needs_review ├──────────────► re-enqueue (pipeline_version bump) opzionale
                  └──────────────┘

   stato terminali: done | dead | needs_review
   stato non-terminali: pending | processing
```

| Stato | Significato | Chi lo setta | Uscita |
|---|---|---|---|
| `pending` | in coda, claimabile da `next_visible_at` | enqueue / backoff / lease-expiry | → processing |
| `processing` | un worker ha il lease attivo | claim | → done / needs_review / pending(retry) / dead |
| `done` | 4 stadi OK, route auto-commit | route | terminale |
| `needs_review` | route ha prodotto candidate sotto soglia (HITL) | route | terminale (human in PARTE 4) |
| `failed` | **alias transiente interno**: stadio fallito, in attesa di decisione retry/dead. Non persistito a lungo — collassa subito in `pending`(retry) o `dead` | worker | → pending / dead |
| `dead` | retry budget esaurito o poison-pill | worker | terminale (DLQ, alert) |

> `failed` esiste nello state-set richiesto dal task ma è uno **stato di transito atomico**:
> il worker, dentro la stessa transazione di nack, lo risolve in `pending`(backoff) o `dead`.
> Non lasciamo righe ferme in `failed` (eviterebbe il loop). È la traduzione del `nack`.

---

## 3. Loop worker (pseudocodice)

Un solo file Python, eseguibile come `python -m backend.intake.worker`, **un loop
sincrono per claim** (concorrenza = N processi worker indipendenti, ognuno con
`worker_id` univoco; `SKIP LOCKED` li serializza senza contesa).

```python
# backend/intake/worker.py  (PARTE 2)
WORKER_ID   = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
LEASE_SEC   = 300          # 5 min: > durata massima dei 4 stadi su 1 doc multipagina
HEARTBEAT   = 60           # rinnova lease ogni 60s mentre lavora
POLL_IDLE   = 5            # sleep se coda vuota
BACKOFF     = lambda n: min(2 ** n * 30, 3600)   # 30s,60s,120s... cap 1h
STAGES      = [classify, extract, validate, route]   # funzioni deterministiche (PARTE 3/4)

def run():
    install_signal_handlers()          # SIGTERM/SIGINT → graceful: finisci il job corrente, poi exit 0
    while not SHUTDOWN:
        job = claim_one()              # transazione atomica, §3.1
        if job is None:
            sleep(POLL_IDLE)           # coda vuota → idle, NIENTE busy-spin
            continue
        try:
            process(job)               # §3.2 esegue stadi da job.stage in poi
        except PoisonPill as e:        # errore non-transitorio (file corrotto, mime non gestito)
            move_to_dead(job, reason=mask_pii(str(e)))
        except TransientError as e:    # OCR flake, lock DB, IO
            nack_with_retry(job, err=mask_pii(str(e)))   # §3.3
        except Exception as e:         # ignoto → conservativo: retry budget, poi dead
            nack_with_retry(job, err=mask_pii(str(e)))
    sys.exit(0)        # ⚠️ CLEAN EXIT su shutdown → vedi §4 (NO KeepAlive infinito)
```

### 3.1 Claim atomico (fix C2 — `FOR UPDATE SKIP LOCKED`)

```sql
-- una sola query, in transazione. Rende lo stato e prende il lease in un colpo.
WITH next AS (
  SELECT id FROM intake_job
   WHERE state IN ('pending','processing')
     AND next_visible_at <= now()
     AND (lease_expires_at IS NULL OR lease_expires_at < now())   -- lease scaduto = ri-claimabile
   ORDER BY id                  -- FIFO
   FOR UPDATE SKIP LOCKED       -- ← cuore exactly-once: 2 worker non prendono lo stesso job
   LIMIT 1
)
UPDATE intake_job j
   SET state='processing',
       lease_owner=$1,                       -- WORKER_ID
       lease_expires_at = now() + interval '300 seconds',
       attempts = attempts + 1,              -- conteggio tentativo all'atto del claim
       updated_at = now()
  FROM next
 WHERE j.id = next.id
 RETURNING j.*;
```

`SKIP LOCKED` garantisce che due worker concorrenti non vedano mai lo stesso job.
Il `WHERE lease_expires_at < now()` ri-rende claimabile un job il cui worker è **morto**
senza rilasciare il lease (vedi §4).

### 3.2 Esecuzione stadi (resume da `stage`)

Ogni stadio è **idempotente** e scrive il suo output in `stage_output[stage]` con una
**idempotency-key** = `sha256(blob_hash | pipeline_version | stage)`. Se il worker muore
a metà e il job viene ri-claimato, riprende dallo stadio non ancora completato — gli
stadi già fatti **non si rieseguono** (lookup su `stage_output`).

```python
def process(job):
    start = STAGES.index(stage_func(job.stage)) + 1 if job.stage else 0
    ctx = StageContext.from_job(job)          # input contract §5
    for stage in STAGES[start:]:
        idem = sha256(f"{job.blob_hash}|{job.pipeline_version}|{stage.__name__}")
        if idem in job.stage_output:          # già eseguito (crash-recovery): salta
            ctx.merge(job.stage_output[idem]); continue
        renew_lease_if_needed(job)            # heartbeat §4
        t0 = time.monotonic()
        out = stage(ctx)                      # ← FUNZIONE deterministica, NON un agente
        metrics_observe(stage.__name__, time.monotonic()-t0, out.confidence)  # §6
        persist_stage_output(job, idem, out)  # commit incrementale: ogni stadio è un checkpoint
        ctx.merge(out)
        if stage is route:
            finalize(job, out)                # done | needs_review (§3.4)
            return
```

Commit incrementale per-stadio = **crash a metà non perde gli stadi già fatti** e non li
ripete (idempotency-key). Questo è il "ogni stage scrive output versionato con
idempotency key" richiesto da Codex (C2).

### 3.3 Nack con retry budget + backoff

```python
def nack_with_retry(job, err):
    if job.attempts >= job.max_attempts:
        move_to_dead(job, reason=err)         # DLQ
        alert_dlq(job)                        # Telegram (osservabilità §6)
        return
    delay = BACKOFF(job.attempts)             # exponential + cap 1h
    db.execute("""
      UPDATE intake_job
         SET state='pending',                 -- torna claimabile
             lease_owner=NULL, lease_expires_at=NULL,
             next_visible_at = now() + make_interval(secs => $2),  -- backoff
             last_error=$3, updated_at=now()
       WHERE id=$1
    """, job.id, delay, err)
```

`attempts` è già stato incrementato all'atto del **claim** (§3.1), quindi un worker che
muore senza nack **consuma comunque un tentativo** (giusto: previene loop infiniti su un
job che fa crashare i worker). Backoff esponenziale 30s→1h evita la retry-storm.

### 3.4 Finalize

```python
def finalize(job, route_out):
    new_state = 'needs_review' if route_out.requires_human else 'done'
    db.execute("UPDATE intake_job SET state=$2, stage='route', lease_owner=NULL, "
               "lease_expires_at=NULL, updated_at=now() WHERE id=$1", job.id, new_state)
    # idempotenza verso PARTE 4: route() ha già scritto in review_queue/documents con la
    # propria idempotency-key, quindi un ri-claim accidentale di un job 'done' è no-op.
```

---

## 4. Lease + heartbeat + resilienza worker (fix C2 + scar W61)

### Lease & recupero da worker morto
- Al claim, `lease_expires_at = now() + 300s`. Mentre lavora, ogni `HEARTBEAT=60s` il
  worker fa `UPDATE ... SET lease_expires_at = now()+300s WHERE id=$1 AND lease_owner=$WORKER_ID`.
- Se il worker **muore** (crash, kill, reboot): smette di rinnovare → dopo ≤300s
  `lease_expires_at < now()` → il prossimo claim (§3.1) lo ri-prende. Niente job orfani.
- Se il heartbeat fallisce (es. job ri-claimato da altri perché lease era scaduto):
  `WHERE lease_owner=$WORKER_ID` ritorna 0 righe → il worker **abbandona** il job
  (un altro lo possiede già) e passa al prossimo. No doppio-commit.

### Worker resiliente/respawnabile — SENZA retry-storm (scar W61)

Il problema panel C2/DeepSeek: "consumer WhatsApp single-process sul Pro è SPOF".
La trappola scar W61: **un clean-exit one-shot sotto `KeepAlive=true` viene respawnato
all'infinito** (retry-storm). Il worker qui è un **daemon a loop interno** (`while not
SHUTDOWN` con `sleep` su coda vuota), **non** un clean-exit one-shot. Quindi:

> **Regola plist (da scar 2026-05-31, "KeepAlive su clean-exit one-shot = W61 storm"):
> prima di KeepAlive, grep il target per un loop interno.** Questo worker HA il loop
> (`while`/`sleep`), quindi `KeepAlive=true` è corretto e NON genera storm: respawna
> solo su crash reale, e su crash il loop riparte e va in idle se la coda è vuota.

LaunchAgent `com.balizero.intake-worker` (Pro):
```xml
<key>KeepAlive</key><dict>
  <key>SuccessfulExit</key><false/>   <!-- respawna SOLO su exit≠0 (crash). exit 0 graceful = NON respawnare -->
</dict>
<key>RunAtLoad</key><true/>
<key>ThrottleInterval</key><integer>30</integer>  <!-- min 30s tra respawn: anti-flap (difesa W61) -->
<key>StandardErrorPath</key><string>/Users/nuzantara/logs/intake-worker.err.log</string>
<key>StandardOutPath</key><string>/Users/nuzantara/logs/intake-worker.out.log</string>
```

Tre difese anti-storm sovrapposte:
1. **Loop interno + idle-sleep**: la quiescenza è dentro il processo, non nel respawn.
   Coda vuota ⇒ il worker dorme 5s, non esce. launchd non vede mai un exit da respawnare.
2. **`SuccessfulExit=false`**: shutdown pulito (SIGTERM→`sys.exit(0)`) NON viene respawnato.
   Solo i crash (exit≠0) respawnano. Esattamente l'opposto della trappola W61.
3. **`ThrottleInterval=30`**: anche in crashloop hard (es. DB down), max 1 respawn/30s,
   non un loop tight. Più un circuit-breaker applicativo: se 3 claim consecutivi falliscono
   sul *connect* al DB (non sul job), il worker logga `CIRCUIT_OPEN`, dorme 60s, ri-prova —
   degrada anziché martellare (difesa C2/DeepSeek "circuit breaker").

### SPOF → resilienza orizzontale
Il design è **multi-worker-safe by construction** (`SKIP LOCKED`). Per togliere lo SPOF:
- Default: 2 processi worker sul Pro (`com.balizero.intake-worker` con 2 istanze, o un
  prefork da N). Uno muore → l'altro continua + il job orfano torna claimabile in ≤300s.
- Opzionale (futuro): un worker anche su Mini-Pro2 — **ma** i file `wa-mirror-media` sono
  fisicamente sul Pro (Law 2). Mini può lavorare solo job i cui `file_path` sono raggiungibili.
  Per ora: **worker solo sul Pro**, ridondanza = 2 processi, non 2 nodi. (Scelta sovranità:
  i byte PII non lasciano il Pro.)

### Poison-pill / DLQ
- `PoisonPill` (errore deterministico: PDF illeggibile, mime non gestito, file mancante)
  → `dead` **immediato** (niente retry: ripeterebbe lo stesso fallimento). DLQ.
- Retry budget esaurito (`attempts >= max_attempts`, default 5) → `dead`. DLQ.
- `dead` = riga in `intake_job` con `state='dead'` + `last_error` + alert Telegram.
  **NON cancellata**: è la dead-letter queue, ispezionabile, ri-attivabile manualmente
  (`UPDATE state='pending', attempts=0, next_visible_at=now()` o bump `pipeline_version`).

---

## 5. INTERFACCE (contratti verso PARTE 1 / 3 / 4)

### ← PARTE 1 (ingestion → enqueue)
PARTE 1 chiama **una funzione di enqueue** (no SQL diretto dai poller). Contratto input:

```python
def enqueue(item: IntakeItem) -> EnqueueResult:
    """Idempotente. Calcola blob_hash, applica dedup C1, INSERT ... ON CONFLICT DO NOTHING."""

@dataclass
class IntakeItem:               # ← contratto da PARTE 1
    source: Literal['whatsapp','drive','zoho']
    source_ref: dict            # {'message_context_id': int} | {'drive_file_id': str} | {'zoho_msg_id','attachment_id'}
    file_path: str              # path assoluto locale (PARTE 1 garantisce file già su disco)
    mime_type: str | None
    blob_hash: str              # SHA-256 dei byte (PARTE 1 lo calcola in ingestion)
    pipeline_version: int = CURRENT_PIPELINE_VERSION

@dataclass
class EnqueueResult:
    job_id: int | None          # None se duplicato (ON CONFLICT) — non un errore
    deduped: bool
```

Mapping sorgenti → enqueue (PARTE 1 li implementa, PARTE 2 li riceve):
- **WhatsApp**: il consumer locale drena `events_outbox.whatsapp_message_received` **oppure**
  polla `whatsapp_message_context WHERE ocr_status='pending' AND media_stored_path IS NOT NULL
  AND media_type IN ('document','image')` → costruisce `IntakeItem(source='whatsapp',
  source_ref={'message_context_id': row.id}, file_path=row.media_stored_path, ...)`.
- **Drive**: `drive_poll_service` (Changes API, leader-elect Pro+Mini) → scarica byte in locale → enqueue.
- **Zoho**: poll `list_emails(is_unread)` → `get_attachment()` → salva locale → enqueue.

### → PARTE 3 (classify / extract / validate — funzioni deterministiche)
L'orchestratore le importa e le chiama **in-process** (NON via rete, NON come agenti):

```python
# contratto comune: ogni stadio è (StageContext) -> StageOutput, deterministico, locale.
def classify(ctx: StageContext) -> StageOutput: ...   # → doc_type + confidence per-tipo
def extract(ctx:  StageContext) -> StageOutput: ...   # → fields{name: {value, confidence}}
def validate(ctx: StageContext) -> StageOutput: ...   # → regole NB (NIB 13, NPWP 16, modal, KITAS E-codes)

@dataclass
class StageContext:             # accumulatore passato di stadio in stadio
    job_id: int
    file_path: str              # i byte restano locali (Law 2)
    mime_type: str | None
    doc_type: str | None        # popolato da classify
    fields: dict = field(default_factory=dict)   # popolato da extract
    prior_output: dict = field(default_factory=dict)  # stage_output già persistito (resume)

@dataclass
class StageOutput:
    stage: str
    confidence: float           # ∈ [0,1]
    data: dict                  # payload strutturato dello stadio
    requires_human: bool = False
    rationale: str | None = None   # ⚠️ C6: rationale STRUTTURATO MINIMO, MAI CoT grezzo con PII
```

**Vincolo C6 (PARTE 2 enforce)**: l'orchestratore persiste in `stage_output` **solo**
`{confidence, data minimale, model, version, blob_hash}` — **mai** il chain-of-thought
grezzo del classify (contiene PII). Se uno stadio ritorna `rationale`, viene troncato/
strutturato prima del persist.

### → PARTE 4 (route — review-queue + commit post-verify)
`route()` è l'ultimo stadio. Stesso contratto `(StageContext) -> StageOutput`, ma con
effetti collaterali governati (scrive in `review_queue`/`documents`/`clients` con propria
idempotency-key). Ritorna `requires_human=True` se sotto soglia → l'orchestratore setta
`needs_review`; altrimenti `done`.

```python
def route(ctx: StageContext) -> StageOutput:
    """PARTE 4. Scrive candidate in review_queue DB-backed (NO mutation diretta su
    documents/clients sopra-soglia → commit post-verify). Idempotente su
    sha256(blob_hash|pipeline_version|'route')."""
```

L'orchestratore **non sa** come PARTE 4 risolve entity-resolution / versioning SK↔PERBAIKAN /
gate per-campo: glieli delega. PARTE 2 garantisce solo che `route` venga chiamato
**esattamente una volta per esito** (idempotency-key) e che il risultato transiti
`done|needs_review`.

---

## 6. Osservabilità (metriche per-stadio, log PII-masked)

- **Metriche per-stadio** (`metrics_observe(stage, latency, confidence)`) → tabella
  `intake_stage_metrics(job_id, stage, latency_ms, confidence, model, ok, ts)` (append-only).
  Aggregabili: p50/p95 latenza per stadio, distribuzione confidence, % `needs_review` per
  `doc_type`, throughput/h, profondità coda (`pending` count), età del job più vecchio.
- **DLQ alert**: ogni `move_to_dead` → Telegram (`TELEGRAM_OWNER_CHAT_ID`) con `job_id`,
  `source`, `last_error` mascherato. Più digest giornaliero "N dead ultime 24h".
- **Log PII-masked** (`mask_pii(s)`): regex su NIK(16), NPWP(16/15), passport(`[A-Z]\d{7}`),
  phone E.164, email → sostituiti con `<NIK>`/`<PASSPORT>`/… prima di scrivere su
  `last_error`, log file, Telegram. **Nessun valore di campo estratto finisce nei log.**
  Coerente con C6 e con la "Clean Logging" golden rule (logger, mai print).
- **Audit append-only** (da proposta §Audit): l'agente audit **osserva** `intake_job` +
  `intake_stage_metrics` (event-log), **mai nel hot-path** — zero coupling col worker.

---

## 7. Cosa NON fa questo documento (boundary)
- NON definisce gli algoritmi di classify/extract/validate (PARTE 3) né route/entity-
  resolution/versioning (PARTE 4). Solo i **contratti** verso di essi (§5).
- NON definisce il dedup semantico phash/normalized_text_hash (PARTE 1/4). Qui C1 è
  consumato solo come **idempotency-key di enqueue** `(blob_hash, pipeline_version)`.
- NON tocca `whatsapp_message_context.ocr_status` come macchina a stati (resta display);
  la verità di stato è `intake_job`.

---

## SINTESI (8 righe)

1. **Coda nuova `intake_job`** source-agnostic (WA/Drive/Zoho) con stati
   `pending→processing→done|dead|needs_review`; `whatsapp_message_context.ocr_status` resta solo display.
2. **Exactly-once (C2 P0)**: claim atomico `FOR UPDATE SKIP LOCKED` + `lease_expires_at`
   → due worker non prendono mai lo stesso job, e un job orfano torna claimabile in ≤300s.
3. **Lease+heartbeat**: rinnovo ogni 60s; worker morto → lease scade → ri-claim automatico,
   nessun job perso, nessun doppio-commit (`WHERE lease_owner=$ME`).
4. **Retry budget+backoff esponenziale** (5 tentativi, 30s→1h cap) + **poison-pill→DLQ
   immediato**; `attempts` incrementato al claim ⇒ un crash ripetuto va comunque in dead.
5. **Anti retry-storm (scar W61)**: worker = daemon a loop interno (idle-sleep su coda
   vuota), `KeepAlive SuccessfulExit=false` (respawna solo crash) + `ThrottleInterval=30`.
6. **Stadi = funzioni deterministiche in-process** (no swarm, verdetto panel), eseguiti
   in sequenza con **commit incrementale + idempotency-key per-stadio** (crash-resume senza ripetere).
7. **C6**: persistito solo rationale strutturato minimo + confidence + model/version/hash;
   mai CoT grezzo; log e DLQ **PII-masked**; byte PII mai fuori dal Pro (Law 2).
8. **Resilienza SPOF**: 2 worker-process sul Pro (non 2 nodi, per sovranità file);
   circuit-breaker su DB-down; metriche per-stadio append-only + audit fuori hot-path.

### INTERFACCE
- **← PARTE 1**: `enqueue(IntakeItem{source, source_ref, file_path, mime_type, blob_hash,
  pipeline_version}) -> EnqueueResult{job_id|None, deduped}`. Idempotente
  (`ON CONFLICT (blob_hash,pipeline_version)`). PARTE 1 garantisce file già su disco locale + hash calcolato.
- **→ PARTE 3**: `classify|extract|validate(StageContext) -> StageOutput{stage, confidence,
  data, requires_human, rationale_strutturato}`. Chiamate **in-process**, deterministiche, locali.
- **→ PARTE 4**: `route(StageContext) -> StageOutput{requires_human}`. Idempotente su
  `sha256(blob_hash|pipeline_version|'route')`; scrive review-queue (commit post-verify, no
  mutation diretta sopra-soglia); l'orchestratore mappa l'esito in `done|needs_review`.
