from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Iterable

from scripts.whatsapp_corpus.build_registry import (
    EXPORT_NORMALIZED_START_RE,
    MIRROR_START_RE,
    parse_timestamp,
    short_hash,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_ALLOWLIST = Path("research/personal/wa-corpus/decisions/content_allowlist.local.jsonl")
DEFAULT_OUTPUT_DIR = Path("research/personal/wa-corpus/analysis")

URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_LIKE_RE = re.compile(r"(?:\+?\d[\d\s().-]{6,}\d)")
MEDIA_OMITTED_RE = re.compile(r"<[^>]*media[^>]*omitted[^>]*>", re.IGNORECASE)


@dataclass(frozen=True)
class AllowlistRow:
    file_id: str
    source: str
    source_tag: str | None
    path_hash: str
    classification_label: str
    privacy_tier: str
    processing_gate: str
    effective_decision: str
    decision_bucket: str
    local_path: Path


@dataclass(frozen=True)
class ParsedMessage:
    file_id: str
    source: str
    source_tag: str | None
    path_hash: str
    message_index: int
    timestamp: str | None
    sender_raw: str | None
    sender_hash: str | None
    direction: str | None
    is_system_event: bool
    body_text: str
    body_char_count: int
    body_line_count: int
    has_url: bool
    has_email: bool
    has_phone_like: bool
    has_media_omitted: bool


@dataclass(frozen=True)
class FileParseSummary:
    file_id: str
    source: str
    source_tag: str | None
    path_hash: str
    parsed_messages: int
    system_events: int
    distinct_sender_hashes: int
    min_timestamp: str | None
    max_timestamp: str | None
    body_chars: int
    warning_codes: tuple[str, ...]


def read_allowlist(path: Path) -> list[AllowlistRow]:
    """Read local allowlist rows with raw paths."""
    if not path.exists():
        raise FileNotFoundError(f"Allowlist does not exist: {path}")

    rows: list[AllowlistRow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        rows.append(
            AllowlistRow(
                file_id=raw["file_id"],
                source=raw["source"],
                source_tag=raw.get("source_tag"),
                path_hash=raw["path_hash"],
                classification_label=raw["classification_label"],
                privacy_tier=raw["privacy_tier"],
                processing_gate=raw["processing_gate"],
                effective_decision=raw["effective_decision"],
                decision_bucket=raw["decision_bucket"],
                local_path=Path(raw["local_path"]),
            )
        )
    return rows


def sender_hash(sender: str | None) -> str | None:
    """Hash sender labels for aggregate analysis."""
    if not sender:
        return None
    return short_hash(sender.strip().casefold(), length=16)


def message_flags(body: str) -> tuple[bool, bool, bool, bool]:
    """Return lightweight feature flags for a message body."""
    return (
        bool(URL_RE.search(body)),
        bool(EMAIL_RE.search(body)),
        bool(PHONE_LIKE_RE.search(body)),
        bool(MEDIA_OMITTED_RE.search(body)),
    )


def parse_export_start(line: str) -> tuple[str | None, str | None, bool, str] | None:
    """Parse a WhatsApp export message-start line."""
    match = EXPORT_NORMALIZED_START_RE.match(line)
    if not match:
        return None

    timestamp = parse_timestamp("whatsapp_export", match)
    rest = match.group("rest").strip()
    if ": " in rest:
        sender, body = rest.split(": ", 1)
        return timestamp, sender.strip() or None, False, body
    return timestamp, None, True, rest


def parse_mirror_start(line: str) -> tuple[str | None, str | None, bool, str] | None:
    """Parse a wa-mirror DB message-start line."""
    match = MIRROR_START_RE.match(line)
    if not match:
        return None
    timestamp = parse_timestamp("wa_mirror_db", match)
    direction = match.group("direction")
    body = line[match.end() :].strip()
    return timestamp, direction, False, body


def parse_allowed_file(row: AllowlistRow) -> tuple[list[ParsedMessage], FileParseSummary]:
    """Parse one allowed file into raw local message rows."""
    parser = "wa_mirror_db" if row.source == "01_wa-mirror-db" else "whatsapp_export"
    text = row.local_path.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    messages: list[ParsedMessage] = []
    current: dict[str, object] | None = None
    warning_codes: list[str] = []

    def flush_current() -> None:
        nonlocal current
        if current is None:
            return
        body_lines = current["body_lines"]
        if not isinstance(body_lines, list):
            raise TypeError("body_lines must be a list")
        body = "\n".join(str(line) for line in body_lines).strip()
        has_url, has_email, has_phone_like, has_media_omitted = message_flags(body)
        sender_value = current["sender_raw"]
        direction_value = current["direction"]
        messages.append(
            ParsedMessage(
                file_id=row.file_id,
                source=row.source,
                source_tag=row.source_tag,
                path_hash=row.path_hash,
                message_index=len(messages) + 1,
                timestamp=current["timestamp"] if isinstance(current["timestamp"], str) else None,
                sender_raw=sender_value if isinstance(sender_value, str) else None,
                sender_hash=sender_hash(sender_value if isinstance(sender_value, str) else None),
                direction=direction_value if isinstance(direction_value, str) else None,
                is_system_event=bool(current["is_system_event"]),
                body_text=body,
                body_char_count=len(body),
                body_line_count=max(1, len(body_lines)),
                has_url=has_url,
                has_email=has_email,
                has_phone_like=has_phone_like,
                has_media_omitted=has_media_omitted,
            )
        )
        current = None

    for line in lines:
        parsed = parse_mirror_start(line) if parser == "wa_mirror_db" else parse_export_start(line)
        if parsed is None:
            if current is not None:
                current_body = current["body_lines"]
                if not isinstance(current_body, list):
                    raise TypeError("body_lines must be a list")
                current_body.append(line)
            continue

        flush_current()
        timestamp, sender_raw, is_system_event, body = parsed
        current = {
            "timestamp": timestamp,
            "sender_raw": sender_raw,
            "direction": sender_raw if parser == "wa_mirror_db" else None,
            "is_system_event": is_system_event,
            "body_lines": [body],
        }

    flush_current()

    if not messages:
        warning_codes.append("zero_messages_parsed")
    timestamps = [message.timestamp for message in messages if message.timestamp]
    sender_hashes = {message.sender_hash for message in messages if message.sender_hash}
    summary = FileParseSummary(
        file_id=row.file_id,
        source=row.source,
        source_tag=row.source_tag,
        path_hash=row.path_hash,
        parsed_messages=len(messages),
        system_events=sum(1 for message in messages if message.is_system_event),
        distinct_sender_hashes=len(sender_hashes),
        min_timestamp=min(timestamps) if timestamps else None,
        max_timestamp=max(timestamps) if timestamps else None,
        body_chars=sum(message.body_char_count for message in messages),
        warning_codes=tuple(warning_codes),
    )
    return messages, summary


def parse_allowed_messages(rows: Iterable[AllowlistRow]) -> tuple[list[ParsedMessage], list[FileParseSummary]]:
    """Parse all allowlisted files."""
    all_messages: list[ParsedMessage] = []
    summaries: list[FileParseSummary] = []
    for row in rows:
        messages, summary = parse_allowed_file(row)
        all_messages.extend(messages)
        summaries.append(summary)
    return all_messages, summaries


def write_sqlite(
    *,
    db_path: Path,
    allowlist_path: Path,
    messages: list[ParsedMessage],
    summaries: list[FileParseSummary],
) -> None:
    """Write raw parsed messages to an ignored local SQLite database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE parse_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at TEXT NOT NULL,
                allowlist_path TEXT NOT NULL,
                privacy_mode TEXT NOT NULL
            );

            CREATE TABLE parsed_messages (
                file_id TEXT NOT NULL,
                source TEXT NOT NULL,
                source_tag TEXT,
                path_hash TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                sender_raw TEXT,
                sender_hash TEXT,
                direction TEXT,
                is_system_event INTEGER NOT NULL,
                body_text TEXT NOT NULL,
                body_char_count INTEGER NOT NULL,
                body_line_count INTEGER NOT NULL,
                has_url INTEGER NOT NULL,
                has_email INTEGER NOT NULL,
                has_phone_like INTEGER NOT NULL,
                has_media_omitted INTEGER NOT NULL,
                PRIMARY KEY (file_id, message_index)
            );

            CREATE TABLE file_parse_summaries (
                file_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_tag TEXT,
                path_hash TEXT NOT NULL,
                parsed_messages INTEGER NOT NULL,
                system_events INTEGER NOT NULL,
                distinct_sender_hashes INTEGER NOT NULL,
                min_timestamp TEXT,
                max_timestamp TEXT,
                body_chars INTEGER NOT NULL,
                warning_codes_json TEXT NOT NULL
            );

            CREATE INDEX idx_parsed_messages_timestamp ON parsed_messages(timestamp);
            CREATE INDEX idx_parsed_messages_file ON parsed_messages(file_id);
            CREATE INDEX idx_parsed_messages_sender_hash ON parsed_messages(sender_hash);
            """
        )
        conn.execute(
            """
            INSERT INTO parse_runs (id, generated_at, allowlist_path, privacy_mode)
            VALUES (1, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                allowlist_path.as_posix(),
                "local_only_raw_text_in_ignored_sqlite_tracked_summary_aggregate_only",
            ),
        )
        conn.executemany(
            """
            INSERT INTO parsed_messages (
                file_id, source, source_tag, path_hash, message_index, timestamp,
                sender_raw, sender_hash, direction, is_system_event, body_text,
                body_char_count, body_line_count, has_url, has_email,
                has_phone_like, has_media_omitted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    message.file_id,
                    message.source,
                    message.source_tag,
                    message.path_hash,
                    message.message_index,
                    message.timestamp,
                    message.sender_raw,
                    message.sender_hash,
                    message.direction,
                    1 if message.is_system_event else 0,
                    message.body_text,
                    message.body_char_count,
                    message.body_line_count,
                    1 if message.has_url else 0,
                    1 if message.has_email else 0,
                    1 if message.has_phone_like else 0,
                    1 if message.has_media_omitted else 0,
                )
                for message in messages
            ],
        )
        conn.executemany(
            """
            INSERT INTO file_parse_summaries (
                file_id, source, source_tag, path_hash, parsed_messages,
                system_events, distinct_sender_hashes, min_timestamp,
                max_timestamp, body_chars, warning_codes_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    summary.file_id,
                    summary.source,
                    summary.source_tag,
                    summary.path_hash,
                    summary.parsed_messages,
                    summary.system_events,
                    summary.distinct_sender_hashes,
                    summary.min_timestamp,
                    summary.max_timestamp,
                    summary.body_chars,
                    json.dumps(summary.warning_codes),
                )
                for summary in summaries
            ],
        )
        conn.commit()


def month_key(timestamp: str | None) -> str | None:
    """Return YYYY-MM for an ISO timestamp."""
    if not timestamp or len(timestamp) < 7:
        return None
    return timestamp[:7]


def year_key(timestamp: str | None) -> str | None:
    """Return YYYY for an ISO timestamp."""
    if not timestamp or len(timestamp) < 4:
        return None
    return timestamp[:4]


def write_summary(
    *,
    summary_path: Path,
    allowlist_path: Path,
    db_path: Path,
    messages: list[ParsedMessage],
    summaries: list[FileParseSummary],
) -> None:
    """Write aggregate-only analysis summary safe for git."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    file_count = len(summaries)
    parsed_count = len(messages)
    body_lengths = [message.body_char_count for message in messages]
    timestamps = [message.timestamp for message in messages if message.timestamp]
    source_counts = Counter(summary.source for summary in summaries)
    source_tag_counts = Counter(summary.source_tag or "" for summary in summaries)
    year_counts = Counter(year for year in (year_key(message.timestamp) for message in messages) if year)
    month_counts = Counter(month for month in (month_key(message.timestamp) for message in messages) if month)
    feature_counts = {
        "system_events": sum(1 for message in messages if message.is_system_event),
        "url": sum(1 for message in messages if message.has_url),
        "email": sum(1 for message in messages if message.has_email),
        "phone_like": sum(1 for message in messages if message.has_phone_like),
        "media_omitted": sum(1 for message in messages if message.has_media_omitted),
    }
    distinct_sender_hashes = {message.sender_hash for message in messages if message.sender_hash}
    warning_counts: Counter[str] = Counter()
    for summary in summaries:
        warning_counts.update(summary.warning_codes)

    lines: list[str] = [
        "# WhatsApp Allowlist Parse Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Input allowlist artifact: `{allowlist_path.name}`",
        f"Local raw SQLite artifact: `{db_path.name}`",
        "",
        "## Privacy Mode",
        "",
        "- This tracked summary contains no raw message text.",
        "- This tracked summary contains no message snippets.",
        "- This tracked summary contains no phone numbers.",
        "- This tracked summary contains no raw source paths.",
        "- This tracked summary contains no raw contact names.",
        "- Raw parsed text and raw sender labels live only in the ignored local SQLite database.",
        "",
        "## Scope",
        "",
        "- Parsed only files present in `content_allowlist.local.jsonl`.",
        "- Denylist and holdlist files were not opened.",
        "- Parser uses normalized WhatsApp timestamp starts, including invisible Unicode-prefixed export lines.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Allowlisted files parsed | {file_count} |",
        f"| Parsed messages | {parsed_count} |",
        f"| Distinct sender hashes | {len(distinct_sender_hashes)} |",
        f"| Total body characters | {sum(body_lengths)} |",
        f"| Median body characters | {int(median(body_lengths)) if body_lengths else 0} |",
        f"| Min timestamp | {min(timestamps) if timestamps else ''} |",
        f"| Max timestamp | {max(timestamps) if timestamps else ''} |",
        "",
        "## Sources",
        "",
        "| Source | Files |",
        "|---|---:|",
    ]
    for source, count in source_counts.most_common():
        lines.append(f"| {source} | {count} |")

    lines.extend(
        [
            "",
            "## Source Tags",
            "",
            "| Source tag | Files |",
            "|---|---:|",
        ]
    )
    for tag, count in source_tag_counts.most_common():
        lines.append(f"| {tag} | {count} |")

    lines.extend(
        [
            "",
            "## Message Features",
            "",
            "| Feature | Messages |",
            "|---|---:|",
        ]
    )
    for feature, count in feature_counts.items():
        lines.append(f"| {feature} | {count} |")

    lines.extend(
        [
            "",
            "## Messages By Year",
            "",
            "| Year | Messages |",
            "|---|---:|",
        ]
    )
    for year, count in sorted(year_counts.items()):
        lines.append(f"| {year} | {count} |")

    lines.extend(
        [
            "",
            "## Top Months",
            "",
            "| Month | Messages |",
            "|---|---:|",
        ]
    )
    for month, count in month_counts.most_common(20):
        lines.append(f"| {month} | {count} |")

    lines.extend(
        [
            "",
            "## Parse Warnings",
            "",
            "| Warning | Files |",
            "|---|---:|",
        ]
    )
    if warning_counts:
        for warning, count in warning_counts.most_common():
            lines.append(f"| {warning} | {count} |")
    else:
        lines.append("| none | 0 |")

    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            "Build local-only aggregate extractors against the ignored SQLite database. Any report committed to git must stay aggregate-only unless explicitly approved.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_allowlist_to_outputs(
    *,
    allowlist_path: Path,
    output_dir: Path,
) -> tuple[list[ParsedMessage], list[FileParseSummary]]:
    """Parse allowlisted files and write local SQLite plus safe summary."""
    rows = read_allowlist(allowlist_path)
    messages, summaries = parse_allowed_messages(rows)
    db_path = output_dir / "allowed_messages.local.sqlite"
    summary_path = output_dir / "allowed_messages_summary.md"
    write_sqlite(
        db_path=db_path,
        allowlist_path=allowlist_path,
        messages=messages,
        summaries=summaries,
    )
    write_summary(
        summary_path=summary_path,
        allowlist_path=allowlist_path,
        db_path=db_path,
        messages=messages,
        summaries=summaries,
    )
    return messages, summaries


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Parse only WhatsApp files from the local content allowlist."
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=DEFAULT_ALLOWLIST,
        help="content_allowlist.local.jsonl produced by compile_review_decisions.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for ignored raw SQLite and aggregate summary.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)
    try:
        messages, summaries = parse_allowlist_to_outputs(
            allowlist_path=args.allowlist,
            output_dir=args.output_dir,
        )
    except FileNotFoundError as exc:
        LOGGER.error("%s", exc)
        return 2

    LOGGER.info("Parsed %d messages from %d allowlisted files.", len(messages), len(summaries))
    LOGGER.info("Wrote %s", args.output_dir / "allowed_messages.local.sqlite")
    LOGGER.info("Wrote %s", args.output_dir / "allowed_messages_summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
