from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

DEFAULT_ANALYSIS_DIR = Path("research/personal/wa-corpus/analysis")
DEFAULT_INPUT_DB = DEFAULT_ANALYSIS_DIR / "allowed_case_windows.local.sqlite"
DEFAULT_OUTPUT_TSV = DEFAULT_ANALYSIS_DIR / "allowed_case_window_review.local.tsv"
DEFAULT_SUMMARY = DEFAULT_ANALYSIS_DIR / "allowed_case_window_review_summary.md"
ALLOWED_INPUT_DB_NAME = "allowed_case_windows.local.sqlite"


@dataclass(frozen=True)
class CaseWindowRow:
    window_id: str
    file_id: str
    window_ordinal: int
    first_month: str
    last_month: str
    first_message_index: int
    last_message_index: int
    event_count: int
    message_count: int
    domain_count: int
    dominant_domain: str
    severity_high_count: int
    top_event_codes_json: str


@dataclass(frozen=True)
class ReviewQueueRow:
    rank: int
    window: CaseWindowRow
    review_score: int
    review_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ReviewQueueIndex:
    windows: list[CaseWindowRow]
    queue_rows: list[ReviewQueueRow]


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    if db_path.name != ALLOWED_INPUT_DB_NAME:
        raise ValueError(f"Refusing to read unexpected input artifact: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"Input DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_windows(db_path: Path) -> list[CaseWindowRow]:
    """Read aggregate-safe case windows from the derived local SQLite."""
    with _connect_readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT window_id, file_id, window_ordinal, first_month, last_month,
                   first_message_index, last_message_index, event_count,
                   message_count, domain_count, dominant_domain,
                   severity_high_count, top_event_codes_json
            FROM case_windows
            ORDER BY severity_high_count DESC, event_count DESC, message_count DESC,
                     domain_count DESC, file_id, window_ordinal
            """
        ).fetchall()

    return [
        CaseWindowRow(
            window_id=str(row["window_id"]),
            file_id=str(row["file_id"]),
            window_ordinal=int(row["window_ordinal"]),
            first_month=str(row["first_month"]),
            last_month=str(row["last_month"]),
            first_message_index=int(row["first_message_index"]),
            last_message_index=int(row["last_message_index"]),
            event_count=int(row["event_count"]),
            message_count=int(row["message_count"]),
            domain_count=int(row["domain_count"]),
            dominant_domain=str(row["dominant_domain"]),
            severity_high_count=int(row["severity_high_count"]),
            top_event_codes_json=str(row["top_event_codes_json"]),
        )
        for row in rows
    ]


def review_reasons(window: CaseWindowRow) -> tuple[str, ...]:
    reasons: list[str] = []
    if window.severity_high_count > 0:
        reasons.append("high_severity")
    if window.domain_count >= 3:
        reasons.append("multi_domain")
    if window.message_count >= 25:
        reasons.append("large_window")
    if window.event_count >= 50:
        reasons.append("high_event_volume")
    if window.first_month != window.last_month:
        reasons.append("cross_month")
    if window.dominant_domain == "followup_risk":
        reasons.append("followup_dominant")
    if window.dominant_domain == "document_requirement":
        reasons.append("document_dominant")
    if window.dominant_domain == "immigration_lifecycle":
        reasons.append("lifecycle_dominant")
    if window.dominant_domain == "tax_payment":
        reasons.append("tax_dominant")
    return tuple(reasons)


def review_score(window: CaseWindowRow) -> int:
    return (
        window.severity_high_count * 10
        + window.event_count
        + window.message_count
        + window.domain_count * 4
        + (20 if window.first_month != window.last_month else 0)
    )


def build_queue(windows: list[CaseWindowRow], *, limit: int) -> list[ReviewQueueRow]:
    """Select the highest-value windows for local owner review."""
    queue_windows = [
        window
        for window in windows
        if window.severity_high_count > 0
        or window.domain_count >= 3
        or window.message_count >= 25
        or window.event_count >= 50
        or window.first_month != window.last_month
    ]
    queue_windows = sorted(
        queue_windows,
        key=lambda window: (
            -review_score(window),
            -window.severity_high_count,
            -window.event_count,
            -window.message_count,
            -window.domain_count,
            window.file_id,
            window.window_ordinal,
        ),
    )[:limit]

    return [
        ReviewQueueRow(
            rank=rank,
            window=window,
            review_score=review_score(window),
            review_reasons=review_reasons(window),
        )
        for rank, window in enumerate(queue_windows, start=1)
    ]


def build_case_window_review_queue(
    *,
    input_db: Path,
    output_tsv: Path,
    summary_path: Path,
    limit: int = 100,
) -> ReviewQueueIndex:
    """Build a local-only review queue from case windows."""
    windows = read_windows(input_db)
    queue_rows = build_queue(windows, limit=limit)
    write_tsv(output_tsv=output_tsv, queue_rows=queue_rows)
    write_summary(
        summary_path=summary_path,
        input_db=input_db,
        windows=windows,
        queue_rows=queue_rows,
    )
    return ReviewQueueIndex(windows=windows, queue_rows=queue_rows)


def write_tsv(*, output_tsv: Path, queue_rows: list[ReviewQueueRow]) -> None:
    """Write the ignored local review queue TSV."""
    output_tsv.parent.mkdir(parents=True, exist_ok=True)
    with output_tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "rank",
                "window_id",
                "file_id",
                "window_ordinal",
                "first_month",
                "last_month",
                "first_message_index",
                "last_message_index",
                "event_count",
                "message_count",
                "domain_count",
                "dominant_domain",
                "severity_high_count",
                "review_score",
                "review_reasons",
                "top_event_codes_json",
            ]
        )
        for row in queue_rows:
            window = row.window
            writer.writerow(
                [
                    row.rank,
                    window.window_id,
                    window.file_id,
                    window.window_ordinal,
                    window.first_month,
                    window.last_month,
                    window.first_message_index,
                    window.last_message_index,
                    window.event_count,
                    window.message_count,
                    window.domain_count,
                    window.dominant_domain,
                    window.severity_high_count,
                    row.review_score,
                    ",".join(row.review_reasons),
                    window.top_event_codes_json,
                ]
            )


def write_summary(
    *,
    summary_path: Path,
    input_db: Path,
    windows: list[CaseWindowRow],
    queue_rows: list[ReviewQueueRow],
) -> None:
    """Write a tracked aggregate summary for the case-window review queue."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    total_windows = len(windows)
    queue_count = len(queue_rows)
    selected_message_count = sum(row.window.message_count for row in queue_rows)
    selected_event_count = sum(row.window.event_count for row in queue_rows)
    selected_high_count = sum(row.window.severity_high_count for row in queue_rows)
    reason_counts = Counter(
        reason for row in queue_rows for reason in row.review_reasons
    )
    domain_counts = Counter(row.window.dominant_domain for row in queue_rows)
    size_counts = Counter(
        bucket_for_size(row.window.message_count) for row in queue_rows
    )

    lines = [
        "# WhatsApp Case Window Review Queue Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Input case-window SQLite artifact: `{input_db.name}`",
        "",
        "## Privacy Mode",
        "",
        "- This tracked summary contains no raw message text.",
        "- This tracked summary contains no message snippets.",
        "- This tracked summary contains no phone numbers or emails.",
        "- This tracked summary contains no raw source paths or raw extracted values.",
        "- The ignored local TSV contains anonymous window IDs and local aggregate metadata only.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Total windows | {total_windows} |",
        f"| Queue windows | {queue_count} |",
        f"| Queue messages | {selected_message_count} |",
        f"| Queue events | {selected_event_count} |",
        f"| High severity events in queue | {selected_high_count} |",
        "",
        "## Review Reason Counts",
        "",
        "| Reason | Windows |",
        "|---|---:|",
    ]
    for reason, count in reason_counts.most_common():
        lines.append(f"| {reason} | {count} |")

    lines.extend(
        [
            "",
            "## Queue Dominant Domains",
            "",
            "| Domain | Windows |",
            "|---|---:|",
        ]
    )
    for domain, count in domain_counts.most_common():
        lines.append(f"| {domain} | {count} |")

    lines.extend(
        [
            "",
            "## Queue Window Size Buckets",
            "",
            "| Message count bucket | Windows |",
            "|---|---:|",
        ]
    )
    for bucket, count in size_counts.items():
        lines.append(f"| {bucket} | {count} |")

    lines.extend(
        [
            "",
            "## Operational Reading",
            "",
            "- Use the ignored TSV as a manual triage queue for dense local windows.",
            "- Review reasons are heuristic signals, not a legal or client-side conclusion.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def bucket_for_size(value: int) -> str:
    if value == 1:
        return "1"
    if value <= 5:
        return "2-5"
    if value <= 10:
        return "6-10"
    if value <= 25:
        return "11-25"
    if value <= 50:
        return "26-50"
    if value <= 100:
        return "51-100"
    return "101+"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an anonymous local review queue from case windows."
    )
    parser.add_argument("--input-db", type=Path, default=DEFAULT_INPUT_DB)
    parser.add_argument("--output-tsv", type=Path, default=DEFAULT_OUTPUT_TSV)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable counts."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        index = build_case_window_review_queue(
            input_db=args.input_db,
            output_tsv=args.output_tsv,
            summary_path=args.summary,
            limit=args.limit,
        )
    except (FileNotFoundError, ValueError, sqlite3.DatabaseError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    if args.json:
        json.dump(
            {
                "input_windows": len(index.windows),
                "queue_windows": len(index.queue_rows),
                "output_tsv": str(args.output_tsv),
                "summary": str(args.summary),
            },
            sys.stdout,
            sort_keys=True,
        )
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
