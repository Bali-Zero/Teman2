# NOTES.md — KG Ingestion Wave 1 Design Notes

Session: `session/kg-gaps` · Date: 2026-04-22 · Model: Claude Opus 4.7 (1M)
Scope: **Design only**. No production code in wave 1.

---

## 1. Chunker Page-Aware Fix — TODO(#76)

### 1.1 Root cause (two bugs, not one)

`apps/backend-rag/backend/core/chunker.py:214-234` exposes `TextChunker.chunk_by_pages(text, page_markers, metadata)`. The body:

```python
if not page_markers:
    return self.semantic_chunk(text, metadata)
# TODO(#76): Implement page-aware chunking
return self.semantic_chunk(text, metadata)   # ← bug: ignores page_markers
```

The obvious bug is the unconditional fallback to `semantic_chunk`. The less obvious bug is upstream:

`apps/backend-rag/backend/core/parsers.py:34-83` (`extract_text_from_pdf_async`) joins pages with `"\n\n".join(text_parts)` and returns a single string. **It never computes the character offsets where each page starts.** So the only call path that could provide `page_markers` to the chunker currently throws away the information before the chunker is even invoked.

Net effect: in production today, `chunk_by_pages` is unreachable dead code — every PDF arrives at `semantic_chunk` with no page metadata attached. This is why KG chunks cannot cite "page 3 of Permenkumham 22/2023" even when the source PDF was OCR-ed properly.

### 1.2 Fix design (pseudocode, two files)

**File 1 — `parsers.py` (`extract_text_from_pdf_async`):** emit `(text, page_markers)` tuple instead of plain `text`. Backward compatibility via an optional flag so 90+ existing callers don't break in one commit.

```python
async def extract_text_from_pdf_async(
    file_path: str,
    use_ocr: bool = False,
    return_page_markers: bool = False,  # NEW
) -> str | tuple[str, list[int]]:
    reader = PdfReader(file_path)
    text_parts = []
    page_offsets = []       # NEW: char offsets where each page starts
    running_offset = 0      # NEW

    for page_num, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
            page_offsets.append(running_offset)      # NEW
            text_parts.append(text)
            running_offset += len(text) + 2          # +2 for "\n\n" join
        except Exception as e:
            logger.warning(f"Error extracting page {page_num}: {e}")
            page_offsets.append(running_offset)      # empty page still gets marker
            text_parts.append("")
            running_offset += 2

    full_text = "\n\n".join(text_parts)

    # OCR fallback unchanged. If OCR kicks in, page_offsets is invalidated
    # (OCR returns a single blob). In that case return page_markers=None.
    if ocr_path_taken:
        page_offsets = None   # explicit: markers are lost under OCR

    if return_page_markers:
        return full_text, page_offsets
    return full_text
```

**File 2 — `chunker.py` (`chunk_by_pages`):** real implementation.

```python
def chunk_by_pages(
    self,
    text: str,
    page_markers: list[int] | None = None,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not page_markers:
        # No OCR-scanned PDFs can give us page info — fall back cleanly.
        chunks = self.semantic_chunk(text, metadata)
        for c in chunks:
            c["page"] = None
        return chunks

    # Chunk each page independently so chunks never cross page boundaries.
    # Rationale: a regulation article rarely spans pages; keeping chunks within
    # a single page makes "cite page N" trivial and avoids mixed-topic chunks.
    all_chunks: list[dict[str, Any]] = []
    global_idx = 0
    total_pages = len(page_markers)

    for page_num, start in enumerate(page_markers, 1):
        end = page_markers[page_num] if page_num < total_pages else len(text)
        page_text = text[start:end].strip()
        if not page_text:
            continue

        page_metadata = dict(metadata or {})
        page_metadata["page"] = page_num
        page_metadata["total_pages"] = total_pages

        page_chunks = self.semantic_chunk(page_text, page_metadata)
        for c in page_chunks:
            c["chunk_index"] = global_idx
            global_idx += 1
        all_chunks.extend(page_chunks)

    # Re-attach total_chunks across ALL pages (semantic_chunk set it per-page).
    for c in all_chunks:
        c["total_chunks"] = len(all_chunks)

    return all_chunks
```

**Key design decisions:**

- **No cross-page overlap.** `chunk_overlap` still applies WITHIN a page, but chunks do not bleed across page boundaries. Trade-off: a sentence split across a page break is lost as context. Acceptable for legal/regulatory corpora (articles rarely straddle pages) and wrong for narrative prose (not our use case).
- **OCR path returns `page_markers=None`.** When OCR or vision fallback fires, page offsets are meaningless — we accept degraded behavior rather than inventing fake markers. Downstream `chunk["page"]` will be `None` for OCR'd docs; retrieval can treat this as "page unknown".
- **`global_idx` across pages.** `chunk_index` must be monotonic across the whole document so existing retrieval code (which uses it as primary key component) doesn't break.

### 1.3 Test strategy

New `tests/core/test_chunker_page_aware.py`:

| Test | Fixture | Assertion |
| ---- | ------- | --------- |
| `test_no_markers_falls_back` | text, `page_markers=None` | Result equals `semantic_chunk` output; all `page=None` |
| `test_single_page` | text="abc\n\ndef", `page_markers=[0]` | 1+ chunk, all `page=1`, `total_pages=1` |
| `test_three_pages_no_overflow` | 300-char text split at [0, 100, 200], `chunk_size=80` | Each chunk's `page` matches which marker range its original offset lands in |
| `test_no_cross_page_chunks` | text where a paragraph straddles markers | No chunk contains content from two different page ranges |
| `test_monotonic_chunk_index` | 3 pages × 2 chunks each | `chunk_index` is 0..5 without gaps |
| `test_empty_page_skipped` | `page_markers=[0, 50, 50]` (empty middle page) | No `page=2` chunk emitted |
| `test_parsers_emit_markers` | sample 3-page PDF fixture | `extract_text_from_pdf_async(return_page_markers=True)` returns marker count == reader.pages count |
| `test_ocr_path_returns_none_markers` | PDF with no extractable text | `return_page_markers=True` returns `(text, None)` |

Existing callers of `extract_text_from_pdf_async` must NOT break — add one assertion that default `return_page_markers=False` still returns plain `str`.

### 1.4 Risk & scope

- **Blast radius:** chunker is consumed by `IngestionService` (legal + generic book path) and the legal ingestion pipeline. Both already call `semantic_chunk` directly today, not `chunk_by_pages`, so the fix is opt-in: call sites must be updated to pass `return_page_markers=True` and route through `chunk_by_pages`. Plan: update `LegalIngestionService` only in wave 2 (legal docs benefit most from page citations); skip for generic books.
- **Re-indexing:** enabling this for any collection invalidates existing chunk IDs. Plan: gate behind a `use_page_aware_chunking` flag in `IngestionService.__init__`, default False. Re-ingest specific collections (e.g. `legal_unified_hybrid`) on demand.
- **Wave 2 effort estimate:** ~1 day implementation + test + 1 day supervised re-ingest of one legal collection. Low risk if gated.

---

## 2. Scraping Pipeline Decision — TODO(#78)

### 2.1 What wave 1 discovered about Indonesian government sites

Tested via WebFetch (from a clean residential-like IP) on 2026-04-22:

| Host | Result | Notes |
| ---- | ------ | ----- |
| `www.imigrasi.go.id` | 301 → legacy rewrite chain, eventually 200 | Language switcher via `/site/lang?lang=en-US`, no `/en/` prefix |
| `oss.go.id` | 200 on root, 404 on deep paths (`/informasi/pma`) | Navigation is JS-driven — static fetch returns shell only |
| `pajak.go.id` | 60s timeout | Slow TTFB, anti-bot or heavy SSR |
| `peraturan.bpk.go.id` | 403 | WAF / bot blocking |
| `jdih.bpk.go.id` | 403 | WAF / bot blocking |
| `klinik.kemenkumham.go.id` | ENOTFOUND | Subdomain dead |
| `www.dpmptsp.baliprov.go.id` | ENOTFOUND | Dead or DNS-fragile |
| `bpjsketenagakerjaan.go.id` | 200 | Clean static content |

Ratio: ~3/8 usable with naive fetch. Three are hard-blocked (BPK family = 403), two are DNS-dead, one needs JS rendering, one is timeout-prone.

### 2.2 Existing infra already chose httpx+BeautifulSoup

`apps/backend-rag/backend/services/kg_monitoring/scraper.py` already implements `LegalScraper` with:

- `httpx.AsyncClient` + `BeautifulSoup`
- `SourceConfig` dataclass with `rate_limit_delay`, `timeout`, `max_retries`, `headers` (User-Agent)
- `ScrapedDocument` with MD5 hashing for change detection
- Targets jdih.kemenkumham.go.id and peraturan.bpk.go.id (both 403 today)

So the choice is not greenfield — wave 1 would EXTEND this, not replace it. Which means the Firecrawl question is really "do we ALSO want a managed fallback for the hard-blocked sites, or do we fix the existing scraper's anti-bot posture first?"

### 2.3 Firecrawl vs httpx+bs4 (numbers)

**Firecrawl** (firecrawl.dev, cloud API):

- Free tier: **500 pages/month total, 10/min**. Scrape + crawl share the quota.
- Hobby: $19/mo = 3,000 credits (~3k pages). 20 req/min.
- Standard: $99/mo = 100k credits. 100 req/min. Includes stealth proxies + JS rendering.
- For 56 gap topics × ~5 pages crawled/topic = 280 pages initial load → fits in free tier ONCE. Quarterly refresh = ~1,120/year → needs Hobby ($228/yr).
- Solves: WAF bypass, JS rendering, IP rotation. Zero infra.
- Downsides: external dependency, rate limit coupling, data exfiltration risk (SYMBIOSIS law 2: OSINT blindato — Firecrawl sees our query patterns), egress cost opaque.

**httpx + BeautifulSoup + playwright-as-fallback** (existing + extension):

- Infra cost: €0, already in repo.
- 403 fix: rotate User-Agent + add `Accept-Language: id-ID` + use HTTP/2 + `httpx.AsyncClient(http2=True)`. Bypasses naive WAF on BPK in ~60% of cases (empirical, needs testing).
- JS rendering: reuse existing Playwright stealth manager from `packages/browser-core/` (already solved for scraping, see `apps/nuzantara-mcp-browser/`). Adds ~500ms/page.
- Residential proxy: if still blocked, add BrightData/Oxylabs pay-as-you-go ($5/GB bandwidth). For 280 pages × ~200KB = ~56MB → $0.28. Quarterly refresh = $1.12/year.
- Downsides: engineering effort (~2-3 days to fix UA/HTTP2, add Playwright fallback, wire proxy), brittle (Indonesian sites change markup frequently — already have `scraper_normalizer.py` which suggests past pain).

### 2.4 Decision

**httpx+bs4 + existing Playwright stealth, NOT Firecrawl.** Rationale:

1. **SYMBIOSIS law 2 is binding.** OSINT blindato says intelligence data does not leave the Pro — Firecrawl logs every URL we crawl and every selector we use. That alone disqualifies it for regulatory sources that feed KG.
2. **Existing `LegalScraper` already picked the stack.** The rewrite cost is near zero — we extend `SourceConfig` with retry + header rotation. Firecrawl would orphan that code.
3. **Playwright stealth is already in-repo** (`packages/browser-core/`, `apps/nuzantara-mcp-browser/`). We already pay the complexity cost; reusing it is cheap.
4. **Cost math favors self-hosted.** Hobby-tier Firecrawl ($228/yr) vs ~$1-5/yr residential proxy bandwidth. Over 3 years: $684 vs $15.

**Caveat:** if BPK 403 proves unfixable with UA rotation + Playwright, revisit Firecrawl for the BPK family only (~8 sources) as a *narrow* exception. Budget 1 engineering day before escalating.

### 2.5 Wave 2 scraping scope

Extensions to `LegalScraper`:

1. **User-Agent rotation pool** (5 real browser UAs). Header rotation per request.
2. **HTTP/2 enabled** by default (`httpx.AsyncClient(http2=True)`).
3. **Playwright fallback** when `httpx` returns 403/429/503 three times → reuse `packages/browser-core/` stealth context.
4. **Retry with exponential backoff** (already partial — promote to 5 retries with jitter).
5. **Per-domain `SourceConfig` presets** for the 3 usable .go.id domains + 5 fallback aggregators (hukumonline.com — licensed mirror, lawforeverything.com, Bali Zero internal KB).
6. **Telemetry:** emit `scrape_success_rate{host=...}` to Langfuse/Sentry so we see decay.

### 2.6 Dream.py TODO(#78) — specific answer

`dream.py` is the "Dream Room" content-scraping endpoint, NOT the KG ingestion scraper. Different use case: editorial/marketing team pasting arbitrary URLs. For dream.py specifically:

- **httpx + bs4 only.** No Playwright (cost of startup kills perceived latency in an interactive UX). No Firecrawl (same SYMBIOSIS argument).
- Add readability-lxml for article extraction (`readability-lxml==0.8.1`, same license story).
- Rate-limit per user (3 URLs/min/user) via existing Redis rate limiter.
- Fail soft: if fetch fails, return `success=False` + error, do NOT fake content (current mock returns bogus "AI is a tool, not a master" quote — bad UX).

Wave 2 implementation effort: ~4h for dream.py, ~2d for LegalScraper extensions.

---

## 3. Open questions deferred to wave 2

- Do we want a `kb/legal/` staging area that accumulates scraped raw HTML for audit, separate from the embedded Qdrant chunks? The scraper already computes `document_hash` — persist raw_html + hash in Postgres before chunking?
- Should the page-aware chunker also emit a `line_range` field (useful for citing specific paragraphs in KG graph edges)? Cheap to add while we're touching the code.
- `parsers.py` has 3 OCR fallbacks (pypdf → tesseract → Vision model). All three blow page offsets. A separate `extract_text_with_pages_strict()` that fails loudly instead of silently returning None markers may be worth having for legal pipeline only.
