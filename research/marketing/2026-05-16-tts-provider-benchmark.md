---
date: 2026-05-16
domain: marketing
client_case: Zantara voice-over for Bali Zero editorial video brand — replace ElevenLabs ($0.18–0.30 per 1K char) with provider matching quality at lower API cost
sources: 18
status: draft pending pilot
---

# TTS Provider Benchmark per Bali Zero — 2026-05-16

## Question

Trovare alternative a ElevenLabs come TTS / voice-cloning provider per la voce "Zantara" (adult Indonesian woman, warm precise calm English, soft Indonesian accent, medium-low female register, protective authority). Criteri prioritari: (1) Indonesian-English accent via cloning da WAV reference 45–75s, (2) API pricing < $0.18/1K char (ElevenLabs Pro floor), (3) quality ≥ ElevenLabs Multilingual v2, (4) self-host opzionale per data sovereignty (UU PDP), (5) ethical consent flow + no-training-on-user-data clause.

## TL;DR top 3 winner

1. **MiniMax Speech 2.6/2.8** — $40/1M char ($0.04/1K), Indonesian nativo nei 40+ lang, voice cloning da **5 secondi** di audio, modello cinese SOTA Speech 2.8 con "studio-grade clarity" e native sound tags. **Best price/quality cloning + native Indonesian phonology**, ~85% cheaper di ElevenLabs Pro. Pilot target #1.
2. **Cartesia Sonic-3** — Pro plan $4/mo + Startup $39/mo (Pro voice clone), pay-as-you-go ~$50/1M char (15 credits/sec audio, Sonic-3 90ms TTFA). MOS-equivalent quality, instant clone già su Pro $4. **Best latency + lowest entry cost con commercial license**. Pilot target #2 se MiniMax accento non convince.
3. **Chatterbox Multilingual (Resemble OSS, MIT)** — **gratis, self-hosted** su Pro M4 48GB. 63.75% blind preference vs ElevenLabs (Dec 2025 Turbo release), 23+ languages incl. Indonesian, zero-shot clone da 7–20s reference, emotion exaggeration control parameter. **Best data sovereignty + zero marginal cost**. Pilot target #3 per long-form (post-prod batch).

## Comparative table — pricing per 1M caratteri (cloud) o licensing (open source)

| Provider | API pricing /1M char | Voice cloning | Indonesian-English | Self-host | Quality signal |
|---|---|---|---|---|---|
| **ElevenLabs** v2 Multilingual | **$165–300** (Pro $99/mo → $0.165; PAYG $0.30) | Instant from Starter $6, Pro PVC from Creator $22 | Native Indonesian voice library + cloning preserves source accent | No | MOS 4.3 (highest commercial, reference) |
| **ElevenLabs** v3 | $100 (launch promo) → $206 standard | Same as v2 | 70+ langs, audio tags | No | Best emotion, NOT realtime, alpha→GA Q1 2026 |
| **ElevenLabs** Flash v2.5 | $66–103 | Instant only | 32 langs | No | MOS slightly below v2, but realtime |
| **Cartesia Sonic-3** | ~$50 (15 cr/sec; $4/mo Pro tier instant clone) | Instant $4/mo; Pro clone $39/mo | "Multilingual" — Indonesian non confirmed in docs | No | TTFA 90ms, MOS ≈ ElevenLabs, top-3 Artificial Analysis |
| **Hume Octave 2** | **$50 ($0.05/1K Business tier) – $76 ($7.60/1M cited)** | None at tier listed; expression-control native | 11 langs + 20 more "coming"; Indonesian **NOT confirmed** | No | Emotion-best, 50% cheaper than Octave 1, <200ms |
| **MiniMax Speech 2.5T/2.6/2.8** | **$40 ($0.04/1K)** | Instant from **5s** of audio, 40+ langs | **Indonesian explicitly listed** | No (cloud only) | Top-tier WER, native sound tags, Hailuo backed |
| **Speechify SIMBA 3.0** | **$10** ($0.01/1K, PAYG) | Yes, included | 60+ langs incl. Indonesian | No | **Top-10 Artificial Analysis leaderboard** above Google/Azure/AWS/OpenAI/ElevenLabs at fraction of cost |
| **Inworld Realtime TTS 1.5/2** | $15 (Mini) / $25 (Max) / $35 (Pro tier) | From 15s of audio | Multilingual — Indonesian unverified | No | **Realtime TTS 1.5 Max = #1 Artificial Analysis Elo 1208** |
| **OpenAI gpt-4o-mini-tts** | **$15** ($0.015/min audio) | None (13 fixed voices) | English-only voice library | No | Steerable via prompt, slightly robotic |
| **PlayHT** (PlayDialog/Play 3.0) | $22–66 (subscription-derived) | Instant from 30s | Indonesian + 142 langs | No | Mid-tier MOS; conversation-tuned |
| **Resemble AI** | $7.94 ($0.006/sec ≈ $0.36/min) | Included; enterprise watermarks | Multilingual, Indonesian via cloning | Yes (Chatterbox OSS) | Enterprise-compliance leader (perceptual hashing) |
| **Azure Neural HD** | $91.75 (HD) / $14.11 (Standard) / $24 (Custom Neural Voice trained) | Custom Neural Voice (trained, slow) | 140+ langs incl. Indonesian | No | Enterprise-grade, slower iteration |
| **Google Chirp 3 HD** | $30 | None on Chirp 3 HD | Multilingual; Indonesian on legacy WaveNet | No | "30 distinct styles", AudioML disfluencies |
| **Amazon Polly Generative** | $30 | None | English-only on Generative tier | No | LLM-based, no streaming |
| **WellSaid Labs** | ~$66 (Maker plan derivative) | Studio-trained (consent-strict) | English narration focus | No | Top consent posture, mid-tier accent range |
| **Coqui XTTS-v2** (legacy OSS) | **$0** self-host | Zero-shot 10–20s | 16 langs incl. Indonesian | **Yes** (16GB+ GPU) | 94% of ElevenLabs quality; accent bleed from reference; archived 2024, fork at idiap |
| **Fish Speech V1.5 / Audio S2** | **$0** self-host (V1.5) | Built-in zero-shot | 80+ langs (S2), Indonesian on cloud | **Yes** (V1.5) | TTS Arena Elo 1339; S2: WER 0.99% EN |
| **Chatterbox / Chatterbox Multilingual** (Resemble OSS MIT) | **$0** self-host | Zero-shot 7–20s, emotion-exag control | 23+ langs incl. Indonesian | **Yes** (~350M params, fits Pro 48GB) | **63.75% blind preference vs ElevenLabs** (Dec 2025 evals) |
| **Suno Bark / MaskGCT / Style-Bert-VITS2 / MeloTTS** | $0 self-host | Variable | Mostly EN/CN/JP-focused | Yes | Bark generative but glitchy; MaskGCT competitive; others narrow lang scope |

> Note pricing methodology: API per-1M figures derived from PAYG when published; subscription-derived figures (ElevenLabs Pro $99 / 600K credits = $165/1M; Play.ht Unlimited $99 / 2.5M cap = $40/1M effective) flagged as such. ElevenLabs cited overage rate $300/1M (Awesome Agents) suggests heavy penalty over plan quota — **MUST size plan correctly or get burned**.

## Detailed evaluation

### Tier 1 — Winner candidates

**MiniMax Speech 2.6 HD / 2.8 (cloud, China-stack):** $0.04/1K char is **~4.5× cheaper than ElevenLabs Pro tier and ~7.5× cheaper than ElevenLabs PAYG**. Indonesian is in the 40+ supported language list. Voice cloning needs only **5 seconds** of reference audio (vs. ElevenLabs IVC requires ~1 minute, PVC requires 30+ minutes). Speech 2.8 added native sound tags (laughter, sigh, whisper) and "studio-grade clarity". **Caveat geopolitico:** Chinese stack — if Antonello/Bali Zero ever publishes content on Indonesian government commentary, hosting voice-clone model weights on Chinese cloud is a residual risk. Mitigation: use only for Bali Zero brand voice (not client-data narration), no NPWP/passport content in prompts.

**Cartesia Sonic-3 (US, Y-Combinator pedigree):** $4/month Pro tier gets you instant voice cloning + commercial license + 100K credits/month. Sonic-3 is the only Tier-1 model with documented 90ms time-to-first-audio — overkill for our post-prod use case but enables future realtime use (e.g. agent voice on kita.balizero.com). Top-3 in Artificial Analysis text-to-speech rankings. **Caveat Indonesian:** Cartesia advertises "multilingual" but Indonesian is NOT explicitly listed on the pricing page; needs empirical test before commit.

**Chatterbox Multilingual (Resemble OSS, MIT):** the dark horse. Released Dec 15, 2025 (Turbo variant). **63.75% blind preference over ElevenLabs** in vendor-published evals (treat with grain of salt — Resemble has commercial Chatterbox-hosted service). Runs on Pro M4 48GB local. Indonesian among 23+ supported languages. MIT license = zero per-character cost, unlimited inference, full data sovereignty (UU PDP-compliant by construction — audio never leaves Pro). Pairs perfectly with current Ollama-first architecture (`backend/llm/ollama_client.py` pattern).

### Tier 2 — Close but...

**Speechify SIMBA 3.0** at $10/1M char is the cheapest credible quality option (top-10 Artificial Analysis), but Speechify's brand is consumer-grade and their API docs are thinner than Cartesia/MiniMax. Worth a pilot for B-roll narration where Zantara persona isn't the front of mind.

**Hume Octave 2** at $7.60–50/1M char depending on tier has the best **emotion control** primitives in the industry (Octave is built atop Hume's empathic voice work). Critical gap: Indonesian is NOT confirmed in the 11-language launch list. If we want emotion-laden narrative VO (e.g. case study story arc), Hume on English-only with explicit "Indonesian accent" prompt steering may produce decent results — empirical test only.

**Inworld TTS** with Realtime TTS 1.5 Max at #1 on Artificial Analysis Elo (1208) at $25/1M char is mathematically attractive, but Inworld is gaming-NPC-focused and Indonesian language coverage isn't documented. Realtime is irrelevant for our post-prod use case.

**Fish Speech V1.5 / Fish Audio S2** is the strongest open-source counter-candidate to Chatterbox. V1.5 has Elo 1339 (TTS Arena), MIT-leaning license, runs on Pro M4. S2 cloud has WER 0.54% Chinese / 0.99% English — borderline production-grade. Indonesian support listed for S2 cloud only; V1.5 self-host Indonesian is unconfirmed.

**PlayHT, Resemble AI cloud, ElevenLabs Flash v2.5** — all viable but priced above MiniMax+Cartesia+Chatterbox triad with no obvious quality edge for Indonesian-English use case.

### Tier 3 — Skip

**Azure Neural HD ($91.75/1M)** and **Amazon Polly Generative ($30/1M)** are priced like ElevenLabs without ElevenLabs' voice cloning ergonomics. Azure Custom Neural Voice requires hours of training audio + days of turnaround = too slow for our editorial cadence.

**Google Chirp 3 HD ($30/1M)** has no voice cloning on the Chirp 3 HD tier; legacy WaveNet has Indonesian but is lower quality.

**OpenAI gpt-4o-mini-tts ($15/1M)** — 13 fixed voices, no cloning, English-focused. Cheap but won't produce Zantara persona.

**Murf, Speechify Studio (UI tool, not API), Coqui XTTS-v2 legacy** — Coqui's archive status (Jan 2024) and reported "German accent bleed" make it second-choice to Chatterbox or Fish for self-host.

**Suno Bark, MaskGCT, MeloTTS, Style-Bert-VITS2** — research-grade or narrow language scope; not production-ready for Bali Zero brand voice.

### Self-hosted options (Ollama-style local on Pro/Mini)

Pro M4 48GB easily runs:
- **Chatterbox Multilingual** (~350M params, ~3–5GB VRAM): primary recommendation.
- **Fish Speech V1.5** (DualAR transformer, ~7B-ish): second seat, especially if Chatterbox Indonesian disappoints.
- **Coqui XTTS-v2 fork (idiap/coqui-ai-TTS)**: fallback only, accent bleed risk.

Mini M4 24GB: same models feasible at slower latency; suitable for batch overnight VO rendering. Pattern parallel to current Ollama deployment.

## Ethical and data-sovereignty notes

ElevenLabs' early-2025 Terms of Service controversy ("perpetual, irrevocable, royalty-free, worldwide license" to user voice recordings) caused Kukarella to publicly terminate partnership. Even post-walkback, ElevenLabs + Speechify + PlayHT + Lovo are flagged by Consumer Reports (Mar 2025) as having only checkbox-level consent attestation. **Resemble AI is the documented enterprise-compliance leader** — perceptual hashing watermarks embedded at synthesis time. **Cartesia** is developer-focused, terms moderate. **Self-hosted (Chatterbox/Fish/Coqui)** is the only path with zero data-leakage risk — audio never leaves Pro.

For Zantara voice talent (whoever records the 45–75s reference WAV): require signed consent specifying (a) Bali Zero PT exclusive use, (b) editorial video distribution only, (c) no training on third-party model, (d) revocation right with 30-day notice. Template by tier:
- MiniMax / Cartesia / Speechify: rely on platform ToS + signed consent for talent's protection.
- Chatterbox/Fish self-host: stronger guarantee (no platform), but still need talent consent for ethical and Indonesian UU 27/2022 (PDP) compliance.

## Numerical analysis (cost projection for Bali Zero scale)

Assumptions: 18-week editorial cadence (per `2026-05-13-video-format-evergreen-b2b-services.md`), 40–55 published videos, avg 90s voice-over per video → ~22 min audio/week → ~33,000 char/week → ~140K char/month → **~1.7M char/year** of TTS inference.

| Provider | Annual cost @ 1.7M char | vs. ElevenLabs Pro ($99/mo = $1,188/yr if absorbed in plan) |
|---|---|---|
| MiniMax Speech 2.8 | **$68/yr** (1.7M × $0.04/1K) | 17× cheaper |
| Cartesia Pro tier | **$48/yr** (12× $4/mo, 1.2M credits/yr in plan + ~500K overage) | 25× cheaper than ElevenLabs PAYG; same order as plan |
| Speechify SIMBA | **$17/yr** | 70× cheaper |
| Chatterbox self-host | **$0/yr marginal** (Pro M4 already runs Ollama) | infinity-× cheaper |
| ElevenLabs Pro plan | $1,188/yr if 1.7M fits in 7.2M credits (12mo × 600K) | reference |
| ElevenLabs PAYG | $510/yr at $0.30/1K | reference |

**Switching savings:** if pilot confirms MiniMax + Chatterbox quality, annual TTS spend drops from ~$1,200 (ElevenLabs Pro) to **<$100** (MiniMax cloud) or **$0** (Chatterbox self-host). Reinvest into Veo 3.1 video credits or designer time.

## Disagreements / open questions

- **MOS / Elo scoring**: vendor-published scores (Chatterbox "63.75% blind preference", Inworld "Elo 1208") are self-disclosed. Artificial Analysis is the most credible third-party leaderboard but its public-facing page only shows top-1 in plain text; full numbers require interactive dashboard. Disagreement among sources is acceptable here — **the only reliable signal is empirical pilot with our reference WAV**.
- **Cartesia + Hume Indonesian support**: NOT explicitly confirmed in docs. Sources mention "multilingual" generically. Must pilot before committing.
- **ElevenLabs PAYG vs. Pro plan effective price**: sources cite $0.18, $0.30, $0.165, $66/1M, $206/1M. Resolution: $99 Pro plan ÷ 600K credits = $0.165/1K; PAYG overage $300/1M = $0.30/1K. Both numbers are accurate, different consumption mode. ElevenLabs Multilingual v2 vs v3 vs Flash v2.5 have different credit-per-character ratios (Flash = 0.5 credit/char, v2/v3 = 1 credit/char) — this is the source of cost-per-1K confusion across articles.
- **MiniMax geopolitical residual risk**: Chinese stack hosting voice clone weights. Bali Zero brand content is low-sensitivity, but worth flagging to Antonello. Mitigation: Chatterbox self-host as fallback.

## Recommendation for Zantara voice ingredient

**Concrete next steps**:

1. **Record reference WAV** (45–75s) with chosen voice talent, ideally in soundproofed environment, 48kHz 24-bit WAV. Script should include: (a) common Bahasa Indonesia phonemes embedded in English (e.g. "Permenkumham," "KITAS," "Kerobokan"), (b) numbers, (c) varied emotional register (warm welcome, precise legal callout, calm reassurance). Get signed consent (template per ethical section above).
2. **3-way pilot, same reference WAV, identical 200-word test script** (Bali Zero brand intro + visa explainer fragment):
   - MiniMax Speech 2.8 voice clone API (~$0.01 cost total)
   - Cartesia Sonic-3 Pro tier instant clone ($4 to start, downgradable)
   - Chatterbox Multilingual self-host on Pro (free)
3. **A/B blind eval**: Antonello + Asya + 2 team members rate each output 1–10 on (a) accent authenticity, (b) brand voice match (warm/precise/calm/protective), (c) editorial production quality. Decision: highest avg score, ties broken on cost.
4. **Production setup**: integrate winner into `apps/zantara-media/` asset pipeline (Sprint 1.7), with self-host Chatterbox as fallback for sensitive content (client-data narration, NPWP/passport — UU PDP scope). Budget cap: $50/month TTS, alert at $30.
5. **Skip ElevenLabs migration** unless pilot fails all three. Sunk-cost is not a reason to stay on $0.30/1K when MiniMax delivers Indonesian native + voice cloning at $0.04/1K.

## Checklist for action

- [ ] Antonello chooses voice talent + records 45–75s reference WAV (deadline: end of week)
- [ ] Sign voice consent agreement (Bali Zero PT exclusive use, revocation right, no third-party model training)
- [ ] Run 3-way A/B pilot (MiniMax + Cartesia + Chatterbox) on identical test script — budget $10 + 4 hours setup
- [ ] Blind-rate outputs with team (Antonello, Asya, Damar, Vino — Damar/Vino are marketing focus)
- [ ] Verify pilot winner has Indonesian phoneme handling (e.g. "Permenkumham" pronunciation)
- [ ] If MiniMax wins: implement consent + ToS review; flag Chinese-cloud caveat to Antonello explicitly
- [ ] If Chatterbox wins: integrate into `apps/zantara-media/` pipeline; document GPU/CPU cost on Pro
- [ ] Set monthly budget alert ($50 cap, $30 yellow) in finance dashboard
- [ ] Update `~/Desktop/nuzantara/skills/google-flow-video/SKILL.md` with chosen TTS for Veo voice-over overlay workflow
- [ ] Document decision + sample output in `~/.claude/projects/-Users-nuzantara/memory/` as `decision_tts_provider_<choice>_2026.md`

## Sources

1. Cartesia Pricing page — [cartesia.ai/pricing](https://cartesia.ai/pricing) (Pro $4/mo with instant clone confirmed, Sonic-3 15 credits/sec audio)
2. Cartesia Sonic-3 product page — [cartesia.ai/sonic](https://cartesia.ai/sonic) (90ms TTFA)
3. ElevenLabs pricing — [elevenlabs.io/pricing](https://elevenlabs.io/pricing) (Free/Starter/Creator/Pro/Scale/Business tiers verified)
4. ElevenLabs Indonesian voice info — [elevenlabs.io/text-to-speech/indonesian](https://elevenlabs.io/text-to-speech/indonesian)
5. Awesome Agents — TTS API Pricing Compared 2026 — [awesomeagents.ai/pricing/voice-tts-pricing/](https://awesomeagents.ai/pricing/voice-tts-pricing/) (comprehensive matrix incl. Cartesia $50/1M, ElevenLabs overage $300/1M, Hume $30/1M Octave, Resemble $7.94/1M)
6. LeanVox via Dev.to — TTS API Pricing 2026 — [dev.to/leanvox/tts-api-pricing-in-2026](https://dev.to/leanvox/tts-api-pricing-in-2026-i-went-through-every-provider-so-you-dont-have-to-bem) (OpenAI tts-1 $15, Google Neural2 $16, Azure $16, Amazon Polly Neural $16)
7. TokenMix — gpt-4o-mini-tts Pricing — [tokenmix.ai/blog/gpt-4o-mini-tts-cheapest-tts-api-2026](https://tokenmix.ai/blog/gpt-4o-mini-tts-cheapest-tts-api-2026) ($15/1M, 13 fixed voices, no cloning)
8. Hume AI pricing — [hume.ai/pricing](https://www.hume.ai/pricing) (Free $0 → Business $500, Octave 2 50% cheaper than v1)
9. Hume Octave 2 launch — [hume.ai/blog/octave-2-launch](https://www.hume.ai/blog/octave-2-launch) (11 languages + 20 coming, <200ms latency)
10. MiniMax Speech 2.6 — [minimax.io/news/minimax-speech-26](https://www.minimax.io/news/minimax-speech-26) (voice agent multilingual)
11. MiniMax Voice Clone docs — [platform.minimax.io/docs/guides/speech-voice-clone](https://platform.minimax.io/docs/guides/speech-voice-clone) (5s clone, Speech 2.5T $0.04/1K, Indonesian listed)
12. Inworld Best TTS APIs 2026 — [inworld.ai/resources/best-voice-ai-tts-apis-for-real-time-voice-agents-2026-benchmarks](https://inworld.ai/resources/best-voice-ai-tts-apis-for-real-time-voice-agents-2026-benchmarks)
13. Speechify SIMBA 3.0 leaderboard claim — [speechify.com/news/speechify-simba-3-artificial-analysis-tts-top-10/](https://speechify.com/news/speechify-simba-3-artificial-analysis-tts-top-10/) ($10/1M, top-10 above Google/Azure/AWS/OpenAI/ElevenLabs)
14. Resemble AI Chatterbox — [resemble.ai/chatterbox/](https://www.resemble.ai/chatterbox/) (MIT, 23+ langs, Turbo Dec 2025 63.75% preference)
15. Chatterbox GitHub — [github.com/resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox) (350M params, zero-shot 7–20s)
16. Fish Speech GitHub — [github.com/fishaudio/fish-speech](https://github.com/fishaudio/fish-speech) (V1.5 Elo 1339, 300K hours training data)
17. Coqui XTTS-v2 — [huggingface.co/coqui/XTTS-v2](https://huggingface.co/coqui/XTTS-v2) (CPML license, 16 languages, fork at idiap)
18. Consumer Reports voice-clone safeguards assessment Mar 2025 — [consumerreports.org/media-room/press-releases/2025/03/consumer-reports-assessment-of-ai-voice-cloning-products/](https://www.consumerreports.org/media-room/press-releases/2025/03/consumer-reports-assessment-of-ai-voice-cloning-products/) (ElevenLabs/Speechify/PlayHT/Lovo flagged for checkbox-only consent; Descript/Resemble flagged as stronger)
19. Margabagus — ElevenLabs ToS analysis 2026 — [margabagus.com/elevenlabs-voice-cloning-consent/](https://margabagus.com/elevenlabs-voice-cloning-consent/) (consent requirements + 2025 ToS controversy context)
20. Cross-reference Bali Zero video format research — `~/Desktop/nuzantara/research/marketing/2026-05-13-video-format-evergreen-b2b-services.md` (1.7M char/year base assumption)
21. Cross-reference Flow Veo manual — `~/Desktop/nuzantara/research/marketing/2026-05-13-flow-veo-3.1-mastery-manual.md` (voice-over integration point)
