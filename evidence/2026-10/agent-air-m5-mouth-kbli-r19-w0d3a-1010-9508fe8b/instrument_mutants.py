"""W0d-3a instrument mutants: each edit is applied to the census or the workflow, the offline suite runs
with -x, and the file is restored before the next one. Run from the repo root; prints one line per mutant."""
import subprocess, sys
from pathlib import Path
C = Path("scripts/mouth/r19_wrapper_token_census.py"); W = Path(".github/workflows/r19-wrapper-census-tests.yml")
M = [
 ("M1 opened all to explorer", C, 'path.startswith("/kbli-explorer")', 'path.startswith("/kbli")'),
 ("M2 list drops SHARED", C, "    for sc in SCENARIOS + SHARED:\n        name, path, which = sc[:3]", "    for sc in SCENARIOS:\n        name, path, which = sc[:3]"),
 ("M3 no missing injection", C, "    for key in missing:\n        kind, name", "    for key in []:\n        kind, name"),
 ("M4 no reorder", C, "            census[k].sort(key=lambda x: want.get(see(x), len(want)))", "            pass"),
 ("M5 load ignores PARTS order", C, "    docs.sort(key=lambda d:", "    sorted(docs, key=lambda d:"),
 ("M6 load overwrites a token", C, "            if prev is None:\n                census[key + \"s\"][name] = row", "            if True:\n                census[key + \"s\"][name] = row"),
 ("M7 no twice", C, '[f"  twice: {k}" for k, n in sorted(got.items()) if n > 1]', '[]'),
 ("M8 no unexpected", C, '+ [f"  unexpected: {k}" for k in sorted(got) if k not in want])', ')'),
 ("M9 check after verdict", C, '    print("\\n".join(received + verdict(census, contract, states)', '    print("\\n".join(verdict(census, contract, states)'),
 ("M10 failed key misparsed", C, '"failed": lambda f: "capture " + f.split(": ", 1)[0],', '"failed": lambda f: "capture " + f.rsplit(": ", 1)[0],'),
 ("M11 empty file crashes", C, "    if not docs:\n        viewports", "    if False:\n        viewports"),
 ("M12 missing never INCOMPLETE on S", C, 'tail = f" (INCOMPLETE: {len(missing)} scenarios not received, not a verdict)" if missing else ""', 'tail = ""'),
 ("M13 colour ties by insertion order", C, 'key=lambda h: (-colors[h]["count"], h))', 'key=lambda h: -colors[h]["count"])'),
 ("M14 a part waits for PAGES only", C, "                              for _, kind, _, how in units))", "                              for _, kind, _, how in units if how[0] in PAGES))"),
 ("W1 matrix drops a part", W, "part: ${{ fromJSON(inputs.parts || '[\"rest\",\"kbli\",\"explorer\",\"shared\"]') }}", "part: ${{ fromJSON(inputs.parts || '[\"rest\",\"kbli\",\"explorer\"]') }}"),
 ("W2 aggregate skipped after a red part", W, "    if: ${{ !cancelled() }}\n", ""),
 ("W3 S line not asserted", W, 'for want in "scenarios-off-manifest: 0" "captures', 'for want in "captures'),
 ("W4 red part not checked", W, '          if [ "$PARTS_RESULT" != success ]; then', '          if false; then'),
 ("W5 aggregate replays one part", W, '--replay "$RUNNER_TEMP/census.jsonl"', '--replay "$RUNNER_TEMP/parts/census-rest.jsonl"'),
]
res = []
for name, f, old, new in M:
    orig = f.read_text()
    assert orig.count(old) == 1, (name, orig.count(old))
    f.write_text(orig.replace(old, new))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "scripts/mouth/tests", "-q", "-x", "-p", "no:cacheprovider", "-k", "not e2e"], capture_output=True, text=True, timeout=600)
        tail = r.stdout.strip().splitlines()[-1]
        failed = [l for l in r.stdout.splitlines() if l.startswith("FAILED")]
        res.append((name, "KILLED" if r.returncode else "SURVIVED", failed[0][7:110] if failed else tail))
    finally:
        f.write_text(orig)
for x in res: print(" | ".join(x))
