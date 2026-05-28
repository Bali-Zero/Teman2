from __future__ import annotations

import argparse
import json
import re
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DB = REPO_ROOT / "research/personal/wa-corpus/analysis/allowed_messages.local.sqlite"
DEFAULT_OUTPUT_DB = REPO_ROOT / "research/personal/wa-corpus/analysis/allowed_temporal.local.sqlite"
DEFAULT_SUMMARY = REPO_ROOT / "research/personal/wa-corpus/analysis/allowed_temporal_summary.md"
DEFAULT_TABLE = "auto"
CANDIDATE_TABLES = ("allowed_messages", "parsed_messages")

FORBIDDEN_COLUMNS = frozenset({"body_text", "sender_raw", "local_path"})
REQUIRED_METRIC_COLUMNS = (
    "file_id",
    "source_tag",
    "timestamp",
    "is_system_event",
    "body_char_count",
)
KNOWN_ALLOWED_COLUMNS = frozenset(
    {
        "file_id",
        "source_tag",
        "message_index",
        "timestamp",
        "sender_hash",
        "direction",
        "is_system_event",
        "body_char_count",
    }
)
FEATURE_PREFIXES = ("feature_", "flag_", "has_", "contains_", "is_")
FEATURE_SUFFIXES = ("_flag",)
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class SafeSelect:
    sql: str
    selected_columns: tuple[str, ...]
    feature_columns: tuple[str, ...]


@dataclass(frozen=True)
class TopFileRow:
    file_id: str
    message_count: int
    first_month: str
    last_month: str


@dataclass(frozen=True)
class TemporalAnalysis:
    total_messages: int
    messages_with_timestamp: int
    messages_without_timestamp: int
    system_event_count: int
    source_tag_counts: list[tuple[str, int]]
    year_counts: list[tuple[int, int]]
    month_counts: list[tuple[str, int]]
    weekday_counts: list[tuple[int, str, int]]
    hour_counts: list[tuple[int, int]]
    top_files: list[TopFileRow]
    monthly_median_body_chars: list[tuple[str, float, int]]
    feature_flag_counts: list[tuple[str, int, int]]


def _quote_identifier(value: str) -> str:
    if not IDENTIFIER_RE.match(value):
        raise ValueError(f"Unsafe SQLite identifier: {value!r}")
    return f'"{value}"'


def _is_feature_column(column_name: str) -> bool:
    lowered = column_name.lower()
    if lowered in FORBIDDEN_COLUMNS or lowered in KNOWN_ALLOWED_COLUMNS:
        return False
    return lowered.startswith(FEATURE_PREFIXES) or lowered.endswith(FEATURE_SUFFIXES)


def build_safe_select_sql(table: str, available_columns: Sequence[str]) -> SafeSelect:
    missing = [column for column in REQUIRED_METRIC_COLUMNS if column not in available_columns]
    if missing:
        raise ValueError(f"Missing required aggregate-safe columns: {', '.join(missing)}")

    feature_columns = tuple(column for column in available_columns if _is_feature_column(column))
    selected_columns = (*REQUIRED_METRIC_COLUMNS, *feature_columns)
    leaked = FORBIDDEN_COLUMNS.intersection(selected_columns)
    if leaked:
        raise ValueError(f"Refusing to select raw/private columns: {', '.join(sorted(leaked))}")

    quoted_columns = ", ".join(_quote_identifier(column) for column in selected_columns)
    sql = f"SELECT {quoted_columns} FROM {_quote_identifier(table)}"
    return SafeSelect(sql=sql, selected_columns=selected_columns, feature_columns=feature_columns)


def _deny_forbidden_column_reads(
    action: int,
    _arg1: str | None,
    arg2: str | None,
    _db_name: str | None,
    _trigger: str | None,
) -> int:
    if action == sqlite3.SQLITE_READ and (arg2 or "").lower() in FORBIDDEN_COLUMNS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"Input SQLite DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.set_authorizer(_deny_forbidden_column_reads)
    return conn


def _discover_columns(conn: sqlite3.Connection, table: str) -> tuple[str, ...]:
    rows = conn.execute(f"PRAGMA table_info({_quote_identifier(table)})").fetchall()
    columns = tuple(str(row["name"]) for row in rows)
    if not columns:
        raise ValueError(f"Table not found or has no columns: {table}")
    return columns


def _resolve_table(conn: sqlite3.Connection, requested_table: str) -> str:
    if requested_table != "auto":
        return requested_table

    for candidate in CANDIDATE_TABLES:
        found = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
            (candidate,),
        ).fetchone()
        if found:
            return candidate
    raise ValueError(f"No supported message table found: {', '.join(CANDIDATE_TABLES)}")


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds = seconds / 1000
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    for candidate in (text, text.replace(" ", "T", 1)):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _int_value(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y"}
    return bool(value)


def _label(value: Any) -> str:
    text = str(value).strip() if value is not None else ""
    return text or "(unknown)"


def _sorted_counter(counter: Counter[Any]) -> list[tuple[Any, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def _month_key(timestamp: datetime) -> str:
    return f"{timestamp.year:04d}-{timestamp.month:02d}"


def _collect_metrics(
    rows: Iterable[sqlite3.Row],
    feature_columns: Sequence[str],
    top_limit: int,
) -> TemporalAnalysis:
    source_tags: Counter[str] = Counter()
    years: Counter[int] = Counter()
    months: Counter[str] = Counter()
    weekdays: Counter[int] = Counter()
    hours: Counter[int] = Counter()
    file_counts: Counter[str] = Counter()
    file_months: dict[str, list[str]] = defaultdict(list)
    body_chars_by_month: dict[str, list[int]] = defaultdict(list)
    feature_counts: Counter[str] = Counter()

    total_messages = 0
    messages_with_timestamp = 0
    system_event_count = 0

    for row in rows:
        total_messages += 1
        source_tags[_label(row["source_tag"])] += 1
        file_id = _label(row["file_id"])
        file_counts[file_id] += 1

        if _truthy(row["is_system_event"]):
            system_event_count += 1

        timestamp = _parse_timestamp(row["timestamp"])
        if timestamp is None:
            continue

        messages_with_timestamp += 1
        month = _month_key(timestamp)
        years[timestamp.year] += 1
        months[month] += 1
        weekdays[timestamp.weekday()] += 1
        hours[timestamp.hour] += 1
        file_months[file_id].append(month)

        body_char_count = _int_value(row["body_char_count"])
        if body_char_count is not None:
            body_chars_by_month[month].append(body_char_count)

        for feature_column in feature_columns:
            if _truthy(row[feature_column]):
                feature_counts[feature_column] += 1

    top_files = [
        TopFileRow(
            file_id=file_id,
            message_count=count,
            first_month=min(file_months[file_id]) if file_months[file_id] else "",
            last_month=max(file_months[file_id]) if file_months[file_id] else "",
        )
        for file_id, count in _sorted_counter(file_counts)[:top_limit]
    ]
    monthly_medians = [
        (month, float(statistics.median(values)), len(values))
        for month, values in sorted(body_chars_by_month.items())
        if values
    ]

    return TemporalAnalysis(
        total_messages=total_messages,
        messages_with_timestamp=messages_with_timestamp,
        messages_without_timestamp=total_messages - messages_with_timestamp,
        system_event_count=system_event_count,
        source_tag_counts=[(tag, count) for tag, count in _sorted_counter(source_tags)],
        year_counts=sorted(years.items()),
        month_counts=sorted(months.items()),
        weekday_counts=[
            (weekday, WEEKDAY_NAMES[weekday], weekdays.get(weekday, 0))
            for weekday in range(7)
            if weekdays.get(weekday, 0) > 0
        ],
        hour_counts=[(hour, hours.get(hour, 0)) for hour in range(24) if hours.get(hour, 0) > 0],
        top_files=top_files,
        monthly_median_body_chars=monthly_medians,
        feature_flag_counts=[
            (feature_column, feature_counts.get(feature_column, 0), total_messages)
            for feature_column in feature_columns
        ],
    )


def _insert_rows(conn: sqlite3.Connection, table: str, columns: Sequence[str], rows: Iterable[tuple[Any, ...]]) -> None:
    quoted_table = _quote_identifier(table)
    quoted_columns = ", ".join(_quote_identifier(column) for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    conn.executemany(
        f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({placeholders})",
        list(rows),
    )


def _write_output_db(result: TemporalAnalysis, output_db: Path) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    tmp_db = output_db.with_name(f"{output_db.name}.tmp")
    if tmp_db.exists():
        tmp_db.unlink()

    conn = sqlite3.connect(tmp_db)
    try:
        conn.executescript(
            """
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE messages_by_year (
                year INTEGER PRIMARY KEY,
                message_count INTEGER NOT NULL
            );
            CREATE TABLE messages_by_month (
                month TEXT PRIMARY KEY,
                message_count INTEGER NOT NULL
            );
            CREATE TABLE messages_by_weekday (
                weekday INTEGER PRIMARY KEY,
                weekday_name TEXT NOT NULL,
                message_count INTEGER NOT NULL
            );
            CREATE TABLE messages_by_hour (
                hour INTEGER PRIMARY KEY,
                message_count INTEGER NOT NULL
            );
            CREATE TABLE messages_by_source_tag (
                source_tag TEXT PRIMARY KEY,
                message_count INTEGER NOT NULL
            );
            CREATE TABLE top_file_id_by_volume (
                rank INTEGER PRIMARY KEY,
                file_id TEXT NOT NULL,
                message_count INTEGER NOT NULL,
                first_month TEXT NOT NULL,
                last_month TEXT NOT NULL
            );
            CREATE TABLE median_body_chars_by_month (
                month TEXT PRIMARY KEY,
                median_body_chars REAL NOT NULL,
                message_count INTEGER NOT NULL
            );
            CREATE TABLE system_event_count (
                event_count INTEGER NOT NULL
            );
            CREATE TABLE feature_flag_counts (
                flag_name TEXT PRIMARY KEY,
                true_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL
            );
            """
        )
        metadata_rows = [
            ("total_messages", str(result.total_messages)),
            ("messages_with_timestamp", str(result.messages_with_timestamp)),
            ("messages_without_timestamp", str(result.messages_without_timestamp)),
            ("system_event_count", str(result.system_event_count)),
        ]
        _insert_rows(conn, "metadata", ("key", "value"), metadata_rows)
        _insert_rows(conn, "messages_by_year", ("year", "message_count"), result.year_counts)
        _insert_rows(conn, "messages_by_month", ("month", "message_count"), result.month_counts)
        _insert_rows(
            conn,
            "messages_by_weekday",
            ("weekday", "weekday_name", "message_count"),
            result.weekday_counts,
        )
        _insert_rows(conn, "messages_by_hour", ("hour", "message_count"), result.hour_counts)
        _insert_rows(
            conn,
            "messages_by_source_tag",
            ("source_tag", "message_count"),
            result.source_tag_counts,
        )
        _insert_rows(
            conn,
            "top_file_id_by_volume",
            ("rank", "file_id", "message_count", "first_month", "last_month"),
            (
                (index, row.file_id, row.message_count, row.first_month, row.last_month)
                for index, row in enumerate(result.top_files, start=1)
            ),
        )
        _insert_rows(
            conn,
            "median_body_chars_by_month",
            ("month", "median_body_chars", "message_count"),
            result.monthly_median_body_chars,
        )
        _insert_rows(conn, "system_event_count", ("event_count",), [(result.system_event_count,)])
        _insert_rows(
            conn,
            "feature_flag_counts",
            ("flag_name", "true_count", "message_count"),
            result.feature_flag_counts,
        )
        conn.commit()
    finally:
        conn.close()

    tmp_db.replace(output_db)


def _format_number(value: float | int) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _markdown_table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    row_list = list(rows)
    if not row_list:
        return "_No rows._\n"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in row_list:
        lines.append("| " + " | ".join(_format_number(value) for value in row) + " |")
    return "\n".join(lines) + "\n"


def _write_summary(result: TemporalAnalysis, summary_path: Path) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# WhatsApp Allowed Temporal Summary",
        "",
        "Aggregate-only report generated from the allowed local message index.",
        "Raw body, sender, and local file path columns are denied by the SQLite authorizer.",
        "",
        "## Overview",
        "",
        _markdown_table(
            ("Metric", "Value"),
            (
                ("Total messages", result.total_messages),
                ("Messages with valid timestamp", result.messages_with_timestamp),
                ("Messages without valid timestamp", result.messages_without_timestamp),
                ("System events", result.system_event_count),
            ),
        ),
        "",
        "## Messages Per Year",
        "",
        _markdown_table(("Year", "Messages"), result.year_counts),
        "",
        "## Messages Per Month",
        "",
        _markdown_table(("Month", "Messages"), result.month_counts),
        "",
        "## Messages Per Weekday",
        "",
        _markdown_table(
            ("Weekday", "Name", "Messages"),
            result.weekday_counts,
        ),
        "",
        "## Messages Per Hour",
        "",
        _markdown_table(
            ("Hour", "Messages"),
            ((f"{hour:02d}:00", count) for hour, count in result.hour_counts),
        ),
        "",
        "## Messages Per Source Tag",
        "",
        _markdown_table(("Source tag", "Messages"), result.source_tag_counts),
        "",
        "## Top File IDs By Volume",
        "",
        _markdown_table(
            ("Rank", "File ID", "Messages", "First month", "Last month"),
            (
                (index, row.file_id, row.message_count, row.first_month, row.last_month)
                for index, row in enumerate(result.top_files, start=1)
            ),
        ),
        "",
        "## Median Body Characters Per Month",
        "",
        _markdown_table(
            ("Month", "Median body chars", "Messages"),
            result.monthly_median_body_chars,
        ),
        "",
        "## Feature Flag Counts",
        "",
        _markdown_table(
            ("Flag", "True count", "Messages"),
            result.feature_flag_counts,
        ),
        "",
    ]
    summary_path.write_text("\n".join(lines), encoding="utf-8")


def analyze_allowed_temporal(
    *,
    input_db: Path,
    output_db: Path,
    summary_path: Path,
    table: str = DEFAULT_TABLE,
    top_limit: int = 20,
) -> TemporalAnalysis:
    if top_limit < 1:
        raise ValueError("top_limit must be >= 1")

    with _connect_readonly(input_db) as conn:
        resolved_table = _resolve_table(conn, table)
        available_columns = _discover_columns(conn, resolved_table)
        safe_select = build_safe_select_sql(resolved_table, available_columns)
        rows = conn.execute(safe_select.sql).fetchall()

    result = _collect_metrics(rows, safe_select.feature_columns, top_limit)
    _write_output_db(result, output_db)
    _write_summary(result, summary_path)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate temporal metrics from allowed_messages.local.sqlite."
    )
    parser.add_argument("--input-db", type=Path, default=DEFAULT_INPUT_DB)
    parser.add_argument("--output-db", type=Path, default=DEFAULT_OUTPUT_DB)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument(
        "--table",
        default=DEFAULT_TABLE,
        help="Message table name, or 'auto' to use allowed_messages/parsed_messages.",
    )
    parser.add_argument("--top-limit", type=int, default=20)
    args = parser.parse_args(argv)

    result = analyze_allowed_temporal(
        input_db=args.input_db,
        output_db=args.output_db,
        summary_path=args.summary,
        table=args.table,
        top_limit=args.top_limit,
    )
    sys.stdout.write(
        json.dumps(
            {
                "input_db": str(args.input_db),
                "output_db": str(args.output_db),
                "summary": str(args.summary),
                "total_messages": result.total_messages,
                "system_event_count": result.system_event_count,
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
