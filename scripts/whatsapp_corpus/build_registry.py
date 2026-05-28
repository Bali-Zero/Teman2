from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

LOGGER = logging.getLogger(__name__)

MIRROR_START_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}) "
    r"\[(?P<direction>SENT|RECEIVED)\]"
)
MIRROR_HEADER_COUNT_RE = re.compile(r"\|\s*(?P<count>\d+)\s+msgs?\s*===")
MIRROR_FILENAME_COUNT_RE = re.compile(r"^(?P<count>\d{5})_")
EXPORT_BASELINE_START_RE = re.compile(
    r"^\[?"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),?\s+"
    r"(?P<time>\d{1,2}[.:]\d{2}(?:[.:]\d{2})?)"
    r"\]?(?:\s+-)?\s*(?P<rest>.*)$"
)
EXPORT_NORMALIZED_START_RE = re.compile(
    r"^[\u200e\ufeff]*\[?"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),?\s+"
    r"(?P<time>\d{1,2}[.:]\d{2}(?:[.:]\d{2})?)"
    r"\]?(?:\s+-)?\s*(?P<rest>.*)$"
)

DEFAULT_CORPUS_ROOT = Path.home() / "Desktop" / "wa-chats-MASTER-2026-05-26"
DEFAULT_OUTPUT_DIR = Path("research/personal/wa-corpus/registry")
DEFAULT_TARGET_TOTAL = 105_530


@dataclass(frozen=True)
class FileRegistry:
    file_id: str
    source: str
    source_tag: str | None
    parser: str
    path_hash: str
    sha256: str
    size_bytes: int
    line_count: int
    message_start_count: int
    normalized_message_start_count: int
    min_timestamp: str | None
    max_timestamp: str | None
    filename_claimed_count: int | None
    header_claimed_count: int | None
    system_event_count: int
    warning_codes: tuple[str, ...]
    warning_details: tuple[str, ...]


@dataclass(frozen=True)
class SourceSummary:
    source: str
    files: int
    message_starts: int
    lines: int
    size_bytes: int
    normalized_message_starts: int
    filename_claimed_sum: int
    header_claimed_sum: int
    warning_count: int


def short_hash(value: str, length: int = 16) -> str:
    """Return a short, stable SHA-256 hash."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def file_sha256(path: Path) -> str:
    """Hash file bytes without exposing contents."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_hash(root: Path, path: Path) -> str:
    """Hash a source-relative path so reports do not expose names or phones."""
    return short_hash(path.relative_to(root).as_posix(), length=24)


def source_tag(root: Path, path: Path) -> str | None:
    """Return hashed ZIP source tag when available, without exposing names."""
    rel = path.relative_to(root)
    if len(rel.parts) >= 2 and rel.parts[0] == "02_zip-extracted":
        return f"tag-{short_hash(rel.parts[1], length=10)}"
    return None


def parser_for(root: Path, path: Path) -> str:
    """Choose parser based on the top-level source folder."""
    top = path.relative_to(root).parts[0]
    if top == "01_wa-mirror-db":
        return "wa_mirror_db"
    return "whatsapp_export"


def iter_chat_files(root: Path) -> list[Path]:
    """Return all TXT chat files under the corpus root."""
    return sorted(p for p in root.rglob("*.txt") if p.is_file())


def parse_timestamp(parser: str, match: re.Match[str]) -> str | None:
    """Parse a message-start timestamp into an ISO string."""
    try:
        if parser == "wa_mirror_db":
            value = f"{match.group('date')} {match.group('time')}"
            return datetime.strptime(value, "%Y-%m-%d %H:%M").isoformat(timespec="minutes")

        time_value = match.group("time").replace(".", ":")
        if len(time_value.split(":")) == 2:
            time_value = f"{time_value}:00"
        date_value = match.group("date")
        year_token = date_value.rsplit("/", 1)[-1]
        fmt = "%d/%m/%y %H:%M:%S" if len(year_token) == 2 else "%d/%m/%Y %H:%M:%S"
        return datetime.strptime(f"{date_value} {time_value}", fmt).isoformat(timespec="seconds")
    except ValueError:
        return None


def claimed_count_from_filename(path: Path) -> int | None:
    """Parse leading mirror filename message count, when present."""
    match = MIRROR_FILENAME_COUNT_RE.match(path.name)
    if not match:
        return None
    return int(match.group("count"))


def claimed_count_from_header(lines: list[str]) -> int | None:
    """Parse mirror header message count, when present."""
    if not lines:
        return None
    match = MIRROR_HEADER_COUNT_RE.search(lines[0])
    if not match:
        return None
    return int(match.group("count"))


def parse_file(root: Path, path: Path, file_id: str) -> FileRegistry:
    """Parse one chat file into metadata-only registry fields."""
    parser = parser_for(root, path)
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    timestamps: list[str] = []
    normalized_timestamps = 0
    normalized_extra_count = 0
    invalid_timestamp_count = 0
    system_event_count = 0

    for line in lines:
        if parser == "wa_mirror_db":
            match = MIRROR_START_RE.match(line)
            normalized_match = match
        else:
            match = EXPORT_BASELINE_START_RE.match(line)
            normalized_match = EXPORT_NORMALIZED_START_RE.match(line)
            if normalized_match:
                normalized_timestamps += 1
                if not match:
                    normalized_extra_count += 1
            if match and ":" not in match.group("rest"):
                system_event_count += 1
        if not match:
            continue
        parsed = parse_timestamp(parser, match)
        if parsed is None:
            invalid_timestamp_count += 1
            continue
        timestamps.append(parsed)

    message_count = len(timestamps) + invalid_timestamp_count
    normalized_message_count = message_count if parser == "wa_mirror_db" else normalized_timestamps
    filename_claimed = claimed_count_from_filename(path) if parser == "wa_mirror_db" else None
    header_claimed = claimed_count_from_header(lines) if parser == "wa_mirror_db" else None

    warning_codes: list[str] = []
    warning_details: list[str] = []
    if message_count == 0:
        warning_codes.append("zero_message_starts")
        warning_details.append("no timestamp-start records detected")
    if invalid_timestamp_count:
        warning_codes.append("invalid_timestamp")
        warning_details.append(f"{invalid_timestamp_count} timestamp-start records could not be parsed")
    if normalized_extra_count:
        warning_codes.append("unicode_prefixed_export_starts")
        warning_details.append(
            f"{normalized_extra_count} normalized export starts were not counted by baseline parser"
        )
    if filename_claimed is not None and filename_claimed != message_count:
        warning_codes.append("filename_count_mismatch")
        warning_details.append(
            f"filename_claimed={filename_claimed}; parser_message_starts={message_count}"
        )
    if header_claimed is not None and header_claimed != message_count:
        warning_codes.append("header_count_mismatch")
        warning_details.append(
            f"header_claimed={header_claimed}; parser_message_starts={message_count}"
        )

    stat = path.stat()
    return FileRegistry(
        file_id=file_id,
        source=path.relative_to(root).parts[0],
        source_tag=source_tag(root, path),
        parser=parser,
        path_hash=path_hash(root, path),
        sha256=file_sha256(path),
        size_bytes=stat.st_size,
        line_count=len(lines),
        message_start_count=message_count,
        normalized_message_start_count=normalized_message_count,
        min_timestamp=min(timestamps) if timestamps else None,
        max_timestamp=max(timestamps) if timestamps else None,
        filename_claimed_count=filename_claimed,
        header_claimed_count=header_claimed,
        system_event_count=system_event_count,
        warning_codes=tuple(dict.fromkeys(warning_codes)),
        warning_details=tuple(warning_details),
    )


def build_registry(root: Path) -> list[FileRegistry]:
    """Build metadata-only registry entries for every chat file."""
    files = iter_chat_files(root)
    entries: list[FileRegistry] = []
    width = max(4, len(str(len(files))))
    for index, path in enumerate(files, start=1):
        entries.append(parse_file(root, path, f"wa-file-{index:0{width}d}"))
    return entries


def summarize_sources(root: Path, entries: Iterable[FileRegistry]) -> list[SourceSummary]:
    """Aggregate registry entries by top-level source folder."""
    by_source: dict[str, list[FileRegistry]] = defaultdict(list)
    for entry in entries:
        by_source[entry.source].append(entry)

    for child in root.iterdir():
        if child.is_dir():
            by_source.setdefault(child.name, [])

    summaries: list[SourceSummary] = []
    for source in sorted(by_source):
        rows = by_source[source]
        summaries.append(
            SourceSummary(
                source=source,
                files=len(rows),
                message_starts=sum(r.message_start_count for r in rows),
                lines=sum(r.line_count for r in rows),
                size_bytes=sum(r.size_bytes for r in rows),
                normalized_message_starts=sum(r.normalized_message_start_count for r in rows),
                filename_claimed_sum=sum(r.filename_claimed_count or 0 for r in rows),
                header_claimed_sum=sum(r.header_claimed_count or 0 for r in rows),
                warning_count=sum(len(r.warning_codes) for r in rows),
            )
        )
    return summaries


def write_sqlite(
    *,
    db_path: Path,
    root: Path,
    entries: list[FileRegistry],
    summaries: list[SourceSummary],
    target_total: int,
) -> None:
    """Write registry metadata to SQLite."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    actual_total = sum(entry.message_start_count for entry in entries)

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE registry_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at TEXT NOT NULL,
                corpus_root_hash TEXT NOT NULL,
                target_total INTEGER NOT NULL,
                actual_total INTEGER NOT NULL,
                delta INTEGER NOT NULL,
                privacy_mode TEXT NOT NULL
            );

            CREATE TABLE corpus_files (
                file_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_tag TEXT,
                parser TEXT NOT NULL,
                path_hash TEXT NOT NULL UNIQUE,
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                line_count INTEGER NOT NULL,
                message_start_count INTEGER NOT NULL,
                normalized_message_start_count INTEGER NOT NULL,
                min_timestamp TEXT,
                max_timestamp TEXT,
                filename_claimed_count INTEGER,
                header_claimed_count INTEGER,
                system_event_count INTEGER NOT NULL,
                warning_codes_json TEXT NOT NULL,
                warning_details_json TEXT NOT NULL
            );

            CREATE TABLE source_summaries (
                source TEXT PRIMARY KEY,
                files INTEGER NOT NULL,
                message_starts INTEGER NOT NULL,
                lines INTEGER NOT NULL,
                size_bytes INTEGER NOT NULL,
                normalized_message_starts INTEGER NOT NULL,
                filename_claimed_sum INTEGER NOT NULL,
                header_claimed_sum INTEGER NOT NULL,
                warning_count INTEGER NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO registry_runs
                (id, generated_at, corpus_root_hash, target_total, actual_total, delta, privacy_mode)
            VALUES (1, ?, ?, ?, ?, ?, ?)
            """,
            (
                generated_at,
                short_hash(str(root.expanduser().resolve()), length=24),
                target_total,
                actual_total,
                actual_total - target_total,
                "metadata_only_no_raw_text_no_raw_paths",
            ),
        )
        conn.executemany(
            """
            INSERT INTO corpus_files (
                file_id, source, source_tag, parser, path_hash, sha256, size_bytes, line_count,
                message_start_count, normalized_message_start_count, min_timestamp, max_timestamp, filename_claimed_count,
                header_claimed_count, system_event_count, warning_codes_json, warning_details_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    entry.file_id,
                    entry.source,
                    entry.source_tag,
                    entry.parser,
                    entry.path_hash,
                    entry.sha256,
                    entry.size_bytes,
                    entry.line_count,
                    entry.message_start_count,
                    entry.normalized_message_start_count,
                    entry.min_timestamp,
                    entry.max_timestamp,
                    entry.filename_claimed_count,
                    entry.header_claimed_count,
                    entry.system_event_count,
                    json.dumps(entry.warning_codes),
                    json.dumps(entry.warning_details),
                )
                for entry in entries
            ],
        )
        conn.executemany(
            """
            INSERT INTO source_summaries (
                source, files, message_starts, lines, size_bytes, normalized_message_starts,
                filename_claimed_sum, header_claimed_sum, warning_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    summary.source,
                    summary.files,
                    summary.message_starts,
                    summary.lines,
                    summary.size_bytes,
                    summary.normalized_message_starts,
                    summary.filename_claimed_sum,
                    summary.header_claimed_sum,
                    summary.warning_count,
                )
                for summary in summaries
            ],
        )
        conn.commit()
    finally:
        conn.close()


def warning_counts(entries: Iterable[FileRegistry]) -> Counter[str]:
    """Count warning codes across files."""
    counts: Counter[str] = Counter()
    for entry in entries:
        counts.update(entry.warning_codes)
    return counts


def top_mismatches(entries: Iterable[FileRegistry], limit: int) -> list[FileRegistry]:
    """Return files with claimed-count mismatches, largest absolute delta first."""
    mismatched = [
        entry
        for entry in entries
        if "filename_count_mismatch" in entry.warning_codes
        or "header_count_mismatch" in entry.warning_codes
    ]
    return sorted(
        mismatched,
        key=lambda entry: max(
            abs((entry.filename_claimed_count or entry.message_start_count) - entry.message_start_count),
            abs((entry.header_claimed_count or entry.message_start_count) - entry.message_start_count),
        ),
        reverse=True,
    )[:limit]


def write_summary(
    *,
    summary_path: Path,
    root: Path,
    db_path: Path,
    entries: list[FileRegistry],
    summaries: list[SourceSummary],
    target_total: int,
    mismatch_limit: int,
) -> None:
    """Write a privacy-preserving Markdown summary."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    actual_total = sum(entry.message_start_count for entry in entries)
    normalized_total = sum(entry.normalized_message_start_count for entry in entries)
    lines: list[str] = [
        "# WhatsApp Corpus Registry Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Corpus root hash: `{short_hash(str(root.expanduser().resolve()), length=24)}`",
        f"SQLite registry: `{db_path.as_posix()}`",
        "",
        "## Privacy Mode",
        "",
        "- Metadata only.",
        "- No raw message text.",
        "- No message snippets.",
        "- No raw source paths in this report.",
        "- Per-file references use `file_id` plus `path_hash`.",
        "",
        "## Global Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| TXT chat files parsed | {len(entries)} |",
        f"| Parser message-start records | {actual_total} |",
        f"| Normalized message-start records | {normalized_total} |",
        f"| Target message count | {target_total} |",
        f"| Delta parser-target | {actual_total - target_total:+d} |",
        "",
        "## Source Breakdown",
        "",
        "| Source | Files | Baseline starts | Normalized starts | Lines | Size bytes | Filename claim sum | Header claim sum | Warnings |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            "| {source} | {files} | {messages} | {normalized} | {line_count} | {size} | {filename_sum} | {header_sum} | {warnings} |".format(
                source=summary.source,
                files=summary.files,
                messages=summary.message_starts,
                normalized=summary.normalized_message_starts,
                line_count=summary.lines,
                size=summary.size_bytes,
                filename_sum=summary.filename_claimed_sum,
                header_sum=summary.header_claimed_sum,
                warnings=summary.warning_count,
            )
        )

    counts = warning_counts(entries)
    lines.extend(
        [
            "",
            "## Warning Codes",
            "",
            "| Warning | Files |",
            "|---|---:|",
        ]
    )
    if counts:
        for code, count in counts.most_common():
            lines.append(f"| {code} | {count} |")
    else:
        lines.append("| none | 0 |")

    lines.extend(
        [
            "",
            "## Count Mismatch Candidates",
            "",
            "These rows expose only `file_id` and `path_hash`, not contact names, phone numbers, or raw paths.",
            "",
            "| File ID | Source | Source tag | Path hash | Baseline starts | Normalized starts | Filename claim | Header claim | Warnings |",
            "|---|---|---|---|---:|---:|---:|---:|---|",
        ]
    )
    mismatches = top_mismatches(entries, mismatch_limit)
    if mismatches:
        for entry in mismatches:
            lines.append(
                "| {file_id} | {source} | {source_tag} | `{path_hash}` | {starts} | {normalized} | {filename} | {header} | {warnings} |".format(
                    file_id=entry.file_id,
                    source=entry.source,
                    source_tag=entry.source_tag or "",
                    path_hash=entry.path_hash,
                    starts=entry.message_start_count,
                    normalized=entry.normalized_message_start_count,
                    filename=entry.filename_claimed_count if entry.filename_claimed_count is not None else "",
                    header=entry.header_claimed_count if entry.header_claimed_count is not None else "",
                    warnings=", ".join(entry.warning_codes),
                )
            )
    else:
        lines.append("| none |  |  |  |  |  |  |  |  |")

    lines.extend(
        [
            "",
            "## Discrepancy Interpretation",
            "",
            f"- The parser count is `{actual_total}`, target count is `{target_total}`, delta is `{actual_total - target_total:+d}`.",
            f"- The normalized count is `{normalized_total}` after accepting invisible Unicode-prefixed WhatsApp timestamp lines.",
            "- This registry counts timestamp-start records, not necessarily the same semantic unit as source indexes, filename prefixes, database totals, or WhatsApp UI counts.",
            "- Baseline count intentionally preserves the original anti-hallucination counting rule used for the 105k brief; normalized count is a separate diagnostic signal.",
            "- The mirror source has separate parser starts, filename claim sums, and header claim sums because those are independent count signals.",
            "- Next reconciliation step: inspect warning classes locally through SQLite using `file_id` and `path_hash`; do not copy raw paths or message text into shareable reports.",
            "",
            "## SQLite Inspection Examples",
            "",
            "```sql",
            "SELECT source, files, message_starts, normalized_message_starts, filename_claimed_sum, header_claimed_sum",
            "FROM source_summaries",
            "ORDER BY source;",
            "",
            "SELECT file_id, source, source_tag, path_hash, message_start_count,",
            "       normalized_message_start_count, filename_claimed_count, header_claimed_count,",
            "       warning_codes_json",
            "FROM corpus_files",
            "WHERE warning_codes_json != '[]'",
            "ORDER BY message_start_count DESC",
            "LIMIT 50;",
            "```",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Build a local-only metadata registry for the WhatsApp corpus."
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_CORPUS_ROOT, help="Corpus root path.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for registry.sqlite and registry_summary.md.",
    )
    parser.add_argument(
        "--target-total",
        type=int,
        default=DEFAULT_TARGET_TOTAL,
        help="Expected message count to compare against parser message-start records.",
    )
    parser.add_argument(
        "--mismatch-limit",
        type=int,
        default=40,
        help="Maximum mismatch rows to include in the Markdown report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)
    root = args.root.expanduser().resolve()
    output_dir = args.output_dir
    if not root.exists():
        LOGGER.error("Corpus root does not exist: %s", root)
        return 2
    if not root.is_dir():
        LOGGER.error("Corpus root is not a directory: %s", root)
        return 2

    entries = build_registry(root)
    summaries = summarize_sources(root, entries)
    db_path = output_dir / "registry.sqlite"
    summary_path = output_dir / "registry_summary.md"
    write_sqlite(
        db_path=db_path,
        root=root,
        entries=entries,
        summaries=summaries,
        target_total=args.target_total,
    )
    write_summary(
        summary_path=summary_path,
        root=root,
        db_path=db_path,
        entries=entries,
        summaries=summaries,
        target_total=args.target_total,
        mismatch_limit=args.mismatch_limit,
    )

    actual_total = sum(entry.message_start_count for entry in entries)
    LOGGER.info("Parsed %d files and %d message-start records.", len(entries), actual_total)
    LOGGER.info("Wrote %s", db_path)
    LOGGER.info("Wrote %s", summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
