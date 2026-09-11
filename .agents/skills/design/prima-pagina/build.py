"""Substitute the inline assets into home.tpl.html -> home.html.

    python3 build.py <work-dir>

<work-dir> must hold assets.json (see assets.py). home.tpl.html is read from
this script's own directory, so the corner is the single source of the template.
"""
import json, pathlib, re, sys

if len(sys.argv) != 2:
    raise SystemExit(__doc__)
here = pathlib.Path(__file__).resolve().parent
d = pathlib.Path(sys.argv[1])
tpl = (here / "home.tpl.html").read_text()
a = json.loads((d / "assets.json").read_text())


def bare(v):
    """assets.json stores a FULL data URI; the template supplies its own prefix.
    Feeding it through unstripped produced `data:...base64,data:...base64,AAA`
    -- which every mechanical gate passed, because a broken <img> still has a
    box, an alt string and a contrast ratio. Strip the prefix at the seam."""
    return re.sub(r"^data:image/[a-z+]+;base64,", "", v)


tpl = tpl.replace("__LOGO__", bare(a["logo"])).replace("__HERO__", bare(a["hero"]))
for k in ("surya", "ari", "sahira", "damar", "krisna", "dewaayu"):
    tpl = tpl.replace("__" + k.upper() + "__", bare(a[k]))

left = sorted(set(re.findall(r"__[A-Z]+__", tpl)))
if left:
    raise SystemExit(f"unreplaced tokens: {left}")
if "base64,data:" in tpl:
    raise SystemExit("double data-URI prefix survived")
(d / "home.html").write_text(tpl)
print(f"home.html  {len(tpl.encode()):,} bytes")
