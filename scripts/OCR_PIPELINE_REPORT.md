# OCR Pipeline v2 — Execution Report

**Date:** 2026-03-07
**Scope:** All 704 companies with Google Drive folders

## Summary

| Metric                                  | Count |     % |
| --------------------------------------- | ----: | ----: |
| **Total processed**                     |   603 |  100% |
| **OK** (data extracted & DB updated)    |   488 | 80.9% |
| **FAIL** (parse failed / contamination) |    78 | 12.9% |
| **NO_PDFS** (no PDF files in folder)    |    32 |  5.3% |
| **EMPTY_FOLDER**                        |     5 |  0.8% |

## DB Field Coverage — Before vs After

| Field              |     Before |       After | Improvement |
| ------------------ | ---------: | ----------: | :---------: |
| registered_address |  65 (9.3%) | 509 (72.3%) |  **+444**   |
| city               |   ~50 (7%) | 520 (73.9%) |  **+470**   |
| province           | ~40 (5.7%) | 432 (61.4%) |  **+392**   |
| npwp_company       | ~200 (28%) | 416 (59.1%) |  **+216**   |
| nib                | ~180 (25%) | 415 (58.9%) |  **+235**   |
| akta_pendirian_no  |     7 (1%) | 450 (63.9%) |  **+443**   |
| sk_menhumkam_no    |   ~50 (7%) | 411 (58.4%) |  **+361**   |
| kbli_code          | ~350 (50%) | 580 (82.4%) |  **+230**   |
| company_type       | 704 (100%) |  704 (100%) |      —      |

## Cost

- **~704 gpt-4o-mini calls** × $0.002/call = **~$1.40 total**
- Text extraction (pypdf): free
- OCR fallback (vision API): ~$0.005/call for scanned PDFs

## Failure Analysis

78 companies failed for these reasons:

1. **Scanned PDFs only** — no text layer, vision API rejects `application/pdf` MIME type
2. **Contamination** — Drive folder contains documents from wrong company
3. **Files too large** — >3MB download limit or >2MB OCR limit
4. **No useful documents** — only personal documents (passports, KITAS), no company docs

## Script Location

- **Repo:** `scripts/ocr_batch_pipeline.py`
- **Desktop:** `~/Desktop/ocr_batch_pipeline.py`
- **Usage:** `python3 ocr_batch_pipeline.py <offset> <batch_size>`
- **Requires:** `DATABASE_URL`, `OPENAI_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON` env vars
