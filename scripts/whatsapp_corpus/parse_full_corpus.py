from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Iterable, Sequence

from scripts.whatsapp_corpus.build_registry import DEFAULT_CORPUS_ROOT, parser_for
from scripts.whatsapp_corpus.parse_allowed_messages import (
    ParsedMessage,
    message_flags,
    parse_export_start,
    parse_mirror_start,
    sender_hash,
)
from scripts.whatsapp_corpus.resolve_refs import FileRef, build_file_refs

LOGGER = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path("research/personal/wa-corpus/full")
DEFAULT_DB = DEFAULT_OUTPUT_DIR / "full_messages.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_OUTPUT_DIR / "full_corpus_parse_summary.md"


@dataclass(frozen=True)
class FullFileRow:
    file_id: str
    source: str
    source_tag: str | None
    path_hash: str
    parser: str
    local_path: Path


@dataclass(frozen=True)
class FullParseSummary:
    file_id: str
    source: str
    source_tag: str | None
    path_hash: str
    parser: str
    local_path: Path
    parsed_messages: int
    system_events: int
    distinct_sender_hashes: int
    min_timestamp: str | None
    max_timestamp: str | None
    body_chars: int
    warning_codes: tuple[str, ...]


def full_rows_from_refs(root: Path, refs: Iterable[FileRef]) -> list[FullFileRow]:
    """Build full-corpus file rows from the registry-compatible local refs."""
    return [
        FullFileRow(
            file_id=ref.file_id,
            source=ref.source,
            source_tag=ref.source_tag,
            path_hash=ref.path_hash,
            parser=parser_for(root, ref.path),
            local_path=ref.path,
        )
        for ref in refs
    ]


def parse_full_file(row: FullFileRow) -> tuple[list[ParsedMessage], FullParseSummary]:
    """Parse one WhatsApp TXT file into local raw message rows."""
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
        parsed = parse_mirror_start(line) if row.parser == "wa_mirror_db" else parse_export_start(line)
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
            "direction": sender_raw if row.parser == "wa_mirror_db" else None,
            "is_system_event": is_system_event,
            "body_lines": [body],
        }

    flush_current()

    if not messages:
        warning_codes.append("zero_messages_parsed")
    timestamps = [message.timestamp for message in messages if message.timestamp]
    sender_hashes = {message.sender_hash for message in messages if message.sender_hash}
    summary = FullParseSummary(
        file_id=row.file_id,
        source=row.source,
        source_tag=row.source_tag,
        path_hash=row.path_hash,
        parser=row.parser,
        local_path=row.local_path,
        parsed_messages=len(messages),
        system_events=sum(1 for message in messages if message.is_system_event),
        distinct_sender_hashes=len(sender_hashes),
        min_timestamp=min(timestamps) if timestamps else None,
        max_timestamp=max(timestamps) if timestamps else None,
        body_chars=sum(message.body_char_count for message in messages),
        warning_codes=tuple(warning_codes),
    )
    return messages, summary


def parse_full_corpus(rows: Iterable[FullFileRow]) -> tuple[list[ParsedMessage], list[FullParseSummary]]:
    """Parse every file in the local corpus."""
    messages: list[ParsedMessage] = []
    summaries: list[FullParseSummary] = []
    for row in rows:
        file_messages, summary = parse_full_file(row)
        messages.extend(file_messages)
        summaries.append(summary)
    return messages, summaries


def write_sqlite(
    *,
    db_path: Path,
    corpus_root: Path,
    messages: list[ParsedMessage],
    summaries: list[FullParseSummary],
) -> None:
    """Write raw full-corpus messages to an ignored local SQLite database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE parse_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at TEXT NOT NULL,
                corpus_root TEXT NOT NULL,
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

            CREATE VIRTUAL TABLE parsed_messages_fts USING fts5(
                body_text,
                content='parsed_messages',
                content_rowid='rowid'
            );

            CREATE TABLE file_parse_summaries (
                file_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_tag TEXT,
                path_hash TEXT NOT NULL,
                parser TEXT NOT NULL,
                local_path TEXT NOT NULL,
                parsed_messages INTEGER NOT NULL,
                system_events INTEGER NOT NULL,
                distinct_sender_hashes INTEGER NOT NULL,
                min_timestamp TEXT,
                max_timestamp TEXT,
                body_chars INTEGER NOT NULL,
                warning_codes_json TEXT NOT NULL
            );

            CREATE INDEX idx_full_messages_timestamp ON parsed_messages(timestamp);
            CREATE INDEX idx_full_messages_file ON parsed_messages(file_id);
            CREATE INDEX idx_full_messages_sender_hash ON parsed_messages(sender_hash);
            CREATE INDEX idx_full_messages_features
                ON parsed_messages(has_url, has_email, has_phone_like);
            """
        )
        conn.execute(
            """
            INSERT INTO parse_runs (id, generated_at, corpus_root, privacy_mode)
            VALUES (1, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                corpus_root.as_posix(),
                "local_only_raw_cleartext_all_messages_ignored_sqlite",
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
        conn.execute(
            """
            INSERT INTO parsed_messages_fts(rowid, body_text)
            SELECT rowid, body_text FROM parsed_messages
            """
        )
        conn.executemany(
            """
            INSERT INTO file_parse_summaries (
                file_id, source, source_tag, path_hash, parser, local_path,
                parsed_messages, system_events, distinct_sender_hashes,
                min_timestamp, max_timestamp, body_chars, warning_codes_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    summary.file_id,
                    summary.source,
                    summary.source_tag,
                    summary.path_hash,
                    summary.parser,
                    summary.local_path.as_posix(),
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


def _month_key(timestamp: str | None) -> str | None:
    if not timestamp or len(timestamp) < 7:
        return None
    return timestamp[:7]


def _year_key(timestamp: str | None) -> str | None:
    if not timestamp or len(timestamp) < 4:
        return None
    return timestamp[:4]


def write_summary(
    *,
    summary_path: Path,
    db_path: Path,
    messages: list[ParsedMessage],
    summaries: list[FullParseSummary],
    skipped_zero_message_files: int = 0,
) -> None:
    """Write tracked aggregate-only full parse summary."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    body_lengths = [message.body_char_count for message in messages]
    timestamps = [message.timestamp for message in messages if message.timestamp]
    source_counts = Counter(summary.source for summary in summaries)
    parser_counts = Counter(summary.parser for summary in summaries)
    year_counts = Counter(year for year in (_year_key(message.timestamp) for message in messages) if year)
    month_counts = Counter(month for month in (_month_key(message.timestamp) for message in messages) if month)
    feature_counts = {
        "system_events": sum(1 for message in messages if message.is_system_event),
        "url": sum(1 for message in messages if message.has_url),
        "email": sum(1 for message in messages if message.has_email),
        "phone_like": sum(1 for message in messages if message.has_phone_like),
        "media_omitted": sum(1 for message in messages if message.has_media_omitted),
    }
    warning_counts: Counter[str] = Counter()
    for summary in summaries:
        warning_counts.update(summary.warning_codes)
    distinct_sender_hashes = {message.sender_hash for message in messages if message.sender_hash}

    lines = [
        "# WhatsApp Full Corpus Parse Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Local raw SQLite artifact: `{db_path.name}`",
        "",
        "## Privacy Mode",
        "",
        "- This tracked summary contains no raw message text.",
        "- This tracked summary contains no message snippets.",
        "- This tracked summary contains no phone numbers or emails.",
        "- This tracked summary contains no raw source paths or contact names.",
        "- The full raw cleartext corpus lives only in the ignored local SQLite database.",
        "- The SQLite database includes an FTS5 index for local cleartext search.",
        "",
        "## Scope",
        "",
        "- Parsed every TXT chat file found by the registry-compatible local resolver.",
        "- This is owner-local processing on the Pro only.",
        "- No cloud LLM or external API received corpus content.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Files parsed | {len(summaries)} |",
        f"| Zero-message files skipped | {skipped_zero_message_files} |",
        f"| Parsed messages | {len(messages)} |",
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

    lines.extend(["", "## Parsers", "", "| Parser | Files |", "|---|---:|"])
    for parser, count in parser_counts.most_common():
        lines.append(f"| {parser} | {count} |")

    lines.extend(["", "## Message Features", "", "| Feature | Messages |", "|---|---:|"])
    for feature, count in feature_counts.items():
        lines.append(f"| {feature} | {count} |")

    lines.extend(["", "## Messages By Year", "", "| Year | Messages |", "|---|---:|"])
    for year, count in sorted(year_counts.items()):
        lines.append(f"| {year} | {count} |")

    lines.extend(["", "## Top Months", "", "| Month | Messages |", "|---|---:|"])
    for month, count in month_counts.most_common(24):
        lines.append(f"| {month} | {count} |")

    lines.extend(["", "## Parse Warnings", "", "| Warning | Files |", "|---|---:|"])
    if warning_counts:
        for warning, count in warning_counts.most_common():
            lines.append(f"| {warning} | {count} |")
    else:
        lines.append("| none | 0 |")

    lines.extend(
        [
            "",
            "## Next Local Step",
            "",
            "Run the spicy/private quarantine pass, then mine only non-quarantined rows for CRM, KB, timeline, and ops use cases.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_full_corpus_to_outputs(
    *,
    corpus_root: Path,
    db_path: Path,
    summary_path: Path,
) -> tuple[list[ParsedMessage], list[FullParseSummary]]:
    """Parse the whole local corpus and write raw local DB plus safe summary."""
    root = corpus_root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Corpus root does not exist: {root}")
    rows = full_rows_from_refs(root, build_file_refs(root))
    all_messages, all_summaries = parse_full_corpus(rows)
    summaries = [summary for summary in all_summaries if summary.parsed_messages > 0]
    kept_file_ids = {summary.file_id for summary in summaries}
    messages = [message for message in all_messages if message.file_id in kept_file_ids]
    skipped_zero_message_files = len(all_summaries) - len(summaries)
    write_sqlite(db_path=db_path, corpus_root=root, messages=messages, summaries=summaries)
    write_summary(
        summary_path=summary_path,
        db_path=db_path,
        messages=messages,
        summaries=summaries,
        skipped_zero_message_files=skipped_zero_message_files,
    )
    return messages, summaries


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse the full local WhatsApp corpus into an ignored cleartext SQLite DB."
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)
    try:
        messages, summaries = parse_full_corpus_to_outputs(
            corpus_root=args.root,
            db_path=args.db,
            summary_path=args.summary,
        )
    except FileNotFoundError as exc:
        LOGGER.error("%s", exc)
        return 2
    if args.json:
        json.dump(
            {
                "files": len(summaries),
                "messages": len(messages),
                "db": str(args.db),
                "summary": str(args.summary),
            },
            sys.stdout,
            sort_keys=True,
        )
        sys.stdout.write("\n")
    else:
        LOGGER.info("Parsed %d messages from %d files.", len(messages), len(summaries))
        LOGGER.info("Wrote %s", args.db)
        LOGGER.info("Wrote %s", args.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
