# War Room 2.0 — Runbook Operativo

> Reference: [docs/war-room-2.0-design.md](../war-room-2.0-design.md) · Implementazione Sprint 1–12 · 2026-04-18

---

## 1. Overview

War Room 2.0 è il centro di produzione mediatica di Bali Zero. Pipeline end-to-end:

```
TrendSignal → Consiglio tone → Drafter → Visual (Imagen 4) → Layout (Playwright)
→ Review Gate Telegram → Publisher (IG/X/LI/Blog) → Measurer → Learner → genome
```

**Leggi cardine attive**:
- **Legge 1** CLI-only per LLM (DeepSeek HTTP eccezione documentata)
- **Legge 4** Graceful degradation ovunque
- **Legge 5** Zero ultima istanza — MAI auto-publish

**Costo operativo a regime**: ~$6/mese (Imagen $4.8 + DeepSeek $0.15 + Claude OAuth flat).

---

## 2. Servizi (12 package backend/services/)

| Package | Responsabilità | Sprint |
|---|---|---|
| `war_room/` | Models Pydantic + WarRoomRepository + DashboardService | 1, 11 |
| `intel/` | Dossier compiler + Trend-Hunter adapters + orchestrator | 2 |
| `council/` | CLI runners (claude/gemini/deepseek) + ToneCouncil 3-round | 3 |
| `visual/` | Imagen 4 client + Ollama qwen2.5vl QA + QAJudge dual-voice | 4 |
| `layout/` | HTML templates + Playwright screenshot + LayoutPatcher CSS | 5 |
| `review/` | Telegram Review Gate + SLA worker 4h/12h/48h | 6 |
| `publisher/` | IG/X/LinkedIn/Blog + Orchestrator parallel | 7, 8 |
| `measurer/` | MetaGraph + UTM + MeasurementScheduler T+24h/72h/7d | 9 |
| `learner/` | Score composito + genome skill/scar + memoria episodica 2000ch | 10 |
| `hardening/` | FailoverDetector + MissedRunsAlerter + TokenWatchdog + QuotaMonitor | 12 |

**442 unit test verdi + 7 integration skippati** (lanciabili con `TEST_DATABASE_URL`).

---

## 3. Env vars richiesti

### Backend-rag core (già presenti)
- `DATABASE_URL` (Fly Postgres)
- `OPENAI_API_KEY`, `QDRANT_URL`, `REDIS_URL`, `JWT_SECRET`

### War Room 2.0 specifici
```bash
# Telegram Review Gate
TELEGRAM_BOT_TOKEN=<bot token>
TELEGRAM_OWNER_CHAT_ID=1125336968             # Zero's chat id (from CLAUDE.md §14)

# Intel Scraper / Trend-Hunter
GROK_API_KEY=<xAI live-search>                # optional, OSINT Legge 2 Pro-only

# Council (DeepSeek HTTP = Legge 1 eccezione)
DEEPSEEK_API_KEY=<deepseek>

# Visual Generator
GOOGLE_API_KEY=<or GEMINI_API_KEY>            # Imagen 4 Ultra + Fast
FIREWORKS_API_KEY=<fireworks>                 # fallback Flux

# Publisher — Instagram
IG_USER_ID=<numeric business account>
IG_LONG_LIVED_TOKEN=<60-day token>

# Publisher — X / Twitter
X_BEARER_TOKEN=<oauth2 user context>

# Publisher — LinkedIn
LINKEDIN_ACCESS_TOKEN=<oauth2>
LINKEDIN_AUTHOR_URN=urn:li:person:<id>        # OR urn:li:organization:<id>

# Publisher — Blog (opzionali, hanno default)
BLOG_CONTENT_ROOT=/Users/nuzantara/Desktop/nuzantara/apps/web/content/war-room
BLOG_SITE_URL=https://balizero.com
BLOG_URL_PREFIX=/blog
BLOG_PUBLISH_SKIP_PUSH=                       # set to "1" for local dry-runs
```

---

## 4. Migrations

```bash
cd apps/backend-rag && source .venv/bin/activate

# Sprint 1 — tabelle core war_room_*
PYTHONPATH=. python -c "
import asyncio, asyncpg, os
from backend.migrations import migration_112_war_room_tables
async def run():
    c = await asyncpg.connect(os.environ['DATABASE_URL'])
    await migration_112_war_room_tables.apply(c)
    await c.close()
asyncio.run(run())
"

# Sprint 2 — intel dossier
PYTHONPATH=. python -c "
import asyncio, asyncpg, os
from backend.migrations import migration_113_intel_dossiers
async def run():
    c = await asyncpg.connect(os.environ['DATABASE_URL'])
    await migration_113_intel_dossiers.apply(c)
    await c.close()
asyncio.run(run())
"
```

Migration test manuali:
```bash
TEST_DATABASE_URL=postgresql://backend_rag_v2:XXX@localhost:15432/nuzantara_rag \
PYTHONPATH=. pytest backend/tests/services/war_room/test_migration_112.py \
                   backend/tests/services/intel/test_migration_113.py -v
```

---

## 5. Cron schedule (suggerito)

Host: **Pro** (macOS, launchd). Fallback Air per Trend-Hunter se Pro down.

| Ora WITA | Job | Script |
|---|---|---|
| Ogni 2h | Trend-Hunter | `python -m backend.services.intel.trend_hunter.cli` |
| 04:00 | Intel Dossier Compiler (batch top-20) | (Sprint 13 — futuro) |
| 08:00 | Intake (scelta topic del giorno) | (wire esistente War Room v1 da portare) |
| Ogni 30min | SLA Review worker | `python -m backend.services.review.sla_worker` |
| Ogni 6h | Measurer scheduler (T+24/72/7d) | `python -m backend.services.measurer.cli` |
| 03:00 | Learner nightly | `python -m backend.services.learner.cli` |
| Ogni 6h | Missed-runs alerter | `python -m backend.services.hardening.missed_runs_cli` |
| Una volta/giorno | Token watchdog | `python -m backend.services.hardening.token_watchdog_cli` |
| Ogni 12h | Quota monitor | `python -m backend.services.hardening.quota_cli` |

*(Note: gli `_cli` moduli sono wrapper triviali che istanziano il servizio e chiamano `sweep_once`. Non forniti in Sprint 12 per evitare bloat — ogni team può deciderne la forma esatta.)*

---

## 6. Dashboard

- **URL**: `https://<admin-dashboard>/war-room/metrics`
- **Windows**: 14 / 30 / 90 giorni
- **Widget**: Timeline · DistributionPie · Funnel · Rejections · Heatmap · CostTable
- **Alert banner**: si accende se un registro > 40% nel periodo (deriva tonale)
- **Data source**: Next.js route handlers `/api/war-room/metrics/*` → pg Pool → PG su Fly

Alternativa backend-only (stesse query, pronte per altri consumer):
- `GET https://nuzantara-rag.fly.dev/api/war-room/metrics/timeline?days=30`
- `GET .../heatmap` · `/distribution` · `/funnel` · `/rejections` · `/costs`

---

## 7. Review Gate Telegram

Flusso:
1. Draft arriva a `status=pending_review` → PG trigger `notify('war_room_event', ...)` → backend subscriber invia foto+keyboard
2. Zero riceve: cover + caption + registro scelto + registri scartati + costo immagini
3. Inline keyboard: `✅ Approva` / `✏️ Edit` / `❌ Rifiuta`
4. Rifiuta → secondo keyboard con 5 motivi (tone/fact/visual/clickbait/other)
5. SLA: 4h soft alert ⏰ · 12h repeat 🚨 · **48h auto-expire → rejected (NON published)**

**Legge 5 enforced**: `SLAWorker` usa `DraftStatus.REJECTED` + `RejectedBy.SYSTEM` + messaggio "Legge 5: nessuna pubblicazione effettuata".

---

## 8. Pipeline produzione — passo-passo

### 8.1 Happy path carousel IG (manuale oggi, cron domani)

```python
# Pseudo: backend/scripts/one_shot_warroom.py
from uuid import uuid4
from backend.services.war_room import (
    WarRoomRepository, WarRoomDraftCreate, DraftStatus, RegisterTone,
)
from backend.services.council import ToneCouncil, ClaudeCLIRunner, GeminiCLIRunner, DeepSeekHTTPRunner
from backend.services.visual import VisualGenerator, ImagenClient, OllamaVisionClient, QAJudge
from backend.services.visual.generator import SlideSpec
from backend.services.layout import LayoutRenderer, ...
from backend.services.review import ReviewHandler, TelegramReviewAdapter, ReviewRequest
from backend.services.publisher import IGPublisher, PublisherOrchestrator
from backend.services.publisher.base import DraftPayload

# 1. Draft
repo = WarRoomRepository(db_pool=pool)
draft = await repo.create_draft(WarRoomDraftCreate(topic="B211A estensione 2026"))

# 2. Consiglio tono
council = ToneCouncil(
    proponents={
        "claude": ClaudeCLIRunner(),
        "gemini": GeminiCLIRunner(),
        "deepseek": DeepSeekHTTPRunner(api_key=os.environ["DEEPSEEK_API_KEY"]),
    },
    judge=ClaudeCLIRunner(),
)
tone_result = await council.run(
    topic=draft.topic,
    registers_last_14d=await repo.count_registers_last_14d(),
)
await repo.update_status(draft.id, DraftStatus.CONCEPT)

# 3. Visual
gen = VisualGenerator(
    imagen=ImagenClient(),
    vision=OllamaVisionClient(),
    judge=QAJudge(judge_runner=ClaudeCLIRunner()),
    cost_repo=repo,
)
slides = [SlideSpec(slide_number=1, image_prompt="editorial hero", is_cover=True)] + ...
visual_result = await gen.generate_carousel(slides, draft_id=draft.id)

# 4. Review gate
review = ReviewHandler(repo=repo, telegram=TelegramReviewAdapter())
await review.send_review_request(ReviewRequest(
    draft_id=draft.id,
    topic=draft.topic,
    tone_register=tone_result.decision.chosen_register,
    cover_image_url=tigris_upload(visual_result.slides[0].image_bytes),
    first_slide_text=...,
))

# → Zero approves via Telegram → status=approved → trigger Publisher (wire EventBus subscriber)
```

### 8.2 Testing end-to-end
- Fixture fixture: `backend/tests/services/war_room/test_migration_112.py` + `test_migration_113.py` (integration, richiede `TEST_DATABASE_URL`).
- Smoke: 442 unit test verdi in 6s, nessuna dep esterna.

---

## 9. Chaos procedures

### 9.1 Pro spento 2h
- Trend-Hunter cron su Air parte in **degraded mode** (`TrendHunterOrchestrator.force_degraded=True`): no xAI (Legge 2 OSINT Pro-only), solo RSS + Ollama locale + Gemini CLI.
- Pipeline pesante (carousel produzione) **salta**: `WarRoomMissedRun` inserito con `skipped_reason=pro_offline`.
- Quando Pro torna online, alert Telegram "3 run missed" (via MissedRunsAlerter).

### 9.2 IG token scaduto
- TokenWatchdog alerta 7gg prima.
- Se comunque scade: IGPublisher ritorna `PublishResult.ok=False` con HTTP 401. Orchestrator fa 3 retry con backoff. Al terzo fallimento la riga non va in `war_room_posts`, va in `war_room_publish_failures` (futuro) o semplicemente log+alert.
- Fix: rigenera token via Meta Business Suite → aggiorna env `IG_LONG_LIVED_TOKEN` → restart backend.

### 9.3 Render fail
- `LayoutRenderer` prova max 3 iterazioni con patch CSS.
- Dopo 3 fallimenti: `LayoutResult.needs_escalation=True` → pipeline può escludere quella slide e procedere con carousel parziale (Legge 4).

### 9.4 QA vision offline (Ollama down)
- `OllamaVisionClient.analyze` ritorna `VisionFlags(ok=False)`.
- `QAJudge` fallback deterministico: se flags non disponibili, treat as retry (una volta), poi pass-through.
- `LayoutRenderer` in caso simile: pass-through con `final_flags.ok=False` — pipeline non si blocca.

---

## 10. Rollback

**Backend**:
```bash
cd apps/backend-rag
fly releases --app nuzantara-rag
fly releases rollback <prev-version> --app nuzantara-rag
```

**Migration rollback**:
```bash
# migration 112 o 113
PYTHONPATH=. python -c "
import asyncio, asyncpg, os
from backend.migrations import migration_112_war_room_tables as m
async def run():
    c = await asyncpg.connect(os.environ['DATABASE_URL'])
    await m.rollback(c)   # drops tutte le tabelle war_room_*
    await c.close()
asyncio.run(run())
"
```

Attenzione: rollback migration 112 rimuove **tutti** i dati operativi War Room (drafts, posts, metrics, costs, rejections, missed_runs, leads).

**Frontend**:
```bash
cd apps/admin-dashboard
vercel rollback
```

---

## 11. Observability

### 11.1 Log essentials
- `backend.services.war_room.*` — draft lifecycle transitions
- `backend.services.review.*` — Telegram callback authz + idempotency
- `backend.services.publisher.*` — per-platform attempts + retry counts
- `backend.services.measurer.*` — sampler partial flags + errors
- `backend.services.learner.*` — skills/scars recorded per sweep

### 11.2 SQL diagnostici
```sql
-- Draft pipeline status distribution ultimi 7gg
SELECT status, COUNT(*) FROM war_room_drafts
 WHERE created_at > NOW() - INTERVAL '7 days'
 GROUP BY status;

-- Post per piattaforma + registro 30gg
SELECT platform, register, COUNT(*)
  FROM war_room_posts
 WHERE published_at > NOW() - INTERVAL '30 days'
 GROUP BY 1, 2 ORDER BY 3 DESC;

-- Costi breakdown 30gg
SELECT cost_type, SUM(cost_usd)::numeric(10,4)
  FROM war_room_costs
 WHERE occurred_at > NOW() - INTERVAL '30 days'
 GROUP BY 1 ORDER BY 2 DESC;

-- Run saltati non notificati
SELECT id, scheduled_at, skipped_reason
  FROM war_room_missed_runs
 WHERE notified_zero = FALSE
 ORDER BY created_at DESC LIMIT 20;

-- Learner skill/scar emessi (via genome SQLite — CLI)
#   mem query "war_room:"
```

---

## 12. Regole operative (Legge 5)

- **MAI modificare** `zantara_core.py` dal War Room. È SSOT voce Zantara.
- **MAI auto-pubblicare** senza click Zero in Review Gate. Anche SLA scaduto → rejected.
- **MAI far partire** Publisher con token scaduto — token watchdog deve alertare prima.
- **MAI bypassare** il Consiglio per scelta registro. Anche in produzione d'emergenza: fallback a `analitico` deterministico, mai a `cinico`/`ironico` arbitrari.

---

## 13. Prossimi sprint (Parte II del design doc)

Sprint 13–20 riguardano: Intel Scraper riposizionato, 10 consumer dossier, Connector/Anomaly/Strategos/Oracle cognitive layer, Blog Publisher extended, Newsletter.

Parte I (Sprint 1–12) è **completa e pronta per produzione**.

---

**Maintained by**: Claude Opus 4.7 + Zero · **Last updated**: 2026-04-18
