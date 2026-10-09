"""Derive R19 night/HC tokens from the DAY values (SPEC-swiftui 1.1) and --check Theme.swift. Py3.9."""
import re, sys, colorsys
rgb = lambda h: [(h >> 16) & 255, (h >> 8) & 255, h & 255]
hx = lambda c: (c[0] << 16) | (c[1] << 8) | c[2]
lin = lambda v: v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
lum = lambda c: sum(w * lin(v / 255) for w, v in zip((.2126, .7152, .0722), c))
cr = lambda a, b: (max(lum(a), lum(b)) + .05) / (min(lum(a), lum(b)) + .05)
hls = lambda h: colorsys.rgb_to_hls(*[v / 255 for v in rgb(h)])
mk = lambda H, L, S: hx([round(v * 255) for v in colorsys.hls_to_rgb(H, L, S)])
mix = lambda a, b, t: hx([round(t * x + (1 - t) * y) for x, y in zip(rgb(a), rgb(b))])
WASH = {0: 0xEAE3D8, 1: 0x1C2B3A}; RX = re.compile(r"static var (\w+): Color\s*\{.*?pick(?:AA)?\((.*)")
def hc(h, night):  # blend toward black/white in 0.05 steps until >= 7:1 on the wash
    t = 0.0
    while cr(rgb(mix(0xFFFFFF if night else 0, h, t)), rgb(WASH[night])) < 7.0: t += .05
    return mix(0xFFFFFF if night else 0, h, t)
def derive(P):  # P: name -> parsed hex ints (day default first); returns name -> {index: value}
    E, (H, _, S), paper = {}, hls(0x1D2C3B), hls(P["antracite"][0])[1]
    for ns, tok in {"antracite": "antracite", "inkLift": "inkLift", "ink": "ink", "surfaceHi": "ink", "scrim": "ink", "lineSoft": "lineSoft", "lineStrong": "lineStrong"}.items():
        E[ns] = {1: mk(H, .10 + abs(hls(P[tok][0])[1] - paper), S)}
    E["white"] = {1: P["antracite"][0]}; fam = {"accent": ["accent"], "red": ["red", "pmaClosed"], "zantara": "zantara statutory blue riskLow riskMediumLow riskMediumHigh riskHigh".split(),
           "yellow": ["yellow", "pmaRestricted"], "pmaOpen": ["pmaOpen", "green"], "muted": ["muted", "faint"], "decor": ["decor", "decorGold"]}
    for k, names in fam.items():
        h, _, s = hls(P[k][0]); L = next(l for l in range(101) if cr(rgb(mk(h, l / 100, s)), rgb(WASH[1])) >= 4.8)
        for n in names:
            E[n] = {1: mk(h, L / 100, s)}
            if k not in ("muted", "decor"): E[n].update({2: hc(P[k][0], 0), 3: hc(E[n][1], 1)})
    sh = lambda h, d: mk(hls(h)[0], hls(h)[1] + d, hls(h)[2])
    E["accentHi"] = {0: sh(P["accent"][0], -.08), 1: sh(E["accent"][1], .08)}
    for n, fg, bg in (("Open", "pmaOpen", "chipOpenBg"), ("Restricted", "pmaRestricted", "chipRestrictedBg"), ("Closed", "pmaClosed", "chipClosedBg")):
        E["chip%sFg" % n] = {1: P[bg][0]}; E["chip%sBg" % n] = {1: mix(P[fg][0], 0x111922, .5)}
    for n, t in (("Low", 0), ("MediumLow", .15), ("MediumHigh", .35), ("High", 1)):
        E["riskFill" + n] = {0: mix(P["zantara"][0], P["antracite"][0], t), 1: mix(E["zantara"][1], 0x111922, t)}
    return E
def parse(path):
    return {m.group(1): [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{6})", m.group(2))] for l in open(path) for m in [RX.search(l)] if m}
if __name__ == "__main__":
    P = parse(sys.argv[2] if len(sys.argv) > 2 else "Sources/Theme.swift"); E = derive(P)
    bad = ["MISMATCH %s[%d] derived=%06X theme=%s" % (n, i, v, "%06X" % P[n][i] if n in P and len(P[n]) > i else "missing") for n, d in E.items() for i, v in d.items() if n not in P or len(P[n]) <= i or P[n][i] != v]
    if "--check" not in sys.argv: print("\n".join("%-18s %s" % (n, " ".join("%06X" % v for _, v in sorted(d.items()))) for n, d in E.items()))
    else: print("\n".join(bad) or "derive: %d tokens checked, 0 mismatches" % len(E)); sys.exit(1 if bad else 0)
