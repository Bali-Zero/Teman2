---
date: 2026-05-23
revised: 2026-05-23 (v2 post deep-researcher panel)
domain: operations
client_case: internal-tooling
sources: 26
panel:
  [
    claude-opus-4-7,
    gemini-3.1-pro,
    deepseek-v4-pro,
    codebase-audit,
    deep-researcher-agent,
  ]
status: DRAFT for Antonello review — UU PDP gating risk identified
companion: research/operations/2026-05-23-wa-mirror-dashboard-discovery.md
---

# WA Team Inbox Webapp — Spec definitiva (v2)

> Local-only webapp per visualizzare tutta la messaggistica WhatsApp captured dai 9 account team Bali Zero, vedere il flow incoming→automation→action, e intervenire (reply, tag, escalate, assign).

## ⚠️ GATING RISK — leggere PRIMA di approvare

**UU PDP 27/2022** (Indonesia Personal Data Protection Law, effettiva Oct 2024, transition 2 anni). Wa-mirror cattura messaggi su account WhatsApp personali del team con **prospects non-clienti** (counterpart che hanno scritto al numero team senza sapere della cattura centralizzata). Il passaggio da "passive logging" a **active centralized reply** introduce esposizione legale aggiuntiva. **MVP v1 = read-only Admin-only finché legal-counsel firma off su**: (a) prospect message retention basis, (b) centralized reply lawful basis, (c) data subject rights surface (deletion/access on request). Send capability = **v2** post sign-off.

## Cambiamenti vs v1

| #   | Topic                  | v1 (mia spec iniziale)                                         | v2 (post deep-researcher panel)                        | Driver                                                                                                                                                   |
| --- | ---------------------- | -------------------------------------------------------------- | ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | App location           | `apps/mouth/(workspace)/wa-inbox`                              | **nuova `apps/wa-dashboard/`**                         | Separation of concerns (mouth è public-facing marketing). Worktree contamination risk DeepSeek R2 ~30% su 2-3 settimane build inside existing app        |
| 2   | Realtime transport     | WebSocket FastAPI + PG LISTEN/NOTIFY                           | **SSE (Server-Sent Events) + PG LISTEN/NOTIFY**        | Throughput 0.88 msg/s sustained, 2.67 msg/s peak — sotto-soglia per WebSocket complessità. SSE built-in reconnect, HTTP/2 multiplexes free, no Socket.io |
| 3   | Outbound rate limit    | idempotency key only                                           | **idempotency + 10-30s jittered cooldown per account** | WA-AKG empirical anti-ban pattern. Baileys non ufficiale, burst send → ban WA. UI countdown 15s default                                                  |
| 4   | Top candidates studied | 5 repos (Chatwoot, Whaticket, Evolution API, Typebot, Baileys) | **14 repos + 3 UI libs**                               | Deep-researcher panel ha aggiunto WA-AKG (top 1 per code-lift), Evolution Manager v2, MultiWA (flow builder reference), Tercela (schema reference)       |
| 5   | Chat UI lib            | react-virtuoso + bubble custom                                 | **@chatscope/chat-ui-kit-react**                       | MIT, MessageList/Message/ChatContainer pre-built — saves ~2 settimane                                                                                    |
| 6   | Legal gating           | nessuno                                                        | **UU PDP 27/2022 counsel sign-off MVP-blocker**        | Opus self-redteam                                                                                                                                        |

## TL;DR (3 paragrafi)

**Cosa è**: nuova app Next.js 16 `apps/wa-dashboard/` (NON dentro `apps/mouth`) che consuma router FastAPI **già esistenti** (`/api/omnichannel/threads`, `/api/wa/messages`, `/api/whatsapp/conversations`) e aggiunge endpoint nuovi: `/api/v1/wa-dashboard/stream` (SSE realtime), `/api/v1/wa-dashboard/send` (outbound POST con jittered rate-limit). UI 3-pane: lista thread (sinistra) — chat view via `@chatscope/chat-ui-kit-react` (centro) — context CRM (destra). Flow visualization (React Flow / xyflow) come tab dentro la chat view. wa-mirror resta bridge headless puro.

**Cosa non è**: un WhatsApp Web clone, una piattaforma multi-tenant SaaS, un sistema che richiede deploy cloud, un reply bot autonomo (operatore sempre nel loop). Single-tenant (1-3 operatori), zero telemetria esterna, tutto su Pro M4 48GB localhost. V1 MVP read-only finché UU PDP counsel sign-off.

**Costo stimato**: ~1500 LOC frontend + ~500 LOC backend nuovo (SSE streaming + send endpoint con rate limiter + outbound queue worker) + ~150 LOC bridge wa-mirror modifications (v2 send capability, gated). Reuse 80%+ stack esistente: 6 endpoint omnichannel già implementati, `WaTimelineTab.tsx` 297 LOC come reference UI, schema PG con 16 indexes pronti, EventBus PG-NOTIFY pattern già rodato (migration 144/146).

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

## 3. Repo open-source studied (top 5 dal panel deep-researcher, 14 totali)

Panel completo: 14 GitHub repos + 3 UI pattern libs. Ranking convergente DeepSeek (MHI + stack-overlap) + Gemini (code-lift fit). Top 5:

| Rank | Repo                                                                                                           | MHI  | Stack overlap | Code-lift fit                                                                                                                       | Verdetto                                                                                        |
| ---- | -------------------------------------------------------------------------------------------------------------- | ---- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 1    | **[mrifqidaffaaditya/WA-AKG](https://github.com/mrifqidaffaaditya/WA-AKG)** (19★, MIT)                         | 1.09 | 5/10          | **HIGH** — Next.js 15 + Baileys native + role-based SUPERADMIN/OWNER/STAFF maps to Admin/Team                                       | **Lift chat composer + multi-session switcher + anti-ban delay 10-30s empirical pattern**       |
| 2    | **[EvolutionAPI/evolution-manager-v2](https://github.com/EvolutionAPI/evolution-manager-v2)** (4★, Apache 2.0) | 0.91 | 6/10          | MEDIUM-HIGH — React 18 + Vite + Radix UI + Tailwind + React Query + React Hook Form + Zod                                           | Lift dashboard chrome, Radix intervention modals, i18n architecture                             |
| 3    | **[ribato22/MultiWA](https://github.com/ribato22/MultiWA)** (24★, MIT)                                         | 1.12 | 7/10          | MEDIUM — Next.js 14 admin + **visual flow builder** + plugin system                                                                 | Reference unico per visual flow builder pattern (msg→automation→action). Skip NestJS backend    |
| 4    | **[chatwoot/chatwoot](https://github.com/chatwoot/chatwoot)** (29.6k★, MIT)                                    | 2.04 | 7/10          | LOW per code, HIGH per architettura — Rails+Vue incompatibile, ma `ContactInbox` polymorphic è gold-standard                        | Studiare ContactInbox abstraction per cross-account contact unification. NON forkare            |
| 5    | **[tags-dev/tercela](https://github.com/tags-dev/tercela)** (~200★, MIT)                                       | 1.01 | 8/10          | MEDIUM — Hono+Bun+Nuxt 4 incompatibile, ma PostgreSQL+Drizzle schema (auth/channels/contacts/inbox/config/storage) ben normalizzato | Reference per schema normalization se sviluppiamo schema separato da `whatsapp_message_context` |

**Esplicitamente NON raccomandati**:

- **EvolutionAPI/evolution-api** (8.4k★, Apache 2.0): NestJS+Fastify+Prisma+RabbitMQ+Kafka+SQS+NATS+Pusher+Socket.io+S3 — overkill single-box, fragmenta monolite FastAPI
- **devlikeapro/waha** (6.6k★): multi-session sotto paywall "Plus"
- **wppconnect-team/wppconnect-frontend** (238★, ARCHIVED Apr 2024): code rot risk
- **wppconnect-team/wppconnect-server** (1k★): Puppeteer-based, sostituisce wa-mirror invece di complementare
- **kopigreenx/zete-whatsapp-dashboard**: PHP/Laravel — language mismatch
- **mohit2777 multi-accounts dashboard** (1★): vanilla JS hobby-grade
- **rmyndharis/OpenWA**: opaque feature set, low maintenance signal

**UI pattern libs aggiuntive** (vincenti del panel, non repository fork):

- **[chatscope/chat-ui-kit-react](https://github.com/chatscope/chat-ui-kit-react)** (MIT) — MessageList, Message, ChatContainer, MessageInput pre-built. **Salva ~2 settimane** vs custom flexbox bubble layout. **Adottato per la chat UI principale.**
- **[xyflow/react-flow](https://github.com/xyflow/react-flow)** (MIT) — sole open-source option per flow viz. Adottato per F8.
- **[assistant-ui/assistant-ui](https://github.com/assistant-ui/assistant-ui)** — TS+React AI chat primitives. Reference per AI-suggested-reply pattern (M5 future).

**Insight non ovvio**: nessun repo open-source implementa nativamente **threading cross-account** (lo stesso cliente che scrive a 3 numeri team viene mostrato come 3 thread separati). Nuzantara può essere prima a implementare contact-centric threading sfruttando `client_id` FK già presente. Chatwoot ContactInbox è il pattern più vicino ma è cross-CHANNEL (email+IG+WA), non cross-account same-channel.

---

## 4. Best practices research

### 4.1 Real-time delivery — SSE + PG LISTEN/NOTIFY (v2 revisione)

**Decisione**: **SSE** (Server-Sent Events) per backend→browser. **PG LISTEN/NOTIFY** per wa-mirror→backend. **Plain HTTP POST** per browser→backend write path.

**Throughput math** (DeepSeek V4 Pro):

- Sustained: 8 account × 33 msg/5min midpoint = 264/5min = **0.88 msg/s** = ~3000 msg/h
- Peak: 8 × 50/5min sustained-high = **1.33 msg/s**, true burst peak **2.67 msg/s**
- Audience: 18 concurrent viewers max realistico (3-6 typical)

| Transport | Bytes/s per listener peak     | Total (18 lst)  | Latency       | Note                                                                                 |
| --------- | ----------------------------- | --------------- | ------------- | ------------------------------------------------------------------------------------ |
| WebSocket | 5.34                          | 96.1 B/s        | <50ms         | Stateful, heartbeat manuale, reconnect logic, session sticky                         |
| **SSE**   | 13.35                         | 240.3 B/s       | <100ms        | **Auto-reconnect built-in, HTTP/2 multiplex gratis, EventSource API browser nativa** |
| PG NOTIFY | asyncpg >5000 notif/s ceiling | 2.7×18 = 48.6/s | <10ms same-DB | Pattern già rodato in EventBus phase-1/2                                             |

Tutti i transport sono ordini di magnitudine sotto limiti hardware. **Scelta = operational complexity, NON throughput**. SSE vince per:

1. Browser EventSource gestisce reconnect automatico (laptop sleep/wake, network blip)
2. HTTP/2 multiplexing — niente porta extra, niente upgrade handshake
3. No dipendenze nuove (no socket.io, no ws lib)
4. Read-path only — write path è plain POST, separato (vedi §4.3)
5. PG LISTEN/NOTIFY è **same-DB**, NON same-machine: wa-mirror su Mini-Pro2 + backend su Pro/Fly entrambi connettono allo stesso PG → notify cross-machine via shared DB (Tailscale 62ms non in SSE delivery path, solo nel PG-write di wa-mirror già accettato).

**Glue stack**:

1. **wa-mirror → backend** (PG NOTIFY): `apps/wa-mirror/bridge/pg.ts` aggiunge `pg_notify('wa_message_inserted', '{message_id, team_member_phone, counterpart_phone, chat_type}'::text)` post-INSERT. Payload pointer-only (sotto 8KB hard limit PG NOTIFY).
2. **backend listener**: FastAPI background task in `apps/backend-rag/backend/app/main.py` lifespan: asyncpg `add_listener('wa_message_inserted', ...)` → broadcast a `WaSseManager`.
3. **backend → browser** (SSE): endpoint `GET /api/v1/wa-dashboard/stream` returns `StreamingResponse` con `Content-Type: text/event-stream`. Filtraggio RBAC server-side prima del forward.
4. **browser → backend** (write): `POST /api/v1/wa-dashboard/{phone}/send` plain HTTP. Backend valida RBAC + idempotency key + accoda in `wa_dashboard_outbound_queue` con `scheduled_for = NOW() + jitter(10-30s)`. UI reflette outbound nello stesso SSE stream dopo wa-mirror confirma send.

```python
# new — apps/backend-rag/backend/app/routers/wa_dashboard_stream.py (~150 LOC)
import asyncio, json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from backend.app.dependencies import get_current_user
from backend.app.deps.crm_access import can_view_all_clients

router = APIRouter(prefix="/api/v1/wa-dashboard", tags=["wa-dashboard"])

class WaSseManager:
    def __init__(self):
        self.subscribers: dict[str, asyncio.Queue] = {}  # user_email → queue
    async def publish(self, payload: dict):
        for q in self.subscribers.values():
            await q.put(payload)
    async def subscribe(self, user_email: str) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=100)
        self.subscribers[user_email] = q
        return q
    def unsubscribe(self, user_email: str):
        self.subscribers.pop(user_email, None)

sse_mgr = WaSseManager()

@router.get("/stream")
async def stream(request: Request, user = Depends(get_current_user)):
    async def event_gen():
        q = await sse_mgr.subscribe(user["email"])
        try:
            while not await request.is_disconnected():
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=15)
                    # RBAC server-side filter
                    if not await can_view_message(user, payload):
                        continue
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"  # heartbeat
        finally:
            sse_mgr.unsubscribe(user["email"])
    return StreamingResponse(event_gen(), media_type="text/event-stream")
```

```python
# app lifespan — asyncpg LISTEN binding
async def lifespan(app):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.add_listener('wa_message_inserted',
        lambda *args: asyncio.create_task(
            sse_mgr.publish(json.loads(args[3]))))
    yield
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

### 4.3 Bridge↔backend outbound — PG queue + jittered cooldown (v2 anti-ban)

**Decisione v2**: backend POST → INSERT `wa_dashboard_outbound_queue` row con `scheduled_for = NOW() + jitter(10-30s)` → wa-mirror LISTEN su `wa_outbound_queued` channel → bridge poll-and-send rispettando `scheduled_for`. **NO HTTP server su wa-mirror** (riduce attack surface + bridge resta puro Baileys actuator).

**Perché cambia dal v1 (HTTP POST diretto)**:

1. **Anti-ban critical**: Baileys non ufficiale. Burst send da operatore (5 msg in 10s su un account) trigga ban heuristic Meta. Jitter 10-30s per account = WA-AKG empirical pattern (top-1 candidate panel). MANDATORIO.
2. **No HTTP server su bridge**: aggiungere FastAPI/Express dentro wa-mirror = vector aggiuntivo di crash che propaga ai 8 Baileys heartbeats (cf. cicatrix odierna `com.balizero.wa-mirror-launcher` exit 127). Bridge resta "dumb actuator": PG LISTEN + Baileys send + PG ack.
3. **Resilienza**: backend restart non perde outbound (queue persistita in PG vs in-flight HTTP).
4. **Audit naturale**: queue row contiene `created_by`, `scheduled_for`, `dispatched_baileys_message_id` → operator audit log gratuito.

**Flusso outbound completo**:

```
Operator UI ──POST /api/v1/wa-dashboard/{phone}/send─→ FastAPI
                                                       │
                                                       │ 1. RBAC + idempotency
                                                       │ 2. jitter = uniform(10,30)s
                                                       │ 3. scheduled_for = max(now,
                                                       │      last_scheduled) + jitter
                                                       │ 4. INSERT queue row
                                                       │ 5. pg_notify('wa_outbound_queued')
                                                       │ 6. 202 → UI countdown
                                                       ▼
                                          pg_notify ──→ wa-mirror outbound_worker.ts
                                                         │ setTimeout(scheduled_for - now)
                                                         │ on fire:
                                                         │   SELECT FOR UPDATE SKIP LOCKED
                                                         │   sock.sendMessage(Baileys)
                                                         │   UPDATE status='dispatched'
                                                         ▼
                                          messages.upsert ──→ capture as direction='outbound'
                                                              → pg_notify('wa_message_inserted')
                                                              → SSE stream → UI reflects
```

**Code snippet — send endpoint** (`apps/backend-rag/backend/app/routers/wa_dashboard_send.py` ~250 LOC):

```python
import random
from datetime import timedelta, datetime, timezone

JITTER_MIN_S = 10  # WA-AKG empirical anti-ban
JITTER_MAX_S = 30

@router.post("/{phone}/send", status_code=202)
async def send_wa(
    phone: str,
    payload: SendRequest,
    x_idempotency_key: str = Header(alias="X-Idempotency-Key"),
    user = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    async with db_pool.acquire() as db, db.transaction():
        # 1. idempotency
        existing = await db.fetchrow(
            "SELECT response_payload FROM wa_outbound_idempotency "
            "WHERE idempotency_key=$1 AND user_email=$2 AND expires_at > NOW()",
            x_idempotency_key, user["email"])
        if existing: return json.loads(existing["response_payload"])

        # 2. RBAC
        if not await can_send_from(db, user, payload.team_member_phone):
            raise HTTPException(403, "Cannot send from this team account")

        # 3. compute jittered scheduled_for
        last = await db.fetchval(
            "SELECT MAX(scheduled_for) FROM wa_dashboard_outbound_queue "
            "WHERE team_member_phone=$1 AND status IN ('pending','dispatching')",
            payload.team_member_phone)
        jitter = random.uniform(JITTER_MIN_S, JITTER_MAX_S)
        now = datetime.now(timezone.utc)
        scheduled_for = max(last or now, now) + timedelta(seconds=jitter)

        # 4. insert queue row
        queue_id = await db.fetchval(
            "INSERT INTO wa_dashboard_outbound_queue "
            "(team_member_phone, counterpart_phone, body, media_path, "
            " scheduled_for, status, created_by) "
            "VALUES ($1, $2, $3, $4, $5, 'pending', $6) RETURNING queue_id",
            payload.team_member_phone, phone, payload.body,
            payload.media_path, scheduled_for, user["email"])

        # 5. notify bridge
        await db.execute(
            "SELECT pg_notify('wa_outbound_queued', $1)",
            json.dumps({"queue_id": str(queue_id),
                        "scheduled_for": scheduled_for.isoformat(),
                        "team_member_phone": payload.team_member_phone}))

        # 6. cache idempotency 24h
        response = {"queue_id": str(queue_id),
                    "scheduled_for": scheduled_for.isoformat(),
                    "eta_seconds": int((scheduled_for - now).total_seconds())}
        await db.execute(
            "INSERT INTO wa_outbound_idempotency "
            "(idempotency_key, user_email, response_payload, expires_at) "
            "VALUES ($1, $2, $3, NOW() + INTERVAL '24 hours')",
            x_idempotency_key, user["email"], json.dumps(response))
        return response
```

**Bridge side** (`apps/wa-mirror/bridge/outbound_worker.ts` ~120 LOC):

- Importa `pg.Client` LISTEN su `wa_outbound_queued` (riusa connection già in `bridge/pg.ts`)
- on notify: `setTimeout(send, scheduled_for - now)` ms
- on fire: `SELECT ... FOR UPDATE SKIP LOCKED` → `sock.sendMessage()` Baileys → UPDATE status
- gestisce timer in-memory; restart bridge → al boot fa `SELECT WHERE status='pending'` per riprendere pending

**UI side**: `useSendMessage` hook ritorna `{queue_id, eta_seconds}` → componente `SendCountdown` mostra timer "Send in 18s" → quando `eta_seconds=0` UI rimuove countdown e attende messaggio outbound dal SSE stream (refletted automaticamente via `messages.upsert` Baileys → INSERT outbound row → pg_notify).

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

| Layer                | Choice                                                     | Rationale                                                              |
| -------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------- |
| Frontend framework   | Next.js 16 App Router (existing)                           | Reuse `apps/mouth`                                                     |
| UI                   | Tailwind + shadcn/ui                                       | Already in WaTimelineTab                                               |
| Chat virtualization  | react-virtuoso                                             | DeepSeek-recommended, 1.8M rows                                        |
| State (UI ephemeral) | Zustand                                                    | Lightweight, 3/3 LLM convergent                                        |
| State (server)       | @tanstack/react-query v5                                   | Already in Nuzantara                                                   |
| Realtime             | native WebSocket API + custom store                        | No socket.io needed                                                    |
| Flow viz             | @xyflow/react                                              | Typebot reference, 3/3 convergent                                      |
| Backend framework    | FastAPI (existing)                                         | Reuse `apps/backend-rag`                                               |
| DB                   | Postgres (existing Fly proxy)                              | Already 16 indexes optimal                                             |
| FTS                  | PG `to_tsvector('simple', body)` + GIN                     | DeepSeek validated 1.8M rows <10ms                                     |
| Realtime glue        | PG LISTEN/NOTIFY                                           | Already adopted (cf. cicatrix P0-2)                                    |
| Bridge outbound      | **PG queue + LISTEN (no HTTP)** + jittered 10-30s cooldown | **Anti-ban WA-AKG empirical** + bridge resta dumb actuator + resilient |
| Browser realtime     | **SSE EventSource** (no WebSocket)                         | Auto-reconnect built-in, HTTP/2 mux, no Socket.io dep                  |
| Auth                 | Existing cookie session + RBAC                             | Reuse `get_current_user`                                               |
| Media                | FastAPI `FileResponse` + auth                              | 3/3 convergent                                                         |
| Audit log            | New table `whatsapp_operator_actions`                      | DeepSeek-recommended                                                   |
| Chat UI lib          | **@chatscope/chat-ui-kit-react** (MIT)                     | MessageList/Message/ChatContainer pre-built (saves ~2 settimane)       |
| Anti-ban delay       | 10-30s uniform jitter per account                          | WA-AKG empirical, MANDATORIO Baileys non ufficiale                     |

### 5.3 Decisioni architetturali chiave (3 divergence resolved via panel)

**Q1**: App location — extend `apps/mouth` or new `apps/wa-dashboard`?
**A**: Nuova `apps/wa-dashboard/`. Driver: separation of concerns (mouth = public marketing), worktree contamination R2 ~30% su 2-3 settimane build inside existing app (DeepSeek). Gemini divergente — accettato override DeepSeek per risk-driven choice.

**Q2**: Realtime transport — WebSocket o SSE o polling?
**A**: SSE (read path) + PG NOTIFY (bridge→backend) + plain POST (write path). Driver: throughput 0.88 msg/s sustained = sotto-soglia WebSocket complexity; EventSource auto-reconnect gratis; no Socket.io dependency.

**Q3**: Bridge↔backend outbound — Redis Pub/Sub vs HTTP POST vs PG queue?
**A**: **PG queue + LISTEN**. Driver: anti-ban jitter MANDATORIO (Baileys non ufficiale); persistence cross-restart; bridge resta actuator puro (no HTTP server riduce attack surface + crash cascade su 8 Baileys heartbeats); operator audit log naturale via queue row.

---

## 6. Schema PG nuove tabelle

```sql
-- migration 192_wa_dashboard_v1.sql
-- Lint via Squawk (PR check). DO NOT drop existing whatsapp_message_context.

-- ============================================================
-- 1. Outbound queue (anti-ban jittered cooldown)
-- ============================================================
CREATE TABLE IF NOT EXISTS wa_dashboard_outbound_queue (
  queue_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  team_member_phone VARCHAR(20) NOT NULL,   -- which account sends
  counterpart_phone VARCHAR(20) NOT NULL,
  body TEXT,
  media_path TEXT,
  scheduled_for TIMESTAMPTZ NOT NULL,        -- jittered cooldown anchor (NOW + 10-30s uniform)
  status VARCHAR(20) NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','dispatching','dispatched','failed','cancelled')),
  dispatched_baileys_message_id TEXT,
  dispatched_at TIMESTAMPTZ,
  error_message TEXT,
  retry_count SMALLINT NOT NULL DEFAULT 0,
  created_by VARCHAR(255) NOT NULL,          -- user email
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_wdoq_team_scheduled
  ON wa_dashboard_outbound_queue(team_member_phone, scheduled_for)
  WHERE status IN ('pending','dispatching');
CREATE INDEX idx_wdoq_created_by ON wa_dashboard_outbound_queue(created_by, created_at DESC);

-- ============================================================
-- 2. Idempotency cache for /send (24h TTL)
-- ============================================================
CREATE TABLE IF NOT EXISTS wa_outbound_idempotency (
  idempotency_key VARCHAR(64) NOT NULL,
  user_email VARCHAR(255) NOT NULL,
  response_payload JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '24 hours',
  PRIMARY KEY (idempotency_key, user_email)
);
CREATE INDEX idx_woi_expires ON wa_outbound_idempotency(expires_at);

-- ============================================================
-- 3. Threads — UI-side state for unified inbox
-- (single-table discriminator over whatsapp_message_context)
-- ============================================================
CREATE TABLE IF NOT EXISTS wa_dashboard_threads (
  thread_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  counterpart_phone VARCHAR(20) NOT NULL,
  chat_type VARCHAR(10) NOT NULL CHECK (chat_type IN ('dm','group')),
  group_jid TEXT,                            -- NULL for DM
  team_member_phone VARCHAR(20),             -- which team account; NULL = cross-account merged
  assigned_to VARCHAR(255),                  -- team member email
  status VARCHAR(20) NOT NULL DEFAULT 'open'
    CHECK (status IN ('open','assigned','waiting','escalated','handled','closed')),
  client_id BIGINT,                          -- FK to clients table when matched
  practice_id BIGINT,                        -- FK to practices when matched
  last_message_at TIMESTAMPTZ NOT NULL,
  unread_count INT NOT NULL DEFAULT 0,
  tags TEXT[] DEFAULT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- Postgres does NOT allow expressions in table-level UNIQUE constraints
-- Use CREATE UNIQUE INDEX with expression for the partial-uniqueness contract
CREATE UNIQUE INDEX idx_wdt_unique_thread
  ON wa_dashboard_threads (
    counterpart_phone,
    COALESCE(team_member_phone, ''),
    COALESCE(group_jid, '')
  );
CREATE INDEX idx_wdt_assigned_status ON wa_dashboard_threads(assigned_to, status)
  WHERE status NOT IN ('handled','closed');
CREATE INDEX idx_wdt_last_message ON wa_dashboard_threads(last_message_at DESC);

-- ============================================================
-- 4. Operator audit log
-- ============================================================
CREATE TABLE IF NOT EXISTS whatsapp_operator_actions (
  id BIGSERIAL PRIMARY KEY,
  user_email VARCHAR(255) NOT NULL,
  action_type VARCHAR(50) NOT NULL CHECK (action_type IN (
    'send','tag','assign','reassign','escalate','resolve_attention',
    'add_note','close_thread','reopen_thread','claim_thread'
  )),
  target_message_id BIGINT REFERENCES whatsapp_message_context(id),
  target_thread_id UUID REFERENCES wa_dashboard_threads(thread_id),
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_woa_user_created ON whatsapp_operator_actions(user_email, created_at DESC);
CREATE INDEX idx_woa_target_msg ON whatsapp_operator_actions(target_message_id)
  WHERE target_message_id IS NOT NULL;
CREATE INDEX idx_woa_target_thread ON whatsapp_operator_actions(target_thread_id)
  WHERE target_thread_id IS NOT NULL;

-- ============================================================
-- 5. FTS index su body (simple config = no language stemming, multilingual safe IT/EN/ID)
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_wmc_body_fts ON whatsapp_message_context
  USING GIN (to_tsvector('simple', COALESCE(body, message_text, '')));

-- ============================================================
-- 6. pg_notify triggers — channels: wa_message_inserted, wa_outbound_queued, wa_outbound_dispatched
-- ============================================================
CREATE OR REPLACE FUNCTION notify_wa_message_inserted() RETURNS TRIGGER AS $$
BEGIN
  -- Pointer-only payload (stay well under 8KB NOTIFY hard limit)
  PERFORM pg_notify('wa_message_inserted', json_build_object(
    'id', NEW.id,
    'direction', NEW.direction,
    'team_member_phone', NEW.team_member_phone,
    'counterpart_phone', NEW.counterpart_phone,
    'chat_type', NEW.chat_type,
    'group_jid', NEW.group_jid,
    'attention_priority', NEW.attention_priority
  )::text);
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_wa_message_notify ON whatsapp_message_context;
CREATE TRIGGER trg_wa_message_notify
  AFTER INSERT ON whatsapp_message_context
  FOR EACH ROW EXECUTE FUNCTION notify_wa_message_inserted();

-- Note: wa_outbound_queued and wa_outbound_dispatched are emitted explicitly
-- by the FastAPI send endpoint and the bridge worker (NOT via row trigger).
-- This avoids notify spam on bulk row updates.

-- ============================================================
-- ROLLBACK
-- ============================================================
-- DROP TRIGGER IF EXISTS trg_wa_message_notify ON whatsapp_message_context;
-- DROP FUNCTION IF EXISTS notify_wa_message_inserted();
-- DROP INDEX IF EXISTS idx_wmc_body_fts;
-- DROP TABLE IF EXISTS whatsapp_operator_actions;
-- DROP TABLE IF EXISTS wa_dashboard_threads;
-- DROP TABLE IF EXISTS wa_outbound_idempotency;
-- DROP TABLE IF EXISTS wa_dashboard_outbound_queue;
```

**PG_CHANNEL_MAP additions** (in EventBus config):

```python
# apps/backend-rag/backend/services/eventbus.py
PG_CHANNEL_MAP.update({
    'wa_message_inserted': WaMessageInsertedPayload,
    'wa_outbound_queued': WaOutboundQueuedPayload,
    'wa_outbound_dispatched': WaOutboundDispatchedPayload,
})
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
│   ├── useWaSse.ts             # native EventSource wrapper + auto-reconnect built-in
│   ├── useThreads.ts           # useInfiniteQuery wrapper
│   ├── useMessages.ts          # useInfiniteQuery per phone
│   ├── useSendMessage.ts       # useMutation + idempotency key + ETA tracking
│   └── useSendCountdown.ts     # countdown timer per queue row scheduled_for
└── _lib/
    ├── api.ts                  # axios instance scoped /api/v1/wa-dashboard /api/omnichannel
    ├── types.ts                # extends @/lib/api/whatsapp/whatsapp.types.ts
    └── eventsource.ts          # SSE client with last-event-id replay
```

Tot estimato: ~1500 LOC frontend (nuovo app `apps/wa-dashboard/`), ~500 LOC backend nuovo, ~150 LOC bridge `outbound_worker.ts`.

---

## 8. Roadmap implementativa (5 milestones — UU PDP gate aggiunto)

| M                                                               | Scope                                                                                                                                                                                                                                             | LOC                                 | Days | Dependencies         |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- | ---- | -------------------- |
| **M0 — UU PDP legal gate**                                      | Counsel review: (a) prospect retention basis, (b) centralized reply basis, (c) data subject rights surface. Until sign-off: read-only Admin-only MVP — outbound capability gated                                                                  | 0 LOC                               | TBD  | nessuna              |
| **M1 — Realtime read foundation**                               | Migration 192 (4 tabelle + FTS + pg_notify trigger). FastAPI `wa_dashboard_stream.py` SSE endpoint. asyncpg listener in lifespan. Nuova app `apps/wa-dashboard/` boilerplate. SSE smoke test                                                      | ~400 be + ~150 fe boilerplate       | 1.5d | M0 read-only path OK |
| **M2 — Unified inbox MVP (read-only)**                          | 3-pane layout `apps/wa-dashboard/app/(inbox)/page.tsx` + `ThreadList` + `ChatView` con `@chatscope/chat-ui-kit-react` + `useWaSse` hook + integration `/api/omnichannel/threads` + filters per team_member_phone + chat_type + attention_priority | ~700 fe                             | 2d   | M1                   |
| **M3 — Intervention + assignments** ⚠️ **REQUIRES M0 SIGN-OFF** | `wa_dashboard_send.py` (jittered queue insert + idempotency) + `apps/wa-mirror/bridge/outbound_worker.ts` (LISTEN + scheduled send) + `ComposeBox` UI + `SendCountdown` + tag/assign/escalate + operator audit log                                | ~250 be + ~150 bridge + ~400 fe     | 2d   | M2 + M0 ✓            |
| **M4 — CRM context + media**                                    | `ContextPane` (right) con client/practice enrichment + `MediaPreview` image/PDF/audio + audio player + OCR result tiered renderer + group sender attribution                                                                                      | ~250 fe + ~80 be (auth media proxy) | 1.5d | M3                   |
| **M5 — Search FTS + Flow viz + responsive**                     | FTS endpoint `/api/v1/wa-dashboard/search` + `FilterBar` + `FlowGraphTab` xyflow per F8 + responsive 3→1 pane <1024px + mobile gesture (swipe between panes)                                                                                      | ~300 fe + ~50 be                    | 1.5d | M4                   |

**Totale estimato**: ~2080 LOC nuovo + ~8 giorni dev solo (escluso M0 legal-counsel timeline, fuori controllo dev). Riuso ~70% codebase esistente (6 endpoint omnichannel + WaTimelineTab + schema PG + EventBus pattern).

**Path opzionale M0-bypass**: shippare M1+M2 (read-only Admin-only) come **MVP "audit-mode"** subito. Permette agli operatori di **vedere** tutto il flusso senza rispondere. Outbound (M3) parte solo dopo counsel sign-off. Riduce time-to-first-value da ~10 giorni a ~3.5 giorni.

---

## 9. Rischi + mitigazioni

| #      | Rischio                                                                                | Severità              | Mitigazione                                                                                                                                                                                                                                                      |
| ------ | -------------------------------------------------------------------------------------- | --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **R0** | **UU PDP 27/2022 — prospect message centralized processing senza lawful basis chiara** | **CRITICAL — GATING** | M0 legal counsel sign-off prima di M3 send capability. Read-only Admin-only ammissibile pre-sign-off (legitimate interest defendable, ma stretto). Data subject rights surface (deletion/access) implementata. **NON shippare outbound senza counsel approval.** |
| R1     | **Baileys breakage cycle 8-12 settimane** (WhatsApp protocol drift)                    | HIGH                  | Pin `@whiskeysockets/baileys@6.7.21` (current). 10-week retest cadence in calendar. Cron `wa_mirror_baileys_health.py` alerta su session-corruption spikes. Quando si rompe: capture stops, dashboard mostra correttamente "no new messages"                     |
| R2     | **Anti-ban detection su outbound bursts** (operatore manda 5 msg in 10s da un account) | HIGH                  | **JITTER 10-30s per account MANDATORIO** (WA-AKG empirical). UI countdown "Send in 18s" visibile. Hard-coded default, env override per testing                                                                                                                   |
| R3     | Bridge crash → outbound queue accumulates                                              | MEDIUM                | Bridge restart riprende da `SELECT WHERE status='pending' AND scheduled_for > NOW()`. launchd KeepAlive (cicatrix odierna). Backend continua ad accettare POST e accodare                                                                                        |
| R4     | History sync Baileys floods PG su nuovo onboard account                                | MEDIUM                | Filter `messaging-history.set` event nel bridge — già implementato `bridge/filters.ts`                                                                                                                                                                           |
| R5     | Memory leak Baileys 8 account → bridge OOM                                             | MEDIUM                | Cron graceful restart 04:00 WITA via launchd. Considerare `max_memory_restart` style                                                                                                                                                                             |
| R6     | PG notify saturation a 2.67 msg/s peak                                                 | LOW                   | asyncpg LISTEN ceiling >5000 notif/s. 2.67×18 viewers = 48/s = sotto-soglia 100×                                                                                                                                                                                 |
| R7     | **Single point of failure: Pro crash → tutto down**                                    | HIGH                  | Out of scope (single-machine constraint). PG backup su Tigris cron già live. Operator può continuare manualmente da WhatsApp.app durante outage                                                                                                                  |
| R8     | Operator manda outbound mentre AI risponde (race)                                      | MEDIUM                | Lock conversation: tabella `wa_conversation_locks` con timestamp + user_email. AI agent check lock prima di send. M3+ scope                                                                                                                                      |
| R9     | Cross-account threading UX confusion (cliente scrive a 3 team contacts)                | MEDIUM                | Vista default = separated thread per `(counterpart_phone, team_member_phone)`. Toggle "Merge by client" attivo solo se `client_id` matched. **Nessun repo OS lo implementa nativamente** — siamo first-of-kind                                                   |
| R10    | Group chat overload (32 gruppi attivi)                                                 | MEDIUM                | Tab separata "Gruppi" da inbox principale. Group event types (join/leave/picture/subject_change) collapse di default. Filtri default escludono `chat_type=group`                                                                                                 |
| R11    | Media filesystem unbounded growth                                                      | MEDIUM                | Cron lifecycle: cancella media >180gg salvo `media_kyc_tagged=true`. Out of scope M1-M5 — ticket separato                                                                                                                                                        |
| R12    | **SSE reconnect on laptop sleep/wake**                                                 | LOW                   | EventSource API gestisce auto. `Last-Event-ID` header replay per messaggi persi durante disconnect — implementare server-side cursor su `wa_message_inserted.id`                                                                                                 |
| R13    | PG NOTIFY 8KB payload limit superato                                                   | LOW                   | Payload pointer-only `{id, direction, team_member_phone, counterpart_phone, chat_type, group_jid, attention_priority}` ben sotto 8KB. SSE worker SELECT full row by ID (outbox pointer pattern)                                                                  |
| R14    | Mini-Pro2 24GB RAM saturation se backend colocato                                      | HIGH                  | **NON colocate FastAPI su Mini-Pro2**. Mini = bridge wa-mirror + Ollama. Backend resta su Pro/Fly. Tailscale 62ms non in SSE path (entrambi clients alla stessa PG)                                                                                              |
| R15    | Worktree contamination durante build 8gg (cicatrix 2026-04-29)                         | MEDIUM                | Branch dedicato `feat/wa-dashboard-2026-05-23`. WIP-commit every 10min se untracked files. Push within 30s. `ps aux \| grep claude \| wc -l` session start                                                                                                       |

---

## 10. Open questions (decisione Antonello richiesta)

1. **UU PDP counsel timeline**: hai già contatto con il legal counsel che ha già firmato off su altre attività Bali Zero (es. KYC retention)? Quanto tempo serve realisticamente per ottenere sign-off su (a)+(b)+(c)? Se >2 settimane, valutare path M0-bypass (read-only Admin-only MVP subito + outbound dopo).
2. **App location final lock**: confermi `apps/wa-dashboard/` come nuovo app standalone (raccomandazione DeepSeek + spec v2)? Gemini consigliava reuse `apps/mouth` ma è public-facing.
3. **Cross-account threading**: vista default mergea i messaggi se `client_id` matched, o tiene separated? _Raccomandazione_: separated default + toggle "Merge by client" attivo solo se `client_id` matched.
4. **Group chat scope**: includere group messages nella inbox principale, o tab separata? _Raccomandazione_: tab separata "Gruppi", filtri default escludono group.
5. **Operator presence**: mostrare typing indicator? _Raccomandazione_: M3 con SSE broadcast leggero.
6. **AI auto-reply hooks**: integriamo LangGraph RAG già in M3 o M5? _Raccomandazione_: M5 future — out of M1-M5 v1 scope per evitare scope creep.
7. **Mobile responsive**: Sahira da tablet? _Raccomandazione_: M5 con responsive 3→1 pane <1024px + swipe gesture.
8. **UI language**: italiano o inglese? _Raccomandazione_: inglese per artifact ma italiano per labels operator (CLAUDE.md §9). Compromesso pragmatico: inglese per ora, i18n opzionale futura.
9. **Outbound jitter override**: hard-coded 10-30s o per-account configurabile via UI Admin? _Raccomandazione_: hard-coded default + env override `WA_DASHBOARD_JITTER_MIN_S=10 / WA_DASHBOARD_JITTER_MAX_S=30`. NO UI override (operatore non deve poter bypass anti-ban).
10. **Auth strategy**: A (admin password .env), B (local JWT contro `users` table — best audit), o C (reverse-proxy su `kita.balizero.com`)? _Raccomandazione_: **B** (local JWT, cookie scoped localhost).
11. **Baileys retest cadence**: calendar entry chi mantiene? _Raccomandazione_: scheduled cron `wa_mirror_baileys_retest.sh` ogni 10 settimane → Telegram alert.

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

**Companion research file** (deep-researcher panel completo): `research/operations/2026-05-23-wa-mirror-dashboard-discovery.md` (commit 51817b43f, 26 sources, 304 lines)

**Multi-LLM panel outputs**:

- Gemini 3.1 Pro long-context (Google AI Ultra subscription, $0): `/tmp/gemini_wa_research_output.md` + `/Users/nuzantara/.gemini/antigravity-cli/brain/069533cc-fd9f-4e7c-a0a3-d6c7133d1277/whatsapp_dashboard_synthesis.md`
- DeepSeek V4 Pro reasoning_effort=high ($0.02 total): `/tmp/deepseek_wa_research_output.md` + `/tmp/wa-dashboard-deepseek-output.txt`
- Claude Opus 4.7 self-redteam (fallback dopo DeepSeek empty completion): documented in research file §10
- Deep-researcher agent transcript: 4939 words / 330 lines, agent ID a9ec142e40071ade2

**Codebase audit empirical** (Fly nuzantara-rag asyncpg, 2026-05-23):

- 16586 rows in `whatsapp_message_context`, 15MB total, 16 indexes
- 9 WA-related tables (whatsapp_contacts, whatsapp_lid_phone_map, whatsapp_session_history, ecc.)
- Router endpoints scan: `apps/backend-rag/backend/app/routers/{omnichannel,wa_mirror_messages,whatsapp_conversations,whatsapp_chat,channel_health}.py` (1916 LOC totali)
- Frontend ref: `apps/mouth/src/app/(workspace)/clients/[id]/components/WaTimelineTab.tsx` (297 LOC)

**14 GitHub repositories evaluated**:

1. https://github.com/EvolutionAPI/evolution-api (Apache 2.0, 8.4k★)
2. https://github.com/EvolutionAPI/evolution-manager-v2 (Apache 2.0, 4★) — **lift candidate #2**
3. https://github.com/devlikeapro/waha (Apache 2.0, 6.6k★)
4. https://github.com/ribato22/MultiWA (MIT, 24★) — **lift candidate #3 flow viz**
5. https://github.com/mrifqidaffaaditya/WA-AKG (MIT, 19★) — **lift candidate #1 chat composer + anti-ban**
6. https://github.com/chatwoot/chatwoot (MIT, 29.6k★) — **architecture reference**
7. https://github.com/tags-dev/tercela (MIT, ~200★) — schema reference
8. https://github.com/wppconnect-team/wppconnect-frontend (ARCHIVED)
9. https://github.com/wppconnect-team/wppconnect-server (Apache 2.0, 1k★)
10. https://github.com/wppconnect-team/wppconnect-manager
11. https://github.com/kopigreenx/zete-whatsapp-dashboard
12. https://github.com/mohit2777/whatsapp-web.js-multiple-accounts-dashboard
13. https://github.com/rmyndharis/OpenWA
14. https://github.com/WhiskeySockets/Baileys (issue refs #399, #1247, #1667, #1683)

**3 UI pattern libraries**: 15. https://github.com/xyflow/react-flow — flow viz 16. https://github.com/chatscope/chat-ui-kit-react — **chat UI primitives adottate** 17. https://github.com/assistant-ui/assistant-ui — AI chat primitives (M5 reference)

**Architecture references**: 18. https://dev.to/teglos/i-built-an-open-source-whatsapp-business-inbox-for-teams-heres-how-411d 19. https://dev.to/ribato/building-multiwa-an-open-source-self-hosted-whatsapp-api-gateway-2me1 20. https://blog.algomaster.io/p/polling-vs-long-polling-vs-sse-vs-websockets-webhooks 21. https://leapcell.io/blog/realtime-applications-with-postgresql-listen-notify-a-lightweight-alternative 22. https://baileys.wiki/docs/api/interfaces/GroupMetadata/ 23. https://deepwiki.com/EvolutionAPI/evolution-api/8-development-guide 24. https://deepwiki.com/chatwoot/chatwoot/7.1-email-configuration

**Internal references**: 25. CLAUDE.md §9 (RBAC), §10 (research capture), §16 (research convention) 26. `.claude/rules/cicatrix-scars.md` (2026-04-29 worktree contamination, 2026-04-29 EventBus PG NOTIFY phase 1+2, 2026-05-22 wa-mirror launcher exit 127)

---

## Status

**DRAFT v2** — post deep-researcher panel — pending review Antonello.

**Next gates**:

1. ⏸️ **M0 UU PDP legal-counsel sign-off** (gating outbound capability M3+)
2. ⏸️ Devils-advocate gate via DeepSeek (knowing token-allocation bug, fallback to Opus self-redteam pattern)
3. ⏸️ Antonello answer 11 open questions §10
4. ✅ Spec written, committed (commit 65b3cccbc per v1, v2 incoming)
5. ⏭️ M1 read-only implementation start (M0-bypass path)

**Decision required from Antonello before M1 start**:

- Confirm spec v2 architectural choices (SSE, PG queue, `apps/wa-dashboard/`, jitter 10-30s, `@chatscope/chat-ui-kit-react`)
- Confirm M0-bypass path (ship M1+M2 read-only Admin-only subito) o aspettare M0 legal full
- Answer 11 open questions §10
