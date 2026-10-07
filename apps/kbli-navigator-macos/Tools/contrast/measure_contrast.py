#!/usr/bin/env python3
"""WCAG 2.x contrast for every (fg,bg) pair the KBLI Navigator views actually use.
Hex values transcribed verbatim from Sources/Theme.swift `pick(light,dark)` /
`pickAA(light,dark,...)` (contrastIncreased=false — the default; Increase Contrast
is a separate opt-in mode not measured here). Pairs identified by grepping
Sources/Views/*.swift for foregroundStyle(Theme.X) and the .background/.fill call
that supplies the surface it sits on (see docs/design/diagnosis-2026-09-17.md).
"""
import json, sys

TOKENS = {
    "antracite": (0xF5F1E8, 0x2F3034), "ink": (0xF8F4EC, 0x34353A),
    "inkLift": (0xFFFCF7, 0x3E3F45), "surfaceHi": (0xEAE2D5, 0x47484E),
    "accent": (0x995026, 0xF5AA72), "accentHi": (0x7F3E1C, 0xFFBA86),
    "red": (0x9F3C3B, 0xFF9F98), "zantara": (0x4E5DB7, 0xB9B5FF),
    "statutory": (0x29639E, 0x91C2F7), "yellow": (0x765A00, 0xEBD077),
    "white": (0x302D29, 0xF5F3EE), "muted": (0x625D55, 0xD0CCC4),
    "faint": (0x686159, 0xBCB8B1),
    "pmaOpen": (0x176F4B, 0x6FD2B0), "pmaRestricted": (0x765A00, 0xEBD077),
    "pmaClosed": (0x9F3C3B, 0xFF9F98),
    "riskLow": (0x176F4B, 0x6FD2B0), "riskMediumLow": (0x29639E, 0x91C2F7),
    "riskMediumHigh": (0x765A00, 0xEBD077), "riskHigh": (0x9F3C3B, 0xFF9F98),
    "literalWhite": (0xFFFFFF, 0xFFFFFF),  # SwiftUI `.white` — does NOT flip per theme
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
def theme_rgb(token, theme):
    idx = 0 if theme == "day" else 1
    return hex_to_rgb(TOKENS[token][idx])
def bg_rgb_for(spec, theme):
    if spec[0] == "solid": return theme_rgb(spec[1], theme)
    _, fg_tok, alpha, base_tok = spec
    return composite(theme_rgb(fg_tok, theme), alpha, theme_rgb(base_tok, theme))

# (label, fg_token, bg_spec, min_required, source)
PAIRS = [
    ("white/antracite", "white", ("solid","antracite"), 4.5, "RootView.swift:104 .background(Theme.antracite)"),
    ("white/ink", "white", ("solid","ink"), 4.5, "RootView.swift:120 .background(Theme.ink)"),
    ("white/inkLift", "white", ("solid","inkLift"), 4.5, "GlassCard fill Theme.inkLift (Theme.swift:507)"),
    ("muted/antracite", "muted", ("solid","antracite"), 4.5, "RootView.swift:390 .foregroundStyle(Theme.muted) on window bg"),
    ("muted/ink", "muted", ("solid","ink"), 4.5, "SearchListView.swift:344/349 on Theme.ink"),
    ("muted/inkLift", "muted", ("solid","inkLift"), 4.5, "KBLIDossierView.swift:60/100 on card"),
    ("faint/antracite", "faint", ("solid","antracite"), 4.5, "RootView.swift:142 on window bg"),
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
    ("pmaOpen/pmaOpen@0.10-on-inkLift", "pmaOpen", ("composite","pmaOpen",0.10,"inkLift"), 4.5, "StatusBadge (Theme.swift:552) color.opacity(0.10) fill"),
    ("pmaRestricted/pmaRestricted@0.10-on-inkLift", "pmaRestricted", ("composite","pmaRestricted",0.10,"inkLift"), 4.5, "StatusBadge on restricted verdict"),
    ("pmaClosed/pmaClosed@0.10-on-inkLift", "pmaClosed", ("composite","pmaClosed",0.10,"inkLift"), 4.5, "StatusBadge on closed verdict"),
    ("yellow/yellow@0.10-on-inkLift", "yellow", ("composite","yellow",0.10,"inkLift"), 4.5, "StatusBadge gold-tier (KBLIDetailRichView.swift:156)"),
    ("riskLow/riskLow@0.10-on-inkLift", "riskLow", ("composite","riskLow",0.10,"inkLift"), 4.5, "StatusBadge risk (KBLIDetailView.swift:185)"),
    ("riskMediumLow/riskMediumLow@0.10-on-inkLift", "riskMediumLow", ("composite","riskMediumLow",0.10,"inkLift"), 4.5, "StatusBadge risk"),
    ("riskMediumHigh/riskMediumHigh@0.10-on-inkLift", "riskMediumHigh", ("composite","riskMediumHigh",0.10,"inkLift"), 4.5, "StatusBadge risk"),
    ("riskHigh/riskHigh@0.10-on-inkLift", "riskHigh", ("composite","riskHigh",0.10,"inkLift"), 4.5, "StatusBadge risk"),
    # C3: literal SwiftUI `.white` (does not flip per theme) on a colored fill — the pattern the
    # 2026-06-24 review flagged. Two call sites, both in KBLIRegistryView.swift.
    ("literalWhite/riskLow@0.55-on-inkLift", "literalWhite", ("composite","riskLow",0.55,"inkLift"), 4.5, "KBLIRegistryView.swift:1541 mini risk chip .foregroundStyle(.white)"),
    ("literalWhite/riskMediumLow@0.55-on-inkLift", "literalWhite", ("composite","riskMediumLow",0.55,"inkLift"), 4.5, "KBLIRegistryView.swift:1541 mini risk chip"),
    ("literalWhite/riskMediumHigh@0.55-on-inkLift", "literalWhite", ("composite","riskMediumHigh",0.55,"inkLift"), 4.5, "KBLIRegistryView.swift:1541 mini risk chip"),
    ("literalWhite/riskHigh@0.55-on-inkLift", "literalWhite", ("composite","riskHigh",0.55,"inkLift"), 4.5, "KBLIRegistryView.swift:1541 mini risk chip"),
    ("literalWhite/riskLow@0.45-on-inkLift", "literalWhite", ("composite","riskLow",0.45,"inkLift"), 4.5, "KBLIRegistryView.swift:1708 cellDetail risk pill .foregroundStyle(.white)"),
    ("literalWhite/riskMediumLow@0.45-on-inkLift", "literalWhite", ("composite","riskMediumLow",0.45,"inkLift"), 4.5, "KBLIRegistryView.swift:1708 cellDetail risk pill"),
    ("literalWhite/riskMediumHigh@0.45-on-inkLift", "literalWhite", ("composite","riskMediumHigh",0.45,"inkLift"), 4.5, "KBLIRegistryView.swift:1708 cellDetail risk pill"),
    ("literalWhite/riskHigh@0.45-on-inkLift", "literalWhite", ("composite","riskHigh",0.45,"inkLift"), 4.5, "KBLIRegistryView.swift:1708 cellDetail risk pill"),
]

def main():
    results = []
    for label, fg_tok, bg_spec, min_req, source in PAIRS:
        for theme in ("day", "night"):
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
    fails = [r for r in results if not r["pass"]]
    sys.stderr.write(f"TOTAL={len(results)} FAIL={len(fails)}\n")
    for r in fails:
        sys.stderr.write(f"  FAIL {r['pair']} [{r['theme']}] ratio={r['ratio']} < {r['min_required']}\n")

if __name__ == "__main__":
    main()
