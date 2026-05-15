---
name: google-flow-video
description: Generate AI video assets via Google Labs Flow + Veo 3.1 on Antonello's AI Ultra plan ($249.99/mo, 25,000 credits/month). Use when the user asks to create video shorts/reels/B-roll/explainers/testimonials for Bali Zero, ZANTARA, or any editorial deliverable. Skill is operational — not academic.
trigger_keywords: ["flow", "veo", "video", "reel", "short", "ai video", "google flow", "veo 3.1", "google ai ultra", "labs.google/flow"]
version: 2.0
updated: 2026-05-13
supersedes: SKILL.v1-pre-2026-05-13.bak (April 2026, contained false "Veo 3.1 Fast = Zero credits" claim, predated Veo 3.1 2025-10-15 release)
companion_manual: research/marketing/2026-05-13-flow-veo-3.1-mastery-manual.md
authority_sources:
  - https://blog.google/technology/ai/veo-updates-flow (Veo 3.1 release 2025-10-15)
  - https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1 (Google ufficiale prompt guide)
  - https://deepmind.google/models/veo/prompt-guide (DeepMind prompt guide)
  - https://support.google.com/flow/answer/16526234 (credits & pricing)
  - https://support.google.com/flow/answer/16353334 (Ingredients, voice, multi-output)
  - https://support.google.com/flow/answer/16352836 (audio limits)
  - https://support.google.com/flow/answer/16935718 (Scene Builder)
  - https://support.google.com/flow/answer/17069754 (keyboard shortcuts)
---

# Flow + Veo 3.1 Operational Skill (v2)

**Account**: `antonellosiano@gmail.com` · Google AI Ultra ($249.99/mo) · 25,000 credits/month
**Flow URL**: https://labs.google/flow
**Model release**: Veo 3.1 GA 2025-10-15 (replaces Veo 3 May 2025)
**Do NOT confuse**: Google Flow Music is a separate product (audio for artists, partnership with Believe). This skill is **Veo video generation inside Flow** only.

---

## 1. Reality check — models & credits in Flow UI (Ultra)

> ⚠️ Credit costs in Flow UI are **per-generation**, NOT per-second. 8s clip = 4s clip = 6s clip = same cost at same tier. The Vertex AI / Gemini API is a different billing model — do not conflate.

| Tier | Credits / generation | Output res | Native audio | Best use |
|---|---|---|---|---|
| **Veo 3.1 Lite** | 5 | 720p (1080p upscale 0 cr) | may vary, weak | Storyboarding, B-roll exploration, animatics |
| **Veo 3.1 Fast** | 10 | 1080p | yes (full) | Workhorse — daily iteration, dialog drafts |
| **Veo 3.1 Quality** | 100 | 1080p (4K upscale +50 cr) | yes (best) | Hero/locked shots, client-facing |
| Lite [Lower Priority] | **0** (Ultra freebie) | 720p | may vary | Off-peak bulk exploration |
| Fast [Lower Priority] | **0** (Ultra freebie) | 1080p | yes | Off-peak bulk drafts |
| 4K upscale | 50 (flat) | — | — | Hero shots only |

**Multiplier rules**:
- 1× / 2× / 3× / 4× = number of parallel variants returned per generation (cost = base × N).
- **Quality is always charged at 2× minimum** in Flow UI (200 cr/gen) — Google forces variant selection on Quality tier.
- Aspect ratio: 16:9 + 9:16 both natively supported, **same cost**.
- Duration: 4s / 6s / 8s all priced the same in a given tier — generate 8s by default.

**Failed generations should not charge credits** (Google policy, support.google.com/flow/answer/16526234). Low-audio-quality fails may refund.

---

## 2. Cost calculator — 3 strategies for 25k monthly budget

> Per-Brief estimate: 6-clip episode (1 hero + 4 supporting + 1 CTA closer) ≈ **650 credits/Brief** → **~36 Briefs/month theoretical**, **15–20 Briefs/month realistic** after retries.

| Strategy | Quality (100 cr) | Fast (10 cr) | Lite (5 cr) | Total cr | Output minutes | Best for |
|---|---|---|---|---|---|---|
| **Hero-heavy** | 200 | 300 | 200 | **24,000** | ~58 min | Brand serial opener, premium client decks |
| **Volume-heavy** | 50 | 1,500 | 500 | **22,500** | ~280 min | SEO library, B-roll, IG/TikTok daily |
| **Balanced (recommended)** | 150 | 700 | 400 | **24,000** | ~210 min | Editorial pipeline Bali Zero default |

**Retry math** (subtract from yield):
- Simple B-roll: ~90% first-pass good → 10% retry
- Talking-head 8s monologue: ~70-75% → +20% credit penalty
- Multi-character dialog: ~55-65% → +35% penalty
- Text-in-scene (legal docs readable): ~40-50% → +50% penalty (USE OVERLAYS IN POST INSTEAD)
- Indonesian-accented English dialog: ~30-40% → +60% penalty

> **Bali Zero takeaway**: never burn Quality credits on text-in-scene legal docs — generate clean B-roll, add overlay in CapCut/Premiere.

---

## 3. Prompt formula — 5-part Google official

**Canonical order** (Google's recommended hierarchy, front-loaded tokens get heaviest attention):

```
[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]
```

| Part | Examples |
|---|---|
| Cinematography | `medium close-up, 35mm, slow dolly-in`, `static locked-off`, `low-angle tracking`, `FPV drone dive` |
| Subject | Full description: age range, ethnicity, wardrobe, hair, expression. Never abbreviate. `Veronika, mid-30s Indonesian woman in white kebaya, hair tied back, calm professional expression` |
| Action | One verb, concrete. `walks toward camera`, `places stamp on document`, `looks directly into lens and says...` |
| Context | Specific location + time of day + props. `Bali Zero office Sanur, late afternoon, wooden desk, KITAS document visible` |
| Style & Ambiance | Lighting source + mood + audio cue. `warm key light from window left, soft tropical shadows, ambient air-con hum, distant scooter` |

**Length sweet spot**: 3–6 sentences, 100–150 words. Longer prompts dilute attention; shorter prompts let the model hallucinate.

**Golden rules**:
1. Camera intent FIRST when shot must feel directed.
2. Concrete > abstract: "warm tungsten from window" beats "beautiful lighting".
3. Source the light: every shot should name the key light direction + temperature.
4. Force verbs: model needs grammatical verbs, not gerund clouds.
5. Material cues: "linen fabric", "weathered teak wood", "wet pavement" — surfaces carry physics.
6. Avoid exact counts ("three people" often → 2 or 4); use "a small group" or single subjects.

**Don't use**:
- ❌ "high quality", "beautiful", "epic", "cinematic" alone (filler, no information)
- ❌ Negative-as-don't ("don't show a man" — model often shows a man anyway; use Negative Prompt field)
- ❌ Multiple conflicting style anchors ("cyberpunk + film noir + Studio Ghibli")
- ❌ Named celebrity/politician/public-figure likeness (auto-blocked + account flag risk)
- ❌ Branded IP / copyrighted logos (memorization-check refusal)

**"Anamorphic" alone doesn't work** — spell out: `oval bokeh, horizontal lens flare, compressed background, 2.39:1 aspect`.

---

## 4. Timestamp Prompting (Google Cloud — advanced)

Generate multi-shot narrative in **one 8s generation** using inline timecodes:

```
[00:00-00:02] Wide establishing shot, Ngurah Rai airport arrivals hall, morning daylight,
   travelers walking, ambient announcement audio.
[00:02-00:04] Cut to medium shot, Indonesian immigration officer at counter, calm
   professional, stamping a passport, "Welcome to Indonesia" said softly.
[00:04-00:06] Close-up on KITAS card placed on counter, hand of officer sliding it forward.
[00:06-00:08] Wide pull-out, applicant smiling, picks up KITAS, walks toward exit.
   Soft uplifting music swell.
```

**Trade-off**: can't retry one segment — entire 8s regenerates. Use for hero shots only after 2–3 Fast iterations confirm composition.

---

## 5. Audio — dialog, SFX, ambient, music

**Dialog syntax** (load-bearing — double-quotes mandatory):

```
A woman says, "We have to leave now." (no subtitles)
```

- Suffix `(no subtitles)` prevents the model from rendering on-screen captions (a known bug per support.google.com/flow/answer/16352836).
- Use the `Dialogue:` keyword as alternative.

**Audio lanes** (separate inside prompt):

```
Dialogue: A woman says, "Welcome to Bali Zero." (no subtitles)
SFX: Soft keyboard typing, paper rustle as document slides forward.
Ambient: Tropical air-con hum, distant gamelan music from neighboring shop.
Music: Subtle uplifting orchestral pad, slow swell, no melody.
```

**Hard rules for lip-sync** (≥90% success):
- **1 speaker per clip** — multi-speaker dialog fails ~50% even on Quality
- **≤5 seconds of spoken audio** per 8s clip — silence pre/post helps registration
- **Close-up or medium shot**, mouth clearly visible — wide shots desync
- Booster phrase: `"...clearly enunciates each word..."`
- For multi-character conversations use **shot/reverse-shot** (separate clips per speaker)

**Known audio bugs**:
- 20–40ms drift on long clips (cut before/after hard consonants)
- Voice timbre can sound robotic — generate 3–4 variants, pick best
- **No native Indonesian-accent voice** — voice references partially work but accent reliability dropped in Veo 3.1 vs Veo 3 (Reddit creator reports)
- Voice does NOT persist cross-Extend reliably

**Workaround for Indonesian-accented English** (Bali Zero spokespersons):

```
Voice: warm Indonesian-accented English, gentle lilt, slight emphasis on initial consonants,
       conversational pace, no exaggeration.
The woman, Veronika, says, "Indonesian tax compliance is simpler when you have
   a local partner." She clearly enunciates each word.
```

**Voice Ingredients** (experimental, Ultra-only — works with Ingredients generations, summoned via `@Voice`). Recommended voice names (creator-empirical):
- Aoede (F, warm, professional) — Veronika spokesperson default
- Alnilam (M, broadcast) — news anchor reads
- Charon (M, documentary) — sober explainer narration
- Despina (F, smooth, premium) — luxury property B-roll VO
- Gacrux (F, mature, authority) — Adit (Director-level testimonials)

---

## 6. Ingredients — character/object/style consistency

**Setup per character**:
1. Generate 4 portrait references using Nano Banana Pro / Imagen 4 inside Flow:
   - Front-facing neutral (eye level)
   - 3/4 angle
   - Speaking (mouth slightly open, hand gesture mid-action)
   - Full environment shot (subject in setting)
2. Plain background (white/light gray) — busy backgrounds confuse the model
3. Save as Ingredient with **unique made-up name** (community trick: `Zantara-Veronika`, `Zantara-Surya`) — more reliable temporal mapping than "the woman"

**Generation rules**:
- **Max 3 Ingredients active per generation** (character + outfit + environment is the typical stack)
- Reference each Ingredient **BY NAME** in the prompt: `Veronika from Ingredient 1, wearing the kebaya from Ingredient 2`
- Drift accumulates after ~3 chained clips → re-upload fresh portrait every 3rd clip
- **Verify model selector says Veo 3.1, not Veo 2** before clicking Generate (community-reported silent fallback on heavy days)

**Voice Ingredient**: 1 voice reference allowed, only works with full Ingredients generation, summoned via `@Voice` in prompt.

---

## 7. Beyond 8 seconds — 3 methods

| Method | How | Quality | Cost (Fast tier) | Best for |
|---|---|---|---|---|
| **Frames-to-Video chaining** | Generate clip → save last frame → use as start frame of next 8s clip | 🟢 Best (each segment fresh full-Veo with audio) | 10 cr/chain (Fast) or 100 cr/chain (Quality) | 30s–2min narrative, dialog scenes |
| **Flow Extend** | Click "Extend" on existing clip → adds +7s from final frame | 🟡 Decays: 1–3 chains OK, 4–5 subtle drift, 6–10 noticeable, 11–20 visible | 10 cr/extend | Continuous unbroken motion, establishing pans |
| **Jump-To / Scene Builder** | Place clips in timeline, use cinematic cuts | 🟢 Reliable on Quality, 🟡 unstable on Fast | Per-clip base cost | Multi-shot narratives, shot/reverse-shot |

**Max theoretical with Extend**: 8s base + 20 extends × 7s = **148s single shot** (then export, re-upload last frame, start new chain — loophole for 5min+).

### Pro workflow — Frames-to-Video chain (7 steps)

1. Write **scene bible** first: cast names, wardrobe, lighting palette, location, voice tone, action beats. Reuse verbatim in every clip prompt.
2. Generate clip 1 with full Subject + Context (Quality if hero, Fast otherwise).
3. In Flow, save last frame as image asset.
4. Lock 1 Ingredient as face anchor (e.g., `Zantara-Veronika` front portrait) — keeps identity across cuts.
5. Generate clip 2: prompt = clip 1's full Subject + new Action + re-stated environment/lighting/palette.
6. **Hand-over-hand prompting**: the last visible state at end of clip N becomes the opening state of clip N+1. Mirror exactly.
7. Test on Lite first (5 cr) before committing to Quality (100–200 cr).

**Continuity rules**:
- Copy-paste full Subject description verbatim across clips
- Re-state environment + lighting + color palette in every prompt
- Lock face anchor Ingredient
- Voice references don't persist — re-cast in each prompt

---

## 8. Camera controls — UI buttons vs prompt language

Flow has UI sliders for Pan/Tilt/Zoom; **text prompting yields higher precision** (Reddit creator consensus). Prompt language wins.

### Empirically reliable cinematography (production-ready)

| Move | Prompt syntax | Reliability |
|---|---|---|
| Slow dolly push-in | `slow dolly push-in over 6 seconds, locked subject` | 🟢 Hero-grade |
| Locked-off static | `static locked-off camera, no movement` OR community hack `"from the perspective of a rock that does not move"` | 🟢 Safest for dialog |
| Orbit | `slow 90-degree arc around subject` (works best with isolated subjects on plain background) | 🟢 |
| Whip pan | `fast whip pan left to right, motion blur` | 🟡 |
| Rack focus | `rack focus from foreground to background, shallow depth of field` | 🟡 |
| Gimbal glide | `smooth gimbal glide forward, low angle` | 🟢 |
| FPV drone dive | `FPV drone dive, fast descent, dynamic angle` | 🟢 |
| Dolly zoom (Vertigo) | `dolly zoom on subject, background compresses` | 🟡 |

### Vocabulary table — 4 categories

| Movement | Composition | Lens | Lighting |
|---|---|---|---|
| dolly, tracking, crane, gimbal, POV, FPV drone, whip pan, push-in, pull-out, orbit, rack focus | wide / medium / close-up / extreme close-up, low-angle, high-angle, Dutch tilt, over-the-shoulder, locked-off | 35mm, 50mm, 85mm, macro, wide-angle, anamorphic (spell out: oval bokeh, horizontal flare, 2.39:1), shallow depth of field, deep focus | key light, fill light, rim light, golden hour, blue hour, tungsten warm, daylight cool, neon, chiaroscuro, soft diffusion |

---

## 9. Negative prompting + Remove tool

**Phrase positively first** — Veo responds better to "smooth motion" than "no jittery motion". Place negative directives at the **end** of prompt. Escalate to positive reframe if artifact recurs.

**Editorial-safe negative stack** (paste in Negative Prompt field):

```
no extra fingers, no warped text, no motion smear, no jump cuts, no watermarks,
no AI artifacts, no morphed limbs, no double faces, consistent anatomy,
no shaky camera, no subtitles, no on-screen text overlays
```

**Remove tool caveat**: Flow's object-remove inpainting uses **Veo 2 internally**, **NOT Veo 3.1**, and produces **NO audio**. Use only for static-shot cleanup, never for hero shots.

---

## 10. Aspect 16:9 + 9:16

**Native support both**, same cost. Generate vertical natively when composition matters — don't crop.

| Format | When | Composition rule |
|---|---|---|
| 16:9 (1920×1080) | YouTube, web, broadcast, hero pieces | Subject occupies center 1/3 horizontally; landscape framing |
| 9:16 (1080×1920) | Instagram Reels, TikTok, Shorts, WhatsApp Status | Subject dead center; vertical hero (full body or close-up); no critical content within 80px of edges |

**Dual-format strategy** (subject dead-center technique):
1. Frame subject **dead center** horizontally and vertically
2. Use **vertical hero elements** (standing portraits, doorways, tree trunks)
3. Keep critical content (text overlays, key gestures) **away from edges**
4. Symmetrical composition works any crop

**Workflow options**:
- **Option A (cleaner)**: Generate 16:9 hero, then regenerate 9:16 separately (2× cost, but native composition each format)
- **Option B (fast)**: ffmpeg center-crop:
  ```bash
  ffmpeg -i in.mp4 -vf "scale=-2:1920,crop=1080:1920" -c:a copy out_9x16.mp4
  ```
- **Option C (padded)**:
  ```bash
  ffmpeg -i in.mp4 -vf "scale=1080:-2,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" -c:a copy out_9x16_pad.mp4
  ```

---

## 11. Throughput + queue strategy

**Wall-clock generation time** (creator-empirical, off-peak):
- Veo 3.1 Lite: ~1 min
- Veo 3.1 Fast: ~1 min 13 s (vs ~2:41 on Veo 3 — measurable speed bump)
- Veo 3.1 Quality (1×): ~2–3 min
- Quality (2× forced): ~3–4 min
- Quality (4×): ~5–6 min
- 4K upscale: ~3–5 min additional

**Lower-priority queue** (Ultra-only freebie): Lite + Fast at 0 cr but 5–20 min wait, off-peak hours best. Use for overnight bulk B-roll harvest.

**Daily workflow**:
| Phase | Tier | Multiplier | Purpose |
|---|---|---|---|
| Composition drafting | Lite | 1× | Cheap iteration, find framing |
| Refinement | Fast | 1× | Lock blocking + audio |
| Hero render | Quality | 2× (forced) | Final shot, pick best variant |
| Bulk harvest | Lite [Lower Priority] | 1× | Free overnight B-roll |
| 4K hero only | Quality + upscale | — | +50 cr flat |

---

## 12. Commercial use + SynthID + UU PDP

### Allowed (Ultra commercial license)
- ✅ Marketing assets for Bali Zero / Nuzantara editorial
- ✅ Generic visuals (Bali landscapes, generic professional spokespersons, abstract concepts)
- ✅ Client/staff likenesses **with written consent**
- ✅ Client portals, ads, B2B decks, social posts

### Forbidden — hard restrictions
- ❌ Real-person likeness without consent (auto-blocked + account flag)
- ❌ Indonesian government officials named likeness (UU PDP + KUHP defamation risk)
- ❌ Copyrighted IP / brand logos (Disney, Apple, etc. — memorization-check refusal)
- ❌ Named minors
- ❌ Violence, hate speech, sexually explicit content
- ❌ Removing SynthID watermark (TOS violation + YouTube/IG de-rank algorithm + EU AI Act + Indonesia UU PDP)

### SynthID — invisible watermark
- **Every Veo 3.1 frame** carries DeepMind SynthID (forensic, undetectable to humans)
- **Visible "veo" bottom-right** watermark: present on non-Ultra Flow; **Ultra exempt** in Flow UI
- API/Vertex outputs: no visible watermark; SynthID invariant
- Removing SynthID = TOS violation **and**:
  - Platform algorithm de-rank (YouTube, Instagram, TikTok)
  - EU AI Act non-compliance for synthetic media disclosure
  - Indonesia UU PDP / UU ITE exposure on misleading content

### Required Bali Zero disclosure
1. Disclaimer in caption/credits: **"AI video assets generated via Veo 3.1 (Google Labs Flow)"**
2. Audit log per asset in `~/Desktop/nuzantara/research/marketing/flow-asset-log.csv` (date, prompt, tier, cost, consent status, publication URL)
3. For client/staff likeness: signed written consent stored in `~/Desktop/nuzantara/research/marketing/consent/<name>-<date>.pdf`

> **Bali Zero verdict matrix**:
> | Use case | Status |
> |---|---|
> | Generic Bali B-roll, abstract explainers, property exteriors | ✅ ship |
> | Veronika/Adit/Surya named likeness | ⚠️ written consent required |
> | Named clients in testimonials | ⚠️ written consent + draft review |
> | Indonesian government officials named | ❌ never |

---

## 13. 10 prompt templates — ready copy-paste for Bali Zero

### T1 — FAQ Visa Anchor (Veronika kebaya, Quality 8s, C1 explainer)
```
Medium close-up, 35mm lens, locked-off static camera. Veronika from Ingredient 1
(mid-30s Indonesian woman, hair tied back, white silk kebaya, calm professional
expression). She looks directly into the lens and says, "The C1 visa replaces the
old B211A. It's valid for sixty days, single-entry, tourism only." She clearly
enunciates each word. (no subtitles) Bali Zero office Sanur, late afternoon,
warm tungsten key light from window left, soft tropical shadow on background
teak wall. Ambient air-con hum, distant scooter passing.
```
Tier: Quality 2× (200 cr). Aspect: 9:16. Voice: @Aoede.

### T2 — Regulatory News Flash (timestamp 4-segment SPT extension)
```
[00:00-00:02] Wide establishing shot, Indonesian tax office Jakarta exterior,
   morning, busy with civil servants walking. Indonesian flag fluttering.
[00:02-00:04] Cut to medium shot, news anchor at desk (generic professional
   man, dark suit, neutral tie), holding a printed document marked
   "KEP-71/PJ/2026". He says, "Tax deadline extended."
[00:04-00:06] Close-up insert on Indonesian calendar, May 31 circled in red ink.
[00:06-00:08] Pull-out to wide, anchor smiles, "Plan accordingly." Logo lower-third.
SFX: subtle paper rustle, soft news-room ambient.
```
Tier: Quality 2× (200 cr). Aspect: 16:9.

### T3 — Property B-roll (drone pull-back Balinese villa, golden hour)
```
Aerial drone pull-back, slow ascent. A traditional Balinese villa with thatched
alang-alang roof, infinity pool reflecting golden hour sky, rice paddies
extending to volcanic mountain on horizon. Coconut palms gently swaying.
Golden hour key light, warm amber tones, long shadows. Ambient: gentle breeze,
distant gamelan music, water lapping pool edge. No people in frame.
```
Tier: Fast 1× (10 cr). Aspect: 16:9. Use Lite [Lower Priority] (0 cr) overnight for bulk.

### T4 — Tax Deadline Countdown (Surya, locked-off, "Eighteen days...")
```
Medium shot, 50mm, locked-off static. Surya from Ingredient 1 (early-40s
Indonesian man, navy batik shirt, glasses, serious expression). Indoor Bali
Zero office, soft daylight from large window camera-left, teak desk in
foreground with a calendar visible. He looks directly at camera and says,
"Eighteen days. After May thirty-first, the SPT extension closes." He clearly
enunciates each word. (no subtitles) Ambient: air-con, soft typing in background.
```
Tier: Quality 2× (200 cr). Aspect: 9:16. Voice: @Charon.

### T5 — Client Testimonial Frame (slow orbit, written consent required)
```
Slow 90-degree orbit, smooth gimbal glide, medium shot. [Client name from
Ingredient 1, with written consent on file] seated on rattan chair, Bali villa
terrace background, tropical plants soft-focused behind. Warm afternoon
sunlight, dappled through bamboo blinds. She says, "Bali Zero made my PT PMA
setup feel effortless." She clearly enunciates each word. (no subtitles)
Ambient: distant ocean, light wind through palms.
```
Tier: Quality 2× (200 cr). **Requires signed consent PDF** before generation.

### T6 — KBLI Explainer (B-roll no dialog, macro lens, hand adjusts page)
```
Macro shot, rack focus from foreground to background. A hand (Indonesian skin
tone) carefully turns the page of a printed KBLI 2020 booklet on a wooden
desk. The page reveals "63122 — Portal web". A pencil rests beside the booklet.
Soft natural daylight from above. No dialog. SFX: paper rustle, faint pencil
roll, ambient quiet office.
```
Tier: Fast 1× (10 cr). Aspect: 16:9 or 9:16.

### T7 — Before/After Metaphor (Frames-to-Video chain)
```
CLIP 1 (start frame upload): Empty Bali Zero office, dawn, dust motes in light
beam from window, no furniture, bare floor. Slow dolly push-in over 6 seconds.

CLIP 2 (last frame of Clip 1 → start frame, generate continuation): Same room
now appointed — teak desk, two chairs, plants, calendar on wall, sunlight now
midday warm. Camera continues slow push-in. Ambient: soft typing begins.

Continuity: identical room dimensions, identical window position, identical
floor texture. Lighting evolves from cool dawn to warm midday.
```
Tier: 2 × Fast (20 cr) or 1× Quality + 1× Fast for hero. Method: Frames-to-Video.

### T8 — Myth-Bust Hook (Reels 9:16, Veronika, "Nominee is not protection")
```
Tight medium close-up, 50mm, locked-off. Veronika from Ingredient 1, neutral
expression turning to slight concern, white kebaya, plain background. She
looks directly into lens and says, "Nominee structures are illegal. They are
not protection." She clearly enunciates each word. (no subtitles) Pause
0.5 seconds. Soft amber light, single key from camera-left. Ambient: silent
office, no music. SFX: subtle paper turn at clip end.
```
Tier: Quality 2× (200 cr). Aspect: 9:16. Voice: @Aoede.

### T9 — News Brief Intro (anchor + lower-third holographic amber data)
```
Wide-to-medium tracking, slow dolly. News anchor (generic mid-30s Indonesian
woman, navy blazer, neutral expression) seated at modern desk. Behind her,
a large holographic display showing data charts in warm amber tones — text
"PERMENKUMHAM 22/2023" partially visible (rendered as overlay, not in-scene
text). Studio lighting cool daylight from above, warm rim from holographic
display. She says, "Tonight, the new immigration framework." She clearly
enunciates each word. (no subtitles) Music: subtle uplifting orchestral pad.
```
Tier: Quality 2× (200 cr). Aspect: 16:9. **Add real lower-third graphic in post** (NLE) — do NOT trust Veo to render legible text.

### T10 — Elegant CTA Closer (logo card on stone surface, candle flame)
```
Static locked-off, extreme close-up, 85mm. A weathered stone temple surface,
warm candle flame flickering frame-right out of focus. In frame center, a
small embossed card with Bali Zero logo (rendered as Ingredient image asset,
NOT in-scene text). Slow soft breeze causes candle flame to dance, casting
amber light on stone texture. Audio: distant gamelan, soft wind, no dialog.
Hold for 4 seconds, then very slow fade.
```
Tier: Quality 1× (100 cr if not forced 2×). Aspect: 9:16. **Pair with WhatsApp + email CTA in post-production overlay** per Article 6.6.1 elegant-close pattern.

---

## 14. Quick Reference Card — pseudo-code

### START NEW PROJECT
```
1. Open labs.google/flow → "New Project"
2. Settings → model selector → verify "Veo 3.1" (NOT Veo 2)
3. Upload Ingredients (max 3 active): character portrait + wardrobe + environment
4. Aspect ratio: 16:9 OR 9:16 (native, same cost)
5. Duration: 8s (default — same cost as 4s/6s)
```

### GENERATE CLIP
```
1. Write prompt: [Cinematography] + [Subject verbatim] + [Action] + [Context] + [Style & Ambiance]
2. Negative prompt: paste editorial-safe stack (§9)
3. Tier:
   - Drafting → Lite (5 cr)
   - Iteration → Fast (10 cr)
   - Hero → Quality 2× (200 cr forced)
4. Click Generate → wait 1–4 min
5. Pick best variant from 1×/2×/4× outputs
```

### EXTEND TO 30s+ PRO (Frames-to-Video chain)
```
1. Generate clip 1 with full Subject + Context
2. Save last frame as image asset
3. Use last frame as start frame of clip 2
4. Re-state Subject + environment + lighting verbatim in clip 2 prompt
5. Lock 1 Ingredient as face anchor
6. Repeat for clip 3, 4, ... (max 4 chained reliably before drift)
7. Assemble in Scene Builder timeline OR export and edit in NLE
```

### EXPORT
```
1. Asset menu → Download
2. Formats: MP4 (default), GIF (270p only)
3. Rename: <project>_<shot>_<version>_<tier>.mp4
4. Log entry: research/marketing/flow-asset-log.csv
5. Disclosure: caption must include "AI video assets generated via Veo 3.1"
```

### DECISION TREE — which tier for which task

```
Brand serial / hero / client-facing  → Quality 2× (200 cr)
Daily editorial / dialog drafts       → Fast 1× (10 cr)
B-roll / property / abstract          → Lite 1× (5 cr) OR Lite [LP] (0 cr overnight)
Multi-variant casting                 → Fast 4× (40 cr) — pick best of 4
30s+ narrative                        → Frames-to-Video chain of Fast (10 cr × N)
Continuous unbroken motion (>8s)      → Extend (10 cr × N, decay by chain 4+)
Final 4K hero                         → Quality 2× + 4K upscale (200 + 50 cr)
```

### OPEN QUESTIONS — empirical pending (sample sprint TODO)

- [ ] Lite tier audio fidelity — does "may-vary" mean degraded or skipped?
- [ ] Extend tier cost — is it base tier per extend or discounted?
- [ ] Remove tool current status — still Veo 2 under hood as of 2026-05?
- [ ] Indonesian-accent English Quality vs Fast — 10-clip side-by-side study
- [ ] Voice Ingredient stability across Frames-to-Video chain (does @Voice persist?)
- [ ] Quality forced-2× — can it be overridden by support request?

> Resolve via **BVCL Sampling Sprint** plan (`docs/superpowers/plans/2026-05-13-bvcl-sampling-sprint.md`). 12 sample clips × 4 archetypes ≈ 600–800 credits.

---

## 15. Editorial pipeline — Bali Zero integration

**Where Flow fits**:
- WR2 (carousel pipeline) → static IG carousels
- **Flow + Veo 3.1** → IG Reels, TikTok, YouTube Shorts, WhatsApp video CTAs
- Companion editorial template: prompt T1–T10 above

**Workflow**:
1. **Brief** → wr2-brief-interpreter or manual (subject, archetype, voice register)
2. **Storyboard** → 6-clip episode plan (1 hero + 4 supporting + 1 CTA closer)
3. **Generate** → Flow, tier-mixed per Balanced strategy (§2)
4. **Edit** → Premiere / DaVinci / CapCut — color match, captions in post, music swap if needed
5. **Disclosure** → caption + asset log entry + consent PDF (if applicable)
6. **Publish** → IG/TikTok/YouTube → metrics in 7 days via wr2-ig-metrics-analyst

**Asset naming convention**:
```
<YYYY-MM-DD>_<topic-slug>_<shot-N>_<tier>_<variant>.mp4
2026-05-13_c1-visa-explainer_hero-01_quality_v3.mp4
```

**Asset log location**:
```
~/Desktop/nuzantara/research/marketing/flow-asset-log.csv
```

CSV columns: `date, project, shot, tier, cost_credits, aspect, duration_s, prompt_hash, consent_status, publication_url, retry_count, notes`.

---

## 16. References (authority chain)

**Google-official primary sources**:
- Veo 3.1 release announcement: https://blog.google/technology/ai/veo-updates-flow (2025-10-15)
- Ultimate prompting guide for Veo 3.1: https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1
- DeepMind Veo prompt guide: https://deepmind.google/models/veo/prompt-guide
- Flow credits & pricing: https://support.google.com/flow/answer/16526234
- Flow generation settings (Ingredients, voice, multi-output): https://support.google.com/flow/answer/16353334
- Audio limits & speech: https://support.google.com/flow/answer/16352836
- Scene Builder & saving frames: https://support.google.com/flow/answer/16935718
- Asset export & sharing: https://support.google.com/flow/answer/16935308
- Keyboard shortcuts: https://support.google.com/flow/answer/17069754
- Image-model help (Nano Banana Pro / Imagen 4): https://support.google.com/flow/answer/16729550
- Vertex AI Veo 3.1 generate spec: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/veo/3-1-generate

**Empirical / creator-community (label as anecdotal)**:
- Curious Refuge review: https://curiousrefuge.com/blog/veo-31-quality-ai-video-generator-review
- Sider field guide (cinematic control): https://sider.ai/blog/ai-tools/best-prompt-techniques-for-veo-3_1-video-output-a-field-guide-to-cinematic-control
- Veo3Gen Shot Card workflow: https://www.veo3gen.app/blog/veo-31-in-google-flow-a-beginner-workflow-to-build-a-1530s-scene-from-shot-cards
- DataCamp complete guide: https://www.datacamp.com/tutorial/veo-3-1-complete-guide-with-examples
- Reddit r/VEO3 lip-sync thread: https://www.reddit.com/r/VEO3/comments/1rkf538/lip_sync_looks_cartoonish_teeth_way_too_visible/
- Reddit r/VEO3 "sucks" critique: https://www.reddit.com/r/VEO3/comments/1o8omm8/veo_31_sucks/
- Reddit r/Bard accent regression: https://www.reddit.com/r/Bard/comments/1o7ftjk/veo_31_is_a_disappoinment/

**Companion deep manual** (audit trail, ≥30 inline citations):
- `research/marketing/2026-05-13-flow-veo-3.1-mastery-manual.md`

**Backup v1** (archeology, do not edit):
- `skills/google-flow-video/SKILL.v1-pre-2026-05-13.bak`
- `.agents/skills/google-flow-video/SKILL.v1-pre-2026-05-13.bak`
