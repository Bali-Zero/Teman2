#!/usr/bin/env python3
"""png_census.py <set-dir> — spec §7 census of a rendered set (Python 3.9 + Pillow).
C5: share of pixels within RGB distance 24 of copper or gold (day/night values) per PNG <= 8 %.
C8: registry-table PNGs — the code ROWS of the table, >= 12 at default text size, narrow/ included. A row is a
lineSoft rule spanning >= 80 % of the table band (x 25-97 % of the width) that (a) lies below the table head (the
2 pt structure rule, whose thickness also gives the pixel scale), (b) closes a stripe >= 32 pt tall since the rule
above it (a row is 8 + 20 + 8 pt) and (c) has ink in that stripe. So a filter-bar rule (above the head), a
column-header rule (a short stripe) and a footer rule (an empty stripe) are not rows; each PNG lists the row rules
and the skipped rules in pt. Under xxl/ C8 is VACUOUS, never a pass: the harness's dynamicTypeSize does not scale
text-style or relativeTo: fonts (imperator ruling). A synthetic self-test runs first. Exit 1 on any FAIL."""
import pathlib, sys
from collections import Counter
from PIL import Image, ImageDraw
ACCENTS = [(0xA4, 0x4B, 0x36), (0xD0, 0x83, 0x71), (0xB8, 0x86, 0x2B), (0xC2, 0x8D, 0x2D)]
LINESOFT = [(0xDA, 0xD8, 0xD1), (0x24, 0x36, 0x49)]
STRUCTURE = [(0x23, 0x3D, 0x51), (0x6C, 0x9B, 0xC0)]
near = lambda p, cs, d: any(sum((a - b) ** 2 for a, b in zip(p, c)) <= d * d for c in cs)

def c8_rows(im):
    """(row rules, skipped rules) in pt, or None when the table head is missing."""
    W, H = im.size; x0, x1 = int(W * .25), int(W * .97); px = im.load()
    bg = Counter(im.resize((W // 8, H // 8), Image.NEAREST).getdata()).most_common(1)[0][0]
    runs = []
    for y in range(H):
        c, n = Counter(px[x, y] for x in range(x0, x1, 4)).most_common(1)[0]
        if n < .8 * len(range(x0, x1, 4)) or near(c, [bg], 6): continue
        if runs and runs[-1][1] == y - 1 and near(c, [runs[-1][2]], 6): runs[-1][1] = y
        else: runs.append([y, y, c])
    head = next((i for i, r in enumerate(runs) if near(r[2], STRUCTURE, 24) and r[1] - r[0] >= 2), None)
    if head is None: return None
    scale = (runs[head][1] - runs[head][0] + 1) / 2
    rows, skipped, prev = [], [], runs[head][1]
    for top, bot, c in runs[head + 1:]:
        if near(c, LINESOFT, 6):
            stripe = (top - prev - 1) / scale
            inked = any(not near(px[x, y], [bg], 40) for y in range(prev + 1, top, 2) for x in range(x0, x1, 3))
            if stripe >= 32 and inked: rows.append(round(top / scale))
            else: skipped.append("%d (%s)" % (round(top / scale), "empty stripe" if not inked else "stripe %.0f pt" % stripe))
        prev = bot
    skipped += ["%d (above the table head)" % round(r[0] / scale) for r in runs[:head] if near(r[2], LINESOFT, 6)]
    return rows, skipped

def selftest():
    """A 2x synthetic table: a filter-bar rule, the head, a column-header rule, 12 rows, a footer rule -> 12 rows;
    the same with one row fewer -> 11. A detector that counted every lineSoft rule would report 15."""
    out = []
    for nrows in (12, 11):
        im = Image.new("RGB", (640, 1600), (0xF7, 0xF4, 0xEE)); d = ImageDraw.Draw(im)
        rule = lambda y, h, c: d.rectangle([0, y * 2, 639, (y + h) * 2 - 1], fill=c)
        ink = lambda y: d.rectangle([260, y * 2, 380, (y + 10) * 2], fill=(0x1D, 0x2C, 0x3B))
        ink(10); rule(40, 1, LINESOFT[0]); rule(100, 2, STRUCTURE[0]); ink(110); rule(125, 1, LINESOFT[0])
        rule(150, 1, (0xA8, 0xAC, 0xA9))
        for k in range(nrows): ink(160 + 37 * k); rule(187 + 37 * k, 1, LINESOFT[0])
        rule(700, 1, LINESOFT[0])
        got = c8_rows(im)
        if got is None or len(got[0]) != nrows or len(got[1]) != 3:
            out.append("C8-SELFTEST %d rows: got %s" % (nrows, got and (len(got[0]), got[1])))
    return out

fails = vacuous = 0
for msg in selftest(): print(msg); fails += 1
for png in sorted(pathlib.Path(sys.argv[1]).rglob("*.png")):
    im = Image.open(png).convert("RGB"); W, H = im.size
    small = im.resize((W // 4, H // 4), Image.NEAREST); px = list(small.getdata())
    share = sum(near(p, ACCENTS, 24) for p in px) / len(px)
    line = "%-40s C5 %5.2f%%" % (png.relative_to(sys.argv[1]), share * 100)
    ok, detail = share <= 0.08, ""
    if png.name.startswith("registry-table"):
        got = c8_rows(im)
        if got is None: line += "  C8 no table head (2 pt structure rule)"; ok = ok and png.parent.name == "xxl"
        elif png.parent.name == "xxl": line += "  C8 VACUOUS (rows %d; text does not scale here)" % len(got[0]); vacuous += 1
        else: line += "  C8 rows %d (need >= 12)" % len(got[0]); ok = ok and len(got[0]) >= 12
        if got: detail = "\n    row rules at pt %s; not rows: %s" % (" ".join(map(str, got[0])), ", ".join(got[1]) or "none")
    print(line + ("" if ok else "  FAIL") + detail); fails += not ok
print("png_census: %d FAIL, %d VACUOUS" % (fails, vacuous)); sys.exit(1 if fails else 0)
