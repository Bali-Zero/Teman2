"""Colour class tokens in the /kbli* fence sources that neither contract table names, with the reason
each one is outside the contract: where it renders, and whether the five walked pages render it.

  python3 unmapped_scan.py <repo root> <out.tsv> [<base url>]
"""
import pathlib
import re
import sys

R, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
sys.path.insert(0, str(R / "scripts/mouth"))
import r19_wrapper_token_census as C  # noqa: E402

TEXT = C.CONTRACT.read_text()
CON = C.parse_contract(TEXT)
ST = C.parse_states(TEXT, CON)
CLASSES = {t for k, t in CON if k == "class"}
DIRS = ["apps/mouth/src/components/kbli", "apps/mouth/src/app/kbli", "apps/mouth/src/app/kbli-explorer"]
UTIL = re.compile(r"^(?:[a-z-]+(?:-\[[^\]]+\])?:)*!?(bg|text|border(?:-[trblxy])?|ring|outline|from|via|to|fill|stroke|"
                  r"decoration|divide|placeholder|caret|accent|shadow)-(.+)$")
COLOUR_WORD = re.compile(r"^(white|black|silver|destructive|primary|muted|foreground|"
                         r"(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|"
                         r"indigo|violet|purple|fuchsia|pink|rose)-\d+|accent-[a-z-]+|surface-[a-z-]+)(/.+)?$")
SIZE = re.compile(r"^(xs|sm|base|lg|xl|\d?xl|left|center|right|justify|start|end|wrap|nowrap|balance|pretty|ellipsis|clip|"
                  r"solid|dashed|dotted|double|none|hidden|inner|inset|offset-\d+|\d+|\[\d+(\.\d+)?(px|rem|em|%)\]|"
                  r"collapse|separate|t|b|l|r|x|y)$")


def colour_value(v: str) -> bool:
    if SIZE.match(v):
        return False
    if v.startswith("["):
        return bool(re.search(r"#|rgb|hsl|var\(|color-mix|oklch|color:", v))
    return bool(COLOUR_WORD.match(v))


hits: dict[str, set[str]] = {}
for d in DIRS:
    for p in sorted((R / d).rglob("*.tsx")):
        if ".test." in p.name:
            continue
        for tok in re.findall(r"[^\s\"'`{}()]+(?:\([^\s\"'`{}]*\))?[^\s\"'`{}]*", p.read_text()):
            tok = tok.strip(",;")
            m = UTIL.match(tok)
            if not m or not colour_value(m.group(2)):
                continue
            if tok in CLASSES or tok in ST:
                continue
            hits.setdefault(tok, set()).add(str(p.relative_to(R / "apps/mouth/src")))
# Where each file's markup renders: the contract's section 2 limits name these surfaces.
SURFACE = {
    "error.tsx": "route error boundary (renders only when the page throws)",
    "ComparisonModal.tsx": "explorer comparison modal (after a click)",
    "BlackBookModal.tsx": "explorer Black Book modal (after a click)",
    "LegacyAlert.tsx": "explorer legacy-code alert (after a search that hits a 2020 code)",
    "KBLIInspector.tsx": "explorer inspector panel (after a result is opened)",
    "ThinkingIndicator.tsx": "explorer thinking indicator (while an answer streams)",
    "KBLISearch.tsx": "/kbli search dropdown (after a query)",
    "KBLISectorOffcanvas.tsx": "sector drawer (after a click)",
    "ZantaraChat.tsx": "chat bubbles (after a message is sent)",
    "KBLISectorStrip.tsx": "sector strip arrows and active chip (scroll and selection states)",
    "KBLISectorBrowser.tsx": "sector browser tabs (inactive-tab edge)",
    "TransitionBadge.tsx": "transition badge variant not used by the walked codes",
    "LicensingSection.tsx": "licensing rows for codes not among the walked ones",
    "ProvenanceBadge.tsx": "provenance badge variant not used by the walked codes",
    "KBLIPanelCodeDetail.tsx": "sector panel code detail (intercepted route, after a click)",
    "KBLISectorTable.tsx": "sector table view (after the Table toggle)",
    "page.tsx": "page branch the walk does not render (results, inspector, sector or code variants)",
}
dom: dict[str, dict] = {}
if len(sys.argv) > 3:
    from playwright.sync_api import sync_playwright
    M = C._load_measure()
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=M.CHROME)
        for page in C.PAGES:
            pg = b.new_page(viewport={"width": 1440, "height": 900})
            pg.goto(sys.argv[3] + page, wait_until="load", timeout=180000)
            pg.wait_for_timeout(1500)
            got = pg.evaluate("""(tokens) => {
              const root = document.querySelector('[data-presentation="r19"]');
              const rules = [];
              const walk = (l) => { for (const r of l) { if (r.selectorText) rules.push(r.selectorText); if (r.cssRules) walk(r.cssRules); } };
              for (const s of document.styleSheets) { try { walk(s.cssRules); } catch (e) {} }
              return Object.fromEntries(tokens.map((t) => [t, {
                rendered: [root, ...root.querySelectorAll("*")].filter((e) => e.classList && e.classList.contains(t)).length,
                rule: rules.some((s) => s.includes("." + CSS.escape(t)))}]));
            }""", sorted(hits))
            for t, v in got.items():
                d = dom.setdefault(t, {"rendered_on": [], "rule": False})
                d["rule"] = d["rule"] or v["rule"]
                if v["rendered"]:
                    d["rendered_on"].append(page)
            pg.close()
        b.close()
rows = ["class_not_in_contract\tfiles\trendered_on_walked_pages\tstylesheet_rule\treason"]
for t, fs in sorted(hits.items()):
    d = dom.get(t, {})
    where = sorted({SURFACE.get(f.split("/")[-1], "unclassified") for f in fs})
    on = ",".join(d.get("rendered_on", [])) or "none"
    rule = "yes" if d.get("rule") else "no" if d else "not checked"
    why = "; ".join(where)
    if d and not d["rule"]:
        why = "no stylesheet rule: the class paints nothing (Tailwind has no such colour); " + why
    rows.append(f"{t}\t{','.join(sorted(fs))}\t{on}\t{rule}\t{why}")
OUT.write_text("\n".join(rows) + "\n")
print(f"unmapped colour classes in the fence: {len(hits)}")
if dom:
    shown = [t for t, d in dom.items() if d["rendered_on"]]
    print(f"rendered on the five walked pages (desktop/light): {len(shown)}")
    for t in shown:
        print(f"  {t}  rule={dom[t]['rule']}  on {','.join(dom[t]['rendered_on'])}")
