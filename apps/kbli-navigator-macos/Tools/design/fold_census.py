#!/usr/bin/env python3
"""fold_census.py <fold.jsonl>... : the verdict fold over every code (#8492 gate bindings 1-2).

Reads what `KBLI Navigator --fold-census` writes: one line per (code, language, window size), the census frames of the real RootView
(sidebar included) with the code's sheet collapsed. A code PASSES when its verdict band, reason line included, ends at or above the
sheet's bottom edge; a row with no `band` or no `sheet` mark is a MISS and FAILs, never a skip. Prints, per (language, size):
codes, passes, the sheets that grew past the default height (the default is the shortest sheet of the group), the tallest sheet, and
the top 3 by head+band height: the worst shapes C27 is armed on. Exit 1 on any FAIL or MISS, and on a file that holds no rows.

H1d adds two rules, each read from the same frames (the census selects the code AFTER the window is mounted, the way a click does; the
PNG census, png_census.py C27/C28, mounts with the code already selected, so it is the path that needs the list's `initial:` scroll):
  O1 whole rows only: the marks `band`, `plate`, `official` that are drawn each end at least 12 pt above the sheet's bottom edge, the
     plate starts 12 pt under the band and the official title 12 pt under the plate, the sheet's bottom edge is within 1 pt of the last
     drawn row's bottom + 12 (no slack for a sliver of the next row), the official title never without the plate, and a row that
     would have fitted whole under the cap is not left out (each row left out is still laid out and marked `plate.hidden` / `official.hidden`: its own bottom and the margin are what it would need).
  O2 the selected row whole in the strip: the `row.selected` mark lies inside the `strip` mark (the scroll view, which ends at the sheet's
     top), and it is a row's height at least. Neither mark present is a MISS, never a skip.

`--self-test` judges synthetic rows: an innocent set passes; a band below the sheet's edge, a band off the canvas, a row with no
`sheet` mark, an empty file and each O1 / O2 guilt FAIL.
"""
import json, sys
from collections import defaultdict

TOL = 1.0     # pt
MARGIN = 12   # pt: the band ends this far above the sheet's bottom edge (SheetFit.margin; the lead's ruling 2026-10-15)
CAP, PEEK = 0.8, 64   # SearchListView.fitCap: min(80% of the window, the pane less a 64 pt peek of the list)
ROW_MIN = 28   # pt: a mark thinner than a table row (37 pt at the comfortable density, 74 and more when its title wraps) is no row

def judge(row, collapsed=None):
    f = row.get("frames", {})
    if row.get("open"):   # E6: the expanded sheet is never shorter than the collapsed one of the same code, language and window; the selected row whole in its strip
        if "sheet" not in f: return False, "miss: no sheet mark"
        key = (row["code"], row["lang"], int(row["w"]), int(row["h"]), int(row.get("sidebar", 232)))
        if collapsed is None or key not in collapsed: return False, "no collapsed row of the same code and window to read the expanded sheet against"
        if f["sheet"][3] < collapsed[key] - TOL:
            return False, "the expanded sheet is %.0f pt, shorter than the collapsed one (%.0f pt): expanding shrank it" % (f["sheet"][3], collapsed[key])
        why = selected_in_strip(f, f["sheet"])
        return (False, why) if why else (True, "expanded sheet %.0f pt, collapsed %.0f pt" % (f["sheet"][3], collapsed[key]))
    if "band" not in f or "sheet" not in f:
        return False, "miss: no %s mark" % ("band" if "band" not in f else "sheet")
    b, s = f["band"], f["sheet"]
    if "pane" in f:   # the height rule, each side under its own cause (E9: a wrong height never reads as "unsettled")
        p = f["pane"]; cap = min(CAP * (p[1] + p[3]), p[3] - PEEK)
        last = max(f[n][1] + f[n][3] for n in ("band", "plate", "official") if n in f); ask = last + MARGIN - s[1]
        if s[3] > cap + TOL:
            return False, "the sheet is %.0f pt, over the cap of %.0f pt (min(%d%% of the window, the pane less %d pt))" % (s[3], cap, round(CAP * 100), PEEK)
        if s[3] < min(ask, cap) - TOL:
            return False, "the sheet is %.0f pt, shorter than the %.0f pt its last drawn row and margin need (cap %.0f): the height rule is wrong or the row was read before it settled" % (s[3], ask, cap)
    bottom, edge = b[1] + b[3], s[1] + s[3]
    if bottom > row["h"] + TOL:
        return False, "band ends at %.0f pt, off the %.0f pt canvas" % (bottom, row["h"])
    if bottom > edge - MARGIN + TOL:
        return False, "band ends at %.0f pt, %s the sheet's bottom edge at %.0f pt (it must end %d pt above it)" % (
            bottom, "below" if bottom > edge + TOL else "short of the %d pt margin above" % MARGIN, edge, MARGIN)
    why = whole_rows(row, f, b, s)
    if why: return False, why
    why = selected_in_strip(f, s)
    if why: return False, why
    return True, "band %.0f, sheet bottom %.0f" % (bottom, edge)

def whole_rows(row, f, b, s):
    """O1: the rows the collapsed sheet draws are whole, 12 pt apart, and the sheet ends 12 pt under the last of them."""
    edge, last, prev = s[1] + s[3], b[1] + b[3], b
    if "official" in f and "plate" not in f: return "the official title is drawn and the plate is not: a row below a row that was left out"
    for name in ("plate", "official"):
        if name not in f: continue
        m = f[name]
        if abs(m[1] - (prev[1] + prev[3]) - MARGIN) > TOL: return "%s starts at %.0f pt, %.1f under the row above (it starts %d pt under it)" % (name, m[1], m[1] - (prev[1] + prev[3]), MARGIN)
        if m[1] + m[3] > edge - MARGIN + TOL: return "%s ends at %.0f pt, %s the sheet's bottom edge at %.0f pt (a sliced row: it must end %d pt above it)" % (
            name, m[1] + m[3], "below" if m[1] + m[3] > edge + TOL else "short of the %d pt margin above" % MARGIN, edge, MARGIN)
        prev = m; last = m[1] + m[3]
    if abs((edge - last) - MARGIN) > TOL: return "the sheet's bottom edge at %.0f pt is %.1f pt under the last drawn row (%d pt: any more is slack for the next row to show in)" % (edge, edge - last, MARGIN)
    if "pane" in f:   # a row that fits whole under the cap is drawn
        p = f["pane"]; cap = min(CAP * (p[1] + p[3]), p[3] - PEEK)
        for name in ("plate", "official"):   # a row left out must not have fitted: what it needs is read off its own hidden mark
            h = f.get(name + ".hidden")
            if h is not None and h[1] + h[3] + MARGIN - s[1] <= cap - TOL:
                return "the %s is left out although it fits: it would end %.0f pt into a sheet of at most %.0f pt" % (name, h[1] + h[3] + MARGIN - s[1], cap)
    return None

def selected_in_strip(f, s):
    """O2: the selected row is drawn, one row tall, whole inside the scroll view, which ends at the sheet's top."""
    if "strip" not in f: return "miss: no strip mark (the scroll view)"
    if "row.selected" not in f: return "the selected row is not drawn: it is not in the strip above the sheet"
    r, t = f["row.selected"], f["strip"]
    if r[3] < ROW_MIN: return "row.selected is %.0f pt tall: not a row (at least %d)" % (r[3], ROW_MIN)
    if t[1] + t[3] > s[1] + TOL: return "the strip ends at %.0f pt, under the sheet's top at %.0f pt" % (t[1] + t[3], s[1])
    if r[1] < t[1] - TOL: return "the selected row starts at %.0f pt, above the strip's top at %.0f pt (sliced at the top)" % (r[1], t[1])
    if r[1] + r[3] > t[1] + t[3] + TOL: return "the selected row ends at %.0f pt, under the strip's bottom at %.0f pt (sliced by the sheet)" % (r[1] + r[3], t[1] + t[3])
    if r[0] < t[0] - TOL or r[0] + r[2] > t[0] + t[2] + TOL: return "the selected row is not inside the strip sideways"
    return None

def report(rows, say=print):
    groups = defaultdict(list)
    collapsed = {(r["code"], r["lang"], int(r["w"]), int(r["h"]), int(r.get("sidebar", 232))): r["frames"]["sheet"][3] for r in rows if not r.get("open") and "sheet" in r.get("frames", {})}
    for r in rows: groups[(r["lang"], int(r["w"]), int(r["h"]), bool(r.get("open")), int(r.get("sidebar", 232)))].append(r)
    bad = 0
    for key in sorted(groups):
        g = groups[key]; res = [(r, judge(r, collapsed)) for r in g]
        if key[3]:
            fails = [(r, why) for r, (ok, why) in res if not ok]; bad += len(fails)
            say("%s %dx%d sb%d OPEN: %d codes, %d pass, %d FAIL (expanded sheet >= collapsed, selected row whole in the strip)" % (key[0], key[1], key[2], key[4], len(g), len(g) - len(fails), len(fails)))
            for r, why in fails[:8]: say("    FAIL %s: %s" % (r["code"], why))
            continue
        fails = [(r, why) for r, (ok, why) in res if not ok]; bad += len(fails)
        heights = [r["frames"]["sheet"][3] for r in g if "sheet" in r.get("frames", {})]
        base = min(heights) if heights else 0
        grew = [h for h in heights if h > base + TOL]
        say("%s %dx%d sb%d: %d codes, %d pass, %d FAIL; default sheet %.0f pt, %d codes grew it, tallest %.0f pt" %
            (key[0], key[1], key[2], key[4], len(g), len(g) - len(fails), len(fails), base, len(grew), max(heights or [0])))
        for r, why in fails[:8]: say("    FAIL %s: %s" % (r["code"], why))
        need = sorted(((r["frames"]["band"][1] + r["frames"]["band"][3] - r["frames"]["sheet"][1], r["code"]) for r in g
                       if "band" in r.get("frames", {}) and "sheet" in r["frames"]), reverse=True)[:3]
        say("    worst head+band height: " + ", ".join("%s %.0f pt" % (c, h) for h, c in need))
        mg = sorted((r["frames"]["sheet"][1] + r["frames"]["sheet"][3] - r["frames"]["band"][1] - r["frames"]["band"][3], r["code"]) for r in g
                    if "band" in r.get("frames", {}) and "sheet" in r["frames"])
        lst = sorted((r["frames"]["pane"][3] - r["frames"]["sheet"][3], r["code"]) for r in g if "pane" in r.get("frames", {}) and "sheet" in r["frames"])
        if mg: say("    minimum margin below the band: %.0f pt (%s)" % mg[0])
        if lst: say("    least list left (pane less sheet): %.0f pt (%s)" % lst[0])
        fr = [r["frames"] for r in g if "sheet" in r.get("frames", {})]
        say("    rows drawn: band only %d, band+plate %d, band+plate+official %d" % (
            sum("plate" not in x for x in fr), sum("plate" in x and "official" not in x for x in fr), sum("official" in x for x in fr)))
        sl = sorted((x["sheet"][1] + x["sheet"][3] - max(x[n][1] + x[n][3] for n in ("band", "plate", "official") if n in x), r["code"])
                    for r, x in ((r, r["frames"]) for r in g) if "sheet" in x and "band" in x)
        sp = sorted((x["strip"][3], r["code"]) for r, x in ((r, r["frames"]) for r in g) if "strip" in x)
        cl = sorted((min(x["row.selected"][1] - x["strip"][1], x["strip"][1] + x["strip"][3] - x["row.selected"][1] - x["row.selected"][3]), r["code"])
                    for r, x in ((r, r["frames"]) for r in g) if "strip" in x and "row.selected" in x)
        fm = sorted((min(x["pane"][3] - PEEK, CAP * (x["pane"][1] + x["pane"][3])) - x["sheet"][3], r["code"]) for r, x in ((r, r["frames"]) for r in g) if "pane" in x and "sheet" in x)
        if fm: say("    free margin against the cap (cap less sheet): min %.1f pt (%s), %d rows at the cap (within 1 pt)" % (fm[0] + (sum(m < 1 for m, _ in fm),)))
        if sl: say("    O1 margin under the last drawn row: min %.1f pt (%s), max %.1f pt (%s)" % (sl[0] + sl[-1]))
        if sp: say("    O2 strip (the scroll view above the sheet): min %.0f pt (%s)" % sp[0])
        if cl: say("    O2 least clearance of the selected row inside the strip: %.1f pt (%s); rows with the mark: %d of %d" % (cl[0] + (len(cl), len(g))))
    return bad

def self_test():
    def full(**kw):
        """An innocent collapsed row (band + plate + official, en, 1040x700 window): sheet 300..620, band ends 500, plate 512..570, official 582..608."""
        f = {"pane": [0, 100, 900, 600], "strip": [0, 100, 900, 194], "sheet": [0, 300, 900, 320], "band": [0, 430, 700, 70],
             "plate": [0, 512, 700, 58], "official": [0, 582, 700, 26], "row.selected": [20, 140, 700, 37]}
        for k, v in kw.items():
            if v is None: f.pop(k, None)
            else: f[k] = v
        if "sheet" not in kw and "official" not in f: f["sheet"] = [0, 300, 900, (f["plate"][1] + f["plate"][3] + MARGIN - 300) if "plate" in f else 212]
        return {"code": "x", "lang": kw.pop("lang", "en"), "w": 1040, "h": 700, "frames": f}
    def prow(sheet_h, band_bottom=600):   # a pane 400 pt tall at the bottom of a 500 pt window: cap min(400, 336) = 336
        r = old_row(band_bottom); r["frames"]["sheet"] = [0, 300, 900, sheet_h]; r["frames"]["pane"] = [0, 100, 900, 400]; return r
    def old_row(band_bottom, sheet=None, h=648, marks=("band", "sheet")):
        sheet = sheet or (band_bottom + MARGIN - 340, 340)   # innocent by default: the sheet ends 12 pt under the band
        f = {"band": [0, band_bottom - 70, 700, 70], "sheet": [0, sheet[0], 900, sheet[1]], "strip": [0, 100, 900, sheet[0] - 100], "row.selected": [20, 110, 700, 37]}
        return {"code": "x", "lang": "en", "w": 1040, "h": h, "frames": {k: f[k] for k in f if k in marks or k in ("strip", "row.selected")}}
    def band_only(**kw):   # a tall band: sheet 120..620, band ends 608; the plate and the official title do not fit under the cap
        r = full(plate=None, official=None, sheet=[0, 120, 900, 500], band=[0, 300, 700, 308], pane=[0, 100, 900, 600], strip=[0, 100, 900, 14], **kw)
        r["frames"]["row.selected"] = [20, 100, 700, 37]; r["frames"]["strip"] = [0, 100, 900, 14 + 30]; return r
    ok = [old_row(600), old_row(626), full()]
    def two(**kw): return full(official=None, sheet=[0, 300, 900, 282], **kw)
    cases = [("innocent", ok, True), ("band below the sheet's edge", [old_row(700, sheet=(300, 340))], False), ("band inside the 12 pt margin", [old_row(632, sheet=(300, 340))], False),
             ("a sheet that grew to its ask", [prow(320, band_bottom=608)], True), ("a sheet that stopped short of its ask (unsettled)", [prow(290, band_bottom=608)], False),
             ("a sheet held at the cap", [prow(336, band_bottom=700)], False), ("band off the canvas", [old_row(900, sheet=(300, 700))], False),
             ("no sheet mark", [old_row(600, marks=("band",))], False), ("no band mark", [old_row(600, marks=("sheet",))], False),
             # O1: whole rows only
             ("O1 a plate and its official title, whole", [full()], True),
             ("O1 the plate sliced by the sheet's edge", [full(sheet=[0, 300, 900, 262], official=None)], False),
             ("O1 slack under the last row (max(470, ...) restored)", [full(sheet=[0, 300, 900, 345])], False),
             ("O1 spacing 10 not 12 under the band (a sliver)", [full(plate=[0, 510, 700, 58], official=[0, 580, 700, 26])], False),
             ("O1 the official title below the sheet's margin", [full(sheet=[0, 300, 900, 300])], False),
             ("O1 an official title with no plate", [full(plate=None)], False),
             ("O1 the plate left out with room for it", [full(plate=None, official=None, sheet=[0, 300, 900, 212], **{"plate.hidden": [0, 512, 700, 58]})], False),
             ("O1 the official title left out with room for it", [two(**{"official.hidden": [0, 582, 700, 26]})], False),
             ("O1 a plate that does not fit is left out", [full(plate=None, official=None, sheet=[0, 300, 900, 212], **{"plate.hidden": [0, 900, 700, 58]})], True),
             ("O1 id: no official title, none expected", [full(official=None, sheet=[0, 300, 900, 282], pane=[0, 100, 900, 600], lang="id")], True),
             # O2: the selected row whole in the strip
             ("O2 the selected row not drawn", [full(**{"row.selected": None})], False),
             ("O2 no strip mark", [full(strip=None)], False),
             ("O2 the row sliced at the strip's top", [full(**{"row.selected": [20, 90, 700, 37]})], False),
             ("O2 the row under the sheet", [full(**{"row.selected": [20, 280, 700, 37]})], False),
             ("O2 a degenerate mark under a row's height", [full(**{"row.selected": [20, 100, 700, 12]})], False),
             ("O2 a strip that runs under the sheet", [full(strip=[0, 100, 900, 260])], False),
             ("O2 a row flush with both edges", [full(**{"row.selected": [20, 100, 700, 37]}, strip=[0, 100, 900, 37])], True)]
    wrong = 0
    for name, rows, want in cases:
        got = all(judge(r)[0] for r in rows)
        if got != want: wrong += 1; print("SELF-TEST WRONG: %s: judged %s (%s)" % (name, got, judge(rows[0])[1]))
    def orow(sheet_h, code="x"):
        return {"code": code, "lang": "en", "w": 1040, "h": 648, "open": True, "frames": {"sheet": [0, 138, 900, sheet_h], "strip": [0, 78, 900, 54], "row.selected": [20, 86, 700, 38]}}
    def crow(sheet_h, code="x"):
        r = old_row(600, sheet=(138, sheet_h)); r["code"] = code; return r
    col = {("x", "en", 1040, 648, 232): 500}
    for name, row, want in (("E6 an expanded sheet as tall as the collapsed one", orow(506), True), ("E6 an expanded sheet taller than it", orow(560), True),
                            ("E6 expanding shrank the sheet (the 300 pt cap restored)", orow(269), False),
                            ("E6 an expanded row with no collapsed partner", orow(506, code="y"), False)):
        cases.append((name, None, want)); got = judge(row, col)[0]
        if got != want: wrong += 1; print("SELF-TEST WRONG: %s: judged %s (%s)" % (name, got, judge(row, col)[1]))
    bad_strip = orow(506); bad_strip["frames"]["row.selected"] = [20, 126, 700, 38]
    cases.append(("E6 the selected row under the strip", None, False))
    if judge(bad_strip, col)[0]: wrong += 1; print("SELF-TEST WRONG: E6 the selected row under the strip passed")
    over = full(sheet=[0, 300, 900, 340], official=None, plate=None); over["frames"]["pane"] = [0, 100, 900, 330]   # cap min(.8*430, 266) = 266, the sheet 340
    short = full(); short["frames"]["sheet"] = [0, 300, 900, 300]   # asks 320, cap 480: shorter than it asks
    for name, row, want, cause in (("E9 a sheet over the cap", over, False, "over the cap"), ("E9 a sheet shorter than its last row asks", short, False, "shorter than")):
        cases.append((name, None, want)); ok_, why_ = judge(row)
        if ok_ != want or (cause and cause not in why_) or "unsettled" in why_: wrong += 1; print("SELF-TEST WRONG: %s: judged %s (%s)" % (name, ok_, why_))
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
