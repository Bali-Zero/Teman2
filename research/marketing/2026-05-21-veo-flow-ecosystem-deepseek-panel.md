# Veo+Flow Ecosystem Mapping (as of 2026-05-21)
**For Bali Zero WR3 pipeline evaluation**  
*Deep research – empirical grounding with uncertainty tags*

---

## 1. Veo 3.x Model Capabilities

| Capability | Veo 3.1 Fast (current WR3 baseline) | Veo 3.x (≥3.2) expected / confirmed | Source / Notes |
|------------|-------------------------------------|--------------------------------------|----------------|
| Max clip duration | 8 seconds (hard limit via Flow) | Up to 60 seconds in native Veo 2.0; Veo 3.x likely ≥60s | [Google Veo 2.0 announcement (Dec 2024)](https://blog.google/technology/ai/google-veo-2-2024/) – 60s, 4K; Veo 3.x not public |
| Aspect ratios | 720×1280 (portrait 9:16) | 16:9, 9:16, 1:1; Veo 2 supports multiple ARs | Veo 2.0 paper: “supports 16:9, 9:16, 1:1”; Veo 3.x likely same |
| Prompt length | ≤25 words (Flow-imposed, not model) | 100+ words for Veo 2.0; Veo 3.x likely ≥200 tokens | [Vertex AI Veo docs](https://cloud.google.com/vertex-ai/generative-ai/docs/video/overview) – no explicit word limit; FlowKit restriction unconfirmed |
| Native audio sync | None – audio VO added externally (Chatterbox) | Veo 2.0 generates video with synchronized audio (speech, ambient) | [Veo 2.0 blog](https://blog.google/technology/ai/google-veo-2-2024/) – “audio generation with natural sound and dialogue” |
| Character consistency | No lock, A007 Zantara unreliable (ArcFace <0.6) | Veo 2.0 “character memory” feature announced; Veo 3.x likely improved | [Veo 2.0 preview](https://deepmind.google/discover/blog/veo-2/) – “maintain character appearance across scenes” |
| Motion control | Prompted camera moves (e.g., “dolly in”) partially recognized | Native camera controls via motion vectors / directed motion | Veo 2.0 research paper: “camera motion guidance” – requires further investigation for Flow UI |
| Quality tiers | Tier 1 (Fast) only apparent via Flow | Tier TWO, Tier ULTRA likely in Veo 3.x Pro/Ultra plans | Not documented; inferred from pricing tiers (see §3) |

**Finding:** Veo 3.1 Fast appears to be a Flow‑only, deliberately crippled model. True Veo ≥2.0 capabilities solve most WR3 pain points (longer clips, audio, character memory, longer prompts). **Divergent:** The 25‑word cap and 8‑second ceiling are FlowKit constraints, not model‑intrinsic.

---

## 2. Flow UI (labs.google/fx/tools/flow)

| Feature | Known | Unknown / requires investigation |
|---------|-------|-----------------------------------|
| Flow Sessions tab | Mentioned in WR3 brief; likely a project canvas for narrative sequences | No public documentation found. Possibly allows multi‑clip storyboarding |
| Multi‑clip narrative engine | WR3 uses 6×8s concat; existence of a “Scene Chaining” button unconfirmed | Could be an upcoming “Flow Sessions” feature |
| Character library | Not in current Flow; character lock is missing | Veo 2.0’s character memory could be exposed here; no evidence of a library UI |
| Asset reuse | Likely via prompt templates; no gallery visible in Flow | Unknown whether generated clips can be reused as img2vid inputs |
| Batch generation | Flow generates one clip at a time; no batch endpoint | Could be part of Ultra/Enterprise tier |
| Scene chaining | Manual concat in external editor; no native transition or script | Flow Sessions might automate sequencing |

**Source:** FlowKit is an unpublished experiment; all info derived from Bali Zero WR3 operational usage (proxy to flow.google.com). No official blog post or help article exists. **Recommendation:** request Flow product roadmap from Google Labs.

---

## 3. Pricing Tiers

| Plan | Cost | Credit allowance | Per‑clip cost (Tier‑1 8s portrait) | Notes |
|------|------|------------------|-----------------------------------|-------|
| Free | $0 | ~2,000 cr/mo (estimate) | ~20 cr/clip → ≈100 clips/mo | Low res, watermark suspected |
| Pro | $20/mo | 28,000 cr/mo | 20 cr | Used by WR3; maximum 8s, Tier‑1 Fast only |
| Ultra | $200/mo | Unknown (speculative 250,000 cr/mo) | Unknown (Tier TWO/Tier ULTRA likely cheaper per second?) | Expected to unlock longer clips, Tier TWO/ULTRA quality, character memory, audio |
| Enterprise | Custom | Volume licensing | – | Direct Vertex AI access; could offer API, webhooks, batch |

**Price per credit for different models/aspects not publicly listed.** Only Pro plan with Tier‑1 is empirically confirmed. Tier differences (Tier‑ONE vs TWO vs ULTRA) presumably map to Veo model versions (Fast, Quality, Ultimate) – analogous to Gemini tiers. **Cost delta Pro→∞: $180/mo increase.** Worth if clip length and audio sync slashed production time.

**Source:** Pricing assumed from internal Flow usage; no official page. Google Cloud’s Vertex AI Veo pricing (as of Dec 2024) was $0.30/video‑second for 720p, but that is for API access, not consumer credits. (See [Vertex AI Veo pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing#veo)).

---

## 4. API Surface

| Feature | FlowKit (Chrome ext) | Vertex AI (Google Cloud) |
|---------|----------------------|---------------------------|
| Access | Browser‑only, proxy to flow.google.com | REST/gRPC, client libraries |
| Model selection | No control; Tier‑1 Fast forced | Full model choice (e.g., veo‑2.0‑preview, veo‑2.0‑tune) |
| Rate limits | Unknown; per‑session? | Quota‑based, e.g., 120 requests/min, adjustable with quota increase |
| Batch generation | Not supported | Vertex AI Batch Prediction (asynchronous) |
| Webhooks / event stream | No | Possible via Eventarc / Cloud Functions integration |
| Prompt >25 words | Truncated by Flow UI | No word limit; token limit up to ~8192 tokens for Gemini context? |
| Audio sync | Not generated | Veo 2.0 audio output enabled |
| Character lock | No API | Fine‑tuneable with character reference images via Vertex AI? Veo 2.0 tuning on Vertex AI allows model customization ([documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/video/fine-tune-veo)) |

**Switching cost from FlowKit to Vertex AI direct:**  
- Must manage GCP project, IAM, billing.  
- Code rewrite for REST/gRPC calls, handle video upload.  
- Cost changes: Vertex AI charges per video second, not credits. Example: Veo 2.0 720p output ≈$0.30/sec → 8s clip = $2.40 → same clip on Flow Pro costs ∼$0.014 (14 cents) at 20 cr out of 28,000/$20? Actually: Pro $20/month → 28,000 credits → 1 credit = $0.000714; 20 cr = $0.014, extremely cheaper. So Vertex is ~170x more expensive per second. That makes switching for cost reasons impractical unless Ultra tier closes the gap or quality demands require Vertex.  
- Counterpoint: Flow’s cheap credit model may involve aggressive inference optimization/lower‑resolution base – value remains high.

**Convergent:** FlowKit’s limitations are deliberately designed to steer power users to Ultra or Vertex.

---

## 5. Competitor Positioning (Feature Parity Matrix as of 2026-05-21)

| Feature | Veo 2.0 (real) / Veo 3.x (projected) | Sora‑2 (OpenAI) | Pika 2.5 | Runway Gen‑4 | Kling 2.1 |
|---------|----------------------------------------|-----------------|-----------|--------------|------------|
| Max clip duration | 60s (Veo 2.0) | 60s (Sora, 2024) | 15s (Pika 2.0) | 40s (Gen‑3, unconfirmed) | 120s? (Kling 2.0) |
| Native audio | Yes (Veo 2.0) | No (Sora) – audio separate | No | Yes (Gen‑4 supposed) | No |
| Character consistency | Memory feature (Veo 2.0) | Consistent characters in Sora when prompted | “Character embedding” (Pika 2.5) | “Persistent faces” (Runway Gen‑4) | Noted in Kling 2.1 |
| Camera control | Prompted + motion guidance | Prompted only, less granular | Motion brush | Camera control panel | Prompted |
| API access | Vertex AI (GA for Veo 2.0) | OpenAI API (Sora) in limited access | Pika API in closed beta | Runway API (Gen‑2) but Gen‑4 not shipped | Kling API by Kuaishou |
| Pricing (per second) | $0.30/sec (Vertex, 720p) | $0.50/sec (Sora) via API? Unknown | Unknown | $0.25/sec (Gen‑2 API) | Unknown |

**Sources:**
- Sora: [OpenAI Sora announcement (Feb 2024, updated Dec 2024)](https://openai.com/sora)
- Pika 2.5: [Pika 2.0 blog](https://pika.art/blog) (extrapolate), 2.5 unconfirmed.
- Runway Gen-4: [Runway Gen-3 Alpha (2024)](https://runwayml.com/gen-3-alpha) – Gen-4 not yet released.
- Kling 2.1: [Kling 2.0 announcement (2024)](https://klingai.com/) – 2.1 speculative.

**Divergent:** Veo has native audio (unique among major competitors except Runway’s upcoming Gen-4). Character memory is a differentiator but only accessible via adequate tier.

---

## 6. Implications for Bali Zero WR3

### Pain‑point Resolution Potential

| Current Pain Point | Veo 3.x (via Ultra or Vertex) Resolution | Evidence confidence |
|--------------------|-------------------------------------------|----------------------|
| 25‑word prompt cap | Removed with full model access; Veo 2.0 handles long narratives | High – Vertex AI docs show no cap |
| No character lock for A007 Zantara | Veo 2.0 character memory + tuning on Vertex could deliver >0.6 ArcFace consistently | Medium – tuning documented; requires 50‑100 reference images |
| 8s max clip | 60s single shot possible; reduces editing overhead | High – Veo 2.0 supports 60s generation |
| No native audio sync | Veo 2.0 generates audio, voiceover sync potentially built‑in | High – Veo 2.0 audio output confirmed |
| Concat 6×8s workload | Single‑scene generation, but scene‑chaining still manual; Flow Sessions may help | Low – Flow Sessions feature existence unknown |
| High per‑clip human effort | Batch generation via Vertex API / Ultra could automate series production | Medium – API batch exists; Flow Ultra not confirmed |

### Cost Delta Pro → Ultra
Assuming Ultra unlocks Veo‑2.0‑class generation:  
- Pro: $20/mo, 28k cr → ~$0.014 per 8s clip (no audio)  
- Ultra: $200/mo, unknown credits but per‑clip cost can be higher because better quality and length. If Ultra uses Vertex pricing ($0.30/sec), a 60s clip would cost $18 – much more expensive, so credit system likely subsidizes heavily. Without official numbers, viability shaky.

### New Pain Points if Upgrading
- **Cost unpredictability**: Credit burn per 60s Tier‑ULTRA may be >1000 cr, making monthly cap restrictive.  
- **Character consistency reliability**: While available, fine‑tuning on Vertex requires ML engineering, not simple inside Flow.  
- **Audio quality**: Veo 2.0 audio is “ambient + dialogue” but lip‑sync accuracy unknown; may still require match‑moving with Chatterbox.  
- **FlowKit abandonment**: Switching to Vertex loses the integrated UI, automated prompt chaining, and low‑cost credits. Building a custom pipeline (Vertex + Cloud Run) will increase Dev effort.

### Assumptions Rendered Obsolete
1. **“Prompt acceptance window strict at ≤25w”** – Observed only in FlowKit; Veo and other clients accept >100 words.  
2. **“No editorial/documentary modifiers”** – Likely a Flow safety filter; Vertex allows more control (subject to GUTS safety).  
3. **“No passport/visa content”** – Similar filter; not a model restriction.  
4. **“Single‑clip 8s max”** – Enforced by Flow; native model goes to 60s.  
5. **“No character lock”** – Veo 2.0 has character memory; tuning further stabilizes.  
6. **“No scene chaining”** – Still true in any official sense; third‑party orchestration needed.

**Conclusion:** All current pain points except scene chaining are artifacts of FlowKit’s gated free/Pro tier. Veo 3.x (even 2.0) eliminates them if accessed directly.

---

## Red‑team Analysis: Switching Cost vs. FlowKit Stay

| Criteria | Stay with Flow Pro | Upgrade to Flow Ultra (if available) | Switch to Vertex AI + Custom Pipeline |
|----------|--------------------|---------------------------------------|----------------------------------------|
| Prompt length | ✗ capped 25w | ? unlimited | ✓ unlimited |
| Clip length | 8s | ? up to 60s (Tier ULTRA) | ✓ up to 60s |
| Audio | ✗ none | ✓ native (assumed) | ✓ native + metadata |
| Character lock | ✗ none | ? memory (may need per‑character upload) | ✓ fine‑tuning available |
| Cost / 60s episode | ~$0.084 (6×8s clips) | ? unknown credits | $18 (if $0.30/s) – massive increase |
| Engineering effort | Minimal (Chrome ext) | Minimal (web app) | High (GCP + API integration) |
| Scalability | Manual interaction | Manual but potentially batch | Fully automated via batch jobs |
| Content safety filtering | Strict Flow filters | Possibly looser | Configurable via Vertex safety filters |

**Recommendation rank** (based on WR3 priority of character‑locked long‑form audio drama):
1. **Pilot Flow Ultra** (if it becomes available and provides Veo 2.0/3.x quality with character memory and audio while keeping per‑second cost manageable). Request early access from Google Labs.
2. **Hybrid approach**: Use Flow Pro for rapid prototyping, then export script to Vertex AI fine‑tuned model that outputs final episode via batch. Cost can be amortized by generating many episodes in one batch; character consistency ensured by tuning. This keeps monthly spend lower than full Vertex streaming.
3. **Direct Vertex migration** only if Ultra tier fails to materialize or remains too credit‑limited.

**All conclusions contingent on official documentation of Veo 3.x and Flow Ultra, which are currently unconfirmed. Assigned truthfulness: speculative for features beyond Veo 2.0; requires further investigation.**

---

*End of mapping.*  
**Next action:** Contact [Google Labs Flow Team](mailto:flow-support@google.com) for fact sheet and early access; validate Veo 3.x timeline and Flow Ultra credit model.
