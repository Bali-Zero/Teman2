#!/usr/bin/env python3
"""Generate branded article covers for Collega 3 using Pillow."""

import os
from PIL import Image, ImageDraw, ImageFont

OUTPUT_BASE = "apps/mouth/public/static/insights/business"
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
    ("kbli-2025-multi-code-strategy.jpg", "Multi-KBLI Strategy", "PT PMA Advanced Planning", BRAND["primary"], (30, 27, 75), BRAND["purple"]),
    ("kbli-2025-new-codes-spotlight.jpg", "New KBLI 2025 Codes", "Technology & Future Sectors", BRAND["primary"], (14, 116, 144), BRAND["teal"]),
    ("kbli-2025-oss-transition-update.jpg", "OSS Transition Update", "KBLI 2025 Portal Guide", BRAND["primary"], (15, 23, 42), BRAND["teal"]),
    ("kbli-2025-real-estate-property.jpg", "Real Estate KBLI 2025", "Property Development Guide", BRAND["primary"], (22, 101, 52), BRAND["green"]),
    ("kbli-2025-red-flags-audit-risk.jpg", "Red Flags & Audit Risk", "KBLI 2025 Compliance", (127, 29, 29), BRAND["primary"], BRAND["red"]),
    ("kbli-2025-retail-ecommerce.jpg", "Retail & E-Commerce", "KBLI 2025 Shop Guide", BRAND["primary"], (133, 77, 14), BRAND["gold"]),
    ("kbli-2025-tax-implications-klu.jpg", "Tax Implications & KLU", "KBLI 2025 Compliance", BRAND["primary"], (133, 77, 14), BRAND["gold"]),
    ("kbli-2025-tourism-travel-services.jpg", "Tourism & Travel Codes", "Bali Tourism Business", (14, 116, 144), BRAND["primary"], BRAND["teal"]),
    ("kbli-2025-visa-kitas-synergy.jpg", "KBLI & KITAS Synergy", "Business + Immigration", (14, 116, 144), (30, 27, 75), BRAND["teal"]),
    ("kbli-klu-fiscal-control-2025.jpg", "KBLI & KLU Convergence", "Coretax Fiscal Surveillance", (30, 27, 75), BRAND["primary"], BRAND["purple"]),
    ("oss-kbli-2025-fiktif-positif.jpg", "Fiktif Positif Paradox", "Deemed Approval Guide", BRAND["primary"], (15, 23, 42), BRAND["gold"]),
    ("upgrading-indonesia-kbli-2025.jpg", "Upgrading Indonesia", "BPS Regulation 7/2025", BRAND["primary"], (30, 27, 75), BRAND["gold"]),
]

def gradient_background(draw, width, height, color1, color2):
    for y in range(height):
        r = int(color1[0] + (color2[0] - color1[0]) * y / height)
        g = int(color1[1] + (color2[1] - color1[1]) * y / height)
        b = int(color1[2] + (color2[2] - color1[2]) * y / height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

def draw_geometric_pattern(draw, width, height, accent):
    draw.polygon([(width, height), (width-300, height), (width, height-150)], fill=(*accent, 20))
    draw.ellipse([(-100, -100), (200, 200)], fill=(*accent, 15))
    for i in range(0, 400, 40):
        draw.line([(width - i, height), (width, height - i)], fill=(*accent, 15), width=1)

def wrap_text(text, max_width, font, draw):
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
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img, "RGBA")
    gradient_background(draw, WIDTH, HEIGHT, color1, color2)
    draw_geometric_pattern(draw, WIDTH, HEIGHT, accent)
    draw.rectangle([(0, 0), (8, HEIGHT)], fill=accent)
    draw.rectangle([(0, HEIGHT-6), (WIDTH, HEIGHT)], fill=accent)
    
    try:
        # MacOS paths
        font_path = "/System/Library/Fonts/Helvetica.ttc"
        small_font = ImageFont.truetype(font_path, 18)
        title_font = ImageFont.truetype(font_path, 52)
        sub_font = ImageFont.truetype(font_path, 28)
        label_font = ImageFont.truetype(font_path, 22)
    except Exception:
        small_font = ImageFont.load_default()
        title_font = small_font
        sub_font = small_font
        label_font = small_font

    draw.text((WIDTH - 160, 30), "BALI ZERO", fill=accent, font=label_font)
    draw.text((60, 200), subtitle.upper(), fill=(*accent, 200), font=small_font)
    lines = wrap_text(title, WIDTH - 120, title_font, draw)
    y = 240
    for line in lines[:3]:
        draw.text((60, y), line, fill=BRAND["white"], font=title_font)
        y += 65
    draw.ellipse([(60, y+20), (70, y+30)], fill=accent)
    draw.ellipse([(80, y+20), (90, y+30)], fill=accent)
    draw.ellipse([(100, y+20), (110, y+30)], fill=accent)
    draw.text((60, HEIGHT - 50), "zantara.balizero.com", fill=(*BRAND["light"], 180), font=small_font)
    img.save(output_path, "JPEG", quality=92, optimize=True)

def main():
    os.makedirs(OUTPUT_BASE, exist_ok=True)
    total = len(IMAGES)
    for i, (filename, title, subtitle, c1, c2, accent) in enumerate(IMAGES):
        path = f"{OUTPUT_BASE}/{filename}"
        create_image(path, title, subtitle, c1, c2, accent)
        print(f"[{i+1}/{total}] Created: {filename}")

if __name__ == "__main__":
    main()
