#!/usr/bin/env python3
"""past/ population helper.

Antonello curates a set of past WR2 carousels (PNG export + brief.md). This script imports
them into `~/.claude/skills/bali-zero-brand/past/` with a normalized naming convention so
the wr2-design-architect can retrieve them as in-context style references.

Naming convention:
  past/<YYYY-MM-DD>__<topic-slug>__<domain>__<register>/
    cover.png
    brief.md
    metadata.json

The orchestrator's "load 3-5 PNGs from past/ semantically similar to topic" step uses the
metadata.json to pick references.

Usage examples:

  # Single import (interactive prompts for missing fields)
  python3 _past-import.py import --png /path/to/carousel.png --brief /path/to/brief.md

  # Batch from CSV (Antonello's preferred curation flow)
  python3 _past-import.py batch --csv ~/Desktop/wr2-curation.csv

  # CSV columns: date, topic_slug, domain, register, layout_primary, png_path, brief_path, ig_url, ig_saves, notes

  # List current past/ inventory
  python3 _past-import.py list
"""

import argparse
import csv
import json
import shutil
import sys
from datetime import date
from pathlib import Path

PAST_DIR = Path.home() / ".claude/skills/bali-zero-brand/past"

VALID_DOMAINS = {"visa", "tax", "property", "regulatory", "health", "brand"}
VALID_REGISTERS = {"rituale", "analitico", "ironico", "militante", "pedagogico", "poetico", "tecnico"}
VALID_LAYOUTS = {"cover-photo", "photo-headline-yellow-sub", "qa-dialogue",
                 "timeline-pinboard", "dark-status-list", "statement-bomb"}


def slugify(s):
    return s.lower().strip().replace(" ", "-").replace("_", "-")


def import_one(png_path, brief_path, *, date_str=None, topic_slug=None, domain=None,
               register=None, layout_primary=None, ig_url=None, ig_saves=None, notes=None):
    png_path = Path(png_path).expanduser()
    brief_path = Path(brief_path).expanduser()

    if not png_path.exists():
        print(f"PNG not found: {png_path}", file=sys.stderr)
        return False
    if not brief_path.exists():
        print(f"Brief not found: {brief_path}", file=sys.stderr)
        return False

    if not date_str:
        date_str = date.today().isoformat()
    if not topic_slug:
        topic_slug = png_path.stem
    topic_slug = slugify(topic_slug)
    domain = (domain or "regulatory").lower()
    register = (register or "analitico").lower()
    layout_primary = (layout_primary or "photo-headline-yellow-sub").lower()

    if domain not in VALID_DOMAINS:
        print(f"Invalid domain '{domain}'. Must be one of {sorted(VALID_DOMAINS)}", file=sys.stderr)
        return False
    if register not in VALID_REGISTERS:
        print(f"Invalid register '{register}'. Must be one of {sorted(VALID_REGISTERS)}", file=sys.stderr)
        return False
    if layout_primary not in VALID_LAYOUTS:
        print(f"Invalid layout '{layout_primary}'. Must be one of {sorted(VALID_LAYOUTS)}", file=sys.stderr)
        return False

    bucket = f"{date_str}__{topic_slug}__{domain}__{register}"
    target_dir = PAST_DIR / bucket
    if target_dir.exists():
        print(f"Already exists: {target_dir}", file=sys.stderr)
        return False
    target_dir.mkdir(parents=True)

    shutil.copy(png_path, target_dir / "cover.png")
    shutil.copy(brief_path, target_dir / "brief.md")

    metadata = {
        "date": date_str,
        "topic_slug": topic_slug,
        "domain": domain,
        "tone_register_primary": register,
        "layout_family_primary": layout_primary,
        "instagram_post_url": ig_url,
        "ig_save_count": ig_saves,
        "notes": notes,
        "imported_from": {
            "png": str(png_path),
            "brief": str(brief_path),
        },
    }
    (target_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    print(f"Imported: {bucket}")
    return True


def cmd_import(args):
    success = import_one(
        png_path=args.png,
        brief_path=args.brief,
        date_str=args.date,
        topic_slug=args.topic_slug,
        domain=args.domain,
        register=args.register,
        layout_primary=args.layout,
        ig_url=args.ig_url,
        ig_saves=int(args.ig_saves) if args.ig_saves else None,
        notes=args.notes,
    )
    sys.exit(0 if success else 1)


def cmd_batch(args):
    csv_path = Path(args.csv).expanduser()
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)
    n_ok = 0
    n_fail = 0
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            ok = import_one(
                png_path=row["png_path"],
                brief_path=row["brief_path"],
                date_str=row.get("date"),
                topic_slug=row.get("topic_slug"),
                domain=row.get("domain"),
                register=row.get("register"),
                layout_primary=row.get("layout_primary"),
                ig_url=row.get("ig_url"),
                ig_saves=int(row["ig_saves"]) if row.get("ig_saves") else None,
                notes=row.get("notes"),
            )
            if ok:
                n_ok += 1
            else:
                n_fail += 1
    print(f"Batch complete: {n_ok} imported, {n_fail} failed.")
    sys.exit(0 if n_fail == 0 else 1)


def cmd_list(args):
    if not PAST_DIR.exists() or not list(PAST_DIR.iterdir()):
        print("past/ is empty.")
        return
    for d in sorted(PAST_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / "metadata.json"
        if not meta_path.exists():
            print(f"  {d.name}  (no metadata)")
            continue
        meta = json.loads(meta_path.read_text())
        print(f"  {d.name}")
        print(f"    domain={meta.get('domain')} register={meta.get('tone_register_primary')} "
              f"saves={meta.get('ig_save_count')}")


def main():
    parser = argparse.ArgumentParser(description="Import past WR2 carousels into skill past/")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_imp = sub.add_parser("import", help="Import one carousel")
    p_imp.add_argument("--png", required=True)
    p_imp.add_argument("--brief", required=True)
    p_imp.add_argument("--date")
    p_imp.add_argument("--topic-slug")
    p_imp.add_argument("--domain", choices=sorted(VALID_DOMAINS))
    p_imp.add_argument("--register", choices=sorted(VALID_REGISTERS))
    p_imp.add_argument("--layout", choices=sorted(VALID_LAYOUTS))
    p_imp.add_argument("--ig-url")
    p_imp.add_argument("--ig-saves")
    p_imp.add_argument("--notes")
    p_imp.set_defaults(func=cmd_import)

    p_batch = sub.add_parser("batch", help="Batch import from CSV")
    p_batch.add_argument("--csv", required=True)
    p_batch.set_defaults(func=cmd_batch)

    p_list = sub.add_parser("list", help="List current past/ inventory")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    PAST_DIR.mkdir(parents=True, exist_ok=True)
    args.func(args)


if __name__ == "__main__":
    main()
