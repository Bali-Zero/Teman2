# Video slides (живые слайды)

A slide with `background.kind: "video"` becomes a short MP4: your text + the dark scrim, composited on top of a moving clip.

## How it works
1. `build.py` marks the slide transparent (`video-bg`) and keeps the scrim. It copies the clip into `build/assets/` and notes it in `render_manifest.json`.
2. `render.py` screenshots the slide with a **transparent** background → a `*_overlay.png` (only text + semi-transparent scrim have pixels).
3. `ffmpeg` scales/crops the clip to the slide size and overlays the PNG → `output/NN_name.mp4`.

So the text is always razor-sharp (rendered by the browser), and only the background moves.

## Rules of thumb
- **Light text only.** Dark text is unreadable over moving footage — the scrim is tuned for light text, and media slides force it.
- **2–4 video slides per carousel, max.** Never the cover (slide 1 must read instantly as a thumbnail) and usually not the final CTA. Mixing a few live slides with static ones is what feels premium; all-video feels noisy.
- **Same aspect ratio as the rest.** Everything is 1080×1350. The composite force-crops to this, so a clip of any size works, but framing matters — pick clips where the action sits center/top, since the bottom is covered by the scrim + text.
- **≤ 15 seconds.** Instagram trims carousel videos; `render.py` caps at `--max-seconds` (default 15). Shorter (6–10s) loops feel calmer.
- **Calm, ambient motion** beats fast cuts: water, light, steam, slow pans. The slide is a backdrop for text, not a Reel.

## Output
Static slides export as PNG, video slides as MP4 — both 1080×1350. Upload them to the Instagram carousel in slide order; IG carousels accept mixed photo + video items.

## Tuning
- Trim/clean a clip beforehand: `python scripts/prep_media.py video raw/in.mp4 raw/clip.mp4 --seconds 10`
- Audio is stripped by default (`-an` in `render.py`). If you want the clip's sound, remove `-an` from the `composite_video` ffmpeg command.
- Scrim too light/heavy over a bright clip? Adjust the `.slide.media .scrim` gradient stops in `assets/styles.css`.
