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
the View PR that names its elements arms it in ARMED (Q18). On an armed band (lead ruling 2026-10-11): a frame the
check reads that is missing FAILs naming it, never VACUOUS or a pass; every frame it reads holds ink against the
ground around it, and meets its spec measure where the spec gives one (MEASURE), so a mark on the wrong element
FAILs; a frame's value is a descriptor (a tone, a step, a fraction) or nothing, never drawn text — encensus stays the
one text instrument. Ink is a pixel whose summed RGB distance from the frame's dominant colour exceeds 60; a band is
a run of ink rows. Every C has a synthetic guilt image that must FAIL and an innocent one that must pass, plus a
forgotten mark and a mark on an empty area per C, and `cap` on a 13 pt element. Self-tests run first. Exit 1 on any
FAIL. Frames ready to arm (PR 3-h-2b, #8250 gate bindings 1-5): every JSON of the set, armed or not, speaks the census
grammar (NAMES: a closed list of names, each with its value's pattern) and agrees with the record's own state the
band snapshot writes beside its frames; a measured element is bounded on both sides; C11 finds a chip whole, never
clipped by its frame, and holds it on its frame — a mark sits outside any `.offset`/Beat, where its element lands."""
import json, pathlib, re, sys, tempfile
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
    if not xs or not ys: return {}
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
    of its scale's header, the nearest above it, and on its own frame, +-4 px. A chip is where it is SEEN, whole: a
    render offset (an entrance beat) moves the ink, and the frame — marked outside the beat — stays where it lands."""
    need(fr, "matrix.head", "matrix.chip"); heads = [(v, b[3], sum(ibox(im, b)[0::2]) / 2) for v, b in fr["matrix.head"]]
    per, off = Counter(), []
    for v, b in fr["matrix.chip"]:
        h = max((h for h in heads if h[0] == v and h[1] <= b[1]), key=lambda h: h[1], default=None)
        if h: per[round(h[1] / 4)] += 1
        c = seen(im, b); cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        if not h or abs(cx - h[2]) > 4 or abs(cx - (b[0] + b[2]) / 2) > 4 or abs(cy - (b[1] + b[3]) / 2) > 4: off.append(v)
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
    """bar = figure: a bar's structure fill over its track is the cap's fraction (the frame's value), +-2 px."""
    need(fr, "bar"); bad = []
    for v, (x0, y0, x1, y1) in fr["bar"]:
        fill = sum(near(im.getpixel((x, (y0 + y1) // 2)), STRUCTURE, 24) for x in range(x0, x1))
        if abs(fill - (x1 - x0) * float(v)) > 2: bad.append("%s fill %d of %d px" % (v, fill, x1 - x0))
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
    """first-baseline: in each multi-line row, code ink top and chip text top within 4 px of the title's (a row is
    the code and chip frames that overlap the title's vertically the most)."""
    need(fr, "row.code", "row.title", "row.chip"); bad, n = [], 0
    over = lambda a, b: min(a[3], b[3]) - max(a[1], b[1])
    for _, b in fr["row.title"]:
        bs = bands(im, b); code, chip = (max((f for _, f in fr[k]), key=lambda f: over(f, b)) for k in ("row.code", "row.chip"))
        if len(bs) < 2 or over(code, b) <= 0 or over(chip, b) <= 0: continue
        t, c, k = bs[0][0], bands(im, code)[0][0], bands(im, chip)[0][0]; n += 1
        if abs(c - t) > 4 or abs(k - t) > 4: bad.append("row at y %d: title %d code %d chip %d" % (b[1], t, c, k))
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
        if under: out.append(("y %d" % b[1], first(im, b), first(im, under)))
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
# The frames each check reads (C23: the ARMED row's own list of chips), and those it reads when present.
NEEDS = {"C11": ("matrix.head", "matrix.chip"), "C12": ("headsup.label",), "C13": ("cap", "chip.bali", "bali.label"),
         "C14": ("cap",), "C15": ("basis.lead", "basis.body"), "C16": ("bar",), "C17": ("figure", "figure.peak", "card.peak"),
         "C18": ("census", "card"), "C19": ("uraian.item",), "C20": ("row.code", "row.title", "row.chip"),
         "C21": ("ladder", "matrix"), "C22": ("group.digits", "row.code"), "C23": ()}
OPTIONAL = {"C12": ("headsup.sentence",)}
# The census grammar (#8250 gate binding 2): a frame's name is one of these, and its value matches the name's pattern —
# a tone, a step ("0"…"3" in `scaleOrder`), an ordinal, a fraction, or nothing. Never drawn text.
TONE, STEP, ORD, FRAC = r"open|restricted|closed|neutral", r"[0-3]", r"[1-9]?", r"0(?:\.\d+)?|1(?:\.0+)?|\.\d+"
NAMES = {**dict.fromkeys(("matrix.head", "matrix.chip", "matrix.cell"), STEP), "headsup.label": ORD, "headsup.sentence": ORD,
         **dict.fromkeys(("chip.national", "chip.bali", "headsup"), TONE), "bar": FRAC,
         **dict.fromkeys(("matrix", "ladder", "cap", "bali.label", "basis.lead", "basis.body", "reason.lead", "reason.body",
                          "figure", "figure.peak", "card.peak", "census", "card", "uraian.item", "row.code", "row.title",
                          "row.chip", "group.digits"), "")}

def grammar(n, v, record=None):
    """Why a frame breaks the census grammar, or None. A state value comes from the record, never from the function that
    paints the element (lead ruling 2026-10-11): one that disagrees with the record's own state FAILs."""
    if n not in NAMES: return "frame %s is no census name: the grammar is png_census's NAMES" % n
    if not re.fullmatch(NAMES[n], v): return "frame %s carries %r: not its value (%s), never drawn text" % (n, v, NAMES[n] or "none")
    axis = n[5:] if n.startswith("chip.") else n if n == "headsup" else None
    if axis in (record or {}) and v != record[axis]:
        return "frame %s carries %r, its record says %r: a value read from the painter, not the record" % (n, v, record[axis])
INK_MIN = .01

def ground(im, b):
    """The dominant colour of a ring 3 px outside b: what b's ink is told from."""
    x0, y0, x1, y1 = b; px = im.load(); W, H = im.size; xs, ys = range(max(x0 - 3, 0), min(x1 + 3, W), 2), range(max(y0 - 3, 0), min(y1 + 3, H), 2)
    ring = [px[x, y] for y in {max(y0 - 3, 0), min(y1 + 2, H - 1)} for x in xs] + [px[x, y] for x in {max(x0 - 3, 0), min(x1 + 2, W - 1)} for y in ys]
    return Counter(ring).most_common(1)[0][0]

def inked(im, b):
    """The share of b's pixels (every other one) unlike the ground around b."""
    x0, y0, x1, y1 = b; px = im.load(); g = ground(im, b); inner = [(x, y) for y in range(y0, y1, 2) for x in range(x0, x1, 2)]
    return sum(sum(abs(a - c) for a, c in zip(px[x, y], g)) > 48 for x, y in inner) / max(1, len(inner))

def seen(im, b):
    """The box of the chip drawn at b: its pixels unlike the ground around b, 3 px in, and every pixel connected to them
    up to one frame width and height outside b — a chip drawn off its frame is found whole, never clipped by it
    (#8250 gate binding 4); a Rendah chip (fill == ground) is found by its border."""
    x0, y0, x1, y1 = b; px = im.load(); g = ground(im, b); W, H = im.size; w, h = x1 - x0, y1 - y0
    unlike = lambda p: sum(abs(a - c) for a, c in zip(px[p], g)) > 48
    todo = [(x, y) for y in range(y0 + 3, y1 - 3) for x in range(x0 + 3, x1 - 3) if unlike((x, y))]
    if not todo: raise Miss("nothing drawn in a frame at %s" % (b,))
    got = set(todo)
    while todo:
        x, y = todo.pop()
        for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if q not in got and max(x0 - w, 0) <= q[0] < min(x1 + w, W) and max(y0 - h, 0) <= q[1] < min(y1 + h, H) and unlike(q):
                got.add(q); todo.append(q)
    return min(x for x, _ in got), min(y for _, y in got), max(x for x, _ in got), max(y for _, y in got)

def weight(im, b, cs):
    """The thickest run of rows in b whose pixels near cs cover 80 % of its width: a rule's weight in px."""
    xs, best, run = range(b[0], b[2], 2), 0, 0
    for y in range(b[1], b[3]):
        run = run + 1 if sum(near(im.getpixel((x, y)), cs, 24) for x in xs) >= .8 * len(xs) else 0; best = max(best, run)
    return best

# The spec's own measure of a marked element (s: px per pt), so a mark on the wrong element FAILs.
# Bounded on both sides (#8250 gate binding 1): a 64 pt figure is no cap. cap's two readers are its position checks too
# (C13: above the Bali label; C14: the right third), so a band that arms a size-measured cap arms its position with it.
MEASURE = {"cap": (lambda im, b, s: .6 * 36 * s <= first(im, b) <= 36 * s, "§3 size, title(36): first ink band 0.6-1.0 x 36 pt"),
           "headsup.sentence": (lambda im, b, s: .6 * 20 * s <= first(im, b) <= 20 * s, "D2 serif(20): first ink band 0.6-1.0 x 20 pt"),
           "bar": (lambda im, b, s: abs(b[3] - b[1] - 2 * s) <= 1 and abs(b[2] - b[0] - 48 * s) <= 2, "D5: 48 x 2 pt"),
           "matrix": (lambda im, b, s: abs(weight(im, b, STRUCTURE) - 2 * s) <= 1, "D1: a 2 pt structure rule")}

def judge(im, fr, s, c, arg):
    """An armed check: a frame it reads that is missing FAILs naming it; each one it reads holds ink and meets its
    MEASURE; then the check itself."""
    names = NEEDS[c] + (tuple(arg) if c == "C23" else ())
    missing = [n for n in names if not fr.get(n)]
    if missing: raise Miss("missing frame %s: the View must mark it" % ", ".join(missing))
    extra = OPTIONAL.get(c, ()) + (tuple(n for n in fr if n.startswith("chip.") or n == "headsup") if c == "C23" else ())
    for n in dict.fromkeys(names + extra):
        for _, b in fr.get(n, []):
            if inked(im, b) < INK_MIN: raise Miss("frame %s at %s holds no ink: a mark on an empty area" % (n, b))
            if n in MEASURE and not MEASURE[n][0](im, b, s): raise Miss("frame %s at %s is not %s" % (n, b, MEASURE[n][1]))
    return CHECKS[c](im, fr, arg)
# (PNG path relative to the set, as a regex; check; its argument). Each View PR arms its own bands here when it names
# the frames its checks read (lead ruling 2026-10-11): none is armed by the harness itself.
ARMED = []

def frames(png, im):
    """({name: [(value, px box)]} of the frames drawn whole on the canvas, px per pt)."""
    doc = json.load(open(png.with_suffix(".json"))); s = im.width / doc["width"]; fr = {}
    for f in doc["frames"]:
        why = grammar(f["name"], f["value"], doc.get("record"))
        if why: raise ValueError(why)
        x, y, w, h = (round(v * s) for v in f["frame"])
        if 0 <= x and 0 <= y and x + w <= im.width + 1 and y + h <= im.height + 1 and w > 0 and h > 0:   # wholly drawn
            fr.setdefault(f["name"], []).append((f["value"], (x, y, min(x + w, im.width), min(y + h, im.height))))
    return fr, s

def armed(png, rel, im):
    out = []
    for rx, c, arg in ARMED:
        if not re.fullmatch(rx, rel): continue
        try: ok, detail = judge(im, *frames(png, im), c, arg)
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
    """Per C, an innocent synthetic image (k = 0) and its guilt (k = 1), at 1 px per pt: (check, argument, k, paint,
    frames). Last, `cap` on a 13 pt element: 9 px of ink where §3 asks 36 pt."""
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
    xs = (60, 140, 220, 300)
    for k in (0, 1):
        yield "C11", 4, k, *m(*[word("matrix.head", str(i), (x - 10, 10, x + 10, 20)) for i, x in enumerate(xs)],
                              *[chip("matrix.chip", str(i), (x - 15 + 10 * k, 40, x + 15 + 10 * k, 64), OP) for i, x in enumerate(xs)])
        yield "C12", None, k, *m(word("headsup.label", "", (20, 10, 120, 20)), word("headsup.sentence", "", (20, 40, 300, 60 - 12 * k)))
        yield "C13", None, k, *m(word("cap", "", (250, 10, 300, 44 - 20 * k)), chip("chip.bali", "open", (240, 100, 300, 124), OP),
                                 word("bali.label", "", (240, 80, 300, 88)))
        yield "C14", None, k, *word("cap", "", (280 - 220 * k, 10, 320 - 220 * k, 44))
        yield "C15", None, k, *m(word("basis.lead", "", (20, 10, 300, 34 - 4 * k)), word("basis.body", "", (20, 60, 300, 80)))
        yield "C16", None, k, [((100, 50, 148, 52), LS), ((100, 50, 124 - 10 * k, 52), ST)], {"bar": [("0.49", (100, 50, 148, 52))]}
        yield "C17", None, k, *m(*[word("figure", "", (x - 40, y, x, y + 20)) for x, y in ((300, 10), (301, 50), (299, 90))],
                                 word("figure.peak", "", (260 - 150 * k, 130, 300 - 150 * k, 160)),
                                 ([], {"card.peak": [("", (20, 120, 340, 170))]}))
        yield "C18", None, k, *m((ink((40, 40, 300, 60)), {"card": [("", (20, 20, 380, 200))]}),
                                 word("census", "", (20, 240 + 40 * k, 200, 252 + 40 * k)))
        yield "C19", None, k, [((20, 20, 28, 22), INK)] + ink((40, 14, 380, 28)) + ink((40 - 20 * k, 34, 300, 48)), {
            "uraian.item": [("", (10, 8, 390, 56))]}
        yield "C20", None, k, *m((ink((110, 12, 290, 24)) + ink((110, 30, 250, 42)), {"row.title": [("", (100, 6, 300, 60))]}),
                                 (ink((30, 14 + 16 * k, 70, 26 + 16 * k)), {"row.code": [("", (20, 6, 80, 60))]}),
                                 chip("row.chip", "", (310, 7, 380, 31), OP))
        yield "C21", None, k, [((300, 200 - 50 * k, 380, 202 - 50 * k), GOLD[0]), ((20, 200, 290, 202), LS), ((20, 30, 290, 32), ST)] + ink(
            (310, 60, 370, 120)), {"ladder": [("", (300, 20, 380, 200))], "matrix": [("", (20, 20, 290, 202))]}
        yield "C22", None, k, *m(word("group.digits", "", (20, 10, 60, 34 - 6 * k)), word("row.code", "", (20, 55, 80, 74)))
        yield "C23", ("chip.national",), k, *chip("chip.national", "open", (20, 20, 120, 44), (OP, CL)[k])
    yield "C14", None, 1, *word("cap", "", (280, 10, 320, 19))
    yield "C14", None, 1, *word("cap", "", (280, 10, 320, 74))   # a 64 pt figure is no cap (#8250 gate binding 1)
    # a chip an entrance beat left 20 pt right of its frame, the frame still on its column: C11 reads the ink (IMM probe)
    yield "C11", 4, 1, *m(*[word("matrix.head", str(i), (x - 10, 10, x + 10, 20)) for i, x in enumerate(xs)],
                          *[([((x + 5, 40, x + 35, 64), OP)] + ink((x + 13, 46, x + 27, 58)), {"matrix.chip": [(str(i), (x - 15, 40, x + 15, 64))]})
                            for i, x in enumerate(xs)])
    # a chip a few px off its frame, which the frame used to clip (#8250 gate binding 4): 2 px passes, 6 and 10 FAIL;
    # a whole node a beat left 10 px off, its header too, its frames marked outside the beat where it lands (binding 5)
    for dx, dh, k in ((2, 0, 0), (6, 0, 1), (10, 0, 1), (10, 10, 1)):
        yield "C11", 4, k, *m(*[(ink((x - 10 + dh, 10, x + 10 + dh, 20)), {"matrix.head": [(str(i), (x - 16, 4, x + 16, 26))]})
                                for i, x in enumerate(xs)],
                              *[chip("matrix.chip", str(i), (x - 15 + dx, 40, x + 15 + dx, 64), OP)[0:1] + ({"matrix.chip": [(str(i), (x - 15, 40, x + 15, 64))]},)
                                for i, x in enumerate(xs)])

def c_selftest():
    """Each C's innocent image passes and its guilt FAILs; on the innocent image, each frame the C reads left out FAILs
    naming it, and the first one moved to an empty area FAILs as no ink."""
    out, n = [], 0
    def run(c, arg, ops, fr):
        im = Image.new("RGB", (400, 400), PAPER); d = ImageDraw.Draw(im)
        for b, col in ops: d.rectangle([b[0], b[1], b[2] - 1, b[3] - 1], fill=col)
        try: return judge(im, fr, 1, c, arg)
        except Miss as e: return False, str(e)
    for c, arg, k, ops, fr in c_cases():
        ok, detail = run(c, arg, ops, fr); n += 1
        if ok == bool(k): out.append("%s-SELFTEST %s image: %s" % (c, ("innocent", "guilt")[k], detail))
        if k: continue
        names = NEEDS[c] + (tuple(arg) if c == "C23" else ())
        for name in names:
            ok, detail = run(c, arg, ops, {x: l for x, l in fr.items() if x != name}); n += 1
            if ok or name not in detail: out.append("%s-SELFTEST %s forgotten: %s" % (c, name, detail))
        moved = {**fr, names[0]: [(v, (b[0], 330, b[2], 330 + min(b[3] - b[1], 60))) for v, b in fr[names[0]]]}
        ok, detail = run(c, arg, ops, moved); n += 1
        if ok or "no ink" not in detail: out.append("%s-SELFTEST %s on an empty area: %s" % (c, names[0], detail))
    for nm, v, rec, want in (("matrix.chip", "2", None, 1), ("matrix.cell", "3", None, 1), ("chip.bali", "open", None, 1),
                             ("bar", "0.49", None, 1), ("bar", "1.0", None, 1), ("headsup.label", "", None, 1), ("cap", "", None, 1),
                             ("matrix.chip", "Mikro", None, 0), ("matrix.chip", "", None, 0), ("chip.bali", "55101", None, 0),
                             ("cap", "49%", None, 0), ("bar", "49", None, 0), ("chip.Mikro", "open", None, 0), ("Cap", "", None, 0),
                             ("chip.bali", "closed", {"bali": "closed"}, 1), ("chip.bali", "open", {"bali": "closed"}, 0),
                             ("headsup", "restricted", {"headsup": "open"}, 0), ("chip.national", "open", {"bali": "closed"}, 1)):
        n += 1   # the grammar: a name it lists, its value's pattern, and the record's own state where it writes one
        if (grammar(nm, v, rec) is None) != bool(want): out.append("GRAMMAR-SELFTEST %s=%r %s" % (nm, v, "refused" if want else "accepted"))
    with tempfile.TemporaryDirectory() as t:   # every JSON of the set is read, armed or not (#8250 gate binding 3)
        Image.new("RGB", (40, 40), PAPER).save(pathlib.Path(t, "detail-card-unarmed.png"))
        for v, want in (("open", 1), ("Mikro", 0)):
            pathlib.Path(t, "detail-card-unarmed.json").write_text(json.dumps({"width": 40, "frames": [
                {"name": "chip.bali", "value": v, "frame": [2, 2, 30, 12]}]}))
            n += 1; ok = census(pathlib.Path(t, "detail-card-unarmed.png"), t)[0]
            if ok != bool(want): out.append("JSON-SELFTEST an unarmed band's chip.bali=%r %s" % (v, "refused" if want else "accepted"))
    return out, n

def census(png, root):
    """(ok, line, vacuous) for one PNG of the set."""
    im = Image.open(png).convert("RGB"); W, H = im.size; vac = 0
    small = im.resize((W // 4, H // 4), Image.NEAREST); px = list(small.getdata())
    share = sum(near(p, ACCENTS, 24) for p in px) / len(px)
    line = "%-40s C5 %5.2f%%" % (png.relative_to(root), share * 100)
    ok, detail = share <= 0.08, ""
    if png.name.startswith("registry-table"):
        got = c8_rows(im)
        if got is None and png.parent.name == "xxl": line += "  C8 VACUOUS (no table head)"; vac = 1
        elif got is None: line += "  C8 no table head (2 pt structure rule)"; ok = False
        elif png.parent.name == "xxl": line += "  C8 VACUOUS (rows %d; text does not scale here)" % len(got[0]); vac = 1
        else: line += "  C8 rows %d (need >= 12)" % len(got[0]); ok = ok and len(got[0]) >= 12
        if got: detail = "\n    row rules at pt %s; not rows: %s" % (" ".join(map(str, got[0])), ", ".join(got[1]) or "none")
    if png.with_suffix(".json").exists():   # the grammar binds every band that writes frames, armed or not
        try: frames(png, im)
        except (ValueError, KeyError, OSError) as e: detail += "\n    frames: %s  FAIL" % e; ok = False
    for good, msg in armed(png, str(png.relative_to(root)), im):
        detail += "\n    %s%s" % (msg, "" if good else "  FAIL"); ok = ok and good
    return ok, line + ("" if ok else "  FAIL") + detail, vac

fails = vacuous = 0
bad, n = c_selftest()
for msg in selftest() + bad: print(msg); fails += 1
print("C11-C23 self-test: %d/%d synthetic images judged right (each C: innocent passes; guilt, a forgotten mark and a "
      "mark on an empty area FAIL; cap on a 13 or a 64 pt element, a chip drawn 6, 10 or 20 px off its frame and a node a beat left off FAIL; the grammar, the record's state and an unarmed JSON); armed: %s" % (
    n - len(bad), n, ", ".join("%s on %s" % (c, rx) for rx, c, _ in ARMED) or "none (each View PR arms its bands)"))
for png in sorted(pathlib.Path(sys.argv[1]).rglob("*.png")):
    ok, line, vac = census(png, sys.argv[1]); vacuous += vac
    print(line); fails += not ok
print("png_census: %d FAIL, %d VACUOUS" % (fails, vacuous)); sys.exit(1 if fails else 0)
