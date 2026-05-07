#!/usr/bin/env python3
"""Convert Chrome devtools cookie dump into Playwright storage_state.json."""
import json
import sys
from pathlib import Path

SRC = Path("/Users/nuzantara/.notebooklm-mcp-cli/profiles/default/cookies.json")
DST = Path("/tmp/nlm-py-spike/storage_state.json")


def main() -> int:
    cookies_raw = json.loads(SRC.read_text())
    if not isinstance(cookies_raw, list):
        print("FAIL: cookies.json is not a list")
        return 1
    cookies_pw = []
    for c in cookies_raw:
        # Playwright accepts: name, value, domain, path, expires, httpOnly, secure, sameSite
        # Map sameSite chrome → playwright (Lax/Strict/None)
        same_site = c.get("sameSite", "Lax")
        if same_site not in ("Strict", "Lax", "None"):
            same_site = "Lax"
        cookies_pw.append({
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c.get("path", "/"),
            "expires": c.get("expires", -1),
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
            "sameSite": same_site,
        })
    storage = {"cookies": cookies_pw, "origins": []}
    DST.write_text(json.dumps(storage, indent=2))
    print(f"Wrote {DST} with {len(cookies_pw)} cookies")
    return 0


if __name__ == "__main__":
    sys.exit(main())
