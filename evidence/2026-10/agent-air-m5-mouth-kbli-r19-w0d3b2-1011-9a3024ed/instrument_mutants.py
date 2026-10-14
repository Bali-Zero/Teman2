"""W0d-3b-2a instrument mutants: each edit undoes one change, the rows run with -x (through the real walks for M,
offline for S), and the file is restored before the next one. Run from the repo root, with no census server
running; prints one line per mutant."""
import subprocess, sys
from pathlib import Path
C = Path("scripts/mouth/r19_wrapper_token_census.py")
OFF = '"*,*::before,*::after{transition:none!important;animation:none!important}"'
M = [
 ("M1 no reduced motion", 'color_scheme=scheme, reduced_motion="reduce")', "color_scheme=scheme)"),
 ("M2 motion removed at rest", '    page.add_style_tag(content=NO_MOTION)\n    page.wait_for_timeout(SETTLE["scroll"])',
  f'    page.add_style_tag(content={OFF})\n    page.wait_for_timeout(SETTLE["scroll"])'),
 ("M3 motion removed on an opened surface", '    page.add_style_tag(content=NO_MOTION)\n    page.wait_for_timeout(SETTLE["open"])',
  f'    page.add_style_tag(content={OFF})\n    page.wait_for_timeout(SETTLE["open"])'),
 ("M4 finished motion forces its end state", '"animation-delay:0s!important;animation-iteration-count:1!important}")',
  '"animation-delay:0s!important;animation-iteration-count:1!important;animation-fill-mode:forwards!important}")'),
 ("M5 the state walk removes motion", '  style.textContent = "*,*::before,*::after{transition:none!important;animation-duration:0s!important;"\n    + "animation-delay:0s!important;animation-iteration-count:1!important}";',
  '  style.textContent = "*,*::before,*::after{transition:none!important;animation:none!important}";'),
 ("M6 every details content skipped (the #8249 gate's N2)", "|| (el.checkVisibility && !el.checkVisibility())) continue;",
  '|| (el.checkVisibility && !el.checkVisibility()) || el.closest("details")) continue;'),
 ("S1 the sector route is the last card", "    return hit.group(1)", "    return re.findall(r'href=\"(/kbli/sectors/[^\"/?#]+)\"', hit.string)[-1]"),
 ("S2 a scenario dropped from the list", '    ("sector-table", "/kbli", "walk", None, False, _open_table, ["div:has(> table)"]),\n', ""),
 ("S3 the armed test is handed the sector template", '"pages": [p for p in PAGES if p != SECTOR_PAGE]', '"pages": PAGES'),
]
WALK = "e2e"
res = []
for name, old, new in M:
    orig = C.read_text()
    assert orig.count(old) == 1, (name, orig.count(old))
    C.write_text(orig.replace(old, new))
    try:
        k = WALK if name.startswith("M") else "not e2e"
        r = subprocess.run([sys.executable, "-m", "pytest", "scripts/mouth/tests/test_r19_wrapper_token_census.py", "-q", "-x",
                            "-p", "no:cacheprovider", "-k", k], capture_output=True, text=True, timeout=1800)
        tail = r.stdout.strip().splitlines()[-1]
        failed = [l for l in r.stdout.splitlines() if l.startswith("FAILED")]
        res.append((name, "KILLED" if r.returncode else "SURVIVED", failed[0][7:120] if failed else tail))
    finally:
        C.write_text(orig)
    print(" | ".join(res[-1]), flush=True)
