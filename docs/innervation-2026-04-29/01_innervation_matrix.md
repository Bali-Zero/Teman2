# 01 — Innervation matrix: inventario organi della flotta

**Data**: 2026-04-29
**Stato**: snapshot baseline (FASE 1, prima del lavoro di innervazione)
**Sorgenti**: filesystem + `launchctl list` + `fly machines list` + audit zero-crash 2026-04-29 + INDEX.md + CLAUDE.md §14 + cicatrix-scars.md + 4 LLM dispatch (Codex 28-pattern catalog)

> **Nota sulla ricostruzione**: questo file è stato perso al filesystem level durante un `git pull origin main` automatico (vedi `02_dispatch_resilience_log.md` § Cosa è successo). Ricostruito identico da context di sessione. Numeri verificati al momento dell'audit.

---

## 1. Numeri prima (Legge 7)

| Dimensione nervosa | Conteggio | % |
|---|---:|---:|
| **Organi totali censiti** | **149** | 100% |
| Heartbeat strutturato verso `organism:events` | 0 | 0% |
| Event emission strutturata verso `organism:events` | 4 | 2.7% |
| Health endpoint HTTP raggiungibile | 4 | 2.7% |
| Genoma entry (registry autoritativo) | 0 | 0% |
| Recovery action automatica documentata | ~10 | 6.7% |
| Cell-aware (Cell ne legge stato) | 6 | 4.0% |
| Ha cicatrice associata | 8 | 5.4% |

**Lettura**: la flotta è strutturalmente cieca a livello bus unificato. Cell vede 6 cose (backend-rag /health + 5 servizi locali Pro). Organism ha 4 caller di `emit_event` (post_commit_hook, scheduled_tick, system_doctor.py, sentinel_lib/zombie_hunter.py) ma solo 1 di questi è schedulato come LaunchAgent attivo → emit funzionali ma scollegati. Heartbeat: zero. Genoma: zero.

**Caveat importante (Codex insight)**: molti organi **emettono già signal** in altri canali (`~/.agent/decisions/state/*.last.json`, `cron:reports` Redis stream, `cell_pulse_log` SQL, `events_outbox` PG). Questi signal NON sono in `organism:events` ma esistono. **Innervation = bridge questi signal verso `organism:events`**, non modifica 149 organi.

---

## 2. Suddivisione per runtime

### 2.1 Runtime: Pro (`nuzantara@Nuzantara`, 48GB M4 Pro)

| Categoria | Conteggio |
|---|---:|
| LaunchAgent project (`com.{nuzantara,balizero,cell}.*.plist` in `~/Library/LaunchAgents/`) | 52 |
| Home scripts (`~/scripts/*.{py,sh}`) | 46 |
| Cron-agent-python scripts (`~/scripts/cron-agent-python/*.py`) | ~30 |
| Cell process (LaunchAgent `com.cell.organism`) | 1 |
| Organism processes (Supervisor + control panel + scheduled_tick) | 0 deployed (3 plist in repo) |
| **Totale Pro** | **132** |

**Suddivisione 52 LaunchAgent Pro per prefisso**:
- 29 `com.balizero.*` (business: WR2 pipeline, intel, post-publish-poller, NLM bridge, sota, dispatch, translate, ecc.)
- 21 `com.nuzantara.*` (infra: sentinel, zombie-hunter, dlq-autopilot, automap-server, monitor cpu/disk, tunnel, login-healthcheck, fly-restart-loop-detector, claude-max-usage-watcher, ecc.)
- 2 `com.cell.*` (cell-organism, cell-metabolic-rollup)

**Top 7 critical Pro (KeepAlive=true daemon)**: cell.organism, balizero.nlm-bridge, balizero.post-publish-poller, balizero.wr2.supervisor, nuzantara.dlq-autopilot, nuzantara.sentinel, nuzantara.automap-server.

**Cicatrici Pro**:
- 2026-04-29 plist mass corruption (51/54 truncated → 5 secret leaked, structural OPEN)
- 2026-04-29 only 7/53 (13%) have KeepAlive=true (P0-3, structural OPEN)
- 2026-04-29 backend `/health` masks `startup_failed` (P0-0 brainstorm — Cell `pulse.py` ora fixed con classify_http_status che inspect body.status semantica)

### 2.2 Runtime: Air (`antonellosiano@Nuzantara-9`, 16GB M4)

| Categoria | Conteggio |
|---|---:|
| LaunchAgent project user (`com.{balizero,nuzantara}.*` in `~/Library/LaunchAgents/`) | 2 |
| Repo scripts (`~/Projects/nuzantara/scripts/*.{sh,py}`) | ~50 (shared via git con Pro) |
| Cron-agent-python (Air-specific) | 0 (gestiti via OpenClaw `.DISABLED`) |
| **Totale Air business runtime** | **2** |

**LaunchAgent Air attivi**:
- `com.balizero.indexing-sweep.daily` (KBLI + articles indexing)
- `com.nuzantara.tmux-work` (interactive session)

**Discovery contraria a CLAUDE.md §14**: la sezione "Cron Air" elenca 13 job (Ollama start/stop, auto_test, sentinel, indexing-sweep, kb-ingest, rag-canary, system-doctor, drive-watchdog, judgement-day, ragas-eval, kg-quality). **Solo `indexing-sweep` è LaunchAgent attivo**. Gli altri sono gestiti da OpenClaw (oggi `.DISABLED`) o sono a livello documentale ma NON in `launchctl list`. Da innervare richiede prima decidere: **OpenClaw va riattivato? O migriamo a LaunchAgent puri?** — Lascio nel `13_known_gaps.md` come domanda aperta.

**Drive-poll**: cron Pro disabilitato 2026-04-29 02:42 dopo cicatrix `get_file_metadata` AttributeError (PR `720d54f5c`). NON re-enable prima di 48h test green.

### 2.3 Runtime: Fly.io

| App | Stato | Macchine | Health |
|---|---|---|---|
| `nuzantara-rag` | LIVE | 2 (api 1781e5eda03438 + rag d894e65bede478) | api 1/1 checks |
| `nuzantara-postgres` | LIVE | 1 (v0.1.0) | n/a |
| `nuzantara-qdrant` | LIVE | 1 (v1.17.0) | n/a |
| `nuzantara-admin` | toml present, deploy state TBD | ? | ? |
| `bali-intel-scraper` | toml present, **NOT deployed** (CLAUDE.md §8 "ONLY local on Pro via OpenClaw") | n/a | n/a |

**Totale Fly innervato**: 3 app live = 3 organi.

### 2.4 Runtime: Vercel (frontend)

8 subdomain dichiarati in CLAUDE.md §10:
- `kita.balizero.com` (workspace)
- `my.balizero.com` (portal)
- `prime.balizero.com` (3D maps)
- `mail.balizero.com`
- `calendar.balizero.com`
- `drive.balizero.com`
- `knowledge.balizero.com`
- `zantara.balizero.com` (AI chat)

`apps/mouth/src/app/` ha 3 route group: `(workspace)`, `(blog)`, `(book)`. I subdomain sono mappati via Vercel rewrite + middleware. **Totale Vercel: 8 subdomain logici** (granularity: 1 prod app `mouth` ma 8 endpoint pubblici osservabili).

### 2.5 Runtime: GitHub Actions

| Workflow | Schedule | Categoria |
|---|---|---|
| `fly-deploy.yml` | on push main backend-rag | deploy |
| `migration-lint.yml` | on PR migrations_v2 | lint |
| `tests.yml` | on PR | tests |
| `e2e-playwright.yml` | on PR | tests |
| `mcp-server-tests.yml` | on PR | tests |
| ~5+ altri (audit, claude-task, sentinel, dispatch) | varie | ops |

Stima: ~10 workflow GitHub Actions.

### 2.6 Runtime: MCP servers

3 MCP server in repo (`apps/nuzantara-mcp*`):
- `nuzantara-mcp` (115 tool, primary, FastMCP stdio)
- `nuzantara-mcp-advanced` (14 tool, Fly ops)
- `nuzantara-mcp-browser` (6 tool, browser automation)

**Stato deploy**: gli MCP sono spawned on-demand via Claude Code config (`~/.claude.json`). Non sono daemon long-running — sono session-bound. **Non hanno heartbeat naturale**. Da innervare: tracking "ultimo invocation" anziché "last heartbeat".

### 2.7 Runtime: Backend-rag interno (sottorganismi)

Anche dentro nuzantara-rag c'è una flotta interna che oggi NON emit eventi su `organism:events` (ma SÌ su PG LISTEN/NOTIFY + outbox interno):
- 7 channel processor (whatsapp, telegram, instagram, twitter, web, gchat, slack) — PR #360 ha aggiunto `webhook_processor.py` ack-first
- 253 router HTTP
- 513 service business logic
- EventBus PG LISTEN/NOTIFY (refactored P0-2 fase 2 con outbox)
- 12 vector collection Qdrant
- KG Postgres (108K nodes, 242K edges)
- Drive poll service (Air)
- 1 lifespan startup (FastAPI app_factory)

**Granularity** sensato per il Genoma:
- 7 channel processor (entità deploy-distinct)
- 1 EventBus consumer
- 1 webhook_processor
- 1 lifespan/health endpoint
- 1 drive_poll_service (Air)
- 1 KG sync
- = 12 organi backend-rag interni

### 2.8 Riepilogo cross-runtime

| Runtime | Organi | %  |
|---|---:|---:|
| Pro (LaunchAgent + scripts) | ~78 (52 plist + 26 scripts critici) | 52% |
| Air (LaunchAgent + cron-agent-python) | ~5 (2 plist + ~3 attivi) | 3% |
| Fly.io | 3 | 2% |
| Vercel | 8 | 5% |
| GitHub Actions | ~10 | 7% |
| MCP servers | 3 | 2% |
| Backend-rag interno | 12 | 8% |
| Cell+Organism (codice esistente) | 2 | 1% |
| **Subtotal "core"** | **121** | 81% |
| OpenClaw legacy / disabled | ~15 | 10% |
| Pipeline NLM/eval | ~10 | 7% |
| Misc (Hammerspoon, comfyui, peekaboo, ecc.) | ~3 | 2% |
| **Totale** | **149** | 100% |

---

## 3. Granularity dell'innervazione (priorità Wave 1)

Non tutti i 149 organi vanno innervati subito. Wave 1 (gli 4 più critici, alta confidenza, feedback rapido) per il design spec §3 "Migration order":

| # | Organo | ID Genoma proposto | Runtime | Heartbeat freq | Recovery action | Cicatrice |
|---|---|---|---|---:|---|---|
| 1 | backend-rag api machine | `backend.api` | Fly | 60s | fly machines start | 2026-04-29 startup_failed mask |
| 2 | drive_poll_service | `backend.crm.drive_poll` | Air cron disabled | 5min | re-enable cron after green | 2026-04-29 get_file_metadata |
| 3 | claude-max-usage-watcher | `pro.claude_max_watcher` | Pro LaunchAgent | 60min | launchctl kickstart | nessuna ancora |
| 4 | login-healthcheck | `pro.login_probe` | Pro LaunchAgent | 15min | launchctl kickstart | 2026-04-29 login broken |

Tutte e 4 sono organi "facili": già esistono come job, basta aggiungere `await emit_event(severity="info", source="<id>", kind="heartbeat", payload={...})` al termine di ogni run e Genoma entry. **Insight Codex**: tutti e 4 già scrivono state files (`~/.agent/decisions/state/<job>.last.json` o `cell_pulse_log`) → bridge daemon può raccogliere senza modifiche.

---

## 4. Schema colonne complete (per il Genoma)

Per ogni organo, il Genoma deve dichiarare 10 campi (definitivo, non ambiguo):

| Campo | Tipo | Esempio |
|---|---|---|
| `id` | str (`<runtime>.<domain>.<name>`) | `backend.crm.drive_poll` |
| `runtime` | enum (`pro_launchd` / `air_launchd` / `air_cron` / `fly_machine` / `vercel_function` / `github_actions` / `mcp_session` / `backend_internal`) | `air_launchd` |
| `type` | enum (`daemon` / `cron` / `webhook` / `agent` / `channel` / `evaluator`) | `cron` |
| `expected_hb_seconds` | int (window, 0 = no heartbeat richiesto) | 300 |
| `owner_module` | str (path repo) | `apps/backend-rag/backend/services/crm/drive_poll_service.py` |
| `dependencies` | list[str] | `["backend.api", "infra.postgres", "google.drive_oauth"]` |
| `recovery_action` | enum (`launchctl_kickstart` / `fly_machines_start` / `cron_reenable` / `webhook_replay` / `human_only`) | `cron_reenable` |
| `recovery_params` | dict (parametri specifici action) | `{"plist": "com.balizero.drive-poll", "machine": "Air"}` |
| `severity_on_silence` | enum (`info` / `warning` / `error` / `critical`) | `error` |
| `cicatrix_refs` | list[str] | `["2026-04-29-drive-poll-attribute-error"]` |

**Persistenza Genoma**: file YAML in `apps/organism/organism/genome.yaml`, complementare a `redundancies.yaml`. Singola sorgente di verità versionata in git. **Non SQLite/PG** (NB-1 ADR-3: niente SQLite per shared state cross-machine). **Checksum SHA256 + ADR-7 HALT** su signature mismatch.

**Aggregazione last-seen**: SQLite locale `~/.organism/last_seen.db` aggiornato dal Supervisor consume loop. Cell+Organism leggono SQLite per "chi è vivo?", il Genoma resta source-of-truth statico per "chi dovrebbe esserci". SQLite locale è ammesso (NB-1 ADR-3 banishes SQLite **shared cross-machine**, non per-machine state).

---

## 5. Output per FASE 2

→ Il design del Genoma è ora schematizzato (sez. 4). FASE 2 design produce `07_innervation_protocol.md` con il contratto nervoso (heartbeat schema + emit format) e la decisione finale tra le 3 proposte DeepSeek (B Tiered Resilience raccomandato).

→ Migration plan in 4 Wave (per Q2-B clarification: parallel solo repo/file, serial Air/Fly/Vercel runtime):
- **Wave 1** (4 organi sez. 3): Pro + Fly + Air, granularity facile, heartbeat-only, sequenziale (Q2-B). Innervazione completa entro ~2h.
- **Wave 2** (Air watcher/cron): SERIAL (Q2-B), gestione SSH Air + LaunchAgent. ~3h.
- **Wave 3** (7 channel + 3 MCP server): SERIAL (Q2-B), backend-internal granularity. ~3-4h.
- **Wave 4** (8 subdomain frontend): PARALLEL (Q2-B), client beacon Vercel preview-only fino a chaos test. ~2h.

Totale Wave 1-4 ≈ 10-12h di lavoro effettivo + chaos test FASE 4.
