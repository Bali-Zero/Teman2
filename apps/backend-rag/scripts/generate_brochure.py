"""
Bali Zero — Company Brochure PDF generator (v5, brand surface)
==============================================================
THIS IS THE SOURCE of the brochure clients receive. Run it when facts, services
or prices change, and commit the PDF it writes.

Output: ``apps/mouth/public/static/brochure_balizero_en.pdf`` — the file served
at https://kita.balizero.com/static/brochure_balizero_en.pdf, which
``welcome_email_service.py`` fetches over HTTP and base64-attaches to every
welcome email. There is no second copy: write here or the clients never see it.

v5 (2026-08-06) — rebuilt ON the brand surface instead of beside it
-------------------------------------------------------------------
v4 drew the document itself with reportlab, in its own palette. That palette
was not the brand's: near-black instead of the antracite ``color.bg.antracite``,
plus terracotta, warm gold, indigo and green accents — four families that the
brand constitution Article 2.2 bans outright in text zones — with League Spartan
titles against the single-family Montserrat rule (Article 3.1) and Title Case
against the uppercase-titles rule (Article 3.3). It also ignored the fact that
this organism already HAS a canonical A4 print surface, used by the client-quote
lane: ``skills/bali-zero-brand/surfaces/internal-print-a4/``.

So the drawing code is gone. This script now does the two things that are
genuinely its own — resolve prices, and refuse to ship a broken artifact — and
delegates every visual decision to the surface:

    content  ->  scripts/brochure/brochure_en.html   (this repo, reviewable)
    design   ->  surfaces/internal-print-a4/_template.css      (REFERENCED)
    render   ->  surfaces/internal-print-a4/_render.py         (IMPORTED)

Nothing about the look is duplicated here or in the HTML. Surface spec A6.3:
"any agent producing a new A4 brief MUST reference the canonical CSS, not
re-write tokens inline." A brand change now reaches this brochure by itself.

What survived from v4, because it was the part that was right
-------------------------------------------------------------
Prices resolve by EXACT key and a miss STOPS THE BUILD. v3 matched substrings,
so the row labelled "ERP" matched the entry "Investor KITAP + M**ERP**" and
would have printed Rp 55.000.000 next to an 800.000 service, on a document
handed to clients. And a lookup that quietly degraded to "–" had put 18 of 33
rows on a dash with exit code 0, which nobody noticed because nothing said so.

The template contract is now checked in BOTH directions: a placeholder with no
mapping is a build failure (it would ship as the literal text ``{{PRICE_X}}``),
and a mapping no placeholder uses is a build failure too (dead weight that looks
like coverage). Then the finished PDF is read back and has to prove it: brand
font actually embedded, no placeholder survived, and the only phone number
anywhere in it is the public CTA line.

Usage:
    cd apps/backend-rag
    .venv/bin/python scripts/generate_brochure.py

Needs Playwright (in the backend venv) and network access at render time — the
surface CSS pulls Montserrat from the Google Fonts CDN, and without it Chromium
falls back to a system font silently. That silence is exactly what the font
check at the end refuses to accept.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path

# ─────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent                     # apps/backend-rag
REPO_ROOT = BACKEND_ROOT.parent.parent               # monorepo root

TEMPLATE_PATH = SCRIPT_DIR / "brochure" / "brochure_en.html"
SURFACE_DIR = REPO_ROOT / "skills" / "bali-zero-brand" / "surfaces" / "internal-print-a4"
RENDER_PATH = SURFACE_DIR / "_render.py"
PRICING_PATH = BACKEND_ROOT / "backend" / "data" / "bali_zero_official_prices_2026.json"

# The SERVED path. Vercel publishes apps/mouth/public/ verbatim, and
# welcome_email_service.py fetches this exact file over HTTP to attach it to
# every welcome email. Writing anywhere else means the clients never see it —
# which is precisely how an earlier generator drifted four months out of date.
OUTPUT_PATH = REPO_ROOT / "apps" / "mouth" / "public" / "static" / "brochure_balizero_en.pdf"

# The public CTA line. The brochure that was live until 2026-08-05 showed a team
# member's personal number eight times; the check at the bottom is what makes
# that impossible to reintroduce silently.
CTA_PHONE_DIGITS = "628213454721"  # +62 821 3454 721, digits only

# ─────────────────────────────────────────────────────────
# PRICES
# ─────────────────────────────────────────────────────────
def load_pricing() -> dict:
    """Loud, not a warning-and-carry-on.

    An empty dict here means every lookup misses, and that used to produce a
    brochure full of dashes with exit code 0 — a client-facing artifact
    degrading in silence, the same shape as a silent font fallback (scar W99).
    """
    try:
        with PRICING_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:  # any failure here must stop the build, not degrade
        raise SystemExit(f"\n❌ PRICING LOAD FAILED — {PRICING_PATH}\n   {exc}\n") from exc


def fmt_amount(raw: str) -> str:
    """'5.800.000 IDR' → 'Rp 5.800.000'.

    Full figures, not 'Rp 5.8M': a price list a client reads once should not
    make them wonder whether that is 5.8 million or 5,800.
    """
    cleaned = raw.replace("IDR", "").strip()
    if not cleaned:
        raise ValueError(f"empty amount: {raw!r}")
    return f"Rp {cleaned}"


def fmt_entry(entry: dict, where: str) -> str:
    """Render one price-list entry, whichever shape it has.

    The 2026 list carries either a single ``price`` or a ``tier_range`` pair —
    the tax tiers and 'Close PMA' use the latter. A tier that silently printed
    only its floor would understate the fee on a client-facing document.
    """
    price = (entry.get("price") or "").strip()
    if price:
        if price.lower().startswith("depend"):
            return "On request"
        return fmt_amount(price)

    tier = entry.get("tier_range")
    if isinstance(tier, list) and len(tier) == 2:
        return f"{fmt_amount(tier[0])} – {fmt_amount(tier[1])}"

    raise SystemExit(
        f"\n❌ PRICE ENTRY HAS NEITHER price NOR tier_range — {where}\n"
        f"   entry: {entry!r}\n"
    )


def get_price(pricing: dict, path: tuple[str, ...]) -> str:
    """Look a price up by its EXACT key path. A miss stops the build.

    Exact, not substring, and the difference is not stylistic — see the ERP /
    M-ERP collision in the module docstring. Superscar #3: match the entity,
    never the shape.
    """
    node: object = pricing.get("services", {})
    walked: list[str] = []
    for part in path:
        if not isinstance(node, dict) or part not in node:
            siblings = sorted(node)[:8] if isinstance(node, dict) else []
            raise SystemExit(
                f"\n❌ PRICE NOT FOUND — refusing to write a client-facing price list.\n"
                f"   asked for : services.{'.'.join(path)}\n"
                f"   resolved  : services.{'.'.join(walked)} (then {part!r} is missing)\n"
                f"   available here: {siblings}\n"
            )
        node = node[part]
        walked.append(part)

    if not isinstance(node, dict):
        raise SystemExit(f"\n❌ PRICE PATH IS NOT AN ENTRY — services.{'.'.join(path)}\n")
    return fmt_entry(node, f"services.{'.'.join(path)}")


# Placeholder → exact key path in bali_zero_official_prices_2026.json.
# Every entry here must appear in the template, and every {{PRICE_*}} in the
# template must appear here: both directions are checked before rendering.
PRICE_MAP: dict[str, tuple[str, ...]] = {
    # — visas
    "PRICE_VOA":        ("single_entry_visas", "B1 Visa on Arrival (VOA)"),
    "PRICE_C1":         ("single_entry_visas", "C1 Tourism"),
    "PRICE_C1_EXT":     ("single_entry_visas", "C1 Tourism Extension"),
    "PRICE_C2":         ("single_entry_visas", "C2 Business"),
    "PRICE_C18":        ("single_entry_visas", "C18 Work Trial"),
    "PRICE_C22":        ("single_entry_visas", "C22A&B Internship (180 Days)"),
    "PRICE_D1_1":       ("multiple_entry_visas", "D1 Tourism (1 Year)"),
    "PRICE_D2_1":       ("multiple_entry_visas", "D2 Business (1 Year)"),
    "PRICE_D12_1":      ("multiple_entry_visas", "D12 Business Investigation (1 Year)"),
    "PRICE_D12_2":      ("multiple_entry_visas", "D12 Business Investigation (2 Years)"),
    # — stay permits
    "PRICE_E33G_OFF":   ("kitas_permits", "E33G Remote Worker (Offshore)"),
    "PRICE_E33G_ALT":   ("kitas_permits", "E33G Remote Worker (Altus/Onshore)"),
    "PRICE_INV_OFF":    ("kitas_permits", "Investor KITAS 2 Years (Offshore)"),
    "PRICE_E23_OFF":    ("kitas_permits", "Freelance E23 (Offshore)"),
    "PRICE_RET_OFF":    ("kitas_permits", "Retirement (Offshore)"),
    "PRICE_SPOUSE_OFF": ("kitas_permits", "Spouse 1 Year (Offshore)"),
    "PRICE_E33E_OFF":   ("kitas_permits", "E33E Second Home Senior (5 Years, Offshore)"),
    "PRICE_KITAP_INV":  ("kitap_permits", "Investor KITAP + MERP"),
    "PRICE_KITAP_RET":  ("kitap_permits", "Retirement KITAP + MERP"),
    # — company
    "PRICE_NEWCO":      ("company_services", "New Company (PT PMA)"),
    "PRICE_VO":         ("company_services", "Virtual Office"),
    "PRICE_CLOSE_PMA":  ("consultant_services", "Close PMA Company"),
    "PRICE_WK_OFF":     ("kitas_permits", "Working KITAS (Offshore)"),
    "PRICE_WK_ALT":     ("kitas_permits", "Working KITAS (Altus/Onshore)"),
    "PRICE_WK_EXT":     ("kitas_permits", "Working KITAS (Extend)"),
    "PRICE_NPWPD":      ("consultant_services", "NPWPD Registration"),
    "PRICE_BPJS_TK":    ("consultant_services", "BPJS Employee (Tenaga Kerja)"),
    "PRICE_BPJS_KES":   ("consultant_services", "BPJS Insurance (Kesehatan)"),
    # — tax
    "PRICE_TAX_M_0_50":     ("tax_accounting", "monthly_tax_basic", "Tier 0-50"),
    "PRICE_TAX_M_50_100":   ("tax_accounting", "monthly_tax_basic", "Tier 50-100"),
    "PRICE_TAX_M_100_200":  ("tax_accounting", "monthly_tax_basic", "Tier 100-200"),
    "PRICE_TAX_M_200":      ("tax_accounting", "monthly_tax_basic", "Tier 200+"),
    "PRICE_TAX_B_0_50":     ("tax_accounting", "monthly_tax_bundled", "Tier 0-50"),
    "PRICE_TAX_B_50_100":   ("tax_accounting", "monthly_tax_bundled", "Tier 50-100"),
    "PRICE_TAX_B_100_200":  ("tax_accounting", "monthly_tax_bundled", "Tier 100-200"),
    "PRICE_TAX_B_200":      ("tax_accounting", "monthly_tax_bundled", "Tier 200+"),
    "PRICE_ANNUAL_CO":      ("tax_accounting", "annual_standalone", "Annual Tax Company"),
    "PRICE_ANNUAL_PERS":    ("tax_accounting", "annual_standalone", "Annual Tax Personal"),
    "PRICE_LKPM":           ("tax_accounting", "annual_standalone", "LKPM Yearly Report"),
    "PRICE_ANNUAL_ZERO":    ("tax_accounting", "annual_basic_packages", "Annual Company ZERO"),
    # — personal documents
    "PRICE_SKTT":       ("other_process", "SKTT"),
    "PRICE_SKCK":       ("other_process", "SKCK"),
    "PRICE_DOM":        ("other_process", "Domicilie Letter"),   # sic: key spelling in the price list
    "PRICE_PP5":        ("other_process", "Passport 5 Years"),
    "PRICE_PP10":       ("other_process", "Passport 10 Years"),
    "PRICE_MUT_PP":     ("other_process", "Mutation Passport"),
    "PRICE_MUT_ADDR":   ("other_process", "Mutation Address"),
    "PRICE_SIM":        ("other_process", "Driving License"),
    "PRICE_EPO":        ("other_process", "EPO (Exit Permit Only)"),
    "PRICE_ERP":        ("other_process", "ERP (Exit Re-entry Permit)"),
}

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def fill_template(html: str, pricing: dict) -> str:
    """Substitute every placeholder, after proving the contract holds both ways."""
    in_template = set(PLACEHOLDER_RE.findall(html))
    in_map = set(PRICE_MAP)

    unmapped = sorted(in_template - in_map)
    unused = sorted(in_map - in_template)
    if unmapped or unused:
        raise SystemExit(
            "\n❌ TEMPLATE / PRICE-MAP MISMATCH — refusing to render.\n"
            + (f"   in the HTML with no mapping (would ship as literal text): {unmapped}\n" if unmapped else "")
            + (f"   mapped but never used in the HTML (dead weight): {unused}\n" if unused else "")
        )

    resolved = {name: get_price(pricing, path) for name, path in PRICE_MAP.items()}
    return PLACEHOLDER_RE.sub(lambda m: resolved[m.group(1)], html)


# ─────────────────────────────────────────────────────────
# RENDER — the canonical surface renderer, imported, never reimplemented
# ─────────────────────────────────────────────────────────
def load_surface_renderer():
    if not RENDER_PATH.exists():
        raise SystemExit(f"\n❌ BRAND SURFACE RENDERER MISSING — {RENDER_PATH}\n")
    spec = importlib.util.spec_from_file_location("bz_internal_print_a4_render", RENDER_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit(f"\n❌ CANNOT LOAD RENDERER — {RENDER_PATH}\n")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.render


# ─────────────────────────────────────────────────────────
# VERIFY THE ARTIFACT — read back what was actually written
# ─────────────────────────────────────────────────────────
def _pdf_font_names(reader) -> set[str]:
    """Every font name in the document, whichever field carries it.

    Three fields, not one, and that is not belt-and-braces. The first version
    of this read only ``/BaseFont`` — and Chromium embeds webfonts as **Type 3**
    fonts, which have no ``/BaseFont`` at all: the name lives in the descriptor.
    So the check reported '(none)' on a PDF carrying twenty Montserrat subsets,
    i.e. it was about to fail the correct artifact while passing the Helvetica
    one, whose CID fonts DO have ``/BaseFont``. A guard that reads one field
    measures the shapes it happens to know.
    """
    fonts: set[str] = set()
    for page in reader.pages:
        resources = page.get("/Resources")
        if resources is None:
            continue
        font_dict = resources.get_object().get("/Font")
        if font_dict is None:
            continue
        for ref in font_dict.get_object().values():
            font = ref.get_object()
            names = [font.get("/BaseFont"), font.get("/Name")]
            descriptor = font.get("/FontDescriptor")
            if descriptor is not None:
                desc = descriptor.get_object()
                names += [desc.get("/FontName"), desc.get("/FontFamily")]
            for name in names:
                if name:
                    # Subsets are prefixed: '/ABCDEF+Montserrat-Regular'.
                    fonts.add(str(name).lstrip("/").split("+")[-1])
    return fonts


def verify(pdf_path: Path, expected_pages: int) -> None:
    """Judge the FILE, not the intention that produced it.

    Three things this catches that the render itself reports as success:
      - Montserrat did not load (offline / CDN blocked) and Chromium fell back
        to a system font — the exact silent degradation of scar W99;
      - a placeholder survived and shipped as literal text;
      - a phone number other than the public CTA line is in the document.
    """
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages = len(reader.pages)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    problems: list[str] = []

    if pages != expected_pages:
        problems.append(
            f"page count is {pages}, expected {expected_pages} — content is "
            f"overflowing its page or a section vanished; open the PDF and look"
        )

    fonts = _pdf_font_names(reader)
    if not any("montserrat" in f.lower() for f in fonts):
        problems.append(
            f"brand font NOT embedded — fonts in the PDF: {sorted(fonts) or '(none)'}. "
            f"The surface CSS loads Montserrat from the Google Fonts CDN; without "
            f"network Chromium substitutes a system font and says nothing."
        )

    survivors = sorted(set(PLACEHOLDER_RE.findall(text)))
    if survivors:
        problems.append(f"placeholders shipped as literal text: {survivors}")

    # Every phone-shaped string in the document must be the CTA line. Enumerating
    # what IS there beats checking that a known-bad list is absent: the number
    # that bites is the one nobody thought to put on the list.
    digits_found = {
        re.sub(r"\D", "", m)
        for m in re.findall(r"\+?\d[\d\s().-]{8,}\d", text)
    }
    phones = {d for d in digits_found if d.startswith("62") and 10 <= len(d) <= 15}
    stray = sorted(phones - {CTA_PHONE_DIGITS})
    if stray:
        problems.append(f"phone numbers other than the public CTA line: {stray}")
    if CTA_PHONE_DIGITS not in phones:
        problems.append("the public CTA number is not in the document at all")

    if problems:
        raise SystemExit(
            "\n❌ BROCHURE REJECTED — written, then read back and found wrong:\n"
            + "".join(f"   • {p}\n" for p in problems)
        )

    brand = sorted({f for f in fonts if "montserrat" in f.lower()})
    print(
        f"  ✓ {pages} pages · {len(brand)} Montserrat faces embedded "
        f"· CTA number present, no stray numbers"
    )


# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
EXPECTED_PAGES = 9  # cover + 8


def main() -> int:
    if not TEMPLATE_PATH.exists():
        raise SystemExit(f"\n❌ TEMPLATE MISSING — {TEMPLATE_PATH}\n")

    pricing = load_pricing()
    html = fill_template(TEMPLATE_PATH.read_text(encoding="utf-8"), pricing)

    render = load_surface_renderer()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # The filled HTML has to sit NEXT TO the template: its stylesheet link is
    # relative, and rendering from a temp dir elsewhere would resolve to nothing
    # — which Chromium would render as an unstyled page without complaining.
    tmp = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", suffix=".html", dir=TEMPLATE_PATH.parent, delete=False
    )
    tmp_path = Path(tmp.name)
    try:
        tmp.write(html)
        tmp.close()
        render(tmp_path, OUTPUT_PATH)
    finally:
        tmp_path.unlink(missing_ok=True)

    verify(OUTPUT_PATH, EXPECTED_PAGES)
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"\n✅ {OUTPUT_PATH.relative_to(REPO_ROOT)} ({size_kb:,.1f} KB)")
    print("   Commit it — this file IS what clients receive.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
