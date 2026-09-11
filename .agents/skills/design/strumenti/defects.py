#!/usr/bin/env python3
"""Mechanise the five defect classes that round one found BY HAND.

Round one's mechanical gates (contrast, overflow, tap size, network, no-JS)
passed all four entries. Everything that actually separated the field was found
by reading — by me, or by an adversarial critic — and two of those readings were
themselves wrong. A defect a human had to notice is a defect the next round will
miss. So each class below is a probe, and each probe is only trusted for a run
where its INNOCENCE control stays silent and its GUILT control fires.

  dead-control       an interactive-looking element that does nothing
  duplicate-string   the same >=3-word visible string doing two different jobs
  heading-order      a heading of higher rank before the h1, or a skipped level
  double-announce    an aria-label repeating text that is also visible and unhidden
  struck-copy        line-through applied to supplied verbatim copy
  clipped-sentence   a whole sentence cut off by an ancestor horizontal scroller

The last one exists because the first five, plus every mechanical gate from
round one, all passed a screen whose headline claim was cut in half on a 390px
phone. The document did not overflow -- the scroll container absorbed it, which
is exactly what the brief asks a wide TABLE to do. A table scrolling its columns
is the accepted pattern; a SENTENCE that must be scrolled to be read is not. The
rule distinguishes them the only honest way available: a sentence has a full stop
and six or more words. A data cell does not.

The probes read the RENDERED accessibility-relevant DOM, not the source text:
`display:none` content is not a duplicate string, and an aria-label on a hidden
element is not announced twice.
"""
from __future__ import annotations

import json
import pathlib
import re
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
PROBE_JS = r"""
() => {
  const vis = el => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0) return false;
    if (el.closest('[aria-hidden="true"]')) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const norm = t => (t || '').replace(/\s+/g, ' ').trim();

  // --- dead controls -------------------------------------------------------
  const dead = [];
  for (const a of document.querySelectorAll('a')) {
    if (!vis(a)) continue;
    const h = a.getAttribute('href');
    const label = norm(a.textContent).slice(0, 60);
    if (h === null) dead.push({kind: 'anchor-without-href', label});
    else if (h.trim() === '' || h.trim() === '#') dead.push({kind: 'empty-href', href: h, label});
    else if (/^mailto:\s*$/i.test(h.trim())) dead.push({kind: 'mailto-without-address', href: h, label});
    else if (/^tel:\s*$/i.test(h.trim())) dead.push({kind: 'tel-without-number', href: h, label});
  }
  // A <button type="button"> in a static mock is NOT a dead control: it names no
  // destination, so it promises none. Reporting it was this probe's own
  // over-match (guard-over-match, family #3) -- caught because the innocence
  // control had been written with the button inside a <form>, a shape none of
  // the real specimens use. An innocence control that is innocent in a way the
  // specimens are not proves nothing. The rule is now: a control is dead when it
  // NAMES a destination it does not have.

  // --- duplicate visible strings ------------------------------------------
  // Leaf-ish text blocks only, so a container does not duplicate its own child.
  const seen = {};
  const BLOCK = 'h1,h2,h3,h4,h5,h6,p,li,td,th,button,a,dt,dd,figcaption,summary,label,span,div';
  for (const el of document.querySelectorAll(BLOCK)) {
    if (!vis(el)) continue;
    if (el.querySelector(BLOCK)) continue;          // not a leaf
    const t = norm(el.textContent);
    if (t.split(' ').length < 3) continue;
    (seen[t] = seen[t] || []).push(el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''));
  }
  const dupes = Object.entries(seen)
    .filter(([, w]) => w.length > 1)
    .map(([text, where]) => ({text: text.slice(0, 80), count: where.length, where}));

  // --- heading order -------------------------------------------------------
  const heads = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')]
    .filter(vis)
    .map(h => ({level: +h.tagName[1], text: norm(h.textContent).slice(0, 60)}));
  const horder = [];
  if (heads.length) {
    const firstH1 = heads.findIndex(h => h.level === 1);
    if (firstH1 === -1) horder.push({kind: 'no-h1', detail: 'document has headings but no visible h1'});
    else if (firstH1 > 0) {
      horder.push({kind: 'heading-before-h1',
                   detail: heads.slice(0, firstH1).map(h => `h${h.level} "${h.text}"`).join(' + ')});
    }
    for (let i = 1; i < heads.length; i++) {
      if (heads[i].level > heads[i - 1].level + 1) {
        horder.push({kind: 'skipped-level',
                     detail: `h${heads[i - 1].level} -> h${heads[i].level} at "${heads[i].text}"`});
      }
    }
  }

  // --- aria double-announcement -------------------------------------------
  const doubles = [];
  const visibleTexts = new Set();
  for (const el of document.querySelectorAll(BLOCK)) {
    if (!vis(el)) continue;
    if (el.querySelector(BLOCK)) continue;
    const t = norm(el.textContent);
    if (t.split(' ').length >= 4) visibleTexts.add(t.toLowerCase());
  }
  for (const el of document.querySelectorAll('[aria-label]')) {
    const lab = norm(el.getAttribute('aria-label'));
    if (lab.split(' ').length < 4) continue;
    if (el.getAttribute('aria-hidden') === 'true' || el.closest('[aria-hidden="true"]')) continue;
    const l = lab.toLowerCase();
    for (const t of visibleTexts) {
      // exact, or the label is a prefix/superset of a visible block
      if (t === l || t.startsWith(l) || l.startsWith(t)) {
        doubles.push({label: lab.slice(0, 90),
                      on: el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''),
                      also_visible_as: t.slice(0, 90)});
        break;
      }
    }
  }

  // --- struck-through text -------------------------------------------------
  const struck = [];
  for (const el of document.querySelectorAll('*')) {
    if (!vis(el)) continue;
    if (el.children.length) continue;
    const s = getComputedStyle(el);
    if ((s.textDecorationLine || '').includes('line-through')) {
      struck.push({text: norm(el.textContent).slice(0, 80),
                   on: el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : '')});
    }
  }

  // --- sentences clipped by an ancestor scroller ---------------------------
  const clipped = [];
  const scrollerOf = el => {
    let p = el.parentElement;
    while (p) {
      const cs = getComputedStyle(p);
      if (cs.overflowX === 'auto' || cs.overflowX === 'scroll' || cs.overflowX === 'hidden') return p;
      p = p.parentElement;
    }
    return null;
  };
  for (const el of document.querySelectorAll(BLOCK)) {
    if (!vis(el)) continue;
    if (el.querySelector(BLOCK)) continue;
    const t = norm(el.textContent);
    if (t.split(' ').length < 6 || !/[.!?]$/.test(t)) continue;   // data cell, not a sentence
    const sc = scrollerOf(el);
    if (!sc) continue;
    const r = el.getBoundingClientRect(), sr = sc.getBoundingClientRect();
    const cut = Math.round(Math.max(0, r.right - sr.right) + Math.max(0, sr.left - r.left));
    if (cut > 8) clipped.push({text: t.slice(0, 70), cut_px: cut,
                               on: el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''),
                               scroller_visible_px: Math.round(sc.clientWidth),
                               scroller_content_px: Math.round(sc.scrollWidth)});
  }

  return {dead_controls: dead, duplicate_strings: dupes, heading_order: horder,
          double_announced: doubles, struck_text: struck, clipped_sentences: clipped,
          heading_outline: heads.map(h => `h${h.level} ${h.text}`)};
}
"""

CLASSES = ("dead_controls", "duplicate_strings", "heading_order", "double_announced",
           "struck_text", "clipped_sentences")


def run(page, path: pathlib.Path) -> dict:
    page.goto(path.resolve().as_uri(), wait_until="load")
    page.wait_for_timeout(400)
    return page.evaluate(PROBE_JS)


def main(argv: list[str]) -> int:
    root = pathlib.Path(argv[1])
    targets = [(p.parent.name, p) for p in sorted(root.glob("*/ui.html"))]
    calib = root.parent / "calib"
    out = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME)
        page = b.new_page(viewport={"width": 390, "height": 844})   # the deciding viewport

        # --- controls, before any verdict is trusted ------------------------
        controls = {}
        for name in ("innocent", "guilty"):
            f = calib / f"defects-{name}.html"
            if f.exists():
                controls[name] = run(page, f)
        for name, seat_path in targets:
            out[name] = run(page, seat_path)
        b.close()

    if controls:
        inn = controls.get("innocent", {})
        gui = controls.get("guilty", {})
        inn_noise = {c: inn.get(c, []) for c in CLASSES if inn.get(c)}
        gui_silent = [c for c in CLASSES if not gui.get(c)]
        print("CONTROLS")
        print(f"  innocence: {'CLEAN' if not inn_noise else 'NOISY ' + json.dumps(inn_noise)}")
        print(f"  guilt:     {'ALL FIRE' if not gui_silent else 'SILENT ON ' + ', '.join(gui_silent)}")
        if inn_noise or gui_silent:
            print("  -> probe NOT trusted for this run; findings below are unverified\n")
        else:
            print("  -> probe trusted for this run\n")

    for name, res in out.items():
        hits = {c: res[c] for c in CLASSES if res[c]}
        print(f"== {name} ==")
        if not hits:
            print("  clean on all six classes")
        for c, items in hits.items():
            print(f"  {c}:")
            for it in items:
                print(f"    - {json.dumps(it)}")
        print(f"  outline: {' | '.join(res['heading_outline'])}")
        print()
    (root / "defects.json").write_text(json.dumps({"controls": controls, "seats": out}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
