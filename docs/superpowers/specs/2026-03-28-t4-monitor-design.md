# T4 Social Media Monitor — Design Spec

**Date:** 2026-03-28
**Status:** APPROVED FOR IMPLEMENTATION
**Notebook Target:** NB-2 (Immigration) — NHS 0.801
**Pipeline:** NLM Deep Research, Phase 3 (Post-Production)

---

## 1. Context & Motivation

NB-2 is GREEN for production (NHS 0.801) with 44 active sources across tiers T0–T3.
T4 adds **institutional social/web signals** — enforcement news, policy announcements, departure notices — that are not captured by official document archives (T0) or news aggregators (T3).

**Problem statement:** Indonesian immigration enforcement decisions (TIMPORA raids, deportations, WNA overstay crackdowns, blacklist updates) often surface 24–72 hours earlier on government social/web channels than on news sites. NB-2 currently misses this signal entirely.

**Mini-test results (2026-03-28 confirmatory):**

| Platform                         | Result                                                 | Decision                  |
| -------------------------------- | ------------------------------------------------------ | ------------------------- |
| Instagram (raw Playwright)       | HTML shell returned, no `__NEXT_DATA__`, API 401       | ❌ NOT viable v1          |
| `ngurahrai.imigrasi.go.id/feed/` | 10 live articles, latest 2026-03-26, CRITICAL keywords | ✅ RSS confirmed          |
| `ditjenimigrasi.go.id/berita/`   | Structured HTML, parseable                             | ✅ Scraping viable        |
| Grok API live search             | HTTP 410 — deprecated, must use Agent Tools API        | ⚠️ X needs Agent Tools    |
| X/Twitter API v2 bearer          | Token staged on Fly, not local — untested              | ⚠️ Available, unconfirmed |

**Brainstorm consensus (Codex + Gemini + DeepSeek):** Website-first architecture beats Instagram-first by ROI formula (Website=9.07 vs Instagram=0.41 vs Twitter=0.11). Instagram is v2 supplementary. X is time-boxed (1 month Premium Plus window).

---

## 2. Architecture Overview

```
T4 Monitor Pipeline
├── Layer 1 — RSS Feeds (zero-friction, v1 immediate)
│   ├── ngurahrai.imigrasi.go.id/feed/
│   ├── ditjenimigrasi.go.id/feed/ (if live)
│   └── kemenkumham.go.id/feed/ (if live)
│
├── Layer 2 — Website Scraping (structured, v1)
│   ├── ditjenimigrasi.go.id/berita/ (pagination)
│   ├── imigrasi.go.id/berita/ (Kanwil Bali)
│   └── kemenkumham.go.id/berita/ (policy)
│
├── Layer 3 — X/Twitter v2 API (time-boxed, 1 month)
│   ├── @ditjen_imigrasi (verified account)
│   ├── @imngurahrai (Ngurah Rai airport)
│   └── @kemenkumbali (Kanwil Bali)
│   Access: TWITTER_BEARER_TOKEN (staged on Fly)
│   Fallback: Grok Agent Tools API (xai- key in local env)
│
└── Layer 4 — Instagram (v2, requires Apify/RSSHub proxy)
    ├── @ditjen_imigrasi
    ├── @imngurahrai
    └── (deferred — raw scraping confirmed non-viable)
```

**Data flow:**

```
Cron (every 6h) → T4Monitor.run()
  → fetch sources (RSS/HTTP/API)
  → 3-layer relevance filter
  → SVS admission gate (≥0.35)
  → T4 budget check (≤11 active T4 slots in NB-2)
  → NLM ingest via nlm CLI subprocess
  → state persistence (t4_state.json)
  → CB_T4 update
```

---

## 3. NHS Capacity Analysis

**NB-2 current state:** 44 active sources, cap=70, T4 budget=0
**T4 steady-state projection (unconstrained):** 54 sources → NHS crash at Week 3

**Hard T4 budget:** `MAX_T4_SLOTS = 11` (leaves 15-slot margin at cap=70)

**Admission gate:** SVS ≥ 0.35 (MARGINAL threshold — aggressive but necessary for enforcement news)

**Rotation:** FIFO with NEWS_HALF_LIFE = 15 days. When budget full, oldest T4 source evicted before new admission.

**SVS formula for T4:**

```
SVS = w_authority(0.30) × authority_score
    + w_freshness(0.25) × freshness_score
    + w_uniqueness(0.20) × uniqueness_score
    + w_density(0.15) × keyword_density
    + w_citations(0.10) × citation_potential
```

Expected SVS ranges:

- RSS enforcement article (TIMPORA/deportasi): 0.55–0.70 → ADMIT
- Policy announcement: 0.45–0.55 → ADMIT
- Generic press release: 0.28–0.40 → BORDERLINE (Haiku decides)
- Event/ceremony notice: 0.15–0.28 → REJECT

---

## 4. 3-Layer Relevance Filter

### Layer 1 — Keyword Recall (fast, ~0ms)

```python
CRITICAL_KEYWORDS = [
    "timpora", "deportasi", "deportation", "overstay", "blacklist",
    "daftar cekal", "visa dicabut", "wna ditangkap", "razia",
    "pendeportasian", "izin tinggal dibatalkan", "cegah tangkal"
]

HIGH_KEYWORDS = [
    "kitas", "kitap", "visa", "izin tinggal", "paspor", "imigrasi",
    "wna", "warga negara asing", "tenaga kerja asing", "tka",
    "peraturan imigrasi", "kebijakan visa", "perpanjangan visa"
]
```

Pass criterion: ≥1 CRITICAL or ≥2 HIGH keywords.

### Layer 2 — Embedding Similarity (precision, ~50ms)

```python
REFERENCE_QUERY = (
    "Indonesian immigration enforcement TIMPORA deportation overstay "
    "WNA foreign nationals visa regulation Bali"
)
# model: text-embedding-3-small (FROZEN — never change)
# threshold: cosine_similarity ≥ 0.35
```

### Layer 3 — Haiku Classifier (borderline only, ~500ms)

Invoked only when Layer 1 passes but Layer 2 cosine is 0.30–0.40 (borderline zone).

```
Prompt: "Is this immigration enforcement relevant for a Bali immigration advisor?
Score 0-1. CRITICAL if: arrest/deportation/policy change. HIGH if: procedure/regulation."
Threshold: ≥ 0.5 → ADMIT
```

---

## 5. X/Twitter Integration

### 5.1 Access Strategy

**Available credentials:**

- `TWITTER_BEARER_TOKEN` — staged on Fly.io (value inaccessible locally via `fly secrets list`)
- `X_BEARER_TOKEN` — also staged
- `GROK_API_KEY=xai-f4zbHbGKB5luqJnD...` — local env, Grok Agent Tools API

**User context:** Premium Plus subscription ($1000/mo) is a **user/consumer** plan — does NOT grant API Pro developer access. However, the bearer tokens already on Fly (from existing Twitter OAuth setup) provide Basic-tier v2 read access.

### 5.2 Primary method: Twitter API v2 (bearer token)

```python
GET https://api.twitter.com/2/users/{id}/tweets
Headers: Authorization: Bearer {TWITTER_BEARER_TOKEN}
Params: max_results=100, tweet.fields=created_at,text,entities
```

Accounts to monitor:

- `@ditjen_imigrasi` → resolve to user_id via `/2/users/by/username/ditjen_imigrasi`
- `@imngurahrai` → user_id resolution
- `@kemenkumbali` → user_id resolution

**Rate limits (Basic tier):** 500K tweets/month, 15 requests/15min per endpoint. T4 at 6h interval = 4 × 3 accounts × 1 request = 12 requests/day → well within limits.

### 5.3 Fallback: Grok Agent Tools API

If bearer token fails (403/401), fall back to Grok Agent Tools API:

```python
POST https://api.x.ai/v1/agent-tools/search
Headers: Authorization: Bearer {GROK_API_KEY}
Body: {"query": "from:ditjen_imigrasi OR from:imngurahrai imigrasi deportasi",
       "max_results": 20}
```

Note: Grok live search (v1/chat/completions with sources) is deprecated (410). Agent Tools API is the current path.

### 5.4 Time-box

X integration active for **30 days** from deployment. After T+30:

- `X_ENABLED = False` (env flag)
- CB_T4_X set to OPEN (skips X layer gracefully)
- No data loss — existing ingested tweets remain in NLM

---

## 6. Module Structure

Two files added to `apps/evaluator/nlm_deep_research/`:

### `t4_monitor.py` (main module)

```python
# Public interface
class T4Monitor:
    async def run(self) -> T4RunResult
    async def fetch_rss(self, url: str) -> list[Article]
    async def fetch_website(self, url: str) -> list[Article]
    async def fetch_twitter(self, handle: str) -> list[Post]
    async def apply_relevance_filter(self, content: str) -> FilterResult
    async def compute_svs(self, article: Article) -> float
    async def ingest_to_nlm(self, notebook_id: str, title: str, content: str) -> bool

@dataclass
class Article:
    source_handle: str
    article_id: str          # URL hash — PRIMARY dedup key
    url: str
    title: str
    content: str
    published_at: Optional[datetime]   # UNRELIABLE for social
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    platform: Literal["rss", "website", "twitter", "instagram"]
    svs_score: float = 0.0
    filter_result: str = "PENDING"

@dataclass
class Post:
    handle: str
    post_id: str             # tweet_id or shortcode — PRIMARY dedup key
    url: str
    content: str
    timestamp: Optional[datetime]
    platform: Literal["twitter", "instagram"]
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class T4MonitorError(Exception): pass
class RateLimitedError(T4MonitorError): pass
class DOMChangedError(T4MonitorError): pass   # → immediate CB OPEN
class NLMIngestError(T4MonitorError): pass
```

### `t4_state.py` (persistence)

```python
@dataclass
class T4State:
    seen_ids: set[str]           # article_id/post_id for dedup
    active_t4_sources: list[str] # NLM source IDs currently in NB-2
    last_run_at: Optional[datetime]
    cb_status: Literal["CLOSED", "OPEN", "HALF_OPEN"]
    cb_failure_count: int
    cb_last_failure: Optional[datetime]
    x_enabled_until: Optional[datetime]   # time-box for X integration
    run_lock_pid: Optional[int]           # PID-based concurrent run guard

# Persistence: JSON at apps/evaluator/nlm_deep_research/t4_state.json
# Lock: apps/evaluator/nlm_deep_research/t4.lock (PID file)
```

---

## 7. Circuit Breaker (CB_T4)

**Standalone** — does NOT cascade to CB_NLM or any other pipeline.

```
States: CLOSED → OPEN → HALF_OPEN → CLOSED

CLOSED:    normal operation
OPEN:      skip T4 entirely, log warning
HALF_OPEN: single probe request, success → CLOSED, fail → OPEN

Thresholds:
  failure_threshold = 3 consecutive failures
  recovery_timeout = 30 minutes
  probe_timeout = 60 seconds
```

**Per-source CBs:** Each source (RSS URL / website / twitter handle) has independent failure counter. A single Instagram account being rate-limited does NOT trip the RSS circuit.

**DOMChangedError → immediate OPEN:** If website structure changes (detection: expected CSS selector missing), CB opens immediately and Telegram alert fires. This prevents ingesting garbage.

---

## 8. NLM Ingest Pattern

**Critical:** Use `nlm` CLI subprocess, NOT MCP protocol. MCP is for interactive sessions; cron scripts must use CLI.

```python
async def ingest_to_nlm(
    self,
    notebook_id: str,
    title: str,
    content: str,
    *,
    timeout_seconds: int = 60
) -> bool:
    nlm_bin = shutil.which("nlm") or "/usr/local/bin/nlm"
    cmd = [
        nlm_bin, "source", "add", notebook_id,
        "--text", content,
        "--title", title,
        "--wait"
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_seconds
        )
        return proc.returncode == 0
    except asyncio.TimeoutError:
        proc.kill()
        raise NLMIngestError(f"NLM ingest timeout after {timeout_seconds}s")
```

**Content format for NLM:**

```
[TITLE]: {article.title}
[SOURCE]: {article.source_handle} | {article.url}
[DATE]: {article.scraped_at.isoformat()}
[PLATFORM]: {article.platform}
[SVS]: {article.svs_score:.2f}

{article.content}
```

---

## 9. Cron Configuration

**Schedule:** Every 6 hours — `0 */6 * * *`
**Machine:** Air (batch jobs run there; Pro is dev)
**Script:** `apps/evaluator/nlm_deep_research/scripts/run_t4_monitor.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
VENV="$PROJECT_ROOT/apps/backend-rag/venv/bin/python"  # Air uses venv (not .venv)

# PID lock — prevent concurrent runs
LOCK_FILE="$SCRIPT_DIR/../t4.lock"
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "T4 monitor already running (PID $PID), exiting"
        exit 0
    fi
    echo "Stale lock (PID $PID dead), cleaning up"
    rm -f "$LOCK_FILE"
fi

echo $$ > "$LOCK_FILE"
trap "rm -f '$LOCK_FILE'" EXIT

cd "$PROJECT_ROOT"
PYTHONPATH=. "$VENV" -m apps.evaluator.nlm_deep_research.t4_monitor \
    --notebook-id "cff93ab0-813a-42f2-a8de-36987e724271" \
    --log-level INFO \
    2>&1 | tee -a ~/.openclaw/logs/t4_monitor.log
```

**OpenClaw cron entry:**

```json
{
  "name": "t4-social-monitor",
  "schedule": "0 */6 * * *",
  "command": "bash /path/to/run_t4_monitor.sh",
  "machine": "air",
  "enabled": true
}
```

---

## 10. Target Sources (v1)

### RSS (immediate, zero friction)

| URL                                      | Authority | Expected SVS | Notes                                           |
| ---------------------------------------- | --------- | ------------ | ----------------------------------------------- |
| `https://ngurahrai.imigrasi.go.id/feed/` | ★★★★★     | 0.55–0.70    | CONFIRMED LIVE — 10 articles, TIMPORA/deportasi |
| `https://ditjenimigrasi.go.id/feed/`     | ★★★★★     | 0.55–0.70    | Verify live                                     |
| `https://www.imigrasi.go.id/feed/`       | ★★★★★     | 0.50–0.65    | Verify live                                     |

### Website Scraping (v1, structured)

| URL                                                 | Selector                         | Frequency |
| --------------------------------------------------- | -------------------------------- | --------- |
| `https://ditjenimigrasi.go.id/kategori/berita/`     | `.post-title a`, `.post-excerpt` | 6h        |
| `https://kanwilbali.kemenkumham.go.id/berita-utama` | `article h2 a`, `article p`      | 6h        |

### X/Twitter (v1, time-boxed 30 days)

| Handle             | Focus                         | Priority |
| ------------------ | ----------------------------- | -------- |
| `@ditjen_imigrasi` | National policy, enforcement  | HIGH     |
| `@imngurahrai`     | Bali airport, deportation ops | CRITICAL |
| `@kemenkumbali`    | Bali kanwil policy            | HIGH     |

### Instagram (v2, deferred)

Not implemented in v1. Raw Playwright confirmed non-viable. v2 options:

- RSSHub self-hosted: `rsshub.app/instagram/user/{handle}`
- Apify Instagram Actor (paid)
- Decision: revisit post-X time-box based on data gap analysis

---

## 11. Testing Plan

### Unit tests (`tests/t4/`)

```python
# test_relevance_filter.py
def test_critical_keyword_pass(): ...       # "timpora deportasi" → ADMIT
def test_generic_keyword_reject(): ...      # "selamat pagi" → REJECT
def test_embedding_borderline(): ...        # Layer 3 Haiku invoked

# test_svs_scoring.py
def test_enforcement_article_score(): ...   # SVS ≥ 0.55
def test_ceremony_article_score(): ...      # SVS < 0.30 → REJECT

# test_circuit_breaker.py
def test_three_failures_open(): ...
def test_half_open_recovery(): ...
def test_dom_changed_immediate_open(): ...

# test_state_persistence.py
def test_pid_lock_prevents_concurrent(): ...
def test_stale_lock_cleanup(): ...
def test_dedup_prevents_reingest(): ...
```

### Integration smoke test

```bash
PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.t4_monitor \
    --dry-run \
    --source-url "https://ngurahrai.imigrasi.go.id/feed/" \
    --verbose
# Expected: fetch 10 articles, filter ~4-6 ADMIT, SVS computed, no NLM write
```

---

## 12. Rollout Plan

**Phase 1 (Day 1–3):** RSS only

- Ngurah Rai feed confirmed live → activate
- Dry-run mode: filter + SVS computed, no NLM ingest yet
- Verify SVS distribution matches predictions

**Phase 2 (Day 4–7):** RSS + website scraping

- Enable NLM ingest (≤5 articles/day budget)
- Monitor NHS — should stay 0.80–0.85
- Verify T4 slot count stays ≤11

**Phase 3 (Day 8+, if bearer works):** + X/Twitter

- Pull bearer from Fly secrets via `fly ssh console`
- Test 3 accounts, verify tweet fetch
- Enable X layer in cron

**Phase 4 (Day 31+):** X sunset

- Set `X_ENABLED_UNTIL = None` (disable)
- Evaluate gap — if significant, evaluate Apify Instagram v2

---

## 13. Failure Modes & Mitigations

| Failure              | Detection                     | Mitigation                             |
| -------------------- | ----------------------------- | -------------------------------------- |
| RSS feed goes 404    | HTTP error in fetch           | CB counter +1, skip, retry in 6h       |
| Website DOM change   | Missing CSS selector          | CB_T4 OPEN immediately, Telegram alert |
| NLM ingest timeout   | asyncio.TimeoutError          | Retry 1x, then log + skip              |
| X bearer 401/403     | HTTP error                    | Disable X layer, log, no crash         |
| T4 budget exceeded   | active_t4_sources len check   | FIFO evict oldest, then admit new      |
| NB-2 NHS drop < 0.75 | Post-run NHS check            | Pause T4 ingestion, alert              |
| Concurrent cron runs | PID lock file                 | Second run exits immediately           |
| NLM CLI not found    | `shutil.which()` returns None | T4MonitorError with clear message      |

---

## 14. Files to Create/Modify

### New files

```
apps/evaluator/nlm_deep_research/t4_monitor.py        # main module
apps/evaluator/nlm_deep_research/t4_state.py          # state persistence
apps/evaluator/nlm_deep_research/scripts/run_t4_monitor.sh  # cron wrapper
apps/evaluator/nlm_deep_research/tests/test_t4_filter.py
apps/evaluator/nlm_deep_research/tests/test_t4_svs.py
apps/evaluator/nlm_deep_research/tests/test_t4_cb.py
apps/evaluator/nlm_deep_research/tests/test_t4_state.py
```

### Modified files

```
apps/evaluator/nlm_deep_research/__init__.py     # export T4Monitor
apps/evaluator/nlm_nb2_sources.json              # add T4 source entries
```

### Dependencies (add to requirements if missing)

```
feedparser>=6.0          # RSS parsing
httpx>=0.27             # Already present (async HTTP)
beautifulsoup4>=4.12    # Website scraping
openai>=1.0             # Embeddings (text-embedding-3-small)
anthropic>=0.34         # Haiku classifier (Layer 3)
```

---

## 15. Open Questions (resolved)

| Question                     | Answer                                                                |
| ---------------------------- | --------------------------------------------------------------------- |
| Instagram viable for v1?     | NO — HTML shell, no structured data without JS/login                  |
| X Premium Plus = API access? | NO — consumer plan ≠ developer API Pro                                |
| Bearer token available?      | YES — `TWITTER_BEARER_TOKEN` staged on Fly                            |
| Grok live search?            | DEPRECATED (410) — use Agent Tools API                                |
| NLM ingest via MCP?          | NO — CLI subprocess only for cron scripts                             |
| Primary dedup key?           | `article_id` = URL hash (not timestamp)                               |
| Instagram v2 timeline?       | After 30-day X window, evaluate based on data gap                     |
| JDIH domain DNS?             | Intermittent (network-specific). Include in v2, not v1 critical path. |

---

_Design approved. Next: invoke writing-plans for implementation plan._
