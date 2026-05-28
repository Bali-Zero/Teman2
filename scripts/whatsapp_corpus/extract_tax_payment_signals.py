#!/usr/bin/env python3
"""Extract aggregate tax/payment signals from local WhatsApp allowlist messages.

This extractor intentionally reads raw message text only from the ignored local
``allowed_messages.local.sqlite`` artifact. It writes no raw text, contact
labels, source paths, money values, or reference values to tracked outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANALYSIS_DIR = REPO_ROOT / "research/personal/wa-corpus/analysis"
DEFAULT_MESSAGES_DB = DEFAULT_ANALYSIS_DIR / "allowed_messages.local.sqlite"
DEFAULT_CANDIDATES_DB = DEFAULT_ANALYSIS_DIR / "allowed_candidates.local.sqlite"
DEFAULT_SIGNALS_DB = DEFAULT_ANALYSIS_DIR / "allowed_signal_hits.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_ANALYSIS_DIR / "allowed_tax_payment.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_ANALYSIS_DIR / "allowed_tax_payment_summary.md"

ALLOWED_MESSAGES_DB_NAME = "allowed_messages.local.sqlite"
ALLOWED_CANDIDATES_DB_NAME = "allowed_candidates.local.sqlite"
ALLOWED_SIGNALS_DB_NAME = "allowed_signal_hits.local.sqlite"

MONTH_RE = re.compile(r"^(\d{4})-(\d{2})")
TAX_ACCOUNTING_RE = re.compile(
    r"\b("
    r"tax(?:es)?|pajak|npwp|pph\s?(?:21|23|25|26|4)|ppn|vat|"
    r"spt|djp|efin|e-?faktur|faktur\s+pajak|e-?billing|kode\s+billing|"
    r"accounting|bookkeeping|akuntansi|laporan\s+pajak|tax\s+return|tax\s+report"
    r")\b",
    re.IGNORECASE,
)
INVOICE_PAYMENT_RE = re.compile(
    r"\b("
    r"invoice|inv\.?|faktur|bill(?:ing)?|kwitansi|receipt|payment|paid|pay|"
    r"transfer|pembayaran|bayar|dibayar|pelunasan|settlement"
    r")\b",
    re.IGNORECASE,
)
PAYMENT_PROOF_RE = re.compile(
    r"\b("
    r"proof\s+of\s+payment|payment\s+proof|bukti\s+(?:bayar|pembayaran|transfer)|"
    r"receipt|kwitansi|slip\s+transfer|transfer\s+slip|screenshot\s+(?:payment|transfer)"
    r")\b",
    re.IGNORECASE,
)
MONEY_RE = re.compile(
    r"\b(?:rp|idr|usd|aud|eur|sgd)\s*[\d][\d.,]*(?:\s*(?:jt|juta|k|rb|ribu|million|mio))?\b|"
    r"\b[\d][\d.,]*\s*(?:rp|idr|usd|aud|eur|sgd)\b|"
    r"\b[\d][\d.,]*\s*(?:jt|juta|rb|ribu)\b",
    re.IGNORECASE,
)
DEADLINE_RE = re.compile(
    r"\b("
    r"deadline|due\s+date|payment\s+due|jatuh\s+tempo|batas\s+waktu|"
    r"before\s+\d{1,2}|by\s+\d{1,2}|last\s+day|due\s+before"
    r")\b",
    re.IGNORECASE,
)
PENALTY_RE = re.compile(
    r"\b("
    r"penalt(?:y|ies)|denda|late\s+fee|terlambat|telat|sanksi|"
    r"bunga|overdue|fine|keterlambatan"
    r")\b",
    re.IGNORECASE,
)
COMPANY_DOC_RE = re.compile(
    r"\b("
    r"nib|oss|akta|deed|company\s+doc(?:ument)?s?|pt\s+pma|company|"
    r"sk\s+kemenkumham|skt|tdp|kbli|shareholder|director|commissioner"
    r")\b",
    re.IGNORECASE,
)
REPORTING_RE = re.compile(
    r"\b("
    r"spt\s+(?:masa|tahunan)|masa\s+pajak|laporan\s+(?:bulanan|tahunan)|"
    r"monthly\s+(?:(?:tax|vat|pajak)\s+)?(?:report|reporting|return)|"
    r"annual\s+(?:(?:tax|vat|pajak)\s+)?(?:report|reporting|return)|"
    r"yearly\s+(?:(?:tax|vat|pajak)\s+)?(?:report|reporting|return)|"
    r"tax\s+(?:return|reporting|report)"
    r")\b",
    re.IGNORECASE,
)
PAYROLL_BPJS_RE = re.compile(
    r"\b("
    r"payroll|salary|salaries|gaji|payslip|bpjs|ketenagakerjaan|kesehatan|"
    r"pph\s?21|employee|karyawan"
    r")\b",
    re.IGNORECASE,
)
DATE_LIKE_RE = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|"
    r"\b\d{4}-\d{2}-\d{2}\b|"
    r"\b\d{1,2}\s+"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|"
    r"januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember)"
    r"\s+\d{2,4}\b",
    re.IGNORECASE,
)
REFERENCE_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (
        re.compile(
            r"\b(?:invoice|inv\.?|faktur|receipt|kwitansi|billing|kode\s+billing|"
            r"ref(?:erence)?|nomor|no\.?)\s*(?:number|#|:|-)?\s*"
            r"([A-Z0-9][A-Z0-9./_-]{3,})",
            re.IGNORECASE,
        ),
        1,
    ),
    (
        re.compile(
            r"\b(?:va|virtual\s+account)\s*(?:number|#|:|-)?\s*([0-9][0-9 .-]{5,})",
            re.IGNORECASE,
        ),
        1,
    ),
)

TAX_RELATED_SIGNALS = frozenset(
    {
        "tax_accounting",
        "invoice_payment_proof",
        "currency_amount",
        "deadline_penalty",
        "monthly_annual_reporting",
        "payroll_bpjs",
        "nib_company_tax_docs",
    }
)
SUPPORT_SIGNAL_CODES = (
    "tax_accounting",
    "money_like",
    "company_corporate",
    "scheduling_followup",
)
SUPPORT_CANDIDATE_CATEGORIES = (
    "tax_payment",
    "money_reference",
    "date_reference",
    "company_case",
)
SUPPORT_CANDIDATE_EVIDENCES = (
    "money_like_hash",
    "date_like_hash",
    "category_keyword",
)


@dataclass(frozen=True)
class RawMessage:
    file_id: str
    source_tag: str | None
    message_index: int
    timestamp: str | None
    sender_hash: str | None
    body_text: str


@dataclass(frozen=True)
class TaxPaymentHit:
    file_id: str
    source_tag: str | None
    message_index: int
    timestamp: str | None
    sender_hash: str | None
    category_code: str
    evidence_code: str
    body_hash: str
    value_hash: str


@dataclass(frozen=True)
class CountRow:
    code: str
    hit_count: int
    message_count: int


@dataclass(frozen=True)
class MonthCountRow:
    month: str
    hit_count: int
    message_count: int


@dataclass(frozen=True)
class CategoryMonthCountRow:
    category_code: str
    month: str
    hit_count: int
    message_count: int


@dataclass(frozen=True)
class SupportCount:
    support_source: str
    support_code: str
    row_count: int
    message_count: int


@dataclass(frozen=True)
class TaxPaymentArtifacts:
    messages_scanned: int
    messages_with_hits: int
    total_hits: int
    distinct_value_hashes: int
    category_counts: list[CountRow]
    evidence_counts: list[CountRow]
    month_counts: list[MonthCountRow]
    category_month_counts: list[CategoryMonthCountRow]
    support_counts: list[SupportCount]


def stable_hash(value: str, length: int = 24) -> str:
    """Return a short stable hash for local-sensitive values."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _validate_input_name(path: Path, expected_name: str) -> None:
    if path.name != expected_name:
        raise ValueError(f"Refusing to read {path.name!r}; expected {expected_name!r}.")


def _connect_readonly(db_path: Path, expected_name: str) -> sqlite3.Connection:
    _validate_input_name(db_path, expected_name)
    if not db_path.is_file():
        raise FileNotFoundError(f"Input DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_optional_readonly(
    db_path: Path | None, expected_name: str
) -> sqlite3.Connection | None:
    if db_path is None:
        return None
    _validate_input_name(db_path, expected_name)
    if not db_path.is_file():
        return None
    return _connect_readonly(db_path, expected_name)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _resolve_messages_table(conn: sqlite3.Connection) -> str:
    for table_name in ("parsed_messages", "allowed_messages"):
        if _table_exists(conn, table_name):
            return table_name
    raise ValueError(
        "No supported message table found: parsed_messages, allowed_messages"
    )


def read_messages(messages_db: Path) -> list[RawMessage]:
    """Read raw local messages from the ignored allowlist SQLite artifact."""
    conn = _connect_readonly(messages_db, ALLOWED_MESSAGES_DB_NAME)
    try:
        table = _resolve_messages_table(conn)
        rows = conn.execute(
            f"""
            SELECT file_id, source_tag, message_index, timestamp, sender_hash, body_text
            FROM {table}
            ORDER BY file_id, message_index
            """
        ).fetchall()
    finally:
        conn.close()

    return [
        RawMessage(
            file_id=str(row["file_id"]),
            source_tag=None if row["source_tag"] is None else str(row["source_tag"]),
            message_index=int(row["message_index"]),
            timestamp=None if row["timestamp"] is None else str(row["timestamp"]),
            sender_hash=None if row["sender_hash"] is None else str(row["sender_hash"]),
            body_text=str(row["body_text"] or ""),
        )
        for row in rows
    ]


def _match_values(
    pattern: re.Pattern[str], body: str, group_index: int = 0
) -> tuple[str, ...]:
    values: set[str] = set()
    for match in pattern.finditer(body):
        value = match.group(group_index).strip().casefold()
        if value:
            values.add(value)
    return tuple(sorted(values))


def _hashed_values(
    pattern: re.Pattern[str], body: str, group_index: int = 0
) -> tuple[str, ...]:
    return tuple(
        stable_hash(value) for value in _match_values(pattern, body, group_index)
    )


def _reference_hashes(body: str) -> tuple[str, ...]:
    values: set[str] = set()
    for pattern, group_index in REFERENCE_PATTERNS:
        values.update(_match_values(pattern, body, group_index))
    return tuple(stable_hash(value) for value in sorted(values))


def _has_tax_context(body: str) -> bool:
    return bool(TAX_ACCOUNTING_RE.search(body) or REPORTING_RE.search(body))


def extract_message_hits(message: RawMessage) -> list[TaxPaymentHit]:
    """Extract tax/payment signal rows for one message without raw values."""
    body = message.body_text
    body_hash = stable_hash(body, length=32)
    hits: list[TaxPaymentHit] = []
    seen: set[tuple[str, str, str]] = set()

    def append(category: str, evidence: str, value_hash: str = "") -> None:
        key = (category, evidence, value_hash)
        if key in seen:
            return
        seen.add(key)
        hits.append(
            TaxPaymentHit(
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

    has_tax_context = _has_tax_context(body)
    has_invoice_payment = bool(INVOICE_PAYMENT_RE.search(body))
    has_deadline = bool(DEADLINE_RE.search(body))
    has_penalty = bool(PENALTY_RE.search(body))
    has_reporting = bool(REPORTING_RE.search(body))

    if has_tax_context:
        append("tax_accounting", "tax_accounting_keyword")
    if has_invoice_payment:
        append("invoice_payment_proof", "invoice_payment_keyword")
    if PAYMENT_PROOF_RE.search(body):
        append("invoice_payment_proof", "payment_proof_keyword")
    for value_hash in _hashed_values(MONEY_RE, body):
        append("currency_amount", "money_like_hash", value_hash)
    if has_deadline:
        append("deadline_penalty", "deadline_keyword")
    if has_penalty:
        append("deadline_penalty", "penalty_keyword")
    if has_deadline or has_penalty:
        for value_hash in _hashed_values(DATE_LIKE_RE, body):
            append("deadline_penalty", "date_like_hash", value_hash)
    if COMPANY_DOC_RE.search(body) and has_tax_context:
        append("nib_company_tax_docs", "company_doc_tax_context")
    if has_reporting:
        append("monthly_annual_reporting", "reporting_period_keyword")
        for value_hash in _hashed_values(DATE_LIKE_RE, body):
            append("monthly_annual_reporting", "date_like_hash", value_hash)
    if PAYROLL_BPJS_RE.search(body):
        append("payroll_bpjs", "payroll_bpjs_keyword")
    if has_invoice_payment or has_tax_context:
        for value_hash in _reference_hashes(body):
            append("invoice_payment_proof", "reference_hash", value_hash)

    return hits


def extract_tax_payment_hits(messages: Sequence[RawMessage]) -> list[TaxPaymentHit]:
    """Extract de-duplicated tax/payment rows from all messages."""
    hits: list[TaxPaymentHit] = []
    seen: set[tuple[str, int, str, str, str]] = set()
    for message in messages:
        for hit in extract_message_hits(message):
            key = (
                hit.file_id,
                hit.message_index,
                hit.category_code,
                hit.evidence_code,
                hit.value_hash,
            )
            if key in seen:
                continue
            seen.add(key)
            hits.append(hit)
    return hits


def _message_key(hit: TaxPaymentHit) -> tuple[str, int]:
    return (hit.file_id, hit.message_index)


def _month_key(timestamp: str | None) -> str:
    if not timestamp:
        return "unknown"
    match = MONTH_RE.match(timestamp)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    return parsed.strftime("%Y-%m")


def _sorted_count_rows(
    hit_counter: Counter[str],
    message_sets: dict[str, set[tuple[str, int]]],
) -> list[CountRow]:
    return [
        CountRow(
            code=code,
            hit_count=count,
            message_count=len(message_sets[code]),
        )
        for code, count in sorted(
            hit_counter.items(), key=lambda item: (-item[1], item[0])
        )
    ]


def _read_signal_support(signals_db: Path | None) -> list[SupportCount]:
    conn = _connect_optional_readonly(signals_db, ALLOWED_SIGNALS_DB_NAME)
    if conn is None:
        return []

    placeholders = ", ".join("?" for _ in SUPPORT_SIGNAL_CODES)
    try:
        rows = conn.execute(
            f"""
            SELECT signal_code AS code,
                   COUNT(*) AS row_count,
                   COUNT(DISTINCT file_id || char(31) || message_index) AS message_count
            FROM signal_hits
            WHERE signal_code IN ({placeholders})
            GROUP BY signal_code
            """,
            SUPPORT_SIGNAL_CODES,
        ).fetchall()
    finally:
        conn.close()

    return [
        SupportCount(
            support_source="signal_code",
            support_code=str(row["code"]),
            row_count=int(row["row_count"]),
            message_count=int(row["message_count"]),
        )
        for row in rows
    ]


def _read_candidate_support(candidates_db: Path | None) -> list[SupportCount]:
    conn = _connect_optional_readonly(candidates_db, ALLOWED_CANDIDATES_DB_NAME)
    if conn is None:
        return []

    category_placeholders = ", ".join("?" for _ in SUPPORT_CANDIDATE_CATEGORIES)
    evidence_placeholders = ", ".join("?" for _ in SUPPORT_CANDIDATE_EVIDENCES)
    try:
        category_rows = conn.execute(
            f"""
            SELECT category_code AS code,
                   COUNT(*) AS row_count,
                   COUNT(DISTINCT file_id || char(31) || message_index) AS message_count
            FROM extracted_candidates
            WHERE category_code IN ({category_placeholders})
            GROUP BY category_code
            """,
            SUPPORT_CANDIDATE_CATEGORIES,
        ).fetchall()
        evidence_rows = conn.execute(
            f"""
            SELECT evidence_code AS code,
                   COUNT(*) AS row_count,
                   COUNT(DISTINCT file_id || char(31) || message_index) AS message_count
            FROM extracted_candidates
            WHERE evidence_code IN ({evidence_placeholders})
              AND category_code IN ({category_placeholders})
            GROUP BY evidence_code
            """,
            (*SUPPORT_CANDIDATE_EVIDENCES, *SUPPORT_CANDIDATE_CATEGORIES),
        ).fetchall()
    finally:
        conn.close()

    support: list[SupportCount] = []
    support.extend(
        SupportCount(
            support_source="candidate_category",
            support_code=str(row["code"]),
            row_count=int(row["row_count"]),
            message_count=int(row["message_count"]),
        )
        for row in category_rows
    )
    support.extend(
        SupportCount(
            support_source="candidate_evidence",
            support_code=str(row["code"]),
            row_count=int(row["row_count"]),
            message_count=int(row["message_count"]),
        )
        for row in evidence_rows
    )
    return support


def read_support_counts(
    *,
    candidates_db: Path | None,
    signals_db: Path | None,
) -> list[SupportCount]:
    """Read optional aggregate support counts from existing local artifacts."""
    support = [
        *_read_signal_support(signals_db),
        *_read_candidate_support(candidates_db),
    ]
    return sorted(
        support,
        key=lambda row: (-row.row_count, row.support_source, row.support_code),
    )


def build_artifacts(
    *,
    messages_scanned: int,
    hits: Sequence[TaxPaymentHit],
    support_counts: Sequence[SupportCount],
) -> TaxPaymentArtifacts:
    category_hits: Counter[str] = Counter()
    category_messages: dict[str, set[tuple[str, int]]] = defaultdict(set)
    evidence_hits: Counter[str] = Counter()
    evidence_messages: dict[str, set[tuple[str, int]]] = defaultdict(set)
    month_hits: Counter[str] = Counter()
    month_messages: dict[str, set[tuple[str, int]]] = defaultdict(set)
    category_month_hits: Counter[tuple[str, str]] = Counter()
    category_month_messages: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(
        set
    )
    messages_with_hits: set[tuple[str, int]] = set()
    value_hashes: set[str] = set()

    for hit in hits:
        message_key = _message_key(hit)
        month = _month_key(hit.timestamp)
        messages_with_hits.add(message_key)
        category_hits[hit.category_code] += 1
        category_messages[hit.category_code].add(message_key)
        evidence_hits[hit.evidence_code] += 1
        evidence_messages[hit.evidence_code].add(message_key)
        month_hits[month] += 1
        month_messages[month].add(message_key)
        category_month_key = (hit.category_code, month)
        category_month_hits[category_month_key] += 1
        category_month_messages[category_month_key].add(message_key)
        if hit.value_hash:
            value_hashes.add(hit.value_hash)

    month_counts = [
        MonthCountRow(
            month=month,
            hit_count=count,
            message_count=len(month_messages[month]),
        )
        for month, count in sorted(
            month_hits.items(), key=lambda item: (-item[1], item[0])
        )
    ]
    category_month_counts = [
        CategoryMonthCountRow(
            category_code=category,
            month=month,
            hit_count=count,
            message_count=len(category_month_messages[(category, month)]),
        )
        for (category, month), count in sorted(
            category_month_hits.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1]),
        )
    ]

    return TaxPaymentArtifacts(
        messages_scanned=messages_scanned,
        messages_with_hits=len(messages_with_hits),
        total_hits=len(hits),
        distinct_value_hashes=len(value_hashes),
        category_counts=_sorted_count_rows(category_hits, category_messages),
        evidence_counts=_sorted_count_rows(evidence_hits, evidence_messages),
        month_counts=month_counts,
        category_month_counts=category_month_counts,
        support_counts=list(support_counts),
    )


def _create_output_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE tax_payment_runs (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            generated_at_utc TEXT NOT NULL,
            messages_db TEXT NOT NULL,
            candidates_db TEXT,
            signals_db TEXT,
            privacy_mode TEXT NOT NULL
        );

        CREATE TABLE tax_payment_hits (
            file_id TEXT NOT NULL,
            source_tag TEXT,
            message_index INTEGER NOT NULL,
            timestamp TEXT,
            sender_hash TEXT,
            category_code TEXT NOT NULL,
            evidence_code TEXT NOT NULL,
            body_hash TEXT NOT NULL,
            value_hash TEXT NOT NULL,
            PRIMARY KEY (file_id, message_index, category_code, evidence_code, value_hash)
        );

        CREATE TABLE category_totals (
            category_code TEXT PRIMARY KEY,
            hit_count INTEGER NOT NULL,
            message_count INTEGER NOT NULL
        );

        CREATE TABLE evidence_totals (
            evidence_code TEXT PRIMARY KEY,
            hit_count INTEGER NOT NULL,
            message_count INTEGER NOT NULL
        );

        CREATE TABLE month_totals (
            month TEXT PRIMARY KEY,
            hit_count INTEGER NOT NULL,
            message_count INTEGER NOT NULL
        );

        CREATE TABLE category_month_totals (
            category_code TEXT NOT NULL,
            month TEXT NOT NULL,
            hit_count INTEGER NOT NULL,
            message_count INTEGER NOT NULL,
            PRIMARY KEY (category_code, month)
        );

        CREATE TABLE support_counts (
            support_source TEXT NOT NULL,
            support_code TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            message_count INTEGER NOT NULL,
            PRIMARY KEY (support_source, support_code)
        );

        CREATE INDEX idx_tax_payment_hits_category ON tax_payment_hits(category_code);
        CREATE INDEX idx_tax_payment_hits_evidence ON tax_payment_hits(evidence_code);
        CREATE INDEX idx_tax_payment_hits_timestamp ON tax_payment_hits(timestamp);
        """
    )


def write_sqlite(
    *,
    output_db: Path,
    messages_db: Path,
    candidates_db: Path | None,
    signals_db: Path | None,
    hits: Sequence[TaxPaymentHit],
    artifacts: TaxPaymentArtifacts,
    generated_at_utc: str,
) -> None:
    """Write local-only tax/payment hit and aggregate tables."""
    output_db.parent.mkdir(parents=True, exist_ok=True)
    if output_db.exists():
        output_db.unlink()

    conn = sqlite3.connect(output_db)
    try:
        _create_output_schema(conn)
        conn.execute(
            """
            INSERT INTO tax_payment_runs (
                id, generated_at_utc, messages_db, candidates_db, signals_db, privacy_mode
            )
            VALUES (1, ?, ?, ?, ?, ?)
            """,
            (
                generated_at_utc,
                messages_db.name,
                candidates_db.name if candidates_db else None,
                signals_db.name if signals_db else None,
                "local_only_hashes_no_raw_text_no_raw_values_tracked_summary_counts_only",
            ),
        )
        conn.executemany(
            """
            INSERT INTO tax_payment_hits (
                file_id, source_tag, message_index, timestamp, sender_hash,
                category_code, evidence_code, body_hash, value_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    hit.file_id,
                    hit.source_tag,
                    hit.message_index,
                    hit.timestamp,
                    hit.sender_hash,
                    hit.category_code,
                    hit.evidence_code,
                    hit.body_hash,
                    hit.value_hash,
                )
                for hit in hits
            ],
        )
        conn.executemany(
            """
            INSERT INTO category_totals (category_code, hit_count, message_count)
            VALUES (?, ?, ?)
            """,
            [
                (row.code, row.hit_count, row.message_count)
                for row in artifacts.category_counts
            ],
        )
        conn.executemany(
            """
            INSERT INTO evidence_totals (evidence_code, hit_count, message_count)
            VALUES (?, ?, ?)
            """,
            [
                (row.code, row.hit_count, row.message_count)
                for row in artifacts.evidence_counts
            ],
        )
        conn.executemany(
            """
            INSERT INTO month_totals (month, hit_count, message_count)
            VALUES (?, ?, ?)
            """,
            [
                (row.month, row.hit_count, row.message_count)
                for row in artifacts.month_counts
            ],
        )
        conn.executemany(
            """
            INSERT INTO category_month_totals
                (category_code, month, hit_count, message_count)
            VALUES (?, ?, ?, ?)
            """,
            [
                (row.category_code, row.month, row.hit_count, row.message_count)
                for row in artifacts.category_month_counts
            ],
        )
        conn.executemany(
            """
            INSERT INTO support_counts
                (support_source, support_code, row_count, message_count)
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    row.support_source,
                    row.support_code,
                    row.row_count,
                    row.message_count,
                )
                for row in artifacts.support_counts
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    if not rows:
        return "_No rows._\n"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines) + "\n"


def render_summary_markdown(
    artifacts: TaxPaymentArtifacts,
    *,
    messages_db_name: str,
    candidates_db_name: str | None,
    signals_db_name: str | None,
    output_db_name: str,
    generated_at_utc: str,
    summary_limit: int,
) -> str:
    """Render tracked aggregate-only markdown."""
    category_rows = [
        (row.code, row.hit_count, row.message_count)
        for row in artifacts.category_counts[:summary_limit]
    ]
    evidence_rows = [
        (row.code, row.hit_count, row.message_count)
        for row in artifacts.evidence_counts[:summary_limit]
    ]
    month_rows = [
        (row.month, row.hit_count, row.message_count)
        for row in artifacts.month_counts[:summary_limit]
    ]
    category_month_rows = [
        (row.category_code, row.month, row.hit_count, row.message_count)
        for row in artifacts.category_month_counts[:summary_limit]
    ]
    support_rows = [
        (row.support_source, row.support_code, row.row_count, row.message_count)
        for row in artifacts.support_counts[:summary_limit]
    ]
    support_db_count = int(candidates_db_name is not None) + int(
        signals_db_name is not None
    )

    return (
        "\n".join(
            [
                "# Allowed Tax/Payment Aggregate Summary",
                "",
                f"- Generated UTC: `{generated_at_utc}`",
                f"- Input messages DB: `{messages_db_name}`",
                f"- Input candidates DB: `{candidates_db_name or 'not read'}`",
                f"- Input signal DB: `{signals_db_name or 'not read'}`",
                f"- Local tax/payment SQLite artifact: `{output_db_name}`",
                "- Privacy boundary: tracked markdown is aggregate counts only; "
                "the ignored local SQLite stores body/value hashes, not raw values.",
                "",
                "## Counts",
                "",
                _markdown_table(
                    ["Metric", "Value"],
                    [
                        ("Messages scanned", artifacts.messages_scanned),
                        (
                            "Messages with tax/payment signals",
                            artifacts.messages_with_hits,
                        ),
                        ("Tax/payment hit rows", artifacts.total_hits),
                        (
                            "Distinct hashed local values",
                            artifacts.distinct_value_hashes,
                        ),
                        ("Optional support DBs read", support_db_count),
                    ],
                ),
                "## Categories",
                "",
                _markdown_table(
                    ["Category", "Hit rows", "Messages"],
                    category_rows,
                ),
                "## Evidence Codes",
                "",
                _markdown_table(
                    ["Evidence", "Hit rows", "Messages"],
                    evidence_rows,
                ),
                "## Month Counts",
                "",
                _markdown_table(
                    ["Month", "Hit rows", "Messages"],
                    month_rows,
                ),
                "## Category x Month",
                "",
                _markdown_table(
                    ["Category", "Month", "Hit rows", "Messages"],
                    category_month_rows,
                ),
                "## Input Support Counts",
                "",
                _markdown_table(
                    ["Support source", "Code", "Rows", "Messages"],
                    support_rows,
                ),
                "## Caveats",
                "",
                "- Deterministic regex extraction only; counts are routing signals, not legal conclusions.",
                "- `nib_company_tax_docs` requires company-document language plus explicit tax/reporting context.",
                "- Amounts, dates, invoice numbers, payment references, message text, contacts, and paths are not present in this tracked summary.",
            ]
        )
        + "\n"
    )


def write_summary_markdown(summary_path: Path, content: str) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(content, encoding="utf-8")


def run_extraction(
    *,
    messages_db: Path,
    candidates_db: Path | None,
    signals_db: Path | None,
    output_db: Path,
    summary_path: Path,
    summary_limit: int,
    generated_at_utc: str | None = None,
) -> TaxPaymentArtifacts:
    """Run the tax/payment extraction and write local artifacts."""
    if messages_db.resolve() == output_db.resolve():
        raise ValueError("Input messages DB and output DB paths must be different.")

    generated_at = (
        generated_at_utc or datetime.now(tz=UTC).replace(microsecond=0).isoformat()
    )
    messages = read_messages(messages_db)
    hits = extract_tax_payment_hits(messages)
    support_counts = read_support_counts(
        candidates_db=candidates_db, signals_db=signals_db
    )
    artifacts = build_artifacts(
        messages_scanned=len(messages),
        hits=hits,
        support_counts=support_counts,
    )
    write_sqlite(
        output_db=output_db,
        messages_db=messages_db,
        candidates_db=candidates_db
        if candidates_db and candidates_db.is_file()
        else None,
        signals_db=signals_db if signals_db and signals_db.is_file() else None,
        hits=hits,
        artifacts=artifacts,
        generated_at_utc=generated_at,
    )
    summary = render_summary_markdown(
        artifacts,
        messages_db_name=messages_db.name,
        candidates_db_name=candidates_db.name
        if candidates_db and candidates_db.is_file()
        else None,
        signals_db_name=signals_db.name
        if signals_db and signals_db.is_file()
        else None,
        output_db_name=output_db.name,
        generated_at_utc=generated_at,
        summary_limit=summary_limit,
    )
    write_summary_markdown(summary_path, summary)
    return artifacts


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract aggregate tax/payment signals from local WhatsApp allowlist messages."
    )
    parser.add_argument("--messages-db", type=Path, default=DEFAULT_MESSAGES_DB)
    parser.add_argument("--candidates-db", type=Path, default=DEFAULT_CANDIDATES_DB)
    parser.add_argument("--signals-db", type=Path, default=DEFAULT_SIGNALS_DB)
    parser.add_argument("--output-db", type=Path, default=DEFAULT_OUTPUT_DB)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--summary-limit", type=int, default=25)
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable run stats."
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress success output.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        artifacts = run_extraction(
            messages_db=args.messages_db,
            candidates_db=args.candidates_db,
            signals_db=args.signals_db,
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
                    "category_counts": {
                        row.code: row.hit_count for row in artifacts.category_counts
                    },
                    "hit_count": artifacts.total_hits,
                    "messages_scanned": artifacts.messages_scanned,
                    "messages_with_hits": artifacts.messages_with_hits,
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
