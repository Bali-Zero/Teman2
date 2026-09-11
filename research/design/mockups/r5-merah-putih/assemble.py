#!/usr/bin/env python3
"""Assemble R5 Merah Putih mockups: _tokens.css + *.body.html -> standalone *.html,
plus static checks -> checks.json. Rev 2 after the R5 panel: every check now has a way
to go RED (codex finding 5: presence-only checks were vacuous passes), and the APCA
advisory annex required by R4 §8 is computed (APCA-W3 0.1.9 4g constants, advisory only —
WCAG 2.x stays the binding bar)."""
import json, pathlib, re

R5 = pathlib.Path(__file__).parent
CSS = (R5 / "_tokens.css").read_text()

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600'
         '&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">')

TPL = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>{fonts}<style>{css}</style></head><body>
{body}
</body></html>"""

TITLES = {
    "m1-garuda-landing": "M1 · GARUDA landing — Merah Putih",
    "m2a-garuda-question": "M2a · GARUDA question — Merah Putih",
    "m2b-garuda-upload": "M2b · GARUDA upload — Merah Putih",
    "m3-vo-question": "M3 · VO question — Merah Putih",
    "m4a-vo-verdict-human-review-named": "M4a · VO human review (named) — Merah Putih",
    "m4b-vo-verdict-human-review-control": "M4b · VO human review (control) — Merah Putih",
    "m5-vo-verdict-supported-payment": "M5 · VO supported+payment — Merah Putih",
    "m6-my-tracker": "M6 · my tracker — Merah Putih",
    "m7-vo-landing": "M7 · VO landing — Merah Putih",
    "m8-garuda-recovery": "M8 · GARUDA recovery — Merah Putih",
}
QUESTION_SCREENS = {"m2a-garuda-question", "m2b-garuda-upload", "m3-vo-question"}

# ---- APCA advisory annex (APCA-W3 0.1.9, 4g constants; advisory only) ----
def _apca_y(hexc):
    r, g, b = (int(hexc[i:i+2], 16) / 255 for i in (1, 3, 5))
    y = 0.2126729 * r**2.4 + 0.7151522 * g**2.4 + 0.0721750 * b**2.4
    if y < 0.022:
        y += (0.022 - y)**1.414
    return y

def apca_lc(txt, bg):
    yt, yb = _apca_y(txt), _apca_y(bg)
    if yb > yt:   # normal polarity: dark text on light ground
        s = (yb**0.56 - yt**0.57) * 1.14
        lc = 0.0 if s < 0.1 else (s - 0.027) * 100
    else:         # reverse polarity
        s = (yb**0.65 - yt**0.62) * 1.14
        lc = 0.0 if s > -0.1 else (s + 0.027) * 100
    return round(lc, 1)

APCA_PAIRS = [
    ("ink on carta", "#16213a", "#f7f6f2"),
    ("ink on white", "#16213a", "#ffffff"),
    ("ink-soft on carta", "#475372", "#f7f6f2"),
    ("ink-soft on white", "#475372", "#ffffff"),
    ("merah-action on carta (links)", "#D01033", "#f7f6f2"),
    ("white on merah-action (CTA)", "#ffffff", "#D01033"),
    ("state-error on white (error msg)", "#a83a44", "#ffffff"),
    ("state-conditional on carta (.ph)", "#7a5209", "#f7f6f2"),
    ("state-conditional on white (.ph in cards)", "#7a5209", "#ffffff"),
    ("state-eligible on white (M5 h2)", "#16683f", "#ffffff"),
]

checks = {}
for body_file in sorted(R5.glob("*.body.html")):
    slug = body_file.name.replace(".body.html", "")
    if slug not in TITLES:
        continue
    body = body_file.read_text()
    html_doc = TPL.format(title=TITLES[slug], fonts=FONTS, css=CSS, body=body)
    (R5 / f"{slug}.html").write_text(html_doc)

    c = {}
    # placeholder markers — must be > 0 everywhere (audited-facts constraint)
    c["placeholder_markers"] = len(re.findall(r'class="(?:mono )?ph[ "]', body))
    # identity header FULL contract: wordmark + toggle + WhatsApp ENTRY (a real <a>)
    c["header_contract"] = ('class="wordmark"' in body and 'lang-toggle' in body
                            and '<a class="wa-entry"' in body)
    # company identifier + dated disclaimer on every screen
    c["identifier_line"] = "{PT_LEGAL_NAME}" in body and "{NPWP}" in body
    c["dated_line"] = "27 Aug 2026" in body
    # counter on question screens; explicit n/a elsewhere (never a vacuous true)
    c["counter"] = ('class="counter"' in body) if slug in QUESTION_SCREENS else "n/a"
    # IDR containment: every IDR occurrence must sit inside a mono/ph span (both nowrap in CSS)
    idr_positions = [m.start() for m in re.finditer(r'IDR', body)]
    c["idr_occurrences"] = len(idr_positions)
    c["idr_contained"] = (all(
        re.search(r'class="(?:mono ph|ph mono|mono|ph)[^"]*"[^>]*>[^<]*$', body[max(0, p-160):p])
        for p in idr_positions) if idr_positions else "n/a")
    # WhatsApp: if mentioned, the component or entry must exist — else n/a
    c["wa_component"] = (("wa-card" in body or "wa-entry" in body)
                         if "WhatsApp" in body else "n/a")
    # red budget: inline red backgrounds/colors outside the documented whitelist (M6 dot)
    inline_red = re.findall(r'(?:background|color):\s*var\(--merah\)', body)
    c["inline_red_uses"] = len(inline_red)
    c["red_budget_ok"] = len(inline_red) <= (1 if slug == "m6-my-tracker" else 0)
    # selection never red
    c["selected_not_red"] = "selected" not in body or not re.search(r'selected[^>]*style="[^"]*--merah', body)
    # variant discipline: named page carries the marker, control page must NOT
    if slug == "m4a-vo-verdict-human-review-named":
        c["variant_ok"] = "{NAMED_AGENT}" in body
    if slug == "m4b-vo-verdict-human-review-control":
        c["variant_ok"] = "{NAMED_AGENT}" not in body
    # guarantee language ban (voice law)
    c["no_guarantee_language"] = not re.search(r'\bnever blocks\b|\bguarantee[d]?\b|\bdijamin\b', body, re.I)
    checks[slug] = c

# CSS-level checks — each names the exact selector it requires
focus_block = re.search(r'([^\{]*):focus-visible[^\{]*\{', CSS)
focus_selectors = focus_block.group(0) if focus_block else ""
checks["_css"] = {
    "cormorant_floor_24": bool(re.search(r'h2 \{ font-size: 24px', CSS)) and bool(re.search(r'h1 \{ font-size: 28px', CSS)),
    "h3_is_inter": "h3 { font-family: var(--font-ui)" in CSS,
    "focus_covers_all_interactives": all(s in focus_selectors for s in
        (".cta:focus-visible", ".option:focus-visible", ".wa-card:focus-visible",
         ".wa-entry:focus-visible", ".lang-toggle span:focus-visible", "a:focus-visible")),
    "placeholder_aa": "::placeholder { color: var(--ink-soft); opacity: 1; }" in CSS,
    "error_not_color_alone": (".error-msg .ic" in CSS),
    "touch44_shell": ".lang-toggle span {" in CSS and "min-height: 44px" in CSS.split(".lang-toggle span {")[1][:200]
                      and "width: 44px; height: 44px" in CSS.split(".wa-entry {")[1][:200],
    "touch44_core": all(("min-height: 44px" in CSS.split(sel)[1][:400]) for sel in (".option {", ".cta {", ".field input {")),
    "cta_clearance_8px": "margin-top: 8px" in CSS.split(".cta-secondary {")[1][:300],
    "interactive_shadow": all("box-shadow" in CSS.split(sel)[1][:400] for sel in (".option {", ".field input {", ".card {", ".wa-card {")),
    "selected_is_ink_with_padding_compensation": "border: 2px solid var(--ink); padding: 13px 15px" in CSS,
    "pressed_has_motion": "transform: scale(.99)" in CSS,
    "track_boundary": "border: 1px solid var(--border-input)" in CSS.split(".progress-track")[1][:200],
    "mono_nowrap": "white-space: nowrap" in CSS.split(".mono {")[1][:120],
    "dark_primitives_present": all(t in CSS for t in ("--ground-dark", "--text-dark", "--soft-dark", "--panel-dark", "--hairline-dark", "--merah-dark-mode")),
    "reduced_motion": "prefers-reduced-motion" in CSS,
    "buttons_inherit_font": "button, input { font-family: inherit; }" in CSS,
}
checks["_apca_advisory"] = [{"pair": n, "Lc": apca_lc(t, b)} for n, t, b in APCA_PAIRS]
(R5 / "checks.json").write_text(json.dumps(checks, indent=1))

flat_fails = []
for scope, group in checks.items():
    if scope == "_apca_advisory":
        continue
    for k, v in group.items():
        if v is False:
            flat_fails.append(f"{scope}.{k}")
print(json.dumps(checks["_css"], indent=1))
print("APCA:", [(d["pair"], d["Lc"]) for d in checks["_apca_advisory"]])
print("FAILS:", flat_fails if flat_fails else "none")
