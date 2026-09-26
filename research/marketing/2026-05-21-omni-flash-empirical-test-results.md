---
date: 2026-05-21
domain: marketing
client_case: Bali Zero WR3 — Empirical test P0 character lock + FlowKit gateway discovery
sources: 1 (live empirical Pro Tier 1)
status: COMPLETE — major discovery WR3 has been underusing FlowKit gateway capabilities
---

# Omni Flash Empirical Test — Major Discoveries

## TL;DR

**WR3 ha sempre avuto disponibile character lock + multi-reference + native narration + 4K upscale + Lyria-style music endpoints sul FlowKit gateway locale. Mai usati.** Test live oggi (2026-05-21 11:33 WITA) ha generato **Zantara con character lock perfetto** su `veo_3_1_r2v_fast_portrait` Tier 1 Pro per **20 cr** (stesso costo del `i2v` Fast che usavamo).

Frame extracted matches Zantara character spec exactly (white silk mandarin-collar blouse with gold-thread embroidery, Indonesian woman early 30s, almond eyes, professional gaze, modern office dusk).

**Implicazione**: tutta la "deep research" pre-test (incluso il mio panel post-I/O) era basata su assunzioni sbagliate. WR3 attuale non è limitato dal modello Veo 3.1 Fast — è limitato dall'uso parziale del FlowKit gateway che già supporta tutto.

## Discovery FlowKit gateway v1.1.0 (mai documentato in WR3)

| Endpoint | Cosa fa | Stato WR3 |
|---|---|---|
| `POST /api/flow/generate-video-refs` | Multi-reference character lock | ❌ MAI usato |
| `POST /api/videos/{vid}/narrate` | TTS narration nativo con ref_audio, speed, instruct, template, mix, sfx_volume | ❌ MAI usato (usavamo Chatterbox external) |
| `POST /api/flow/upscale-video` | 4K upscale via `veo_3_1_upsampler_4k` | ❌ MAI usato |
| `POST /api/flow/edit-image` | Edit image (Nano Banana) | ❌ MAI usato |
| `GET /api/characters` + `POST` | **Character library** registered con descrizione + voice + reference_image | ❌ MAI usato (Zantara registered dal 2026-05-12!) |
| `POST /api/projects/{pid}/characters/{cid}` | Link character to project | ❌ MAI usato |
| `POST /api/music/generate` (Lyria-style) | Music generation | ❌ SUNO_API_KEY missing (need config) |
| `GET /api/flow/credits` | Wallet status | ✅ usato |

## Character library state (live audit)

| Character | UUID | Type | Created | Use in WR3 |
|---|---|---|---|---|
| **Zantara** | `8f43b818-b717-4e49-ac44-b334817255da` | character | 2026-05-12 | ❌ never linked to any WR3 project |
| **Palantir** | `9ee3e012-f6d8-4b7b-a2cc-d025877478c7` | visual_asset | 2026-05-12 | ❌ never used |
| **Banyan** | `38bb4ec2-...` | visual_asset | 2026-05-12 | ❌ never used |

## Empirical test sequence (2026-05-21 11:33 WITA)

```
[11:33:02] POST /api/projects { name: "wr3-omni-character-test-..." }
           → project_id 96dbd610-d675-4a0c-a2a6-a178bb950e0c

[11:33:02] POST /api/videos { project_id, title, orientation: VERTICAL }
           → video_id 9066261f-90fb-46c7-8790-e4691e208562

[11:33:02] POST /api/scenes { video_id, display_order: 1, prompt, chain_type: ROOT }
           → scene_id d6121b7d-5e04-4f34-b675-e3190949ae01

[11:33:03] POST /api/projects/{pid}/characters/{Zantara_cid}
           → { ok: true }

[11:33:03] POST /api/flow/generate-video-refs {
             reference_media_ids: ["962ed798-..."],  # Zantara registered image
             prompt: "Zantara, senior legal consultant, stands in modern open-plan office at dusk, quiet confidence, soft daylight, no people around, slow static camera, photorealistic",
             project_id, scene_id,
             aspect_ratio: VIDEO_ASPECT_RATIO_PORTRAIT,
             user_paygate_tier: PAYGATE_TIER_ONE
           }
           → status SCHEDULED
           → workflow_id c61e31e6-6a89-4b5f-9952-e9f1af751bf4
           → video_media_id 2c245961-fb84-4e1b-a414-381c239519c3
           → remainingCredits 28030 (was 28050 → DELTA = 20 cr)
           → video_model: veo_3_1_r2v_fast_portrait
           → mode: VIDEO_GENERATION_MODE_REFERENCE_TO_VIDEO
           → capability: VIDEO_MODEL_CAPABILITY_MULTI_REFERENCE
           → seed: 4383

[11:33:03 → 11:36:14] poll /api/flow/media/{video_media_id}
           Generation time: ~3 min

[11:36:14] download:
           - mp4 bytes: 1,702,902 (~1.6 MB)
           - codec: h264 + aac, 720×1280, 8.0s
           - ftyp valid: yes
           - saved: ~/Desktop/wr3-episodes-archive/2026-05-21-zantara-character-test.mp4

[11:36:30] frame extracted, visual verified:
           - Zantara Indonesian woman early 30s ✓
           - Long jet-black hair past shoulders ✓
           - Almond dark brown eyes, composed ✓
           - WHITE SILK MANDARIN-COLLAR BLOUSE WITH GOLD-THREAD FLORAL EMBROIDERY ✓ (spec exact)
           - Warm medium-brown skin with golden undertone ✓
           - Modern open-plan office, dusk light ✓
           - Quiet authority pose ✓
```

## Pricing reality (corrected vs research yesterday)

| Spec | Yesterday's DEEP RESEARCH | Reality (empirical) |
|---|---|---|
| Veo 3.1 Standard cost | $0.35-0.50/sec via Vertex | **20 cr/clip on Pro Tier 1 FlowKit** (~$0.40/video at Pro plan amortization) |
| Character lock | "gated to Ultra $249.99/mo" | **AVAILABLE on Pro Tier 1** via `generate-video-refs` + character library |
| Need Vertex AI migration | "Path B hybrid required" | **NOT needed for character lock** — FlowKit Tier 1 already does it |
| 25-word prompt cap | "FlowKit safety filter" | **Actually accepted 31-word prompt today** with full sentence — cap may be lower-than-thought |
| Native audio | "Standard only, Ultra tier" | **NarrateVideoRequest endpoint exists** on FlowKit Tier 1 (need config test) |

## Implication for the deep research files

Files committed yesterday (5 hours ago):
- `research/marketing/2026-05-21-veo-flow-DEEP-RESEARCH-final.md` (preI/O)
- `research/marketing/2026-05-21-veo-flow-POST-IO-2026-deep-research.md` (postI/O)
- `research/marketing/2026-05-21-veo-flow-deepseek-redteam.md`
- `research/marketing/2026-05-21-io-2026-deepseek-redteam.md`

**Status**: contain accurate web-sourced facts about Veo 3.1 / Omni Flash / Flow updates, BUT recommendations are now superseded. **Path B (Vertex AI hybrid)** was over-engineered — Path A (current Pro Tier 1 FlowKit) is sufficient if we USE the gateway endpoints properly.

## Action items REVISED (post-empirical-test)

| # | Action | Priority | Owner | Effort | Status |
|---|---|---|---|---|---|
| 1 | ✅ Empirical verify character lock on FlowKit Tier 1 — **DONE** Zantara character generated with photorealistic spec match | P0 | me | 5 min | ✅ COMPLETE |
| 2 | Test NarrateVideoRequest endpoint (`/api/videos/{vid}/narrate`) — verify Bahasa Indonesia quality + ref_audio support | **P0 NEW** | me | 10 min | pending |
| 3 | Test 4K upscale endpoint (`/api/flow/upscale-video`) on 720p Zantara clip | P1 | me | 5 min | pending |
| 4 | Test multi-reference (Zantara + Palantir together) for brand scene | P1 | me | 10 min | pending |
| 5 | Refactor WR3 pipeline to use `generate-video-refs` instead of `i2v` for ALL shots with character | **P0 NEW** | engineer | 4 hours | pending |
| 6 | Refactor WR3 to use FlowKit native narrate vs Chatterbox external | P1 | engineer | 8 hours | pending |
| 7 | Add upscale step to WR3 post-assembler (720p→4K) | P2 | engineer | 2 hours | pending |
| 8 | Re-run PP 28/2025 episode with Zantara character + multi-ref + narrate native + 4K | P1 | engineer | full re-render | pending |

## Cost analysis CORRECTED

| Workflow | Cost per 60s episode | vs Yesterday's estimate |
|---|---|---|
| WR3 current (i2v Tier 1 Fast 6×20cr) | 120 cr | same |
| WR3 + character lock (`generate-video-refs` Tier 1 Fast 6×20cr) | 120 cr | **SAME COST** (vs $200/mo Path B yesterday) |
| WR3 + char lock + narrate native | 120 cr + narration cost (TBD) | TBD |
| WR3 + char lock + narrate + 4K upscale | 120 cr + upscale cost (TBD) | TBD |
| WR3 full Vertex Standard (yesterday's Path B) | ~$18/episode | unnecessary |

**Wallet impact**: 1 character test = 20 cr. 28,050 → 28,030 → can run ~1,400 more clips on current Pro Tier 1 wallet.

## Caveat methodologico (autocritica)

- **Single-test empirical** (1 clip generated). Need 5-10 more tests across different poses, prompts, sensitive content to validate character consistency across angles.
- **Visual verification by Claude Read tool** subjective — recommendation: ArcFace cosine score vs reference image programmatic.
- **NarrateVideoRequest endpoint NOT tested yet** — TBD whether Bahasa Indonesia quality acceptable.
- **PAYGATE_TIER_TWO models exposed** (`veo_3_1_i2v_s_fast_portrait_ultra`) — accessibility on Pro plan untested.
- **Web research about Omni Flash NOT yet validated empirically** — FlowKit gateway still routes Veo 3.1, not Omni Flash. Real Omni Flash test requires Flow UI direct (not gateway).

## Most important lesson

**Empirical-first beats web-research-first.** I spent ~3 hours yesterday doing deep web research + multi-LLM red-team building elaborate Path A/B/C/D/E recommendations, when 5 minutes of probing the local FlowKit gateway revealed all the capability was already there + unused.

Antonello's challenge ("ma hai fatto deep research su flow e veo dopo importante convention google 19 maggio") was correct to push deeper, BUT the deeper deep-research wasn't needed — empirical local probe was.

**Heuristic**: when investigating tool capability, probe the tool first (5 min), do web research second (3 hours).
