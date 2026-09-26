---
date: 2026-06-27
domain: operations
client_case: internal
status: draft
author: deep-researcher (Antonello / Bali Zero)
sources:
  - Ollama library qwen3-vl (https://ollama.com/library/qwen3-vl) — tags/sizes/min-version, fetched 2026-06-27
  - HF Qwen/Qwen3-VL-8B-Instruct (https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct) — license apache-2.0, OCR 32-lang, fetched 2026-06-27
  - Qwen3-VL Technical Report (https://arxiv.org/abs/2511.21631)
  - GLM-OCR GitHub (https://github.com/zai-org/GLM-OCR) — MIT weights, OmniDocBench v1.5 94.62, fetched 2026-06-27
  - Ollama library glm-ocr (https://ollama.com/library/glm-ocr) — tags latest/q8_0/bf16, fetched 2026-06-27
  - dots.ocr GitHub (https://github.com/rednote-hilab/dots.ocr) — MIT, 1.7B, JSON layout, fetched 2026-06-27
  - mlx-vlm dots_ocr (https://github.com/Blaizzy/mlx-vlm/blob/main/mlx_vlm/models/dots_ocr/README.md)
  - HF deepseek-ai/DeepSeek-OCR (https://huggingface.co/deepseek-ai/DeepSeek-OCR) — MIT, ~3B MoE/570M active, fetched 2026-06-27
  - Ollama library deepseek-ocr (https://ollama.com/library/deepseek-ocr) — 3b tag 6.7GB, Ollama v0.13.0+, fetched 2026-06-27
  - HF PaddlePaddle/PaddleOCR-VL (https://huggingface.co/PaddlePaddle/PaddleOCR-VL) — apache-2.0, 0.9B, 109 langs, fetched 2026-06-27
  - HF openbmb/MiniCPM-V-4_5 README (https://huggingface.co/openbmb/MiniCPM-V-4_5/blob/main/README.md) — Apache-2.0, optional registration, fetched 2026-06-27
  - HF stepfun-ai/GOT-OCR2_0 (https://huggingface.co/stepfun-ai/GOT-OCR2_0) — apache-2.0
  - Spheron OCR/VLM self-host benchmark 2026 (https://www.spheron.network/blog/best-open-source-ocr-vlm-self-host-gpu-cloud-2026/)
  - LlamaIndex "OmniDocBench is Saturated" (https://www.llamaindex.ai/blog/omnidocbench-is-saturated-what-s-next-for-ocr-benchmarks)
  - Indonesian ID Card Extractor (classic OCR+NLP) arXiv 2101.05214 (https://arxiv.org/pdf/2101.05214)
  - Gemini 3.1 Pro landscape sweep (full: scratchpad/gemini-ocr-out.txt)
  - DeepSeek V4 Pro throughput/latency-factor math (full: scratchpad/deepseek-out.txt)
  - Prior internal study: research/operations/2026-06-27-39k-drive-ocr-backlog-sovereign-pipeline.md
---

# Local OCR Model Bake-off for Indonesian ID / Legal Documents

## Question

Is there a LOCAL model better than `qwen2.5vl:7b` for OCR + structured field-extraction on Indonesian identity/legal documents (KTP, passports, NIB, NPWP, KITAS/KITAP, akta pendirian, OSS certificates), runnable sovereign on Apple Silicon (Pro M4 Pro 48GB / Mini + M5 24GB) via Ollama and/or mlx-vlm, with a commercially-clean license for a profitable agency? Produce a ranked grounded comparison, a clear stay/switch recommendation, and a short local bake-off plan.

## TL;DR

- **No public benchmark covers Indonesian-ID-document field-extraction for ANY of these VLMs.** Every accuracy claim is multilingual-transfer (Latin script + broad-language pretraining), not Indonesian-ID-specific. This is the single binding fact: the decision cannot be made on benchmarks alone — it needs a local bake-off on real KTP/passport pages.
- **License gate: all live candidates pass clean** (Apache-2.0 or MIT, no revenue cap). Surya ($5M) and Marker ($2M) stay disqualified (prior study). The only license correction to make: **MiniCPM-V 4.5 is Apache-2.0** (registration optional) — an earlier Gemini pass mislabeled it as a restrictive community license.
- **Recommendation: STAY on `qwen2.5vl:7b` as the production default, and bake off Qwen3-VL-8B (primary) + GLM-OCR-0.9B (speed) against it on 50 real docs.** Qwen3-VL is the same-family, same-license, drop-in Ollama upgrade with an explicit OCR-robustness jump (32 languages up from 10, hardened for poor light / blur / skew — exactly our phone-camera failure mode). Do not switch blind: a smaller/faster model that hallucinates a plausible-but-wrong NIK or city name on a glared KTP is worse than a slower correct one.

## License GO/NO-GO gate (applied first)

All candidates below clear the commercial gate. Verbatim license tags fetched 2026-06-27:

| Model | License (verbatim) | Revenue cap? | Gate |
|---|---|---|---|
| qwen2.5vl:7b (incumbent) | `apache-2.0` | No | GO |
| Qwen3-VL 4B/8B | `apache-2.0` (HF model card) | No | GO |
| GLM-OCR 0.9B | "GLM-OCR model is released under the MIT License" (weights); repo code Apache-2.0 | No | GO |
| dots.ocr 1.7B | `MIT` | No | GO |
| DeepSeek-OCR ~3B MoE | `MIT` | No | GO |
| PaddleOCR-VL 0.9B | `apache-2.0` | No | GO |
| MiniCPM-V 4.5 8B | "model weights and code are open-sourced under the **Apache-2.0** license"; registration questionnaire **optional** | No | GO |
| GOT-OCR2.0 ~580M | `apache-2.0` | No | GO |
| Granite-Docling 258M | `apache-2.0` | No | GO |
| PP-OCRv5 (classic) | `apache-2.0` | No | GO |
| Tesseract `ind` (classic) | `apache-2.0` | No | GO |
| ~~Surya 2~~ | Open-RAIL-M weights, **$5M revenue cap** | YES | NO-GO |
| ~~Marker~~ | Open-RAIL-M weights, **$2M revenue cap** | YES | NO-GO |

No live candidate fails the license gate. The competition is decided entirely on accuracy/runnability, not licensing.

## Ranked comparison (best -> worst for THIS task, license gate already passed)

Ranking axis: Indonesian-ID field-extraction fitness = (multilingual OCR strength on noisy phone photos) x (native structured-JSON) x (proven local runnability), speed as tiebreaker. **All Indonesian-accuracy cells are "no ID-specific evidence" — ranking reflects priors + family lineage + robustness claims, NOT measured Indonesian numbers.**

| Rank | Model | Size / quant that fits | Apple-Silicon path | Indonesian-ID evidence | Structured JSON | Speed vs qwen2.5vl:7b (proxy) | Verdict |
|---|---|---|---|---|---|---|---|
| **1** | **Qwen3-VL-8B-Instruct** | 8B, `qwen3-vl:8b` 6.1GB Q4 (needs Ollama 0.12.7) | **Ollama tag live** + mlx-community | None ID-specific; OCR 32 langs (up from 10), explicitly hardened for poor light / blur / tilt; inherits Qwen2.5 multilingual priors | Native (QwenVL-HTML + JSON on prompt) | ~1.1x (comparable) | **Primary challenger** — same family, same license, drop-in, robustness upgrade targets our exact failure mode |
| 2 | qwen2.5vl:7b (incumbent) | 7B, 6GB Q4 (installed) | **Installed, Ollama** | None ID-specific; proven in our pipeline; native `{NIK,nama,...}` JSON | Native | 1.0x (baseline) | **Hold as default** — only displace on measured win |
| 3 | Qwen3-VL-4B-Instruct | 4B, `qwen3-vl:4b` 3.3GB | Ollama tag live | Same lineage as #1, smaller | Native | ~0.6x (faster) | Speed/accuracy hedge if 8B too slow on Mini/M5 24GB |
| 4 | GLM-OCR-0.9B | 0.9B, `glm-ocr:latest` 2.2GB / `q8_0` 1.6GB | **Ollama tag live** + mlx-vlm | None ID-specific; **#1 OmniDocBench v1.5 (94.62)** beating frontier models — but that benchmark is doc-parsing/Latin/CJK, not Indonesian ID | Native (JSON/Markdown/LaTeX) | ~0.15x (very fast) | **Speed challenger** — if accurate enough on KTP, 6-7x throughput; risk: tiny model may hallucinate degraded fields |
| 5 | dots.ocr-1.7B | 1.7B, ~3.4GB FP16 | **No Ollama tag**; mlx-vlm conversion exists (Blaizzy/mlx-vlm) | None ID-specific; 100+ lang claim, Indonesian not explicitly listed | Native (JSON layout w/ bbox + categories) | ~0.25x (fast) | Layout-first design fits ID cards; needs mlx-vlm path (more setup than Ollama) |
| 6 | MiniCPM-V 4.5 8B | 8B, ~6GB Q4 | Ollama + llama.cpp + mlx-community | None ID-specific; strong OCRBench (claims > GPT-4o/Gemini 2.5), high-res tiling good for skewed photos | Native | ~1.1x | Accuracy hedge for worst photos; same weight class as incumbent |
| 7 | DeepSeek-OCR 3B MoE | 3B total / 570M active, `deepseek-ocr:3b` 6.7GB (needs Ollama 0.13.0) | Ollama tag live; llama.cpp GGUF (PR-branch only) | None ID-specific; markdown-first (JSON not documented) | Scaffolded (markdown -> needs mapping) | ~0.5x | "Optical compression" optimizes for long docs, not single ID cards; markdown output adds a mapping step |
| 8 | PaddleOCR-VL-0.9B | 0.9B, ~FP16 | **Not in Ollama**; custom Transformers/Paddle | None ID-specific; 109 langs (Indonesian not explicitly listed); classic Paddle pipeline supports `id` well | Native (JSON/Markdown, strong tables) | ~0.15x | Strong on tables/structure; Paddle/Metal install is clunky vs Ollama |
| 9 | GOT-OCR2.0 ~580M | 580M | Transformers / mlx-vlm | None; English/Chinese layout focus | Prompt-scaffolded (prefers markdown) | ~0.1x | Weak schema control for ID fields |
| 10 | Granite-Docling 258M | 258M | Docling SDK / Transformers | None; English/Latin enterprise PDF focus | DocTags -> JSON | ~0.1x | Built for invoices/papers, weak for ID layout + Bahasa |
| — | PP-OCRv5 (~5M, classic) | tiny | native | **Indonesian dictionary verified** | **NONE** (raw text + bbox) | instant | Triage/text only; needs a VLM/regex to reach `{NIK,...}` JSON |
| — | Tesseract `ind` (classic) | classic | native (brew) | **Indonesian traineddata verified** | **NONE** | instant | Baseline for clean printed text; **breaks on glare/skew** (our common case) |

## The decisive finding: zero Indonesian-ID benchmark evidence exists

For every VLM here, the Indonesian-accuracy cell is "no ID-specific evidence." OmniDocBench / OCRBench / olmOCR-bench measure English/Chinese document parsing; OmniDocBench is now described as saturated (top models clustered ~94+). None contains Indonesian KTP/passport layouts. The only verified Indonesian support is in the *classic* engines (Tesseract `ind` traineddata, PaddleOCR `id` dictionary) — and those emit raw text, not the `{NIK, nama, tempat_tgl_lahir, alamat, no_passport, masa_berlaku, NPWP}` structure that is the actual value. Public prior art on Indonesian KTP extraction (arXiv 2101.05214) used classic OCR + heavy NLP post-processing, predating modern VLMs — confirming this is a narrow domain no leaderboard covers. **Conclusion: benchmark numbers are proxies here; only a local bake-off on real noisy KTP/passport pages resolves the choice.** Anyone claiming a model is "better for Indonesian KTP" from a leaderboard score is extrapolating.

## Numerical analysis (latency factor + throughput, DeepSeek V4 Pro, proxies)

DeepSeek's architectural point is the load-bearing caveat for the speed column above:

- **For a prefill-dominated, short-JSON-output OCR task, per-page latency is gated by vision-encoder token count / image-tiling resolution — NOT total params.** A 0.9B model is not automatically 7x faster end-to-end: if its vision tower tiles a high-res KTP photo into several thousand visual tokens, O(n^2) prefill attention dominates and the param-count advantage shrinks. Active (MoE) params cut compute per token but not the memory footprint or the visual-token prefill. So the "~0.15x GLM-OCR" band is an upper bound on speedup that only a real measurement confirms.
- Relative per-page latency bands vs qwen2.5vl:7b=1.0x (proxy, NOT measured): Qwen3-VL-4B ~0.6x · Qwen3-VL-8B ~1.1x · GLM-OCR-0.9B ~0.15x · dots.ocr-1.7B ~0.25x · DeepSeek-OCR ~0.5x · MiniCPM-V-4.5 ~1.1x · PaddleOCR-VL ~0.15x.
- Throughput sanity (relevance to the 33,400-page backlog from the prior study): a model at 4s/page across 2 M4-Pro nodes x 4 streams x 20h/day x eff 0.8 = 8 parallel pages / 4s = 2 pg/s x 0.8 = 1.6 pg/s = 115,200 pg/day -> 33,400 / 115,200 = **~0.29 days**. i.e. a genuinely-4x-faster accurate model would cut the prior study's ~1.2-1.7-day Config-4 wall-clock to well under a day. **But speed is axis #3; do not trade Indonesian field-accuracy for it.**

## Disagreements / hallucinations caught and resolved

- **MiniCPM-V 4.5 license** — Gemini sweep claimed "MiniCPM Model Community License (requires registration)." The HF README verbatim says "model weights and code are open-sourced under the **Apache-2.0** license" with an **optional** registration questionnaire. **Trusting the verbatim model card: Apache-2.0, GO.** The historical MiniCPM non-commercial worry is obsolete for 4.5.
- **GLM-OCR Ollama availability** — Gemini claimed "no official Ollama tag yet." The Ollama library page `ollama.com/library/glm-ocr` exists with tags `latest` (2.2GB), `q8_0` (1.6GB), `bf16` (2.2GB). **Trusting the live Ollama page: tag exists.** GLM-OCR is therefore a one-command pull, not an mlx-vlm-only build — materially lowers its bake-off cost.
- **dots.ocr identity** (carried from prior study) — re-confirmed it is a ~1.7B RedNote/Xiaohongshu VLM (MIT), NOT a macOS Vision wrapper. Not on Ollama; mlx-vlm conversion exists.
- **Qwen3-VL OCR language-count drift** — Ollama page says "32 languages (up from 10)"; HF card says "(up from 19)." Either way it is a strict expansion over Qwen2.5-VL and adds languages (Greek/Hebrew/Hindi/Romanian/Thai cited); **Indonesian is not confirmed in the explicit 32-language OCR list** in any source I could fetch — flagged as unverified, do not assume it.
- **Terminology** — Gemini said "mlx-community GGUF" for Qwen3-VL; MLX uses safetensors, not GGUF. Minor; the runnable fact (Ollama tag + mlx-community conversion) stands.

## Recommendation

**Stay on `qwen2.5vl:7b` as the production default. Run a 3-way bake-off before any switch. Most likely outcome: switch to Qwen3-VL-8B if it wins on real KTPs; keep GLM-OCR-0.9B in reserve as a speed tier for high-volume clean scans.**

Why not switch blind to a flashy small model: GLM-OCR's #1 OmniDocBench score and PaddleOCR-VL's table strength are real but measured on the wrong domain. For ID documents the failure that costs us is a *confidently-wrong* NIK digit or a hallucinated Indonesian city on a glared photo — and sub-2B models are the most exposed to that exact error (DeepSeek's point: degraded fields + small linguistic prior = plausible fabrication). qwen2.5vl:7b is already proven in our pipeline and emits the right JSON natively. Qwen3-VL-8B is the rational upgrade target precisely because it is the *same family + same Apache-2.0 license + same Ollama workflow*, so adopting it is a model-tag swap with near-zero integration risk, and its headline change (OCR hardened for poor light / blur / tilt) is aimed straight at our phone-camera corpus.

**The single most important caveat:** no number in this report is measured on an Indonesian ID document. Treat the entire ranking as a hypothesis to be falsified by the bake-off below.

## Empirical-validation plan (the bake-off to actually run)

Run on the Pro (M4 Pro 48GB), sovereign, on REAL but de-identified-in-output docs:

1. **Assemble a 50-page gold set** from the existing backlog: ~20 KTP, ~10 passports (mix Indonesian + foreign), ~5 NIB, ~5 NPWP, ~5 KITAS/KITAP, ~5 akta pendirian pages (incl. director pages 2-3). Deliberately include glare / skew / low-light / handwriting samples. Hand-key the ground-truth fields ONCE into a local CSV (this is the scoring key; keep it on the Pro, never in any report/commit — PII).
2. **Pull the 3 contenders** (all Ollama, no build needed): `ollama pull qwen3-vl:8b` · `ollama pull glm-ocr` · incumbent `qwen2.5vl:7b` already installed. Optional 4th: `ollama pull qwen3-vl:4b` (speed hedge for the 24GB nodes). dots.ocr only if the top 3 underwhelm (it needs an mlx-vlm conversion step).
3. **Single fixed prompt + JSON schema** for all models (same `{NIK,nama,tempat_tgl_lahir,alamat,no_passport,masa_berlaku,NPWP,doc_type}` schema) so the comparison isolates the model, not the scaffolding. Use Ollama `/api/generate` (GLM-OCR's docs warn its OpenAI-compat vision path is lossy).
4. **Score by hand**, per field: exact-match accuracy on the high-stakes fields (NIK 16-digit, passport number, NPWP, dates) — these are GO/NO-GO; an 80% model that flips a NIK digit is unusable. Track per-page wall-clock (`time`) on the Pro for the real speed numbers (replaces every proxy band in this report).
5. **Decision rule:** switch only if a challenger beats qwen2.5vl:7b on high-stakes field exact-match by a clear margin AND never confidently-fabricates a field on the degraded samples. If GLM-OCR matches accuracy at ~4-7x speed, adopt it as a fast tier for clean scans and keep a VLM-7B/8B tier for the hard photos (tiered router, consistent with the prior pipeline study). If nothing beats the incumbent, the answer is "stay" — and that is a valid, money-saving result.

## Checklist for action

- [ ] Assemble + hand-key the 50-page Indonesian gold set on the Pro (KTP/passport/NIB/NPWP/KITAS/akta, include glare/skew/handwriting); keep the ground-truth key local, never committed (PII).
- [ ] `ollama pull qwen3-vl:8b` and `ollama pull glm-ocr` (verify Ollama >= 0.12.7 for qwen3-vl, >= 0.13.0 if also testing deepseek-ocr); confirm qwen2.5vl:7b baseline still warm.
- [ ] Run all 3 (optionally +qwen3-vl:4b) on the 50 pages with ONE fixed JSON-schema prompt via `/api/generate`; capture per-page wall-clock with `time`.
- [ ] Hand-score per-field exact-match (NIK/passport/NPWP/dates = GO/NO-GO) + log any confidently-wrong fabrication on degraded samples.
- [ ] Decide: stay on qwen2.5vl:7b, switch to qwen3-vl:8b, or adopt GLM-OCR as a fast tier behind a VLM tier — and record the measured numbers (these replace every proxy in this report).
- [ ] If switching, update the intake pipeline OCR stage tag and re-run the prior study's wall-clock estimate with the measured per-page latency (closes the biggest extrapolation flagged there).

## Sources

1. Ollama `qwen3-vl` library — tags 2B/4B/8B/30B/32B/235B, 8B=6.1GB, min Ollama 0.12.7, OCR 32 langs — https://ollama.com/library/qwen3-vl (fetched 2026-06-27).
2. HF `Qwen/Qwen3-VL-8B-Instruct` — license `apache-2.0`, OCR 32 langs (up from 19), Indonesian not explicitly listed — https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct (fetched 2026-06-27).
3. Qwen3-VL Technical Report — https://arxiv.org/abs/2511.21631
4. GLM-OCR GitHub — MIT weights / Apache-2.0 code, 0.9B, OmniDocBench v1.5 = 94.62 (#1), JSON/Markdown — https://github.com/zai-org/GLM-OCR (fetched 2026-06-27).
5. Ollama `glm-ocr` — tags `latest` 2.2GB / `q8_0` 1.6GB / `bf16` 2.2GB — https://ollama.com/library/glm-ocr (fetched 2026-06-27).
6. dots.ocr GitHub — MIT, 1.7B, JSON layout w/ bbox + categories, 100+ langs (Indonesian not listed) — https://github.com/rednote-hilab/dots.ocr (fetched 2026-06-27).
7. mlx-vlm dots_ocr support — https://github.com/Blaizzy/mlx-vlm/blob/main/mlx_vlm/models/dots_ocr/README.md
8. HF `deepseek-ai/DeepSeek-OCR` — MIT, ~3B MoE / ~570M active, markdown output — https://huggingface.co/deepseek-ai/DeepSeek-OCR (fetched 2026-06-27).
9. Ollama `deepseek-ocr` — `3b` tag 6.7GB, min Ollama 0.13.0 — https://ollama.com/library/deepseek-ocr (fetched 2026-06-27).
10. HF `PaddlePaddle/PaddleOCR-VL` — `apache-2.0`, 0.9B, 109 langs (Indonesian not explicitly listed), JSON/Markdown, OmniDocBench v1.5 SOTA — https://huggingface.co/PaddlePaddle/PaddleOCR-VL (fetched 2026-06-27).
11. HF `openbmb/MiniCPM-V-4_5` README — "Apache-2.0", optional registration — https://huggingface.co/openbmb/MiniCPM-V-4_5/blob/main/README.md (fetched 2026-06-27).
12. HF `stepfun-ai/GOT-OCR2_0` — `apache-2.0` — https://huggingface.co/stepfun-ai/GOT-OCR2_0
13. Spheron, "Best Open-Source OCR and Document VLMs to Self-Host 2026" — https://www.spheron.network/blog/best-open-source-ocr-vlm-self-host-gpu-cloud-2026/
14. LlamaIndex, "OmniDocBench is Saturated, What's Next for OCR Benchmarks?" — https://www.llamaindex.ai/blog/omnidocbench-is-saturated-what-s-next-for-ocr-benchmarks
15. "Indonesian ID Card Extractor Using OCR and NLP Post-Processing" arXiv 2101.05214 — https://arxiv.org/pdf/2101.05214
16. Gemini 3.1 Pro landscape sweep — full output: scratchpad/gemini-ocr-out.txt
17. DeepSeek V4 Pro latency-factor + throughput math — full output: scratchpad/deepseek-out.txt
18. Prior internal study (39k backlog sovereign pipeline) — research/operations/2026-06-27-39k-drive-ocr-backlog-sovereign-pipeline.md
