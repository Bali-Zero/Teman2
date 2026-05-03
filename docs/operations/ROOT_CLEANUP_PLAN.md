# Root Cleanup Plan

Questo documento definisce la struttura target della root del repository e il mapping dei file che oggi risultano fuori posto.

## Obiettivo

La root deve contenere solo:

- file di bootstrap del repository
- configurazioni condivise
- directory canoniche del monorepo
- documenti di governance realmente necessari

Tutto il resto deve essere spostato in cartelle dedicate o rimosso dal controllo versione se si tratta di artefatti locali, cache o credenziali.

## Root Target

```text
nuzantara/
├── README.md
├── .gitignore
├── .dockerignore
├── .env.example
├── package.json
├── package-lock.json
├── docker-compose.yml
├── docker-compose.production.yml
├── docker-compose.monitoring.yml
├── vercel.json
├── tsconfig.json
├── AGENTS.md
├── CLAUDE.md
├── .mcp.json
├── .github/
├── .husky/
├── apps/
├── packages/
├── docs/
├── scripts/
├── config/
├── data/
└── tests/
```

## Cosa Tenere In Root

- `README.md`
- `.gitignore`
- `.dockerignore`
- `.env.example`
- `package.json`
- `package-lock.json`
- `docker-compose.yml`
- `docker-compose.production.yml`
- `docker-compose.monitoring.yml`
- `vercel.json`
- `tsconfig.json`
- `AGENTS.md`
- `CLAUDE.md`
- `.mcp.json`
- `.github/`
- `.husky/`
- `apps/`
- `packages/`
- `docs/`
- `scripts/`
- `config/`
- `data/`
- `tests/`

## Mapping Root -> Destinazione

### Documentazione sparsa

- `AI_CONFIG_DEPLOYMENT_LOG.md` -> `docs/operations/AI_CONFIG_DEPLOYMENT_LOG.md`
- `GEMINI.md` -> `docs/ai/GEMINI.md`
- `DEPLOYMENT_GUIDE.md` -> `docs/operations/DEPLOYMENT_GUIDE.md`
- `PRODUCTION_TEST_GUIDE.md` -> `docs/operations/PRODUCTION_TEST_GUIDE.md`
- `QUICK_START.md` -> `docs/operations/QUICK_START.md`
- `CLEANUP_10_STEPS.md` -> `docs/operations/CLEANUP_10_STEPS.md`
- `WORKSPACE.md` -> `docs/operations/WORKSPACE.md`
- `SITUAZIONE_ATTUALE.md` -> `docs/operations/SITUAZIONE_ATTUALE.md`
- `DASHBOARD_INTEGRATION_NOTES.md` -> `docs/features/DASHBOARD_INTEGRATION_NOTES.md`

### Architettura e design

- `SYSTEM_MAP.mermaid` -> `docs/architecture/SYSTEM_MAP.mermaid`
- `SYSTEM_MAP_LIVE.md` -> `docs/architecture/SYSTEM_MAP_LIVE.md`
- `SUPER_KNOWLEDGE_GRAPH_STRATEGY.md` -> `docs/architecture/SUPER_KNOWLEDGE_GRAPH_STRATEGY.md`
- `KG_LANGGRAPH_FIX_SUMMARY.md` -> `docs/architecture/KG_LANGGRAPH_FIX_SUMMARY.md`
- `CHAIN_ONBOARDING_IMPROVEMENTS.md` -> `docs/architecture/CHAIN_ONBOARDING_IMPROVEMENTS.md`

### Report e analisi

- `ARTICLE_PERFORMANCE_ANALYSIS.md` -> `docs/reports/ARTICLE_PERFORMANCE_ANALYSIS.md`
- `CRM_AUTOMATION_ANALYSIS_REPORT.md` -> `docs/reports/CRM_AUTOMATION_ANALYSIS_REPORT.md`
- `SEO_AI_ANALYSIS_270_ARTICLES.md` -> `docs/reports/SEO_AI_ANALYSIS_270_ARTICLES.md`
- `SEO_PATCH_IMPLEMENTATION_SUMMARY.md` -> `docs/reports/SEO_PATCH_IMPLEMENTATION_SUMMARY.md`
- `REPORT_OPENCLAW_NOTEBOOKLM_INTEGRATION.md` -> `docs/reports/REPORT_OPENCLAW_NOTEBOOKLM_INTEGRATION.md`
- `TEST_RESULTS.md` -> `docs/reports/TEST_RESULTS.md`

### Script sciolti

- `cleanup_complete.sh` -> `scripts/maintenance/cleanup_complete.sh`
- `cleanup_script.sh` -> `scripts/maintenance/cleanup_script.sh`
- `deploy_docker_compose.sh` -> `scripts/deployment/deploy_docker_compose.sh`
- `deploy_production.sh` -> `scripts/deployment/deploy_production.sh`
- `fix_critical_issues.sh` -> `scripts/maintenance/fix_critical_issues.sh`
- `setup_auth.py` -> `scripts/auth/setup_auth.py`
- `sentinel` -> `scripts/ops/sentinel` con wrapper temporaneo in root per compatibilita su `./sentinel`

### Dati e output

- `SEO_ACTION_PLAN_REAL_DATA.json` -> `data/analysis/SEO_ACTION_PLAN_REAL_DATA.json`
- `scan_geonode_desa.json` -> `data/analysis/scan_geonode_desa.json`
- `pending_articles.txt` -> `data/analysis/pending_articles.txt`
- `gold_kbli_list.txt` -> `data/reference/gold_kbli_list.txt`
- `SYSTEM_MAP.mermaid` -> `docs/architecture/SYSTEM_MAP.mermaid`
- `DOSSIER_GERMINIANI_BOSSI.md` -> `docs/client_briefs/DOSSIER_GERMINIANI_BOSSI.md`
- `OPENCLAW_MASTER_GUIDE_2026.md` -> `docs/ai/OPENCLAW_MASTER_GUIDE_2026.md`
- `SENTRY_AND_LOGGER_COMPLETE.md` -> `docs/security/SENTRY_AND_LOGGER_COMPLETE.md`
- `SENTRY_TASK_COMPLETE.md` -> `docs/security/SENTRY_TASK_COMPLETE.md`
- `nuzantara-rebrand-brainstorm.md` -> `archives/experiments/brand/nuzantara-rebrand-brainstorm.md`

### Immagini e artefatti

- `prime-header-fix.png` -> `docs/assets/prime-header-fix.png`
- `prime-new-logo.png` -> `docs/assets/prime-new-logo.png`
- `prime-sidebar-redesign-qa.png` -> `docs/assets/prime-sidebar-redesign-qa.png`
- `prime-zantara-idle.png` -> `docs/assets/prime-zantara-idle.png`
- `prime_map_loaded.png` -> `docs/assets/prime_map_loaded.png`
- `prime_qa_deploy.png` -> `docs/assets/prime_qa_deploy.png`

### Cartelle da classificare

- `backend/` -> consolidare in `apps/backend-rag/` oppure archiviare in `docs/archive/legacy-root/backend/`
- `POSTGRESQL/` -> `docs/database/postgresql/`
- `google-apps-script/` -> `integrations/google-apps-script/`
- `source_documents/` -> `data/source_documents/`
- `monitoring/` -> `config/monitoring/`
- `tools/` -> unificare in `scripts/`
- `prompts/` -> `config/prompts/`
- `reports/` -> `docs/reports/root-legacy/reports/`
- `storage/` -> `data/runtime/storage/`
- `harvested_zones/` -> `data/harvested_zones/`
- `KBLI-Navigator-2025/` -> `archives/legacy-root/kbli-navigator/KBLI-Navigator-2025/`

### Compatibilita temporanea

Per evitare rotture immediate sui path storici, alcune directory possono restare esposte in root come symlink temporanei:

- `source_documents` -> `data/source_documents`
- `monitoring` -> `config/monitoring`
- `prompts` -> `config/prompts`
- `POSTGRESQL` -> `docs/database/postgresql`
- `reports` -> `docs/reports/root-legacy/reports`
- `tools` -> `scripts/tools`
- `storage` -> `data/runtime/storage`
- `backend` -> `archives/legacy-root/backend`

## Eccezioni Temporanee

Questi file possono restare in root fino a una decisione piu strutturale:

- `app_dashboard.py` - entrypoint standalone referenziato da documentazione e piani storici

## Artefatti Locali

Gli artefatti locali ignorati non devono restare nella root attiva. Se non possono essere rimossi subito, possono essere spostati in una quarantena locale come:

- `.local-trash/root-artifacts-YYYY-MM-DD/`

I file locali sensibili non devono restare in root. Se servono sulla macchina locale, possono essere ricollocati in `.secrets/`, ad esempio:

- `.secrets/env.combined.local`

## Da Rimuovere Dal Controllo Versione

- `node_modules/`
- `.next/`
- `venv/`
- `__pycache__/`
- `.playwright-mcp/`
- `test_results/`
- `snapshots/`
- `.ruff_cache/`
- `.vercel/`
- `.env.combined`
- `service-account.json`
- `google-credentials.json`
- `.DS_Store`
- file swap editor e altri artefatti temporanei

## Local Secrets

I file sensibili locali devono vivere in `.secrets/` e non in root.

- `.secrets/service-account.json`
- `.secrets/google-credentials.json`

## Ordine Consigliato Di Esecuzione

1. Creare il `README.md` canonico in root.
2. Creare le cartelle mancanti in `docs/` e `data/`.
3. Spostare i file Markdown della root verso `docs/`.
4. Spostare gli script sciolti verso `scripts/`.
5. Rimuovere credenziali e artefatti locali dal controllo versione.
6. Aggiornare eventuali riferimenti interni dopo gli spostamenti.
7. Standardizzare lockfile e package manager.

## Nota Operativa

Prima di eseguire move massivi:

- verificare riferimenti da script CI, documentazione e workflow AI
- riallineare i due repository locali Pro/Air
- eseguire la pulizia su un branch dedicato
