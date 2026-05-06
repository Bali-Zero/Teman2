"""Briefs for codex exec → Image 2 (gpt-image-1) generation.

Pure data, no I/O. Each entry is (output_basename, brief_text, size).

ICON_BRIEFS keys must be a 1:1 cover of every icon_id used in
bali_zero_official_prices_2026.json (45 unique ids as of 2026-05-06).
The generator script (generate_assets.py) iterates this dict; missing
keys = missing PNGs = AssetMissingError at render time.
"""
from __future__ import annotations

# Shared style constraints injected into every brief
_STYLE_HEROS = (
    "Cinematic editorial still-life. Slow-magazine photography aesthetic, "
    "low-key chiaroscuro, shallow depth of field. Palette anchored on deep "
    "navy #1d273b, copper #d4845a, warm gold #c9a96e on cream paper #fbfaf6 "
    "highlights. NO TEXT, NO LOGOS, NO WATERMARKS, NO READABLE WRITING on "
    "any surface. 16:9 landscape composition."
)

_STYLE_ICONS = (
    "Single line-art icon, 2px stroke weight, copper color #d4845a only, "
    "transparent background, centered in 1024×1024 frame, minimalist "
    "editorial style, no fill, no shadows, single subject only. NO TEXT."
)

# 6 hero photographs, one per macro-section (1792x1024 = closest 16:9 supported by Image 2)
HERO_BRIEFS: list[tuple[str, str, str]] = [
    (
        "01_visas",
        f"{_STYLE_HEROS} Subject: open passport with embossed Indonesian "
        "visa stamp resting on travertine marble surface, soft dawn light "
        "from upper left, brass key in soft focus background.",
        "1792x1024",
    ),
    (
        "02_kitas_kitap",
        f"{_STYLE_HEROS} Subject: tilt-shift Jakarta skyline at golden hour "
        "bokeh in background, foreground crisp printed Letter of Approval "
        "document with embossed seal partly visible (no readable text on "
        "document).",
        "1792x1024",
    ),
    (
        "03_tax",
        f"{_STYLE_HEROS} Subject: macro detail of a vintage fountain pen "
        "poised over a blank ledger page, Indonesian rupiah banknotes "
        "blurred at edge, copper highlights on metal pen body.",
        "1792x1024",
    ),
    (
        "04_company",
        f"{_STYLE_HEROS} Subject: notarial seal pressed into deep red "
        "sealing wax on cream Akta document, hand of notary partly visible "
        "holding brass seal (no readable text on document).",
        "1792x1024",
    ),
    (
        "05_other_process",
        f"{_STYLE_HEROS} Subject: top-down flat-lay of identity documents, "
        "immigration stamps, brass paperclips on cream linen surface, soft "
        "diffused window light (no readable text on documents).",
        "1792x1024",
    ),
    (
        "06_urgent",
        f"{_STYLE_HEROS} Subject: crystal hourglass with copper sand "
        "mid-flow, deep navy background, single beam of light from upper "
        "right, dramatic shadow.",
        "1792x1024",
    ),
]

# Micro-icons keyed by icon_id used in the JSON.
# Must be a 1:1 cover of the icon_id set (45 ids as of 2026-05-06).
ICON_BRIEFS: dict[str, str] = {
    # Visas (7)
    "visa-tourism":        f"{_STYLE_ICONS} Subject: passport with palm tree.",
    "visa-business":       f"{_STYLE_ICONS} Subject: briefcase with passport corner showing.",
    "visa-art":            f"{_STYLE_ICONS} Subject: musical note inside circular frame.",
    "visa-internship":     f"{_STYLE_ICONS} Subject: graduation cap.",
    "visa-worktrial":      f"{_STYLE_ICONS} Subject: clipboard with checkmark.",
    "visa-extension":      f"{_STYLE_ICONS} Subject: calendar page with curved arrow extending right.",
    "visa-multiple":       f"{_STYLE_ICONS} Subject: passport with two arrows pointing in opposite directions.",
    "visa-investigation":  f"{_STYLE_ICONS} Subject: magnifying glass over a briefcase.",

    # KITAS (7)
    "kitas-working":       f"{_STYLE_ICONS} Subject: hard hat positioned above a document.",
    "kitas-investor":      f"{_STYLE_ICONS} Subject: rising bar chart with a coin on top.",
    "kitas-freelance":     f"{_STYLE_ICONS} Subject: laptop with a palm leaf beside it.",
    "kitas-remote":        f"{_STYLE_ICONS} Subject: laptop with three concentric wifi waves above.",
    "kitas-spouse":        f"{_STYLE_ICONS} Subject: two interlocking rings.",
    "kitas-dependent":     f"{_STYLE_ICONS} Subject: silhouettes of a family of three (two adults, one child).",
    "kitas-retirement":    f"{_STYLE_ICONS} Subject: lounge chair under a palm tree.",

    # KITAP (2)
    "kitap-permanent":     f"{_STYLE_ICONS} Subject: house outline with a key.",
    "kitap-merp":          f"{_STYLE_ICONS} Subject: airplane with two re-entry arrows beneath.",

    # Tax (4)
    "tax-monthly":         f"{_STYLE_ICONS} Subject: calendar page with a currency symbol.",
    "tax-annual":          f"{_STYLE_ICONS} Subject: ledger book with a bookmark ribbon.",
    "tax-lkpm":            f"{_STYLE_ICONS} Subject: bar chart inside a government building outline.",
    "tax-personal":        f"{_STYLE_ICONS} Subject: single person silhouette holding a document.",

    # Company (4)
    "company-pma":         f"{_STYLE_ICONS} Subject: Indonesian temple gate (candi bentar) in outline form.",
    "company-virtual":     f"{_STYLE_ICONS} Subject: cloud with a small building inside.",
    "company-akta":        f"{_STYLE_ICONS} Subject: scroll with a notary seal beneath.",
    "company-close":       f"{_STYLE_ICONS} Subject: building with an X mark over its door.",

    # Consultant (6)
    "consultant-npwpd":    f"{_STYLE_ICONS} Subject: city map pin over a document.",
    "consultant-bpjs-tk":  f"{_STYLE_ICONS} Subject: hand outline above a worker silhouette.",
    "consultant-bpjs-kes": f"{_STYLE_ICONS} Subject: medical cross inside a shield.",
    "consultant-npwp":     f"{_STYLE_ICONS} Subject: ID card with a hash symbol.",
    "consultant-update":   f"{_STYLE_ICONS} Subject: pencil over a document with a small refresh arrow.",
    "consultant-efin":     f"{_STYLE_ICONS} Subject: digital fingerprint.",

    # Other Process (11)
    "other-passport":      f"{_STYLE_ICONS} Subject: passport icon with the front cover visible.",
    "other-sktt":          f"{_STYLE_ICONS} Subject: ID card with a small house outline beside it.",
    "other-skck":          f"{_STYLE_ICONS} Subject: shield with a checkmark inside.",
    "other-domicile":      f"{_STYLE_ICONS} Subject: house with a document beside it.",
    "other-born":          f"{_STYLE_ICONS} Subject: stork in flight.",
    "other-epo":           f"{_STYLE_ICONS} Subject: door with a single arrow exiting to the right.",
    "other-erp":           f"{_STYLE_ICONS} Subject: door with two arrows (one entering, one exiting).",
    "other-mutation":      f"{_STYLE_ICONS} Subject: passport with a curved transfer arrow above.",
    "other-cancel":        f"{_STYLE_ICONS} Subject: document with a diagonal X mark across it.",
    "other-molina":        f"{_STYLE_ICONS} Subject: circular refresh arrow.",
    "other-boarding":      f"{_STYLE_ICONS} Subject: airplane boarding pass.",

    # Urgent (3)
    "urgent-1day":         f"{_STYLE_ICONS} Subject: stopwatch with the numeral 1 on its face.",
    "urgent-2day":         f"{_STYLE_ICONS} Subject: stopwatch with the numeral 2 on its face.",
    "urgent-3day":         f"{_STYLE_ICONS} Subject: stopwatch with the numeral 3 on its face.",
}
