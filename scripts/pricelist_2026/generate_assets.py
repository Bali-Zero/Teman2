"""Driver: generates hero + icon PNGs via `codex exec` → Image 2 (gpt-image-1).

Idempotent: skips files already present in the output dir. Use
--regenerate <basename> to force re-gen of a specific asset.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Add repo root to sys.path so `from scripts...` resolves when run as module
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.pricelist_2026 import asset_briefs

DEFAULT_OUT = Path.home() / "Desktop" / "Bali_Zero_Price_List_2026_assets"


def _check_codex() -> None:
    if shutil.which("codex") is None:
        sys.exit(
            "ERROR: `codex` CLI not found in PATH. Install Codex CLI before "
            "running this script. Do NOT introduce paid-API fallbacks."
        )


def _codex_image_prompt(brief: str, out_path: Path, size: str) -> str:
    """Wrap the brief in instructions Codex will follow non-interactively."""
    return (
        f"Generate ONE image using OpenAI gpt-image-1 (Image 2). "
        f"Brief: {brief} "
        f"Size: {size}. "
        f"Save the resulting PNG file at exactly this absolute path: "
        f"{out_path}. "
        f"Do not output anything else after generation. Do not explain. "
        f"Do not generate variants. Do not ask for confirmation."
    )


def _generate_one(brief: str, out_path: Path, size: str, *, dry_run: bool) -> bool:
    """Returns True if generated, False if skipped."""
    if out_path.exists():
        print(f"  ✓ skip (exists): {out_path.name}")
        return False
    prompt = _codex_image_prompt(brief, out_path, size)
    if dry_run:
        print(f"  [dry-run] would gen: {out_path.name}")
        print(f"           prompt: {prompt[:120]}...")
        return True
    print(f"  ⏳ generating: {out_path.name} ({size})")
    cmd = ["codex", "exec", "--full-auto", prompt]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300
        )
    except subprocess.TimeoutExpired:
        print(f"  ✗ TIMEOUT: {out_path.name}", file=sys.stderr)
        return False
    if result.returncode != 0:
        print(
            f"  ✗ codex exec failed (exit {result.returncode}): "
            f"{result.stderr[:300]}",
            file=sys.stderr,
        )
        return False
    if not out_path.exists():
        print(
            f"  ✗ codex completed but file not at {out_path}", file=sys.stderr
        )
        print(f"     stdout: {result.stdout[:300]}", file=sys.stderr)
        return False
    print(f"  ✓ generated: {out_path.name} ({out_path.stat().st_size} bytes)")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--only", choices=["heros", "icons", "all"], default="all"
    )
    parser.add_argument(
        "--regenerate", action="append", default=[],
        help="Force re-gen of basename (without .png). Repeatable."
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _check_codex()

    heros_dir = args.out_dir / "heros"
    icons_dir = args.out_dir / "icons"
    heros_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)

    # Force re-gen by deleting the existing PNGs first
    for basename in args.regenerate:
        for d in (heros_dir, icons_dir):
            target = d / f"{basename}.png"
            if target.exists():
                print(f"  ✗ deleting for re-gen: {target}")
                target.unlink()

    n_gen = 0
    n_skip = 0

    if args.only in ("heros", "all"):
        print(f"=== Heros ({len(asset_briefs.HERO_BRIEFS)}) ===")
        for basename, brief, size in asset_briefs.HERO_BRIEFS:
            out = heros_dir / f"{basename}.png"
            if _generate_one(brief, out, size, dry_run=args.dry_run):
                n_gen += 1
            else:
                if out.exists():
                    n_skip += 1

    if args.only in ("icons", "all"):
        print(f"=== Icons ({len(asset_briefs.ICON_BRIEFS)}) ===")
        for icon_id, brief in sorted(asset_briefs.ICON_BRIEFS.items()):
            out = icons_dir / f"{icon_id}.png"
            if _generate_one(brief, out, "1024x1024", dry_run=args.dry_run):
                n_gen += 1
            else:
                if out.exists():
                    n_skip += 1

    print(f"\nDone. Generated: {n_gen}, Skipped (already exist): {n_skip}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
