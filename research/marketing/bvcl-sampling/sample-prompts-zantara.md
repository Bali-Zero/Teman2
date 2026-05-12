# BVCL Zantara Sampling — 4 archetype × 3 tier prompts

> **Anchor**: Zantara (synthetic, inspired by Riri) — recurring across all editorial BVCL content.
> **Brand bar**: tecnologicamente sacro — Balinese ritual aesthetic + obsidian/gold/silver/amber palette + Palantir-style sphere with Bali Zero logo as recurring authority object.
> **Tier protocol**: ogni prompt si genera 3 volte (Lite 5cr, Fast 10cr, Quality 100cr ×2 multiplier) per A/B tier-comparison. Tutti gli altri parametri identici (8s, 16:9 landscape salvo AR3 9:16, 1× multiplier salvo Quality 2×).
> **Ingredients caricati** (3 max per generazione, Veo 3.1 limit): `zantara-portrait.jpeg` + `palantir-sphere-bali-zero.jpeg` + `banyan-tree.jpeg` per AR1+AR2. AR3+AR4 senza character anchor (no Ingredients).

---

## AR1 — FAQ Anchor with Resolution Arc (talking-head Quality, Ingredients required)

**Hypothesis tested**: lip-sync precision + character consistency + narrative tension→resolution in 8s + audio scene (tense string → crystalline chime → warm silence).

**This is Antonello's reference prompt verbatim** (slightly tightened to fit Veo 3.1 150-word target while preserving every story beat).

```
Slow dolly push-in, medium shot, 16:9. Zantara, a young Indonesian woman late
30s, long straight black hair, warm medium-brown skin, subtle black eyeliner,
small hoop earrings, thin gold chain. She sits at a polished dark stone altar
with Balinese floral carvings, at the base of a massive ancient Banyan tree.
She wears a structured white silk blouse with mandarin collar and delicate
gold floral embroidery, white silk trousers. On the altar rests a perfectly
smooth matte black obsidian sphere — the Bali Zero logo glows from inside
with an uneasy red shimmer. A small ornate golden key rests beside it. The
aerial roots glow in alternating waves — warm gold one side, cold silver the
other, the tree torn between opportunity and danger. Canang sari offerings
with lit candles on the ground.

Zantara looks directly into camera with a concerned protective expression and
says, "Beautiful villa. Five years prison. Know the difference." Her voice
warm, sharpening at "five years prison," softening at "know the difference,"
soft natural Indonesian English accent.

After speaking, her right hand picks up the golden key, holds it one second,
deliberately touches it to the apex of the sphere. At contact the sphere
shifts from uneasy red to steady gold glow. All aerial roots synchronize to
warm gold. Danger resolves into safety. She holds a protective steady gaze.
No smile but warmth in eyes. Complete stillness.

SFX: wind through ancient leaves. Tense string-like tone during speech.
Resonant crystalline chime when key touches sphere — like a lock opening.
Then warm ambient silence. Cinematic, photorealistic, warm golden amber with
cold silver contrast, shallow depth of field, magical realism. (no subtitles)
```

**Ingredients to load** (3): `zantara-portrait.jpeg` (face anchor) + `palantir-sphere-bali-zero.jpeg` + `banyan-tree.jpeg`. Reference "Zantara" by name in prompt verbatim.

**Word count**: ~245 words — slightly over the 150 target but the multi-beat narrative arc demands it. Acceptable per Google docs ("up to ~200 words before Veo loses focus"). If Lite struggles, this confirms prompt-length sensitivity per tier.

---

## AR2 — Regulatory Authority Pronouncement (anchor + Palantir, NO Banyan, NO key)

**Hypothesis tested**: Ingredients consistency holds when ONE element is removed from reference set (no Banyan), outfit/location variation while keeping anchor identity.

```
Locked-off static medium shot, 16:9. Zantara, same Indonesian woman late 30s,
long straight black hair, warm medium-brown skin, subtle eyeliner. This time
she wears a deep charcoal silk kebaya with antique silver Balinese embroidery
at the collar and cuffs, her hair pulled back simply, a single small silver
earring. She sits at a clean obsidian desk in a minimalist temple-inspired
office. Behind her, weathered teak columns frame a window opening to soft
overcast sky. On the desk sits the matte black obsidian sphere with the Bali
Zero logo glowing inside — this time in a steady cool blue, calm and
authoritative. No tension.

Zantara looks directly into camera, hands folded on the desk, and says
clearly, "Permenkumham twenty-two of twenty-twenty-three. C1 replaces B211A.
Sixty days. One extension." Her tone is measured, precise, archival. Each
visa code spoken with deliberate clarity. Soft natural Indonesian English
accent.

She does not move after speaking. Quiet authority. The sphere's blue glow
gently pulses once — like a heartbeat acknowledging the rule.

SFX: distant temple bell at the very start. Quiet office ambient — paper,
soft air. A single low resonant tone when the sphere pulses. Photorealistic,
cinematic, cool overcast daylight from the window, archival neutral palette
with the lone blue sphere as focal point, shallow depth of field. (no
subtitles)
```

**Ingredients to load** (2): `zantara-portrait.jpeg` + `palantir-sphere-bali-zero.jpeg`. NO Banyan reference.

---

## AR3 — Pure B-roll Property Authority (no character, no Ingredients, 9:16 portrait)

**Hypothesis tested**: pure B-roll (no character anchor) generation quality at all 3 tiers + portrait format viability for Reels/Shorts.

```
Slow drone pull-back, 9:16 vertical portrait format. A traditional Balinese
villa with thatched alang-alang roof, carved teak doors, infinity pool in
foreground reflecting morning sky. The villa sits among emerald rice paddies,
distant Mount Batur on the horizon. In the center of the pool, half-submerged
on a stone pedestal, rests a single matte black obsidian sphere with the
Bali Zero logo glowing softly inside in steady warm amber — like a quiet
guardian watching the land.

Golden hour, soft volumetric god rays through palm fronds. Gentle wind moves
the paddies in slow waves. A single white heron flies through frame far in
the distance.

SFX: gentle dawn wind, distant rooster crowing once, a barely-audible
gamelan note. Photorealistic, cinematic, shallow depth of field, 24mm wide
angle with shallow foreground, 9:16. Composition centered for vertical
crop — sphere is the focal point at the lower-third golden ratio. (no
subtitles)
```

**Ingredients**: none — pure text-to-video stress test.
**Note**: this is the ONLY 9:16 in the sample set. If Veo handles 9:16 well here, we know vertical-first content is viable; if it crops/distorts, we adopt 16:9-first + ffmpeg reframe workflow.

---

## AR4 — Document Close-Up with Text-in-Scene (regulatory citation stress test)

**Hypothesis tested**: Veo 3.1 text-rendering on Indonesian regulatory documents — does ANY tier render legible Indonesian text, or do we ALWAYS composite text in post?

```
Slow tilt up, 16:9. A clean obsidian desk in a quiet temple-inspired office,
mid-morning soft window light from the left. On the desk: a printed Indonesian
regulatory document with the heading "PERMENKUMHAM 22/2023" clearly visible at
the top in clean black sans-serif type, with subheading "Visa dan Izin Tinggal".
Beside it sits the matte black obsidian sphere with the Bali Zero logo glowing
in soft amber inside — a quiet authority watching over the document.

A hand reaches into frame from the right and gently rests one fingertip on the
heading "PERMENKUMHAM 22/2023" — confirming, anchoring. The hand is calm,
deliberate. The sphere's amber glow brightens almost imperceptibly at the
touch.

SFX: paper rustle as the hand approaches. A faint resonant hum from the
sphere. Quiet office ambient. Photorealistic, macro lens detail on paper
texture, shallow depth of field, the regulation heading in sharp focus, the
sphere softly bokeh'd behind. (no subtitles)
```

**Ingredients**: 1 only (`palantir-sphere-bali-zero.jpeg`) — text on document is the test, sphere is brand-anchor.
**Critical observation**: read the rendered text in the output clip carefully. Is "PERMENKUMHAM 22/2023" legible at each tier? If even Quality fails, AR4 is dead at the Veo layer — Bali Zero will need to composite document text in post-production for all regulatory content.

---

## Generation order recommendation

Per credit-efficiency + risk-management:

1. **AR3 Lite (5cr)** — pure B-roll, lowest risk, fastest signal on baseline tier
2. **AR3 Fast (10cr)** — same prompt, comparison
3. **AR3 Quality (100cr)** — same prompt, comparison — total AR3 = 115cr
4. **AR4 Lite/Fast/Quality** — text-in-scene test (~115cr) — second-easiest
5. **AR2 Lite/Fast/Quality** — anchor Zantara without Banyan (~115cr) — Ingredients consistency test
6. **AR1 Lite/Fast/Quality 2× on Q** — full reference prompt with all 3 Ingredients (~215cr) — most ambitious, do LAST when you've learned from AR2-3-4

**Total: ~560 cr (2.24% of 25k monthly)**

After AR1 completes, look at all 12 clips together. The picks that pass rubric ≥22 become your BVCL pilot library.

## Logging template per clip

After each generation, append a row to `~/Desktop/nuzantara/research/marketing/flow-asset-log.csv`:

```
2026-05-13T03:00:00Z,AR3,AR3-lite,Lite,1x,8,5,24995,~85,no,en,AR3/lite/clip.mp4,55,RAW,baseline B-roll Lite tier
```

Fields: timestamp, archetype, sample_id, tier, multiplier, duration_s, credits_consumed, credits_balance_after, prompt_word_count, used_ingredients (yes/no), language, output_filename, gen_time_seconds, outcome (RAW/PASS/RETRY-NEEDED/FAIL), notes (max 1 line).
