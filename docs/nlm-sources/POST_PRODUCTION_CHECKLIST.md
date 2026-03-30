# Post-Production Checklist — DaVinci Resolve (Free)

## Bali Zero Branded Video from NotebookLM Source

---

## Brand Reference

| Element | Value |
|---------|-------|
| Background / Shadows | `#0c0c0e` (near-black) |
| Accent / Warm Copper | `#d4845a` (Bali Zero signature copper) |
| Secondary Accent | `#e09870` (lighter copper for hover/highlights) |
| Text Primary | `#FFFFFF` (pure white) |
| Text Secondary | `#A0A0A0` (muted gray) |
| Logo | Circular black Bali Zero logo (`balizero-logo-clean.png`) |
| Font | Montserrat (headings), Inter or system sans-serif (body) |

---

## Step 0: Project Setup

1. Open DaVinci Resolve Free.
2. Create new project: `KBLI_2025_BaliZero_v1`.
3. Set project settings:
   - Timeline resolution: **1920x1080** (16:9).
   - Frame rate: **30 fps**.
   - Color science: **DaVinci YRGB**.
4. Import media:
   - NLM-generated MP4 (the raw video).
   - `balizero-logo-clean.png` (the circular black logo).
   - Montserrat font (download from Google Fonts if not installed).

---

## Step 1: Import and Place NLM Video

1. Switch to the **Edit** page.
2. Drag the NLM MP4 to **Video Track 1** (V1) on the timeline.
3. Play through the full video once. Note timestamps for:
   - The best "hook" moment (first compelling statement) — for the 15s teaser.
   - The strongest 60 seconds — for the hook cut.
   - Any NLM artifacts to trim (awkward pauses, repeated phrases, factual errors).

---

## Step 2: Color Grading (Color Page)

1. Switch to the **Color** page.
2. Select the NLM clip on the timeline.

### 2a. Lift / Gamma / Gain (Primary Wheels)

| Control | Action | Purpose |
|---------|--------|---------|
| **Lift** (shadows) | Pull toward `#0c0c0e`. Reduce R/G/B equally, target Luminance ~3-5%. | Deep, cinematic black shadows matching BZ brand. |
| **Gamma** (midtones) | Slight warm push. Add +0.02 to Red channel, +0.01 to Green. | Subtle warmth without orange-casting faces. |
| **Gain** (highlights) | Leave mostly neutral. Minor warm push if NLM video is too cool. | Clean highlights, not blown out. |

### 2b. Curves

1. Open **Custom Curves**.
2. Bring the bottom of the Luma curve up slightly (~3%) to create a subtle film lift (crushed blacks become very dark gray, not pure black — prevents banding on compressed exports).
3. On the **Hue vs Sat** curve: boost saturation around the orange/copper range (280-330 degrees) by ~10%. This makes any warm tones in the NLM video align with the BZ copper accent.

### 2c. Color Space (if needed)

If the NLM video looks flat:
1. Add a **Serial Node** (Alt+S).
2. Apply a slight S-curve on Luma (darken shadows, brighten highlights) for contrast.
3. Do NOT over-contrast — the BZ brand aesthetic is "warm depth," not high-contrast.

---

## Step 3: Intro Sequence (3-5 seconds)

### Timeline: `00:00:00 — 00:00:04`

1. Create a **Fusion Composition** at the start of the timeline (right-click > Add Fusion Composition, 4 seconds).
2. Inside Fusion:

   **Background:**
   - Add `Background` node. Color: `#0c0c0e`. Full frame.

   **Logo Reveal:**
   - Add `MediaIn` node with `balizero-logo-clean.png`.
   - Connect to a `Merge` node over the background.
   - Size the logo to approximately **20% of frame width**, centered.
   - Animate **Opacity**: 0% at frame 0, 100% at frame 45 (1.5 seconds). Use ease-in curve.
   - Animate **Scale**: 0.95 at frame 0, 1.0 at frame 45. Subtle zoom-in.

   **Tagline (optional):**
   - Add `Text+` node below the logo.
   - Text: Leave blank (no tagline in intro — keep it clean).
   - If you want a subtitle, use: the video title in Montserrat, 24pt, `#A0A0A0`, fade in at frame 60.

   **Copper accent line:**
   - Add a thin horizontal line (2px) in `#d4845a` below the logo.
   - Animate width from 0 to 200px over frames 30-60.

3. Back on the Edit page, add a **Cross Dissolve** (0.5s) transition between the intro and the NLM video.

---

## Step 4: Logo Overlay (Persistent Watermark)

1. Drag `balizero-logo-clean.png` to **Video Track 2** (V2), stretching it across the entire NLM video duration (not the intro/outro).
2. Open the **Inspector** panel for the logo clip:

| Setting | Value |
|---------|-------|
| Position X | 0.88 (bottom-right area) |
| Position Y | 0.12 (near bottom) |
| Zoom | 0.06 (small — approximately 60px on a 1080p frame) |
| Opacity | 40% (visible but not distracting) |

3. The logo should be present throughout but subtle. If it obscures important content at any point, keyframe the opacity down to 20% for that section.

---

## Step 5: Lower Third Template (Name/Title Bar)

Use this for any on-screen identification (e.g., if you add a face-cam segment later, or for section titles).

### Design Specifications

1. Create a **Fusion Composition** (5 seconds) on V3.
2. Inside Fusion:

   **Background bar:**
   - `Background` node: `#0c0c0e` with 85% opacity.
   - Crop to a rectangle: full width, 80px height, positioned at Y = 0.12 (lower portion).

   **Copper accent:**
   - 3px line at the top edge of the bar in `#d4845a`.

   **Name text:**
   - `Text+` node: Montserrat Bold, 22pt, `#FFFFFF`.
   - Position: left-aligned, 80px from left edge, vertically centered in bar.

   **Title text:**
   - `Text+` node: Inter Regular, 16pt, `#d4845a`.
   - Position: below name text, same left alignment.

   **Animation:**
   - Bar slides in from left over 0.5s (ease-out).
   - Text fades in 0.2s after bar lands.
   - Hold for 3.5 seconds.
   - Bar slides out left over 0.5s.

### When to Use

- Place at the beginning of the NLM content (after intro dissolve) to show the topic title.
- Example name: `KBLI 2025` / Example title: `What Changed and Why It Matters`

---

## Step 6: Outro Sequence (5 seconds)

### Timeline: Last 5 seconds

1. Create a **Fusion Composition** (5 seconds) at the end of the timeline.
2. Add a **Cross Dissolve** (1s) transition from the NLM video into the outro.

   **Background:**
   - `Background` node: `#0c0c0e`.

   **Logo:**
   - Centered, 25% frame width.
   - Already visible at full opacity (no animation — it was on screen via the watermark).

   **CTA Line 1:**
   - `Text+`: Montserrat Medium, 28pt, `#FFFFFF`.
   - Text: `Follow @balizero`
   - Centered, below logo.
   - Fade in at frame 15.

   **CTA Line 2:**
   - `Text+`: Inter Regular, 20pt, `#d4845a`.
   - Text: `balizero.com`
   - Centered, below CTA Line 1.
   - Fade in at frame 25.

   **Social Icons (optional):**
   - Small X/Instagram/WhatsApp icons in `#A0A0A0` below the URL.
   - Only if you have the SVG icons available; skip if not.

---

## Step 7: Captions / Subtitles

### Option A: Burn-in Captions (Recommended for X/Instagram)

1. Switch to the **Edit** page.
2. Go to **Workspace > Audio Transcription** (DaVinci Resolve 19+).
3. Click **Transcribe**. Select language: English.
4. Review the auto-generated transcript. Fix any errors (especially: "KBLI," "PT PMA," "OSS," "NIB," "BPS," Indonesian terms).
5. Go to **Timeline > Create Subtitles from Transcript**.
6. Style the subtitles:
   - Font: Inter Bold, 24pt.
   - Color: `#FFFFFF`.
   - Background: `#0c0c0e` at 70% opacity.
   - Position: center-bottom, 10% from bottom edge.
   - Max 2 lines, max 42 characters per line.
7. Verify timing — no subtitle should appear for less than 1 second or more than 5 seconds.

### Option B: SRT Export (for platforms that support separate captions)

1. After transcription, right-click the subtitle track > **Export Subtitles**.
2. Export as `.srt` format.
3. Upload alongside the video on YouTube/LinkedIn.

---

## Step 8: Export Settings

### 8a: Full Version (for YouTube, LinkedIn, Website)

1. Switch to the **Deliver** page.
2. Settings:

| Setting | Value |
|---------|-------|
| Format | MP4 |
| Codec | H.264 |
| Resolution | 1920x1080 |
| Frame Rate | 30 fps |
| Bitrate | 20,000 kbps (high quality) |
| Audio | AAC, 320 kbps, 48 kHz |
| Filename | `KBLI_2025_BaliZero_FULL_v1.mp4` |

3. Click **Add to Render Queue** > **Start Render**.

### 8b: X/Twitter Optimized

| Setting | Value |
|---------|-------|
| Format | MP4 |
| Codec | H.264 |
| Resolution | 1920x1080 |
| Frame Rate | 30 fps |
| Bitrate | 8,000 kbps (X compresses further; diminishing returns above this) |
| Max file size | 512 MB (X limit for video) |
| Max duration | 2 min 20 sec (X limit for optimal engagement) |
| Audio | AAC, 256 kbps, 48 kHz |
| Filename | `KBLI_2025_BaliZero_X_v1.mp4` |

### 8c: Instagram Reels / Stories (9:16)

If repurposing for vertical:
1. Change timeline resolution to **1080x1920** (9:16).
2. The NLM video (16:9) will need to be scaled and repositioned — either crop to center or add `#0c0c0e` bars top/bottom with text overlays.
3. Export at 8,000 kbps, max 90 seconds.

---

## Step 9: Three Cuts

### Cut 1: 15-Second Teaser

**Purpose:** X preview, Instagram story, ad creative.

1. Duplicate the timeline (right-click > Duplicate Timeline). Rename: `KBLI_2025_TEASER_15s`.
2. Find the single most compelling statement from the NLM video (identified in Step 1).
3. Trim to exactly 15 seconds around that statement.
4. Keep the intro (compressed to 2 seconds: just logo flash + copper line).
5. End with the outro CTA (compressed to 2 seconds: logo + `@balizero`).
6. Structure: `[2s intro] [11s hook content] [2s CTA]`
7. Export at X settings (8b above).
8. Filename: `KBLI_2025_BaliZero_TEASER_15s_v1.mp4`

### Cut 2: 60-Second Hook

**Purpose:** X main post, LinkedIn feed, paid promotion.

1. Duplicate the main timeline. Rename: `KBLI_2025_HOOK_60s`.
2. Select the strongest 60 seconds — prioritize:
   - The "what changed" section (numbers: 234 new codes, 1,563 total).
   - The deadline (June 18, 2026).
   - One concrete example (restaurant code 56101 or consulting 70209).
3. Keep full intro (4s) and full outro (5s).
4. Structure: `[4s intro] [51s content] [5s outro]`
5. Export at X settings.
6. Filename: `KBLI_2025_BaliZero_HOOK_60s_v1.mp4`

### Cut 3: Full Version

This is the main export from Step 8a. No additional editing needed.
Filename: `KBLI_2025_BaliZero_FULL_v1.mp4`

---

## Final QA Checklist

Before publishing any cut:

- [ ] Logo visible and correctly positioned throughout.
- [ ] Copper accent color matches `#d4845a` (not orange, not brown).
- [ ] Background blacks match `#0c0c0e` (not gray, not pure black).
- [ ] Captions are accurate — especially: KBLI, PT PMA, OSS, NIB, BPS.
- [ ] No NLM artifacts (awkward pauses, factual errors) remain.
- [ ] Audio levels consistent (-14 LUFS target for speech).
- [ ] Outro CTA is legible and correctly spelled.
- [ ] File sizes within platform limits (512 MB for X, 250 MB for Instagram).
- [ ] All three cuts exported and named correctly.

---

## File Naming Convention

```
KBLI_2025_BaliZero_{CUT}_{VERSION}.mp4

CUT:     FULL | HOOK_60s | TEASER_15s
VERSION: v1, v2, etc.

Examples:
  KBLI_2025_BaliZero_FULL_v1.mp4
  KBLI_2025_BaliZero_HOOK_60s_v1.mp4
  KBLI_2025_BaliZero_TEASER_15s_v1.mp4
```
