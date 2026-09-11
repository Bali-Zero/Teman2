#!/usr/bin/env python3
"""What did the revision REMOVE? -- the axis the defect probe cannot see.

The five-class probe reported "zero introduced" for every seat, and it was
right about what it measures. It was also blind to the thing that actually went
wrong in round two: one entry deleted a real responsive type tier so that a
declared number could not be argued with. Nothing broke. Something was lost.

A defect report that names only a discrepancy invites the cheapest
reconciliation, and the cheapest reconciliation is usually to remove. So this
probe compares round one against round two on what each screen ACTUALLY
RENDERS, per viewport, and reports losses as loudly as gains.
"""
from __future__ import annotations

import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

import os as _os, glob as _glob
def _find_chrome():
    """The headless binary is per-machine (M5 is /Users/balizero, Pro/Mini
    /Users/nuzantara) and its version dir changes on every Playwright bump, so a
    hardcoded path is a probe that dies silently on the other machine."""
    if _os.environ.get("CHROME_HEADLESS"):
        return _os.environ["CHROME_HEADLESS"]
    pat = _os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium_headless_shell-*/"
        "chrome-headless-shell-mac-*/chrome-headless-shell")
    hits = sorted(_glob.glob(pat))
    if not hits:
        raise SystemExit("no chrome-headless-shell found; set CHROME_HEADLESS")
    return hits[-1]
CHROME = _find_chrome()
SEATS = ("qwen", "agy", "claude", "codex")
VIEWS = (("mobile", 390, 844), ("desktop", 1440, 900))

SHAPE_JS = r"""
() => {
  const vis = el => { const s = getComputedStyle(el); if (s.display==='none'||s.visibility==='hidden') return false;
                      const r = el.getBoundingClientRect(); return r.width>0 && r.height>0; };
  const sizes = new Set(), weights = new Set(), fams = new Set();
  let textLen = 0, elems = 0;
  for (const el of document.querySelectorAll('body *')) {
    if (!vis(el)) continue;
    elems++;
    if (el.children.length === 0 && el.textContent.trim()) {
      const s = getComputedStyle(el);
      sizes.add(Math.round(parseFloat(s.fontSize) * 100) / 100);
      weights.add(s.fontWeight);
      fams.add(s.fontFamily.split(',')[0].replace(/["']/g, '').trim());
      textLen += el.textContent.trim().length;
    }
  }
  return {sizes: [...sizes].sort((a,b)=>a-b), weights: [...weights].sort(),
          families: [...fams].sort(), elements: elems, text_chars: textLen,
          doc_height: document.documentElement.scrollHeight};
}
"""


def shapes(page, path: pathlib.Path, b) -> dict:
    out = {}
    for name, w, h in VIEWS:
        ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme="light")
        pg = ctx.new_page()
        pg.goto(path.resolve().as_uri(), wait_until="load")
        pg.wait_for_timeout(400)
        out[name] = pg.evaluate(SHAPE_JS)
        ctx.close()
    return out


def main(argv: list[str]) -> int:
    root = pathlib.Path(argv[1])
    r1, r2 = root / "final", root / "r2" / "entries"
    data = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME)
        for s in SEATS:
            a, c = r1 / s / "ui.html", r2 / s / "ui.html"
            if not (a.exists() and c.exists()):
                continue
            data[s] = {"before": shapes(None, a, b), "after": shapes(None, c, b)}
        b.close()

    for s, d in data.items():
        print(f"== {s} ==")
        losses, gains = [], []
        for v, _, _ in VIEWS:
            bef, aft = d["before"][v], d["after"][v]
            lost = sorted(set(bef["sizes"]) - set(aft["sizes"]))
            got = sorted(set(aft["sizes"]) - set(bef["sizes"]))
            if lost:
                losses.append(f"{v}: type sizes gone {lost}")
            if got:
                gains.append(f"{v}: type sizes new {got}")
            wl = sorted(set(bef["weights"]) - set(aft["weights"]))
            if wl:
                losses.append(f"{v}: weights gone {wl}")
            fl = sorted(set(bef["families"]) - set(aft["families"]))
            if fl:
                losses.append(f"{v}: typefaces gone {fl}")
            de = aft["elements"] - bef["elements"]
            dt = aft["text_chars"] - bef["text_chars"]
            if de:
                (gains if de > 0 else losses).append(f"{v}: elements {de:+d}")
            if dt:
                (gains if dt > 0 else losses).append(f"{v}: rendered characters {dt:+d}")
        # the tell: a tier that existed at ONE viewport only, now gone everywhere
        b_all = set(d["before"]["mobile"]["sizes"]) | set(d["before"]["desktop"]["sizes"])
        a_all = set(d["after"]["mobile"]["sizes"]) | set(d["after"]["desktop"]["sizes"])
        responsive_lost = sorted(
            x for x in (b_all - a_all)
            if (x in d["before"]["desktop"]["sizes"]) != (x in d["before"]["mobile"]["sizes"]))
        print("  LOST: " + ("; ".join(losses) if losses else "nothing"))
        print("  GAINED: " + ("; ".join(gains) if gains else "nothing"))
        if responsive_lost:
            print(f"  !! RESPONSIVE TIER REMOVED: {responsive_lost} existed at one viewport only "
                  f"and is now gone from both — a real design feature traded for an unarguable number")
        print()
    (root / "r2" / "regression.json").write_text(json.dumps(data, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
