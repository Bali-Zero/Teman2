"""W0d-3b-2b-i' instrument mutants: each edit undoes one cure, the named rows run with -x (through the real walks
for N1 and N2, offline for the rest), and the file is restored before the next one. Run from the repo root with
no census server running; prints one line per mutant."""
import subprocess, sys
from pathlib import Path
C = Path("scripts/mouth/r19_wrapper_token_census.py")
W = Path(".github/workflows/r19-wrapper-census-tests.yml")
M = [
 ("N1 G1: no scrim descendant is ever exempt", C, "s === el || (stacks(s) && s.contains(el))", "s === el", "I-fixed-scrim-child"),
 ("N1b G2: only a scrim that is itself fixed or sticky stacks", C, '["fixed", "sticky"].includes(cs(s).position) || cs(s).filter !== "none"\n    || (cs(s).backdropFilter || "none") !== "none" || cs(s).transform !== "none" || opacity(s) < 1;',
  '["fixed", "sticky"].includes(cs(s).position);', "I-blur-scrim-child"),
 ("N1c A1: the scrim's ANCESTORS make it stack (the #8560 head)", C, "(stacks(s) && s.contains(el))", "(position(s) && s.contains(el))", "G-flat-scrim-in-fixed-wrapper"),
 ("N1d G3: the scrim clause never prints", C, 'r.get("exempt") == "scrim" for r in runs)', 'r.get("exempt") == "scrim" and False for r in runs)', "names_the_cause"),
 ("N1e a surface-covered run is counted as behind the scrim", C, '? "surface" : null;', '? "scrim" : null;', "names_the_cause"),
 ("N2 a drop-shadow reaches", C, "const side = { top: b,",
  "const dsb = /drop-shadow/.test(cs(el).filter) ? 24 : 0; const side = { top: Math.max(b, dsb),", "I-drop-shadow-no-reach"),
 ("N3 the capture pass opens its own context", C, "        ctx = new_context(browser, w, h, scheme)\n        ctx.add_init_script(FREEZE_JS)\n        page = ctx.new_page()\n        try:",
  "        ctx = browser.new_context(viewport={'width': w, 'height': h}, color_scheme=scheme)\n        ctx.add_init_script(FREEZE_JS)\n        page = ctx.new_page()\n        try:", "reduced_motion_from_one"),
 ("N4 G9: bring() keeps the occluder but drops why it is exempt", C, "r.occludedBy = occ.occluded; r.exempt = occ.exempt; }\n          this.pending.shift();",
  "r.occludedBy = occ.occluded; r.exempt = occ.exempt && false; }\n          this.pending.shift();", "bring_fallback"),
 ("N4b G7: a drop-shadow reaches, written without the literal", C, "const side = { top: b,",
  'const dsb = cs(el).filter.indexOf("drop") >= 0 ? 24 : 0; const side = { top: Math.max(b, dsb),', "I-drop-shadow-only-no-reach"),
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
