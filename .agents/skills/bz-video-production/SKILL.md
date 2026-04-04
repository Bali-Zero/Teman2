# Skill: Bali Zero Video Production (Gemini Agent)

## Purpose

Assist in producing the weekly "Bali Zero Morning News" video. Gemini's role: generate intro clips in Google Flow, create character/environment images, and assist with content research.

## When to Use

- User asks to create the BZ Morning News intro in Flow
- User needs character consistency images for Zantara avatar
- User needs environment images for studio backgrounds
- User needs to iterate on Flow prompt engineering

## Google Flow Workflow

### Access

URL: https://labs.google/flow/
Account: antonellosiano@gmail.com (Ultra tier)

### Ingredients Library

These permanent assets must be loaded as Ingredients in every Flow session:

- **Zantara face** (front portrait) — young Indonesian woman, long brown hair, warm skin, subtle eyeliner, thin silver necklace, black top
- **Throne Room** — Balinese temple hall, dvarapala guardians with amber eyes, circular stone table with holographic data, oculus to starry sky, candles
- **Banyan Tree** — massive Banyan with golden data-cable roots, stone platform, canang sari offerings, amber glow

### Prompt Formula

```
[Camera] + [Subject with full description] + [Action/Dialogue] + [Environment] + [Style]
```

Always include in EVERY prompt:

- Character: "young Indonesian woman, late 20s, long brown hair, warm skin, subtle eyeliner, small hoop earrings, thin silver necklace, modern black outfit"
- Camera: specify movement explicitly
- Dialogue: in quotes within the prompt
- Style: "cinematic, photorealistic, warm amber lighting, 16:9"

### Models to Use

- **Veo 3.1 Fast**: for iteration (zero credits on Ultra)
- **Veo 3.1 Full**: for final render
- **Nano Banana Pro / Imagen 4**: for generating reference images (free)

### Scene Builder for Longer Clips

1. Generate 8-sec clip → "Add to Scene"
2. Hover last frame → save as asset
3. Use saved frame as START in new "Frames to Video"
4. REPEAT full character description in new prompt
5. Chain until desired length
6. Export as single video

### Voice

- Use **Aoede** (female, breezy, mid pitch) for Zantara
- Add accent guidance in prompt: "She speaks with a natural soft Indonesian English accent"
- Voice does NOT carry over on Extend — re-apply each clip

### Dual Format (16:9 + 9:16)

- Design all compositions with **center-dominant** focal point
- Use **vertical elements** (columns, roots, light beams) that work in both crops
- Generate 16:9 first → regenerate same prompt in 9:16 for social

## Content Pipeline Integration

### NLM Notebooks (source data)

| NB   | Domain        | Query for news                               |
| ---- | ------------- | -------------------------------------------- |
| NB-2 | Immigration   | "top 2-3 visa/immigration changes this week" |
| NB-3 | Company Setup | "PT PMA / KBLI / OSS changes this week"      |
| NB-4 | Tax           | "tax deadlines and compliance changes"       |
| NB-5 | Property      | "property regulation changes for foreigners" |
| NB-6 | Compliance    | "licensing and compliance changes"           |

### Script Rules

- KBLI 2025 deadline: **June 18, 2026** (BPS Reg. 7/2025)
- Prices: ONLY from PricingTool — never invent
- Language: English for video (NLM cinematic English-only)
- Visual language: concrete ("officers at airport") not abstract ("unified system")

## Post-Processing (handled by Claude Code)

After Flow generates intro → Claude Code handles:

- ffmpeg concatenation (intro + NLM content)
- Logo overlay
- Whisper subtitles
- Social media splits

## Key Reference

Full guide: `docs/GOOGLE_FLOW_MASTERY_GUIDE.md`
