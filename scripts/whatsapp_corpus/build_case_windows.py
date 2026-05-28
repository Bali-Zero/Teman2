from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

DEFAULT_ANALYSIS_DIR = Path("research/personal/wa-corpus/analysis")
DEFAULT_EVENTS_DB = DEFAULT_ANALYSIS_DIR / "allowed_domain_events.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_ANALYSIS_DIR / "allowed_case_windows.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_ANALYSIS_DIR / "allowed_case_windows_summary.md"

ALLOWED_EVENTS_DB_NAME = "allowed_domain_events.local.sqlite"
HIGH_SEVERITY_LABELS = frozenset({"high", "critical", "urgent"})
WINDOW_SIZE_BINS: tuple[tuple[str, int, int | None], ...] = (
    ("1", 1, 1),
    ("2-5", 2, 5),
    ("6-10", 6, 10),
    ("11-25", 11, 25),
    ("26-50", 26, 50),
    ("51-100", 51, 100),
    ("101+", 101, None),
)


@dataclass(frozen=True)
class DomainEventRow:
    domain_code: str
    event_code: str
    file_id: str
    message_index: int
    timestamp: str | None
    parsed_timestamp: datetime | None
    month: str
    severity: str


@dataclass(frozen=True)
class EventCodeTotal:
    domain_code: str
    event_code: str
    event_count: int


@dataclass(frozen=True)
class DomainTotal:
    domain_code: str
    event_count: int
    message_count: int


@dataclass(frozen=True)
class CaseWindow:
    window_id: str
    file_id: str
    window_ordinal: int
    first_timestamp: str | None
    last_timestamp: str | None
    first_month: str
    last_month: str
    first_message_index: int
    last_message_index: int
    event_count: int
    message_count: int
    domain_count: int
    dominant_domain: str
    severity_high_count: int
    domain_totals: tuple[DomainTotal, ...]
    top_event_codes: tuple[EventCodeTotal, ...]


@dataclass(frozen=True)
class CaseWindowIndex:
    events: tuple[DomainEventRow, ...]
    windows: tuple[CaseWindow, ...]
    max_gap_hours: float
    max_message_gap: int


def stable_hash(value: str, length: int = 24) -> str:
    """Return a stable local hash for anonymous case-window IDs."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    if db_path.name != ALLOWED_EVENTS_DB_NAME:
        raise ValueError(f"Refusing to read unexpected input artifact: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"Input DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


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
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        return _as_utc(parsed)

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _month_key(timestamp: datetime | None, fallback: str) -> str:
    if timestamp is not None:
        return f"{timestamp.year:04d}-{timestamp.month:02d}"
    if len(fallback) >= 7:
        return fallback[:7]
    return "unknown"


def _event_sort_key(
    event: DomainEventRow,
) -> tuple[str, int, datetime, int, str, str]:
    return (
        event.file_id,
        1 if event.parsed_timestamp is None else 0,
        event.parsed_timestamp or datetime.max.replace(tzinfo=timezone.utc),
        event.message_index,
        event.domain_code,
        event.event_code,
    )


def read_domain_events(events_db: Path) -> list[DomainEventRow]:
    """Read only aggregate-safe columns from the derived domain event index."""
    with _connect_readonly(events_db) as conn:
        rows = conn.execute(
            """
            SELECT domain_code, event_code, file_id, message_index,
                   timestamp, month, severity
            FROM domain_events
            ORDER BY file_id, timestamp, message_index, domain_code, event_code
            """
        ).fetchall()

    events = [
        DomainEventRow(
            domain_code=str(row["domain_code"]),
            event_code=str(row["event_code"]),
            file_id=str(row["file_id"]),
            message_index=int(row["message_index"]),
            timestamp=str(row["timestamp"]) if row["timestamp"] is not None else None,
            parsed_timestamp=_parse_timestamp(row["timestamp"]),
            month=str(row["month"] or "unknown"),
            severity=str(row["severity"] or "").strip().lower(),
        )
        for row in rows
    ]
    return sorted(events, key=_event_sort_key)


def _is_new_window(
    previous: DomainEventRow,
    current: DomainEventRow,
    *,
    max_gap_hours: float,
    max_message_gap: int,
) -> bool:
    message_gap = current.message_index - previous.message_index
    if message_gap > max_message_gap:
        return True

    if previous.parsed_timestamp is None or current.parsed_timestamp is None:
        return False
    time_gap_hours = (
        current.parsed_timestamp - previous.parsed_timestamp
    ).total_seconds() / 3600
    return time_gap_hours > max_gap_hours


def _message_count(events: Iterable[DomainEventRow]) -> int:
    return len({event.message_index for event in events})


def _sorted_domain_totals(events: Sequence[DomainEventRow]) -> tuple[DomainTotal, ...]:
    event_counts = Counter(event.domain_code for event in events)
    message_sets: dict[str, set[int]] = defaultdict(set)
    for event in events:
        message_sets[event.domain_code].add(event.message_index)
    return tuple(
        DomainTotal(
            domain_code=domain,
            event_count=event_count,
            message_count=len(message_sets[domain]),
        )
        for domain, event_count in sorted(
            event_counts.items(),
            key=lambda item: (-item[1], -len(message_sets[item[0]]), item[0]),
        )
    )


def _sorted_event_code_totals(
    events: Sequence[DomainEventRow],
    limit: int,
) -> tuple[EventCodeTotal, ...]:
    event_counts = Counter((event.domain_code, event.event_code) for event in events)
    return tuple(
        EventCodeTotal(domain_code=domain, event_code=event_code, event_count=count)
        for (domain, event_code), count in sorted(
            event_counts.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1]),
        )[:limit]
    )


def _valid_months(events: Sequence[DomainEventRow]) -> list[str]:
    return [
        _month_key(event.parsed_timestamp, event.month)
        for event in events
        if _month_key(event.parsed_timestamp, event.month) != "unknown"
    ]


def _timestamp_bounds(
    events: Sequence[DomainEventRow],
) -> tuple[str | None, str | None]:
    timestamped = sorted(
        (event.parsed_timestamp, event.timestamp)
        for event in events
        if event.parsed_timestamp is not None
    )
    if not timestamped:
        return None, None
    return timestamped[0][1], timestamped[-1][1]


def _window_id(
    *,
    file_id: str,
    window_ordinal: int,
    first_message_index: int,
    last_message_index: int,
    first_timestamp: str | None,
    last_timestamp: str | None,
) -> str:
    raw = "|".join(
        (
            "case_window_v1",
            file_id,
            str(window_ordinal),
            str(first_message_index),
            str(last_message_index),
            first_timestamp or "",
            last_timestamp or "",
        )
    )
    return stable_hash(raw, length=32)


def _build_window(
    events: Sequence[DomainEventRow],
    *,
    window_ordinal: int,
    top_event_codes_limit: int,
) -> CaseWindow:
    if not events:
        raise ValueError("Cannot build a case window from zero events")
    first_message_index = min(event.message_index for event in events)
    last_message_index = max(event.message_index for event in events)
    first_timestamp, last_timestamp = _timestamp_bounds(events)
    months = _valid_months(events)
    first_month = min(months) if months else "unknown"
    last_month = max(months) if months else "unknown"
    domain_totals = _sorted_domain_totals(events)
    top_event_codes = _sorted_event_code_totals(events, limit=top_event_codes_limit)
    dominant_domain = domain_totals[0].domain_code if domain_totals else "unknown"
    file_id = events[0].file_id
    window_id = _window_id(
        file_id=file_id,
        window_ordinal=window_ordinal,
        first_message_index=first_message_index,
        last_message_index=last_message_index,
        first_timestamp=first_timestamp,
        last_timestamp=last_timestamp,
    )
    return CaseWindow(
        window_id=window_id,
        file_id=file_id,
        window_ordinal=window_ordinal,
        first_timestamp=first_timestamp,
        last_timestamp=last_timestamp,
        first_month=first_month,
        last_month=last_month,
        first_message_index=first_message_index,
        last_message_index=last_message_index,
        event_count=len(events),
        message_count=_message_count(events),
        domain_count=len({event.domain_code for event in events}),
        dominant_domain=dominant_domain,
        severity_high_count=sum(
            1 for event in events if event.severity in HIGH_SEVERITY_LABELS
        ),
        domain_totals=domain_totals,
        top_event_codes=top_event_codes,
    )


def build_windows(
    events: Sequence[DomainEventRow],
    *,
    max_gap_hours: float,
    max_message_gap: int,
    top_event_codes_limit: int,
) -> tuple[CaseWindow, ...]:
    """Group domain events into per-file anonymous case windows."""
    if max_gap_hours < 0:
        raise ValueError("--max-gap-hours must be >= 0")
    if max_message_gap < 0:
        raise ValueError("--max-message-gap must be >= 0")
    if top_event_codes_limit <= 0:
        raise ValueError("--top-event-codes-limit must be > 0")

    windows: list[CaseWindow] = []
    current: list[DomainEventRow] = []
    previous: DomainEventRow | None = None
    current_file = ""
    ordinal_by_file: Counter[str] = Counter()

    for event in sorted(events, key=_event_sort_key):
        starts_file = event.file_id != current_file
        starts_gap = (
            previous is not None
            and not starts_file
            and _is_new_window(
                previous,
                event,
                max_gap_hours=max_gap_hours,
                max_message_gap=max_message_gap,
            )
        )
        if current and (starts_file or starts_gap):
            ordinal_by_file[current_file] += 1
            windows.append(
                _build_window(
                    current,
                    window_ordinal=ordinal_by_file[current_file],
                    top_event_codes_limit=top_event_codes_limit,
                )
            )
            current = []

        current_file = event.file_id
        current.append(event)
        previous = event

    if current:
        ordinal_by_file[current_file] += 1
        windows.append(
            _build_window(
                current,
                window_ordinal=ordinal_by_file[current_file],
                top_event_codes_limit=top_event_codes_limit,
            )
        )
    return tuple(windows)


def _event_codes_json(window: CaseWindow) -> str:
    return json.dumps(
        [
            {
                "domain_code": item.domain_code,
                "event_code": item.event_code,
                "event_count": item.event_count,
            }
            for item in window.top_event_codes
        ],
        sort_keys=True,
        separators=(",", ":"),
    )


def write_sqlite(*, output_db: Path, index: CaseWindowIndex) -> None:
    """Write the ignored local case-window SQLite artifact."""
    output_db.parent.mkdir(parents=True, exist_ok=True)
    if output_db.exists():
        output_db.unlink()

    windows = index.windows
    files = {window.file_id for window in windows}
    messages = {
        (event.file_id, event.message_index)
        for event in index.events
        if event.file_id in files
    }
    domains = {event.domain_code for event in index.events}
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            CREATE TABLE case_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                max_gap_hours REAL NOT NULL,
                max_message_gap INTEGER NOT NULL,
                event_rows_read INTEGER NOT NULL,
                window_count INTEGER NOT NULL,
                file_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                domain_count INTEGER NOT NULL
            );

            CREATE TABLE case_windows (
                window_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                window_ordinal INTEGER NOT NULL,
                first_timestamp TEXT,
                last_timestamp TEXT,
                first_month TEXT NOT NULL,
                last_month TEXT NOT NULL,
                first_message_index INTEGER NOT NULL,
                last_message_index INTEGER NOT NULL,
                event_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                domain_count INTEGER NOT NULL,
                dominant_domain TEXT NOT NULL,
                severity_high_count INTEGER NOT NULL,
                top_event_codes_json TEXT NOT NULL
            );

            CREATE TABLE case_window_domains (
                window_id TEXT NOT NULL,
                domain_code TEXT NOT NULL,
                event_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                PRIMARY KEY (window_id, domain_code)
            );

            CREATE TABLE case_window_event_codes (
                window_id TEXT NOT NULL,
                rank INTEGER NOT NULL,
                domain_code TEXT NOT NULL,
                event_code TEXT NOT NULL,
                event_count INTEGER NOT NULL,
                PRIMARY KEY (window_id, rank)
            );

            CREATE INDEX idx_case_windows_file ON case_windows(file_id, first_message_index);
            CREATE INDEX idx_case_windows_month ON case_windows(first_month, last_month);
            CREATE INDEX idx_case_windows_domain ON case_windows(dominant_domain);
            """
        )
        conn.execute(
            """
            INSERT INTO case_runs (
                id, generated_at_utc, privacy_mode, max_gap_hours,
                max_message_gap, event_rows_read, window_count, file_count,
                message_count, domain_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "local_only_anonymous_case_windows_no_raw_text_no_raw_values_no_raw_paths",
                index.max_gap_hours,
                index.max_message_gap,
                len(index.events),
                len(windows),
                len(files),
                len(messages),
                len(domains),
            ),
        )
        conn.executemany(
            """
            INSERT INTO case_windows (
                window_id, file_id, window_ordinal, first_timestamp,
                last_timestamp, first_month, last_month, first_message_index,
                last_message_index, event_count, message_count, domain_count,
                dominant_domain, severity_high_count, top_event_codes_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    window.window_id,
                    window.file_id,
                    window.window_ordinal,
                    window.first_timestamp,
                    window.last_timestamp,
                    window.first_month,
                    window.last_month,
                    window.first_message_index,
                    window.last_message_index,
                    window.event_count,
                    window.message_count,
                    window.domain_count,
                    window.dominant_domain,
                    window.severity_high_count,
                    _event_codes_json(window),
                )
                for window in windows
            ],
        )
        conn.executemany(
            """
            INSERT INTO case_window_domains (
                window_id, domain_code, event_count, message_count
            )
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    window.window_id,
                    domain.domain_code,
                    domain.event_count,
                    domain.message_count,
                )
                for window in windows
                for domain in window.domain_totals
            ],
        )
        conn.executemany(
            """
            INSERT INTO case_window_event_codes (
                window_id, rank, domain_code, event_code, event_count
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    window.window_id,
                    rank,
                    event_code.domain_code,
                    event_code.event_code,
                    event_code.event_count,
                )
                for window in windows
                for rank, event_code in enumerate(window.top_event_codes, start=1)
            ],
        )
        conn.commit()


def _bucket_for_size(value: int) -> str:
    for label, lower, upper in WINDOW_SIZE_BINS:
        if value >= lower and (upper is None or value <= upper):
            return label
    return "unknown"


def _window_size_distribution(
    windows: Sequence[CaseWindow],
) -> list[tuple[str, int]]:
    counts = Counter(_bucket_for_size(window.message_count) for window in windows)
    return [(label, counts[label]) for label, _, _ in WINDOW_SIZE_BINS]


def _window_event_distribution(
    windows: Sequence[CaseWindow],
) -> list[tuple[str, int]]:
    counts = Counter(_bucket_for_size(window.event_count) for window in windows)
    return [(label, counts[label]) for label, _, _ in WINDOW_SIZE_BINS]


def _domain_mix(
    windows: Sequence[CaseWindow],
) -> list[tuple[str, int, int, int, int]]:
    event_counts: Counter[str] = Counter()
    message_counts: Counter[str] = Counter()
    window_counts: Counter[str] = Counter()
    dominant_counts: Counter[str] = Counter(
        window.dominant_domain for window in windows
    )

    for window in windows:
        for domain in window.domain_totals:
            event_counts[domain.domain_code] += domain.event_count
            message_counts[domain.domain_code] += domain.message_count
            window_counts[domain.domain_code] += 1

    return [
        (
            domain,
            event_counts[domain],
            message_counts[domain],
            window_counts[domain],
            dominant_counts[domain],
        )
        for domain in sorted(
            event_counts,
            key=lambda item: (
                -event_counts[item],
                -window_counts[item],
                item,
            ),
        )
    ]


def _top_months(
    windows: Sequence[CaseWindow],
    summary_limit: int,
) -> list[tuple[str, int, int, int]]:
    window_counts: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()
    message_counts: Counter[str] = Counter()
    for window in windows:
        month = window.first_month
        window_counts[month] += 1
        event_counts[month] += window.event_count
        message_counts[month] += window.message_count

    return [
        (month, window_counts[month], event_counts[month], message_counts[month])
        for month in sorted(
            window_counts,
            key=lambda item: (-window_counts[item], item),
        )[:summary_limit]
    ]


def write_summary(
    *,
    summary_path: Path,
    events_db: Path,
    output_db: Path,
    index: CaseWindowIndex,
    summary_limit: int,
) -> None:
    """Write tracked aggregate-only case-window summary."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    windows = index.windows
    file_count = len({window.file_id for window in windows})
    message_count = sum(window.message_count for window in windows)
    domain_count = len({event.domain_code for event in index.events})
    high_severity_count = sum(window.severity_high_count for window in windows)
    lines = [
        "# WhatsApp Anonymous Case Window Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Input event SQLite artifact: `{events_db.name}`",
        f"Local case-window SQLite artifact: `{output_db.name}`",
        "",
        "## Privacy Mode",
        "",
        "- This tracked summary contains no raw message text.",
        "- This tracked summary contains no message snippets.",
        "- This tracked summary contains no phone numbers or emails.",
        "- This tracked summary contains no raw names.",
        "- This tracked summary contains no raw source paths or raw extracted values.",
        "- File IDs, timestamps, message indexes, and per-window event-code lists stay only in the ignored local SQLite artifact.",
        "- This builder reads only the derived domain event index, not the raw parsed-message DB.",
        "",
        "## Windowing Parameters",
        "",
        "| Parameter | Value |",
        "|---|---:|",
        f"| Max timestamp gap hours | {index.max_gap_hours:g} |",
        f"| Max message index gap | {index.max_message_gap} |",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Event rows read | {len(index.events)} |",
        f"| Case windows | {len(windows)} |",
        f"| Files represented | {file_count} |",
        f"| Window messages | {message_count} |",
        f"| Domains represented | {domain_count} |",
        f"| High severity events | {high_severity_count} |",
        "",
        "## Window Size Distribution",
        "",
        "| Message count bucket | Windows |",
        "|---|---:|",
    ]
    for label, count in _window_size_distribution(windows):
        lines.append(f"| {label} | {count} |")

    lines.extend(
        [
            "",
            "## Window Event Distribution",
            "",
            "| Event count bucket | Windows |",
            "|---|---:|",
        ]
    )
    for label, count in _window_event_distribution(windows):
        lines.append(f"| {label} | {count} |")

    lines.extend(
        [
            "",
            "## Domain Mix",
            "",
            "| Domain | Events | Messages | Windows | Dominant windows |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for domain, events, messages, domain_windows, dominant_windows in _domain_mix(
        windows
    ):
        lines.append(
            f"| {domain} | {events} | {messages} | {domain_windows} | {dominant_windows} |"
        )

    lines.extend(
        [
            "",
            "## Top Months",
            "",
            "| First month | Windows | Events | Messages |",
            "|---|---:|---:|---:|",
        ]
    )
    for month, month_windows, events, messages in _top_months(windows, summary_limit):
        lines.append(f"| {month} | {month_windows} | {events} | {messages} |")

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_case_windows(
    *,
    events_db: Path,
    output_db: Path,
    summary_path: Path,
    max_gap_hours: float = 72.0,
    max_message_gap: int = 80,
    top_event_codes_limit: int = 5,
    summary_limit: int = 25,
) -> CaseWindowIndex:
    """Build and persist anonymous local case windows from domain events."""
    events = tuple(read_domain_events(events_db))
    windows = build_windows(
        events,
        max_gap_hours=max_gap_hours,
        max_message_gap=max_message_gap,
        top_event_codes_limit=top_event_codes_limit,
    )
    index = CaseWindowIndex(
        events=events,
        windows=windows,
        max_gap_hours=max_gap_hours,
        max_message_gap=max_message_gap,
    )
    write_sqlite(output_db=output_db, index=index)
    write_summary(
        summary_path=summary_path,
        events_db=events_db,
        output_db=output_db,
        index=index,
        summary_limit=summary_limit,
    )
    return index


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build anonymous local WhatsApp case windows from the derived "
            "domain event index."
        )
    )
    parser.add_argument("--events-db", type=Path, default=DEFAULT_EVENTS_DB)
    parser.add_argument("--output-db", type=Path, default=DEFAULT_OUTPUT_DB)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--max-gap-hours", type=float, default=72.0)
    parser.add_argument("--max-message-gap", type=int, default=80)
    parser.add_argument("--top-event-codes-limit", type=int, default=5)
    parser.add_argument("--summary-limit", type=int, default=25)
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable counts."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        index = build_case_windows(
            events_db=args.events_db,
            output_db=args.output_db,
            summary_path=args.summary,
            max_gap_hours=args.max_gap_hours,
            max_message_gap=args.max_message_gap,
            top_event_codes_limit=args.top_event_codes_limit,
            summary_limit=args.summary_limit,
        )
    except (FileNotFoundError, ValueError, sqlite3.DatabaseError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    if args.json:
        json.dump(
            {
                "domain_count": len({event.domain_code for event in index.events}),
                "event_rows_read": len(index.events),
                "file_count": len({window.file_id for window in index.windows}),
                "max_gap_hours": index.max_gap_hours,
                "max_message_gap": index.max_message_gap,
                "message_count": sum(window.message_count for window in index.windows),
                "output_db": str(args.output_db),
                "summary": str(args.summary),
                "window_count": len(index.windows),
            },
            sys.stdout,
            sort_keys=True,
        )
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
