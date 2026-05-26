from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

LOGGER = logging.getLogger(__name__)

DEFAULT_REGISTRY_DB = Path("research/personal/wa-corpus/registry/registry.sqlite")
DEFAULT_OUTPUT_DIR = Path("research/personal/wa-corpus/classification")


@dataclass(frozen=True)
class RegistryEntry:
    file_id: str
    source: str
    source_tag: str | None
    path_hash: str
    message_start_count: int
    normalized_message_start_count: int
    min_timestamp: str | None
    max_timestamp: str | None
    warning_codes: tuple[str, ...]


@dataclass(frozen=True)
class SourceTagProfile:
    source_tag: str
    files: int
    message_starts: int
    normalized_message_starts: int


@dataclass(frozen=True)
class ClassifiedChat:
    file_id: str
    source: str
    source_tag: str | None
    path_hash: str
    message_start_count: int
    normalized_message_start_count: int
    min_timestamp: str | None
    max_timestamp: str | None
    classification_label: str
    privacy_tier: str
    processing_gate: str
    confidence: float
    review_required: bool
    evidence_codes: tuple[str, ...]
    warning_codes: tuple[str, ...]


@dataclass(frozen=True)
class LabelSummary:
    classification_label: str
    files: int
    message_starts: int
    normalized_message_starts: int
    review_required_files: int


@dataclass(frozen=True)
class GateSummary:
    processing_gate: str
    files: int
    message_starts: int
    normalized_message_starts: int


def decode_json_list(value: str | None) -> tuple[str, ...]:
    """Decode a JSON string list from the registry."""
    if not value:
        return ()
    loaded = json.loads(value)
    if not isinstance(loaded, list):
        raise ValueError("expected JSON list")
    return tuple(str(item) for item in loaded)


def read_registry_entries(registry_db: Path) -> list[RegistryEntry]:
    """Read metadata-only registry rows from SQLite."""
    if not registry_db.exists():
        raise FileNotFoundError(f"Registry DB does not exist: {registry_db}")

    with sqlite3.connect(registry_db) as conn:
        rows = conn.execute(
            """
            SELECT file_id, source, source_tag, path_hash, message_start_count,
                   normalized_message_start_count, min_timestamp, max_timestamp,
                   warning_codes_json
            FROM corpus_files
            ORDER BY file_id
            """
        ).fetchall()

    return [
        RegistryEntry(
            file_id=row[0],
            source=row[1],
            source_tag=row[2],
            path_hash=row[3],
            message_start_count=int(row[4]),
            normalized_message_start_count=int(row[5]),
            min_timestamp=row[6],
            max_timestamp=row[7],
            warning_codes=decode_json_list(row[8]),
        )
        for row in rows
    ]


def build_source_tag_profiles(entries: Iterable[RegistryEntry]) -> dict[str, SourceTagProfile]:
    """Aggregate ZIP source tags without revealing raw folder names."""
    grouped: dict[str, list[RegistryEntry]] = defaultdict(list)
    for entry in entries:
        if entry.source == "02_zip-extracted" and entry.source_tag:
            grouped[entry.source_tag].append(entry)

    return {
        source_tag: SourceTagProfile(
            source_tag=source_tag,
            files=len(rows),
            message_starts=sum(row.message_start_count for row in rows),
            normalized_message_starts=sum(row.normalized_message_start_count for row in rows),
        )
        for source_tag, rows in grouped.items()
    }


def largest_zip_tag(profiles: dict[str, SourceTagProfile]) -> str | None:
    """Return the source tag with the largest file count."""
    if not profiles:
        return None
    return max(
        profiles.values(),
        key=lambda profile: (profile.files, profile.message_starts, profile.source_tag),
    ).source_tag


def classify_entry(
    entry: RegistryEntry,
    profiles: dict[str, SourceTagProfile],
    largest_tag: str | None,
) -> ClassifiedChat:
    """Assign a privacy-first classification using registry metadata only."""
    evidence_codes: list[str] = []
    review_required = True
    confidence = 0.5

    if entry.warning_codes:
        evidence_codes.append("parser_warnings_present")
    if entry.normalized_message_start_count > entry.message_start_count:
        evidence_codes.append("normalized_count_exceeds_baseline")
    if entry.message_start_count == 0:
        evidence_codes.append("zero_message_starts")
        return ClassifiedChat(
            file_id=entry.file_id,
            source=entry.source,
            source_tag=entry.source_tag,
            path_hash=entry.path_hash,
            message_start_count=entry.message_start_count,
            normalized_message_start_count=entry.normalized_message_start_count,
            min_timestamp=entry.min_timestamp,
            max_timestamp=entry.max_timestamp,
            classification_label="empty_or_unparsed_chat",
            privacy_tier="unknown_sensitive",
            processing_gate="manual_review_before_any_use",
            confidence=0.95,
            review_required=True,
            evidence_codes=tuple(evidence_codes),
            warning_codes=entry.warning_codes,
        )

    if entry.source == "01_wa-mirror-db":
        evidence_codes.append("source:wa_mirror_db")
        classification_label = "mirror_contact_archive_unreviewed"
        privacy_tier = "mixed_sensitive"
        processing_gate = "manual_review_before_content_mining"
        confidence = 0.62
    elif entry.source == "03_drive-icloud":
        evidence_codes.append("source:drive_icloud")
        classification_label = "private_drive_icloud_candidate"
        privacy_tier = "personal_sensitive"
        processing_gate = "deny_content_mining_until_owner_allowlist"
        confidence = 0.86
    elif entry.source == "02_zip-extracted" and entry.source_tag:
        profile = profiles[entry.source_tag]
        evidence_codes.extend(["source:zip_extracted", "source_tag:hashed"])
        if entry.source_tag == largest_tag and profile.files > 1:
            evidence_codes.append("zip_tag:largest_by_file_count")
            classification_label = "bulk_drive_export_candidate"
            privacy_tier = "mixed_sensitive"
            processing_gate = "manual_review_before_content_mining"
            confidence = 0.72
        elif profile.files == 1 and profile.message_starts <= 100:
            evidence_codes.append("zip_tag:singleton_low_volume")
            classification_label = "pilot_or_test_archive_candidate"
            privacy_tier = "unknown_sensitive"
            processing_gate = "manual_review_before_any_use"
            confidence = 0.69
        else:
            evidence_codes.append("zip_tag:operator_sized_archive")
            classification_label = "team_operator_archive_candidate"
            privacy_tier = "team_sensitive"
            processing_gate = "local_only_team_analysis_after_owner_approval"
            confidence = 0.78
    else:
        evidence_codes.append("source:unknown")
        classification_label = "unknown_archive_candidate"
        privacy_tier = "unknown_sensitive"
        processing_gate = "manual_review_before_any_use"
        confidence = 0.55

    return ClassifiedChat(
        file_id=entry.file_id,
        source=entry.source,
        source_tag=entry.source_tag,
        path_hash=entry.path_hash,
        message_start_count=entry.message_start_count,
        normalized_message_start_count=entry.normalized_message_start_count,
        min_timestamp=entry.min_timestamp,
        max_timestamp=entry.max_timestamp,
        classification_label=classification_label,
        privacy_tier=privacy_tier,
        processing_gate=processing_gate,
        confidence=confidence,
        review_required=review_required,
        evidence_codes=tuple(dict.fromkeys(evidence_codes)),
        warning_codes=entry.warning_codes,
    )


def classify_entries(entries: Iterable[RegistryEntry]) -> list[ClassifiedChat]:
    """Classify all registry rows into privacy-first processing gates."""
    entry_list = list(entries)
    profiles = build_source_tag_profiles(entry_list)
    largest_tag = largest_zip_tag(profiles)
    return [classify_entry(entry, profiles, largest_tag) for entry in entry_list]


def summarize_labels(classified: Iterable[ClassifiedChat]) -> list[LabelSummary]:
    """Aggregate classified rows by label."""
    grouped: dict[str, list[ClassifiedChat]] = defaultdict(list)
    for row in classified:
        grouped[row.classification_label].append(row)

    return [
        LabelSummary(
            classification_label=label,
            files=len(rows),
            message_starts=sum(row.message_start_count for row in rows),
            normalized_message_starts=sum(row.normalized_message_start_count for row in rows),
            review_required_files=sum(1 for row in rows if row.review_required),
        )
        for label, rows in sorted(grouped.items())
    ]


def summarize_gates(classified: Iterable[ClassifiedChat]) -> list[GateSummary]:
    """Aggregate classified rows by processing gate."""
    grouped: dict[str, list[ClassifiedChat]] = defaultdict(list)
    for row in classified:
        grouped[row.processing_gate].append(row)

    return [
        GateSummary(
            processing_gate=gate,
            files=len(rows),
            message_starts=sum(row.message_start_count for row in rows),
            normalized_message_starts=sum(row.normalized_message_start_count for row in rows),
        )
        for gate, rows in sorted(grouped.items())
    ]


def count_by_source_and_label(classified: Iterable[ClassifiedChat]) -> Counter[tuple[str, str]]:
    """Count rows by source and classification label."""
    counts: Counter[tuple[str, str]] = Counter()
    for row in classified:
        counts[(row.source, row.classification_label)] += 1
    return counts


def write_sqlite(
    *,
    db_path: Path,
    registry_db: Path,
    classified: list[ClassifiedChat],
) -> None:
    """Write privacy-safe classification output to SQLite."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    label_summaries = summarize_labels(classified)
    gate_summaries = summarize_gates(classified)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE classification_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at TEXT NOT NULL,
                registry_db TEXT NOT NULL,
                privacy_mode TEXT NOT NULL
            );

            CREATE TABLE classified_chats (
                file_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_tag TEXT,
                path_hash TEXT NOT NULL,
                message_start_count INTEGER NOT NULL,
                normalized_message_start_count INTEGER NOT NULL,
                min_timestamp TEXT,
                max_timestamp TEXT,
                classification_label TEXT NOT NULL,
                privacy_tier TEXT NOT NULL,
                processing_gate TEXT NOT NULL,
                confidence REAL NOT NULL,
                review_required INTEGER NOT NULL,
                evidence_codes_json TEXT NOT NULL,
                warning_codes_json TEXT NOT NULL
            );

            CREATE TABLE classification_summaries (
                classification_label TEXT PRIMARY KEY,
                files INTEGER NOT NULL,
                message_starts INTEGER NOT NULL,
                normalized_message_starts INTEGER NOT NULL,
                review_required_files INTEGER NOT NULL
            );

            CREATE TABLE gate_summaries (
                processing_gate TEXT PRIMARY KEY,
                files INTEGER NOT NULL,
                message_starts INTEGER NOT NULL,
                normalized_message_starts INTEGER NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO classification_runs (id, generated_at, registry_db, privacy_mode)
            VALUES (1, ?, ?, ?)
            """,
            (
                generated_at,
                registry_db.as_posix(),
                "metadata_only_no_raw_text_no_raw_paths_no_raw_contact_names",
            ),
        )
        conn.executemany(
            """
            INSERT INTO classified_chats (
                file_id, source, source_tag, path_hash, message_start_count,
                normalized_message_start_count, min_timestamp, max_timestamp,
                classification_label, privacy_tier, processing_gate, confidence,
                review_required, evidence_codes_json, warning_codes_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.file_id,
                    row.source,
                    row.source_tag,
                    row.path_hash,
                    row.message_start_count,
                    row.normalized_message_start_count,
                    row.min_timestamp,
                    row.max_timestamp,
                    row.classification_label,
                    row.privacy_tier,
                    row.processing_gate,
                    row.confidence,
                    1 if row.review_required else 0,
                    json.dumps(row.evidence_codes),
                    json.dumps(row.warning_codes),
                )
                for row in classified
            ],
        )
        conn.executemany(
            """
            INSERT INTO classification_summaries (
                classification_label, files, message_starts,
                normalized_message_starts, review_required_files
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    summary.classification_label,
                    summary.files,
                    summary.message_starts,
                    summary.normalized_message_starts,
                    summary.review_required_files,
                )
                for summary in label_summaries
            ],
        )
        conn.executemany(
            """
            INSERT INTO gate_summaries (
                processing_gate, files, message_starts, normalized_message_starts
            )
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    summary.processing_gate,
                    summary.files,
                    summary.message_starts,
                    summary.normalized_message_starts,
                )
                for summary in gate_summaries
            ],
        )
        conn.commit()


def top_review_rows(classified: Iterable[ClassifiedChat], limit: int) -> list[ClassifiedChat]:
    """Return highest-volume rows that still need manual review."""
    return sorted(
        (row for row in classified if row.review_required),
        key=lambda row: (row.message_start_count, row.normalized_message_start_count, row.file_id),
        reverse=True,
    )[:limit]


def write_summary(
    *,
    summary_path: Path,
    registry_db: Path,
    classification_db: Path,
    classified: list[ClassifiedChat],
    review_limit: int,
) -> None:
    """Write a privacy-preserving Markdown classification summary."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    label_summaries = summarize_labels(classified)
    gate_summaries = summarize_gates(classified)
    source_label_counts = count_by_source_and_label(classified)
    total_files = len(classified)
    total_starts = sum(row.message_start_count for row in classified)
    total_normalized = sum(row.normalized_message_start_count for row in classified)

    lines: list[str] = [
        "# WhatsApp Chat Classification Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Input registry: `{registry_db.as_posix()}`",
        f"SQLite classification DB: `{classification_db.as_posix()}`",
        "",
        "## Privacy Mode",
        "",
        "- Metadata only.",
        "- No raw message text.",
        "- No message snippets.",
        "- No phone numbers.",
        "- No raw source paths.",
        "- No raw contact names.",
        "- Per-chat references use `file_id`, `path_hash`, and hashed `source_tag` only.",
        "",
        "## Scope",
        "",
        "- This is a deterministic pre-flight taxonomy, not semantic content analysis.",
        "- Every chat remains review-gated before any content mining.",
        "- The output is intended to prevent personal, family, client, and team chats from being mixed accidentally.",
        "",
        "## Global Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Classified chat files | {total_files} |",
        f"| Baseline message-start records | {total_starts} |",
        f"| Normalized message-start records | {total_normalized} |",
        "",
        "## Classification Labels",
        "",
        "| Label | Files | Baseline starts | Normalized starts | Review-required files |",
        "|---|---:|---:|---:|---:|",
    ]
    for summary in label_summaries:
        lines.append(
            "| {label} | {files} | {starts} | {normalized} | {review} |".format(
                label=summary.classification_label,
                files=summary.files,
                starts=summary.message_starts,
                normalized=summary.normalized_message_starts,
                review=summary.review_required_files,
            )
        )

    lines.extend(
        [
            "",
            "## Processing Gates",
            "",
            "| Gate | Files | Baseline starts | Normalized starts |",
            "|---|---:|---:|---:|",
        ]
    )
    for summary in gate_summaries:
        lines.append(
            "| {gate} | {files} | {starts} | {normalized} |".format(
                gate=summary.processing_gate,
                files=summary.files,
                starts=summary.message_starts,
                normalized=summary.normalized_message_starts,
            )
        )

    lines.extend(
        [
            "",
            "## Source Cross-Tab",
            "",
            "| Source | Label | Files |",
            "|---|---|---:|",
        ]
    )
    for (source, label), count in sorted(source_label_counts.items()):
        lines.append(f"| {source} | {label} | {count} |")

    lines.extend(
        [
            "",
            "## Highest-Volume Review Queue",
            "",
            "These rows expose only `file_id`, `path_hash`, and hashed `source_tag`.",
            "",
            "| File ID | Source | Source tag | Path hash | Label | Gate | Baseline starts | Normalized starts | Evidence | Warnings |",
            "|---|---|---|---|---|---|---:|---:|---|---|",
        ]
    )
    for row in top_review_rows(classified, review_limit):
        lines.append(
            "| {file_id} | {source} | {source_tag} | `{path_hash}` | {label} | {gate} | {starts} | {normalized} | {evidence} | {warnings} |".format(
                file_id=row.file_id,
                source=row.source,
                source_tag=row.source_tag or "",
                path_hash=row.path_hash,
                label=row.classification_label,
                gate=row.processing_gate,
                starts=row.message_start_count,
                normalized=row.normalized_message_start_count,
                evidence=", ".join(row.evidence_codes),
                warnings=", ".join(row.warning_codes),
            )
        )

    lines.extend(
        [
            "",
            "## Operating Rule",
            "",
            "- `deny_content_mining_until_owner_allowlist`: do not inspect message bodies unless the owner creates a local allowlist.",
            "- `local_only_team_analysis_after_owner_approval`: can be analyzed only on Pro after explicit local approval for that source group.",
            "- `manual_review_before_content_mining`: safe for metadata counts only until reviewed.",
            "- `manual_review_before_any_use`: do not use except to decide whether the file belongs in the corpus.",
            "",
            "## SQLite Inspection Examples",
            "",
            "```sql",
            "SELECT classification_label, files, message_starts, normalized_message_starts, review_required_files",
            "FROM classification_summaries",
            "ORDER BY files DESC;",
            "",
            "SELECT processing_gate, files, message_starts",
            "FROM gate_summaries",
            "ORDER BY files DESC;",
            "",
            "SELECT file_id, source, source_tag, path_hash, classification_label, processing_gate, message_start_count",
            "FROM classified_chats",
            "WHERE review_required = 1",
            "ORDER BY message_start_count DESC",
            "LIMIT 50;",
            "```",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Classify WhatsApp corpus registry rows into local-only privacy gates."
    )
    parser.add_argument(
        "--registry-db",
        type=Path,
        default=DEFAULT_REGISTRY_DB,
        help="Path to registry.sqlite produced by build_registry.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for chat_classification.sqlite and classification_summary.md.",
    )
    parser.add_argument(
        "--review-limit",
        type=int,
        default=40,
        help="Maximum review queue rows to include in the Markdown report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)
    registry_db = args.registry_db
    output_dir = args.output_dir

    try:
        entries = read_registry_entries(registry_db)
    except FileNotFoundError as exc:
        LOGGER.error("%s", exc)
        return 2

    classified = classify_entries(entries)
    classification_db = output_dir / "chat_classification.sqlite"
    summary_path = output_dir / "classification_summary.md"
    write_sqlite(
        db_path=classification_db,
        registry_db=registry_db,
        classified=classified,
    )
    write_summary(
        summary_path=summary_path,
        registry_db=registry_db,
        classification_db=classification_db,
        classified=classified,
        review_limit=args.review_limit,
    )

    LOGGER.info("Classified %d chat files.", len(classified))
    LOGGER.info("Wrote %s", classification_db)
    LOGGER.info("Wrote %s", summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
