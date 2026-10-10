#!/usr/bin/env python3
"""WCAG 2.x contrast for every (fg,bg) pair the KBLI Navigator views use, plus a PARITY check.
TOKENS are the (day, night) defaults of Sources/Theme.swift `pick`/`pickAA` (R19 Direction-A,
design loop 2026-10-09; contrastIncreased=false). Every TOKENS entry is re-read from Theme.swift and
a differing pair or a missing token is a PARITY failure. SITE_PAIRS are also measured under Increase
Contrast (dayHC/nightHC, the pickAA HC values and `contrastIncreased ?` redirects read from Theme.swift).
Sources/ is scanned for literal white foregrounds, so a deleted census row cannot hide a live site:
each hit outside WHITE_ALLOW is a WHITE failure, and the scan self-tests its spellings. The SITE_PAIRS
sites and RISK_CHIP are checked against the code (PARITY). Exit 1 on any FAIL, PARITY or WHITE. Python 3.9.
"""
import json, re, sys
from pathlib import Path

TOKENS = {
    "antracite": (0xF7F4EE, 0x111922), "ink": (0xEAE3D8, 0x1C2B3A),
    "inkLift": (0xFFFCF7, 0x16222E), "surfaceHi": (0xEAE3D8, 0x1C2B3A),
    "accent": (0xA44B36, 0xD08371), "accentHi": (0x853D2C, 0xDA9E90),
    "red": (0x86200F, 0xED6F5A), "zantara": (0x233D52, 0x6C9BC0),
    "statutory": (0x233D52, 0x6C9BC0), "blue": (0x233D52, 0x6C9BC0),
    "yellow": (0x5B4000, 0xC78C00), "white": (0x1D2C3B, 0xF7F4EE),
    "muted": (0x58626B, 0x8C97A1), "faint": (0x58626B, 0x8C97A1),
    "pmaOpen": (0x17452A, 0x39AC69), "pmaRestricted": (0x5B4000, 0xC78C00),
    "pmaClosed": (0x86200F, 0xED6F5A), "green": (0x17452A, 0x39AC69),
    "riskLow": (0x233D52, 0x6C9BC0), "riskMediumLow": (0x233D52, 0x6C9BC0),
    "riskMediumHigh": (0x233D52, 0x6C9BC0), "riskHigh": (0x233D52, 0x6C9BC0),
    "lineSoft": (0xDAD8D1, 0x243649), "lineStrong": (0xA8ACA9, 0x416283),
    "scrim": (0xEAE3D8, 0x1C2B3A),
    "iconOnAccentFill": (0xF7F4EE, 0x111922), "iconOnZantaraFill": (0xF7F4EE, 0x111922),
    "decor": (0xB8862B, 0xC28D2D), "decorGold": (0xB8862B, 0xC28D2D),
    "chipOpenFg": (0x17452A, 0xDDEBDF), "chipOpenBg": (0xDDEBDF, 0x142F26),
    "chipRestrictedFg": (0x5B4000, 0xF4E3B9), "chipRestrictedBg": (0xF4E3B9, 0x362C11),
    "chipClosedFg": (0x86200F, 0xF4D6D0), "chipClosedBg": (0xF4D6D0, 0x4C1C18),
    "riskFillLow": (0xF7F4EE, 0x111922), "riskFillMediumLow": (0xD7D9D7, 0x1F2C3A),
    "riskFillMediumHigh": (0xADB4B7, 0x314659), "riskFillHigh": (0x233D52, 0x6C9BC0),
    "riskInk": (0x233D52, 0xF7F4EE), "riskInkOnHigh": (0xF7F4EE, 0x111922),
}

def hex_to_rgb(h): return ((h >> 16) & 0xFF, (h >> 8) & 0xFF, h & 0xFF)
def srgb_to_lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
def rel_lum(rgb):
    r, g, b = rgb
    return 0.2126*srgb_to_lin(r) + 0.7152*srgb_to_lin(g) + 0.0722*srgb_to_lin(b)
def contrast_ratio(rgb1, rgb2):
    l1, l2 = rel_lum(rgb1), rel_lum(rgb2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)
def composite(fg_rgb, alpha, bg_rgb):
    return tuple(round(fg_rgb[i]*alpha + bg_rgb[i]*(1-alpha)) for i in range(3))
HC = {}  # token -> (dayHC, nightHC) or the token it redirects to under Increase Contrast

def theme_rgb(token, theme):
    idx = 0 if theme.startswith("day") else 1
    hc = HC.get(token) if theme.endswith("HC") else None
    if isinstance(hc, str): return theme_rgb(hc, theme)
    return hex_to_rgb(hc[idx] if hc else TOKENS[token][idx])
def bg_rgb_for(spec, theme):
    if spec[0] == "solid": return theme_rgb(spec[1], theme)
    _, fg_tok, alpha, base_tok = spec
    return composite(theme_rgb(fg_tok, theme), alpha, theme_rgb(base_tok, theme))

# (label, fg_token, bg_spec, min_required, source)
PAIRS = [
    ("white/antracite", "white", ("solid","antracite"), 4.5, "RootView.swift:104 .background(Theme.antracite)"),
    ("white/ink", "white", ("solid","ink"), 4.5, "RootView.swift:120 .background(Theme.ink)"),
    ("white/inkLift", "white", ("solid","inkLift"), 4.5, "GlassCard fill Theme.inkLift"),
    ("muted/antracite", "muted", ("solid","antracite"), 4.5, "RootView.swift:340 .foregroundStyle(Theme.muted) on window bg"),
    ("muted/ink", "muted", ("solid","ink"), 4.5, "SearchListView.swift:437/442 on Theme.ink; = neutral chip (Theme.chip(.neutral): muted on wash)"),
    ("muted/inkLift", "muted", ("solid","inkLift"), 4.5, "KBLIDossierView.swift:60/100 on card"),
    ("faint/antracite", "faint", ("solid","antracite"), 4.5, "RootView.swift:142 on window bg; SearchFieldBar.swift:48 density glyph on the bar"),
    ("faint/ink", "faint", ("solid","ink"), 4.5, "RegistryVerdictSheet.swift:93/108 on Theme.ink"),
    ("faint/inkLift", "faint", ("solid","inkLift"), 4.5, "KBLIDetailView.swift:102/207 on card"),
    ("accent/antracite", "accent", ("solid","antracite"), 4.5, "KBLIDetailRichView.swift:379 accent link on window"),
    ("accent/inkLift", "accent", ("solid","inkLift"), 4.5, "KBLIRegistryView.swift:137/2023 accent on card"),
    ("zantara/antracite", "zantara", ("solid","antracite"), 4.5, "ChatView.swift:48/105/117 zantara label on window"),
    ("zantara/ink", "zantara", ("solid","ink"), 4.5, "KBLIDetailRichView.swift:358/366 zantara on ink"),
    ("statutory/inkLift", "statutory", ("solid","inkLift"), 4.5, "KBLIRegistryView.swift:992 statutory pill text"),
    ("statutory/ink", "statutory", ("solid","ink"), 4.5, "KBLIRegistryView.swift:1567/1601 statutory on ink"),
    ("yellow/antracite", "yellow", ("solid","antracite"), 4.5, "KBLIRegistryView.swift:481/893 yellow on window"),
    ("yellow/inkLift", "yellow", ("solid","inkLift"), 4.5, "KBLIDetailView.swift:93 gold-tier label on card"),
    ("white/ink@0.6-on-antracite", "white", ("composite","ink",0.6,"antracite"), 4.5, "ChatView.swift:61/180 header/footer strip"),
    ("faint/ink@0.6-on-antracite", "faint", ("composite","ink",0.6,"antracite"), 4.5, "ChatView.swift:53 on header strip"),
    ("muted/ink@0.6-on-antracite", "muted", ("composite","ink",0.6,"antracite"), 4.5, "ChatView.swift:58/90 on header/footer strip"),
    ("white/zantara@0.08-on-antracite", "white", ("composite","zantara",0.08,"antracite"), 4.5, "ChatView.swift:106/110 assistant quote strip"),
    # --- R19 additions (20) ---
    ("statutory/antracite", "statutory", ("solid","antracite"), 4.5, "structure on paper (Theme.structure / hairlineHi under HC)"),
    ("pmaOpen/antracite", "pmaOpen", ("solid","antracite"), 4.5, "Theme.kbliStatusColor / pmaOpen glyph on window"),
    ("pmaOpen/inkLift", "pmaOpen", ("solid","inkLift"), 4.5, "pmaOpen glyph on card"),
    ("pmaOpen/ink", "pmaOpen", ("solid","ink"), 4.5, "pmaOpen glyph on panel"),
    ("pmaClosed/antracite", "pmaClosed", ("solid","antracite"), 4.5, "pmaClosed glyph on window"),
    ("pmaClosed/inkLift", "pmaClosed", ("solid","inkLift"), 4.5, "pmaClosed glyph on card"),
    ("pmaClosed/ink", "pmaClosed", ("solid","ink"), 4.5, "pmaClosed glyph on panel"),
    ("accent/ink", "accent", ("solid","ink"), 4.5, "accent text on panel (wash)"),
    ("yellow/ink", "yellow", ("solid","ink"), 4.5, "yellow text on panel (wash)"),
    ("pmaRestricted/ink", "pmaRestricted", ("solid","ink"), 4.5, "pmaRestricted glyph on panel (wash)"),
    ("chipOpenFg/chipOpenBg", "chipOpenFg", ("solid","chipOpenBg"), 4.5, "Theme.chip(.open) — StatusBadge(tone:)"),
    ("chipRestrictedFg/chipRestrictedBg", "chipRestrictedFg", ("solid","chipRestrictedBg"), 4.5, "Theme.chip(.restricted) — StatusBadge(tone:)"),
    ("chipClosedFg/chipClosedBg", "chipClosedFg", ("solid","chipClosedBg"), 4.5, "Theme.chip(.closed) — StatusBadge(tone:)"),
    ("riskInk/riskFillLow", "riskInk", ("solid","riskFillLow"), 4.5, "Theme.riskChip rank 1 — StatusBadge(risk:)"),
    ("riskInk/riskFillMediumLow", "riskInk", ("solid","riskFillMediumLow"), 4.5, "Theme.riskChip rank 2 — StatusBadge(risk:)"),
    ("riskInk/riskFillMediumHigh", "riskInk", ("solid","riskFillMediumHigh"), 4.5, "Theme.riskChip rank 3 — StatusBadge(risk:)"),
    ("riskInkOnHigh/riskFillHigh", "riskInkOnHigh", ("solid","riskFillHigh"), 4.5, "Theme.riskChip rank 4 — StatusBadge(risk:)"),
    # (SITE_PAIRS below: the same chip painted at its live non-StatusBadge call sites)
    ("iconOnAccentFill/accent", "iconOnAccentFill", ("solid","accent"), 4.5, "ChatView send button: iconOnAccentFill on accent"),
    ("iconOnZantaraFill/zantara", "iconOnZantaraFill", ("solid","zantara"), 4.5, "BZLogo fallback glyph: iconOnZantaraFill on zantara"),
    ("muted/surfaceHi", "muted", ("solid","surfaceHi"), 4.5, "muted text on hover/inset surface"),
]

# Live call sites that paint `Theme.riskChip` themselves (not through StatusBadge): every tier's pair
# plus the unranked fallback (muted on wash), at each site, day / night / dayHC / nightHC.
RISK_CHIP = [("riskInk", "riskFillLow", "rank 1"), ("riskInk", "riskFillMediumLow", "rank 2"),
             ("riskInk", "riskFillMediumHigh", "rank 3"), ("riskInkOnHigh", "riskFillHigh", "rank 4"),
             ("muted", "ink", "unranked")]
SITES = ["KBLIRegistryView.swift:1541 scopeRow mini risk chip", "KBLIRegistryView.swift:1708 cellDetail risk chip"]
SITE_PAIRS = [("%s/%s@%s" % (fg, bg, site.split()[0]), fg, ("solid", bg), 4.5, "%s — Theme.riskChip %s" % (site, tier))
              for site in SITES for fg, bg, tier in RISK_CHIP]

# Literal white (or grey-scale) colours: `.white`, `Color.white`, `NSColor.white`, any `white:` / `…White:`
# initialiser (`Color(white:`, `Color.init(white:`, `.init(white:`, `Color(.sRGB, white:`, `NSColor(white:alpha:)`,
# `NSColor(calibratedWhite:`), `Color(red: 1, green: 1, blue: 1)` and `Color(hex: 0xFFFFFF)`. A grey `white:` is
# flagged too, on purpose: a literal is not a token. `Theme.white` is a token.
WHITE_RE = re.compile(r"(?<![\w.])\.white\b|\b(?:Color|NSColor)\.white\b"
                      r"|(?:\b(?:Color|NSColor)(?:\.init)?|(?<!\w)\.init)\s*\((?:\s*\.\w+\s*,)?\s*\w*[wW]hite\s*:"
                      r"|\b(?:Color|NSColor)(?:\.init)?\s*\((?:\s*\.\w+\s*,)?\s*red\s*:\s*1(?:\.0*)?\s*,\s*green\s*:\s*1(?:\.0*)?\s*,\s*blue\s*:\s*1(?:\.0*)?\b"
                      r"|\bColor(?:\.init)?\s*\(\s*hex\s*:\s*0x[fF]{6}(?:[fF]{2})?\b")
# Self-test, run on every invocation: each GUILT spelling must hit, no INNOCENT line may.
WHITE_GUILT = ["Text(x).foregroundStyle(.white)", "Color.white", "NSColor.white", "Color(white: 1)", "Color( white: 1)",
               "Color.init(white: 1)", ".foregroundStyle(.init(white: 1))", "Color(.sRGB, white: 1, opacity: 1)",
               "NSColor(white: 1, alpha: 1)", "NSColor(calibratedWhite: 1, alpha: 1)", "Color(red: 1, green: 1, blue: 1)",
               "Color(red:1.0,green:1.0,blue:1.0)", "Color(hex: 0xFFFFFF)", "Color(hex:0xffffffff)"]
WHITE_INNOCENT = ["Text(x).foregroundStyle(Theme.white)", "CharacterSet.whitespaces", "Color(red: 1, green: 0.5, blue: 1)",
                  "Color(red: 1, green: 1, blue: 10)", "Color(hex: 0xF7F4EE)", "Color(hex: isDark ? dark : light)"]
# A hit allowed on purpose: (path relative to Sources/, line number, stripped line) -> reason (e.g. photo overlay).
# Keyed by line NUMBER too, so one reason admits one line; an entry that matches no hit is stale and fails.
WHITE_ALLOW = {}

def white_sites(src):
    hits, used = [], set()
    for f in sorted(Path(src).rglob("*.swift")):
        for n, line in enumerate(f.read_text().splitlines(), 1):
            key = (str(f.relative_to(src)), n, line.strip())
            if line.strip().startswith("//") or not WHITE_RE.search(line): continue
            if WHITE_ALLOW.get(key, "").strip(): used.add(key)
            else: hits.append("WHITE %s:%d %s" % key)
    hits += ["WHITE-ALLOW %s:%d stale or without a reason" % k[:2] for k in WHITE_ALLOW if k not in used]
    hits += ["WHITE-SELFTEST missed: %s" % g for g in WHITE_GUILT if not WHITE_RE.search(g)]
    return hits + ["WHITE-SELFTEST false hit: %s" % i for i in WHITE_INNOCENT if WHITE_RE.search(i)]

def site_parity(src, theme_path):
    """RISK_CHIP must equal Theme.riskChip's switch (aliases resolved), and each SITES line must paint riskChip's fg."""
    text, bad = Path(theme_path).read_text(), []
    alias = dict(re.findall(r"static var (\w+): Color\s*\{\s*(\w+)\s*\}", text))
    body = text[text.find("static func riskChip"):]; body = body[:body.find("\n    }\n")]
    code = {k: (alias.get(fg, fg), alias.get(bg, bg)) for k, fg, bg in re.findall(r"(case \d|default):\s*return \((\w+), (\w+)", body)}
    table = {("case " + t.split()[1]) if t.startswith("rank") else "default": (fg, bg) for fg, bg, t in RISK_CHIP}
    if code != table: bad.append("PARITY RISK_CHIP %s != Theme.riskChip %s" % (sorted(table.items()), sorted(code.items())))
    for site in SITES:
        name, n = site.split()[0].split(":"); n = int(n)
        lines = next(Path(src).rglob(name)).read_text().splitlines()
        if ".fg)" not in lines[n - 1] or "Theme.riskChip(" not in "\n".join(lines[max(0, n - 4):n]):
            bad.append("PARITY site %s does not paint Theme.riskChip(…).fg: %s" % (site.split()[0], lines[n - 1].strip()))
    return bad

def parse_hc(path):
    out = {}
    for line in Path(path).read_text().splitlines():
        m = re.search(r"static var (\w+): Color\s*\{\s*contrastIncreased \? (\w+) :", line)
        h = re.search(r"static var (\w+): Color.*lightHC: 0x([0-9A-Fa-f]{6}), darkHC: 0x([0-9A-Fa-f]{6})", line)
        if m: out[m.group(1)] = m.group(2)
        elif h: out[h.group(1)] = (int(h.group(2), 16), int(h.group(3), 16))
    return out

THEME_RE = re.compile(r"static var (\w+): Color\s*\{\s*(?:contrastIncreased \? \w+ : )?pick(?:AA)?\(0x([0-9A-Fa-f]{6}), 0x([0-9A-Fa-f]{6})")

def parse_theme(path):
    out = {}
    for line in Path(path).read_text().splitlines():
        m = THEME_RE.search(line)
        if m: out[m.group(1)] = (int(m.group(2), 16), int(m.group(3), 16))
    return out

def parity(theme_path):
    parsed, bad = parse_theme(theme_path), []
    fmt = lambda p: "(0x%06X, 0x%06X)" % p
    for name, pair in TOKENS.items():
        if name not in parsed: bad.append("PARITY %s not in Theme.swift" % name)
        elif parsed[name] != pair: bad.append("PARITY %s theme.swift=%s tool=%s" % (name, fmt(parsed[name]), fmt(pair)))
    return bad

def main():
    args = sys.argv[1:]
    theme_path = args[args.index("--theme") + 1] if "--theme" in args else Path(__file__).resolve().parents[2] / "Sources" / "Theme.swift"
    src = args[args.index("--sources") + 1] if "--sources" in args else Path(__file__).resolve().parents[2] / "Sources"
    HC.update(parse_hc(theme_path))
    results = []
    rows = [(p, ("day", "night")) for p in PAIRS] + [(p, ("day", "night", "dayHC", "nightHC")) for p in SITE_PAIRS]
    for (label, fg_tok, bg_spec, min_req, source), themes in rows:
        for theme in themes:
            fg = theme_rgb(fg_tok, theme)
            bg = bg_rgb_for(bg_spec, theme)
            ratio = round(contrast_ratio(fg, bg), 2)
            results.append({
                "pair": label, "theme": theme,
                "fg": "#%02X%02X%02X" % fg, "bg": "#%02X%02X%02X" % bg,
                "ratio": ratio, "min_required": min_req, "pass": ratio >= min_req,
                "source": source,
            })
    print(json.dumps(results, indent=2))
    fails = [x for x in results if not x["pass"]]
    bad = parity(theme_path) + site_parity(src, theme_path)
    sys.stderr.write("TOTAL=%d FAIL=%d\n" % (len(results), len(fails)))
    for x in fails:
        sys.stderr.write("  FAIL %s [%s] ratio=%s < %s\n" % (x["pair"], x["theme"], x["ratio"], x["min_required"]))
    for b in bad: sys.stderr.write(b + "\n")
    sys.stderr.write("PARITY=%d\n" % len(bad))
    white = white_sites(src)
    for w in white: sys.stderr.write(w + "\n")
    sys.stderr.write("WHITE=%d\n" % len(white))
    sys.exit(1 if fails or bad or white else 0)

if __name__ == "__main__":
    main()
