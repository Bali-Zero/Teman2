"""The /v2 non-R19 drawer: its computed ground, what the old DOM composite read, and what the pixels read."""
import sys
from pathlib import Path

wt, base = sys.argv[1:3]
sys.path.insert(0, str(Path(wt) / "scripts/mouth"))
import r19_wrapper_token_census as c  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

m = c._load_measure()
JS = """() => { const d = document.querySelector('[role="dialog"]'); const a = d.querySelector('ul a');
  const s = getComputedStyle(d), t = getComputedStyle(a);
  return {drawer: s.backgroundColor, backdrop: s.backdropFilter, item: t.backgroundColor,
          body: getComputedStyle(document.body).backgroundColor, theme: document.documentElement.getAttribute('data-theme')}; }"""
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=m.CHROME)
    for tname in ("light", "system-dark"):
        scheme, forced = m.THEMES[tname]
        ctx = b.new_context(viewport={"width": 390, "height": 844}, color_scheme=scheme)
        ctx.add_init_script(c.FREEZE_JS)
        page = ctx.new_page()
        page.goto(base + "/v2", wait_until="load", timeout=180000)
        if forced:
            page.evaluate("t => document.documentElement.setAttribute('data-theme', t)", forced)
        page.wait_for_timeout(1500)
        c._open_mobile_nav(page)
        page.add_style_tag(content="*,*::before,*::after{transition:none!important;animation:none!important}")
        page.wait_for_timeout(2500)
        info = page.evaluate(JS)
        res = c.resolve(page, "shared", ['[role="dialog"]'])
        home = next(r for r in res["runs"] if r["text"] == "Home")
        print(tname, info, "| Home: A", home["a"], "spread", home["spread"], "B", home["b"], "approx", home["approx"],
              "painter", home["painter"], "| root", res["rootGround"])
        ctx.close()
    b.close()
