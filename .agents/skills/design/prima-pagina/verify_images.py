import sys, pathlib
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
p=pathlib.Path(sys.argv[1])
# Guilt+innocence: a deliberately broken copy must FAIL this probe, or the probe
# proves nothing. Six mechanical gates passed a page with seven dead images.
broken = p.with_name("_broken_control.html")
broken.write_text(p.read_text().replace("base64,", "base64,data:image/jpeg;base64,", 1))
JS = """() => [...document.images].map(i => ({
  alt: (i.alt||'').slice(0,40),
  ok: i.complete && i.naturalWidth > 1 && i.naturalHeight > 1,
  w: i.naturalWidth, h: i.naturalHeight }))"""
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=CHROME)
    def run(f):
        pg=b.new_page(viewport={"width":390,"height":844})
        pg.goto(f.resolve().as_uri(), wait_until="load"); pg.wait_for_timeout(600)
        pg.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")  # trip lazy loads
        pg.wait_for_timeout(600)
        r=pg.evaluate(JS); pg.close(); return r
    ctrl=run(broken); real=run(p); b.close()
broken.unlink()
cbad=[i for i in ctrl if not i["ok"]]
print(f"CONTROL (deliberately broken): {len(cbad)}/{len(ctrl)} dead -> "
      + ("probe trusted" if cbad else "PROBE BLIND, findings below mean nothing"))
bad=[i for i in real if not i["ok"]]
for i in real: print(f"   {'ok ' if i['ok'] else 'DEAD'} {i['w']:>5}x{i['h']:<5} {i['alt']}")
print(f"-> {len(real)-len(bad)}/{len(real)} images actually decoded")
sys.exit(1 if bad else 0)
