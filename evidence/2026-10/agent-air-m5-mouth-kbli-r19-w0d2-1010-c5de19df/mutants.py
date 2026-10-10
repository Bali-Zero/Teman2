"""Walks the shared pins and the /kbli drawers on the scratch tree once per mutation (I9, A, B, I10), then
writes the fixture the suite replays: each mutation's fingerprints and the grounds the pixels read under
the /kbli drawers' text.

  python3 w0d2-mutants.py WORKTREE BASE_URL FIXTURE_OUT
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

worktree, base, out = sys.argv[1:4]
here = Path(__file__).resolve().parent
fixture = {}
for name in ("I9", "A", "B", "I10"):
    subprocess.run([sys.executable, str(here / "mutate.py"), "revert"], check=True)
    if name != "I9":
        subprocess.run([sys.executable, str(here / "mutate.py"), name], check=True)
    time.sleep(5)
    for route in ("/v2", "/kbli", "/tax-calendar"):  # let the dev server recompile before the walk
        urllib.request.urlopen(base + route, timeout=300).read()
    dump = here / f"w0d2-mutant-{name}.json"
    txt = subprocess.run([sys.executable, str(here / "shared_walk.py"), worktree, base, "shared+kbli-nav", str(dump)],
                         capture_output=True, text=True, check=True).stdout
    (here / f"w0d2-mutant-{name}.txt").write_text(txt)
    census = json.loads(dump.read_text())
    assert not census["shared_failed"], census["shared_failed"]
    assert all(o["state"] == "ok" for o in census["opened"]), [o["state"] for o in census["opened"]]
    fixture[name] = {
        "shared": {f"{s['name']} {s['walk']}": s["fingerprint"] for s in census["shared"]},
        "kbli_painted": sorted({(r["a"], r["text"], f"{o['name']} {o['walk']}") for o in census["opened"]
                                for r in o["runs"] if r["state"] == "ok"}),
    }
    fixture[name]["kbli_painted"] = [{"hex": h, "text": t, "where": w} for h, t, w in fixture[name]["kbli_painted"]]
    print(name, [ln for ln in txt.splitlines() if ln.startswith(("opened-surfaces", "shared-"))], flush=True)
subprocess.run([sys.executable, str(here / "mutate.py"), "revert"], check=True)
Path(out).write_text(json.dumps(fixture, indent=1, sort_keys=True) + "\n")
