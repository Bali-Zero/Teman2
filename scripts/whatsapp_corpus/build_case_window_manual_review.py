from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_ANALYSIS_DIR = Path("research/personal/wa-corpus/analysis")
DEFAULT_REVIEW_DIR = Path("research/personal/wa-corpus/review")
DEFAULT_QUEUE_TSV = DEFAULT_ANALYSIS_DIR / "allowed_case_window_review.local.tsv"
DEFAULT_MESSAGES_DB = DEFAULT_ANALYSIS_DIR / "allowed_messages.local.sqlite"
DEFAULT_EVENTS_DB = DEFAULT_ANALYSIS_DIR / "allowed_domain_events.local.sqlite"
DEFAULT_WORKBOOK = DEFAULT_REVIEW_DIR / "case_window_review_workbook.local.tsv"
DEFAULT_CONTEXT = DEFAULT_REVIEW_DIR / "case_window_context.local.tsv"
DEFAULT_SUMMARY = DEFAULT_REVIEW_DIR / "case_window_manual_review_summary.md"

EXPECTED_QUEUE_NAME = "allowed_case_window_review.local.tsv"
EXPECTED_MESSAGES_DB_NAME = "allowed_messages.local.sqlite"
EXPECTED_EVENTS_DB_NAME = "allowed_domain_events.local.sqlite"

OWNER_DECISIONS = ("approve", "hold", "deny", "duplicate", "no_action")
ACTION_TYPES = (
    "crm_followup",
    "document_chase",
    "deadline_check",
    "immigration_status_check",
    "payment_reconcile",
    "case_note",
    "kb_extract",
    "team_escalation",
)
OWNER_COLUMNS = (
    "review_status",
    "owner_decision",
    "action_type",
    "priority",
    "action_owner",
    "due_date",
    "owner_notes",
)

EMAIL_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9._%+-])[A-Z0-9._%+-]+@(?:[A-Z0-9-]+\.)+[A-Z]{2,63}\b"
)
PHONE_RE = re.compile(
    r"""(?x)
    (?<![\w-])
    (?:
        \+(?:\d[\s().-]?){8,16}\d
        | 00(?:\d[\s().-]?){8,16}\d
        | 62(?:[\s().-]?\d){8,14}
    )
    (?![\w-])
    """
)
URL_RE = re.compile(r"(?i)\bhttps?://[^\s<>)\]]+")
PASSPORT_RE = re.compile(r"(?<![\w-])(?:[A-Z][0-9]{7,8}|[A-Z]{2}[0-9]{6,8})(?![\w-])")
LONG_DIGIT_RE = re.compile(r"(?<![\w-])\d{9,20}(?![\w-])")
WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class QueueRow:
    rank: int
    window_id: str
    file_id: str
    window_ordinal: int
    first_month: str
    last_month: str
    first_message_index: int
    last_message_index: int
    event_count: int
    message_count: int
    domain_count: int
    dominant_domain: str
    severity_high_count: int
    review_score: int
    review_reasons: str
    top_event_codes_json: str


@dataclass(frozen=True)
class MessageContextRow:
    rank: int
    window_id: str
    context_scope: str
    message_index: int
    timestamp: str
    sender_hash: str
    direction: str
    body_preview_redacted: str
    body_char_count: int
    matched_event_codes: tuple[str, ...]


@dataclass(frozen=True)
class ManualReviewPack:
    queue_rows: list[QueueRow]
    context_rows: list[MessageContextRow]
    preserved_owner_rows: int


def _require_expected_name(path: Path, expected_name: str) -> None:
    if path.name != expected_name:
        raise ValueError(f"Refusing unexpected WhatsApp artifact name: {path.name}")


def _connect_readonly(db_path: Path, expected_name: str) -> sqlite3.Connection:
    _require_expected_name(db_path, expected_name)
    if not db_path.exists():
        raise FileNotFoundError(f"Input DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _int_value(raw: str | None) -> int:
    if raw is None or raw == "":
        return 0
    return int(raw)


def read_queue(path: Path, *, limit: int | None = None) -> list[QueueRow]:
    """Read the local aggregate review queue."""
    _require_expected_name(path, EXPECTED_QUEUE_NAME)
    if not path.exists():
        raise FileNotFoundError(f"Queue TSV not found: {path}")

    rows: list[QueueRow] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for raw in reader:
            rows.append(
                QueueRow(
                    rank=_int_value(raw.get("rank")),
                    window_id=str(raw.get("window_id") or ""),
                    file_id=str(raw.get("file_id") or ""),
                    window_ordinal=_int_value(raw.get("window_ordinal")),
                    first_month=str(raw.get("first_month") or "unknown"),
                    last_month=str(raw.get("last_month") or "unknown"),
                    first_message_index=_int_value(raw.get("first_message_index")),
                    last_message_index=_int_value(raw.get("last_message_index")),
                    event_count=_int_value(raw.get("event_count")),
                    message_count=_int_value(raw.get("message_count")),
                    domain_count=_int_value(raw.get("domain_count")),
                    dominant_domain=str(raw.get("dominant_domain") or "unknown"),
                    severity_high_count=_int_value(raw.get("severity_high_count")),
                    review_score=_int_value(raw.get("review_score")),
                    review_reasons=str(raw.get("review_reasons") or ""),
                    top_event_codes_json=str(raw.get("top_event_codes_json") or "[]"),
                )
            )
            if limit is not None and len(rows) >= limit:
                break
    return rows


def redact_text(value: str, *, max_chars: int) -> str:
    """Return a local review preview with direct identifiers masked."""
    text = WHITESPACE_RE.sub(" ", value).strip()
    text = URL_RE.sub("[URL]", text)
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    text = PASSPORT_RE.sub("[ID]", text)
    text = LONG_DIGIT_RE.sub("[ID]", text)
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3].rstrip()}..."


def read_existing_owner_fields(workbook_path: Path) -> dict[str, dict[str, str]]:
    """Preserve manual owner fields when regenerating the workbook."""
    if not workbook_path.exists():
        return {}
    rows: dict[str, dict[str, str]] = {}
    with workbook_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for raw in reader:
            window_id = str(raw.get("window_id") or "").strip()
            if not window_id:
                continue
            rows[window_id] = {column: str(raw.get(column) or "") for column in OWNER_COLUMNS}
    return rows


def _context_scope(row: QueueRow, message_index: int) -> str:
    if message_index < row.first_message_index:
        return "before"
    if message_index > row.last_message_index:
        return "after"
    return "window"


def read_event_codes_for_windows(
    *,
    events_db: Path,
    queue_rows: Iterable[QueueRow],
) -> dict[tuple[str, int], tuple[str, ...]]:
    """Read event codes for messages represented by the review windows."""
    with _connect_readonly(events_db, EXPECTED_EVENTS_DB_NAME) as conn:
        event_codes: dict[tuple[str, int], set[str]] = {}
        for row in queue_rows:
            rows = conn.execute(
                """
                SELECT file_id, message_index, domain_code, event_code
                FROM domain_events
                WHERE file_id = ?
                  AND message_index BETWEEN ? AND ?
                ORDER BY message_index, domain_code, event_code
                """,
                (row.file_id, row.first_message_index, row.last_message_index),
            ).fetchall()
            for event in rows:
                key = (str(event["file_id"]), int(event["message_index"]))
                event_codes.setdefault(key, set()).add(
                    f"{event['domain_code']}:{event['event_code']}"
                )
    return {key: tuple(sorted(values)) for key, values in event_codes.items()}


def build_context_rows(
    *,
    messages_db: Path,
    queue_rows: list[QueueRow],
    event_codes: dict[tuple[str, int], tuple[str, ...]],
    context_radius: int,
    max_chars: int,
) -> list[MessageContextRow]:
    """Build the ignored local context TSV rows for owner review."""
    context_rows: list[MessageContextRow] = []
    with _connect_readonly(messages_db, EXPECTED_MESSAGES_DB_NAME) as conn:
        for row in queue_rows:
            start_index = max(0, row.first_message_index - context_radius)
            end_index = row.last_message_index + context_radius
            rows = conn.execute(
                """
                SELECT message_index, timestamp, sender_hash, direction,
                       body_text, body_char_count
                FROM parsed_messages
                WHERE file_id = ?
                  AND message_index BETWEEN ? AND ?
                ORDER BY message_index
                """,
                (row.file_id, start_index, end_index),
            ).fetchall()
            for message in rows:
                message_index = int(message["message_index"])
                context_rows.append(
                    MessageContextRow(
                        rank=row.rank,
                        window_id=row.window_id,
                        context_scope=_context_scope(row, message_index),
                        message_index=message_index,
                        timestamp=str(message["timestamp"] or ""),
                        sender_hash=str(message["sender_hash"] or ""),
                        direction=str(message["direction"] or ""),
                        body_preview_redacted=redact_text(
                            str(message["body_text"] or ""),
                            max_chars=max_chars,
                        ),
                        body_char_count=_int_value(str(message["body_char_count"] or "0")),
                        matched_event_codes=event_codes.get((row.file_id, message_index), ()),
                    )
                )
    return context_rows


def write_workbook(
    *,
    workbook_path: Path,
    queue_rows: list[QueueRow],
    preserved_fields: dict[str, dict[str, str]],
) -> int:
    """Write the editable local manual-review workbook."""
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    preserved_count = 0
    with workbook_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                *OWNER_COLUMNS,
                "rank",
                "window_id",
                "file_id",
                "window_ordinal",
                "first_month",
                "last_month",
                "first_message_index",
                "last_message_index",
                "event_count",
                "message_count",
                "domain_count",
                "dominant_domain",
                "severity_high_count",
                "review_score",
                "review_reasons",
                "top_event_codes_json",
            ]
        )
        for row in queue_rows:
            owner_values = preserved_fields.get(row.window_id, {})
            if any(owner_values.values()):
                preserved_count += 1
            writer.writerow(
                [
                    owner_values.get("review_status") or "todo",
                    owner_values.get("owner_decision") or "",
                    owner_values.get("action_type") or "",
                    owner_values.get("priority") or "P2",
                    owner_values.get("action_owner") or "",
                    owner_values.get("due_date") or "",
                    owner_values.get("owner_notes") or "",
                    row.rank,
                    row.window_id,
                    row.file_id,
                    row.window_ordinal,
                    row.first_month,
                    row.last_month,
                    row.first_message_index,
                    row.last_message_index,
                    row.event_count,
                    row.message_count,
                    row.domain_count,
                    row.dominant_domain,
                    row.severity_high_count,
                    row.review_score,
                    row.review_reasons,
                    row.top_event_codes_json,
                ]
            )
    return preserved_count


def write_context_tsv(*, context_path: Path, context_rows: list[MessageContextRow]) -> None:
    """Write local message context with redacted previews."""
    context_path.parent.mkdir(parents=True, exist_ok=True)
    with context_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "rank",
                "window_id",
                "context_scope",
                "message_index",
                "timestamp",
                "sender_hash",
                "direction",
                "body_preview_redacted",
                "body_char_count",
                "matched_event_codes",
            ]
        )
        for row in context_rows:
            writer.writerow(
                [
                    row.rank,
                    row.window_id,
                    row.context_scope,
                    row.message_index,
                    row.timestamp,
                    row.sender_hash,
                    row.direction,
                    row.body_preview_redacted,
                    row.body_char_count,
                    ",".join(row.matched_event_codes),
                ]
            )


def write_summary(
    *,
    summary_path: Path,
    queue_rows: list[QueueRow],
    context_rows: list[MessageContextRow],
    workbook_path: Path,
    context_path: Path,
    preserved_owner_rows: int,
) -> None:
    """Write a tracked aggregate-only manual-review summary."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    domain_counts = Counter(row.dominant_domain for row in queue_rows)
    scope_counts = Counter(row.context_scope for row in context_rows)
    total_window_messages = sum(row.message_count for row in queue_rows)
    total_events = sum(row.event_count for row in queue_rows)
    total_high = sum(row.severity_high_count for row in queue_rows)

    lines = [
        "# WhatsApp Case Window Manual Review",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Private workbook: `{workbook_path.as_posix()}`",
        f"Private context TSV: `{context_path.as_posix()}`",
        "",
        "## Privacy Mode",
        "",
        "- This tracked summary contains no raw message text.",
        "- This tracked summary contains no message snippets.",
        "- This tracked summary contains no phone numbers or emails.",
        "- This tracked summary contains no raw source paths or extracted values.",
        "- The private `.local.tsv` workbook and context files are ignored by git.",
        "- Context previews mask direct identifiers and still stay local-only.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Review windows | {len(queue_rows)} |",
        f"| Window messages | {total_window_messages} |",
        f"| Window events | {total_events} |",
        f"| High-severity event refs | {total_high} |",
        f"| Context rows | {len(context_rows)} |",
        f"| Preserved owner rows | {preserved_owner_rows} |",
        "",
        "## Context Scopes",
        "",
        "| Scope | Rows |",
        "|---|---:|",
    ]
    for scope, count in scope_counts.most_common():
        lines.append(f"| {scope} | {count} |")

    lines.extend(
        [
            "",
            "## Dominant Domains",
            "",
            "| Domain | Windows |",
            "|---|---:|",
        ]
    )
    for domain, count in domain_counts.most_common():
        lines.append(f"| {domain} | {count} |")

    lines.extend(
        [
            "",
            "## Owner Decision Values",
            "",
            "| Value | Meaning |",
            "|---|---|",
            "| approve | Queue a local CRM/ops action. |",
            "| hold | Keep for later review. |",
            "| deny | Exclude from action generation. |",
            "| duplicate | Exclude as duplicated context. |",
            "| no_action | Reviewed, no action required. |",
            "",
            "## Action Types",
            "",
            "| Type | Use |",
            "|---|---|",
            "| crm_followup | Follow-up or status check. |",
            "| document_chase | Missing or pending document chase. |",
            "| deadline_check | Date or deadline validation. |",
            "| immigration_status_check | Visa or immigration status check. |",
            "| payment_reconcile | Invoice, transfer, or proof reconciliation. |",
            "| case_note | Add an internal case note only. |",
            "| kb_extract | Extract reusable internal knowledge. |",
            "| team_escalation | Internal escalation for owner/team review. |",
            "",
            "## Next Command",
            "",
            "After filling `owner_decision=approve` on selected rows, run:",
            "",
            "```bash",
            "source .venv/bin/activate",
            "PYTHONPATH=. python -m scripts.whatsapp_corpus.compile_case_window_actions",
            "```",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_manual_review_pack(
    *,
    queue_tsv: Path,
    messages_db: Path,
    events_db: Path,
    workbook_path: Path,
    context_path: Path,
    summary_path: Path,
    limit: int | None,
    context_radius: int,
    max_chars: int,
) -> ManualReviewPack:
    """Create local manual-review files for the top case windows."""
    queue_rows = read_queue(queue_tsv, limit=limit)
    preserved_fields = read_existing_owner_fields(workbook_path)
    event_codes = read_event_codes_for_windows(events_db=events_db, queue_rows=queue_rows)
    context_rows = build_context_rows(
        messages_db=messages_db,
        queue_rows=queue_rows,
        event_codes=event_codes,
        context_radius=context_radius,
        max_chars=max_chars,
    )
    preserved_owner_rows = write_workbook(
        workbook_path=workbook_path,
        queue_rows=queue_rows,
        preserved_fields=preserved_fields,
    )
    write_context_tsv(context_path=context_path, context_rows=context_rows)
    write_summary(
        summary_path=summary_path,
        queue_rows=queue_rows,
        context_rows=context_rows,
        workbook_path=workbook_path,
        context_path=context_path,
        preserved_owner_rows=preserved_owner_rows,
    )
    return ManualReviewPack(
        queue_rows=queue_rows,
        context_rows=context_rows,
        preserved_owner_rows=preserved_owner_rows,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local manual-review files for WhatsApp case windows."
    )
    parser.add_argument("--queue-tsv", type=Path, default=DEFAULT_QUEUE_TSV)
    parser.add_argument("--messages-db", type=Path, default=DEFAULT_MESSAGES_DB)
    parser.add_argument("--events-db", type=Path, default=DEFAULT_EVENTS_DB)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--context", type=Path, default=DEFAULT_CONTEXT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--context-radius", type=int, default=2)
    parser.add_argument("--max-chars", type=int, default=500)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        pack = build_manual_review_pack(
            queue_tsv=args.queue_tsv,
            messages_db=args.messages_db,
            events_db=args.events_db,
            workbook_path=args.workbook,
            context_path=args.context,
            summary_path=args.summary,
            limit=args.limit,
            context_radius=args.context_radius,
            max_chars=args.max_chars,
        )
    except (FileNotFoundError, ValueError, sqlite3.DatabaseError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    if args.json:
        json.dump(
            {
                "review_windows": len(pack.queue_rows),
                "context_rows": len(pack.context_rows),
                "preserved_owner_rows": pack.preserved_owner_rows,
                "workbook": str(args.workbook),
                "context": str(args.context),
                "summary": str(args.summary),
            },
            sys.stdout,
            sort_keys=True,
        )
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
