---
name: google-flow-video
description: Use when creating, iterating, or improving videos in Google Flow, including Veo prompt structure, model selection, Ingredients, voice settings, and frames-to-video chaining.
metadata:
  short-description: Google Flow video prompting workflow
---

# Skill: Google Flow — Mastering AI Video Creation

## Trigger

User wants to create, iterate, or improve a video in Google Flow.

## Access

- URL: https://labs.google/flow/
- Account: antonellosiano@gmail.com (Ultra — zero credits on Veo 3.1 Fast)

---

## The Prompt Formula

Every prompt must contain 5 parts in this order:

```
[CAMERA] + [SUBJECT] + [ACTION] + [CONTEXT] + [STYLE]
```

| Part    | What to specify                        | Example                                                                                                                                                                               |
| ------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CAMERA  | Movement + framing                     | `Slow dolly push-in, medium close-up`                                                                                                                                                 |
| SUBJECT | Full physical description — EVERY TIME | `a young Indonesian woman with long brown hair, warm skin, subtle eyeliner, small hoop earrings, thin silver necklace, wearing modern black kebaya`                                   |
| ACTION  | What happens + dialogue in quotes      | `speaks directly to camera and says: "Welcome to the Bali Zero Morning News."`                                                                                                        |
| CONTEXT | Environment, lighting, time of day     | `seated at a circular stone table in an ancient Balinese temple hall, holographic amber data floating above the table, dvarapala guardian statues with glowing eyes along both sides` |
| STYLE   | Technical look                         | `cinematic, photorealistic, warm amber lighting, shallow depth of field, 16:9`                                                                                                        |

### Golden Rules

- **NEVER abbreviate the subject.** Write the full character description in every single prompt. Veo does not remember previous prompts.
- **Concrete visuals beat abstract concepts.** "Immigration officers checking passports at Ngurah Rai airport" >> "unified immigration system"
- **Dialogue goes in quotes inside the prompt.** `She says: "Five deadlines. Zero room for error."`
- **Camera movement in the first words.** Veo prioritizes the beginning of the prompt.

---

## Model Selection

| Model               | When                                               | Credits (Ultra) | Audio |
| ------------------- | -------------------------------------------------- | --------------- | ----- |
| **Veo 3.1 Fast**    | Iterating, testing prompts                         | **Zero**        | Yes   |
| **Veo 3.1 Full**    | Final render only                                  | 5x              | Yes   |
| **Nano Banana Pro** | Generating images (character sheets, environments) | Free            | N/A   |

**Strategy:** Do ALL iterations with Fast. Only switch to Full for the final version you'll publish.

---

## Ingredients — Character Consistency

### Setup (do this once per project)

1. Settings gear → enable **Ingredients**
2. Upload reference images:
   - **1 front-facing portrait** (most important — anchors identity)
   - **1 three-quarter view** (helps with angle consistency)
   - **1 speaking/mid-sentence** (helps with mouth/expression)
   - **1 environment** (your studio background)
3. Max 4 ingredients active per generation

### Rules

- A front-facing neutral portrait is the **strongest anchor** for face consistency
- If the character drifts after 3+ clips → re-upload ingredients and regenerate
- Ingredients control identity and pose; the **prompt controls everything else** (camera, lighting, action)
- For consistent clothing: describe it identically in every prompt, don't rely on the image alone

---

## Voice Ingredients (Experimental)

### Setup

1. Settings → enable Voice Ingredients (requires Ultra)
2. Must have at least **1 Image Ingredient active** (character face)
3. Open Voice menu → hover to preview → select

### Best Voices by Use Case

| Use                      | Voice                              | Why                               |
| ------------------------ | ---------------------------------- | --------------------------------- |
| Young professional woman | **Aoede** (F, breezy, mid)         | Matches warm, approachable anchor |
| News authority           | **Alnilam** (M, firm, mid-low)     | Classic broadcast tone            |
| Documentary narrator     | **Charon** (M, informative, lower) | Deep, measured                    |
| Sophisticated woman      | **Despina** (F, smooth, mid)       | Premium feel                      |
| Senior authority         | **Gacrux** (F, mature, mid)        | For older character               |

### Critical Limitations

- Voice does **NOT carry over** when you Extend or chain clips → re-select voice for each new clip
- Indonesian accent: not available natively → add in prompt: `"She speaks English with a soft natural Indonesian accent, melodic rhythm of Bahasa Indonesia"`
- Audio quality: mono 44.1kHz — acceptable for web, enhance post with ffmpeg for broadcast

---

## Making Videos Longer Than 8 Seconds

### Method 1: Extend (quick but lower quality)

- Click "+" at end of clip → "Extend"
- Uses **Veo 2 Fast** (no audio, lower quality)
- Good for: testing sequence, previewing flow
- Bad for: final production

### Method 2: Frames-to-Video Chaining (best quality)

**This is the pro technique for full Veo 3.1 quality + audio:**

1. Generate first 8-sec clip with Veo 3.1
2. Hover over **last frame** → click "+" → **Save as Asset**
3. Start new generation → switch to **"Frames to Video"**
4. Load saved frame as **Start Frame**
5. Write NEW prompt — **repeat full character description + environment**
6. Add continuation: what happens next
7. Generate with **Veo 3.1** (not Extend)
8. "Add to Scene" → repeat from step 2
9. Each chain = +8 seconds at full quality with audio

### Method 3: Scene Builder Jump-To (for cuts between scenes)

- Click "+" → "Jump To"
- Uses Veo 3.1 full quality
- Creates a **new camera angle** or scene cut (not seamless continuation)
- Good for: switching from wide shot to close-up, changing environment

### Avoiding Drift in Long Sequences

- Copy-paste your character description verbatim into every prompt
- Re-lock ingredients before each generation
- If skin tone shifts → add specific color: "warm medium-brown skin tone"
- If clothing changes → specify exact garment in every prompt
- If lighting shifts → specify exact lighting setup every time

---

## Dual Format Production (16:9 + 9:16)

### Composition Rules for Both Formats

- **Subject at dead center** — in 9:16 crop, sides disappear
- **Strong vertical elements** — columns, trees, light beams, smoke (become hero in portrait)
- **No critical content at left/right edges** — will be cropped in vertical
- **Symmetrical compositions** work in any crop

### Workflow

1. Generate in **16:9** first (landscape — primary format)
2. For social: regenerate **same prompt** with 9:16 aspect ratio
3. Or: center-crop the 16:9 with ffmpeg (loses resolution but saves time):
   ```
   ffmpeg -i input_16x9.mp4 -vf "crop=ih*9/16:ih" output_9x16.mp4
   ```

---

## Camera Movement Reference

| Movement       | Prompt keyword              | Best for                              |
| -------------- | --------------------------- | ------------------------------------- |
| Push in slowly | `slow dolly push-in`        | Dramatic reveals, building tension    |
| Pull back      | `slow dolly pull-back`      | Establishing shots, revealing context |
| Pan across     | `slow pan left/right`       | Scanning environments                 |
| Tilt up        | `slow tilt up`              | Revealing from ground to sky          |
| Orbit          | `slow orbit around subject` | 360 showcase                          |
| Static         | `locked-off static shot`    | Dialogue, anchor shots                |
| Handheld       | `subtle handheld movement`  | Documentary feel                      |
| Crane down     | `crane shot descending`     | Grand entrances                       |
| Tracking       | `tracking shot following`   | Movement, walking                     |

**Tip:** Start prompt with camera movement — Veo prioritizes early words.

---

## Style Modifiers That Improve Quality

### Photorealism

```
photorealistic, cinematic, shallow depth of field, film grain,
anamorphic lens, 8K detail, natural skin texture
```

### Lighting

```
warm amber key light from the left, soft fill from above,
dramatic side-lighting, golden hour, volumetric light rays,
practical lighting from candles and screens
```

### Mood

```
atmospheric, moody, dramatic shadows, high contrast,
intimate, epic, serene, urgent
```

### What to Avoid in Prompts

- "high quality" or "beautiful" — too vague, adds nothing
- Multiple conflicting styles — pick one mood
- Overly long prompts (>200 words) — Veo loses focus
- Negative prompts ("don't show X") — Veo doesn't handle negation well

---

## Image Generation (for Ingredients)

Use Nano Banana Pro / Imagen 4 inside Flow:

1. Type prompt in text box (same as video, but generates image)
2. Best for: character sheets, environment references, style boards
3. Generated images → immediately usable as Ingredients
4. **Lasso tool:** click area of generated image → type modification → instant edit

### Character Sheet Prompt Template

```
Portrait of [full character description]. [Pose: front-facing /
three-quarter / profile / speaking]. [Lighting]. Portrait
photography, shallow depth of field, neutral background.
```

### Environment Prompt Template

```
Interior/exterior of [environment description]. No people.
[Lighting and time of day]. [Materials and textures].
Architectural photography, centered composition that works
in both 16:9 and 9:16 crop. [Style].
```

---

## Troubleshooting

| Problem                              | Fix                                                                  |
| ------------------------------------ | -------------------------------------------------------------------- |
| Character face changes between clips | Re-upload face ingredient, add skin tone + feature details to prompt |
| Clothing changes                     | Specify exact garment (color, cut, material) in every prompt         |
| Voice sounds different on next clip  | Re-select Voice Ingredient — it doesn't persist                      |
| Video stuck generating >5 min        | Cancel and regenerate — likely stuck                                 |
| Environment looks different          | Upload environment as Ingredient image, describe in prompt too       |
| Weird artifacts / glitches           | Regenerate — AI video is stochastic, some generations fail           |
| Extend has no audio                  | Extend uses Veo 2 — use Frames-to-Video instead                      |
| 9:16 crops out important elements    | Redesign composition with center-dominant layout                     |
| Prompt too long, Veo ignores parts   | Split into shorter clips, one concept per prompt                     |
| Lips don't match dialogue            | Known Veo limitation — lip sync is approximate, not perfect          |

---

## Quick Reference Card

```
START NEW PROJECT:
  Flow → New Project → Settings → Veo 3.1 Fast → Ingredients ON

GENERATE CLIP:
  Write 5-part prompt → Generate → Pick best → Add to Scene

EXTEND (pro method):
  Last frame → Save as Asset → Frames to Video → Full prompt again

EXPORT:
  Scene Builder → Play preview → Download (1080p or 4K)

GOLDEN RULE:
  Every prompt = full character + full environment + camera + action + style
  Never assume Veo remembers anything from the previous clip.
```
