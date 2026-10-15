"""W0d-3b-2b-ii paint receipts (ii-13): for every row that claims a paint relation, plain Chrome, no census code in the
page. At each of the run's five census sample points (centre + four corners inset by min(2, 25%)), it reports the
scrim S's index and the run's own layer i in elementsFromPoint, and the pixel channel delta with vs without the
occluder (display:none, or box-shadow/filter:none when S itself is the reacher), explicitly separated from the
whole-box maximum delta (box_max_delta), plus box_unchanged. Run from the repo root: python3 <this file>."""
import io
import sys

from PIL import Image

sys.path.insert(0, "scripts/mouth/tests")
sys.path.insert(0, "scripts/mouth")
import test_r19_wrapper_token_census as T  # noqa: E402

ROWS = [
    "G-flat-scrim-in-fixed-wrapper", "G-flat-scrim-faded-wrapper", "G-flat-scrim-faded-abs-wrapper",
    "G-reach-glow-scrim-under-run", "G-reach-shadow-scrim-absent", "G-reach-blur-scrim-absent",
    "D-reach-bar-confined-under-surface",
    "G-mix-reach", "G-mix-reach-outside", "G-mix-main", "G-mix-main-outside",
    "G-self-shadow-scrim-absent", "I-self-shadow-scrim-covers",
    "G-two-scrims-wrong-one-covers",
    "G-near-first-reacher-and-toast", "G-near-first-toast-only", "G-two-reachers-exempt-first",
    "I-fixed-scrim-child", "I-blur-scrim-child", "I-scrim-own-opacity", "I-scrim-zindex", "I-scrim-isolate",
    "I-scrim-translate", "I-flat-scrim-itself", "I-reach-scrim-covers-run-fixed", "I-reach-scrim-covers-run-flat",
]
TAG = """() => {
  const vw = innerWidth, vh = innerHeight, cs = (e) => getComputedStyle(e);
  const roots = [...document.querySelectorAll("#s, #d")];
  const all = [...document.querySelectorAll("body *")];
  const scrims = all.filter((e) => { const r = e.getBoundingClientRect();
    return r.width >= vw * 0.95 && r.height >= vh * 0.95 && /^rgba?\\(29, 44, 59/.test(cs(e).backgroundColor)
      && !roots.some((x) => e.contains(x) || x.contains(e)) && !e.textContent.trim(); });
  scrims.forEach((s, k) => s.setAttribute("data-gs", String(k)));
  const self = scrims.find((s) => cs(s).boxShadow !== "none" || cs(s).filter !== "none");
  const occ = all.filter((e) => !scrims.includes(e) && !roots.some((x) => x.contains(e)) && e.id !== "d"
    && (cs(e).backgroundColor === "rgb(29, 44, 59)" || cs(e).filter !== "none" || cs(e).boxShadow !== "none"));
  occ.forEach((e) => e.setAttribute("data-gocc", ""));
  if (self) self.setAttribute("data-gself", "");
  return { scrims: scrims.length, occ: occ.length, self: !!self };
}"""
POINTS = """() => {
  const run = [...document.querySelectorAll("p")].find((e) => e.textContent === "Villa");
  const g = document.createRange(); g.selectNodeContents(run.firstChild);
  const e = run.getBoundingClientRect(), pts = [];
  for (const q of g.getClientRects()) {
    const l = Math.max(q.left, e.left), t = Math.max(q.top, e.top), r = Math.min(q.right, e.right), b = Math.min(q.bottom, e.bottom);
    if (!(r - l > 1 && b - t > 1)) continue;
    const dx = Math.min(2, (r - l) * 0.25), dy = Math.min(2, (b - t) * 0.25);
    pts.push([(l + r) / 2, (t + b) / 2], [l + dx, t + dy], [r - dx, t + dy], [l + dx, b - dy], [r - dx, b - dy]);
  }
  const scrims = [...document.querySelectorAll("[data-gs]")];
  return { box: [e.left, e.top, e.width, e.height], pts: pts.filter(([x, y]) => x >= 0 && y >= 0 && x < innerWidth && y < innerHeight)
    .map(([x, y]) => { const st = document.elementsFromPoint(x, y); let i = -1;
      for (let a = run; a && i < 0; a = a.parentElement) i = st.indexOf(a);
      return { x, y, i, s: scrims.map((s) => st.indexOf(s)) }; }) };
}"""


def shot(page):
    return Image.open(io.BytesIO(page.screenshot())).convert("RGB")


def main() -> None:
    from playwright.sync_api import sync_playwright
    m = T.census_mod._load_measure()
    cases = {c[0]: c for c in T.CASES}
    out = ["row | box_unchanged | point relations (S vs run i at the 5 census points) | census-point deltas [c,tl,tr,bl,br] (max) | whole-box max_delta"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=m.CHROME)
        for rid in ROWS:
            _, body, css, opener, _, _ = cases[rid]
            ctx = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light", reduced_motion="reduce")
            page = ctx.new_page()
            page.set_content(T.PAGE.format(css=css, body=body, tail=""))
            page.evaluate(f"() => {{ {opener} }}")
            page.wait_for_timeout(150)
            page.evaluate(TAG)
            at = page.evaluate(POINTS)
            page.add_style_tag(content="*{color:transparent!important;-webkit-text-fill-color:transparent!important;"
                                       "text-shadow:none!important;caret-color:transparent!important}")
            page.wait_for_timeout(150)
            a = shot(page)
            page.add_style_tag(content="[data-gocc]{display:none!important}[data-gself]{box-shadow:none!important;"
                                       "filter:none!important}")
            page.wait_for_timeout(150)
            b = shot(page)
            after = page.evaluate(POINTS)
            p_deltas, rels = [], []
            for q in at["pts"]:
                xy = (int(q["x"]), int(q["y"]))
                p_deltas.append(max(abs(u - v) for u, v in zip(a.getpixel(xy), b.getpixel(xy))))
                s_list = q["s"]
                rels.append("no-S" if not s_list else "/".join(
                    "absent" if s < 0 else (f"S{s}<i{q['i']}" if s < q["i"] else f"S{s}>i{q['i']}") for s in s_list))
            bx, by, bw, bh = (max(int(v), 0) for v in at["box"])
            crop_a = a.crop((bx, by, bx + max(bw, 1), by + max(bh, 1)))
            crop_b = b.crop((bx, by, bx + max(bw, 1), by + max(bh, 1)))
            box_max = max(max(abs(u - v) for u, v in zip(p1, p2)) for p1, p2 in zip(crop_a.getdata(), crop_b.getdata()))
            out.append(f"{rid} | {at['box'] == after['box']} | {', '.join(rels)} | "
                       f"{p_deltas} (max {max(p_deltas)}) | box_max {box_max}")
            ctx.close()
        browser.close()
    print("\n".join(out))


if __name__ == "__main__":
    main()
