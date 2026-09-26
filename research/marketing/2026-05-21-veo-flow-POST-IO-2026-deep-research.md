---
date: 2026-05-21
domain: marketing
client_case: Bali Zero WR3 — Veo+Flow ecosystem POST Google I/O 2026 (19 May)
sources: 25
panels: [WebSearch ×3, WebFetch ×6 official Google+third-party, DeepSeek V4 Pro max-effort red-team 8 questions]
status: COMPLETE — supersedes 2026-05-21-veo-flow-DEEP-RESEARCH-final.md (which was pre-I/O)
correction_note: Yesterday's research (e6f3303c4) missed Google I/O 19 May 2026 announcements — this update corrects.
---

# Veo + Flow Ecosystem — POST Google I/O 2026 DEEP RESEARCH

> **TL;DR**: Google I/O 2026 (19 May) ha annunciato **Gemini Omni** — nuovo world model che **sostituisce Veo** nell'app Gemini + è ora il default in Flow UI come **Omni Flash**. Flow guadagna **AI Agent FREE** + **Flow Tools custom workflows** + mobile apps + integrazione Lyria 3 Pro. **Impact Bali Zero CRITICO**: FlowKit Chrome ext (su cui WR3 si basa) probabilmente si romperà quando Veo viene sostituito da Omni nel Flow UI. Decisione operativa: **PROCEED con WR3 attuale + parallel-test Omni Flash + migra a Flow Tools native per evitare break**.

---

## 1. Google I/O 2026 — annunci 19 maggio empirici

### Gemini Omni (nuovo world model)

| Spec | Valore | Fonte |
|---|---|---|
| Description | "World model — combina Gemini + Veo + Nano Banana + Genie" | [DeepMind Demis Hassabis quote](https://decrypt.co/368393/google-unveils-gemini-omni-next-gen-ai-video-builder-simulate-world) |
| Variant available NOW | **Omni Flash** (live in Flow + Flow Music + Gemini app) | [blog.google Flow updates](https://blog.google/innovation-and-ai/models-and-research/google-labs/flow-updates/) |
| Max clip duration | **10 secondi** (dalla Gemini app) | [gemini.google/overview/video-generation](https://gemini.google/overview/video-generation/) |
| Input format | **Image-to-video, max 5 photos** input | [gemini.google official](https://gemini.google/overview/video-generation/) |
| Native audio | ✅ Yes (specs linguistiche non pubblicate) | Official |
| Conversational editing | swap characters, lighting, stabilize, change backgrounds via chat | [Decrypt I/O coverage](https://decrypt.co/368393/google-unveils-gemini-omni-next-gen-ai-video-builder-simulate-world) |
| Persistence | character + background + movement consistent across edits | Official + I/O demo |
| Replaces Veo? | **YES in Gemini app**. In Flow è "Omni Flash upgrades" — Veo non esplicitamente deprecated | [9to5google](https://9to5google.com/2026/05/19/google-flow-video-music-ai-apps/) |
| Tier required | **AI Plus / AI Pro / AI Ultra** (Free escluso) | [gemini.google](https://gemini.google/overview/video-generation/) |
| Age restriction | 18+ | Official |
| Demo I/O | claymation protein folding (educational) + selfie video with element/environment edits | [Gizmodo live updates](https://gizmodo.com/live-updates-from-google-io-2026-2000757469) |
| AGI framing | "Step towards AGI" — Demis Hassabis | [Decrypt](https://decrypt.co/368393/google-unveils-gemini-omni-next-gen-ai-video-builder-simulate-world) |

### Flow updates 19 maggio 2026

| Feature | Cosa fa | Pricing | Status |
|---|---|---|---|
| **Gemini Omni Flash in Flow** | sostituisce Veo come default generation engine | Google AI subscribers | **LIVE TODAY** |
| **Flow Agent** | brainstorm/edit/plan/batch + dialogue variations + asset organization | **FREE per TUTTI Flow users globally** | LIVE |
| **Flow Tools** | custom workflows via natural language (resize/edit/VFX) | All deploy, only AI subscribers create+remix | LIVE |
| **Flow mobile Android** | beta video editor | Free tier? | beta |
| **Flow mobile iOS** | video editor coming soon | unclear | coming |
| **Flow Music mobile iOS** | live | AI subscribers | LIVE |
| **Flow Music mobile Android** | coming soon | AI subscribers | coming |
| **Lyria 3 Pro section editing** | rewrite/translate lyrics, restyle beat drop | AI subscribers | LIVE |
| **AI Music videos** | generate music video via Omni | AI subscribers | LIVE |
| **Covers feature** | transform full song styles | AI subscribers | LIVE |

Source: [blog.google Flow updates 19 May](https://blog.google/innovation-and-ai/models-and-research/google-labs/flow-updates/), [9to5google](https://9to5google.com/2026/05/19/google-flow-video-music-ai-apps/), [Business Standard](https://www.business-standard.com/technology/tech-news/google-i-o-2026-new-workspace-apps-flow-update-omni-flash-126052000609_1.html), [Fonearena](https://www.fonearena.com/blog/483182/google-i-o-2026-google-flow-music-gemini-omni-ai-agents-mobile-apps.html), [SiliconANGLE](https://siliconangle.com/2026/05/19/google-flow-adds-agentic-brainstorming-precise-editing-tools-sharing-features/).

### Lyria 3 Pro (music)

| Spec | Valore | Fonte |
|---|---|---|
| Model | Lyria 3 + Lyria 3 Pro production text-to-music API | [blog.google Lyria 3 Pro](https://blog.google/innovation-and-ai/technology/ai/lyria-3-pro/) |
| Track length | longer tracks (specifico non pubblicato) | Official |
| Section editing | edit specific sections without changing entire track | Official |
| Lyrics | translation + rewrite | Official |
| Music video gen | via Gemini Omni | Official |
| Built on | ProducerAI (Google acquisition Feb 2026) | [TestingCatalog X post](https://x.com/testingcatalog/status/2045265110898237743) |

### Pricing tier change (NEW: AI Plus)

- **Free** — Flow Tools deploy (no create), Flow Agent (free)
- **AI Plus** — NEW tier, pricing not yet disclosed (industry speculation $9.99/mo basato su Google One AI Premium precedente)
- **AI Pro** — $19.99/mo (~1000 cr/mo, Omni Flash access)
- **AI Ultra** — $249.99/mo (~12,500 cr/mo, full quality, no watermark)

Source convergent: [costgoat.com](https://costgoat.com/pricing/google-veo), [costbench.com](https://costbench.com/software/ai-video-generators/google-veo/), [gemini.google overview](https://gemini.google/overview/video-generation/), [mindstudio.ai](https://www.mindstudio.ai/blog/google-flow-pricing-credits-tiers-explained).

---

## 2. Cosa cambia per Bali Zero WR3 (vs research ieri)

| Asset WR3 | Stato ieri (Veo 3.1 Fast assumption) | Stato POST I/O 2026 |
|---|---|---|
| **FlowKit Chrome ext** | Strumento principale, undocumented | **A RISCHIO BREAKAGE** — Omni sostituisce Veo nel Flow UI |
| **Veo 3.1 Fast Tier 1** | Default WR3 pipeline | Probabile DEPRECAZIONE entro mesi nel Flow UI (Vertex API resta?) |
| **wr3_prompt_normalizer.py** (25w cap) | Necessario per Veo 3.1 Fast safety filter | **OBSOLETO** se Omni ha prompt acceptance window diverso (da testare) |
| **Chatterbox Emma TTS Bahasa Indonesia** | VO esterno via ffmpeg mux | **MANTENERE** — Omni native audio non garantisce Bahasa quality |
| **6×8s ffmpeg concat** | Strategia 60s episode | **MANTENERE** — Omni Flash hard limit 10s, comunque concat necessario |
| **ArcFace gate post-render** | Verifica character consistency | **PARALLEL TEST con Omni** — character persistence claim verificare empirically |
| **Ingredients to Video (Veo 3.1)** | Mai usato (no character lock) | **POTENZIALMENTE SUPERATO** — Omni "5 input photos" + conversational character swap |
| **wr3-design-architect orchestrator** | Claude-based pipeline | **CONFLITTO con Flow Agent (free)** — valutare migrazione |
| **wr3-shot-director** | Python prompt generation | **POSSIBILE REWRITE come Flow Tool** (natural language workflow) |

---

## 3. Adversarial red-team Bali Zero specifico — DeepSeek V4 Pro max effort

| # | Verdict | Confidence | False Friend |
|---|---|---|---|
| **Q1** Omni character consistency supersede ArcFace gate per Zantara? | Demo Omni copre selfie/claymation, **NOT** 6-shot multi-narrative con character stylizzato. Side-by-side test mandatorio. | **Low** | ✅ "Persistence solved" è classic false friend |
| **Q2** 10s max Omni Flash hard or UI limit? | **Hard limit**, ma WR3 60s = 6×10s concat (vs 6×8s attuale, meno seams) — **non danno** | **Medium** | ❌ Limit may lift later via API |
| **Q3** Flow Agent FREE può replace wr3-design-architect? | **Likely YES** per brainstorm/breakdown/batch. Conflitto diretto con Claude agent contracts paid. | **High** | — |
| **Q4** Flow Tools custom rebuild wr3-shot-director? | Effort LOW (natural language), MA 25w cap logic da replicare o sostituire con Flow safety nativo | **Medium** | — |
| **Q5** Lyria 3 Pro AI music videos competono con WR3? | **NO, COMPLEMENTARI** — WR3 narrative dialogue-driven, Lyria per BGM + transition visuals | **High** | ✅ "AI music videos" tenta pivot fuori scope |
| **Q6** AI Plus tier sensible per Bali Zero? | **Pricing speculato ~$9.99/mo (50% Pro)**, quota unknown decisive | **Medium** | ✅ Lower price = false economy se quota throttled |
| **Q7** FlowKit Chrome ext risk breakage? | **ALMOST CERTAIN** quando Omni sostituisce Veo UI. Migrare urgentemente. | **High** | ✅ "FlowKit stable" è false friend mortale |
| **Q8** PAUSE WR3 vs PROCEED? | **PROCEED** con Veo 3.1 Fast + parallel-test Omni Flash (20% wallet). Halt = delay senza certezza Omni Standard ready | **High** | ✅ "Omni replaces Veo immediately" è false friend |

### 6 FALSE FRIENDS identificati (Bali Zero specifici)

1. **"Character/background/movement persistence solved"** → dimostrato solo su short clips, non su 6-shot Zantara narrative
2. **"10s max è UI restriction"** → in realtà hard generation limit (no impact ma no false hope per longer)
3. **"Flow Agent FREE = full director-agent"** → brainstorm/edit ≠ profondità wr3-design-architect script→shot breakdown
4. **"AI music videos via Omni"** → tenta pivot Bali Zero fuori dal core 60s narrative regulatory
5. **"AI Plus tier downgrade saves money"** → quota throttling potenziale = false economy
6. **"FlowKit Chrome ext stable"** → undocumented + scrape-based, breakage imminente con Omni rollout

---

## 4. Updated path comparison (POST I/O 2026)

| Path | Cost/mo | Effort | Risk | Quality | Quando |
|---|---|---|---|---|---|
| **A. Stay Pro Fast + FlowKit (status quo)** | $19.99 | $0 | **HIGH** breakage Omni rollout | 720p watermark | NON raccomandato post-I/O |
| **B. Stay Pro + Omni Flash parallel test** | $19.99 | 10-20 hrs | Medium | Omni capabilities | **CONSIGLIATO IMMEDIATE** |
| **C. Pro Fast + Vertex Veo 3.1 Standard à la carte** | $70-120 | 30-50 hrs | Medium | 1080p native audio character lock | quando volume >5 ep/mese |
| **D. Upgrade Ultra + full Flow Tools migration** | $249.99 | 40-60 hrs | Medium-High | Omni Flash + Standard + Lyria | quando Omni stabilization confermata |
| **E. Wait for AI Plus tier (TBD pricing)** | ~$9.99 (speculative) | 5 hrs | Low | quota unknown | quando Google annuncia officially |

---

## 5. Action items concreti aggiornati (post-I/O)

| # | Action | Priority | Owner | Effort | Cost |
|---|---|---|---|---|---|
| 1 | **Empirical test Omni Flash via Flow UI** — 6 shots Zantara character consistency (verifica claim "persistence across edits") | **P0** | Antonello | 1h + ~$0 (Pro plan) | $0 |
| 2 | Compara Omni Flash 6×10s concat vs Veo 3.1 Fast 6×8s concat su same script — face consistency + audio quality | P0 | Engineer | 4h | ~$5-10 credits |
| 3 | **Test Flow Agent FREE** su 1 episode brief — verifica se sostituisce wr3-design-architect orchestrator | **P0** | Engineer | 2h | $0 |
| 4 | **Migrare wr3-shot-director come Flow Tool** prototype — avvia migrazione da FlowKit Chrome ext | P1 | Engineer | 8h | $0 |
| 5 | Test Omni Flash conversational editing su 1 shot — verifica se "swap characters" mantiene Zantara identity | P1 | Engineer | 2h | $5 credits |
| 6 | Monitor Google blog + Flow UI per AI Plus pricing announcement | P2 | Antonello | watch | $0 |
| 7 | Verifica Vertex AI Veo 3.1 Standard API per fallback se Flow UI rompe FlowKit | P1 | Engineer | 4h | $10-20 credits |
| 8 | Test Lyria 3 Pro BGM per WR3 episodes — verifica match con narrative tone (regulatory professional) | P2 | Engineer | 3h | $0 (AI subscriber) |
| 9 | **DEPRECATE FlowKit Chrome ext usage** progressivamente — set kill-switch date Aug 2026 (3 mesi safety window) | P1 | Antonello | decision | $0 |
| 10 | Update CLAUDE.md §10 + WR3 contracts per riflettere Omni Flash + Flow Tools come primary path | P2 | me | 1h | $0 |

---

## 6. Critical decision matrix

### Should Bali Zero PAUSE WR3 production ora?
**NO**. Reasons:
1. WR3 6/6 PoC clips già renderizzate (2026-05-20)
2. Omni Flash limit 10s = stesso pattern concat necessario (no breakthrough)
3. Omni "persistence" claims NOT validated for 6-shot Zantara narrative
4. Bahasa Indonesia native audio quality untested
5. FlowKit breakage timeline = mesi (NON giorni)

### Should Bali Zero START parallel-testing Omni Flash ora?
**SI** — P0 priority. Reasons:
1. Free with current Pro plan (no extra cost)
2. Validates "false friends" empirically prima di rebuild
3. Risk de-risking: se Omni superiore → migrate proactive; se inferiore → confirm Veo path
4. FlowKit Chrome ext rischio breakage = need fallback NOW

### Should Bali Zero MIGRATE FlowKit → Flow Tools?
**SI ENTRO 3 MESI** — P1 priority. Reasons:
1. FlowKit unofficial + scrape-based → certain breakage when Omni rollout completes
2. Flow Tools natural language workflows = lower maintenance burden
3. AI subscriber tier (Pro $19.99 already paid) include Flow Tools creation
4. Mantiene investment in shot-director / pre-render-gatekeeper logic semantica

---

## 7. Caveat metodologico

- **Multi-source convergent** (25 sources): Google official (blog.google ×4, gemini.google, deepmind.google, cloud.google.com), third-party (9to5google, Gizmodo, Decrypt, MacRumors, SiliconANGLE, MindStudio, CostGoat, CostBench, Imagine.art, Pxz.ai, Pixflow, Humai, Genra, AIVideoBootcamp, Aumiqx), social (TestingCatalog).
- **Adversarial red-team**: DeepSeek V4 Pro max reasoning, 8 questions, 6 FALSE FRIENDS identificati.
- **Codex GPT-5.5 cross-check**: SKIPPED — OAuth token_invalidated.
- **Gemini 3.1 Pro cross-check**: SKIPPED — quota exhausted 15h reset.
- **Empirical NOT yet validated** (require Bali Zero hands-on):
  - Omni Flash Bahasa Indonesia audio quality
  - Omni "persistence across edits" su 6-shot Zantara narrative
  - Flow Agent depth vs wr3-design-architect
  - FlowKit breakage actual timeline
  - AI Plus tier real pricing + quota
  - Vertex AI Veo 3.1 Standard prompt safety filter strictness

## 8. Confronto con research di ieri (e6f3303c4)

| Topic | Research IERI (2026-05-21 pre-I/O) | Research OGGI (post-I/O) |
|---|---|---|
| Default Flow engine | Veo 3.1 Fast | **Omni Flash** (sostituisce Veo) |
| Character consistency | Ingredients to Video (3 imgs) | Omni native persistence (5 imgs + conversational) — NEEDS VALIDATION |
| AI agent in Flow | NON menzionato | **Flow Agent FREE** for all |
| Custom workflows | Build custom Python wrappers | **Flow Tools** native (natural language) |
| Pricing tiers | Free / Pro $19.99 / Ultra $249.99 | + **AI Plus** (new, pricing TBD) |
| Mobile | NON menzionato | Flow Android beta + Flow Music iOS LIVE |
| Music | NON menzionato | **Lyria 3 Pro section editing + AI music videos** |
| Recommended path | Hybrid Pro + Vertex à la carte | **Pro + parallel Omni Flash + FlowKit migration plan** |

---

## 9. Sources index (25 + previous 18 still valid)

### Google official (post-I/O)
1. [Flow updates 19 May 2026 — blog.google](https://blog.google/innovation-and-ai/models-and-research/google-labs/flow-updates/)
2. [Sundar Pichai I/O keynote — blog.google](https://blog.google/innovation-and-ai/sundar-pichai-io-2026/)
3. [100 things at Google I/O 2026 — blog.google](https://blog.google/innovation-and-ai/technology/ai/google-io-2026-all-our-announcements/)
4. [Lyria 3 Pro — blog.google](https://blog.google/innovation-and-ai/technology/ai/lyria-3-pro/)
5. [Gemini Omni overview — gemini.google](https://gemini.google/overview/video-generation/)
6. [Generate music with Lyria 3 — ai.google.dev](https://ai.google.dev/gemini-api/docs/music-generation)
7. [Custom music in Google Vids — workspaceupdates.googleblog.com](https://workspaceupdates.googleblog.com/2026/03/generate-custom-music-in-google-vids-powered-by-Lyria-3-and-Lyria-3-Pro.html)
8. [Developer keynote recap — developers.googleblog.com](https://developers.googleblog.com/all-the-news-from-the-google-io-2026-developer-keynote/)

### Third-party I/O coverage
9. [Google Flow Omni Flash update — 9to5google](https://9to5google.com/2026/05/19/google-flow-video-music-ai-apps/)
10. [I/O 2026 Roundup — MacRumors](https://www.macrumors.com/2026/05/19/google-io-2026-roundup/)
11. [Live updates I/O 2026 — Gizmodo](https://gizmodo.com/live-updates-from-google-io-2026-2000757469)
12. [Google Unveils Gemini Omni — Decrypt](https://decrypt.co/368393/google-unveils-gemini-omni-next-gen-ai-video-builder-simulate-world)
13. [Workspace + Flow update — Business Standard](https://www.business-standard.com/technology/tech-news/google-i-o-2026-new-workspace-apps-flow-update-omni-flash-126052000609_1.html)
14. [Flow Music + Omni + AI agents — Fonearena](https://www.fonearena.com/blog/483182/google-i-o-2026-google-flow-music-gemini-omni-ai-agents-mobile-apps.html)
15. [Flow agentic brainstorming + tools — SiliconANGLE](https://siliconangle.com/2026/05/19/google-flow-adds-agentic-brainstorming-precise-editing-tools-sharing-features/)
16. [Flow upgrade major AI agents music videos — AndroidHeadlines](https://www.androidheadlines.com/2026/05/google-flow-gets-a-major-upgrade-ai-agents-music-videos-and-mobile-apps-are-here.html)
17. [Flow Tools custom workflows guide — pasqualepillitteri.it](https://pasqualepillitteri.it/en/news/2944/google-flow-tools-custom-ai-workflows)
18. [Trending Topics I/O 2026 coverage](https://www.trendingtopics.eu/google-i-o-2026-ai-takes-center-stage-with-new-gemini-and-video-generator/)
19. [INCRYPTED hands-on testing](https://incrypted.com/en/google-io-2026-testing/)
20. [Gemini Omni leak iWeaver](https://www.iweaver.ai/blog/gemini-omni-video-model/)
21. [Omni leak WaveSpeed Blog](https://wavespeed.ai/blog/posts/google-omni-video-model-leak-i-o-2026/)
22. [Blockchain Council Google Omni overview](https://www.blockchain-council.org/ai/google-omni-gemini-omni-video-model/)
23. [Gemini Omni Engadget](https://www.engadget.com/ai/gemini-can-now-generate-a-30-second-approximation-of-what-real-music-sounds-like-204445903.html)
24. [9to5google Gemini Omni leak May 11](https://9to5google.com/2026/05/11/gemini-omni-video-model-shows-up-with-some-early-demos/)
25. [TestingCatalog X — Flow Music ProducerAI](https://x.com/testingcatalog/status/2045265110898237743)

### Previous research (still valid for Veo 3.1 specs)
26. [Veo 3.1 Ultimate Prompting Guide — cloud.google.com](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)
27. [Veo 3.1 Lite + Vertex upscaling — cloud.google.com](https://cloud.google.com/blog/products/ai-machine-learning/veo-3-1-lite-and-a-new-veo-upscaling-capability-on-vertex-ai)
28. [Vertex AI Veo pricing — cloud.google.com](https://cloud.google.com/vertex-ai/generative-ai/pricing#veo)
29. [Veo 3.1 vs Fast vs Lite — MindStudio](https://www.mindstudio.ai/blog/veo-3-1-vs-veo-3-1-fast-vs-veo-3-1-light-comparison)
30. [Google Veo pricing — CostGoat](https://costgoat.com/pricing/google-veo)

### Bali Zero internal (cross-reference)
- `research/marketing/2026-05-21-veo-flow-DEEP-RESEARCH-final.md` (pre-I/O baseline — superseded)
- `research/marketing/2026-05-21-veo-flow-deepseek-redteam.md` (pre-I/O 7Q red-team)
- `research/marketing/2026-05-21-io-2026-deepseek-redteam.md` (post-I/O 8Q red-team — this doc)
- `research/operations/2026-05-20-wr3-veo-panel-synthesis.md` (Tier 1 rejection root cause)
- `research/operations/2026-05-20-wr3-live-e2e-complete.md` (Veo 3.1 Fast live E2E)
- `~/Desktop/wr3-episodes-archive/pp28-2025-pma-transition-2026-05-20/` (PoC episode 202MB)
