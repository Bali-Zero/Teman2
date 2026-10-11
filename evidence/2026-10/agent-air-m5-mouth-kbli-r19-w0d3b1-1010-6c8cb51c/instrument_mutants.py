"""W0d-3b-1 instrument mutants: each edit undoes one cure, the guilt and innocence rows run with -x (through the
real walk for B, offline for V and W), and the file is restored before the next one. Run from the repo root, with
no census server running; prints one line per mutant."""
import subprocess, sys
from pathlib import Path
C = Path("scripts/mouth/r19_wrapper_token_census.py"); W = Path(".github/workflows/r19-wrapper-census-tests.yml")
M = [
 ("B1 an occluded run is not counted", 'if r["state"] == "occluded" and r.get("hides"):', 'if False:'),
 ("B2 hides ignores another opened surface", "\n    && !roots.some((r) => r.contains(el) && !r.contains(runEl));", ";"),
 ("B3 hides ignores the walk's scrims", "const hides = (el, runEl) => !scrims.some((s) => s === el || s.contains(el))", "const hides = (el, runEl) => true"),
 ("B4 a faint layer occludes", '    && (cs(el).filter !== "none" || (cs(el).backdropFilter', '    && (layersOf(el).some((l) => l.a > 0) || cs(el).filter !== "none" || (cs(el).backdropFilter'),
 ("B5 a shadow is not an overlay", ' || cs(el).boxShadow !== "none");', ');'),
 ("B6 no reach past the box", "    if (near) return", "    if (false) return"),
 ("B7 the reach ignores a blur", "b = blur ? 3 * parseFloat(blur[1]) : 0", "b = 0"),
 ("B8 a scrim paints a colour only", "const paints = (el) => !!parse(cs(el).backgroundColor) || (opacity(el) >= 0.1", "const paints = (el) => !!parse(cs(el).backgroundColor) || (false"),
 ("B9 a colourless scrim passes", '(not c["hex"] or c.get("image") or not near(c["hex"], DIRECTION_A["ink"]) or c["a"] >= 1)', '(c["hex"] and (c.get("image") or not near(c["hex"], DIRECTION_A["ink"]) or c["a"] >= 1))'),
 ("B10 an ink scrim over an image passes", 'not c["hex"] or c.get("image") or not near(', 'not c["hex"] or not near('),
 ("B11 the query devtools are painted", "nextjs-portal,.tsqd-parent-container{display:none!important}", "nextjs-portal{display:none!important}"),
 ("B12 the theme may turn mid-walk", "            if (now := page.evaluate(THEME_JS)) != theme:", "            if (now := page.evaluate(THEME_JS)) != theme and False:"),
 ("B13 a reloaded walk is not walked again", "            for attempt in (1, 2):", "            for attempt in (2,):"),
 ("B15 an overlay behind the run still reaches it", "      return over >= 0 && (under < 0 || over < under);", "      return true;"),
 ("B16 a shadow reaches against its offset", "side.top = Math.max(side.top, r + spread - dy);", "side.top = Math.max(side.top, r + spread + Math.abs(dy));"),
 ("B17 a transparent shadow reaches", "(colour && !parse(colour[0]))", "false"),
 ("B14 the sector card stays hovered", "    page.mouse.move(0, 0)  # the card under the pointer is not the drawer's state (#8202 gate)\n", ""),
 ("B18 unrendered text is a run", "\n          || (el.checkVisibility && !el.checkVisibility())) continue;", ") continue;"),
 ("V1 reads bare without rest", 'for k, v in by_kind.items()) + f"){tail}")', 'for k, v in by_kind.items()) + ")")'),
 ("V2 defined-above-wrapper bare without rest", "resolved outside the wrapper today){tail}", "resolved outside the wrapper today)"),
 ("V3 colours bare without rest", 'f"colors-outside-direction-a: {len(outside)}{tail}"', 'f"colors-outside-direction-a: {len(outside)}"'),
 ("V4 disagreements bare on a failed capture", '(tail or (f" (INCOMPLETE: {len(cap_failed)} captures failed, not a verdict)" if cap_failed else ""))', "tail"),
 ("W6 a re-run part cannot replace its dump", "          overwrite: true\n", "", W),
]
WALK = "e2e_guilt_and_innocence or e2e_page_grounds or sector_opener"
res = []
for name, old, new, *f in M:
    f = f[0] if f else C
    orig = f.read_text()
    assert orig.count(old) == 1, (name, orig.count(old))
    f.write_text(orig.replace(old, new))
    try:
        k = WALK if name.startswith("B") else "not e2e"
        r = subprocess.run([sys.executable, "-m", "pytest", "scripts/mouth/tests/test_r19_wrapper_token_census.py", "-q", "-x",
                            "-p", "no:cacheprovider", "-k", k], capture_output=True, text=True, timeout=1200)
        tail = r.stdout.strip().splitlines()[-1]
        failed = [l for l in r.stdout.splitlines() if l.startswith("FAILED")]
        res.append((name, "KILLED" if r.returncode else "SURVIVED", failed[0][7:120] if failed else tail))
    finally:
        f.write_text(orig)
    print(" | ".join(res[-1]), flush=True)
