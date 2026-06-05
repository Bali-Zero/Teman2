#!/usr/bin/env python3
"""Composite Antonello's original PUNGLINESIA raster wordmark into a 1080x1350
cover background. Crops the wordmark+subtitle band (EXCLUDES the Garuda emblem
at top — UU 24/2009 — and the 'BRIEF GRAFIS' annotation at bottom), fades the
band edges into black, centers it on a portrait black canvas. HTML overlays
(KPK badge, empirical anchor, logo) are added at render time by build.py.
"""
from pathlib import Path
from PIL import Image

SRC = Path.home() / "Desktop/PHOTO-2026-06-05-12-55-13.jpg"
OUT = Path(__file__).parent / "cover-bg.png"

CW, CH = 1080, 1350  # portrait canvas

src = Image.open(SRC).convert("RGB")  # 1280x960
assert src.size == (1280, 960), src.size

# Crop band: the WORDMARK + its red veins ONLY (sub + anchor are re-rendered
# in CSS for full control). y190 sits just BELOW the Garuda (~y70-170); y630
# sits just ABOVE the 'BUKAN OKNUM' subtitle (~y660).
band = src.crop((0, 190, 1280, 630))            # 1280 x 440 — wordmark + veins

# scale to canvas width
w = CW
h = round(band.height * w / band.width)         # ~481
band = band.resize((w, h), Image.LANCZOS).convert("RGBA")

# vertical alpha fade top/bottom so the band melts into pure black
fade = 70
mask = Image.new("L", (w, h), 255)
mpx = mask.load()
for y in range(h):
    if y < fade:
        a = round(255 * y / fade)
    elif y > h - fade:
        a = round(255 * (h - y) / fade)
    else:
        a = 255
    for x in range(w):
        mpx[x, y] = a
band.putalpha(mask)

canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 255))
top = 330                                        # wordmark sits in the upper third
canvas.alpha_composite(band, (0, top))
canvas.convert("RGB").save(OUT, "PNG")
print(f"cover-bg.png {canvas.size} · band {band.size} at y={top}..{top + h}")
