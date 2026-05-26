#!/usr/bin/env python3
"""Extract aggregate WhatsApp document-requirement signals locally.

The extractor reads raw message text only from the ignored local allowlist
SQLite. Outputs intentionally avoid raw message text, raw extracted values,
phone numbers, emails, raw contact names, and raw source paths.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Iterable, Sequence

LOGGER = logging.getLogger(__name__)

DEFAULT_ANALYSIS_DIR = Path("research/personal/wa-corpus/analysis")
DEFAULT_MESSAGES_DB = DEFAULT_ANALYSIS_DIR / "allowed_messages.local.sqlite"
DEFAULT_CANDIDATES_DB = DEFAULT_ANALYSIS_DIR / "allowed_candidates.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_ANALYSIS_DIR / "allowed_document_requirements.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_ANALYSIS_DIR / "allowed_document_requirements_summary.md"

REQUIREMENT_CONTEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b("
        r"need|needs|required|requirement|requirements|please send|send|upload|"
        r"provide|submit|prepare|attach|bring|missing|pending|dokumen|document|"
        r"documents|perlu|butuh|dibutuhkan|wajib|harus|tolong|mohon|kirim|"
        r"lengkap|kurang"
        r")\b",
        re.I,
    ),
)


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
    has_media_omitted: bool


@dataclass(frozen=True)
class CandidateContext:
    file_id: str
    message_index: int
    category_code: str
    evidence_code: str
    body_hash: str
    value_hash: str


@dataclass(frozen=True)
class RequirementPattern:
    requirement_code: str
    evidence_code: str
    patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class ValuePattern:
    requirement_code: str
    evidence_code: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class RequirementHit:
    file_id: str
    source_tag_hash: str
    message_index: int
    timestamp: str | None
    month: str
    sender_hash: str
    body_hash: str
    requirement_code: str
    evidence_code: str
    context_code: str
    value_hash: str


@dataclass(frozen=True)
class ExtractionResult:
    messages: list[RawMessage]
    candidate_count: int
    hits: list[RequirementHit]


DOCUMENT_PATTERNS: tuple[RequirementPattern, ...] = (
    RequirementPattern(
        requirement_code="passport_identity_document",
        evidence_code="passport_identity_keyword",
        patterns=(
            re.compile(
                r"\b("
                r"passport|paspor|ktp|id card|identity card|kartu identitas|"
                r"copy of id|scan id|npwp pribadi|national id"
                r")\b",
                re.I,
            ),
        ),
    ),
    RequirementPattern(
        requirement_code="company_document",
        evidence_code="company_document_keyword",
        patterns=(
            re.compile(
                r"\b("
                r"company document|company documents|akta|deed|articles of association|"
                r"ahu|sk kemenkumham|nib|oss|business license|siup|tdp|"
                r"shareholder|director|commissioner|beneficial owner|npwp perusahaan"
                r")\b",
                re.I,
            ),
        ),
    ),
    RequirementPattern(
        requirement_code="tax_document",
        evidence_code="tax_document_keyword",
        patterns=(
            re.compile(
                r"\b("
                r"tax document|tax documents|tax report|pajak|npwp|spt|efin|e-fin|"
                r"faktur|bukti potong|pph|ppn|tax invoice|tax card"
                r")\b",
                re.I,
            ),
        ),
    ),
    RequirementPattern(
        requirement_code="property_document",
        evidence_code="property_document_keyword",
        patterns=(
            re.compile(
                r"\b("
                r"property document|land certificate|sertifikat|certificate|shm|hgb|"
                r"ajb|lease agreement|rental agreement|sppt|pbb|imb|pbg|"
                r"building permit|land title|tanah"
                r")\b",
                re.I,
            ),
        ),
    ),
    RequirementPattern(
        requirement_code="visa_immigration_document",
        evidence_code="visa_immigration_keyword",
        patterns=(
            re.compile(
                r"\b("
                r"visa|kitas|kitap|b211|voa|e-?visa|stay permit|immigration|"
                r"imigrasi|arrival stamp|boarding pass|flight ticket|sponsor letter|"
                r"guarantee letter|telex"
                r")\b",
                re.I,
            ),
        ),
    ),
    RequirementPattern(
        requirement_code="translation_legalization_notary",
        evidence_code="translation_legalization_notary_keyword",
        patterns=(
            re.compile(
                r"\b("
                r"translate|translation|translated|terjemahan|legalize|legalized|"
                r"legalization|legalisasi|legalisir|apostille|notary|notaris|"
                r"certified true copy|waarmerking"
                r")\b",
                re.I,
            ),
        ),
    ),
    RequirementPattern(
        requirement_code="photo_biometric",
        evidence_code="photo_biometric_keyword",
        patterns=(
            re.compile(
                r"\b("
                r"photo|foto|passport photo|red background|white background|"
                r"biometric|biometrics|fingerprint|sidik jari|scan biometrik"
                r")\b",
                re.I,
            ),
        ),
    ),
    RequirementPattern(
        requirement_code="payment_proof",
        evidence_code="payment_proof_keyword",
        patterns=(
            re.compile(
                r"\b("
                r"payment proof|proof of payment|bukti bayar|bukti transfer|"
                r"transfer receipt|receipt|bank slip|payment receipt|"
                r"transaction proof|paid|invoice|billing"
                r")\b",
                re.I,
            ),
        ),
    ),
)

VALUE_PATTERNS: tuple[ValuePattern, ...] = (
    ValuePattern(
        requirement_code="passport_identity_document",
        evidence_code="passport_like_value_hash",
        pattern=re.compile(r"\b[A-Z]{1,2}[0-9]{6,8}\b", re.I),
    ),
    ValuePattern(
        requirement_code="payment_proof",
        evidence_code="money_like_value_hash",
        pattern=re.compile(
            r"\b(?:rp|idr|usd|aud|eur)\s?[\d.,]+|[\d.,]+\s?\b(?:rp|idr|usd|aud|eur)\b",
            re.I,
        ),
    ),
    ValuePattern(
        requirement_code="tax_document",
        evidence_code="tax_id_like_value_hash",
        pattern=re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}\.?\d-?\d{3}\.?\d{3}\b"),
    ),
    ValuePattern(
        requirement_code="company_document",
        evidence_code="company_registration_like_value_hash",
        pattern=re.compile(r"\b(?:nib|ahu|oss)[\s:#-]*[A-Z0-9./-]{6,}\b", re.I),
    ),
)

CANDIDATE_REQUIREMENT_MAP: dict[str, tuple[str, str]] = {
    "identity_document": ("passport_identity_document", "candidate_identity_document"),
    "company_case": ("company_document", "candidate_company_case"),
    "tax_payment": ("tax_document", "candidate_tax_payment"),
    "property_case": ("property_document", "candidate_property_case"),
    "visa_case": ("visa_immigration_document", "candidate_visa_case"),
    "money_reference": ("payment_proof", "candidate_money_reference"),
}


def stable_hash(value: str, length: int = 24) -> str:
    """Return a stable short hash for local sensitive values."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def month_key(timestamp: str | None) -> str:
    """Return a safe YYYY-MM bucket for an ISO-ish timestamp."""
    if not timestamp or len(timestamp) < 7:
        return "unknown"
    return timestamp[:7]


def _connect_readonly(path: Path) -> sqlite3.Connection:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def read_messages(db_path: Path) -> list[RawMessage]:
    """Read raw local allowlist messages from SQLite."""
    if not db_path.is_file():
        raise FileNotFoundError(f"Messages DB does not exist: {db_path}")

    with _connect_readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT file_id, source_tag, message_index, timestamp, sender_hash,
                   body_text, has_url, has_email, has_phone_like, has_media_omitted
            FROM parsed_messages
            ORDER BY file_id, message_index
            """
        ).fetchall()

    return [
        RawMessage(
            file_id=str(row[0]),
            source_tag=row[1],
            message_index=int(row[2]),
            timestamp=row[3],
            sender_hash=row[4],
            body_text=str(row[5]),
            has_url=bool(row[6]),
            has_email=bool(row[7]),
            has_phone_like=bool(row[8]),
            has_media_omitted=bool(row[9]),
        )
        for row in rows
    ]


def read_candidates(db_path: Path) -> list[CandidateContext]:
    """Read hashed candidate context from the local candidate SQLite."""
    if not db_path.is_file():
        raise FileNotFoundError(f"Candidates DB does not exist: {db_path}")

    with _connect_readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT file_id, message_index, category_code, evidence_code, body_hash, value_hash
            FROM extracted_candidates
            ORDER BY file_id, message_index, category_code, evidence_code
            """
        ).fetchall()

    return [
        CandidateContext(
            file_id=str(row[0]),
            message_index=int(row[1]),
            category_code=str(row[2]),
            evidence_code=str(row[3]),
            body_hash=str(row[4]),
            value_hash="" if row[5] is None else str(row[5]),
        )
        for row in rows
    ]


def requirement_context_code(body: str) -> str:
    """Classify whether a message explicitly asks for a requirement."""
    if any(pattern.search(body) for pattern in REQUIREMENT_CONTEXT_PATTERNS):
        return "explicit_requirement_context"
    return "document_mention_context"


def hashed_regex_values(pattern: re.Pattern[str], body: str) -> tuple[str, ...]:
    """Return hashes for unique regex matches without exposing raw matches."""
    values = {match.group(0).strip().casefold() for match in pattern.finditer(body)}
    return tuple(sorted(stable_hash(value) for value in values if value))


def _message_source_hash(message: RawMessage) -> str:
    if not message.source_tag:
        return ""
    return stable_hash(message.source_tag.strip().casefold(), length=16)


def _base_hit(
    *,
    message: RawMessage,
    body_hash: str,
    requirement_code: str,
    evidence_code: str,
    context_code: str,
    value_hash: str = "",
) -> RequirementHit:
    return RequirementHit(
        file_id=message.file_id,
        source_tag_hash=_message_source_hash(message),
        message_index=message.message_index,
        timestamp=message.timestamp,
        month=month_key(message.timestamp),
        sender_hash=message.sender_hash or "",
        body_hash=body_hash,
        requirement_code=requirement_code,
        evidence_code=evidence_code,
        context_code=context_code,
        value_hash=value_hash,
    )


def extract_message_hits(
    message: RawMessage,
    candidate_contexts: Sequence[CandidateContext],
) -> list[RequirementHit]:
    """Extract document-requirement hits for one message."""
    hits: list[RequirementHit] = []
    body = message.body_text
    body_hash = stable_hash(body, length=32)
    context_code = requirement_context_code(body)

    for pattern_spec in DOCUMENT_PATTERNS:
        if any(pattern.search(body) for pattern in pattern_spec.patterns):
            hits.append(
                _base_hit(
                    message=message,
                    body_hash=body_hash,
                    requirement_code=pattern_spec.requirement_code,
                    evidence_code=pattern_spec.evidence_code,
                    context_code=context_code,
                )
            )

    for value_spec in VALUE_PATTERNS:
        for value_hash in hashed_regex_values(value_spec.pattern, body):
            hits.append(
                _base_hit(
                    message=message,
                    body_hash=body_hash,
                    requirement_code=value_spec.requirement_code,
                    evidence_code=value_spec.evidence_code,
                    context_code=context_code,
                    value_hash=value_hash,
                )
            )

    for candidate in candidate_contexts:
        mapped = CANDIDATE_REQUIREMENT_MAP.get(candidate.category_code)
        if mapped is None:
            continue
        requirement_code, evidence_code = mapped
        hits.append(
            _base_hit(
                message=message,
                body_hash=candidate.body_hash or body_hash,
                requirement_code=requirement_code,
                evidence_code=evidence_code,
                context_code="candidate_context",
                value_hash=candidate.value_hash,
            )
        )

    if message.has_media_omitted and any(
        hit.requirement_code in {"passport_identity_document", "photo_biometric"}
        for hit in hits
    ):
        hits.append(
            _base_hit(
                message=message,
                body_hash=body_hash,
                requirement_code="photo_biometric",
                evidence_code="media_omitted_near_identity_photo",
                context_code=context_code,
            )
        )

    return dedupe_hits(hits)


def _hit_key(hit: RequirementHit) -> tuple[str, int, str, str, str, str]:
    return (
        hit.file_id,
        hit.message_index,
        hit.requirement_code,
        hit.evidence_code,
        hit.context_code,
        hit.value_hash,
    )


def dedupe_hits(hits: Iterable[RequirementHit]) -> list[RequirementHit]:
    """Deduplicate hits while preserving first-seen order."""
    deduped: list[RequirementHit] = []
    seen: set[tuple[str, int, str, str, str, str]] = set()
    for hit in hits:
        key = _hit_key(hit)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
    return deduped


def extract_requirement_hits(
    messages: Sequence[RawMessage],
    candidates: Sequence[CandidateContext],
) -> list[RequirementHit]:
    """Extract all document-requirement hits from messages and candidates."""
    candidates_by_message: dict[tuple[str, int], list[CandidateContext]] = defaultdict(
        list
    )
    for candidate in candidates:
        candidates_by_message[(candidate.file_id, candidate.message_index)].append(
            candidate
        )

    hits: list[RequirementHit] = []
    for message in messages:
        hits.extend(
            extract_message_hits(
                message=message,
                candidate_contexts=candidates_by_message.get(
                    (message.file_id, message.message_index),
                    (),
                ),
            )
        )
    return dedupe_hits(hits)


def message_key(hit: RequirementHit) -> tuple[str, int]:
    """Return the local message key for aggregate counting."""
    return (hit.file_id, hit.message_index)


def _count_messages_by(rows: Iterable[RequirementHit], attr: str) -> dict[str, int]:
    grouped: dict[str, set[tuple[str, int]]] = defaultdict(set)
    for row in rows:
        grouped[str(getattr(row, attr))].add(message_key(row))
    return {key: len(value) for key, value in grouped.items()}


def _category_counts(hits: Sequence[RequirementHit]) -> list[tuple[str, int, int]]:
    hit_counts = Counter(hit.requirement_code for hit in hits)
    message_counts = _count_messages_by(hits, "requirement_code")
    return [
        (category, hit_count, message_counts[category])
        for category, hit_count in hit_counts.most_common()
    ]


def _evidence_counts(hits: Sequence[RequirementHit]) -> list[tuple[str, int, int]]:
    hit_counts = Counter(hit.evidence_code for hit in hits)
    message_counts = _count_messages_by(hits, "evidence_code")
    return [
        (evidence, hit_count, message_counts[evidence])
        for evidence, hit_count in hit_counts.most_common()
    ]


def _context_counts(hits: Sequence[RequirementHit]) -> list[tuple[str, int, int]]:
    hit_counts = Counter(hit.context_code for hit in hits)
    message_counts = _count_messages_by(hits, "context_code")
    return [
        (context, hit_count, message_counts[context])
        for context, hit_count in hit_counts.most_common()
    ]


def _month_category_counts(
    hits: Sequence[RequirementHit],
) -> list[tuple[str, str, int, int]]:
    hit_counts = Counter((hit.month, hit.requirement_code) for hit in hits)
    message_sets: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(set)
    for hit in hits:
        message_sets[(hit.month, hit.requirement_code)].add(message_key(hit))
    return sorted(
        (
            (month, category, hit_count, len(message_sets[(month, category)]))
            for (month, category), hit_count in hit_counts.items()
        ),
        key=lambda row: (-row[2], row[0], row[1]),
    )


def _cooccurrence_counts(hits: Sequence[RequirementHit]) -> list[tuple[str, str, int]]:
    categories_by_message: dict[tuple[str, int], set[str]] = defaultdict(set)
    for hit in hits:
        categories_by_message[message_key(hit)].add(hit.requirement_code)

    counts: Counter[tuple[str, str]] = Counter()
    for categories in categories_by_message.values():
        for left, right in combinations(sorted(categories), 2):
            counts[(left, right)] += 1
    return [(left, right, count) for (left, right), count in counts.most_common()]


def write_sqlite(
    *,
    output_db: Path,
    messages_db: Path,
    candidates_db: Path,
    result: ExtractionResult,
) -> None:
    """Write ignored local SQLite output with hashed values and counters only."""
    output_db.parent.mkdir(parents=True, exist_ok=True)
    if output_db.exists():
        output_db.unlink()

    hits = result.hits
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            CREATE TABLE requirement_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at TEXT NOT NULL,
                messages_db TEXT NOT NULL,
                candidates_db TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                messages_scanned INTEGER NOT NULL,
                candidate_rows_read INTEGER NOT NULL,
                hit_rows INTEGER NOT NULL
            );

            CREATE TABLE requirement_hits (
                file_id TEXT NOT NULL,
                source_tag_hash TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                month TEXT NOT NULL,
                sender_hash TEXT NOT NULL,
                body_hash TEXT NOT NULL,
                requirement_code TEXT NOT NULL,
                evidence_code TEXT NOT NULL,
                context_code TEXT NOT NULL,
                value_hash TEXT NOT NULL,
                PRIMARY KEY (
                    file_id,
                    message_index,
                    requirement_code,
                    evidence_code,
                    context_code,
                    value_hash
                )
            );

            CREATE TABLE requirement_category_counts (
                requirement_code TEXT PRIMARY KEY,
                hit_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL
            );

            CREATE TABLE requirement_evidence_counts (
                evidence_code TEXT PRIMARY KEY,
                hit_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL
            );

            CREATE TABLE requirement_context_counts (
                context_code TEXT PRIMARY KEY,
                hit_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL
            );

            CREATE TABLE requirement_month_counts (
                month TEXT NOT NULL,
                requirement_code TEXT NOT NULL,
                hit_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                PRIMARY KEY (month, requirement_code)
            );

            CREATE INDEX idx_requirement_hits_category ON requirement_hits(requirement_code);
            CREATE INDEX idx_requirement_hits_evidence ON requirement_hits(evidence_code);
            CREATE INDEX idx_requirement_hits_month ON requirement_hits(month);
            """
        )
        conn.execute(
            """
            INSERT INTO requirement_runs (
                id, generated_at, messages_db, candidates_db, privacy_mode,
                messages_scanned, candidate_rows_read, hit_rows
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                messages_db.name,
                candidates_db.name,
                "local_only_hashed_document_requirements_no_raw_text_no_raw_values",
                len(result.messages),
                result.candidate_count,
                len(hits),
            ),
        )
        conn.executemany(
            """
            INSERT INTO requirement_hits (
                file_id, source_tag_hash, message_index, timestamp, month, sender_hash,
                body_hash, requirement_code, evidence_code, context_code, value_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    hit.file_id,
                    hit.source_tag_hash,
                    hit.message_index,
                    hit.timestamp,
                    hit.month,
                    hit.sender_hash,
                    hit.body_hash,
                    hit.requirement_code,
                    hit.evidence_code,
                    hit.context_code,
                    hit.value_hash,
                )
                for hit in hits
            ],
        )
        conn.executemany(
            """
            INSERT INTO requirement_category_counts (
                requirement_code, hit_count, message_count
            )
            VALUES (?, ?, ?)
            """,
            _category_counts(hits),
        )
        conn.executemany(
            """
            INSERT INTO requirement_evidence_counts (
                evidence_code, hit_count, message_count
            )
            VALUES (?, ?, ?)
            """,
            _evidence_counts(hits),
        )
        conn.executemany(
            """
            INSERT INTO requirement_context_counts (
                context_code, hit_count, message_count
            )
            VALUES (?, ?, ?)
            """,
            _context_counts(hits),
        )
        conn.executemany(
            """
            INSERT INTO requirement_month_counts (
                month, requirement_code, hit_count, message_count
            )
            VALUES (?, ?, ?, ?)
            """,
            _month_category_counts(hits),
        )
        conn.commit()


def write_summary(
    *,
    summary_path: Path,
    messages_db: Path,
    candidates_db: Path,
    output_db: Path,
    result: ExtractionResult,
) -> None:
    """Write tracked aggregate-only markdown summary."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    hits = result.hits
    messages_with_hits = {message_key(hit) for hit in hits}
    explicit_messages = {
        message_key(hit)
        for hit in hits
        if hit.context_code == "explicit_requirement_context"
    }
    value_hash_count = len({hit.value_hash for hit in hits if hit.value_hash})

    lines: list[str] = [
        "# WhatsApp Allowlist Document Requirement Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Input raw SQLite artifact: `{messages_db.name}`",
        f"Input candidate SQLite artifact: `{candidates_db.name}`",
        f"Local requirement SQLite artifact: `{output_db.name}`",
        "",
        "## Privacy Mode",
        "",
        "- This tracked summary contains no raw message text.",
        "- This tracked summary contains no message snippets.",
        "- This tracked summary contains no phone numbers or emails.",
        "- This tracked summary contains no raw source paths.",
        "- This tracked summary contains no raw contact names.",
        "- This tracked summary contains no raw extracted document values.",
        "- The ignored local SQLite stores hashes, message indexes, timestamps, and category counters only.",
        "",
        "## Scope",
        "",
        "- Extracted only from messages parsed out of `content_allowlist.local.jsonl`.",
        "- Denylist and holdlist files were not opened.",
        "- Detection is deterministic regex plus existing hashed candidate context, not LLM interpretation.",
        "- Categories are aggregate routing signals, not legal or client-level conclusions.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Messages scanned | {len(result.messages)} |",
        f"| Candidate rows read | {result.candidate_count} |",
        f"| Messages with document requirement signals | {len(messages_with_hits)} |",
        f"| Messages with explicit requirement context | {len(explicit_messages)} |",
        f"| Requirement hit rows | {len(hits)} |",
        f"| Distinct requirement categories | {len({hit.requirement_code for hit in hits})} |",
        f"| Distinct hashed extracted values | {value_hash_count} |",
        "",
        "## Requirement Categories",
        "",
        "| Requirement category | Hit rows | Messages |",
        "|---|---:|---:|",
    ]
    for category, hit_count, message_count in _category_counts(hits):
        lines.append(f"| {category} | {hit_count} | {message_count} |")

    lines.extend(
        [
            "",
            "## Evidence Codes",
            "",
            "| Evidence code | Hit rows | Messages |",
            "|---|---:|---:|",
        ]
    )
    for evidence, hit_count, message_count in _evidence_counts(hits):
        lines.append(f"| {evidence} | {hit_count} | {message_count} |")

    lines.extend(
        [
            "",
            "## Context Codes",
            "",
            "| Context code | Hit rows | Messages |",
            "|---|---:|---:|",
        ]
    )
    for context, hit_count, message_count in _context_counts(hits):
        lines.append(f"| {context} | {hit_count} | {message_count} |")

    lines.extend(
        [
            "",
            "## Top Month Buckets",
            "",
            "| Month | Requirement category | Hit rows | Messages |",
            "|---|---|---:|---:|",
        ]
    )
    for month, category, hit_count, message_count in _month_category_counts(hits)[:20]:
        lines.append(f"| {month} | {category} | {hit_count} | {message_count} |")

    lines.extend(
        [
            "",
            "## Top Requirement Co-Occurrences",
            "",
            "| Requirement A | Requirement B | Messages |",
            "|---|---|---:|",
        ]
    )
    for left, right, count in _cooccurrence_counts(hits)[:20]:
        lines.append(f"| {left} | {right} | {count} |")

    lines.extend(
        [
            "",
            "## Operational Reading",
            "",
            "- Use the ignored SQLite for local queueing by `requirement_code`, `evidence_code`, and month.",
            "- Resolve hashed values only inside local owner-review tools.",
            "- Treat high `candidate_context` volume as inherited signal breadth from the prior candidate extractor.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def extract_document_requirements(
    *,
    messages_db: Path,
    candidates_db: Path,
    output_db: Path,
    summary_path: Path,
) -> ExtractionResult:
    """Extract document-requirement artifacts from local SQLite inputs."""
    messages = read_messages(messages_db)
    candidates = read_candidates(candidates_db)
    hits = extract_requirement_hits(messages, candidates)
    result = ExtractionResult(
        messages=messages,
        candidate_count=len(candidates),
        hits=hits,
    )
    write_sqlite(
        output_db=output_db,
        messages_db=messages_db,
        candidates_db=candidates_db,
        result=result,
    )
    write_summary(
        summary_path=summary_path,
        messages_db=messages_db,
        candidates_db=candidates_db,
        output_db=output_db,
        result=result,
    )
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Extract local-only aggregate document requirement signals."
    )
    parser.add_argument(
        "--messages-db",
        type=Path,
        default=DEFAULT_MESSAGES_DB,
        help="allowed_messages.local.sqlite produced by parse_allowed_messages.",
    )
    parser.add_argument(
        "--candidates-db",
        type=Path,
        default=DEFAULT_CANDIDATES_DB,
        help="allowed_candidates.local.sqlite produced by extract_allowed_candidates.",
    )
    parser.add_argument(
        "--output-db",
        type=Path,
        default=DEFAULT_OUTPUT_DB,
        help="Ignored local SQLite output for hashed requirement hits and counters.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=DEFAULT_SUMMARY,
        help="Tracked aggregate-only markdown summary.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)
    try:
        result = extract_document_requirements(
            messages_db=args.messages_db,
            candidates_db=args.candidates_db,
            output_db=args.output_db,
            summary_path=args.summary,
        )
    except FileNotFoundError as exc:
        LOGGER.error("%s", exc)
        return 2

    LOGGER.info("Scanned %d messages.", len(result.messages))
    LOGGER.info("Read %d candidate rows.", result.candidate_count)
    LOGGER.info("Wrote %d document requirement hits.", len(result.hits))
    LOGGER.info("Wrote %s", args.output_db)
    LOGGER.info("Wrote %s", args.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
