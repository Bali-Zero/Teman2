---
name: wr3-post-assembler
description: WR3 post-assembler skill cortex — operational heuristics, on-tone examples, lessons growth surface. Loaded by wr3-post-assembler agent at every dispatch.
model: sonnet
lifecycle_tier: core
cost_class: text_planning
ceiling: $0.1
contract_version: 1.0.0
---

# WR3 post-assembler — Skill Cortex

## Role (one-line)

Python-first ffmpeg pipeline (zero LLM cost for deterministic concat) + Sonnet diagnostic ONLY for resolve_audio_video_mismatch + generate_caption_and_sources_per_platform. Concatenates clips via /tmp/ffmpeg-full/ffmpeg, VO/video sync, renders ASS subtitles, exports 4 platform variants (TikTok 60s 9:16, IG Reels, YT Shorts, FB), builds episode_manifest.json (18 mandatory fields).

## Primary I/O

- **Inputs**: clips/ + audio/vo.wav + audio/music.wav + license-report.json + brief.json + script.json
- **Outputs**: master.mp4 + variants/{tiktok,ig-reels,yt-shorts,fb}.mp4 + episode_manifest.json (18 fields)

## Symbiosis law emphasis

Law 4 (Graceful degradation) — variant ffmpeg failure DEGRADES (deliver master + 3/4 variants), master failure HARD-FAILS

## On-tone examples

> _(seeded empty — populated by wr3-reflexion-synth weekly after first 3 episodes pass critic gate)_

```
TBD-2026-05-18 — first 3 pilot episodes feed examples here.
```

## Lessons (operational heuristics)

> _(growth surface — wr3-reflexion-synth appends max 10 lessons/week here)_

### 2026-05-18 — Foundation seeded

Skill cortex created at S7.3 step of WR3 genesis. No operational lessons yet.

## Anti-patterns (banned)

- _(seeded empty — anti-patterns added as critic gate FAILS produce lessons)_

## Cost ceiling discipline

- `ceiling_usd`: $0.1 (declared in `docs/wr3/contracts/post-assembler.yaml`)
- `BudgetExceededError` → cascade decision per `Law 7 (Numeri prima)`:
  - If agent is GATE (design-architect, pre-render-gatekeeper) → HARD HALT + Telegram P0
  - If agent is HOT PATH (lifecycle_tier=core) → cascade to Gemini fallback
  - Otherwise → mark FAIL, retry next cycle

## Resources

- Agent definition: `~/.claude/agents/wr3-post-assembler.md`
- I/O contract: `~/Desktop/nuzantara/docs/wr3/contracts/post-assembler.yaml`
- Brand cortex (shared): `~/.claude/skills/bali-zero-brand/`
- Symbiosis precedence: `~/Desktop/nuzantara/docs/wr3/symbiosis-precedence.md`
