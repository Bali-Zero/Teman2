"""SPEC-3b2bi r1 paint receipts: for every row that claims a paint relation, plain Chrome, no census code in the
page. The run's text is made transparent, the pixels under the run's box are read with and without the occluder
(a fixed bar with a filter or a shadow, or an opaque ink bar), and the largest channel difference is reported
(delta). It also reports, at the run's centre, the index of the scrim S and of the run's own layer in
elementsFromPoint (S above the run when S < run). Run from the repo root: python3 <this file>."""
import io
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, "scripts/mouth/tests")
sys.path.insert(0, "scripts/mouth")
import test_r19_wrapper_token_census as T  # noqa: E402

GUILT = ["G-flat-scrim-in-fixed-wrapper", "G-flat-scrim-faded-wrapper", "G-flat-scrim-faded-abs-wrapper",
         "G-reach-glow-scrim-under-run", "G-reach-shadow-scrim-absent", "G-reach-blur-scrim-absent",
         "D-reach-bar-confined-under-surface"]
INNOCENT = ["I-fixed-scrim-child", "I-blur-scrim-child", "I-scrim-own-opacity", "I-scrim-zindex", "I-scrim-isolate",
            "I-scrim-translate", "I-flat-scrim-itself", "I-reach-scrim-covers-run-fixed", "I-reach-scrim-covers-run-flat"]
JS_TAG = """() => {
  const vw = innerWidth, vh = innerHeight, cs = (e) => getComputedStyle(e);
  const run = [...document.querySelectorAll("p")].find((e) => e.textContent === "Villa");
  const all = [...document.querySelectorAll("body *")];
  const scrim = all.find((e) => { const r = e.getBoundingClientRect(), c = cs(e).backgroundColor;
    return r.width >= vw * 0.95 && r.height >= vh * 0.95 * 0.95 && /^rgba\\(29, 44, 59/.test(c) && !e.textContent.trim(); });
  const bars = all.filter((e) => cs(e).backgroundColor === "rgb(29, 44, 59)"
    || (cs(e).position === "fixed" && (cs(e).filter !== "none" || cs(e).boxShadow !== "none")));
  bars.forEach((e) => e.setAttribute("data-occ", "1"));
  if (scrim) scrim.setAttribute("data-s", "1");
  const r = run.getBoundingClientRect();
  return { x: r.left, y: r.top, w: r.width, h: r.height, hasS: !!scrim, bars: bars.length };
}"""
JS_STACK = """() => {
  const run = [...document.querySelectorAll("p")].find((e) => e.textContent === "Villa");
  const r = run.getBoundingClientRect(), st = document.elementsFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  const s = document.querySelector("[data-s]");
  return { s: s ? st.indexOf(s) : -2, i: st.findIndex((e) => e.contains(run)) };
}"""


def shot(page, clip):
    return Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")


def main() -> None:
    from playwright.sync_api import sync_playwright
    m = T.census_mod._load_measure()
    rows = {c[0]: c for c in T.CASES}
    out = ["row | S index at the run's centre / run's own layer | max delta with vs without the occluder"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=m.CHROME)
        for rid in GUILT + INNOCENT:
            _, body, css, opener, _, _ = rows[rid]
            page = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light",
                                       reduced_motion="reduce").new_page()
            page.set_content(T.PAGE.format(css=css, body=body, tail=""))
            page.evaluate(f"() => {{ {opener} }}")
            box = page.evaluate(JS_TAG)
            stack = page.evaluate(JS_STACK)
            page.add_style_tag(content="*{color:transparent!important;caret-color:transparent}")
            page.wait_for_timeout(100)
            clip = {"x": max(box["x"], 0), "y": max(box["y"], 0), "width": max(box["w"], 1), "height": max(box["h"], 1)}
            with_occ = shot(page, clip)
            page.add_style_tag(content="[data-occ]{display:none!important}")
            page.wait_for_timeout(100)
            without = shot(page, clip)
            delta = max(max(abs(a - b) for a, b in zip(p1, p2)) for p1, p2 in zip(with_occ.getdata(), without.getdata()))
            where = "S absent" if stack["s"] == -1 else ("no S" if stack["s"] == -2 else
                    f"S {stack['s']} {'above' if stack['s'] < stack['i'] else 'UNDER'} run {stack['i']}")
            out.append(f"{rid} | {where} | delta {delta} ({box['bars']} occluder element(s))")
            page.context.close()
        browser.close()
    print("\n".join(out))


if __name__ == "__main__":
    main()
