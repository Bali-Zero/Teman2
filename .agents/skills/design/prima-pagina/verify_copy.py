import sys, re, pathlib
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

# the live-site blocklist + the GARUDA charter's klaim terlarang, as ENTITIES not spellings
BLOCK = [
 (r"\b(?:no\.?\s*)?#\s*1\b|\bnumber one\b|\bnumero uno\b", "rank superlative"),
 (r"\bbest\b|\bleading\b|\btop[- ]rated\b|\bpremier\b", "rank superlative"),
 (r"\bofficial (?:partner|reseller|agent)\b|\bauthori[sz]ed partner\b", "affiliation claim"),
 (r"\bguarantee\w*\b|\bdijamin\b|\b100%\s*(?:approval|success)\b", "outcome guarantee"),
 (r"\bfastest\b|\b24[- ]hour(?:s)? guarantee\b|\bsame[- ]day guaranteed\b", "speed guarantee"),
 (r"\bzero risk\b|\brisk[- ]free\b|\bno risk\b", "risk claim"),
 (r"\btrusted by \d|\b\d[\d,]*\+? (?:happy )?clients since\b", "unsourced lifetime total"),
 (r"\bwork remotely (?:on|with) (?:a )?b211\b", "B1/B211 work claim"),
]
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=CHROME)
    pg=b.new_page(viewport={"width":390,"height":844})
    pg.goto(p.resolve().as_uri(), wait_until="load"); pg.wait_for_timeout(300)

    # drive every branch of the answer widget and collect what it says
    said=[]
    for d in ["30","60","180"]:
        pg.click(f'#dur button[data-k="{d}"]'); pg.wait_for_timeout(80)
        said.append((d, pg.inner_text("#ans-code"), pg.inner_text("#ans-name")))
    for w in ["tourism","remote","company","retire"]:
        pg.click('#dur button[data-k="year"]'); pg.wait_for_timeout(50)
        assert not pg.is_hidden("#why"), "reason row never appeared"
        pg.click(f'#why button[data-k="{w}"]'); pg.wait_for_timeout(80)
        assert not pg.is_hidden("#ans"), f"no answer for year|{w}"
        said.append((f"year|{w}", pg.inner_text("#ans-code"), pg.inner_text("#ans-name")))
    print("WIDGET — all 7 branches answered:")
    for k,c,n in said: print(f"   {k:<14} {c:<6} {n}")

    text = pg.evaluate("() => document.body.innerText")
    b.close()

print("\nBLOCKLIST")
hits=0
for pat,why in BLOCK:
    for m in re.finditer(pat, text, re.I):
        s=max(0,m.start()-40); print(f"   HIT [{why}] ...{text[s:m.end()+40]!r}"); hits+=1
print("   clean" if not hits else f"   {hits} hit(s)")
