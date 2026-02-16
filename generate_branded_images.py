#!/usr/bin/env python3
"""Generate branded placeholder article covers using Pillow.
Professional gradient + title design matching Bali Zero brand."""

import os
import math
from PIL import Image, ImageDraw, ImageFont

OUTPUT_BASE = "apps/mouth/public/static/insights"
WIDTH, HEIGHT = 1200, 630

# Bali Zero brand colors
BRAND = {
    "primary": (15, 23, 42),      # deep navy
    "accent": (249, 115, 22),     # orange
    "gold": (234, 179, 8),        # gold
    "teal": (20, 184, 166),       # teal
    "green": (34, 197, 94),       # green
    "red": (239, 68, 68),         # red
    "purple": (139, 92, 246),     # purple
    "white": (255, 255, 255),
    "light": (148, 163, 184),     # light gray
}

# (filename, title, subtitle, color1, color2, accent_color)
IMAGES = [
    # BUSINESS
    ("business", "kbli-2025-education-training.jpg",
     "Education & Training", "KBLI 2025 Industry Guide",
     (14, 116, 144), (6, 78, 59), BRAND["teal"]),
    ("business", "kbli-2025-agriculture-agritourism.jpg",
     "Agriculture & Agritourism", "KBLI 2025 Industry Guide",
     (22, 101, 52), (133, 77, 14), BRAND["green"]),
    ("business", "kbli-2025-manufacturing-production.jpg",
     "Manufacturing & Production", "KBLI 2025 Industry Guide",
     (30, 27, 75), (67, 20, 7), BRAND["red"]),
    ("business", "kbli-2025-healthcare-wellness.jpg",
     "Healthcare & Wellness", "KBLI 2025 Industry Guide",
     (88, 28, 135), (6, 78, 59), BRAND["purple"]),
    ("business", "kbli-2025-green-economy-waste.jpg",
     "Green Economy & Waste", "KBLI 2025 Industry Guide",
     (6, 78, 59), (2, 44, 34), BRAND["green"]),
    ("business", "kbli-2025-future-proofing-flexibility.jpg",
     "Future-Proofing & Flexibility", "KBLI 2025 Strategy",
     (15, 23, 42), (30, 27, 75), BRAND["purple"]),
    ("business", "kbli-2025-brand-positioning-strategy.jpg",
     "Brand Positioning Strategy", "KBLI 2025 Business",
     (15, 23, 42), (7, 7, 7), BRAND["gold"]),
    ("business", "kbli-2025-environmental-permits-amdal.jpg",
     "Environmental Permits & AMDAL", "KBLI 2025 Compliance",
     (6, 78, 59), (14, 116, 144), BRAND["teal"]),
    ("business", "kbli-2025-halal-certification-fnb.jpg",
     "Halal Certification F&B", "KBLI 2025 Industry Guide",
     (6, 78, 59), (133, 77, 14), BRAND["gold"]),
    ("business", "kbli-2025-import-export-licenses.jpg",
     "Import & Export Licenses", "KBLI 2025 Trade",
     (14, 116, 144), (15, 23, 42), BRAND["teal"]),
    ("business", "kbli-2025-location-restrictions-bali.jpg",
     "Location Restrictions Bali", "KBLI 2025 Zoning",
     (6, 78, 59), (14, 116, 144), BRAND["green"]),
    ("business", "kbli-2025-bali-transformation.jpg",
     "Bali Business Transformation", "KBLI 2025 Overview",
     (249, 115, 22), (15, 23, 42), BRAND["accent"]),
    ("business", "kbli-2025-gold-rush-migration.jpg",
     "Gold Rush Migration", "KBLI 2025 Investment",
     (133, 77, 14), (15, 23, 42), BRAND["gold"]),
    ("business", "beginners-guide-kbli-2025.jpg",
     "Beginner's Guide to KBLI 2025", "Complete Classification System",
     (249, 115, 22), (234, 179, 8), BRAND["white"]),
    ("business", "upgrading-indonesia-kbli-2025.jpg",
     "Upgrading Indonesia: KBLI 2025", "BPS Regulation 7/2025",
     (15, 23, 42), (30, 27, 75), BRAND["gold"]),
    ("business", "kbli-2025-new-codes-spotlight.jpg",
     "New KBLI Codes Spotlight", "2025 Technology Sectors",
     (15, 23, 42), (30, 27, 75), BRAND["teal"]),
    ("business", "kbli-2025-foreign-ownership-pma-guide.jpg",
     "Foreign Ownership (PMA)", "KBLI 2025 Investment Guide",
     (15, 23, 42), (14, 116, 144), BRAND["gold"]),
    ("business", "kbli-2025-multi-code-strategy.jpg",
     "Multi-Code Business Strategy", "KBLI 2025 Advanced Planning",
     (30, 27, 75), (15, 23, 42), BRAND["purple"]),
    ("business", "kbli-2025-tax-implications-klu.jpg",
     "Tax Implications & KLU", "KBLI 2025 Compliance",
     (6, 78, 59), (133, 77, 14), BRAND["gold"]),
    ("business", "kbli-2025-capital-investment-requirements.jpg",
     "Capital Investment Requirements", "PT PMA Setup Guide",
     (133, 77, 14), (15, 23, 42), BRAND["gold"]),
    ("business", "kbli-2025-oss-transition-update.jpg",
     "OSS Transition Update", "KBLI 2025 Portal Guide",
     (14, 116, 144), (15, 23, 42), BRAND["teal"]),
    ("business", "kbli-2025-license-permit-requirements.jpg",
     "License & Permit Requirements", "KBLI 2025 Risk Categories",
     (15, 23, 42), (67, 20, 7), BRAND["red"]),
    ("business", "kbli-2025-red-flags-audit-risk.jpg",
     "Red Flags & Audit Risk", "KBLI 2025 Compliance",
     (127, 29, 29), (15, 23, 42), BRAND["red"]),
    ("business", "kbli-2025-visa-kitas-synergy.jpg",
     "KBLI & KITAS Synergy", "Business + Immigration",
     (14, 116, 144), (30, 27, 75), BRAND["teal"]),
    ("business", "kbli-2020-to-2025-migration-guide.jpg",
     "KBLI 2020 → 2025 Migration", "Complete Transition Guide",
     (133, 77, 14), (15, 23, 42), BRAND["gold"]),
    # IMMIGRATION
    ("immigration", "e25b-director-kitas-guide.jpg",
     "Director KITAS (E25B)", "Indonesia Work Permit Guide",
     (15, 23, 42), (14, 116, 144), BRAND["gold"]),
    ("immigration", "e23-employee-kitas-guide.jpg",
     "Employee KITAS (E23)", "Indonesia Work Permit Guide",
     (14, 116, 144), (15, 23, 42), BRAND["teal"]),
    ("immigration", "e33g-remote-worker-visa-guide.jpg",
     "Remote Worker Visa (E33G)", "Digital Nomad Indonesia",
     (6, 78, 59), (14, 116, 144), BRAND["green"]),
    ("immigration", "e28a-investor-kitas-guide.jpg",
     "Investor KITAS (E28A)", "Indonesia Investment Visa",
     (133, 77, 14), (15, 23, 42), BRAND["gold"]),
    ("immigration", "rptka-foreign-worker-plan-guide.jpg",
     "RPTKA Foreign Worker Plan", "Indonesia HR Compliance",
     (15, 23, 42), (30, 27, 75), BRAND["teal"]),
    ("immigration", "kitas-extension-renewal-guide.jpg",
     "KITAS Extension & Renewal", "Step-by-Step Guide",
     (15, 23, 42), (67, 20, 7), BRAND["red"]),
    ("immigration", "kitas-transfer-change-sponsor.jpg",
     "KITAS Transfer & Sponsor Change", "Indonesia Immigration",
     (14, 116, 144), (30, 27, 75), BRAND["teal"]),
    ("immigration", "kitas-cancellation-company-closure.jpg",
     "KITAS Cancellation Guide", "Company Closure Procedures",
     (67, 20, 7), (15, 23, 42), BRAND["red"]),
    ("immigration", "kitas-upgrade-downgrade-conversion.jpg",
     "KITAS Upgrade, Downgrade & Conversion", "Visa Type Changes",
     (14, 116, 144), (30, 27, 75), BRAND["purple"]),
    ("immigration", "kitas-renewal-denied-common-reasons.jpg",
     "KITAS Renewal Denied?", "Common Reasons & Solutions",
     (127, 29, 29), (15, 23, 42), BRAND["red"]),
    ("immigration", "e33f-spouse-dependent-kitas-guide.jpg",
     "Spouse Dependent KITAS (E33F)", "Family Visa Indonesia",
     (133, 77, 14), (88, 28, 135), BRAND["gold"]),
    ("immigration", "e33e-child-dependent-kitas-guide.jpg",
     "Child Dependent KITAS (E33E)", "Family Visa Indonesia",
     (249, 115, 22), (133, 77, 14), BRAND["accent"]),
    ("immigration", "e311a-retirement-visa-kitas-guide.jpg",
     "Retirement Visa (E311A)", "Live in Bali Guide",
     (6, 78, 59), (14, 116, 144), BRAND["green"]),
    ("immigration", "kitap-permanent-residence-guide.jpg",
     "KITAP Permanent Residence", "Indonesia Long-Term Visa",
     (15, 23, 42), (6, 78, 59), BRAND["gold"]),
    ("immigration", "golden-visa-indonesia-complete-guide.jpg",
     "Indonesia Golden Visa", "Premium Investment Residence",
     (133, 77, 14), (15, 23, 42), BRAND["gold"]),
    ("immigration", "e-voa-electronic-visa-on-arrival-guide.jpg",
     "E-VOA Guide 2025", "Electronic Visa on Arrival",
     (14, 116, 144), (15, 23, 42), BRAND["teal"]),
    ("immigration", "stm-exit-reentry-permit-guide.jpg",
     "STM Exit & Reentry Permit", "Indonesia Travel Compliance",
     (15, 23, 42), (14, 116, 144), BRAND["teal"]),
    ("immigration", "visa-overstay-penalties-indonesia-guide.jpg",
     "Visa Overstay Penalties", "IDR 1M/Day — What To Do",
     (127, 29, 29), (15, 23, 42), BRAND["red"]),
    ("immigration", "wajib-lapor-reporting-obligations-guide.jpg",
     "Wajib Lapor Obligations", "Foreigner Reporting Requirements",
     (14, 116, 144), (6, 78, 59), BRAND["teal"]),
    ("immigration", "passport-renewal-active-kitas-guide.jpg",
     "Passport Renewal with Active KITAS", "Step-by-Step Guide",
     (15, 23, 42), (14, 116, 144), BRAND["gold"]),
    ("immigration", "b211-social-cultural-visit-visa-guide.jpg",
     "B211 Social Cultural Visa", "Bali Visit Visa Guide",
     (249, 115, 22), (6, 78, 59), BRAND["accent"]),
    ("immigration", "business-visit-vs-work-visa-indonesia-guide.jpg",
     "Business Visit vs Work Visa", "Which One Do You Need?",
     (15, 23, 42), (14, 116, 144), BRAND["teal"]),
    ("immigration", "multiple-entry-vs-single-entry-visa-indonesia.jpg",
     "Multiple vs Single Entry Visa", "Indonesia Visa Comparison",
     (14, 116, 144), (30, 27, 75), BRAND["teal"]),
    ("immigration", "border-runs-indonesia-reality-check-2026.jpg",
     "Border Runs: Reality Check 2026", "Is It Still Worth It?",
     (127, 29, 29), (15, 23, 42), BRAND["red"]),
    ("immigration", "visa-free-vs-evoa-indonesia-comparison.jpg",
     "Visa-Free vs E-VOA", "Indonesia Entry Options Compared",
     (6, 78, 59), (14, 116, 144), BRAND["green"]),
    ("immigration", "tourist-visa-extension-indonesia-guide.jpg",
     "Tourist Visa Extension", "Indonesia 2025 Guide",
     (14, 116, 144), (133, 77, 14), BRAND["teal"]),
    ("immigration", "emergency-visa-procedures-indonesia-guide.jpg",
     "Emergency Visa Procedures", "Indonesia Crisis Protocols",
     (127, 29, 29), (14, 116, 144), BRAND["red"]),
    ("immigration", "immigration-checks-documents-carry-indonesia.jpg",
     "Documents to Carry in Indonesia", "Immigration Compliance Kit",
     (15, 23, 42), (6, 78, 59), BRAND["teal"]),
    ("immigration", "indonesia-immigration-blacklist-guide.jpg",
     "Immigration Blacklist Guide", "How to Check & Appeal",
     (15, 23, 42), (127, 29, 29), BRAND["red"]),
    ("immigration", "ina-digital-immigration-indonesia-2026.jpg",
     "INA Digital Immigration 2026", "Indonesia Smart Border System",
     (30, 27, 75), (14, 116, 144), BRAND["purple"]),
    # TAX-LEGAL
    ("tax-legal", "coretax-login-errors-fixes-2026.jpg",
     "CoreTax Login Errors & Fixes", "DJP 2026 Troubleshooting",
     (127, 29, 29), (15, 23, 42), BRAND["red"]),
    ("tax-legal", "coretax-npwp16-vs-npwp15-foreigners.jpg",
     "NPWP 16 vs NPWP 15", "Foreigners' Tax ID in CoreTax",
     (14, 116, 144), (15, 23, 42), BRAND["teal"]),
    ("tax-legal", "coretax-vs-djp-online-what-changed.jpg",
     "CoreTax vs DJP Online", "What Changed in 2025?",
     (15, 23, 42), (30, 27, 75), BRAND["purple"]),
    ("tax-legal", "tax-amnesty-indonesia-history.jpg",
     "Tax Amnesty Indonesia History", "2016, 2022, and Beyond",
     (133, 77, 14), (15, 23, 42), BRAND["gold"]),
    ("tax-legal", "pph-25-monthly-installments-guide.jpg",
     "PPh 25 Monthly Installments", "Corporate Tax Guide",
     (6, 78, 59), (15, 23, 42), BRAND["green"]),
    ("tax-legal", "pph-29-annual-settlement-guide.jpg",
     "PPh 29 Annual Settlement", "Year-End Tax Balancing",
     (15, 23, 42), (133, 77, 14), BRAND["gold"]),
]


def gradient_background(draw, width, height, color1, color2):
    """Draw vertical gradient."""
    for y in range(height):
        r = int(color1[0] + (color2[0] - color1[0]) * y / height)
        g = int(color1[1] + (color2[1] - color1[1]) * y / height)
        b = int(color1[2] + (color2[2] - color1[2]) * y / height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def draw_geometric_pattern(draw, width, height, accent):
    """Draw subtle geometric decorative elements."""
    # Corner decorations
    a = (*accent, 30)  # semi-transparent
    # Bottom-right triangle
    draw.polygon([(width, height), (width-300, height), (width, height-150)],
                 fill=(*accent, 20))
    # Top-left circle
    draw.ellipse([(-100, -100), (200, 200)], fill=(*accent, 15))
    # Diagonal lines pattern
    for i in range(0, 400, 40):
        alpha = 15
        draw.line([(width - i, height), (width, height - i)],
                 fill=(*accent, alpha), width=1)


def wrap_text(text, max_width, font, draw):
    """Wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > max_width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def create_image(output_path, title, subtitle, color1, color2, accent):
    """Create a professional branded image."""
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img, "RGBA")

    # Gradient background
    gradient_background(draw, WIDTH, HEIGHT, color1, color2)

    # Geometric pattern
    draw_geometric_pattern(draw, WIDTH, HEIGHT, accent)

    # Accent bar on left
    draw.rectangle([(0, 0), (8, HEIGHT)], fill=accent)

    # Bottom accent strip
    draw.rectangle([(0, HEIGHT-6), (WIDTH, HEIGHT)], fill=accent)

    # Brand label top-right
    try:
        small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 52)
        sub_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
        label_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except Exception:
        small_font = ImageFont.load_default()
        title_font = small_font
        sub_font = small_font
        label_font = small_font

    # "BALI ZERO" brand label
    draw.text((WIDTH - 160, 30), "BALI ZERO", fill=accent, font=label_font)

    # Subtitle (category label)
    draw.text((60, 200), subtitle.upper(), fill=(*accent, 200), font=small_font)

    # Title (main)
    lines = wrap_text(title, WIDTH - 120, title_font, draw)
    y = 240
    for line in lines[:3]:
        draw.text((60, y), line, fill=BRAND["white"], font=title_font)
        y += 65

    # Decorative dot separator
    draw.ellipse([(60, y+20), (70, y+30)], fill=accent)
    draw.ellipse([(80, y+20), (90, y+30)], fill=accent)
    draw.ellipse([(100, y+20), (110, y+30)], fill=accent)

    # Bottom tagline
    draw.text((60, HEIGHT - 50), "zantara.balizero.com",
              fill=(*BRAND["light"], 180), font=small_font)

    img.save(output_path, "JPEG", quality=92, optimize=True)


def main():
    total = len(IMAGES)
    done = 0
    for cat, filename, title, subtitle, c1, c2, accent in IMAGES:
        out_dir = f"{OUTPUT_BASE}/{cat}"
        os.makedirs(out_dir, exist_ok=True)
        path = f"{out_dir}/{filename}"

        if os.path.exists(path) and os.path.getsize(path) > 10000:
            print(f"SKIP: {filename}")
            done += 1
            continue

        try:
            create_image(path, title, subtitle, c1, c2, accent)
            size = os.path.getsize(path) // 1024
            print(f"OK [{done+1}/{total}]: {filename} ({size}KB)")
            done += 1
        except Exception as e:
            print(f"ERROR: {filename}: {e}")

    print(f"\nDone: {done}/{total}")


if __name__ == "__main__":
    main()
