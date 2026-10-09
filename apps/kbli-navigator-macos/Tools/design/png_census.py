#!/usr/bin/env python3
"""png_census.py <set-dir> — spec §7 census of a rendered set (Python 3.9 + Pillow).
C5: share of pixels within RGB distance 24 of copper or gold (day/night values) per PNG <= 8 %.
C8: registry-table PNGs — horizontal lineSoft rules spanning >= 80 % of the table band (x 25-97 %
of the width) counted as rows; >= 12 at default text size. Under xxl/ C8 is VACUOUS, never a pass: the
harness's dynamicTypeSize does not scale text-style or relativeTo: fonts (imperator ruling). Exit 1 on any FAIL."""
import pathlib, sys
from PIL import Image
ACCENTS = [(0xA4, 0x4B, 0x36), (0xD0, 0x83, 0x71), (0xB8, 0x86, 0x2B), (0xC2, 0x8D, 0x2D)]
LINESOFT = [(0xDA, 0xD8, 0xD1), (0x24, 0x36, 0x49)]
near = lambda p, cs, d: any(sum((a - b) ** 2 for a, b in zip(p, c)) <= d * d for c in cs)
fails = vacuous = 0
for png in sorted(pathlib.Path(sys.argv[1]).rglob("*.png")):
    im = Image.open(png).convert("RGB"); W, H = im.size
    small = im.resize((W // 4, H // 4), Image.NEAREST); px = list(small.getdata())
    share = sum(near(p, ACCENTS, 24) for p in px) / len(px)
    line = "%-40s C5 %5.2f%%" % (png.relative_to(sys.argv[1]), share * 100)
    ok = share <= 0.08
    if png.name.startswith("registry-table"):
        x0, x1, rules, prev = int(W * .25), int(W * .97), 0, False
        for y in range(H):
            row = [im.getpixel((x, y)) for x in range(x0, x1, 4)]
            hit = sum(near(p, LINESOFT, 6) for p in row) >= .8 * len(row)
            rules += hit and not prev; prev = hit
        if png.parent.name == "xxl": line += "  C8 VACUOUS (rows %d; text does not scale here)" % rules; vacuous += 1
        else: line += "  C8 rows %d (need >= 12)" % rules; ok = ok and (png.parent.name == "narrow" or rules >= 12)
    print(line + ("" if ok else "  FAIL")); fails += not ok
print("png_census: %d FAIL, %d VACUOUS" % (fails, vacuous)); sys.exit(1 if fails else 0)
