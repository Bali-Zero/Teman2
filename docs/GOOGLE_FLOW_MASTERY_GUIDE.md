# Google Flow Mastery Guide — Bali Zero Production Reference

> Compiled from 20+ sources: Google Blog, Google Help, Tom's Guide, CineD, Skywork, Veo3AI,
> DigiWebInsight, ToolFolio, VidAU, Veo3Gen, user reports (TikTok/Facebook), DataCamp,
> NinjaAI, SimpliLearn, GeekyGadgets, ChaseJarvis. Cross-verified April 2026.

---

## 1. What Is Flow

Google Flow is an AI video production workspace at [labs.google/flow](https://labs.google/flow/).
It combines Veo 3.1 (video), Imagen 4 / Nano Banana Pro (images), and Gemini (prompt assistance)
in a unified editor with timeline, scene builder, and asset management.

**Access:**

- Free tier: limited credits, daily refresh
- Google AI Pro ($19.99/mo): full Veo 3.1, more credits
- Google AI Ultra ($249.99/mo): all features + Veo 3.1 Fast (zero credits), Ingredients, Voice Ingredients, experimental features, 4K upscale

**Our account:** `antonellosiano@gmail.com` (Ultra)

---

## 2. Models & What Each Does

| Model                          | What It Does                                             | Speed   | Credits           | Audio        |
| ------------------------------ | -------------------------------------------------------- | ------- | ----------------- | ------------ |
| **Veo 3**                      | Text/Frames → 8sec video                                 | ~2 min  | 5x base           | Yes (native) |
| **Veo 3.1**                    | Text/Frames/Ingredients → 8sec video, better consistency | ~2 min  | 5x base           | Yes          |
| **Veo 3.1 Fast**               | Same as 3.1 but faster                                   | ~30 sec | **Zero on Ultra** | Yes          |
| **Imagen 4 / Nano Banana Pro** | Text → Image (up to 2K)                                  | ~10 sec | Free on Ultra     | N/A          |

**Key:** Use Veo 3.1 Fast for iteration (free), Veo 3.1 Full for final renders.

---

## 3. The 5-Part Prompt Formula

From Google Cloud's official guide:

```
[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]
```

**Example:**

```
[Slow dolly push-in] + [a young Indonesian woman in a black kebaya] +
[speaks directly to camera with calm authority] + [seated at a stone table
in an ancient Balinese temple with holographic data floating above] +
[cinematic, warm amber lighting, shallow depth of field, photorealistic, 16:9]
```

### Camera Movements (available as dropdown or in prompt)

| Movement         | Effect                         | Use For                    |
| ---------------- | ------------------------------ | -------------------------- |
| `dolly in/out`   | Camera moves toward/away       | Dramatic reveals           |
| `pan left/right` | Camera rotates horizontally    | Establishing shots         |
| `tilt up/down`   | Camera rotates vertically      | Reveals from ground to sky |
| `zoom in/out`    | Lens zoom                      | Emphasizing details        |
| `orbit`          | Camera circles subject         | 360° showcases             |
| `handheld`       | Slight shake, documentary feel | Authenticity               |
| `static`         | No movement                    | Anchor shots, dialogue     |
| `crane/aerial`   | High to low or sweeping        | Epic establishing shots    |

### Style Modifiers That Work

```
photorealistic, cinematic, shallow depth of field, warm lighting,
golden hour, dramatic shadows, documentary style, broadcast quality,
8K resolution, film grain, anamorphic lens, soft bokeh background
```

---

## 4. Ingredients System (Key Feature)

### Image Ingredients

- Upload up to **4 reference images** per generation
- Types: Character face, Object, Style reference, Environment
- Veo uses them to maintain visual consistency

### Best Practices for Character Ingredients

1. **Front-facing neutral portrait** is the most reliable base reference
2. **Generate 2-3 poses** (front, three-quarter, profile) for better consistency
3. **Repeat the full character description** in every prompt — don't assume Veo remembers
4. **Lock reference images** in the Ingredients panel before extending
5. **Include clothing, lighting, age, expression** in every prompt, not just the first

### Voice Ingredients (Experimental, Ultra only)

- Requires at least 1 Image Ingredient (character) active
- Select from preset voice menu (hover to preview)
- Add dialogue in prompt: `She says: "Welcome to Bali Zero Morning News."`
- Voice does NOT carry over with Extend — must re-apply each clip
- Can add tone guidance in prompt: "warm, measured, with Indonesian accent"

### Available Voices (April 2026)

| Name       | Gender | Style       | Pitch   | Best For                   |
| ---------- | ------ | ----------- | ------- | -------------------------- |
| Achernar   | F      | soft        | high    | Gentle narration           |
| Aoede      | F      | breezy      | mid     | Young professional, warm   |
| Autonoe    | F      | bright      | mid     | Energetic content          |
| Callirrhoe | F      | easy-going  | mid     | Casual                     |
| Despina    | F      | smooth      | mid     | Sophisticated              |
| Erinome    | F      | clear       | mid     | Professional, neutral      |
| Gacrux     | F      | mature      | mid     | Senior authority           |
| Achird     | M      | friendly    | mid     | Approachable               |
| Algenib    | M      | gravelly    | low     | Drama, intensity           |
| Algieba    | M      | easy-going  | mid-low | Casual professional        |
| Alnilam    | M      | firm        | mid-low | **News anchor, authority** |
| Charon     | M      | informative | lower   | Documentary                |
| Enceladus  | M      | breathy     | lower   | Intimate                   |
| Fenrir     | M      | excitable   | younger | Energetic, social media    |
| Iapetus    | M      | clear       | mid-low | Data, precision            |

---

## 5. Video Creation Methods

### Method A: Text to Video

1. New Project → prompt box
2. Settings gear → select model (Veo 3.1 Fast recommended for iteration)
3. Write prompt using 5-part formula
4. Click generate → 2 options appear → pick best
5. "Add to Scene" to send to timeline

### Method B: Frames to Video

1. Dropdown next to "Text to Video" → "Frames to Video"
2. Click "+" → upload or generate start frame
3. Optionally add end frame
4. Write prompt describing what happens between frames
5. Generate → Flow creates seamless transition video

### Method C: Ingredients to Video

1. Settings → enable Ingredients
2. Upload up to 4 reference images (character, environment, style, object)
3. Write prompt — Veo uses ingredients for consistency
4. For character: front-facing photo is the strongest anchor

---

## 6. Scene Builder — Creating Longer Videos

### The 8-Second Limit

Individual Veo clips are max 8 seconds. Scene Builder chains them.

### Step-by-Step Scene Building

1. Generate your first clip → "Add to Scene"
2. In Scene Builder timeline, click **"+"** at clip's end
3. Choose:
   - **Extend**: continues same shot seamlessly (uses Veo 2 Fast — lower quality, no audio)
   - **Jump To**: new camera angle/cut (uses Veo 3.1 — full quality + audio)
4. For Extend: system auto-populates your prompt. Add micro-adjustments ("camera slowly tilts up")
5. For Jump To: write new prompt but REPEAT character description fully
6. Generate → pick best → repeat

### The Pro Technique: Frames-to-Video Chaining (Full Veo 3.1 Quality)

**This is the secret for maintaining Veo 3.1 quality + audio in long videos:**

1. Generate first 8-sec clip with Veo 3.1
2. Hover over last frame → click "+" → save as asset
3. Use that saved frame as START frame in new "Frames to Video" generation
4. Write continuation prompt — **repeat ALL character details**
5. Generate with Veo 3.1 (not Veo 2 Extend)
6. Repeat → seamless 16, 24, 32, 60+ second scenes with full audio

### Avoiding Consistency Drift

- Repeat character description (age, clothing, lighting, skin tone) in EVERY prompt
- Re-select character ingredient references when extending
- Use identical camera language across clips
- If drift occurs: delete clip, regenerate with more specific prompt

---

## 7. Image Generation

Flow now includes Nano Banana Pro (Imagen) built-in:

- Free image generation for Ultra users
- Use for: creating character sheets, environment references, style boards
- Generated images can immediately become Ingredients for video
- Lasso tool: select area of image → modify with natural language prompt

---

## 8. Export & Download

| Format    | Resolution | Notes                         |
| --------- | ---------- | ----------------------------- |
| GIF       | Low        | For previews                  |
| 720p      | 1280x720   | Default                       |
| **1080p** | 1920x1080  | Upscaled — **recommended**    |
| **4K**    | 3840x2160  | Upscaled — available on Ultra |

- Aspect ratios: **16:9** (landscape), **9:16** (vertical/Stories/Shorts), **1:1** (square)
- **Scene Builder resets when you leave** — but clips saved as Project
- Download individual clips or full assembled sequence

---

## 9. Audio Generation

- Audio generated natively with Veo 3 and 3.1 (not Veo 2)
- Control via prompt: "the sound of morning birds", "subtle ambient music", "she says: ..."
- Dialogue: include spoken text in quotes within the prompt
- Veo 3.1 quality audio = AAC, typically mono 44.1kHz
- For better audio: generate video → extract audio → enhance with external tools → re-merge with ffmpeg

---

## 10. Credit System

| Tier                | Credits  | Refresh | Veo 3.1 Fast     |
| ------------------- | -------- | ------- | ---------------- |
| Free                | Limited  | Daily   | No               |
| Pro ($19.99)        | Standard | Daily   | Uses credits     |
| **Ultra ($249.99)** | Highest  | Daily   | **Zero credits** |

- Veo 3/3.1 Full: 5x credit cost vs Fast
- Imagen/Nano Banana: free for all tiers
- Strategy: **iterate with Fast (free), render final with Full**

---

## 11. Whisk Migration (April 30, 2026)

Whisk and ImageFX are moving into Flow by April 30, 2026:

- All Whisk projects/assets transfer to Flow library
- Style transfer, image remix → now in Flow
- Opt-in to transfer starting March 2026

---

## 12. Limitations & Known Issues

| Limitation                                   | Workaround                                                    |
| -------------------------------------------- | ------------------------------------------------------------- |
| Max 8 sec per clip                           | Scene Builder + Frames-to-Video chaining                      |
| Extend uses Veo 2 (no audio, lower quality)  | Use Frames-to-Video with Veo 3.1 instead                      |
| Character drift after 3-4 extensions         | Repeat full description in every prompt + re-lock ingredients |
| Voice Ingredients don't carry over on Extend | Re-apply voice ingredient for each new clip                   |
| No logo overlay in Flow                      | Post-process with ffmpeg                                      |
| No subtitle/caption tools                    | Whisper + ffmpeg post-process                                 |
| No video trimming precision                  | Export → ffmpeg or DaVinci Resolve                            |
| Scene Builder resets on exit                 | Clips saved in project, reassemble on return                  |
| English only for voice                       | ElevenLabs for other languages → ffmpeg audio replace         |
| Rendering inconsistency (2 min to hours)     | Regenerate if >5 min — likely stuck                           |

---

## 13. Post-Processing Pipeline (Bali Zero)

```bash
# 1. Logo overlay (persistent across all video)
ffmpeg -i video.mp4 -i logo.png \
  -filter_complex "[1:v]scale=80:-1[logo];[0:v][logo]overlay=W-w-20:H-h-20" \
  -c:a copy branded.mp4

# 2. Generate subtitles
whisper video.mp4 --model medium --language en --output_format srt

# 3. Burn-in subtitles
ffmpeg -i branded.mp4 \
  -vf "subtitles=video.srt:force_style='FontSize=20,FontName=Inter,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,MarginV=30'" \
  final.mp4

# 4. Split into segments
ffmpeg -i final.mp4 -ss 00:00:00 -to 00:00:38 -c copy story1.mp4

# 5. Replace audio (for Italian version)
ffmpeg -i final.mp4 -i voce_italiana.mp3 -c:v copy -map 0:v:0 -map 1:a:0 final_it.mp4

# 6. Upscale 720p to 1080p
ffmpeg -i input_720p.mp4 -vf "scale=1920:1080:flags=lanczos" -c:a copy output_1080p.mp4

# 7. Concatenate intro + content + outro
ffmpeg -f concat -i filelist.txt -c copy full_video.mp4
# filelist.txt:
# file 'intro.mp4'
# file 'content.mp4'
# file 'outro.mp4'
```

---

## 14. Bali Zero Specific Workflow

### Weekly Morning News Production

1. **Monday AM**: NLM query all NB (2-6) → extract top news → write script
2. **Monday**: Upload script to NLM NB → generate cinematic video (NLM)
3. **Monday**: Generate intro clip in Flow (Zantara + Throne Room)
4. **Monday**: Generate 5 title cards in Flow (one per story)
5. **Tuesday AM**: ffmpeg assemble: intro + [title + segment]×5 + outro
6. **Tuesday**: Whisper subtitles → burn-in → logo overlay
7. **Tuesday**: Split into 5 social clips → schedule on social
8. **Tuesday**: Full video → YouTube
9. **Optional**: ElevenLabs Italian voice → ffmpeg replace → WhatsApp IT channel

### Ingredient Library (Permanent)

- `zantara-face-front.png` — front portrait
- `zantara-face-3quarter.png` — three-quarter view
- `zantara-speaking.png` — mid-sentence expression
- `studio-throne-room.png` — Sala del Trono environment
- `studio-banyan-tree.png` — Banyan Tree environment
- `balizero-logo-circle.png` — logo (only black circle)

---

_Last updated: 2026-04-03_
_Maintained by: Bali Zero AI Team_
