# Backend RAG — Non-Inferable Knowledge

> Archive of session notes: `docs/sessions/CLAUDE-archive-2026-04-06.md`
> Only things the agent CANNOT discover independently belong here.

---

## Critical Gotchas

### Docker Build Context — Monorepo Root (PR #62)

The Dockerfile expects build context at **monorepo root**, not `apps/backend-rag/`.
Fly uses this via `flyctl deploy --dockerfile apps/backend-rag/Dockerfile --config apps/backend-rag/fly.toml` in `.github/workflows/fly-deploy.yml`.

**Local `docker build` — RUN FROM REPO ROOT:**

```bash
cd "$(git rev-parse --show-toplevel)"
docker build -f apps/backend-rag/Dockerfile -t rag-test .
```

**Do NOT** `cd apps/backend-rag && docker build -t rag-test .` — that excludes `packages/cell-core/` from context and breaks the cell-core editable install.

Authoritative `.dockerignore` is at repo root (`/.dockerignore`); `apps/backend-rag/.dockerignore` is retained but IGNORED by Fly.

### SQLite Persistence — `/data` Volume on `api` Process (PR #75)

The `api` process has a persistent Fly volume (`nuzantara_api_data → /data`). Two SQLite databases live there:

- `EXPERIENCE_DB_PATH=/data/experience.db` — Genome (Experience/Skill)
- `METABOLIC_DB_PATH=/data/organism_metrics.db` — Metabolic snapshots

Both env vars are set in `fly.toml [env]`. Data survives rolling deploys. The `rag` process has its own separate volume (`nuzantara_rag_data`).

### Router Registration — Manifest Pattern (PR #63)

**NEVER edit `router_registration.py` directly.** It reads from `router_manifest.py`.

To add a new router:

1. Create file in `backend/app/routers/`
2. Add `RouterEntry` in `backend/app/setup/router_manifest.py` with correct `process_groups`
3. Run `PYTHONPATH=. pytest backend/tests/setup/test_router_manifest.py -q`
4. Done. No other file needs editing.

Process groups: `_API` (light, public HTTP via main_api), `_RAG` (heavy, internal via main_rag), `_BOTH` (health checks).

**SCAR:** PRs #54/#55/#60 registered routers only in `include_routers()` (dev) but not `include_light_routers()` (prod), causing silent 404s. The manifest makes this structurally impossible.

### ABSTAIN Override (reasoning.py)

`calculate_evidence_score()` returns 0.00 when Gemini answers directly without calling tools. Score < 0.15 = ABSTAIN → blocks all valid business answers.

**Three-layer fix** (both streaming + non-streaming paths in `reasoning.py`):

1. `intent_classifier.py`: 17 pricing keywords in `GENERAL_TASK_KEYWORDS` trigger `skip_rag=True`
2. If `final_answer` contains pricing markers (Rp, IDR, USD), set `trusted_tools_used = True`
3. **KEY**: If LLM had `_gemini_tools` configured and produced `final_answer`, trust it → `trusted_tools_used = True`

### Rogue AI Import Removal

AI refactors (Gemini/Windsurf) silently remove `Any` from `typing` imports. `dependencies.py` is imported by EVERY router — missing `Any` crashes entire app at startup.

**Prevention**: Always run before deploy:

```bash
python -c "from backend.app.dependencies import get_current_user; print('OK')"
PYTHONPATH=. pytest backend/tests/services/rag/ -q
```

### Service Injection Pattern (avoid circular imports)

Use `get_service()` lazy loading pattern, NOT direct imports between services. Circular imports between services will crash FastAPI startup silently.

---

## Pricing Rules (ABSOLUTE)

### HAS_FEE in KG ≠ Bali Zero Prices

KG `HAS_FEE` relations (~1,500) contain government PNBP fees and legal regulation costs extracted from imigrasi.go.id — NOT Bali Zero service prices.

**Bali Zero prices are ONLY in:**

- File: `backend/data/bali_zero_official_prices_2025.json`
- Tool: `PricingTool` (Tool #2)
- Loaded by: `PricingService._load_prices()`

**Rules enforced in `prompt_builder.py:47-66`:**

1. ONLY use prices from `get_pricing` tool
2. NEVER invent, estimate, or guess ANY price
3. If price not in tool → "Questo costo specifico è da verificare con il team"

---

## Model Configuration

| Use Case           | Model                       | Fallback         | Notes                                          |
| ------------------ | --------------------------- | ---------------- | ---------------------------------------------- |
| KBLI chat          | `claude-haiku-4-5-20251001` | Gemini Flash     | In `kbli_notebook.py`                          |
| RAG orchestrator   | Gemini 2.5 Flash            | Gemini 2.0 Flash | Primary reasoning                              |
| Embedding          | `text-embedding-3-small`    | NONE             | **FROZEN** — changing invalidates 93K+ vectors |
| Evidence threshold | 0.15                        | —                | Below = ABSTAIN                                |

---

## Test Commands

```bash
# Full backend tests
PYTHONPATH=. pytest backend/tests/ -v --tb=short -x

# Critical path (RAG + KG)
PYTHONPATH=. pytest backend/tests/services/rag/ -q

# Coverage with gate
PYTHONPATH=. pytest backend/tests/ --cov=backend --cov-report=term-missing --cov-fail-under=40

# Import chain validation (catches rogue AI removals)
python -c "from backend.app.dependencies import get_current_user; print('OK')"
```

---

## Deploy Checklist

```bash
# 1. Check for rogue changes
git diff --name-only HEAD -- apps/backend-rag/backend/

# 2. Test import chain
python -c "from backend.app.dependencies import get_current_user; print('OK')"

# 3. Run core tests
PYTHONPATH=. pytest backend/tests/services/rag/ -q

# 4. Deploy
fly deploy --app nuzantara-rag --strategy rolling

# 5. Verify
curl -s https://nuzantara-rag.fly.dev/health | jq .
```

---

## Non-Standard Patterns

- Routers are in `backend/app/routers/`, NOT `backend/routers/`
- `PYTHONPATH=.` is REQUIRED for all pytest commands
- Qdrant payloads must be **flat** (no nested dicts)
- `zantara_core.py` is the SINGLE source of truth for core config — edit ONLY there
- bali-intel-scraper runs LOCALLY on Pro only, NOT on Fly.io

### Compliance alerts (2026-04-18, this PR)

- Generation: `backend.services.compliance.alerts_engine.AlertsEngine.generate_alerts(forecasts)`
- Persistence: `compliance_alerts` (m114) + `alert_outcomes` (m115)
- Dispatch: `alert_dispatcher.AlertDispatcher` — team channels unconditional, client via `notification_prefs` (m110)
- Delivery trace: existing `notification_log` (m111) with `ref = f"compliance_alert:{alert_id}:{channel}"` convention (NO schema change)
- Retrain: `AlertFeedback.retrain()` adjusts per-category URGENT thresholds (kill-switch in `system_settings.compliance_alert_autotune_enabled`, defaults to `false`)
- Intel validators: 3-tier pipeline logged in `intel_validator_log` (m116); valid entities proposed (not auto-promoted) via `intel_kg_bridge.propose_kg_entities` → `kg_proposals` (m108)
- LKPM ready-pack: `POST /api/lkpm/ready-pack/{client_id}` (reportlab PDF + openpyxl XLSX + Drive + Brevo `zantara@balizero.com`)
- Migration convention: v2 SQL files now support `-- === ROLLBACK ===` marker (parsed by `migration_manager._extract_rollback_sql`)

Deprecated:
- `backend.services.compliance.alert_generator.AlertGeneratorService` — shim; use `AlertsEngine`.
- `backend.services.misc.proactive_compliance_monitor` — 5-line deprecation warning only, logic untouched (scope exception, decision #10).
