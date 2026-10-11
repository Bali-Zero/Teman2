#!/usr/bin/env python3
"""mark_order_check.py - where a `.censusFrame(` mark sits in its modifier chain (lead ruling 2026-10-12, #8297 gate finding 4).

A census frame reports the element's LAYOUT frame, where it is MEANT to land, and png_census checks that the ink is there. So:
  1. the mark goes AFTER any animation modifier (`.modifier(Beat(`, `.transition(`): placed before, it travels with the move
     and can never disagree with the ink, while placed after it keeps the layout frame and a beat that leaves the element
     out of place FAILs on ink against frame;
  2. nothing in the chain after the mark may `.offset(` the element (that moves the ink off its frame);
  3. a deliberate static nudge on a marked element is expressed in layout (`padding`, alignment), not with `.offset(`, so frame
     and ink agree. A static `.offset(` on a marked element is allowed only on the explicit ALLOW list, with its reason.
png_census cannot see the order (it reads ink against the frame), so this reads the source. Limit: the scan is chain-local; a
mark nested inside a view that a parent Beats is not seen (none today: the Beats of RegistryVerdictSheet wrap the title and
the axis cards, which carry no mark).

  mark_order_check.py            check Sources/ (exit 1 on a finding)
  mark_order_check.py --selftest guilt (a mark before a Beat, before an offset, a static offset unlisted) and innocence
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2] / "Sources"
CALL = re.compile(r"\.censusFrame\(")
ANIMATION = re.compile(r"\.modifier\(\s*Beat\(|\.transition\(")
OFFSET = re.compile(r"\.offset\(")
COMMENT = re.compile(r"//[^\n]*")
NAME = re.compile(r'\(\s*"([^"]+)"')
# (file, mark name) -> why a static `.offset(` on that marked element stays. Empty: the one that was (the ladder's 3.5 pt) is layout now.
ALLOW = {}

def after_call(text, start):
    """The mark's chain after its closing paren: the rest of its line and the lines that continue with `.`."""
    depth, i = 0, start
    while i < len(text):
        depth += (text[i] == "(") - (text[i] == ")")
        i += 1
        if depth == 0: break
    end = text.find("\n", i); end = len(text) if end < 0 else end
    chain = text[i:end]
    for line in text[end + 1:].split("\n"):
        if not line.strip().startswith("."): break
        chain += "\n" + line
    return chain

def before_call(text, start):
    """The element the mark sits on: the line up to the mark, and the lines above it while the chain continues with `.`."""
    ls = text.rfind("\n", 0, start) + 1
    chain, cont = text[ls:start], text[ls:].lstrip().startswith(".")
    above = text[:ls - 1].split("\n") if ls else []
    while cont and above:
        line = above.pop(); chain = line + "\n" + chain; cont = line.strip().startswith(".")
    return chain

def check(files):
    bad, marks = [], 0
    for path, text in files:
        name = pathlib.Path(path).name
        for m in CALL.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            if name == "CensusFrame.swift" and "func censusFrame" in text[text.rfind("\n", 0, m.start()) + 1:m.end() + 60]: continue
            marks += 1
            mark = (NAME.match(text[m.end() - 1:]) or [None, "?"])[1]
            after, before = after_call(text, m.end() - 1), before_call(text, m.start())
            a = ANIMATION.search(after)
            if a: bad.append("%s:%d mark %s sits before %s: it goes after any animation modifier" % (name, line, mark, a.group().strip(".(")))
            if OFFSET.search(after): bad.append("%s:%d mark %s sits before an .offset(: an offset after the mark moves the ink off its frame" % (name, line, mark))
            if OFFSET.search(before) and (name, mark) not in ALLOW:
                bad.append("%s:%d mark %s is on an element with a static .offset(: say it in layout (padding, alignment) or allow-list it with a reason" % (name, line, mark))
    return bad, marks

def main():
    if "--selftest" in sys.argv:
        good = [("A.swift", 'x\n    .overlay(alignment: .bottom) { PadiLadder().padding(.bottom, -3.5).censusFrame("ladder") }\n'),
                ("B.swift", 'chip(a)\n    .modifier(Beat(p: 1, from: 0, to: 1, dy: 6))\n    .censusFrame("chip.national", t)\n    .padding(2)\n'),
                ("C.swift", 'Text("x").censusFrame("hint")\n'), ("D.swift", 'a.padding(-3.5).censusFrame("ring", "1")\n')]
        assert check(good) == ([], 4), check(good)
        inv = [("A.swift", 'x\n    .overlay { PadiLadder().censusFrame("ladder").offset(y: 3.5) }\n')]
        assert len(check(inv)[0]) == 1, "a mark before its offset must fail"
        beat = [("B.swift", 'chip(a)\n    .censusFrame("chip.national", t)\n    .modifier(Beat(p: 1, from: 0, to: 1, dy: 6))\n')]
        assert len(check(beat)[0]) == 1, "a mark before its Beat must fail"
        trans = [("B.swift", 'chip(a)\n    .censusFrame("x")\n    .transition(.opacity)\n')]
        assert len(check(trans)[0]) == 1, "a mark before a transition must fail"
        static = [("A.swift", 'x\n    .overlay(alignment: .bottom) { PadiLadder().offset(y: 3.5).censusFrame("ladder") }\n')]
        assert len(check(static)[0]) == 1, "a static offset on a marked element must fail"
        multi = [("A.swift", 'chip(a)\n    .offset(y: 2)\n    .censusFrame("x")\n')]
        assert len(check(multi)[0]) == 1, "a static offset on a chain above the mark must fail"
        ALLOW[("A.swift", "ladder")] = "selftest"
        assert check(static)[0] == [], "an allow-listed static offset passes"
        ALLOW.clear()
        far = [("E.swift", 'a.censusFrame("x")\n\n    .offset(y: 2)\n')]
        assert check(far)[0] == [], "a blank line ends the chain"
        print("mark_order_check selftest ok (guilt + innocence)"); return 0
    files = [(str(p), COMMENT.sub("", p.read_text())) for p in sorted(ROOT.rglob("*.swift"))]
    bad, marks = check(files)
    for b in bad: print("MARK-ORDER", b)
    print("mark_order_check: %d finding(s) in %d marks (allow-list: %d)" % (len(bad), marks, len(ALLOW)))
    return 1 if bad else 0

sys.exit(main())
