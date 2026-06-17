from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

DEFAULT_NEXT_ACTION_DIR = Path("research/personal/wa-corpus/next-best-actions")
DEFAULT_OPERATOR_INBOX_DIR = Path("research/personal/wa-corpus/operator-action-inbox")
DEFAULT_NEXT_ACTION_DB = DEFAULT_NEXT_ACTION_DIR / "next_best_actions.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_OPERATOR_INBOX_DIR / "operator_action_inbox.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_OPERATOR_INBOX_DIR / "operator_action_inbox_summary.md"

EXPECTED_NEXT_ACTION_DB_NAME = "next_best_actions.local.sqlite"


@dataclass(frozen=True)
class NextBestActionRow:
    case_card_id: str
    action_rank: int
    action_code: str
    action_title: str
    reason_code: str
    urgency_score: int
    impact_score: int
    combined_score: int
    assigned_lane: str
    action_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OperatorInboxItem:
    inbox_item_id: str
    case_card_id: str
    queue_rank: int
    assigned_lane: str
    priority_label: str
    queue_bucket: str
    action_code: str
    action_title: str
    reason_code: str
    urgency_score: int
    impact_score: int
    combined_score: int
    operator_instruction: str
    approval_mode: str
    item_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OperatorActionInboxBuildResult:
    case_count: int
    candidate_action_count: int
    inbox_item_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    priority_counts: dict[str, int]
    lane_counts: dict[str, int]
    bucket_counts: dict[str, int]
    output_db: Path
    summary_path: Path


def _connect_next_best_actions(db_path: Path) -> sqlite3.Connection:
    if db_path.name != EXPECTED_NEXT_ACTION_DB_NAME:
        raise ValueError(f"Refusing to read unexpected Next Best Actions DB: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"Next Best Actions DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_ranked_actions(db_path: Path) -> tuple[NextBestActionRow, ...]:
    with _connect_next_best_actions(db_path) as conn:
        rows = conn.execute(
            """
            SELECT case_card_id, action_rank, action_code, action_title, reason_code,
                   urgency_score, impact_score, combined_score, assigned_lane,
                   action_payload_json, send_whatsapp, crm_mutation,
                   requires_human_approval
            FROM next_best_action_rankings
            ORDER BY case_card_id, action_rank
            """
        ).fetchall()
    return tuple(
        NextBestActionRow(
            case_card_id=str(row["case_card_id"]),
            action_rank=int(row["action_rank"]),
            action_code=str(row["action_code"]),
            action_title=str(row["action_title"]),
            reason_code=str(row["reason_code"]),
            urgency_score=int(row["urgency_score"]),
            impact_score=int(row["impact_score"]),
            combined_score=int(row["combined_score"]),
            assigned_lane=str(row["assigned_lane"]),
            action_payload=json.loads(str(row["action_payload_json"])),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def _priority_label(action: NextBestActionRow) -> str:
    if action.urgency_score >= 90 or action.combined_score >= 90:
        return "now"
    if action.urgency_score >= 65 or action.combined_score >= 75:
        return "today"
    return "next"


def _queue_bucket(action: NextBestActionRow, priority_label: str) -> str:
    if action.action_code == "crm_followup":
        return "follow_up_now" if priority_label == "now" else "follow_up_today"
    if action.action_code == "payment_reconcile":
        return "finance_now" if priority_label == "now" else "finance_today"
    if action.action_code == "document_chase":
        return "document_gap_now" if priority_label == "now" else "document_gap_today"
    if action.action_code == "immigration_status_check":
        return "status_check_now" if priority_label == "now" else "status_check_today"
    if action.action_code == "team_escalation":
        return "team_escalation_now" if priority_label == "now" else "team_escalation_today"
    return f"operator_review_{priority_label}"


def _operator_instruction(action: NextBestActionRow) -> str:
    instructions = {
        "crm_followup": (
            "Operator must review the CRM follow-up, prepare the client status draft, "
            "and wait for human approval before any send."
        ),
        "payment_reconcile": (
            "Operator must reconcile payment evidence, check the ledger, and request "
            "human approval before any client-facing update."
        ),
        "document_chase": (
            "Operator must review the missing-document checklist, draft the request, "
            "and wait for human approval before contacting the client."
        ),
        "immigration_status_check": (
            "Operator must verify immigration status, update the internal timeline, "
            "and request specialist confirmation before any reply."
        ),
        "team_escalation": (
            "Operator must escalate the case internally, capture the blocker, and wait "
            "for owner or specialist review."
        ),
    }
    return instructions.get(
        action.action_code,
        "Operator must review the case action, capture the next step, and wait for human approval.",
    )


def _priority_sort_value(priority_label: str) -> int:
    return {"now": 0, "today": 1, "next": 2}.get(priority_label, 9)


def build_inbox_items(actions: Sequence[NextBestActionRow]) -> tuple[OperatorInboxItem, ...]:
    grouped: dict[str, list[NextBestActionRow]] = defaultdict(list)
    for action in actions:
        grouped[action.case_card_id].append(action)

    provisional: list[tuple[NextBestActionRow, int, str, str]] = []
    for case_card_id in sorted(grouped):
        ranked = sorted(grouped[case_card_id], key=lambda item: item.action_rank)
        if not ranked:
            continue
        top_action = ranked[0]
        priority_label = _priority_label(top_action)
        provisional.append(
            (
                top_action,
                len(ranked),
                priority_label,
                _queue_bucket(top_action, priority_label),
            )
        )

    provisional.sort(
        key=lambda item: (
            _priority_sort_value(item[2]),
            -item[0].combined_score,
            -item[0].urgency_score,
            item[0].assigned_lane,
            item[0].action_code,
            item[0].case_card_id,
        )
    )

    items: list[OperatorInboxItem] = []
    for queue_rank, (action, candidate_action_count, priority_label, queue_bucket) in enumerate(
        provisional,
        start=1,
    ):
        payload = {
            "schema_version": "operator_action_inbox.v1",
            "privacy_mode": "local_only_operator_inbox_no_raw_text",
            "source_action_rank": action.action_rank,
            "candidate_action_count": candidate_action_count,
            "source_action_code": action.action_code,
            "source_reason_code": action.reason_code,
            "source_case_status": action.action_payload.get("source_case_status", "unknown"),
            "source_risk_level": action.action_payload.get("source_risk_level", "unknown"),
            "source_blocker_code": action.action_payload.get("source_blocker_code", "unknown"),
            "latest_movement": action.action_payload.get("latest_movement", "unknown"),
            "priority_label": priority_label,
            "queue_bucket": queue_bucket,
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        items.append(
            OperatorInboxItem(
                inbox_item_id=f"inbox-{action.case_card_id}",
                case_card_id=action.case_card_id,
                queue_rank=queue_rank,
                assigned_lane=action.assigned_lane,
                priority_label=priority_label,
                queue_bucket=queue_bucket,
                action_code=action.action_code,
                action_title=action.action_title,
                reason_code=action.reason_code,
                urgency_score=action.urgency_score,
                impact_score=action.impact_score,
                combined_score=action.combined_score,
                operator_instruction=_operator_instruction(action),
                approval_mode="human_review_required",
                item_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(items)


def write_inbox_sqlite(path: Path, items: Sequence[OperatorInboxItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE operator_action_inbox_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                case_count INTEGER NOT NULL,
                inbox_item_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE operator_action_inbox (
                inbox_item_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                queue_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                priority_label TEXT NOT NULL,
                queue_bucket TEXT NOT NULL,
                action_code TEXT NOT NULL,
                action_title TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                urgency_score INTEGER NOT NULL,
                impact_score INTEGER NOT NULL,
                combined_score INTEGER NOT NULL,
                operator_instruction TEXT NOT NULL,
                approval_mode TEXT NOT NULL,
                item_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_operator_action_inbox_rank ON operator_action_inbox(queue_rank);
            CREATE INDEX idx_operator_action_inbox_lane ON operator_action_inbox(assigned_lane);
            CREATE INDEX idx_operator_action_inbox_priority ON operator_action_inbox(priority_label);
            CREATE INDEX idx_operator_action_inbox_bucket ON operator_action_inbox(queue_bucket);
            """
        )
        conn.execute(
            """
            INSERT INTO operator_action_inbox_runs (
                id, generated_at_utc, privacy_mode, case_count, inbox_item_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, 0, 0)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "local_only_operator_action_inbox_no_raw_text_no_send_no_crm_mutation",
                len({item.case_card_id for item in items}),
                len(items),
            ),
        )
        conn.executemany(
            """
            INSERT INTO operator_action_inbox (
                inbox_item_id, case_card_id, queue_rank, assigned_lane,
                priority_label, queue_bucket, action_code, action_title,
                reason_code, urgency_score, impact_score, combined_score,
                operator_instruction, approval_mode, item_payload_json,
                send_whatsapp, crm_mutation, requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.inbox_item_id,
                    item.case_card_id,
                    item.queue_rank,
                    item.assigned_lane,
                    item.priority_label,
                    item.queue_bucket,
                    item.action_code,
                    item.action_title,
                    item.reason_code,
                    item.urgency_score,
                    item.impact_score,
                    item.combined_score,
                    item.operator_instruction,
                    item.approval_mode,
                    json.dumps(item.item_payload, ensure_ascii=False, sort_keys=True),
                    int(item.send_whatsapp),
                    int(item.crm_mutation),
                    int(item.requires_human_approval),
                )
                for item in items
            ],
        )
        conn.commit()


def _counter_table(title: str, counts: Counter[str]) -> list[str]:
    lines = [f"## {title}", "", "| Value | Count |", "|---|---:|"]
    if not counts:
        lines.append("| none | 0 |")
        return lines
    for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {value or 'unknown'} | {count} |")
    return lines


def write_summary(
    *,
    summary_path: Path,
    items: Sequence[OperatorInboxItem],
    candidate_action_count: int,
    generated_at_utc: str | None = None,
) -> None:
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    priority_counts = Counter(item.priority_label for item in items)
    bucket_counts = Counter(item.queue_bucket for item in items)
    lane_counts = Counter(item.assigned_lane for item in items)
    action_counts = Counter(item.action_code for item in items)
    reason_counts = Counter(item.reason_code for item in items)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Operator Action Inbox Summary",
        "",
        f"Generated UTC: `{generated}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, shadow IDs, or window IDs.",
        "- Operator inbox rows are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Inbox items | {len(items)} |",
        f"| Candidate actions reviewed | {candidate_action_count} |",
        "| Actions per inbox item | 1 top-ranked action |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Priority Labels", priority_counts),
        "",
        *_counter_table("Queue Buckets", bucket_counts),
        "",
        *_counter_table("Assigned Lanes", lane_counts),
        "",
        *_counter_table("Inbox Actions", action_counts),
        "",
        *_counter_table("Reason Codes", reason_counts),
        "",
        "## Execution Contract",
        "",
        "- The inbox selects the top ranked action per case for operator review.",
        "- It creates a local work queue; it does not execute any action.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- A human must approve any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_operator_action_inbox(
    *,
    next_best_actions_db: Path = DEFAULT_NEXT_ACTION_DB,
    output_dir: Path = DEFAULT_OPERATOR_INBOX_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
) -> OperatorActionInboxBuildResult:
    """Build a local-only operator inbox from top-ranked next best actions."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    actions = read_ranked_actions(next_best_actions_db)
    items = build_inbox_items(actions)
    write_inbox_sqlite(output_db, items)
    write_summary(
        summary_path=summary_path,
        items=items,
        candidate_action_count=len(actions),
    )
    return OperatorActionInboxBuildResult(
        case_count=len({action.case_card_id for action in actions}),
        candidate_action_count=len(actions),
        inbox_item_count=len(items),
        send_whatsapp_count=sum(1 for item in items if item.send_whatsapp),
        crm_mutation_count=sum(1 for item in items if item.crm_mutation),
        priority_counts=dict(Counter(item.priority_label for item in items)),
        lane_counts=dict(Counter(item.assigned_lane for item in items)),
        bucket_counts=dict(Counter(item.queue_bucket for item in items)),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a local-only Zantara Operator Action Inbox from next best actions."
    )
    parser.add_argument("--next-best-actions-db", type=Path, default=DEFAULT_NEXT_ACTION_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OPERATOR_INBOX_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_operator_action_inbox(
            next_best_actions_db=args.next_best_actions_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Operator action inbox input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Operator action inbox run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Operator action inbox run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "case_count": result.case_count,
                    "candidate_action_count": result.candidate_action_count,
                    "inbox_item_count": result.inbox_item_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "crm_mutation_count": result.crm_mutation_count,
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
