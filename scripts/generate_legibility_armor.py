#!/usr/bin/env python3
"""Generate the Legibility Armor gradient PNG used by the WR2 Canva pipeline.

The gradient overlays every hero slide image so the League Spartan / Montserrat
white text stays readable regardless of image luminance. The PNG is 4:5 portrait
(1080×1350, IG Post size) with:

  * Top 28% of height: black fade (opacity 170→0) — protects headline text
  * Middle ~27%: fully transparent — lets the hero image shine
  * Bottom 45%: black fade (opacity 0→180) — protects body + CTA text

Re-run and re-upload to bump the version. Update LEGIBILITY_ARMOR_URL in
`apps/backend-rag/backend/services/canva_renderer/pending_builder.py` to
invalidate cached assets on Canva side.

Requires: Pillow, boto3. AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY for Tigris.
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from PIL import Image

TIGRIS_ENDPOINT = "https://fly.storage.tigris.dev"
TIGRIS_BUCKET = "nuzantara-warroom-images"
DEFAULT_KEY = "warroom/template-assets/legibility-armor-gradient-v1.png"

W, H = 1080, 1350  # 4:5 portrait Instagram Post


def generate(
    *,
    top_zone_ratio: float = 0.28,
    bottom_zone_start_ratio: float = 0.55,
    top_opacity: int = 170,
    bottom_opacity: int = 180,
) -> bytes:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = img.load()
    top_zone_end = int(H * top_zone_ratio)
    bottom_zone_start = int(H * bottom_zone_start_ratio)

    for y in range(H):
        if y < top_zone_end:
            alpha = int(top_opacity * (1 - y / top_zone_end))
        elif y >= bottom_zone_start:
            t = (y - bottom_zone_start) / (H - bottom_zone_start)
            alpha = int(bottom_opacity * t)
        else:
            alpha = 0
        for x in range(W):
            px[x, y] = (0, 0, 0, alpha)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def upload(data: bytes, key: str = DEFAULT_KEY) -> str:
    import boto3

    s3 = boto3.client(
        "s3", endpoint_url=TIGRIS_ENDPOINT, region_name="auto",
    )
    s3.put_object(
        Bucket=TIGRIS_BUCKET,
        Key=key,
        Body=data,
        ContentType="image/png",
        ACL="public-read",
    )
    return f"https://{TIGRIS_BUCKET}.fly.storage.tigris.dev/{key}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--key", default=DEFAULT_KEY, help="Tigris S3 key")
    p.add_argument("--local-out", default="/tmp/legibility-armor.png")
    p.add_argument("--skip-upload", action="store_true", help="preview only")
    p.add_argument("--top-opacity", type=int, default=170)
    p.add_argument("--bottom-opacity", type=int, default=180)
    args = p.parse_args()

    data = generate(top_opacity=args.top_opacity, bottom_opacity=args.bottom_opacity)
    Path(args.local_out).write_bytes(data)
    print(f"Local: {args.local_out} ({len(data):,} bytes)")

    if args.skip_upload:
        return 0

    url = upload(data, key=args.key)
    print(f"Uploaded: {url}")
    print()
    print("To invalidate Canva's asset cache:")
    print("  edit LEGIBILITY_ARMOR_URL in "
          "apps/backend-rag/backend/services/canva_renderer/pending_builder.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
