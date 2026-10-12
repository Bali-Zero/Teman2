#!/usr/bin/env python3
"""detail_identity_check.py - the `detail` census mark names the cell its detail describes (#8297 gate finding 3, binding G_DETAILLIE).

C24 reads the sheet's `detail` frame against the ring's row, but no pixel says which cell the detail's TEXT describes: a detail drawn for
row k with its mark left on the shown row passes every census. The mark's honesty is structural, so this reads the source: every
`cellDetail(scales[X])` is followed, in the same expression, by `.censusFrame("detail", "\\(X)")` with the SAME X, and every
`.censusFrame("detail", ...)` sits on a `cellDetail(...)` call. One identifier, one expression: the painter and the mark cannot disagree.

A first-pass lint like mark_order_check.py (docs/specs/2026-10-12-kbli-nav-census-mark-order.md): it reads the shape the View uses today
(`cellDetail(scales[X]).censusFrame("detail", "\\(X)")`) and fails closed on any other use of either call, a bare reference
(`content: cellDetail`) included. The one exemption is bound to its ENTITY, not its spelling: exactly one `expanded: { AnyView(cellDetail($0)) }`,
in KBLIRegistryView.swift; a second one, or one in another file, is a finding that names both. The committed mutant table is
detail_identity_mutants.py (content_check.sh step 8 runs it).

  detail_identity_check.py            check Sources/ (exit 1 on a finding)
  detail_identity_check.py --sources DIR   the same on another copy of Sources/
  detail_identity_check.py --selftest      guilt (the mark left on another row, an unmarked detail, a mark on something else) and innocence (the list's `expanded: { AnyView(cellDetail($0)) }` is the one other use, exempt)
"""
import importlib.util, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1] / "Sources"
ENTRY = "\nsys.exit(main())"
EXEMPT_FILE = "KBLIRegistryView.swift"


def load_lexer(src, path):
    """The scan's lexer, imported without running mark_order_check's own main. Refuses when its entry line is not the one this strips,
    and when the exec exits at all: either would otherwise run THAT scan and return ITS verdict as this one's."""
    if ENTRY not in src: sys.exit("detail_identity_check: mark_order_check.py entry line changed (%r not found); refusing to run" % ENTRY.strip())
    spec = importlib.util.spec_from_file_location("mark_order_check_lib", path); mod = importlib.util.module_from_spec(spec)
    try: exec(compile(src.replace(ENTRY, "\n"), str(path), "exec"), mod.__dict__)
    except SystemExit: sys.exit("detail_identity_check: mark_order_check.py exited while being imported; refusing to run")
    return mod


lib = load_lexer(open(HERE / "mark_order_check.py").read(), HERE / "mark_order_check.py")

CELL = re.compile(r"(?<!func )\bcellDetail\s*\(")
REF = re.compile(r"(?<!func )\bcellDetail\b(?!\s*\()")
ANCHOR = re.compile(r"expanded:\s*\{\s*AnyView\(\s*$")
MARKED = re.compile(r'\.\s*censusFrame\(\s*"detail"\s*,\s*"\\\(([^"]*?)\)"\s*\)')
MARK = re.compile(r"\.\s*censusFrame\s*\(")
INDEX = re.compile(r"\(\s*scales\[\s*([^\]]+?)\s*\]\s*\)\s*$")


def check(files):
    bad, cells, marks, exempt = [], 0, 0, []
    for path, text in files:
        name, s = pathlib.Path(path).name, lib.blank(text)
        good = set()
        for m in REF.finditer(s):
            bad.append("%s:%d a bare `cellDetail` reference: a detail drawn through a function value carries no mark" % (name, s.count("\n", 0, m.start()) + 1))
        for m in CELL.finditer(s):
            cells += 1; line = s.count("\n", 0, m.start()) + 1
            end = lib.match_fwd(s, m.end() - 1)
            if ANCHOR.search(s[max(0, m.start() - 60):m.start()]) and re.fullmatch(r"\(\s*\$0\s*\)", s[m.end() - 1:end]):
                cells -= 1; exempt.append((name, line)); continue   # the 6+ scope list's expanded row: the row the reader opened, bound by the closure's own argument; C24 judges the picked cell, not this
            idx = INDEX.search(text[m.end() - 1:end])
            tail = MARK.match(s, lib.ws(s, end)) if s[lib.ws(s, end):lib.ws(s, end) + 1] == "." else None
            got = tail and MARKED.match(text, lib.ws(s, end))
            if not (idx and got and re.sub(r"\s+", "", got.group(1)) == re.sub(r"\s+", "", idx.group(1))):
                bad.append("%s:%d cellDetail(%s) is not followed by .censusFrame(\"detail\", \"\\(same row)\"): the mark must name the cell the detail describes"
                           % (name, line, idx.group(1) if idx else "?"))
            elif tail: good.add(tail.start())
        for m in MARK.finditer(s):
            if (lib.NAME.match(text[m.end() - 1:]) or [None, ""])[1] != "detail": continue
            marks += 1
            if m.start() not in good: bad.append("%s:%d a `detail` mark that is not on a cellDetail(scales[X]) call" % (name, s.count("\n", 0, m.start()) + 1))
    sites = ", ".join("%s:%d" % e for e in exempt)
    for e in exempt[1:]: bad.append("%s:%d a second list-row expansion exemption (sites: %s): the exemption names exactly ONE site" % (e + (sites,)))
    for e in exempt[:1]:
        if e[0] != EXEMPT_FILE: bad.append("%s:%d the list-row expansion exemption is bound to %s, not %s (sites: %s)" % (e + (EXEMPT_FILE, e[0], sites)))
    return bad, cells, marks, ["%s:%d" % e for e in exempt]


def selftest():
    ok = 'if let mi = sel { cellDetail(scales[mi]).censusFrame("detail", "\\(mi)") }\n'
    spaced = 'cellDetail( scales[ mi ] )\n    .censusFrame("detail", "\\(mi)")\n'
    spaced_mark = 'cellDetail(scales[mi + 0]).censusFrame("detail", "\\(mi+0)")\n'
    listed = 'Row(expanded: { AnyView(cellDetail($0)) })\n'
    commented = '// cellDetail(scales[k]).censusFrame("detail", "\\(mi)")\n' + ok
    anchor_comment = '// expanded: { AnyView(\ncellDetail($0)\n'
    guilt = {"the detail drawn for row k with its mark left on mi": 'cellDetail(scales[k]).censusFrame("detail", "\\(mi)")\n',
             "an unmarked detail": 'cellDetail(scales[mi])\n',
             "a detail mark on something else": 'Text("x").censusFrame("detail", "\\(mi)")\n',
             "a detail marked with a literal row": 'cellDetail(scales[mi]).censusFrame("detail", "0")\n',
             "the second of two details unmarked": ok + 'cellDetail(scales[mi])\n',
             "an unlisted cellDetail($0)": 'Row(content: { AnyView(cellDetail($0)) })\n',
             "G16 a function reference": 'ForEach(scales, id: \\.skalaUsaha, content: cellDetail)\n',
             "G18 a comment feeding the exemption anchor": anchor_comment}
    for src, want in ((ok, 0), (spaced, 0), (spaced_mark, 0), (commented, 0), *((g, 1) for g in guilt.values())):
        got = check([(EXEMPT_FILE, src)])[0]
        assert bool(got) == bool(want), (src, got)
    for label, src in guilt.items(): assert check([(EXEMPT_FILE, src)])[0], label
    assert not check([(EXEMPT_FILE, listed + ok)])[0], "the one exemption, in its file"
    assert check([(EXEMPT_FILE, listed + listed)])[0], "G17 a second exempt site"
    assert check([(EXEMPT_FILE, listed), ("B.swift", listed)])[0], "a second exempt site in another file"
    assert check([("ScalePath.swift", listed)])[0], "G20 the exempt shape in another file"
    for entry in ("raise SystemExit(main())", "pass", "import sys\nsys.exit(0)\nsys.exit(main())"):
        try: load_lexer("x = 1\n" + entry + "\n", HERE / "mark_order_check.py")
        except SystemExit as e: assert "refusing" in str(e), (entry, e)
        else: raise AssertionError("G19 the lexer import accepted a lexer source that would exit or run its own verdict: " + entry)
    print("detail_identity_check selftest ok (%d guilt + exemption bound to one site in %s + lexer import refusals + 5 innocence)" % (len(guilt), EXEMPT_FILE)); return 0


def main():
    if "--selftest" in sys.argv: return selftest()
    root = pathlib.Path(sys.argv[sys.argv.index("--sources") + 1]) if "--sources" in sys.argv else ROOT
    bad, cells, marks, exempt = check([(str(p), p.read_text()) for p in sorted(root.rglob("*.swift"))])
    for b in bad: print("DETAIL-IDENTITY", b)
    for e in exempt: print("exempt: list-row expansion (the reader opens a row; not the selected cell) at", e)
    print("detail_identity_check: %d finding(s) in %d cellDetail calls and %d detail marks" % (len(bad), cells, marks))
    return 1 if bad else 0


sys.exit(main())
