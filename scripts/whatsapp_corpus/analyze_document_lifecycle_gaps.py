from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

DEFAULT_ANALYSIS_DIR = Path("research/personal/wa-corpus/analysis")
DEFAULT_EVENTS_DB = DEFAULT_ANALYSIS_DIR / "allowed_domain_events.local.sqlite"
DEFAULT_OUTPUT_DB = (
    DEFAULT_ANALYSIS_DIR / "allowed_document_lifecycle_gaps.local.sqlite"
)
DEFAULT_SUMMARY = DEFAULT_ANALYSIS_DIR / "allowed_document_lifecycle_gaps_summary.md"
ALLOWED_EVENTS_DB_NAME = "allowed_domain_events.local.sqlite"

DOCUMENT_DOMAIN = "document_requirement"
LIFECYCLE_DOMAIN = "immigration_lifecycle"


@dataclass(frozen=True)
class EventRow:
    domain_code: str
    event_code: str
    file_id: str
    message_index: int
    month: str


@dataclass(frozen=True)
class GapAnalysis:
    events: list[EventRow]
    lifecycle_message_count: int
    document_message_count: int
    overlap_message_count: int
    stage_coverage: list[tuple[str, int, int, int, float]]
    document_coverage: list[tuple[str, int, int, int, float]]
    stage_document_matrix: list[tuple[str, str, int, int]]
    month_stage_gaps: list[tuple[str, str, int, int, int]]


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    if db_path.name != ALLOWED_EVENTS_DB_NAME:
        raise ValueError(f"Refusing to read unexpected input artifact: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"Input DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_events(db_path: Path) -> list[EventRow]:
    """Read aggregate-safe domain events only."""
    with _connect_readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT domain_code, event_code, file_id, message_index, month
            FROM domain_events
            WHERE domain_code IN (?, ?)
            ORDER BY file_id, message_index, domain_code, event_code
            """,
            (DOCUMENT_DOMAIN, LIFECYCLE_DOMAIN),
        ).fetchall()
    return [
        EventRow(
            domain_code=str(row["domain_code"]),
            event_code=str(row["event_code"]),
            file_id=str(row["file_id"]),
            message_index=int(row["message_index"]),
            month=str(row["month"]),
        )
        for row in rows
    ]


def _message_key(event: EventRow) -> tuple[str, int]:
    return (event.file_id, event.message_index)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def analyze_events(events: Sequence[EventRow]) -> GapAnalysis:
    """Build aggregate document/lifecycle coverage matrices."""
    lifecycle_by_message: dict[tuple[str, int], set[str]] = defaultdict(set)
    document_by_message: dict[tuple[str, int], set[str]] = defaultdict(set)
    month_by_message: dict[tuple[str, int], str] = {}
    file_by_message: dict[tuple[str, int], str] = {}

    for event in events:
        key = _message_key(event)
        month_by_message.setdefault(key, event.month)
        file_by_message.setdefault(key, event.file_id)
        if event.domain_code == LIFECYCLE_DOMAIN:
            lifecycle_by_message[key].add(event.event_code)
        elif event.domain_code == DOCUMENT_DOMAIN:
            document_by_message[key].add(event.event_code)

    lifecycle_messages = set(lifecycle_by_message)
    document_messages = set(document_by_message)
    overlap_messages = lifecycle_messages.intersection(document_messages)

    lifecycle_stage_messages: dict[str, set[tuple[str, int]]] = defaultdict(set)
    lifecycle_stage_document_messages: dict[str, set[tuple[str, int]]] = defaultdict(
        set
    )
    document_messages_by_code: dict[str, set[tuple[str, int]]] = defaultdict(set)
    document_with_lifecycle_by_code: dict[str, set[tuple[str, int]]] = defaultdict(set)
    matrix_messages: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(set)
    matrix_files: dict[tuple[str, str], set[str]] = defaultdict(set)
    month_stage_messages: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(set)
    month_stage_doc_messages: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(
        set
    )

    for key, lifecycle_codes in lifecycle_by_message.items():
        document_codes = document_by_message.get(key, set())
        month = month_by_message.get(key, "unknown")
        file_id = file_by_message.get(key, "")
        for stage in lifecycle_codes:
            lifecycle_stage_messages[stage].add(key)
            month_stage_messages[(month, stage)].add(key)
            if document_codes:
                lifecycle_stage_document_messages[stage].add(key)
                month_stage_doc_messages[(month, stage)].add(key)
            for document_code in document_codes:
                matrix_messages[(stage, document_code)].add(key)
                matrix_files[(stage, document_code)].add(file_id)

    for key, document_codes in document_by_message.items():
        has_lifecycle = key in lifecycle_by_message
        for document_code in document_codes:
            document_messages_by_code[document_code].add(key)
            if has_lifecycle:
                document_with_lifecycle_by_code[document_code].add(key)

    stage_coverage = sorted(
        (
            (
                stage,
                len(messages),
                len(lifecycle_stage_document_messages[stage]),
                len(messages) - len(lifecycle_stage_document_messages[stage]),
                _ratio(len(lifecycle_stage_document_messages[stage]), len(messages)),
            )
            for stage, messages in lifecycle_stage_messages.items()
        ),
        key=lambda row: (-row[2], row[0]),
    )
    document_coverage = sorted(
        (
            (
                document_code,
                len(messages),
                len(document_with_lifecycle_by_code[document_code]),
                len(messages) - len(document_with_lifecycle_by_code[document_code]),
                _ratio(
                    len(document_with_lifecycle_by_code[document_code]), len(messages)
                ),
            )
            for document_code, messages in document_messages_by_code.items()
        ),
        key=lambda row: (-row[2], row[0]),
    )
    stage_document_matrix = sorted(
        (
            (
                stage,
                document_code,
                len(messages),
                len(matrix_files[(stage, document_code)]),
            )
            for (stage, document_code), messages in matrix_messages.items()
        ),
        key=lambda row: (-row[2], row[0], row[1]),
    )
    month_stage_gaps = sorted(
        (
            (
                month,
                stage,
                len(messages),
                len(month_stage_doc_messages[(month, stage)]),
                len(messages) - len(month_stage_doc_messages[(month, stage)]),
            )
            for (month, stage), messages in month_stage_messages.items()
        ),
        key=lambda row: (-row[4], row[0], row[1]),
    )

    return GapAnalysis(
        events=list(events),
        lifecycle_message_count=len(lifecycle_messages),
        document_message_count=len(document_messages),
        overlap_message_count=len(overlap_messages),
        stage_coverage=stage_coverage,
        document_coverage=document_coverage,
        stage_document_matrix=stage_document_matrix,
        month_stage_gaps=month_stage_gaps,
    )


def write_sqlite(*, output_db: Path, analysis: GapAnalysis) -> None:
    """Write ignored local gap matrix SQLite."""
    output_db.parent.mkdir(parents=True, exist_ok=True)
    if output_db.exists():
        output_db.unlink()
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            CREATE TABLE gap_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                event_rows_read INTEGER NOT NULL,
                lifecycle_message_count INTEGER NOT NULL,
                document_message_count INTEGER NOT NULL,
                overlap_message_count INTEGER NOT NULL
            );

            CREATE TABLE lifecycle_stage_document_coverage (
                stage_code TEXT PRIMARY KEY,
                lifecycle_message_count INTEGER NOT NULL,
                with_document_message_count INTEGER NOT NULL,
                without_document_message_count INTEGER NOT NULL,
                coverage_ratio REAL NOT NULL
            );

            CREATE TABLE document_lifecycle_coverage (
                document_code TEXT PRIMARY KEY,
                document_message_count INTEGER NOT NULL,
                with_lifecycle_message_count INTEGER NOT NULL,
                without_lifecycle_message_count INTEGER NOT NULL,
                coverage_ratio REAL NOT NULL
            );

            CREATE TABLE stage_document_matrix (
                stage_code TEXT NOT NULL,
                document_code TEXT NOT NULL,
                co_message_count INTEGER NOT NULL,
                file_count INTEGER NOT NULL,
                PRIMARY KEY (stage_code, document_code)
            );

            CREATE TABLE month_stage_gap_matrix (
                month TEXT NOT NULL,
                stage_code TEXT NOT NULL,
                lifecycle_message_count INTEGER NOT NULL,
                with_document_message_count INTEGER NOT NULL,
                without_document_message_count INTEGER NOT NULL,
                PRIMARY KEY (month, stage_code)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO gap_runs (
                id, generated_at_utc, privacy_mode, event_rows_read,
                lifecycle_message_count, document_message_count, overlap_message_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "local_only_domain_event_gap_matrix_no_raw_text_no_raw_values",
                len(analysis.events),
                analysis.lifecycle_message_count,
                analysis.document_message_count,
                analysis.overlap_message_count,
            ),
        )
        conn.executemany(
            """
            INSERT INTO lifecycle_stage_document_coverage (
                stage_code, lifecycle_message_count, with_document_message_count,
                without_document_message_count, coverage_ratio
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            analysis.stage_coverage,
        )
        conn.executemany(
            """
            INSERT INTO document_lifecycle_coverage (
                document_code, document_message_count, with_lifecycle_message_count,
                without_lifecycle_message_count, coverage_ratio
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            analysis.document_coverage,
        )
        conn.executemany(
            """
            INSERT INTO stage_document_matrix (
                stage_code, document_code, co_message_count, file_count
            )
            VALUES (?, ?, ?, ?)
            """,
            analysis.stage_document_matrix,
        )
        conn.executemany(
            """
            INSERT INTO month_stage_gap_matrix (
                month, stage_code, lifecycle_message_count,
                with_document_message_count, without_document_message_count
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            analysis.month_stage_gaps,
        )
        conn.commit()


def write_summary(
    *,
    summary_path: Path,
    events_db: Path,
    output_db: Path,
    analysis: GapAnalysis,
    summary_limit: int,
) -> None:
    """Write tracked aggregate-only markdown summary."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# WhatsApp Document Lifecycle Gap Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Input event SQLite artifact: `{events_db.name}`",
        f"Local gap SQLite artifact: `{output_db.name}`",
        "",
        "## Privacy Mode",
        "",
        "- This tracked summary contains no raw message text.",
        "- This tracked summary contains no message snippets.",
        "- This tracked summary contains no phone numbers or emails.",
        "- This tracked summary contains no raw source paths or raw extracted values.",
        "- This analyzer reads only the derived domain event index, not the raw parsed-message DB.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Event rows read | {len(analysis.events)} |",
        f"| Lifecycle messages | {analysis.lifecycle_message_count} |",
        f"| Document messages | {analysis.document_message_count} |",
        f"| Messages with lifecycle and document events | {analysis.overlap_message_count} |",
        "",
        "## Lifecycle Stage Document Coverage",
        "",
        "| Stage | Lifecycle messages | With document | Without document | Coverage ratio |",
        "|---|---:|---:|---:|---:|",
    ]
    for stage, lifecycle_count, with_doc, without_doc, ratio in analysis.stage_coverage:
        lines.append(
            f"| {stage} | {lifecycle_count} | {with_doc} | {without_doc} | {ratio:.3f} |"
        )

    lines.extend(
        [
            "",
            "## Document Coverage Against Lifecycle",
            "",
            "| Document code | Document messages | With lifecycle | Without lifecycle | Coverage ratio |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for (
        document_code,
        doc_count,
        with_lifecycle,
        without_lifecycle,
        ratio,
    ) in analysis.document_coverage:
        lines.append(
            f"| {document_code} | {doc_count} | {with_lifecycle} | {without_lifecycle} | {ratio:.3f} |"
        )

    lines.extend(
        [
            "",
            "## Top Stage x Document Co-Occurrence",
            "",
            "| Stage | Document code | Messages | Files |",
            "|---|---|---:|---:|",
        ]
    )
    for (
        stage,
        document_code,
        message_count,
        file_count,
    ) in analysis.stage_document_matrix[:summary_limit]:
        lines.append(f"| {stage} | {document_code} | {message_count} | {file_count} |")

    lines.extend(
        [
            "",
            "## Top Month x Stage Gaps",
            "",
            "| Month | Stage | Lifecycle messages | With document | Without document |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for (
        month,
        stage,
        lifecycle_count,
        with_doc,
        without_doc,
    ) in analysis.month_stage_gaps[:summary_limit]:
        lines.append(
            f"| {month} | {stage} | {lifecycle_count} | {with_doc} | {without_doc} |"
        )

    lines.extend(
        [
            "",
            "## Operational Reading",
            "",
            "- High `without_document_message_count` does not prove a missing document; it marks lifecycle-stage messages with no same-message document event.",
            "- Use the ignored local SQLite for anonymous review queues before changing operational process.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze_document_lifecycle_gaps(
    *,
    events_db: Path,
    output_db: Path,
    summary_path: Path,
    summary_limit: int = 25,
) -> GapAnalysis:
    """Analyze aggregate document/lifecycle coverage from domain events."""
    events = read_events(events_db)
    analysis = analyze_events(events)
    write_sqlite(output_db=output_db, analysis=analysis)
    write_summary(
        summary_path=summary_path,
        events_db=events_db,
        output_db=output_db,
        analysis=analysis,
        summary_limit=summary_limit,
    )
    return analysis


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze document/lifecycle coverage from local domain events."
    )
    parser.add_argument("--events-db", type=Path, default=DEFAULT_EVENTS_DB)
    parser.add_argument("--output-db", type=Path, default=DEFAULT_OUTPUT_DB)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--summary-limit", type=int, default=25)
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable counts."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        analysis = analyze_document_lifecycle_gaps(
            events_db=args.events_db,
            output_db=args.output_db,
            summary_path=args.summary,
            summary_limit=args.summary_limit,
        )
    except (FileNotFoundError, ValueError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    if args.json:
        json.dump(
            {
                "document_message_count": analysis.document_message_count,
                "lifecycle_message_count": analysis.lifecycle_message_count,
                "overlap_message_count": analysis.overlap_message_count,
                "output_db": str(args.output_db),
                "summary": str(args.summary),
            },
            sys.stdout,
            sort_keys=True,
        )
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
