"""Writes the shared-component pin from a census --json dump: one entry per pinned walk, its fingerprint.

  python3 w0d2p-regen-pin.py DUMP.jsonl PIN.json
"""
import json
import sys
from pathlib import Path

dump, out = sys.argv[1:3]
pin = {}
for ln in Path(dump).read_text().splitlines():
    d = json.loads(ln)
    if "shared" in d and "fingerprint" in d:
        pin[f"{d['name']} {d['walk']}"] = d["fingerprint"]
assert len(pin) == 24, len(pin)
Path(out).write_text(json.dumps(dict(sorted(pin.items())), indent=2) + "\n")
print(len(pin), "entries")
