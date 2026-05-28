#!/usr/bin/env python3
"""Aggregate local WhatsApp immigration lifecycle stages.

This analyzer is local-only. It may read raw allowlisted message text from the
ignored ``allowed_messages.local.sqlite`` database to classify deterministic
stage codes, but it never writes raw message text, raw extracted values, sender
labels, phone numbers, emails, or local source paths to tracked output.
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
from itertools import combinations
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_ANALYSIS_DIR = Path("research/personal/wa-corpus/analysis")
DEFAULT_MESSAGES_DB = DEFAULT_ANALYSIS_DIR / "allowed_messages.local.sqlite"
DEFAULT_CANDIDATES_DB = DEFAULT_ANALYSIS_DIR / "allowed_candidates.local.sqlite"
DEFAULT_SIGNAL_DB = DEFAULT_ANALYSIS_DIR / "allowed_signal_hits.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_ANALYSIS_DIR / "allowed_immigration_lifecycle.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_ANALYSIS_DIR / "allowed_immigration_lifecycle_summary.md"

ALLOWED_MESSAGES_NAME = "allowed_messages.local.sqlite"
ALLOWED_CANDIDATES_NAME = "allowed_candidates.local.sqlite"
ALLOWED_SIGNAL_NAME = "allowed_signal_hits.local.sqlite"

STAGE_ORDER: tuple[str, ...] = (
    "lead_intake",
    "identity_passport",
    "sponsor_company",
    "application_submission",
    "appointment_biometric",
    "approval_issuance",
    "extension_renewal_expiry",
    "problem_escalation",
)
STAGE_LABELS: dict[str, str] = {
    "lead_intake": "lead/intake",
    "identity_passport": "identity/passport",
    "sponsor_company": "sponsor/company",
    "application_submission": "application/submission",
    "appointment_biometric": "appointment/biometric",
    "approval_issuance": "approval/issuance",
    "extension_renewal_expiry": "extension/renewal/expiry",
    "problem_escalation": "problem/escalation",
}
PRIMARY_STAGE_PRIORITY: dict[str, int] = {
    "problem_escalation": 80,
    "extension_renewal_expiry": 70,
    "approval_issuance": 60,
    "appointment_biometric": 50,
    "identity_passport": 45,
    "sponsor_company": 45,
    "application_submission": 35,
    "lead_intake": 20,
}
MONTH_RE = re.compile(r"^(\d{4})-(\d{2})")


@dataclass(frozen=True)
class StageRule:
    stage_code: str
    body_patterns: tuple[re.Pattern[str], ...] = ()
    signal_codes: frozenset[str] = frozenset()
    candidate_categories: frozenset[str] = frozenset()
    candidate_evidence_codes: frozenset[str] = frozenset()


@dataclass(frozen=True)
class MessageRecord:
    file_id: str
    source_tag: str
    message_index: int
    timestamp: str | None
    month: str
    body_text: str
    is_system_event: bool


@dataclass(frozen=True)
class FeatureRecord:
    file_id: str
    source_tag: str
    message_index: int
    timestamp: str | None
    code: str


@dataclass(frozen=True)
class StageHit:
    file_id: str
    source_tag: str
    message_index: int
    timestamp: str | None
    month: str
    stage_code: str
    stage_label: str
    evidence_code: str
    score: int


@dataclass(frozen=True)
class MessageStageSummary:
    file_id: str
    source_tag: str
    message_index: int
    timestamp: str | None
    month: str
    primary_stage_code: str
    primary_stage_label: str
    stage_count: int
    evidence_count: int
    total_score: int


@dataclass(frozen=True)
class LifecycleArtifacts:
    input_message_count: int
    classified_message_count: int
    skipped_system_event_count: int
    orphan_feature_message_count: int
    stage_hits: list[StageHit]
    message_stage_summaries: list[MessageStageSummary]
    stage_totals: list[dict[str, object]]
    stage_month_matrix: list[dict[str, object]]
    stage_source_matrix: list[dict[str, object]]
    stage_cooccurrence: list[dict[str, object]]
    stage_transitions: list[dict[str, object]]
    evidence_totals: list[dict[str, object]]


@dataclass(frozen=True)
class CliConfig:
    messages_db: Path
    candidates_db: Path
    signal_db: Path
    output_db: Path
    summary: Path
    summary_limit: int
    generated_at_utc: str | None
    emit_json: bool
    quiet: bool


STAGE_RULES: tuple[StageRule, ...] = (
    StageRule(
        stage_code="lead_intake",
        body_patterns=(
            re.compile(
                r"\b("
                r"hello|hi|ciao|buongiorno|consultation|consult|interested|"
                r"need help|can you help|what visa|which visa|quotation|quote|"
                r"price|pricing|service|requirements|how to apply|vorrei|vorremmo"
                r")\b",
                re.I,
            ),
        ),
    ),
    StageRule(
        stage_code="identity_passport",
        body_patterns=(
            re.compile(
                r"\b("
                r"passport|paspor|ktp|npwp|identity|id card|photo|foto|scan|"
                r"copy|biodata|passport number"
                r")\b",
                re.I,
            ),
        ),
        signal_codes=frozenset({"identity_document"}),
        candidate_categories=frozenset({"identity_document"}),
        candidate_evidence_codes=frozenset({"passport_like_hash"}),
    ),
    StageRule(
        stage_code="sponsor_company",
        body_patterns=(
            re.compile(
                r"\b("
                r"sponsor|sponsorship|company|pt pma|shareholder|director|"
                r"commissioner|akta|deed|nib|oss|kbli|corporate"
                r")\b",
                re.I,
            ),
        ),
        signal_codes=frozenset({"company_corporate"}),
        candidate_categories=frozenset({"company_case"}),
    ),
    StageRule(
        stage_code="application_submission",
        body_patterns=(
            re.compile(
                r"\b("
                r"submit|submitted|submission|apply|application|lodg(?:e|ed)|"
                r"processing|process|upload|form|documents? sent|sent to immigration|"
                r"submitted to immigration|immigration submission|immigration process|"
                r"molina|e-?visa|b211|kitas|kitap"
                r")\b",
                re.I,
            ),
        ),
        signal_codes=frozenset({"immigration"}),
        candidate_categories=frozenset({"visa_case"}),
    ),
    StageRule(
        stage_code="appointment_biometric",
        body_patterns=(
            re.compile(
                r"\b("
                r"appointment|biometric|fingerprint|interview|schedule|booking|"
                r"come to immigration|immigration office|kantor imigrasi|photo session"
                r")\b",
                re.I,
            ),
        ),
    ),
    StageRule(
        stage_code="approval_issuance",
        body_patterns=(
            re.compile(
                r"\b("
                r"approved|approval|issued|issuance|granted|permit ready|"
                r"visa ready|kitas ready|kitap ready|pickup|collect|terbit|selesai"
                r")\b",
                re.I,
            ),
        ),
    ),
    StageRule(
        stage_code="extension_renewal_expiry",
        body_patterns=(
            re.compile(
                r"\b("
                r"extend|extension|renew|renewal|expiry|expire|expired|valid until|"
                r"overstay|perpanjang|habis|masa berlaku"
                r")\b",
                re.I,
            ),
        ),
    ),
    StageRule(
        stage_code="problem_escalation",
        body_patterns=(
            re.compile(
                r"\b("
                r"problem|issue|urgent|asap|reject(?:ed)?|mismatch|mistake|"
                r"blocked|complain|cancel|delay|late|error|failed|refused|denied"
                r")\b",
                re.I,
            ),
        ),
        signal_codes=frozenset({"urgency_risk"}),
        candidate_categories=frozenset({"urgency_case"}),
    ),
)


def _validate_input_path(path: Path, expected_name: str) -> None:
    if path.name != expected_name:
        raise ValueError(f"Refusing to read {path.name!r}; expected {expected_name!r}.")
    if not path.is_file():
        raise FileNotFoundError(f"Input DB not found: {path}")


def _normalize_text(value: object, fallback: str) -> str:
    text = "" if value is None else str(value).strip()
    return text or fallback


def _normalize_int(value: object) -> int:
    if value is None or value == "":
        return -1
    return int(value)


def _truthy(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y"}
    return bool(value)


def _extract_month(value: object) -> str:
    if value is None or value == "":
        return "unknown"
    if isinstance(value, int | float):
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds = seconds / 1000
        try:
            return datetime.fromtimestamp(seconds, tz=UTC).strftime("%Y-%m")
        except (OverflowError, OSError, ValueError):
            return "unknown"

    text = str(value).strip()
    match = MONTH_RE.match(text)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    return parsed.strftime("%Y-%m")


def _deny_private_column_reads(
    action: int,
    _arg1: str | None,
    arg2: str | None,
    _db_name: str | None,
    _trigger: str | None,
) -> int:
    denied_columns = {"sender_raw", "local_path", "raw_path", "body_hash", "value_hash"}
    if action == sqlite3.SQLITE_READ and (arg2 or "").lower() in denied_columns:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.set_authorizer(_deny_private_column_reads)
    return conn


def read_messages(db_path: Path) -> list[MessageRecord]:
    """Read allowlisted local messages needed for deterministic stage matching."""
    _validate_input_path(db_path, ALLOWED_MESSAGES_NAME)
    with _connect_readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT file_id, source_tag, message_index, timestamp, body_text, is_system_event
            FROM parsed_messages
            ORDER BY file_id, message_index
            """
        ).fetchall()

    return [
        MessageRecord(
            file_id=_normalize_text(row["file_id"], "unknown_file"),
            source_tag=_normalize_text(row["source_tag"], "unknown_source"),
            message_index=_normalize_int(row["message_index"]),
            timestamp=None if row["timestamp"] is None else str(row["timestamp"]),
            month=_extract_month(row["timestamp"]),
            body_text="" if row["body_text"] is None else str(row["body_text"]),
            is_system_event=_truthy(row["is_system_event"]),
        )
        for row in rows
    ]


def read_candidate_features(db_path: Path) -> list[FeatureRecord]:
    """Read candidate category/evidence codes without body/value hashes."""
    _validate_input_path(db_path, ALLOWED_CANDIDATES_NAME)
    with _connect_readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT file_id, source_tag, message_index, timestamp,
                   category_code, evidence_code
            FROM extracted_candidates
            ORDER BY file_id, message_index
            """
        ).fetchall()

    features: list[FeatureRecord] = []
    for row in rows:
        prefix_pairs = (
            ("candidate_category", row["category_code"]),
            ("candidate_evidence", row["evidence_code"]),
        )
        for prefix, value in prefix_pairs:
            normalized = _normalize_text(value, "")
            if not normalized:
                continue
            features.append(
                FeatureRecord(
                    file_id=_normalize_text(row["file_id"], "unknown_file"),
                    source_tag=_normalize_text(row["source_tag"], "unknown_source"),
                    message_index=_normalize_int(row["message_index"]),
                    timestamp=None
                    if row["timestamp"] is None
                    else str(row["timestamp"]),
                    code=f"{prefix}:{normalized}",
                )
            )
    return features


def read_signal_features(db_path: Path) -> list[FeatureRecord]:
    """Read signal codes without raw message text."""
    _validate_input_path(db_path, ALLOWED_SIGNAL_NAME)
    with _connect_readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT file_id, source_tag, message_index, timestamp, signal_code
            FROM signal_hits
            ORDER BY file_id, message_index
            """
        ).fetchall()

    return [
        FeatureRecord(
            file_id=_normalize_text(row["file_id"], "unknown_file"),
            source_tag=_normalize_text(row["source_tag"], "unknown_source"),
            message_index=_normalize_int(row["message_index"]),
            timestamp=None if row["timestamp"] is None else str(row["timestamp"]),
            code=f"signal:{_normalize_text(row['signal_code'], 'unknown_signal')}",
        )
        for row in rows
    ]


def _message_key(record: MessageRecord | FeatureRecord | StageHit) -> tuple[str, int]:
    return (record.file_id, record.message_index)


def _feature_maps(
    candidate_features: Sequence[FeatureRecord],
    signal_features: Sequence[FeatureRecord],
) -> tuple[dict[tuple[str, int], set[str]], dict[tuple[str, int], FeatureRecord]]:
    by_message: dict[tuple[str, int], set[str]] = defaultdict(set)
    first_feature: dict[tuple[str, int], FeatureRecord] = {}
    for feature in (*candidate_features, *signal_features):
        key = _message_key(feature)
        by_message[key].add(feature.code)
        first_feature.setdefault(key, feature)
    return by_message, first_feature


def _orphan_messages(
    message_keys: set[tuple[str, int]],
    first_features: dict[tuple[str, int], FeatureRecord],
) -> list[MessageRecord]:
    records: list[MessageRecord] = []
    for key, feature in sorted(first_features.items()):
        if key in message_keys:
            continue
        records.append(
            MessageRecord(
                file_id=feature.file_id,
                source_tag=feature.source_tag,
                message_index=feature.message_index,
                timestamp=feature.timestamp,
                month=_extract_month(feature.timestamp),
                body_text="",
                is_system_event=False,
            )
        )
    return records


def _stage_evidence(
    rule: StageRule, body_text: str, feature_codes: set[str]
) -> dict[str, int]:
    evidence: dict[str, int] = {}
    if any(pattern.search(body_text) for pattern in rule.body_patterns):
        evidence[f"body_keyword:{rule.stage_code}"] = 3

    for signal_code in sorted(rule.signal_codes):
        feature = f"signal:{signal_code}"
        if feature in feature_codes:
            evidence[feature] = 2

    for category_code in sorted(rule.candidate_categories):
        feature = f"candidate_category:{category_code}"
        if feature in feature_codes:
            evidence[feature] = 2

    for evidence_code in sorted(rule.candidate_evidence_codes):
        feature = f"candidate_evidence:{evidence_code}"
        if feature in feature_codes:
            evidence[feature] = 1

    return evidence


def classify_message(record: MessageRecord, feature_codes: set[str]) -> list[StageHit]:
    """Classify one message into zero or more aggregate lifecycle stage hits."""
    if record.is_system_event:
        return []

    hits: list[StageHit] = []
    for rule in STAGE_RULES:
        evidence = _stage_evidence(rule, record.body_text, feature_codes)
        for evidence_code, score in sorted(evidence.items()):
            hits.append(
                StageHit(
                    file_id=record.file_id,
                    source_tag=record.source_tag,
                    message_index=record.message_index,
                    timestamp=record.timestamp,
                    month=record.month,
                    stage_code=rule.stage_code,
                    stage_label=STAGE_LABELS[rule.stage_code],
                    evidence_code=evidence_code,
                    score=score,
                )
            )
    return hits


def _primary_stage(hits: Sequence[StageHit]) -> tuple[str, str, int, int]:
    by_stage: dict[str, list[StageHit]] = defaultdict(list)
    for hit in hits:
        by_stage[hit.stage_code].append(hit)

    ranked: list[tuple[int, int, int, str]] = []
    for stage_code, stage_hits in by_stage.items():
        total_score = sum(hit.score for hit in stage_hits)
        ranked.append(
            (
                total_score,
                PRIMARY_STAGE_PRIORITY[stage_code],
                -STAGE_ORDER.index(stage_code),
                stage_code,
            )
        )
    total_score, _priority, _order, stage_code = max(ranked)
    return stage_code, STAGE_LABELS[stage_code], len(by_stage), total_score


def _build_message_summaries(
    stage_hits: Sequence[StageHit],
) -> list[MessageStageSummary]:
    hits_by_message: dict[tuple[str, int], list[StageHit]] = defaultdict(list)
    for hit in stage_hits:
        hits_by_message[_message_key(hit)].append(hit)

    summaries: list[MessageStageSummary] = []
    for key in sorted(hits_by_message):
        hits = hits_by_message[key]
        first = hits[0]
        stage_code, stage_label, stage_count, total_score = _primary_stage(hits)
        summaries.append(
            MessageStageSummary(
                file_id=first.file_id,
                source_tag=first.source_tag,
                message_index=first.message_index,
                timestamp=first.timestamp,
                month=first.month,
                primary_stage_code=stage_code,
                primary_stage_label=stage_label,
                stage_count=stage_count,
                evidence_count=len(hits),
                total_score=total_score,
            )
        )
    return summaries


def _sort_rows(
    rows: Iterable[dict[str, object]], count_key: str
) -> list[dict[str, object]]:
    return sorted(
        rows,
        key=lambda row: (
            -int(row[count_key]),
            str(row.get("stage_code", row.get("from_stage_code", ""))),
            str(row.get("month", row.get("source_tag", row.get("to_stage_code", "")))),
        ),
    )


def _stage_totals(stage_hits: Sequence[StageHit]) -> list[dict[str, object]]:
    hit_counts: Counter[str] = Counter(hit.stage_code for hit in stage_hits)
    messages: dict[str, set[tuple[str, int]]] = defaultdict(set)
    files: dict[str, set[str]] = defaultdict(set)
    for hit in stage_hits:
        messages[hit.stage_code].add(_message_key(hit))
        files[hit.stage_code].add(hit.file_id)

    return _sort_rows(
        (
            {
                "stage_code": stage_code,
                "stage_label": STAGE_LABELS[stage_code],
                "hit_count": hit_counts[stage_code],
                "message_count": len(messages[stage_code]),
                "file_count": len(files[stage_code]),
            }
            for stage_code in STAGE_ORDER
            if hit_counts[stage_code]
        ),
        "message_count",
    )


def _stage_dimension_matrix(
    stage_hits: Sequence[StageHit],
    *,
    dimension: str,
) -> list[dict[str, object]]:
    hit_counts: Counter[tuple[str, str]] = Counter()
    messages: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(set)
    files: dict[tuple[str, str], set[str]] = defaultdict(set)
    for hit in stage_hits:
        dimension_value = getattr(hit, dimension)
        key = (hit.stage_code, str(dimension_value))
        hit_counts[key] += 1
        messages[key].add(_message_key(hit))
        files[key].add(hit.file_id)

    return _sort_rows(
        (
            {
                "stage_code": stage_code,
                "stage_label": STAGE_LABELS[stage_code],
                dimension: value,
                "hit_count": hit_count,
                "message_count": len(messages[(stage_code, value)]),
                "file_count": len(files[(stage_code, value)]),
            }
            for (stage_code, value), hit_count in hit_counts.items()
        ),
        "message_count",
    )


def _stage_cooccurrence(stage_hits: Sequence[StageHit]) -> list[dict[str, object]]:
    stages_by_message: dict[tuple[str, int], set[str]] = defaultdict(set)
    files_by_message: dict[tuple[str, int], str] = {}
    for hit in stage_hits:
        key = _message_key(hit)
        stages_by_message[key].add(hit.stage_code)
        files_by_message[key] = hit.file_id

    pair_counts: Counter[tuple[str, str]] = Counter()
    pair_files: dict[tuple[str, str], set[str]] = defaultdict(set)
    for key, stages in stages_by_message.items():
        for left, right in combinations(sorted(stages), 2):
            pair_counts[(left, right)] += 1
            pair_files[(left, right)].add(files_by_message[key])

    return _sort_rows(
        (
            {
                "stage_code": left,
                "stage_label": STAGE_LABELS[left],
                "paired_stage_code": right,
                "paired_stage_label": STAGE_LABELS[right],
                "message_count": count,
                "file_count": len(pair_files[(left, right)]),
            }
            for (left, right), count in pair_counts.items()
        ),
        "message_count",
    )


def _stage_transitions(
    summaries: Sequence[MessageStageSummary],
) -> list[dict[str, object]]:
    by_file: dict[str, list[MessageStageSummary]] = defaultdict(list)
    for summary in summaries:
        by_file[summary.file_id].append(summary)

    transition_counts: Counter[tuple[str, str]] = Counter()
    transition_files: dict[tuple[str, str], set[str]] = defaultdict(set)
    for file_id, file_summaries in by_file.items():
        ordered = sorted(
            file_summaries,
            key=lambda row: (
                row.timestamp or "",
                row.message_index,
                row.primary_stage_code,
            ),
        )
        for previous, current in zip(ordered, ordered[1:]):
            key = (previous.primary_stage_code, current.primary_stage_code)
            transition_counts[key] += 1
            transition_files[key].add(file_id)

    return _sort_rows(
        (
            {
                "from_stage_code": left,
                "from_stage_label": STAGE_LABELS[left],
                "to_stage_code": right,
                "to_stage_label": STAGE_LABELS[right],
                "transition_count": count,
                "file_count": len(transition_files[(left, right)]),
            }
            for (left, right), count in transition_counts.items()
        ),
        "transition_count",
    )


def _evidence_totals(stage_hits: Sequence[StageHit]) -> list[dict[str, object]]:
    counts: Counter[tuple[str, str]] = Counter()
    messages: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(set)
    for hit in stage_hits:
        key = (hit.stage_code, hit.evidence_code)
        counts[key] += 1
        messages[key].add(_message_key(hit))

    return _sort_rows(
        (
            {
                "stage_code": stage_code,
                "stage_label": STAGE_LABELS[stage_code],
                "evidence_code": evidence_code,
                "hit_count": count,
                "message_count": len(messages[(stage_code, evidence_code)]),
            }
            for (stage_code, evidence_code), count in counts.items()
        ),
        "message_count",
    )


def build_artifacts(
    messages: Sequence[MessageRecord],
    candidate_features: Sequence[FeatureRecord],
    signal_features: Sequence[FeatureRecord],
) -> LifecycleArtifacts:
    feature_codes, first_features = _feature_maps(candidate_features, signal_features)
    message_keys = {_message_key(message) for message in messages}
    orphan_messages = _orphan_messages(message_keys, first_features)
    all_messages = [*messages, *orphan_messages]

    stage_hits: list[StageHit] = []
    for message in all_messages:
        stage_hits.extend(
            classify_message(message, feature_codes.get(_message_key(message), set()))
        )

    message_stage_summaries = _build_message_summaries(stage_hits)
    return LifecycleArtifacts(
        input_message_count=len(messages),
        classified_message_count=len(message_stage_summaries),
        skipped_system_event_count=sum(
            1 for message in messages if message.is_system_event
        ),
        orphan_feature_message_count=len(orphan_messages),
        stage_hits=stage_hits,
        message_stage_summaries=message_stage_summaries,
        stage_totals=_stage_totals(stage_hits),
        stage_month_matrix=_stage_dimension_matrix(stage_hits, dimension="month"),
        stage_source_matrix=_stage_dimension_matrix(stage_hits, dimension="source_tag"),
        stage_cooccurrence=_stage_cooccurrence(stage_hits),
        stage_transitions=_stage_transitions(message_stage_summaries),
        evidence_totals=_evidence_totals(stage_hits),
    )


def _create_output_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE analysis_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE stage_hits (
            file_id TEXT NOT NULL,
            source_tag TEXT NOT NULL,
            message_index INTEGER NOT NULL,
            timestamp TEXT,
            month TEXT NOT NULL,
            stage_code TEXT NOT NULL,
            stage_label TEXT NOT NULL,
            evidence_code TEXT NOT NULL,
            score INTEGER NOT NULL,
            PRIMARY KEY (file_id, message_index, stage_code, evidence_code)
        );
        CREATE TABLE message_stage_summary (
            file_id TEXT NOT NULL,
            source_tag TEXT NOT NULL,
            message_index INTEGER NOT NULL,
            timestamp TEXT,
            month TEXT NOT NULL,
            primary_stage_code TEXT NOT NULL,
            primary_stage_label TEXT NOT NULL,
            stage_count INTEGER NOT NULL,
            evidence_count INTEGER NOT NULL,
            total_score INTEGER NOT NULL,
            PRIMARY KEY (file_id, message_index)
        );
        CREATE TABLE stage_totals (
            stage_code TEXT PRIMARY KEY,
            stage_label TEXT NOT NULL,
            hit_count INTEGER NOT NULL,
            message_count INTEGER NOT NULL,
            file_count INTEGER NOT NULL
        );
        CREATE TABLE stage_month_matrix (
            stage_code TEXT NOT NULL,
            stage_label TEXT NOT NULL,
            month TEXT NOT NULL,
            hit_count INTEGER NOT NULL,
            message_count INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            PRIMARY KEY (stage_code, month)
        );
        CREATE TABLE stage_source_matrix (
            stage_code TEXT NOT NULL,
            stage_label TEXT NOT NULL,
            source_tag TEXT NOT NULL,
            hit_count INTEGER NOT NULL,
            message_count INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            PRIMARY KEY (stage_code, source_tag)
        );
        CREATE TABLE stage_cooccurrence (
            stage_code TEXT NOT NULL,
            stage_label TEXT NOT NULL,
            paired_stage_code TEXT NOT NULL,
            paired_stage_label TEXT NOT NULL,
            message_count INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            PRIMARY KEY (stage_code, paired_stage_code)
        );
        CREATE TABLE primary_stage_transitions (
            from_stage_code TEXT NOT NULL,
            from_stage_label TEXT NOT NULL,
            to_stage_code TEXT NOT NULL,
            to_stage_label TEXT NOT NULL,
            transition_count INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            PRIMARY KEY (from_stage_code, to_stage_code)
        );
        CREATE TABLE evidence_totals (
            stage_code TEXT NOT NULL,
            stage_label TEXT NOT NULL,
            evidence_code TEXT NOT NULL,
            hit_count INTEGER NOT NULL,
            message_count INTEGER NOT NULL,
            PRIMARY KEY (stage_code, evidence_code)
        );
        CREATE INDEX idx_stage_hits_stage ON stage_hits(stage_code);
        CREATE INDEX idx_stage_hits_month ON stage_hits(month);
        CREATE INDEX idx_stage_hits_message ON stage_hits(file_id, message_index);
        """
    )


def _insert_dicts(
    conn: sqlite3.Connection, table: str, rows: Sequence[dict[str, object]]
) -> None:
    if not rows:
        return
    columns = tuple(rows[0].keys())
    column_sql = ", ".join(columns)
    placeholder_sql = ", ".join(f":{column}" for column in columns)
    conn.executemany(
        f"INSERT INTO {table} ({column_sql}) VALUES ({placeholder_sql})",
        rows,
    )


def write_lifecycle_db(
    output_db: Path,
    artifacts: LifecycleArtifacts,
    *,
    generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    tmp_db = output_db.with_name(f"{output_db.name}.tmp")
    if tmp_db.exists():
        tmp_db.unlink()

    conn = sqlite3.connect(tmp_db)
    try:
        _create_output_schema(conn)
        conn.executemany(
            "INSERT INTO analysis_metadata (key, value) VALUES (?, ?)",
            [
                ("generated_at_utc", generated_at_utc),
                ("messages_input_name", ALLOWED_MESSAGES_NAME),
                ("candidates_input_name", ALLOWED_CANDIDATES_NAME),
                ("signal_input_name", ALLOWED_SIGNAL_NAME),
                ("input_message_count", str(artifacts.input_message_count)),
                ("classified_message_count", str(artifacts.classified_message_count)),
                ("stage_hit_count", str(len(artifacts.stage_hits))),
                ("privacy_mode", "local_only_no_raw_text_no_values_in_outputs"),
            ],
        )
        _insert_dicts(
            conn,
            "stage_hits",
            [
                {
                    "file_id": hit.file_id,
                    "source_tag": hit.source_tag,
                    "message_index": hit.message_index,
                    "timestamp": hit.timestamp,
                    "month": hit.month,
                    "stage_code": hit.stage_code,
                    "stage_label": hit.stage_label,
                    "evidence_code": hit.evidence_code,
                    "score": hit.score,
                }
                for hit in artifacts.stage_hits
            ],
        )
        _insert_dicts(
            conn,
            "message_stage_summary",
            [
                {
                    "file_id": row.file_id,
                    "source_tag": row.source_tag,
                    "message_index": row.message_index,
                    "timestamp": row.timestamp,
                    "month": row.month,
                    "primary_stage_code": row.primary_stage_code,
                    "primary_stage_label": row.primary_stage_label,
                    "stage_count": row.stage_count,
                    "evidence_count": row.evidence_count,
                    "total_score": row.total_score,
                }
                for row in artifacts.message_stage_summaries
            ],
        )
        _insert_dicts(conn, "stage_totals", artifacts.stage_totals)
        _insert_dicts(conn, "stage_month_matrix", artifacts.stage_month_matrix)
        _insert_dicts(conn, "stage_source_matrix", artifacts.stage_source_matrix)
        _insert_dicts(conn, "stage_cooccurrence", artifacts.stage_cooccurrence)
        _insert_dicts(conn, "primary_stage_transitions", artifacts.stage_transitions)
        _insert_dicts(conn, "evidence_totals", artifacts.evidence_totals)
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
    artifacts: LifecycleArtifacts,
    *,
    output_name: str,
    generated_at_utc: str,
    limit: int,
) -> str:
    overview_rows = [
        {"metric": "Messages read", "value": artifacts.input_message_count},
        {
            "metric": "Messages with lifecycle stage",
            "value": artifacts.classified_message_count,
        },
        {"metric": "Stage evidence hits", "value": len(artifacts.stage_hits)},
        {
            "metric": "Skipped system events",
            "value": artifacts.skipped_system_event_count,
        },
        {
            "metric": "Feature-only orphan messages",
            "value": artifacts.orphan_feature_message_count,
        },
    ]
    return "\n".join(
        [
            "# Allowed Immigration Lifecycle Summary",
            "",
            f"- Generated UTC: `{generated_at_utc}`",
            f"- Input DBs: `{ALLOWED_MESSAGES_NAME}`, `{ALLOWED_CANDIDATES_NAME}`, "
            f"`{ALLOWED_SIGNAL_NAME}`",
            f"- Local lifecycle SQLite artifact: `{output_name}`",
            "- Privacy boundary: tracked markdown is aggregate-only and contains no raw "
            "message text, snippets, extracted values, phone numbers, emails, raw "
            "contact names, or raw source paths.",
            "- Classification is deterministic local regex plus local signal/candidate "
            "codes; it is not legal advice and not an LLM interpretation.",
            "",
            "## Overview",
            "",
            _markdown_table(
                ["Metric", "Value"],
                overview_rows,
                keys=["metric", "value"],
                limit=limit,
            ),
            "## Stage Totals",
            "",
            _markdown_table(
                [
                    "stage_code",
                    "stage_label",
                    "hit_count",
                    "message_count",
                    "file_count",
                ],
                artifacts.stage_totals,
                keys=[
                    "stage_code",
                    "stage_label",
                    "hit_count",
                    "message_count",
                    "file_count",
                ],
                limit=limit,
            ),
            "## Stage x Month",
            "",
            _markdown_table(
                [
                    "stage_code",
                    "stage_label",
                    "month",
                    "hit_count",
                    "message_count",
                    "file_count",
                ],
                artifacts.stage_month_matrix,
                keys=[
                    "stage_code",
                    "stage_label",
                    "month",
                    "hit_count",
                    "message_count",
                    "file_count",
                ],
                limit=limit,
            ),
            "## Stage x Source Tag",
            "",
            _markdown_table(
                [
                    "stage_code",
                    "stage_label",
                    "source_tag",
                    "hit_count",
                    "message_count",
                    "file_count",
                ],
                artifacts.stage_source_matrix,
                keys=[
                    "stage_code",
                    "stage_label",
                    "source_tag",
                    "hit_count",
                    "message_count",
                    "file_count",
                ],
                limit=limit,
            ),
            "## Stage Co-Occurrence",
            "",
            _markdown_table(
                [
                    "stage_code",
                    "stage_label",
                    "paired_stage_code",
                    "paired_stage_label",
                    "message_count",
                    "file_count",
                ],
                artifacts.stage_cooccurrence,
                keys=[
                    "stage_code",
                    "stage_label",
                    "paired_stage_code",
                    "paired_stage_label",
                    "message_count",
                    "file_count",
                ],
                limit=limit,
            ),
            "## Primary Stage Transitions",
            "",
            _markdown_table(
                [
                    "from_stage_code",
                    "from_stage_label",
                    "to_stage_code",
                    "to_stage_label",
                    "transition_count",
                    "file_count",
                ],
                artifacts.stage_transitions,
                keys=[
                    "from_stage_code",
                    "from_stage_label",
                    "to_stage_code",
                    "to_stage_label",
                    "transition_count",
                    "file_count",
                ],
                limit=limit,
            ),
            "## Evidence Code Totals",
            "",
            _markdown_table(
                [
                    "stage_code",
                    "stage_label",
                    "evidence_code",
                    "hit_count",
                    "message_count",
                ],
                artifacts.evidence_totals,
                keys=[
                    "stage_code",
                    "stage_label",
                    "evidence_code",
                    "hit_count",
                    "message_count",
                ],
                limit=limit,
            ),
            "## Caveats",
            "",
            "- One message can map to multiple lifecycle stages.",
            "- System-event messages are excluded from lifecycle classification.",
            "- `application_submission` intentionally includes broad immigration/visa "
            "signals, so it is a high-recall stage rather than a final case status.",
            "",
        ]
    )


def write_summary_markdown(summary_path: Path, content: str) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(content, encoding="utf-8")


def run_analysis(
    *,
    messages_db: Path,
    candidates_db: Path,
    signal_db: Path,
    output_db: Path,
    summary_path: Path,
    summary_limit: int,
    generated_at_utc: str | None = None,
) -> LifecycleArtifacts:
    if output_db.resolve() in {
        messages_db.resolve(),
        candidates_db.resolve(),
        signal_db.resolve(),
    }:
        raise ValueError("Output DB path must be different from all input DB paths.")
    if summary_limit < 1:
        raise ValueError("summary_limit must be >= 1")

    generated_at = (
        generated_at_utc or datetime.now(tz=UTC).replace(microsecond=0).isoformat()
    )
    messages = read_messages(messages_db)
    candidate_features = read_candidate_features(candidates_db)
    signal_features = read_signal_features(signal_db)
    artifacts = build_artifacts(messages, candidate_features, signal_features)
    write_lifecycle_db(output_db, artifacts, generated_at_utc=generated_at)
    write_summary_markdown(
        summary_path,
        render_summary_markdown(
            artifacts,
            output_name=output_db.name,
            generated_at_utc=generated_at,
            limit=summary_limit,
        ),
    )
    return artifacts


def parse_args(argv: Sequence[str] | None = None) -> CliConfig:
    parser = argparse.ArgumentParser(
        description="Build aggregate immigration lifecycle stages from local WhatsApp DBs."
    )
    parser.add_argument("--messages-db", type=Path, default=DEFAULT_MESSAGES_DB)
    parser.add_argument("--candidates-db", type=Path, default=DEFAULT_CANDIDATES_DB)
    parser.add_argument("--signal-db", type=Path, default=DEFAULT_SIGNAL_DB)
    parser.add_argument("--output-db", type=Path, default=DEFAULT_OUTPUT_DB)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--summary-limit", type=int, default=25)
    parser.add_argument(
        "--generated-at-utc",
        default=None,
        help="Override generated timestamp for deterministic tests.",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable run stats."
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress success output.")
    args = parser.parse_args(argv)
    return CliConfig(
        messages_db=args.messages_db,
        candidates_db=args.candidates_db,
        signal_db=args.signal_db,
        output_db=args.output_db,
        summary=args.summary,
        summary_limit=args.summary_limit,
        generated_at_utc=args.generated_at_utc,
        emit_json=args.json,
        quiet=args.quiet,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        artifacts = run_analysis(
            messages_db=args.messages_db,
            candidates_db=args.candidates_db,
            signal_db=args.signal_db,
            output_db=args.output_db,
            summary_path=args.summary,
            summary_limit=args.summary_limit,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, OSError, sqlite3.Error, ValueError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    stats = {
        "classified_message_count": artifacts.classified_message_count,
        "input_message_count": artifacts.input_message_count,
        "output_db": str(args.output_db),
        "stage_hit_count": len(artifacts.stage_hits),
        "summary": str(args.summary),
    }
    if args.emit_json:
        sys.stdout.write(json.dumps(stats, sort_keys=True) + "\n")
    elif not args.quiet:
        sys.stdout.write(f"Wrote {args.output_db} and {args.summary}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
