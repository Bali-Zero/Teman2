"""Walks only the shared pins (plus, on request, the /kbli mobile nav drawers) of the W0d-1 census."""
import json
import sys

sys.path.insert(0, "/Users/balizero/nuzantara/.worktrees/mouth-kbli-r19-w0d1-1010/scripts/mouth")
import r19_wrapper_token_census as c  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

base, mode, out = sys.argv[1], sys.argv[2], sys.argv[3]
keep = {"kbli-mobile-nav", "kbli-code-mobile-nav"} if mode == "shared+kbli-nav" else set()
c.SCENARIOS[:] = [s for s in c.SCENARIOS if s[0] in keep]
text = c.CONTRACT.read_text()
k = c.load_contract(text)
su = c.parse_surfaces(text, k, c.parse_states(text, k))
m = c._load_measure()
census: dict = {}
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=m.CHROME)
    c.walk_opened(b, m, base, census)
    b.close()
pin = json.loads(c.SHARED_PIN.read_text()) if c.SHARED_PIN.exists() else None
for line in c.opened_verdict(census, su, k, pin, []):
    print(line)
with open(out, "w") as f:
    json.dump(census, f, indent=1)
