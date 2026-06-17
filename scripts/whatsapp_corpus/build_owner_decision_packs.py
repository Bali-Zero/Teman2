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

DEFAULT_OWNER_APPROVAL_DIR = Path("research/personal/wa-corpus/owner-approval-console")
DEFAULT_OWNER_DECISION_PACK_DIR = Path("research/personal/wa-corpus/owner-decision-packs")

DEFAULT_OWNER_APPROVAL_DB = DEFAULT_OWNER_APPROVAL_DIR / "owner_approval_console.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_OWNER_DECISION_PACK_DIR / "owner_decision_packs.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_OWNER_DECISION_PACK_DIR / "owner_decision_packs_summary.md"

EXPECTED_OWNER_APPROVAL_DB_NAME = "owner_approval_console.local.sqlite"


@dataclass(frozen=True)
class OwnerApprovalRow:
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
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OwnerDecisionPack:
    pack_id: str
    case_card_id: str
    pack_rank: int
    assigned_lane: str
    decision_type: str
    decision_priority: str
    owner_prompt_code: str
    pack_title: str
    risk_brief: str
    recommended_decision: str
    draft_action_type: str
    draft_action_status: str
    approval_status: str
    top_gap_code: str
    top_gap_category: str
    top_gap_severity: str
    resolution_gate: str
    owner_decision_required: bool
    pack_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OwnerDecisionPacksBuildResult:
    source_case_count: int
    owner_item_count: int
    pack_count: int
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


def read_source_metadata(db_path: Path) -> tuple[str, int, int]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_OWNER_APPROVAL_DB_NAME,
        label="Owner Approval Console",
    ) as conn:
        row = conn.execute(
            """
            SELECT generated_at_utc, source_case_count, owner_item_count
            FROM owner_approval_console_runs
            WHERE id = 1
            """
        ).fetchone()
    if row is None:
        return "unknown", 0, 0
    return (
        str(row["generated_at_utc"]),
        int(row["source_case_count"]),
        int(row["owner_item_count"]),
    )


def read_owner_approval_rows(db_path: Path) -> tuple[OwnerApprovalRow, ...]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_OWNER_APPROVAL_DB_NAME,
        label="Owner Approval Console",
    ) as conn:
        rows = conn.execute(
            """
            SELECT approval_id, case_card_id, approval_rank, assigned_lane,
                   primary_action, closure_status, decision_type,
                   decision_priority, owner_prompt_code,
                   recommended_owner_action, approval_status, top_gap_code,
                   top_gap_category, top_gap_severity, resolution_gate,
                   owner_decision_required, send_whatsapp, crm_mutation,
                   requires_human_approval
            FROM owner_approval_items
            ORDER BY approval_rank, case_card_id
            """
        ).fetchall()
    return tuple(
        OwnerApprovalRow(
            approval_id=str(row["approval_id"]),
            case_card_id=str(row["case_card_id"]),
            approval_rank=int(row["approval_rank"]),
            assigned_lane=str(row["assigned_lane"]),
            primary_action=str(row["primary_action"]),
            closure_status=str(row["closure_status"]),
            decision_type=str(row["decision_type"]),
            decision_priority=str(row["decision_priority"]),
            owner_prompt_code=str(row["owner_prompt_code"]),
            recommended_owner_action=str(row["recommended_owner_action"]),
            approval_status=str(row["approval_status"]),
            top_gap_code=str(row["top_gap_code"]),
            top_gap_category=str(row["top_gap_category"]),
            top_gap_severity=str(row["top_gap_severity"]),
            resolution_gate=str(row["resolution_gate"]),
            owner_decision_required=bool(row["owner_decision_required"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def _pack_title(decision_type: str) -> str:
    return {
        "approve_client_recovery_followup": "Client recovery follow-up approval",
        "approve_immigration_status_escalation": "Immigration status escalation approval",
        "approve_document_evidence_request": "Document evidence request approval",
        "approve_payment_reconciliation_review": "Payment reconciliation review approval",
    }.get(decision_type, "Owner case review approval")


def _risk_brief(row: OwnerApprovalRow) -> str:
    if row.decision_type == "approve_client_recovery_followup":
        return "Urgent client response gap requires owner-approved recovery follow-up."
    if row.decision_type == "approve_immigration_status_escalation":
        return "Urgent immigration status gap requires owner-approved escalation."
    if row.decision_type == "approve_document_evidence_request":
        return "Document evidence gap requires owner-approved evidence request."
    if row.decision_type == "approve_payment_reconciliation_review":
        return "Finance evidence gap requires owner-approved reconciliation review."
    return "Case gap requires owner-approved operational review."


def _recommended_decision(decision_type: str) -> str:
    return {
        "approve_client_recovery_followup": "approve_recovery_followup_after_review",
        "approve_immigration_status_escalation": "approve_status_escalation_after_review",
        "approve_document_evidence_request": "approve_document_request_after_review",
        "approve_payment_reconciliation_review": "approve_payment_review_after_review",
    }.get(decision_type, "approve_case_review_after_review")


def _draft_action_type(decision_type: str) -> str:
    return {
        "approve_client_recovery_followup": "owner_review_client_followup_draft",
        "approve_immigration_status_escalation": "owner_review_status_escalation_draft",
        "approve_document_evidence_request": "owner_review_document_request_draft",
        "approve_payment_reconciliation_review": "owner_review_payment_reconciliation_draft",
    }.get(decision_type, "owner_review_case_draft")


def build_packs(rows: Sequence[OwnerApprovalRow]) -> tuple[OwnerDecisionPack, ...]:
    packs: list[OwnerDecisionPack] = []
    for rank, row in enumerate(rows, start=1):
        payload = {
            "schema_version": "owner_decision_packs.v1",
            "privacy_mode": "local_only_owner_decision_pack_no_raw_text",
            "source_approval_rank": row.approval_rank,
            "source_approval_status": row.approval_status,
            "source_closure_status": row.closure_status,
            "source_owner_prompt_code": row.owner_prompt_code,
            "decision_type": row.decision_type,
            "decision_priority": row.decision_priority,
            "recommended_owner_action": row.recommended_owner_action,
            "recommended_decision": _recommended_decision(row.decision_type),
            "draft_action_type": _draft_action_type(row.decision_type),
            "draft_action_status": "draft_ready_for_owner_review",
            "owner_decision_required": True,
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        packs.append(
            OwnerDecisionPack(
                pack_id=f"owner-pack-{rank:06d}",
                case_card_id=row.case_card_id,
                pack_rank=rank,
                assigned_lane=row.assigned_lane,
                decision_type=row.decision_type,
                decision_priority=row.decision_priority,
                owner_prompt_code=row.owner_prompt_code,
                pack_title=_pack_title(row.decision_type),
                risk_brief=_risk_brief(row),
                recommended_decision=_recommended_decision(row.decision_type),
                draft_action_type=_draft_action_type(row.decision_type),
                draft_action_status="draft_ready_for_owner_review",
                approval_status=row.approval_status,
                top_gap_code=row.top_gap_code,
                top_gap_category=row.top_gap_category,
                top_gap_severity=row.top_gap_severity,
                resolution_gate=row.resolution_gate,
                owner_decision_required=True,
                pack_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(packs)


def write_packs_sqlite(
    output_db: Path,
    *,
    packs: Sequence[OwnerDecisionPack],
    source_case_count: int,
    owner_item_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS owner_decision_pack_runs;
            DROP TABLE IF EXISTS owner_decision_packs;

            CREATE TABLE owner_decision_pack_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_case_count INTEGER NOT NULL,
                owner_item_count INTEGER NOT NULL,
                pack_count INTEGER NOT NULL,
                urgent_pack_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE owner_decision_packs (
                pack_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                pack_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                owner_prompt_code TEXT NOT NULL,
                pack_title TEXT NOT NULL,
                risk_brief TEXT NOT NULL,
                recommended_decision TEXT NOT NULL,
                draft_action_type TEXT NOT NULL,
                draft_action_status TEXT NOT NULL,
                approval_status TEXT NOT NULL,
                top_gap_code TEXT NOT NULL,
                top_gap_category TEXT NOT NULL,
                top_gap_severity TEXT NOT NULL,
                resolution_gate TEXT NOT NULL,
                owner_decision_required INTEGER NOT NULL CHECK (owner_decision_required = 1),
                pack_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_owner_pack_rank ON owner_decision_packs(pack_rank);
            CREATE INDEX idx_owner_pack_lane ON owner_decision_packs(assigned_lane);
            CREATE INDEX idx_owner_pack_type ON owner_decision_packs(decision_type);
            CREATE INDEX idx_owner_pack_priority ON owner_decision_packs(decision_priority);
            CREATE INDEX idx_owner_pack_draft_action ON owner_decision_packs(draft_action_type);
            """
        )
        conn.execute(
            """
            INSERT INTO owner_decision_pack_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count,
                urgent_pack_count, send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                source_generated_at_utc,
                "local_only_owner_decision_pack_no_raw_text_no_send_no_crm_mutation",
                source_case_count,
                owner_item_count,
                len(packs),
                sum(1 for pack in packs if pack.decision_priority == "now"),
            ),
        )
        conn.executemany(
            """
            INSERT INTO owner_decision_packs (
                pack_id, case_card_id, pack_rank, assigned_lane, decision_type,
                decision_priority, owner_prompt_code, pack_title, risk_brief,
                recommended_decision, draft_action_type, draft_action_status,
                approval_status, top_gap_code, top_gap_category, top_gap_severity,
                resolution_gate, owner_decision_required, pack_payload_json,
                send_whatsapp, crm_mutation, requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    pack.pack_id,
                    pack.case_card_id,
                    pack.pack_rank,
                    pack.assigned_lane,
                    pack.decision_type,
                    pack.decision_priority,
                    pack.owner_prompt_code,
                    pack.pack_title,
                    pack.risk_brief,
                    pack.recommended_decision,
                    pack.draft_action_type,
                    pack.draft_action_status,
                    pack.approval_status,
                    pack.top_gap_code,
                    pack.top_gap_category,
                    pack.top_gap_severity,
                    pack.resolution_gate,
                    int(pack.owner_decision_required),
                    json.dumps(pack.pack_payload, ensure_ascii=False, sort_keys=True),
                    int(pack.send_whatsapp),
                    int(pack.crm_mutation),
                    int(pack.requires_human_approval),
                )
                for pack in packs
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
    packs: Sequence[OwnerDecisionPack],
    source_case_count: int,
    owner_item_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    decision_counts = Counter(pack.decision_type for pack in packs)
    lane_counts = Counter(pack.assigned_lane for pack in packs)
    priority_counts = Counter(pack.decision_priority for pack in packs)
    draft_counts = Counter(pack.draft_action_type for pack in packs)
    status_counts = Counter(pack.draft_action_status for pack in packs)
    approval_counts = Counter(pack.approval_status for pack in packs)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Owner Decision Packs Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source Owner Approval UTC: `{source_generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, judgment IDs, approval IDs, pack IDs, gap IDs, event IDs, inbox item IDs, or room item IDs.",
        "- Owner decision packs are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Source cases | {source_case_count} |",
        f"| Owner approval items | {owner_item_count} |",
        f"| Owner decision packs | {len(packs)} |",
        f"| Urgent owner packs | {sum(1 for pack in packs if pack.decision_priority == 'now')} |",
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
        *_counter_table("Draft Action Types", draft_counts),
        "",
        *_counter_table("Draft Action Status", status_counts),
        "",
        *_counter_table("Approval Status", approval_counts),
        "",
        "## Execution Contract",
        "",
        "- The Owner Decision Pack turns owner approval rows into readable decision packets.",
        "- It does not parse raw WhatsApp messages.",
        "- It does not call a cloud LLM.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- Owner approval remains mandatory before any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_owner_decision_packs(
    *,
    owner_approval_db: Path = DEFAULT_OWNER_APPROVAL_DB,
    output_dir: Path = DEFAULT_OWNER_DECISION_PACK_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    generated_at_utc: str | None = None,
) -> OwnerDecisionPacksBuildResult:
    """Build local-only owner decision packs from owner approval rows."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    generated = _format_utc(generated_at_utc)
    source_generated, source_case_count, owner_item_count = read_source_metadata(
        owner_approval_db
    )
    approval_rows = read_owner_approval_rows(owner_approval_db)
    packs = build_packs(approval_rows)
    source_case_total = source_case_count or len(approval_rows)
    owner_item_total = owner_item_count or len(approval_rows)
    write_packs_sqlite(
        output_db,
        packs=packs,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    write_summary(
        summary_path=summary_path,
        packs=packs,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    return OwnerDecisionPacksBuildResult(
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=len(packs),
        send_whatsapp_count=sum(1 for pack in packs if pack.send_whatsapp),
        crm_mutation_count=sum(1 for pack in packs if pack.crm_mutation),
        decision_type_counts=dict(Counter(pack.decision_type for pack in packs)),
        lane_counts=dict(Counter(pack.assigned_lane for pack in packs)),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara owner decision packs from owner approval rows."
    )
    parser.add_argument("--owner-approval-db", type=Path, default=DEFAULT_OWNER_APPROVAL_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OWNER_DECISION_PACK_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_owner_decision_packs(
            owner_approval_db=args.owner_approval_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Owner decision packs input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Owner decision packs run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Owner decision packs run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "crm_mutation_count": result.crm_mutation_count,
                    "owner_item_count": result.owner_item_count,
                    "pack_count": result.pack_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "source_case_count": result.source_case_count,
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Owner decision packs complete: "
            f"{result.pack_count} packs -> {result.output_db.name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
