#!/usr/bin/env python3
"""Aggregate privacy-approved WhatsApp signal hits into matrix artifacts.

This script intentionally reads only the allowlisted signal table:
``signal_hits(file_id, source_tag, message_index, timestamp, signal_code)``.
It must not read raw WhatsApp exports, ``*.local.jsonl`` files, or raw-message
SQLite columns.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_ANALYSIS_DIR = Path("research/personal/wa-corpus/analysis")
DEFAULT_INPUT_DB = DEFAULT_ANALYSIS_DIR / "allowed_signal_hits.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_ANALYSIS_DIR / "allowed_signal_matrix.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_ANALYSIS_DIR / "allowed_signal_matrix_summary.md"
ALLOWED_INPUT_NAME = "allowed_signal_hits.local.sqlite"
MONTH_RE = re.compile(r"^(\d{4})-(\d{2})")
SELECT_ALLOWED_SIGNAL_HITS = """
SELECT file_id, source_tag, message_index, timestamp, signal_code
FROM signal_hits
"""


@dataclass(frozen=True)
class SignalHit:
    file_id: str
    source_tag: str
    message_index: int
    timestamp: str | None
    month: str
    signal_code: str


@dataclass(frozen=True)
class MatrixArtifacts:
    hit_count: int
    signal_totals: list[dict[str, object]]
    signal_source_matrix: list[dict[str, object]]
    signal_month_matrix: list[dict[str, object]]
    file_signal_density: list[dict[str, object]]
    signal_cooccurrence: list[dict[str, object]]


def _normalize_text(value: object, fallback: str) -> str:
    text = "" if value is None else str(value).strip()
    return text or fallback


def _normalize_message_index(value: object) -> int:
    if value is None or value == "":
        return -1
    return int(value)


def _extract_month(value: object) -> str:
    if value is None or value == "":
        return "unknown"
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, tz=UTC).strftime("%Y-%m")

    text = str(value).strip()
    match = MONTH_RE.match(text)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    return parsed.strftime("%Y-%m")


def _validate_input_path(input_db: Path) -> None:
    if input_db.name != ALLOWED_INPUT_NAME:
        raise ValueError(
            f"Refusing to read {input_db.name!r}; expected {ALLOWED_INPUT_NAME!r}."
        )
    if input_db.suffix == ".jsonl" or input_db.name.endswith(".local.jsonl"):
        raise ValueError("Refusing to read JSONL WhatsApp exports.")


def _read_signal_hits(input_db: Path) -> list[SignalHit]:
    _validate_input_path(input_db)
    if not input_db.is_file():
        raise FileNotFoundError(f"Input DB not found: {input_db}")

    uri = f"file:{input_db.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(SELECT_ALLOWED_SIGNAL_HITS).fetchall()
    finally:
        conn.close()

    hits: list[SignalHit] = []
    for row in rows:
        timestamp = row["timestamp"]
        hits.append(
            SignalHit(
                file_id=_normalize_text(row["file_id"], "unknown_file"),
                source_tag=_normalize_text(row["source_tag"], "unknown_source"),
                message_index=_normalize_message_index(row["message_index"]),
                timestamp=None if timestamp is None else str(timestamp),
                month=_extract_month(timestamp),
                signal_code=_normalize_text(row["signal_code"], "unknown_signal"),
            )
        )
    return hits


def _message_key(hit: SignalHit) -> tuple[str, int]:
    return (hit.file_id, hit.message_index)


def _sort_count_rows(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        rows,
        key=lambda row: (
            -int(row.get("hit_count", row.get("message_count", 0))),
            str(row.get("signal_code", row.get("signal_code_a", ""))),
            str(row.get("source_tag", row.get("month", row.get("signal_code_b", "")))),
        ),
    )


def build_artifacts(hits: Sequence[SignalHit]) -> MatrixArtifacts:
    signal_hits: Counter[str] = Counter(hit.signal_code for hit in hits)
    signal_files: dict[str, set[str]] = defaultdict(set)
    signal_messages: dict[str, set[tuple[str, int]]] = defaultdict(set)

    source_hits: Counter[tuple[str, str]] = Counter()
    source_files: dict[tuple[str, str], set[str]] = defaultdict(set)
    source_messages: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(set)

    month_hits: Counter[tuple[str, str]] = Counter()
    month_files: dict[tuple[str, str], set[str]] = defaultdict(set)
    month_messages: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(set)

    file_hits: dict[str, list[SignalHit]] = defaultdict(list)
    signals_by_message: dict[tuple[str, int], set[str]] = defaultdict(set)
    file_by_message: dict[tuple[str, int], str] = {}

    for hit in hits:
        message_key = _message_key(hit)
        signal_files[hit.signal_code].add(hit.file_id)
        signal_messages[hit.signal_code].add(message_key)

        source_key = (hit.signal_code, hit.source_tag)
        source_hits[source_key] += 1
        source_files[source_key].add(hit.file_id)
        source_messages[source_key].add(message_key)

        month_key = (hit.signal_code, hit.month)
        month_hits[month_key] += 1
        month_files[month_key].add(hit.file_id)
        month_messages[month_key].add(message_key)

        file_hits[hit.file_id].append(hit)
        signals_by_message[message_key].add(hit.signal_code)
        file_by_message[message_key] = hit.file_id

    signal_totals = _sort_count_rows(
        {
            "signal_code": signal_code,
            "hit_count": hit_count,
            "file_count": len(signal_files[signal_code]),
            "message_count": len(signal_messages[signal_code]),
        }
        for signal_code, hit_count in signal_hits.items()
    )

    signal_source_matrix = _sort_count_rows(
        {
            "signal_code": signal_code,
            "source_tag": source_tag,
            "hit_count": hit_count,
            "file_count": len(source_files[(signal_code, source_tag)]),
            "message_count": len(source_messages[(signal_code, source_tag)]),
        }
        for (signal_code, source_tag), hit_count in source_hits.items()
    )

    signal_month_matrix = _sort_count_rows(
        {
            "signal_code": signal_code,
            "month": month,
            "hit_count": hit_count,
            "file_count": len(month_files[(signal_code, month)]),
            "message_count": len(month_messages[(signal_code, month)]),
        }
        for (signal_code, month), hit_count in month_hits.items()
    )

    density_rows: list[dict[str, object]] = []
    for file_id, file_rows in file_hits.items():
        message_indexes = [hit.message_index for hit in file_rows]
        min_index = min(message_indexes)
        max_index = max(message_indexes)
        message_span = max_index - min_index + 1 if min_index >= 0 else 0
        hit_messages = {_message_key(hit) for hit in file_rows}
        timestamps = sorted(hit.timestamp for hit in file_rows if hit.timestamp)
        hit_message_count = len(hit_messages)
        total_hits = len(file_rows)
        density_rows.append(
            {
                "file_id": file_id,
                "source_tag": ", ".join(sorted({hit.source_tag for hit in file_rows})),
                "min_message_index": min_index,
                "max_message_index": max_index,
                "message_span": message_span,
                "hit_message_count": hit_message_count,
                "total_hits": total_hits,
                "unique_signal_count": len({hit.signal_code for hit in file_rows}),
                "hits_per_hit_message": round(total_hits / hit_message_count, 6)
                if hit_message_count
                else 0.0,
                "hits_per_message_span": round(total_hits / message_span, 6)
                if message_span
                else 0.0,
                "first_timestamp": timestamps[0] if timestamps else None,
                "last_timestamp": timestamps[-1] if timestamps else None,
            }
        )
    file_signal_density = sorted(
        density_rows,
        key=lambda row: (
            -float(row["hits_per_message_span"]),
            -int(row["total_hits"]),
            str(row["file_id"]),
        ),
    )

    pair_messages: Counter[tuple[str, str]] = Counter()
    pair_files: dict[tuple[str, str], set[str]] = defaultdict(set)
    for message_key, message_signals in signals_by_message.items():
        for signal_a, signal_b in combinations(sorted(message_signals), 2):
            pair = (signal_a, signal_b)
            pair_messages[pair] += 1
            pair_files[pair].add(file_by_message[message_key])

    signal_cooccurrence = sorted(
        (
            {
                "signal_code_a": signal_a,
                "signal_code_b": signal_b,
                "message_count": message_count,
                "file_count": len(pair_files[(signal_a, signal_b)]),
            }
            for (signal_a, signal_b), message_count in pair_messages.items()
        ),
        key=lambda row: (
            -int(row["message_count"]),
            str(row["signal_code_a"]),
            str(row["signal_code_b"]),
        ),
    )

    return MatrixArtifacts(
        hit_count=len(hits),
        signal_totals=signal_totals,
        signal_source_matrix=signal_source_matrix,
        signal_month_matrix=signal_month_matrix,
        file_signal_density=file_signal_density,
        signal_cooccurrence=signal_cooccurrence,
    )


def _create_output_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE analysis_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE signal_totals (
            signal_code TEXT NOT NULL PRIMARY KEY,
            hit_count INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            message_count INTEGER NOT NULL
        );
        CREATE TABLE signal_source_matrix (
            signal_code TEXT NOT NULL,
            source_tag TEXT NOT NULL,
            hit_count INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            message_count INTEGER NOT NULL,
            PRIMARY KEY (signal_code, source_tag)
        );
        CREATE TABLE signal_month_matrix (
            signal_code TEXT NOT NULL,
            month TEXT NOT NULL,
            hit_count INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            message_count INTEGER NOT NULL,
            PRIMARY KEY (signal_code, month)
        );
        CREATE TABLE file_signal_density (
            file_id TEXT NOT NULL PRIMARY KEY,
            source_tag TEXT NOT NULL,
            min_message_index INTEGER NOT NULL,
            max_message_index INTEGER NOT NULL,
            message_span INTEGER NOT NULL,
            hit_message_count INTEGER NOT NULL,
            total_hits INTEGER NOT NULL,
            unique_signal_count INTEGER NOT NULL,
            hits_per_hit_message REAL NOT NULL,
            hits_per_message_span REAL NOT NULL,
            first_timestamp TEXT,
            last_timestamp TEXT
        );
        CREATE TABLE signal_cooccurrence (
            signal_code_a TEXT NOT NULL,
            signal_code_b TEXT NOT NULL,
            message_count INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            PRIMARY KEY (signal_code_a, signal_code_b)
        );
        """
    )


def write_matrix_db(
    output_db: Path,
    artifacts: MatrixArtifacts,
    *,
    input_name: str,
    generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    if output_db.exists():
        output_db.unlink()

    conn = sqlite3.connect(output_db)
    try:
        _create_output_schema(conn)
        conn.executemany(
            "INSERT INTO analysis_metadata (key, value) VALUES (?, ?)",
            [
                ("generated_at_utc", generated_at_utc),
                ("input_name", input_name),
                ("hit_count", str(artifacts.hit_count)),
            ],
        )
        conn.executemany(
            """
            INSERT INTO signal_totals
                (signal_code, hit_count, file_count, message_count)
            VALUES (:signal_code, :hit_count, :file_count, :message_count)
            """,
            artifacts.signal_totals,
        )
        conn.executemany(
            """
            INSERT INTO signal_source_matrix
                (signal_code, source_tag, hit_count, file_count, message_count)
            VALUES (:signal_code, :source_tag, :hit_count, :file_count, :message_count)
            """,
            artifacts.signal_source_matrix,
        )
        conn.executemany(
            """
            INSERT INTO signal_month_matrix
                (signal_code, month, hit_count, file_count, message_count)
            VALUES (:signal_code, :month, :hit_count, :file_count, :message_count)
            """,
            artifacts.signal_month_matrix,
        )
        conn.executemany(
            """
            INSERT INTO file_signal_density
                (
                    file_id, source_tag, min_message_index, max_message_index,
                    message_span, hit_message_count, total_hits,
                    unique_signal_count, hits_per_hit_message,
                    hits_per_message_span, first_timestamp, last_timestamp
                )
            VALUES (
                :file_id, :source_tag, :min_message_index, :max_message_index,
                :message_span, :hit_message_count, :total_hits,
                :unique_signal_count, :hits_per_hit_message,
                :hits_per_message_span, :first_timestamp, :last_timestamp
            )
            """,
            artifacts.file_signal_density,
        )
        conn.executemany(
            """
            INSERT INTO signal_cooccurrence
                (signal_code_a, signal_code_b, message_count, file_count)
            VALUES (:signal_code_a, :signal_code_b, :message_count, :file_count)
            """,
            artifacts.signal_cooccurrence,
        )
        conn.commit()
    finally:
        conn.close()


def _markdown_value(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|")


def _markdown_table(
    headers: Sequence[str],
    rows: Sequence[dict[str, object]],
    *,
    keys: Sequence[str],
    limit: int,
) -> str:
    if not rows:
        return "_No rows._\n"

    limited_rows = rows[:limit]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in limited_rows:
        lines.append("| " + " | ".join(_markdown_value(row.get(key)) for key in keys) + " |")
    if len(rows) > limit:
        lines.append(f"\n_Showing {limit} of {len(rows)} rows._")
    return "\n".join(lines) + "\n"


def render_summary_markdown(
    artifacts: MatrixArtifacts,
    *,
    input_name: str,
    output_name: str,
    generated_at_utc: str,
    limit: int,
) -> str:
    return "\n".join(
        [
            "# Allowed Signal Matrix Summary",
            "",
            f"- Generated UTC: `{generated_at_utc}`",
            f"- Input DB: `{input_name}`",
            f"- Matrix DB: `{output_name}`",
            f"- Signal hits read: `{artifacts.hit_count}`",
            "- Privacy boundary: reads only `file_id`, `source_tag`, "
            "`message_index`, `timestamp`, and `signal_code` from "
            "`signal_hits`.",
            "",
            "## Signal Totals",
            "",
            _markdown_table(
                ["signal_code", "hit_count", "file_count", "message_count"],
                artifacts.signal_totals,
                keys=["signal_code", "hit_count", "file_count", "message_count"],
                limit=limit,
            ),
            "## Signal x Source Tag",
            "",
            _markdown_table(
                ["signal_code", "source_tag", "hit_count", "file_count", "message_count"],
                artifacts.signal_source_matrix,
                keys=[
                    "signal_code",
                    "source_tag",
                    "hit_count",
                    "file_count",
                    "message_count",
                ],
                limit=limit,
            ),
            "## Signal x Month",
            "",
            _markdown_table(
                ["signal_code", "month", "hit_count", "file_count", "message_count"],
                artifacts.signal_month_matrix,
                keys=["signal_code", "month", "hit_count", "file_count", "message_count"],
                limit=limit,
            ),
            "## Per-File Signal Density",
            "",
            _markdown_table(
                [
                    "file_id",
                    "source_tag",
                    "total_hits",
                    "hit_message_count",
                    "message_span",
                    "hits_per_hit_message",
                    "hits_per_message_span",
                ],
                artifacts.file_signal_density,
                keys=[
                    "file_id",
                    "source_tag",
                    "total_hits",
                    "hit_message_count",
                    "message_span",
                    "hits_per_hit_message",
                    "hits_per_message_span",
                ],
                limit=limit,
            ),
            "## Signal Co-Occurrence",
            "",
            _markdown_table(
                ["signal_code_a", "signal_code_b", "message_count", "file_count"],
                artifacts.signal_cooccurrence,
                keys=["signal_code_a", "signal_code_b", "message_count", "file_count"],
                limit=limit,
            ),
        ]
    )


def write_summary_markdown(summary_path: Path, content: str) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(content, encoding="utf-8")


def run_analysis(
    *,
    input_db: Path,
    output_db: Path,
    summary_path: Path,
    summary_limit: int,
    generated_at_utc: str | None = None,
) -> MatrixArtifacts:
    if input_db.resolve() == output_db.resolve():
        raise ValueError("Input and output DB paths must be different.")
    generated_at = generated_at_utc or datetime.now(tz=UTC).replace(microsecond=0).isoformat()
    hits = _read_signal_hits(input_db)
    artifacts = build_artifacts(hits)
    write_matrix_db(
        output_db,
        artifacts,
        input_name=input_db.name,
        generated_at_utc=generated_at,
    )
    summary = render_summary_markdown(
        artifacts,
        input_name=input_db.name,
        output_name=output_db.name,
        generated_at_utc=generated_at,
        limit=summary_limit,
    )
    write_summary_markdown(summary_path, summary)
    return artifacts


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build aggregate matrices from allowed WhatsApp signal hits."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_DB)
    parser.add_argument("--output-db", type=Path, default=DEFAULT_OUTPUT_DB)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--summary-limit", type=int, default=25)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable run stats.")
    parser.add_argument("--quiet", action="store_true", help="Suppress success output.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        artifacts = run_analysis(
            input_db=args.input,
            output_db=args.output_db,
            summary_path=args.summary,
            summary_limit=args.summary_limit,
        )
    except (FileNotFoundError, OSError, sqlite3.Error, ValueError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    if args.json:
        sys.stdout.write(
            json.dumps(
                {
                    "hit_count": artifacts.hit_count,
                    "output_db": str(args.output_db),
                    "summary": str(args.summary),
                },
                sort_keys=True,
            )
            + "\n"
        )
    elif not args.quiet:
        sys.stdout.write(f"Wrote {args.output_db} and {args.summary}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
