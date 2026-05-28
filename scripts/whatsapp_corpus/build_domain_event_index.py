from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_ANALYSIS_DIR = Path("research/personal/wa-corpus/analysis")
DEFAULT_DOCUMENT_DB = (
    DEFAULT_ANALYSIS_DIR / "allowed_document_requirements.local.sqlite"
)
DEFAULT_LIFECYCLE_DB = (
    DEFAULT_ANALYSIS_DIR / "allowed_immigration_lifecycle.local.sqlite"
)
DEFAULT_TAX_DB = DEFAULT_ANALYSIS_DIR / "allowed_tax_payment.local.sqlite"
DEFAULT_FOLLOWUP_DB = DEFAULT_ANALYSIS_DIR / "allowed_followup_risk.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_ANALYSIS_DIR / "allowed_domain_events.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_ANALYSIS_DIR / "allowed_domain_events_summary.md"

ALLOWED_INPUT_NAMES = frozenset(
    {
        "allowed_document_requirements.local.sqlite",
        "allowed_immigration_lifecycle.local.sqlite",
        "allowed_tax_payment.local.sqlite",
        "allowed_followup_risk.local.sqlite",
    }
)


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    domain_code: str
    event_code: str
    evidence_code: str
    file_id: str
    message_index: int
    timestamp: str | None
    month: str
    source_ref_hash: str
    sender_hash: str
    score: float
    severity: str
    reference_hash: str


@dataclass(frozen=True)
class DomainEventIndex:
    events: list[DomainEvent]
    input_status: dict[str, int]


def stable_hash(value: str, length: int = 24) -> str:
    """Return a stable local hash for event identities and source references."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def month_key(timestamp: str | None) -> str:
    """Return YYYY-MM from an ISO-ish timestamp."""
    if not timestamp or len(timestamp) < 7:
        return "unknown"
    return timestamp[:7]


def _source_hash(value: str | None) -> str:
    if not value:
        return ""
    return stable_hash(value.strip().casefold(), length=16)


def _event_id(
    *,
    domain_code: str,
    event_code: str,
    evidence_code: str,
    file_id: str,
    message_index: int,
    reference_hash: str,
) -> str:
    raw = "|".join(
        (
            domain_code,
            event_code,
            evidence_code,
            file_id,
            str(message_index),
            reference_hash,
        )
    )
    return stable_hash(raw, length=32)


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"Input DB not found: {db_path}")
    if db_path.name not in ALLOWED_INPUT_NAMES:
        raise ValueError(f"Refusing to read unexpected input artifact: {db_path.name}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _event(
    *,
    domain_code: str,
    event_code: str,
    evidence_code: str,
    file_id: str,
    message_index: int,
    timestamp: str | None,
    source_ref_hash: str,
    sender_hash: str = "",
    score: float = 1.0,
    severity: str = "",
    reference_hash: str = "",
) -> DomainEvent:
    return DomainEvent(
        event_id=_event_id(
            domain_code=domain_code,
            event_code=event_code,
            evidence_code=evidence_code,
            file_id=file_id,
            message_index=message_index,
            reference_hash=reference_hash,
        ),
        domain_code=domain_code,
        event_code=event_code,
        evidence_code=evidence_code,
        file_id=file_id,
        message_index=message_index,
        timestamp=timestamp,
        month=month_key(timestamp),
        source_ref_hash=source_ref_hash,
        sender_hash=sender_hash,
        score=score,
        severity=severity,
        reference_hash=reference_hash,
    )


def read_document_events(db_path: Path) -> list[DomainEvent]:
    """Read document requirement hits as normalized domain events."""
    with _connect_readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT file_id, source_tag_hash, message_index, timestamp, sender_hash,
                   requirement_code, evidence_code, context_code, value_hash, body_hash
            FROM requirement_hits
            ORDER BY file_id, message_index, requirement_code, evidence_code, value_hash
            """
        ).fetchall()

    events: list[DomainEvent] = []
    for row in rows:
        reference_hash = str(row["value_hash"] or row["body_hash"] or "")
        evidence_code = f"{row['evidence_code']}:{row['context_code']}"
        events.append(
            _event(
                domain_code="document_requirement",
                event_code=str(row["requirement_code"]),
                evidence_code=evidence_code,
                file_id=str(row["file_id"]),
                message_index=int(row["message_index"]),
                timestamp=row["timestamp"],
                source_ref_hash=str(row["source_tag_hash"] or ""),
                sender_hash=str(row["sender_hash"] or ""),
                reference_hash=reference_hash,
            )
        )
    return events


def read_lifecycle_events(db_path: Path) -> list[DomainEvent]:
    """Read immigration lifecycle stage hits as normalized domain events."""
    with _connect_readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT file_id, source_tag, message_index, timestamp,
                   stage_code, evidence_code, score
            FROM stage_hits
            ORDER BY file_id, message_index, stage_code, evidence_code
            """
        ).fetchall()

    events: list[DomainEvent] = []
    for row in rows:
        source_ref_hash = _source_hash(row["source_tag"])
        events.append(
            _event(
                domain_code="immigration_lifecycle",
                event_code=str(row["stage_code"]),
                evidence_code=str(row["evidence_code"]),
                file_id=str(row["file_id"]),
                message_index=int(row["message_index"]),
                timestamp=row["timestamp"],
                source_ref_hash=source_ref_hash,
                score=float(row["score"]),
            )
        )
    return events


def read_tax_events(db_path: Path) -> list[DomainEvent]:
    """Read tax/payment hits as normalized domain events."""
    with _connect_readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT file_id, source_tag, message_index, timestamp, sender_hash,
                   category_code, evidence_code, body_hash, value_hash
            FROM tax_payment_hits
            ORDER BY file_id, message_index, category_code, evidence_code, value_hash
            """
        ).fetchall()

    events: list[DomainEvent] = []
    for row in rows:
        reference_hash = str(row["value_hash"] or row["body_hash"] or "")
        events.append(
            _event(
                domain_code="tax_payment",
                event_code=str(row["category_code"]),
                evidence_code=str(row["evidence_code"]),
                file_id=str(row["file_id"]),
                message_index=int(row["message_index"]),
                timestamp=row["timestamp"],
                source_ref_hash=_source_hash(row["source_tag"]),
                sender_hash=str(row["sender_hash"] or ""),
                reference_hash=reference_hash,
            )
        )
    return events


def _reason_codes(value: str) -> tuple[str, ...]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return ()
    if not isinstance(parsed, list):
        return ()
    return tuple(sorted(str(item) for item in parsed if str(item)))


def read_followup_events(db_path: Path) -> list[DomainEvent]:
    """Read follow-up/risk queue items as normalized domain events."""
    with _connect_readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT file_id, source_tag, message_index, timestamp, sender_hash,
                   queue_bucket, severity, score, reason_codes_json
            FROM queue_items
            ORDER BY file_id, message_index
            """
        ).fetchall()

    events: list[DomainEvent] = []
    for row in rows:
        reasons = _reason_codes(str(row["reason_codes_json"] or "[]")) or (
            "queue_item",
        )
        for reason in reasons:
            events.append(
                _event(
                    domain_code="followup_risk",
                    event_code=str(row["queue_bucket"]),
                    evidence_code=reason,
                    file_id=str(row["file_id"]),
                    message_index=int(row["message_index"]),
                    timestamp=row["timestamp"],
                    source_ref_hash=_source_hash(row["source_tag"]),
                    sender_hash=str(row["sender_hash"] or ""),
                    score=float(row["score"]),
                    severity=str(row["severity"] or ""),
                )
            )
    return events


def dedupe_events(events: Iterable[DomainEvent]) -> list[DomainEvent]:
    """Deduplicate by event_id while preserving first-seen order."""
    deduped: list[DomainEvent] = []
    seen: set[str] = set()
    for event in events:
        if event.event_id in seen:
            continue
        seen.add(event.event_id)
        deduped.append(event)
    return deduped


def build_event_index(
    *,
    document_db: Path,
    lifecycle_db: Path,
    tax_db: Path,
    followup_db: Path,
) -> DomainEventIndex:
    """Build normalized domain events from local derived artifacts."""
    readers = (
        ("document_requirement", document_db, read_document_events),
        ("immigration_lifecycle", lifecycle_db, read_lifecycle_events),
        ("tax_payment", tax_db, read_tax_events),
        ("followup_risk", followup_db, read_followup_events),
    )
    events: list[DomainEvent] = []
    input_status: dict[str, int] = {}
    for domain_code, db_path, reader in readers:
        domain_events = reader(db_path)
        input_status[domain_code] = len(domain_events)
        events.extend(domain_events)
    return DomainEventIndex(events=dedupe_events(events), input_status=input_status)


def _message_key(event: DomainEvent) -> tuple[str, int]:
    return (event.file_id, event.message_index)


def _domain_totals(events: Sequence[DomainEvent]) -> list[tuple[str, int, int, int]]:
    hit_counts = Counter(event.domain_code for event in events)
    messages: dict[str, set[tuple[str, int]]] = defaultdict(set)
    files: dict[str, set[str]] = defaultdict(set)
    for event in events:
        messages[event.domain_code].add(_message_key(event))
        files[event.domain_code].add(event.file_id)
    return [
        (domain, count, len(messages[domain]), len(files[domain]))
        for domain, count in hit_counts.most_common()
    ]


def _event_totals(
    events: Sequence[DomainEvent],
) -> list[tuple[str, str, int, int, int]]:
    hit_counts = Counter((event.domain_code, event.event_code) for event in events)
    messages: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(set)
    files: dict[tuple[str, str], set[str]] = defaultdict(set)
    for event in events:
        key = (event.domain_code, event.event_code)
        messages[key].add(_message_key(event))
        files[key].add(event.file_id)
    return [
        (domain, code, count, len(messages[(domain, code)]), len(files[(domain, code)]))
        for (domain, code), count in hit_counts.most_common()
    ]


def _month_totals(events: Sequence[DomainEvent]) -> list[tuple[str, str, int, int]]:
    hit_counts = Counter((event.month, event.domain_code) for event in events)
    messages: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(set)
    for event in events:
        messages[(event.month, event.domain_code)].add(_message_key(event))
    return sorted(
        (
            (month, domain, count, len(messages[(month, domain)]))
            for (month, domain), count in hit_counts.items()
        ),
        key=lambda row: (-row[2], row[0], row[1]),
    )


def _domain_cooccurrence(
    events: Sequence[DomainEvent],
) -> list[tuple[str, str, int, int]]:
    domains_by_message: dict[tuple[str, int], set[str]] = defaultdict(set)
    files_by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    for event in events:
        domains_by_message[_message_key(event)].add(event.domain_code)

    counts: Counter[tuple[str, str]] = Counter()
    file_by_message = {_message_key(event): event.file_id for event in events}
    for key, domains in domains_by_message.items():
        for left, right in combinations(sorted(domains), 2):
            pair = (left, right)
            counts[pair] += 1
            files_by_pair[pair].add(file_by_message[key])
    return [
        (left, right, count, len(files_by_pair[(left, right)]))
        for (left, right), count in counts.most_common()
    ]


def write_sqlite(
    *,
    output_db: Path,
    index: DomainEventIndex,
) -> None:
    """Write the ignored local domain event index."""
    output_db.parent.mkdir(parents=True, exist_ok=True)
    if output_db.exists():
        output_db.unlink()
    events = index.events
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            CREATE TABLE event_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                event_count INTEGER NOT NULL
            );

            CREATE TABLE input_event_counts (
                domain_code TEXT PRIMARY KEY,
                input_event_count INTEGER NOT NULL
            );

            CREATE TABLE domain_events (
                event_id TEXT PRIMARY KEY,
                domain_code TEXT NOT NULL,
                event_code TEXT NOT NULL,
                evidence_code TEXT NOT NULL,
                file_id TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                month TEXT NOT NULL,
                source_ref_hash TEXT NOT NULL,
                sender_hash TEXT NOT NULL,
                score REAL NOT NULL,
                severity TEXT NOT NULL,
                reference_hash TEXT NOT NULL
            );

            CREATE TABLE domain_totals (
                domain_code TEXT PRIMARY KEY,
                event_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                file_count INTEGER NOT NULL
            );

            CREATE TABLE event_code_totals (
                domain_code TEXT NOT NULL,
                event_code TEXT NOT NULL,
                event_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                file_count INTEGER NOT NULL,
                PRIMARY KEY (domain_code, event_code)
            );

            CREATE TABLE month_domain_totals (
                month TEXT NOT NULL,
                domain_code TEXT NOT NULL,
                event_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                PRIMARY KEY (month, domain_code)
            );

            CREATE TABLE domain_cooccurrence (
                domain_code_a TEXT NOT NULL,
                domain_code_b TEXT NOT NULL,
                message_count INTEGER NOT NULL,
                file_count INTEGER NOT NULL,
                PRIMARY KEY (domain_code_a, domain_code_b)
            );

            CREATE INDEX idx_domain_events_message ON domain_events(file_id, message_index);
            CREATE INDEX idx_domain_events_domain ON domain_events(domain_code, event_code);
            CREATE INDEX idx_domain_events_month ON domain_events(month);
            """
        )
        conn.execute(
            """
            INSERT INTO event_runs (id, generated_at_utc, privacy_mode, event_count)
            VALUES (1, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "local_only_derived_events_no_raw_text_no_raw_values_no_raw_paths",
                len(events),
            ),
        )
        conn.executemany(
            """
            INSERT INTO input_event_counts (domain_code, input_event_count)
            VALUES (?, ?)
            """,
            sorted(index.input_status.items()),
        )
        conn.executemany(
            """
            INSERT INTO domain_events (
                event_id, domain_code, event_code, evidence_code, file_id,
                message_index, timestamp, month, source_ref_hash, sender_hash,
                score, severity, reference_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    event.event_id,
                    event.domain_code,
                    event.event_code,
                    event.evidence_code,
                    event.file_id,
                    event.message_index,
                    event.timestamp,
                    event.month,
                    event.source_ref_hash,
                    event.sender_hash,
                    event.score,
                    event.severity,
                    event.reference_hash,
                )
                for event in events
            ],
        )
        conn.executemany(
            """
            INSERT INTO domain_totals (
                domain_code, event_count, message_count, file_count
            )
            VALUES (?, ?, ?, ?)
            """,
            _domain_totals(events),
        )
        conn.executemany(
            """
            INSERT INTO event_code_totals (
                domain_code, event_code, event_count, message_count, file_count
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            _event_totals(events),
        )
        conn.executemany(
            """
            INSERT INTO month_domain_totals (
                month, domain_code, event_count, message_count
            )
            VALUES (?, ?, ?, ?)
            """,
            _month_totals(events),
        )
        conn.executemany(
            """
            INSERT INTO domain_cooccurrence (
                domain_code_a, domain_code_b, message_count, file_count
            )
            VALUES (?, ?, ?, ?)
            """,
            _domain_cooccurrence(events),
        )
        conn.commit()


def write_summary(
    *,
    summary_path: Path,
    output_db: Path,
    index: DomainEventIndex,
    summary_limit: int,
) -> None:
    """Write tracked aggregate summary for the domain event index."""
    events = index.events
    message_count = len({_message_key(event) for event in events})
    file_count = len({event.file_id for event in events})
    lines = [
        "# WhatsApp Domain Event Index Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Local event SQLite artifact: `{output_db.name}`",
        "",
        "## Privacy Mode",
        "",
        "- This tracked summary contains no raw message text.",
        "- This tracked summary contains no message snippets.",
        "- This tracked summary contains no phone numbers or emails.",
        "- This tracked summary contains no raw source paths or raw extracted values.",
        "- The ignored local SQLite stores normalized event codes plus local IDs and hashes only.",
        "- This builder reads only derived extractor DBs, not the raw parsed-message DB.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Domain events | {len(events)} |",
        f"| Messages with any domain event | {message_count} |",
        f"| Files with any domain event | {file_count} |",
        f"| Input domains | {len(index.input_status)} |",
        "",
        "## Input Event Counts",
        "",
        "| Domain | Input events |",
        "|---|---:|",
    ]
    for domain, count in sorted(index.input_status.items()):
        lines.append(f"| {domain} | {count} |")

    lines.extend(
        [
            "",
            "## Domain Totals",
            "",
            "| Domain | Events | Messages | Files |",
            "|---|---:|---:|---:|",
        ]
    )
    for domain, event_count, domain_message_count, domain_file_count in _domain_totals(
        events
    ):
        lines.append(
            f"| {domain} | {event_count} | {domain_message_count} | {domain_file_count} |"
        )

    lines.extend(
        [
            "",
            "## Top Event Codes",
            "",
            "| Domain | Event code | Events | Messages | Files |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for (
        domain,
        code,
        event_count,
        event_message_count,
        event_file_count,
    ) in _event_totals(events)[:summary_limit]:
        lines.append(
            f"| {domain} | {code} | {event_count} | {event_message_count} | {event_file_count} |"
        )

    lines.extend(
        [
            "",
            "## Top Month x Domain Buckets",
            "",
            "| Month | Domain | Events | Messages |",
            "|---|---|---:|---:|",
        ]
    )
    for month, domain, event_count, event_message_count in _month_totals(events)[
        :summary_limit
    ]:
        lines.append(f"| {month} | {domain} | {event_count} | {event_message_count} |")

    lines.extend(
        [
            "",
            "## Domain Co-Occurrence",
            "",
            "| Domain A | Domain B | Messages | Files |",
            "|---|---|---:|---:|",
        ]
    )
    for left, right, co_message_count, co_file_count in _domain_cooccurrence(events):
        lines.append(f"| {left} | {right} | {co_message_count} | {co_file_count} |")

    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            "Use `allowed_domain_events.local.sqlite` as the input for local case-window stitching and document/lifecycle gap analysis. Do not resolve local IDs outside owner-review tools.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_domain_event_index(
    *,
    document_db: Path,
    lifecycle_db: Path,
    tax_db: Path,
    followup_db: Path,
    output_db: Path,
    summary_path: Path,
    summary_limit: int = 25,
) -> DomainEventIndex:
    """Build and persist the normalized domain event index."""
    index = build_event_index(
        document_db=document_db,
        lifecycle_db=lifecycle_db,
        tax_db=tax_db,
        followup_db=followup_db,
    )
    write_sqlite(output_db=output_db, index=index)
    write_summary(
        summary_path=summary_path,
        output_db=output_db,
        index=index,
        summary_limit=summary_limit,
    )
    return index


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a normalized local domain event index from derived WhatsApp artifacts."
    )
    parser.add_argument("--document-db", type=Path, default=DEFAULT_DOCUMENT_DB)
    parser.add_argument("--lifecycle-db", type=Path, default=DEFAULT_LIFECYCLE_DB)
    parser.add_argument("--tax-db", type=Path, default=DEFAULT_TAX_DB)
    parser.add_argument("--followup-db", type=Path, default=DEFAULT_FOLLOWUP_DB)
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
        index = build_domain_event_index(
            document_db=args.document_db,
            lifecycle_db=args.lifecycle_db,
            tax_db=args.tax_db,
            followup_db=args.followup_db,
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
                "event_count": len(index.events),
                "input_status": index.input_status,
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
