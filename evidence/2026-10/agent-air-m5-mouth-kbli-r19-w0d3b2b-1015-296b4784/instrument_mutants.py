"""W0d-3b-2b-i instrument mutants: each edit undoes one cure, the named rows run with -x (through the real walks
for N1 and N2, offline for the rest), and the file is restored before the next one. Run from the repo root with
no census server running; prints one line per mutant."""
import subprocess, sys
from pathlib import Path
C = Path("scripts/mouth/r19_wrapper_token_census.py")
W = Path(".github/workflows/r19-wrapper-census-tests.yml")
M = [
 ("N1 a flat scrim's child is exempt again", C, "!scrims.some((s) => s === el || (position(s) && s.contains(el)))",
  "!scrims.some((s) => s === el || s.contains(el))", "G-flat-scrim-child"),
 ("N2 a drop-shadow reaches", C, "const side = { top: b,",
  "const dsb = /drop-shadow/.test(cs(el).filter) ? 24 : 0; const side = { top: Math.max(b, dsb),", "I-drop-shadow-no-reach"),
 ("N3 the capture pass opens its own context", C, "        ctx = new_context(browser, w, h, scheme)\n        ctx.add_init_script(FREEZE_JS)\n        page = ctx.new_page()\n        try:",
  "        ctx = browser.new_context(viewport={'width': w, 'height': h}, color_scheme=scheme)\n        ctx.add_init_script(FREEZE_JS)\n        page = ctx.new_page()\n        try:", "reduced_motion_from_one"),
 ("N4 bring() drops the occluder", C, "          if (occ) { r.occludedBy = occ.occluded; r.hides = occ.hides; }\n          this.pending.shift();",
  "          this.pending.shift();", "bring_fallback"),
 ("N5 ground-resolver-disagree ignores a capture not read through", C, "cap_failed or cap_short", "cap_failed", "not_read_through"),
 ("N6 the full job is back at 40 minutes", W, "${{ matrix.part == 'full' && 75 || 40 }}", "40", "full_dispatch_has_headroom"),
 ("N7 the exit step omits the declared line", W, "|declared-|opened-|", "|opened-|", "full_dispatch_has_headroom"),
]
for name, path, old, new, k in M:
    orig = path.read_text()
    if orig.count(old) != 1:
        print(f"{name} | ERROR | pattern found {orig.count(old)} times"); continue
    path.write_text(orig.replace(old, new))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "scripts/mouth/tests/test_r19_wrapper_token_census.py", "-q", "-x",
                            "-p", "no:cacheprovider", "-k", k], capture_output=True, text=True, timeout=1800)
        failed = [l for l in r.stdout.splitlines() if l.startswith("FAILED")]
        print(" | ".join((name, "KILLED" if r.returncode else "SURVIVED", failed[0][7:130] if failed else r.stdout.strip().splitlines()[-1])), flush=True)
    finally:
        path.write_text(orig)
