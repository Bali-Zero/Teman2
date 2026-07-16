#!/usr/bin/env python3
"""vault_manifest.py — Batch-0 vault compiler: deterministic sha256 manifest.

Walks <vault-root> and emits a sorted, deterministic JSON manifest —
[{rel_path, sha256, bytes, source_url?, fetched_at?}, ...] — merging
per-file provenance from every `fetch-log.jsonl` found under the vault
(each fetcher writes its own `rel_path` field, so the merge is an exact
key match, no path reconstruction/guessing).

This is THE compiler that will eventually write data/kbli-filiera/manifest/
in the repo (guard-protected, infra/claude-hooks/data-plane-registry.json)
— for now it only supports `--out <any path>`; this PR does not commit a
generated manifest (per the batch-0 mandate).

Determinism (G16-adjacent, "reproducibility gate"): entries are sorted by
rel_path and every dict is built with a fixed key order, so the SAME vault
tree always produces byte-identical output regardless of filesystem walk
order.

Absences never enter the manifest — they don't produce a file (P3/no
"empty file pretending to be data"), so there is nothing on disk to hash.

Usage:
    python scripts/kbli_filiera/vault_manifest.py --vault-root PATH [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from kbli_filiera import vault_common as common
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from kbli_filiera import vault_common as common

LOG_FILE_NAMES = {"fetch-log.jsonl", "absences.jsonl"}
LOG = common.setup_logger("vault_manifest")


def collect_provenance(vault_root: Path) -> dict[str, dict]:
    """rel_path -> {source_url, fetched_at}, built from every
    fetch-log.jsonl under the vault. Only clean 200 records with a
    `rel_path` contribute — an error record has no file on disk to merge
    onto."""
    provenance: dict[str, dict] = {}
    for log_path in sorted(vault_root.rglob("fetch-log.jsonl")):
        for rec in common.read_jsonl(log_path):
            rel_path = rec.get("rel_path")
            if not rel_path or rec.get("http_status") != 200:
                continue
            provenance[rel_path] = {
                "source_url": rec.get("url"),
                "fetched_at": rec.get("fetched_at"),
            }
    return provenance


def build_manifest(vault_root: Path) -> list[dict]:
    provenance = collect_provenance(vault_root)
    entries: list[dict] = []
    for path in vault_root.rglob("*"):
        if not path.is_file() or path.name in LOG_FILE_NAMES:
            continue
        rel_path = path.relative_to(vault_root).as_posix()
        entry: dict = {
            "rel_path": rel_path,
            "sha256": common.sha256_file(path),
            "bytes": path.stat().st_size,
        }
        prov = provenance.get(rel_path)
        if prov:
            entry["source_url"] = prov.get("source_url")
            entry["fetched_at"] = prov.get("fetched_at")
        entries.append(entry)
    entries.sort(key=lambda e: e["rel_path"])
    return entries


def render_manifest(entries: list[dict]) -> str:
    return json.dumps(entries, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault-root", type=Path, default=common.DEFAULT_VAULT_ROOT)
    ap.add_argument("--out", type=Path, default=None, help="write manifest here instead of stdout")
    args = ap.parse_args(argv)

    vault_root = args.vault_root.expanduser()
    if not vault_root.exists():
        LOG.error("vault root does not exist: %s", vault_root)
        return 2

    entries = build_manifest(vault_root)
    payload = render_manifest(entries)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
        LOG.info("wrote %s entries to %s", len(entries), args.out)
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
