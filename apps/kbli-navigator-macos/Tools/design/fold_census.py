#!/usr/bin/env python3
"""fold_census.py <fold.jsonl>... : the verdict fold over every code (#8492 gate bindings 1-2).

Reads what `KBLI Navigator --fold-census` writes: one line per (code, language, window size), the census frames of the real RootView
(sidebar included) with the code's sheet collapsed. A code PASSES when its verdict band, reason line included, ends at or above the
sheet's bottom edge; a row with no `band` or no `sheet` mark is a MISS and FAILs, never a skip. Prints, per (language, size):
codes, passes, the sheets that grew past the default height (the default is the shortest sheet of the group), the tallest sheet, and
the top 3 by head+band height: the worst shapes C27 is armed on. Exit 1 on any FAIL or MISS, and on a file that holds no rows.

`--self-test` judges synthetic rows: an innocent set passes; a band below the sheet's edge, a band off the canvas, a row with no
`sheet` mark and an empty file each FAIL.
"""
import json, sys
from collections import defaultdict

TOL = 1.0     # pt
MARGIN = 12   # pt: the band ends this far above the sheet's bottom edge (SheetFit.margin; the lead's ruling 2026-10-15)
CAP, PEEK = 0.8, 64   # SearchListView.fitCap: min(80% of the window, the pane less a 64 pt peek of the list)

def judge(row):
    f = row.get("frames", {})
    if "band" not in f or "sheet" not in f:
        return False, "miss: no %s mark" % ("band" if "band" not in f else "sheet")
    b, s = f["band"], f["sheet"]
    if "pane" in f:   # the sheet takes at least min(what its head asks for, the cap): a shorter one is a measurement taken before the window settled
        p = f["pane"]; ask = b[1] + b[3] + MARGIN - s[1]; cap = min(CAP * (p[1] + p[3]), p[3] - PEEK)
        if s[3] < min(ask, cap) - TOL:
            return False, "unsettled: the sheet is %.0f pt, its head asks for %.0f and the cap is %.0f: the row was read before the window settled" % (s[3], ask, cap)
    bottom, edge = b[1] + b[3], s[1] + s[3]
    if bottom > row["h"] + TOL:
        return False, "band ends at %.0f pt, off the %.0f pt canvas" % (bottom, row["h"])
    if bottom > edge - MARGIN + TOL:
        return False, "band ends at %.0f pt, %s the sheet's bottom edge at %.0f pt (it must end %d pt above it)" % (
            bottom, "below" if bottom > edge + TOL else "short of the %d pt margin above" % MARGIN, edge, MARGIN)
    return True, "band %.0f, sheet bottom %.0f" % (bottom, edge)

def report(rows, say=print):
    groups = defaultdict(list)
    for r in rows: groups[(r["lang"], int(r["w"]), int(r["h"]))].append(r)
    bad = 0
    for key in sorted(groups):
        g = groups[key]; res = [(r, judge(r)) for r in g]
        fails = [(r, why) for r, (ok, why) in res if not ok]; bad += len(fails)
        heights = [r["frames"]["sheet"][3] for r in g if "sheet" in r.get("frames", {})]
        base = min(heights) if heights else 0
        grew = [h for h in heights if h > base + TOL]
        say("%s %dx%d: %d codes, %d pass, %d FAIL; default sheet %.0f pt, %d codes grew it, tallest %.0f pt" %
            (key[0], key[1], key[2], len(g), len(g) - len(fails), len(fails), base, len(grew), max(heights or [0])))
        for r, why in fails[:8]: say("    FAIL %s: %s" % (r["code"], why))
        need = sorted(((r["frames"]["band"][1] + r["frames"]["band"][3] - r["frames"]["sheet"][1], r["code"]) for r in g
                       if "band" in r.get("frames", {}) and "sheet" in r["frames"]), reverse=True)[:3]
        say("    worst head+band height: " + ", ".join("%s %.0f pt" % (c, h) for h, c in need))
        mg = sorted((r["frames"]["sheet"][1] + r["frames"]["sheet"][3] - r["frames"]["band"][1] - r["frames"]["band"][3], r["code"]) for r in g
                    if "band" in r.get("frames", {}) and "sheet" in r["frames"])
        lst = sorted((r["frames"]["pane"][3] - r["frames"]["sheet"][3], r["code"]) for r in g if "pane" in r.get("frames", {}) and "sheet" in r["frames"])
        if mg: say("    minimum margin below the band: %.0f pt (%s)" % mg[0])
        if lst: say("    least list left (pane less sheet): %.0f pt (%s)" % lst[0])
    return bad

def self_test():
    def row(band_bottom, sheet=(300, 340), h=648, marks=("band", "sheet")):
        f = {"band": [0, band_bottom - 70, 700, 70], "sheet": [0, sheet[0], 900, sheet[1]]}
        return {"code": "x", "lang": "en", "w": 1040, "h": h, "frames": {k: f[k] for k in marks}}
    ok = [row(600), row(626)]
    def prow(sheet_h, band_bottom=600):   # a pane 400 pt tall at the bottom of a 500 pt window: cap min(400, 336) = 336
        r = row(band_bottom); r["frames"]["sheet"] = [0, 300, 900, sheet_h]; r["frames"]["pane"] = [0, 100, 900, 400]; return r
    cases = [("innocent", ok, True), ("band below the sheet's edge", [row(700)], False), ("band inside the 12 pt margin", [row(632)], False),
             ("a sheet that grew to its ask", [prow(320, band_bottom=608)], True), ("a sheet that stopped short of its ask (unsettled)", [prow(290, band_bottom=608)], False),
             ("a sheet held at the cap", [prow(336, band_bottom=700)], False), ("band off the canvas", [row(900, sheet=(300, 700))], False),
             ("no sheet mark", [row(600, marks=("band",))], False), ("no band mark", [row(600, marks=("sheet",))], False)]
    wrong = 0
    for name, rows, want in cases:
        got = all(judge(r)[0] for r in rows)
        if got != want: wrong += 1; print("SELF-TEST WRONG: %s: judged %s" % (name, got))
    empty = main_files([]) == 1
    if not empty: wrong += 1; print("SELF-TEST WRONG: an empty set passed")
    print("fold_census self-test: %d of %d cases judged right" % (len(cases) + 1 - wrong, len(cases) + 1))
    return wrong

def main_files(paths):
    rows = []
    for p in paths:
        for line in open(p):
            if line.strip(): rows.append(json.loads(line))
    if not rows:
        print("fold_census: no rows: nothing was measured"); return 1
    bad = report(rows)
    print("fold_census: %d rows, %d FAIL" % (len(rows), bad))
    return 1 if bad else 0

if __name__ == "__main__":
    if "--self-test" in sys.argv: sys.exit(1 if self_test() else 0)
    sys.exit(main_files([a for a in sys.argv[1:] if not a.startswith("--")]))
