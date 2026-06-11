"""Demo: compose a full carousel from a slides_json file (manual E2E test).

Usage:
    PYTHONPATH=<wt>/scripts <venv>/python -m wr2_html_renderer._compose_demo \
        <slides_json_path> <output_dir> ["topic"]
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


async def _run(slides_path: Path, out_dir: Path, topic: str) -> int:
    from wr2_html_renderer.composer import compose_carousel

    slides = json.loads(slides_path.read_text(encoding="utf-8"))
    res = await compose_carousel(slides, out_dir, topic=topic)

    print("=== RESULT ===")
    print("ok:", res.ok)
    print("slides_rendered:", res.slides_rendered)
    print("heroes_expected:", res.heroes_expected, "heroes_placed:", res.heroes_placed)
    print("pdf:", res.pdf_path)
    if res.failures:
        print("FAILURES:")
        for f in res.failures:
            print("  -", f)

    manifest_path = out_dir / "manifest.json"
    if manifest_path.is_file():
        man = json.loads(manifest_path.read_text(encoding="utf-8"))
        print("families:", man.get("families"))

    pngs = sorted((out_dir / "slides").glob("*.png"))
    print(f"PNGs: {len(pngs)}")
    for p in pngs:
        print(f"  {p.name}  {p.stat().st_size} bytes")

    return 0 if res.ok else 1


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: python -m wr2_html_renderer._compose_demo <slides_json> <out_dir> [topic]")
        return 2
    slides_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    topic = sys.argv[3] if len(sys.argv) > 3 else ""
    if not slides_path.is_file():
        print(f"slides_json not found: {slides_path}")
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    return asyncio.run(_run(slides_path, out_dir, topic))


if __name__ == "__main__":
    raise SystemExit(main())
