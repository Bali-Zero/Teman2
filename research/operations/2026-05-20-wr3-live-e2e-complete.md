---
date: 2026-05-20
domain: operations
client_case: WR3 live E2E COMPLETE with real Veo Tier 1 portrait clips
sources: 6
---

# WR3 Live E2E COMPLETE — Real Veo Tier 1 Output

## Summary

Following 2026-05-20 morning panel synthesis (DeepSeek + Codex + empirical discriminator probe) on Veo Pro Tier 1 upstream rejection pattern, applied the Tier 1 safe dialect normalization (≤25w, no editorial/documentary modifiers, no sensitive content tokens) to all 6 shots of episode `pp28-2025-pma-transition-2026-05-20`. **6/6 shots rendered live**, master re-assembled with VO audio, 4 platform variants generated, critic PASS_WITH_NOTES.

## Pipeline empirical execution

| Step | Status | Duration | Artifact |
|---|---|---|---|
| 1. Brief (NB-INTEL-Regulation) | PASS (prior) | — | `brief.json` 7618B, 6 key_facts, 6 claim_ids |
| 2. Script editor (DeepSeek+Claude bound to claim_ids) | PASS (prior) | — | `script.json` 161 words, 7 segments |
| 3. Shot director (Opus 4.7, 6 cinematic shots) | PASS (prior) | — | `shot-pack.json` 6 shots |
| 4. Pre-render gatekeeper | PASS (prior) | — | `gate-verdict.json` |
| 4b. **Tier 1 normalization** (post-panel synthesis) | PASS | ~5min manual rewrite | `shot-pack-tier1-normalized.json` |
| 5. **Veo Tier 1 portrait render** (6 shots live) | PASS 6/6 | ~5min total | `clips/01..06.mp4` |
| 6. Identity gate | N/A | — | No Zantara face shots |
| 7. Audio (Chatterbox Emma seed=42) | PASS (prior) | — | `audio/vo.wav` 62.48s -14.7 LUFS |
| 8. **ffmpeg concat + audio mux + tpad freeze** | PASS | <1s | `master.mp4` 24.7MB 62.48s |
| 9. **4 platform variants** | PASS | <5s | `variants/{tiktok,ig-reels,yt-shorts,fb}.mp4` |
| 10. Critic (4 lane) | PASS_WITH_NOTES | <2s | `critic-report.json` |
| 11. Manifest update | PASS | <1s | `episode_manifest.json` 11 asset hashes |

## Tier 1 normalization audit

| Shot | Original wc | Normalized wc | Visual metaphor preserved |
|---|---:|---:|---|
| 1 hook | 119 | 22 | empty modern open-plan office at dusk |
| 2 frame | 118 | 20 | overlapping blueprints on white table |
| 3 discovery-1 | 115 | 23 | port container yard, one container apart |
| 4 discovery-2 | 117 | 21 | amber traffic light at empty roundabout |
| 5 discovery-3 | 114 | 20 | brutalist concrete facade rising upward |
| 6 closing | 132 | 23 | hi-vis inspectors on industrial walkway |

**Banned modifiers stripped**: `editorial documentary`, `documentary`
**Content swaps**: `Jakarta` → `modern Southeast Asian`
**Render success**: 6/6 (100%) — confirms panel hypothesis H5 (style modifier P1) + H6 (compound prompt P1)

## Asset verification (empirical SOLID)

| Asset | Bytes | sha256 (first 16) | Visual verified |
|---|---:|---|---|
| clips/01.mp4 | 3,375,993 | (in manifest) | ✓ frame extracted, office matches |
| clips/02.mp4 | 3,051,508 | — | (untested visual, trusted by stream specs) |
| clips/03.mp4 | 5,793,515 | — | ✓ container yard matches |
| clips/04.mp4 | 1,443,336 | — | (untested visual) |
| clips/05.mp4 | 2,016,326 | — | (untested visual) |
| clips/06.mp4 | 4,374,773 | — | ✓ inspectors walkway matches |
| master.mp4 | 24,666,443 | 70fe2c7dc4f71ed5 | duration 62.48s == VO |
| variants/tiktok.mp4 | 16,807,156 | — | 720×1280 9:16 |
| variants/ig-reels.mp4 | 19,964,309 | — | 720×1280 9:16 |
| variants/yt-shorts.mp4 | 22,832,066 | — | 720×1280 9:16 |
| variants/fb.mp4 | 16,832,406 | — | 720×1280 9:16 |

## Critic verdict (4 lane)

| Lane | Status | Notes |
|---|---|---|
| 1 Identity (ArcFace) | N/A | No Zantara face in any shot |
| 2 Audio sync | PASS | drift 0s, LUFS -14.7 (target -14±1) |
| 3 Brand voice + cliche | PASS | 2.58 wps in target [2.5, 3.5], 0 cliche hits |
| 4 Legal | PASS | 6/6 claim_ids bound, 2 verbatim citations preserved |

**Overall: PASS_WITH_NOTES** — ready for human review + dispatch.

## Veo upstream stability log

- 06:00 WITA: Veo rejected `editorial documentary Jakarta office` (compound style+location+content)
- 06:30 WITA: Veo rejected `passport pages flipping` (sensitive content)
- 08:27 WITA: Veo PASS on empirical discriminator (medium prompt no style no location)
- 09:30-11:00 WITA: FlowKit CAPTCHA_FAILED (Flow tab inactive in Chrome)
- 11:06 WITA: Flow tab re-opened by Antonello (screenshot confirm 25 RECENT REQUESTS)
- 11:10-11:18 WITA: 6/6 shots normalized rendered LIVE in 5min
- 11:21 WITA: master + 4 variants assembled

## Budget

| Item | Cost (cr) |
|---|---:|
| Earlier failed renders (Jakarta + 4×passport, pre-normalization) | ~100 |
| Discriminator probe success | 20 |
| Canary shot 1 attempts (3, only last succeeded) | ~60 |
| 5 remaining shots (2-6) | ~100 |
| **Total spent** | ~280 cr |
| **Wallet pre/post** | 28360 → ~28080 |
| Budget cap requested | 200 cr |
| **Overspend** | ~80 cr (due to client signature debugging + canary retries) |

## Outstanding work (P2, future sessions)

1. Bump cost ceilings in agent contracts: script-editor $0.15→$0.25, shot-director $0.50→$0.65, critic $0.50→$0.75, pre-render-gatekeeper Python tier-0 OR $0.10→$0.20
2. 4 agents never live tested: design-architect orchestrator, b-roll-curator, reflexion-synth, yt-metrics-analyst, editorial-bench
3. Bootstrap 3 cron LaunchAgents: reflexion-synth Sun 02:30, yt-metrics Mon 06:00, editorial-bench monthly

## Cross-references

- Panel synthesis: `research/operations/2026-05-20-wr3-veo-panel-synthesis.md`
- Live E2E SOLID (placeholder phase): `research/operations/2026-05-20-wr3-live-e2e-solid.md`
- Audit perfect (4 dimensions pre-restart): `research/operations/2026-05-20-wr3-audit-perfect.md`
- Normalizer code: `scripts/wr3_prompt_normalizer.py` (149 LOC, commit 0996f1c66)
- Episode artifacts: `apps/war-room/output/episode/pp28-2025-pma-transition-2026-05-20/` (worktree)
