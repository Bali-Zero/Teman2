#!/usr/bin/env python3
"""decertify_editorial_entries.py — sanctioned compiler for removing entries
from data/kbli-filiera/pma-editorial-certifications.json's canonicalIntel/
mouthGold/standaloneGold sections (data_plane_guard: the registry is
compiled, hand-edits are refused; this is the compiler).

Spec: JSON {"entries": [{"section", "code", "reason",
"expected_content_sha256"}, ...]}. `expected_content_sha256` is the PREMISE —
refuses (exit 2) unless the registry's live contentSha256 matches exactly,
so drift is never removed blind. A code already absent from an existing
section is an idempotent no-op (exit 0). An unknown `section` name always
refuses. Never touches sourceDatasetSha256/reviewedAt or an unlisted entry.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REGISTRY = Path("data/kbli-filiera/pma-editorial-certifications.json")


def run(spec_path: Path, apply: bool, registry_path: Path = REGISTRY) -> int:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    changed = False
    for entry in spec["entries"]:
        section, code = entry["section"], entry["code"]
        if section not in registry:
            print(f"REFUSE: unknown registry section {section!r}", file=sys.stderr)
            return 2
        current = registry[section].get(code)
        if current is None:
            print(f"no-op: {section}/{code} is already de-certified")
            continue
        actual = current.get("contentSha256")
        expected = entry["expected_content_sha256"]
        if actual != expected:
            print(f"REFUSE: {section}/{code} drifted (expected {expected}, found {actual})", file=sys.stderr)
            return 2
        verb = "apply" if apply else "check"
        print(f"{verb}: de-certify {section}/{code} — {entry['reason']}")
        if apply:
            del registry[section][code]
            changed = True
    if apply and changed:
        registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="dry run (default)")
    group.add_argument("--apply", action="store_true", help="mutate the registry")
    args = parser.parse_args(argv)
    return run(args.spec, apply=args.apply, registry_path=args.registry)


if __name__ == "__main__":
    raise SystemExit(main())
