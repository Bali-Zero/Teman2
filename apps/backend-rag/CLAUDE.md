# Backend RAG — Non-Inferable Knowledge

> Archive of session notes: `docs/sessions/CLAUDE-archive-2026-04-06.md`
> Only things the agent CANNOT discover independently belong here.

---

## Critical Gotchas

### Sentry PII Redaction Is Load-Bearing (2026-04-21)

`backend/app/setup/sentry_config.py::_before_send` is the only thing stopping
UU PDP-regulated PII (NPWP, NIB, passport, email, phone, client_id, name,
surname) from leaking to Sentry cloud on every exception. Three rules:

1. **Never remove the `before_send=_before_send` kwarg** from `sentry_sdk.init`.
   Sentry has NO opt-in knob for this behavior — without the hook, every
   unhandled exception with a request body in locals leaks PII.
2. **Never set `SENTRY_SEND_DEFAULT_PII=1`** in production. `send_default_pii`
   would add IP addresses and user headers on top of the fields the hook is
   already redacting; `scripts/sentry-quota-check.sh` alerts on this.
3. **Never raise `SENTRY_TRACES_SAMPLE_RATE > 0.02`** in production. Free tier
   is 5k events/month shared across errors AND transactions; APM sampling
   burns it silently, after which error events are dropped too. Default is
   `0.0` in prod — APM is opt-in per deploy.

When you add a new PII-bearing field to a router:

- Add the token to `_PII_KEY_SUBSTRINGS` in `sentry_config.py` (or to
  `_PII_EXACT_KEYS` if the bare key would collide with debug fields —
  e.g. `name` is exact-match-only because `filename`/`function_name`
  must survive).
- Add a case to `PII_SAMPLES` in `tests/test_sentry_pii_redaction.py`.
- Run `SKIP_SENTRY_INIT=1 PYTHONPATH=. pytest tests/test_sentry_pii_redaction.py -q`.

Kill-switch for the whole integration: `fly secrets set SKIP_SENTRY_INIT=1 -a nuzantara-rag`.

### Migration Runner Was Executing ROLLBACK Section In-Transaction (SCAR 2026-04-19, FIXED)

`backend/db/migration_base.py` `BaseMigration.apply()` previously read the
**full** content of every `.sql` file in `db/migrations_v2/`, including the
section after the `-- === ROLLBACK ===` marker, and passed it all to
`conn.execute(sql)`. PostgreSQL treats `-- === ROLLBACK ===` as a normal
comment, so CREATE TABLE followed by DROP TABLE ran in the same transaction:
the migration logged "applied successfully" and then the table vanished. The
next migration found "relation does not exist" and failed.

Concrete symptom from PB2 deploy 2026-04-19:

```
Migration 114_compliance_alerts applied successfully in 67ms   ← log says OK
Applying migration 115_alert_outcomes
ERROR: SQL execution failed: relation "compliance_alerts" does not exist
```

**Fix (branch `fix/migration-runner-rollback-strip`):**
- Added `ROLLBACK_MARKER_RE` regex to `migration_base.py`.
- New `split_migration_sql(sql) -> (forward, rollback)` helper.
- `BaseMigration.apply()` now uses only the forward portion.
- Checksum still computed on the full file content for audit stability.
- 2 integration tests added that drive real `apply()` and
  `apply_all_pending()` against PG (the previous tests validated only the
  extraction helper, not the apply path).

**Cost of incident:** 19-commit revert of `pro/backend-compliance-intel-e2e`
from main + ~2-3 hours debug. PB2 branch preserved on origin, ready to be
rebased on the fix branch and redeployed.

**Diagnostic note for future Claude:** an earlier draft of this SCAR (now
overwritten) attributed the failure to "cross-connection visibility on Fly
ephemeral machine". That hypothesis was wrong. The bug was reproducible
locally as soon as you exercised the real `BaseMigration.apply()` path
(not the extraction helper test). Lesson: **reproduce the bug on the
real call path locally before theorizing**, especially for failures observed
only in deploy logs.

**Convention going forward:** any new SQL migration in `db/migrations_v2/`
SHOULD include a `-- === ROLLBACK ===` section. The runner now correctly
extracts the forward DDL only.

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

### Router Registration — Manifest + Parity Gate (PR #63, corrected 2026-06-13)

> CORRECTION 2026-06-13: this section previously claimed `router_registration.py`
> "reads from router_manifest.py" and "no other file needs editing" — FALSE.
> Registration is EXPLICIT imports + `include_router` calls (see scar #424:
> the fix WAS editing registration). The drift the old text declared
> "structurally impossible" happened repeatedly (#54/#55/#60, #422→#424,
> olympus/intel trio caught 2026-06-13). What IS structural now is the
> parity test below.

To add a new router (all 3 steps, same PR):

1. Create file in `backend/app/routers/`
2. Add `RouterEntry` in `backend/app/setup/router_manifest.py` with correct `process_groups`
3. Add the matching `api.include_router(...)` calls in `backend/app/setup/router_registration.py`:
   ALWAYS in `include_routers()` (monolithic = full union), PLUS
   `include_light_routers()` for `_API` and/or `include_heavy_routers()` for `_RAG`

Then run BOTH gates:

```bash
PYTHONPATH=. pytest backend/tests/setup/test_router_manifest.py \
  backend/tests/setup/test_manifest_registration_parity.py -q
```

Process groups: `_API` (light, public HTTP via main_api), `_RAG` (heavy, internal via main_rag), `_BOTH` (health checks).

**SCAR:** PRs #54/#55/#60 registered routers only in `include_routers()` (dev) but not `include_light_routers()` (prod) → silent 404s; #422 needed hotfix #424 for the same class. `test_manifest_registration_parity.py` (2026-06-13) enforces bidirectional manifest ↔ registration parity per process group — on its first run it caught `olympus.internal_router` missing from main_api prod and the `intel` trio missing from the monolithic app.

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

- File: `backend/data/bali_zero_official_prices_2026.json` (since 2026-05-06)
- Tool: `PricingTool` (Tool #2)
- Loaded by: `PricingService._load_prices()`

The 2026 schema has 9 categories vs the legacy 2025 schema's 8:
`single_entry_visas` (now includes ``C1 Tourism Extension``),
`multiple_entry_visas`, `kitas_permits`, `kitap_permits`,
`tax_accounting` (NEW — has one extra nesting level for the 4 tier
sub-blocks ``monthly_tax_basic`` / ``monthly_tax_bundled`` /
``annual_basic_packages`` / ``annual_standalone``), `company_services`,
`consultant_services` (NEW — Close PMA, NPWPD, BPJS, NPWP Personal,
Update Data, EFIN), `other_process`, `urgent_processing` (was
``urgent_services`` in 2025). The legacy `visa_extensions` category was
dropped.

Each entry now exposes `name` / `description_en` / `icon_id` /
`tier_range` (a `[low, high]` pair when there is no single `price`)
on top of the existing `price` / `duration` / `validity` / `notes`
fields. The legacy `text` markdown field is gone.

Contact metadata moved to ``metadata.contact``: ``zero@balizero.com`` /
``+62 822 3010 2328`` / ``Kerobokan`` / ``balizero.com``.

The 2025 file is kept on disk for rollback; deletion is a follow-up PR
once 2026 has run unblocked in prod for a few weeks.

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

---

## T2.7 augmentation 2026-05-23 — extracted from project root CLAUDE.md

Following content extracted during T2.7 refactor to compress root from 582→185 lines. Lives here because it's backend-rag specific and this file auto-loads when cwd is in this subtree.

### Backend Structure

```
apps/backend-rag/
├── backend/
│   ├── app/                # FastAPI app
│   │   ├── routers/        # API endpoints (HTTP routers — flat files)
│   │   ├── services/       # App-level services (CRM, auth, metrics)
│   │   ├── setup/          # app_factory, router_registration, service_initializer
│   │   ├── dependencies.py # ⚠️ Imported by ALL routers — test before deploy
│   │   └── main.py         # Entrypoint (alias for main_cloud.py)
│   ├── services/           # Core business logic (domain services, subpackages)
│   ├── channels/           # 4 live (whatsapp, telegram, instagram, web) + .disabled-2026-04-30/ (twitter — CRC broken; gchat/slack scaffolds never wired)
│   ├── core/               # Config, security, logging
│   ├── llm/                # LLM clients (Gemini, Ollama, OpenRouter)
│   ├── prompts/            # ⭐ Prompt SSOT (zantara_core.py)
│   └── migrations/         # Custom migration system (migration_NNN_*.py; runner: backend/db/migration_manager.py)
├── tests/                  # Unit + integration tests (backend/tests — separate from top-level apps/backend-rag/tests)
├── .venv/                  # ⚠️ ALWAYS .venv, not venv
└── fly.toml
```

> Absolute counts for routers / services / tests / migrations live in the DOCSYNC-marked block in project root CLAUDE.md `### Tech Stack` (auto-regenerated by `scripts/docs_sync.py`).

**IMPORTANT:** Routers in `backend/app/routers/`, NOT `backend/routers/`. Services in both `backend/services/` and `backend/app/services/`.

### Prompt Architecture

Edit ONLY `backend/prompts/zantara_core.py`. All consumers import from it.
Sections: `SECURITY_BOUNDARY` · `TOOL_USAGE_POLICY` · `SYSTEM_INSTRUCTIONS` · `KNOWLEDGE_GOVERNANCE` · `LANGUAGE_PROTOCOL` · `GREETING_RULES` · `CITATION_RULES` · `INTERNAL_MONOLOGUE` · `ESCALATION_PROTOCOL` · `CRASH_PROTOCOL` · `CLOSING_PHRASES` · `CREATOR_PERSONA` · `TEAM_PERSONA` · `ZANTARA_MASTER_TEMPLATE`

### LLM Structured Output Pattern (PR #311)

For any LLM call expected to return **structured data** (list, dict, enum, yes/no), use `client.generate_structured()` instead of prompt-engineered JSON + `try/except json.loads`. Pydantic v2 validates the response; on `ValidationError` the call retries once with the parser feedback in the prompt. Catches silent JSON-decode failures that previously fell through to fallback heuristics.

```python
from pydantic import BaseModel
from backend.llm.genai_client import get_genai_client, LLMStructuredOutputError

class GraderVerdict(BaseModel):
    reasoning: str  # ALWAYS first — forces think-before-commit
    relevant: bool
    confidence: float

client = get_genai_client()
try:
    verdict = await client.generate_structured(
        contents=prompt, response_schema=GraderVerdict, endpoint="rag.grader.X"
    )
except LLMStructuredOutputError:
    # Schema failed twice — fall back to your default heuristic.
    ...
```

OUT of scope today: KG entity extraction (deeply nested, qwen3.5 fails), Claude OAuth CLI (no SDK to wrap). Reference: [`docs/oss-injections-2026-04-26.md`](../../docs/oss-injections-2026-04-26.md).

### Observability Env Vars (PR #312)

When `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` are unset, observability is **dormant** (~1ms no-op per call). To activate on Fly:

```bash
fly secrets set -a nuzantara-rag \
  LANGFUSE_PUBLIC_KEY="<your-pk>" LANGFUSE_SECRET_KEY="<your-sk>" \
  LANGFUSE_HOST="https://us.cloud.langfuse.com"
```

Defaults are **PII-hidden** (`hide_input_messages`/`hide_output_messages` ON because Bali Zero queries contain NPWP/NIB/passport/names — UU PDP scope). Opt-in for debugging: `LANGFUSE_TRACE_LLM_MESSAGES=true`.

Per-provider kill-switch (no redeploy, takes effect on next restart):
- `LANGFUSE_INSTRUMENT_GOOGLE_GENAI=false` — disable Gemini auto-trace
- `LANGFUSE_INSTRUMENT_OPENAI=false` — disable DeepSeek/Ollama auto-trace
- `LANGFUSE_INSTRUMENT_ANTHROPIC=false` — disable Anthropic auto-trace
- `LANGFUSE_ENABLED=false` — disable everything (full kill-switch)

### Drive OAuth lifecycle

- Token in `google_drive_tokens` table — expires ~90 days
- Watchdog: `scripts/drive_token_watchdog.py` alerts 7 days before
- Re-auth: `https://kita.balizero.com/settings/integrations`

### Local AI Ollama (CRITICAL detail)

- `backend/llm/ollama_client.py` — **CRITICAL:** `think: false` for Qwen 3.5
- Models: gemma4:26b (MoE, KG/JSON), qwen3.5:9b (fast), deepseek-r1:32b (reasoning), qwen2.5vl:7b (vision)
- Vision: **qwen2.5vl:7b ONLY** (qwen3.5 Q4_K_M strips vision weights). API: `"images": [base64]`
- Pattern: Ollama local → fallback Gemini. On Fly.io: Gemini always.

### Drive Polling architecture

- Cron every 5min (`scripts/drive_poll_cron.sh`) — runs on Pro (NOT on Fly.io: auto_stop loses page_token)
- `page_token` in `system_settings` table — loss = full re-scan
- Circuit breaker: 3 failures → OPEN + Telegram alert → auto-recovery 5min
