from __future__ import annotations

import argparse
import csv
import json
import logging
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from scripts.whatsapp_corpus.build_registry import DEFAULT_CORPUS_ROOT
from scripts.whatsapp_corpus.classify_chats import DEFAULT_OUTPUT_DIR as DEFAULT_CLASSIFICATION_DIR
from scripts.whatsapp_corpus.resolve_refs import FileRef, build_file_refs

LOGGER = logging.getLogger(__name__)

DEFAULT_CLASSIFICATION_DB = DEFAULT_CLASSIFICATION_DIR / "chat_classification.sqlite"
DEFAULT_OUTPUT_DIR = Path("research/personal/wa-corpus/review")
DEFAULT_LIMIT = 80


@dataclass(frozen=True)
class ClassifiedRow:
    file_id: str
    source: str
    source_tag: str | None
    path_hash: str
    message_start_count: int
    normalized_message_start_count: int
    min_timestamp: str | None
    max_timestamp: str | None
    classification_label: str
    privacy_tier: str
    processing_gate: str
    confidence: float
    review_required: bool
    evidence_codes: tuple[str, ...]
    warning_codes: tuple[str, ...]


@dataclass(frozen=True)
class ReviewManifestRow:
    rank: int
    classified: ClassifiedRow
    local_path: Path | None
    resolution_status: str


def decode_json_list(value: str | None) -> tuple[str, ...]:
    """Decode a JSON string list from SQLite."""
    if not value:
        return ()
    loaded = json.loads(value)
    if not isinstance(loaded, list):
        raise ValueError("expected JSON list")
    return tuple(str(item) for item in loaded)


def read_classified_rows(classification_db: Path) -> list[ClassifiedRow]:
    """Read classified chat rows from the local classification DB."""
    if not classification_db.exists():
        raise FileNotFoundError(f"Classification DB does not exist: {classification_db}")

    with sqlite3.connect(classification_db) as conn:
        rows = conn.execute(
            """
            SELECT file_id, source, source_tag, path_hash, message_start_count,
                   normalized_message_start_count, min_timestamp, max_timestamp,
                   classification_label, privacy_tier, processing_gate, confidence,
                   review_required, evidence_codes_json, warning_codes_json
            FROM classified_chats
            ORDER BY file_id
            """
        ).fetchall()

    return [
        ClassifiedRow(
            file_id=row[0],
            source=row[1],
            source_tag=row[2],
            path_hash=row[3],
            message_start_count=int(row[4]),
            normalized_message_start_count=int(row[5]),
            min_timestamp=row[6],
            max_timestamp=row[7],
            classification_label=row[8],
            privacy_tier=row[9],
            processing_gate=row[10],
            confidence=float(row[11]),
            review_required=bool(row[12]),
            evidence_codes=decode_json_list(row[13]),
            warning_codes=decode_json_list(row[14]),
        )
        for row in rows
    ]


def select_review_rows(
    rows: Iterable[ClassifiedRow],
    *,
    limit: int,
    gates: set[str],
    labels: set[str],
    sources: set[str] | None = None,
) -> list[ClassifiedRow]:
    """Select the highest-volume rows requiring owner review."""
    source_filter = sources or set()
    selected = [
        row
        for row in rows
        if row.review_required
        and (not gates or row.processing_gate in gates)
        and (not labels or row.classification_label in labels)
        and (not source_filter or row.source in source_filter)
    ]
    return sorted(
        selected,
        key=lambda row: (row.message_start_count, row.normalized_message_start_count, row.file_id),
        reverse=True,
    )[:limit]


def file_ref_index(refs: Iterable[FileRef]) -> dict[str, FileRef]:
    """Index resolved local file refs by file ID."""
    return {ref.file_id: ref for ref in refs}


def build_manifest_rows(
    *,
    selected_rows: list[ClassifiedRow],
    refs_by_file_id: dict[str, FileRef],
) -> list[ReviewManifestRow]:
    """Attach local paths to selected classification rows."""
    manifest_rows: list[ReviewManifestRow] = []
    for rank, row in enumerate(selected_rows, start=1):
        ref = refs_by_file_id.get(row.file_id)
        if ref is None:
            manifest_rows.append(
                ReviewManifestRow(
                    rank=rank,
                    classified=row,
                    local_path=None,
                    resolution_status="missing_file_ref",
                )
            )
            continue
        if ref.path_hash != row.path_hash:
            manifest_rows.append(
                ReviewManifestRow(
                    rank=rank,
                    classified=row,
                    local_path=ref.path,
                    resolution_status="path_hash_mismatch",
                )
            )
            continue
        manifest_rows.append(
            ReviewManifestRow(
                rank=rank,
                classified=row,
                local_path=ref.path,
                resolution_status="resolved",
            )
        )
    return manifest_rows


def write_private_manifest(path: Path, rows: list[ReviewManifestRow]) -> None:
    """Write the raw-path owner review manifest. This file must stay ignored."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "rank",
                "file_id",
                "source",
                "source_tag",
                "path_hash",
                "classification_label",
                "privacy_tier",
                "processing_gate",
                "message_start_count",
                "normalized_message_start_count",
                "min_timestamp",
                "max_timestamp",
                "confidence",
                "resolution_status",
                "local_path",
                "evidence_codes",
                "warning_codes",
                "owner_decision",
                "owner_notes",
            ]
        )
        for row in rows:
            classified = row.classified
            writer.writerow(
                [
                    row.rank,
                    classified.file_id,
                    classified.source,
                    classified.source_tag or "",
                    classified.path_hash,
                    classified.classification_label,
                    classified.privacy_tier,
                    classified.processing_gate,
                    classified.message_start_count,
                    classified.normalized_message_start_count,
                    classified.min_timestamp or "",
                    classified.max_timestamp or "",
                    f"{classified.confidence:.2f}",
                    row.resolution_status,
                    row.local_path.as_posix() if row.local_path else "",
                    ",".join(classified.evidence_codes),
                    ",".join(classified.warning_codes),
                    "",
                    "",
                ]
            )


def summarize_counter(
    rows: Iterable[ReviewManifestRow],
    key_name: str,
) -> Counter[str]:
    """Count rows by a ClassifiedRow attribute."""
    counts: Counter[str] = Counter()
    for row in rows:
        counts.update([str(getattr(row.classified, key_name))])
    return counts


def write_safe_summary(
    *,
    summary_path: Path,
    classification_db: Path,
    private_manifest_path: Path,
    selected_rows: list[ReviewManifestRow],
    total_review_required: int,
) -> None:
    """Write tracked review summary without raw paths or raw names."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    resolved = sum(1 for row in selected_rows if row.resolution_status == "resolved")
    total_starts = sum(row.classified.message_start_count for row in selected_rows)
    total_normalized = sum(row.classified.normalized_message_start_count for row in selected_rows)
    status_counts = Counter(row.resolution_status for row in selected_rows)
    gate_counts = summarize_counter(selected_rows, "processing_gate")
    label_counts = summarize_counter(selected_rows, "classification_label")

    lines: list[str] = [
        "# WhatsApp Review Manifest Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Input classification DB: `{classification_db.as_posix()}`",
        f"Private local manifest: `{private_manifest_path.as_posix()}`",
        "",
        "## Privacy Mode",
        "",
        "- This tracked summary contains no raw message text.",
        "- This tracked summary contains no message snippets.",
        "- This tracked summary contains no phone numbers.",
        "- This tracked summary contains no raw source paths.",
        "- This tracked summary contains no raw contact names.",
        "- The private `.local.tsv` manifest contains raw local paths and is ignored by git.",
        "",
        "## Scope",
        "",
        "- The manifest is for owner review only.",
        "- The goal is to create a local allowlist/denylist before content mining.",
        "- Rows are ordered by baseline message-start volume.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Total review-required chats in classification DB | {total_review_required} |",
        f"| Rows selected for this private manifest | {len(selected_rows)} |",
        f"| Rows resolved to local paths | {resolved} |",
        f"| Baseline message-start records in selected rows | {total_starts} |",
        f"| Normalized message-start records in selected rows | {total_normalized} |",
        "",
        "## Resolution Status",
        "",
        "| Status | Rows |",
        "|---|---:|",
    ]
    for status, count in status_counts.most_common():
        lines.append(f"| {status} | {count} |")

    lines.extend(
        [
            "",
            "## Selected Gates",
            "",
            "| Gate | Rows |",
            "|---|---:|",
        ]
    )
    for gate, count in gate_counts.most_common():
        lines.append(f"| {gate} | {count} |")

    lines.extend(
        [
            "",
            "## Selected Labels",
            "",
            "| Label | Rows |",
            "|---|---:|",
        ]
    )
    for label, count in label_counts.most_common():
        lines.append(f"| {label} | {count} |")

    lines.extend(
        [
            "",
            "## Owner Decision Values",
            "",
            "Use these values in the private manifest `owner_decision` column:",
            "",
            "| Decision | Meaning |",
            "|---|---|",
            "| `allow_team_local` | Team archive can be analyzed locally after explicit scope selection. |",
            "| `allow_business_local` | Business/client archive can be analyzed locally for Bali Zero use cases. |",
            "| `deny_personal` | Personal/family/private archive stays excluded from content mining. |",
            "| `deny_sensitive` | Sensitive archive stays excluded except for legal/forensic owner-directed use. |",
            "| `unknown_hold` | Do not use until more review is done. |",
            "",
            "## Next Command",
            "",
            "```bash",
            "source .venv/bin/activate",
            "PYTHONPATH=. python -m scripts.whatsapp_corpus.build_review_manifest \\",
            "  --root \"$HOME/Desktop/wa-chats-MASTER-2026-05-26\" \\",
            "  --classification-db research/personal/wa-corpus/classification/chat_classification.sqlite \\",
            "  --output-dir research/personal/wa-corpus/review \\",
            "  --limit 80",
            "```",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_review_manifest(
    *,
    root: Path,
    classification_db: Path,
    private_manifest_path: Path,
    summary_path: Path,
    limit: int,
    gates: set[str],
    labels: set[str],
    sources: set[str] | None = None,
) -> list[ReviewManifestRow]:
    """Build the private review manifest and safe tracked summary."""
    classified_rows = read_classified_rows(classification_db)
    selected = select_review_rows(
        classified_rows,
        limit=limit,
        gates=gates,
        labels=labels,
        sources=sources,
    )
    refs_by_file_id = file_ref_index(build_file_refs(root))
    manifest_rows = build_manifest_rows(
        selected_rows=selected,
        refs_by_file_id=refs_by_file_id,
    )
    write_private_manifest(private_manifest_path, manifest_rows)
    write_safe_summary(
        summary_path=summary_path,
        classification_db=classification_db,
        private_manifest_path=private_manifest_path,
        selected_rows=manifest_rows,
        total_review_required=sum(1 for row in classified_rows if row.review_required),
    )
    return manifest_rows


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Build an ignored local review manifest for WhatsApp chat classification."
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_CORPUS_ROOT, help="Corpus root path.")
    parser.add_argument(
        "--classification-db",
        type=Path,
        default=DEFAULT_CLASSIFICATION_DB,
        help="Path to chat_classification.sqlite produced by classify_chats.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for review manifest outputs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Maximum number of review rows to place in the private manifest.",
    )
    parser.add_argument(
        "--gate",
        action="append",
        default=[],
        help="Optional processing_gate filter. Can be repeated.",
    )
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        help="Optional classification_label filter. Can be repeated.",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Optional source filter. Can be repeated.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)
    root = args.root.expanduser().resolve()
    classification_db = args.classification_db
    output_dir = args.output_dir

    if not root.exists():
        LOGGER.error("Corpus root does not exist: %s", root)
        return 2
    if not root.is_dir():
        LOGGER.error("Corpus root is not a directory: %s", root)
        return 2
    try:
        rows = build_review_manifest(
            root=root,
            classification_db=classification_db,
            private_manifest_path=output_dir / "review_manifest.local.tsv",
            summary_path=output_dir / "review_manifest_summary.md",
            limit=args.limit,
            gates=set(args.gate),
            labels=set(args.label),
            sources=set(args.source),
        )
    except FileNotFoundError as exc:
        LOGGER.error("%s", exc)
        return 2

    LOGGER.info("Wrote %d private review rows.", len(rows))
    LOGGER.info("Wrote %s", output_dir / "review_manifest.local.tsv")
    LOGGER.info("Wrote %s", output_dir / "review_manifest_summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
