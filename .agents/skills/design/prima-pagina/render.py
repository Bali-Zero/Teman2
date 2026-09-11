import sys, pathlib, json
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
src = pathlib.Path(sys.argv[1]); out = pathlib.Path(sys.argv[2]); out.mkdir(exist_ok=True)

# The widget-answered shots exist because a still of an interactive element in its
# EMPTY state shows the chrome, not the product. What the visitor is promised is
# the answer, so at least one shot must contain one.
STATES = [
 ("phone-day",       390, 844, "light",  "neutral", None),
 ("phone-night",     390, 844, "dark",   "neutral", None),
 ("phone-night-answered", 390, 844, "dark", "neutral", ("year","remote")),
 ("phone-day-answered",   390, 844, "light","neutral", ("30",None)),
 ("phone-oxblood",   390, 844, "dark",   "oxblood", ("year","company")),
 ("desktop-day",    1280, 900, "light",  "neutral", None),
 ("desktop-night",  1280, 900, "dark",   "neutral", ("180",None)),
 # Two diagnostics, not designs. Greyscale proves nothing on the page carries
 # meaning by hue alone; the sunlight pass approximates a phone held outdoors
 # at midday in Bali, which is where this page is actually read.
 ("diagnostic-greyscale", 390, 844, "light", "neutral", ("60",None), "grayscale(1)"),
 ("diagnostic-sunlight",  390, 844, "light", "neutral", ("60",None),
   "contrast(.62) brightness(1.22)"),
]
made=[]
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=CHROME)
    for st in STATES:
        name,w,h,theme,night,drive = st[:6]
        css_filter = st[6] if len(st) > 6 else None
        pg=b.new_page(viewport={"width":w,"height":h}, device_scale_factor=2,
                      color_scheme="dark" if theme=="dark" else "light")
        pg.goto(src.resolve().as_uri(), wait_until="load")
        pg.evaluate(f"() => {{document.documentElement.setAttribute('data-theme','{theme}');"
                    f"document.documentElement.setAttribute('data-night','{night}');}}")
        if drive:
            d,why = drive
            pg.click(f'#dur button[data-k="{d}"]')
            if why: pg.wait_for_timeout(80); pg.click(f'#why button[data-k="{why}"]')
        if css_filter:
            pg.add_style_tag(content=f'html{{filter:{css_filter}}}')
        pg.wait_for_timeout(500)
        f=out/f"{name}.png"; pg.screenshot(path=str(f), full_page=True)
        made.append((name, f.stat().st_size)); pg.close()
    b.close()
for n,s in made: print(f"{n:<24} {s/1024:7.1f} KB")
