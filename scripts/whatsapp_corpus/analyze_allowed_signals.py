from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Iterable

LOGGER = logging.getLogger(__name__)

DEFAULT_MESSAGES_DB = Path("research/personal/wa-corpus/analysis/allowed_messages.local.sqlite")
DEFAULT_OUTPUT_DIR = Path("research/personal/wa-corpus/analysis")


@dataclass(frozen=True)
class MessageSignalInput:
    file_id: str
    source_tag: str | None
    message_index: int
    timestamp: str | None
    body_text: str
    has_url: bool
    has_email: bool
    has_phone_like: bool


@dataclass(frozen=True)
class SignalHit:
    file_id: str
    source_tag: str | None
    message_index: int
    timestamp: str | None
    signal_code: str


SIGNAL_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "identity_document": (
        re.compile(r"\b(passport|paspor|ktp|npwp|id card|identity|scan|photo|foto)\b", re.I),
    ),
    "immigration": (
        re.compile(r"\b(visa|kitas|kitap|b211|voa|e-?visa|imigration|immigration|imigrasi)\b", re.I),
    ),
    "company_corporate": (
        re.compile(r"\b(pt pma|company|shareholder|director|commissioner|akta|deed|nib|oss|kbli)\b", re.I),
    ),
    "tax_accounting": (
        re.compile(r"\b(tax|pajak|invoice|faktur|billing|receipt|paid|payment|transfer)\b", re.I),
    ),
    "property_real_estate": (
        re.compile(r"\b(property|villa|lease|rent|rental|land|tanah|notary|notaris|imb|pbg)\b", re.I),
    ),
    "scheduling_followup": (
        re.compile(r"\b(today|tomorrow|besok|meeting|call|update|follow[ -]?up|deadline|schedule)\b", re.I),
    ),
    "urgency_risk": (
        re.compile(r"\b(urgent|asap|blocked|problem|issue|mistake|mismatch|reject|rejected|expired|complain|cancel)\b", re.I),
    ),
    "bahasa_operational": (
        re.compile(r"\b(bisa|sudah|belum|nanti|tolong|terima kasih|makasih|pak|ibu|mas|mba)\b", re.I),
    ),
    "money_like": (
        re.compile(r"\b(rp|idr|usd|aud|eur)\s?[\d.,]+", re.I),
        re.compile(r"[\d.,]+\s?\b(rp|idr|usd|aud|eur)\b", re.I),
    ),
}


def read_messages(db_path: Path) -> list[MessageSignalInput]:
    """Read raw parsed messages from the ignored local SQLite database."""
    if not db_path.exists():
        raise FileNotFoundError(f"Messages DB does not exist: {db_path}")

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT file_id, source_tag, message_index, timestamp, body_text,
                   has_url, has_email, has_phone_like
            FROM parsed_messages
            ORDER BY file_id, message_index
            """
        ).fetchall()

    return [
        MessageSignalInput(
            file_id=row[0],
            source_tag=row[1],
            message_index=int(row[2]),
            timestamp=row[3],
            body_text=row[4],
            has_url=bool(row[5]),
            has_email=bool(row[6]),
            has_phone_like=bool(row[7]),
        )
        for row in rows
    ]


def detect_signals(message: MessageSignalInput) -> tuple[str, ...]:
    """Detect aggregate signal codes for one message."""
    body = message.body_text
    codes: list[str] = []
    for code, patterns in SIGNAL_PATTERNS.items():
        if any(pattern.search(body) for pattern in patterns):
            codes.append(code)
    if message.has_url:
        codes.append("contains_url")
    if message.has_email:
        codes.append("contains_email")
    if message.has_phone_like:
        codes.append("contains_phone_like")
    return tuple(dict.fromkeys(codes))


def build_signal_hits(messages: Iterable[MessageSignalInput]) -> list[SignalHit]:
    """Build signal hit rows."""
    hits: list[SignalHit] = []
    for message in messages:
        for code in detect_signals(message):
            hits.append(
                SignalHit(
                    file_id=message.file_id,
                    source_tag=message.source_tag,
                    message_index=message.message_index,
                    timestamp=message.timestamp,
                    signal_code=code,
                )
            )
    return hits


def write_signal_sqlite(path: Path, messages_db: Path, hits: list[SignalHit]) -> None:
    """Write local signal hits without raw message text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE signal_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at TEXT NOT NULL,
                messages_db TEXT NOT NULL,
                privacy_mode TEXT NOT NULL
            );

            CREATE TABLE signal_hits (
                file_id TEXT NOT NULL,
                source_tag TEXT,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                signal_code TEXT NOT NULL,
                PRIMARY KEY (file_id, message_index, signal_code)
            );

            CREATE INDEX idx_signal_hits_code ON signal_hits(signal_code);
            CREATE INDEX idx_signal_hits_timestamp ON signal_hits(timestamp);
            """
        )
        conn.execute(
            """
            INSERT INTO signal_runs (id, generated_at, messages_db, privacy_mode)
            VALUES (1, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                messages_db.name,
                "local_only_signal_codes_no_raw_text_no_raw_paths",
            ),
        )
        conn.executemany(
            """
            INSERT INTO signal_hits (file_id, source_tag, message_index, timestamp, signal_code)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    hit.file_id,
                    hit.source_tag,
                    hit.message_index,
                    hit.timestamp,
                    hit.signal_code,
                )
                for hit in hits
            ],
        )
        conn.commit()


def month_key(timestamp: str | None) -> str | None:
    """Return YYYY-MM for an ISO timestamp."""
    if not timestamp or len(timestamp) < 7:
        return None
    return timestamp[:7]


def hit_message_key(hit: SignalHit) -> tuple[str, int]:
    """Return message primary key for a hit."""
    return (hit.file_id, hit.message_index)


def build_cooccurrence(hits: list[SignalHit]) -> Counter[tuple[str, str]]:
    """Count signal co-occurrences within the same message."""
    by_message: dict[tuple[str, int], set[str]] = {}
    for hit in hits:
        by_message.setdefault(hit_message_key(hit), set()).add(hit.signal_code)

    counts: Counter[tuple[str, str]] = Counter()
    for codes in by_message.values():
        for left, right in combinations(sorted(codes), 2):
            counts.update([(left, right)])
    return counts


def write_summary(
    *,
    summary_path: Path,
    messages_db: Path,
    signal_db: Path,
    messages: list[MessageSignalInput],
    hits: list[SignalHit],
) -> None:
    """Write aggregate-only signal summary."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    messages_with_signal = {hit_message_key(hit) for hit in hits}
    signal_counts = Counter(hit.signal_code for hit in hits)
    month_counts = Counter(month for month in (month_key(hit.timestamp) for hit in hits) if month)
    source_tag_counts = Counter(hit.source_tag or "" for hit in hits)
    cooccurrence = build_cooccurrence(hits)

    lines: list[str] = [
        "# WhatsApp Allowlist Signal Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Input raw SQLite artifact: `{messages_db.name}`",
        f"Local signal SQLite artifact: `{signal_db.name}`",
        "",
        "## Privacy Mode",
        "",
        "- This tracked summary contains no raw message text.",
        "- This tracked summary contains no message snippets.",
        "- This tracked summary contains no phone numbers.",
        "- This tracked summary contains no raw source paths.",
        "- This tracked summary contains no raw contact names.",
        "- Signal SQLite contains only file IDs, message indexes, timestamps, hashed source tags, and signal codes.",
        "",
        "## Scope",
        "",
        "- Analyzed only messages parsed from `content_allowlist.local.jsonl`.",
        "- Denylist and holdlist files were not opened.",
        "- Signal detection is deterministic regex matching, not LLM interpretation.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Messages analyzed | {len(messages)} |",
        f"| Messages with at least one signal | {len(messages_with_signal)} |",
        f"| Signal hits | {len(hits)} |",
        f"| Distinct signal codes | {len(signal_counts)} |",
        "",
        "## Signal Codes",
        "",
        "| Signal | Hits |",
        "|---|---:|",
    ]
    for signal, count in signal_counts.most_common():
        lines.append(f"| {signal} | {count} |")

    lines.extend(
        [
            "",
            "## Signal Hits By Source Tag",
            "",
            "| Source tag | Hits |",
            "|---|---:|",
        ]
    )
    for source_tag, count in source_tag_counts.most_common():
        lines.append(f"| {source_tag} | {count} |")

    lines.extend(
        [
            "",
            "## Top Signal Months",
            "",
            "| Month | Hits |",
            "|---|---:|",
        ]
    )
    for month, count in month_counts.most_common(20):
        lines.append(f"| {month} | {count} |")

    lines.extend(
        [
            "",
            "## Top Co-Occurrences",
            "",
            "| Signal A | Signal B | Messages |",
            "|---|---|---:|",
        ]
    )
    for (left, right), count in cooccurrence.most_common(20):
        lines.append(f"| {left} | {right} | {count} |")

    lines.extend(
        [
            "",
            "## Operational Reading",
            "",
            "- High `contains_phone_like` usually means many operational exchanges include IDs, amounts, dates, or phone-like digit runs.",
            "- `tax_accounting`, `identity_document`, `immigration`, and `company_corporate` are the first safe candidates for local-only structured extraction.",
            "- Treat these as routing signals only; do not make client or legal claims from regex counts alone.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze_allowed_signals(
    *,
    messages_db: Path,
    output_dir: Path,
) -> tuple[list[MessageSignalInput], list[SignalHit]]:
    """Analyze parsed allowlist messages into aggregate signals."""
    messages = read_messages(messages_db)
    hits = build_signal_hits(messages)
    signal_db = output_dir / "allowed_signal_hits.local.sqlite"
    summary_path = output_dir / "allowed_signal_summary.md"
    write_signal_sqlite(signal_db, messages_db, hits)
    write_summary(
        summary_path=summary_path,
        messages_db=messages_db,
        signal_db=signal_db,
        messages=messages,
        hits=hits,
    )
    return messages, hits


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Analyze aggregate signals from the local allowlist parsed-message SQLite."
    )
    parser.add_argument(
        "--messages-db",
        type=Path,
        default=DEFAULT_MESSAGES_DB,
        help="allowed_messages.local.sqlite produced by parse_allowed_messages.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for signal SQLite and aggregate summary.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)
    try:
        messages, hits = analyze_allowed_signals(
            messages_db=args.messages_db,
            output_dir=args.output_dir,
        )
    except FileNotFoundError as exc:
        LOGGER.error("%s", exc)
        return 2

    LOGGER.info("Analyzed %d messages and wrote %d signal hits.", len(messages), len(hits))
    LOGGER.info("Wrote %s", args.output_dir / "allowed_signal_hits.local.sqlite")
    LOGGER.info("Wrote %s", args.output_dir / "allowed_signal_summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
