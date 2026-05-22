---
date: 2026-05-23
domain: operations
client_case: internal-tooling
sources: 12
panel: [claude-opus-4-7, gemini-3.1-pro, deepseek-v4-pro, codebase-audit]
status: DRAFT for Antonello review
---

# WA Team Inbox Webapp — Spec definitiva

> Local-only webapp per visualizzare tutta la messaggistica WhatsApp captured dai 9 account team Bali Zero, vedere il flow incoming→automation→action, e intervenire (reply, tag, escalate, assign).

## TL;DR (3 paragrafi)

**Cosa è**: una single-page Next.js dentro `apps/mouth` (route `/(workspace)/wa-inbox`) che consuma 3 router FastAPI **già esistenti** (`/api/omnichannel/threads`, `/api/wa/messages`, `/api/whatsapp/conversations`) e aggiunge **2 nuovi endpoint** (`/api/wa/ws` WebSocket realtime, `/api/wa/send` outbound POST). L'UI è 3-pane: lista thread (sinistra) — chat view (centro) — context CRM (destra), pattern Chatwoot/Whaticket battle-tested. Layer flow visualization (React Flow) come tab opzionale dentro la chat view.

**Cosa non è**: un WhatsApp Web clone, una piattaforma multi-tenant SaaS, un sistema che richiede deploy cloud. Single-tenant (1-3 operatori), zero telemetria esterna, tutto su Pro M4 48GB.

**Costo stimato**: ~1500 LOC frontend + ~400 LOC backend nuovo (WebSocket manager + send endpoint con idempotency). Reuse 80%+ stack esistente: backend router già scritti, `WaTimelineTab.tsx` come reference per chat bubble UI, `wa-mirror` bridge Baileys già running con 8/8 account live.

---

## 1. Stato dell'arte — cosa abbiamo già

### 1.1 Bridge Baileys (Node, `apps/wa-mirror/`)

- 9 LaunchAgent supervisato `com.balizero.wa-mirror-launcher` (fix shipped PR #822) — 8 account team RUNNING al momento della spec
- Cattura `messages.upsert` + media download → table `whatsapp_message_context` + media filesystem `~/wa-mirror-media/<jid>/`
- Telegram alert P0/P1 via `bridge/telegram.ts` per attention queue HIGH

### 1.2 Postgres schema (FLY-hosted, proxy locale `localhost:15432`)

```
whatsapp_message_context   16586 rows | 15MB | 16 indexes
  - id, baileys_message_id (unique)
  - direction (sent|received|inbound|outbound — schema mix, va unificato)
  - chat_type (direct|group), chat_jid, group_jid, group_subject_snapshot
  - sender_phone, sender_lid, sender_push_name_snapshot
  - team_member_phone, counterpart_phone, counterpart_lid
  - body, message_text (legacy duplicate — pick `body`)
  - media_type, media_mime, media_stored_path, ocr_result jsonb
  - attention_priority (HIGH|MEDIUM|LOW), attention_reason text[], attention_resolved_at
  - client_id, practice_id (CRM links, NULL = prospect)
  - raw_baileys_event jsonb (full Baileys payload)
  - message_date, created_at, updated_at

whatsapp_team_sessions     bridge connection state per account
whatsapp_contacts          contact dictionary cross-account
whatsapp_lid_phone_map     resolver LID→phone
whatsapp_session_history   storico sessioni
```

GIN trigram index `idx_wmc_message_text_trgm` già presente per FTS-like search.

### 1.3 Backend FastAPI (`apps/backend-rag`)

**Router già esistenti che useremo verbatim**:

- `/api/omnichannel/threads` (GET/PATCH) — list/update thread con filtri status, priority, assigned_to, channel, search
- `/api/omnichannel/threads/{id}` (GET) — dettaglio
- `/api/omnichannel/threads/{id}/messages` (POST) — **intervention reply** (già esiste!)
- `/api/omnichannel/threads/{id}/assign` (POST) — assignment
- `/api/omnichannel/threads/{id}/context` (GET) — CRM context (client, practice, history)
- `/api/omnichannel/stats` (GET) — dashboard counters
- `/api/wa/messages` (GET) — CRM-safe timeline allowlist, supporta filtri client_id, practice_id, prospect_only, attention_priority — 271 LOC, RBAC integrato
- `/api/whatsapp/conversations` (GET) — conversation list
- `/api/whatsapp/messages/{phone}` (GET) — per-phone history
- `/api/channel/health` (GET) — heartbeat 8 bridge

**Router da estendere**:

- `wa_mirror_messages.py` aggiungere endpoint `/api/wa/conversations` (unified inbox query, cross-account)

**Router NUOVI da creare** (≤400 LOC totale):

1. `wa_realtime.py` — `WebSocket /api/wa/ws` con `ConnectionManager` broadcast su `pg_notify` event
2. `wa_send.py` — `POST /api/wa/send` outbound con idempotency key

### 1.4 Frontend Next.js (`apps/mouth`)

- App Router 16 + React 19
- Tailwind + shadcn/ui style (dark theme già adottato in `WaTimelineTab`)
- `lib/api/whatsapp/whatsapp.types.ts` ha già i Pydantic-mirror types
- `WaTimelineTab.tsx` (297 LOC) è la reference per chat bubble + attention badge + media icon — riutilizzabile interamente

### 1.5 Bridge↔backend pipeline outbound (decisione tra Redis e HTTP)

Vedi §5.3.

---

## 2. Requisiti funzionali

| ID  | Requisito                                                                                                                                                                                  | Priorità |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------- |
| F1  | Vista unified inbox 3-pane: lista thread → chat view → context CRM                                                                                                                         | P0       |
| F2  | Filtri lista thread: per account team (8 chip), per attention_priority, per chat_type (DM/group), per assigned_to, per status (open/waiting/resolved), per date range, per text search FTS | P0       |
| F3  | Chat view: scroll bubble inbound/outbound time-ordered, media gallery inline (image/PDF/audio/document), OCR result expandable, group sender attribution                                   | P0       |
| F4  | Intervention: compose box + send (POST `/api/wa/send`), templates (3-5 quick replies pre-caricati), tag conversation, mark attention_resolved, escalate-to-human                           | P0       |
| F5  | Assignment: assegna thread a team member email (Adit, Surya, Ari, ecc.) — link a `assigned_to` colonna                                                                                     | P1       |
| F6  | CRM enrichment pane (destra): mostra `client_id`, `practice_id`, attivi visa/tax/property, ultime 5 interazioni cross-channel                                                              | P1       |
| F7  | Realtime stream: nuovi messaggi appaiono <500ms via WebSocket (no F5 polling)                                                                                                              | P0       |
| F8  | Flow visualization: tab opzionale che mostra DAG messaggio → automation (RAG response) → action (reply / escalate / tag)                                                                   | P2       |
| F9  | Operator action audit log: ogni send/tag/assign/escalate registrato in `whatsapp_operator_actions` (nuova table)                                                                           | P1       |
| F10 | Search FTS: full-text body + counterpart_phone + sender_push_name su 1.8M+ rows projected                                                                                                  | P0       |
| F11 | Media gallery globale: vista "tutte le immagini ricevute oggi" per scan rapido KYC                                                                                                         | P2       |

---

## 3. Repo open-source studied (top 5 ranked)

| #   | Repo                                                                         | Stars  | License  | Reusability                                                                                                                    | Note                                                                                                          |
| --- | ---------------------------------------------------------------------------- | ------ | -------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| 1   | [chatwoot/chatwoot](https://github.com/chatwoot/chatwoot)                    | ~20.5k | MIT      | LOW (stack Rails+Vue incompatibile, ma **pattern 3-pane**, **state machine status** + **assignment** sono il riferimento gold) | Studiare schema `conversations`, `messages`, `inbox_members`. NON forkare.                                    |
| 2   | [canove/whaticket-community](https://github.com/canove/whaticket-community)  | ~2.5k  | MIT      | MEDIUM (frontend React/Material UI riusabile come reference, backend Node/MySQL scartare)                                      | Buon esempio chat bubble UI + ticket lifecycle. Pattern "ticket" assimilabile a "thread" omnichannel.         |
| 3   | [evolution-api/evolution-api](https://github.com/EvolutionAPI/evolution-api) | ~3.8k  | MIT      | MEDIUM (Baileys multi-tenant gateway in Node, reference per refactor futuro `wa-mirror`)                                       | Architettura gateway HTTP attorno a Baileys con Redis Pub/Sub — interessante per il bridge outbound endpoint. |
| 4   | [typebot-io/typebot](https://github.com/typebot-io/typebot)                  | ~8.1k  | AGPL-3.0 | HIGH (canvas editor flow)                                                                                                      | Non per chat, ma per F8 flow visualization. Usa React Flow custom.                                            |
| 5   | [WhiskeySockets/Baileys](https://github.com/WhiskeySockets/Baileys)          | ~11.5k | MIT      | HIGH (è la nostra base)                                                                                                        | Examples folder ha multi-auth references.                                                                     |

Scartati: wapikit (focus bulk marketing), tercela (Bun-Vue incompatibile stack), wuzapi (Go vs Node), pedroslopez/whatsapp-web.js (Puppeteer heavy).

**Insight non ovvio**: nessun repo open-source implementa nativamente **threading cross-account** (lo stesso cliente che scrive a 3 numeri team viene mostrato come 3 thread separati). Nuzantara può essere prima a implementare contact-centric threading sfruttando `client_id` FK già presente.

---

## 4. Best practices research

### 4.1 Real-time delivery (3/3 LLM convergent)

**Decisione**: WebSocket via FastAPI `ConnectionManager` su `/api/wa/ws`.

- Inflow: 80 msg/min sustained, peak 400 msg/min = 6.7 msg/s → trivialmente sotto qualsiasi limite WebSocket
- Bidirezionale necessario per typing indicators, read receipts, operator presence
- Single-tier (browser ↔ FastAPI) — il bridge Node NON parla mai con il browser (RBAC/auth centralizzato in Python)

**Glue bridge → FastAPI realtime**: Postgres `LISTEN/NOTIFY` su `whatsapp_message_inserted` channel. Trigger PG già esistente per `events_outbox` family (cf. cicatrix P0-2 phase 2 — pattern già consolidato in Nuzantara). FastAPI listener pre-loaded come parte di `app.state.event_bus`.

```python
# new — apps/backend-rag/backend/app/routers/wa_realtime.py (estimato 120 LOC)
from fastapi import WebSocket, WebSocketDisconnect, Depends

class WaConnectionManager:
    def __init__(self): self.active: dict[str, list[WebSocket]] = {}
    async def connect(self, ws, user_email): ...
    async def broadcast_message(self, msg_payload): ...

@router.websocket("/ws")
async def wa_ws(ws: WebSocket, user=Depends(get_current_user)):
    await mgr.connect(ws, user["email"])
    try:
        async for _ in ws.iter_text(): pass  # client → server: typing, presence
    except WebSocketDisconnect:
        mgr.disconnect(ws)
```

### 4.2 Database query unified inbox (DeepSeek convergent)

`DISTINCT ON (counterpart_phone)` window function per "latest message per conversation":

```sql
SELECT DISTINCT ON (counterpart_phone, team_member_phone)
  counterpart_phone, team_member_phone, body, message_date,
  attention_priority, client_id, practice_id
FROM whatsapp_message_context
WHERE message_date > NOW() - INTERVAL '30 days'
ORDER BY counterpart_phone, team_member_phone, message_date DESC
LIMIT 200;
```

Index supportato: `idx_wmc_counterpart_date` esistente. Query <50ms a 1.8M rows.

### 4.3 Bridge↔backend outbound (Gemini vs DeepSeek divergent)

**Gemini propone**: Redis Pub/Sub (`wa_outbound` channel) — Bridge SUBSCRIBE, FastAPI PUBLISH.
**DeepSeek propone**: HTTP POST diretto bridge espone `POST /bridge/send`.

**Decisione raccomandata**: **HTTP POST diretto + idempotency key**, per 3 motivi empirici:

1. Redis è OVERHEAD non necessario per single-tenant local (Redis è già attivo su 127.0.0.1:6379 per altri usi, ma aggiunge un async pubsub layer che è soft fail-prone)
2. HTTP retry semantics sono triviali con `httpx.AsyncClient(timeout=5)` + idempotency
3. Path latency: localhost HTTP ~1-3ms vs Redis pubsub ~0.5ms — irrilevante a 6.7msg/s
4. Bridge crash recovery via launchd (già live, cicatrix odierna PR #822 confermata)

```python
# new — apps/backend-rag/backend/app/routers/wa_send.py (estimato 200 LOC)
@router.post("/send", response_model=SendResponse)
async def send_wa(
    payload: SendRequest,
    x_idempotency_key: str = Header(),
    user = Depends(get_current_user),
    db = Depends(get_database_pool),
):
    # 1. check idempotency (table wa_outbound_idempotency unique (key,user_email))
    cached = await idem_get(db, x_idempotency_key, user["email"])
    if cached: return cached

    # 2. RBAC check: user can send from team_member_phone?
    if not await can_send_from(db, user, payload.team_member_phone):
        raise HTTPException(403)

    # 3. insert outbound row with status='pending'
    msg_id = await insert_outbound(db, payload, user["email"])

    # 4. POST to bridge
    async with httpx.AsyncClient(timeout=5) as c:
        resp = await c.post(f"http://localhost:3001/send", json=payload.dict())
        resp.raise_for_status()
    baileys_id = resp.json()["baileys_message_id"]

    # 5. update outbound row status='sent', baileys_message_id=...
    await mark_sent(db, msg_id, baileys_id)

    # 6. cache idempotency
    await idem_put(db, x_idempotency_key, user["email"], {"msg_id": msg_id, "baileys_id": baileys_id})
    return SendResponse(msg_id=msg_id, baileys_message_id=baileys_id)
```

**Bridge side** (nuovo file `apps/wa-mirror/bridge/http_server.ts` ~150 LOC):

- Espone `POST /send` su `localhost:3001`
- Riceve `{team_member_phone, counterpart_phone, body, media?}` → chiama `sock.sendMessage()` Baileys
- Ritorna `{baileys_message_id, status}`

### 4.4 Search FTS (3/3 convergent)

PostgreSQL FTS `to_tsvector` + GIN index. Già esiste `idx_wmc_message_text_trgm` per LIKE pattern; aggiungiamo GIN tsvector per phrase search:

```sql
-- migration NEW
CREATE INDEX idx_wmc_body_fts ON whatsapp_message_context
  USING GIN (to_tsvector('simple', COALESCE(body, message_text)));
```

`simple` config (non `english` né `indonesian`) perché i messaggi sono mistilingue (IT/EN/ID/Bahasa).

### 4.5 Media handling (3/3 convergent)

FastAPI `FileResponse` authenticated, mai static mount. Endpoint `/api/wa/media/{message_id}` (≤80 LOC):

```python
@router.get("/media/{message_id}")
async def serve_media(message_id: int, user = Depends(get_current_user), db = ...):
    row = await db.fetchrow("SELECT media_stored_path, media_mime, client_id FROM whatsapp_message_context WHERE id=$1", message_id)
    if not row: raise HTTPException(404)
    # RBAC: user can see this client?
    if not await can_view_message(user, row): raise HTTPException(403)
    return FileResponse(row["media_stored_path"], media_type=row["media_mime"])
```

### 4.6 Frontend state mgmt (3/3 convergent)

- **Zustand** per UI state ephemeral (chat aperto, compose draft, presence operator)
- **TanStack Query** (`useInfiniteQuery`) per server state + pagination + cache invalidation
- **react-virtuoso** per virtualized chat list (1.8M rows projection)
- **@xyflow/react** per F8 flow visualization

### 4.7 Auth (Gemini + DeepSeek + my codebase audit convergent)

Riusare l'auth esistente Nuzantara: cookie session + `get_current_user` dependency già usata in tutti i router citati. RBAC via `can_view_all_clients` + nuovo decorator `can_send_from(team_member_phone)` (verifica che user sia mapped a quel numero team, da `team_member_email` table).

### 4.8 Audit log operator actions (DeepSeek unique)

Nuova table:

```sql
-- migration NEW
CREATE TABLE whatsapp_operator_actions (
  id BIGSERIAL PRIMARY KEY,
  user_email VARCHAR(255) NOT NULL,
  action_type VARCHAR(50) NOT NULL, -- send|tag|assign|escalate|resolve_attention
  target_message_id BIGINT REFERENCES whatsapp_message_context(id),
  target_thread_id UUID,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_woa_user_created ON whatsapp_operator_actions(user_email, created_at DESC);
```

---

## 5. Architettura proposta

### 5.1 Diagramma alto livello

```
[ Browser Chrome on Pro ]
         │ wss://localhost:8000/api/wa/ws  +  https://localhost:8000/api/...
         ▼
┌────────────────────────────┐
│ Next.js apps/mouth         │  ← Server Components per layout + RSC props
│ /(workspace)/wa-inbox      │     Client Components per chat (Zustand+TanStack)
│ - ThreadList (left pane)   │
│ - ChatView (center)        │     Realtime: native WebSocket → useStore
│ - ContextPane (right)      │
│ - FlowGraph (tab) xyflow   │
└────────────────────────────┘
         │ FastAPI 8000
         ▼
┌────────────────────────────────────────────────────────────┐
│ apps/backend-rag (FastAPI)                                 │
│ /api/omnichannel/* (EXISTING)                              │
│ /api/wa/messages    (EXISTING - 271 LOC)                   │
│ /api/wa/conversations (NEW - cross-account unified)        │
│ /api/wa/send        (NEW - intervention POST + idempotency)│
│ /api/wa/ws          (NEW - WebSocket realtime)             │
│ /api/wa/media/{id}  (NEW - auth proxy media)               │
│                                                            │
│ Background: PG LISTEN whatsapp_message_inserted            │
│ → ConnectionManager.broadcast()                            │
└────────────────────────────────────────────────────────────┘
         │ asyncpg pool                  │ httpx.AsyncClient
         ▼                               ▼
┌──────────────────────┐       ┌────────────────────────────┐
│ Postgres (Fly proxy) │       │ wa-mirror bridge (Node)    │
│ whatsapp_message_*   │       │ localhost:3001/send (NEW)  │
│ + TRIGGER pg_notify  │ ◄─── │ apps/wa-mirror/bridge/     │
│ + GIN tsvector FTS   │       │ http_server.ts (NEW)       │
│ + whatsapp_operator_ │       │ → Baileys sock.sendMessage │
│   actions (NEW)      │       └────────────────────────────┘
│ + wa_outbound_idem   │
│   potency (NEW)      │
└──────────────────────┘
```

### 5.2 Tech stack consolidato

| Layer                | Choice                                 | Rationale                             |
| -------------------- | -------------------------------------- | ------------------------------------- |
| Frontend framework   | Next.js 16 App Router (existing)       | Reuse `apps/mouth`                    |
| UI                   | Tailwind + shadcn/ui                   | Already in WaTimelineTab              |
| Chat virtualization  | react-virtuoso                         | DeepSeek-recommended, 1.8M rows       |
| State (UI ephemeral) | Zustand                                | Lightweight, 3/3 LLM convergent       |
| State (server)       | @tanstack/react-query v5               | Already in Nuzantara                  |
| Realtime             | native WebSocket API + custom store    | No socket.io needed                   |
| Flow viz             | @xyflow/react                          | Typebot reference, 3/3 convergent     |
| Backend framework    | FastAPI (existing)                     | Reuse `apps/backend-rag`              |
| DB                   | Postgres (existing Fly proxy)          | Already 16 indexes optimal            |
| FTS                  | PG `to_tsvector('simple', body)` + GIN | DeepSeek validated 1.8M rows <10ms    |
| Realtime glue        | PG LISTEN/NOTIFY                       | Already adopted (cf. cicatrix P0-2)   |
| Bridge outbound      | HTTP POST localhost:3001 + idempotency | DeepSeek validated, no Redis overhead |
| Auth                 | Existing cookie session + RBAC         | Reuse `get_current_user`              |
| Media                | FastAPI `FileResponse` + auth          | 3/3 convergent                        |
| Audit log            | New table `whatsapp_operator_actions`  | DeepSeek-recommended                  |

### 5.3 Decisione architetturale chiave (cross-LLM divergence resolved)

**Q**: Bridge↔backend usa Redis Pub/Sub o HTTP POST?
**A**: HTTP POST.
**Why**: Single-tenant, no horizontal scale needed, ~6.7msg/s saturazione lontana. Riduce moving parts. HTTP retry semantics più chiaro per idempotency. Redis aggiunge solo overhead operazionale (cron monitoring, persistence config). Se in futuro serve fan-out (es. multi-bridge per redundancy) si migra a Redis.

---

## 6. Schema PG nuove tabelle

```sql
-- migration 192_wa_inbox_idempotency_audit.sql

CREATE TABLE IF NOT EXISTS wa_outbound_idempotency (
  idempotency_key VARCHAR(64) NOT NULL,
  user_email VARCHAR(255) NOT NULL,
  response_payload JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '24 hours',
  PRIMARY KEY (idempotency_key, user_email)
);
CREATE INDEX idx_woi_expires ON wa_outbound_idempotency(expires_at);

CREATE TABLE IF NOT EXISTS whatsapp_operator_actions (
  id BIGSERIAL PRIMARY KEY,
  user_email VARCHAR(255) NOT NULL,
  action_type VARCHAR(50) NOT NULL CHECK (action_type IN ('send','tag','assign','escalate','resolve_attention','add_note')),
  target_message_id BIGINT REFERENCES whatsapp_message_context(id),
  target_thread_id UUID,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_woa_user_created ON whatsapp_operator_actions(user_email, created_at DESC);
CREATE INDEX idx_woa_target_msg ON whatsapp_operator_actions(target_message_id) WHERE target_message_id IS NOT NULL;

-- FTS index su body (simple config = no language stemming, multilingual safe)
CREATE INDEX IF NOT EXISTS idx_wmc_body_fts ON whatsapp_message_context
  USING GIN (to_tsvector('simple', COALESCE(body, message_text, '')));

-- pg_notify trigger
CREATE OR REPLACE FUNCTION notify_wa_message_inserted() RETURNS TRIGGER AS $$
BEGIN
  PERFORM pg_notify('whatsapp_message_inserted', json_build_object(
    'id', NEW.id,
    'direction', NEW.direction,
    'team_member_phone', NEW.team_member_phone,
    'counterpart_phone', NEW.counterpart_phone,
    'chat_type', NEW.chat_type,
    'group_jid', NEW.group_jid,
    'attention_priority', NEW.attention_priority,
    'message_date', NEW.message_date
  )::text);
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_wa_message_notify ON whatsapp_message_context;
CREATE TRIGGER trg_wa_message_notify
  AFTER INSERT ON whatsapp_message_context
  FOR EACH ROW EXECUTE FUNCTION notify_wa_message_inserted();
```

---

## 7. Frontend struttura file

```
apps/mouth/src/app/(workspace)/wa-inbox/
├── page.tsx                    # Server Component, prefetch threads + permissions
├── layout.tsx                  # 3-pane CSS grid
├── _components/
│   ├── ThreadList.tsx          # Left: virtualized list, filters chip, search
│   ├── ChatView.tsx            # Center: react-virtuoso chat bubbles + compose
│   ├── ContextPane.tsx         # Right: CRM enrichment + assigned_to + tags
│   ├── ComposeBox.tsx          # Bottom of ChatView: textarea + templates + send
│   ├── MessageBubble.tsx       # Single message UI (reuse WaTimelineTab patterns)
│   ├── MediaPreview.tsx        # Image / PDF / audio inline
│   ├── AttentionBadge.tsx      # Priority pill HIGH/MEDIUM/LOW (reuse existing)
│   ├── FlowGraphTab.tsx        # xyflow visualization (F8, P2)
│   └── stores/
│       ├── activeThread.ts     # Zustand: current thread_id, draft, presence
│       └── operatorActions.ts  # Zustand: tag/assign/escalate optimistic UI
├── _hooks/
│   ├── useWaWebSocket.ts       # native WS wrapper + reconnect
│   ├── useThreads.ts           # useInfiniteQuery wrapper
│   ├── useMessages.ts          # useInfiniteQuery per phone
│   └── useSendMessage.ts       # useMutation + idempotency key generation
└── _lib/
    ├── api.ts                  # axios instance scoped /api/wa /api/omnichannel
    └── types.ts                # extends @/lib/api/whatsapp/whatsapp.types.ts
```

Tot estimato: ~1500 LOC frontend, ~400 LOC backend nuovo.

---

## 8. Roadmap implementativa (4 milestones)

| M                                       | Scope                                                                                                                                                                                                                                        | LOC               | Days | Dependencies |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- | ---- | ------------ |
| **M1 — Realtime + outbound foundation** | Migration 192 (idempotency + audit + tsvector + pg_notify trigger) + `wa_realtime.py` (WebSocket + ConnectionManager) + `wa_send.py` (POST /send + idempotency) + `apps/wa-mirror/bridge/http_server.ts` (Baileys sendMessage HTTP endpoint) | ~700 backend      | 1.5d | nessuna      |
| **M2 — Unified inbox MVP**              | `wa-inbox/page.tsx` + 3-pane layout + `ThreadList` + `ChatView` (read-only) + `useWaWebSocket` + integration con `/api/omnichannel/threads`                                                                                                  | ~600 fe           | 1.5d | M1           |
| **M3 — Intervention + assignments**     | `ComposeBox` + `useSendMessage` + `ContextPane` (CRM) + tag/assign UI + `MediaPreview` (image/PDF) + operator action audit                                                                                                                   | ~500 fe + ~100 be | 1.5d | M2           |
| **M4 — Search FTS + Flow viz**          | FTS endpoint + filter bar + `FlowGraphTab` xyflow + audio player + group sender attribution + media gallery                                                                                                                                  | ~400 fe + ~50 be  | 1.5d | M3           |

**Totale estimato**: ~2350 LOC nuovo + ~6 giorni dev solo. Riuso ~70% codebase esistente.

---

## 9. Rischi + mitigazioni

| #   | Rischio                                                                                     | Severità | Mitigazione                                                                                                                                                            |
| --- | ------------------------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R1  | Bridge crash → outbound POST `/send` fallisce → UI mostra errore ma idempotency già scritta | HIGH     | Idempotency key con TTL 24h + retry policy frontend (3 retry, exponential backoff). Status `pending` in DB visibile in UI come spinner.                                |
| R2  | History sync di Baileys floodding PG su nuovo onboard account                               | MEDIUM   | Filtrare `messaging-history.set` event nel bridge — già implementato in `bridge/filters.ts`.                                                                           |
| R3  | Memory leak Baileys 8 account → bridge OOM                                                  | MEDIUM   | Cron graceful restart 04:00 WITA via launchd (esiste già `com.balizero.wa-mirror-launcher` con KeepAlive). Considerare `max_memory_restart` style.                     |
| R4  | PG notify saturation a 400msg/min peak con 3 operatori = 1200 broadcast/min                 | LOW      | Test load: PG notify gestisce 100k+ msg/s. 1200/min trivial.                                                                                                           |
| R5  | Single point of failure: Pro crash → tutto down                                             | HIGH     | Out of scope per ora (single-machine constraint). Backup PG già su Tigris (cron). Operator può continuare manualmente da WhatsApp Web durante outage.                  |
| R6  | Operator manda outbound mentre AI risponde (race)                                           | MEDIUM   | Lock conversation: `wa_conversation_locks` table con timestamp + user_email. AI agent check lock prima di send.                                                        |
| R7  | Cross-account threading (cliente con 3 team contacts) UX confusion                          | MEDIUM   | Implementare merge solo se `client_id` matched. Vista default = separated thread per (counterpart_phone, team_member_phone). Vista opzionale "Merge by client" toggle. |
| R8  | Group chat overload: 32 group con N members each = rumore                                   | MEDIUM   | Filtri default escludono `chat_type=group`. Tab dedicata "Gruppi" con sender attribution. Group event types (join/leave/picture) collapse di default.                  |
| R9  | Media filesystem grow unbounded                                                             | MEDIUM   | Cron lifecycle: cancella media >180gg salvo `media_kyc_tagged=true`. Out of scope M1-M4, ticket separato.                                                              |
| R10 | WebSocket reconnect on laptop sleep wake                                                    | LOW      | useWaWebSocket hook con auto-reconnect + last_seen_message_id replay via `GET /api/wa/messages?since=<id>`                                                             |

---

## 10. Open questions (decisione Antonello richiesta)

1. **Cross-account threading**: vista default mergea i messaggi se `client_id` matched, o tiene separated? _Raccomandazione_: separato default + toggle "Merge by client".
2. **Group chat scope**: includere group messages nella inbox principale, o tab separata? _Raccomandazione_: tab separata.
3. **Operator presence**: mostrare quale operatore sta scrivendo dove? _Raccomandazione_: M3 con WebSocket broadcast (typing indicator).
4. **AI auto-reply hooks**: integriamo già con il LangGraph RAG esistente? Possibile mostrare "AI suggested reply" sopra compose box, operatore accetta/modifica/scarta. _Raccomandazione_: M5 (future), out of M1-M4 scope per evitare scope creep.
5. **Mobile-friendly responsive**: Sahira potrebbe usare da tablet. _Raccomandazione_: M3 con CSS responsive — 3-pane collapse a 1-pane su <1024px.
6. **Multi-language**: UI in italiano o inglese? Bali Zero team è multilingua (Adit/Ari/Sahira IT/ID, Antonello IT). _Raccomandazione_: italiano per gli operatori (riusa il pattern `apps/mouth` esistente).
7. **Outbound rate limit**: limite send/min per team*member_phone? WA Business ha hard limit ~1msg/sec per number. \_Raccomandazione*: backend enforce 0.5 msg/s per team_member_phone via token bucket.

---

## 11. Devils-advocate gate (pending)

PRIMA dell'approvazione finale Antonello, eseguire devils-advocate (DeepSeek reasoning_effort=high) su questa spec per cercare:

- Hidden assumption (es. "PG LISTEN/NOTIFY è gratis" — verificare wakeup cost)
- Missing edge case (es. operator quit mid-send, bridge restart mid-broadcast)
- Performance miscalculation (es. virtualized list con react-virtuoso a 1.8M rows ha edge case?)
- Security flaw (es. cookie session via WSS senza CSRF token su mutations)
- Schema regression (es. nuova trigger su `whatsapp_message_context` rallenta INSERT in bridge — measure pre-deploy)

---

## 12. Sources

- Gemini 3.1 Pro long-context research output: `/tmp/gemini_wa_research_output.md` (12KB, 10 repo + arch + tech + risks)
- DeepSeek V4 Pro reasoning_effort=high output: `/tmp/deepseek_wa_research_output.md` (13KB, 10 patterns + numerical validation)
- Codebase audit empirical:
  - `apps/backend-rag/backend/app/routers/{omnichannel,wa_mirror_messages,whatsapp_conversations}.py`
  - `apps/mouth/src/app/(workspace)/clients/[id]/components/WaTimelineTab.tsx`
  - PG schema audit on Fly nuzantara-rag via asyncpg (16586 rows snapshot)
- Repo references:
  - https://github.com/chatwoot/chatwoot
  - https://github.com/canove/whaticket-community
  - https://github.com/EvolutionAPI/evolution-api
  - https://github.com/typebot-io/typebot
  - https://github.com/WhiskeySockets/Baileys

---

## Status

**DRAFT** — pending review Antonello. Su `y`:

1. Devils-advocate gate (DeepSeek)
2. Spec → research/operations/specs/ (commit branch dedicato)
3. M1 implementation start
