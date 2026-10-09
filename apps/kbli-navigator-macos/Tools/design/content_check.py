#!/usr/bin/env python3
"""content_check.py [--pack PATH] < contenttest.json  (Python 3.9, stdlib; dataset from env KBLI_JSON).
Compares every leaf of the frozen content pack with what the app produced, byte for byte; authority
arrays after an order-keeping collapse of exact repeats; 51101 heads_up = the canonical pair."""
import json, os, sys
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
args = sys.argv[1:]
pack = json.load(open(args[args.index("--pack") + 1] if "--pack" in args else root + "/docs/design/content-pack-2026-10-09.json"))
app = json.load(sys.stdin)
diffs = []
def collapse(xs): return [x for i, x in enumerate(xs) if x not in xs[:i]]
def walk(p, a, b, key=""):
    if key == "authority" and isinstance(a, list) and isinstance(b, list): a, b = collapse(a), collapse(b)
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)): walk(p + "." + k, a.get(k, "<absent>"), b.get(k, "<absent>"), k)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)): walk("%s[%d]" % (p, i), x, y, key)
    elif a != b: diffs.append("DIFF %s: pack=%r app=%r" % (p[1:], a, b))
ds = json.load(open(os.environ["KBLI_JSON"]))["data"]
for code in pack["frozen"]:
    want, got = pack["codes"][code], app["codes"].get(code, {})
    if code == "51101":
        rec = [r for r in ds if r["kode_kbli_2025"] == code][0]
        canon = ["%s · %s%%" % (want["verdict"], want["cap"]), rec["pma_kondisi"]]
        for lang in ("en", "id"):
            if got.get(lang, {}).get("heads_up") != canon: diffs.append("DIFF 51101.%s.heads_up: want canonical %r app=%r" % (lang, canon, got.get(lang, {}).get("heads_up")))
            if want[lang]["heads_up"] == canon: diffs.append("DIFF 51101.%s.heads_up: pack pair equals canonical (expected the open pair)" % lang)
            want[lang].pop("heads_up"); got.get(lang, {}).pop("heads_up", None)
    walk("." + code, want, got)
diffs += ["DIFF balanced_rejoin.%s: false" % c for c, ok in app.get("balanced_rejoin", {}).items() if not ok]
diffs += ["DIFF probe: " + v for v in app.get("probe_violations", [])]
print("\n".join(diffs) if diffs else "content: 3 frozen codes identical (51101 heads-up = canonical pair)")
sys.exit(1 if diffs else 0)
