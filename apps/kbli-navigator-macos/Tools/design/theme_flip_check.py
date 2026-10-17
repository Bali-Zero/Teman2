#!/usr/bin/env python3
"""theme_flip_check.py - the app never paints a mixed theme: not at launch, not after a runtime flip.

Theme tokens are static computed values and only RootView observes the ThemeManager, so a view that did not rebuild after the mode
changed keeps the old mode's colours: cream title on paper, night chips on a day list. Every other check in this directory renders
with the theme FORCED before the first frame and so cannot see it. This one reproduces the launch order and the toggle:

  launch  `--snapshot-band root-sheet --theme day|night`  the window as the app builds it (ThemeManager.launchMode() seed)
  flip    the same with `--flip`: after the window settled, the mode is flipped the way the toolbar toggle flips it

and reads pixels in the render, against the tokens parsed from Sources/Theme.swift for the mode the window must END in:
  surface   the sheet's own fill is Theme.ink of the mode
  chip      the selected row's Bali chip fill is Theme.chipClosedBg of the mode (code 55203: closed on the national axis)
  title     the sheet's title vs the sheet fill >= 4.5:1
  activity  the selected row's Activity text vs the row fill >= 4.5:1

  theme_flip_check.py BIN            4 cases (offscreen: the launch order of a real window is not reproducible here, see git log) (launch day, launch night, day then flip, night then flip); exit 1 on a FAIL
  theme_flip_check.py BIN --selftest the instrument: a day render judged as night FAILS, judged as day PASSES (and the reverse)

The geometry is the app's own: the row's and the title's frames come from `--layout-json`, the chip sits where KBLIRegistryRow puts it
(10 pt padding, two 132 pt cells, 12 pt spacing, comfortable density).
"""
import json, pathlib, re, subprocess, sys, tempfile
from PIL import Image

THEME = pathlib.Path(__file__).resolve().parents[2] / "Sources" / "Theme.swift"
CODE, W, H = "55203", 1180, 800
AA = 4.5

def tokens():
    src = THEME.read_text()
    out = {}
    for name in ("ink", "chipClosedBg"):
        m = re.search(r"static var %s:\s*Color\s*\{\s*pick\(0x([0-9A-Fa-f]{6}),\s*0x([0-9A-Fa-f]{6})\)" % name, src)
        if not m: sys.exit("theme_flip_check: cannot read token %s from Theme.swift" % name)
        out[name] = {"day": tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4)),
                     "night": tuple(int(m.group(2)[i:i + 2], 16) for i in (0, 2, 4))}
    return out

def lum(p):
    f = lambda c: (c / 255) / 12.92 if c / 255 <= 0.03928 else ((c / 255 + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(p[0]) + 0.7152 * f(p[1]) + 0.0722 * f(p[2])

def contrast(a, b):
    hi, lo = max(lum(a), lum(b)), min(lum(a), lum(b))
    return (hi + 0.05) / (lo + 0.05)

def close(a, b, tol=3):
    return all(abs(x - y) <= tol for x, y in zip(a, b))

def ink_contrast(im, box):
    """Contrast of the strongest ink in `box` against the box's own fill (its commonest colour)."""
    x0, y0, x1, y1 = (int(v) for v in box)
    px = [im.getpixel((x, y)) for x in range(x0, x1) for y in range(y0, y1)]
    fill = max(set(px), key=px.count)
    return fill, max(contrast(fill, p) for p in px)

def judge(png, frames, mode, tok):
    """[(name, ok, detail)] for one render that must be in `mode`."""
    im = Image.open(png).convert("RGB")
    s = im.size[0] / W
    f = {x["name"]: x["frame"] for x in frames}
    res = []
    sx, sy, sw, sh = f["sheet"]
    surf = im.getpixel((int((sx + sw * 0.6) * s), int((sy + 14) * s)))
    res.append(("surface", close(surf, tok["ink"][mode]), "sheet fill %s, want %s" % (surf, tok["ink"][mode])))
    rx, ry, rw, rh = f["row.selected"]
    chip = im.getpixel((int((rx + rw - 10 - 132 - 12 - 132 + 6) * s), int((ry + rh / 2) * s)))
    res.append(("chip", close(chip, tok["chipClosedBg"][mode]), "chip fill %s, want %s" % (chip, tok["chipClosedBg"][mode])))
    tx, ty, tw, th = f["title"]
    _, c = ink_contrast(im, (tx * s, ty * s, (tx + tw) * s, (ty + th) * s))
    res.append(("title", c >= AA, "title %.2f:1" % c))
    _, c = ink_contrast(im, ((rx + 80) * s, (ry + 4) * s, (rx + rw - 300) * s, (ry + rh - 4) * s))
    res.append(("activity", c >= AA, "activity %.2f:1" % c))
    return res

def render(binp, out, theme, flip):
    js = out.with_suffix(".json")
    cmd = [binp, "--snapshot-band", "root-sheet", "--theme", theme, "--lang", "en", "--code", CODE,
           "--width", str(W), "--height", str(H), "--layout-json", str(js)] + (["--flip"] if flip else []) + [str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0 or not out.exists():
        sys.exit("theme_flip_check: render failed (%s): %s" % (" ".join(cmd[1:6]), r.stderr[-300:]))
    return json.loads(js.read_text())["frames"]

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    binp, selftest = sys.argv[1], "--selftest" in sys.argv
    tok, tmp = tokens(), pathlib.Path(tempfile.mkdtemp(prefix="themeflip-"))
    cases = [("launch day", "day", False, "day"), ("launch night", "night", False, "night"),
             ("flip day>night", "day", True, "night"), ("flip night>day", "night", True, "day")]
    bad = 0
    if selftest:
        for theme in ("day", "night"):
            png = tmp / ("self-%s.png" % theme)
            frames = render(binp, png, theme, False)
            for want in ("day", "night"):
                fails = [n for n, ok, _ in judge(png, frames, want, tok) if not ok]
                should_fail = want != theme
                ok = bool(fails) == should_fail
                bad += not ok
                print("%s a %s render judged as %s: %s (%s)" % ("PASS" if ok else "FAIL", theme, want,
                      "fails " + ",".join(fails) if fails else "passes", "guilt" if should_fail else "innocence"))
        sys.exit(1 if bad else 0)
    for label, theme, flip, final in cases:
        png = tmp / ("%s-%s.png" % (theme, "flip" if flip else "launch"))
        res = judge(png, render(binp, png, theme, flip), final, tok)
        failed = [n for n, ok, _ in res if not ok]
        bad += bool(failed)
        print("%s %-15s ends %-5s %s" % ("FAIL" if failed else "PASS", label, final, "; ".join(d for _, ok, d in res if not ok) or
              "; ".join(d for _, _, d in res)))
    print("theme_flip_check: %d of %d cases FAIL (renders in %s)" % (bad, len(cases), tmp))
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
