"""Rebuild assets.json (inline data-URIs) from the REPO's own image files.

    python3 assets.py <repo-root> <out-dir>

Nothing is copied into this corner: the hero and the six staff cards live in
apps/mouth/public/static and are re-encoded on demand. That is deliberate --
the staff photos are the one clean-consent image class we have, and a second
copy in a skill directory is a second thing to keep in sync and a second place
they can leak from.

Needs Pillow, which lives in the backend venv, not in system python:
    apps/backend-rag/.venv/bin/python assets.py <repo-root> <out-dir>
"""
import base64, io, json, pathlib, sys

from PIL import Image

if len(sys.argv) != 3:
    raise SystemExit(__doc__)
P = pathlib.Path(sys.argv[1]) / "apps/mouth/public/static"
D = pathlib.Path(sys.argv[2]); D.mkdir(parents=True, exist_ok=True)
if not P.is_dir():
    raise SystemExit(f"not a repo root (no {P}): {sys.argv[1]}")

out, total = {}, 0

def jpg(im, w, q, key, crop=None):
    global total
    if crop:
        im = im.crop(crop)
    im = im.convert("RGB").resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=q, optimize=True, progressive=True)
    d = b.getvalue(); total += len(d)
    out[key] = "data:image/jpeg;base64," + base64.b64encode(d).decode()
    print(f"  {key:16s} {im.size[0]}x{im.size[1]}  {len(d)/1024:6.1f} KB")

# The mark is the brand's own asset, trimmed to its ink and shrunk to the size it
# is actually drawn at. It is NOT set as the word's letter B: the staff cards put
# the mark BESIDE the wordmark, and at 26px the "B" reading fails (it reads "3").
print("MARK")
m = Image.open(P.parent / "assets/logo/balizero-3-red.png").convert("RGBA")
bbox = m.getbbox()
if bbox:
    m = m.crop(bbox)
m = m.resize((round(m.width * 102 / m.height), 102), Image.LANCZOS)
_b = io.BytesIO(); m.save(_b, "PNG", optimize=True)
_d = _b.getvalue(); total += len(_d)
out["logo"] = "data:image/png;base64," + base64.b64encode(_d).decode()
print(f"  {'logo':16s} {m.size[0]}x{m.size[1]}  {len(_d)/1024:6.1f} KB")

print("\nHERO — sized for a 390px phone at 2x, gate 36 budget 150-200 KB")
jpg(Image.open(P / "news" / "perfect-storm-bali.jpg"), 1100, 72, "hero")

print("\nTEAM — the cards carry their own name and role, so nothing is retyped")
missing = []
for t in ["surya", "ari", "sahira", "damar", "krisna", "dewaayu"]:
    f = P / "team" / f"{t}.jpg"
    if not f.exists():
        missing.append(t); print(f"  {t}: MISSING"); continue
    jpg(Image.open(f), 300, 74, t)

print(f"\nTOTAL {total/1024:.0f} KB")
(D / "assets.json").write_text(json.dumps(out))
if missing:
    raise SystemExit(f"missing team cards: {missing} — the page would ship dead images")
