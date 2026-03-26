"""
Bali Zero — Company Brochure PDF Generator
==========================================
One-time script. Run when services/prices change.
Output: data/assets/brochure_balizero_en.pdf

Usage:
    cd apps/backend-rag
    python scripts/generate_brochure.py

Psychological arc (DeepSeek synthesis):
    Page 1 (Cover)        → Relief: "You are in the right place"
    Page 2 (Who We Are)   → Orientation: "Here is what we are"
    Page 3 (Immigration)  → Impressed Confidence: "They know this cold"
    Page 4 (Business)     → Safety: "They have done this before"
    Page 5 (Tax)          → Informed Confidence: "Nothing will surprise me"
    Page 6 (How We Work)  → Belonging: "This system was built for people like me"
    Page 7 (Contact)      → Readiness: "I know exactly what to do next"
"""

from __future__ import annotations

import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageTemplate,
    Paragraph,
    Spacer,
)

# ─────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent.parent.parent  # monorepo root
BACKEND_ROOT = Path(__file__).parent.parent  # apps/backend-rag
OUTPUT_PATH = BACKEND_ROOT / "data" / "assets" / "brochure_balizero_en.pdf"
LOGO_PATH = REPO_ROOT / "apps" / "mouth" / "public" / "static" / "balizero-logo-clean.png"

# ─────────────────────────────────────────────────────────
# BRAND PALETTE
# ─────────────────────────────────────────────────────────
BASE = colors.HexColor("#0c0c0e")        # near-black background
TERRACOTTA = colors.HexColor("#d4845a")  # primary accent — warmth, action
GOLD = colors.HexColor("#c9a96e")        # secondary accent — trust, precision
TEXT = colors.HexColor("#edeae4")        # warm off-white — body text
SUBTLE = colors.HexColor("#3a3a40")      # cards, dividers — dark grey
MUTED = colors.HexColor("#9e9b95")       # secondary text — captions

# ─────────────────────────────────────────────────────────
# PAGE DIMENSIONS
# ─────────────────────────────────────────────────────────
W, H = A4  # 595 x 842 pts
MARGIN = 2.0 * cm
CONTENT_W = W - 2 * MARGIN


# ─────────────────────────────────────────────────────────
# CANVAS HELPERS
# ─────────────────────────────────────────────────────────

def fill_background(c: canvas.Canvas, color: colors.Color = BASE) -> None:
    c.setFillColor(color)
    c.rect(0, 0, W, H, fill=1, stroke=0)


def draw_horizontal_rule(c: canvas.Canvas, y: float, color: colors.Color = SUBTLE, width: float = CONTENT_W) -> None:
    c.setStrokeColor(color)
    c.setLineWidth(0.5)
    c.line(MARGIN, y, MARGIN + width, y)


def draw_accent_bar(c: canvas.Canvas, y: float, height: float = 3, color: colors.Color = TERRACOTTA) -> None:
    c.setFillColor(color)
    c.rect(MARGIN, y, 40, height, fill=1, stroke=0)


def draw_card(
    c: canvas.Canvas,
    x: float, y: float,
    w: float, h: float,
    color: colors.Color = SUBTLE,
    radius: float = 4,
) -> None:
    c.setFillColor(color)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=0)


def draw_text(
    c: canvas.Canvas,
    text: str,
    x: float, y: float,
    font: str = "Helvetica",
    size: float = 10,
    color: colors.Color = TEXT,
    align: str = "left",
) -> None:
    c.setFont(font, size)
    c.setFillColor(color)
    if align == "center":
        c.drawCentredString(x, y, text)
    elif align == "right":
        c.drawRightString(x, y, text)
    else:
        c.drawString(x, y, text)


def draw_wrapped_text(
    c: canvas.Canvas,
    text: str,
    x: float, y: float,
    max_width: float,
    font: str = "Helvetica",
    size: float = 10,
    color: colors.Color = TEXT,
    line_height: float = 14,
) -> float:
    """Draw wrapped text, returns final y position."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        if stringWidth(test_line, font, size) <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)

    c.setFont(font, size)
    c.setFillColor(color)
    for line in lines:
        c.drawString(x, y, line)
        y -= line_height

    return y


def draw_bullet_item(
    c: canvas.Canvas,
    text: str,
    x: float, y: float,
    max_width: float,
    bullet_color: colors.Color = TERRACOTTA,
    text_color: colors.Color = TEXT,
    font: str = "Helvetica",
    size: float = 9.5,
) -> float:
    bullet_x = x
    text_x = x + 12
    # Bullet dot
    c.setFillColor(bullet_color)
    c.circle(bullet_x + 3, y + 3, 2, fill=1, stroke=0)
    # Text
    y = draw_wrapped_text(c, text, text_x, y, max_width - 12, font, size, text_color, line_height=13)
    return y - 3


def draw_stat_block(c: canvas.Canvas, value: str, label: str, x: float, y: float, w: float) -> None:
    draw_text(c, value, x + w / 2, y + 16, "Helvetica-Bold", 22, TERRACOTTA, "center")
    draw_text(c, label, x + w / 2, y, "Helvetica", 8, MUTED, "center")


# ─────────────────────────────────────────────────────────
# PAGE 1 — COVER
# Emotion: RELIEF — "You are in the right place"
# ─────────────────────────────────────────────────────────

def page_cover(c: canvas.Canvas) -> None:
    c.showPage()
    fill_background(c)

    # Subtle geometric accent — top right quadrant
    c.setFillColor(colors.HexColor("#1a1a1f"))
    c.rect(W * 0.55, H * 0.45, W * 0.5, H * 0.6, fill=1, stroke=0)

    # Thin terracotta vertical line (left side, architectural)
    c.setFillColor(TERRACOTTA)
    c.rect(MARGIN - 8, MARGIN, 2, H - 2 * MARGIN, fill=1, stroke=0)

    # Logo — centered upper third
    logo_y = H * 0.62
    logo_size = 90
    if LOGO_PATH.exists():
        logo_x = W / 2 - logo_size / 2
        c.drawImage(str(LOGO_PATH), logo_x, logo_y, logo_size, logo_size, preserveAspectRatio=True, mask="auto")
    else:
        draw_text(c, "BALI ZERO", W / 2, logo_y + 30, "Helvetica-Bold", 28, TEXT, "center")

    # Tagline — below logo
    draw_text(c, "Guided by humans.", W / 2, H * 0.58, "Helvetica", 15, TEXT, "center")
    draw_text(c, "Powered by AI.", W / 2, H * 0.55, "Helvetica-Oblique", 15, TERRACOTTA, "center")

    # Separator line
    sep_y = H * 0.50
    c.setStrokeColor(SUBTLE)
    c.setLineWidth(0.5)
    c.line(W * 0.3, sep_y, W * 0.7, sep_y)

    # Core promise — the emotional anchor
    draw_text(c, "You will never be in the dark.", W / 2, H * 0.45, "Helvetica-BoldOblique", 12, GOLD, "center")

    # Three service pillars — compact icons row
    pillars = [
        ("Immigration", "Visas & Permits"),
        ("Business", "PT PMA & Setup"),
        ("Tax & Property", "Compliance & Land"),
    ]
    pill_y = H * 0.34
    col_w = CONTENT_W / 3
    for i, (title, sub) in enumerate(pillars):
        cx = MARGIN + col_w * i + col_w / 2
        draw_card(c, MARGIN + col_w * i + 5, pill_y - 10, col_w - 10, 44, SUBTLE)
        draw_text(c, title, cx, pill_y + 22, "Helvetica-Bold", 8.5, TERRACOTTA, "center")
        draw_text(c, sub, cx, pill_y + 9, "Helvetica", 7.5, MUTED, "center")

    # Stats row
    stats_y = H * 0.20
    stats = [
        ("5,000+", "clients served"),
        ("10+ yrs", "in Bali"),
        ("4 domains", "one team"),
    ]
    stat_w = CONTENT_W / 3
    for i, (val, lbl) in enumerate(stats):
        sx = MARGIN + stat_w * i
        draw_stat_block(c, val, lbl, sx, stats_y, stat_w)

    # Footer
    draw_text(c, "Canggu, Bali  ·  balizero.com  ·  zantara@balizero.com", W / 2, MARGIN - 5, "Helvetica", 7.5, MUTED, "center")


# ─────────────────────────────────────────────────────────
# PAGE 2 — WHO WE ARE
# Emotion: ORIENTATION — "I know who I'm dealing with"
# ─────────────────────────────────────────────────────────

def page_who_we_are(c: canvas.Canvas) -> None:
    c.showPage()
    fill_background(c)

    y = H - MARGIN

    # Section label
    draw_text(c, "WHO WE ARE", MARGIN, y, "Helvetica", 8, TERRACOTTA)
    y -= 20

    # Headline
    draw_text(c, "Born traditional.", MARGIN, y, "Helvetica-Bold", 24, TEXT)
    y -= 30
    draw_text(c, "Rebuilt as something new.", MARGIN, y, "Helvetica-Bold", 24, GOLD)
    y -= 20

    draw_accent_bar(c, y)
    y -= 20

    # Story paragraph — 3 blocks
    story_lines = [
        "Bali Zero was founded as a traditional consulting firm — a team of lawyers, immigration specialists, and tax advisors operating from Canggu.",
        "Over the past decade, we evolved. We built specialized AI agents to handle the parts of our work that never needed human judgment: price lookups, document checklists, deadline tracking, legal database searches.",
        "Today, our clients get both: human experts who know Bali and human nature, supported by AI that never forgets a regulation, never misquotes a price, and never misses a deadline.",
    ]
    for para in story_lines:
        y = draw_wrapped_text(c, para, MARGIN, y, CONTENT_W, size=10, line_height=15)
        y -= 8

    y -= 10
    draw_horizontal_rule(c, y)
    y -= 20

    # The key distinction — 2-column card layout
    draw_text(c, "Our model in plain terms", MARGIN, y, "Helvetica-Bold", 11, TEXT)
    y -= 18

    col_w = (CONTENT_W - 12) / 2
    cards = [
        (SUBTLE, "AI does the deterministic work", [
            "Prices from a verified internal database",
            "Deadlines from a live legal calendar",
            "Documents from official registries",
            "Status tracking and automated alerts",
        ]),
        (colors.HexColor("#1e1e24"), "Humans do the intelligent work", [
            "Strategy and commercial judgment",
            "Client relationships and trust",
            "Complex negotiations",
            "Edge cases and problem solving",
        ]),
    ]

    card_h = 130
    for i, (bg, title, items) in enumerate(cards):
        cx = MARGIN + i * (col_w + 12)
        draw_card(c, cx, y - card_h, col_w, card_h, bg, radius=5)
        draw_text(c, title, cx + 10, y - 14, "Helvetica-Bold", 9, GOLD if i == 0 else TERRACOTTA)
        iy = y - 30
        for item in items:
            draw_bullet_item(c, item, cx + 10, iy, col_w - 20, size=8.5)
            iy -= 15

    y -= card_h + 20

    # Why this matters — single line callout
    draw_card(c, MARGIN, y - 28, CONTENT_W, 36, colors.HexColor("#1a1a1f"), radius=4)
    draw_text(
        c,
        '"AI is not our brand. Reliability is. AI just makes reliability possible at scale."',
        MARGIN + 12, y - 10, "Helvetica-Oblique", 9.5, GOLD,
    )
    y -= 50

    # Founding numbers
    draw_text(c, "By the numbers", MARGIN, y, "Helvetica-Bold", 10, TEXT)
    y -= 15
    facts = [
        ("5,000+", "clients across 60+ nationalities"),
        ("4", "service domains: immigration, company, tax, property"),
        ("10+", "years operating in Bali"),
        ("15+", "AI agents trained on Indonesian law"),
    ]
    for val, label in facts:
        draw_text(c, val, MARGIN, y, "Helvetica-Bold", 11, TERRACOTTA)
        draw_text(c, label, MARGIN + 45, y, "Helvetica", 9.5, TEXT)
        y -= 16

    # Footer
    draw_text(c, "balizero.com", W - MARGIN, MARGIN - 5, "Helvetica", 7, MUTED, "right")


# ─────────────────────────────────────────────────────────
# PAGE 3 — IMMIGRATION
# Emotion: IMPRESSED CONFIDENCE — "They know this cold"
# ─────────────────────────────────────────────────────────

def page_immigration(c: canvas.Canvas) -> None:
    c.showPage()
    fill_background(c)

    y = H - MARGIN
    draw_text(c, "IMMIGRATION", MARGIN, y, "Helvetica", 8, TERRACOTTA)
    y -= 20

    draw_text(c, "Living in Bali,", MARGIN, y, "Helvetica-Bold", 22, TEXT)
    y -= 28
    draw_text(c, "done right.", MARGIN, y, "Helvetica-Bold", 22, GOLD)
    y -= 16
    draw_accent_bar(c, y)
    y -= 18

    intro = "Indonesian immigration law changes frequently. Our system monitors every regulatory update and surfaces the impact on your case in real time. You don't need to follow the news — we do that for you."
    y = draw_wrapped_text(c, intro, MARGIN, y, CONTENT_W, size=10, line_height=14)
    y -= 15

    # Services grid — 2 columns
    services = [
        ("Social Visa (B211A)", "Up to 180 days. Extendable. Perfect for first-time arrivals exploring options."),
        ("KITAS — Work Permit", "Stay and work legally. Sponsored by employer or PT PMA company."),
        ("KITAS — Investor", "For PT PMA directors and shareholders. Renewable annually."),
        ("KITAS — Retirement", "For those 55+. Passive income from abroad. No local work permitted."),
        ("KITAP (Permanent Stay)", "After 5 years on KITAS. The most stable long-term option."),
        ("KITAS — Second Home Visa", "5 or 10-year visa. Requires Rp 2B or Rp 5B in Indonesian bank."),
    ]

    col_w = (CONTENT_W - 10) / 2
    card_h = 60
    gap = 8
    col_y = y
    for i, (title, desc) in enumerate(services):
        col = i % 2
        row = i // 2
        sx = MARGIN + col * (col_w + 10)
        sy = col_y - row * (card_h + gap)
        draw_card(c, sx, sy - card_h, col_w, card_h, SUBTLE, radius=4)
        draw_text(c, title, sx + 10, sy - 14, "Helvetica-Bold", 9, GOLD)
        draw_wrapped_text(c, desc, sx + 10, sy - 28, col_w - 20, size=8.5, color=MUTED, line_height=12)

    y = col_y - (3 * (card_h + gap)) - 15

    draw_horizontal_rule(c, y)
    y -= 18

    # Process — compact 4 steps
    draw_text(c, "How a typical KITAS application works", MARGIN, y, "Helvetica-Bold", 10, TEXT)
    y -= 16

    steps = [
        ("01", "Documents", "Passport + photos + sponsor letter"),
        ("02", "Sponsor", "PT PMA or employer files IMTA"),
        ("03", "Telex", "Immigration issues approval telex"),
        ("04", "KITAS", "Biometrics + card issued in-country"),
    ]
    step_w = CONTENT_W / 4
    for i, (num, title, sub) in enumerate(steps):
        sx = MARGIN + i * step_w
        draw_text(c, num, sx + step_w / 2, y - 2, "Helvetica-Bold", 18, SUBTLE, "center")
        draw_text(c, title, sx + step_w / 2, y - 18, "Helvetica-Bold", 9, TERRACOTTA, "center")
        draw_wrapped_text(c, sub, sx + 4, y - 32, step_w - 8, size=7.5, color=MUTED, line_height=11)
        if i < 3:
            c.setStrokeColor(SUBTLE)
            c.setLineWidth(0.5)
            c.line(sx + step_w - 4, y - 12, sx + step_w + 4, y - 12)

    draw_text(c, "balizero.com", W - MARGIN, MARGIN - 5, "Helvetica", 7, MUTED, "right")


# ─────────────────────────────────────────────────────────
# PAGE 4 — BUSINESS SETUP
# Emotion: SAFETY — "They have done this before, many times"
# ─────────────────────────────────────────────────────────

def page_business(c: canvas.Canvas) -> None:
    c.showPage()
    fill_background(c)

    y = H - MARGIN
    draw_text(c, "BUSINESS SETUP", MARGIN, y, "Helvetica", 8, TERRACOTTA)
    y -= 20

    draw_text(c, "Your company in Indonesia,", MARGIN, y, "Helvetica-Bold", 20, TEXT)
    y -= 26
    draw_text(c, "without the guesswork.", MARGIN, y, "Helvetica-Bold", 20, GOLD)
    y -= 16
    draw_accent_bar(c, y)
    y -= 18

    intro = "Setting up a business in Indonesia involves regulatory steps that are precise, sequential, and non-negotiable. We handle every one of them — and we have done it thousands of times."
    y = draw_wrapped_text(c, intro, MARGIN, y, CONTENT_W, size=10, line_height=14)
    y -= 15

    # PT PMA highlight box
    draw_card(c, MARGIN, y - 90, CONTENT_W, 90, colors.HexColor("#1c1c22"), radius=5)
    draw_text(c, "PT PMA — Foreign-Owned Company", MARGIN + 12, y - 14, "Helvetica-Bold", 11, GOLD)
    pma_text = "The standard structure for foreigners doing business in Indonesia. Full foreign ownership allowed in most sectors. Minimum capital requirements vary by business sector (typically Rp 10 billion investment plan)."
    draw_wrapped_text(c, pma_text, MARGIN + 12, y - 30, CONTENT_W - 24, size=9, color=TEXT, line_height=13)
    # Mini stat row inside card
    pma_stats = [("~3 months", "registration time"), ("100%", "foreign ownership (most sectors)"), ("Rp 10B", "min investment plan")]
    for i, (val, lbl) in enumerate(pma_stats):
        sx = MARGIN + 12 + i * ((CONTENT_W - 24) / 3)
        draw_text(c, val, sx, y - 66, "Helvetica-Bold", 11, TERRACOTTA)
        draw_text(c, lbl, sx, y - 79, "Helvetica", 7.5, MUTED)

    y -= 105

    # Other structures — 3 smaller cards
    structs = [
        ("CV (Commanditaire Vennootschap)", "For domestic businesses. Not available to foreigners as primary shareholder."),
        ("Representative Office (KPPA)", "Allowed for market research and promotion only. Cannot generate revenue in Indonesia."),
        ("Virtual Office", "Registered address + meeting rooms. Required for PT PMA during setup. Fully compliant."),
    ]
    struct_w = (CONTENT_W - 16) / 3
    struct_h = 80
    for i, (title, desc) in enumerate(structs):
        sx = MARGIN + i * (struct_w + 8)
        draw_card(c, sx, y - struct_h, struct_w, struct_h, SUBTLE, radius=4)
        draw_wrapped_text(c, title, sx + 8, y - 12, struct_w - 16, "Helvetica-Bold", 8.5, TERRACOTTA, line_height=12)
        draw_wrapped_text(c, desc, sx + 8, y - 38, struct_w - 16, size=8, color=MUTED, line_height=11)

    y -= struct_h + 15
    draw_horizontal_rule(c, y)
    y -= 18

    # What's included
    draw_text(c, "What we handle for you", MARGIN, y, "Helvetica-Bold", 10, TEXT)
    y -= 14
    included = [
        "KBLI code selection and regulatory pre-check",
        "NIB (Business Identification Number) via OSS",
        "AHU registration with Ministry of Law and Human Rights",
        "NPWP (tax number) registration",
        "Bank account opening support",
        "Virtual office arrangement (if needed)",
        "LKPM quarterly investment reporting",
        "OSS licensing and sector-specific permits",
    ]
    col_h = len(included) // 2
    for i, item in enumerate(included):
        col = i // col_h
        row = i % col_h
        ix = MARGIN + col * (CONTENT_W / 2)
        iy = y - row * 14
        draw_bullet_item(c, item, ix, iy, CONTENT_W / 2 - 10, size=8.5)

    draw_text(c, "balizero.com", W - MARGIN, MARGIN - 5, "Helvetica", 7, MUTED, "right")


# ─────────────────────────────────────────────────────────
# PAGE 5 — TAX & COMPLIANCE
# Emotion: INFORMED CONFIDENCE — "Nothing will surprise me"
# ─────────────────────────────────────────────────────────

def page_tax(c: canvas.Canvas) -> None:
    c.showPage()
    fill_background(c)

    y = H - MARGIN
    draw_text(c, "TAX & COMPLIANCE", MARGIN, y, "Helvetica", 8, TERRACOTTA)
    y -= 20

    draw_text(c, "No surprises.", MARGIN, y, "Helvetica-Bold", 22, TEXT)
    y -= 28
    draw_text(c, "No missed deadlines.", MARGIN, y, "Helvetica-Bold", 22, GOLD)
    y -= 16
    draw_accent_bar(c, y)
    y -= 18

    intro = "Indonesian tax law is precise and unforgiving on deadlines. Our compliance calendar tracks every obligation for every client — SPT, LKPM, VAT, withholding — and sends alerts before penalties become relevant."
    y = draw_wrapped_text(c, intro, MARGIN, y, CONTENT_W, size=10, line_height=14)
    y -= 15

    # Services — 2 columns
    tax_services = [
        ("NPWP Registration", "Individual or corporate tax ID. Required for employment, banking, and most government services."),
        ("Annual Tax Return (SPT)", "Individual and corporate SPT filing. We prepare and submit — you approve."),
        ("VAT Registration & Reporting", "For businesses exceeding Rp 4.8B annual revenue. Monthly VAT returns."),
        ("Withholding Tax (PPh 21/23/26)", "Payroll tax, service fee withholding, and royalty tax management."),
        ("LKPM Investment Reporting", "Quarterly investment reports required for all PT PMA companies."),
        ("Tax Residency Advisory", "DTA treaty analysis and residency planning for expatriates."),
    ]

    col_w = (CONTENT_W - 10) / 2
    card_h = 65
    gap = 8
    base_y = y
    for i, (title, desc) in enumerate(tax_services):
        col = i % 2
        row = i // 2
        sx = MARGIN + col * (col_w + 10)
        sy = base_y - row * (card_h + gap)
        draw_card(c, sx, sy - card_h, col_w, card_h, SUBTLE, radius=4)
        draw_text(c, title, sx + 10, sy - 14, "Helvetica-Bold", 9, GOLD)
        draw_wrapped_text(c, desc, sx + 10, sy - 28, col_w - 20, size=8.5, color=MUTED, line_height=12)

    y = base_y - 3 * (card_h + gap) - 10

    draw_horizontal_rule(c, y)
    y -= 18

    # Compliance calendar highlight
    draw_card(c, MARGIN, y - 70, CONTENT_W, 70, colors.HexColor("#1a1a1f"), radius=5)
    draw_text(c, "Compliance Calendar — always on", MARGIN + 12, y - 14, "Helvetica-Bold", 10, GOLD)
    cal_text = "Every PT PMA and KITAS client has a live compliance timeline in our system. 30 days before any deadline, you receive a WhatsApp and email alert. Penalties for late LKPM or SPT filing can be significant — our system exists so you never discover them retrospectively."
    draw_wrapped_text(c, cal_text, MARGIN + 12, y - 28, CONTENT_W - 24, size=8.5, color=TEXT, line_height=13)

    draw_text(c, "balizero.com", W - MARGIN, MARGIN - 5, "Helvetica", 7, MUTED, "right")


# ─────────────────────────────────────────────────────────
# PAGE 6 — HOW WE WORK
# Emotion: BELONGING — "This system was built for people like me"
# ─────────────────────────────────────────────────────────

def page_how_we_work(c: canvas.Canvas) -> None:
    c.showPage()
    fill_background(c)

    y = H - MARGIN
    draw_text(c, "HOW WE WORK", MARGIN, y, "Helvetica", 8, TERRACOTTA)
    y -= 20

    draw_text(c, "A system built on", MARGIN, y, "Helvetica-Bold", 21, TEXT)
    y -= 26
    draw_text(c, "rules, not memory.", MARGIN, y, "Helvetica-Bold", 21, GOLD)
    y -= 16
    draw_accent_bar(c, y)
    y -= 18

    intro = "Most consulting firms run on the expertise and memory of individual consultants. If your consultant is on holiday, sick, or leaves the firm, so does your knowledge. We built a different system."
    y = draw_wrapped_text(c, intro, MARGIN, y, CONTENT_W, size=10, line_height=14)
    y -= 15

    # The AI guardrails explanation
    draw_card(c, MARGIN, y - 85, CONTENT_W, 85, colors.HexColor("#1c1c22"), radius=5)
    draw_text(c, "Why our AI doesn't hallucinate", MARGIN + 12, y - 14, "Helvetica-Bold", 10, TERRACOTTA)
    ai_text = (
        "Our AI agents are deterministic by design. When you ask about a visa fee, the agent queries our internal pricing database — not its training data. "
        "When it cites a regulation, it references a versioned legal document, not a statistical prediction. "
        "The AI never invents numbers. It either retrieves a verified answer or tells you: 'this requires human review.'"
    )
    draw_wrapped_text(c, ai_text, MARGIN + 12, y - 30, CONTENT_W - 24, size=9, color=TEXT, line_height=13)
    y -= 100

    # 4-step process
    draw_text(c, "Your client journey", MARGIN, y, "Helvetica-Bold", 10, TEXT)
    y -= 16

    journey_steps = [
        ("Day 0", "Onboarding", "You receive a WhatsApp from your advisor within 2 hours. We confirm your goals and the right structure."),
        ("Day 1–3", "Case Opening", "Your case is opened in our system. You receive a document checklist and a timeline estimate."),
        ("Week 1–4", "Execution", "We handle all government submissions. You track status in real time on your client portal."),
        ("Ongoing", "Compliance", "Automated reminders before every renewal, deadline, or regulatory update that affects you."),
    ]

    step_h = 72
    step_w = (CONTENT_W - 12) / 4
    step_y = y
    for i, (day, title, desc) in enumerate(journey_steps):
        sx = MARGIN + i * (step_w + 4)
        draw_card(c, sx, step_y - step_h, step_w, step_h, SUBTLE, radius=4)
        draw_text(c, day, sx + step_w / 2, step_y - 12, "Helvetica-Bold", 8, TERRACOTTA, "center")
        draw_text(c, title, sx + step_w / 2, step_y - 24, "Helvetica-Bold", 9.5, TEXT, "center")
        draw_wrapped_text(c, desc, sx + 6, step_y - 38, step_w - 12, size=7.5, color=MUTED, line_height=11)
        if i < 3:
            c.setStrokeColor(TERRACOTTA)
            c.setLineWidth(0.7)
            c.line(sx + step_w + 2, step_y - step_h / 2, sx + step_w + 4, step_y - step_h / 2)

    y = step_y - step_h - 18
    draw_horizontal_rule(c, y)
    y -= 18

    # Client portal highlight
    draw_text(c, "Your client portal", MARGIN, y, "Helvetica-Bold", 10, TEXT)
    y -= 14
    portal_items = [
        "Live status of every open case — updated in real time",
        "Document vault — upload once, always accessible",
        "Compliance calendar — renewals and deadlines at a glance",
        "Direct messaging with your advisor",
        "Full timeline and history of every interaction",
    ]
    for item in portal_items:
        y = draw_bullet_item(c, item, MARGIN, y, CONTENT_W, size=9)
        y -= 2

    y -= 8
    draw_card(c, MARGIN, y - 24, CONTENT_W, 24, colors.HexColor("#1a1a1f"), radius=3)
    draw_text(c, "Access your portal at:  my.balizero.com", MARGIN + 12, y - 10, "Helvetica", 9.5, GOLD)

    draw_text(c, "balizero.com", W - MARGIN, MARGIN - 5, "Helvetica", 7, MUTED, "right")


# ─────────────────────────────────────────────────────────
# PAGE 7 — CONTACT
# Emotion: READINESS — "I know exactly what to do next"
# ─────────────────────────────────────────────────────────

def page_contact(c: canvas.Canvas) -> None:
    c.showPage()
    fill_background(c)

    # Full-bleed terracotta strip at top
    c.setFillColor(TERRACOTTA)
    c.rect(0, H - 120, W, 120, fill=1, stroke=0)

    # Headline on colored strip
    draw_text(c, "Ready to start?", W / 2, H - 55, "Helvetica-Bold", 26, BASE, "center")
    draw_text(c, "Your advisor is waiting.", W / 2, H - 80, "Helvetica", 13, colors.HexColor("#2a1a10"), "center")

    y = H - 145

    # Three contact channels — large cards
    channels = [
        ("WhatsApp", "+62 821 3107 363", "Fastest. Reply within 2 hours."),
        ("Email", "zantara@balizero.com", "For documents and formal requests."),
        ("Portal", "my.balizero.com", "Track your case 24/7. Full history."),
    ]
    chan_w = (CONTENT_W - 16) / 3
    chan_h = 80
    for i, (channel, contact, note) in enumerate(channels):
        cx = MARGIN + i * (chan_w + 8)
        draw_card(c, cx, y - chan_h, chan_w, chan_h, SUBTLE, radius=5)
        draw_text(c, channel.upper(), cx + chan_w / 2, y - 16, "Helvetica-Bold", 8, TERRACOTTA, "center")
        draw_text(c, contact, cx + chan_w / 2, y - 34, "Helvetica-Bold", 9, TEXT, "center")
        draw_wrapped_text(c, note, cx + 8, y - 52, chan_w - 16, size=8, color=MUTED, line_height=12)

    y -= chan_h + 20

    draw_horizontal_rule(c, y)
    y -= 20

    # Office info
    draw_text(c, "Bali Zero Office", MARGIN, y, "Helvetica-Bold", 12, TEXT)
    y -= 16
    office_lines = [
        ("Address", "Canggu, Bali, Indonesia"),
        ("Hours", "Monday–Friday, 09:00–18:00 WITA (UTC+8)"),
        ("Languages", "English, Italian, Russian, Ukrainian, Indonesian"),
    ]
    for label, value in office_lines:
        draw_text(c, label, MARGIN, y, "Helvetica-Bold", 9, MUTED)
        draw_text(c, value, MARGIN + 75, y, "Helvetica", 9, TEXT)
        y -= 14

    y -= 10
    draw_horizontal_rule(c, y, GOLD)
    y -= 20

    # Social proof — client quote
    draw_card(c, MARGIN, y - 60, CONTENT_W, 60, colors.HexColor("#1a1a1f"), radius=5)
    draw_text(c, '"', MARGIN + 10, y - 10, "Helvetica-Bold", 28, TERRACOTTA)
    quote_text = "I moved from Italy with zero knowledge of Indonesian bureaucracy. They opened my PT PMA, got my KITAS, and registered me for tax — all in 3 months. I never once felt lost."
    draw_wrapped_text(c, quote_text, MARGIN + 30, y - 14, CONTENT_W - 50, "Helvetica-Oblique", 9, TEXT, 13)
    draw_text(c, "— Marco V., Italian entrepreneur, Canggu", MARGIN + 30, y - 52, "Helvetica", 7.5, MUTED)

    y -= 80

    # Final CTA — bottom of page
    draw_text(c, "Reply to this email to schedule your first consultation.", MARGIN, y, "Helvetica-Bold", 11, GOLD)
    y -= 16
    draw_text(c, "No forms. No waiting room. We'll come to you.", MARGIN, y, "Helvetica", 10, MUTED)

    # Footer bar
    c.setFillColor(colors.HexColor("#111115"))
    c.rect(0, 0, W, 30, fill=1, stroke=0)
    draw_text(c, "Bali Zero · balizero.com · zantara@balizero.com · +62 821 3107 363 · Canggu, Bali", W / 2, 10, "Helvetica", 7, MUTED, "center")


# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────

def generate() -> Path:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(OUTPUT_PATH), pagesize=A4)
    c.setTitle("Bali Zero — Your Guide to Living and Working in Bali")
    c.setAuthor("Bali Zero")
    c.setSubject("Immigration, Business Setup, Tax & Compliance in Indonesia")
    c.setCreator("Bali Zero AI System")

    page_cover(c)
    page_who_we_are(c)
    page_immigration(c)
    page_business(c)
    page_tax(c)
    page_how_we_work(c)
    page_contact(c)

    c.save()

    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"✅ Brochure generated: {OUTPUT_PATH}")
    print(f"   Size: {size_kb:.1f} KB  |  Pages: 7")
    return OUTPUT_PATH


if __name__ == "__main__":
    generate()
