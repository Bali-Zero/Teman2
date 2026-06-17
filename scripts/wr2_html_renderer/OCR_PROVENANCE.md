# EasyOCR — provenance, license & rationale

Per reuse-first §4 (license gate) + §7 (provenance tracking).

| Dependency | Source                              | License        | Version                     |
| ---------- | ----------------------------------- | -------------- | --------------------------- |
| `easyocr`  | https://github.com/JaidedAI/EasyOCR | **Apache-2.0** | `>=1.7.2` (installed 1.7.2) |

> License note: EasyOCR ships under **Apache-2.0** (not MIT, as I first said in
> chat — corrected here against the repo `LICENSE`). Apache-2.0 is permissive and
> vendorable as a dependency with attribution; no copyleft obligation. The
> pre-trained recognition/detection weights it downloads are also Apache-2.0
> (JaidedAI model zoo).

Installed into the backend venv on **M5 + Pro + Mini** on 2026-06-07 (all three
verified `Reader(['en'], gpu=False)` → "Reader OK").

## Why a dependency (not vendored source) + why EasyOCR over the alternatives

The designer loop (`designer_loop.py`) uses Claude vision as its critic + brand
verifier. VLMs **hallucinate text specifics** — in the E2E they reported
`"5 RULES CHANGED."` when the slide says `"3 RULES"`, and a garbled
`"...keewkuhan"` that wasn't there. Because the brand verifier is fail-closed, a
hallucinated "headline garbled/clipped" can block a _good_ change.

`ocr_check.py` closes that gap with an OCR round-trip (SOTA dimension #1): OCR the
rendered PNG and confirm the headline reads back verbatim. The engine must be a
**pure OCR model that reads text, not a generative model that can invent it**.

| Option                                     | Verdict                                                                                                                                                                                                                                      |
| ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **EasyOCR** (chosen)                       | Pure OCR (reads, never generates) → right tool for an anti-hallucination oracle. pip-only (no system binary) → **identical on M5/Pro/Mini**. Reuses `torch` already in the venv. Strong on large display type over a photo (our exact case). |
| tesseract (`crm_guardian/ocr.py`)          | System binary, **present only on Pro**, absent on M5+Mini → non-identical behavior; built for A4 scans, weak on big uppercase over photos.                                                                                                   |
| qwen2.5vl (`crm_guardian/ocr.py` fallback) | A **VLM** — hallucinates the same way the critic does → wrong tool for the job. Also slow (30–120s) + Ollama-dependent per host.                                                                                                             |

The existing tesseract→qwen2.5vl cascade in `crm_guardian/ocr.py` is **untouched**
— it serves CRM document intake (multi-page PDFs), a different problem.

## Operational notes

- **Model download**: on first `Reader` init EasyOCR downloads detection +
  recognition weights (~64MB total) to `~/.EasyOCR/`. One-time per machine; runs
  fully **offline** afterwards → SYMBIOSIS Law 6 (local sovereignty) preserved
  after warm-up. The install step warmed all three caches.
- **torch pin side-effect**: `easyocr` pulls `torchvision`, which pins
  `torch==2.12.0`. On Mini this auto-upgraded torch 2.11.0 → 2.12.0 (no error;
  Reader init fine). Net: all three machines now on torch 2.12.0 — parity, but
  recorded here in case a Mini-only consumer depended on 2.11.0.
- **Determinism / parity**: `gpu=False` forces CPU inference → no CUDA/MPS
  nondeterminism, and identical scores across the three machines (the whole point
  of choosing a pip-only engine).
- **Graceful degradation**: if EasyOCR is unavailable, `headline_legible` returns
  `degraded=True, legible=True` and the loop does NOT block (same philosophy as
  the QA-outage pass-through in the production layout loop).

Fetched/installed 2026-06-07.
