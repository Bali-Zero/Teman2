"""Keyboard-focus walk on /kbli and /kbli/55203 (desktop, light and forced-dark).

For the Zantara chat textarea and the search input it presses Tab from the top of the
page until the element is the active element, then asserts that something visible changed
between the resting and the focused snapshot of the element and its three nearest
ancestors: border colour, outline, box-shadow or background. Exit 1 if either target
shows no change or never receives focus-visible.
"""
import importlib.util
import pathlib
import sys

R = pathlib.Path(sys.argv[1])
BASE = sys.argv[2]
sp = importlib.util.spec_from_file_location(
    "measure", R / ".claude/skills/design/strumenti/measure.py"
)
M = importlib.util.module_from_spec(sp)
sp.loader.exec_module(M)
from playwright.sync_api import sync_playwright

SNAP = """(el)=>{const out=[];let n=el;for(let i=0;i<4&&n&&n.nodeType===1;i++,n=n.parentElement){const c=getComputedStyle(n);out.push([c.borderTopColor,c.borderTopWidth,(c.outlineStyle==='none'?'none':c.outlineStyle+c.outlineWidth+c.outlineColor),c.boxShadow,c.backgroundColor].join('|'))}return out}"""
TARGETS = {"chat textarea": "textarea", "search input": "#search input"}
bad = []
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=M.CHROME)
    for path in ("/kbli", "/kbli/55203"):
        for scheme, forced in (("light", None), ("light", "dark")):
            ctx = b.new_context(viewport={"width": 1440, "height": 900}, color_scheme=scheme)
            pg = ctx.new_page()
            pg.goto(BASE + path, wait_until="load", timeout=180000)
            pg.wait_for_timeout(400)
            if forced:
                pg.evaluate("t=>document.documentElement.setAttribute('data-theme',t)", forced)
            pg.wait_for_timeout(1500)
            for name, sel in TARGETS.items():
                tag = f"{path} {forced or 'light'} {name}"
                el = pg.query_selector(sel)
                if not el:
                    if path == "/kbli/55203" and name == "search input":
                        continue
                    bad.append(f"{tag}: element not found")
                    continue
                rest = el.evaluate(SNAP)
                pg.evaluate("()=>{document.activeElement&&document.activeElement.blur();window.scrollTo(0,0)}")
                hit = False
                for _ in range(300):
                    pg.keyboard.press("Tab")
                    if pg.evaluate("(s)=>document.activeElement===document.querySelector(s)", sel):
                        hit = True
                        break
                if not hit:
                    bad.append(f"{tag}: Tab never reached it")
                    continue
                pg.wait_for_timeout(600)
                fv = el.evaluate("e=>e.matches(':focus-visible')")
                foc = el.evaluate(SNAP)
                changed = [i for i, (a, c) in enumerate(zip(rest, foc)) if a != c]
                line = f"{tag}: focus-visible={fv} changed-levels={changed}"
                print(line)
                if not fv or not changed:
                    bad.append(line)
            ctx.close()
    b.close()
print("TAB-WALK:", "FAIL" if bad else "PASS")
for x in bad:
    print("  ", x)
sys.exit(1 if bad else 0)
