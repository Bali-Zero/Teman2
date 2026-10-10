"""Each mutation of the resolvers must fail the e2e table: runs pytest once per mutation, restores the file."""
import shutil
import subprocess
import sys
from pathlib import Path

wt = Path(sys.argv[1])
f = wt / "scripts/mouth/r19_wrapper_token_census.py"
keep = f.read_text()
MUTANTS = {
    "no forced pointer-events": ('"*{pointer-events:auto!important;scroll-behavior', '"*{scroll-behavior'),
    "no pseudo layers": ('for (const pseudo of ["::after", "::before"]) {', 'for (const pseudo of []) {'),
    "copper box always ok": ('? "ok" : "box";', '? "ok" : "ok";'),
    "opaque scrim allowed": ('or c["a"] >= 1) and key not in off', ') and key not in off'),
    "small pseudo is a layer": ("if (!(parseFloat(p.width) >= w * 0.9", "if (false && !(parseFloat(p.width) >= w * 0.9"),
    "no occluders": ("if (!runEl.contains(st[k]) && (layersOf(st[k]).some((l) => !l.faint) || overlay(st[k])))", "if (false)"),
    "faint image is a layer": ("(l.a * 255 < 6 || l.blend)", "(l.blend)"),
    "blended image is a ground": ("(l.a * 255 < 6 || l.blend)", "(l.a * 255 < 6)"),
    "fixed pseudo against its host": ('p.position === "fixed" ? [innerWidth, innerHeight]', 'false ? 0'),
    "text not transparent": [("{color:transparent!important;", "{"),
                             ("-webkit-text-fill-color:transparent!important;", "")],
    "image only under translucent colour": ("direct = top && top.kind !== \"color\" ? top.kind : null",
                                            "direct = null"),
    "drift without tolerance": ("hit = next((y for y in left if same_print(x, y)), None)", "hit = None"),
    "dev indicator painted": ('st.textContent = "nextjs-portal{display:none!important}"\n    + "', 'st.textContent = "'),
    "a fixed overlay must paint": (" || overlay(st[k])))", "))"),
    "no retarget on a partial occlusion": [("        if (occ && occ.fixed && this.target !== i) continue;\n", ""),
                                           ("          if (occ) { r.state", "          if (occ && (this.target === i || !occ.fixed)) { r.state")],
    "no retry on 0 roots": ("                if opener and not opened:", "                if False:"),
    "no retry on a thrown opener": ("                    if not opener:\n                        raise\n", "                    raise\n"),
    "forced theme not held": ("    if not forced or page.evaluate(THEME_JS) == forced:\n        return", "    return"),
}
shutil.copy(f, f.with_suffix(".py.keep"))
try:
    for name, edits in MUTANTS.items():
        if len(sys.argv) > 2 and name not in sys.argv[2].split(","):
            continue
        text = keep
        for a, b in edits if isinstance(edits, list) else [edits]:
            assert text.count(a) == 1, name
            text = text.replace(a, b)
        f.write_text(text)
        r = subprocess.run([sys.executable, "-m", "pytest", "scripts/mouth/tests", "-q", "-p", "no:cacheprovider",
                            "-k", "e2e_guilt_and_innocence or page_grounds_at_rest or within_two_levels or i9"], cwd=wt, capture_output=True,
                           text=True)
        tail = r.stdout.strip().splitlines()[-1]
        failed = [ln.split("[")[-1].rstrip("]") for ln in r.stdout.splitlines() if ln.startswith("FAILED")]
        print(f"{name:40} {'KILLED' if r.returncode else 'SURVIVED'}  {tail}  {failed[:8]}", flush=True)
finally:
    f.write_text(keep)
    f.with_suffix(".py.keep").unlink()
