"""Render the HTML output to a print-ready PDF via Playwright headless Chromium."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def render_pdf(html_path: Path, pdf_path: Path) -> None:
    if not html_path.exists():
        sys.exit(f"ERROR: HTML not found at {html_path}. Run generate.py first.")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    file_url = f"file://{html_path.resolve()}"
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--html",
        type=Path,
        default=Path.home() / "Desktop" / "Bali_Zero_Price_List_2026.html",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path.home() / "Desktop" / "Bali_Zero_Price_List_2026.pdf",
    )
    args = parser.parse_args()
    print(f"  → PDF: {args.pdf}")
    render_pdf(args.html, args.pdf)
    print(f"✓ Done ({args.pdf.stat().st_size:,} bytes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
