from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_REVIEW_DIR = Path("research/personal/wa-corpus/review")
DEFAULT_ACTION_DIR = Path("research/personal/wa-corpus/actions")
DEFAULT_WORKBOOK = DEFAULT_REVIEW_DIR / "case_window_review_workbook.local.tsv"
DEFAULT_ACTIONS = DEFAULT_ACTION_DIR / "case_window_actions.local.tsv"
DEFAULT_SUMMARY = DEFAULT_ACTION_DIR / "case_window_actions_summary.md"

EXPECTED_WORKBOOK_NAME = "case_window_review_workbook.local.tsv"
VALID_DECISIONS = frozenset({"", "approve", "hold", "deny", "duplicate", "no_action"})
VALID_ACTION_TYPES = frozenset(
    {
        "crm_followup",
        "document_chase",
        "deadline_check",
        "immigration_status_check",
        "payment_reconcile",
        "case_note",
        "kb_extract",
        "team_escalation",
    }
)
VALID_PRIORITIES = frozenset({"P1", "P2", "P3"})
DOMAIN_DEFAULT_ACTION = {
    "followup_risk": "crm_followup",
    "document_requirement": "document_chase",
    "immigration_lifecycle": "immigration_status_check",
    "tax_payment": "payment_reconcile",
}


@dataclass(frozen=True)
class WorkbookRow:
    review_status: str
    owner_decision: str
    action_type: str
    priority: str
    action_owner: str
    due_date: str
    owner_notes: str
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


@dataclass(frozen=True)
class ActionRow:
    action_id: str
    status: str
    priority: str
    action_type: str
    action_owner: str
    due_date: str
    source_window_id: str
    source_file_id: str
    window_ordinal: int
    first_month: str
    last_month: str
    first_message_index: int
    last_message_index: int
    dominant_domain: str
    event_count: int
    message_count: int
    severity_high_count: int
    review_score: int
    owner_notes: str


@dataclass(frozen=True)
class ActionCompileResult:
    workbook_rows: list[WorkbookRow]
    action_rows: list[ActionRow]


def _int_value(raw: str | None) -> int:
    if raw is None or raw == "":
        return 0
    return int(raw)


def stable_action_id(window_id: str, action_type: str) -> str:
    digest = hashlib.sha256(f"{window_id}|{action_type}".encode("utf-8")).hexdigest()
    return f"wa-action-{digest[:16]}"


def normalize_text(raw: str | None) -> str:
    return str(raw or "").strip()


def read_workbook(path: Path) -> list[WorkbookRow]:
    """Read the local manual-review workbook."""
    if path.name != EXPECTED_WORKBOOK_NAME:
        raise ValueError(f"Refusing unexpected workbook name: {path.name}")
    if not path.exists():
        raise FileNotFoundError(f"Workbook not found: {path}")

    rows: list[WorkbookRow] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for raw in reader:
            owner_decision = normalize_text(raw.get("owner_decision"))
            if owner_decision not in VALID_DECISIONS:
                window_id = normalize_text(raw.get("window_id"))
                raise ValueError(
                    f"Invalid owner_decision {owner_decision!r} for window {window_id!r}"
                )
            action_type = normalize_text(raw.get("action_type"))
            if action_type and action_type not in VALID_ACTION_TYPES:
                window_id = normalize_text(raw.get("window_id"))
                raise ValueError(f"Invalid action_type {action_type!r} for window {window_id!r}")
            priority = normalize_text(raw.get("priority")) or "P2"
            if priority not in VALID_PRIORITIES:
                window_id = normalize_text(raw.get("window_id"))
                raise ValueError(f"Invalid priority {priority!r} for window {window_id!r}")
            rows.append(
                WorkbookRow(
                    review_status=normalize_text(raw.get("review_status")) or "todo",
                    owner_decision=owner_decision,
                    action_type=action_type,
                    priority=priority,
                    action_owner=normalize_text(raw.get("action_owner")),
                    due_date=normalize_text(raw.get("due_date")),
                    owner_notes=normalize_text(raw.get("owner_notes")),
                    rank=_int_value(raw.get("rank")),
                    window_id=normalize_text(raw.get("window_id")),
                    file_id=normalize_text(raw.get("file_id")),
                    window_ordinal=_int_value(raw.get("window_ordinal")),
                    first_month=normalize_text(raw.get("first_month")) or "unknown",
                    last_month=normalize_text(raw.get("last_month")) or "unknown",
                    first_message_index=_int_value(raw.get("first_message_index")),
                    last_message_index=_int_value(raw.get("last_message_index")),
                    event_count=_int_value(raw.get("event_count")),
                    message_count=_int_value(raw.get("message_count")),
                    domain_count=_int_value(raw.get("domain_count")),
                    dominant_domain=normalize_text(raw.get("dominant_domain")) or "unknown",
                    severity_high_count=_int_value(raw.get("severity_high_count")),
                    review_score=_int_value(raw.get("review_score")),
                    review_reasons=normalize_text(raw.get("review_reasons")),
                )
            )
    return rows


def infer_action_type(row: WorkbookRow) -> str:
    """Infer a conservative action type when an approved row leaves it blank."""
    return DOMAIN_DEFAULT_ACTION.get(row.dominant_domain, "case_note")


def build_actions(rows: Iterable[WorkbookRow]) -> list[ActionRow]:
    """Build local ops actions only from explicitly approved rows."""
    actions: list[ActionRow] = []
    for row in rows:
        if row.owner_decision != "approve":
            continue
        action_type = row.action_type or infer_action_type(row)
        actions.append(
            ActionRow(
                action_id=stable_action_id(row.window_id, action_type),
                status="queued",
                priority=row.priority,
                action_type=action_type,
                action_owner=row.action_owner,
                due_date=row.due_date,
                source_window_id=row.window_id,
                source_file_id=row.file_id,
                window_ordinal=row.window_ordinal,
                first_month=row.first_month,
                last_month=row.last_month,
                first_message_index=row.first_message_index,
                last_message_index=row.last_message_index,
                dominant_domain=row.dominant_domain,
                event_count=row.event_count,
                message_count=row.message_count,
                severity_high_count=row.severity_high_count,
                review_score=row.review_score,
                owner_notes=row.owner_notes,
            )
        )
    return actions


def write_actions(path: Path, rows: list[ActionRow]) -> None:
    """Write the ignored local CRM/ops action queue."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "action_id",
                "status",
                "priority",
                "action_type",
                "action_owner",
                "due_date",
                "source_window_id",
                "source_file_id",
                "window_ordinal",
                "first_month",
                "last_month",
                "first_message_index",
                "last_message_index",
                "dominant_domain",
                "event_count",
                "message_count",
                "severity_high_count",
                "review_score",
                "owner_notes",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.action_id,
                    row.status,
                    row.priority,
                    row.action_type,
                    row.action_owner,
                    row.due_date,
                    row.source_window_id,
                    row.source_file_id,
                    row.window_ordinal,
                    row.first_month,
                    row.last_month,
                    row.first_message_index,
                    row.last_message_index,
                    row.dominant_domain,
                    row.event_count,
                    row.message_count,
                    row.severity_high_count,
                    row.review_score,
                    row.owner_notes,
                ]
            )


def _counter_table(title: str, counts: Counter[str]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Value | Rows |",
        "|---|---:|",
    ]
    if counts:
        for value, count in counts.most_common():
            lines.append(f"| {value or 'blank'} | {count} |")
    else:
        lines.append("| none | 0 |")
    return lines


def write_summary(
    *,
    summary_path: Path,
    workbook_path: Path,
    actions_path: Path,
    workbook_rows: list[WorkbookRow],
    action_rows: list[ActionRow],
) -> None:
    """Write a tracked aggregate summary for local action generation."""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    decision_counts = Counter(row.owner_decision or "blank" for row in workbook_rows)
    action_type_counts = Counter(row.action_type for row in action_rows)
    priority_counts = Counter(row.priority for row in action_rows)
    domain_counts = Counter(row.dominant_domain for row in action_rows)
    total_events = sum(row.event_count for row in action_rows)
    total_messages = sum(row.message_count for row in action_rows)
    total_high = sum(row.severity_high_count for row in action_rows)

    lines = [
        "# WhatsApp Case Window Actions Summary",
        "",
        f"Generated UTC: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"Private workbook: `{workbook_path.as_posix()}`",
        f"Private actions queue: `{actions_path.as_posix()}`",
        "",
        "## Privacy Mode",
        "",
        "- This tracked summary contains no raw message text.",
        "- This tracked summary contains no message snippets.",
        "- This tracked summary contains no phone numbers or emails.",
        "- This tracked summary contains no raw source paths or owner notes.",
        "- Only rows with `owner_decision=approve` become local CRM/ops actions.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Workbook rows | {len(workbook_rows)} |",
        f"| Approved action rows | {len(action_rows)} |",
        f"| Action event refs | {total_events} |",
        f"| Action message refs | {total_messages} |",
        f"| Action high-severity refs | {total_high} |",
        "",
        *_counter_table("Workbook Decisions", decision_counts),
        "",
        *_counter_table("Action Types", action_type_counts),
        "",
        *_counter_table("Action Priorities", priority_counts),
        "",
        *_counter_table("Action Dominant Domains", domain_counts),
        "",
        "## Local Execution Contract",
        "",
        "- Treat `case_window_actions.local.tsv` as a local ops queue, not a client record.",
        "- Validate each row against the local context before copying anything into CRM.",
        "- Do not upload the workbook, context TSV, or action queue to any cloud service.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def compile_case_window_actions(
    *,
    workbook_path: Path,
    actions_path: Path,
    summary_path: Path,
) -> ActionCompileResult:
    """Compile approved manual-review rows into a local action queue."""
    workbook_rows = read_workbook(workbook_path)
    action_rows = build_actions(workbook_rows)
    write_actions(actions_path, action_rows)
    write_summary(
        summary_path=summary_path,
        workbook_path=workbook_path,
        actions_path=actions_path,
        workbook_rows=workbook_rows,
        action_rows=action_rows,
    )
    return ActionCompileResult(workbook_rows=workbook_rows, action_rows=action_rows)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile approved WhatsApp case-window review rows into local actions."
    )
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--actions", type=Path, default=DEFAULT_ACTIONS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = compile_case_window_actions(
            workbook_path=args.workbook,
            actions_path=args.actions,
            summary_path=args.summary,
        )
    except (FileNotFoundError, ValueError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    if args.json:
        json.dump(
            {
                "workbook_rows": len(result.workbook_rows),
                "action_rows": len(result.action_rows),
                "actions": str(args.actions),
                "summary": str(args.summary),
            },
            sys.stdout,
            sort_keys=True,
        )
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
