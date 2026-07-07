#!/usr/bin/env python3
"""QR code renderer for WR2 carousel elegant-close slides — Article 14.5 (deferred).

Generates a Bali Zero brand-styled QR code (red foreground #C8102E on white,
sized to fit the .qr-closing CSS class 120×120 slot). Used by layout-composer
when brief.primary_source_url is set; output PNG is copied into the slide
render directory and referenced via .qr-closing { background-image: url(qr.png) }.

The URL target MUST be a regulator-issued primary source (DJP, OSS, JDIH,
Permenkumham PDF, BPS) — Bali Zero own domains are forbidden by constitution
Article 6.6 (no hard-sell CTA). This script does NOT enforce the validation
itself; that's wr2-critic Rubric 5 check 5.7 territory. We just render.

Library usage:
    from _qr_renderer import render_qr
    render_qr(url, out_path, size=120)

CLI usage:
    python3 _qr_renderer.py --url <URL> --out <PATH> [--size 120]
    python3 _qr_renderer.py --url <URL> --out <PATH> --validate-host

Cost: zero (segno is pure Python, no API).
Latency: ~50ms per QR.

Dependencies: segno>=1.5 (small Python lib), Pillow (already in backend-rag venv).
Install: `apps/backend-rag/.venv/bin/pip install segno` (done 2026-05-12).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

# Bali Zero brand colors (constitution Article 2.1)
QR_FG_COLOR = "#C8102E"  # color.status.red — brand red
QR_BG_COLOR = "#FFFFFF"  # color.text.white — white background for scan reliability
QR_BORDER_MODULES = 2    # quiet zone, 2 modules per QR spec minimum
QR_ERROR_LEVEL = "M"     # ~15% error correction — balance between density and resilience
DEFAULT_SIZE_PX = 120    # matches .qr-closing CSS class in _base.css

# Trusted primary-source hosts for WR2 Article 14.5 (advisory only — not enforced here,
# wr2-critic Rubric 5.7 is the gate). Kept here for --validate-host convenience.
TRUSTED_HOSTS = {
    "pajak.go.id",
    "www.pajak.go.id",
    "jdih.kemenkumham.go.id",
    "jdih.imigrasi.go.id",
    "jdih.go.id",
    "oss.go.id",
    "bps.go.id",
    "kemenkeu.go.id",
    "simbg.pu.go.id",
    "imigrasi.go.id",
    "kpu.go.id",
    "bi.go.id",
}

# Forbidden hosts (Article 6.6 hard-sell ban — Bali Zero own domains)
FORBIDDEN_HOSTS = {
    "balizero.com",
    "www.balizero.com",
    "kita.balizero.com",
    "my.balizero.com",
    "zantara.balizero.com",
    "instagram.com",
    "www.instagram.com",
    "wa.me",
    "api.whatsapp.com",
}


def validate_url(url: str) -> tuple[bool, str]:
    """Check URL against trusted/forbidden host lists.

    Returns (is_valid, message). is_valid=False if forbidden; True otherwise.
    NOTE: this is advisory only. Critic Rubric 5.7 is the constitutional gate.
    """
    if not url or not url.strip():
        return False, "empty URL"
    try:
        parsed = urlparse(url.strip())
    except Exception as e:
        return False, f"unparseable URL: {e}"
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "no host in URL"
    if host in FORBIDDEN_HOSTS:
        return False, f"forbidden host (Article 6.6 hard-sell ban): {host}"
    if host in TRUSTED_HOSTS:
        return True, f"trusted primary-source host: {host}"
    return True, f"unknown host {host} — advisory: verify is regulator-issued"


def render_qr(
    url: str,
    out_path: str | Path,
    size: int = DEFAULT_SIZE_PX,
    fg_color: str = QR_FG_COLOR,
    bg_color: str = QR_BG_COLOR,
    border_modules: int = QR_BORDER_MODULES,
    error_level: str = QR_ERROR_LEVEL,
) -> Path:
    """Render a QR code PNG sized exactly to `size`×`size` pixels.

    Uses segno to generate the symbol, then Pillow to resize to exact target
    dimensions (LANCZOS resample for crisp edges at 120×120).

    Args:
        url: target URL to encode.
        out_path: output PNG path.
        size: square output dimension in pixels. Default 120 matches
              `.qr-closing` CSS class.
        fg_color: dark-module color (default Bali Zero red).
        bg_color: light-module color (default white).
        border_modules: quiet-zone width in modules (default 2, spec min).
        error_level: 'L'|'M'|'Q'|'H' (default 'M' ≈15% correction).

    Returns:
        Path to the written PNG.

    Raises:
        ValueError: invalid args (size ≤ 0, malformed colors).
        RuntimeError: segno generation failed (URL too long, etc.).
    """
    if size <= 0:
        raise ValueError(f"size must be > 0, got {size}")
    if not url:
        raise ValueError("url required")

    import segno
    from PIL import Image

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        qr = segno.make(url, error=error_level)
    except Exception as e:
        raise RuntimeError(f"segno.make failed for url ({len(url)} chars): {e}") from e

    # Render at scale=8 (high-quality) into temp BytesIO, then resize to target
    # via Pillow. This gives crisp anti-aliased edges at the final size.
    import io
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=8, dark=fg_color, light=bg_color, border=border_modules)
    buf.seek(0)
    img = Image.open(buf).convert("RGB").resize((size, size), Image.LANCZOS)
    img.save(out_path, format="PNG", optimize=True)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a Bali Zero brand QR code for WR2 elegant-close slides.",
    )
    parser.add_argument("--url", required=True, help="URL to encode")
    parser.add_argument("--out", required=True, help="Output PNG path")
    parser.add_argument(
        "--size", type=int, default=DEFAULT_SIZE_PX,
        help=f"Square dimension in pixels (default {DEFAULT_SIZE_PX})",
    )
    parser.add_argument(
        "--fg-color", default=QR_FG_COLOR,
        help=f"Foreground color hex (default Bali Zero red {QR_FG_COLOR})",
    )
    parser.add_argument(
        "--bg-color", default=QR_BG_COLOR,
        help=f"Background color hex (default white {QR_BG_COLOR})",
    )
    parser.add_argument(
        "--error-level", choices=["L", "M", "Q", "H"], default=QR_ERROR_LEVEL,
        help="Error correction level (default M ≈15%%)",
    )
    parser.add_argument(
        "--validate-host", action="store_true",
        help="Pre-check URL host against trusted/forbidden list, exit 2 if forbidden",
    )
    args = parser.parse_args()

    if args.validate_host:
        is_valid, msg = validate_url(args.url)
        if not is_valid:
            print(f"VALIDATION FAIL: {msg}", file=sys.stderr)
            return 2
        print(f"VALIDATION OK: {msg}", file=sys.stderr)

    try:
        out = render_qr(
            args.url, args.out,
            size=args.size,
            fg_color=args.fg_color,
            bg_color=args.bg_color,
            error_level=args.error_level,
        )
    except (ValueError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"OK: wrote {out} ({out.stat().st_size} bytes, {args.size}x{args.size})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
