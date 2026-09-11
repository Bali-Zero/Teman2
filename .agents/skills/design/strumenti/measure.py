#!/usr/bin/env python3
"""The judging instrument for the "perfect screen" contest.

Everything here measures the RENDERED page, never the source text. Two reference
files (ref-good.html / ref-bad.html) calibrate it: the instrument is only trusted
for a run in which the good one passes every gate and the bad one trips the gate
it was built to trip. A probe made more sensitive without calibration becomes the
defect it was meant to find.
"""
from __future__ import annotations

import json
import math
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
VIEWPORTS = {"mobile": (390, 844), "desktop": (1440, 900)}
# Three theme states, because that is how many a viewer actually has: an explicit
# light choice, the un-stamped default under a dark OS, and an explicit dark choice.
THEMES = {
    "light": ("light", "light"),
    "system-dark": ("dark", None),
    "forced-dark": ("light", "dark"),
}

PROBE_JS = r"""
() => {
  const srgb = (c) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
  const lum = ([r, g, b]) => 0.2126 * srgb(r / 255) + 0.7152 * srgb(g / 255) + 0.0722 * srgb(b / 255);
  const parse = (s) => {
    const m = String(s).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(Number);
    return { rgb: [p[0], p[1], p[2]], a: p.length > 3 ? p[3] : 1 };
  };
  const over = (fg, bg, a) => fg.map((c, i) => c * a + bg[i] * (1 - a));
  const ratio = (a, b) => {
    const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x);
    return (l1 + 0.05) / (l2 + 0.05);
  };
  const path = (el) => {
    const bits = [];
    for (let n = el; n && n.nodeType === 1 && bits.length < 4; n = n.parentElement) {
      bits.unshift(n.tagName.toLowerCase() + (n.className && typeof n.className === "string"
        ? "." + n.className.trim().split(/\s+/).slice(0, 2).join(".") : ""));
    }
    return bits.join(">");
  };

  // Effective background: walk up until an opaque-enough layer is found. An
  // element sitting on a background-IMAGE is reported unmeasurable, never passed.
  const effBg = (el) => {
    let acc = null, imaged = false;
    for (let n = el; n; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.backgroundImage && cs.backgroundImage !== "none") imaged = true;
      const c = parse(cs.backgroundColor);
      if (c && c.a > 0) {
        acc = acc === null ? { rgb: c.rgb, a: c.a } : { rgb: over(acc.rgb, c.rgb, acc.a), a: Math.min(1, acc.a + c.a) };
        if (acc.a >= 0.99) return { rgb: acc.rgb, imaged };
      }
    }
    const html = parse(getComputedStyle(document.documentElement).backgroundColor);
    const base = html && html.a > 0 ? html.rgb : [255, 255, 255];
    return { rgb: acc ? over(acc.rgb, base, acc.a) : base, imaged };
  };

  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || cs.display === "none" || parseFloat(cs.opacity) < 0.1) return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };

  const contrast = [], sizes = {}, sizeChars = {}, unmeasurable = [];
  for (const el of document.querySelectorAll("*")) {
    const own = Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim().length > 0);
    if (!own || !visible(el)) continue;
    const cs = getComputedStyle(el);
    const fg = parse(cs.color);
    if (!fg) continue;
    const bg = effBg(el);
    const px = parseFloat(cs.fontSize);
    const weight = parseInt(cs.fontWeight, 10) || 400;
    // WCAG states large text in POINTS: 18pt = 24px, 14pt bold = 18.66px.
    const large = px >= 24 || (px >= 18.66 && weight >= 700);
    const need = large ? 3.0 : 4.5;
    const colour = fg.a < 1 ? over(fg.rgb, bg.rgb, fg.a) : fg.rgb;
    const r = ratio(colour, bg.rgb);
    sizes[px] = (sizes[px] || 0) + 1;
    const ownText = Array.from(el.childNodes).filter(n => n.nodeType === 3)
                         .map(n => n.textContent.trim()).join(" ").length;
    sizeChars[px] = (sizeChars[px] || 0) + ownText;
    const rec = { path: path(el), px, weight, ratio: Math.round(r * 100) / 100, need,
                  text: el.textContent.trim().slice(0, 48) };
    if (bg.imaged) unmeasurable.push(rec);
    else if (r < need) contrast.push(rec);
  }

  const targets = [];
  const SEL = "a[href],button,input,select,textarea,summary,[role=button],[role=link],[tabindex]:not([tabindex='-1'])";
  for (const el of document.querySelectorAll(SEL)) {
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    // A control may reach 44px through padding on an inline wrapper; measure the
    // union of the element and its nearest block-level parent's inline box.
    const w = Math.round(r.width), h = Math.round(r.height);
    if (w < 44 || h < 44) targets.push({ path: path(el), w, h, text: el.textContent.trim().slice(0, 40) });
  }

  const de = document.documentElement;
  return {
    horizontal_scroll: de.scrollWidth > window.innerWidth + 1,
    scroll_width: de.scrollWidth,
    inner_width: window.innerWidth,
    body_bg: getComputedStyle(document.body).backgroundColor,
    body_color: getComputedStyle(document.body).color,
    html_bg: getComputedStyle(de).backgroundColor,
    contrast_failures: contrast,
    unmeasurable_over_image: unmeasurable,
    small_targets: targets,
    font_sizes: sizes,
    font_size_chars: sizeChars,
    text_length: document.body.innerText.replace(/\s+/g, " ").trim().length,
  };
}
"""


def rgb_of(css: str) -> tuple[float, float, float] | None:
    import re
    m = re.match(r"rgba?\(([^)]+)\)", css or "")
    if not m:
        return None
    p = [float(x) for x in re.split(r"[\s,/]+", m.group(1)) if x]
    return (p[0], p[1], p[2])


def lstar(rgb: tuple[float, float, float]) -> float:
    def f(c: float) -> float:
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    y = 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2])
    return 116 * (y ** (1 / 3)) - 16 if y > 0.008856 else 903.3 * y


def chroma(rgb: tuple[float, float, float]) -> float:
    """Saturation as a 0-1 fraction, the same shape the brief asked seats to declare."""
    mx, mn = max(rgb), min(rgb)
    return 0.0 if mx == 0 else (mx - mn) / mx


def measure_file(html: pathlib.Path) -> dict:
    out: dict = {"file": str(html), "states": {}, "external_requests": [], "errors": []}
    url = html.resolve().as_uri()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME)
        for vname, (w, h) in VIEWPORTS.items():
            for tname, (cs_scheme, forced) in THEMES.items():
                ctx = browser.new_context(viewport={"width": w, "height": h},
                                          color_scheme=cs_scheme, device_scale_factor=2)
                ext: list[str] = []
                ctx.on("request", lambda r: ext.append(r.url) if not r.url.startswith(("file:", "data:", "blob:", "about:")) else None)
                page = ctx.new_page()
                page.on("pageerror", lambda e: out["errors"].append(f"{vname}/{tname}: {e}"))
                page.goto(url, wait_until="load")
                page.wait_for_timeout(250)
                if forced:
                    page.evaluate("t => document.documentElement.setAttribute('data-theme', t)", forced)
                page.wait_for_timeout(700)
                first = page.evaluate(PROBE_JS)
                page.wait_for_timeout(400)
                second = page.evaluate(PROBE_JS)
                if len(first["contrast_failures"]) != len(second["contrast_failures"]):
                    out.setdefault("unsettled", []).append(f"{vname}/{tname}")
                    page.wait_for_timeout(1200)
                    second = page.evaluate(PROBE_JS)
                out["states"][f"{vname}/{tname}"] = second
                out["external_requests"] += ext
                ctx.close()

        # JS disabled: the screen must already be complete without it.
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, java_script_enabled=False)
        page = ctx.new_page()
        page.goto(url, wait_until="load")
        out["nojs_text_length"] = page.evaluate("() => document.body.innerText.replace(/\\s+/g,' ').trim().length")
        out["nojs_text"] = page.evaluate("() => document.body.innerText")
        ctx.close()
        browser.close()
    return out


def derive(m: dict) -> dict:
    """What the pixels say the generator was — to be diffed against what the seat declared."""
    light = m["states"]["desktop/light"]
    dark = m["states"]["desktop/forced-dark"]
    g_light = rgb_of(light["body_bg"]) or rgb_of(light["html_bg"]) or (255, 255, 255)
    g_dark = rgb_of(dark["body_bg"]) or rgb_of(dark["html_bg"]) or (0, 0, 0)
    sizes = {float(k): v for k, v in light["font_sizes"].items()}
    ordered = sorted(sizes)
    ratios = [round(b / a, 3) for a, b in zip(ordered, ordered[1:]) if a > 0]
    chars = {float(k): v for k, v in light.get("font_size_chars", {}).items()}
    base_by_elements = max(sizes.items(), key=lambda kv: kv[1])[0] if sizes else 0.0
    base = max(chars.items(), key=lambda kv: kv[1])[0] if chars else base_by_elements
    travel_l = abs(lstar(g_light) - 50.0)
    travel_d = abs(lstar(g_dark) - 50.0)
    return {
        "ground_light": "#%02X%02X%02X" % tuple(int(round(c)) for c in g_light),
        "ground_dark": "#%02X%02X%02X" % tuple(int(round(c)) for c in g_dark),
        "ink_light": light["body_color"],
        "ground_light_L": round(lstar(g_light), 1),
        "ground_dark_L": round(lstar(g_dark), 1),
        "dark_travel_multiplier": round(travel_d / travel_l, 2) if travel_l > 0.5 else None,
        "ground_chroma": round(chroma(g_light), 3),
        "type_tiers": len(sizes),
        "type_base_px": base,
        "type_base_px_by_element_count": base_by_elements,
        "type_ratio_median": sorted(ratios)[len(ratios) // 2] if ratios else None,
        "type_sizes": ordered,
    }


def main(argv: list[str]) -> int:
    results = {}
    for arg in argv[1:]:
        p = pathlib.Path(arg)
        m = measure_file(p)
        m["derived"] = derive(m)
        results[p.parent.name] = m
    print(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
