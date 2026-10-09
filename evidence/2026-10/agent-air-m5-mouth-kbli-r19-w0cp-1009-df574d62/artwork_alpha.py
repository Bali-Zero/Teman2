#!/usr/bin/env python3
"""Section 8.3: the PNG header of every raster the /kbli* wrapper draws, and whether it has an alpha channel.

  python3 -I artwork_alpha.py REPO_ROOT
"""
import struct
import sys
from pathlib import Path

ASSETS = {
    "explorer sidebar <img>": "apps/mouth/public/images/logo-zantara.png",
    "BZLogo full (/kbli nav)": "apps/mouth/public/assets/logo/balizero-logo-clean.png",
    "BZLogo mark (8.3 ruling)": "apps/mouth/public/assets/logo/balizero-3-red.png",
    "BZLogo round (v2 footer)": "apps/mouth/public/assets/logo/balizero-logo-circle.png",
    "BZLogo zantara": "apps/mouth/public/static/zantara-lotus.png",
}
TYPES = {0: "grey", 2: "RGB", 3: "palette", 4: "grey+alpha", 6: "RGBA"}

root = Path(sys.argv[1])
for where, rel in ASSETS.items():
    head = (root / rel).read_bytes()[:33]
    assert head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR", rel
    w, h, depth, ctype = struct.unpack(">IIBB", head[16:26])
    alpha = ctype in (4, 6)
    print(f"{where}\t{rel}\t{w}x{h}\tcolour type {ctype} ({TYPES.get(ctype, '?')})\t"
          f"{'transparent ground possible' if alpha else 'NO alpha: the file paints its own ground'}")
