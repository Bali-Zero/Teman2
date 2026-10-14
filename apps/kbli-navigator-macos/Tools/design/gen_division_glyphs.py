#!/usr/bin/env python3
"""gen_division_glyphs.py <glyphs/final dir> <out.swift>   (Python 3.9, stdlib)

Bakes the KBLI division glyph set (glyph-forge, 87 monoline SVGs on a 24 pt grid, stroke 1, currentColor) into static path
data for `DivisionGlyph.table`. Shapes (path, circle, ellipse, rect with rx) and group transforms (rotate, translate) are
flattened to absolute move/line/cubic/close ops. Titles in glyphs.json are internal and are NOT read: the glyph is drawn
without text. Op codes in the flat arrays: 0 M x y, 1 L x y, 2 C x1 y1 x2 y2 x y, 3 Z."""
import hashlib, math, os, re, sys
import xml.etree.ElementTree as ET

NS = "{http://www.w3.org/2000/svg}"
# The inputs are not in the repo: they are pinned by digest (sha256 over "name:sha256(file)" lines of the 87 files, sorted by name). A run on
# other inputs fails here instead of baking a different set silently; a deliberate change of the set changes this line in the same PR.
INPUTS_SHA256 = "883a7b289de30f5bd3f18e805b71470a01d6969de1b4b29b4924f37974796153"


def arc_to_cubics(x1, y1, rx, ry, phi, fa, fs, x2, y2):
    if rx == 0 or ry == 0:
        return [("L", x2, y2)]
    phi = math.radians(phi)
    cp, sp = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    rx, ry = abs(rx), abs(ry)
    lam = x1p ** 2 / rx ** 2 + y1p ** 2 / ry ** 2
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2
    den = rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2
    co = math.sqrt(max(0, num / den)) * (-1 if fa == fs else 1)
    cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
    cx, cy = cp * cxp - sp * cyp + (x1 + x2) / 2, sp * cxp + cp * cyp + (y1 + y2) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a
    th1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dth = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not fs and dth > 0:
        dth -= 2 * math.pi
    elif fs and dth < 0:
        dth += 2 * math.pi
    n = max(1, int(math.ceil(abs(dth) / (math.pi / 2))))
    seg = dth / n
    out = []
    t = 4 / 3 * math.tan(seg / 4)
    for i in range(n):
        a1, a2 = th1 + i * seg, th1 + (i + 1) * seg
        p = lambda a: (cx + rx * math.cos(a) * cp - ry * math.sin(a) * sp, cy + rx * math.cos(a) * sp + ry * math.sin(a) * cp)
        d = lambda a: (-rx * math.sin(a) * cp - ry * math.cos(a) * sp, -rx * math.sin(a) * sp + ry * math.cos(a) * cp)
        p1, p2 = p(a1), p(a2)
        d1, d2 = d(a1), d(a2)
        out.append(("C", p1[0] + t * d1[0], p1[1] + t * d1[1], p2[0] - t * d2[0], p2[1] - t * d2[1], p2[0], p2[1]))
    return out


def parse_path(d):
    toks = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+(?:e-?\d+)?", d)
    i, ops, cur, start, last_c, last_q, cmd = 0, [], (0.0, 0.0), (0.0, 0.0), None, None, None

    def num():
        nonlocal i
        v = float(toks[i]); i += 1
        return v
    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]; i += 1
            if cmd in "Zz":
                ops.append(("Z",)); cur = start; last_c = last_q = None
                continue
        rel = cmd.islower(); c = cmd.upper()
        ox, oy = cur if rel else (0.0, 0.0)
        if c == "M":
            x, y = num() + ox, num() + oy
            ops.append(("M", x, y)); cur = start = (x, y); cmd = "l" if rel else "L"; last_c = last_q = None
        elif c == "L":
            x, y = num() + ox, num() + oy; ops.append(("L", x, y)); cur = (x, y); last_c = last_q = None
        elif c == "H":
            x = num() + ox; ops.append(("L", x, cur[1])); cur = (x, cur[1]); last_c = last_q = None
        elif c == "V":
            y = num() + oy; ops.append(("L", cur[0], y)); cur = (cur[0], y); last_c = last_q = None
        elif c == "C":
            a = [num() + (ox if k % 2 == 0 else oy) for k in range(6)]
            ops.append(("C", *a)); last_c = (a[2], a[3]); cur = (a[4], a[5]); last_q = None
        elif c == "S":
            a = [num() + (ox if k % 2 == 0 else oy) for k in range(4)]
            c1 = (2 * cur[0] - last_c[0], 2 * cur[1] - last_c[1]) if last_c else cur
            ops.append(("C", c1[0], c1[1], a[0], a[1], a[2], a[3])); last_c = (a[0], a[1]); cur = (a[2], a[3]); last_q = None
        elif c in "QT":
            if c == "Q":
                q = (num() + ox, num() + oy); e = (num() + ox, num() + oy)
            else:
                q = (2 * cur[0] - last_q[0], 2 * cur[1] - last_q[1]) if last_q else cur
                e = (num() + ox, num() + oy)
            ops.append(("C", cur[0] + 2 / 3 * (q[0] - cur[0]), cur[1] + 2 / 3 * (q[1] - cur[1]),
                        e[0] + 2 / 3 * (q[0] - e[0]), e[1] + 2 / 3 * (q[1] - e[1]), e[0], e[1]))
            cur = e; last_q = q; last_c = None
        elif c == "A":
            rx, ry, phi, fa, fs = num(), num(), num(), int(num()), int(num())
            x, y = num() + ox, num() + oy
            ops += arc_to_cubics(cur[0], cur[1], rx, ry, phi, fa, fs, x, y); cur = (x, y); last_c = last_q = None
    return ops


def ellipse_ops(cx, cy, rx, ry):
    k = 0.5522847498
    return [("M", cx + rx, cy), ("C", cx + rx, cy + k * ry, cx + k * rx, cy + ry, cx, cy + ry),
            ("C", cx - k * rx, cy + ry, cx - rx, cy + k * ry, cx - rx, cy),
            ("C", cx - rx, cy - k * ry, cx - k * rx, cy - ry, cx, cy - ry),
            ("C", cx + k * rx, cy - ry, cx + rx, cy - k * ry, cx + rx, cy), ("Z",)]


def rect_ops(x, y, w, h, r):
    if r <= 0:
        return [("M", x, y), ("L", x + w, y), ("L", x + w, y + h), ("L", x, y + h), ("Z",)]
    k = 0.5522847498 * r
    return [("M", x + r, y), ("L", x + w - r, y), ("C", x + w - r + k, y, x + w, y + r - k, x + w, y + r),
            ("L", x + w, y + h - r), ("C", x + w, y + h - r + k, x + w - r + k, y + h, x + w - r, y + h),
            ("L", x + r, y + h), ("C", x + r - k, y + h, x, y + h - r + k, x, y + h - r),
            ("L", x, y + r), ("C", x, y + r - k, x + r - k, y, x + r, y), ("Z",)]


def matrix(tf):
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # a b c d e f
    for name, args in re.findall(r"(rotate|translate)\(([^)]*)\)", tf or ""):
        v = [float(x) for x in re.split(r"[ ,]+", args.strip())]
        if name == "translate":
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0.0)
        else:
            a = math.radians(v[0]); c, s = math.cos(a), math.sin(a)
            cx, cy = (v[1], v[2]) if len(v) > 2 else (0.0, 0.0)
            t = (c, s, -s, c, cx - c * cx + s * cy, cy - s * cx - c * cy)
        m = (m[0] * t[0] + m[2] * t[1], m[1] * t[0] + m[3] * t[1], m[0] * t[2] + m[2] * t[3], m[1] * t[2] + m[3] * t[3],
             m[0] * t[4] + m[2] * t[5] + m[4], m[1] * t[4] + m[3] * t[5] + m[5])
    return m


def apply(m, ops):
    f = lambda x, y: (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])
    out = []
    for o in ops:
        if o[0] == "Z":
            out.append(o)
        else:
            pts = [f(o[i], o[i + 1]) for i in range(1, len(o), 2)]
            out.append((o[0],) + tuple(v for p in pts for v in p))
    return out


def walk(el, m, acc):
    for ch in el:
        tag = ch.tag.replace(NS, "")
        if tag == "g":
            t = matrix(ch.get("transform"))
            nm = (m[0] * t[0] + m[2] * t[1], m[1] * t[0] + m[3] * t[1], m[0] * t[2] + m[2] * t[3], m[1] * t[2] + m[3] * t[3],
                  m[0] * t[4] + m[2] * t[5] + m[4], m[1] * t[4] + m[3] * t[5] + m[5])
            walk(ch, nm, acc)
            continue
        g = lambda k, d=0.0: float(ch.get(k, d))
        if tag == "path": ops = parse_path(ch.get("d"))
        elif tag == "circle": ops = ellipse_ops(g("cx"), g("cy"), g("r"), g("r"))
        elif tag == "ellipse": ops = ellipse_ops(g("cx"), g("cy"), g("rx"), g("ry"))
        elif tag == "rect": ops = rect_ops(g("x"), g("y"), g("width"), g("height"), g("rx"))
        else: raise SystemExit("unhandled element " + tag)
        acc += apply(m, ops)


src, out = sys.argv[1], sys.argv[2]
rows, seen = [], []
for f in sorted(os.listdir(src)):
    mt = re.match(r"div-(\d\d)\.svg$", f)
    if not mt: continue
    data = open(os.path.join(src, f), "rb").read(); raw = data.decode("utf-8")
    seen.append("%s:%s\n" % (f, hashlib.sha256(data).hexdigest()))
    if "<!DOCTYPE" in raw or "<!ENTITY" in raw: raise SystemExit("refusing " + f + ": a DTD/entity declaration")
    acc = []
    walk(ET.fromstring(raw), (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), acc)
    flat = []
    for o in acc:
        flat += [{"M": 0, "L": 1, "C": 2, "Z": 3}[o[0]]] + [round(v, 3) for v in o[1:]]
    rows.append((int(mt.group(1)), flat))
digest = hashlib.sha256("".join(seen).encode()).hexdigest()
if digest != INPUTS_SHA256: raise SystemExit("the %d input SVGs digest to %s, not the pinned %s: refusing to bake another set" % (len(seen), digest, INPUTS_SHA256))
with open(out, "w") as fh:
    fh.write("// GENERATED by Tools/design/gen_division_glyphs.py - do not edit by hand.\n")
    fh.write("// SOURCE: the KBLI division glyph set (glyph-forge, 24 pt grid, monoline, stroke 1): %d divisions. No text is carried.\n" % len(rows))
    fh.write("// INPUTS: %d SVGs, sha256 %s (pinned in the generator; the files are the design loop's, accepted in Z-DECISIONI.md \"GLYPHS FINAL\").\n" % (len(seen), digest))
    fh.write("import Foundation\n\n/// Flat op arrays per division: 0 M x y, 1 L x y, 2 C x1 y1 x2 y2 x y, 3 Z.\nenum DivisionGlyphData {\n    static let ops: [Int: [Double]] = [\n")
    for d, flat in rows:
        fh.write("        %d: [%s],\n" % (d, ", ".join(("%g" % v) for v in flat)))
    fh.write("    ]\n}\n")
print("divisions", len(rows))
