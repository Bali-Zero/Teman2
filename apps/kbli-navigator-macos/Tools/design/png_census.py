#!/usr/bin/env python3
"""png_census.py <set-dir> — spec §7 census of a rendered set (Python 3.9 + Pillow).
C5: share of pixels within RGB distance 24 of copper or gold (day/night values) per PNG <= 8 %.
C8: registry-table PNGs — the code ROWS of the table, >= 12 at default text size, narrow/ included. A row is a
lineSoft rule spanning >= 80 % of the table band (x 25-97 % of the width) that (a) lies below the table head (the
2 pt structure rule, whose thickness also gives the pixel scale), (b) closes a stripe >= 32 pt tall since the rule
above it (a row is 8 + 20 + 8 pt) and (c) has ink in that stripe. So a filter-bar rule (above the head), a
column-header rule (a short stripe) and a footer rule (an empty stripe) are not rows; each PNG lists the row rules
and the skipped rules in pt. Under xxl/ C8 is VACUOUS, never a pass: the harness's dynamicTypeSize does not scale
text-style or relativeTo: fonts (imperator ruling); an xxl PNG with no table head is VACUOUS too (#8200 gate P2-5).
C11-C23 (SPEC-detail-polish v3, PR 3-h-2) measure the elements a View names with `.censusFrame(name, value)`, whose
frames the band snapshot writes beside the PNG (<name>.json, `--layout-json`, pt). A check runs on a band only once
the View PR that names its elements arms it in ARMED (Q18); a missing frame then FAILs, never passes. Ink is a pixel
whose summed RGB distance from the frame's dominant colour exceeds 60; a band is a run of ink rows. Every C has a
synthetic guilt image that must FAIL and an innocent one that must pass. Self-tests run first. Exit 1 on any FAIL."""
import json, pathlib, re, sys
from collections import Counter
from PIL import Image, ImageDraw
ACCENTS = [(0xA4, 0x4B, 0x36), (0xD0, 0x83, 0x71), (0xB8, 0x86, 0x2B), (0xC2, 0x8D, 0x2D)]
LINESOFT = [(0xDA, 0xD8, 0xD1), (0x24, 0x36, 0x49)]
STRUCTURE = [(0x23, 0x3D, 0x51), (0x6C, 0x9B, 0xC0)]
near = lambda p, cs, d: any(sum((a - b) ** 2 for a, b in zip(p, c)) <= d * d for c in cs)
THEME = (pathlib.Path(__file__).resolve().parents[2] / "Sources" / "Theme.swift").read_text()

def tok(name):
    """A Theme colour token's (day, night) RGB, through an alias (`wash` is `ink`)."""
    body = re.search(r"static var %s: Color\s*\{([^}]*)\}" % name, THEME).group(1)
    pick = re.search(r"pick\w*\(0x(\w{6}),\s*0x(\w{6})", body)
    return [tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) for h in pick.groups()] if pick else tok(body.strip())
TONE_BG = {t: tok("chip%sBg" % t.title()) for t in ("open", "restricted", "closed")}; TONE_BG["neutral"] = tok("wash")
TONE_FG = {t: tok("chip%sFg" % t.title()) for t in ("open", "restricted", "closed")}; TONE_FG["neutral"] = tok("muted")
GOLD, PAPER, INK = tok("decorGold"), tok("antracite")[0], tok("white")[0]

class Miss(Exception): pass

def scan(im, b):
    """{y: [x, ...]} of the ink pixels in box b, 3 px in (a chip's rounded corner is no ink), against the box's
    dominant colour."""
    x0, y0, x1, y1 = b; px = im.load(); xs, ys = range(x0 + 3, x1 - 3), range(y0 + 3, y1 - 3)
    bg = Counter(px[x, y] for y in ys[::2] for x in xs[::2]).most_common(1)[0][0]
    rows = {y: [x for x in xs if sum(abs(a - c) for a, c in zip(px[x, y], bg)) > 60] for y in ys}
    return {y: r for y, r in rows.items() if r}

def bands(im, b):
    out = []
    for y in sorted(scan(im, b)):
        if out and out[-1][1] == y - 1: out[-1][1] = y
        else: out.append([y, y])
    if not out: raise Miss("no ink in a frame at %s" % (b,))
    return out
first = lambda im, b: (lambda t: t[1] - t[0] + 1)(bands(im, b)[0])

def ibox(im, b):
    rows = scan(im, b)
    if not rows: raise Miss("no ink in a frame at %s" % (b,))
    return min(r[0] for r in rows.values()), min(rows), max(r[-1] for r in rows.values()), max(rows)

def need(fr, *names):
    if any(not fr.get(n) for n in names): raise Miss("no %s frame" % ", ".join(n for n in names if not fr.get(n)))

def rule(im, b, cs, share):
    """The lowest row in b (or 2 px under it) whose pixels near cs cover `share` of its width."""
    xs = range(b[0], b[2], 2)
    return next((y for y in range(min(b[3] + 2, im.height) - 1, b[1] - 1, -1)
                 if sum(near(im.getpixel((x, y)), cs, 12) for x in xs) >= share * len(xs)), None)
nearest = lambda p, table: min(table, key=lambda t: min(sum(abs(a - c) for a, c in zip(p, q)) for q in table[t]))

def c11(im, fr, rows):
    """matrix-columns: each matrix (its header row) holds the fixture's row count of chips, each centred on the ink
    of its scale's header, the nearest above it, +-4 px."""
    need(fr, "matrix.head", "matrix.chip"); heads = [(v, b[3], sum(ibox(im, b)[0::2]) / 2) for v, b in fr["matrix.head"]]
    per, off = Counter(), []
    for v, b in fr["matrix.chip"]:
        h = max((h for h in heads if h[0] == v and h[1] <= b[1]), key=lambda h: h[1], default=None)
        if h: per[round(h[1] / 4)] += 1
        if not h or abs((b[0] + b[2]) / 2 - h[2]) > 4: off.append(v)
    ok = bool(per) and set(per.values()) == {rows} and not off
    return ok, "chips per matrix %s (need %d), off their header: %s" % (sorted(per.values()), rows, off or "none")

def c12(im, fr, _):
    """heads-up hierarchy: each sentence's first band >= 1.6 x its label's; no sentence: the label's >= 30 px."""
    need(fr, "headsup.label"); sent, out = dict(fr.get("headsup.sentence", [])), []
    for v, b in fr["headsup.label"]:
        lab = first(im, b); sen = first(im, sent[v]) if v in sent else None
        out.append((sen / lab >= 1.6 if sen else lab >= 30, "%s %s/%d px" % (v or "block", sen or "-", lab)))
    return all(o for o, _ in out), "sentence/label " + ", ".join(d for _, d in out) + " (need >= 1.6; alone >= 30)"

def c13(im, fr, _):
    """cap-leads: the cap's first band >= 2.5 x the Bali chip's text band, and the cap above the Bali label."""
    need(fr, "cap", "chip.bali", "bali.label")
    cap = bands(im, fr["cap"][0][1])[0]; chip = first(im, fr["chip.bali"][0][1]); lab = bands(im, fr["bali.label"][0][1])[0][0]
    h = cap[1] - cap[0] + 1
    return h >= 2.5 * chip and cap[0] < lab, "cap %d px / Bali chip text %d px; cap top %d, Bali label top %d" % (
        h, chip, cap[0], lab)

def c14(im, fr, _):
    """verdict on the right: the cap's ink lies in the canvas's right third."""
    need(fr, "cap"); x = ibox(im, fr["cap"][0][1])[0]
    return x >= im.width * 2 / 3, "cap ink from x %d (need >= %d)" % (x, -(-im.width * 2 // 3))

def c15(im, fr, _):
    """basis-lead: the lead's first band above the body's top and >= 1.15 x the body's first band."""
    need(fr, "basis.lead", "basis.body")
    lead = bands(im, fr["basis.lead"][0][1])[0]; body = min((bands(im, b)[0] for _, b in fr["basis.body"]), key=lambda t: t[0])
    lh, bh = lead[1] - lead[0] + 1, body[1] - body[0] + 1
    return lead[1] < body[0] and lh >= 1.15 * bh, "lead %d px ending y %d, body %d px from y %d" % (lh, lead[1], bh, body[0])

def c16(im, fr, _):
    """bar = figure: a bar's structure fill over its track is the cap / 100 (the frame's value), +-2 px."""
    need(fr, "bar"); bad = []
    for v, (x0, y0, x1, y1) in fr["bar"]:
        fill = sum(near(im.getpixel((x, (y0 + y1) // 2)), STRUCTURE, 24) for x in range(x0, x1))
        if abs(fill - (x1 - x0) * float(v) / 100) > 2: bad.append("%s%% fill %d of %d px" % (v, fill, x1 - x0))
    return not bad, "%d bars, off their figure: %s" % (len(fr["bar"]), ", ".join(bad) or "none")

def c17(im, fr, _):
    """figure-axis: trailing figures' right edges equal +-2 px; the peak's within 48 px of its card's inner edge."""
    need(fr, "figure", "figure.peak", "card.peak")
    r = [ibox(im, b)[2] for _, b in fr["figure"]]; p = ibox(im, fr["figure.peak"][0][1])[2]; c = fr["card.peak"][0][1][2]
    return max(r) - min(r) <= 2 and c - p <= 48, "figure right edges %d-%d; peak %d, card inner edge %d" % (
        min(r), max(r), p, c)

def c18(im, fr, _):
    """census-gap: the census's first ink <= 64 px under the last result card."""
    need(fr, "census", "card"); y = bands(im, fr["census"][0][1])[0][0]; end = max(b[3] for _, b in fr["card"])
    return y - end <= 64, "census ink at y %d, cards end at %d: gap %d px (need <= 64)" % (y, end, y - end)

def c19(im, fr, _):
    """hang: a wrapped "- " item's second line starts at its text's x, not the dash's, +-2 px."""
    need(fr, "uraian.item"); bad, n = [], 0
    for v, b in fr["uraian.item"]:
        rows = scan(im, b); bs = bands(im, b)
        if len(bs) < 2: continue
        cols = sorted({x for y in range(bs[0][0], bs[0][1] + 1) for x in rows.get(y, [])})
        text = next((c for a, c in zip(cols, cols[1:]) if c - a > 4), cols[0])
        line2 = min(rows[y][0] for y in range(bs[1][0], bs[1][1] + 1) if y in rows); n += 1
        if abs(line2 - text) > 2: bad.append("%s line 2 at x %d, text at x %d" % (v or "item", line2, text))
    if not n: raise Miss("no wrapped uraian.item")
    return not bad, "%d wrapped items, not hung: %s" % (n, ", ".join(bad) or "none")

def c20(im, fr, _):
    """first-baseline: in each multi-line row, code ink top and chip text top within 4 px of the title's."""
    need(fr, "row.code", "row.title", "row.chip"); code, chip = dict(fr["row.code"]), dict(fr["row.chip"]); bad, n = [], 0
    for v, b in fr["row.title"]:
        bs = bands(im, b)
        if len(bs) < 2 or v not in code or v not in chip: continue
        t, c, k = bs[0][0], bands(im, code[v])[0][0], bands(im, chip[v])[0][0]; n += 1
        if abs(c - t) > 4 or abs(k - t) > 4: bad.append("%s title %d code %d chip %d" % (v, t, c, k))
    if not n: raise Miss("no multi-line row")
    return not bad, "%d multi-line rows, off the title's first line: %s" % (n, ", ".join(bad) or "none")

def c21(im, fr, _):
    """ornament-on-grid: the ladder's gold ground line on the matrix's bottom lineSoft rule, +-2 px."""
    need(fr, "ladder", "matrix"); g = rule(im, fr["ladder"][0][1], GOLD, .5); m = rule(im, fr["matrix"][0][1], LINESOFT, .8)
    return g is not None and m is not None and abs(g - m) <= 2, "gold ground line y %s, matrix bottom rule y %s" % (g, m)

def c22(im, fr, _):
    """group head: each division's digits band >= 1.2 x the code band of the row under it."""
    need(fr, "group.digits", "row.code"); codes = sorted((b for _, b in fr["row.code"]), key=lambda b: b[1]); out = []
    for v, b in fr["group.digits"]:
        under = next((c for c in codes if c[1] >= b[3]), None)
        if under: out.append((v, first(im, b), first(im, under)))
    if not out: raise Miss("no division with a row under it")
    bad = ["%s %d/%d px" % o for o in out if o[1] < 1.2 * o[2]]
    return not bad, "%d division heads, under 1.2 x their row's code: %s" % (len(out), ", ".join(bad) or "none")

def c23(im, fr, _):
    """state->tone parity: a chip's fill 4 px inside its leading edge (a heads-up block's fill past its bar, and the
    bar) is the tone its record's state dispatches, the frame's value (`Theme.tone(<record field>)`)."""
    marks = [(n, v, b) for n, l in fr.items() if n.startswith("chip.") or n == "headsup" for v, b in l]
    if not marks: raise Miss("no chip.* or headsup frame")
    bad = []
    for n, v, (x0, y0, x1, y1) in marks:
        y = (y0 + y1) // 2; got = nearest(im.getpixel((x0 + (12 if n == "headsup" else 4), y)), TONE_BG)
        if n == "headsup" and nearest(im.getpixel((x0 + 2, y)), TONE_FG) != v: got += " bar"
        if got != v: bad.append("%s at %d,%d is %s, its state says %s" % (n, x0, y0, got, v))
    return not bad, "%d chips, off their state's tone: %s" % (len(marks), "; ".join(bad) or "none")

CHECKS = {"C%d" % n: f for n, f in zip(range(11, 24), (c11, c12, c13, c14, c15, c16, c17, c18, c19, c20, c21, c22, c23))}
# (PNG path relative to the set, as a regex; check; its argument). Each View PR arms its own bands here when it names
# the frames its checks read (lead ruling 2026-10-11): none is armed by the harness itself.
ARMED = []

def frames(png, im):
    doc = json.load(open(png.with_suffix(".json"))); s = im.width / doc["width"]; fr = {}
    for f in doc["frames"]:
        x, y, w, h = (round(v * s) for v in f["frame"])
        if x < im.width and y < im.height and w > 0 and h > 0:   # drawn: a frame below the canvas is not
            fr.setdefault(f["name"], []).append((f["value"], (max(x, 0), max(y, 0), min(x + w, im.width), min(y + h, im.height))))
    return fr

def armed(png, rel, im):
    out = []
    for rx, c, arg in ARMED:
        if not re.fullmatch(rx, rel): continue
        try: ok, detail = CHECKS[c](im, frames(png, im), arg)
        except (Miss, OSError, ValueError, KeyError) as e: ok, detail = False, "%s: %s" % (type(e).__name__, e)
        out.append((ok, "%s %s" % (c, detail)))
    return out

def c8_rows(im):
    """(row rules, skipped rules) in pt, or None when the table head is missing."""
    W, H = im.size; x0, x1 = int(W * .25), int(W * .97); px = im.load()
    bg = Counter(im.resize((W // 8, H // 8), Image.NEAREST).getdata()).most_common(1)[0][0]
    runs = []
    for y in range(H):
        c, n = Counter(px[x, y] for x in range(x0, x1, 4)).most_common(1)[0]
        if n < .8 * len(range(x0, x1, 4)) or near(c, [bg], 6): continue
        if runs and runs[-1][1] == y - 1 and near(c, [runs[-1][2]], 6): runs[-1][1] = y
        else: runs.append([y, y, c])
    head = next((i for i, r in enumerate(runs) if near(r[2], STRUCTURE, 24) and r[1] - r[0] >= 2), None)
    if head is None: return None
    scale = (runs[head][1] - runs[head][0] + 1) / 2
    rows, skipped, prev = [], [], runs[head][1]
    for top, bot, c in runs[head + 1:]:
        if near(c, LINESOFT, 6):
            stripe = (top - prev - 1) / scale
            inked = any(not near(px[x, y], [bg], 40) for y in range(prev + 1, top, 2) for x in range(x0, x1, 3))
            if stripe >= 32 and inked: rows.append(round(top / scale))
            else: skipped.append("%d (%s)" % (round(top / scale), "empty stripe" if not inked else "stripe %.0f pt" % stripe))
        prev = bot
    skipped += ["%d (above the table head)" % round(r[0] / scale) for r in runs[:head] if near(r[2], LINESOFT, 6)]
    return rows, skipped

def selftest():
    """A 2x synthetic table: a filter-bar rule, the head, a column-header rule, 12 rows, a footer rule -> 12 rows;
    the same with one row fewer -> 11. A detector that counted every lineSoft rule would report 15."""
    out = []
    for nrows in (12, 11):
        im = Image.new("RGB", (640, 1600), (0xF7, 0xF4, 0xEE)); d = ImageDraw.Draw(im)
        rule = lambda y, h, c: d.rectangle([0, y * 2, 639, (y + h) * 2 - 1], fill=c)
        ink = lambda y: d.rectangle([260, y * 2, 380, (y + 10) * 2], fill=(0x1D, 0x2C, 0x3B))
        ink(10); rule(40, 1, LINESOFT[0]); rule(100, 2, STRUCTURE[0]); ink(110); rule(125, 1, LINESOFT[0])
        rule(150, 1, (0xA8, 0xAC, 0xA9))
        for k in range(nrows): ink(160 + 37 * k); rule(187 + 37 * k, 1, LINESOFT[0])
        rule(700, 1, LINESOFT[0])
        got = c8_rows(im)
        if got is None or len(got[0]) != nrows or len(got[1]) != 3:
            out.append("C8-SELFTEST %d rows: got %s" % (nrows, got and (len(got[0]), got[1])))
    return out

def c_cases():
    """Per C, an innocent synthetic image (k = 0) and its guilt (k = 1): (check, argument, k, paint, frames)."""
    OP, CL, LS, ST = TONE_BG["open"][0], TONE_BG["closed"][0], LINESOFT[0], STRUCTURE[0]
    pad = lambda b, m=6: (b[0] - m, b[1] - m, b[2] + m, b[3] + m)
    ink = lambda b: [((x, b[1], x + 2, b[3]), INK) for x in range(b[2] - 2, b[0] - 1, -5)]   # glyph-like strokes
    word = lambda name, v, b: (ink(b), {name: [(v, pad(b))]})
    def chip(name, v, b, fill, t=6):
        return [(b, fill)] + ink((b[0] + 8, b[1] + t, b[2] - 8, b[3] - t)), {name: [(v, b)]}
    def m(*parts):
        ops, fr = [], {}
        for o, f in parts:
            ops += o
            for n, l in f.items(): fr.setdefault(n, []).extend(l)
        return ops, fr
    xs, ks = (60, 140, 220, 300), ("Mikro", "Kecil", "Menengah", "Besar")
    for k in (0, 1):
        yield "C11", 4, k, *m(*[word("matrix.head", n, (x - 10, 10, x + 10, 20)) for n, x in zip(ks, xs)],
                              *[chip("matrix.chip", n, (x - 15 + 10 * k, 40, x + 15 + 10 * k, 64), OP) for n, x in zip(ks, xs)])
        yield "C12", None, k, *m(word("headsup.label", "", (20, 10, 120, 20)), word("headsup.sentence", "", (20, 40, 300, 60 - 12 * k)))
        yield "C13", None, k, *m(word("cap", "", (250, 10, 300, 50 - 20 * k)), chip("chip.bali", "open", (240, 100, 300, 124), OP),
                                 word("bali.label", "", (240, 80, 300, 88)))
        yield "C14", None, k, *word("cap", "", (280 - 220 * k, 10, 320 - 220 * k, 50))
        yield "C15", None, k, *m(word("basis.lead", "", (20, 10, 300, 34 - 4 * k)), word("basis.body", "", (20, 60, 300, 80)))
        yield "C16", None, k, [((100, 50, 200, 54), LS), ((100, 50, 149 - 19 * k, 54), ST)], {"bar": [("49", (100, 50, 200, 54))]}
        yield "C17", None, k, *m(*[word("figure", "", (x - 40, y, x, y + 20)) for x, y in ((300, 10), (301, 50), (299, 90))],
                                 word("figure.peak", "", (260 - 150 * k, 130, 300 - 150 * k, 160)),
                                 ([], {"card.peak": [("", (20, 120, 340, 170))]}))
        yield "C18", None, k, *m(([], {"card": [("", (20, 20, 380, 200))]}), word("census", "", (20, 240 + 40 * k, 200, 252 + 40 * k)))
        yield "C19", None, k, [((20, 20, 28, 22), INK)] + ink((40, 14, 380, 28)) + ink((40 - 20 * k, 34, 300, 48)), {
            "uraian.item": [("", (10, 8, 390, 56))]}
        yield "C20", None, k, *m((ink((110, 12, 290, 24)) + ink((110, 30, 250, 42)), {"row.title": [("55300", (100, 6, 300, 60))]}),
                                 (ink((30, 14 + 16 * k, 70, 26 + 16 * k)), {"row.code": [("55300", (20, 6, 80, 60))]}),
                                 chip("row.chip", "55300", (310, 7, 380, 31), OP))
        yield "C21", None, k, [((300, 200 - 50 * k, 380, 202 - 50 * k), GOLD[0]), ((20, 200, 290, 202), LS)], {
            "ladder": [("", (300, 20, 380, 200))], "matrix": [("", (20, 20, 290, 202))]}
        yield "C22", None, k, *m(word("group.digits", "55", (20, 10, 60, 34 - 6 * k)), word("row.code", "55101", (20, 55, 80, 74)))
        yield "C23", None, k, *chip("chip.national", "open", (20, 20, 120, 44), (OP, CL)[k])

def c_selftest():
    out, n = [], 0
    for c, arg, k, ops, fr in c_cases():
        im = Image.new("RGB", (400, 300), PAPER); d = ImageDraw.Draw(im)
        for b, col in ops: d.rectangle([b[0], b[1], b[2] - 1, b[3] - 1], fill=col)
        try: ok, detail = CHECKS[c](im, fr, arg)
        except Miss as e: ok, detail = False, str(e)
        n += 1
        if ok == bool(k): out.append("%s-SELFTEST %s image: %s" % (c, ("innocent", "guilt")[k], detail))
    return out, n

fails = vacuous = 0
bad, n = c_selftest()
for msg in selftest() + bad: print(msg); fails += 1
print("C11-C23 self-test: %d/%d synthetic images judged right (each C: innocent passes, guilt FAILs); armed: %s" % (
    n - len(bad), n, ", ".join("%s on %s" % (c, rx) for rx, c, _ in ARMED) or "none (each View PR arms its bands)"))
for png in sorted(pathlib.Path(sys.argv[1]).rglob("*.png")):
    im = Image.open(png).convert("RGB"); W, H = im.size
    small = im.resize((W // 4, H // 4), Image.NEAREST); px = list(small.getdata())
    share = sum(near(p, ACCENTS, 24) for p in px) / len(px)
    line = "%-40s C5 %5.2f%%" % (png.relative_to(sys.argv[1]), share * 100)
    ok, detail = share <= 0.08, ""
    if png.name.startswith("registry-table"):
        got = c8_rows(im)
        if got is None and png.parent.name == "xxl": line += "  C8 VACUOUS (no table head)"; vacuous += 1
        elif got is None: line += "  C8 no table head (2 pt structure rule)"; ok = False
        elif png.parent.name == "xxl": line += "  C8 VACUOUS (rows %d; text does not scale here)" % len(got[0]); vacuous += 1
        else: line += "  C8 rows %d (need >= 12)" % len(got[0]); ok = ok and len(got[0]) >= 12
        if got: detail = "\n    row rules at pt %s; not rows: %s" % (" ".join(map(str, got[0])), ", ".join(got[1]) or "none")
    for good, msg in armed(png, str(png.relative_to(sys.argv[1])), im):
        detail += "\n    %s%s" % (msg, "" if good else "  FAIL"); ok = ok and good
    print(line + ("" if ok else "  FAIL") + detail); fails += not ok
print("png_census: %d FAIL, %d VACUOUS" % (fails, vacuous)); sys.exit(1 if fails else 0)
