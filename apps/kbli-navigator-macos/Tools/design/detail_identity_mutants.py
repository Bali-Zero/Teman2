#!/usr/bin/env python3
"""detail_identity_mutants.py - the committed mutant table of detail_identity_check.py (#8399 gate: G1-G20 guilt, I0-I8 innocence).

Each case copies the REAL Sources/ and Tools/design/ into a scratch directory, makes one edit, runs the scan there (`--sources`) and
compares its exit code with the wanted one. A case whose anchor text is gone from the real source FAILS: the table is coupled to the
code it mutates, so a rewrite of the View makes this table say so instead of passing on a mutation that no longer applies.

  detail_identity_mutants.py            run the table, print one row per case (id, want, rc, ok), exit 1 on any miss
"""
import pathlib, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
APP = HERE.parents[1]
VIEW, PATH = "Sources/Views/KBLIRegistryView.swift", "Sources/Views/ScalePath.swift"
IMM = 'if let mi = matrixSel ?? defaultCell, mi < scales.count { cellDetail(scales[mi]).censusFrame("detail", "\\(mi)") }'
SEL = 'cellDetail(scales[mi]).censusFrame("detail", "\\(mi)")'
EXP = "expanded: { AnyView(cellDetail($0)) })"
PATHCALL = "ScalePath(scales: scales, isID: isID, mode: .ledger, selection: shownCell)"
SHOWN = "let shownCell = Binding(get: { matrixSel ?? defaultCell }, set: { matrixSel = $0 })"


def rep(t, old, new, nth=1):
    """Replace the nth occurrence of old; a missing anchor is an error, not a skipped case."""
    i = -1
    for _ in range(nth):
        i = t.find(old, i + 1)
        if i < 0: raise SystemExit("detail_identity_mutants: anchor not found in the real source (the table is stale): " + old[:70])
    return t[:i] + new + t[i + len(old):]


def second(new): return lambda t: rep(t, SEL, new, 2)
def first(new): return lambda t: rep(t, SEL, new, 1)
def view(f): return lambda d: {VIEW: f(d[VIEW])}
def stmt(line, after=PATHCALL): return lambda d: {VIEW: rep(d[VIEW], after, after + "\n" + line)}

# (id, wanted rc, edit: dict(path -> text) -> dict of changed texts)
CASES = [
    ("I0 unmodified head", 0, lambda d: {}),
    ("G1 detail for scales[0], mark mi", 1, view(second('cellDetail(scales[0]).censusFrame("detail", "\\(mi)")'))),
    ("G1b the immersive site: scales[k], mark mi", 1, view(first('cellDetail(scales[k]).censusFrame("detail", "\\(mi)")'))),
    ("G2 mark names the selection", 1, view(second('cellDetail(scales[mi]).censusFrame("detail", "\\(matrixSel ?? 0)")'))),
    ("G3 mark names the shown default", 1, view(second('cellDetail(scales[mi]).censusFrame("detail", "\\(defaultCell!)")'))),
    ("G4 literal mark", 1, view(second('cellDetail(scales[mi]).censusFrame("detail", "3")'))),
    ("G5 literal interpolation", 1, view(second('cellDetail(scales[mi]).censusFrame("detail", "\\(3)")'))),
    ("G6 equal at runtime, other identifier", 1, view(second('let shown = mi\n cellDetail(scales[shown]).censusFrame("detail", "\\(mi)")'))),
    ("G6b mark reads the binding", 1, view(second('cellDetail(scales[mi]).censusFrame("detail", "\\(shownCell.wrappedValue!)")'))),
    ("G7 no mark (list-below-6 site)", 1, view(second("cellDetail(scales[mi])"))),
    ("G7b no mark (immersive site)", 1, view(first("cellDetail(scales[mi])"))),
    ("G8 an orphan detail mark", 1, view(lambda t: rep(t, IMM, 'Color.clear.censusFrame("detail", "\\(0)")\n' + IMM))),
    ("G8b the mark on Text", 1, view(second('Text("x").censusFrame("detail", "\\(mi)")'))),
    ("G9 list-row-like site under another label", 1, view(lambda t: rep(t, EXP, "rows: { AnyView(cellDetail($0)) })"))),
    ("G10 multi-line call, wrong mark", 1, view(second('cellDetail(\n scales[k]\n)\n.censusFrame("detail", "\\(mi)")'))),
    ("G11 trailing closure", 1, view(second('cellDetail(scales[mi]) { Text("") }.censusFrame("detail", "\\(mi)")'))),
    ("G12 mark before, call unmarked", 1, view(second('Text("a").censusFrame("detail", "\\(mi)")\n cellDetail(scales[mi])'))),
    ("G13 a modifier between call and mark", 1, view(second('cellDetail(scales[mi]).padding(4).censusFrame("detail", "\\(mi)")'))),
    ("G14 wrapped in Group", 1, view(second('Group { cellDetail(scales[mi]) }.censusFrame("detail", "\\(mi)")'))),
    ("G15 scales[mi + 0], mark mi", 1, view(second('cellDetail(scales[mi + 0]).censusFrame("detail", "\\(mi)")'))),
    ("G16 a function reference", 1, lambda d: {VIEW: rep(d[VIEW], SHOWN, SHOWN + "\nForEach(scales, id: \\.skalaUsaha, content: cellDetail)")}),
    ("G17 a second expanded site, same file", 1, stmt("ScaleMatrix(scales: scales, isID: isID, mode: .ledger, selection: shownCell,\n " + EXP)),
    ("G18 a comment feeding the anchor", 1, stmt("// expanded: { AnyView(\n cellDetail($0)\n)")),
    ("G20 the exempt shape moved to ScalePath.swift", 1,
     lambda d: {VIEW: rep(d[VIEW], EXP, "expanded: { AnyView(EmptyView()) })"), PATH: d[PATH] + "\nScaleMatrix(a, expanded: { AnyView(cellDetail($0)) })\n"}),
    ("I1 the exempt site moved down", 0, view(lambda t: rep(t, EXP, "\n\n\n\n\n" + EXP))),
    ("I2 multi-line call, right mark", 0, view(second('cellDetail(\n scales[mi]\n)\n.censusFrame("detail", "\\(mi)")'))),
    ("I3 cellDetail( in comments and strings", 0,
     view(lambda t: rep(t, SHOWN, SHOWN + '\n// cellDetail(scales[k])\n/* cellDetail(scales[k]) */\nlet a = "cellDetail(scales[k])"\nlet b = """\ncellDetail(scales[k])\n"""'))),
    ("I4 scales[mi + 0], mark mi + 0", 0, view(second('cellDetail(scales[mi + 0]).censusFrame("detail", "\\(mi + 0)")'))),
    ("I5 another identifier, both sides", 0, view(second('cellDetail(scales[sel]).censusFrame("detail", "\\(sel)")'))),
    ("I6 a comment between call and mark", 0, view(second('cellDetail(scales[mi]) // x\n.censusFrame("detail", "\\(mi)")'))),
    ("I7 whitespace only inside the index", 0, view(second('cellDetail(scales[mi + 0]).censusFrame("detail", "\\(mi+0)")'))),
    ("I8 the mark on the next line", 0, view(second('cellDetail(scales[mi])\n\n.censusFrame("detail", "\\(mi)")'))),
]


def run(case):
    name, want, edit = case
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        shutil.copytree(APP / "Sources", root / "Sources"); shutil.copytree(HERE, root / "Tools" / "design")
        real = {VIEW: (APP / VIEW).read_text(), PATH: (APP / PATH).read_text()}
        for rel, text in edit(real).items(): (root / rel).write_text(text)
        return scan(root)


def scan(root):
    r = subprocess.run([sys.executable, str(root / "Tools/design/detail_identity_check.py"), "--sources", str(root / "Sources")], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def run_g19():
    """G19: mark_order_check.py's last line becomes `raise SystemExit(main())` on a guilty tree; the scan must still fail."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        shutil.copytree(APP / "Sources", root / "Sources"); shutil.copytree(HERE, root / "Tools" / "design")
        mo = root / "Tools/design/mark_order_check.py"
        mo.write_text(rep(mo.read_text(), "\nsys.exit(main())", "\nraise SystemExit(main())"))
        v = root / VIEW; v.write_text(second('cellDetail(scales[0]).censusFrame("detail", "\\(mi)")')(v.read_text()))
        return scan(root)


# the guilts the #8399 gate found must fail FOR THEIR REASON, not for any rc != 0
REASON = {"G16": "bare `cellDetail` reference", "G17": "second list-row expansion exemption", "G18": "is not followed by .censusFrame",
          "G20": "is bound to KBLIRegistryView.swift", "G19": "entry line changed"}


def main():
    miss, rows = 0, [(c[0], c[1], run(c)) for c in CASES] + [("G19 the lexer's entry line changed, guilty tree", 1, run_g19())]
    for name, want, (rc, out) in rows:
        why = REASON.get(name.split()[0])
        ok = (rc != 0) == (want != 0) and (why is None or why in out)
        miss += not ok
        print("%-52s want %s rc %d %s" % (name, "!=0" if want else "0  ", rc, "ok" if ok else "MISS" + (" (reason %r not in output)" % why if why else "")))
    print("detail_identity_mutants: %d case(s), %d miss(es)" % (len(rows), miss))
    return 1 if miss else 0


sys.exit(main())
