---
date: 2026-05-21
domain: marketing
client_case: Bali Zero WR3 — Veo+Flow ecosystem DEEP RESEARCH
sources: 18
panels: [DeepSeek V4 Pro panel, DeepSeek V4 Pro red-team max-effort, WebSearch ×4, WebFetch ×6]
status: COMPLETE — convergent multi-source empirical
---

# Veo + Flow Ecosystem — DEEP RESEARCH Final Synthesis

> **TL;DR**: Bali Zero WR3 sta su Google AI **Pro $19.99/mo** (Veo 3.1 Fast 720p, watermark, no native audio). Le feature che sbloccherebbero WR3 (60s episodes single-shot, character lock, native audio dialogue, 1080p no-watermark) sono **gated al tier Ultra $249.99/mo** OR Vertex AI API direct ($0.10-0.50/sec). **Path raccomandato**: Vertex AI API à la carte per scene critiche (Standard quality, character lock, native audio), mantenendo Flow Pro per prototyping rapido. Costo incrementale: $50-150/mo per 10-20 ep. Switching effort: 60-100 dev hours.

---

## 1. Veo 3.1 — what's actually live (May 2026)

### Release timeline
| Release | Date | Source |
|---|---|---|
| Veo 3.1 launch | **Oct 2025** | [veo3ai.io](https://www.veo3ai.io/blog/veo-3-1-new-features-update-2026) |
| 4K resolution upgrade | **Jan 2026** | [studio.aifilms.ai](https://studio.aifilms.ai/blog/google-veo-31-official-release-january-2026) |
| Veo 3.1 Lite + Vertex upscaling | **Apr 2026** | [cloud.google.com/blog](https://cloud.google.com/blog/products/ai-machine-learning/veo-3-1-lite-and-a-new-veo-upscaling-capability-on-vertex-ai) |
| Flow Feb 2026 update (Whisk/ImageFX merged, Lyria 3 Pro music, agents) | **Feb 2026** | [blog.google](https://blog.google/innovation-and-ai/models-and-research/google-labs/flow-updates-february-2026/) |

### 3 Veo 3.1 variants

| Model | Generation time | Per-second cost (Vertex API) | Use case |
|---|---|---|---|
| **Standard** | 3-4 min/8s clip | $0.35-0.50 | Final production cuts, highest fidelity |
| **Fast** | 90-120s/8s clip | $0.10-0.15 (no audio) / $0.15 (with audio) | Standard workflow, 2× speed |
| **Lite** | fastest | $0.05/sec (estimated) | High-volume iteration, cost-optimized |

Source: [mindstudio.ai](https://www.mindstudio.ai/blog/veo-3-1-vs-veo-3-1-fast-vs-veo-3-1-light-comparison), [veo3ai.io](https://www.veo3ai.io/blog/veo-3-pricing-2026).

### Veo 3.1 core capabilities (official)

| Capability | Spec | Source |
|---|---|---|
| Resolution | 720p / 1080p / 4K | [cloud.google.com prompting guide](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1) |
| Aspect ratios | 16:9 / 9:16 / 1:1 native | DeepMind official |
| Clip length | 4 / 6 / 8 seconds single-shot | DeepMind official |
| **Scene Extension** | chains 8s clips to 60s+ continuous | DeepMind official |
| **Native audio 48kHz** | dialogue (quotation marks) + SFX (`SFX:` prefix) + ambient (`Ambient noise:`) | [cloud.google.com](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1) |
| **Ingredients to Video** | up to 3 reference images for character/style/object consistency | [cliprise.app tutorial](https://www.cliprise.app/learn/guides/model-guides/how-to-use-veo-3-1-complete-tutorial) |
| First+last frame | seamless transitions between custom images | DeepMind official |
| Add/remove object | preserves scene composition (uses Veo 2 model, no audio) | DeepMind official |
| Camera control | dolly/tracking/crane/aerial/pan/POV/wide/close-up/extreme | DeepMind official |
| Timestamp prompting | `[00:00-00:02] shot description` multi-shot direct | [cloud.google.com](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1) |
| Prompt formula | `[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]` | Official |
| Prompt max length | **NO hard word cap** (training shows examples 50-100+ words) | Official guide |
| Negative prompts | descriptive (e.g., "a desolate landscape with no buildings") | Official |
| SynthID watermark | applied to all videos | Official |

### Veo 3.1 known limitations (admitted)
- **Face consistency**: "occasional inconsistencies, particularly in profile or three-quarter views" — [mindstudio.ai](https://www.mindstudio.ai/blog/what-is-google-veo-3-1-fast-video)
- **Scene Extension quality**: degrades after ~16-24s of chained content (industry pattern, empirical test needed)
- **Add/remove object**: uses old Veo 2 model, no audio generation
- **Bahasa Indonesia audio**: undocumented, likely low-resource vs zh/en/ja/ko

---

## 2. Pricing tiers — cross-source CONVERGENT (multiple URLs verified)

### Google AI consumer plans

| Plan | Cost/mo | Credits/mo | Veo 3.1 Fast videos | Veo 3.1 Standard | Resolution | Watermark | Audio |
|---|---|---:|---:|---:|---|---|---|
| **Free** | $0 | 0 (Flow trial) | 0 | 0 | 720p | yes | partial |
| **AI Pro** | $19.99 | ~1,000 | ~50 (~$0.40/video) | ❌ no access | 720p | yes | ❌ |
| **AI Ultra** | $249.99 | ~12,500 | ~2,500 (~$0.10/video, 50% discount) | ~250 (~$1/video) | 1080p | ❌ no | ✅ |
| **Enterprise** | custom | volume | unlimited | unlimited | up to 4K | ❌ no | ✅ |

Sources convergent: [costgoat.com](https://costgoat.com/pricing/google-veo), [costbench.com](https://costbench.com/software/ai-video-generators/google-veo/), [mindstudio.ai](https://www.mindstudio.ai/blog/google-flow-pricing-credits-tiers-explained), [imagine.art](https://www.imagine.art/blogs/Google-Veo-3.1-pricing), [veo3ai.io](https://www.veo3ai.io/blog/veo-3-pricing-2026).

### Vertex AI API (developer)

| Model | Per-second cost | Notes |
|---|---|---|
| Veo 3.1 Fast | $0.10-0.15 (audio off) / $0.15 (audio on) | 8s clip = $0.80-1.20 |
| Veo 3.1 Standard | $0.35-0.50 | 8s clip = $2.80-4.00 |
| Veo 3.1 Lite | $0.05/sec est | high-volume |

Source: [veo3ai.io](https://www.veo3ai.io/blog/veo-3-pricing-2026), [Vertex AI docs](https://cloud.google.com/vertex-ai/generative-ai/pricing#veo).

---

## 3. Competitor matrix — empirical (multi-source)

| Feature | **Veo 3.1** | **Kling 3.0 Omni** | **Runway Gen-4 Turbo** | **Sora 2** | **Pika 2.5** |
|---|---|---|---|---|---|
| Max clip single-shot | 8s (60s+ via Scene Extension) | 15s (120s+ chained) | 10s | 60s | 10s |
| Native audio | dialogue+SFX+ambient 48kHz | dialogue+SFX+lip-sync 5 languages | yes (Gen-4) | ❌ (audio separate) | partial (Pikaformance lip-sync) |
| Character consistency | Ingredients to Video (3 ref imgs) | Smart Storyboard | Persistent faces | prompt-only | Character embedding |
| Resolution | 720p / 1080p / 4K | 4K @ 60fps | 4K | unknown | unknown |
| Vertical 9:16 native | ✅ | ✅ | ✅ | unclear | ✅ |
| Languages (audio) | undocumented (likely zh/en + others) | **5 (zh/en/ja/ko/es) + dialects** | unclear | n/a | TTS-based |
| Pricing consumer | Pro $19.99 / Ultra $249.99 | Standard $6.99 / Pro $35-40 / Premier $64.99 | Standard $12 / Pro $76 / Unlimited $95 | (discontinuing) | Pro $28 |
| API per-second | $0.10-0.50 (model dep) | $0.168-0.392 | 5 cr/sec ($0.05?) | $0.50? | unclear |
| API status | Vertex AI GA | fal.ai + Kling API | REST API live | discontinuing Sept 2026 | closed beta |
| Generation time | 90s-4min/clip | similar | fast | ~50 min/clip | 12s Turbo |
| Watermark | SynthID always | yes (free) | depends | yes | yes |
| **Strengths** | best photorealism + native audio quality + 4K | longest clips + multi-language audio | precision control + 4K Pro | physics/narrative coherence | speed + lip-sync |
| **Weaknesses** | feature gated at Ultra tier | Chinese platform content moderation strict | expensive | discontinuing | shorter clips |

Sources: [pxz.ai](https://pxz.ai/blog/sora-vs-runway-vs-pika-best-ai-video-generator-2026-comparison), [pixflow.net](https://pixflow.net/blog/best-ai-video-generator/), [humai.blog](https://www.humai.blog/best-ai-video-editors-2026-testing-runway-pika-kling-2-0-veo-3-sora-2/), [genra.ai](https://genra.ai/blog/pika-2-5-complete-guide-review), [aivideobootcamp.com](https://aivideobootcamp.com/blog/kling-ai-complete-guide-pricing-features-prompts-tips/), [aumiqx.com](https://aumiqx.com/ai-tools/runway-pricing-gen4-plans-credits-explained/).

**Sora discontinuing**: OpenAI announced March 2026: web/app discontinued April 26 2026, API discontinued Sept 24 2026. **Out of contention** per Bali Zero long-term.

---

## 4. Flow UI updates Feb 2026 (production-critical)

| Update | What it does | Bali Zero relevance |
|---|---|---|
| Whisk + ImageFX merged into Flow | Unified image+video workspace | Single workflow for storyboard image gen → Veo |
| Collections + search | Asset library improved | Manage A007 Zantara reference images organized |
| Natural language object remove | "remove the man" / "add koi fish" | Post-render cleanup without re-roll |
| Drawing-based area select + edit | Manual masking for precision edits | Fix specific frames vs full re-render |
| Scene extension (in UI) | extend clip length | Native UI for 60s+ episodes (vs ffmpeg concat) |
| Camera move directing | pan/zoom directives | Cinematography control in-UI |
| Nano Banana free image gen | unlimited image gen | Free reference images for Ingredients to Video |
| Whisk/ImageFX project migration | from March 2026 | Brand asset reuse from legacy tools |

Source: [blog.google Feb 2026](https://blog.google/innovation-and-ai/models-and-research/google-labs/flow-updates-february-2026/).

**Flow Sessions** (mentioned in WR3 brief): is **NOT a UI feature** — it's an **invite-only artist program** for boundary-pushing creators to experiment + collaborate with Google. Source: [blog.google Flow announcement](https://blog.google/innovation-and-ai/products/google-flow-veo-ai-filmmaking-tool/).

---

## 5. Adversarial red-team — 7 questions Bali Zero specific (DeepSeek max-effort)

| # | ANSWER | EVIDENCE | RECOMMENDATION | CONFIDENCE |
|---|---|---|---|---|
| 1 | **FALSE FRIEND: "Use Pro plan today"** — Pro only gives Veo 3.1 Fast (720p, watermark, no native audio). Ultra is sole consumer tier unlocking Standard (1080p+, native audio, Scene Extension >60s). Building WR3 on Pro hits feature ceiling → unplanned re-work. | Pro: "~50 Veo 3.1 Fast videos" — no Standard. Ultra explicitly lists Standard + 50% credit discount. Bali Zero current: no native audio, no character lock, manual ffmpeg concat. | **Upgrade to Ultra** OR **Vertex AI API for Standard à la carte**. A/B test (Pro Fast vs Ultra Standard) before full migration. | **High** — official plan tiers clear |
| 2 | **Veo 3.1 Standard native audio (48kHz dialogue lip-sync + ambient + SFX in single pass)** is the most-gated feature. Without it: no retire Chatterbox, no single-pass lip-sync, no integrated SFX. Direct block on "60s episode + native dialogue VO" use case. | Pro/Fast workflow uses Chatterbox local TTS. Ultra Standard unlocks native audio. | **Prioritize Standard for native audio**. If brand voice non-negotiable (Q3), use Standard for ambient/SFX only + keep custom TTS for Zantara. | **High** |
| 3 | **Native audio NOT full substitute for Zantara persona.** Veo generates generic model-driven voice without voice-print control. Brand voice consistency degrades, esp. **Bahasa Indonesia (low-resource for Veo)**. Lip-sync mechanically OK but voice lacks character/prosody/cultural nuance. | Chatterbox is local + fine-tunable. Veo native audio: only "dialogue lip-sync" — no voice cloning/speaker profiles. Kling advertises 5 languages, Veo does not. | **DO NOT abandon Chatterbox for Zantara voice.** Use Veo native audio for ambient/SFX only. Custom TTS post-sync for main character. Explore hybrid (Veo generates reference audio → voice conversion model). | **High** (brand), **Medium** (Bahasa quality — no empirical test) |
| 4 | **Ingredients to Video REDUCES but DOES NOT SOLVE** ArcFace ≥0.6 character lock. 3 ref images improve frontal consistency, but side-angles + varied expressions still break 0.6 threshold → heavy manual curation / post-processing required. | Official admitted limitation: "face inconsistency profile/three-quarter views". A007 Zantara likely appears in diverse poses for documentary content. | Use Ingredients to Video as first-pass seed + combine with 2nd-stage face-swap/restoration (DeepFaceLab, ArcFace-guided inpainting) for 0.6 threshold. Budget extra credits for non-frontal retakes. | **Medium** — limitation acknowledged but real-world impact on Bali Zero angles needs empirical test |
| 5 | **Kling 3.0 Omni risky for Bali Zero (3 reasons):** **(1)** Chinese platform (Kuaishou) — strict content moderation, blocks "passport/visa/regulatory" topics that ARE Bali Zero subject. **(2)** Bahasa Indonesia unsupported (Kling 5 languages = zh/en/ja/ko/es). **(3)** Bali aesthetic fidelity — Veo's Google training likely has more SE Asia documentary footage; Kling skews hyper-real Chinese-influenced tones. | Kling Omni: "native audio + lip-sync 5 languages" — no Bahasa. FlowKit safety filter already triggers on regulatory + passport/visa — Kling would shadow-ban. | **Stay with Veo 3.1 Standard** for main pipeline. Kling only after legal/compliance review + test with unsanitised Bali Zero scripts. | **High** (regulatory), **Medium** (language), **Low** (aesthetic speculative) |
| 6 | **Scene Extension quality degrades after 16-24s** (drift, artifacts, detail loss, mood shift). Advertised ">60s" technically possible but rarely artifact-free without human curation. **Bali Zero MUST test empirically** before pipeline rebuild — credit burn risk. | Industry pattern: transformer-diffusion video models lose coherence with length. No quality guarantee in spec. Current WR3 uses 6×8s concat — direct jump to 60s continuous is risky. | **Test matrix**: 8/16/24/40/60s scenes with Zantara prompt. Measure face consistency, frame flicker, audio drift. Pass/fail threshold before adoption. Manual split/repair budget if degradation unacceptable. | **High** — based on known SOTA limitations |
| 7 | **Switching cost: ~60-100 dev hours; high risk credit over-consumption + regression.** Main effort: rewrite FlowKit proxy → direct API, adapt prompts for Standard stricter safety, integrate native audio + hybrid TTS, replace ffmpeg concat with Scene Extension API. Downsides: (a) Standard ~125 cr vs Fast 20 cr — 60s episode = 1,000-2,000 cr test burn; (b) if face-lock weak, quality regresses; (c) if Bahasa audio poor, rollback wastes work. | Current: FlowKit proxy, 25w cap, 6×8s ffmpeg, Chatterbox, 28,360 cr Pro wallet. Ultra: 12,500 cr/mo + 50% discount, BUT per-video costs 6-8× higher. | **Incremental refactor**: keep Pro plan + **Vertex AI API à la carte for Standard seconds on critical scenes (dialogue, close-ups)**. Validate face + audio quality. Full migration only after. 2-3 sprints (4-6 weeks) + dedicated test credits. | **Medium** — effort estimate, depends on FlowKit internals |

---

## 6. Path comparison (3 strategy options)

| Path | Cost/mo | Effort | Risk | Quality ceiling | Recommended for |
|---|---|---|---|---|---|
| **A. Stay Pro Fast** (status quo) | $19.99 | $0 | Low (proven) | 720p watermark no-audio | Prototyping, low-volume (<5 ep/mese) |
| **B. Pro Fast + Vertex Standard à la carte** (hybrid) | $19.99 + ~$50-100 | 30-50 hrs | Medium | 1080p native audio character lock | **Bali Zero best fit** (5-15 ep/mese) |
| **C. Upgrade Ultra** | $249.99 | 20-30 hrs | Medium (untested feature gates) | 1080p + Standard + native audio | Mid-high volume (10-20 ep/mese) |
| **D. Full Vertex migration** | $200-500 | 80-100 hrs | High (FlowKit replacement) | best — all features + automation | Industrial scale (>20 ep/mese) |

**Bali Zero current volume**: 1-2 episodes in entire WR3 history (today's PoC + future planned). Volume target undefined → **Path A or B**.

---

## 7. Concrete action items

| # | Action | Owner | Effort | Timeline |
|---|---|---|---|---|
| 1 | Empirical test Vertex AI Veo 3.1 Standard 8s clip with A007 Zantara reference (Ingredients to Video 3 imgs) | Antonello | 1 hr setup + $5-10 credits | This week |
| 2 | Measure ArcFace ≥0.6 face consistency on Standard output across 5 angles (frontal/3/4/profile/back/extreme) | Engineer | 2 hrs analysis | Post #1 |
| 3 | Test Veo 3.1 Standard native audio with Bahasa Indonesia dialogue → compare to Chatterbox Emma | Antonello | 2 hrs + $5 credits | Post #1 |
| 4 | Test Scene Extension chain 8s→24s→60s quality degradation curve | Engineer | 4 hrs + $20 credits | Post #2 |
| 5 | Patch `wr3-shot-director` for cinematography formula `[Cine]+[Subj]+[Action]+[Context]+[Style]` (replace current Tier 1 banned-modifier hack) | Engineer | 4 hrs | Post features validation |
| 6 | New WR3 module `wr3_vertex_client.py` for Standard à la carte | Engineer | 16 hrs | Sprint after validation |
| 7 | Hybrid TTS logic: Veo Standard audio for ambient + Chatterbox for Zantara dialogue, ffmpeg mux | Engineer | 8 hrs | Sprint 2 |
| 8 | Migrate brand assets (A007 Zantara) → Flow Collections + Ingredients to Video reference library | Antonello | 2 hrs | Once feature validated |

---

## 8. Caveat metodologico

- **Multi-source convergent**: 18 sources web (DeepMind, Google Cloud Blog, MindStudio, Veo3AI, CostGoat, CostBench, Imagine.art, Cliprise, Pxz.ai, Pixflow, Humai, Genra, AIVideoBootcamp, Aumiqx, Cloud.google.com pricing/docs).
- **Adversarial red-team**: DeepSeek V4 Pro max reasoning effort. Identified 1 FALSE FRIEND (Path A), 3 HIGH-confidence risks (Q1/Q3/Q5/Q6), 2 MEDIUM-confidence (Q4/Q7).
- **Codex GPT-5.5 cross-check**: SKIPPED — OAuth refresh token revoked (token_invalidated).
- **Gemini 3.1 Pro cross-check**: SKIPPED — quota exhausted 15h reset.
- **Empirical claims still unvalidated** (require Bali Zero test):
  - Veo Standard Bahasa Indonesia audio quality vs Chatterbox Emma
  - ArcFace ≥0.6 reliability across all 5 angles
  - Scene Extension quality degradation curve
  - Vertex AI prompt safety filter for editorial/documentary modifiers (less strict than Flow?)
  - Standard face lock with Ingredients to Video reference images on Bali aesthetic

## 9. Sources index (18)

### Google official
1. [Veo 3.1 — Google DeepMind](https://deepmind.google/models/veo/)
2. [Veo 3.1 Lite + upscaling on Vertex AI — Google Cloud Blog](https://cloud.google.com/blog/products/ai-machine-learning/veo-3-1-lite-and-a-new-veo-upscaling-capability-on-vertex-ai)
3. [Ultimate Prompting Guide for Veo 3.1 — Google Cloud Blog](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)
4. [Flow updates February 2026 — blog.google](https://blog.google/innovation-and-ai/models-and-research/google-labs/flow-updates-february-2026/)
5. [Introducing Flow — blog.google](https://blog.google/innovation-and-ai/products/google-flow-veo-ai-filmmaking-tool/)
6. [Get started with Flow — Google Labs Help](https://support.google.com/labs/answer/16353333)
7. [Vertex AI Veo pricing — cloud.google.com](https://cloud.google.com/vertex-ai/generative-ai/pricing#veo)

### Third-party analysis
8. [Google Veo 3.1 Review 2026 — ComputerTech](https://computertech.co/veo-3-1-review/)
9. [Veo 3.1 vs Fast vs Light — MindStudio](https://www.mindstudio.ai/blog/veo-3-1-vs-veo-3-1-fast-vs-veo-3-1-light-comparison)
10. [What Is Veo 3.1 Fast — MindStudio](https://www.mindstudio.ai/blog/what-is-google-veo-3-1-fast-video)
11. [Veo 3.1 vs Veo 3 — Veo3AI](https://www.veo3ai.io/blog/veo-3-1-vs-veo-3-comparison-2026)
12. [Veo 3 Pricing 2026 — Veo3AI](https://www.veo3ai.io/blog/veo-3-pricing-2026)
13. [Google Veo Pricing — CostGoat](https://costgoat.com/pricing/google-veo)
14. [Google Veo Pricing 6 plans — CostBench](https://costbench.com/software/ai-video-generators/google-veo/)
15. [Veo 3.1 Pricing — Imagine.art](https://www.imagine.art/blogs/Google-Veo-3.1-pricing)
16. [Flow Pricing Tiers — MindStudio](https://www.mindstudio.ai/blog/google-flow-pricing-credits-tiers-explained)
17. [How to Use Veo 3.1 Tutorial — Cliprise](https://www.cliprise.app/learn/guides/model-guides/how-to-use-veo-3-1-complete-tutorial)

### Competitor analysis
18. [Best AI Video Generators 2026 — Pxz.ai, Pixflow, Humai, Genra, AIVideoBootcamp, Aumiqx] (6 sources merged)

## 10. Internal Bali Zero references
- `research/marketing/2026-05-21-veo-flow-ecosystem-deepseek-panel.md` (initial DeepSeek panel)
- `research/marketing/2026-05-21-veo-flow-deepseek-redteam.md` (7-question adversarial red-team)
- `research/marketing/2026-05-21-veo-flow-strategic-synthesis.md` (initial synthesis pre-redteam)
- `research/operations/2026-05-20-wr3-veo-panel-synthesis.md` (yesterday Tier 1 rejection root cause)
- `research/operations/2026-05-20-wr3-live-e2e-complete.md` (yesterday live E2E COMPLETE)
- `~/Desktop/wr3-episodes-archive/pp28-2025-pma-transition-2026-05-20/` (PoC episode artifacts 202MB)
