# SOTA Agentic Carousel-Generation Automations — Architectures + Reusable Code

**Captured**: 2026-06-06
**Author**: Claude Opus 4.8 (orchestrator) + 3 background research lanes (Sonnet 4.6)
**Method**: reuse-first decomposition (7 bricks) → parallel fan-out (orchestration / render / image+critic lanes) → license-gate every repo → orchestrator verification of load-bearing claims
**Cost**: $0 (Claude OAuth MAX, free WebSearch/WebFetch)
**Anchor**: compared against our own production pipeline `apps/war-room` (WR2) + prior `~/.claude/skills/bali-zero-brand/_external-bench-2026-05.md`

> **Why this exists**: Antonello asked for a deep research on how SOTA agentic IG-carousel automations are built, using `/skill reuse-first` so we bring home **both architectures and code**. We already run a mature pipeline (WR2). So this is comparative + code-acquisitive: what is genuinely beyond what we have, and which working code (license-cleared) we can vendor.

---

## 0. Executive summary

A SOTA agentic carousel automation in 2026 is a **deterministic 5-7 stage pipeline under a centralized orchestrator**, not a free-form "swarm of agents". The stages are stable across every serious implementation:

```
brief/ground-truth → narrative/copy (structured) → layout/render → hero-image-gen → critic gate (VLM) → [human review] → publish
                                                  ↖___________ retry loop (gate-routed) __________↙
                          feedback loop: metrics → reflexion/skill-library → next run
```

Three findings reframe our position:

1. **Our no-peer-to-peer orchestrator topology is the academic SOTA recommendation**, not just an ops preference. (arXiv:2512.08296, Google, Dec 2025 — _qualitative_ claim verified; the "17.2× / 4.4×" multipliers are from secondary commentary, see §1.)
2. **Our binary PASS/FAIL critic is the statistically correct design.** VLMs reliably _rank_ but cannot reliably _score_ on absolute scales for vision-heavy tasks (arXiv:2604.25235, verified). Scalar 1-5 rubrics are noise for palette/composition.
3. **Our weakest brick is cross-slide visual consistency** (anchor-reuse + sha256 only prevents _exact_ reuse, not _coherent_ lighting/palette/framing across slides). This is the highest-value upgrade — and it's solvable with tools already inside our Google AI Ultra subscription (Nano Banana Pro, 14 reference images) or with FLUX.1 Kontext multi-turn.

**Bottom line**: WR2 is architecturally on the SOTA frontier. The gains are at the margins — durable orchestration (LangGraph + Postgres checkpointer), one render-contract pattern, structured-output enforcement (`instructor`), cross-slide consistency, and three cheap critic-hardening fixes. None require a paid Anthropic key; the only paid-API temptation (Imagen 4 Ultra, Recraft) is optional and gated behind Zero's authorization + the PII boundary.

---

## 1. Brick 1 — Orchestration & content pipeline

### Architecture findings (source-calibrated)

**Four coordination paradigms crystallized by mid-2026:**

| Paradigm                          | Framework                                   | Fit for a carousel pipeline                                                                                                                                                                   |
| --------------------------------- | ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Graph-state (DAG + checkpointing) | **LangGraph** (MIT, ~34k★, v1.2.x Jun 2026) | Typed state through named nodes; conditional edges route on a status field (not the LLM); Postgres/Redis checkpointers survive crashes + enable replay + durable human-in-loop. **Best fit.** |
| Role-based crew                   | CrewAI                                      | Role+goal YAML; no typed state schema; retry/gate logic fights the framework. **Not recommended.**                                                                                            |
| Handoff / agent-as-tool           | OpenAI Agents SDK                           | Minimal; HITL not first-class; fan-out is manual async. **Not recommended.**                                                                                                                  |
| Structured workflow + LLM routing | Google ADK                                  | `SequentialAgent`/`ParallelAgent`/`LoopAgent` ≈ our pipeline conceptually; Gemini-native but portable pattern. **Study-pattern (relevant if we ever go Gemini-primary).**                     |
| Durable-execution layer           | Temporal (used by Postiz)                   | Long-running multi-step workflow durability; heavyweight. **Study-pattern.**                                                                                                                  |

**The academic anchor for our no-peer rule** — calibrated honestly:

- arXiv:2512.08296 "Towards a Science of Scaling Agent Systems" (Kim, Gu, Park et al., Google, Dec 2025) **is a real paper** (verified abstract). Its load-bearing claim: _"architectures without centralized verification tend to propagate errors more than those with centralized coordination"_; it evaluates 5 topologies (Single, Independent, Centralized, Decentralized, Hybrid) and finds coordination yields diminishing returns and mismatched coordination degrades performance (relative range +80.8% to −70.0%).
- ⚠️ **The specific "17.2× unstructured / 4.4× orchestrator" multipliers are NOT in the paper's abstract** — they come from secondary commentary ([Towards Data Science: "The 17x Error Trap"](https://towardsdatascience.com/why-your-multi-agent-system-is-failing-escaping-the-17x-error-trap-of-the-bag-of-agents/)). Cite the _paper_ for the qualitative finding; cite TDS for the numbers. (Our own brand-cortex/agent docs currently attribute "17.2×" to "Google" — worth softening to "centralized coordination contains error propagation (Google 2512.08296); a widely-cited secondary analysis puts unstructured amplification ~17×".)

**LangGraph vs script-driven for OUR pipeline** — consensus: for a pipeline with conditional retry loops + a critic gate that loops back + (optional) human approval + crash-resume need, **LangGraph is SOTA over plain script**. Plain scripts win only for truly linear, no-retry, no-resume pipelines. Decisive advantages: structural gates as conditional edges (the model can't rationalize past a failure), PostgresSaver checkpointing (crash-resume + replay), first-class parallel fan-out, first-class durable interrupts. LangGraph is **already in our stack** (`kg_langgraph_orchestrator` has PostgresSaver; Federation Orchestrator uses LangGraph) — but WR2's primary carousel fan-out is script-driven. That's the migration target.

**Reflexion / skill-library loops in production**: Reflexion (arXiv:2303.11366) = store verbal self-critiques after failure. Voyager = write reusable skills on success. SAGE (2025-26) adds the key insight: skills accumulated _only on success miss refinement through failure_. **Crucial caveat**: self-improvement works reliably **only where outcomes are objectively verifiable**. For open-ended creative quality there is no production evidence of automated self-improvement _without a human-scored or metric ground-truth signal_. → Our weekly Reflexion using IG engagement (saves/reach) as the objective signal is structurally sound. What's missing: storing _critic-rejected drafts as negative examples_ (see §8 Rec 3).

### Reuse-first code table — orchestration

| Repo                                                                                                  | What                                                                                                   | Stack                                | License                                         | Maturity          | Verdict                                                         | Take                                                                                                                                                                                                                 |
| ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------ | ----------------------------------------------- | ----------------- | --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [langchain-ai/social-media-agent](https://github.com/langchain-ai/social-media-agent)                 | URL → marketing report → Twitter/LinkedIn post → HITL approval → schedule                              | TS, LangGraph, Claude                | **MIT** ✅                                      | ~2.6k★, Jun 2026  | **[STUDIA-PATTERN-RISCRIVI]** (MIT permits copy, but TS→Python) | 11-node `StateGraph`; `Send` primitive parallel fanout; `interrupt()` durable HITL; condense-loop retry (≤3); annotation reducers (`(_s,u)=>u` full-replace); URL-dedup store. The canonical content-pipeline graph. |
| [SilvioBaratto/clipcraft](https://github.com/SilvioBaratto/clipcraft)                                 | NestJS + BAML type-safe LLM → carousel slides; Opus→Sonnet→Gemini cascade; Playwright render; Postgres | TS, NestJS, BAML, Prisma, Playwright | **MIT** ✅                                      | ~7★, Jun 2026     | **[FORKA-E-ADATTA]**                                            | BAML type-safe slide schema; the 3-LLM cascade (mirrors our tier model in TS); server-side Playwright render.                                                                                                        |
| [FranciscoMoretti/carousel-generator](https://github.com/FranciscoMoretti/carousel-generator)         | LinkedIn carousel editor; OpenAI copy; slide-type taxonomy (Intro/Content/Outro); ZOD validation       | TS, Next.js, shadcn, ZOD             | **MIT** ✅                                      | ~192★             | **[STUDIA-PATTERN-RISCRIVI]**                                   | Slide-type taxonomy as a structured-output schema for the storyboarder; ZOD-validated LLM output.                                                                                                                    |
| [gitroomhq/postiz-app](https://github.com/gitroomhq/postiz-app)                                       | Full self-host social scheduler; Temporal orchestration; 15+ platforms incl IG                         | TS, NestJS, Temporal, Prisma         | **AGPL-3.0** ⚠️                                 | ~31.5k★, May 2026 | **pattern-only** (copyleft — do NOT vendor)                     | Temporal durable-execution pattern; IG connector as reference. _Largely moot for us — we don't auto-publish (Legge 5)._                                                                                              |
| [DataTalksClub/carousel-automation](https://github.com/DataTalksClub/carousel-automation)             | Template HTML/CSS → PNG/PDF via Playwright; JSON-driven; no AI                                         | JS, Playwright                       | **none visible** ⚠️ (treat all-rights-reserved) | ~3★               | **[STUDIA-PATTERN-RISCRIVI]** (license unverified)              | Slide-type → HTML-partial + CSS-file injection; clean data/template separation.                                                                                                                                      |
| [alejandro-ao/crewai-instagram-example](https://github.com/alejandro-ao/crewai-instagram-example)     | CrewAI IG content-strategy crew (research / visual-planner / writer)                                   | Python, CrewAI                       | **none visible** ⚠️                             | ~101★             | **[STUDIA-PATTERN-RISCRIVI]** (license unverified)              | `config/agents.yaml` + `tasks.yaml` — YAML-externalized agent specs (a config pattern, if we ever externalize WR2 agent defs).                                                                                       |
| [jeevanbavandla/instagram-carousel-skill](https://github.com/jeevanbavandla/instagram-carousel-skill) | Claude Code skill; 4 CSS presets auto-picked by topic; HTML→Playwright 1080×1350                       | Python, Playwright                   | **MIT** ✅                                      | ~1★, low maturity | **[FORKA-E-ADATTA]**                                            | Topic-type → design-preset auto-selection logic. Low maturity — study, don't depend.                                                                                                                                 |

---

## 2. Brick 2 — Brief / ground-truth (RAG)

**SOTA pattern**: retrieve → ground → cite verbatim _before_ generation. This is exactly what our `wr2-brief-interpreter` does via NotebookLM (Contract B: ≥1 NB query, `nb_sources_consulted`/`nb_query_log` non-empty or abort). The general-purpose world uses vector RAG (pgvector/Qdrant) + verbatim-citation discipline; our domain-RAG-via-NotebookLM is _more_ authoritative for Indonesian regulation than a generic vector store would be (curated ground-truth corpus, not scraped web). **No gap here — WR2 leads.** The only general lesson: enforce structured citation objects (regulation, issuing body, decree number, date) — which our constitution Art 6 + the external-bench "source-citation slide" recommendation already push toward.

---

## 3. Brick 3 — Structured copy / narrative output

**The one clean library win.**

| Repo                                                          | What                                                                                                                | License    | Maturity                            | Verdict            | Take                                                                                                            |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ---------- | ----------------------------------- | ------------------ | --------------------------------------------------------------------------------------------------------------- |
| [567-labs/instructor](https://github.com/567-labs/instructor) | Pydantic-validated structured LLM output + **auto-retry on validation failure** (sends the error back to the model) | **MIT** ✅ | ~13.1k★, v1.15.1 Apr 2026, 3M dl/mo | **[INSTALLA-LIB]** | Supports Anthropic, Ollama, DeepSeek. Replaces "emit JSON by prompt convention" with _enforced_ schema + retry. |

**Why it matters for us**: our storyboarder/brief-interpreter emit JSON by prompt convention — when the model drifts, we get malformed slides (the documented "mappazza" / whitelist-strip failures). `instructor` makes the schema load-bearing with automatic re-ask on Pydantic failure. It is provider-agnostic and works with our OAuth Claude (via the `auth_token` SDK path in CLAUDE.md) and local Ollama. Pure additive, MIT, $0.

---

## 4. Brick 4 — Render & layout engine

### Findings

- **HTML/CSS→PNG**: Playwright (persistent process) is still SOTA for _full-fidelity_ branded render — 3-13ms warm, full CSS (Grid, z-index, custom props, WOFF2). Cold-start 42-119ms; binary 300-500MB. **Satori** (Vercel, HTML/JSX→SVG→PNG via Yoga flexbox) is ~5× faster cold (50-200ms total, ~10MB, bit-identical cross-OS) **but** drops CSS Grid, z-index, `calc()`, CSS custom properties (tokens!), WOFF2, `<style>`/external CSS. resvg = the SVG→PNG step.
- **Canvas** (Konva/Fabric/Pillow): better for interactive editors or data-charts, not static branded batch. Pillow is a good _post-process_ step (sharpen, WebP), not a layout engine (no CSS).
- **Templated SaaS** (Bannerbear ~$0.049/img, Placid ~$0.03, Templated.io, Canva Connect): per-render cost + lock-in + rate limits; Canva Autofill (true bulk slot-fill) needs **Enterprise (30+ seats)**. At our volume, OSS self-host is strictly better and $0. Our Canva-MCP path is correctly positioned as the _human-review gate_, at the practical ceiling of non-Enterprise Canva.

### Reuse-first code table — render

| Repo                                                                                        | What                                                                                                          | License                  | Maturity                | Verdict                                                                                        | Take                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------ | ----------------------- | ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Hainrixz/open-carrusel](https://github.com/Hainrixz/open-carrusel) ⭐                      | Chat-with-Claude → HTML/CSS slides → Puppeteer screenshot @1080×1350 → PNG zip. **Nearly our exact pattern.** | **MIT** ✅ (verified)    | ~303★, active 2026      | **[STUDIA-PATTERN-RISCRIVI]** (TS→Python)                                                      | `src/lib/slide-html.ts::wrapSlideHtml()` — ONE render contract for both preview-iframe AND export → "what you see is what you export". async-mutex atomic state writes. |
| [vercel/satori](https://github.com/vercel/satori)                                           | HTML/JSX→SVG layout engine (Yoga flexbox)                                                                     | **MPL-2.0** ⚠️ (not MIT) | ~13.5k★, v0.27 Apr 2026 | **[INSTALLA-LIB]** (MPL: using unmodified is clean; modifying MPL files = publish those files) | Fast-path render for flexbox-only layouts.                                                                                                                              |
| [thx/resvg-js](https://github.com/thx/resvg-js)                                             | SVG→PNG rasterizer (Rust/napi)                                                                                | **MPL-2.0** ⚠️           | ~1.9k★                  | **[INSTALLA-LIB]**                                                                             | PNG-emit step of the Satori path; bit-identical cross-OS.                                                                                                               |
| [Zhengqbbb/x-satori](https://github.com/Zhengqbbb/x-satori)                                 | Vue/Astro → SVG/PNG via Satori+resvg, **CLI batch**                                                           | **MIT** ✅               | ~53★, v0.5.1 May 2026   | **[FORKA-E-ADATTA]**                                                                           | CLI batch loop: iterate slide-props → one PNG each, font as TTF Buffer.                                                                                                 |
| [kvnang/workers-og](https://github.com/kvnang/workers-og)                                   | @vercel/og ported to Cloudflare Workers (browserless edge)                                                    | **MIT** ✅               | ~344★                   | **[STUDIA-PATTERN-RISCRIVI]**                                                                  | WASM bundling for an optional future live-preview endpoint.                                                                                                             |
| [sst/social-cards](https://github.com/sst/social-cards)                                     | Serverless social cards, HTML+Puppeteer on Lambda                                                             | **MIT** ✅               | ~33★                    | **[STUDIA-PATTERN-RISCRIVI]**                                                                  | Template folder + `.fonts/` loading + Lambda Chromium layer.                                                                                                            |
| [SamuraiPolix/Image-Quote-Generator](https://github.com/SamuraiPolix/Image-Quote-Generator) | Python Pillow batch quote-image @1080×1350 (crop/darken/composite)                                            | **GPL-3.0** ⚠️           | ~25★                    | **[STUDIA-PATTERN-RISCRIVI]** (GPL — pattern only, no vendor)                                  | Pillow batch-composition pattern as a post-process complement.                                                                                                          |
| [Maartenlouis/remotion-ads](https://github.com/Maartenlouis/remotion-ads)                   | Remotion + ElevenLabs video ads; includes 1080×1350 static                                                    | **MIT** ✅               | ~44★                    | **[STUDIA-PATTERN-RISCRIVI]**                                                                  | React-component-per-slide model if we ever add animated transitions (→ WR3 territory).                                                                                  |

---

## 5. Brick 5 — Hero image generation & prompt authoring

### Findings — model landscape (2026)

No universal champion; pick per job. Highlights relevant to us:

| Model                                    | Cost/img                             | Photoreal  | Text-in-img | Consistency               | Local?             | Note                                                                                                                  |
| ---------------------------------------- | ------------------------------------ | ---------- | ----------- | ------------------------- | ------------------ | --------------------------------------------------------------------------------------------------------------------- |
| **Nano Banana Pro** (Gemini 3 Pro Image) | **$0 via our Google AI Ultra OAuth** | ★★★★★      | ★★★★★       | up to **14 ref images**   | API                | won ~63% photoreal head-to-heads; **already in our subscription**                                                     |
| GPT Image 2 (our current `$imagegen`)    | $0.04-0.08                           | ★★★★½      | ★★★★★       | good via anchor prompting | no                 | best instruction-following / dense text                                                                               |
| FLUX.1 Kontext Pro/Max                   | ~$0.04-0.08                          | ★★★★       | ★★★★        | ★★★★★ **multi-turn**      | dev=non-commercial | architecturally built for cross-edit consistency                                                                      |
| Imagen 4 Ultra                           | ~$0.08                               | ★★★★★      | ★★★★        | API                       | no                 | quality ceiling; **paid → needs Zero authorization + non-PII only**                                                   |
| Recraft V4 (base)                        | $0.25                                | ★★★★½      | ★★★★        | **style_id brand-lock**   | no                 | `/v1/styles`: 1-5 refs → `style_id` reused across slides. ⚠️ V4.1 Pro _blocks_ style_id (400) — use V4 base           |
| FLUX.1 dev / SD3.5                       | $0 compute                           | ★★★★ / ★★★ | ★★★ / ★★★½  | Redux/IP-Adapter          | **yes**            | FLUX.1 dev ~50s/img on M4 24GB; Q6_K ≈ no quality loss; `--use-pytorch-cross-attention` 30-50% faster. PII-safe path. |

**Prompt-authoring SOTA** (OpenAI image-prompting guide): 5-slot `[scene]→[subject]→[photographic vocab: 35mm/lighting/grain]→[artifact type: "IG 4:5 editorial"]→[preservation constraints repeated every turn]`. Anchor technique: define a reference image, then "Same face/coat/proportions, do not redesign". Avoid aspirational adjectives ("stunning"); describe the photograph. (LPA, arXiv:2507.20094: split content vs style tokens across attention timesteps — training-free uniformity.)

**Cross-slide consistency** (our weak brick) — three viable paths:

1. **FLUX.1 Kontext multi-turn**: generate slide 1 → feed as reference to slides 2-N → identity/lighting/palette carry forward (latent concat). Ref strength ~0.7 sweet spot. Local Kontext-dev on Mini ~50s/img.
2. **Recraft V4 style_id**: one `style_id` from brand refs → pass to every call → palette+texture+lighting lock. (Paid → gate.)
3. **Nano Banana Pro 14-ref**: pass prior slides as references — _zero incremental cost_ (our subscription).

---

## 6. Brick 6 — Critic / QA gate (VLM-as-judge)

### Findings — what's verified

- **Binary is correct.** arXiv:2604.25235 "VLM Judges Can Rank but Cannot Score" (verified real): VLMs rank well but absolute-score badly; uncertainty intervals ~40% of range for aesthetics/natural images, ~70% for charts/diagrams. Point-prediction exact-match ~32-34%; ±1 tolerance ~70-76%. → **Our binary PASS/FAIL is the statistically sound design; scalar 1-5 on palette/composition is noise.** Pairwise (slide A vs B) is more reliable than pointwise if we ever want ranking.
- **Bias taxonomy** (arXiv:2505.15249, EMNLP 2025): text-embedded-in-image inflates scores (dangerous for _design_ images that contain text!); brightness/gamma +5-15%; beauty-filter bias on open-source judges. Prompt-based mitigations (CoT, bias-aware) **largely fail** → use a **closed-source judge** (Claude Opus/GPT-5) which is less susceptible. ✅ we already do.
- **Hallucination snowballing** (arXiv:2407.00569, ACL 2024): if the judge receives an upstream agent's hallucinated claim in context, open-source judges degrade ≥31%. **Mitigation: keep critic context clean** — feed only `{image, brief, rubric}`, never the prompt-author's chain-of-thought.
- **Design-eval reality** (AesEval-Bench): proprietary > open-source on multi-dim design; reasoning models (o1/o3) show _no_ clear advantage for design; precise problem _localization_ is hard (~0.20 IoU best). → validates Haiku cheap semantic pre-pass + Opus final multi-rubric (what we do).

### Reuse-first code table — critic + image-gen

| Repo                                                                                                                        | What                                                                            | License                        | Maturity                        | Verdict                                                                            | Take                                                                                                                            |
| --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------ | ------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| [prometheus-eval/prometheus-vision](https://github.com/prometheus-eval/prometheus-vision)                                   | OSS VLM evaluator; 15K rubric templates; rubric input format                    | **Apache-2.0** ✅              | ~86★, 2024                      | **[STUDIA-PATTERN-RISCRIVI]** (don't deploy 13B; port the rubric _schema_ to Opus) | Rubric format: `instruction + image + score_rubric{1..5 descriptions} + reference_answer`.                                      |
| [BCG-X-Official/artkit](https://github.com/BCG-X-Official/artkit)                                                           | GenAI testing framework; image-gen + VLM scoring pipeline                       | **Apache-2.0** ✅              | ~162★                           | **[STUDIA-PATTERN-RISCRIVI]**                                                      | `ak.chain()`/`ak.parallel()` pipeline + `CachedVisionModel` caching + JSON-schema rubric.                                       |
| [robertvoy/ComfyUI-Flux-Continuum](https://github.com/robertvoy/ComfyUI-Flux-Continuum)                                     | Modular FLUX workflow; Redux ≤3 refs; ControlNet Canny/Depth/Pose; seed control | **MIT** ✅                     | ~239★, 2025                     | **[FORKA-E-ADATTA]**                                                               | Local consistency: Redux multi-ref + ControlNet composition lock + `POST /api/prompt` seed-locked automation. PII-safe on Mini. |
| [cubiq/ComfyUI_IPAdapter_plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus)                                             | IP-Adapter style transfer in ComfyUI                                            | **GPL-3.0** ⚠️                 | ~6k★, maintenance-only Apr 2025 | **[STUDIA-PATTERN-RISCRIVI]** (GPL — pattern only)                                 | Reference-image style conditioning (scale ~0.7). InstantX caveat: not for fine-grained character consistency.                   |
| [EvoLinkAI/awesome-gpt-image-2-API-and-Prompts](https://github.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts)           | GPT Image 2 prompt patterns + API examples                                      | **CC0-1.0** ✅ (public domain) | ~16k★                           | **[INSTALLA-LIB]** / copy verbatim                                                 | Mine `/cases` for editorial-photography prompt templates (public domain, copy freely).                                          |
| [whongzhong/MMHalSnowball](https://github.com/whongzhong/MMHalSnowball)                                                     | Hallucination-snowball benchmark + Residual Visual Decoding mitigation          | **GPL-3.0** ⚠️                 | ~16★, ACL 2024                  | **[STUDIA-PATTERN-RISCRIVI]** (GPL)                                                | The architectural principle: no upstream CoT in judge context.                                                                  |
| [ziqihuangg/Awesome-Evaluation-of-Visual-Generation](https://github.com/ziqihuangg/Awesome-Evaluation-of-Visual-Generation) | Index of 50+ visual-gen eval methods                                            | not stated                     | ~450★                           | **[STUDIA-PATTERN-RISCRIVI]**                                                      | Discovery index (DesignBench, EvalAlign entries).                                                                               |

---

## 7. Brick 7 — Publishing & feedback loop

- **Publishing**: Postiz (AGPL, 31.5k★, Temporal) and Mixpost (MIT, 3.3k★, Laravel/PHP) are the OSS self-host leaders. **But auto-publish to Instagram is a deliberate non-goal for us** (Legge 5 / OB-1 owner-binding: Damar publishes manually). So this brick is intentionally human-gated; we do not need a scheduler. Mixpost is MIT-vendorable but off-stack (PHP); Postiz is pattern-only (AGPL). Keep both as reference, adopt neither.
- **Feedback loop**: our weekly Reflexion (`com.balizero.wr2.reflexion.weekly`) + monthly external-bench + IG-metrics-analyst is the SOTA shape (metric-grounded self-improvement). The one documented missing piece is a **negative-example library** (see §8 Rec 3).

---

## 8. WR2 gap analysis — prioritized actions

What WR2 already does at/above SOTA (DEFEND, don't regress): orchestrator + stateless no-peer workers; NotebookLM verbatim ground-truth; 4-rubric vision critic with binary verdict + Haiku pre-pass; weekly metric-grounded Reflexion; closed-source judge; cost-zero OAuth discipline; anti-cliché brand constitution. The six-anchor headline rule is industry-aligned (per `_external-bench-2026-05.md`).

**Prioritized upgrades** (each is additive, $0 unless flagged):

| #                           | Action                                                                                                                                                                                                                                                                                                                                                                        | Source / code                                                                                                 | Effort  | Why                                                                                                                                                                  |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **P1**                      | **Cross-slide visual consistency**: pass slide-1 hero as a reference image to subsequent hero calls. Use **Nano Banana Pro (14-ref)** — already in our Google AI Ultra sub — as Tier-1A in the hero cascade.                                                                                                                                                                  | Brick 5; `agy`/Flow path we already have (FlowKit)                                                            | Medium  | Our weakest brick; zero incremental cost; fixes incoherent lighting/palette across slides.                                                                           |
| **P2**                      | **`instructor` for structured output** in brief-interpreter + storyboarder (Pydantic schema + auto-retry on validation fail).                                                                                                                                                                                                                                                 | [567-labs/instructor](https://github.com/567-labs/instructor) MIT, `[INSTALLA-LIB]`                           | Low     | Kills the "JSON-by-convention drifts → mappazza/whitelist-strip" failure class. Works with OAuth Claude + Ollama.                                                    |
| **P3**                      | **Critic hardening (3 fixes)**: (a) context isolation — feed critic only `{image, brief, rubric}`, never upstream CoT; (b) split scalar rubrics into clean binaries (hue-in-palette? text-legible-at-320px? text-safe-zone-clear? subject-matches-topic?); (c) Pydantic critic output with `retry_priority: hero\|text\|layout\|none` so the retry agent knows _what_ to fix. | Bricks 6; arXiv:2407.00569 / 2604.25235 / 2505.15249                                                          | Low-Med | Directly attacks snowballing + scalar-noise; closes the "retry agent re-infers failure from free-text" gap.                                                          |
| **P4**                      | **One render contract**: a `wrap_slide_html(body, w=1080, h=1350)` consumed identically by preview AND Playwright export (inject viewport meta + preloaded @font-face + overflow:hidden).                                                                                                                                                                                     | [open-carrusel](https://github.com/Hainrixz/open-carrusel) `slide-html.ts` (pattern → Python) MIT             | Low     | Eliminates "looks-right-in-preview, broken-in-export" divergence (a bug class we've hit).                                                                            |
| **P5**                      | **Persistent Playwright browser pool** in the render worker (single launch, reuse across all slides in a run).                                                                                                                                                                                                                                                                | Brick 4 benchmark (warm 13ms vs cold 2s/slide)                                                                | Low     | Cheap latency/cost win if each slide currently spawns a fresh Chromium.                                                                                              |
| **P6**                      | **Migrate the carousel fan-out to LangGraph** with typed `CarouselState`, `AsyncPostgresSaver` checkpointer (reuse `kg_langgraph_orchestrator`'s), and a `critic_gate` conditional edge (route on `status` enum, loop back to storyboarder, fall to human_review at retries≥2).                                                                                               | [social-media-agent](https://github.com/langchain-ai/social-media-agent) MIT pattern + our existing LangGraph | High    | Crash-resume (we've lost draft states on deploy restart), structural gate the model can't rationalize past, durable HITL. Biggest structural win but biggest effort. |
| **P7**                      | **Negative-example library**: persist critic-rejected drafts to `carousel_negative_examples (topic_type, dominant_mode, storyboard_json, critic_verdict_json, rejection_reason)`; storyboarder RAG-queries last 3 for the topic_type before generating (read-only; orchestrator writes post-critic).                                                                          | SAGE/Reflexion pattern; our autopsy memory `decision_wr2_autopsy_remediation_batch1_2026_06_04`               | Medium  | Converts failure memory into _intra-run avoidance_ (not just weekly retrospective) — directly attacks the documented "monotono+sbagliato" recurrence.                |
| **O1** (optional, gated)    | Imagen 4 Ultra / Recraft V4 `style_id` for ceiling-quality or hard brand-lock.                                                                                                                                                                                                                                                                                                | Brick 5                                                                                                       | —       | **Paid API → requires Zero's authorization + non-PII only** (CLAUDE.md cost rule). Don't install autonomously.                                                       |
| **O2** (optional, PII-safe) | Local FLUX.1 Kontext-dev / Redux + ControlNet on Mini for $0 PII-safe consistency.                                                                                                                                                                                                                                                                                            | [ComfyUI-Flux-Continuum](https://github.com/robertvoy/ComfyUI-Flux-Continuum) MIT                             | Med     | When a hero must not touch cloud (rare for public carousels, but available).                                                                                         |

**Suggested sequencing**: P2 + P3 + P4 + P5 first (all low-effort, high-leverage, $0, no architecture change). Then P1 (consistency, the headline gain). Then P7 (negative-example library). P6 (LangGraph migration) last — highest value but a real refactor; do it when a draft-loss-on-restart incident next bites.

---

## 9. License gate summary (load-bearing)

- **Vendorable (MIT/Apache/BSD/CC0)**: instructor, langchain social-media-agent, clipcraft, carousel-generator, jeevanbavandla-skill, x-satori, workers-og, sst/social-cards, remotion-ads, open-carrusel, prometheus-vision, artkit, ComfyUI-Flux-Continuum, EvoLinkAI prompts.
- **MPL-2.0** (use unmodified = clean; modifying the MPL files obliges publishing _those_ files): satori, resvg-js.
- **GPL-3.0 — PATTERN ONLY, never copy code** (copyleft contaminates): SamuraiPolix/Image-Quote-Generator, cubiq/ComfyUI_IPAdapter_plus, MMHalSnowball, ComfyUI-ReduxFineTune.
- **AGPL-3.0 — PATTERN ONLY** (strongest copyleft): postiz-app.
- **No LICENSE file = all-rights-reserved, NOT copyable** (study only): DataTalksClub/carousel-automation, crewai-instagram-example, ziqihuangg index.

When vendoring any MIT/Apache code, keep the attribution header + add to a `PROVENANCE.md` (repo, license, file, commit).

---

## 10. Source-honesty notes (anti-hallucination)

These were **verified by the orchestrator** (not just relayed from sub-lanes):

- arXiv:2512.08296 — real; but "17.2×/4.4×" are secondary-commentary numbers, NOT in the abstract. Soften our internal attribution.
- arXiv:2604.25235 — real (the `2604` prefix looked future-dated; it resolves; ranking-vs-scoring finding genuine).
- `Hainrixz/open-carrusel` — real, MIT, 303★, `wrapSlideHtml()` confirmed present.

Items relayed from Sonnet lanes but **NOT independently re-verified by the orchestrator** (high prior of being correct, but treat star counts/dates as approximate and re-check before acting): exact star counts and last-commit dates of the other ~20 repos; the FLUX.1 Kontext / Recraft / Nano Banana per-image prices; arXiv:2505.15249 / 2407.00569 / 2507.20094 / AesEval ids. Before building on any single one, re-fetch it (CLAUDE.md rule 1-2: verify load-bearing facts with a fresh tool call).

---

## 11. Carryover / open questions

- [ ] P1 cross-slide consistency: prototype Nano Banana Pro 14-ref via FlowKit on one real carousel; measure visual coherence vs current anchor-reuse.
- [ ] Decide if `instructor` (P2) goes into brief-interpreter/storyboarder this cycle — it's the cheapest high-leverage change.
- [ ] Soften the "17.2× (Google)" attribution wherever it appears in our agent docs / brand cortex to match §1.
- [ ] Re-verify the ~20 unverified repo star/date claims before any one becomes a dependency.
- [ ] P6 LangGraph migration — park until next draft-loss-on-restart incident, then prioritize.
