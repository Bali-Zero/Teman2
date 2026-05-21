from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def summarize_jsonl(path: str | Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record: dict[str, Any] = json.loads(line)
            record_type = str(record.get("record_type") or "unknown")
            counts[record_type] = counts.get(record_type, 0) + 1
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run skeleton for future WhatsApp export staging imports."
    )
    parser.add_argument("jsonl_path", type=Path)
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args(argv)

    counts = summarize_jsonl(args.jsonl_path)
    sys.stdout.write(json.dumps({"dry_run": True, "counts": counts}, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
