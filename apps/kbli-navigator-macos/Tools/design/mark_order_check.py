#!/usr/bin/env python3
"""mark_order_check.py - a `.censusFrame(` mark sits AFTER any `.offset(` or `.modifier(Beat(` of its own modifier chain.

A mark states where its element must LAND, so it comes after the move: `x.offset(y: 3.5).censusFrame("ladder")`. A mark placed
before the move (`x.censusFrame("ladder").offset(y: 3.5)`) travels with it, and an element left at a residual offset would carry
its frame along and pass. png_census cannot see the order (it reads ink against the frame), so this reads the source: for each
call, the rest of its own chain (the same line after the call, then the following lines that start with `.`) must hold neither.
Limit: the scan is chain-local; a mark nested inside a view that a parent Beats is not seen (none today: the Beats of
RegistryVerdictSheet wrap the title and the axis cards, which carry no mark).

  mark_order_check.py            check Sources/ (exit 1 on a mark before a move)
  mark_order_check.py --selftest guilt (the two inversions) and innocence (a mark after its move, a mark in a closure)
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2] / "Sources"
CALL = re.compile(r"\.censusFrame\(")
MOVE = re.compile(r"\.offset\(|\.modifier\(\s*Beat\(")
COMMENT = re.compile(r"//[^\n]*")

def after_call(text, start):
    """The text of the mark's chain after its closing paren: the rest of its line and the lines that continue with `.`."""
    depth, i = 0, start
    while i < len(text):
        depth += (text[i] == "(") - (text[i] == ")")
        i += 1
        if depth == 0: break
    end = text.find("\n", i); end = len(text) if end < 0 else end
    chain, lines = text[i:end], text[end + 1:].split("\n")
    for line in lines:
        if not line.strip().startswith("."): break
        chain += "\n" + line
    return chain

def check(files):
    bad, marks = [], 0
    for path, text in files:
        for m in CALL.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            if pathlib.Path(path).name == "CensusFrame.swift" and "func censusFrame" in text[text.rfind("\n", 0, m.start()) + 1:m.end() + 60]: continue
            marks += 1
            move = MOVE.search(after_call(text, m.end() - 1))
            if move: bad.append("%s:%d a census mark sits before %s: it must come after the move" % (pathlib.Path(path).name, line, move.group().strip(".(")))
    return bad, marks

def main():
    if "--selftest" in sys.argv:
        good = [("A.swift", 'x\n    .overlay { PadiLadder().offset(y: 3.5).censusFrame("ladder") }\n'),
                ("B.swift", 'chip(a)\n    .modifier(Beat(p: 1, from: 0, to: 1, dy: 6))\n    .censusFrame("chip.national", t)\n    .padding(2)\n'),
                ("C.swift", 'Text("x").censusFrame("hint")\n'), ("D.swift", 'a.padding(-3.5).censusFrame("ring", "1")\n')]
        assert check(good) == ([], 4), check(good)
        inv = [("A.swift", 'x\n    .overlay { PadiLadder().censusFrame("ladder").offset(y: 3.5) }\n')]
        assert len(check(inv)[0]) == 1, "the ladder mark before its offset must fail"
        beat = [("B.swift", 'chip(a)\n    .censusFrame("chip.national", t)\n    .modifier(Beat(p: 1, from: 0, to: 1, dy: 6))\n')]
        assert len(check(beat)[0]) == 1, "a mark before its Beat must fail"
        far = [("E.swift", 'a.censusFrame("x")\n\n    .offset(y: 2)\n')]
        assert check(far)[0] == [], "a blank line ends the chain"
        print("mark_order_check selftest ok (guilt + innocence)"); return 0
    files = [(str(p), COMMENT.sub("", p.read_text())) for p in sorted(ROOT.rglob("*.swift"))]
    bad, marks = check(files)
    for b in bad: print("MARK-ORDER", b)
    print("mark_order_check: %d finding(s) in %d marks" % (len(bad), marks))
    return 1 if bad else 0

sys.exit(main())
