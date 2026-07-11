from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

DEFAULT_CASE_CLOSURE_DIR = Path("research/personal/wa-corpus/case-closure-judge")
DEFAULT_OWNER_APPROVAL_DIR = Path("research/personal/wa-corpus/owner-approval-console")

DEFAULT_CASE_CLOSURE_DB = DEFAULT_CASE_CLOSURE_DIR / "case_closure_judge.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_OWNER_APPROVAL_DIR / "owner_approval_console.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_OWNER_APPROVAL_DIR / "owner_approval_console_summary.md"

EXPECTED_CASE_CLOSURE_DB_NAME = "case_closure_judge.local.sqlite"


@dataclass(frozen=True)
class CaseClosureJudgmentRow:
    judgment_id: str
    case_card_id: str
    judgment_rank: int
    assigned_lane: str
    primary_action: str
    closure_status: str
    closure_blocker_count: int
    top_gap_code: str
    top_gap_category: str
    top_gap_severity: str
    resolution_gate: str
    owner_attention_required: bool
    operator_evidence_required: bool
    lane_review_required: bool
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OwnerApprovalItem:
    approval_id: str
    case_card_id: str
    approval_rank: int
    assigned_lane: str
    primary_action: str
    closure_status: str
    decision_type: str
    decision_priority: str
    owner_prompt_code: str
    recommended_owner_action: str
    approval_status: str
    top_gap_code: str
    top_gap_category: str
    top_gap_severity: str
    resolution_gate: str
    owner_decision_required: bool
    approval_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OwnerApprovalConsoleBuildResult:
    source_case_count: int
    owner_item_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    decision_type_counts: dict[str, int]
    lane_counts: dict[str, int]
    output_db: Path
    summary_path: Path


def _format_utc(value: str | None = None) -> str:
    if value is not None:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect_ro(db_path: Path, *, expected_name: str, label: str) -> sqlite3.Connection:
    if db_path.name != expected_name:
        raise ValueError(f"Refusing to read unexpected {label} DB: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"{label} DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_source_metadata(db_path: Path) -> tuple[str, int]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_CASE_CLOSURE_DB_NAME,
        label="Case Closure",
    ) as conn:
        row = conn.execute(
            "SELECT generated_at_utc, case_count FROM case_closure_judge_runs WHERE id = 1"
        ).fetchone()
    if row is None:
        return "unknown", 0
    return str(row["generated_at_utc"]), int(row["case_count"])


def read_case_closure_judgments(db_path: Path) -> tuple[CaseClosureJudgmentRow, ...]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_CASE_CLOSURE_DB_NAME,
        label="Case Closure",
    ) as conn:
        rows = conn.execute(
            """
            SELECT judgment_id, case_card_id, judgment_rank, assigned_lane,
                   primary_action, closure_status, closure_blocker_count,
                   top_gap_code, top_gap_category, top_gap_severity,
                   resolution_gate, owner_attention_required,
                   operator_evidence_required, lane_review_required,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM case_closure_judgments
            ORDER BY judgment_rank, case_card_id
            """
        ).fetchall()
    return tuple(
        CaseClosureJudgmentRow(
            judgment_id=str(row["judgment_id"]),
            case_card_id=str(row["case_card_id"]),
            judgment_rank=int(row["judgment_rank"]),
            assigned_lane=str(row["assigned_lane"]),
            primary_action=str(row["primary_action"]),
            closure_status=str(row["closure_status"]),
            closure_blocker_count=int(row["closure_blocker_count"]),
            top_gap_code=str(row["top_gap_code"]),
            top_gap_category=str(row["top_gap_category"]),
            top_gap_severity=str(row["top_gap_severity"]),
            resolution_gate=str(row["resolution_gate"]),
            owner_attention_required=bool(row["owner_attention_required"]),
            operator_evidence_required=bool(row["operator_evidence_required"]),
            lane_review_required=bool(row["lane_review_required"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def _decision_type(row: CaseClosureJudgmentRow) -> str:
    if row.primary_action == "crm_followup" or row.top_gap_category == "client_response":
        return "approve_client_recovery_followup"
    if row.primary_action == "immigration_status_check" or row.top_gap_category == "status":
        return "approve_immigration_status_escalation"
    if row.primary_action == "document_chase" or row.top_gap_category == "document":
        return "approve_document_evidence_request"
    if row.primary_action == "payment_reconcile" or row.top_gap_category == "finance":
        return "approve_payment_reconciliation_review"
    return "approve_owner_case_review"


def _decision_priority(row: CaseClosureJudgmentRow) -> str:
    if row.top_gap_severity == "urgent":
        return "now"
    if row.top_gap_severity == "high":
        return "today"
    return "review"


def _owner_prompt_code(decision_type: str) -> str:
    return {
        "approve_client_recovery_followup": "owner_client_recovery_followup",
        "approve_immigration_status_escalation": "owner_immigration_status_escalation",
        "approve_document_evidence_request": "owner_document_evidence_request",
        "approve_payment_reconciliation_review": "owner_payment_reconciliation_review",
    }.get(decision_type, "owner_case_review")


def _recommended_owner_action(decision_type: str) -> str:
    return {
        "approve_client_recovery_followup": (
            "Review and approve the client recovery follow-up before any message is sent."
        ),
        "approve_immigration_status_escalation": (
            "Review and approve the immigration status escalation before any message is sent."
        ),
        "approve_document_evidence_request": (
            "Review and approve the document evidence request before any message is sent."
        ),
        "approve_payment_reconciliation_review": (
            "Review and approve the payment reconciliation review before any message is sent."
        ),
    }.get(
        decision_type,
        "Review and approve the owner case decision before any message is sent.",
    )


def build_owner_items(
    judgments: Sequence[CaseClosureJudgmentRow],
) -> tuple[OwnerApprovalItem, ...]:
    owner_rows = [row for row in judgments if row.owner_attention_required]
    items: list[OwnerApprovalItem] = []
    for rank, row in enumerate(owner_rows, start=1):
        decision_type = _decision_type(row)
        owner_prompt_code = _owner_prompt_code(decision_type)
        recommended_action = _recommended_owner_action(decision_type)
        payload = {
            "schema_version": "owner_approval_console.v1",
            "privacy_mode": "local_only_owner_approval_no_raw_text",
            "source_closure_status": row.closure_status,
            "source_judgment_rank": row.judgment_rank,
            "decision_type": decision_type,
            "decision_priority": _decision_priority(row),
            "owner_prompt_code": owner_prompt_code,
            "approval_status": "pending_owner_review",
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        items.append(
            OwnerApprovalItem(
                approval_id=f"owner-approval-{rank:06d}",
                case_card_id=row.case_card_id,
                approval_rank=rank,
                assigned_lane=row.assigned_lane,
                primary_action=row.primary_action,
                closure_status=row.closure_status,
                decision_type=decision_type,
                decision_priority=_decision_priority(row),
                owner_prompt_code=owner_prompt_code,
                recommended_owner_action=recommended_action,
                approval_status="pending_owner_review",
                top_gap_code=row.top_gap_code,
                top_gap_category=row.top_gap_category,
                top_gap_severity=row.top_gap_severity,
                resolution_gate=row.resolution_gate,
                owner_decision_required=True,
                approval_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(items)


def write_owner_approval_sqlite(
    output_db: Path,
    *,
    items: Sequence[OwnerApprovalItem],
    source_case_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS owner_approval_console_runs;
            DROP TABLE IF EXISTS owner_approval_items;

            CREATE TABLE owner_approval_console_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_case_count INTEGER NOT NULL,
                owner_item_count INTEGER NOT NULL,
                urgent_item_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE owner_approval_items (
                approval_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                approval_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                primary_action TEXT NOT NULL,
                closure_status TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                owner_prompt_code TEXT NOT NULL,
                recommended_owner_action TEXT NOT NULL,
                approval_status TEXT NOT NULL,
                top_gap_code TEXT NOT NULL,
                top_gap_category TEXT NOT NULL,
                top_gap_severity TEXT NOT NULL,
                resolution_gate TEXT NOT NULL,
                owner_decision_required INTEGER NOT NULL CHECK (owner_decision_required = 1),
                approval_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_owner_approval_rank ON owner_approval_items(approval_rank);
            CREATE INDEX idx_owner_approval_lane ON owner_approval_items(assigned_lane);
            CREATE INDEX idx_owner_approval_type ON owner_approval_items(decision_type);
            CREATE INDEX idx_owner_approval_priority ON owner_approval_items(decision_priority);
            """
        )
        conn.execute(
            """
            INSERT INTO owner_approval_console_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, urgent_item_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                source_generated_at_utc,
                "local_only_owner_approval_no_raw_text_no_send_no_crm_mutation",
                source_case_count,
                len(items),
                sum(1 for item in items if item.decision_priority == "now"),
            ),
        )
        conn.executemany(
            """
            INSERT INTO owner_approval_items (
                approval_id, case_card_id, approval_rank, assigned_lane,
                primary_action, closure_status, decision_type, decision_priority,
                owner_prompt_code, recommended_owner_action, approval_status,
                top_gap_code, top_gap_category, top_gap_severity, resolution_gate,
                owner_decision_required, approval_payload_json, send_whatsapp,
                crm_mutation, requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.approval_id,
                    item.case_card_id,
                    item.approval_rank,
                    item.assigned_lane,
                    item.primary_action,
                    item.closure_status,
                    item.decision_type,
                    item.decision_priority,
                    item.owner_prompt_code,
                    item.recommended_owner_action,
                    item.approval_status,
                    item.top_gap_code,
                    item.top_gap_category,
                    item.top_gap_severity,
                    item.resolution_gate,
                    int(item.owner_decision_required),
                    json.dumps(item.approval_payload, ensure_ascii=False, sort_keys=True),
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
    items: Sequence[OwnerApprovalItem],
    source_case_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    decision_counts = Counter(item.decision_type for item in items)
    lane_counts = Counter(item.assigned_lane for item in items)
    priority_counts = Counter(item.decision_priority for item in items)
    action_counts = Counter(item.primary_action for item in items)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Owner Approval Console Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source Case Closure UTC: `{source_generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, judgment IDs, approval IDs, gap IDs, event IDs, inbox item IDs, or room item IDs.",
        "- Owner approval rows are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Source cases judged | {source_case_count} |",
        f"| Owner approval items | {len(items)} |",
        f"| Urgent owner items | {sum(1 for item in items if item.decision_priority == 'now')} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Decision Types", decision_counts),
        "",
        *_counter_table("Decision Priorities", priority_counts),
        "",
        *_counter_table("Assigned Lanes", lane_counts),
        "",
        *_counter_table("Primary Actions", action_counts),
        "",
        "## Execution Contract",
        "",
        "- The Owner Approval Console filters case closure judgments down to owner-only decisions.",
        "- It does not parse raw WhatsApp messages.",
        "- It does not call a cloud LLM.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- Owner approval remains mandatory before any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_owner_approval_console(
    *,
    case_closure_db: Path = DEFAULT_CASE_CLOSURE_DB,
    output_dir: Path = DEFAULT_OWNER_APPROVAL_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    generated_at_utc: str | None = None,
) -> OwnerApprovalConsoleBuildResult:
    """Build local-only owner approval items from case closure judgments."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    generated = _format_utc(generated_at_utc)
    source_generated, source_case_count = read_source_metadata(case_closure_db)
    judgments = read_case_closure_judgments(case_closure_db)
    items = build_owner_items(judgments)
    write_owner_approval_sqlite(
        output_db,
        items=items,
        source_case_count=source_case_count or len(judgments),
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    write_summary(
        summary_path=summary_path,
        items=items,
        source_case_count=source_case_count or len(judgments),
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    return OwnerApprovalConsoleBuildResult(
        source_case_count=source_case_count or len(judgments),
        owner_item_count=len(items),
        send_whatsapp_count=sum(1 for item in items if item.send_whatsapp),
        crm_mutation_count=sum(1 for item in items if item.crm_mutation),
        decision_type_counts=dict(Counter(item.decision_type for item in items)),
        lane_counts=dict(Counter(item.assigned_lane for item in items)),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara owner approval console from case closure judgments."
    )
    parser.add_argument("--case-closure-db", type=Path, default=DEFAULT_CASE_CLOSURE_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OWNER_APPROVAL_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_owner_approval_console(
            case_closure_db=args.case_closure_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Owner approval console input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Owner approval console run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Owner approval console run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "crm_mutation_count": result.crm_mutation_count,
                    "owner_item_count": result.owner_item_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "source_case_count": result.source_case_count,
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Owner approval console complete: "
            f"{result.owner_item_count} items -> {result.output_db.name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
