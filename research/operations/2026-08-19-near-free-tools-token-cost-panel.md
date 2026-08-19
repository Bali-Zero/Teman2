---
date: 2026-08-19
domain: operations
client_case: none
discovered_by: cross-family panel (Gemini agy + Kimi K3 + Codex GPT-5.6 xhigh) + Fable 5 independent web verification
sources:
  - scratchpad panel outputs (seat_agy.md 11.6KB, seat_kimi.md 16KB, seat_codex.md 19KB — session e8b85382)
  - https://releases.drawthings.ai/p/introducing-qwen-image-support
  - https://engineering.drawthings.ai/p/optimizing-qwen-image-for-edge-devices
  - https://github.com/remotion-dev/remotion/blob/main/LICENSE.md
  - https://openrouter.ai/docs/faq (free tier: 50 req/day, prompt-logging caveats)
  - https://github.com/resemble-ai/chatterbox/blob/master/src/chatterbox/mtl_tts.py (verified 2026-08-19: 23 languages, Malay yes, Indonesian NO)
  - https://github.com/docling-project/docling (Granite-Docling-258M, Apache-2.0, fully local)
  - https://github.com/ggml-org/whisper.cpp · mlx-whisper (Apple-native transcription paths)
  - https://github.com/Wan-Video/Wan2.2 (official: ≥24GB NVIDIA VRAM for 720p) · mlx-gen port (384×224 on M5 Max 128GB — not production)
  - https://huggingface.co/mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit (~17.2GB weights)
  - https://github.com/microsoft/LLMLingua · https://www.lmsys.org/blog/2024-07-01-routellm/
adversarial_review: codex
---

# Near-free / OSS tools vs our token, quota & credit pain — cross-family panel verdict

**Mandate (Zero, 2026-08-19):** evaluate the "free AI tools" video list + deep-research report he
received; convoke the other big LLMs for alternatives; judge what is integrable in the Nuzantara
stack to cut token costs.

**Panel:** Gemini 3.x (agy) ✅ · Kimi K3 ✅ · Codex GPT-5.6 (default model, xhigh, web-research) ✅ ·
GLM 5.2 ✗ (429 usage-window, reset 18:49) · Qwen TP1 ✗ (401 invalid key — confirms the known
`qwen-cloud-code` UNARMED state; cure is `operator[credential]`). Degraded to 3 heterogeneous
families + conductor verification — declared, not silent.

## 0. The reframe every seat converged on

Our pain is **three different physics**, and most of the candidate list addresses none of them:

| Pain | Physics | What actually moves it |
|---|---|---|
| (a) Quota windows (Claude/Codex rolling caps) | context size × message count; cached reads still consume the window | structural session discipline (subagent isolation, circuit-breaker, context compiler) — i.e. the levers ALREADY in the 2026-08-12 token plan (P1/P2, Leva A, M1). No tool on the list shrinks a 290K context. |
| (b) The ONE metered seat (Gemini prepay, WA bot — 4 depletions/6 weeks) | production QPS × prompt size, per-token dollars | **semantic+exact answer cache + intent-tier routing to local qwen3.5:9b** — the single biggest lever, unanimous #1 across all three seats |
| (c) Image/video credits (Flow/Veo, Nano Banana) | generation count | **local stills on Apple Silicon (yes) + deterministic video composition (yes) + local video diffusion (NO — marketing)** |

Tools that swap the orchestrator (Aider, Continue, Plandex) are **category errors** for pain (a):
they re-spend the same flat quotas through a different UI. Aider's one great idea (tree-sitter
repomap) we already run as a 15-min cron.

## 1. Unanimous verdicts on the candidate list

**ADOPT (all seats + conductor verification agree):**

| Tool | For | Note |
|---|---|---|
| **Docling** (IBM, Apache-2.0) | intake pipeline: deterministic PDF/layout/table parsing BEFORE qwen2.5vl; VLM only on uncertain regions | fully local (PII boundary intact); Granite-Docling-258M; supports native macOS Vision OCR. Target: −50–90% VLM page passes |
| **Qwen-Image via Draw Things / mflux** (48GB Pro) | WR2 carousel hero images off Nano Banana/Flow credits | Draw Things ships official Qwen-Image support (in-image typography = our headline use case). 24GB machines experimental only |
| **whisper.cpp / mlx-whisper** (large-v3-turbo) | reel subtitles, voice-note intake, meeting transcription | NOT WhisperX proper (CUDA-first, MPS broken); use MLX/Metal paths |
| **Semantic+exact answer cache on the WA bot** (own Qdrant/Redis, bge-m3, threshold ≥0.92 + metadata isolation) | pain (b) | an afternoon inside the existing FastAPI stack; never cache PII/prices (PricingTool at response time); TTL + snapshot-versioned invalidation. NOTE: the bot corner already has an answer-cache lane — extend, don't duplicate (load `/bot` before building) |
| **Local grunt lane: Qwen3-Coder-30B-A3B 4-bit MLX** (48GB Pro only) | mechanical cron work (classify, extract, format, log triage) | ~17.2GB weights, ~25–40 tok/s; NOT Qwen3-Coder-Next (48GB file — doesn't fit). Route judgment calls to cloud as today |

**SKIP (unanimous):**

- **Dify / n8n / Khoj** — platform duplication; we ARE the platform (FastAPI+Qdrant+cron). Pure maintenance debt on a 3-Mac fleet.
- **Aider / Continue.dev / Plandex** — orchestrator swaps that don't create quota; repomap idea already taken.
- **Wan2.1/2.2 / HunyuanVideo as Veo replacement** — "beats Sora" is a VBench cherry-pick on NVIDIA hardware. Official Wan2.2 720p wants ≥24GB **NVIDIA** VRAM; the real MLX port produced 384×224×33f on an M5 Max **128GB**. On our 24–48GB unified memory it's an overnight-render novelty that freezes the machine. Hunyuan3D irrelevant (no 3D deliverable).
- **Fooocus / InvokeAI** — SDXL-era, CUDA-first or redundant; Draw Things supersedes both on Mac (Fooocus's own docs send Mac users elsewhere).
- **OpenRouter free tier in production** — 50 req/day (1000 only after $10 spend), 20 RPM, free endpoints may log/train on prompts → never for client-adjacent traffic, too flaky for cron. Also: installing any paid key needs Zero's authorization (cost rule 2026-06-04).
- **OptiLLM** — inference MULTIPLIER (best-of-N, reflection) marketed as optimization; architecturally opposed to quota reduction.
- **Nemotron** — a model family, not a tool; flagship is CUDA/FP8; small quants must first beat qwen3.5:9b on our own gold set to deserve disk.
- **OpenCut / Open Montage** — young/churny; Open Montage orchestrates via your coding-assistant subscription (not quota-free) and still calls Veo-class APIs for generation.

**CONDITIONAL:**

- **Remotion** — the deterministic-reel idea is right (80% of our regulatory reels is composed text/motion, not generative), BUT **it is NOT free for Bali Zero**: free only ≤3 employees; we need a Company License ($25/seat/mo, or $0.01/render min $100/mo). New paid sub ⇒ Legge 5. **MIT alternative: Motion Canvas** (Codex's pick) or the existing Playwright/ffmpeg renderer we already own in WR2/WR3. Recommended: extend our own renderer first; buy nothing.
- **Chatterbox TTS** — already our WR3 fallback seat. Verified this turn: the multilingual model's language map has **Malay but NOT Indonesian** → fine for EN/IT VO, never present Malay as production Bahasa Indonesia. Kokoro-82M (agy's pick) is a lighter EN alternative worth a listen test.
- **Stable Audio Open** — one weekend, once: generate a small licensed-clean loop/SFX library, then done. Community License (free under $1M revenue). Low priority.
- **LLMLingua-2** — ONLY on prose (RAG chunks on the metered bot path, OCR text post-extraction, repetitive logs). **Never on code, diffs, tool schemas, legal quotations, prices, KBLI codes** — documented failure mode, and our 290K contexts are code. agy's blanket recommendation is overruled by Kimi+Codex+the literature.
- **Hyprnote/anarlog** (the video's "Analog") — local meeting notes on macOS; fine as an operator app for Zero's calls; zero integration work; not a token lever.

## 2. Consolidated top levers (merged ranking, by expected impact)

1. **WA-bot call-avoidance funnel** (exact cache → semantic cache → local 9B intent tier → Gemini only on miss). Metric: metered Gemini calls/day, target −50% in week 1. This attacks the only lane where we pay per token and have had 4 client-facing outages.
2. **Docling-first document cascade** in intake. Metric: qwen2.5vl page calls per 100 intake pages.
3. **Local hero-image lane** (mflux headless + Draw Things interactive, Qwen-Image on the 48GB Pro; fixed seeds + brand LoRA for consistency). Metric: cloud image credits per accepted carousel hero.
4. **Deterministic reel pipeline** (own renderer / Motion Canvas; Veo reserved for 1 hero shot per reel). Metric: Veo credits per published reel, target −60–80%.
5. **Grunt lane Qwen3-Coder-30B MLX on Pro** for mechanical cron. Metric: cloud-CLI invocations/day (60–90 → 20–30). Needs a 100–300-task gold set + canary before routing anything client-adjacent.
6. **mlx-whisper for all transcription** (subtitles, voice intake). Metric: % media minutes transcribed locally = 100.
7. **MCP/tool-context audit on headless lanes** (Codex): interactive sessions already defer tools via ToolSearch, but cron/SDK lanes may eagerly load schemas — measure with mcpsnoop before assuming. Metric: tool-schema+result tokens per successful job.
8. **Approved-asset retrieval before generation** (CLIP/pHash over the WR2 asset store, provenance + license metadata) — fewer regenerations, and it mechanizes the existing no-silent-reuse rule.

Quota-window relief (pain a) stays owned by the EXISTING token plan (P1/P2 shipped, Leva A
orchestrate-gate cured, M1 circuit-breaker pending GO) — the panel found no external tool that
beats those structural cures, and two seats independently warned that prompt-compression there
would damage code contexts for ~1% gain.

## 3. Corrections to the report Zero received (adversarial pass)

| Claim in the pasted research | Reality |
|---|---|
| "Wan2.1 supera Sora, gira su RTX consumer" | VBench slice + NVIDIA-only; on Apple Silicon: proxy-resolution experiments, not production |
| "Aider sostituisce Copilot/Cursor/Devin" | it re-spends the same model quota; its repomap is the one good idea and we already run it |
| "Remotion a costo praticamente zero" | free only ≤3 employees; Bali Zero needs a paid Company License |
| "WhisperX salvavita" | CUDA-first; on Mac the path is whisper.cpp/mlx-whisper (WhisperX only for alignment/diarization on CPU) |
| "Dify/n8n game-changer" | for us: a second platform to babysit that removes zero model calls |
| "Chatterbox = ElevenLabs killer" | credible for EN (blind-test data real), but NO Indonesian in the language map (Malay ≠ Bahasa production quality) |
| "OpenRouter/OmniRouter salvavita per le API" | 50 req/day free, logging caveats, and our problem isn't per-token dollars |
| Nemotron "affidabile per agenti" | NVIDIA-first; irrelevant on this fleet |

## §Solo-operatore

- **Qwen TP1 seat**: 401 invalid key — re-credential `~/.qwen/settings.json` (`operator[credential]`).
- **Remotion Company License** purchase (if ever wanted over Motion Canvas/own renderer) — Legge 5.
- **GO on the build lanes** above (each will land as its own PR per normal flow); the WA-bot cache
  lane touches the bot corner → build under `/bot` corner rules.

## Adversarial review

Three independent cross-family seats reviewed the candidate list adversarially against the same
brief: Codex GPT-5.6 (xhigh, with live web research — the deepest pass, cited in frontmatter),
Kimi K3, and Gemini via agy. GLM 5.2 hit its 429 usage window and the Qwen TP1 seat returned 401
(known UNARMED state), so the panel ran degraded at 3 families — declared above. Material
disagreements between seats (Qwen-Image viability on Apple Silicon, LLMLingua scope, Remotion
cost) were settled by the conductor against primary sources in the same turn, not by vote.

## Method note

Seat outputs preserved in session scratchpad; every ADOPT/SKIP above was either unanimous across
≥2 independent families or re-verified by the conductor against primary sources (Draw Things
release notes, Remotion LICENSE.md, Chatterbox source, Wan2.2 README, OpenRouter docs) in the
same turn. Seat claims not re-verified are attributed inline.
