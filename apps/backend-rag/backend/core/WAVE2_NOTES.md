# KG Wave 2 — Implementation Notes

Implementation of the wave 1 design in PR #174 (merged `7e8d39b274`).
Scope was deliberately chirurgical: chunker + parsers + scraper +
gap_scanner JSON fix. No endpoint changes, no KG ingestion refactor.

## Part 1 — Page-aware chunker + parsers page markers (TODO #76)

### What shipped

- `backend/core/parsers.py`
  - `extract_text_from_pdf(..., return_page_markers: bool = False)`.
    Default `False` keeps the signature byte-identical for existing
    callers. When `True`, returns `(text, markers: list[int])` where
    `markers[i]` is the character offset of page `i+1` inside `text`.
  - Same flag added to `extract_text_from_pdf_async`.
  - `_join_pages_with_markers` helper guarantees the offsets are
    consistent with the joined text (uses `PDF_PAGE_SEPARATOR`
    constant shared between parsers and chunker).
  - OCR / Vision fallback paths return `markers=[]` — per-page
    offsets are not reliable there; callers then fall back to
    semantic chunking.

- `backend/core/chunker.py`
  - `TextChunker.chunk_by_pages(text, page_markers, metadata)` now
    actually respects page boundaries. Each chunk carries:
    `page` (1-based), `page_chunk_index` (index inside that page),
    `chunk_index`, `total_chunks`, `chunk_length`, `text`.
  - Consecutive pages never merge (intra-page overlap only).
  - Garbage markers (non-monotonic, out of range, negative) fall
    back to `semantic_chunk` instead of crashing.
  - `max_chunks` cap applied after per-page chunking.

### Test matrix (8 from wave 1 pseudocode + 7 support = 15 total)

File: `backend/tests/unit/core/test_chunker_page_aware.py`

1. PDF single-page → one marker, chunks all tagged `page=1`.
2. PDF multi-page → markers per page, every chunk tagged with
   source page; no cross-page content leakage.
3. Page break mid-chunk → even with `chunk_size=10_000`, a page
   boundary forces a new chunk. No cross-page merging.
4. OCR path (no markers) → `page_markers=[]` or `None` falls back
   to `semantic_chunk`; resulting chunks have no `page` key.
5. Empty pages → zero-length pages skipped, non-empty retained.
6. Markers mismatched content → 3 cases (past-EOF, non-monotonic,
   negative) all fall back gracefully to `semantic_chunk`.
7. Backward-compat flag → default `False` returns `str`; `True`
   returns `tuple[str, list[int]]`.
8. Perf regression → fallback path ≤ 3× `semantic_chunk` baseline
   (typically identical — fallback literally calls `semantic_chunk`).

### Test run

```
backend/tests/unit/core/test_chunker_page_aware.py  15 passed
backend/tests/unit/core/test_chunker.py             11 passed (existing)
backend/tests/unit/core/test_parsers.py             17 passed (existing, 1 slow OCR test deselected)
```

## Part 2 — Scraper hardening (TODOs #77 + #78 partial)

### What shipped

- `backend/services/kg_monitoring/scraper.py`
  - `REALISTIC_USER_AGENTS`: 5 desktop UAs (Chrome/FF/Safari/Edge,
    macOS / Win / Linux).
  - `UserAgentRotator`: round-robin, thread-unsafe (one instance
    per scraper is fine — httpx is the bottleneck, not this).
  - `SourceConfig` gains three keyword-only fields with safe
    defaults: `rotate_user_agent=True`, `use_playwright_fallback=False`,
    `http2=True`. Existing `DEFAULT_SOURCES` literals unchanged.
  - `_get_client()`: `httpx.AsyncClient(http2=True, ...)`. If the
    `h2` package is missing at runtime, `ImportError` is caught and
    we fall back to HTTP/1.1 transparently.
  - `_build_request_headers(source)`: merges source headers with
    a rotated UA (when enabled). Never mutates `source.headers`.
  - `_fetch_with_retry()`: every retry gets a new UA. If all httpx
    retries fail AND a block-style status (401/403/406/429/503)
    was seen AND the source opted in, `_fetch_with_playwright` is
    invoked. Timeouts alone do NOT trigger the browser.
  - `_fetch_with_playwright(url, source)`: headless Chromium via
    `playwright.async_api` (imported lazily). Returns an
    `httpx.Response` wrapper so downstream BeautifulSoup code is
    unchanged. `rate_limit_delay` honored after the fallback too.
  - Stats counters: `playwright_fallback_invocations`,
    `playwright_fallback_successes`, `user_agent_rotations`.

- NO Firecrawl dependency added. SYMBIOSIS law 2.

### Test run

File: `backend/tests/services/kg_monitoring/test_scraper_wave2.py`
12 new tests covering:
- UA rotation wrap-around, empty-list rejection, default agents
- HTTP/2 kwarg passed to httpx.AsyncClient; graceful fallback when
  h2 missing
- UA rotation during fetch (each retry uses a different UA);
  rotate_user_agent=False honoured
- Playwright fallback: triggered only on block-status exhaustion +
  opt-in; NOT on timeouts; uses rotated UA for browser context
- Rate-limit compliance after Playwright success

Playwright is MOCKED in these tests (no real browser launched) —
full browser-integration test belongs in a separate job because of
binary-install cost.

```
backend/tests/services/kg_monitoring/test_scraper_wave2.py  12 passed
backend/tests/services/kg_monitoring/test_scraper.py        15 passed (existing)
```

## Part 3 — gap_scanner._extract_gap_topics JSON fix

### Bug discovered

Wave 1 flagged 35 corrupted `essential_questions` in
`apps/evaluator/nlm_deep_research/coverage_matrix.json`. Root cause
confirmed in this session by inspecting the current matrix file:

```json
"essential_questions": [
  "\"answer\": \"Il testo integrale della circolare SE Kemnaker ...",
  "\"conversation_id\": \"3e8fe6db-8873-4689-9bff-226ee875c09d\",",
  "\"sources_used\": [],",
  "\"citations\": {},",
  "\"references\": []"
]
```

The NLM CLI periodically returns a JSON envelope instead of the bare
answer text. `_extract_gap_topics` split the whole envelope by `\n`
and retained every line longer than 15 chars — so envelope keys like
`"conversation_id"` and `"sources_used"` ended up as fake gap topics.

### Fix (6 lines of real logic + defensive filter)

`apps/evaluator/nlm_deep_research/gap_scanner.py::_extract_gap_topics`:

1. If response starts with `{`, try `json.loads`. If it is a dict
   with an `answer` string, use `answer` as the text to split.
2. Defensive line-level filter drops any line that looks like a bare
   JSON key-value (starts with `"` and has `":` in the first 60
   chars). Catches the corruption even when `json.loads` bails (e.g.
   the CLI emits half-valid JSON).

### Test run

File: `apps/evaluator/nlm_deep_research/tests/test_extract_gap_topics.py`
5 regression tests:
- JSON envelope → answer field used, no key leakage
- Plain text unchanged
- Malformed JSON → line filter still drops keys
- Empty input → []
- 8-gap cap still enforced through JSON path

```
apps/evaluator/nlm_deep_research/tests/test_extract_gap_topics.py  5 passed
apps/evaluator/nlm_deep_research/tests/test_gap_remediation.py    21 passed (existing)
```

The 35 corrupted entries already in `coverage_matrix.json` will be
cleaned out automatically on the next Layer A run (05:30 WITA) now
that `_extract_gap_topics` filters the envelope. No migration needed.

## Reality check

| Dimension | Value |
| --- | --- |
| Chunker test pass rate | 15/15 new + 11+17 existing = 43/43 |
| Scraper test pass rate | 12/12 new + 15/15 existing = 27/27 |
| gap_scanner test pass rate | 5/5 new + 21/21 existing = 26/26 |
| Playwright tests: mocked or real? | **Mocked.** Real Chromium run belongs in a separate integration job. |
| gap_scanner bug: found? | Yes — JSON envelope leakage. <10 lines to fix, 1 test added. |
| Lines changed total (prod code) | +~210 parsers+chunker, +~110 scraper, +~25 gap_scanner |
| Firecrawl added? | No. SYMBIOSIS law 2. |

## Wave 3 TODO (for next session)

1. **Playwright integration test** — launch real Chromium once per
   scrape target to verify the end-to-end path. Gate with an env
   var so CI doesn't pay the binary-install cost unconditionally.
2. **Scraping content remediation** — populate top-5 critical KG
   gaps from wave 1 triage using the now-hardened scraper. Explicit
   out-of-scope in wave 2 brief.
3. **Citation verification** — feed the 5 regulation citations
   refreshed in PR #174 through the KG ingestion pipeline and
   verify they replace the stale ones.
4. **KG ingestion pipeline** — plumb `chunk_by_pages` through the
   ingestion flow so new PDFs actually carry `page` metadata
   downstream (currently only the chunker exposes it).
5. **Clean coverage_matrix.json** — the 35 corrupted entries are
   still on disk. Either wait for next Layer A run or run
   `python -m apps.evaluator.nlm_deep_research.gap_scanner --layer-a`
   manually after a deploy.
