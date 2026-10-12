#!/usr/bin/env python3
"""anti_flatness.py — plan 2026-10-08 §2.4: C1..C10 of briefs/seat.md measured on the RENDERED mockup DOM, 1440x900.
Contrast is measure.py's PROBE_JS with no large-text allowance (every pair >= 4.5:1); content is check_content.
--controls prints the five lines the workflow needs before any verdict (calib good/bad, reference variety, innocence
= the 24 baseline PNGs + pack text, guilt = one verdict word changed). --kit K --stage S --slots a,b prints per set
a C1..C10 row and "<slot> verdict=PASS|FAIL fails=<n>" (a missing screen fails all ten), into K/probes-<stage>.json.
C8 counts verdict cells that own the hit-test at their centre; C10 reads labels and text, not drawn shapes."""
from __future__ import annotations
import argparse, base64, html, io, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
DESIGN = HERE.parents[1] / ".claude/skills/design/strumenti"
sys.path[:0] = [str(HERE), str(DESIGN)]
import measure  # noqa: E402
from content_pack import BASE, check_content, flat  # noqa: E402
from PIL import Image  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

STRICT_JS = measure.PROBE_JS.replace("const need = large ? 3.0 : 4.5;", "const need = 4.5;")
assert STRICT_JS != measure.PROBE_JS, "measure.py changed its contrast rule; re-derive STRICT_JS"
DAY = ("search-results-day", "registry-table-day", "detail-card-day", "dossier-day", "sheet-ledger-day", "chat-day")
SCREENS = DAY + ("detail-card-night", "registry-table-night")
SHAPE_JS = r"""() => {
  const vis = (e) => { const c = getComputedStyle(e), r = e.getBoundingClientRect();
    return c.display !== "none" && c.visibility !== "hidden" && parseFloat(c.opacity) >= 0.1 && r.width > 1 && r.height > 1; };
  const W = innerWidth, H = innerHeight, all = [...document.querySelectorAll("body *")].filter(vis), box = (e) => e.getBoundingClientRect();
  const regions = new Set(all.map(box).filter((r) => r.height >= 0.25 * H && r.width >= 0.1 * W && r.width <= 0.98 * W && r.top < H)
    .map((r) => `${Math.round(r.left / 120)}:${Math.round(r.width / 120)}`));
  const gaps = new Set();
  for (const p of all) { const k = [...p.children].filter(vis).map(box).sort((a, b) => a.top - b.top);
    for (let i = 1; i < k.length; i++) { const g = Math.round((k[i].top - k[i - 1].bottom) / 2) * 2;
      if (g > 0 && k[i].left < k[i - 1].right && k[i - 1].left < k[i].right) gaps.add(g); } }
  const own = (e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
  const law = /garuda|emas\s*2045|lambang\s*negara|pancasila/i;
  const inView = (e) => { const r = box(e); return r.top >= 0 && r.bottom <= H && r.left >= 0 && r.right <= W; };
  document.head.append(Object.assign(document.createElement("style"), { textContent: "[data-pack]{pointer-events:auto!important}" }));
  const hit = (e) => { const r = box(e); return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)?.closest('[data-pack$=".verdict"]') === e; };
  const rows = [...document.querySelectorAll('[data-pack$=".verdict"]')].filter(vis).filter(inView).filter(hit);
  return {
    pack: [...document.querySelectorAll("[data-pack]")].map((e) => [e.dataset.pack, e.innerText]),
    peaks: [...document.querySelectorAll("[data-peak]")].filter(vis).map((e) => box(e).width * box(e).height / (W * H)),
    editorial: [...document.querySelectorAll("[data-editorial]")].filter(vis).length,
    grid: [...regions].sort().join(" ") || "single", gaps: gaps.size,
    display: all.some((e) => own(e) && /fraunces/i.test(getComputedStyle(e).fontFamily) && parseFloat(getComputedStyle(e).fontSize) >= 48),
    rows: new Set(rows.map((e) => e.dataset.pack.split(".")[0])).size,
    law: [...document.querySelectorAll("*")].filter((e) => law.test([e.id, typeof e.className === "string" ? e.className : "",
      e.getAttribute("alt"), e.getAttribute("title"), e.getAttribute("aria-label"), e.tagName === "title" ? e.textContent : ""].join(" "))).length
      + (law.test(document.body.innerText) ? 1 : 0),
  };
}"""


def measure_page(browser, path: Path, accent: bool = True) -> dict:
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(path.resolve().as_uri(), wait_until="load")
    page.wait_for_timeout(400)
    c, s = page.evaluate(STRICT_JS), page.evaluate(SHAPE_JS)
    s.update(contrast=len(c["contrast_failures"]) + len(c["unmeasurable_over_image"]), sizes=len(c["font_sizes"]),
             hscroll=c["horizontal_scroll"])
    if accent:
        page.add_style_tag(content="[data-pma], [data-pma] * { visibility: hidden !important; }")
        img = Image.open(io.BytesIO(page.screenshot())).convert("RGB").resize((360, 225), Image.NEAREST).convert("HSV")
        s["accent"] = sum(1 for h, sat, v in zip(*[iter(img.tobytes())] * 3) if 6 <= h <= 36 and sat >= 90 and v >= 64) / (360 * 225)
    page.close()
    return s


def judge(m: dict[str, dict], pack: dict) -> dict[str, bool]:
    grids = [m[d]["grid"] for d in DAY]
    every = lambda f: all(f(x) for x in m.values())
    return {"C1": every(lambda x: len(x["peaks"]) == 1 and x["peaks"][0] <= 0.25),
            "C2": len(set(grids)) >= 3 and all(a != b for a, b in zip(grids, grids[1:])),
            "C3": every(lambda x: x["sizes"] >= 4) and all(m[s]["display"] for s in ("detail-card-day", "dossier-day", "detail-card-night")),
            "C4": every(lambda x: x["editorial"] == 1), "C5": every(lambda x: x.get("accent", 0) <= 0.08),
            "C6": every(lambda x: x["gaps"] >= 3), "C7": every(lambda x: x["contrast"] == 0 and not x["hscroll"]),
            "C8": m["registry-table-day"]["rows"] >= 12 and m["registry-table-night"]["rows"] >= 12,
            "C9": not check_content(pack, [tuple(p) for x in m.values() for p in x["pack"]]),
            "C10": every(lambda x: x["law"] == 0)}


def wrap(png: Path, pack: dict, tamper: str | None, out: Path) -> Path:
    spans = "".join(f'<div><span data-pack="{k}">{html.escape("TERBUKA" if k == tamper else v)}</span></div>'
                    for k, v in flat(pack["codes"]).items())
    out.write_text(f'<!doctype html><meta charset="utf-8"><body style="margin:0;background:#F7F4EE;color:#1D2C3B;font:15px sans-serif">'
                   f'<img style="display:block;width:1440px" src="data:image/png;base64,{base64.b64encode(png.read_bytes()).decode()}">'
                   f'<section style="white-space:pre-wrap">{spans}</section>', encoding="utf-8")
    return out


def baseline_set(b, app: Path, pack: dict, theme: str, lang: str, tamper: str | None, tmp: Path) -> dict[str, bool]:
    m = {f"{s}-day": measure_page(b, wrap(app / BASE / f"{s}-{theme}-{lang}.png", pack, tamper,
                                          tmp / f"{tamper or 'innocence'}-{s}-{theme}-{lang}.html"), accent=False)
         for s in ("search-results", "registry-table", "detail-card", "dossier", "sheet-ledger", "chat")}
    m["detail-card-night"], m["registry-table-night"] = m["detail-card-day"], m["registry-table-day"]
    return judge(m, pack)


def controls(kit: Path, app: Path) -> list[str]:
    pack, tmp = json.loads((kit / "content-pack.json").read_text(encoding="utf-8")), kit / "controls"
    tmp.mkdir(exist_ok=True)
    pf = lambda ok: "PASS" if ok else "FAIL"
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=measure.CHROME)
        out = [f"calib {n} contrast={pf(measure_page(b, DESIGN / 'controlli-di-calibrazione' / n / 'ui.html', False)['contrast'] == 0)}"
               for n in ("good", "bad")]
        grids = []
        for i, cols in enumerate(([360, 1000], [400, 400, 400], [1000], [1000, 360], [300, 700, 300], [1200])):
            f = tmp / f"reference-{i}.html"
            f.write_text('<!doctype html><meta charset="utf-8"><body style="margin:0;display:flex;gap:20px;justify-content:center">'
                         + "".join(f'<div style="width:{w}px;height:700px;background:#EAE3D8"></div>' for w in cols), encoding="utf-8")
            grids.append(measure_page(b, f, accent=False)["grid"])
        out.append(f"reference variety={pf(len(set(grids)) >= 3 and all(x != y for x, y in zip(grids, grids[1:])))}")
        seen = {f"variety={pf(j['C2'])} content={pf(j['C9'])}" for j in
                (baseline_set(b, app, pack, t, lg, None, tmp) for t in ("day", "night") for lg in ("en", "id"))}
        out.append("innocence " + " | ".join(sorted(seen)))
        out.append(f"guilt content={pf(baseline_set(b, app, pack, 'day', 'en', '51101.verdict', tmp)['C9'])}")
        b.close()
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kit", type=Path, required=True)
    ap.add_argument("--app", type=Path, default=Path.home() / "kbli-navigator-app")
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--stage", choices=("r1", "repair"), default="r1")
    ap.add_argument("--slots", default="a,b,c")
    a = ap.parse_args(argv)
    if a.controls:
        return print("\n".join(controls(a.kit, a.app))) or 0
    pack, report = json.loads((a.kit / "content-pack.json").read_text(encoding="utf-8")), {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=measure.CHROME)
        for slot in a.slots.split(","):
            d = a.kit / "mockups" / slot / a.stage
            missing = [s for s in SCREENS if not (d / f"{s}.html").is_file()]
            m = {} if missing else {s: measure_page(b, d / f"{s}.html") for s in SCREENS}
            j = {f"C{i}": False for i in range(1, 11)} if missing else judge(m, pack)
            report[slot] = {"criteria": j, "missing": missing, "screens": m,
                            "content": check_content(pack, [tuple(p) for x in m.values() for p in x["pack"]]) if m else []}
            print(f"{slot} " + " ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in j.items()))
            print(f"{slot} verdict={'PASS' if all(j.values()) else 'FAIL'} fails={sum(not v for v in j.values())}")
        b.close()
    (a.kit / f"probes-{a.stage}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
