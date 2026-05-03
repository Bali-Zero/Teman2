# KG Wave 3 — Outcome Notes

**Branch:** `session/kg-layer-a-rerun`
**Base:** `main @ d4fa14115` (wave 2 merged)
**Executed:** 2026-04-22 · **Machine:** Pro (`nuzantara@Nuzantara`)
**Commits on this branch (oldest → newest):**
1. `7e2946c04` data(kg): regenerate 35 corrupted gap topics + parser nested-wrapper fix
2. `48f16dbdc` data(kg): populate top-5 authoritative domain raw snapshots (prep)
3. `2b81a2e87` perf(chunker): production PDF benchmark vs semantic_chunk baseline

---

## Part 1 — Layer A re-run: 35/35 gaps regenerated

### What shipped
- `_extract_gap_topics` (gap_scanner.py) extended to handle the
  `{"value": {"answer": "..."}}` nested wrapper the NLM CLI actually emits.
  Wave 2's fix only covered the flat `{"answer": ...}` shape.
- Regression test `test_nested_value_answer_envelope_supported` locks the
  new path. All 6 tests in `test_extract_gap_topics.py` pass.
- `coverage_matrix.json` updated end-to-end across 7 notebooks (NB-2..8):
  - 35/35 gap topics (5 per domain) regenerated — **target hit on the nose**.
  - 0 JSON/`conversation_id`/`sources_used`/`citations` leakage.
  - `gaps_updated` bumped from **2026-04-03 → 2026-04-22** in every domain.
  - `gap_scanner_state.json` `last_layer_a` timestamped.

### Scar (wave 3, new)
**The wave 2 parser passed all its own regression tests but produced zero
gap topics on the real run.** The CLI envelope is nested, not flat — the
line-level fallback filter correctly dropped the leakage, but in doing so
it also dropped the genuine answer content sitting two keys deeper. Lesson:
"parser fix ships only after a clean end-to-end run against live CLI
output, not just synthetic unit fixtures."

### Sample regenerated topics (audit)
- immigration[0]: *"Quali sono le disposizioni esatte della potenziale nuova
  legge UU No. 1 Tahun 2026 sull'immigrazione e in che modo modifica la UU
  No. 63 Tahun 2024?"*
- tax[2]: *"Con quali procedure esatte un expat SPDN deve dichiarare i
  capital gain su asset cripto detenuti all'estero nella propria SPT
  Tahunan all'interno di CoreTax rispetto a un SPLN?"*

These are full, grammatical, domain-specific questions — i.e. what Layer A
is supposed to produce. The wave 2 run (no nested-wrapper fix) would have
returned `[]` here.

---

## Part 2 — Top-5 domain raw snapshots: 5/5 success

### What shipped
- `apps/backend-rag/backend/services/kg_monitoring/scripts/wave3_top5_snapshot.py`
  new driver reusing `LegalScraper` wave 2 primitives (UA rotation, HTTP/2,
  Playwright fallback opt-in, per-source rate limit) but **one canonical
  landing page per domain** — no paginated crawl, no automatic ingestion.
- Raw snapshots under `apps/backend-rag/backend/kb/raw/top5_wave3/<domain>/`
  with per-source `meta.json` + top-level `index.json`.

### Results
| Domain | Base URL | Bytes | HTTP | Playwright used |
|---|---|---:|---|:-:|
| imigrasi | imigrasi.go.id/ | 150,118 | 200 HTTP/2 | no |
| oss | oss.go.id/id | 156,059 | 200 HTTP/2 | no |
| pajak | pajak.go.id/ | 135,752 | 200 HTTP/1.1 | no |
| tarubali | tarubali.baliprov.go.id/ | 171,305 | 200 HTTP/1.1 | no |
| bpjs_ketenagakerjaan | bpjsketenagakerjaan.go.id/ | ~115 KB | 200 HTTP/2 | no |

**Surprise vs wave 1 triage:**
- Wave 1 (PR #174) flagged `oss.go.id` as *JS-rendered, needs Playwright*
  and `pajak.go.id` as *timeout*. **Both return usable SSR HTML when
  queried with a real Chrome/Firefox/Safari UA from the rotator.** The UA
  rotation alone resolved the blocker — Playwright was not needed. This
  is a good outcome: Playwright is not installed in the venv, and the
  fallback never fired even when opt-in. The sites *may* be JS-heavy for
  deep navigation (KBLI search forms on OSS, e.g.) but the landing pages
  are server-rendered.
- Wave 2 contract holds: `_BLOCK_STATUSES` (401/403/406/429/503) didn't
  trigger anywhere, so the fallback path stayed cold. Good — means we can
  keep the opt-in semantics even if Playwright is added to the prod image.

### Rate-limit discipline
- Per-source `rate_limit_delay = 3.0 s`. Wall clock for 5 domains: **~18 s**.
- UA rotation counter bumped 5 times (1 per source). Cycle pool = 5 agents.

### NOT done (intentional — wave 4)
- No ingestion into Qdrant, no KG node creation, no embedder call.
- No crawl depth > 1.
- No `change_detector.py` wiring.

---

## Part 3 — PDF chunker perf benchmark: PASS (max 1.10×)

### What shipped
- `apps/backend-rag/backend/core/benchmarks/wave3_chunker_benchmark.py`
  standalone driver. Exits non-zero if any PDF exceeds the 3.0× threshold;
  wired for CI gating.
- Results report at `apps/backend-rag/backend/core/PERF_BENCHMARK.md`.

### Numbers
5 production-representative PDFs, 3 repeats each, median reported:

| Size bucket | File | Pages | baseline | page-aware | ratio |
|---|---|---:|---:|---:|---:|
| 350 KB | 965_Profil Perseroan.pdf | 7 | 0.14 ms | 0.14 ms | **1.04×** |
| 1.3 MB | brochure_balizero_en.pdf | 7 | 0.07 ms | 0.08 ms | **1.10×** |
| 13 MB | UU Nomor 20 Tahun 2025.pdf | 238 | 3.30 ms | 3.24 ms | **0.98×** |
| 21 MB | PP Nomor 28 Tahun 2025.pdf | 383 | 5.28 ms | 5.42 ms | **1.03×** |
| 25 MB | UU_1_2023_KUHP_Baru.pdf | 345 | 5.20 ms | 5.25 ms | **1.01×** |

**Max observed ratio: 1.10× · Threshold: 3.0× · Verdict: PASS.**

The wave 2 contract was conservative — in practice page-aware chunking
costs effectively nothing extra because it reuses the same recursive
separator logic and only pays for the boundary-slice setup.

### Chunk-count observation
Page-aware produces slightly more chunks than baseline on small PDFs
(brochure: 11 → 15) because it never merges across pages. On large PDFs
the delta is tiny (UU 20/2025: 425 → 432 — ~1.6%). This is the correctness
payoff we're buying: every chunk carries a trustworthy `page` field
without meaningful size inflation.

---

## Reality-check vs task success criteria

| Criterion | Target | Achieved |
|---|---|---|
| Gap topics regenerated | 35 (accept ≥25) | **35/35** |
| Top-5 raw snapshot success | 5/5 (accept 3/5 + Playwright) | **5/5 httpx-only** |
| Perf ratio | ≤ 1.5× ideal, ≤ 3× accept | **1.10× max** |
| Wall clock | ≤ 4 h | **~15 min actual** |

---

## Wave 4 TODO (out of scope for wave 3)

1. **Ingestion automation.** Convert `top5_wave3/*/` raw HTML → structured
   docs (BeautifulSoup already used by `LegalScraper._parse_document_item`)
   → chunked with `chunk_by_pages` (when PDFs involved) or
   `semantic_chunk` (HTML) → embedded with `text-embedding-3-small` →
   Qdrant upsert. Gate behind a dry-run flag + Telegram digest.
2. **Embedder batch update.** Migration plan for re-ingesting older KB
   pages with the page-aware chunker so citations can surface page
   numbers (UI-facing). No embedding-model change — still
   `text-embedding-3-small` (frozen by CLAUDE.md rule #12).
3. **Scraper depth > 1.** The one-page snapshot is a *reachability* proof;
   wave 4 needs per-domain selector packs (imigrasi `/berita`, pajak
   `/peraturan`, etc.) to crawl list → detail pages with `change_detector`
   keeping the KG diff-aware.
4. **Playwright install decision.** Still not needed for landing pages,
   but JS-heavy search paths on OSS / pajak may force the hand. Decide
   once wave 4 selector packs fail — don't install pre-emptively.
5. **Gap scanner hardening.** Consider emitting a loud warning (Telegram)
   when Layer A returns 0 topics for *all* domains, as happened during
   the wave 3 first run before the nested-wrapper fix. A silent 0 across
   the board is almost always a parser regression, not reality.
