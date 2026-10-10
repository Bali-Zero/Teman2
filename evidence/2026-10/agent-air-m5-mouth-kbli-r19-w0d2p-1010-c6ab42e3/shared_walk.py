"""Walks part of the census against a running dev server and prints its verdict.

  python3 shared_walk.py WORKTREE BASE_URL MODE OUT.json [SCENARIO,...]

WORKTREE is the checkout whose census runs (its scripts/mouth). MODE is `shared` (the shared-component pins
only), `shared+kbli-nav` (plus the /kbli mobile nav drawers) or `opened` (the scenarios named, or all).
"""
import json
import sys
from pathlib import Path

worktree, base, mode, out = sys.argv[1:5]
only = set(sys.argv[5].split(",")) if len(sys.argv) > 5 and sys.argv[5] else None
sys.path.insert(0, str(Path(worktree) / "scripts/mouth"))
import r19_wrapper_token_census as c  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

if mode.startswith("shared"):
    keep = {"kbli-mobile-nav", "kbli-code-mobile-nav"} if mode == "shared+kbli-nav" else set()
    c.SCENARIOS[:] = [s for s in c.SCENARIOS if s[0] in keep]
else:
    c.SHARED[:] = []
    if only:
        c.SCENARIOS[:] = [s for s in c.SCENARIOS if s[0] in only]
text = c.CONTRACT.read_text()
rows = c.load_contract(text)
surfaces = c.parse_surfaces(text, rows, c.parse_states(text, rows))
m = c._load_measure()
census: dict = {}
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=m.CHROME)
    c.walk_opened(browser, m, base, census)
    browser.close()
pin = json.loads(c.SHARED_PIN.read_text()) if c.SHARED_PIN.exists() else None
print("\n".join(c.opened_verdict(census, surfaces, rows, pin, [])))
Path(out).write_text(json.dumps(census, indent=1))
