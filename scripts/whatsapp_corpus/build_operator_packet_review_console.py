from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

DEFAULT_OPERATOR_EXECUTION_PACKET_DIR = Path(
    "research/personal/wa-corpus/operator-execution-packets"
)
DEFAULT_OPERATOR_PACKET_REVIEW_CONSOLE_DIR = Path(
    "research/personal/wa-corpus/operator-packet-review-console"
)

DEFAULT_PACKETS_DB = (
    DEFAULT_OPERATOR_EXECUTION_PACKET_DIR
    / "operator_execution_packets.local.sqlite"
)
DEFAULT_OUTPUT_DB = (
    DEFAULT_OPERATOR_PACKET_REVIEW_CONSOLE_DIR
    / "operator_packet_review_console.local.sqlite"
)
DEFAULT_SUMMARY = (
    DEFAULT_OPERATOR_PACKET_REVIEW_CONSOLE_DIR
    / "operator_packet_review_console_summary.md"
)

EXPECTED_PACKETS_DB_NAME = "operator_execution_packets.local.sqlite"


@dataclass(frozen=True)
class OperatorExecutionPacketRow:
    packet_id: str
    work_order_id: str
    event_id: str
    entry_id: str
    route_id: str
    case_card_id: str
    brief_id: str
    pack_id: str
    packet_rank: int
    assigned_lane: str
    operator_lane: str
    decision_type: str
    decision_priority: str
    route_bucket: str
    owner_decision: str
    source_work_order_status: str
    packet_status: str
    packet_type: str
    packet_gate: str
    packet_action: str
    operator_instruction: str
    escalation_target: str
    decision_note: str
    source_work_order_hash: str
    packet_hash: str
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class ReviewConsolePolicy:
    review_state: str
    console_bucket: str
    review_priority: str
    visible_owner_action: str
    operator_action: str
    console_instruction: str
    review_gate: str
    action_lock: str


@dataclass(frozen=True)
class OperatorPacketReviewItem:
    review_item_id: str
    packet_id: str
    work_order_id: str
    event_id: str
    entry_id: str
    route_id: str
    case_card_id: str
    brief_id: str
    pack_id: str
    review_rank: int
    source_packet_rank: int
    assigned_lane: str
    operator_lane: str
    decision_type: str
    decision_priority: str
    route_bucket: str
    owner_decision: str
    packet_status: str
    packet_type: str
    packet_gate: str
    packet_action: str
    operator_instruction: str
    escalation_target: str
    review_state: str
    console_bucket: str
    review_priority: str
    visible_owner_action: str
    operator_action: str
    console_instruction: str
    review_gate: str
    action_lock: str
    decision_note: str
    source_packet_hash: str
    review_hash: str
    review_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OperatorPacketReviewConsoleBuildResult:
    source_case_count: int
    owner_item_count: int
    pack_count: int
    brief_count: int
    queue_item_count: int
    ledger_entry_count: int
    event_row_count: int
    work_order_count: int
    packet_count: int
    review_item_count: int
    owner_decision_item_count: int
    operator_ready_item_count: int
    deferred_item_count: int
    rejected_item_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    review_state_counts: dict[str, int]
    console_bucket_counts: dict[str, int]
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


def _hash_review_item(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_source_metadata(db_path: Path) -> tuple[str, int, int, int, int, int, int, int, int, int]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_PACKETS_DB_NAME,
        label="Operator Execution Packets",
    ) as conn:
        row = conn.execute(
            """
            SELECT generated_at_utc, source_case_count, owner_item_count,
                   pack_count, brief_count, queue_item_count, ledger_entry_count,
                   event_row_count, work_order_count, packet_count
            FROM operator_execution_packet_runs
            WHERE id = 1
            """
        ).fetchone()
    if row is None:
        return "unknown", 0, 0, 0, 0, 0, 0, 0, 0, 0
    return (
        str(row["generated_at_utc"]),
        int(row["source_case_count"]),
        int(row["owner_item_count"]),
        int(row["pack_count"]),
        int(row["brief_count"]),
        int(row["queue_item_count"]),
        int(row["ledger_entry_count"]),
        int(row["event_row_count"]),
        int(row["work_order_count"]),
        int(row["packet_count"]),
    )


def read_operator_packets(db_path: Path) -> tuple[OperatorExecutionPacketRow, ...]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_PACKETS_DB_NAME,
        label="Operator Execution Packets",
    ) as conn:
        rows = conn.execute(
            """
            SELECT packet_id, work_order_id, event_id, entry_id, route_id,
                   case_card_id, brief_id, pack_id, packet_rank, assigned_lane,
                   operator_lane, decision_type, decision_priority, route_bucket,
                   owner_decision, source_work_order_status, packet_status,
                   packet_type, packet_gate, packet_action, operator_instruction,
                   escalation_target, decision_note, source_work_order_hash,
                   packet_hash, send_whatsapp, crm_mutation,
                   requires_human_approval
            FROM operator_execution_packets
            ORDER BY packet_rank, case_card_id
            """
        ).fetchall()
    return tuple(
        OperatorExecutionPacketRow(
            packet_id=str(row["packet_id"]),
            work_order_id=str(row["work_order_id"]),
            event_id=str(row["event_id"]),
            entry_id=str(row["entry_id"]),
            route_id=str(row["route_id"]),
            case_card_id=str(row["case_card_id"]),
            brief_id=str(row["brief_id"]),
            pack_id=str(row["pack_id"]),
            packet_rank=int(row["packet_rank"]),
            assigned_lane=str(row["assigned_lane"]),
            operator_lane=str(row["operator_lane"]),
            decision_type=str(row["decision_type"]),
            decision_priority=str(row["decision_priority"]),
            route_bucket=str(row["route_bucket"]),
            owner_decision=str(row["owner_decision"]),
            source_work_order_status=str(row["source_work_order_status"]),
            packet_status=str(row["packet_status"]),
            packet_type=str(row["packet_type"]),
            packet_gate=str(row["packet_gate"]),
            packet_action=str(row["packet_action"]),
            operator_instruction=str(row["operator_instruction"]),
            escalation_target=str(row["escalation_target"]),
            decision_note=str(row["decision_note"]),
            source_work_order_hash=str(row["source_work_order_hash"]),
            packet_hash=str(row["packet_hash"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def derive_review_console_policy(packet: OperatorExecutionPacketRow) -> ReviewConsolePolicy:
    if packet.send_whatsapp or packet.crm_mutation:
        raise ValueError(f"Unsafe packet flags on {packet.packet_id}")
    if not packet.requires_human_approval:
        raise ValueError(f"Packet missing human approval gate: {packet.packet_id}")

    allowed_statuses = {
        "ready_for_operator_review",
        "blocked_awaiting_owner_decision",
        "deferred_owner_followup",
        "rejected_no_action",
    }
    if packet.packet_status not in allowed_statuses:
        raise ValueError(
            f"Unsupported packet status for {packet.packet_id}: {packet.packet_status}"
        )

    if (
        packet.packet_status == "blocked_awaiting_owner_decision"
        or packet.owner_decision == "pending"
    ):
        return ReviewConsolePolicy(
            review_state="waiting_owner_decision",
            console_bucket="owner_decision_inbox",
            review_priority="owner_now",
            visible_owner_action="capture_owner_decision",
            operator_action="no_operator_action",
            console_instruction="owner_must_approve_reject_or_defer_before_team_work",
            review_gate="owner_input_required",
            action_lock="locked_until_owner_decision",
        )
    if (
        packet.packet_status == "ready_for_operator_review"
        and packet.owner_decision == "approve"
    ):
        return ReviewConsolePolicy(
            review_state="ready_for_human_review",
            console_bucket="operator_review_queue",
            review_priority="operator_now",
            visible_owner_action="no_owner_action_required",
            operator_action="review_packet_before_send_or_crm",
            console_instruction="review_ready_packet_and_request_human_approval",
            review_gate="human_review_before_send_or_crm",
            action_lock="locked_until_human_review",
        )
    if packet.packet_status == "deferred_owner_followup" or packet.owner_decision == "defer":
        return ReviewConsolePolicy(
            review_state="deferred_owner_revisit",
            console_bucket="owner_revisit_queue",
            review_priority="owner_revisit",
            visible_owner_action="revisit_deferred_decision",
            operator_action="no_operator_action",
            console_instruction="owner_must_revisit_deferred_packet",
            review_gate="owner_revisit_required",
            action_lock="locked_until_owner_revisit",
        )
    if packet.packet_status == "rejected_no_action" or packet.owner_decision == "reject":
        return ReviewConsolePolicy(
            review_state="rejected_closed",
            console_bucket="closed_no_action",
            review_priority="closed",
            visible_owner_action="no_action",
            operator_action="no_operator_action",
            console_instruction="no_action_packet_rejected",
            review_gate="no_external_action",
            action_lock="closed_no_external_action",
        )
    raise ValueError(
        f"Unsupported packet status for {packet.packet_id}: {packet.packet_status}"
    )


def build_review_items(
    packets: Sequence[OperatorExecutionPacketRow],
) -> tuple[OperatorPacketReviewItem, ...]:
    items: list[OperatorPacketReviewItem] = []
    for rank, packet in enumerate(packets, start=1):
        policy = derive_review_console_policy(packet)
        payload = {
            "schema_version": "operator_packet_review_console.v1",
            "privacy_mode": "local_only_operator_packet_review_console_no_raw_text",
            "source_packet_rank": packet.packet_rank,
            "packet_status": packet.packet_status,
            "packet_type": packet.packet_type,
            "packet_gate": packet.packet_gate,
            "packet_action": packet.packet_action,
            "owner_decision": packet.owner_decision,
            "review_state": policy.review_state,
            "console_bucket": policy.console_bucket,
            "review_priority": policy.review_priority,
            "visible_owner_action": policy.visible_owner_action,
            "operator_action": policy.operator_action,
            "console_instruction": policy.console_instruction,
            "review_gate": policy.review_gate,
            "action_lock": policy.action_lock,
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        review_item_id = f"operator-packet-review-item-{rank:06d}"
        review_hash = _hash_review_item(
            {
                **payload,
                "review_item_id": review_item_id,
                "packet_id": packet.packet_id,
                "work_order_id": packet.work_order_id,
                "event_id": packet.event_id,
                "entry_id": packet.entry_id,
                "route_id": packet.route_id,
                "case_card_id": packet.case_card_id,
                "brief_id": packet.brief_id,
                "pack_id": packet.pack_id,
                "review_rank": rank,
                "source_packet_hash": packet.packet_hash,
            }
        )
        items.append(
            OperatorPacketReviewItem(
                review_item_id=review_item_id,
                packet_id=packet.packet_id,
                work_order_id=packet.work_order_id,
                event_id=packet.event_id,
                entry_id=packet.entry_id,
                route_id=packet.route_id,
                case_card_id=packet.case_card_id,
                brief_id=packet.brief_id,
                pack_id=packet.pack_id,
                review_rank=rank,
                source_packet_rank=packet.packet_rank,
                assigned_lane=packet.assigned_lane,
                operator_lane=packet.operator_lane,
                decision_type=packet.decision_type,
                decision_priority=packet.decision_priority,
                route_bucket=packet.route_bucket,
                owner_decision=packet.owner_decision,
                packet_status=packet.packet_status,
                packet_type=packet.packet_type,
                packet_gate=packet.packet_gate,
                packet_action=packet.packet_action,
                operator_instruction=packet.operator_instruction,
                escalation_target=packet.escalation_target,
                review_state=policy.review_state,
                console_bucket=policy.console_bucket,
                review_priority=policy.review_priority,
                visible_owner_action=policy.visible_owner_action,
                operator_action=policy.operator_action,
                console_instruction=policy.console_instruction,
                review_gate=policy.review_gate,
                action_lock=policy.action_lock,
                decision_note=packet.decision_note,
                source_packet_hash=packet.packet_hash,
                review_hash=review_hash,
                review_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(items)


def write_operator_packet_review_console_sqlite(
    output_db: Path,
    *,
    review_items: Sequence[OperatorPacketReviewItem],
    source_case_count: int,
    owner_item_count: int,
    pack_count: int,
    brief_count: int,
    queue_item_count: int,
    ledger_entry_count: int,
    event_row_count: int,
    work_order_count: int,
    packet_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    state_counts = Counter(item.review_state for item in review_items)
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS operator_packet_review_console_runs;
            DROP TABLE IF EXISTS operator_packet_review_items;

            CREATE TABLE operator_packet_review_console_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_case_count INTEGER NOT NULL,
                owner_item_count INTEGER NOT NULL,
                pack_count INTEGER NOT NULL,
                brief_count INTEGER NOT NULL,
                queue_item_count INTEGER NOT NULL,
                ledger_entry_count INTEGER NOT NULL,
                event_row_count INTEGER NOT NULL,
                work_order_count INTEGER NOT NULL,
                packet_count INTEGER NOT NULL,
                review_item_count INTEGER NOT NULL,
                owner_decision_item_count INTEGER NOT NULL,
                operator_ready_item_count INTEGER NOT NULL,
                deferred_item_count INTEGER NOT NULL,
                rejected_item_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE operator_packet_review_items (
                review_item_id TEXT PRIMARY KEY,
                packet_id TEXT NOT NULL,
                work_order_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                route_id TEXT NOT NULL,
                case_card_id TEXT NOT NULL,
                brief_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                review_rank INTEGER NOT NULL,
                source_packet_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                operator_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                route_bucket TEXT NOT NULL,
                owner_decision TEXT NOT NULL,
                packet_status TEXT NOT NULL,
                packet_type TEXT NOT NULL,
                packet_gate TEXT NOT NULL,
                packet_action TEXT NOT NULL,
                operator_instruction TEXT NOT NULL,
                escalation_target TEXT NOT NULL,
                review_state TEXT NOT NULL,
                console_bucket TEXT NOT NULL,
                review_priority TEXT NOT NULL,
                visible_owner_action TEXT NOT NULL,
                operator_action TEXT NOT NULL,
                console_instruction TEXT NOT NULL,
                review_gate TEXT NOT NULL,
                action_lock TEXT NOT NULL,
                decision_note TEXT NOT NULL,
                source_packet_hash TEXT NOT NULL,
                review_hash TEXT NOT NULL UNIQUE,
                review_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_operator_packet_review_rank
                ON operator_packet_review_items(review_rank);
            CREATE INDEX idx_operator_packet_review_state
                ON operator_packet_review_items(review_state);
            CREATE INDEX idx_operator_packet_review_bucket
                ON operator_packet_review_items(console_bucket);
            CREATE INDEX idx_operator_packet_review_lane
                ON operator_packet_review_items(operator_lane);
            CREATE INDEX idx_operator_packet_review_packet
                ON operator_packet_review_items(packet_id);
            """
        )
        conn.execute(
            """
            INSERT INTO operator_packet_review_console_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count, brief_count,
                queue_item_count, ledger_entry_count, event_row_count,
                work_order_count, packet_count, review_item_count,
                owner_decision_item_count, operator_ready_item_count,
                deferred_item_count, rejected_item_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                source_generated_at_utc,
                "local_only_operator_packet_review_console_no_raw_text_no_send_no_crm_mutation",
                source_case_count,
                owner_item_count,
                pack_count,
                brief_count,
                queue_item_count,
                ledger_entry_count,
                event_row_count,
                work_order_count,
                packet_count,
                len(review_items),
                state_counts.get("waiting_owner_decision", 0),
                state_counts.get("ready_for_human_review", 0),
                state_counts.get("deferred_owner_revisit", 0),
                state_counts.get("rejected_closed", 0),
            ),
        )
        conn.executemany(
            """
            INSERT INTO operator_packet_review_items (
                review_item_id, packet_id, work_order_id, event_id, entry_id,
                route_id, case_card_id, brief_id, pack_id, review_rank,
                source_packet_rank, assigned_lane, operator_lane, decision_type,
                decision_priority, route_bucket, owner_decision, packet_status,
                packet_type, packet_gate, packet_action, operator_instruction,
                escalation_target, review_state, console_bucket, review_priority,
                visible_owner_action, operator_action, console_instruction,
                review_gate, action_lock, decision_note, source_packet_hash,
                review_hash, review_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.review_item_id,
                    item.packet_id,
                    item.work_order_id,
                    item.event_id,
                    item.entry_id,
                    item.route_id,
                    item.case_card_id,
                    item.brief_id,
                    item.pack_id,
                    item.review_rank,
                    item.source_packet_rank,
                    item.assigned_lane,
                    item.operator_lane,
                    item.decision_type,
                    item.decision_priority,
                    item.route_bucket,
                    item.owner_decision,
                    item.packet_status,
                    item.packet_type,
                    item.packet_gate,
                    item.packet_action,
                    item.operator_instruction,
                    item.escalation_target,
                    item.review_state,
                    item.console_bucket,
                    item.review_priority,
                    item.visible_owner_action,
                    item.operator_action,
                    item.console_instruction,
                    item.review_gate,
                    item.action_lock,
                    item.decision_note,
                    item.source_packet_hash,
                    item.review_hash,
                    json.dumps(item.review_payload, ensure_ascii=False, sort_keys=True),
                    int(item.send_whatsapp),
                    int(item.crm_mutation),
                    int(item.requires_human_approval),
                )
                for item in review_items
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
    review_items: Sequence[OperatorPacketReviewItem],
    source_case_count: int,
    owner_item_count: int,
    pack_count: int,
    brief_count: int,
    queue_item_count: int,
    ledger_entry_count: int,
    event_row_count: int,
    work_order_count: int,
    packet_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    state_counts = Counter(item.review_state for item in review_items)
    bucket_counts = Counter(item.console_bucket for item in review_items)
    priority_counts = Counter(item.review_priority for item in review_items)
    lane_counts = Counter(item.operator_lane for item in review_items)
    owner_action_counts = Counter(item.visible_owner_action for item in review_items)
    operator_action_counts = Counter(item.operator_action for item in review_items)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Operator Packet Review Console Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source Operator Execution Packets UTC: `{source_generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, judgment IDs, approval IDs, pack IDs, brief IDs, route IDs, ledger entry IDs, event IDs, work order IDs, packet IDs, review item IDs, inbox item IDs, or room item IDs.",
        "- Operator packet review console artifacts are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Source cases | {source_case_count} |",
        f"| Owner approval items | {owner_item_count} |",
        f"| Owner decision packs | {pack_count} |",
        f"| Owner briefs | {brief_count} |",
        f"| Queue items | {queue_item_count} |",
        f"| Ledger entries | {ledger_entry_count} |",
        f"| Event rows | {event_row_count} |",
        f"| Work orders | {work_order_count} |",
        f"| Operator packets | {packet_count} |",
        f"| Review items | {len(review_items)} |",
        f"| Owner decision items | {state_counts.get('waiting_owner_decision', 0)} |",
        f"| Operator-ready items | {state_counts.get('ready_for_human_review', 0)} |",
        f"| Deferred items | {state_counts.get('deferred_owner_revisit', 0)} |",
        f"| Rejected items | {state_counts.get('rejected_closed', 0)} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Review States", state_counts),
        "",
        *_counter_table("Console Buckets", bucket_counts),
        "",
        *_counter_table("Review Priorities", priority_counts),
        "",
        *_counter_table("Operator Lanes", lane_counts),
        "",
        *_counter_table("Visible Owner Actions", owner_action_counts),
        "",
        *_counter_table("Operator Actions", operator_action_counts),
        "",
        "## Execution Contract",
        "",
        "- The review console is an internal operator and owner reading surface only.",
        "- Waiting-owner items require explicit owner approve, reject, or defer before team work.",
        "- Operator-ready items remain locked until human review before send or CRM mutation.",
        "- Deferred items remain locked until owner revisit.",
        "- Rejected items are closed with no external action.",
        "- It does not parse raw WhatsApp messages.",
        "- It does not call a cloud LLM.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- Human approval remains mandatory before any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_operator_packet_review_console(
    *,
    packets_db: Path = DEFAULT_PACKETS_DB,
    output_dir: Path = DEFAULT_OPERATOR_PACKET_REVIEW_CONSOLE_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    generated_at_utc: str | None = None,
) -> OperatorPacketReviewConsoleBuildResult:
    """Build local-only review console rows from operator execution packets."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    generated = _format_utc(generated_at_utc)
    (
        source_generated,
        source_case_count,
        owner_item_count,
        pack_count,
        brief_count,
        queue_item_count,
        ledger_entry_count,
        event_row_count,
        work_order_count,
        source_packet_count,
    ) = read_source_metadata(packets_db)
    packets = read_operator_packets(packets_db)
    review_items = build_review_items(packets)
    source_case_total = source_case_count or len(review_items)
    owner_item_total = owner_item_count or len(review_items)
    pack_total = pack_count or len(review_items)
    brief_total = brief_count or len(review_items)
    queue_total = queue_item_count or len(review_items)
    ledger_total = ledger_entry_count or len(review_items)
    event_row_total = event_row_count or len(review_items)
    work_order_total = work_order_count or len(review_items)
    packet_total = source_packet_count or len(packets)
    write_operator_packet_review_console_sqlite(
        output_db,
        review_items=review_items,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        ledger_entry_count=ledger_total,
        event_row_count=event_row_total,
        work_order_count=work_order_total,
        packet_count=packet_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    write_summary(
        summary_path=summary_path,
        review_items=review_items,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        ledger_entry_count=ledger_total,
        event_row_count=event_row_total,
        work_order_count=work_order_total,
        packet_count=packet_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    state_counts = Counter(item.review_state for item in review_items)
    bucket_counts = Counter(item.console_bucket for item in review_items)
    return OperatorPacketReviewConsoleBuildResult(
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        ledger_entry_count=ledger_total,
        event_row_count=event_row_total,
        work_order_count=work_order_total,
        packet_count=packet_total,
        review_item_count=len(review_items),
        owner_decision_item_count=state_counts.get("waiting_owner_decision", 0),
        operator_ready_item_count=state_counts.get("ready_for_human_review", 0),
        deferred_item_count=state_counts.get("deferred_owner_revisit", 0),
        rejected_item_count=state_counts.get("rejected_closed", 0),
        send_whatsapp_count=sum(1 for item in review_items if item.send_whatsapp),
        crm_mutation_count=sum(1 for item in review_items if item.crm_mutation),
        review_state_counts=dict(state_counts),
        console_bucket_counts=dict(bucket_counts),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara operator packet review console."
    )
    parser.add_argument("--packets-db", type=Path, default=DEFAULT_PACKETS_DB)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OPERATOR_PACKET_REVIEW_CONSOLE_DIR,
    )
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_operator_packet_review_console(
            packets_db=args.packets_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Operator packet review console input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Operator packet review console run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Operator packet review console run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "brief_count": result.brief_count,
                    "crm_mutation_count": result.crm_mutation_count,
                    "deferred_item_count": result.deferred_item_count,
                    "event_row_count": result.event_row_count,
                    "ledger_entry_count": result.ledger_entry_count,
                    "operator_ready_item_count": result.operator_ready_item_count,
                    "owner_decision_item_count": result.owner_decision_item_count,
                    "owner_item_count": result.owner_item_count,
                    "pack_count": result.pack_count,
                    "packet_count": result.packet_count,
                    "queue_item_count": result.queue_item_count,
                    "rejected_item_count": result.rejected_item_count,
                    "review_item_count": result.review_item_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "source_case_count": result.source_case_count,
                    "work_order_count": result.work_order_count,
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Operator packet review console complete: "
            f"{result.review_item_count} review items -> {result.output_db.name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
