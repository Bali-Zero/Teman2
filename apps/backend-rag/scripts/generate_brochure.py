"""
Bali Zero — Company Brochure PDF Generator v3
=============================================
One-time script. Run when services/prices change.
Output: data/assets/brochure_balizero_en.pdf

Usage:
    cd apps/backend-rag
    python scripts/generate_brochure.py

v3 changes:
    - Real pricing data from bali_zero_official_prices_2025.json
    - League Spartan (VF TTF) for titles — white
    - Montserrat (VF TTF) for body — white
    - Cleaner layout: more whitespace, stronger hierarchy
    - Real service categories with actual prices
    - Contact: info@balizero.com / +62 813 3805 1876 / Canggu Bali
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────
REPO_ROOT    = Path(__file__).parent.parent.parent.parent  # monorepo root
BACKEND_ROOT = Path(__file__).parent.parent                # apps/backend-rag
OUTPUT_PATH  = BACKEND_ROOT / "data" / "assets" / "brochure_balizero_en.pdf"
LOGO_PATH    = REPO_ROOT / "apps" / "mouth" / "public" / "static" / "balizero-logo-clean.png"
PRICING_PATH = BACKEND_ROOT / "backend" / "data" / "bali_zero_official_prices_2025.json"

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────────
import numpy as np
from PIL import Image as PILImage

from reportlab.lib.colors import Color, HexColor, white, black
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)

# ─────────────────────────────────────────────────────────
# BRAND PALETTE
# ─────────────────────────────────────────────────────────
BASE        = HexColor("#0c0c0e")   # near-black background
DARK2       = HexColor("#141416")   # slightly lighter background
TERRA       = HexColor("#d4845a")   # terracotta accent
GOLD        = HexColor("#c9a96e")   # gold accent
INDIGO      = HexColor("#5e7fb5")   # immigration
GREEN       = HexColor("#4db87a")   # AI/how-we-work
TEXT_MAIN   = HexColor("#edeae4")   # off-white body text
TEXT_DIM    = HexColor("#9d9a94")   # dimmed text
CARD_BG     = Color(1, 1, 1, 0.06) # subtle card surface
DIVIDER     = Color(1, 1, 1, 0.12) # faint dividers
WHITE       = HexColor("#ffffff")

# section accent per page
SECTION_COLORS = {
    "cover":   TERRA,
    "who":     TERRA,
    "imm":     INDIGO,
    "biz":     TERRA,
    "tax":     GOLD,
    "how":     GREEN,
    "contact": TERRA,
}

# ─────────────────────────────────────────────────────────
# PAGE SIZE
# ─────────────────────────────────────────────────────────
W, H = A4  # 210 × 297 mm

# ─────────────────────────────────────────────────────────
# LOAD PRICING DATA
# ─────────────────────────────────────────────────────────
def load_pricing() -> dict:
    try:
        with open(PRICING_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  Pricing load failed: {e}")
        return {}

PRICING = load_pricing()


def fmt_price(idr_str: str) -> str:
    """'5.800.000 IDR' → 'Rp 5.8M'"""
    try:
        num = int(idr_str.replace(".", "").replace(",", "").replace(" IDR", "").replace("IDR", "").strip())
        if num >= 1_000_000:
            val = num / 1_000_000
            return f"Rp {val:g}M"
        elif num >= 1_000:
            return f"Rp {num // 1000}K"
        return f"Rp {num:,}"
    except Exception:
        return idr_str


def get_price(category: str, key_fragment: str) -> str:
    """Get first matching price from pricing data."""
    cat = PRICING.get("services", {}).get(category, {})
    for k, v in cat.items():
        if key_fragment.lower() in k.lower():
            return fmt_price(v.get("price", ""))
    return "–"


# ─────────────────────────────────────────────────────────
# FONT REGISTRATION
# ─────────────────────────────────────────────────────────
FONT_DIR = Path("/Users/nuzantara/Library/Fonts")
SYS_FONT_DIR = Path("/System/Library/Fonts")

def _reg(name: str, path: Path) -> bool:
    if path.exists():
        try:
            pdfmetrics.registerFont(TTFont(name, str(path)))
            return True
        except Exception:
            return False
    return False

# League Spartan — titles
LS_VF = FONT_DIR / "LeagueSpartan-VF.ttf"
if not _reg("LS", LS_VF):
    _reg("LS", FONT_DIR / "LeagueSpartan-Regular.otf")  # fallback (won't work OTF, handled below)

# For OTF files that don't work, fall back to Helvetica
try:
    pdfmetrics.getFont("LS")
    TITLE_FONT = "LS"
except Exception:
    TITLE_FONT = "Helvetica-Bold"

# Montserrat — body
MONT_VF = FONT_DIR / "Montserrat[wght].ttf"
if _reg("Mont", MONT_VF):
    BODY_FONT = "Mont"
elif _reg("Mont", FONT_DIR / "Montserrat-Regular.ttf"):
    BODY_FONT = "Mont"
else:
    BODY_FONT = "Helvetica"

print(f"   Fonts: title={TITLE_FONT}, body={BODY_FONT}")

# ─────────────────────────────────────────────────────────
# PARAGRAPH STYLES
# ─────────────────────────────────────────────────────────
def S(name: str, font: str, size: float, color=WHITE, leading_mul: float = 1.3,
      align=TA_LEFT, bold: bool = False, space_before: float = 0, space_after: float = 0) -> ParagraphStyle:
    return ParagraphStyle(
        name,
        fontName=font,
        fontSize=size,
        textColor=color,
        leading=size * leading_mul,
        alignment=align,
        spaceBefore=space_before,
        spaceAfter=space_after,
    )

ST = {
    # Headings — League Spartan
    "H1":    S("H1",    TITLE_FONT, 36, WHITE, 1.1, TA_LEFT),
    "H1C":   S("H1C",   TITLE_FONT, 36, WHITE, 1.1, TA_CENTER),
    "H2":    S("H2",    TITLE_FONT, 22, WHITE, 1.2, TA_LEFT),
    "H2C":   S("H2C",   TITLE_FONT, 22, WHITE, 1.2, TA_CENTER),
    "H3":    S("H3",    TITLE_FONT, 15, WHITE, 1.25, TA_LEFT),
    "H3C":   S("H3C",   TITLE_FONT, 15, WHITE, 1.25, TA_CENTER),
    "TAGLINE": S("TAGLINE", TITLE_FONT, 13, TEXT_DIM, 1.4, TA_LEFT),
    "TAGLINEC": S("TAGLINEC", TITLE_FONT, 13, TEXT_DIM, 1.4, TA_CENTER),
    # Body — Montserrat
    "BODY":  S("BODY",  BODY_FONT, 9.5, TEXT_MAIN, 1.5, TA_LEFT),
    "BODYC": S("BODYC", BODY_FONT, 9.5, TEXT_MAIN, 1.5, TA_CENTER),
    "SMALL": S("SMALL", BODY_FONT, 8,   TEXT_DIM,  1.4, TA_LEFT),
    "SMALLC":S("SMALLC",BODY_FONT, 8,   TEXT_DIM,  1.4, TA_CENTER),
    "LABEL": S("LABEL", BODY_FONT, 7.5, TEXT_DIM,  1.3, TA_LEFT),
    "LABELC":S("LABELC",BODY_FONT, 7.5, TEXT_DIM,  1.3, TA_CENTER),
    "PRICE": S("PRICE", TITLE_FONT, 13, TERRA, 1.2, TA_RIGHT),
    "PRICEG":S("PRICEG",TITLE_FONT, 13, GOLD,  1.2, TA_RIGHT),
    "PRICEI":S("PRICEI",TITLE_FONT, 13, INDIGO,1.2, TA_RIGHT),
    "BULLET":S("BULLET",BODY_FONT, 9,  TEXT_MAIN, 1.45, TA_LEFT),
    "FOOTER":S("FOOTER",BODY_FONT, 7.5, TEXT_DIM, 1.3, TA_CENTER),
    "ACCENT":S("ACCENT",TITLE_FONT, 10, TERRA, 1.3, TA_LEFT),
    "ACCENTG":S("ACCENTG",TITLE_FONT, 10, GOLD, 1.3, TA_LEFT),
    "ACCENTI":S("ACCENTI",TITLE_FONT, 10, INDIGO, 1.3, TA_LEFT),
    "ACCENTGR":S("ACCENTGR",TITLE_FONT, 10, GREEN, 1.3, TA_LEFT),
    "URL":   S("URL",   BODY_FONT, 9.5, TERRA, 1.4, TA_CENTER),
}


# ─────────────────────────────────────────────────────────
# LOGO PREPROCESSING
# ─────────────────────────────────────────────────────────
def _prepare_logo(path: Path) -> ImageReader | None:
    if not path.exists():
        print(f"⚠️  Logo not found: {path}")
        return None
    try:
        img = PILImage.open(path).convert("RGBA")
        arr = np.array(img, dtype=np.float32)
        r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]
        brightness = 0.299 * r + 0.587 * g + 0.114 * b
        # Dark pixels (near-black background) → transparent
        mask = brightness < 30
        soft = (brightness >= 30) & (brightness < 60)
        arr[mask, 3] = 0
        arr[soft, 3] = ((brightness[soft] - 30) / 30 * 255).clip(0, 255)
        out = PILImage.fromarray(arr.astype(np.uint8), "RGBA")
        buf = io.BytesIO()
        out.save(buf, format="PNG")
        buf.seek(0)
        return ImageReader(buf)
    except Exception as e:
        print(f"⚠️  Logo prep failed: {e}")
        return None

LOGO_READER = _prepare_logo(LOGO_PATH)


# ─────────────────────────────────────────────────────────
# BACKGROUND CALLBACKS
# ─────────────────────────────────────────────────────────
def _bg_cover(canvas, doc):
    canvas.saveState()
    # Dark base
    canvas.setFillColor(HexColor("#0a0a0c"))
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    # Warm gradient panel left ~40%
    canvas.setFillColor(HexColor("#1a100a"))
    canvas.rect(0, 0, W * 0.42, H, fill=1, stroke=0)
    # Terracotta vertical bar
    canvas.setFillColor(TERRA)
    canvas.rect(W * 0.42 - 3, 0, 3, H, fill=1, stroke=0)
    # Decorative dots grid (subtle)
    canvas.setFillColor(Color(0.83, 0.52, 0.35, 0.08))
    dot_size = 2
    for row in range(0, int(H / 18) + 1):
        for col in range(0, int(W * 0.42 / 18) + 1):
            canvas.circle(col * 18 + 9, row * 18 + 9, dot_size, fill=1, stroke=0)
    # Top accent band
    canvas.setFillColor(TERRA)
    canvas.rect(0, H - 3*mm, W, 3*mm, fill=1, stroke=0)
    # Footer line
    canvas.setFillColor(TERRA)
    canvas.rect(0, 12*mm, W, 0.5, fill=1, stroke=0)
    canvas.setFillColor(TEXT_DIM)
    canvas.setFont(BODY_FONT, 7.5)
    canvas.drawCentredString(W / 2, 5*mm, "balizero.com  ·  info@balizero.com  ·  +62 813 3805 1876  ·  Canggu, Bali")
    canvas.restoreState()


def _make_content_bg(section_id: str):
    accent = SECTION_COLORS.get(section_id, TERRA)
    def _bg(canvas, doc):
        canvas.saveState()
        # Base
        canvas.setFillColor(BASE)
        canvas.rect(0, 0, W, H, fill=1, stroke=0)
        # Subtle top panel
        canvas.setFillColor(HexColor("#111113"))
        canvas.rect(0, H - 28*mm, W, 28*mm, fill=1, stroke=0)
        # Accent top stripe
        canvas.setFillColor(accent)
        canvas.rect(0, H - 1.5, W, 1.5, fill=1, stroke=0)
        # Left accent bar
        canvas.setFillColor(accent)
        canvas.rect(0, 18*mm, 3, H - 36*mm, fill=1, stroke=0)
        # Footer
        canvas.setFillColor(Color(1, 1, 1, 0.08))
        canvas.rect(0, 0, W, 14*mm, fill=1, stroke=0)
        canvas.setFillColor(accent)
        canvas.rect(0, 14*mm, W, 0.5, fill=1, stroke=0)
        canvas.setFillColor(TEXT_DIM)
        canvas.setFont(BODY_FONT, 7.5)
        canvas.drawCentredString(W / 2, 5*mm, "balizero.com  ·  info@balizero.com  ·  +62 813 3805 1876  ·  Canggu, Bali")
        canvas.restoreState()
    return _bg


# ─────────────────────────────────────────────────────────
# CUSTOM FLOWABLES
# ─────────────────────────────────────────────────────────
class HRule(Flowable):
    """Horizontal rule with optional accent color."""
    def __init__(self, width_mm: float = 60, color=TERRA, thickness: float = 1.5, space_after: float = 6):
        super().__init__()
        self._w = width_mm * mm
        self._color = color
        self._t = thickness
        self._sa = space_after
        self.hAlign = "LEFT"

    def wrap(self, avail_w, avail_h):
        return self._w, self._t + self._sa

    def draw(self):
        self.canv.setFillColor(self._color)
        self.canv.rect(0, self._sa, self._w, self._t, fill=1, stroke=0)


class SectionHeader(Flowable):
    """Full-width section header with accent label + title."""
    def __init__(self, label: str, title: str, accent=TERRA):
        super().__init__()
        self._label = label.upper()
        self._title = title
        self._accent = accent

    def wrap(self, avail_w, avail_h):
        self._avail_w = avail_w
        return avail_w, 22*mm

    def draw(self):
        c = self.canv
        c.saveState()
        # label
        c.setFont(BODY_FONT, 8)
        c.setFillColor(self._accent)
        c.drawString(0, 14*mm, self._label)
        # rule under label
        c.setFillColor(self._accent)
        c.rect(0, 13*mm, self._avail_w * 0.25, 1, fill=1, stroke=0)
        # title
        c.setFont(TITLE_FONT, 24)
        c.setFillColor(WHITE)
        c.drawString(0, 3*mm, self._title)
        c.restoreState()


class PriceRow(Flowable):
    """One price line: service name (left) + price (right) + subtle divider."""
    def __init__(self, service: str, price: str, accent=TERRA, note: str = ""):
        super().__init__()
        self._service = service
        self._price = price
        self._accent = accent
        self._note = note

    def wrap(self, avail_w, avail_h):
        self._avail_w = avail_w
        return avail_w, 8*mm

    def draw(self):
        c = self.canv
        c.saveState()
        # divider
        c.setFillColor(DIVIDER)
        c.rect(0, 7.5*mm, self._avail_w, 0.5, fill=1, stroke=0)
        # service name
        c.setFont(BODY_FONT, 9)
        c.setFillColor(TEXT_MAIN)
        c.drawString(0, 1.5*mm, self._service)
        # note
        if self._note:
            c.setFont(BODY_FONT, 7)
            c.setFillColor(TEXT_DIM)
            c.drawString(0, -1.5*mm, self._note)
        # price
        c.setFont(TITLE_FONT, 11)
        c.setFillColor(self._accent)
        c.drawRightString(self._avail_w, 1.5*mm, self._price)
        c.restoreState()


class StatBox(Flowable):
    """Stat number + label in a card box."""
    def __init__(self, number: str, label: str, accent=TERRA, width_mm: float = 40):
        super().__init__()
        self._number = number
        self._label = label
        self._accent = accent
        self._bw = width_mm * mm

    def wrap(self, avail_w, avail_h):
        return self._bw, 22*mm

    def draw(self):
        c = self.canv
        c.saveState()
        # card bg
        c.setFillColor(CARD_BG)
        c.roundRect(0, 0, self._bw, 21*mm, 3, fill=1, stroke=0)
        # accent left bar
        c.setFillColor(self._accent)
        c.rect(0, 0, 3, 21*mm, fill=1, stroke=0)
        # number
        c.setFont(TITLE_FONT, 20)
        c.setFillColor(self._accent)
        c.drawCentredString(self._bw / 2 + 1.5, 12*mm, self._number)
        # label
        c.setFont(BODY_FONT, 7.5)
        c.setFillColor(TEXT_DIM)
        c.drawCentredString(self._bw / 2 + 1.5, 5*mm, self._label)
        c.restoreState()


class ProcessStep(Flowable):
    """Numbered process step."""
    def __init__(self, number: int, title: str, desc: str, accent=TERRA):
        super().__init__()
        self._n = str(number)
        self._title = title
        self._desc = desc
        self._accent = accent

    def wrap(self, avail_w, avail_h):
        self._avail_w = avail_w
        return avail_w, 18*mm

    def draw(self):
        c = self.canv
        c.saveState()
        # circle
        cx, cy = 6*mm, 9*mm
        c.setFillColor(self._accent)
        c.circle(cx, cy, 5.5*mm, fill=1, stroke=0)
        c.setFont(TITLE_FONT, 11)
        c.setFillColor(WHITE)
        c.drawCentredString(cx, cy - 1.5*mm, self._n)
        # connector line
        c.setFillColor(Color(0.83, 0.52, 0.35, 0.3))
        c.rect(cx, 0, 1, cy - 5.5*mm, fill=1, stroke=0)
        # title
        c.setFont(TITLE_FONT, 11)
        c.setFillColor(WHITE)
        c.drawString(14*mm, 12*mm, self._title)
        # desc
        c.setFont(BODY_FONT, 8.5)
        c.setFillColor(TEXT_MAIN)
        c.drawString(14*mm, 6*mm, self._desc)
        c.restoreState()


class ContactCard(Flowable):
    """Contact info card with icon-label pairs."""
    def __init__(self, items: list[tuple[str, str]], accent=TERRA):
        super().__init__()
        self._items = items
        self._accent = accent

    def wrap(self, avail_w, avail_h):
        self._avail_w = avail_w
        h = len(self._items) * 10*mm + 6*mm
        return avail_w, h

    def draw(self):
        c = self.canv
        c.saveState()
        h = len(self._items) * 10*mm + 6*mm
        # card bg
        c.setFillColor(CARD_BG)
        c.roundRect(0, 0, self._avail_w, h, 4, fill=1, stroke=0)
        c.setFillColor(self._accent)
        c.rect(0, 0, 3, h, fill=1, stroke=0)
        # items
        for i, (icon, text) in enumerate(self._items):
            y = h - (i + 1) * 10*mm + 1*mm
            c.setFont(BODY_FONT, 9)
            c.setFillColor(self._accent)
            c.drawString(6*mm, y + 2*mm, icon)
            c.setFillColor(TEXT_MAIN)
            c.drawString(18*mm, y + 2*mm, text)
        c.restoreState()


# ─────────────────────────────────────────────────────────
# HELPER: build two-column table
# ─────────────────────────────────────────────────────────
def two_col(left: list, right: list, col_ratio: float = 0.5, gap_mm: float = 6) -> Table:
    gap = gap_mm * mm
    avail = W - 25*mm  # frame width
    lw = avail * col_ratio - gap / 2
    rw = avail * (1 - col_ratio) - gap / 2
    return Table(
        [[left, right]],
        colWidths=[lw, rw],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("INNERGRID", (0, 0), (-1, -1), 0, white),
        ]),
    )


# ─────────────────────────────────────────────────────────
# PAGE CONTENT BUILDERS
# ─────────────────────────────────────────────────────────
def page_cover() -> list:
    story = []

    # ── Logo (top-right zone, drawn on canvas in bg — here we place it via spacer + inline)
    story.append(Spacer(1, 15*mm))

    # ── Big headline
    story.append(Paragraph("Your Bali.", ST["H1"]))
    story.append(Paragraph("Done Right.", ST["H1"]))
    story.append(Spacer(1, 4*mm))
    story.append(HRule(50, TERRA, 2))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        "Expert immigration, company setup & tax advisory\n"
        "for expats and investors in Bali, Indonesia.",
        ST["TAGLINE"]))

    story.append(Spacer(1, 20*mm))

    # ── Stats row
    stats = [
        StatBox("5,000+", "Clients served",  TERRA, 42),
        StatBox("10+",    "Years in Bali",    GOLD,  42),
        StatBox("3",      "Core services",    INDIGO, 42),
        StatBox("99%",    "Compliance rate",  GREEN,  42),
    ]
    gap = 4*mm
    tbl = Table(
        [stats],
        colWidths=[42*mm, 42*mm, 42*mm, 42*mm],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), gap),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]),
    )
    story.append(tbl)

    story.append(Spacer(1, 20*mm))

    # ── Tagline block
    story.append(Paragraph("AI-powered intelligence.", ST["ACCENT"]))
    story.append(Paragraph("Human expertise.", ST["ACCENT"]))
    story.append(Paragraph("Local authority.", ST["ACCENT"]))

    story.append(Spacer(1, 20*mm))

    # ── Service pills
    pills = ["Immigration", "Company Setup", "Tax & Accounting"]
    pill_str = "  ·  ".join(f'<font color="{TERRA.hexval()}">{p}</font>' for p in pills)
    story.append(Paragraph(pill_str, ST["SMALL"]))

    # Logo positioned in top-right via onPage canvas
    story.append(NextPageTemplate("who"))
    story.append(PageBreak())
    return story


def page_who() -> list:
    story = []
    story.append(SectionHeader("About Bali Zero", "Who We Are", TERRA))
    story.append(Spacer(1, 6*mm))

    intro = (
        "Bali Zero is Bali's leading immigration and business services firm, "
        "serving expats and investors from over 40 countries since 2014. "
        "We combine deep local expertise with AI-powered intelligence to deliver "
        "accurate, fast, and reliable guidance — so you can build your life in Bali "
        "with full confidence and zero uncertainty."
    )
    story.append(Paragraph(intro, ST["BODY"]))
    story.append(Spacer(1, 6*mm))

    # Why us: 3 pillars
    pillars = [
        ("Local Authority", "10+ years in Bali. We know every immigration officer, every notary, every rule change — often before it's announced."),
        ("AI-Verified Accuracy", "Our AI cross-references every regulation, flags inconsistencies, and ensures every answer is grounded in current law. AI verifies. Humans decide."),
        ("End-to-End Service", "From your first visa to company setup, KBLI compliance, tax filing, and property acquisition — one team, one relationship."),
    ]
    for title, desc in pillars:
        story.append(KeepTogether([
            Paragraph(f'<font color="{TERRA.hexval()}">{title}</font>', ST["H3"]),
            Spacer(1, 1.5*mm),
            Paragraph(desc, ST["BODY"]),
            Spacer(1, 4*mm),
        ]))

    story.append(Spacer(1, 3*mm))
    story.append(HRule(40, TERRA, 1))
    story.append(Spacer(1, 4*mm))

    # Anti-fraud note
    story.append(Paragraph(
        "Transparency guarantee: We never ask for personal document originals. "
        "All work is traceable in your client portal. Our team identities are verifiable.",
        ST["SMALL"]))

    story.append(NextPageTemplate("imm"))
    story.append(PageBreak())
    return story


def page_immigration() -> list:
    story = []
    story.append(SectionHeader("Immigration Services", "Visas & Permits", INDIGO))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        "From a 60-day tourist visa to a lifetime KITAP — we handle every immigration "
        "pathway in Indonesia. All applications are filed digitally via the Molina portal "
        "by our licensed team.",
        ST["BODY"]))
    story.append(Spacer(1, 5*mm))

    # Left column: visa categories + prices
    # Right column: key notes

    # Popular single-entry
    left = []
    left.append(Paragraph("Single-Entry Visas", ST["ACCENTI"]))
    left.append(Spacer(1, 2*mm))

    single_entries = [
        ("C1 Tourism (60 days)",      get_price("single_entry_visas", "C1 Tourism")),
        ("C2 Business (60 days)",     get_price("single_entry_visas", "C2 Business")),
        ("C18 Work Trial (90 days)",  get_price("single_entry_visas", "C18 Work Trial")),
        ("C22A&B Internship (180d)",  get_price("single_entry_visas", "C22A&B Internship (180")),
    ]
    for name, price in single_entries:
        left.append(PriceRow(name, price, INDIGO))
    left.append(Spacer(1, 4*mm))

    left.append(Paragraph("Multiple-Entry Visas", ST["ACCENTI"]))
    left.append(Spacer(1, 2*mm))
    left.append(PriceRow("D12 Business (1 year)",  get_price("multiple_entry_visas", "D12 Business Investigation (1"), INDIGO))
    left.append(PriceRow("D12 Business (2 years)", get_price("multiple_entry_visas", "D12 Business Investigation (2"), INDIGO))
    left.append(Spacer(1, 4*mm))

    left.append(Paragraph("KITAS / Stay Permits", ST["ACCENTI"]))
    left.append(Spacer(1, 2*mm))
    kitas_rows = [
        ("E33G Remote Worker (Offshore)", get_price("kitas_permits", "E33G Remote Worker (Offshore")),
        ("E33G Remote Worker (Altus)",    get_price("kitas_permits", "E33G Remote Worker (Altus")),
        ("Freelance E23 (Offshore)",      get_price("kitas_permits", "Freelance E23 (Offshore")),
        ("Investor KITAS 2Y (Offshore)",  get_price("kitas_permits", "Investor KITAS 2 Years (Offshore")),
        ("Retirement KITAS (Offshore)",   get_price("kitas_permits", "Retirement (Offshore")),
        ("Spouse / Dependent 1Y",         get_price("kitas_permits", "Spouse 1 Year (Offshore")),
    ]
    for name, price in kitas_rows:
        left.append(PriceRow(name, price, INDIGO))

    # Right column: key info
    right = []
    right.append(Paragraph("Offshore vs Altus", ST["ACCENTI"]))
    right.append(Spacer(1, 1.5*mm))
    right.append(Paragraph(
        "<b>Offshore:</b> Applied from outside Indonesia (recommended for new applicants).\n\n"
        "<b>Altus/Onshore:</b> Applied while in Bali — faster, no flight required.",
        ST["SMALL"]))
    right.append(Spacer(1, 4*mm))

    right.append(Paragraph("Urgent Processing", ST["ACCENTI"]))
    right.append(Spacer(1, 1.5*mm))
    right.append(PriceRow("Same day (1 day)",  "Rp 3M", TERRA))
    right.append(PriceRow("2-day service",     "Rp 2.5M", GOLD))
    right.append(PriceRow("3-day service",     "Rp 1M",  TEXT_DIM))
    right.append(Spacer(1, 4*mm))

    right.append(Paragraph("KITAP (Permanent)", ST["ACCENTI"]))
    right.append(Spacer(1, 1.5*mm))
    right.append(PriceRow("Investor KITAP + MERP", get_price("kitas_permits", "Investor KITAP"), GOLD))
    right.append(PriceRow("Retirement KITAP",      get_price("kitas_permits", "Retirement KITAP"), GOLD))
    right.append(Spacer(1, 4*mm))

    right.append(Paragraph("MERP (Re-entry)", ST["ACCENTI"]))
    right.append(Spacer(1, 1.5*mm))
    right.append(PriceRow("MERP 1 year", get_price("kitas_permits", "MERP 1 Year"), INDIGO))
    right.append(PriceRow("MERP 2 year", get_price("kitas_permits", "MERP 2 Year"), INDIGO))

    story.append(two_col(left, right, col_ratio=0.56))
    story.append(NextPageTemplate("biz"))
    story.append(PageBreak())
    return story


def page_business() -> list:
    story = []
    story.append(SectionHeader("Business Services", "Company Setup", TERRA))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        "Setting up a PT PMA (foreign-owned company) or PT PMDN in Bali requires "
        "navigating OSS, KBLI codes, notarial deeds, and LKPM reporting. "
        "We handle every step — from entity selection to BKPM registration and "
        "the June 2026 KBLI 2025 migration.",
        ST["BODY"]))
    story.append(Spacer(1, 5*mm))

    # Prices
    left = []
    left.append(Paragraph("Company Formation", ST["ACCENT"]))
    left.append(Spacer(1, 2*mm))
    left.append(PriceRow("New PMA Company (full package)", get_price("other_services", "NEW COMPANY"), TERRA, "Includes OSS, BKPM, NIB, notarial deed"))
    left.append(PriceRow("Virtual Office (1 year)",        get_price("other_services", "VIRTUAL OFFICE"), TERRA))
    left.append(Spacer(1, 4*mm))

    left.append(Paragraph("Work Permits (Foreign Employees)", ST["ACCENT"]))
    left.append(Spacer(1, 2*mm))
    working_rows = [
        ("Working KITAS (Offshore)", get_price("kitas_permits", "Working KITAS (Offshore")),
        ("Working KITAS (Altus)",    get_price("kitas_permits", "Working KITAS (Altus")),
        ("Working KITAS (Extend)",   get_price("kitas_permits", "Working KITAS (Extend")),
    ]
    for name, price in working_rows:
        left.append(PriceRow(name, price, TERRA))
    left.append(Spacer(1, 4*mm))

    left.append(Paragraph("Compliance & Admin", ST["ACCENT"]))
    left.append(Spacer(1, 2*mm))
    admin_rows = [
        ("Cancel RPTKA / IMTA / Wajib Lapor", get_price("other_services", "CANCEL (RPTKA")),
        ("Cancel RPTKA only",                  get_price("other_services", "CANCEL RPTKA")),
        ("Reset Molina",                       get_price("other_services", "RESET MOLINA")),
        ("EPO (OSS permit)",                   get_price("other_services", "EPO")),
        ("ERP (OSS amendment)",                get_price("other_services", "ERP")),
    ]
    for name, price in admin_rows:
        left.append(PriceRow(name, price, TERRA))

    right = []
    right.append(Paragraph("KBLI 2025 Deadline", ST["ACCENT"]))
    right.append(Spacer(1, 1.5*mm))
    right.append(Paragraph(
        "All businesses must migrate from KBLI 2020 to KBLI 2025 codes "
        "by <b>18 June 2026</b>. Non-compliant NIBs risk suspension.\n\n"
        "Use our KBLI Navigator at <b>balizero.com/kbli</b> to check "
        "your codes and PMA status instantly.",
        ST["SMALL"]))
    right.append(Spacer(1, 4*mm))

    right.append(Paragraph("What's Included", ST["ACCENT"]))
    right.append(Spacer(1, 1.5*mm))
    included = [
        "OSS & BKPM registration",
        "KBLI 2025 selection & PMA check",
        "Notarial deed coordination",
        "NIB issuance",
        "LKPM reporting setup",
        "Virtual office address",
    ]
    for item in included:
        right.append(Paragraph(f'<font color="{TERRA.hexval()}">✓</font>  {item}', ST["SMALL"]))
        right.append(Spacer(1, 1.5*mm))

    story.append(two_col(left, right, col_ratio=0.58))
    story.append(NextPageTemplate("tax"))
    story.append(PageBreak())
    return story


def page_tax() -> list:
    story = []
    story.append(SectionHeader("Tax & Accounting", "Financial Compliance", GOLD))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        "Indonesian tax law is complex — and the wrong structure can cost more than "
        "the tax itself. Our certified advisors ensure your PT PMA, KITAS, and personal "
        "obligations are met, with zero surprises.",
        ST["BODY"]))
    story.append(Spacer(1, 5*mm))

    left = []
    left.append(Paragraph("Personal Tax", ST["ACCENTG"]))
    left.append(Spacer(1, 2*mm))
    left.append(Paragraph(
        "If you hold a KITAS (working, investor, freelance), you are a tax resident "
        "and must file an annual SPT. We handle registration, filing, and NPWP issuance.",
        ST["SMALL"]))
    left.append(Spacer(1, 4*mm))

    left.append(Paragraph("Corporate Tax", ST["ACCENTG"]))
    left.append(Spacer(1, 2*mm))
    left.append(Paragraph(
        "PT PMA companies must file monthly VAT (PPN), income tax (PPh 21/25), "
        "and annual reports. We act as your local tax representative.",
        ST["SMALL"]))
    left.append(Spacer(1, 4*mm))

    left.append(Paragraph("Document Services", ST["ACCENTG"]))
    left.append(Spacer(1, 2*mm))
    doc_rows = [
        ("SKTT (Resident Card)",        get_price("other_services", "SKTT")),
        ("SKCK (Police Clearance)",     get_price("other_services", "SKCK")),
        ("Domicile Letter",             get_price("other_services", "DOMICILIE LETTER")),
        ("Domicile + SKTT (combined)",  get_price("other_services", "DOMICILIE + SKTT")),
        ("Passport 5 years",            get_price("other_services", "PASSPORT 5 YEARS")),
        ("Passport 10 years",           get_price("other_services", "PASSPORT 10 YEARS")),
        ("Mutation (passport/address)", get_price("other_services", "MUTATION PASSPORT")),
    ]
    for name, price in doc_rows:
        left.append(PriceRow(name, price, GOLD))

    right = []
    right.append(Paragraph("Key Tax Facts", ST["ACCENTG"]))
    right.append(Spacer(1, 1.5*mm))
    facts = [
        ("Personal income tax", "5%–35% progressive"),
        ("Corporate income tax", "22% flat"),
        ("VAT (PPN)",            "12% (2025)"),
        ("NPWP requirement",     "Mandatory for KITAS holders"),
        ("Filing deadline",      "Annual SPT: 31 March"),
        ("DGT jurisdiction",     "Worldwide income (tax residents)"),
    ]
    for k, v in facts:
        right.append(Paragraph(f'<font color="{GOLD.hexval()}">{k}:</font>  {v}', ST["SMALL"]))
        right.append(Spacer(1, 2*mm))

    right.append(Spacer(1, 4*mm))
    right.append(Paragraph("Property Documents", ST["ACCENTG"]))
    right.append(Spacer(1, 1.5*mm))
    right.append(Paragraph(
        "Foreign nationals cannot hold Hak Milik (freehold). "
        "We structure Hak Pakai (Right of Use) and Hak Sewa (Leasehold) "
        "arrangements that are legally compliant under PP 18/2021.",
        ST["SMALL"]))

    story.append(two_col(left, right, col_ratio=0.55))
    story.append(NextPageTemplate("how"))
    story.append(PageBreak())
    return story


def page_how() -> list:
    story = []
    story.append(SectionHeader("Our Process", "How We Work", GREEN))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        "Every client gets a dedicated advisor, a private portal to track their case, "
        "and access to our AI assistant Zantara — available 24/7 for questions, "
        "document checklists, and status updates.",
        ST["BODY"]))
    story.append(Spacer(1, 5*mm))

    steps = [
        (1, "Free Discovery Call",    "We map your situation: visa needs, business goals, tax obligations."),
        (2, "Proposal & Onboarding",  "You receive a fixed-price proposal. No surprises. No hidden fees."),
        (3, "Dedicated Advisor",      "Your advisor coordinates everything. You have one point of contact."),
        (4, "AI-Backed Preparation",  "Zantara cross-checks all documents before submission. AI verifies. Humans decide."),
        (5, "Filing & Tracking",      "We file with the relevant authority. You track progress in real-time."),
        (6, "Approval & Aftercare",   "We deliver your permit/certificate. Annual reminders keep you compliant."),
    ]
    for n, title, desc in steps:
        story.append(ProcessStep(n, title, desc, GREEN))
        story.append(Spacer(1, 1.5*mm))

    story.append(Spacer(1, 4*mm))
    story.append(HRule(40, GREEN, 1))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph(
        "Your client portal at <b>my.balizero.com</b> gives you "
        "real-time case status, document vault, and direct messaging with your advisor.",
        ST["SMALL"]))

    story.append(NextPageTemplate("contact"))
    story.append(PageBreak())
    return story


def page_contact() -> list:
    story = []
    story.append(SectionHeader("Get In Touch", "Start Today", TERRA))
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph(
        "Ready to make Bali official? Our team is available Monday–Saturday, "
        "9am–6pm WITA. WhatsApp is the fastest way to reach us.",
        ST["BODY"]))
    story.append(Spacer(1, 6*mm))

    contact_items = [
        ("✉",  "info@balizero.com"),
        ("📱",  "+62 813 3805 1876  (WhatsApp)"),
        ("🌐",  "balizero.com"),
        ("📍",  "Canggu, Bali, Indonesia"),
        ("🕐",  "Mon–Sat  09:00–18:00 WITA"),
        ("🤖",  "AI chat available 24/7 at zantara.balizero.com"),
    ]
    story.append(ContactCard(contact_items, TERRA))
    story.append(Spacer(1, 8*mm))

    # Second column: QR prompt + note
    story.append(Paragraph("First consultation is always free.", ST["H3"]))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "We'll map your situation, identify the right pathway, and give you "
        "a fixed-price quote before you commit to anything.",
        ST["BODY"]))
    story.append(Spacer(1, 5*mm))

    story.append(HRule(60, TERRA, 1.5))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        '"We built Bali Zero because we saw too many expats get caught by wrong visas, '
        'fraudulent agents, and surprise tax bills. '
        'Ten years later, we\'ve helped 5,000 people do it right."',
        ST["BODY"]))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("— Bali Zero Founding Team", ST["LABEL"]))

    return story


# ─────────────────────────────────────────────────────────
# COVER LOGO OVERLAY
# ─────────────────────────────────────────────────────────
def _cover_logo_overlay(canvas, doc):
    """Draw logo on cover page (called as onPage)."""
    _bg_cover(canvas, doc)
    if LOGO_READER:
        lw = 45*mm
        lh = 18*mm
        lx = W - lw - 12*mm
        ly = H - lh - 12*mm
        canvas.drawImage(LOGO_READER, lx, ly, width=lw, height=lh, mask="auto")


def _content_logo_overlay(section_id: str):
    """Return onPage callback that draws background + small logo for content pages."""
    bg_fn = _make_content_bg(section_id)
    def _fn(canvas, doc):
        bg_fn(canvas, doc)
        if LOGO_READER:
            lw = 28*mm
            lh = 11*mm
            lx = W - lw - 10*mm
            ly = H - lh - 9*mm
            canvas.drawImage(LOGO_READER, lx, ly, width=lw, height=lh, mask="auto")
    return _fn


# ─────────────────────────────────────────────────────────
# DOCUMENT ASSEMBLY
# ─────────────────────────────────────────────────────────
MARGIN_LR = 15*mm
MARGIN_TOP_COVER = 20*mm
MARGIN_BOT_COVER = 18*mm
MARGIN_TOP = 18*mm
MARGIN_BOT = 20*mm

def build_doc() -> None:
    doc = BaseDocTemplate(
        str(OUTPUT_PATH),
        pagesize=A4,
        leftMargin=MARGIN_LR,
        rightMargin=MARGIN_LR,
        topMargin=MARGIN_TOP_COVER,
        bottomMargin=MARGIN_BOT_COVER,
    )

    # Frames
    f_cover = Frame(MARGIN_LR, MARGIN_BOT_COVER, W - 2*MARGIN_LR, H - MARGIN_TOP_COVER - MARGIN_BOT_COVER, id="cover")
    f_content = Frame(MARGIN_LR + 5, MARGIN_BOT, W - 2*MARGIN_LR - 5, H - MARGIN_TOP - MARGIN_BOT, id="content")

    pages = [
        PageTemplate(id="cover",   frames=[f_cover],   onPage=_cover_logo_overlay),
        PageTemplate(id="who",     frames=[f_content],  onPage=_content_logo_overlay("who")),
        PageTemplate(id="imm",     frames=[f_content],  onPage=_content_logo_overlay("imm")),
        PageTemplate(id="biz",     frames=[f_content],  onPage=_content_logo_overlay("biz")),
        PageTemplate(id="tax",     frames=[f_content],  onPage=_content_logo_overlay("tax")),
        PageTemplate(id="how",     frames=[f_content],  onPage=_content_logo_overlay("how")),
        PageTemplate(id="contact", frames=[f_content],  onPage=_content_logo_overlay("contact")),
    ]
    doc.addPageTemplates(pages)

    story = []
    story += page_cover()
    story += page_who()
    story += page_immigration()
    story += page_business()
    story += page_tax()
    story += page_how()
    story += page_contact()

    doc.build(story)


# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🏝  Bali Zero Brochure Generator v3")
    print(f"   Output: {OUTPUT_PATH}")
    build_doc()
    size_kb = OUTPUT_PATH.stat().st_size // 1024
    print(f"✅ Brochure generated: {OUTPUT_PATH}")
    print(f"   Size: {size_kb} KB | Pages: 7")
    print(f"   Pricing source: {PRICING_PATH.name}")
    print(f"   Logo: {'embedded (RGBA)' if LOGO_READER else 'missing'}")
