# Brief uniforme — Audit zero-crash 2026-04-29

> Stesso brief inviato (con micro-adattamenti di tono per ciascun CLI) ai 4 LLM
> esterni: Codex GPT-5.4, Gemini 3.1 Pro, DeepSeek Reasoner, NotebookLM.
> Mio (Opus 4.7) brief è leggermente esteso perché ho già letto i 6 libri sacri
> e contiene context inline.

---

## Goal

Da 2026-04-30 il sistema Nuzantara non può più avere un crash senza
ripartenza automatica. Mai più "schermo bianco" come PR #273 (i18n provider
mancante in workspace), mai più "machine in restart loop" come
nuzantara-rag d894e65bede478, mai più "deploy crash silenzioso" come la
trauma cicatrix di fly-deploy.yml pre-2026-04-18 (Air A3, deploy crashava
prima di health check senza alert).

## Background factual (numeri prima — Legge 7)

- Monorepo: 27 apps, 5 packages
- Backend: 139 routers, 512 services in `apps/backend-rag/backend/`
- Channels: 7 (whatsapp/telegram/instagram/twitter/web/gchat/slack)
- Migrations v2: 30 SQL files (last applied: 140)
- Fly.io: 3 app dichiarate. Stato 2026-04-29 05:00 UTC:
  - `nuzantara-rag` deployed 3h15m ago, 2 machines (api + rag)
  - `nuzantara-postgres` deployed 2026-04-10
  - `nuzantara-qdrant` **SUSPENDED** (Qdrant Cloud usato via `QDRANT_URL` secret)
- Knowledge Graph: 108K nodi, 243K edges (PostgreSQL)
- Vector: 12 collection Qdrant, 10 visibili da local
- LaunchAgents Pro: 19 plist `com.nuzantara.*`
- Circuit breakers: 58 entries totali, 16 OPEN (28%) al 2026-04-29 13:19
- Escalation cooldowns attivi: 40
- Escalations Pro pending: 5 (NB pipeline NB-1/6/7/8 + weekly_report)
- Escalation Air HIGH `air-a1-auth-surface` (apps/web SSO) **non risolta da 11 giorni**
- Cicatrix STRUCTURAL aperta: PR #307 SQL v2 deploy ordering bug (workaround manuale `gh workflow run` post-merge)

## Failure mode già documentati (cicatrix)

1. **Atlas migrate-lint paywall v0.38** — RISOLTO 2026-04-26 via pivot Squawk
2. **SQL v2 migrations applicate sull'OLD image** — APERTO. `flyctl ssh console` runs migrations against image PRECEDENTE; nuove SQL richiedono manual re-trigger
3. **Deploy crash pre-health-check unalerted (Air A3)** — RISOLTO 2026-04-18 via `deploy-failure-alert` job
4. **Dockerfile cell-core missing** — RISOLTO 2026-04-17 via cell-core-workspace
5. **Hook regex falso positivo print()** — RISOLTO (lessons.md)
6. **Migration manager runner runs ROLLBACK as part of forward** — RISOLTO 2026-04-19 via `split_migration_sql()`
7. **i18n provider per route group** (PR #273) — RISOLTO ma riproducibile per ogni nuovo route group senza provider
8. **Drive polling Air OAuth expiry 90gg** — protetto da watchdog ma non monitorato in modo formale

## Surfaces da analizzare (espandi se ne vedi altre)

### BACKEND
- Fly.io app (image pull, OOM, restart, secret rotation, machine fail)
- 139 routers (import chain, dependencies.py SPOF, registration order)
- 512 services (async client leak Golden Rule #10, DB pool exhaustion, cache stampede)
- Migration system v2 (cicatrix PR #307 — ancora aperto?)
- Drive polling Air (page_token loss, OAuth 90gg, circuit breaker 3 fail → OPEN)
- Cron Air (12+ job: Ollama window, system_doctor, sentinel, drive watchdog, RAGAS, KG quality, indexing sweep, RAG canary)
- Channels 7 (webhook timeout, retry storm, dead letter; X CRC broken da settimane)
- EventBus Redis (Symbiosis Legge 4: "se Redis è down, ogni agente funziona in isolamento" — VERIFICATO?)
- KG (108k nodi: subgraph generation fail, embedding drift `text-embedding-3-small` FROZEN, qdrant collection corruption)

### FRONTEND
- Mouth (Next.js 16/React 19): i18n provider per route group, hydration mismatch, edge runtime crash
- 8 subdomain (kita/my/prime/mail/calendar/drive/knowledge/zantara): SSO `nz_access_token` cookie expiry, rewrite chain
- Service Worker / PWA cache poisoning, stale bundle
- Build env vars `NEXT_PUBLIC_*` (devono passare via `git push`, non `vercel --prod`)

### ORGANI LOCALI
- Cell (apps/cell): sistema nervoso. Chi ascolta i suoi segnali? Cosa succede se Cell stessa crasha?
- Organism (apps/organism): autonomic design — gap rispetto a `docs/superpowers/specs/2026-04-22-autonomic-organism-design.md`?
- Mata Garuda (OSINT): blindatura — quale superficie può perdere dati intelligence?
- MCP servers (3): nuzantara-mcp, -advanced, -browser. Crash di uno = blast su quanti tool?

### DEPLOY / CI
- fly-deploy.yml: Air-A3 risolto, ma copre TUTTI gli stage failure?
- Squawk migration lint: bypass legittimi tracciati?
- Pre-deploy gate: copre dependencies.py + router registration?
- Post-deploy QA browser: run automatico o solo on-demand?

### OSSERVABILITÀ
- Langfuse (PR #312): dormant di default. ATTIVA o resta off?
- System Doctor cron 08:00: cosa NON vede?
- Telegram alert chat 1125336968: dedup? rate limit? alert fatigue?
- Healthcheck probe team_members `healthcheck@balizero.com` 15min: copertura?

## Vincoli (non negoziabili)

1. **CLI-only LLM** (Symbiosis Legge 1) — DeepSeek API è unica eccezione
2. **OSINT blindato** (Legge 2) — dati intelligence mai in cloud/team/frontend
3. **Event-driven** (Legge 3) — Redis Streams, no polling, no orchestratore centrale
4. **Graceful degradation** (Legge 4) — un organo down ≠ sistema down
5. **Zero ultima istanza** (Legge 5) — decisioni strutturali via Telegram
6. **Sovranità locale** (Legge 6) — sistema vive su Pro 48GB + Air 16GB
7. **Numeri prima** (Legge 7) — ogni claim quantificato
8. **Cell + Genoma centrali** — ogni proposta touchpoint Cell o motiva l'esclusione
9. **Anthropic API banned** — solo `claude` CLI con `CLAUDE_CODE_OAUTH_TOKEN`. SDK import = banned.
10. **CLAUDE.md OFF-LIMITS**: `zantara_core.py`, `fly.toml`, `.env.production`, `alembic/env.py`

## Output atteso da te (LLM esterno)

Per ogni superficie con gap di recovery automatico, riporta:
- **Failure mode concreto** + esempio (cita scar se applicabile)
- **Blast radius**: cosa cade quando questo fallisce. Numeri prima.
- **Rilevazione attuale** (o assenza)
- **Recovery attuale** (o assenza)
- **Fix proposto**: codice/config/cron specifico. File path + diff conceptuale. Riferimento a Cell/Genoma se applicabile.
- **Verifica post-fix**: comando per testare. Numeri before/after attesi.
- **Severità**: P0 (crash sistema senza recovery oggi) | P1 (degrade sistema senza alert) | P2 (degrade rilevato ma manuale)
- **Autonomia**: auto-implementabile da Claude L2 sì/no

Non sintetizzare — esaustività > brevità. Se vedi superfici NON elencate sopra, includile.

Ricorda: graceful degradation. Ogni fix deve preservare l'isolamento degli organi. Mai introdurre un SPOF nuovo per risolverne uno vecchio.

---

## Versione tu (LLM)

[Inserito a runtime per ogni dispatch]
