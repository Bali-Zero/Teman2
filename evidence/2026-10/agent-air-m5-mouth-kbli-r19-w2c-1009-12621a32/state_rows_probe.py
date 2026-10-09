"""Row-by-row proof of the section 7.1 state table, including rows the census walk never reaches.

The census walk (section 7.5) judges the state classes rendered on the five pages. Modals, search
results, drawers and the chat answer are not rendered there. This probe takes every painted state
row whose class Tailwind generated at this head (a stylesheet rule names it), injects one element
carrying it inside the wrapper on /kbli, drives its state with real input (page.hover, Tab, a
programmatic range for selection), and reads it with the census's own STATE_JS, so the hex is cut
exactly as the census cuts it. The verdict is the census's own judge_states().

  python3 state_rows_probe.py <repo root> <base url> <out.json>
"""
import json
import pathlib
import re
import sys

R, BASE, OUT = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
sys.path.insert(0, str(R / "scripts/mouth"))
import r19_wrapper_token_census as C  # noqa: E402

TEXT = C.CONTRACT.read_text()
STATES = C.parse_states(TEXT, C.parse_contract(TEXT))
M = C._load_measure()

# Where a class can reach the wrapper: the /kbli* fence, plus the components outside it that render
# inside the wrapper (footer, mobile nav, funnel session, lead button, the packages/core shells).
REACH = ["apps/mouth/src/components/kbli", "apps/mouth/src/app/kbli", "apps/mouth/src/app/kbli-explorer",
         "apps/mouth/src/app/v2/_components/Footer.tsx", "apps/mouth/src/app/v2/_components/MobileNav.tsx",
         "apps/mouth/src/components/funnel", "apps/mouth/src/components/lead", "packages/core/components"]


def _reach_text() -> str:
    out = []
    for d in REACH:
        base = R / d
        for p in ([base] if base.is_file() else base.rglob("*.tsx")):
            if ".test." not in p.name:
                out.append(p.read_text())
    return "\n".join(out)


REACH_TEXT = _reach_text()


def reaches(token: str) -> bool:
    return re.search(r"(?<![\w:/\[\]()-])" + re.escape(token) + r"(?![\w/\[\]()-])", REACH_TEXT) is not None


# Ring rows set a width; the colour is the --tw-ring-color of a sibling class. Each is probed
# with the ring colour class it carries in the source, so the reading is the real pairing.
RING_PAIR = {
    "focus:ring-1": "focus:ring-[#D4B483]/30",
    "focus:ring-2": "focus:ring-[#dc2626]",
    "focus-visible:ring-2": "focus-visible:ring-[var(--kbli-accent)]",
}

INJECT = r"""
(rows) => {
  const root = document.querySelector('[data-presentation="r19"]');
  const box = document.createElement("div");
  box.id = "r19-state-probe";
  box.style.cssText = "position:fixed;inset:0 auto auto 0;z-index:2147483647;width:420px;max-height:100vh;overflow:auto;padding:8px";
  const B = "border-width:2px;border-style:solid;display:inline-block;padding:4px;margin:2px";
  const generated = new Set();
  const rules = [];
  const walk = (list) => { for (const r of list) { if (r.selectorText) rules.push(r.selectorText); if (r.cssRules) walk(r.cssRules); } };
  for (const s of document.styleSheets) { try { walk(s.cssRules); } catch (e) {} }
  const made = [];
  rows.forEach(([token, state, cls], i) => {
    const esc = "." + CSS.escape(token);
    if (!rules.some((s) => s.includes(esc))) return;
    generated.add(token);
    const row = document.createElement("div");
    row.dataset.row = String(i);
    const c = cls;
    const html = {
      "hover": `<a href="#p" class="${c}" style="${B}" data-drive>hover ${i}</a>`,
      "group-hover": `<a href="#p" class="group" style="display:inline-block;padding:4px" data-drive><span class="${c}" style="${B}">group ${i}</span></a>`,
      "focus": `<input data-sentinel value="s"><input class="${c}" style="${B}" value="focus ${i}">`,
      "focus-visible": `<input data-sentinel value="s"><input class="${c}" style="${B}" value="fv ${i}">`,
      "focus-within": `<input data-sentinel value="s"><div class="${c}" style="${B}"><input value="fw ${i}"></div>`,
      "group-focus-within": `<input data-sentinel value="s"><div class="group"><span class="${c}" style="${B}">gfw ${i}</span><input value="x"></div>`,
      "group-focus-visible": `<input data-sentinel value="s"><a href="#p" class="group"><span class="${c}" style="${B}">gfv ${i}</span></a>`,
      "selection": `<div class="${c}"><span>selected ${i}</span></div>`,
      "placeholder": `<input class="${c}" placeholder="placeholder ${i}">`,
      "prose-a": `<div class="prose ${c}"><p>para <a href="#p">link ${i}</a></p></div>`,
      "prose-p": `<div class="prose ${c}"><p>para ${i}</p></div>`,
      "prose-strong": `<div class="prose ${c}"><p><strong>strong ${i}</strong></p></div>`,
      "scrollbar": `<div class="${c}" style="overflow:auto;height:24px;width:120px"><div style="height:80px">scroll ${i}</div></div>`,
    }[state];
    row.innerHTML = html;
    box.append(row);
    made.push(i);
  });
  root.append(box);
  return { generated: [...generated], made };
}
"""


# The raw computed value the state paints, so a translucent paint is named even where the
# alpha-dropping hex reads the right role (ruling: state colours are painted opaque).
RAW = r"""
([i, token, state]) => {
  const row = document.querySelector(`#r19-state-probe [data-row="${i}"]`);
  const el = [...row.querySelectorAll("*")].find((e) => e.classList.contains(token));
  const util = token.slice(token.lastIndexOf(":") + 1);
  const kind = util.split("-")[0];
  if (state === "selection") {
    const t = el.querySelector("span"), r = document.createRange();
    r.selectNodeContents(t); getSelection().removeAllRanges(); getSelection().addRange(r);
    const k = kind === "bg" ? "backgroundColor" : "color";
    return [getComputedStyle(el, "::selection")[k], getComputedStyle(t, "::selection")[k]];
  }
  if (state === "placeholder") return [getComputedStyle(el, "::placeholder").color];
  if (state.startsWith("prose-")) return [getComputedStyle(el.querySelector(state.slice(6))).color];
  const cs = getComputedStyle(el);
  if (state === "scrollbar") return [cs.scrollbarColor];
  return [{ bg: cs.backgroundColor, text: cs.color, border: cs.borderTopColor, ring: cs.boxShadow }[kind] ?? cs.color];
}
"""


# Section 5 class rows that are not state variants: one element each, read at rest.
REST = r"""
(rows) => {
  const root = document.querySelector('[data-presentation="r19"]');
  const box = document.createElement("div");
  box.id = "r19-rest-probe";
  root.append(box);
  const rules = [];
  const walk = (list) => { for (const r of list) { if (r.selectorText) rules.push(r.selectorText); if (r.cssRules) walk(r.cssRules); } };
  for (const s of document.styleSheets) { try { walk(s.cssRules); } catch (e) {} }
  const out = {};
  for (const [token, value] of rows) {
    if (!rules.some((s) => s.includes("." + CSS.escape(token)))) { out[token] = null; continue; }
    const el = document.createElement("div");
    el.className = token;
    el.style.cssText = "border-width:2px;border-style:solid;padding:2px";
    el.textContent = "rest";
    box.append(el);
    const cs = getComputedStyle(el);
    if (value.startsWith("type ")) { out[token] = [cs.fontFamily, cs.fontWeight]; continue; }
    const side = (token.match(/^border-([trbl])-/) || [, "t"])[1];
    const prop = token.startsWith("bg-") ? cs.backgroundColor
      : token.startsWith("border-") ? cs.getPropertyValue("border-" + { t: "top", r: "right", b: "bottom", l: "left" }[side] + "-color")
      : cs.color;
    out[token] = [prop];
  }
  return out;
}
"""


def rest_rows(pg) -> dict:
    con = C.parse_contract(TEXT)
    rows = [[t, r["value"]] for (k, t), r in sorted(con.items())
            if k == "class" and t not in STATES and (r["hex"] or r["value"].startswith("type "))]
    raw = pg.evaluate(REST, rows)
    hexes = pg.evaluate(C.STATE_JS, C.STATE_TOKEN) and pg.evaluate(
        "(vals) => Object.fromEntries(Object.entries(vals).map(([k, v]) => [k, v && v.length === 1 ? window.__r19s.hex(v[0]) : null]))",
        raw)
    off, faded, judged = [], [], 0
    elsewhere = []
    for t, value in rows:
        v = raw.get(t)
        if v is None:
            continue
        if not reaches(t):
            elsewhere.append(t)
            continue
        judged += 1
        if value.startswith("type "):
            face, weight = value.split()[1:3]
            fam_ok = face in v[0] if t in ("font-sans", "font-serif", "font-mono") else True
            wt_ok = v[1] == weight if t.startswith("font-") and t not in ("font-sans", "font-serif", "font-mono") else True
            if not (fam_ok and wt_ok):
                off.append(f"  {t}  expected {value}, painted {v}")
            continue
        want = con[("class", t)]["hex"]
        if hexes[t] != want:
            off.append(f"  {t}  expected {want}, painted {hexes[t]} ({v[0]})")
        if re.search(r"/\s*0?\.\d+\s*\)|rgba\([^)]*,\s*0?\.\d+\)", v[0]):
            faded.append(f"  {t}  {v[0]}")
    return {"rows": len(rows), "judged": judged, "not_generated": sorted(t for t, _ in rows if raw.get(t) is None),
            "generated_for_other_pages_only": sorted(elsewhere),
            "off": off, "translucent": faded, "raw": raw}


def main() -> int:
    from playwright.sync_api import sync_playwright

    painted = [(t, r) for t, r in sorted(STATES.items()) if r["hex"]]
    rows = []
    for t, r in painted:
        cls = f"{t} {RING_PAIR[t]}" if t in RING_PAIR else t
        rows.append([t, r["state"], cls])
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=M.CHROME)
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
        pg = ctx.new_page()
        pg.goto(BASE + "/kbli", wait_until="load", timeout=180000)
        pg.wait_for_function("() => document.readyState === 'complete'", timeout=60000)
        pg.wait_for_timeout(1500)
        res = pg.evaluate(INJECT, rows)
        generated = set(res["generated"])
        if not pg.evaluate(C.STATE_JS, C.STATE_TOKEN).get("root"):
            raise SystemExit("wrapper root not found")
        raw = {}
        for i in res["made"]:
            token, state, _ = rows[i]
            sel = f'#r19-state-probe [data-row="{i}"]'
            if state in ("hover", "group-hover"):
                pg.hover(f"{sel} [data-drive]", timeout=5000)
            elif state.startswith(("focus", "group-focus")):
                pg.focus(f"{sel} [data-sentinel]")
                pg.keyboard.press("Tab")
            pg.evaluate("() => window.__r19s.observe()")
            raw[token] = pg.evaluate(RAW, [i, token, state])
            pg.mouse.move(1439, 899)
            pg.evaluate("() => window.__r19s.blur()")
        found = {o["token"]: o for o in pg.evaluate("() => window.__r19s.collect()")}
        pg.reload(wait_until="load")
        pg.wait_for_timeout(1500)
        rest = rest_rows(pg)
        b.close()
    obs = {t: {**found[t], "page": "/kbli", "walk": "desktop/light"} for t in generated if t in found}
    lines, off = C.judge_states({"state_obs": obs}, STATES)
    unseen = sorted(t for t in generated if not (found.get(t) or {}).get("observed"))
    absent = sorted(t for t, _ in painted if t not in generated)
    report = {
        "painted_rows": len(painted),
        "generated_at_head": len(generated),
        "not_generated_at_head": absent,
        "observed": {t: sorted(set(o["observed"])) for t, o in sorted(obs.items())},
        "unseen": unseen,
        "off_contract": lines,
        "raw": raw,
        "rest": rest,
        "translucent": sorted(t for t, v in raw.items() if any(re.search(r"/\s*0?\.\d+\s*\)|rgba\([^)]*,\s*0?\.\d+\)", x) for x in v)),
    }
    OUT.write_text(json.dumps(report, indent=1) + "\n")
    src = "\n".join(p.read_text() for p in (R / "apps/mouth/src").rglob("*.tsx"))
    print(f"painted state rows: {len(painted)} | generated at this head: {len(generated)} "
          f"(of which in a source that renders in the wrapper: {sum(1 for t in generated if reaches(t))}) | "
          f"no stylesheet rule names the class: {len(absent)}")
    for t in absent:
        why = "in the source, no Tailwind rule (variant or plugin missing)" if t in src else "in no apps/mouth source"
        print(f"  not generated {t}: {why}")
    print(f"state-rows-probed-unseen: {len(unseen)}")
    for t in unseen:
        print(f"  {t}")
    print("\n".join(lines))
    print(f"state-rows-probed-translucent: {len(report['translucent'])}")
    for t in report["translucent"]:
        print(f"  {t}  {raw[t]}")
    print(f"state-rows-probed-off-contract: {off}")
    print(f"rest class rows (section 5, no state variant, painted or type): {rest['rows']} | "
          f"judged (generated and in a source that renders in the wrapper): {rest['judged']} | "
          f"generated for other pages only (0 occurrences where the wrapper renders): "
          f"{len(rest['generated_for_other_pages_only'])} | no stylesheet rule: {len(rest['not_generated'])}")
    print(f"rest-rows-probed-translucent: {len(rest['translucent'])}")
    print("\n".join(rest["translucent"]))
    print("\n".join(rest["off"]))
    print(f"rest-rows-probed-off-contract: {len(rest['off'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
