from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_FULL_DIR = Path("research/personal/wa-corpus/full")
DEFAULT_INPUT_DB = DEFAULT_FULL_DIR / "full_messages.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_FULL_DIR / "spicy_quarantine.local.sqlite"
DEFAULT_QUARANTINE_TSV = DEFAULT_FULL_DIR / "spicy_quarantine.local.tsv"
DEFAULT_USABLE_TSV = DEFAULT_FULL_DIR / "usable_after_spicy_quarantine.local.tsv"
DEFAULT_SUMMARY = DEFAULT_FULL_DIR / "spicy_quarantine_summary.md"

EXPECTED_INPUT_DB_NAME = "full_messages.local.sqlite"

HARD_PATTERNS: dict[str, re.Pattern[str]] = {
    "explicit_sex_en": re.compile(r"\b(?:sex|sexual|horny|orgasm|erotic)\b", re.I),
    "explicit_sex_it": re.compile(r"\b(?:sesso|sessuale|eccitat[oaie]|orgasm[oa])\b", re.I),
    "explicit_sex_id": re.compile(r"\b(?:seks|seksual|nafsu|orgasme)\b", re.I),
    "nude_content": re.compile(r"\b(?:nude|nudes|naked|nudo|nuda|bugil|telanjang)\b", re.I),
    "porn_content": re.compile(r"\b(?:porn|porno|pornograf\w*)\b", re.I),
    "masturbation": re.compile(r"\b(?:masturbat\w*|masturbazione|masturbasi)\b", re.I),
}
SOFT_PATTERNS: dict[str, re.Pattern[str]] = {
    "romantic_love_en": re.compile(r"\b(?:i love you|love you|miss you|babe|baby)\b", re.I),
    "romantic_love_it": re.compile(r"\b(?:ti amo|mi manchi|amore|tesoro)\b", re.I),
    "romantic_love_id": re.compile(r"\b(?:sayang|aku cinta|kangen)\b", re.I),
    "romantic_affection": re.compile(r"\b(?:kiss|kisses|baci|bacio|peluk|cium)\b", re.I),
}


@dataclass(frozen=True)
class MessageScanRow:
    file_id: str
    source: str
    source_tag: str | None
    path_hash: str
    message_index: int
    timestamp: str | None
    sender_hash: str | None
    body_text: str


@dataclass(frozen=True)
class FileSummaryRow:
    file_id: str
    source: str
    source_tag: str | None
    path_hash: str
    local_path: str
    parsed_messages: int
    min_timestamp: str | None
    max_timestamp: str | None


@dataclass(frozen=True)
class HitRow:
    file_id: str
    source: str
    source_tag: str | None
    path_hash: str
    message_index: int
    timestamp: str | None
    sender_hash: str | None
    hit_code: str
    hit_strength: str
    evidence_hash: str


@dataclass(frozen=True)
class ConversationDecision:
    file_summary: FileSummaryRow
    hard_hits: int
    soft_hits: int
    hit_codes: tuple[str, ...]
    quarantine_decision: str
    quarantine_reason: str


@dataclass(frozen=True)
class QuarantineResult:
    file_summaries: list[FileSummaryRow]
    hits: list[HitRow]
    decisions: list[ConversationDecision]


def stable_hash(value: str, length: int = 24) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    if db_path.name != EXPECTED_INPUT_DB_NAME:
        raise ValueError(f"Refusing unexpected input DB: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"Input DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_full_corpus(db_path: Path) -> tuple[list[FileSummaryRow], list[MessageScanRow]]:
    """Read cleartext local full-corpus rows for private quarantine classification."""
    with _connect_readonly(db_path) as conn:
        file_rows = [
            FileSummaryRow(
                file_id=str(row["file_id"]),
                source=str(row["source"]),
                source_tag=str(row["source_tag"]) if row["source_tag"] is not None else None,
                path_hash=str(row["path_hash"]),
                local_path=str(row["local_path"]),
                parsed_messages=int(row["parsed_messages"]),
                min_timestamp=str(row["min_timestamp"]) if row["min_timestamp"] is not None else None,
                max_timestamp=str(row["max_timestamp"]) if row["max_timestamp"] is not None else None,
            )
            for row in conn.execute(
                """
                SELECT file_id, source, source_tag, path_hash, local_path,
                       parsed_messages, min_timestamp, max_timestamp
                FROM file_parse_summaries
                ORDER BY file_id
                """
            )
        ]
        message_rows = [
            MessageScanRow(
                file_id=str(row["file_id"]),
                source=str(row["source"]),
                source_tag=str(row["source_tag"]) if row["source_tag"] is not None else None,
                path_hash=str(row["path_hash"]),
                message_index=int(row["message_index"]),
                timestamp=str(row["timestamp"]) if row["timestamp"] is not None else None,
                sender_hash=str(row["sender_hash"]) if row["sender_hash"] is not None else None,
                body_text=str(row["body_text"] or ""),
            )
            for row in conn.execute(
                """
                SELECT file_id, source, source_tag, path_hash, message_index,
                       timestamp, sender_hash, body_text
                FROM parsed_messages
                ORDER BY file_id, message_index
                """
            )
        ]
    return file_rows, message_rows


def classify_message(row: MessageScanRow) -> list[HitRow]:
    """Return spicy/intimate hit rows for one message without storing raw text."""
    hits: list[HitRow] = []
    for hit_code, pattern in HARD_PATTERNS.items():
        if pattern.search(row.body_text):
            hits.append(_hit(row=row, hit_code=hit_code, hit_strength="hard"))
    for hit_code, pattern in SOFT_PATTERNS.items():
        if pattern.search(row.body_text):
            hits.append(_hit(row=row, hit_code=hit_code, hit_strength="soft"))
    return hits


def _hit(*, row: MessageScanRow, hit_code: str, hit_strength: str) -> HitRow:
    return HitRow(
        file_id=row.file_id,
        source=row.source,
        source_tag=row.source_tag,
        path_hash=row.path_hash,
        message_index=row.message_index,
        timestamp=row.timestamp,
        sender_hash=row.sender_hash,
        hit_code=hit_code,
        hit_strength=hit_strength,
        evidence_hash=stable_hash(f"{row.file_id}|{row.message_index}|{hit_code}|{row.body_text}"),
    )


def decide_conversations(
    *,
    file_summaries: list[FileSummaryRow],
    hits: list[HitRow],
) -> list[ConversationDecision]:
    """Quarantine only conversations with explicit spicy evidence."""
    hits_by_file: dict[str, list[HitRow]] = {}
    for hit in hits:
        hits_by_file.setdefault(hit.file_id, []).append(hit)

    decisions: list[ConversationDecision] = []
    for summary in file_summaries:
        file_hits = hits_by_file.get(summary.file_id, [])
        hard_hits = sum(1 for hit in file_hits if hit.hit_strength == "hard")
        soft_hits = sum(1 for hit in file_hits if hit.hit_strength == "soft")
        hit_codes = tuple(sorted({hit.hit_code for hit in file_hits}))
        if hard_hits:
            decision = "quarantine_spicy_candidate"
            reason = "explicit_spicy_keyword_hit"
        else:
            decision = "usable"
            reason = "no_explicit_spicy_hit"
        decisions.append(
            ConversationDecision(
                file_summary=summary,
                hard_hits=hard_hits,
                soft_hits=soft_hits,
                hit_codes=hit_codes,
                quarantine_decision=decision,
                quarantine_reason=reason,
            )
        )
    return decisions


def build_quarantine(
    *,
    input_db: Path,
) -> QuarantineResult:
    """Build local spicy-conversation quarantine decisions."""
    file_summaries, message_rows = read_full_corpus(input_db)
    hits: list[HitRow] = []
    for row in message_rows:
        hits.extend(classify_message(row))
    decisions = decide_conversations(file_summaries=file_summaries, hits=hits)
    return QuarantineResult(file_summaries=file_summaries, hits=hits, decisions=decisions)


def write_sqlite(*, output_db: Path, input_db: Path, result: QuarantineResult) -> None:
    """Write local quarantine evidence and decisions."""
    output_db.parent.mkdir(parents=True, exist_ok=True)
    if output_db.exists():
        output_db.unlink()
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            CREATE TABLE quarantine_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at TEXT NOT NULL,
                input_db TEXT NOT NULL,
                privacy_mode TEXT NOT NULL
            );

            CREATE TABLE quarantine_hits (
                file_id TEXT NOT NULL,
                source TEXT NOT NULL,
                source_tag TEXT,
                path_hash TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                timestamp TEXT,
                sender_hash TEXT,
                hit_code TEXT NOT NULL,
                hit_strength TEXT NOT NULL,
                evidence_hash TEXT NOT NULL,
                PRIMARY KEY (file_id, message_index, hit_code)
            );

            CREATE TABLE conversation_decisions (
                file_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_tag TEXT,
                path_hash TEXT NOT NULL,
                local_path TEXT NOT NULL,
                parsed_messages INTEGER NOT NULL,
                min_timestamp TEXT,
                max_timestamp TEXT,
                hard_hits INTEGER NOT NULL,
                soft_hits INTEGER NOT NULL,
                hit_codes_json TEXT NOT NULL,
                quarantine_decision TEXT NOT NULL,
                quarantine_reason TEXT NOT NULL
            );

            CREATE INDEX idx_quarantine_hits_file ON quarantine_hits(file_id);
            CREATE INDEX idx_quarantine_decision ON conversation_decisions(quarantine_decision);
            """
        )
        conn.execute(
            """
            INSERT INTO quarantine_runs (id, generated_at, input_db, privacy_mode)
            VALUES (1, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                input_db.name,
                "local_only_spicy_quarantine_no_raw_text_in_outputs",
            ),
        )
        conn.executemany(
            """
            INSERT INTO quarantine_hits (
                file_id, source, source_tag, path_hash, message_index, timestamp,
                sender_hash, hit_code, hit_strength, evidence_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    hit.file_id,
                    hit.source,
                    hit.source_tag,
                    hit.path_hash,
                    hit.message_index,
                    hit.timestamp,
                    hit.sender_hash,
                    hit.hit_code,
                    hit.hit_strength,
                    hit.evidence_hash,
                )
                for hit in result.hits
            ],
        )
        conn.executemany(
            """
            INSERT INTO conversation_decisions (
                file_id, source, source_tag, path_hash, local_path, parsed_messages,
                min_timestamp, max_timestamp, hard_hits, soft_hits, hit_codes_json,
                quarantine_decision, quarantine_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    decision.file_summary.file_id,
                    decision.file_summary.source,
                    decision.file_summary.source_tag,
                    decision.file_summary.path_hash,
                    decision.file_summary.local_path,
                    decision.file_summary.parsed_messages,
                    decision.file_summary.min_timestamp,
                    decision.file_summary.max_timestamp,
                    decision.hard_hits,
                    decision.soft_hits,
                    json.dumps(decision.hit_codes),
                    decision.quarantine_decision,
                    decision.quarantine_reason,
                )
                for decision in result.decisions
            ],
        )
        conn.commit()


def write_decision_tsvs(
    *,
    quarantine_tsv: Path,
    usable_tsv: Path,
    decisions: list[ConversationDecision],
) -> None:
    """Write local file lists for quarantined and usable conversations."""
    quarantine_tsv.parent.mkdir(parents=True, exist_ok=True)
    usable_tsv.parent.mkdir(parents=True, exist_ok=True)
    _write_decision_tsv(
        quarantine_tsv,
        [
            decision
            for decision in decisions
            if decision.quarantine_decision == "quarantine_spicy_candidate"
        ],
    )
    _write_decision_tsv(
        usable_tsv,
        [decision for decision in decisions if decision.quarantine_decision == "usable"],
    )


def _write_decision_tsv(path: Path, decisions: Iterable[ConversationDecision]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "file_id",
                "source",
                "source_tag",
                "path_hash",
                "local_path",
                "parsed_messages",
                "min_timestamp",
                "max_timestamp",
                "hard_hits",
                "soft_hits",
                "hit_codes_json",
                "quarantine_decision",
                "quarantine_reason",
            ]
        )
        for decision in decisions:
            summary = decision.file_summary
            writer.writerow(
                [
                    summary.file_id,
                    summary.source,
                    summary.source_tag or "",
                    summary.path_hash,
                    summary.local_path,
                    summary.parsed_messages,
                    summary.min_timestamp or "",
                    summary.max_timestamp or "",
                    decision.hard_hits,
                    decision.soft_hits,
                    json.dumps(decision.hit_codes),
                    decision.quarantine_decision,
                    decision.quarantine_reason,
                ]
            )


def write_summary(
    *,
    summary_path: Path,
    input_db: Path,
    output_db: Path,
    quarantine_tsv: Path,
    usable_tsv: Path,
    result: QuarantineResult,
) -> None:
    """Write tracked aggregate-only spicy quarantine summary."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    decision_counts = Counter(decision.quarantine_decision for decision in result.decisions)
    source_counts = Counter(
        decision.file_summary.source
        for decision in result.decisions
        if decision.quarantine_decision == "quarantine_spicy_candidate"
    )
    hit_strength_counts = Counter(hit.hit_strength for hit in result.hits)
    hit_code_counts = Counter(hit.hit_code for hit in result.hits)
    quarantined_message_total = sum(
        decision.file_summary.parsed_messages
        for decision in result.decisions
        if decision.quarantine_decision == "quarantine_spicy_candidate"
    )
    usable_message_total = sum(
        decision.file_summary.parsed_messages
        for decision in result.decisions
        if decision.quarantine_decision == "usable"
    )

    lines = [
        "# WhatsApp Spicy Conversation Quarantine Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Input full corpus DB: `{input_db.name}`",
        f"Local quarantine DB: `{output_db.name}`",
        f"Private quarantine TSV: `{quarantine_tsv.name}`",
        f"Private usable TSV: `{usable_tsv.name}`",
        "",
        "## Privacy Mode",
        "",
        "- This tracked summary contains no raw message text.",
        "- This tracked summary contains no message snippets.",
        "- This tracked summary contains no phone numbers or emails.",
        "- This tracked summary contains no raw source paths or contact names.",
        "- Private TSV and SQLite artifacts are ignored by git and stay local-only.",
        "",
        "## Policy",
        "",
        "- Only conversations with explicit spicy keyword evidence are set aside.",
        "- Romantic/affection hints alone are not quarantined.",
        "- Quarantine is a conservative routing step, not a final claim about the conversation.",
        "- Non-quarantined conversations can feed local CRM/ops/KB mining.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Files scanned | {len(result.file_summaries)} |",
        f"| Quarantined files | {decision_counts.get('quarantine_spicy_candidate', 0)} |",
        f"| Usable files | {decision_counts.get('usable', 0)} |",
        f"| Quarantined messages | {quarantined_message_total} |",
        f"| Usable messages | {usable_message_total} |",
        f"| Total keyword hits | {len(result.hits)} |",
        "",
        "## Hit Strengths",
        "",
        "| Strength | Hits |",
        "|---|---:|",
    ]
    if hit_strength_counts:
        for strength, count in hit_strength_counts.most_common():
            lines.append(f"| {strength} | {count} |")
    else:
        lines.append("| none | 0 |")

    lines.extend(["", "## Quarantine Sources", "", "| Source | Files |", "|---|---:|"])
    if source_counts:
        for source, count in source_counts.most_common():
            lines.append(f"| {source} | {count} |")
    else:
        lines.append("| none | 0 |")

    lines.extend(["", "## Generic Hit Codes", "", "| Code | Hits |", "|---|---:|"])
    if hit_code_counts:
        for code, count in hit_code_counts.most_common():
            lines.append(f"| {code} | {count} |")
    else:
        lines.append("| none | 0 |")

    lines.extend(
        [
            "",
            "## Next Local Step",
            "",
            "Use `usable_after_spicy_quarantine.local.tsv` as the file-level include list for full-corpus local mining.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def quarantine_to_outputs(
    *,
    input_db: Path,
    output_db: Path,
    quarantine_tsv: Path,
    usable_tsv: Path,
    summary_path: Path,
) -> QuarantineResult:
    """Run the quarantine pass and write all local artifacts."""
    result = build_quarantine(input_db=input_db)
    write_sqlite(output_db=output_db, input_db=input_db, result=result)
    write_decision_tsvs(
        quarantine_tsv=quarantine_tsv,
        usable_tsv=usable_tsv,
        decisions=result.decisions,
    )
    write_summary(
        summary_path=summary_path,
        input_db=input_db,
        output_db=output_db,
        quarantine_tsv=quarantine_tsv,
        usable_tsv=usable_tsv,
        result=result,
    )
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Set aside only explicit spicy/private WhatsApp conversations."
    )
    parser.add_argument("--input-db", type=Path, default=DEFAULT_INPUT_DB)
    parser.add_argument("--output-db", type=Path, default=DEFAULT_OUTPUT_DB)
    parser.add_argument("--quarantine-tsv", type=Path, default=DEFAULT_QUARANTINE_TSV)
    parser.add_argument("--usable-tsv", type=Path, default=DEFAULT_USABLE_TSV)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = quarantine_to_outputs(
            input_db=args.input_db,
            output_db=args.output_db,
            quarantine_tsv=args.quarantine_tsv,
            usable_tsv=args.usable_tsv,
            summary_path=args.summary,
        )
    except (FileNotFoundError, ValueError, sqlite3.DatabaseError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    if args.json:
        decision_counts = Counter(decision.quarantine_decision for decision in result.decisions)
        json.dump(
            {
                "files_scanned": len(result.file_summaries),
                "hits": len(result.hits),
                "quarantined_files": decision_counts.get("quarantine_spicy_candidate", 0),
                "usable_files": decision_counts.get("usable", 0),
                "output_db": str(args.output_db),
                "summary": str(args.summary),
            },
            sys.stdout,
            sort_keys=True,
        )
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
