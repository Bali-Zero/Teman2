#!/usr/bin/env python3
"""ringgap.py <dir> — the shown cell's ring against the ink around it, on the expanded live sheet renders in <dir>
(files <code>-<theme>-<mode>.png, 2 px per pt). Prints, per render, the ring's box and the nearest foreign ink above and
below it in pt (0 = touching). Exit 1 if any gap is under 1.5 pt."""
import pathlib, sys
from collections import deque
from PIL import Image
ACC = {"day": (0xA4, 0x4B, 0x36), "night": (0xD0, 0x83, 0x71)}
def near(p, c, d): return sum((a - b) ** 2 for a, b in zip(p[:3], c)) <= d * d
def ring(im, theme):
    W, H = im.size; px = im.load(); c = ACC[theme]
    pts = {(x, y) for y in range(900, H, 1) for x in range(0, W, 1) if near(px[x, y], c, 14)} if False else None
    seen = set(); best = None
    for y in range(900, H):
        for x in range(0, W):
            if (x, y) in seen or not near(px[x, y], c, 14): continue
            q = deque([(x, y)]); seen.add((x, y)); comp = []
            while q:
                a, b = q.popleft(); comp.append((a, b))
                for n in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                    if n not in seen and 0 <= n[0] < W and 0 <= n[1] < H and near(px[n[0], n[1]], c, 14): seen.add(n); q.append(n)
            xs = [p[0] for p in comp]; ys = [p[1] for p in comp]; w, h = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
            if 80 <= w <= 600 and 36 <= h <= 140 and len(comp) < 0.35 * w * h and (best is None or len(comp) > best[0]):
                best = (len(comp), min(xs), min(ys), max(xs), max(ys))
    return best
def gaps(im, b):
    _, x0, y0, x1, y1 = b; px = im.load(); W, H = im.size
    ref = px[max(x0 - 8, 0), (y0 + y1) // 2]
    foreign = lambda p: sum(abs(a - c) for a, c in zip(p[:3], ref[:3])) > 40
    def scan(rows):
        for n, y in enumerate(rows):
            if any(foreign(px[x, y]) for x in range(x0 + 6, x1 - 5, 1)): return n
        return 999
    up = scan(range(y0 - 1, max(y0 - 60, 0), -1)); down = scan(range(y1 + 1, min(y1 + 60, H)))
    return up / 2, down / 2
def main(d):
    bad = 0
    for f in sorted(pathlib.Path(d).glob("*.png")):
        code, theme, mode = f.stem.split("-")
        im = Image.open(f).convert("RGB"); b = ring(im, theme)
        if not b: print("%-28s no ring found" % f.stem); bad += 1; continue
        up, down = gaps(im, b); ok = min(up, down) >= 1.5; bad += not ok
        print("%-28s ring %dx%d pt at y %d: nearest ink above %.1f pt, below %.1f pt%s" % (f.stem, (b[3] - b[1]) // 2, (b[4] - b[2]) // 2, b[2] // 2, up, down, "" if ok else "  <-- TOUCHES"))
    return 1 if bad else 0
sys.exit(main(sys.argv[1]))
