"""
Bali Zero — Company Brochure PDF Generator v2
=============================================
One-time script. Run when services/prices change.
Output: data/assets/brochure_balizero_en.pdf

Usage:
    cd apps/backend-rag
    python scripts/generate_brochure.py

Psychological arc (DeepSeek synthesis):
    Page 1 (Cover)        → Relief:              "You are in the right place"
    Page 2 (Who We Are)   → Orientation:          "Here is what we are"
    Page 3 (Immigration)  → Impressed Confidence: "They know this cold"
    Page 4 (Business)     → Safety:               "They have done this before"
    Page 5 (Tax)          → Informed Confidence:  "Nothing will surprise me"
    Page 6 (How We Work)  → Belonging:            "This system was built for me"
    Page 7 (Contact)      → Readiness:            "I know exactly what to do next"

Content strategy (Gemini research):
    - Premium immigration brochures fail when they describe services.
      They succeed when they eliminate the prospect's dominant fear.
    - Every section answers: "Can I trust these people with something this consequential?"
    - Anti-fraud signals critical for Bali market (PT MGI scandal documented)
    - AI messaging: "AI verifies. Humans decide." — never say "automated" or "algorithm"
    - Fear hierarchy: wrong visa/deportation > fraud > wrong PT PMA > regulations change

Design (Codex research):
    - BaseDocTemplate + PageTemplate per-page background (not SimpleDocTemplate)
    - All custom elements as Flowable subclasses
    - Logo: RGBA transparency via Pillow, mask='auto' in drawImage
    - Semi-transparent fills: Color(r,g,b,alpha) not hex string concatenation
    - Section accent colors: cover/who/biz/contact=#d4845a, imm=#5e7fb5, tax=#c9a96e, ai=#4db87a
"""

from __future__ import annotations

import io
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

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────────
import numpy as np
from PIL import Image as PILImage

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
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
)

# ─────────────────────────────────────────────────────────
# PAGE GEOMETRY
# ─────────────────────────────────────────────────────────
W, H = A4  # 595.28 x 841.89 pt
MARGIN = 20 * mm

# ─────────────────────────────────────────────────────────
# BRAND PALETTE
# ─────────────────────────────────────────────────────────
BASE      = HexColor("#0c0c0e")
PANEL     = HexColor("#111115")
CARD_BG   = HexColor("#1a1a1e")
CARD_BG2  = HexColor("#202024")
BORDER    = HexColor("#262629")
TERRA     = HexColor("#d4845a")
GOLD      = HexColor("#c9a96e")
TEXT      = HexColor("#edeae4")
MUTED     = HexColor("#8c8884")
FAINT     = HexColor("#575350")
INDIGO    = HexColor("#5e7fb5")
GREEN     = HexColor("#4db87a")
GREEN_BG  = Color(0.302, 0.722, 0.478, alpha=0.12)
TERRA_BG  = Color(0.831, 0.518, 0.353, alpha=0.12)

# Section accent colors per page
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
# FONT LOADING
# ─────────────────────────────────────────────────────────
def _load_fonts() -> dict[str, str]:
    fonts: dict[str, str] = {}
    montserrat = Path("/Users/nuzantara/Library/Fonts/Montserrat[wght].ttf")
    sf         = Path("/System/Library/Fonts/SFNS.ttf")
    sf_italic  = Path("/System/Library/Fonts/SFNSItalic.ttf")

    if montserrat.exists():
        pdfmetrics.registerFont(TTFont("Display", str(montserrat)))
        fonts["display"] = "Display"
    else:
        fonts["display"] = "Helvetica-Bold"

    if sf.exists():
        pdfmetrics.registerFont(TTFont("Body", str(sf)))
        fonts["body"] = "Body"
    else:
        fonts["body"] = "Helvetica"

    if sf_italic.exists():
        pdfmetrics.registerFont(TTFont("BodyItalic", str(sf_italic)))
        fonts["body_italic"] = "BodyItalic"
    else:
        fonts["body_italic"] = "Helvetica-Oblique"

    return fonts

FONTS = _load_fonts()
DF = FONTS["display"]   # display / headline font
BF = FONTS["body"]      # body font
BI = FONTS["body_italic"]

# ─────────────────────────────────────────────────────────
# PARAGRAPH STYLES
# ─────────────────────────────────────────────────────────
def _s(**kw: object) -> ParagraphStyle:
    return ParagraphStyle("_", **kw)

S = {
    "h1": _s(fontName=DF, fontSize=28, leading=36, textColor=TERRA,
              spaceAfter=12, spaceBefore=6, alignment=TA_LEFT),
    "h2": _s(fontName=DF, fontSize=18, leading=24, textColor=GOLD,
              spaceAfter=8, spaceBefore=16),
    "h3": _s(fontName="Helvetica-Bold", fontSize=12, leading=18,
              textColor=TEXT, spaceAfter=5, spaceBefore=12),
    "body": _s(fontName=BF, fontSize=10, leading=16, textColor=TEXT,
               spaceAfter=7),
    "body_muted": _s(fontName=BF, fontSize=9.5, leading=15, textColor=MUTED,
                     spaceAfter=5),
    "label": _s(fontName="Helvetica-Bold", fontSize=7.5, leading=11,
                textColor=MUTED, spaceAfter=2),
    "caption": _s(fontName=BF, fontSize=7.5, leading=11, textColor=FAINT,
                  spaceAfter=3),
    "cover_title": _s(fontName=DF, fontSize=40, leading=48, textColor=TEXT,
                      spaceAfter=16, alignment=TA_CENTER),
    "cover_sub": _s(fontName=BF, fontSize=13, leading=20, textColor=MUTED,
                    spaceAfter=10, alignment=TA_CENTER),
    "cover_accent": _s(fontName=DF, fontSize=10, leading=15, textColor=TERRA,
                       alignment=TA_CENTER),
    "bullet": _s(fontName=BF, fontSize=9.5, leading=15, textColor=TEXT,
                 spaceAfter=3, leftIndent=12),
    "table_header": _s(fontName="Helvetica-Bold", fontSize=8.5, leading=12,
                       textColor=TERRA),
    "table_cell": _s(fontName=BF, fontSize=9, leading=13, textColor=TEXT),
    "table_cell_muted": _s(fontName=BF, fontSize=9, leading=13, textColor=MUTED),
}

# ─────────────────────────────────────────────────────────
# LOGO PREPARATION
# ─────────────────────────────────────────────────────────
def _prepare_logo(logo_path: Path) -> ImageReader | None:
    """Convert near-black-background logo PNG to RGBA for dark PDF use."""
    if not logo_path.exists():
        return None
    try:
        img = PILImage.open(str(logo_path)).convert("RGB")
        arr = np.array(img)
        rgba = np.zeros((*arr.shape[:2], 4), dtype=np.uint8)
        rgba[:, :, :3] = arr
        brightness = arr.max(axis=2)
        # Hard cut at 25, soft antialiasing 25–60
        alpha = np.where(brightness < 25, 0, 255).astype(np.uint8)
        soft_mask = (brightness >= 25) & (brightness < 60)
        alpha[soft_mask] = ((brightness[soft_mask] - 25) / 35.0 * 255).astype(np.uint8)
        rgba[:, :, 3] = alpha
        pil_rgba = PILImage.fromarray(rgba, "RGBA")
        buf = io.BytesIO()
        pil_rgba.save(buf, format="PNG")
        buf.seek(0)
        return ImageReader(buf)
    except Exception as e:
        print(f"⚠ Logo preparation failed: {e}", file=sys.stderr)
        return None

LOGO_READER = _prepare_logo(LOGO_PATH)

# ─────────────────────────────────────────────────────────
# CUSTOM FLOWABLES
# ─────────────────────────────────────────────────────────

class AccentDivider(Flowable):
    """Terracotta/gold horizontal rule with left diamond marker."""
    def __init__(self, width: float = 165 * mm, color: HexColor = TERRA, thickness: float = 1.5):
        super().__init__()
        self.width = width
        self.height = 14
        self.color = color
        self.thickness = thickness

    def draw(self) -> None:
        c = self.canv
        c.setStrokeColor(self.color)
        c.setLineWidth(self.thickness)
        c.line(0, 7, self.width, 7)
        c.setFillColor(self.color)
        c.saveState()
        c.translate(0, 7)
        c.rotate(45)
        c.rect(-3.5, -3.5, 7, 7, fill=1, stroke=0)
        c.restoreState()


class StatCard(Flowable):
    """Numbered stat card: big number + label."""
    def __init__(self, number: str, label: str, width: float = 36 * mm,
                 height: float = 32 * mm, accent: HexColor = TERRA):
        super().__init__()
        self.width = width
        self.height = height
        self.number = number
        self.label = label
        self.accent = accent

    def draw(self) -> None:
        c = self.canv
        c.setFillColor(CARD_BG)
        c.roundRect(0, 0, self.width, self.height, 6, fill=1, stroke=0)
        c.setFillColor(self.accent)
        c.rect(0, self.height - 2.5, self.width, 2.5, fill=1, stroke=0)
        # Number
        c.setFillColor(self.accent)
        c.setFont(DF, 18)
        c.drawCentredString(self.width / 2, self.height / 2 + 2, self.number)
        # Label
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7)
        c.drawCentredString(self.width / 2, self.height / 2 - 10, self.label.upper())


class ProcessStep(Flowable):
    """Numbered process step with optional connector line."""
    def __init__(self, number: int, title: str, description: str,
                 is_last: bool = False, accent: HexColor = GREEN,
                 width: float = 155 * mm):
        super().__init__()
        self.width = width
        self.height = 48
        self.number = str(number)
        self.title = title
        self.description = description
        self.is_last = is_last
        self.accent = accent

    def draw(self) -> None:
        c = self.canv
        # Connector (dashed vertical line below circle)
        if not self.is_last:
            c.setStrokeColor(BORDER)
            c.setLineWidth(1)
            c.setDash(3, 4)
            c.line(13, 0, 13, self.height - 25)
            c.setDash()
        # Circle
        c.setFillColor(self.accent)
        c.circle(13, self.height - 13, 10, fill=1, stroke=0)
        # Number in circle
        c.setFillColor(BASE)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(13, self.height - 17, self.number)
        # Title
        c.setFillColor(TEXT)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(34, self.height - 11, self.title)
        # Description
        c.setFillColor(MUTED)
        c.setFont(BF, 9)
        c.drawString(34, self.height - 24, self.description)


class GuardrailBadge(Flowable):
    """Pill badge for AI guardrail features."""
    def __init__(self, label: str, color: HexColor = GREEN, width: float = 72 * mm):
        super().__init__()
        self.label = label
        self.width = width
        self.height = 26
        self.color = color
        if color == GREEN:
            self.bg = GREEN_BG
        else:
            self.bg = TERRA_BG

    def draw(self) -> None:
        c = self.canv
        c.setFillColor(self.bg)
        c.roundRect(0, 0, self.width, self.height, 13, fill=1, stroke=0)
        c.setStrokeColor(self.color)
        c.setLineWidth(0.8)
        c.roundRect(0, 0, self.width, self.height, 13, fill=0, stroke=1)
        c.setFillColor(self.color)
        c.circle(12, self.height / 2, 3.5, fill=1, stroke=0)
        c.setFillColor(TEXT)
        c.setFont(BF, 8.5)
        c.drawString(22, self.height / 2 - 3.5, self.label)


class ServiceCard(Flowable):
    """Service category card with title, accent line, and bullet points."""
    def __init__(self, title: str, bullets: list[str],
                 width: float = 77 * mm, accent: HexColor = TERRA):
        super().__init__()
        self.title = title
        self.bullets = bullets
        self.width = width
        self.accent = accent
        self.height = 28 + len(bullets) * 14

    def draw(self) -> None:
        c = self.canv
        c.setFillColor(CARD_BG)
        c.roundRect(0, 0, self.width, self.height, 5, fill=1, stroke=0)
        c.setFillColor(self.accent)
        c.roundRect(0, self.height - 3, self.width, 3, 5, fill=1, stroke=0)
        # Title
        c.setFillColor(self.accent)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(10, self.height - 17, self.title)
        # Bullets
        c.setFillColor(TEXT)
        c.setFont(BF, 8.5)
        for i, bullet in enumerate(self.bullets):
            y = self.height - 30 - i * 14
            c.setFillColor(self.accent)
            c.circle(15, y + 4, 2, fill=1, stroke=0)
            c.setFillColor(TEXT)
            c.drawString(22, y, bullet)


class KeyValueCard(Flowable):
    """Dark card with key:value rows (e.g. processing times, rates)."""
    def __init__(self, rows: list[tuple[str, str]],
                 width: float = 60 * mm, accent: HexColor = INDIGO):
        super().__init__()
        self.rows = rows
        self.width = width
        self.accent = accent
        self.height = 16 + len(rows) * 20

    def draw(self) -> None:
        c = self.canv
        c.setFillColor(CARD_BG)
        c.roundRect(0, 0, self.width, self.height, 5, fill=1, stroke=0)
        c.setFillColor(self.accent)
        c.roundRect(0, self.height - 3, self.width, 3, 5, fill=1, stroke=0)
        for i, (key, val) in enumerate(self.rows):
            y = self.height - 20 - i * 20
            c.setStrokeColor(BORDER)
            c.setLineWidth(0.4)
            if i > 0:
                c.line(8, y + 18, self.width - 8, y + 18)
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 7)
            c.drawString(10, y + 5, key.upper())
            c.setFillColor(TEXT)
            c.setFont("Helvetica-Bold", 9)
            c.drawRightString(self.width - 10, y + 5, val)


# ─────────────────────────────────────────────────────────
# PAGE BACKGROUND CALLBACKS
# ─────────────────────────────────────────────────────────

def _make_cover_bg(canvas: object, doc: object) -> None:  # type: ignore[override]
    canvas.saveState()
    # Dark gradient background (60 bands)
    for i in range(60):
        t = i / 60
        r = 0.047 + t * 0.035
        g = 0.047 + t * 0.025
        b = 0.055 + t * 0.035
        canvas.setFillColorRGB(r, g, b)
        canvas.rect(0, i * (H / 60), W, H / 60 + 1, fill=1, stroke=0)
    # Top accent bar
    canvas.setFillColor(TERRA)
    canvas.rect(0, H - 4, W, 4, fill=1, stroke=0)
    # Bottom accent bar
    canvas.setFillColor(HexColor("#1e1e23"))
    canvas.rect(0, 0, W, 50, fill=1, stroke=0)
    canvas.restoreState()


def _make_content_bg(section_id: str) -> object:
    accent = SECTION_COLORS.get(section_id, TERRA)

    def _bg(canvas: object, doc: object) -> None:  # type: ignore[override]
        canvas.saveState()
        # Flat base
        canvas.setFillColor(BASE)
        canvas.rect(0, 0, W, H, fill=1, stroke=0)
        # Left accent bar
        canvas.setFillColor(accent)
        canvas.rect(0, 35 * mm, 3, H - 55 * mm, fill=1, stroke=0)
        # Footer divider
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, 17 * mm, W - MARGIN, 17 * mm)
        # Footer text
        canvas.setFillColor(FAINT)
        canvas.setFont(BF, 7)
        canvas.drawString(MARGIN, 11 * mm, "BALI ZERO  ·  balizero.com  ·  wa.me/6281338051876")
        canvas.drawRightString(W - MARGIN, 11 * mm, str(doc.page - 1))
        canvas.restoreState()

    return _bg


# ─────────────────────────────────────────────────────────
# STORY BUILDERS
# ─────────────────────────────────────────────────────────

def _sp(h: float = 8) -> Spacer:
    return Spacer(1, h)


def _p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, S[style])


def _comparison_table(data: list[list[str]], col_widths: list[float]) -> Table:
    """Dark alternating-row comparison table."""
    para_data = []
    for r_idx, row in enumerate(data):
        para_row = []
        for c_idx, cell in enumerate(row):
            if r_idx == 0:
                para_row.append(_p(cell, "table_header"))
            elif c_idx == 0:
                para_row.append(_p(cell, "table_cell"))
            else:
                para_row.append(_p(cell, "table_cell_muted"))
        para_data.append(para_row)

    t = Table(para_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  CARD_BG2),
        ("LINEBELOW",    (0, 0), (-1, 0),  1.5, TERRA),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#131315"), CARD_BG]),
        ("TOPPADDING",   (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 7),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW",    (0, 1), (-1, -2), 0.4, BORDER),
        ("BOX",          (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _two_col(left: Flowable, right: Flowable,
             lw: float = 92 * mm, rw: float = 63 * mm) -> Table:
    t = Table([[left, right]], colWidths=[lw, rw])
    t.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    return t


def _badge_row(badges: list[GuardrailBadge], col_width: float = 52 * mm) -> Table:
    t = Table([badges], colWidths=[col_width] * len(badges))
    t.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _stat_row(stats: list[tuple[str, str, str]]) -> Table:
    """Row of StatCards. stats = [(number, label, accent_hex), ...]"""
    cards = [StatCard(n, l, accent=HexColor(a)) for n, l, a in stats]
    cw = 155 * mm / len(cards)
    t = Table([cards], colWidths=[cw] * len(cards))
    t.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    return t


# ─────────────────────────────────────────────────────────
# PAGE CONTENT FUNCTIONS
# ─────────────────────────────────────────────────────────

def _page_cover(story: list) -> None:
    """
    Page 1: Relief — "You are in the right place"
    Cover is assembled via a custom canvas Flowable (drawn directly).
    """

    class CoverContent(Flowable):
        def __init__(self) -> None:
            super().__init__()
            self.width = 170 * mm
            self.height = 252 * mm

        def draw(self) -> None:
            c = self.canv
            cx = self.width / 2

            # Logo
            if LOGO_READER:
                logo_size = 62
                c.drawImage(LOGO_READER, cx - logo_size / 2,
                            self.height - 90, logo_size, logo_size, mask="auto")

            # Brand name
            c.setFillColor(TEXT)
            c.setFont(DF, 38)
            c.drawCentredString(cx, self.height - 118, "BALI ZERO")

            # Terracotta accent rule
            c.setStrokeColor(TERRA)
            c.setLineWidth(1.2)
            c.line(cx - 55, self.height - 128, cx + 55, self.height - 128)

            # Tagline
            c.setFillColor(MUTED)
            c.setFont(BF, 12)
            c.drawCentredString(cx, self.height - 142, "Guided by humans. Powered by AI.")

            # Hero statement
            c.setFillColor(TERRA)
            c.setFont(DF, 11)
            c.drawCentredString(cx, self.height - 162,
                                "INDONESIAN BUSINESS & IMMIGRATION SPECIALISTS")

            # Stat cards row
            stats = [
                ("5,000+", "Clients Served", "#d4845a"),
                ("10 Yrs",  "In Bali", "#c9a96e"),
                ("7",       "Services", "#d4845a"),
                ("24/7",    "AI Support", "#c9a96e"),
            ]
            card_w = 35 * mm
            card_h = 30 * mm
            total_w = len(stats) * card_w + (len(stats) - 1) * 4
            start_x = cx - total_w / 2
            y_cards = self.height - 235

            for i, (number, label, accent) in enumerate(stats):
                x = start_x + i * (card_w + 4)
                # Card bg
                c.setFillColor(CARD_BG)
                c.roundRect(x, y_cards, card_w, card_h, 5, fill=1, stroke=0)
                # Accent top
                c.setFillColor(HexColor(accent))
                c.roundRect(x, y_cards + card_h - 2.5, card_w, 2.5, 5, fill=1, stroke=0)
                # Number
                c.setFillColor(HexColor(accent))
                c.setFont(DF, 16)
                c.drawCentredString(x + card_w / 2, y_cards + card_h / 2 + 2, number)
                # Label
                c.setFillColor(MUTED)
                c.setFont("Helvetica", 6.5)
                c.drawCentredString(x + card_w / 2, y_cards + card_h / 2 - 9,
                                    label.upper())

            # Service list
            c.setStrokeColor(BORDER)
            c.setLineWidth(0.4)
            c.line(cx - 70, self.height - 280, cx + 70, self.height - 280)

            services = "Visa  ·  Company Setup  ·  Tax  ·  Property  ·  Compliance  ·  KBLI"
            c.setFillColor(FAINT)
            c.setFont(BF, 8)
            c.drawCentredString(cx, self.height - 291, services)

            # Website
            c.setFillColor(GOLD)
            c.setFont(DF, 9)
            c.drawCentredString(cx, self.height - 308, "www.balizero.com")

            # Anti-fraud signal (bottom area)
            c.setFillColor(CARD_BG)
            c.roundRect(cx - 80, 8, 160, 18, 4, fill=1, stroke=0)
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 7)
            c.drawCentredString(cx, 14,
                "Registered PT PMA  ·  KBLI 62090  ·  Jl. Raya Canggu, Bali, Indonesia")

    story.append(CoverContent())


def _page_who_we_are(story: list) -> None:
    """Page 2: Orientation — "Here is what we are" """
    story += [
        AccentDivider(color=TERRA),
        _p("Who We Are", "h1"),
        _p("Bali's first AI-powered business &amp; immigration platform", "h2"),
        _sp(4),
        _p(
            "Bali Zero was founded as a traditional consulting firm — lawyers, immigration "
            "specialists, and tax advisors based in Canggu. Over the past decade, we evolved "
            "into something different: a hybrid human+AI system where specialized agents "
            "handle deterministic work (price lookups, document checklists, deadline tracking, "
            "legal database searches) so our human experts can focus entirely on judgment, "
            "relationships, and complex problem-solving.",
            "body",
        ),
        _p(
            "The vast majority of our processes run on rules, not memory — which means you get "
            "consistent, reliable answers whether you reach us on a Monday morning or a "
            "Friday afternoon. No guesses. No outdated information. No hallucinated prices.",
            "body",
        ),
        _sp(10),
        _stat_row([
            ("5,000+",  "Clients Served", "#d4845a"),
            ("10+ Yrs", "In Bali", "#c9a96e"),
            ("40+",     "Nationalities", "#d4845a"),
            ("&lt;2h",  "Response Time", "#c9a96e"),
        ]),
        _sp(14),
        _p("Our Commitment", "h3"),
        AccentDivider(width=60 * mm, color=GOLD, thickness=1),
        _sp(4),
        _p(
            "Every regulation verified. Every decision reviewed by a human. "
            "Payments only through official bank transfers. Your documents never leave "
            "our secure client portal.",
            "body",
        ),
        _sp(8),
        _p(
            "We have been asked many times what separates us from the dozens of visa agents "
            "operating on the island. The answer is simple: we are the only firm in Bali "
            "where the AI cannot invent a price, and every answer is grounded in a cited "
            "Indonesian government source.",
            "body",
        ),
        _sp(12),
        AccentDivider(color=GOLD, thickness=1),
        _sp(4),
        _p(
            "PT Zero Intelligence Indonesia  ·  Registered PT PMA  ·  KBLI 62090  ·  "
            "Jl. Raya Canggu, Kuta Utara, Bali 80361",
            "body_muted",
        ),
    ]


def _page_immigration(story: list) -> None:
    """Page 3: Impressed Confidence — "They know this cold" """
    story += [
        AccentDivider(color=INDIGO),
        _p("Immigration Services", "h1"),
        _p("From tourist visa to permanent residency — we handle the full journey", "h2"),
        _sp(6),
    ]

    left_content: list[Flowable] = [
        _p("Visa-on-Arrival &amp; Short-Stay", "h3"),
        _p(
            "VOA (30 days), B211A Social/Cultural (60 days extendable to 180 days), "
            "B211B Investor Visit. We handle extensions and conversions.",
            "body",
        ),
        _sp(6),
        _p("KITAS — Limited Stay Permits", "h3"),
        _p(
            "KITAS Employment (sponsored by your PT PMA), KITAS Investor, "
            "KITAS Retirement (Lansia), Digital Nomad KITAS. "
            "We select the correct category for your exact situation — "
            "a wrong KITAS type leads to detention and two-year blacklisting.",
            "body",
        ),
        _sp(6),
        _p("KITAP — Permanent Stay", "h3"),
        _p(
            "After 5 consecutive years of valid KITAS, you qualify for KITAP. "
            "We track your eligibility date and initiate the process automatically.",
            "body",
        ),
    ]

    right_content: list[Flowable] = [
        _sp(4),
        KeyValueCard([
            ("Processing", "2–5 weeks"),
            ("Validity",   "1–2 years"),
            ("Multi-entry", "Yes"),
            ("Sponsor req.", "PT PMA"),
        ], accent=INDIGO),
        _sp(10),
        _badge_row([
            GuardrailBadge("AI-verified", GREEN, 54 * mm),
            GuardrailBadge("Regulation-grounded", GREEN, 70 * mm),
        ], col_width=76 * mm),
    ]

    story.append(_two_col(
        Table([[f] for f in left_content], colWidths=[92 * mm]),
        Table([[f] for f in right_content], colWidths=[63 * mm]),
    ))

    story += [
        _sp(12),
        _p("Common Visa Pathways", "h3"),
        _comparison_table(
            [
                ["Visa Type",    "Timeline",   "Key Requirement",    "Starting From"],
                ["VOA",          "On arrival", "Eligible passport",  "IDR 500K"],
                ["B211A",        "1 week",     "Any nationality",    "IDR 3.5M"],
                ["KITAS Invest", "3–5 weeks",  "PT PMA + min. cap.", "IDR 8.5M"],
                ["KITAS Employ", "3–4 weeks",  "Work permit (IMTA)", "IDR 9.5M"],
                ["KITAP",        "4–6 weeks",  "5 yrs KITAS",        "IDR 12M"],
            ],
            [48 * mm, 26 * mm, 46 * mm, 35 * mm],
        ),
    ]


def _page_business(story: list) -> None:
    """Page 4: Safety — "They have done this before" """
    story += [
        AccentDivider(color=TERRA),
        _p("Business Setup", "h1"),
        _p("PT PMA, CV, Yayasan — the right structure for your goals", "h2"),
        _sp(6),
        _p(
            "The wrong business structure in Indonesia is not just inconvenient — it can "
            "freeze your bank accounts, invalidate your licenses, or expose you to personal "
            "liability. We match your activity to the correct structure before we file anything.",
            "body",
        ),
        _sp(8),
    ]

    cards = [
        ServiceCard("PT PMA (Foreign-Owned)",
                    ["100% foreign ownership", "Requires IDR 10B capital",
                     "Full operational rights"],
                    accent=TERRA),
        ServiceCard("CV (Local Partnership)",
                    ["Lower capital requirements", "Requires Indonesian partner",
                     "Suitable for small operations"],
                    accent=GOLD),
        ServiceCard("Yayasan (Foundation)",
                    ["Non-profit structure", "Educational / social activities",
                     "No shareholder profits"],
                    accent=INDIGO),
        ServiceCard("Representative Office",
                    ["No commercial activity", "Market research & liaison",
                     "Bridge to full PT PMA"],
                    accent=MUTED),
    ]

    cards_row1 = Table([[cards[0], cards[1]]],
                       colWidths=[77 * mm, 77 * mm])
    cards_row1.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    cards_row2 = Table([[cards[2], cards[3]]],
                       colWidths=[77 * mm, 77 * mm])
    cards_row2.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    story += [cards_row1, _sp(6), cards_row2, _sp(12)]

    story += [
        _p("PT PMA Setup — What We Handle", "h3"),
        _comparison_table(
            [
                ["Step", "What We Do",                               "Timeline"],
                ["01",   "KBLI selection + business plan review",    "Day 1–2"],
                ["02",   "NIB registration (OSS-RBA system)",        "Day 3–5"],
                ["03",   "Notarial deed + Ministry of Law approval", "Week 2"],
                ["04",   "NPWP + DJP tax registration",             "Week 3"],
                ["05",   "Bank account + operational permits",       "Week 4–6"],
            ],
            [12 * mm, 100 * mm, 43 * mm],
        ),
        _sp(8),
        _p(
            "All KBLI codes verified against the 2025 KBLI classification database. "
            "Wrong KBLI selection is the #1 cause of PT PMA license rejection.",
            "body_muted",
        ),
    ]


def _page_tax(story: list) -> None:
    """Page 5: Informed Confidence — "Nothing will surprise me" """
    story += [
        AccentDivider(color=GOLD),
        _p("Tax &amp; Compliance", "h1"),
        _p("Indonesia's tax regime — end-to-end management", "h2"),
        _sp(6),
    ]

    left_content: list[Flowable] = [
        _p("Monthly Obligations", "h3"),
        _p(
            "<b>PPh 21</b> (employee income tax), <b>PPh 23</b> (withholding on services), "
            "<b>PPN</b> (VAT, 12% from Jan 2025) — due by the 15th or end of each month.",
            "body",
        ),
        _sp(6),
        _p("Annual Obligations", "h3"),
        _p(
            "<b>PPh Badan</b> (corporate income tax, 22%), <b>SPT Tahunan</b> (annual tax "
            "return, due end of March), transfer pricing documentation for related-party "
            "transactions.",
            "body",
        ),
        _sp(6),
        _p("LKPM Reporting", "h3"),
        _p(
            "Quarterly investment activity reports to BKPM. Missing a LKPM filing "
            "triggers automatic PT PMA suspension — the fine exceeds a full year of "
            "our compliance service fee.",
            "body",
        ),
    ]

    right_content: list[Flowable] = [
        _sp(4),
        KeyValueCard([
            ("PPN Rate",    "12% (Jan 2025)"),
            ("PPh Badan",  "22% standard"),
            ("PPh 21",     "5–35% prog."),
            ("LKPM",       "Quarterly"),
            ("SPT Due",    "End of March"),
        ], accent=GOLD),
    ]

    story.append(_two_col(
        Table([[f] for f in left_content], colWidths=[92 * mm]),
        Table([[f] for f in right_content], colWidths=[63 * mm]),
    ))

    story += [
        _sp(12),
        _p("Compliance Calendar — Key Deadlines", "h3"),
        _comparison_table(
            [
                ["Obligation",   "Frequency",  "Deadline",     "Penalty for Late"],
                ["PPh 21",       "Monthly",    "15th",         "2% per month"],
                ["PPN",          "Monthly",    "End of month", "2% per month"],
                ["LKPM",         "Quarterly",  "End of Q",     "PT PMA suspension"],
                ["SPT Tahunan",  "Annual",     "End of March", "IDR 1M flat"],
                ["PPh Badan",    "Annual",     "End of April", "2% per month"],
            ],
            [47 * mm, 27 * mm, 33 * mm, 48 * mm],
        ),
        _sp(8),
        _badge_row([
            GuardrailBadge("Updated for UU 20/2025", GREEN, 65 * mm),
            GuardrailBadge("AI-verified rates", GREEN, 56 * mm),
            GuardrailBadge("PMK-grounded", GOLD, 48 * mm),
        ], col_width=60 * mm),
    ]


def _page_how_we_work(story: list) -> None:
    """Page 6: Belonging — "This system was built for people like me" """
    story += [
        AccentDivider(color=GREEN),
        _p("How We Work", "h1"),
        _p("Deterministic AI with human guardrails", "h2"),
        _sp(4),
        _p(
            "Zantara, our AI assistant, is built on a knowledge graph of 56,000+ verified "
            "regulatory nodes and 93,000+ sourced documents. Think of it as the difference "
            "between a calculator and a mathematician: the AI handles computation, "
            "the humans handle judgment.",
            "body",
        ),
        _sp(10),
        ProcessStep(1, "You Ask",
                    "Via WhatsApp, Telegram, Web Chat — in your language"),
        ProcessStep(2, "RAG Retrieval",
                    "Hybrid search across 93,000+ verified documents and regulations"),
        ProcessStep(3, "Evidence Scoring",
                    "Each answer scored 0–1 against source confidence thresholds"),
        ProcessStep(4, "Guardrail Check",
                    "Low-confidence answers escalated to human specialists immediately"),
        ProcessStep(5, "Verified Response",
                    "Cited answer delivered — source document referenced, never invented",
                    is_last=True),
        _sp(12),
        _p("What Our AI Does vs. What Humans Do", "h3"),
        _comparison_table(
            [
                ["Deterministic System (AI)",     "Human Intelligence (Advisors)"],
                ["Prices from verified database", "Strategy and judgment"],
                ["Deadlines from legal calendar", "Client relationships"],
                ["Docs from official registries", "Complex negotiations"],
                ["Status tracking &amp; alerts",  "Problem solving &amp; advocacy"],
            ],
            [82 * mm, 73 * mm],
        ),
        _sp(10),
        _badge_row([
            GuardrailBadge("Never invents a price", GREEN, 64 * mm),
            GuardrailBadge("Regulation-grounded", GREEN, 60 * mm),
            GuardrailBadge("Human escalation path", GOLD, 64 * mm),
        ], col_width=64 * mm),
        _sp(6),
        _p(
            "Evidence threshold: 0.60. Scores below 0.15 → system refuses to answer. "
            "Scores 0.15–0.60 → cautious answer with explicit uncertainty disclaimer. "
            "Above 0.60 → confident cited answer.",
            "body_muted",
        ),
    ]


def _page_contact(story: list) -> None:
    """Page 7: Readiness — "I know exactly what to do next" """

    class ContactContent(Flowable):
        def __init__(self) -> None:
            super().__init__()
            self.width = 165 * mm
            self.height = 200 * mm

        def draw(self) -> None:
            c = self.canv
            cx = self.width / 2
            y = self.height

            # Logo
            if LOGO_READER:
                logo_size = 56
                c.drawImage(LOGO_READER, cx - logo_size / 2, y - 75,
                            logo_size, logo_size, mask="auto")

            # "Ready to Start?"
            c.setFillColor(TEXT)
            c.setFont(DF, 30)
            c.drawCentredString(cx, y - 98, "Ready to Start?")

            # Accent rule
            c.setStrokeColor(TERRA)
            c.setLineWidth(1.2)
            c.line(cx - 55, y - 108, cx + 55, y - 108)

            # Subtext
            c.setFillColor(MUTED)
            c.setFont(BF, 11)
            c.drawCentredString(cx, y - 122,
                                "Talk to Zantara, our AI assistant, or book a free consultation.")

            # Contact cards
            contacts = [
                ("WhatsApp", "wa.me/6281338051876", TERRA),
                ("Telegram", "@balizerobot", GOLD),
                ("Web Chat", "balizero.com/chat", INDIGO),
            ]
            card_w = 46 * mm
            gap = 5
            total = len(contacts) * card_w + (len(contacts) - 1) * gap
            start_x = cx - total / 2

            for i, (ch, val, accent) in enumerate(contacts):
                x = start_x + i * (card_w + gap)
                y_card = y - 178
                card_h = 34
                c.setFillColor(CARD_BG)
                c.roundRect(x, y_card, card_w, card_h, 5, fill=1, stroke=0)
                c.setFillColor(accent)
                c.roundRect(x, y_card + card_h - 2.5, card_w, 2.5, 5, fill=1, stroke=0)
                c.setFillColor(accent)
                c.setFont("Helvetica-Bold", 8)
                c.drawCentredString(x + card_w / 2, y_card + 20, ch)
                c.setFillColor(TEXT)
                c.setFont(BF, 7.5)
                c.drawCentredString(x + card_w / 2, y_card + 8, val)

            # Address
            c.setFillColor(MUTED)
            c.setFont(BF, 9)
            c.drawCentredString(cx, y - 195, "Jl. Raya Canggu, Kuta Utara, Bali 80361")

            # Response time
            c.setFillColor(FAINT)
            c.setFont("Helvetica", 7.5)
            c.drawCentredString(cx, y - 206, "We reply within 2 business hours · Mon–Sat 09:00–18:00 WITA")

    story.append(ContactContent())

    story += [
        _sp(12),
        AccentDivider(color=GOLD, thickness=1),
        _sp(8),
        _p(
            "5,000+ clients served across 40+ nationalities since 2014. "
            "Italian · English · Russian · Ukrainian · Indonesian.",
            "body_muted",
        ),
        _sp(4),
        _p(
            "PT Zero Intelligence Indonesia  ·  PT PMA  ·  KBLI 62090  ·  "
            "© 2026 Bali Zero. All rights reserved.",
            "caption",
        ),
    ]


# ─────────────────────────────────────────────────────────
# MAIN BUILD
# ─────────────────────────────────────────────────────────

def build_brochure() -> None:
    # Frames
    cover_frame   = Frame(MARGIN, MARGIN, W - 2 * MARGIN, H - 2 * MARGIN,
                          id="cover", showBoundary=0)
    content_frame = Frame(25 * mm, 22 * mm, W - 25 * mm - MARGIN, H - 42 * mm,
                          id="content", showBoundary=0)

    templates = [
        PageTemplate(id="cover",   frames=[cover_frame],   onPage=_make_cover_bg),
        PageTemplate(id="who",     frames=[content_frame], onPage=_make_content_bg("who")),
        PageTemplate(id="imm",     frames=[content_frame], onPage=_make_content_bg("imm")),
        PageTemplate(id="biz",     frames=[content_frame], onPage=_make_content_bg("biz")),
        PageTemplate(id="tax",     frames=[content_frame], onPage=_make_content_bg("tax")),
        PageTemplate(id="how",     frames=[content_frame], onPage=_make_content_bg("how")),
        PageTemplate(id="contact", frames=[content_frame], onPage=_make_content_bg("contact")),
    ]

    doc = BaseDocTemplate(
        str(OUTPUT_PATH),
        pagesize=A4,
        pageTemplates=templates,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    story: list[Flowable] = []

    # Page 1: Cover
    _page_cover(story)

    # Page 2: Who We Are
    story += [NextPageTemplate("who"), PageBreak()]
    _page_who_we_are(story)

    # Page 3: Immigration
    story += [NextPageTemplate("imm"), PageBreak()]
    _page_immigration(story)

    # Page 4: Business Setup
    story += [NextPageTemplate("biz"), PageBreak()]
    _page_business(story)

    # Page 5: Tax & Compliance
    story += [NextPageTemplate("tax"), PageBreak()]
    _page_tax(story)

    # Page 6: How We Work
    story += [NextPageTemplate("how"), PageBreak()]
    _page_how_we_work(story)

    # Page 7: Contact
    story += [NextPageTemplate("contact"), PageBreak()]
    _page_contact(story)

    doc.build(story)
    size_kb = OUTPUT_PATH.stat().st_size // 1024
    print(f"✅ Brochure generated: {OUTPUT_PATH}")
    print(f"   Size: {size_kb} KB | Pages: 7")
    print(f"   Logo: {'embedded (RGBA)' if LOGO_READER else 'NOT FOUND'}")


if __name__ == "__main__":
    build_brochure()
