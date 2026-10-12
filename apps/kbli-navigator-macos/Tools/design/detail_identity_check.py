#!/usr/bin/env python3
"""detail_identity_check.py - the `detail` census mark names the cell its detail describes (#8297 gate finding 3, binding G_DETAILLIE).

C24 reads the sheet's `detail` frame against the ring's row, but no pixel says which cell the detail's TEXT describes: a detail drawn for
row k with its mark left on the shown row passes every census. The mark's honesty is structural, so this reads the source: every
`cellDetail(scales[X])` is followed, in the same expression, by `.censusFrame("detail", "\\(X)")` with the SAME X, and every
`.censusFrame("detail", ...)` sits on a `cellDetail(...)` call. One identifier, one expression: the painter and the mark cannot disagree.

A first-pass lint like mark_order_check.py (docs/specs/2026-10-12-kbli-nav-census-mark-order.md): it reads the shape the View uses today
(`cellDetail(scales[X]).censusFrame("detail", "\\(X)")`) and fails closed on any other use of either call.

  detail_identity_check.py            check Sources/ (exit 1 on a finding)
  detail_identity_check.py --sources DIR   the same on another copy of Sources/
  detail_identity_check.py --selftest      guilt (the mark left on another row, an unmarked detail, a mark on something else) and innocence (the list's `expanded: { AnyView(cellDetail($0)) }` is the one other use, exempt)
"""
import importlib.util, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1] / "Sources"
_spec = importlib.util.spec_from_file_location("mark_order_check_lib", HERE / "mark_order_check.py")
_src = open(HERE / "mark_order_check.py").read().replace("\nsys.exit(main())", "\n")   # the scan's lexer, imported without running it
lib = importlib.util.module_from_spec(_spec); exec(compile(_src, str(HERE / "mark_order_check.py"), "exec"), lib.__dict__)

CELL = re.compile(r"(?<!func )\bcellDetail\s*\(")
MARK = re.compile(r"\.\s*censusFrame\s*\(")
INDEX = re.compile(r"\(\s*scales\[\s*([^\]]+?)\s*\]\s*\)\s*$")


def check(files):
    bad, cells, marks = [], 0, 0
    for path, text in files:
        name, s = pathlib.Path(path).name, lib.blank(text)
        good = set()
        for m in CELL.finditer(s):
            cells += 1; line = s.count("\n", 0, m.start()) + 1
            end = lib.match_fwd(s, m.end() - 1)
            if re.search(r"expanded:\s*\{\s*AnyView\(\s*$", text[max(0, m.start() - 60):m.start()]) and re.fullmatch(r"\(\s*\$0\s*\)", text[m.end() - 1:end]):
                cells -= 1; continue   # the 6+ scope list's expanded row: the row the reader opened, bound by the closure's own argument; C24 judges the picked cell, not this
            idx = INDEX.search(text[m.end() - 1:end])
            tail = MARK.match(s, lib.ws(s, end)) if s[lib.ws(s, end):lib.ws(s, end) + 1] == "." else None
            want = idx and re.compile(r'\.\s*censusFrame\(\s*"detail"\s*,\s*"\\\(\s*%s\s*\)"\s*\)' % re.escape(idx.group(1)))
            if not (idx and tail and want.match(text, lib.ws(s, end))):
                bad.append("%s:%d cellDetail(%s) is not followed by .censusFrame(\"detail\", \"\\(same row)\"): the mark must name the cell the detail describes"
                           % (name, line, idx.group(1) if idx else "?"))
            elif tail: good.add(tail.start())
        for m in MARK.finditer(s):
            if (lib.NAME.match(text[m.end() - 1:]) or [None, ""])[1] != "detail": continue
            marks += 1
            if m.start() not in good: bad.append("%s:%d a `detail` mark that is not on a cellDetail(scales[X]) call" % (name, s.count("\n", 0, m.start()) + 1))
    return bad, cells, marks


def selftest():
    ok = 'if let mi = sel { cellDetail(scales[mi]).censusFrame("detail", "\\(mi)") }\n'
    spaced = 'cellDetail( scales[ mi ] )\n    .censusFrame("detail", "\\(mi)")\n'
    listed = 'Row(expanded: { AnyView(cellDetail($0)) })\n' + ok
    commented = '// cellDetail(scales[k]).censusFrame("detail", "\\(mi)")\n' + ok
    guilt = {"the detail drawn for row k with its mark left on mi": 'cellDetail(scales[k]).censusFrame("detail", "\\(mi)")\n',
             "an unmarked detail": 'cellDetail(scales[mi])\n',
             "a detail mark on something else": 'Text("x").censusFrame("detail", "\\(mi)")\n',
             "a detail marked with a literal row": 'cellDetail(scales[mi]).censusFrame("detail", "0")\n',
             "the second of two details unmarked": ok + 'cellDetail(scales[mi])\n',
             "an unlisted cellDetail($0)": 'Row(content: { AnyView(cellDetail($0)) })\n'}
    for src, want in ((ok, 0), (spaced, 0), (commented, 0), (listed, 0), *((g, 1) for g in guilt.values())):
        got = check([("A.swift", src)])[0]
        assert bool(got) == bool(want), (src, got)
    for label, src in guilt.items(): assert check([("A.swift", src)])[0], label
    print("detail_identity_check selftest ok (%d guilt + 4 innocence)" % len(guilt)); return 0


def main():
    if "--selftest" in sys.argv: return selftest()
    root = pathlib.Path(sys.argv[sys.argv.index("--sources") + 1]) if "--sources" in sys.argv else ROOT
    bad, cells, marks = check([(str(p), p.read_text()) for p in sorted(root.rglob("*.swift"))])
    for b in bad: print("DETAIL-IDENTITY", b)
    print("detail_identity_check: %d finding(s) in %d cellDetail calls and %d detail marks" % (len(bad), cells, marks))
    return 1 if bad else 0


sys.exit(main())
