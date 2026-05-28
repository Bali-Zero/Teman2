#!/usr/bin/env python3
"""Build aggregate follow-up and risk queue artifacts from local WhatsApp indexes.

This script is intentionally local-only. It may read raw message text from the
ignored ``allowed_messages.local.sqlite`` database to classify queue signals,
but it writes only reason codes, hashed/local IDs, timestamps, and aggregate
counts. The tracked markdown summary must never contain raw message text,
contact names, phone numbers, emails, source paths, or extracted values.
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
from pathlib import Path
from typing import Any, Iterable, Sequence

DEFAULT_ANALYSIS_DIR = Path("research/personal/wa-corpus/analysis")
DEFAULT_MESSAGES_DB = DEFAULT_ANALYSIS_DIR / "allowed_messages.local.sqlite"
DEFAULT_SIGNAL_DB = DEFAULT_ANALYSIS_DIR / "allowed_signal_hits.local.sqlite"
DEFAULT_TEMPORAL_DB = DEFAULT_ANALYSIS_DIR / "allowed_temporal.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_ANALYSIS_DIR / "allowed_followup_risk.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_ANALYSIS_DIR / "allowed_followup_risk_summary.md"

ALLOWED_MESSAGES_NAME = "allowed_messages.local.sqlite"
ALLOWED_SIGNAL_NAME = "allowed_signal_hits.local.sqlite"
ALLOWED_TEMPORAL_NAME = "allowed_temporal.local.sqlite"

MESSAGE_SELECT = """
SELECT file_id, source_tag, message_index, timestamp, sender_hash, direction,
       is_system_event, body_text, body_char_count
FROM parsed_messages
ORDER BY file_id, message_index
"""

SIGNAL_SELECT = """
SELECT file_id, message_index, signal_code
FROM signal_hits
"""

FOLLOWUP_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bfollow[ -]?up\b", re.I),
    re.compile(r"\b(update|status|progress|any news|checking in)\b", re.I),
    re.compile(r"\b(cek|check|lanjut|follow)\b", re.I),
)
REMINDER_WAITING_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(remind|reminder|pending|waiting|still waiting)\b", re.I),
    re.compile(r"\b(menunggu|nunggu|tunggu|belum|masih tunggu)\b", re.I),
)
RISK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(urgent|asap|blocked|problem|issue|mistake|error|failed?|reject(?:ed)?|"
        r"expired|complain|complaint|cancel(?:led)?|penalty|fine|overstay)\b",
        re.I,
    ),
    re.compile(r"\b(masalah|kendala|salah|ditolak|telat|terlambat|denda)\b", re.I),
)
DEADLINE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(deadline|due|eod|today|tomorrow|tonight|this week)\b", re.I),
    re.compile(r"\b(besok|hari ini|minggu ini|sebelum|tanggal|tgl)\b", re.I),
    re.compile(r"\b(by|before)\s+[A-Za-z]{3,}\b", re.I),
    re.compile(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b"),
)
REQUEST_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\?", re.I),
    re.compile(
        r"\b(please|pls|kindly|can you|could you|need|send|share|provide|upload|"
        r"submit|confirm|confirmation|status|update)\b",
        re.I,
    ),
    re.compile(r"\b(tolong|mohon|bisa|butuh|kirim|konfirmasi|cek)\b", re.I),
)

SOURCE_SIGNAL_REASONS = {
    "scheduling_followup": "source_signal_scheduling_followup",
    "urgency_risk": "source_signal_urgency_risk",
}
QUEUE_REASON_CODES = frozenset(
    {
        "explicit_followup",
        "reminder_waiting",
        "urgency_risk_problem",
        "deadline_mention",
        "repeated_request_thread",
        "unanswered_later_than_threshold",
        "source_signal_scheduling_followup",
        "source_signal_urgency_risk",
    }
)
REASON_WEIGHTS = {
    "explicit_followup": 3,
    "reminder_waiting": 2,
    "urgency_risk_problem": 4,
    "deadline_mention": 3,
    "repeated_request_thread": 3,
    "unanswered_later_than_threshold": 5,
    "source_signal_scheduling_followup": 1,
    "source_signal_urgency_risk": 2,
}
BUCKET_PRIORITY = (
    "waiting_or_unanswered",
    "risk_or_problem",
    "deadline_followup",
    "repeated_request",
    "followup_or_reminder",
)
SEVERITY_PRIORITY = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class MessageRow:
    file_id: str
    source_tag: str
    message_index: int
    timestamp: str | None
    parsed_timestamp: datetime | None
    month: str
    sender_hash: str | None
    direction: str | None
    is_system_event: bool
    body_text: str
    body_char_count: int
    signal_codes: frozenset[str]


@dataclass(frozen=True)
class QueueItem:
    file_id: str
    source_tag: str
    message_index: int
    timestamp: str | None
    month: str
    sender_hash: str | None
    direction: str | None
    queue_bucket: str
    severity: str
    score: int
    reason_codes: tuple[str, ...]
    signal_codes: tuple[str, ...]
    response_gap_hours: float | None
    body_char_count: int


@dataclass(frozen=True)
class FollowupRiskArtifacts:
    message_count: int
    signal_hit_count: int
    temporal_total_messages: int | None
    queue_items: list[QueueItem]
    bucket_counts: list[dict[str, object]]
    reason_counts: list[dict[str, object]]
    severity_counts: list[dict[str, object]]
    month_counts: list[dict[str, object]]
    source_counts: list[dict[str, object]]
    file_counts: list[dict[str, object]]
    reason_cooccurrence: list[dict[str, object]]


def _normalize_text(value: object, fallback: str) -> str:
    text = "" if value is None else str(value).strip()
    return text or fallback


def _normalize_int(value: object) -> int:
    if value is None or value == "":
        return 0
    return int(value)


def _truthy(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y"}
    return bool(value)


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds /= 1000
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None

    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    candidates = (text, text.replace(" ", "T", 1))
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _month_key(timestamp: datetime | None) -> str:
    if timestamp is None:
        return "unknown"
    return timestamp.strftime("%Y-%m")


def _validate_input_path(path: Path, expected_name: str) -> None:
    if path.name != expected_name:
        raise ValueError(f"Refusing to read {path.name!r}; expected {expected_name!r}.")
    if path.suffix == ".jsonl" or path.name.endswith(".local.jsonl"):
        raise ValueError("Refusing to read WhatsApp JSONL exports.")


def _connect_readonly(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(f"Input DB not found: {path}")
    uri = f"file:{path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _read_signal_codes(
    signal_db: Path,
) -> tuple[dict[tuple[str, int], frozenset[str]], int]:
    _validate_input_path(signal_db, ALLOWED_SIGNAL_NAME)
    signals_by_message: dict[tuple[str, int], set[str]] = defaultdict(set)
    hit_count = 0
    with _connect_readonly(signal_db) as conn:
        rows = conn.execute(SIGNAL_SELECT).fetchall()
    for row in rows:
        file_id = _normalize_text(row["file_id"], "unknown_file")
        message_index = _normalize_int(row["message_index"])
        signal_code = _normalize_text(row["signal_code"], "unknown_signal")
        signals_by_message[(file_id, message_index)].add(signal_code)
        hit_count += 1
    return {
        key: frozenset(value) for key, value in signals_by_message.items()
    }, hit_count


def _read_messages(
    messages_db: Path,
    signals_by_message: dict[tuple[str, int], frozenset[str]],
) -> list[MessageRow]:
    _validate_input_path(messages_db, ALLOWED_MESSAGES_NAME)
    with _connect_readonly(messages_db) as conn:
        rows = conn.execute(MESSAGE_SELECT).fetchall()

    messages: list[MessageRow] = []
    for row in rows:
        file_id = _normalize_text(row["file_id"], "unknown_file")
        message_index = _normalize_int(row["message_index"])
        timestamp = None if row["timestamp"] is None else str(row["timestamp"])
        parsed_timestamp = _parse_timestamp(timestamp)
        messages.append(
            MessageRow(
                file_id=file_id,
                source_tag=_normalize_text(row["source_tag"], "unknown_source"),
                message_index=message_index,
                timestamp=timestamp,
                parsed_timestamp=parsed_timestamp,
                month=_month_key(parsed_timestamp),
                sender_hash=None
                if row["sender_hash"] is None
                else str(row["sender_hash"]),
                direction=None if row["direction"] is None else str(row["direction"]),
                is_system_event=_truthy(row["is_system_event"]),
                body_text=str(row["body_text"] or ""),
                body_char_count=_normalize_int(row["body_char_count"]),
                signal_codes=signals_by_message.get(
                    (file_id, message_index), frozenset()
                ),
            )
        )
    return messages


def _read_temporal_total(temporal_db: Path | None) -> int | None:
    if temporal_db is None:
        return None
    _validate_input_path(temporal_db, ALLOWED_TEMPORAL_NAME)
    if not temporal_db.exists():
        return None
    with _connect_readonly(temporal_db) as conn:
        row = conn.execute(
            "SELECT value FROM metadata WHERE key = 'total_messages'"
        ).fetchone()
    if row is None:
        return None
    return int(row["value"])


def _has_any_pattern(patterns: Sequence[re.Pattern[str]], body: str) -> bool:
    return any(pattern.search(body) for pattern in patterns)


def _detect_base_reasons(message: MessageRow) -> set[str]:
    if message.is_system_event:
        return set()

    reasons: set[str] = set()
    body = message.body_text
    if _has_any_pattern(FOLLOWUP_PATTERNS, body):
        reasons.add("explicit_followup")
    if _has_any_pattern(REMINDER_WAITING_PATTERNS, body):
        reasons.add("reminder_waiting")
    if _has_any_pattern(RISK_PATTERNS, body):
        reasons.add("urgency_risk_problem")
    if _has_any_pattern(DEADLINE_PATTERNS, body):
        reasons.add("deadline_mention")

    for signal_code, reason_code in SOURCE_SIGNAL_REASONS.items():
        if signal_code in message.signal_codes:
            reasons.add(reason_code)
    return reasons


def _is_request_like(message: MessageRow, reasons: set[str]) -> bool:
    if message.is_system_event:
        return False
    if reasons.intersection(
        {
            "explicit_followup",
            "reminder_waiting",
            "urgency_risk_problem",
            "deadline_mention",
            "source_signal_scheduling_followup",
            "source_signal_urgency_risk",
        }
    ):
        return True
    return _has_any_pattern(REQUEST_PATTERNS, message.body_text)


def _message_sort_key(message: MessageRow) -> tuple[datetime, int]:
    return (
        message.parsed_timestamp or datetime.min.replace(tzinfo=UTC),
        message.message_index,
    )


def _detect_repeated_requests(
    messages: Sequence[MessageRow],
    reasons_by_key: dict[tuple[str, int], set[str]],
    *,
    repeat_window_hours: float,
) -> set[tuple[str, int]]:
    repeated: set[tuple[str, int]] = set()
    by_thread_sender: dict[tuple[str, str], list[MessageRow]] = defaultdict(list)
    for message in messages:
        if message.sender_hash is None:
            continue
        key = (message.file_id, message.message_index)
        if _is_request_like(message, reasons_by_key[key]):
            by_thread_sender[(message.file_id, message.sender_hash)].append(message)

    for request_messages in by_thread_sender.values():
        previous: MessageRow | None = None
        for message in sorted(request_messages, key=_message_sort_key):
            if previous is None:
                previous = message
                continue
            if (
                previous.parsed_timestamp is not None
                and message.parsed_timestamp is not None
            ):
                delta_hours = (
                    message.parsed_timestamp - previous.parsed_timestamp
                ).total_seconds() / 3600
                is_repeat = 0 <= delta_hours <= repeat_window_hours
            else:
                index_delta = message.message_index - previous.message_index
                is_repeat = 0 < index_delta <= 40
            if is_repeat:
                repeated.add((message.file_id, message.message_index))
            previous = message
    return repeated


def _detect_unanswered_late(
    messages: Sequence[MessageRow],
    reasons_by_key: dict[tuple[str, int], set[str]],
    *,
    threshold_hours: float,
    analysis_now: datetime,
) -> dict[tuple[str, int], float]:
    gap_hours_by_key: dict[tuple[str, int], float] = {}
    by_file: dict[str, list[MessageRow]] = defaultdict(list)
    for message in messages:
        by_file[message.file_id].append(message)

    for file_messages in by_file.values():
        sorted_messages = sorted(file_messages, key=_message_sort_key)
        for index, message in enumerate(sorted_messages):
            if message.sender_hash is None or message.parsed_timestamp is None:
                continue
            key = (message.file_id, message.message_index)
            if not _is_request_like(message, reasons_by_key[key]):
                continue

            response_timestamp: datetime | None = None
            for later in sorted_messages[index + 1 :]:
                if later.is_system_event or later.parsed_timestamp is None:
                    continue
                if later.sender_hash and later.sender_hash != message.sender_hash:
                    response_timestamp = later.parsed_timestamp
                    break

            comparison_timestamp = response_timestamp or analysis_now
            delta_hours = (
                comparison_timestamp - message.parsed_timestamp
            ).total_seconds() / 3600
            if delta_hours >= threshold_hours:
                gap_hours_by_key[key] = round(delta_hours, 2)
    return gap_hours_by_key


def _score_reasons(reason_codes: Iterable[str]) -> int:
    return sum(REASON_WEIGHTS.get(reason_code, 0) for reason_code in set(reason_codes))


def _severity(score: int) -> str:
    if score >= 7:
        return "high"
    if score >= 4:
        return "medium"
    return "low"


def _bucket(reason_codes: set[str]) -> str:
    if "unanswered_later_than_threshold" in reason_codes:
        return "waiting_or_unanswered"
    if (
        "urgency_risk_problem" in reason_codes
        or "source_signal_urgency_risk" in reason_codes
    ):
        return "risk_or_problem"
    if "deadline_mention" in reason_codes:
        return "deadline_followup"
    if "repeated_request_thread" in reason_codes:
        return "repeated_request"
    return "followup_or_reminder"


def _queue_sort_key(item: QueueItem) -> tuple[int, int, str, str, int]:
    return (
        SEVERITY_PRIORITY[item.severity],
        -item.score,
        item.month,
        item.file_id,
        item.message_index,
    )


def build_queue_items(
    messages: Sequence[MessageRow],
    *,
    threshold_hours: float,
    repeat_window_hours: float,
    analysis_now: datetime,
) -> list[QueueItem]:
    reasons_by_key: dict[tuple[str, int], set[str]] = {
        (message.file_id, message.message_index): _detect_base_reasons(message)
        for message in messages
    }

    repeated_keys = _detect_repeated_requests(
        messages,
        reasons_by_key,
        repeat_window_hours=repeat_window_hours,
    )
    for key in repeated_keys:
        reasons_by_key[key].add("repeated_request_thread")

    unanswered_gaps = _detect_unanswered_late(
        messages,
        reasons_by_key,
        threshold_hours=threshold_hours,
        analysis_now=analysis_now,
    )
    for key in unanswered_gaps:
        reasons_by_key[key].add("unanswered_later_than_threshold")

    queue_items: list[QueueItem] = []
    for message in messages:
        key = (message.file_id, message.message_index)
        reason_codes = reasons_by_key[key].intersection(QUEUE_REASON_CODES)
        if not reason_codes:
            continue
        score = _score_reasons(reason_codes)
        queue_items.append(
            QueueItem(
                file_id=message.file_id,
                source_tag=message.source_tag,
                message_index=message.message_index,
                timestamp=message.timestamp,
                month=message.month,
                sender_hash=message.sender_hash,
                direction=message.direction,
                queue_bucket=_bucket(reason_codes),
                severity=_severity(score),
                score=score,
                reason_codes=tuple(sorted(reason_codes)),
                signal_codes=tuple(sorted(message.signal_codes)),
                response_gap_hours=unanswered_gaps.get(key),
                body_char_count=message.body_char_count,
            )
        )
    return sorted(queue_items, key=_queue_sort_key)


def _sorted_count_rows(counter: Counter[Any], key_name: str) -> list[dict[str, object]]:
    return [
        {key_name: key, "queue_message_count": count}
        for key, count in sorted(
            counter.items(), key=lambda item: (-item[1], str(item[0]))
        )
    ]


def _reason_counts(queue_items: Sequence[QueueItem]) -> list[dict[str, object]]:
    message_counts: Counter[str] = Counter()
    files_by_reason: dict[str, set[str]] = defaultdict(set)
    high_by_reason: Counter[str] = Counter()
    for item in queue_items:
        for reason_code in item.reason_codes:
            message_counts[reason_code] += 1
            files_by_reason[reason_code].add(item.file_id)
            if item.severity == "high":
                high_by_reason[reason_code] += 1
    return [
        {
            "reason_code": reason_code,
            "queue_message_count": count,
            "file_count": len(files_by_reason[reason_code]),
            "high_severity_count": high_by_reason[reason_code],
        }
        for reason_code, count in sorted(
            message_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def _source_counts(queue_items: Sequence[QueueItem]) -> list[dict[str, object]]:
    message_counts: Counter[str] = Counter()
    files_by_source: dict[str, set[str]] = defaultdict(set)
    high_by_source: Counter[str] = Counter()
    for item in queue_items:
        message_counts[item.source_tag] += 1
        files_by_source[item.source_tag].add(item.file_id)
        if item.severity == "high":
            high_by_source[item.source_tag] += 1
    return [
        {
            "source_tag": source_tag,
            "queue_message_count": count,
            "file_count": len(files_by_source[source_tag]),
            "high_severity_count": high_by_source[source_tag],
        }
        for source_tag, count in sorted(
            message_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def _file_counts(queue_items: Sequence[QueueItem]) -> list[dict[str, object]]:
    by_file: dict[str, list[QueueItem]] = defaultdict(list)
    for item in queue_items:
        by_file[item.file_id].append(item)

    rows: list[dict[str, object]] = []
    for file_id, items in by_file.items():
        rows.append(
            {
                "file_id": file_id,
                "source_tag": ", ".join(sorted({item.source_tag for item in items})),
                "queue_message_count": len(items),
                "high_severity_count": sum(
                    1 for item in items if item.severity == "high"
                ),
                "distinct_reason_count": len(
                    {reason for item in items for reason in item.reason_codes}
                ),
                "first_month": min(item.month for item in items),
                "last_month": max(item.month for item in items),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -int(row["high_severity_count"]),
            -int(row["queue_message_count"]),
            str(row["file_id"]),
        ),
    )


def _reason_cooccurrence(queue_items: Sequence[QueueItem]) -> list[dict[str, object]]:
    pair_counts: Counter[tuple[str, str]] = Counter()
    pair_files: dict[tuple[str, str], set[str]] = defaultdict(set)
    for item in queue_items:
        reasons = sorted(set(item.reason_codes))
        for left_index, left in enumerate(reasons):
            for right in reasons[left_index + 1 :]:
                pair = (left, right)
                pair_counts[pair] += 1
                pair_files[pair].add(item.file_id)
    return [
        {
            "reason_code_a": left,
            "reason_code_b": right,
            "queue_message_count": count,
            "file_count": len(pair_files[(left, right)]),
        }
        for (left, right), count in sorted(
            pair_counts.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1]),
        )
    ]


def build_artifacts(
    messages: Sequence[MessageRow],
    queue_items: Sequence[QueueItem],
    *,
    signal_hit_count: int,
    temporal_total_messages: int | None,
) -> FollowupRiskArtifacts:
    return FollowupRiskArtifacts(
        message_count=len(messages),
        signal_hit_count=signal_hit_count,
        temporal_total_messages=temporal_total_messages,
        queue_items=list(queue_items),
        bucket_counts=_sorted_count_rows(
            Counter(item.queue_bucket for item in queue_items),
            "queue_bucket",
        ),
        reason_counts=_reason_counts(queue_items),
        severity_counts=_sorted_count_rows(
            Counter(item.severity for item in queue_items), "severity"
        ),
        month_counts=_sorted_count_rows(
            Counter(item.month for item in queue_items), "month"
        ),
        source_counts=_source_counts(queue_items),
        file_counts=_file_counts(queue_items),
        reason_cooccurrence=_reason_cooccurrence(queue_items),
    )


def _create_output_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE analysis_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE queue_items (
            file_id TEXT NOT NULL,
            source_tag TEXT NOT NULL,
            message_index INTEGER NOT NULL,
            timestamp TEXT,
            month TEXT NOT NULL,
            sender_hash TEXT,
            direction TEXT,
            queue_bucket TEXT NOT NULL,
            severity TEXT NOT NULL,
            score INTEGER NOT NULL,
            reason_codes_json TEXT NOT NULL,
            signal_codes_json TEXT NOT NULL,
            response_gap_hours REAL,
            body_char_count INTEGER NOT NULL,
            PRIMARY KEY (file_id, message_index)
        );
        CREATE TABLE bucket_counts (
            queue_bucket TEXT PRIMARY KEY,
            queue_message_count INTEGER NOT NULL
        );
        CREATE TABLE reason_counts (
            reason_code TEXT PRIMARY KEY,
            queue_message_count INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            high_severity_count INTEGER NOT NULL
        );
        CREATE TABLE severity_counts (
            severity TEXT PRIMARY KEY,
            queue_message_count INTEGER NOT NULL
        );
        CREATE TABLE month_counts (
            month TEXT PRIMARY KEY,
            queue_message_count INTEGER NOT NULL
        );
        CREATE TABLE source_counts (
            source_tag TEXT PRIMARY KEY,
            queue_message_count INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            high_severity_count INTEGER NOT NULL
        );
        CREATE TABLE file_counts (
            file_id TEXT PRIMARY KEY,
            source_tag TEXT NOT NULL,
            queue_message_count INTEGER NOT NULL,
            high_severity_count INTEGER NOT NULL,
            distinct_reason_count INTEGER NOT NULL,
            first_month TEXT NOT NULL,
            last_month TEXT NOT NULL
        );
        CREATE TABLE reason_cooccurrence (
            reason_code_a TEXT NOT NULL,
            reason_code_b TEXT NOT NULL,
            queue_message_count INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            PRIMARY KEY (reason_code_a, reason_code_b)
        );
        """
    )


def _insert_dict_rows(
    conn: sqlite3.Connection,
    table: str,
    columns: Sequence[str],
    rows: Sequence[dict[str, object]],
) -> None:
    if not rows:
        return
    column_sql = ", ".join(columns)
    placeholder_sql = ", ".join(f":{column}" for column in columns)
    conn.executemany(
        f"INSERT INTO {table} ({column_sql}) VALUES ({placeholder_sql})",
        rows,
    )


def write_output_db(
    output_db: Path,
    artifacts: FollowupRiskArtifacts,
    *,
    generated_at_utc: str,
    messages_name: str,
    signal_name: str,
    temporal_name: str | None,
    threshold_hours: float,
    repeat_window_hours: float,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    tmp_db = output_db.with_name(f"{output_db.name}.tmp")
    if tmp_db.exists():
        tmp_db.unlink()

    conn = sqlite3.connect(tmp_db)
    try:
        _create_output_schema(conn)
        metadata_rows = [
            ("generated_at_utc", generated_at_utc),
            ("messages_input_name", messages_name),
            ("signal_input_name", signal_name),
            ("temporal_input_name", temporal_name or ""),
            ("threshold_hours", str(threshold_hours)),
            ("repeat_window_hours", str(repeat_window_hours)),
            ("messages_scanned", str(artifacts.message_count)),
            ("signal_hits_read", str(artifacts.signal_hit_count)),
            ("queue_message_count", str(len(artifacts.queue_items))),
        ]
        if artifacts.temporal_total_messages is not None:
            metadata_rows.append(
                ("temporal_total_messages", str(artifacts.temporal_total_messages))
            )
        conn.executemany(
            "INSERT INTO analysis_metadata (key, value) VALUES (?, ?)", metadata_rows
        )
        conn.executemany(
            """
            INSERT INTO queue_items (
                file_id, source_tag, message_index, timestamp, month, sender_hash,
                direction, queue_bucket, severity, score, reason_codes_json,
                signal_codes_json, response_gap_hours, body_char_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.file_id,
                    item.source_tag,
                    item.message_index,
                    item.timestamp,
                    item.month,
                    item.sender_hash,
                    item.direction,
                    item.queue_bucket,
                    item.severity,
                    item.score,
                    json.dumps(item.reason_codes, sort_keys=True),
                    json.dumps(item.signal_codes, sort_keys=True),
                    item.response_gap_hours,
                    item.body_char_count,
                )
                for item in artifacts.queue_items
            ],
        )
        _insert_dict_rows(
            conn,
            "bucket_counts",
            ("queue_bucket", "queue_message_count"),
            artifacts.bucket_counts,
        )
        _insert_dict_rows(
            conn,
            "reason_counts",
            ("reason_code", "queue_message_count", "file_count", "high_severity_count"),
            artifacts.reason_counts,
        )
        _insert_dict_rows(
            conn,
            "severity_counts",
            ("severity", "queue_message_count"),
            artifacts.severity_counts,
        )
        _insert_dict_rows(
            conn,
            "month_counts",
            ("month", "queue_message_count"),
            artifacts.month_counts,
        )
        _insert_dict_rows(
            conn,
            "source_counts",
            ("source_tag", "queue_message_count", "file_count", "high_severity_count"),
            artifacts.source_counts,
        )
        _insert_dict_rows(
            conn,
            "file_counts",
            (
                "file_id",
                "source_tag",
                "queue_message_count",
                "high_severity_count",
                "distinct_reason_count",
                "first_month",
                "last_month",
            ),
            artifacts.file_counts,
        )
        _insert_dict_rows(
            conn,
            "reason_cooccurrence",
            ("reason_code_a", "reason_code_b", "queue_message_count", "file_count"),
            artifacts.reason_cooccurrence,
        )
        conn.commit()
    finally:
        conn.close()

    tmp_db.replace(output_db)


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
        lines.append(
            "| " + " | ".join(_markdown_value(row.get(key)) for key in keys) + " |"
        )
    if len(rows) > limit:
        lines.append(f"\n_Showing {limit} of {len(rows)} rows._")
    return "\n".join(lines) + "\n"


def render_summary_markdown(
    artifacts: FollowupRiskArtifacts,
    *,
    generated_at_utc: str,
    messages_name: str,
    signal_name: str,
    temporal_name: str | None,
    output_name: str,
    threshold_hours: float,
    repeat_window_hours: float,
    limit: int,
) -> str:
    high_count = sum(1 for item in artifacts.queue_items if item.severity == "high")
    medium_count = sum(1 for item in artifacts.queue_items if item.severity == "medium")
    low_count = sum(1 for item in artifacts.queue_items if item.severity == "low")
    overview_rows: list[dict[str, object]] = [
        {"metric": "Messages scanned", "value": artifacts.message_count},
        {"metric": "Signal hits read", "value": artifacts.signal_hit_count},
        {
            "metric": "Temporal total messages",
            "value": artifacts.temporal_total_messages or "",
        },
        {"metric": "Queue messages", "value": len(artifacts.queue_items)},
        {"metric": "High severity queue messages", "value": high_count},
        {"metric": "Medium severity queue messages", "value": medium_count},
        {"metric": "Low severity queue messages", "value": low_count},
        {"metric": "Threshold hours", "value": threshold_hours},
        {"metric": "Repeat window hours", "value": repeat_window_hours},
    ]
    return "\n".join(
        [
            "# WhatsApp Follow-Up Risk Queue Summary",
            "",
            f"- Generated UTC: `{generated_at_utc}`",
            f"- Messages DB: `{messages_name}`",
            f"- Signal DB: `{signal_name}`",
            f"- Temporal DB: `{temporal_name or 'not used'}`",
            f"- Local queue DB: `{output_name}`",
            "",
            "## Privacy Boundary",
            "",
            "- This tracked summary contains no raw message text or snippets.",
            "- This tracked summary contains no raw contact names, phone numbers, or emails.",
            "- This tracked summary contains no raw source paths or raw extracted values.",
            "- The ignored local SQLite queue stores only hashed/local message references, timestamps, aggregate-safe metadata, and reason codes.",
            "",
            "## Overview",
            "",
            _markdown_table(
                ("Metric", "Value"), overview_rows, keys=("metric", "value"), limit=20
            ),
            "## Queue Buckets",
            "",
            _markdown_table(
                ("Bucket", "Queue messages"),
                artifacts.bucket_counts,
                keys=("queue_bucket", "queue_message_count"),
                limit=limit,
            ),
            "## Reason Codes",
            "",
            _markdown_table(
                ("Reason code", "Queue messages", "Files", "High severity"),
                artifacts.reason_counts,
                keys=(
                    "reason_code",
                    "queue_message_count",
                    "file_count",
                    "high_severity_count",
                ),
                limit=limit,
            ),
            "## Severity",
            "",
            _markdown_table(
                ("Severity", "Queue messages"),
                artifacts.severity_counts,
                keys=("severity", "queue_message_count"),
                limit=limit,
            ),
            "## Queue By Month",
            "",
            _markdown_table(
                ("Month", "Queue messages"),
                artifacts.month_counts,
                keys=("month", "queue_message_count"),
                limit=limit,
            ),
            "## Queue By Source Tag",
            "",
            _markdown_table(
                ("Source tag", "Queue messages", "Files", "High severity"),
                artifacts.source_counts,
                keys=(
                    "source_tag",
                    "queue_message_count",
                    "file_count",
                    "high_severity_count",
                ),
                limit=limit,
            ),
            "## Top File IDs",
            "",
            _markdown_table(
                (
                    "File ID",
                    "Source tag",
                    "Queue messages",
                    "High severity",
                    "Distinct reasons",
                    "First month",
                    "Last month",
                ),
                artifacts.file_counts,
                keys=(
                    "file_id",
                    "source_tag",
                    "queue_message_count",
                    "high_severity_count",
                    "distinct_reason_count",
                    "first_month",
                    "last_month",
                ),
                limit=limit,
            ),
            "## Reason Co-Occurrence",
            "",
            _markdown_table(
                ("Reason A", "Reason B", "Queue messages", "Files"),
                artifacts.reason_cooccurrence,
                keys=(
                    "reason_code_a",
                    "reason_code_b",
                    "queue_message_count",
                    "file_count",
                ),
                limit=limit,
            ),
            "## Caveats",
            "",
            "- Queue membership is deterministic pattern matching plus timestamp/sender-hash heuristics, not a client instruction or legal conclusion.",
            "- `unanswered_later_than_threshold` uses the next different sender in the same file as the reply proxy; archived or side-channel replies can create false positives.",
            "- Deadline detection records only a boolean reason code; extracted date values are intentionally not written to the tracked summary.",
            "",
        ]
    )


def write_summary_markdown(summary_path: Path, content: str) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(content, encoding="utf-8")


def run_analysis(
    *,
    messages_db: Path,
    signal_db: Path,
    temporal_db: Path | None,
    output_db: Path,
    summary_path: Path,
    threshold_hours: float,
    repeat_window_hours: float,
    summary_limit: int,
    generated_at_utc: str | None = None,
) -> FollowupRiskArtifacts:
    if threshold_hours <= 0:
        raise ValueError("threshold_hours must be > 0")
    if repeat_window_hours <= 0:
        raise ValueError("repeat_window_hours must be > 0")
    if output_db.resolve() in {messages_db.resolve(), signal_db.resolve()}:
        raise ValueError("Output DB path must differ from input DB paths.")
    if temporal_db is not None and output_db.resolve() == temporal_db.resolve():
        raise ValueError("Output DB path must differ from temporal DB path.")

    generated_at = (
        generated_at_utc or datetime.now(tz=UTC).replace(microsecond=0).isoformat()
    )
    analysis_now = _parse_timestamp(generated_at)
    if analysis_now is None:
        raise ValueError("generated_at_utc must be an ISO timestamp when provided.")

    signals_by_message, signal_hit_count = _read_signal_codes(signal_db)
    messages = _read_messages(messages_db, signals_by_message)
    temporal_total = _read_temporal_total(temporal_db)
    queue_items = build_queue_items(
        messages,
        threshold_hours=threshold_hours,
        repeat_window_hours=repeat_window_hours,
        analysis_now=analysis_now,
    )
    artifacts = build_artifacts(
        messages,
        queue_items,
        signal_hit_count=signal_hit_count,
        temporal_total_messages=temporal_total,
    )
    write_output_db(
        output_db,
        artifacts,
        generated_at_utc=generated_at,
        messages_name=messages_db.name,
        signal_name=signal_db.name,
        temporal_name=temporal_db.name if temporal_db is not None else None,
        threshold_hours=threshold_hours,
        repeat_window_hours=repeat_window_hours,
    )
    write_summary_markdown(
        summary_path,
        render_summary_markdown(
            artifacts,
            generated_at_utc=generated_at,
            messages_name=messages_db.name,
            signal_name=signal_db.name,
            temporal_name=temporal_db.name if temporal_db is not None else None,
            output_name=output_db.name,
            threshold_hours=threshold_hours,
            repeat_window_hours=repeat_window_hours,
            limit=summary_limit,
        ),
    )
    return artifacts


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a local-only aggregate follow-up/risk queue from WhatsApp corpus DBs."
    )
    parser.add_argument("--messages-db", type=Path, default=DEFAULT_MESSAGES_DB)
    parser.add_argument("--signal-db", type=Path, default=DEFAULT_SIGNAL_DB)
    parser.add_argument("--temporal-db", type=Path, default=DEFAULT_TEMPORAL_DB)
    parser.add_argument("--output-db", type=Path, default=DEFAULT_OUTPUT_DB)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--threshold-hours", type=float, default=48.0)
    parser.add_argument("--repeat-window-hours", type=float, default=72.0)
    parser.add_argument("--summary-limit", type=int, default=25)
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable run stats."
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress success output.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    temporal_db = args.temporal_db if args.temporal_db else None
    try:
        artifacts = run_analysis(
            messages_db=args.messages_db,
            signal_db=args.signal_db,
            temporal_db=temporal_db,
            output_db=args.output_db,
            summary_path=args.summary,
            threshold_hours=args.threshold_hours,
            repeat_window_hours=args.repeat_window_hours,
            summary_limit=args.summary_limit,
        )
    except (FileNotFoundError, OSError, sqlite3.Error, ValueError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    if args.json:
        sys.stdout.write(
            json.dumps(
                {
                    "message_count": artifacts.message_count,
                    "output_db": str(args.output_db),
                    "queue_message_count": len(artifacts.queue_items),
                    "signal_hit_count": artifacts.signal_hit_count,
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
