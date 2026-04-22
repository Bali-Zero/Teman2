# SOTA Social 2026 — Fase 1 Loop 90gg (Tasks 23-32)

> **Instructions:** copy the entire contents of this file into a new Claude
> chat session to resume SOTA implementation at Fase 1. Self-contained —
> assumes no prior context.

Riprendi l'implementazione della ricerca SOTA Bali Zero. Fase 0 (10 giorni
shot intensivo) è chiusa e approvata. Ora parte la Fase 1: infrastruttura
Loop rolling 90 giorni che chiude il ciclo post → measure → retrain.

## Stato attuale

**Branch:** `feat/sota-social-research` nel worktree
`/Users/nuzantara/Desktop/sota-social-research/` (NON
`/Users/nuzantara/Desktop/nuzantara/`).

**Venv:** symlink `apps/backend-rag/.venv` → parent nuzantara. Usa
sempre il python binary diretto:
`VENV_PY="/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python"`

**DB locale:** `nuzantara_dev` (NON `nuzantara`, che non esiste).

**Secrets env file:** `~/.nuzantara-secrets.env`. Deve essere `source`-ato
prima di ogni run live. Token IG + Brevo + Telegram già presenti e
funzionanti (tutti con `export` corretto).

**Gate 7 status:** Zero ha risposto `APPROVE SOTA` su Telegram. Fase 0
approvata, Loop 90gg può partire.

**Fase 0 artefatti live** in `research/sota-social-2026-v1/`:
- `00_baseline.json` (21 metriche — IG: 10,360 followers, 245 media;
  GSC: 56 clicks / 640 impressions / 76 queries; Brevo: dormant; CRM:
  324 leads 90d / 5 social / 100% coverage; Ahrefs: plan_insufficient)
- `01_balizero_corpus.json` (25 post classificati hook+tone+topic+format)
- `03_sota_literature.md` (51 URL, quality soft — Gemini non grounded)
- `04_personas.json` (6 personas × 16 attr)
- `05_format_matrix.json` (294 celle stub conf=0.3)
- `06_cadence_engine.json` (14×3×24 hour quality scores)
- `07_gap_analysis.md` (16 gaps + 8 strengths, PARTIAL mode)
- `08_playbook.md` (89 Consiglio claims)
- `09_wr2_weights.json` (WR2 config: 60% ID domestic + 40% expat;
  channel priority [IG, LinkedIn, Newsletter]; KPI target Lead 5→45/mese,
  Audience +2500 IG + 1500 newsletter, Authority +800 LinkedIn)
- `10_m13_measurer_config.md` (feedback loop spec)
- `11_go_live_canary.md` (runbook 7gg)

**Artefatto mancante:** `02_competitor_corpus.json` (Vino sta scrapando,
consegna prevista entro 5 giorni lavorativi). Quando arriva:
`python scripts/sota_ingest_competitors.py` (Task 13 del piano, da
implementare in Fase 1 come parte di Task 26 monthly retrain).

## Piano da eseguire

Spec autoritativo: `docs/superpowers/specs/2026-04-22-bali-zero-social-sota-research-design.md`

Piano task-by-task: `docs/superpowers/plans/2026-04-22-bali-zero-social-sota-research-loop.md`
(file root + integration, già scritti).

I 10 task Fase 1 da implementare in ordine:

**Task 23** — `M13FeedbackLoop` core class (migration 128 già applicata)
  - `apps/backend-rag/backend/services/measurer/m13_feedback_loop.py`
  - 5 metodi: collect_post_metrics, compute_delta_vs_baseline,
    should_trigger_retrain, is_pillar_threshold_breach, log_retrain
  - Smoothing cap 20%/settimana, retrain threshold ±10%, breach -20%
  - Test unitari TDD

**Task 24** — Cron every-6h: `scripts/m13_collect_post_metrics.py` +
  `infra/launchagents/com.balizero.sota.m13-collect.plist`
  - Kill switch `system_settings.sota_m13_collect_enabled = 'true'`
  - Pull metriche IG Graph per ogni post in `war_room_posts` ultimi 168h
    per horizon appropriato (24h / 72h / 168h)

**Task 25** — Cron weekly: `scripts/m13_weekly_report.py` (Sunday 06:00 WITA)
  - Aggrega week, calcola delta per channel × pillar
  - Retrain se ±10%, auto-toggle publisher OFF se pillar -20%
  - Telegram digest

**Task 26** — Cron monthly: `scripts/m13_monthly_retrain.py` (1st 04:30 WITA)
  - Re-fetch Ahrefs + re-ingest competitor + re-infer personas + Consiglio
  - Archive `09_wr2_weights_YYYY-MM.json`

**Task 27** — Cron checkpoint: `scripts/m13_checkpoint.py` (daily 09:00)
  - Se Loop day è 30/60/90, trigger checkpoint formale + Telegram

**Task 28** — `editorial_config.py` (WR2 integration)
  - `apps/backend-rag/backend/services/war_room/editorial_config.py`
  - Legge `09_wr2_weights.json`, espone `EditorialConfig` class

**Task 29** — Council v2 accetta persona_slug input
  - Modifica `apps/backend-rag/backend/services/council/tone_council.py`
  - Aggiungi field opzionale `persona_slug` a `CouncilInput`

**Task 30** — Telegram kill-switch router
  - `apps/backend-rag/backend/app/routers/research.py`
  - Comandi: /research pause|resume, /publisher off <ch>, /retrain off,
    /playbook freeze
  - Registra in `router_manifest.py`

**Task 31** — Grafana dashboard JSON
  - `infra/grafana/social-sota-dashboard.json`
  - `docs/runbooks/grafana-sota-setup.md`
  - 5 panels: 3 pillari + heatmap posting hours + top 10 post

**Task 32** — End-to-end smoke
  - `scripts/sota_smoke_fase1.sh`
  - Dispatch tutti i sensor + cron stub + verifica artefatti

## Lezioni apprese Fase 0 (critiche, NON riscoprire)

1. **DB name:** sempre `nuzantara_dev` locale, mai `nuzantara`
2. **Test path:** `apps/backend-rag/backend/tests/unit/services/...`, NON
   `apps/backend-rag/tests/...`
3. **Settings validation:** script che importano `backend.*` richiedono
   `os.environ.setdefault("JWT_SECRET_KEY", "sota-dev-placeholder-32chars-min-ok")`
   + `os.environ.setdefault("API_KEYS", "sota-dev-placeholder-key")` PRIMA
   dell'import
4. **IG Graph v22+** ha deprecato `impressions` metric → NON richiederlo
   mai (400 error)
5. **Gemini CLI rate limit 429** su chiamate sequenziali rapide → preferisci
   Claude CLI per batch LLM work. Gemini solo per 1M ctx (empirical tone
   classify)
6. **Claude CLI su prompt lunghi >100KB** può produrre meta-report invece
   di documento vero → prompt deve avere OUTPUT DIRECTIVE chiaro + forzare
   opening line + bandire meta-phrasing
7. **Ahrefs plan insufficient** per site-explorer + brand-radar → stub
   con `source_status="plan_insufficient"`, NON tentare re-upgrade in Loop
8. **Telegram parse_mode=Markdown** 400-errors su emoji + backtick nested
   → plain text è più sicuro
9. **File env secrets** usa `export VAR=` non `VAR=` — controlla con
   `env | grep VAR` dopo source
10. **PYTHONPATH** per script che usano sia `backend.*` sia
    `apps.evaluator.*`: aggiungi SIA `apps/backend-rag` SIA repo root a
    `sys.path`

## Modalità di lavoro

Usa il `superpowers:subagent-driven-development` skill per i task
implementazione (TDD: red → green → commit). Commit atomici con
Co-Authored-By, branch `feat/sota-social-research`, push solo quando
ti dico (autonomous L2 protocol).

**Primo passo:** leggi
`docs/superpowers/plans/2026-04-22-bali-zero-social-sota-research-loop.md`
e comincia Task 23 (M13FeedbackLoop core).

Pronto? Scrivi `procedo Task 23` e dispatch il primo subagent per il
scaffold + test TDD.
