#!/usr/bin/env python3
"""Does a fixed/sticky overlay cover content the reader needs?

Three earlier versions of this probe were wrong, each caught by a control:
  v1 "is any text ever covered?"        -> INNOCENCE tripped: a bottom bar covers
                                           something at nearly every mid-scroll
                                           offset, and you simply scroll past it.
  v2 "covered at EVERY offset?"         -> right question, guilt case too weak.
  v3 centre-point via elementFromPoint  -> blind to partial overlap: a line 6px
                                           under the bar has its centre in the clear.
This version measures the AREA of each line's box under an overlay, and separates
the worst mid-scroll moment from the state at the document's end — the one a
reader cannot escape by scrolling further.
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
COVERED = 0.35

PROBE = r"""
() => {
  const alphaOf = (css) => {
    const m = String(css).match(/rgba?\(([^)]+)\)/);
    if (!m) return 0;
    const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(Number);
    return p.length > 3 ? p[3] : 1;
  };
  const overlays = [];
  for (const el of document.querySelectorAll("*")) {
    const cs = getComputedStyle(el);
    if (cs.position !== "fixed" && cs.position !== "sticky") continue;
    if (cs.visibility === "hidden" || cs.display === "none" || parseFloat(cs.opacity) < 0.5) continue;
    if (alphaOf(cs.backgroundColor) < 0.5) continue;   // a see-through overlay hides nothing
    const r = el.getBoundingClientRect();
    if (r.width > 1 && r.height > 1) overlays.push({ el, r });
  }
  if (!overlays.length) return { overlays: 0, items: [] };
  const inOverlay = (n) => { for (let p = n; p; p = p.parentElement) if (overlays.some(o => o.el === p)) return true; return false; };

  const items = [];
  for (const el of document.querySelectorAll("*")) {
    if (inOverlay(el)) continue;
    if (!Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim().length > 0)) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || cs.display === "none") continue;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    if (r.bottom <= 0 || r.top >= window.innerHeight) continue;
    const vt = Math.max(r.top, 0), vb = Math.min(r.bottom, window.innerHeight);
    const vArea = Math.max(0, vb - vt) * r.width;
    if (vArea < 1) continue;
    let covered = 0;
    for (const o of overlays) {
      const ox = Math.max(0, Math.min(r.right, o.r.right) - Math.max(r.left, o.r.left));
      const oy = Math.max(0, Math.min(vb, o.r.bottom) - Math.max(vt, o.r.top));
      covered += ox * oy;
    }
    items.push({ text: el.textContent.trim().slice(0, 60), frac: Math.min(1, covered / vArea) });
  }
  return { overlays: overlays.length, items };
}
"""


def check(path: pathlib.Path, step: int = 120) -> dict:
    seen: dict[str, dict] = {}
    overlays = 0
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME)
        ctx = b.new_context(viewport={"width": 390, "height": 844}, color_scheme="light")
        page = ctx.new_page()
        page.goto(path.resolve().as_uri(), wait_until="load")
        height = page.evaluate("() => document.documentElement.scrollHeight")
        y = 0
        while True:
            page.evaluate("v => window.scrollTo(0, v)", y)
            page.wait_for_timeout(25)
            r = page.evaluate(PROBE)
            overlays = max(overlays, r["overlays"])
            for it in r["items"]:
                rec = seen.setdefault(it["text"], {"text": it["text"], "clearest": 1.0})
                rec["clearest"] = min(rec["clearest"], it["frac"])
            if y + 844 >= height:
                break
            y += step
        page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
        page.wait_for_timeout(80)
        end = page.evaluate(PROBE)
        ctx.close()
        b.close()
    return {
        "file": str(path),
        "overlays": overlays,
        "text_elements": len(seen),
        # even at its clearest, still mostly buried -> the reader can never read it
        "never_readable": sorted([v for v in seen.values() if v["clearest"] >= COVERED],
                                 key=lambda v: -v["clearest"]),
        "covered_at_document_end": sorted([i for i in end["items"] if i["frac"] >= COVERED],
                                          key=lambda v: -v["frac"]),
    }


def main(argv: list[str]) -> int:
    print(json.dumps([check(pathlib.Path(a)) for a in argv[1:]], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
