---
date: 2026-05-27
domain: wr2
client_case: autonomous-workflow-spec
sources:
  - research/wr2/2026-05-27-cluster-c-modules-verify.md (Agent A.1 empirical)
  - research/wr2/2026-05-27-ig-layer-verify.md (Agent A.2 empirical)
  - research/wr2/2026-05-27-claude-print-capabilities.md (Agent A.3 empirical)
  - research/wr2/2026-05-26-wr2-cron-audit.md (sessione precedente)
  - Gemini 3.1 Pro panel verdict (/tmp/wr2-panel-gemini.md)
  - DeepSeek V4 Pro reasoning panel (/tmp/wr2-panel-deepseek.json)
  - NB-7 Editorial f51ab8a0-50d0-49f1-a64f-ebc131fed7b8 (Bali Zero governance)
  - Codex GPT-5.5 panel (/tmp/wr2-panel-codex.md)
  - Empirical disk audit 35 LaunchAgent com.balizero.wr2.*
---

# WR2 Autonomous Carousel Workflow — Architecture Spec (post 4-LLM panel)

**Status**: SHIPPABLE post-FIXES (overall risk 4.5/10 Gemini, 8/10 DeepSeek prima delle amendments — target 4/10 post-amendments)
**Scope**: ESTESO — carousel workflow + IG canonicalization gap closure + Cluster C event-driven re-evaluation
**Date**: 2026-05-27
**Author**: Claude Opus 4.7 orchestrator session (worktree `wr2-wr2-spec-2026-05-27`)
**Approver**: Antonello (operator) — pending sign-off

---

## 0. Critical context corrections post-FASE A empirica

| Premessa originaria                            | Realtà empirica (FASE A)                                                                                                                                      | Implicazione spec                                                                         |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Cluster C = 6 moduli scaffold/orfani da retire | TUTTI 6 VALID + live-wired in 6 plist cron                                                                                                                    | NO retire. Re-evaluation event-driven (B.7) opzionale.                                    |
| `claude --print` non supporta subagent         | `--agent <name>` carica subagent .md verbatim                                                                                                                 | Python orchestrator sottile (subprocess), NO duplicazione prompt.                         |
| Greenfield workflow                            | 35 plist `com.balizero.wr2.*` GIA' esistenti (topic-selector, draft-generator, image-generator, fact-checker, fact-extractor, queue-server, supervisor, ecc.) | **Spec è REFACTOR + GAP CLOSURE, non greenfield**.                                        |
| IG layer ready                                 | `ig_publisher.py` 313 LOC complete MA zero non-test caller                                                                                                    | Wiring NEW: service_initializer registration + plist publisher + token rotation watchdog. |

**Output dir CORREZIONE DeepSeek**: NON `~/.claude/skills/bali-zero-brand/_carousels-by-session/` (contamina skill cortex). USA `~/.claude/carousels/<session-id>/`.

---

## 1. Architecture diagram (B.1 post-panel)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          WR2 AUTONOMOUS CAROUSEL                         │
│                  (cron 3x/wk Lun-Mer-Ven 06:00 WITA)                     │
└─────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────┐         ┌─────────────────────────┐
  │ topic-selector cron  │────────▶│ wr2_topics (PG table)   │
  │ (EXISTING healthy)   │         │ status=pending          │
  └──────────────────────┘         └─────────────────────────┘
              │                                │
              │ PG NOTIFY topic_ready          │ supervisor LISTENs
              ▼                                ▼
  ┌─────────────────────────────────────────────────────────┐
  │  wr2_supervisor.py (EXISTING) → consume 1 topic at a time│
  │  triggers: wr2_carousel_orchestrator.py (NEW)            │
  └─────────────────────────────────────────────────────────┘
              │
              ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │ scripts/wr2_carousel_orchestrator.py (NEW, Python subprocess)    │
  │                                                                   │
  │  ┌───────────────────────────────────────────────────────────┐  │
  │  │ 0. agent_start.py --lane wr2-run --task-id carousel-<id>   │  │
  │  │ 1. brief-interpreter  (claude --print --agent <name>)      │  │
  │  │ 2. storyboarder       (claude --print --agent <name>)      │  │
  │  │ 3. image-prompt-author (claude --print --agent <name>)     │  │
  │  │ 4. layout-composer    (claude --print --agent <name>)      │  │
  │  │ 5. critic gate PASS/FAIL/RETRYABLE_FAIL retry max 2        │  │
  │  │ 6. Playwright render PNG 1080x1350 IG 4:5 + cover          │  │
  │  │ 7. cleanup_temp_assets (Gemini amendment)                  │  │
  │  └───────────────────────────────────────────────────────────┘  │
  │                                                                   │
  │  Output: ~/.claude/carousels/<session-id>/{slides/,brief.json,   │
  │          storyboard.json,critic-verdict.json}                     │
  │                                                                   │
  │  State: PG wr2_carousel_runs (NEW table, migration 197+)         │
  │  Idempotency: pg_try_advisory_lock(hash(carousel_id))             │
  └──────────────────────────────────────────────────────────────────┘
              │
              ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │ wr2_telegram_publish_gate.py (NEW, KeepAlive plist)              │
  │                                                                   │
  │ POST Telegram inline button + signed manual_publish_token         │
  │ (Codex amendment: NOT just "message sent"=approval — token        │
  │  single-use, expiring 24h, bound to content_hash)                 │
  └──────────────────────────────────────────────────────────────────┘
              │
       ┌──────┴──────┐
       │             │
   approved      rejected
       │             │
       ▼             ▼
  ┌─────────┐  ┌──────────────────────┐
  │ Insert  │  │ archive draft         │
  │publish_ │  │ increment reject_count│
  │attempts │  │ NO retry              │
  │table    │  └──────────────────────┘
  │(NEW)    │
  └─────────┘
       │
       ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │ ig_publisher.py (EXISTING complete code, NEW caller)             │
  │ Meta Graph v20: child × N + parent + publish + permalink         │
  │ Per Codex: write publish_attempts BEFORE Meta call; update       │
  │ container_created → published → recorded                          │
  └──────────────────────────────────────────────────────────────────┘
              │
              ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │ POST-PUBLISH event PG NOTIFY: carousel_published                 │
  │  → strategos consumer (Cluster C event-driven optional)          │
  │  → newsletter weekly aggregate consumer (B.7)                    │
  │  → ig_graph_sensor scheduled metric collection (EXISTING)        │
  └──────────────────────────────────────────────────────────────────┘
```

### 1.1 Components STATUS empirical map

| Component                                                                 | Status                                  | Action                                         |
| ------------------------------------------------------------------------- | --------------------------------------- | ---------------------------------------------- |
| `topic-selector` plist + script                                           | EXISTING healthy                        | Keep, no change                                |
| `wr2_supervisor.py` PG NOTIFY listener                                    | EXISTING (cicatrix W47 keepalive fixed) | Keep, extend dispatch to orchestrator          |
| `wr2_carousel_orchestrator.py`                                            | **NEW**                                 | Write                                          |
| `wr2_telegram_publish_gate.py`                                            | **NEW**                                 | Write + KeepAlive plist                        |
| `bali-zero-brand` skill cortex                                            | EXISTING                                | Pass via `--add-dir` (copy to /tmp workspace)  |
| 8 subagent `.md` in `~/.claude/agents/wr2-*.md`                           | EXISTING (CLI dispatch verified A.3)    | Keep verbatim                                  |
| `ig_publisher.py` (313 LOC)                                               | EXISTING complete, ZERO caller          | Wire via orchestrator post-approval            |
| `ig_graph_sensor.py` (153 LOC)                                            | EXISTING                                | Keep, no change                                |
| `wr2_carousel_runs` PG table                                              | **NEW migration**                       | Create migration 197+                          |
| `wr2_publish_attempts` PG table                                           | **NEW migration** (Codex amendment)     | Create migration 198+                          |
| `wr2_carousel_events_outbox` PG table (DeepSeek STRONG REJECT-mitigation) | **NEW migration**                       | Create migration 199+ for Cluster C decoupling |

---

## 2. Token/quota management (B.2 post-panel — Claude OAuth MAX 2 plan)

**Setup reale**: Claude OAuth MAX (2× plan x20). Quota FLAT, NON pay-per-token. I costi $/run figurativi nella §11 sono AUDIT METRICS (detect runaway/loop), NON spesa effettiva. La vera throttle metric è **MAX usage rolling 5h window**.

### 2.1 Pre-flight + quota-based throttle

```python
# Once at orchestrator startup (DeepSeek amendment: NOT per-step)
def preflight_claude_auth():
    r = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True, timeout=10)
    if r.returncode != 0 or "not authenticated" in r.stdout.lower():
        telegram_alert("WR2 orchestrator: claude --print not authenticated, exit 75")
        sys.exit(75)  # launchd retry after ThrottleInterval

# Quota-based throttle (read da claude-max-usage-watcher.py existing)
def quota_throttle_check():
    usage_5h = read_max_usage_pct()  # 0-100 da watchdog existing
    if usage_5h > 70:
        logger.warning(f"MAX usage_5h={usage_5h}%, deferring 30min")
        time.sleep(1800)
        return quota_throttle_check()  # re-check
    return True

# Budget figurativo per AUDIT (detect runaway, NOT throttle)
AUDIT_BUDGET_PER_RUN_USD = 5.00  # hard cap, alert se superato
AUDIT_BUDGET_PER_MONTH_USD = 10.00  # warn se superato, headroom event-driven

# Global subprocess circuit breaker (Codex amendment)
MAX_CLAUDE_INVOCATIONS_PER_DRAFT = 8  # 5 steps + 2 critic retries + 1 buffer
MAX_CLAUDE_INVOCATIONS_PER_HOUR = 50
```

### 2.2 Cascade fallback explicit mapping (Antonello 2026-05-27 — opus su brief/story/critic, sonnet su image/layout)

| Step                             | Tier 1 (Claude OAuth MAX) | Tier 2 fallback | Tier 3 fallback | Tier 4                 |
| -------------------------------- | ------------------------- | --------------- | --------------- | ---------------------- |
| brief-interpreter                | **claude-opus-4-7**       | gemini agy      | DeepSeek V4 Pro | NO Ollama (creative)   |
| storyboarder                     | **claude-opus-4-7**       | gemini agy      | DeepSeek V4 Pro | NO Ollama              |
| image-prompt-author              | **claude-sonnet-4-6**     | gemini agy      | NO              | NO Ollama              |
| layout-composer                  | **claude-sonnet-4-6**     | gemini agy      | DeepSeek V4 Pro | NO Ollama (structured) |
| critic                           | **claude-opus-4-7**       | gemini agy      | DeepSeek V4 Pro | NO Ollama (judgment)   |
| (validation/parsing/JSON checks) | NO LLM (Python)           | —               | —               | qwen3.5:9b OK          |

**Cascade kick-in policy**:

- `usage_5h > 90%` → cascade Tier 2 (preserva quota MAX per altri workflow)
- `quota_exhausted error` → cascade Tier 2 immediato
- 2 carousel run consecutivi che triggerano cascade → Telegram alert "MAX quota saturation strutturale, investigate"

### 2.3 Subprocess wrapper template (A.3 empirical, applied)

```python
def call_subagent(agent_name: str, user_prompt: str, model: str, budget: float) -> dict:
    # Pre-flight: subagent file must exist (Pitfall #1)
    agent_path = Path(f"~/.claude/agents/{agent_name}.md").expanduser()
    if not agent_path.is_file():
        raise RuntimeError(f"Subagent {agent_name} not found")

    # cwd /tmp (Pitfall #2: avoid CLAUDE.md context overflow)
    # env strip ANTHROPIC_API_KEY (CLAUDE.md §5 ban)
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

    r = subprocess.run(
        ["claude", "--print", "--agent", agent_name,
         "--model", model, "--output-format", "json",
         "--max-budget-usd", f"{budget:.2f}",
         "--no-session-persistence",
         "--exclude-dynamic-system-prompt-sections",
         user_prompt],
        cwd="/tmp", env=env,
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        raise RuntimeError(f"claude --print failed exit {r.returncode}: {r.stderr[:500]}")

    payload = json.loads(r.stdout)
    if payload.get("is_error"):
        raise RuntimeError(f"claude payload is_error: {payload.get('error_message', '')}")

    return payload  # contains response, token_usage, cost
```

---

## 3. State machine + idempotency (B.3 post-panel)

### 3.1 Tabella `wr2_carousel_runs` (NEW migration 197)

```sql
CREATE TABLE wr2_carousel_runs (
    carousel_id UUID PRIMARY KEY,
    topic TEXT NOT NULL,
    topic_hash TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'drafted','brief_done','storyboard_done','layout_done',
        'critic_pass','rendered','awaiting_approval',
        'approved','rejected','published','failed_cascade','stale_abandoned'
    )),
    state_updated_at TIMESTAMPTZ DEFAULT now(),
    session_id TEXT NOT NULL,  -- worktree path identifier
    cost_total_usd NUMERIC(10,4) DEFAULT 0,
    retry_count INT DEFAULT 0,
    last_error TEXT,
    output_dir TEXT,  -- ~/.claude/carousels/<session-id>/
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX idx_carousel_topic_hash_active ON wr2_carousel_runs(topic_hash)
    WHERE state NOT IN ('published','rejected','failed_cascade','stale_abandoned');
CREATE INDEX idx_carousel_stale ON wr2_carousel_runs(state_updated_at)
    WHERE state IN ('drafted','brief_done','storyboard_done','layout_done','critic_pass','rendered');
```

### 3.2 Tabella `wr2_publish_attempts` (NEW migration 198 — Codex amendment)

```sql
CREATE TABLE wr2_publish_attempts (
    id BIGSERIAL PRIMARY KEY,
    carousel_id UUID REFERENCES wr2_carousel_runs(carousel_id),
    platform TEXT NOT NULL CHECK (platform IN ('instagram','facebook','linkedin')),
    content_hash TEXT NOT NULL,  -- sha256 di slides+caption
    state TEXT NOT NULL CHECK (state IN (
        'planned','container_created','published','recorded','failed','blocked_manual_gate'
    )),
    provider_response JSONB,  -- raw Meta Graph response per step
    idempotency_key TEXT UNIQUE NOT NULL,  -- carousel_id||platform||content_hash
    manual_publish_token TEXT,  -- signed by Telegram operator bot
    token_expires_at TIMESTAMPTZ,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### 3.3 Idempotency con advisory lock

```python
async def acquire_carousel_lock(conn, carousel_id: str) -> bool:
    lock_key = hash(carousel_id) & 0x7FFFFFFFFFFFFFFF  # int8 positive
    r = await conn.fetchval("SELECT pg_try_advisory_lock($1)", lock_key)
    return r

async def release_carousel_lock(conn, carousel_id: str):
    lock_key = hash(carousel_id) & 0x7FFFFFFFFFFFFFFF
    await conn.execute("SELECT pg_advisory_unlock($1)", lock_key)
```

### 3.4 ACID transitions (Gemini amendment)

```python
async def transition_state(conn, carousel_id, new_state, output_artifact_path):
    async with conn.transaction():
        # Only commit DB state AFTER file is written + flushed
        with open(output_artifact_path, 'w') as f:
            json.dump(payload, f)
            f.flush()
            os.fsync(f.fileno())
        await conn.execute(
            "UPDATE wr2_carousel_runs SET state=$1, state_updated_at=now() WHERE carousel_id=$2",
            new_state, carousel_id
        )
```

---

## 4. Worktree isolation (B.4 post-panel)

- Ogni run: `python scripts/agent_start.py --lane wr2-run --task-id carousel-<carousel_id>`
- Inherits `agent_start.py` lease + worktree machinery (existing)
- **CRITICAL** (DeepSeek amendment): worktree inherits CLAUDE.md from repo root (~50k token). Per evitare overflow nel subagent:
  - Pass `cwd="/tmp"` quando si invoca `claude --print` (A.3 Pitfall #2)
  - Skill cortex `bali-zero-brand` deve essere COPIATO in `/tmp/wr2-skills-<carousel_id>/` e passato via `--add-dir`
- **NEW cleanup cron** `com.balizero.wr2.worktree-gc.daily` (08:00 WITA): rimuove `.worktrees/wr2-run-carousel-*` con age >24h
- **Output dir** (DeepSeek correction): `~/.claude/carousels/<session-id>/` (NON dentro skills/)

---

## 5. Observability (B.5 post-panel — APPROVE_AS_IS)

### 5.1 Daily watchdog `scripts/wr2-daily-health.sh` (NEW, cron 08:00 WITA)

Output Telegram esempio:

```
WR2 fleet health 2026-05-27 08:00 WITA
- Live cron: 35 LaunchAgent (33 healthy / 2 degraded)
- Carousel runs last 7d: 9 drafted, 8 published, 1 rejected
- Avg cost/run: $0.18
- Stuck runs >2h: 0
- IG token expires: 47d remaining
- Last published: 2026-05-26 21:32 WITA (kbli-pma-2025)
```

### 5.2 Metrics persistence

- Per-step: latency_ms, tokens_in/out, cost_usd, retry_count → `wr2_orchestrator_metrics` (NEW migration 200) OR extend existing `observability.*` if presente
- Aggregation: daily rollup view `mv_wr2_daily_stats` (refresh 07:55 WITA)
- Alert thresholds:
  - cost/run > $0.50 → WARNING
  - stuck state > 2h → CRITICAL (Telegram)
  - ship_rate weekly < 70% → WARNING

---

## 6. Failure modes (B.6 post-panel)

| Failure                                        | Detection                                    | Action                                                                                   |
| ---------------------------------------------- | -------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `claude --print` quota exhausted (Tier 1)      | grep stdout "out of extra usage\|quota\|429" | Cascade Tier 2 (gemini agy)                                                              |
| Tutta cascade fallita                          | All 3 tier exit 1                            | state → `failed_cascade` + Telegram + STOP (Gemini amendment)                            |
| Critic FAIL 2x                                 | retry_count >= 2                             | state → `failed_cascade` + Telegram + STOP, NO ship                                      |
| Playwright render fail                         | exit non-0                                   | retry once con headless config alternativo                                               |
| JSON malformed da claude --print               | json.JSONDecodeError                         | NO state transition, retry once, then fail (DeepSeek amendment)                          |
| Subagent .md modificato mid-session            | hash check load-time vs cached               | Alert + STOP (DeepSeek amendment)                                                        |
| IG publish parziale (container OK, publish KO) | publish_attempts state inconsistent          | Reconciliation loop (Codex amendment): resume from last durable step                     |
| IG publish OK, DB record KO                    | Meta response logged, DB INSERT failed       | Reconciliation by `idempotency_key`: query Meta `/me/media?since=`, dedup by IG media_id |
| Telegram bot down                              | aiohttp ClientConnectorError                 | Draft persiste in `awaiting_approval`, retry polling ogni 60s, alert se >1h down         |
| Stuck `awaiting_approval` >7d                  | watchdog query                               | Auto-transition `stale_abandoned` + Telegram digest                                      |

---

## 7. Cluster C re-evaluation (B.7 — DeepSeek STRONG REJECT mitigation)

**Verdict finale (sintesi panel)**: NON convertire i 6 moduli a event-driven diretto. **USA outbox pattern** (DeepSeek raccomandazione, mitiga rischio cascading failures).

### 7.1 Design `wr2_carousel_events_outbox` (NEW migration 199)

```sql
CREATE TABLE wr2_carousel_events_outbox (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'carousel_published','carousel_rejected','carousel_failed','topic_consumed'
    )),
    carousel_id UUID REFERENCES wr2_carousel_runs(carousel_id),
    payload JSONB NOT NULL,
    consumed_by JSONB DEFAULT '[]'::jsonb,  -- array di consumer name che hanno consumed
    created_at TIMESTAMPTZ DEFAULT now(),
    pruned_at TIMESTAMPTZ
);
CREATE INDEX idx_carousel_outbox_unconsumed ON wr2_carousel_events_outbox(created_at)
    WHERE pruned_at IS NULL;
```

### 7.2 Per-consumer mapping

| Module                 | Pattern                                                      | Trigger                                                                 | Rationale                                                 |
| ---------------------- | ------------------------------------------------------------ | ----------------------------------------------------------------------- | --------------------------------------------------------- |
| `connector_cli`        | Pre-carousel cron (existing)                                 | Hourly                                                                  | Continua come oggi, fornisce topic raw a topic-selector   |
| `oracle_cli`           | Cron weekly (existing)                                       | Tuesday 09:00                                                           | Strategic council, NO cambio                              |
| `strategos_cli`        | **NEW outbox consumer**                                      | Polling outbox `carousel_published` every 15min                         | Post-publish strategic synthesis                          |
| `newsletter_cli`       | Cron weekly independent (no refactor — Antonello 2026-05-27) | Monday 06:00                                                            | News standalone, carousel link in menu inferiore OPTIONAL |
| `learner_cli`          | **NEW outbox consumer** (Antonello 2026-05-27)               | Polling outbox `carousel_published` + `carousel_rejected` nightly 03:00 | Voyager skill library update da publish/reject pattern    |
| `dossier_compiler_cli` | Cron daily (existing)                                        | 04:30                                                                   | Compila dossier daily, NO cambio                          |

**NB**: outbox consumer idempotent: ogni consumer scrive in `consumed_by` jsonb array prima di processare. Re-run safe.

---

## 8. IG env-var canonicalization + token rotation (B.8 post-panel)

### 8.1 Canonicalization (parzialmente già implementata — Codex discovery)

```python
# apps/backend-rag/backend/services/publisher/ig_publisher.py (EXISTING)
# IG_USER_ID / IG_LONG_LIVED_TOKEN  → primary
# INSTAGRAM_ACCOUNT_ID / INSTAGRAM_ACCESS_TOKEN → fallback (already tested)
# IG_BUSINESS_ACCOUNT_ID / IG_GRAPH_API_TOKEN → m13_collect (LEGACY, deprecate)
```

**Amendment Gemini**: shim warning su legacy vars per 30 giorni, poi hard-fail.

**Amendment Codex**: startup validation log SOLO account_id (no token leak), verify Graph `/me` identity, fail-loud se 2 alias puntano ad account diversi.

```python
def validate_ig_credentials_at_startup():
    ig_id = os.environ.get("IG_USER_ID")
    ig_tok = os.environ.get("IG_LONG_LIVED_TOKEN")
    insta_id = os.environ.get("INSTAGRAM_ACCOUNT_ID")
    insta_tok = os.environ.get("INSTAGRAM_ACCESS_TOKEN")

    if ig_id and insta_id and ig_id != insta_id:
        raise SystemExit(f"IG account mismatch: IG_USER_ID={ig_id} vs INSTAGRAM_ACCOUNT_ID={insta_id}")

    primary_id = ig_id or insta_id
    primary_tok = ig_tok or insta_tok
    if not primary_id or not primary_tok:
        raise SystemExit("IG credentials missing")

    # Verify via Meta /me
    r = httpx.get(f"https://graph.facebook.com/v21.0/{primary_id}",
                  params={"access_token": primary_tok, "fields": "id,username"},
                  timeout=10)
    if r.status_code != 200:
        raise SystemExit(f"IG token invalid: {r.status_code}")

    data = r.json()
    logger.info(f"IG credentials validated: account_id={data['id']} username={data.get('username','?')}")
```

### 8.2 Token rotation watchdog (Gemini amendment Task 30 TBD)

```
NEW LaunchAgent com.balizero.wr2.ig-token-watchdog.weekly
- Cadence: Monday 07:00 WITA
- Action:
  1. curl https://graph.facebook.com/v21.0/debug_token?input_token=<TOKEN>&access_token=<APP_TOKEN>
  2. Parse `expires_at` (Unix timestamp)
  3. If expires_at < now() + 7 days → Telegram alert "IG token expires <date>, renew at https://developers.facebook.com/tools/explorer"
  4. If expires_at < now() + 1 day → CRITICAL Telegram + auto-pause `com.balizero.wr2.queue-server` until operator rotates
```

---

## 9. Editorial governance gates (NB-7 ground truth integration)

NB-7 ha identificato **4 PASS/FAIL gates ufficiali** che il critic step DEVE applicare verbatim:

### Gate 1 — Primary source citation (PASS/FAIL)

Ogni claim normativo deve avere `[Fonte: UU/PP/PMK xx/xxxx]` inline. Critic verifica:

- regex `\[Fonte:\s*(UU|PP|PMK|Perpres|Permenkumham|Permenaker)\s+\d+/\d{4}.*?\]` presente per ogni numerical/regulatory claim
- Se assente → critic returns `FAIL` con reason "missing_primary_citation"

### Gate 2 — NotebookLM consistency (PASS/FAIL)

Critic invia claim contestati a NB-7/NB-3/NB-2 via MCP `mcp__notebooklm-mcp__notebook_query`. Risposta cita `[Fonte: <reg>]` → claim VERIFIED. Risposta dice "non trovo" o cita altra reg → critic returns `FAIL` con reason "contradicts_notebooklm_ground_truth".

### Gate 3 — Mandatory disclaimer (PASS/FAIL)

Ultima slide carousel DEVE contenere disclaimer standard:

```
Le informazioni in questo carousel hanno scopo informativo generale e non
costituiscono consulenza legale o fiscale. Per la tua situazione specifica,
consulta un professionista autorizzato.
```

Critic regex `informativo|non costituiscono consulenza` sull'ultima slide. Assente → `FAIL`.

### Gate 4 — Operator approval gate (PASS/FAIL — HUMAN)

**NESSUN auto-publish** per visti/PT PMA/tasse/proprietà/regolamenti indonesiani. Telegram inline button + signed `manual_publish_token` (Codex amendment) ESCLUSIVAMENTE.

### Auto-block phrases (Brand-Voice Red Flags — NB-7)

Critic regex scan blocca pubblicazione su match:

- Prezzi hardcoded servizi Bali Zero: `IDR\s*\d+.*?Bali Zero\s*(visa|kitas|pma)`
- Garanzie tempistiche: `garant\w+\s+\d+\s+gg|approv\w+\s+entro\s+\d+`
- Denigrazione competitor: `A differenza di\s+\w+|molte agenzie\s+\w+\s+ma`
- Opinioni politiche: `governo indonesiano\s+(non|sbaglia|fallisce)|Presiden\s+\w+\s+(non|sbaglia)`
- Banned openings: `^(In questo carosello|In questa guida|Oggi parleremo)`
- Bullet wall instead of numbered steps su procedure

### Format check (NB-7 ufficiale)

- 5-13 slide (breaking 5-7 / explainer 8-10 / deep dive 11-13)
- Template Canva ID `DAHE6lx1lf8` (verifica meta)
- Fonts: League Spartan title + Montserrat subheading
- Palette: dark charcoal + ochre
- Format: Instagram Post 4:5

### Bilingual assist (terminology — NB-7 §4)

Primo uso termine indonesiano in italics + traduzione parentesi (eccezioni acquisite: KITAS, KITAP, NIB, NPWP, OSS, PMK, PP). Critic regex scan prima occurrence.

---

## 10. Operator publish gate (Telegram — Codex hardening)

### 10.1 NEW script `scripts/wr2_telegram_publish_gate.py`

KeepAlive LaunchAgent `com.balizero.wr2.telegram-publish-gate.plist` (always-on polling bot).

```python
# Workflow:
# 1. Orchestrator transitions state → awaiting_approval
# 2. Generate signed manual_publish_token = HMAC-SHA256(carousel_id + content_hash + nonce + expires_at, secret)
# 3. Store token + expires_at in wr2_publish_attempts (state=blocked_manual_gate)
# 4. POST Telegram message with inline keyboard:
#    [✅ Approve] callback_data=approve:<carousel_id>:<token_short>
#    [❌ Reject]  callback_data=reject:<carousel_id>:<token_short>
#    [👀 Preview] URL to preview HTML
# 5. Polling bot listens for callback_query updates
# 6. On approve: validate token (HMAC + expiry), validate user_id whitelist
#    → state → approved → invoke ig_publisher.py
# 7. On reject: state → rejected + reason prompt
# 8. Token expires 24h → orchestrator watchdog auto-archives → state=stale_abandoned

ALLOWED_USER_IDS = {1125336968}  # Zero only (per CLAUDE.md TELEGRAM_OWNER_CHAT_ID)

def verify_callback(callback_data, token, user_id):
    if user_id not in ALLOWED_USER_IDS:
        return False, "unauthorized_user"
    # Check token not already used (single-use)
    attempt = await pool.fetchrow(
        "SELECT manual_publish_token, token_expires_at, approved_at FROM wr2_publish_attempts WHERE id=$1",
        attempt_id
    )
    if attempt["approved_at"] is not None:
        return False, "token_already_used"
    if datetime.now(timezone.utc) > attempt["token_expires_at"]:
        return False, "token_expired"
    if not hmac.compare_digest(token, attempt["manual_publish_token"]):
        return False, "token_mismatch"
    return True, "ok"
```

### 10.2 Fail-closed posture (Codex amendment)

- Missing TELEGRAM_BOT_TOKEN env → orchestrator exit 75 (no publish path)
- Telegram API down → state resta `awaiting_approval` (NO auto-publish bypass)
- Token expired → operator deve approvare ri-invocando workflow (no auto-renew)

### 10.3 Dual publish_mode design (Antonello 2026-05-27 — auto path in standby Day 1)

Env flag controlla pre-publish behavior:

```bash
# Day 1 setup
WR2_PUBLISH_MODE="manual"        # default Day 1
WR2_AUTO_PUBLISH_ENABLED="false"  # path auto codato ma disabled
```

**Path `manual` (Day 1 active)**:

1. critic PASS → state=awaiting_approval
2. Telegram inline button [Approve/Reject/Preview]
3. Antonello approve → invoke ig_publisher.py
4. Antonello reject → state=rejected

**Path `auto` (codato + tested, NON enabled)**:

1. critic PASS → state=awaiting_approval (ANCHE in auto mode — Telegram gate IRREDUCIBILE per Law 5)
2. Telegram inline button [Approve/Reject/Preview] (sempre presente)
3. Antonello approve → invoke ig_publisher.py
4. Antonello reject → state=rejected
5. **NEW se WR2_AUTO_PUBLISH_ENABLED=true**: timer 4h auto-approve fallback se nessuna risposta Telegram (defaults safe-fail = reject)

**Implementation contract**:

- Codebase orchestrator CONTIENE entrambi i path (no dead-code)
- `WR2_AUTO_PUBLISH_ENABLED=false` Day 1 (hardcoded in plist EnvironmentVariables)
- Test suite copre entrambi i path (test_publish_mode_manual, test_publish_mode_auto_with_timer_approval)
- Flip a `auto` futuro = SOLO operator decision via env edit + launchctl reload (no code change)
- Telegram gate sempre presente (anche in auto mode) — solo cambia behavior post-timer (manual=infinite wait, auto=4h then reject)

**Rationale**: codice ready per futuro trust maturity, ZERO surprise refactor quando vorrai flippare. Ultimo step (publish call) sempre human-gated Day 1.

---

## 11. Cost analysis figurativa (Law 7 — Numbers first per AUDIT)

**ATTENZIONE**: Claude OAuth MAX 2 plan = quota FLAT, NON pay-per-token. I valori $/run sono **figurativi per detect runaway/loop** (audit metrics), NON spesa effettiva. Vera throttle = quota MAX 5h-window (vedi §2.1).

### 11.1 Per-run cost figurative (Anthropic pricing 2026, cache_read 97% hit assumed)

| Step                     | Model    | Cache IN (95k)         | New IN              | Token OUT           | Costo step figurativo |
| ------------------------ | -------- | ---------------------- | ------------------- | ------------------- | --------------------- |
| brief-interpreter        | **opus** | 95k × $1.50/M = $0.143 | 5k × $15/M = $0.075 | 2k × $75/M = $0.150 | **$0.368**            |
| storyboarder             | **opus** | $0.143                 | 6k → $0.090         | 3k → $0.225         | **$0.458**            |
| image-prompt-author      | sonnet   | 95k × $0.30/M = $0.029 | 3k → $0.009         | 1k → $0.015         | **$0.053**            |
| layout-composer          | sonnet   | $0.029                 | 8k → $0.024         | 5k → $0.075         | **$0.128**            |
| critic                   | **opus** | $0.143                 | 10k → $0.150        | 2k → $0.150         | **$0.443**            |
| Playwright render        | NO LLM   | —                      | —                   | —                   | $0                    |
| Telegram polling         | NO LLM   | —                      | —                   | —                   | $0                    |
| **TOTAL figurativo/run** |          |                        |                     |                     | **~$1.45**            |

**Implication**: NON pago realmente — è quota MAX consumption. Hard cap audit $5/run, $10/mo (Antonello 2026-05-27).

### 11.2 Weekly figurative + headroom

- 3 run/wk × $1.45 = ~$4.35/wk figurativo
- Monthly avg figurativo: ~$17/mo (sopra audit cap $10 — accettabile se quota MAX regge)
- Event-driven regulatory urgent overlay: +1-2 run/wk peak, headroom OK

### 11.3 Audit alert thresholds (NON throttle reale)

- Audit_cost_per_run > $5 → WARNING Telegram (probabile loop/runaway, NOT quota issue)
- Audit_cost_monthly > $10 → WARNING (info-only, no auto-pause — MAX quota copre)
- MAX usage_5h > 70% → DEFER 30min next run (vera throttle, §2.1)
- MAX usage_5h > 90% → CASCADE Tier 2 (preserva quota per altri workflow)
- 2 cascade consecutivi → CRITICAL Telegram "MAX quota saturation"

---

## 12. Cross-cutting verdicts panel summary

| Q                                         | Decision                                                                             | Convergent?                                                                                           | Rationale                                           |
| ----------------------------------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| Q-A Postgres vs Redis state               | **Postgres**                                                                         | 3/3 (Gemini + DeepSeek + Codex)                                                                       | Durability + transactional + joinable observability |
| Q-B Cadence 3x/wk vs daily                | **3x/wk**                                                                            | 2/2 (Gemini + DeepSeek; NB-7 dice 5-7 post/wk MA include lifestyle/repost — solo 3 WR2 carousel core) | Budget headroom + audience fatigue                  |
| Q-C Critic rubric oggettivo vs soggettivo | **Rubric oggettivo**                                                                 | 2/2 (Gemini + DeepSeek; NB-7 implicit con 4 quality gates)                                            | Predictable ship rate, no infinite retry            |
| Q-D Cron vs event-driven                  | **HYBRID: cron kickoff + supervisor event-driven inter-step + outbox per consumers** | 2/2 (Gemini + DeepSeek consenso parziale)                                                             | Predictability budget + low-latency inter-step      |
| Q-E Operator gate necessario              | **YES non-negoziabile**                                                              | 4/4 (Gemini + DeepSeek + Codex + NB-7 explicit "JWT token humano richiesto")                          | Law 5 + reputation cost di hallucination publish    |

---

## 13. Risk assessment finale post-amendments

| Section                 | Risk pre-amendments         | Risk post-amendments                                   |
| ----------------------- | --------------------------- | ------------------------------------------------------ |
| B.1 Architecture        | 3-9 (range Gemini-DeepSeek) | **4** (supervisor listener + outbox correzione)        |
| B.2 Token/quota         | 2-7                         | **3** (mapping cascade + global circuit breaker)       |
| B.3 State machine       | 4-8                         | **4** (advisory lock + ACID + publish_attempts ledger) |
| B.4 Worktree            | 5-7                         | **4** (cleanup cron + skill cortex /tmp copy)          |
| B.5 Observability       | 1-3                         | **2** (daily watchdog + stuck detection)               |
| B.6 Failure modes       | 4-6                         | **4** (JSON validation + cascade_failed transition)    |
| B.7 Cluster C           | 6-9                         | **5** (outbox pattern invece di direct event coupling) |
| B.8 IG canonicalization | 5-6                         | **4** (shim + startup validation + token rotation)     |
| **OVERALL**             | **4.5-8**                   | **3.75**                                               |

**Verdict finale**: SHIPPABLE con amendments. Risk target 3.75/10 (= acceptable per autonomous pipeline non-mission-critical).

---

## 14. Implementation roadmap (post-spec approval)

### Phase 1 — Foundation (Week 1)

- [ ] Migration 197: `wr2_carousel_runs` table
- [ ] Migration 198: `wr2_publish_attempts` table
- [ ] Migration 199: `wr2_carousel_events_outbox` table
- [ ] Migration 200: `wr2_orchestrator_metrics` table
- [ ] IG startup validation function + canonicalization shim
- [ ] Token rotation watchdog plist + script

### Phase 2 — Orchestrator (Week 2)

- [ ] `scripts/wr2_carousel_orchestrator.py` (~600 LOC)
- [ ] `scripts/wr2_telegram_publish_gate.py` (~400 LOC + KeepAlive plist)
- [ ] Supervisor patch: dispatch to orchestrator on topic_ready NOTIFY
- [ ] Critic rubric integration (4 NB-7 gates + auto-block phrases)

### Phase 3 — Wiring (Week 3)

- [ ] Wire `ig_publisher.py` post-approval call (service_initializer + caller in orchestrator)
- [ ] Outbox consumers: strategos / newsletter / learner refactor
- [ ] Worktree cleanup cron `com.balizero.wr2.worktree-gc.daily`

### Phase 4 — Observability + cutover (Week 4)

- [ ] `scripts/wr2-daily-health.sh` + plist
- [ ] Telegram daily digest 08:00 WITA
- [ ] Shadow mode: orchestrator runs but Telegram gate auto-rejects (no publish) for 1 week
- [ ] Production cutover with operator approval

---

## 15. Operator decisions log (Antonello sign-off 2026-05-27)

| #   | Domanda                 | Decisione                                                   | Note                                                                                                     |
| --- | ----------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Q1  | B.7 Cluster C pattern   | **Outbox polling**                                          | DeepSeek raccomandazione; consumer poll outbox table, idempotency banale via consumed_by jsonb           |
| Q2  | Cost budget             | **$10/mo + $5/run hard cap AUDIT (NOT throttle)**           | OAuth MAX 2 plan flat quota; real throttle = usage_5h-window. Vedi §11                                   |
| Q3  | Shadow mode pre-cutover | **Skip shadow, full auto Day 1 + dual publish_mode codato** | Path `manual` (default) + path `auto` (in standby, disabled). Ultimo step sempre human-gated. Vedi §10.3 |
| Q4  | Learner refactor        | **Refactor a outbox consumer**                              | Polling outbox `carousel_published`+`carousel_rejected` nightly 03:00                                    |
| Q5  | Telegram token expiry   | **24h**                                                     | Standard, copre sleep/weekend. Stuck >7d auto-archivia stale_abandoned                                   |
| Q6  | NB-7 check critic step  | **Si, full NB query (Gate 2)**                              | Latency +30-90s/query accettabile vs hallucination ship cost                                             |
| Q7  | Newsletter content      | **Independent (no outbox refactor)**                        | Newsletter standalone; carousel link OPTIONAL menu inferiore                                             |

### 15.1 Critical updates triggered da decisions

- **§2.1 Token/quota**: AUDIT_BUDGET_PER_RUN_USD=$5, AUDIT_BUDGET_PER_MONTH_USD=$10 (figurativi); throttle reale via quota_throttle_check()
- **§2.2 Cascade mapping**: opus su brief/storyboard/critic, sonnet su image-prompt+layout (Antonello scelta)
- **§7 Cluster C outbox**: newsletter rimosso da consumers list (independent cron preservato); strategos+learner = outbox consumer
- **§10.3 Dual publish_mode**: orchestrator codifica BOTH `manual` + `auto` path; flag `WR2_AUTO_PUBLISH_ENABLED=false` Day 1; Telegram gate irreducibile
- **§11 Cost analysis**: figurative ($1.45/run avg vs spec originale $0.30 errato); real metric = quota MAX 5h-window

---

**Spec status**: APPROVED post-7-decisions (Antonello 2026-05-27). READY FOR PHASE 1 IMPLEMENTATION.
**Wall time sessione**: ~90 min (target on-budget)
**Panel cost reale**: ~$0.04 (DeepSeek API only) + quota Claude OAuth MAX consumata
**Next**: Phase 1 — 4 migration SQL + IG validation startup function (vedi §14 roadmap)
