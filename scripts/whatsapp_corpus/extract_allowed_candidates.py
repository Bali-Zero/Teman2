from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

LOGGER = logging.getLogger(__name__)

DEFAULT_MESSAGES_DB = Path("research/personal/wa-corpus/analysis/allowed_messages.local.sqlite")
DEFAULT_OUTPUT_DIR = Path("research/personal/wa-corpus/analysis")

PASSPORT_LIKE_RE = re.compile(r"\b[A-Z][0-9]{6,8}\b|\b[A-Z]{2}[0-9]{6,8}\b")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_LIKE_RE = re.compile(r"(?:\+?\d[\d\s().-]{6,}\d)")
MONEY_RE = re.compile(r"\b(?:rp|idr|usd|aud|eur)\s?[\d.,]+|[\d.,]+\s?\b(?:rp|idr|usd|aud|eur)\b", re.IGNORECASE)
DATE_LIKE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b")

CATEGORY_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "visa_case": (
        re.compile(r"\b(visa|kitas|kitap|b211|voa|e-?visa|imigrasi|immigration)\b", re.I),
    ),
    "identity_document": (
        re.compile(r"\b(passport|paspor|ktp|npwp|identity|id card|scan|photo|foto)\b", re.I),
    ),
    "company_case": (
        re.compile(r"\b(pt pma|company|shareholder|director|commissioner|akta|deed|nib|oss|kbli)\b", re.I),
    ),
    "tax_payment": (
        re.compile(r"\b(tax|pajak|invoice|faktur|billing|receipt|paid|payment|transfer)\b", re.I),
    ),
    "property_case": (
        re.compile(r"\b(property|villa|lease|rent|rental|land|tanah|notary|notaris|imb|pbg)\b", re.I),
    ),
    "urgency_case": (
        re.compile(r"\b(urgent|asap|blocked|problem|issue|mistake|mismatch|reject|rejected|expired|complain|cancel)\b", re.I),
    ),
}


@dataclass(frozen=True)
class RawMessage:
    file_id: str
    source_tag: str | None
    message_index: int
    timestamp: str | None
    sender_hash: str | None
    body_text: str
    has_url: bool
    has_email: bool
    has_phone_like: bool


@dataclass(frozen=True)
class Candidate:
    file_id: str
    source_tag: str | None
    message_index: int
    timestamp: str | None
    sender_hash: str | None
    category_code: str
    evidence_code: str
    body_hash: str
    value_hash: str | None


def stable_hash(value: str, length: int = 24) -> str:
    """Return a short stable hash for sensitive local values."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def read_messages(db_path: Path) -> list[RawMessage]:
    """Read raw allowed messages from local SQLite."""
    if not db_path.exists():
        raise FileNotFoundError(f"Messages DB does not exist: {db_path}")
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT file_id, source_tag, message_index, timestamp, sender_hash,
                   body_text, has_url, has_email, has_phone_like
            FROM parsed_messages
            ORDER BY file_id, message_index
            """
        ).fetchall()

    return [
        RawMessage(
            file_id=row[0],
            source_tag=row[1],
            message_index=int(row[2]),
            timestamp=row[3],
            sender_hash=row[4],
            body_text=row[5],
            has_url=bool(row[6]),
            has_email=bool(row[7]),
            has_phone_like=bool(row[8]),
        )
        for row in rows
    ]


def category_hits(body: str) -> tuple[str, ...]:
    """Detect high-level candidate categories."""
    hits: list[str] = []
    for category, patterns in CATEGORY_PATTERNS.items():
        if any(pattern.search(body) for pattern in patterns):
            hits.append(category)
    return tuple(hits)


def hashed_regex_values(pattern: re.Pattern[str], body: str) -> tuple[str, ...]:
    """Return unique hashes of regex matches without exposing raw values."""
    values = {match.group(0).strip().casefold() for match in pattern.finditer(body)}
    return tuple(sorted(stable_hash(value) for value in values if value))


def extract_message_candidates(message: RawMessage) -> list[Candidate]:
    """Extract local candidate rows without storing raw body text."""
    candidates: list[Candidate] = []
    body = message.body_text
    body_hash = stable_hash(body, length=32)

    def append(category: str, evidence: str, value_hash: str | None = None) -> None:
        candidates.append(
            Candidate(
                file_id=message.file_id,
                source_tag=message.source_tag,
                message_index=message.message_index,
                timestamp=message.timestamp,
                sender_hash=message.sender_hash,
                category_code=category,
                evidence_code=evidence,
                body_hash=body_hash,
                value_hash=value_hash,
            )
        )

    for category in category_hits(body):
        append(category, "category_keyword")
    for value_hash in hashed_regex_values(PASSPORT_LIKE_RE, body):
        append("identity_document", "passport_like_hash", value_hash)
    for value_hash in hashed_regex_values(EMAIL_RE, body):
        append("contact_reference", "email_hash", value_hash)
    for value_hash in hashed_regex_values(PHONE_LIKE_RE, body):
        append("contact_reference", "phone_like_hash", value_hash)
    for value_hash in hashed_regex_values(MONEY_RE, body):
        append("money_reference", "money_like_hash", value_hash)
    for value_hash in hashed_regex_values(DATE_LIKE_RE, body):
        append("date_reference", "date_like_hash", value_hash)
    if message.has_url:
        append("external_reference", "url_present")
    if message.has_email:
        append("contact_reference", "email_present")
    if message.has_phone_like:
        append("contact_reference", "phone_like_present")
    return candidates


def extract_candidates(messages: Iterable[RawMessage]) -> list[Candidate]:
    """Extract candidate rows from all messages."""
    candidates: list[Candidate] = []
    seen: set[tuple[str, int, str, str, str | None]] = set()
    for message in messages:
        for candidate in extract_message_candidates(message):
            key = (
                candidate.file_id,
                candidate.message_index,
                candidate.category_code,
                candidate.evidence_code,
                candidate.value_hash,
            )
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
    return candidates


def write_sqlite(path: Path, messages_db: Path, candidates: list[Candidate]) -> None:
    """Write candidate rows to ignored local SQLite."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE candidate_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at TEXT NOT NULL,
                messages_db TEXT NOT NULL,
                privacy_mode TEXT NOT NULL
            );

            CREATE TABLE extracted_candidates (
                file_id TEXT NOT NULL,
                source_tag TEXT,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                sender_hash TEXT,
                category_code TEXT NOT NULL,
                evidence_code TEXT NOT NULL,
                body_hash TEXT NOT NULL,
                value_hash TEXT,
                PRIMARY KEY (file_id, message_index, category_code, evidence_code, value_hash)
            );

            CREATE INDEX idx_candidates_category ON extracted_candidates(category_code);
            CREATE INDEX idx_candidates_evidence ON extracted_candidates(evidence_code);
            CREATE INDEX idx_candidates_timestamp ON extracted_candidates(timestamp);
            """
        )
        conn.execute(
            """
            INSERT INTO candidate_runs (id, generated_at, messages_db, privacy_mode)
            VALUES (1, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                messages_db.name,
                "local_only_hashed_candidates_no_raw_text_no_raw_paths",
            ),
        )
        conn.executemany(
            """
            INSERT INTO extracted_candidates (
                file_id, source_tag, message_index, timestamp, sender_hash,
                category_code, evidence_code, body_hash, value_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    candidate.file_id,
                    candidate.source_tag,
                    candidate.message_index,
                    candidate.timestamp,
                    candidate.sender_hash,
                    candidate.category_code,
                    candidate.evidence_code,
                    candidate.body_hash,
                    candidate.value_hash,
                )
                for candidate in candidates
            ],
        )
        conn.commit()


def month_key(timestamp: str | None) -> str | None:
    """Return YYYY-MM for an ISO timestamp."""
    if not timestamp or len(timestamp) < 7:
        return None
    return timestamp[:7]


def write_summary(
    *,
    summary_path: Path,
    messages_db: Path,
    candidate_db: Path,
    messages: list[RawMessage],
    candidates: list[Candidate],
) -> None:
    """Write aggregate-only candidate summary."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    category_counts = Counter(candidate.category_code for candidate in candidates)
    evidence_counts = Counter(candidate.evidence_code for candidate in candidates)
    month_counts = Counter(month for month in (month_key(c.timestamp) for c in candidates) if month)
    source_tag_counts = Counter(candidate.source_tag or "" for candidate in candidates)
    message_keys = {(candidate.file_id, candidate.message_index) for candidate in candidates}
    value_hash_count = len({candidate.value_hash for candidate in candidates if candidate.value_hash})

    lines: list[str] = [
        "# WhatsApp Allowlist Candidate Extraction Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Input raw SQLite artifact: `{messages_db.name}`",
        f"Local candidate SQLite artifact: `{candidate_db.name}`",
        "",
        "## Privacy Mode",
        "",
        "- This tracked summary contains no raw message text.",
        "- This tracked summary contains no message snippets.",
        "- This tracked summary contains no phone numbers.",
        "- This tracked summary contains no raw source paths.",
        "- This tracked summary contains no raw contact names.",
        "- Candidate SQLite stores hashed body/value references only, not raw extracted values.",
        "",
        "## Scope",
        "",
        "- Extracted only from messages parsed out of `content_allowlist.local.jsonl`.",
        "- Denylist and holdlist files were not opened.",
        "- Extraction is deterministic regex and hashing, not LLM interpretation.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Messages scanned | {len(messages)} |",
        f"| Messages with candidates | {len(message_keys)} |",
        f"| Candidate rows | {len(candidates)} |",
        f"| Distinct hashed extracted values | {value_hash_count} |",
        "",
        "## Candidate Categories",
        "",
        "| Category | Rows |",
        "|---|---:|",
    ]
    for category, count in category_counts.most_common():
        lines.append(f"| {category} | {count} |")

    lines.extend(
        [
            "",
            "## Evidence Codes",
            "",
            "| Evidence | Rows |",
            "|---|---:|",
        ]
    )
    for evidence, count in evidence_counts.most_common():
        lines.append(f"| {evidence} | {count} |")

    lines.extend(
        [
            "",
            "## Candidate Rows By Source Tag",
            "",
            "| Source tag | Rows |",
            "|---|---:|",
        ]
    )
    for source_tag, count in source_tag_counts.most_common():
        lines.append(f"| {source_tag} | {count} |")

    lines.extend(
        [
            "",
            "## Top Candidate Months",
            "",
            "| Month | Rows |",
            "|---|---:|",
        ]
    )
    for month, count in month_counts.most_common(20):
        lines.append(f"| {month} | {count} |")

    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            "Use the ignored candidate SQLite to build local review queues by `category_code` and `evidence_code`. Do not publish raw values; resolve hashes only inside local owner-review tools.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def extract_allowed_candidates(
    *,
    messages_db: Path,
    output_dir: Path,
) -> tuple[list[RawMessage], list[Candidate]]:
    """Extract structured candidates from local allowlist messages."""
    messages = read_messages(messages_db)
    candidates = extract_candidates(messages)
    candidate_db = output_dir / "allowed_candidates.local.sqlite"
    summary_path = output_dir / "allowed_candidates_summary.md"
    write_sqlite(candidate_db, messages_db, candidates)
    write_summary(
        summary_path=summary_path,
        messages_db=messages_db,
        candidate_db=candidate_db,
        messages=messages,
        candidates=candidates,
    )
    return messages, candidates


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Extract hashed structured candidates from local allowlist messages."
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
        help="Directory for candidate SQLite and aggregate summary.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)
    try:
        messages, candidates = extract_allowed_candidates(
            messages_db=args.messages_db,
            output_dir=args.output_dir,
        )
    except FileNotFoundError as exc:
        LOGGER.error("%s", exc)
        return 2

    LOGGER.info("Scanned %d messages and wrote %d candidates.", len(messages), len(candidates))
    LOGGER.info("Wrote %s", args.output_dir / "allowed_candidates.local.sqlite")
    LOGGER.info("Wrote %s", args.output_dir / "allowed_candidates_summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
