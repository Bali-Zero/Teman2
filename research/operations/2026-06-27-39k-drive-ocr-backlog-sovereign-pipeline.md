---
date: 2026-06-27
domain: operations
client_case: internal
status: draft
author: deep-researcher (Antonello / Bali Zero)
sources:
  - live Pro Postgres figures (intake_queue, 2026-06-27, supplied verified)
  - codebase apps/backend-rag/backend/services/intake/* (read 2026-06-27)
  - Spheron OCR/VLM self-host benchmark 2026 (https://www.spheron.network/blog/best-open-source-ocr-vlm-self-host-gpu-cloud-2026/)
  - Qnovi OCR benchmark 2025 (https://www.qnovi.de/en/blog/ocr-benchmarks-2025-the-best-open-source-models-in-a-practical-test/)
  - Docling GitHub (https://github.com/docling-project/docling)
  - MinerU GitHub (https://github.com/opendatalab/MinerU)
  - Surya GitHub (https://github.com/datalab-to/surya)
  - Marker GitHub + Datalab pricing (https://github.com/datalab-to/marker, https://www.datalab.to/pricing)
  - OCRmyPDF batch docs (https://ocrmypdf.readthedocs.io/en/latest/batch.html)
  - rclone Google Drive backend (https://rclone.org/drive/)
  - JMLab M5 MacBook LLM benchmark (https://jmlab.net/projects/m5-macbook-benchmark-pipeline/)
  - Gemini 3.1 Pro synthesis (full: scratchpad/gemini-out.txt)
  - DeepSeek V4 Pro throughput math (full: scratchpad/deepseek-out.txt) cross-checked vs Claude-computed
---

# Clearing the 39k Drive OCR Backlog with a Sovereign Local Pipeline

## Question

How do we clear ~39,438 `intake-v1` stub documents (legacy worker never ran real OCR/classify; ~92% of blob cache purged but every row carries a recoverable Drive `file_id`) on a 2-3 Mac Apple-Silicon fleet, under a hard Law 2 / UU PDP constraint that all PII OCR/vision stays local (no cloud LLM, no third-party OCR SaaS)? Research throughput/batching architecture, the right tool per modality, REUSE-FIRST candidates, Drive bulk re-fetch, and the single best architecture with expected wall-clock.

## TL;DR

- **Adopt our own already-shipped intake v2 pipeline** (lease queue + `document_instances` dedup + qwen2.5-vl OCR stage + `_download_file` Drive re-fetch + `intake_reprocess_backlog.py` stub-revive). The reuse winner is internal: ~90% built. Build = thin batch-driver + a faster OCR tier, not a new framework.
- **Best architecture: tiered triage router.** Office docs → direct extract (instant); printed scans/images → fast classic OCR (PaddleOCR/Tesseract or Docling); only the ~40% identity docs (KTP/passport/NIB) → qwen2.5-vl-7b for structured JSON field extraction. **Realistic wall-clock ~1.2–1.7 days** on 2 always-on M4-Pro nodes (M5 opportunistic 3rd shortens it).
- **Brute-force "qwen2.5-vl on everything" = ~3.5–4.6 days** — accurate but slowest; avoid as the default path. Surya/Marker have **revenue-cap weight licenses ($5M/$2M)** — a profitable agency should treat them as disqualified for production.

## Verified problem state (live, 2026-06-27)

| Bucket | Count | Disposition |
|---|---|---|
| Total stub rows (`source='drive'`, terminal `done`, empty value) | 39,438 | reprocess |
| PII-poison (PII-guard-blocked KTP/passport) | 872 | **EXCLUDE, never reprocess** |
| Actionable | **38,566** | |
| PDF scans (sampled: 0 text-layer) | ~16,400 | vision OCR |
| Images (jpg/jpeg/png/heic) | ~17,000 | vision OCR |
| Office (docx/doc/xls/xlsx/txt) | ~5,900 | direct text extract, no OCR |
| Non-docs (zip/rar/kml/mov) | ~250 | skip |
| **Heavy vision-OCR set** | **33,400** | |

Drive recovery: every row's `blob_path` follows `.../intake-blobs/drive/1x/<DRIVE_FILE_ID>__name.ext`; the source still exists on Drive and is re-fetchable by `file_id`. The retention cron (`scripts/intake_blob_retention.py`) deliberately keeps the immutable `document_instances` row, so re-fetch is a 1:1 reload, not a re-discovery.

## The decisive REUSE-FIRST finding: the pipeline already exists

`/reuse-first` here points **inward**, not to an external framework. Reading `apps/backend-rag/backend/services/intake/` shows the sovereign pipeline is essentially already built:

- **Work queue + concurrency** — `worker.py`: SKIP-LOCKED lease claim (`lease_owner`/`lease_expires_at`), heartbeat, attempts/backoff, DLQ, review-claim reaper. `DEFAULT_CONCURRENCY=1`, env-tunable `INTAKE_CONCURRENCY`; code comment: "2-3 overlaps... high concurrency starves VRAM and causes empty-page timeouts." This is exactly the backpressure/checkpoint/idempotency layer the task asks for.
- **Dedup-before-OCR** — `document_instances` (migration `212_intake_unified.sql`) is an append-only registry with `blob_hash` + `phash` (perceptual) + `normalized_text_hash`, unique on `(blob_hash, pipeline_version)`, plus `dedup_of`/`near_dup_of` columns on `intake_queue`. Dedup is structural, not bolted-on.
- **OCR stage (sovereign)** — `classify.py` does preprocess + local OCR via qwen-vl in one stage; `stages.py` wires it; `extract.py` runs local field extraction. All Ollama-local. No cloud path.
- **Drive re-fetch by file_id** — `drive_adapter.py::_download_file` already downloads bytes via `service.files().get_media(fileId=...)` + `MediaIoBaseDownload`, async-wrapped.
- **Stub-revive driver** — `scripts/intake_reprocess_backlog.py` already has a stub-revive mode (`v2.1-stub-revive` pipeline version) that resets queue rows to `pending`/stage NULL with a bumped `pipeline_version` so `routing._make_routing_key` yields a fresh proposal. This is the re-arming mechanism for these 39k rows.

**Implication:** do not adopt Docling/MinerU/Unstructured as the spine. The spine is ours and is Postgres-native, lease-correct, and already PII-local. The genuine gaps are (1) a **batch driver** that re-fetches from Drive in bulk and enqueues the 38,566 with the stub-revive version, and (2) a **faster/triaged OCR tier**, because the current `extract.py` uses SEA-LION 32B — which MEMORY flags as ~80% noise as a reviewer and is heavy (25-45s warm).

## Local OCR / document-understanding landscape (early 2026)

Benchmarks below are mostly **vendor self-reported on GPU**; Apple-Silicon (MPS/Metal) numbers are far lower and are the ones that bind us. Flagged where unverified.

| Tool | Params | License | Sovereign? | Indonesian / MPS | Role fit |
|---|---|---|---|---|---|
| **qwen2.5-vl-7b** (installed) | 7B | Apache-2.0 | yes (Ollama) | strong multi-lang OCR + spatial layout; runs on MPS via Ollama, ~70 tok/s on M5 Max [JMLab] | **Tier-3 identity-doc JSON field extraction** |
| **Docling** (IBM) | converter | **MIT** | yes, air-gap supported | PDF/DOCX/XLSX/PPTX/HTML/images; M3 Max ~1.27 s/page CPU (digital, not heavy scan-OCR); 62k stars | **Tier-1 office + Tier-2 digital-PDF parsing** |
| **PaddleOCR / PaddleOCR-VL** | 0.9B (VL) | **Apache-2.0** | yes | 100+ langs incl. Indonesian; MPS compile clunky; OmniDocBench v1.6 96.33 (self-reported) | Tier-2 classic line OCR (clean license) |
| **Tesseract / OCRmyPDF** | classic | Apache / MPL-2.0 | yes | Indonesian (`ind`) trained data; CPU-bound, high-parallel | Tier-2 cheap triage pass (printed text) |
| **Surya 2** | 650M | Apache code / **Open-RAIL-M weights, $5M revenue cap** | local but **license trap** | 90+ langs incl. Indonesian; Metal **~0.108 pg/s** (8-parallel) | DISQUALIFIED (cap) |
| **Marker** | DL pipeline | GPL-3 / **Open-RAIL-M weights, $2M cap** | local but **license trap** | M4 MPS **~0.22 pg/s**; no own heavy vision OCR (digital PDFs) | DISQUALIFIED (cap + not for scans) |
| **MinerU** | pipeline | custom Apache-based; **weights may carry NC terms** | mostly | PP-OCRv6, 109 langs; MPS heavy; 70.9k stars; OmniDocBench 86.47 | possible, heavy env, compliance check needed |
| **dots.ocr** | ~1.7B | MIT | yes | ~100 langs; ~3.5GB VRAM | alt VLM (NOT a macOS Vision wrapper — see Disagreements) |
| **DeepSeek-OCR** | ~3B MoE | MIT | yes | ~100 langs; MLX/llama.cpp | alt VLM |
| **GOT-OCR2.0** | ~580M | Apache-2.0 | yes | 20+ langs; memory-heavy MPS | alt, less schema-friendly than Qwen |
| **Granite-Docling** | 258M | Apache-2.0 | yes | primarily English | Docling layout helper, weak for ID |
| **Unstructured.io OSS** | framework | Apache-2.0 | yes (local models) | wraps Tesseract/Docling; dependency-heavy | redundant vs Docling |
| **Apache Tika** | Java | Apache-2.0 | yes | instant office extract; Tesseract OCR; no MPS | office-only fallback |

License verdict: **clean = qwen2.5-vl (Apache), Docling (MIT), PaddleOCR (Apache), Tesseract/OCRmyPDF, dots.ocr (MIT), DeepSeek-OCR (MIT).** Avoid Surya and Marker weights in production; treat MinerU's model weights as needing a license read before commercial use.

## The right tool per modality

- **Office (docx/doc/xls/xlsx/txt, ~5,900):** direct library extraction — python-docx / openpyxl / pdfplumber for any digital text, or Docling (MIT) for a single uniform converter. No OCR. Total cost negligible (~5 min for the whole bucket).
- **Digital-PDF text layer (none here — all sampled scans had 0 text layer):** pymupdf/pdfplumber would short-circuit OCR; kept in the router for future Drive intake even though this batch has none.
- **Scanned PDFs + images (~33,400):** vision OCR. Two-speed: cheap classic OCR (Tesseract `ind` / PaddleOCR, CPU, high-parallel) for triage + plain-text scans; qwen2.5-vl-7b for documents that need **structured field extraction** (KTP NIK/name/address, passport number/dates, NIB, NPWP).

## Numerical analysis (wall-clock to clear 33,400 vision jobs, 2-node fleet)

Two independent derivations — Claude-computed and DeepSeek V4 Pro — agree within rounding. Inputs: 39,960 vision *pages* (16,400 PDF × 1.4 avg + 17,000 images) or 33,400 *jobs*; 2 always-on M4-Pro nodes; thermal sustained-efficiency factor 0.8 on realistic numbers; 20 productive h/day.

| Config | Engine | Realistic sustained | Valid for scans? | ID-field accuracy |
|---|---|---|---|---|
| **4 — Tiered triage** | cheap OCR + qwen2.5-vl on ~40% | **~1.2–1.7 days** | yes | highest where it matters |
| 3 — Marker fleet | Marker MPS 0.22 pg/s | ~1.6 days | **NO (digital PDFs only)** | n/a |
| 2 — Surya fleet | Surya Metal 0.108 pg/s ×2 | ~3.2 days | yes | line OCR, weaker field-level |
| 1 — qwen2.5-vl everywhere | VLM 20 s/page, 4 streams | **~3.5–4.6 days** | yes | highest on every doc, slowest |

Key derivations (realistic, eff 0.8):
- **Config 1** (brute VLM): 39,960 pages × 20 s ÷ 4 streams ÷ 0.8 = ~249,750 s ≈ **69 h ≈ 3.5 days** (4-stream); ~4.6 days at 3-stream. Per-page latency 12/20/30 s is **extrapolated** from ~35–55 tok/s on M4 Pro × 300–900 output tokens + vision-encoder prefill — FLAG: measure on the actual Pro before committing.
- **Config 4** (tiered): cheap pass 39,960 pg ÷ 16 pg/s (8 CPU streams) ≈ 2,500 s (~0.7 h); heavy VLM on ~13,360 identity docs × 20 s ÷ 4 ÷ 0.8 ≈ 83,500 s (~23 h). Total **~24 h ≈ 1.2 days** (single-page) to ~1.7 days (1.4 avg pages). The 60% non-identity scans are satisfied by cheap-pass plain text.
- **Office bucket:** 5,900 × ~0.05 s ≈ 5 min, negligible in every config.

Caveat carried from DeepSeek: **Marker has no heavy vision-OCR engine** — its 0.22 pg/s is for digital PDFs, so Config 3 is invalid for this scan-heavy backlog and is listed only for completeness.

Adding the opportunistic M5 as a 3rd node (~50% more vision streams when idle) pulls Config 4 toward ~0.8–1.1 days.

## Google Drive bulk re-fetch (~38.6k by file_id)

- **Reuse our own `_download_file`** (Drive API `get_media`, already authed via `google_drive_tokens`, async). Wrap it in the batch driver with a bounded concurrency semaphore + exponential backoff on 403/429 + checkpoint cursor.
- **Rate reality:** Google's default is ~10 queries/s per client_id, but real-world per-user throttling limits sustained downloads to **~2 files/s** [rclone]. At 2 files/s, 38.6k files ≈ **5.4 h** of fetch wall-clock — small vs OCR, and overlappable with OCR (fetch tier N+1 while OCR tier N runs).
- **Use a dedicated Google Cloud client_id** (not a shared one) and `--tpslimit`/transfers ≈ 2-4 to avoid "User rate limit exceeded" (which forces a 24 h cooldown). rclone `backend copyid drive: <ID> <path>` is a viable alternative tool, but staying inside `drive_adapter` keeps one auth + one sovereign code path.
- **Resumability:** idempotent on `intake_key` + `blob_hash` dedup means a re-run skips already-fetched blobs for free; checkpoint = last processed `intake_queue.id`.

## Recommendation (ranked)

**Option A (recommended) — Re-arm our v2 pipeline as a tiered batch backfill.**
1. Build one batch driver `scripts/intake_drive_backlog_backfill.py` that: selects the 39,438 stub rows, EXCLUDES the 872 poison rows (status guard), re-fetches each blob via `drive_adapter._download_file(file_id)`, and enqueues with `pipeline_version='v2.1-stub-revive'` through the existing idempotent path.
2. Insert a **triage tier** before the heavy extractor: office → direct extract; scans/images → cheap Tesseract(`ind`)/PaddleOCR pass; route only identity-type docs to qwen2.5-vl-7b structured JSON. Keep qwen2.5-vl as the Tier-3 ID engine (it natively emits `{NIK, name, address, ...}` — no fragile regex).
3. **Replace SEA-LION 32B in `extract.py`** for this backlog with qwen2.5-vl JSON-schema extraction (faster, flagged-better, already installed). SEA-LION's ~80% reviewer-noise + 25-45s latency is a throughput and quality drag.
4. Run on Pro + Mini H24 with `INTAKE_CONCURRENCY=2` (48GB Pro can hold 2-3 of the 6GB model; 24GB Mini 1-2), M5 opportunistic. Proposals land in `document_routing_proposal` → HITL on kita.balizero.com (unchanged).
**Expected wall-clock: ~1.2–1.7 days** (2 nodes), ~0.8–1.1 days with M5.

**Option B — Brute-force qwen2.5-vl on everything.** Simpler (no triage logic), max accuracy on all docs, but **~3.5–4.6 days** and melts the fleet longer. Use only if triage classification proves unreliable on this corpus.

**Option C — Adopt Docling (MIT) as the converter, qwen2.5-vl as Tier-3.** Cleanest external reuse if we ever want one uniform office+PDF+image converter beyond this batch. Adds a dependency and does NOT replace our queue/dedup/routing (still ours). Worth it as a forward investment, not required to clear this backlog.

Reuse beats build everywhere except the thin batch driver and the triage router. No external framework satisfies sovereignty + Postgres-lease + Indonesian-ID-field extraction better than the stack already on disk.

## Disagreements / open questions

- **Gemini hallucination flagged:** Gemini described `dots.ocr` as "an Apple-Silicon wrapper for macOS native Vision framework running on the Neural Engine." That is **wrong** — dots.ocr is a ~1.7B VLM (RedNote/Xiaohongshu, MIT, ~3.5GB VRAM per Spheron). Do not adopt it on that false premise. Treated as a generic local VLM alternative only.
- **GitHub-star drift:** Gemini under-counted stars; verified WebFetch gives Docling 62.2k and MinerU 70.9k. Used verified numbers.
- **qwen2.5-vl per-page latency on M4 Pro is EXTRAPOLATED** (35-55 tok/s × token budget + prefill). The 12/20/30 s band drives every wall-clock estimate. **Measure on the actual Pro with 50 real documents before committing** — single biggest source of estimate error.
- **Triage split (40% identity / 60% plain) is an assumption.** If a larger share are identity docs, Config 4 trends toward Config 1. Sample the corpus to set the real ratio.
- **Office-doc count (5,900) assumed all digital-text.** Any image-only "office" exports would fall back to OCR; verify by attempting text extraction first (the router already short-circuits on a present text layer).

## Checklist for action

- [ ] Sample 50 real backlog documents on the Pro; **measure actual qwen2.5-vl-7b per-page latency** and the identity-vs-plain ratio (replaces the two biggest extrapolations).
- [ ] Write `scripts/intake_drive_backlog_backfill.py`: select 39,438 stub rows, hard-EXCLUDE the 872 poison rows, re-fetch via `drive_adapter._download_file`, enqueue at `pipeline_version='v2.1-stub-revive'` (idempotent on `intake_key`).
- [ ] Add a triage tier (office→direct, scans→Tesseract `ind`/PaddleOCR cheap pass, identity→qwen2.5-vl JSON) and swap qwen2.5-vl for SEA-LION in `extract.py` for this run.
- [ ] Provision a dedicated Google Cloud client_id; cap Drive fetch at 2-4 concurrent with backoff on 403/429; checkpoint on last `intake_queue.id`.
- [ ] Set `INTAKE_CONCURRENCY=2` on Pro + Mini, run H24; add M5 opportunistically; watch `intake_stage_metrics` latency + thermal throttling.
- [ ] Confirm proposals flow to `document_routing_proposal` → HITL review on kita.balizero.com unchanged; verify the 872 poison rows never re-enter the queue.

## Sources

1. Live Pro Postgres figures (intake_queue), 2026-06-27 — supplied verified.
2. Codebase read 2026-06-27: `apps/backend-rag/backend/services/intake/{worker,classify,stages,extract,drive_adapter}.py`, `db/migrations_v2/212_intake_unified.sql`, `scripts/intake_reprocess_backlog.py`, `scripts/intake_blob_retention.py`.
3. Spheron, "Best Open-Source OCR and Document VLMs to Self-Host 2026" — https://www.spheron.network/blog/best-open-source-ocr-vlm-self-host-gpu-cloud-2026/
4. Qnovi, "OCR Benchmarks 2025" — https://www.qnovi.de/en/blog/ocr-benchmarks-2025-the-best-open-source-models-in-a-practical-test/
5. Docling — https://github.com/docling-project/docling (MIT, 62.2k stars).
6. MinerU — https://github.com/opendatalab/MinerU (custom Apache-based, 70.9k stars).
7. Surya — https://github.com/datalab-to/surya (Apache code / Open-RAIL-M weights $5M cap).
8. Marker + Datalab pricing — https://github.com/datalab-to/marker , https://www.datalab.to/pricing ($2M cap; M4 MPS ~0.22 pg/s).
9. OCRmyPDF batch — https://ocrmypdf.readthedocs.io/en/latest/batch.html
10. rclone Google Drive backend (rate limits, copyid) — https://rclone.org/drive/
11. JMLab M5 MacBook LLM benchmark (qwen2.5-vl 7B ~70 tok/s) — https://jmlab.net/projects/m5-macbook-benchmark-pipeline/
12. Gemini 3.1 Pro synthesis — full output: scratchpad/gemini-out.txt
13. DeepSeek V4 Pro throughput math (cross-checked vs Claude-computed) — full output: scratchpad/deepseek-out.txt
