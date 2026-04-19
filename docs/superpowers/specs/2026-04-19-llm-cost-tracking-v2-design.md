# LLM Cost Tracking v2 — Complete Coverage + Governance

**Date:** 2026-04-19
**Status:** Design approved, ready for implementation
**Author:** Claude Opus 4.7
**Feeds:** PR #107 (triple-write ledger) — extends coverage to every paid endpoint

---

## 1. Problem statement

PR #107 shipped `record_llm_call` + migration 117 (`llm_cost_events`) and
integrated **3 clients**: `genai_client` (Gemini), `deepseek_client`,
`claude_oauth_client`. Every other paid call (OpenAI embeddings, OpenRouter,
Imagen, OpenAI audio, direct Gemini bypass in KG extractor, DeepSeek HTTP
branch in Council) is **silent**: no cost telemetry, no endpoint attribution,
no invoice reconciliation. There is also no structural protection against
_new_ paid clients landing without tracking.

## 2. Goals

1. **100% paid-endpoint coverage** — every line of code that generates a USD
   charge emits one `record_llm_call` event.
2. **Structural drift prevention** — CI fails if a new client ships without
   tracking.
3. **Remote ingestion** — Pro/Air cron agents can POST cost events to
   `/api/admin/llm-costs/record`.
4. **Cost governance** — a weekly agent analyses the last 7 days and proposes
   cheaper model substitutions, with saving estimates and quality trade-offs.
5. **Local visibility** — a standalone Pro-only Next.js dashboard (port 3100,
   no Vercel, no auth) that reads directly from Postgres.

## 3. Non-goals

- Tracking Ollama (local, zero cost).
- Changing the triple-write ledger architecture (PR #107 is authoritative).
- Replacing Prometheus dashboards — this is complementary, not a substitute.
- Real-time spending caps / rate-limiting (future work, out of scope).

## 4. Architecture

### 4.1 Coverage extension (Task 1)

Six files gain `record_llm_call` integration, sharing a new helper:

**New:** `backend/services/observability/tracking_decorator.py`

```python
@llm_cost_tracked(provider="openai_embeddings", model_attr="model")
async def embed(self, texts: list[str]) -> list[list[float]]:
    ...
```

- Async-only decorator.
- Extracts `model` from a configured attribute or static value.
- Requires the wrapped function to return an object exposing
  `.usage` (`input_tokens`, `output_tokens`) OR to call the helper's
  `set_usage(input, output)` within its body via a contextvar.
- Computes `cost_usd` via `backend.services.llm_clients.pricing` — if the
  provider/model pair is unknown, falls back to `0.0` and logs a warning
  (so tracking never blocks a real call).
- Never raises.

**Integration targets (6 files):**

| File                                                                        | Provider string       | Model source           | Token source                                                       | Cost source                                                          |
| --------------------------------------------------------------------------- | --------------------- | ---------------------- | ------------------------------------------------------------------ | -------------------------------------------------------------------- |
| `core/embeddings.py` (OpenAIEmbeddingsClient)                               | `openai_embeddings`   | `self.model`           | `response.usage.prompt_tokens` (+ `input_tokens` field), no output | pricing: `$0.02 per 1M input tokens` for `text-embedding-3-small`    |
| `services/llm_clients/openrouter_client.py`                                 | `openrouter`          | from completion result | `response.usage.prompt_tokens` / `completion_tokens`               | pricing: per OpenRouter response `generation` (fetched once, cached) |
| `services/knowledge_graph/extractor_gemini.py`                              | `gemini` (refactored) | —                      | —                                                                  | — (via `genai_client` refactor, see §4.1.1)                          |
| `services/visual/imagen_client.py`                                          | `imagen`              | ImagenQuality.model_id | `input_tokens=len(prompt)//4` est, `output_tokens=0`               | per-image flat: ULTRA=$0.06, STANDARD=$0.04, FAST=$0.02              |
| `app/services/audio_service.py` (OpenAI path only)                          | `openai_audio`        | `tts-1`/`whisper-1`    | estimated (see §4.1.2)                                             | pricing: TTS $15/1M char, Whisper $0.006/min                         |
| `services/council/cli_runners.py` (DeepSeek HTTP + Gemini API-key branches) | `deepseek` / `gemini` | from args              | from response                                                      | pricing module                                                       |

**Per 4.1.1 — extractor_gemini refactor**

`GeminiKGExtractor.__init__` currently does `from google import genai` and
`genai.Client(...)`. Refactored to delegate to `get_genai_client()` from
`backend.llm.genai_client`. This eliminates the duplicate SDK surface and
inherits tracking automatically (no bespoke `record_llm_call` needed).
Net delete: ~40 lines of auth/client boilerplate.

**Per 4.1.2 — audio token estimation**

Whisper STT bills by **audio duration** (minutes), not tokens. Convention:

- `input_tokens = int(duration_seconds)` (1 token = 1 second of audio, for
  dashboard legibility)
- `output_tokens = len(transcript_text) // 4` (standard 4-char token proxy)
- `cost_usd` from pricing module (authoritative)

TTS: `input_tokens = len(input_text)`, `output_tokens = 0`, cost from char
count.

Audio is the only endpoint where tokens are an estimation. Documented in
recorder comment; **no schema change** (existing `input_tokens` INT field is
overloaded with a note in pricing/provider combination).

### 4.2 CI enforcer (Task 1.2)

**New:** `scripts/check_llm_cost_tracking.py`

Scans two directory roots:

- `apps/backend-rag/backend/llm/`
- `apps/backend-rag/backend/services/llm_clients/`
- `apps/backend-rag/backend/services/visual/`
- `apps/backend-rag/backend/services/knowledge_graph/extractor_*.py`
- `apps/backend-rag/backend/services/council/cli_runners.py`
- `apps/backend-rag/backend/app/services/audio_service.py`
- `apps/backend-rag/backend/core/embeddings.py`

For each file, applies three classifiers:

1. **LLM-client detector** — imports `anthropic`/`openai`/`google.genai` OR
   `httpx.post` URL contains one of: `api.openai.com`, `api.deepseek.com`,
   `openrouter.ai/api`, `generativelanguage.googleapis`, `api.anthropic.com`.
2. **Tracking detector** — file contains `record_llm_call` OR
   `@llm_cost_tracked`.
3. **Whitelist** — static list of files explicitly exempted (infra, proxy,
   Ollama). One line per entry with a reason comment.

Fails CI (exit 1) if a file matches #1 but not #2 and not #3.

**CI wiring:** new step in `.github/workflows/tests.yml`, job `unit-tests`,
before the pytest invocation. Blocking.

### 4.3 Remote ingestion endpoint (Task 1.3)

**New:** `apps/backend-rag/backend/app/routers/llm_costs.py`

Single endpoint:

```
POST /api/admin/llm-costs/record
Authorization: Bearer <admin-JWT>
Content-Type: application/json

{
  "provider": "gemini",
  "model": "gemini-flash-3.0-preview",
  "input_tokens": 1234,
  "output_tokens": 567,
  "cost_usd": 0.000891,
  "success": true,
  "latency_ms": 412,
  "endpoint": "cron.intel_scraper",
  "request_id": "air-cron-2026-04-19T04:30Z",
  "error_class": null
}
```

- `require_admin` dependency (existing).
- Validates all 8 required fields; returns 422 on missing.
- Calls `record_llm_call` internally, returns the 3-sink result dict.
- Registered in `router_manifest.py` under `_API` process group, tags
  `("observability","admin")`.

### 4.4 Cost advisor agent (Task 2)

**New:** `backend/services/observability/cost_advisor.py`

**Data model:**

```python
@dataclass(frozen=True)
class EndpointCostSummary:
    endpoint: str
    model: str
    provider: str
    call_count: int
    total_cost_usd: Decimal
    avg_cost_per_call_usd: Decimal
    p50_latency_ms: int
    p95_latency_ms: int
    success_rate: float

@dataclass(frozen=True)
class CostRecommendation:
    endpoint: str
    current_model: str
    proposed_model: str
    estimated_monthly_saving_usd: Decimal
    quality_tradeoff: str       # short human-readable explanation
    confidence: Literal["low", "medium", "high"]
    spike_flag: bool            # True if current period >3x baseline
```

**Core class:**

```python
class CostAdvisor:
    def __init__(self, *, pg_pool, oauth_client: ClaudeOAuthClient): ...

    async def analyze_last_window(
        self, days: int = 7
    ) -> list[EndpointCostSummary]: ...

    async def detect_spikes(
        self, summaries: list[EndpointCostSummary], baseline_days: int = 28
    ) -> set[str]: ...

    async def propose_substitutions(
        self, top_n: int = 5
    ) -> list[CostRecommendation]: ...
```

**LLM-judge prompt (propose_substitutions):**

Takes top-N endpoints by total cost, passes to Claude OAuth Max with the
following structure:

- Input: list of `(endpoint, current_model, call_count, total_cost_usd,
median_input_tokens, median_output_tokens)`.
- Prompt asks for one JSON array of suggestions, each with `proposed_model`,
  `estimated_monthly_saving_usd`, `quality_tradeoff`, `confidence`.
- Guardrails in system prompt: "Only suggest models available on providers
  already integrated in Nuzantara (Gemini/DeepSeek/Claude OAuth). Do NOT
  suggest OpenAI GPT-4 unless current endpoint already uses OpenAI."
- Output validated against pydantic schema, rejected and retried once on
  malformed JSON.

**Spike rule:** For each endpoint, compare `last_7d_cost` to
`trailing_28d_avg_weekly_cost`. If ratio > 3.0 → `spike_flag=True` AND the
recommendation's `confidence` is pinned to `"high"` (it's a regression to
investigate, not a cost optimization).

**Persistence:** migration 118.

**New:** `backend/migrations/migration_118_cost_recommendations.py`

```sql
CREATE TABLE llm_cost_recommendations (
    id                          BIGSERIAL PRIMARY KEY,
    ts_utc                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    endpoint                    VARCHAR(128) NOT NULL,
    current_model               VARCHAR(128) NOT NULL,
    proposed_model              VARCHAR(128) NOT NULL,
    estimated_monthly_saving_usd NUMERIC(12,6) NOT NULL,
    quality_tradeoff            TEXT NOT NULL,
    confidence                  VARCHAR(16) NOT NULL
        CHECK (confidence IN ('low','medium','high')),
    spike_flag                  BOOLEAN NOT NULL DEFAULT FALSE,
    status                      VARCHAR(16) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','reviewed','applied','rejected')),
    reviewed_at                 TIMESTAMPTZ,
    reviewed_by                 VARCHAR(128),
    notes                       TEXT
);
CREATE INDEX idx_llm_cost_reco_status_ts ON llm_cost_recommendations (status, ts_utc DESC);
CREATE INDEX idx_llm_cost_reco_endpoint ON llm_cost_recommendations (endpoint, ts_utc DESC);
```

**CLI:**

**New:** `backend/scripts/cost_advisor_cli.py`

- `PYTHONPATH=. python -m backend.scripts.cost_advisor_cli run`
- Calls `analyze_last_window(7)` + `propose_substitutions(5)`.
- Persists recommendations (UPSERT on `endpoint+current_model+proposed_model`
  within 7 days — no dupes from re-runs).
- Generates Markdown report:
  ```
  ## Weekly LLM Cost Report — YYYY-MM-DD
  **Total spend (last 7d):** $X.XX (Δ vs prior week: +Y%)
  **Anomalies:** N spikes detected
  ### Top 3 recommendations
  1. endpoint=X, current=Y → propose=Z, save ~$N/mo (confidence)
     Trade-off: ...
  ```
- Sends via existing `/api/notifications/send-email`-style Telegram pattern
  (Brevo `zantara@balizero.com` → chat_id `1125336968`).

**Schedule:** Pro launchd, Monday 07:00 WITA. Use existing
`~/Library/LaunchAgents/com.nuzantara.cron.plist` conventions. Add a new
entry (no systemd, this is Pro macOS).

**Governance constants (hard-coded):**

```python
DAILY_SPEND_ALERT_THRESHOLD_USD = Decimal("20.00")
SPIKE_MULTIPLIER = 3.0
BASELINE_WINDOW_DAYS = 28
```

Daily alert is a separate cron (08:00 WITA) that queries yesterday's total
and pages Telegram if > threshold. Same script, flag `--check-daily-cap`.

### 4.5 Local UI (Task 3)

**New dir:** `apps/admin-dashboard-local/`

Structure:

```
apps/admin-dashboard-local/
├── package.json              # Next.js 16, tailwind, port 3100
├── next.config.js            # LOCAL_ONLY guard
├── tsconfig.json
├── tailwind.config.ts
├── .gitignore
├── .env.example              # DATABASE_URL_LOCAL, FLY_TUNNEL_URL
├── app/
│   ├── layout.tsx
│   ├── page.tsx              # redirect → /cost-dashboard
│   ├── cost-dashboard/
│   │   └── page.tsx          # main view
│   ├── api/
│   │   └── llm-costs/
│   │       ├── kpi/route.ts           # today/7d/30d totals
│   │       ├── timeline/route.ts      # daily stacked by provider
│   │       ├── top-endpoints/route.ts # top 10 by cost
│   │       ├── model-mix/route.ts     # tokens by provider
│   │       ├── recommendations/route.ts # GET + PATCH
│   │       └── anomalies/route.ts     # active spikes
│   └── lib/
│       ├── db.ts             # pg pool with fallback detection
│       └── queries.ts        # pure SQL, read-only
└── components/
    ├── CostKpiCards.tsx
    ├── CostTimeline.tsx
    ├── TopEndpoints.tsx
    ├── ModelMix.tsx
    ├── RecommendationPanel.tsx
    └── AnomalyBanner.tsx
```

**DB access:**

- Primary: `DATABASE_URL_LOCAL=postgresql://...@localhost:5432/nuzantara`.
- Fallback: if `fly proxy` is running on 15432, uses `FLY_TUNNEL_URL` instead.
- Auto-detection in `lib/db.ts` — tries local, falls back to tunnel, logs
  which one it used.
- All queries **read-only** except `PATCH /recommendations/:id` which updates
  `status='reviewed'` + `reviewed_by='local'` + `reviewed_at=NOW()`.

**UI framework choice:** **Recharts** for all charts (Next.js-friendly, no
Canvas), Tailwind for layout. Same stack as `apps/admin-dashboard/` so Zero
recognizes the codebase.

**Deploy/run script:**

**New:** `scripts/start-cost-dashboard.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)/apps/admin-dashboard-local"
export LOCAL_ONLY=1
npm run dev -- --port 3100 &
SERVER_PID=$!
sleep 2
open "http://localhost:3100/cost-dashboard"
wait $SERVER_PID
```

No Fly config. No Vercel config. Explicit `LOCAL_ONLY=1` env var checked at
runtime; if absent, server refuses to start (guard against accidental
deployment).

## 5. Testing strategy

**TDD for all new code. Coverage ≥ 40% on new files.**

### 5.1 Unit tests

- `test_tracking_decorator.py` — decorator wraps fn, records on success +
  failure, never raises, handles missing `.usage`.
- `test_cost_advisor.py` — `analyze_last_window` aggregation, spike
  detection, prompt-building, pydantic validation of LLM judge output,
  UPSERT dedup.
- `test_check_llm_cost_tracking.py` — fixture files that should/shouldn't
  trip the enforcer; ensure whitelist works; ensure exit code is 1 on
  violation.
- `test_llm_costs_router.py` — endpoint validates fields, requires admin
  auth, propagates result dict.
- `test_migration_118.py` — apply + rollback cycle against a test PG.

### 5.2 Integration tests

- `test_cost_advisor_cli_integration.py` — end-to-end CLI run against a
  fixture `llm_cost_events` table; verifies Markdown output shape and DB
  state after.
- `test_remote_ingestion_integration.py` — POST event, read back from
  `llm_cost_events`.

### 5.3 UI tests

Local dashboard is deliberately lightweight; **one integration test** that
boots the Next dev server with a fake DB URL and asserts the 6 route handlers
return 200 with expected JSON shape. Visual components untested (would
require Playwright overhead not worth it for a Pro-only tool).

### 5.4 TDD cycle per file

For each of the 6 missing-tracking files:

1. RED: write `test_X_records_cost_on_success` + `test_X_records_cost_on_failure`.
2. Verify both FAIL (pattern `record_llm_call.assert_awaited` against a
   patched recorder).
3. GREEN: add `@llm_cost_tracked` or direct `record_llm_call` call.
4. Verify both PASS.
5. Refactor if needed.

## 6. Rollout sequence

**Branch strategy:** single feature branch
`feat/llm-cost-tracking-v2-complete` for Phases B+C, separate branch
`feat/llm-cost-ui-local` for Phase D (keeps Fly-touching vs Pro-only scopes
clean for review).

**Checkpoint after each phase** — report to Zero, wait for OK.

### Phase B (2-3h) — Coverage + enforcer + remote endpoint

1. Create `tracking_decorator.py` + tests.
2. Refactor `extractor_gemini.py` to use `genai_client` + tests.
3. Integrate the 5 remaining files one by one with TDD.
4. Write `scripts/check_llm_cost_tracking.py` + tests + CI wiring.
5. Write `llm_costs.py` router + register + tests.
6. Run full `pytest backend/tests/ -q --cov=backend --cov-fail-under=40`.
7. Commit + push + open draft PR.

### Phase C (2-4h) — Cost advisor

1. Migration 118 + apply test.
2. `cost_advisor.py` (dataclasses first, then analyze, then spike detect,
   then LLM judge) — each step TDD.
3. `cost_advisor_cli.py` + integration test.
4. Launchd plist entry + doc.
5. Daily cap cron flag (`--check-daily-cap`) + separate launchd entry
   Mon-Sun 08:00 WITA.
6. Commit to same branch, push.

### Phase D (2-3h) — Local UI

1. New branch `feat/llm-cost-ui-local` from main.
2. Scaffold Next.js 16 app with LOCAL_ONLY guard (check in
   `next.config.js` `async rewrites()` — throws on cold-start if
   `process.env.LOCAL_ONLY !== "1"`).
3. Write `lib/db.ts` with tunnel fallback + unit test.
4. Write 6 route handlers + integration test.
5. Compose 6 components + dashboard page.
6. `start-cost-dashboard.sh`.
7. Smoke test: `bash scripts/start-cost-dashboard.sh`, verify loads at
   `http://localhost:3100/cost-dashboard`.
8. Commit, push, **no PR merge to main until Zero approves** (it's a dev
   tool, but we still want the repo to have it).

## 7. Risks & mitigations

| Risk                                                      | Mitigation                                                                               |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Enforcer false-positives on future legitimate infra files | Explicit whitelist file, documented reason per entry.                                    |
| Cost advisor hallucinates model names                     | Pydantic schema validates against a known-providers enum; unknown = reject.              |
| LLM-as-judge cost itself spirals                          | Cap input at 5 endpoints × 10 fields = ~500 tokens prompt; 1 call/week; cost ~$0.001.    |
| Audio token estimation drift vs real billing              | Audio volume is low; reconciliation note in docs; acceptable drift.                      |
| Migration 118 collision with ongoing PR                   | Confirmed 2026-04-19: 115/116 free as Python (used only in SQL v2); 118 free both sides. |
| Local UI accidentally deployed                            | `LOCAL_ONLY=1` runtime check + no vercel.json + no fly.toml.                             |
| Tracking decorator slows hot path                         | Decorator overhead ≤ 1ms (measured on existing 3 integrations); negligible.              |

## 8. Durable constraints (from project memory)

- **Never set `ANTHROPIC_API_KEY`** — Claude via OAuth Max only
  (`feedback_claude_oauth_only.md`).
- **Never use `logger` → `print()`** — but this design doesn't touch logging
  anyway.
- **No deploy Fly without pre-deploy checklist** (CLAUDE.md §11). Phase B+C
  will deploy via the normal checklist.
- **No force-push to main**. All work on feature branches with PRs.
- **Local UI is NOT a deploy target** — scaffolded, committed, but no Fly/
  Vercel config.
- **Migration convention:** support `-- === ROLLBACK ===` marker
  (`migration_117` already conforms; 118 will too). Scar 2026-04-19 fix in
  `migration_base.py` must remain on main.

## 9. Open questions (resolved 2026-04-19 with Zero)

1. ~~Refactor `extractor_gemini.py` or add bespoke recorder?~~ → **Refactor
   via `genai_client`.**
2. ~~Introduce `@llm_cost_tracked` decorator?~~ → **Yes.**
3. ~~Image/audio in same `llm_cost_events` table or separate?~~ → **Same
   table, `provider` discriminates.**
4. ~~Weekly report timing?~~ → **Monday 07:00 WITA, Telegram chat_id 1125336968.**
5. ~~How to determine Gemini CLI branch in Council runners?~~ → **Inspect
   subprocess args at runtime: if `GEMINI_API_KEY` env is set, track;
   otherwise (Max OAuth path) skip.**
