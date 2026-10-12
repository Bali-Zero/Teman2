#!/usr/bin/env python3
"""mark_order_check.py - where a `.censusFrame(` mark sits in the modifier chain of its element (lead ruling 2026-10-12, #8297
gate finding 4; the chain is read by STRUCTURE after the #8309 gate).

A census frame reports the element's LAYOUT frame, where it is MEANT to land, and png_census checks that the ink is there. So:
  1. the mark goes AFTER any animation modifier: placed before, it travels with the move and can never disagree with the ink,
     while placed after it keeps the layout frame and a beat that leaves the element out of place FAILs on ink against frame;
  2. nothing in the chain after the mark may `.offset` the element (that moves the ink off its frame);
  3. a deliberate static nudge on a marked element is expressed in layout (`padding`, alignment), not with `.offset`, so frame
     and ink agree. A static `.offset` on a marked element is allowed only on the explicit ALLOW list, with its reason.
png_census cannot see the order (it reads ink against the frame), so this reads the source.

THIS IS A FIRST-PASS LINT, NOT A GUARANTEE (lead re-ruling 2026-10-12, #8309 and #8327 gates): a hand-written reader of Swift
chains is an unbounded surface, so it is declared for what it reads and for what it does not (L1-L9 below). The recommended
implementation, a SwiftSyntax tool target, is specified in docs/specs/2026-10-12-kbli-nav-census-mark-order.md and is built later,
in its own lane. None of the unread shapes is live in Sources/ today.

The chain of the marked expression is its postfix chain of `.name`, `.name(args)`, `.name(args) { closure }` and `.name { closure }`
links, read forwards from the mark and backwards from it, with balanced parens and braces, over the line breaks of the shapes it
knows: a link that wraps over lines (`.overlay { ... }`, `.modifier(\\n Beat(...))`) is one link. Strings and comments are blanked first, so an
`.offset(` inside a string or a comment is nothing. What counts, read from Sources/ and never hand-listed:
  ANIMATION  = `.transition`; `.modifier(T(...))` for every type T that is Animatable (declares `animatableData`, or conforms to
               Animatable / AnimatableModifier / GeometryEffect: Beat, DrawnRule, CountUpPercent today); and every helper
               function whose body applies one of these (`func enter(...) { modifier(Beat(...)) }`), to a fixed point.
  MOVE       = `.offset` (a space before the paren included).
A link inside a closure belongs to the closure's own chain. So an offset on the host of an `.overlay { ... }` that holds the marked
element does not move the mark ONLY when it comes BEFORE the overlay (`x.offset(...).overlay { mark }`); AFTER the overlay it moves
the mark with its ink (L4), and the scan does not see it.

KNOWN UNREAD SHAPES (each is a guilt of the spec, none is live today; the gate's case ids in brackets):
  L1  a trailing closure with the `{` on the next line, with parens or without (B1a, B1b).
  L2  labelled trailing closures `label: { ... }`, read forwards and backwards (B2a, B2b).
  L3  a postfix `#if` / `#elseif` / `#else` / `#endif` inside the chain (B3a-c).
  L4  a mark inside a closure or an argument whose enclosing chain then moves or animates: `Group { mark }.offset` (B4),
      `host.overlay { mark }.offset` or `.modifier(Beat)` (B5a, B5b), `ForEach { mark }.offset` (B5c). Measured at +4.0 pt: the
      frame travels with the move, and on chip.national the census is blind too.
  L5  a marked view used by name and moved where it is used, e.g. `matrix.offset(...)` (B15): offsets as well as animations.
  L6  a MOVE helper: a func or a ViewModifier whose body applies `.offset` (B6, B7a), the real `HoverLift` included (B7b).
  L7  an Animatable conformance declared in an `extension` (B8).
  L8  a non-Animatable ViewModifier that applies Beat or another animation (B11).
  L9  built-in render effects, not read: scaleEffect, rotationEffect, rotation3DEffect, transformEffect, projectionEffect,
      matchedGeometryEffect (B14). `.position` and `.alignmentGuide` are layout, not moves.

  mark_order_check.py            check Sources/ (exit 1 on a finding)
  mark_order_check.py --sources DIR  the same on another copy of Sources/ (the real-file mutants)
  mark_order_check.py --selftest guilt (the gate's G1-G9) and innocence (I1-I6, the real chains)
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2] / "Sources"
CALL = re.compile(r"\.\s*censusFrame\s*\(")
NAME = re.compile(r'\(\s*"([^"]+)"')
IDENT = re.compile(r"[A-Za-z_]\w*")
# (file, mark name) -> why a static `.offset` on that marked element stays. Empty: the one that was (the ladder's 3.5 pt) is layout now.
ALLOW = {}
OPEN, CLOSE = {"(": ")", "{": "}", "[": "]"}, {")": "(", "}": "{", "]": "["}


def blank(text):
    """The text with comments and the inside of string literals replaced by spaces (newlines and length kept): `\\(...)`
    interpolations are blanked with their string, `//` and nested `/* */` comments go, `\"\"\"` and raw `#"..."#` strings too."""
    out, i, n, mode = list(text), 0, len(text), []   # mode stack: ("str", triple, hashes) | ("interp", depth) | ("cmt", depth)
    def put(a, b):
        for k in range(a, b):
            if out[k] != "\n": out[k] = " "
    def opener(i):   # a string opening at i: (length of the opener incl. hashes and quotes, triple, hashes), or None
        h = 0
        while i + h < n and text[i + h] == "#": h += 1
        if i + h < n and text[i + h] == '"': t = text.startswith('"""', i + h); return h + (3 if t else 1), t, h
        return None
    while i < n:
        top = mode[-1] if mode else None
        if top and top[0] == "cmt":
            if text.startswith("/*", i): mode[-1] = ("cmt", top[1] + 1); put(i, i + 2); i += 2
            elif text.startswith("*/", i):
                put(i, i + 2); i += 2
                if top[1] == 1: mode.pop()
                else: mode[-1] = ("cmt", top[1] - 1)
            else: put(i, i + 1); i += 1
        elif top and top[0] == "str":
            _, triple, h = top; esc = "\\" + "#" * h
            if text.startswith(esc + "(", i): put(i, i + len(esc) + 1); mode.append(("interp", 1)); i += len(esc) + 1
            elif text.startswith(esc, i): put(i, i + len(esc) + 1); i += len(esc) + 1
            elif text.startswith(('"""' if triple else '"') + "#" * h, i):
                k = len(('"""' if triple else '"')) + h; put(i, i + k); mode.pop(); i += k
            else: put(i, i + 1); i += 1
        elif top and top[0] == "interp":
            c, o = text[i], opener(i) if text[i] in '#"' else None
            if o: put(i, i + o[0]); mode.append(("str", o[1], o[2])); i += o[0]; continue
            if c == "(": mode[-1] = ("interp", top[1] + 1)
            elif c == ")":
                mode[-1] = ("interp", top[1] - 1)
                if top[1] == 1: mode.pop()
            put(i, i + 1); i += 1
        else:
            o = opener(i) if text[i] in '#"' else None
            if text.startswith("//", i):
                j = text.find("\n", i); j = n if j < 0 else j; put(i, j); i = j
            elif text.startswith("/*", i): mode.append(("cmt", 1)); put(i, i + 2); i += 2
            elif o: mode.append(("str", o[1], o[2])); put(i, i + o[0]); i += o[0]
            else: i += 1
    return "".join(out)


def match_fwd(s, i):
    """Index just past the group opened at s[i] (`(`, `{` or `[`), or len(s) when it never closes."""
    stack = []
    while i < len(s):
        c = s[i]
        if c in OPEN: stack.append(OPEN[c])
        elif c in CLOSE:
            if not stack or stack.pop() != c: return len(s)
            if not stack: return i + 1
        i += 1
    return len(s)


def match_back(s, e):
    """Index of the opener of the group closed at s[e - 1]."""
    stack = []
    for i in range(e - 1, -1, -1):
        c = s[i]
        if c in CLOSE: stack.append(CLOSE[c])
        elif c in OPEN:
            if not stack or stack.pop() != c: return 0
            if not stack: return i
    return 0


def ws(s, i):
    while i < len(s) and s[i].isspace(): i += 1
    return i


def forward(s, i):
    """The links after position i: [(name, args, closure)]. `.name`, optional `(args)` after any whitespace, optional trailing closure
    on the same line."""
    links = []
    while True:
        j = ws(s, i)
        if not (j + 1 < len(s) and s[j] == "." and (m := IDENT.match(s, j + 1))): return links
        name, k, args, clo = m.group(), m.end(), "", ""
        k2 = ws(s, k)
        if k2 < len(s) and s[k2] == "(": e = match_fwd(s, k2); args, k = s[k2:e], e
        k3 = k
        while k3 < len(s) and s[k3] in " \t": k3 += 1
        if k3 < len(s) and s[k3] == "{": e = match_fwd(s, k3); clo, k = s[k3:e], e
        links.append((name, args, clo)); i = k


def backward(s, p):
    """The links before the `.` at s[p]: [(name, args, closure)], nearest first; the root of the expression is not a link."""
    links = []
    while True:
        e = p
        while e > 0 and s[e - 1].isspace(): e -= 1
        groups = []
        while e > 0 and s[e - 1] in ")}]":
            b = match_back(s, e); groups.append(s[b:e]); e = b
            while e > 0 and s[e - 1].isspace(): e -= 1
        k = e
        while k > 0 and (s[k - 1].isalnum() or s[k - 1] == "_"): k -= 1
        name = s[k:e]
        if not name or not IDENT.fullmatch(name): return links
        b = k
        while b > 0 and s[b - 1].isspace(): b -= 1
        if b == 0 or s[b - 1] != ".": return links   # `Foo(...)` is the root
        args = next((g for g in reversed(groups) if g[0] == "("), ""); clo = next((g for g in reversed(groups) if g[0] == "{"), "")
        links.append((name, args, clo)); p = b - 1


def animation(files):
    """(types, helpers) from the sources: the Animatable types and the functions that apply one, to a fixed point."""
    types, texts = set(), [blank(t) for _, t in files]
    for s in texts:
        for m in re.finditer(r"\b(?:struct|class|enum)\s+(\w+)\s*(?:<[^>{]*>)?\s*(?::[^{]*)?\{", s):
            head, body = m.group(0), s[m.end() - 1:match_fwd(s, m.end() - 1)]
            if re.search(r"\b(?:Animatable|AnimatableModifier|GeometryEffect)\b", head) or re.search(r"\bvar\s+animatableData\b", body): types.add(m.group(1))
    helpers, funcs = set(), []
    for s in texts:
        for m in re.finditer(r"\bfunc\s+(\w+)\s*(?:<[^>(]*>)?\s*\(", s):
            close = match_fwd(s, m.end() - 1); br = s.find("{", close)
            if br >= 0: funcs.append((m.group(1), s[br:match_fwd(s, br)]))
    while True:
        hre = r"\.?\b(?:%s)\s*\(" % "|".join(sorted(helpers)) if helpers else r"(?!)"
        new = {n for n, body in funcs if n not in helpers and (re.search(r"\bmodifier\s*\(\s*(?:%s)\b" % "|".join(sorted(types)) if types else r"(?!)", body)
                                                                or re.search(r"\.transition\s*\(", body) or re.search(hre, body))}
        if not new: return types, helpers
        helpers |= new


def check(files):
    bad, marks = [], 0
    types, helpers = animation(files)
    tre = re.compile(r"\b(?:%s)\b" % "|".join(sorted(types))) if types else re.compile(r"(?!)")
    for path, text in files:
        name, s = pathlib.Path(path).name, blank(text)
        for m in CALL.finditer(s):
            line = s.count("\n", 0, m.start()) + 1
            if name == "CensusFrame.swift" and "func censusFrame" in s[s.rfind("\n", 0, m.start()) + 1:m.end() + 60]: continue
            marks += 1
            mark = (NAME.match(text[m.end() - 1:]) or [None, "?"])[1]
            end = match_fwd(s, m.end() - 1)
            for ln, args, clo in forward(s, end):
                if ln == "transition" or ln in helpers or (ln == "modifier" and tre.search(args)):
                    bad.append("%s:%d mark %s sits before an animation (%s): it goes after any animation modifier" % (name, line, mark, ln + (" " + tre.search(args).group() if ln == "modifier" else "")))
                if ln == "offset": bad.append("%s:%d mark %s sits before an .offset: an offset after the mark moves the ink off its frame" % (name, line, mark))
            if any(ln == "offset" for ln, _, _ in backward(s, m.start())) and (name, mark) not in ALLOW:
                bad.append("%s:%d mark %s is on an element with a static .offset: say it in layout (padding, alignment) or allow-list it with a reason" % (name, line, mark))
    return bad, marks


BEAT = "struct Beat: ViewModifier, Animatable {\n    var animatableData: Double { 0 }\n}\nstruct DrawnRule: ViewModifier, Animatable {}\n"
HELPER = "extension View {\n    func enter(_ p: Double) -> some View {\n        modifier(Beat(p: p))\n    }\n}\n"


def selftest():
    def run(src, extra=""): return check([("Immersion.swift", BEAT + HELPER), ("A.swift", src + extra)])[0]
    guilt = {
        "G1 a mark before its Beat": 'chip(a)\n    .censusFrame("chip.national", t)\n    .modifier(Beat(p: 1, from: 0, to: 1, dy: 6))\n',
        "G2 a mark, then an offset": 'cap(a)\n    .censusFrame("cap")\n    .offset(y: 9)\n',
        "G3 an offset above the mark": 'label(a)\n    .offset(x: 4)\n    .censusFrame("bali.label")\n',
        "G4 a mark before DrawnRule": 'rule(a)\n    .censusFrame("rule")\n    .modifier(DrawnRule(p: arrival, from: 0, to: 1))\n',
        "G5 a mark, a multi-line overlay, an offset": 'cap(a)\n    .censusFrame("cap")\n    .overlay {\n        Color.clear\n    }\n    .offset(y: 9)\n',
        "G6 an offset, a multi-line background, the mark": 'chip(a)\n    .offset(x: 9)\n    .background {\n        Color.clear\n    }\n    .censusFrame("chip.bali")\n',
        "G7 a mark, then a wrapped .modifier(Beat)": 'chip(a)\n    .censusFrame("chip.national")\n    .modifier(\n        Beat(p: 1, from: 0, to: 1, dy: 6))\n',
        "G8 a mark before a helper that applies Beat": 'chip(a)\n    .censusFrame("chip.national")\n    .enter(p)\n',
        "G9 an offset with a space": 'cap(a)\n    .censusFrame("cap")\n    .offset (y: 9)\n',
        "G10 a mark before a transition": 'chip(a)\n    .censusFrame("x")\n    .transition(.opacity)\n',
        "G11 a static offset inside the marked element's own overlay": 'x\n    .overlay(alignment: .bottom) { PadiLadder().offset(y: 3.5).censusFrame("ladder") }\n',
        "G12 an offset after an offset-free closure link": 'a.censusFrame("x").overlay { b }.offset(y: 2)\n',
        "G13 the helper, one level down": 'chip(a)\n    .censusFrame("x")\n    .enterTwice(p)\n',
    }
    for label, src in guilt.items():
        extra = "extension View { func enterTwice(_ p: Double) -> some View { enter(p) } }\n" if label.startswith("G13") else ""
        got = run(src, extra)
        assert got, "%s must fail the scan" % label
    new = "struct Wobble: ViewModifier {\n    var p = 0.0\n    var animatableData: Double { get { p } set { p = newValue } }\n}\n"   # a type the list never named
    assert run('chip(a)\n    .censusFrame("x")\n    .modifier(Wobble(p: 1))\n', new), "a new Animatable type must be read from the sources"
    assert run('chip(a)\n    .censusFrame("x")\n    .modifier(Plain(p: 1))\n', new.replace("animatableData", "value")) == [], "a modifier that is not Animatable is no animation"
    innocent = {
        "I1 an unmarked sibling with an offset": 'VStack {\n    Text(a).offset(y: 2)\n    cap(a).censusFrame("cap")\n}\n',
        "I2 a mark after a Beat": 'label(a)\n    .modifier(Beat(p: 1, from: 0, to: 1, dy: 6))\n    .censusFrame("bali.label")\n    .padding(2)\n',
        "I3 an offset in a comment": 'cap(a).censusFrame("cap")\n    // was .offset(y: 3.5)\n    .padding(2)\n',
        "I4 an offset in a string": 'cap(a).censusFrame("cap")\n    .accessibilityHint("no .offset(y:) here")\n',
        "I5 an offset in a block comment": 'cap(a).censusFrame("cap")\n    /* .offset(y: 3.5) */\n    .padding(2)\n',
        "I6 an offset on the unmarked host, the mark inside its overlay": 'Color.clear\n    .offset(x: 2)\n    .overlay { PadiLadder().censusFrame("ladder") }\n',
        "I7 a mark after the helper": 'chip(a)\n    .enter(p)\n    .censusFrame("chip.national")\n',
        "I8 an offset inside a later overlay's closure": 'cap(a).censusFrame("cap")\n    .overlay { Dot().offset(y: 2) }\n',
        "I9 padding, not an offset": 'PadiLadder().padding(.bottom, -3.5).censusFrame("ladder")\n',
        "I11 a raw string holding a backslash-paren and an offset": 't = r.replacing(of: #"a\\(b) .offset(y: 1)"#, with: "x")\ncap(a).censusFrame("cap")\n',
        "I10 a string with an interpolation and quotes": 'Text("a \\(f("x")) .offset(y: 1)").censusFrame("hint")\n',
    }
    for label, src in innocent.items():
        got = run(src)
        assert got == [], "%s must pass: %s" % (label, got)
    ALLOW[("A.swift", "ladder")] = "selftest"
    assert run(guilt["G11 a static offset inside the marked element's own overlay"]) == [], "an allow-listed static offset passes"
    ALLOW.clear()
    types, helpers = animation([("Immersion.swift", BEAT + HELPER)])
    assert types == {"Beat", "DrawnRule"} and helpers == {"enter"}, (types, helpers)
    print("mark_order_check selftest ok (%d guilt + %d innocence, discovery: types %s, helpers %s)" % (len(guilt), len(innocent), sorted(types), sorted(helpers)))
    return 0


def main():
    if "--selftest" in sys.argv: return selftest()
    root = pathlib.Path(sys.argv[sys.argv.index("--sources") + 1]) if "--sources" in sys.argv else ROOT
    files = [(str(p), p.read_text()) for p in sorted(root.rglob("*.swift"))]
    bad, marks = check(files)
    types, helpers = animation(files)
    for b in bad: print("MARK-ORDER", b)
    print("mark_order_check: %d finding(s) in %d marks (allow-list: %d; animation types %s, helpers %s)" % (len(bad), marks, len(ALLOW), sorted(types), sorted(helpers)))
    return 1 if bad else 0


sys.exit(main())
