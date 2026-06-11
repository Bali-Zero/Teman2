# WA Meta Inbox — Design Spec

```
date: 2026-06-03
domain: ops / channels
client_case: internal-tool
status: panel-approved (5/5 sections, 3-LLM each, 15 reviews, 0 REJECT)
panel: DeepSeek V4 Pro + Codex GPT-5.5 + Gemini 3.1 Pro (per-section adversarial)
author: Claude Opus 4.8 (orchestrator) per Antonello
```

## Scopo

UI desktop locale (icona Mac `.app` → `localhost:7791`) per **leggere e scrivere** sul canale WhatsApp Business Meta API **+62 821-3465-159** (`verified_name=BALI ZERO`, `phone_number_id=1104946272705747`). Antonello sta per pubblicarlo come numero di contatto pubblico → deve poterlo **preparare e monitorare PRIMA** della pubblicazione. Oggi i messaggi Meta finiscono solo al webhook Fly (`inbound_webhooks`, ultimo 2026-06-02) e nessuna UI li mostra.

Il bot AI esistente (triage `business→RAG`) resta attivo come **human-in-the-loop**: risponde di default, ma Antonello può prendere il controllo di un thread (bot OFF su quel thread finché non lo riattiva).

## Vincoli

- Zero nuove API a pagamento (invio via `whatsapp_service` esistente, Meta Graph già pagato).
- Operatore singolo, non-dev, non rivede codice → affidabilità + semplicità > feature.
- Finestra Meta 24h: testo libero solo entro 24h dall'ultimo inbound cliente; oltre → template (FUORI SCOPO v1, si mostra solo banner).
- Local UI legge/scrive SOLO via backend Fly (mai DB diretto). Bind `127.0.0.1` only.

## Limite esplicito noto (no silent gap)

Il token CSRF effimero protegge dal **browser-CSRF** (altre pagine localhost). NON protegge da un **processo locale malevolo** che fa `curl` + scrape della pagina per estrarre il token. Per un single-operator sul proprio Mac (chi controlla la macchina ha già accesso) è rischio accettato. Documentato, non mascherato. (DeepSeek + Codex, sez. 5.)

---

## Sezione 1 — Architettura (panel ✅)

```
cliente WA ─► Webhook Meta (Fly, ESTESO)
               ├─[1 TX]─► inbound_webhooks (raw, ACK Meta solo DOPO insert durabile)
               │          + meta_inbox_messages (ledger)
               │          + wa_outbox (send-intent, SOLO se human_handling=false)
               │          human_handling check DENTRO la TX
               └─► ACK 200 (<3s) — non-200 SOLO se il raw insert fallisce

           wa_outbox_worker (Fly, loop ~3s) ─► genera testo bot ─► Graph send ─► update ledger.status
           replay_worker (Fly) ─► riprocessa inbound_webhooks non-processate (OBBLIGATORIO)

local :7791 (127.0.0.1 only, NO DB pool, token effimero + X-API-Key da Keychain)
   = THIN PROXY agli endpoint FastAPI /api/wa-inbox/*
   viewer.html: 2-col inbox + takeover + banner 24h
```

**3 unità isolate:** (1) persistenza Fly (3 tabelle + worker), (2) endpoint FastAPI autenticati, (3) local proxy + UI + .app.

**Fix panel integrati:** local NON tocca DB Fly (tutto via FastAPI); outbox pattern; idempotency_key generato dal client; API key in Keychain.

---

## Sezione 2 — Schema dati (panel ✅)

Migration numerata in `migrations_v2/` (tracked in `schema_migrations`).

### `meta_inbox_threads`
```sql
thread_id BIGSERIAL PK
counterpart_phone TEXT NOT NULL UNIQUE   -- e164 cliente
counterpart_name TEXT
human_handling BOOLEAN NOT NULL DEFAULT false   -- bot gate
handling_version INT NOT NULL DEFAULT 0          -- usato SOLO lato worker (non blocca takeover umano)
last_customer_at TIMESTAMPTZ    -- finestra 24h; aggiornato SOLO da inbound reali, via GREATEST(), MAI da status receipts
last_message_at TIMESTAMPTZ
created_at TIMESTAMPTZ DEFAULT now()
```

### `meta_inbox_messages` (ledger append-only)
```sql
id BIGSERIAL PK
thread_id BIGINT FK
meta_message_id TEXT          -- wamid; NULL per outbound finché non inviato
direction TEXT CHECK (direction IN ('inbound','outbound'))
sender_role TEXT CHECK (sender_role IN ('customer','bot','human'))
body TEXT
media_type TEXT, media_url TEXT
status TEXT CHECK (status IN ('received','queued','generating','sending','sent','delivered','read','failed'))
error TEXT
idempotency_key TEXT          -- client-supplied per human send
webhook_id BIGINT FK inbound_webhooks(id)
created_at TIMESTAMPTZ DEFAULT now(), sent_at TIMESTAMPTZ
-- dedup inbound:
CONSTRAINT uq_meta_msg UNIQUE (meta_message_id)  -- partial WHERE meta_message_id IS NOT NULL
-- dedup human send:
CONSTRAINT uq_idem UNIQUE (thread_id, idempotency_key)  -- partial WHERE idempotency_key IS NOT NULL
```

### `wa_outbox` (coda send-intent per il worker)
```sql
id BIGSERIAL PK
thread_id BIGINT FK
message_id BIGINT FK meta_inbox_messages(id)  UNIQUE   -- una ledger row non accodabile due volte
needs_generation BOOLEAN DEFAULT false   -- bot reply: testo generato dal worker, non nel webhook
status TEXT CHECK (status IN ('pending','generating','claimed','done','failed')) DEFAULT 'pending'
claim_token UUID, claimed_at TIMESTAMPTZ, claim_expires_at TIMESTAMPTZ   -- lease (anti worker-crash)
attempts INT DEFAULT 0, next_retry_at TIMESTAMPTZ DEFAULT now()
created_at TIMESTAMPTZ DEFAULT now()
```

### Indici (panel-required)
```sql
CREATE INDEX meta_inbox_threads_last_message_idx ON meta_inbox_threads (last_message_at DESC, thread_id DESC);
CREATE INDEX meta_inbox_messages_thread_created_idx ON meta_inbox_messages (thread_id, created_at DESC);
CREATE INDEX wa_outbox_pending_idx ON wa_outbox (next_retry_at, id) WHERE status = 'pending';
```

### Tabella per status-callback orfani (sez. 3)
```sql
-- orphan status receipts (read/delivered prima che il send sia committato)
CREATE TABLE wa_status_pending (
  meta_message_id TEXT PRIMARY KEY,
  status TEXT, error TEXT, received_at TIMESTAMPTZ DEFAULT now()
);
-- applicato al ledger appena la riga con quel wamid esiste
```

---

## Sezione 3 — Webhook + worker (panel ✅)

### Webhook (estende `whatsapp_chat.py`, SOLO per phone_number_id=1104946272705747)
1. Verifica HMAC (esiste). **INSERT durabile in `inbound_webhooks`** → solo allora **ACK 200**. Se il raw insert fallisce → **non-200** (Meta ritenta). Processing a valle può fallire → `inbound_webhooks` è **replay queue obbligatoria** (`processed_at`/`error`/`attempts`).
2. Branch su tipo payload:
   - **STATUS callback** (`statuses[]`): aggiorna `meta_inbox_messages.status` by `meta_message_id` (sent→delivered→read | failed+error). **MAI** toccare `last_customer_at`. Se wamid sconosciuto (race con commit send) → INSERT in `wa_status_pending`, applicato dopo.
   - **MESSAGE** (`messages[]`) in 1 TX:
     a. upsert thread; `last_customer_at = GREATEST(existing, meta_ts)` (solo qui).
     b. `INSERT ledger(inbound/customer/received, meta_message_id, webhook_id) ON CONFLICT(meta_message_id) DO NOTHING RETURNING id`.
     c. **SOLO se (b) ha dato riga nuova AND human_handling=false**: `INSERT ledger(outbound/bot/queued)` + `INSERT wa_outbox(needs_generation=true)`.
3. Generazione testo bot: NON nel webhook (lento) → `needs_generation` flag, il worker genera.
4. **Scope per phone_number_id**: tutta questa logica SOLO per il numero target; altri numeri/canali restano sul triage inline esistente.

### Worker (loop ~3s su Fly)
1. **Reclaim stale**: outbox `claimed` con `claim_expires_at < now()` → torna `pending` (lease/heartbeat, non reclaim cieco).
2. **Claim**: `SELECT ... FOR UPDATE SKIP LOCKED WHERE status='pending' AND next_retry_at<=now() LIMIT 1`.
3. Se `needs_generation`: **re-check human_handling** (può essere flippato dal takeover) → se ora true, ABORT+drop outbox. Stato `generating` separato da `sending`. Genera testo bot.
4. **24h window**: `now() - last_customer_at > 24h` → `status=failed, error='24h_window_closed'`.
5. **Send via Graph**. Success → `ledger.status=sent, meta_message_id=wamid, sent_at`; applica eventuale `wa_status_pending`. Fail HTTP → `attempts++, next_retry_at=backoff`; dopo N → `failed`.
6. Timeout Graph + LLM < 30s (sotto la lease 2min, anti doppio-invio).

### Takeover (da endpoint, sez. 4)
Flip `human_handling=true` → **cancella/sopprime le outbox `pending` del thread** (non solo re-check pre-send).

---

## Sezione 4 — Endpoint FastAPI + auth (panel ✅)

### Router `/api/wa-inbox/*` (NON in PUBLIC_ENDPOINTS)
- `GET /threads?limit=50&cursor=<ts>,<thread_id>` → keyset pagination `ORDER BY last_message_at DESC, thread_id DESC`.
- `GET /threads/{id}/messages?before=<id>&limit=50` → ledger ASC + stato thread (human_handling, last_customer_at, window_open).
- `POST /threads/{id}/send` `{text, idempotency_key (UUIDv4 client)}` → 24h-check request-time (409 `window_closed`); 1 TX: `INSERT ledger(outbound/human/queued, idempotency_key) ON CONFLICT(thread_id,idempotency_key) DO NOTHING RETURNING id`; se nuovo → `human_handling=true` + `wa_outbox`; ritorna `{message_id, status:'queued'}`. Idem-key già visto → ritorna message_id precedente (replay idempotente).
- `POST /threads/{id}/takeover` → `human_handling=true` (umano vince SEMPRE, no 409) + cancella outbox pending.
- `POST /threads/{id}/release` → `human_handling=false`.

### Auth (risolta divergenza panel)
- **Token dedicato** (least-privilege, NON l'admin `zantara-secret-2024`) aggiunto a `Settings.api_keys` (lista comma-separated già supportata dal middleware), inviato come **`X-API-Key` standard** → il middleware lo riconosce, niente 401-prima-della-dependency.
- ⚠️ **Da VERIFICARE in impl (Codex: "test non inspection")**: se `api_keys` NON supporta scoping per-route (tutte le chiavi pari potere), aggiungere una dependency su `/api/wa-inbox/*` che verifica *quale* chiave. **Test auth espliciti OBBLIGATORI**: 401 unauth, webhook resta public, solo la chiave wa-inbox passa.
- `handling_version`: usato SOLO lato worker (bot non invia se version cambiata); NON imposto al takeover umano.

---

## Sezione 5 — Local server + UI + .app (panel ✅)

### `apps/wa-meta-inbox/server.cjs`
- Bind `127.0.0.1:7791` ONLY.
- NO pg pool. Chiama `https://nuzantara-rag.fly.dev/api/wa-inbox/*` con `X-API-Key`.
- API key da **macOS Keychain** (`security find-generic-password -s wa-inbox-api-key -w`); fallback env var; **exit(1) fail-loud** se assente/locked + auth-probe a Fly allo startup.
- **Token CSRF effimero**: `crypto.randomUUID()` allo startup (in-memory, reset al restart, mai su disco), iniettato in `viewer.html`, validato su OGNI route mutation (`/send`, `/takeover`, `/release`) via header → fail-closed. (Origin/Referer da solo NON basta.)
- idempotency_key: generato nel browser (`crypto.randomUUID()`), server.cjs forwarda.

### `viewer.html` (single file, vanilla JS)
- 2-col: thread list (poll `/threads` ogni 5s) | conversazione (poll messages ogni 3s, **no-overlap guard + AbortController** per cancellare poll stale al thread-switch).
- reply box disabilitato + banner quando `window_open=false`.
- takeover/release per thread + badge bot/human.
- send: optimistic UI **solo come `pending`** (mai `delivered`); su rifiuto POST → `failed` immediato; riconcilia da ledger al poll.

### `WA Meta Inbox.app` + LaunchAgent
- Clona `WA Dashboard.app`, apre `http://127.0.0.1:7791/?token=<csrf>`.
- LaunchAgent `com.balizero.wa-meta-inbox.plist`: **label/port/log/plist path UNICI** (no collision con wa-dashboard-m1 :7790), absolute Node path, `WorkingDirectory`, `plutil -lint`, bootout/bootstrap idempotente, verifica con `launchctl print` + `lsof 127.0.0.1:7791`.

---

## Piano deploy/test (workflow Antonello)

1. Implementazione in worktree `.worktrees/backend-rag-wa-meta-inbox-2026-06-03` (branch `agent/nuzantara/backend-rag/wa-meta-inbox-2026-06-03`).
2. Test backend: auth `/api/wa-inbox/*` (401 unauth, scoping), webhook idempotency (ON CONFLICT), 24h window, outbox worker (claim/reclaim/race human_handling), status-callback orfani.
3. Se GREEN → merge → push → `fly deploy` (build context = repo root, vedi scar 503).
4. Smoke test prod: **prima takeover del thread** (no auto-reply bot), poi msg dall'altro numero di Antonello → +62 821-3465-159 → verifica appare in UI → reply da UI → verifica delivery (status sent→delivered).

## File toccati/creati

- `apps/backend-rag/backend/db/migrations_v2/NNN_wa_meta_inbox.sql` (NEW — 4 tabelle + indici)
- `apps/backend-rag/backend/app/routers/whatsapp_chat.py` (EXTEND — branch outbox scoped per phone_number_id)
- `apps/backend-rag/backend/app/routers/wa_inbox.py` (NEW — router /api/wa-inbox)
- `apps/backend-rag/backend/services/.../wa_outbox_worker.py` (NEW — worker loop)
- `apps/backend-rag/backend/app/setup/router_registration.py` (EXTEND — include wa_inbox)
- `apps/backend-rag/backend/app/core/config.py` (EXTEND — wa_inbox key in api_keys)
- `apps/wa-meta-inbox/{server.cjs,viewer.html,package.json}` (NEW)
- `WA Meta Inbox.app` + `com.balizero.wa-meta-inbox.plist` (NEW, infra non-repo)
- Test: `tests/.../test_wa_inbox_auth.py`, `test_wa_inbox_webhook.py`, `test_wa_outbox_worker.py`
