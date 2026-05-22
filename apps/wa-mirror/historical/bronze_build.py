"""Bronze layer — immutable raw archive + SHA-256 manifest for the WhatsApp historical corpus.

Medallion F1 (spec 2026-05-23-chat-data-intelligence-nuzantara.md). NO LLM, NO PII processing:
walks the corpus, hashes every file, emits a manifest. Safe to run before the F0 legal gate.

Usage:
    python3 bronze_build.py --roots <dir>... --out manifest.jsonl [--copy <dest>]

Output: JSONL manifest, one row per file:
    {path, sha256, size, ext, source_root, conv, mtime}
Dedup: identical sha256 across paths flagged in the summary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

_CHUNK = 1 << 20  # 1 MiB


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def conversation_of(path: str, root: str) -> str | None:
    """Best-effort: the 'WhatsApp Chat - X' folder a file belongs to, else None."""
    rel = os.path.relpath(path, root)
    for part in rel.split(os.sep):
        if part.startswith("WhatsApp Chat - "):
            return part[len("WhatsApp Chat - ") :]
    return None


def walk_corpus(roots: list[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for root in roots:
        root = os.path.expanduser(root)
        if not os.path.isdir(root):
            print(f"WARN: root not a dir, skipping: {root}", file=sys.stderr)
            continue
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if fn == ".DS_Store":
                    continue
                out.append((os.path.join(dirpath, fn), root))
    return out


def build(roots: list[str], out_path: str, copy_dest: str | None = None) -> dict:
    files = walk_corpus(roots)
    by_hash: dict[str, list[str]] = defaultdict(list)
    ext_counter: Counter[str] = Counter()
    total_bytes = 0
    rows_written = 0

    with open(out_path, "w") as out_fh:
        for path, root in files:
            try:
                st = os.stat(path)
                digest = sha256_file(path)
            except OSError as exc:
                print(f"WARN: cannot read {path}: {exc}", file=sys.stderr)
                continue
            ext = os.path.splitext(path)[1].lower().lstrip(".") or "(none)"
            row = {
                "path": path,
                "sha256": digest,
                "size": st.st_size,
                "ext": ext,
                "source_root": root,
                "conv": conversation_of(path, root),
                "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            }
            out_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows_written += 1
            by_hash[digest].append(path)
            ext_counter[ext] += 1
            total_bytes += st.st_size

            if copy_dest:
                # immutable copy keyed by hash prefix (content-addressed, dedup-free)
                sub = os.path.join(copy_dest, digest[:2])
                os.makedirs(sub, exist_ok=True)
                target = os.path.join(sub, f"{digest}{os.path.splitext(path)[1].lower()}")
                if not os.path.exists(target):
                    import shutil

                    shutil.copy2(path, target)
                    os.chmod(target, 0o444)  # read-only = immutable intent

    dupes = {h: ps for h, ps in by_hash.items() if len(ps) > 1}
    summary = {
        "files_total": len(files),
        "rows_written": rows_written,
        "unique_sha256": len(by_hash),
        "duplicate_groups": len(dupes),
        "duplicate_files": sum(len(ps) for ps in dupes.values()),
        "total_bytes": total_bytes,
        "by_ext": dict(ext_counter.most_common()),
        "manifest": out_path,
    }
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--copy", default=None, help="optional content-addressed immutable copy dest")
    args = ap.parse_args()

    summary = build(args.roots, args.out, args.copy)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
