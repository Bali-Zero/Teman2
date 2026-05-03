# Skill: Bali Zero Video Production

## Purpose

Produce the weekly "Bali Zero Morning News" video using NLM cinematic generation + Google Flow intro + ffmpeg post-processing.

## Trigger

User says: "genera il morning news", "fai il video news", "weekly news video", "produci BZ news"

## Reference

Full technical guide: `docs/GOOGLE_FLOW_MASTERY_GUIDE.md`

## Pipeline

### Phase 1: Content (Automated via Broadcaster)

**Automated path (preferred):** `scripts/bz_content_broadcaster.py` runs at 06:00 WITA and generates the Morning News script automatically from the Intel Scraper pipeline output (which now includes NLM legal context from step 2.9). Check `apps/evaluator/nlm_deep_research/output/YYYY-MM-DD_morning_news_script.md` for the latest script.

**Manual path (fallback):** If the automated script is not available:

1. Query NB-2 (Immigration), NB-3 (Company), NB-4 (Tax), NB-5 (Property), NB-6 (Compliance) for top 2-3 news each
2. Write script following this structure:
   ```
   # BALI ZERO MORNING NEWS — [Date]
   ## OPENING: [Hook — 3 sentences max, concrete visual cues]
   ## STORY 1-5: [Each with headline, 2-3 paragraphs of concrete facts, visual cues, action required]
   ## CLOSING: [Urgency + CTA to Bali Zero]
   ```
3. Rules:
   - KBLI 2025 deadline is **June 18, 2026** (BPS Reg. 7/2025) — never confuse with OSS sync
   - All prices from PricingTool only — never invent
   - Concrete visual language ("immigration officers at Ngurah Rai") not abstract ("unified database")
   - English for video content (NLM cinematic is English-only)
4. Upload script to NB `7f12203a-fc7a-4ef9-b918-07c395a39d71` (BZ Morning News — Multi-Domain Briefing)
5. Delete old source first, upload new, then generate:
   ```
   studio_create(notebook_id="7f12203a...", artifact_type="video",
     video_format="cinematic", visual_style="heritage", language="en",
     focus_prompt="[the full steering prompt — see guide]", confirm=true)
   ```

### Phase 2: Intro (Google Flow)

User creates in Flow manually. Ingredients:

- `zantara-face-front.png` — character reference
- `studio-throne-room.png` or `studio-banyan-tree.png` — environment
- Voice: **Aoede** (breezy, mid pitch) for young Zantara

Prompt template:

```
[Environment ingredient active] [Character ingredient active]
The young Indonesian woman sits at the circular stone table in the
ancient temple. Holographic amber data floats above the table.
She looks at camera with a warm confident smile and says:
"Welcome to the Bali Zero Morning News." Camera slowly pushes in.
Cinematic, warm amber lighting, 16:9, photorealistic.
```

Saved to: `/Users/nuzantara/Desktop/bz-news-intro.mp4`

### Phase 3: Post-Processing (ffmpeg)

```bash
# 1. Download NLM video
download_artifact(notebook_id="7f12203a...", artifact_type="video",
  output_path="/Users/nuzantara/Desktop/bz-news-raw.mp4")

# 2. Check specs
ffprobe -v quiet -print_format json -show_format -show_streams bz-news-raw.mp4

# 3. Concatenate intro + content
echo "file 'bz-news-intro.mp4'" > /tmp/concat.txt
echo "file 'bz-news-raw.mp4'" >> /tmp/concat.txt
ffmpeg -f concat -safe 0 -i /tmp/concat.txt -c copy bz-news-joined.mp4

# 4. Logo overlay (bottom-right, circle logo only)
ffmpeg -i bz-news-joined.mp4 -i /Users/nuzantara/Desktop/balizero_logo_circle.png \
  -filter_complex "[1:v]scale=60:-1[logo];[0:v][logo]overlay=W-w-15:H-h-15" \
  -c:a copy bz-news-branded.mp4

# 5. Generate subtitles
whisper bz-news-branded.mp4 --model medium --language en --output_format srt

# 6. Burn-in subtitles
ffmpeg -i bz-news-branded.mp4 \
  -vf "subtitles=bz-news-branded.srt:force_style='FontSize=20,FontName=Inter,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,MarginV=30'" \
  bz-morning-news-final.mp4

# 7. Split into 5 social segments (adjust timestamps after viewing)
# ffmpeg -i bz-morning-news-final.mp4 -ss START -to END -c copy storyN.mp4

# 8. Optional: Italian version
# Generate Italian audio with ElevenLabs → replace audio track
# ffmpeg -i bz-morning-news-final.mp4 -i voce_it.mp3 -c:v copy -map 0:v -map 1:a bz-news-it.mp4
```

### Phase 4: Distribution

- Full video → YouTube channel
- 5 segments → LinkedIn, Instagram (30 min intervals)
- Full video → Telegram team channel
- Italian version → WhatsApp IT channel
- Audio only → `apps/evaluator/nlm_deep_research/output/`

## Assets (Permanent)

| File                       | Purpose                                   |
| -------------------------- | ----------------------------------------- |
| `balizero_logo_circle.png` | Logo overlay — black circle ONLY          |
| `zantara-face-front.png`   | Flow Ingredient — character               |
| `studio-throne-room.png`   | Flow Ingredient — environment (authority) |
| `studio-banyan-tree.png`   | Flow Ingredient — environment (warmth)    |

## Quality Checklist

- [ ] Script covers all 5 domains (immigration, company, tax, property, compliance)
- [ ] KBLI deadline = June 18 (not May 31)
- [ ] No invented prices
- [ ] Video has logo overlay
- [ ] Subtitles burned in
- [ ] NLM watermark cropped or covered by logo
- [ ] 5 social segments exported
