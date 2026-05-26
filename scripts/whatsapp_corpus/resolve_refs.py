from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from scripts.whatsapp_corpus.build_registry import (
    DEFAULT_CORPUS_ROOT,
    iter_chat_files,
    path_hash,
    source_tag,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileRef:
    file_id: str
    source: str
    source_tag: str | None
    path_hash: str
    path: Path


def build_file_refs(root: Path) -> list[FileRef]:
    """Build local file references using the same ordering as the registry."""
    files = iter_chat_files(root)
    width = max(4, len(str(len(files))))
    refs: list[FileRef] = []
    for index, path in enumerate(files, start=1):
        refs.append(
            FileRef(
                file_id=f"wa-file-{index:0{width}d}",
                source=path.relative_to(root).parts[0],
                source_tag=source_tag(root, path),
                path_hash=path_hash(root, path),
                path=path,
            )
        )
    return refs


def filter_refs(
    refs: list[FileRef],
    *,
    file_ids: set[str],
    path_hashes: set[str],
    source_tags: set[str],
) -> list[FileRef]:
    """Filter local refs by explicit identifiers."""
    return [
        ref
        for ref in refs
        if (file_ids and ref.file_id in file_ids)
        or (path_hashes and ref.path_hash in path_hashes)
        or (source_tags and ref.source_tag in source_tags)
    ]


def write_table(rows: list[FileRef]) -> None:
    """Write local refs as TSV to stdout."""
    writer = csv.writer(sys.stdout, delimiter="\t")
    writer.writerow(["file_id", "source", "source_tag", "path_hash", "path"])
    for row in rows:
        writer.writerow(
            [
                row.file_id,
                row.source,
                row.source_tag or "",
                row.path_hash,
                row.path.as_posix(),
            ]
        )


def write_jsonl(rows: list[FileRef]) -> None:
    """Write local refs as JSONL to stdout."""
    for row in rows:
        sys.stdout.write(
            json.dumps(
                {
                    "file_id": row.file_id,
                    "source": row.source,
                    "source_tag": row.source_tag,
                    "path_hash": row.path_hash,
                    "path": row.path.as_posix(),
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Resolve privacy-safe WhatsApp file refs to local raw paths."
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_CORPUS_ROOT, help="Corpus root path.")
    parser.add_argument(
        "--file-id",
        action="append",
        default=[],
        help="File ID to resolve. Can be repeated.",
    )
    parser.add_argument(
        "--path-hash",
        action="append",
        default=[],
        help="Path hash to resolve. Can be repeated.",
    )
    parser.add_argument(
        "--source-tag",
        action="append",
        default=[],
        help="Hashed ZIP source tag to resolve. Can be repeated.",
    )
    parser.add_argument(
        "--format",
        choices=("tsv", "jsonl"),
        default="tsv",
        help="Output format for stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)
    root = args.root.expanduser().resolve()
    if not root.exists():
        LOGGER.error("Corpus root does not exist: %s", root)
        return 2
    if not root.is_dir():
        LOGGER.error("Corpus root is not a directory: %s", root)
        return 2

    file_ids = set(args.file_id)
    path_hashes = set(args.path_hash)
    source_tags = set(args.source_tag)
    if not file_ids and not path_hashes and not source_tags:
        LOGGER.error("Refuse to dump all paths. Provide --file-id, --path-hash, or --source-tag.")
        return 2

    rows = filter_refs(
        build_file_refs(root),
        file_ids=file_ids,
        path_hashes=path_hashes,
        source_tags=source_tags,
    )
    if args.format == "jsonl":
        write_jsonl(rows)
    else:
        write_table(rows)
    LOGGER.info("Resolved %d refs.", len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
