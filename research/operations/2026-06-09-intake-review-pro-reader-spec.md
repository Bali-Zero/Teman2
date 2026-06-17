---
date: 2026-06-09
domain: operations
subject: Fix #1 — instradare /api/intake/review/* a un reader sul Pro (la UI legge da Fly, i dati intake stanno sul Pro)
client_case: false
sources:
  - apps/backend-rag/backend/app/rag_proxy.py (HEAVY_PREFIXES, RAG_WORKER_URL)
  - apps/backend-rag/fly.toml (RAG_WORKER_URL=http://rag.process.nuzantara-rag.internal:8080)
  - apps/backend-rag/backend/app/routers/intake_review.py (list_review_queue, claim/approve/reject)
  - apps/backend-rag/backend/services/intake/worker.py:464 (DATABASE_URL = LOCAL nuzantara_dev only)
  - live empiria 2026-06-09: GET /api/intake/review/queue → total:0 per adit; Pro nuzantara_dev → 89 review_pending (12 adit)
status: SPEC — panel 4-LLM DONE (GO-WITH-CONDITIONS 2026-06-09) — pronto per implementazione con le 5 condizioni P0 incorporate
---

# Fix #1 — Intake-review reader sul Pro

## Problema (root-cause provata 2026-06-09)

La UI `kita.balizero.com/review` chiama `GET /api/intake/review/queue`. Il processo
`api` su Fly proxa gli `HEAVY_PREFIXES` (incl. `/api/intake/review`) al processo `rag`
su Fly (`RAG_WORKER_URL=http://rag.process.nuzantara-rag.internal:8080`, `fly.toml:40`).
Il processo `rag` su Fly è connesso al **Postgres gestito da Fly** (`nuzantara_rag`),
dove `intake_queue=0` e `document_routing_proposal=0` (contati live).

MA il **worker intake gira sul Pro** e scrive le proposte **solo** sul Postgres
locale del Pro `nuzantara_dev` (`worker.py:464` docstring: "LOCAL nuzantara_dev only",
DSN default `postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev`). Lì: 89 review_pending
(12 con `received_by='adit@balizero.com'`).

→ **Produttore (Pro) e consumatore (Fly) leggono due DB fisici diversi; nulla replica
l'intake.** `crm/clients` funziona solo perché la tabella `clients` è popolata
separatamente su entrambi i DB (11.733 Fly vs 11.524 Pro = DB indipendenti).

La memoria "Fly API → Pro RAG via 6PN" è **stale**: il codice punta a un processo
interno a Fly, mai al Pro.

## Vincolo non negoziabile (Law 2 / UU PDP)

L'intake è PII (KTP/passaporti/akta). **La PII NON deve mai lasciare il Pro.**
Quindi il *reader* deve stare dove sono i dati (sul Pro). NON replicare verso Fly,
NON spostare il worker su Fly (opzioni #2/#3 scartate per sovranità).

## Design proposto

Un reader HTTP **sul Pro** che serve il subset `/api/intake/review/*`, raggiungibile
dal processo `api` su Fly via Tailscale (Pro tailscale IP nota: `100.107.22.111` da
CLAUDE.md — DA RI-VERIFICARE in questo turn prima di hardcodare).

Pattern già esistente da riusare (reuse-first, verificato 2026-06-09):
- Pro ha già un backend uvicorn Pro-local in ascolto: `nlm-bridge` su `0.0.0.0:18790`,
  + openclaw bridge `127.0.0.1:8789`. Il pattern "uvicorn Pro-local raggiungibile"
  esiste — non serve inventarlo.

### Componenti

1. **Pro intake-review reader** (uvicorn Pro-local, porta dedicata es. 18795):
   monta SOLO il router `intake_review.py` (queue/detail/claim/approve/reject) con la
   stessa auth (`get_current_user`) e lo stesso pool → `nuzantara_dev` (Pro).
   Bind su `127.0.0.1:18795` (solo loopback; è `cloudflared` a esporlo, NON 0.0.0.0)
   + `X-Bridge-Auth` shared secret (come bridge.py) come secondo strato applicativo.
   - LaunchAgent `com.nuzantara.intake-review-reader` (KeepAlive, no secret in plist —
     env-file 0600, lezione W65/P0-3).

2. **Proxy split su Fly** (`rag_proxy.py`): per il prefix `/api/intake/review`,
   target = `INTAKE_REVIEW_WORKER_URL` (URL Cloudflare Tunnel del Pro) invece di
   `RAG_WORKER_URL`. Fallback esplicito: se il Pro è irraggiungibile → **503 "intake
   review reader offline"** (NON 200-vuoto: il 200-vuoto è esattamente ciò che ha
   nascosto il bug per giorni — un fail deve essere visibile).

### Acceptance (falsificabile)

- `GET /api/intake/review/queue` come adit (non-admin) → **12 items** (i suoi
  `received_by='adit@balizero.com'`), non 0.
- Come admin (asya/zero) → 89 items.
- Pro reader giù → endpoint risponde **503**, non 200-vuoto.
- Zero PII verso Fly Postgres (la query gira solo sul Pro reader).
- `claim/approve/reject` funzionano end-to-end (con INTAKE_WRITER_ENABLED OFF → dry-run).

## PANEL 4-LLM — verdetto + condizioni (2026-06-09, asimmetrico-avversariale)

**VERDETTO CONSOLIDATO: GO-WITH-CONDITIONS.** Gemini (red-team) + Codex (engineering)
espliciti GO-WITH-CONDITIONS; DeepSeek (logic) converge su proxy/timeout/error-mapping;
Claude sintesi. Il design (reader Pro + Cloudflare Tunnel) è valido ma **non sicuro
così com'era scritto**. Condizioni per gravità:

### Law 2 — formulazione CORRETTA (Codex P0#5, decisione Antonello 2026-06-09)

La formulazione originale "PII never leaves the Pro" era **FALSA**: le *risposte* del
reader (queue + OCR + nomi) transitano cifrate via Fly + Cloudflare fino al browser.
**Formulazione onesta**: *nessuna PERSISTENZA di PII su Postgres Fly né su Cloudflare;
il transito TLS cifrato attraverso Fly/CF (che non la salvano) è presente e ACCETTATO*
— coerente con come già funziona `crm/clients` (dati cliente passano via Fly al browser).
Decisione Antonello: **transito cifrato OK, no persistenza** → Cloudflare Tunnel confermato.

### P0 — bloccanti (nel design prima del codice)

1. **JWT auth ibrida** (Codex P0#1, VERIFICATO su `deps/auth.py:40-50`): `get_current_user`
   usa (1) `request.state.user` da `HybridAuthMiddleware` (**cookie JWT**, priorità 1)
   poi (2) fallback header `Authorization: Bearer` validato con `settings.jwt_secret_key`.
   Il browser di adit usa COOKIE (priorità 1); il mio test curl usava Bearer (priorità 2).
   → **Il reader Pro DEVE montare `HybridAuthMiddleware` + lo stesso `JWT_SECRET_KEY`**,
   non solo il router, altrimenti il cookie viene ignorato. VERIFICATO: `JWT_SECRET_KEY`
   è un secret Fly (`5f080148...`) → copiabile sul Pro in env-file 0600. Il proxy
   inoltra GIÀ tutti gli header incl. Cookie+Authorization (`rag_proxy.py:134`).

2. **Proxy: client httpx per-target** (Codex P0#2, `rag_proxy.py:91`): oggi UN solo
   `httpx.AsyncClient(base_url=RAG_WORKER_URL)` globale. Aggiungere `INTAKE_REVIEW_WORKER_URL`
   riusando lo stesso client → misroute. Costruire client per-target o usare URL assoluti.

3. **Prefix-match esatto** (Codex P0#3, `rag_proxy.py:23`): `startswith("/api/intake/review")`
   cattura anche un futuro `/api/intake/review-metrics`. Usare boundary `/api/intake/review` o
   `/api/intake/review/`. `/api/intake/gate` NON è in HEAVY_PREFIXES → resta sull'api process ✓.

4. **Pro-offline = DoS dell'INTERA API** (Gemini P0 + DeepSeek + Codex P1#3): senza
   timeout stretto il proxy esaurisce il worker pool Fly → down tutta l'API, non solo
   /review. Timeout connect/read **3-5s** (NON i 300s del RAG proxy attuale), fail-fast
   **503 esplicito** mappando OGNI errore (connection refused, 5xx CF, timeout) a 503,
   non forward del raw error.

5. **PII edge-caching CF** (Gemini P0): reader emette `Cache-Control: no-store, private`
   + cache disabilitata nel dashboard CF, o Cloudflare cachea OCR all'edge.

### P1/P2 — da incorporare (non bloccanti)

- **Claim non retry-safe** (Codex P0#4, `intake_review.py:348`): timeout tunnel dopo il
  commit DB → retry 409 → utente perde il token. Fix: claim live dello stesso utente
  ritorna il token esistente (idempotenza), o idempotency-key client-supplied.
- **Approve retry** (Codex P1#2, `:593`): può duplicare audit-row dry-run → read-after-write/
  status-poll, non blind retry.
- **Pool dedicato piccolo** (Codex P1#1, `deps/database.py:24`): il reader monta il suo
  `app.state.db_pool` min1/max3 + statement_timeout + close on shutdown; NON l'app-factory
  completa (no scheduler/eventbus).
- `/healthz` sul reader (DB pool + JWT config, senza esporre dati).
- Strip header `X-Bridge-Auth`/`CF-Access-*` in INGRESSO dalle richieste utente prima di
  aggiungere quelli di servizio (Codex P2#2 + Gemini P1).
- `INTAKE_WRITER_ENABLED=0` esplicito nell'env del reader, non solo default.
- JWT + `X-Bridge-Auth` droppati dai log CF (Gemini P1, replay vector).
- Tunnel target `http://127.0.0.1:18795` esplicito, NON `localhost` (Gemini P2: cloudflared
  risolve localhost come `::1` IPv6 → connection refused se uvicorn binda IPv4).

## Rischi / aperti

- **Transport — DECISO 2026-06-09 (Antonello): Cloudflare Tunnel.** Verificato che la
  tailnet del Pro ha 4 peer e **nessuno è Fly** → Fly NON può raggiungere il Pro via
  Tailscale oggi. Scelta: **Cloudflare Tunnel dal Pro** (`cloudflared`).
  - **Perché**: il router del Pro è ISP-locked (no port-forward) → `cloudflared` fa
    connessione IN USCITA dal Pro, zero porte aperte. Fly è effimero → un URL CF stabile
    batte il ri-enrollment Tailscale a ogni deploy. Cloudflare già in uso per balizero.com.
  - **Law 2**: il reader gira sul Pro, la PII non lascia mai il Pro in chiaro. Cloudflare
    instrada solo TLS cifrato Fly→Pro (non vede i dati). Auth: **Cloudflare Access Service
    Token** (header `CF-Access-Client-Id`/`CF-Access-Client-Secret` dal lato Fly) +
    `X-Bridge-Auth` shared secret applicativo come secondo strato. L'`Authorization`
    (JWT utente) viene inoltrato così il reader Pro fa `get_current_user` identico → RBAC
    invariata.
  - **Setup**: `cloudflared tunnel` sul Pro → hostname `intake-review.balizero.com` (o
    sottodominio dedicato) → `localhost:18795`. Token CF in env-file 0600 sul Pro (no plist).
    Lato Fly: secret `INTAKE_REVIEW_WORKER_URL=https://intake-review.balizero.com` +
    `CF_ACCESS_CLIENT_ID`/`CF_ACCESS_CLIENT_SECRET`.
  - **Scartate**: Tailscale sidecar su Fly (fragile con l'effimerità Fly); Tailscale
    Funnel (endpoint pubblico, più superficie); Pro→Fly push (PII su Fly, viola Law 2).
    Più semplice di A, ma espone un endpoint pubblico (auth forte obbligatoria).
  - **D. Pro→Fly push** — SCARTATO: la coda review contiene OCR/nomi = PII, non può
    salire su Fly (Law 2).
  → **Questo è il vero rischio #1 e va deciso PRIMA del reader.** Senza transport,
    lo spec del reader è corretto ma non eseguibile.
- **Pro offline** = /review non disponibile (per design: i dati sono lì). Accettabile
  per intake review (operazione di back-office), MA va comunicato (503 chiaro).
- **Latency**: una hop Fly→Tailscale→Pro per ogni load della coda. Accettabile per
  una UI di review a bassa frequenza.
- **Auth replay**: il reader Pro deve validare lo STESSO JWT (stesso JWT_SECRET_KEY)
  o il proxy inoltra l'header Authorization originale. Preferito: inoltro header +
  `get_current_user` identico → zero divergenza RBAC.

## Cosa NON fa questa fix

- NON sblocca adit da sola se manca il transport Tailscale Fly→Pro (rischio #1).
- NON tocca il worker intake (resta sul Pro, corretto).
- I 6 review_claimed orfani sono già stati rilasciati a review_pending (2026-06-09,
  UPDATE sul Pro DB); restano `received_by` NULL = admin-only.

## Next

1. ~~Transport~~ DECISO: Cloudflare Tunnel (vedi Rischi/aperti).
2. Panel 4-LLM (Gemini red-team + Codex + DeepSeek + Claude) su questo spec — focus:
   (a) l'inoltro del JWT utente attraverso CF Access non rompe `get_current_user`;
   (b) il 503-on-Pro-offline non degrada il resto della UI; (c) il reader Pro condivide
   lo stesso `JWT_SECRET_KEY` del Fly per validare i token; (d) idempotenza di
   claim/approve/reject attraverso il tunnel (retry/timeout).
3. Setup `cloudflared` sul Pro + secret CF Access (operator step, no segreti in plist).
4. Implementazione in worktree broker, branch dedicato, PR — proxy split + Pro reader +
   LaunchAgent.
5. Acceptance E2E: adit login → `/review` mostra i suoi 12; admin vede 89; Pro giù → 503.
