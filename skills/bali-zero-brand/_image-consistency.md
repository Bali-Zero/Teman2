# Image consistency across carousel slides

> Addresses Gemini FLAW HIGH "image style drift between slide 1 and slide 9". 5-9 hero images generated independently produce different lighting/subject/quality.

## The problem

For one 9-slide carousel with 5 hero images:
- Slide 1: 35mm chiaroscuro teal-amber, dark wood desk, lamp
- Slide 4: bright daylight, different aspect, different subject
- Slide 7: AI-art fingerprint visible, different model bias

Even with identical prompt prefix, image generators have stochastic variance. The carousel looks like 5 different photoshoots stitched together.

## Solution: 3-layer consistency

### Layer 1 — Topic-hash seed locking

The orchestrator computes:
```python
import hashlib
seed = int(hashlib.md5(topic_slug.encode()).hexdigest()[:8], 16) % (2**31)
```

This `seed` is passed to the image generator for every hero in this carousel. With Codex `$imagegen` (gpt-image-2) the seed parameter doesn't directly control output (model not deterministic), but logging it pairs runs to topics. With Gemini Imagen / Flux LoRA / Flowkit, seed locking IS effective.

Stored in `slide_states.image_seed` column.

### Layer 2 — Reference image cascade (PRIMARY mechanism)

After slide 1 cover image is generated and approved, slide 1 PNG becomes the **style reference** passed to slide 2..N image generation:

```bash
# Slide 1 — initial generation
codex exec "\$imagegen <full prompt for cover>"
# Output: ~/.codex/generated_images/<uuid>/ig_<hash>.png
# Move to slides/1.hero.png

# Slides 2..N — reference-conditioned
codex exec "\$imagegen --reference-image slides/1.hero.png \
  match style and mood and grading of reference exactly. \
  Subject for this slide: <slide-specific subject>. \
  Same chiaroscuro, same teal-amber grading, same 35mm grain."
```

If `--reference-image` flag not supported by current Codex CLI version: include the slide-1 PNG as input attachment in the prompt body.

### Layer 3 — Camera + grading prompt anchor

Every hero image prompt MUST include the same camera + grading anchor (Article 5.2):

```
Anchor (verbatim across all hero prompts in same carousel):
  shot on ARRI Alexa Mini LF, 35mm film cinematic,
  chiaroscuro lighting, teal-amber color grading,
  Villeneuve/Deakins reference,
  low saturation outside palette
```

Pick ONE camera per carousel (ARRI Alexa Mini LF or Hasselblad X2D or RED V-Raptor or Leica M11) — store in `carousel_runs.notes` as `camera: <name>`. Don't mix cameras within same carousel.

## Render workflow for orchestrator

```python
# Pseudo-code in orchestrator
camera = random.choice(["ARRI Alexa Mini LF", "Hasselblad X2D", "RED V-Raptor", "Leica M11"])
seed = topic_hash_seed(topic_slug)

# Slide 1 cover — no reference
slide_1_png = imagegen(
    prompt=f"{slide_1_subject} | {anchor} | shot on {camera} | seed {seed}",
)

# Slides 2..N
for i, slide in enumerate(slides[1:], start=2):
    if not slide.is_hero_image:
        continue
    slide_N_png = imagegen(
        prompt=f"{slide.subject} | {anchor} | shot on {camera} | seed {seed} | match grading of reference",
        reference=slide_1_png,
    )
```

## Critic enforcement (rubric 4 image-fit)

The `wr2-critic` checks per-slide:
- Cinematic style consistency vs slide 1 (subjective; vision-based)
- Same camera/grading hint
- No AI-art fingerprints

Hard fail if a slide is dramatically off-style relative to slide 1 (e.g., slide 1 is dark editorial, slide 4 is bright pastel). Soft fail if minor variance (acceptable).

## Cost discipline

Reference-image conditioning adds latency but doesn't multiply cost on Codex `$imagegen` (still 1 call per image). On Gemini Imagen / Flux, reference conditioning is free.

For 5 hero images × 30 carousels/month = 150 image generations/month. Within Codex Plus quota.

## Failure modes

- **Slide 1 fails to generate**: abort carousel (cannot anchor). Surface to user.
- **Reference-image flag not supported by Codex CLI version**: fall back to "include reference URL in prompt body" — less effective but not broken.
- **Style-drift detected by critic on slide N**: regenerate that slide with stronger reference language ("match exactly the lighting and atmosphere of reference"). Max 1 regen per slide before soft-fail to human queue.

## Open question (sessione 3)

Should we maintain a "canonical anchor image" for each topic-domain (visa-anchor.png, tax-anchor.png) curated by Antonello, instead of using slide-1 as the in-carousel anchor? This would give cross-carousel consistency, but reduces per-carousel artistic variation. Decide post-empirical-test.
