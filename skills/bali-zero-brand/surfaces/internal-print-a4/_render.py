"""Render Bali Zero internal-print-a4 surface HTML to PDF.

Canonical Playwright headless Chromium renderer. Used by every A4 brief
authored under this surface. See `surfaces/internal-print-a4.md` for
the spec.

Usage:
    python3 _render.py --html /path/to/Brief.html --pdf ~/Desktop/Brief.pdf

Constraints (inherited from surface spec A1.3):
    - A4 portrait
    - print_background=True (cover dark mode requires this)
    - prefer_css_page_size=True (CSS @page directives win)
    - zero margin (CSS controls all whitespace)
    - wait_until="networkidle" (Google Fonts CDN must finish loading
      before pdf() is called, or Montserrat fails to render)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def render(html_path: Path, pdf_path: Path) -> None:
    if not html_path.exists():
        sys.exit(f"ERROR: HTML not found at {html_path}")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    file_url = f"file://{html_path.resolve()}"
    print(f"  → rendering {html_path.name} -> {pdf_path}")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(file_url, wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            prefer_css_page_size=True,
        )
        browser.close()
    size_kb = pdf_path.stat().st_size / 1024
    print(f"    OK ({size_kb:,.1f} KB)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, required=True, help="Path to source HTML file")
    parser.add_argument("--pdf", type=Path, required=True, help="Output PDF path")
    args = parser.parse_args()
    render(args.html, args.pdf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
