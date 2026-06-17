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

DEFAULT_POST_DECISION_WORK_ORDER_DIR = Path(
    "research/personal/wa-corpus/post-decision-work-orders"
)
DEFAULT_OPERATOR_EXECUTION_PACKET_DIR = Path(
    "research/personal/wa-corpus/operator-execution-packets"
)

DEFAULT_WORK_ORDERS_DB = (
    DEFAULT_POST_DECISION_WORK_ORDER_DIR
    / "post_decision_work_order_queue.local.sqlite"
)
DEFAULT_OUTPUT_DB = (
    DEFAULT_OPERATOR_EXECUTION_PACKET_DIR
    / "operator_execution_packets.local.sqlite"
)
DEFAULT_SUMMARY = (
    DEFAULT_OPERATOR_EXECUTION_PACKET_DIR
    / "operator_execution_packets_summary.md"
)

EXPECTED_WORK_ORDERS_DB_NAME = "post_decision_work_order_queue.local.sqlite"


@dataclass(frozen=True)
class PostDecisionWorkOrderRow:
    work_order_id: str
    event_id: str
    entry_id: str
    route_id: str
    case_card_id: str
    brief_id: str
    pack_id: str
    work_order_rank: int
    assigned_lane: str
    decision_type: str
    decision_priority: str
    route_bucket: str
    owner_decision: str
    source_capture_status: str
    work_order_status: str
    work_order_type: str
    execution_gate: str
    next_actor: str
    action_intent: str
    decision_effect: str
    decision_note: str
    source_event_hash: str
    work_order_hash: str
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OperatorPacketPolicy:
    packet_status: str
    packet_type: str
    operator_lane: str
    packet_gate: str
    packet_action: str
    operator_instruction: str
    escalation_target: str


@dataclass(frozen=True)
class OperatorExecutionPacket:
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
    packet_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OperatorExecutionPacketsBuildResult:
    source_case_count: int
    owner_item_count: int
    pack_count: int
    brief_count: int
    queue_item_count: int
    ledger_entry_count: int
    event_row_count: int
    work_order_count: int
    packet_count: int
    ready_packet_count: int
    blocked_packet_count: int
    deferred_packet_count: int
    rejected_packet_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    packet_status_counts: dict[str, int]
    operator_lane_counts: dict[str, int]
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


def _hash_packet(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_source_metadata(db_path: Path) -> tuple[str, int, int, int, int, int, int, int, int]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_WORK_ORDERS_DB_NAME,
        label="Post-Decision Work Order Queue",
    ) as conn:
        row = conn.execute(
            """
            SELECT generated_at_utc, source_case_count, owner_item_count,
                   pack_count, brief_count, queue_item_count, ledger_entry_count,
                   event_row_count, work_order_count
            FROM post_decision_work_order_runs
            WHERE id = 1
            """
        ).fetchone()
    if row is None:
        return "unknown", 0, 0, 0, 0, 0, 0, 0, 0
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
    )


def read_work_orders(db_path: Path) -> tuple[PostDecisionWorkOrderRow, ...]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_WORK_ORDERS_DB_NAME,
        label="Post-Decision Work Order Queue",
    ) as conn:
        rows = conn.execute(
            """
            SELECT work_order_id, event_id, entry_id, route_id, case_card_id,
                   brief_id, pack_id, work_order_rank, assigned_lane, decision_type,
                   decision_priority, route_bucket, owner_decision,
                   source_capture_status, work_order_status, work_order_type,
                   execution_gate, next_actor, action_intent, decision_effect,
                   decision_note, source_event_hash, work_order_hash,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM post_decision_work_orders
            ORDER BY work_order_rank, case_card_id
            """
        ).fetchall()
    return tuple(
        PostDecisionWorkOrderRow(
            work_order_id=str(row["work_order_id"]),
            event_id=str(row["event_id"]),
            entry_id=str(row["entry_id"]),
            route_id=str(row["route_id"]),
            case_card_id=str(row["case_card_id"]),
            brief_id=str(row["brief_id"]),
            pack_id=str(row["pack_id"]),
            work_order_rank=int(row["work_order_rank"]),
            assigned_lane=str(row["assigned_lane"]),
            decision_type=str(row["decision_type"]),
            decision_priority=str(row["decision_priority"]),
            route_bucket=str(row["route_bucket"]),
            owner_decision=str(row["owner_decision"]),
            source_capture_status=str(row["source_capture_status"]),
            work_order_status=str(row["work_order_status"]),
            work_order_type=str(row["work_order_type"]),
            execution_gate=str(row["execution_gate"]),
            next_actor=str(row["next_actor"]),
            action_intent=str(row["action_intent"]),
            decision_effect=str(row["decision_effect"]),
            decision_note=str(row["decision_note"]),
            source_event_hash=str(row["source_event_hash"]),
            work_order_hash=str(row["work_order_hash"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def _approved_packet_type_and_instruction(order: PostDecisionWorkOrderRow) -> tuple[str, str]:
    if (
        order.action_intent == "prepare_client_recovery_followup_for_human_review"
        or order.decision_type == "approve_client_recovery_followup"
    ):
        return (
            "client_recovery_followup_packet",
            "review_client_recovery_followup_before_any_send",
        )
    if (
        order.action_intent == "prepare_immigration_status_escalation_for_human_review"
        or order.decision_type == "approve_immigration_status_escalation"
    ):
        return (
            "immigration_status_escalation_packet",
            "review_immigration_status_escalation_before_any_send",
        )
    return (
        "approved_operator_packet",
        "review_owner_approved_action_before_execution",
    )


def derive_packet_policy(order: PostDecisionWorkOrderRow) -> OperatorPacketPolicy:
    if order.send_whatsapp or order.crm_mutation:
        raise ValueError(f"Unsafe work order flags on {order.work_order_id}")
    if not order.requires_human_approval:
        raise ValueError(f"Work order missing human approval gate: {order.work_order_id}")

    allowed_statuses = {
        "ready_for_operator_review",
        "blocked_awaiting_owner_decision",
        "deferred_owner_followup",
        "rejected_no_action",
    }
    if order.work_order_status not in allowed_statuses:
        raise ValueError(
            f"Unsupported work order status for {order.work_order_id}: "
            f"{order.work_order_status}"
        )

    if (
        order.work_order_status == "ready_for_operator_review"
        and order.owner_decision == "approve"
    ):
        packet_type, instruction = _approved_packet_type_and_instruction(order)
        operator_lane = order.next_actor if order.next_actor != "owner" else order.assigned_lane
        return OperatorPacketPolicy(
            packet_status="ready_for_operator_review",
            packet_type=packet_type,
            operator_lane=operator_lane,
            packet_gate="human_review_before_send_or_crm",
            packet_action=order.action_intent,
            operator_instruction=instruction,
            escalation_target="owner",
        )
    if (
        order.work_order_status == "blocked_awaiting_owner_decision"
        or order.owner_decision == "pending"
    ):
        return OperatorPacketPolicy(
            packet_status="blocked_awaiting_owner_decision",
            packet_type="owner_decision_required_packet",
            operator_lane="owner",
            packet_gate="owner_input_required",
            packet_action="wait_for_owner_decision",
            operator_instruction="no_operator_execution_until_owner_decides",
            escalation_target="owner",
        )
    if order.work_order_status == "deferred_owner_followup" or order.owner_decision == "defer":
        return OperatorPacketPolicy(
            packet_status="deferred_owner_followup",
            packet_type="owner_deferred_packet",
            operator_lane="owner",
            packet_gate="owner_revisit_required",
            packet_action="schedule_owner_revisit",
            operator_instruction="hold_operator_execution_until_owner_revisits",
            escalation_target="owner",
        )
    if order.work_order_status == "rejected_no_action" or order.owner_decision == "reject":
        return OperatorPacketPolicy(
            packet_status="rejected_no_action",
            packet_type="owner_rejected_packet",
            operator_lane="owner",
            packet_gate="no_external_action",
            packet_action="record_rejection_and_stop",
            operator_instruction="do_not_execute_rejected_work_order",
            escalation_target="owner",
        )
    raise ValueError(
        f"Unsupported work order status for {order.work_order_id}: "
        f"{order.work_order_status}"
    )


def build_packets(
    work_orders: Sequence[PostDecisionWorkOrderRow],
) -> tuple[OperatorExecutionPacket, ...]:
    packets: list[OperatorExecutionPacket] = []
    for rank, order in enumerate(work_orders, start=1):
        policy = derive_packet_policy(order)
        payload = {
            "schema_version": "operator_execution_packets.v1",
            "privacy_mode": "local_only_operator_execution_packet_no_raw_text",
            "source_work_order_rank": order.work_order_rank,
            "source_work_order_status": order.work_order_status,
            "source_work_order_type": order.work_order_type,
            "owner_decision": order.owner_decision,
            "packet_status": policy.packet_status,
            "packet_type": policy.packet_type,
            "packet_gate": policy.packet_gate,
            "packet_action": policy.packet_action,
            "operator_instruction": policy.operator_instruction,
            "operator_lane": policy.operator_lane,
            "escalation_target": policy.escalation_target,
            "decision_note": order.decision_note,
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        packet_id = f"operator-execution-packet-{rank:06d}"
        packet_hash = _hash_packet(
            {
                **payload,
                "packet_id": packet_id,
                "work_order_id": order.work_order_id,
                "event_id": order.event_id,
                "entry_id": order.entry_id,
                "route_id": order.route_id,
                "case_card_id": order.case_card_id,
                "brief_id": order.brief_id,
                "pack_id": order.pack_id,
                "packet_rank": rank,
                "source_work_order_hash": order.work_order_hash,
            }
        )
        packets.append(
            OperatorExecutionPacket(
                packet_id=packet_id,
                work_order_id=order.work_order_id,
                event_id=order.event_id,
                entry_id=order.entry_id,
                route_id=order.route_id,
                case_card_id=order.case_card_id,
                brief_id=order.brief_id,
                pack_id=order.pack_id,
                packet_rank=rank,
                assigned_lane=order.assigned_lane,
                operator_lane=policy.operator_lane,
                decision_type=order.decision_type,
                decision_priority=order.decision_priority,
                route_bucket=order.route_bucket,
                owner_decision=order.owner_decision,
                source_work_order_status=order.work_order_status,
                packet_status=policy.packet_status,
                packet_type=policy.packet_type,
                packet_gate=policy.packet_gate,
                packet_action=policy.packet_action,
                operator_instruction=policy.operator_instruction,
                escalation_target=policy.escalation_target,
                decision_note=order.decision_note,
                source_work_order_hash=order.work_order_hash,
                packet_hash=packet_hash,
                packet_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(packets)


def write_operator_execution_packets_sqlite(
    output_db: Path,
    *,
    packets: Sequence[OperatorExecutionPacket],
    source_case_count: int,
    owner_item_count: int,
    pack_count: int,
    brief_count: int,
    queue_item_count: int,
    ledger_entry_count: int,
    event_row_count: int,
    work_order_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    status_counts = Counter(packet.packet_status for packet in packets)
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS operator_execution_packet_runs;
            DROP TABLE IF EXISTS operator_execution_packets;

            CREATE TABLE operator_execution_packet_runs (
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
                ready_packet_count INTEGER NOT NULL,
                blocked_packet_count INTEGER NOT NULL,
                deferred_packet_count INTEGER NOT NULL,
                rejected_packet_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE operator_execution_packets (
                packet_id TEXT PRIMARY KEY,
                work_order_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                route_id TEXT NOT NULL,
                case_card_id TEXT NOT NULL,
                brief_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                packet_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                operator_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                route_bucket TEXT NOT NULL,
                owner_decision TEXT NOT NULL,
                source_work_order_status TEXT NOT NULL,
                packet_status TEXT NOT NULL,
                packet_type TEXT NOT NULL,
                packet_gate TEXT NOT NULL,
                packet_action TEXT NOT NULL,
                operator_instruction TEXT NOT NULL,
                escalation_target TEXT NOT NULL,
                decision_note TEXT NOT NULL,
                source_work_order_hash TEXT NOT NULL,
                packet_hash TEXT NOT NULL UNIQUE,
                packet_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_operator_execution_packet_rank
                ON operator_execution_packets(packet_rank);
            CREATE INDEX idx_operator_execution_packet_status
                ON operator_execution_packets(packet_status);
            CREATE INDEX idx_operator_execution_packet_lane
                ON operator_execution_packets(operator_lane);
            CREATE INDEX idx_operator_execution_packet_decision
                ON operator_execution_packets(owner_decision);
            CREATE INDEX idx_operator_execution_packet_work_order
                ON operator_execution_packets(work_order_id);
            """
        )
        conn.execute(
            """
            INSERT INTO operator_execution_packet_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count, brief_count,
                queue_item_count, ledger_entry_count, event_row_count,
                work_order_count, packet_count, ready_packet_count,
                blocked_packet_count, deferred_packet_count,
                rejected_packet_count, send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                source_generated_at_utc,
                "local_only_operator_execution_packet_no_raw_text_no_send_no_crm_mutation",
                source_case_count,
                owner_item_count,
                pack_count,
                brief_count,
                queue_item_count,
                ledger_entry_count,
                event_row_count,
                work_order_count,
                len(packets),
                status_counts.get("ready_for_operator_review", 0),
                status_counts.get("blocked_awaiting_owner_decision", 0),
                status_counts.get("deferred_owner_followup", 0),
                status_counts.get("rejected_no_action", 0),
            ),
        )
        conn.executemany(
            """
            INSERT INTO operator_execution_packets (
                packet_id, work_order_id, event_id, entry_id, route_id,
                case_card_id, brief_id, pack_id, packet_rank, assigned_lane,
                operator_lane, decision_type, decision_priority, route_bucket,
                owner_decision, source_work_order_status, packet_status,
                packet_type, packet_gate, packet_action, operator_instruction,
                escalation_target, decision_note, source_work_order_hash,
                packet_hash, packet_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    packet.packet_id,
                    packet.work_order_id,
                    packet.event_id,
                    packet.entry_id,
                    packet.route_id,
                    packet.case_card_id,
                    packet.brief_id,
                    packet.pack_id,
                    packet.packet_rank,
                    packet.assigned_lane,
                    packet.operator_lane,
                    packet.decision_type,
                    packet.decision_priority,
                    packet.route_bucket,
                    packet.owner_decision,
                    packet.source_work_order_status,
                    packet.packet_status,
                    packet.packet_type,
                    packet.packet_gate,
                    packet.packet_action,
                    packet.operator_instruction,
                    packet.escalation_target,
                    packet.decision_note,
                    packet.source_work_order_hash,
                    packet.packet_hash,
                    json.dumps(packet.packet_payload, ensure_ascii=False, sort_keys=True),
                    int(packet.send_whatsapp),
                    int(packet.crm_mutation),
                    int(packet.requires_human_approval),
                )
                for packet in packets
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
    packets: Sequence[OperatorExecutionPacket],
    source_case_count: int,
    owner_item_count: int,
    pack_count: int,
    brief_count: int,
    queue_item_count: int,
    ledger_entry_count: int,
    event_row_count: int,
    work_order_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    status_counts = Counter(packet.packet_status for packet in packets)
    type_counts = Counter(packet.packet_type for packet in packets)
    lane_counts = Counter(packet.operator_lane for packet in packets)
    decision_counts = Counter(packet.owner_decision for packet in packets)
    decision_type_counts = Counter(packet.decision_type for packet in packets)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Operator Execution Packets Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source Post-Decision Work Order Queue UTC: `{source_generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, judgment IDs, approval IDs, pack IDs, brief IDs, route IDs, ledger entry IDs, event IDs, work order IDs, packet IDs, inbox item IDs, or room item IDs.",
        "- Operator execution packets are local-only and ignored under `research/personal/wa-corpus/`.",
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
        f"| Operator packets | {len(packets)} |",
        f"| Ready packets | {status_counts.get('ready_for_operator_review', 0)} |",
        f"| Blocked packets | {status_counts.get('blocked_awaiting_owner_decision', 0)} |",
        f"| Deferred packets | {status_counts.get('deferred_owner_followup', 0)} |",
        f"| Rejected packets | {status_counts.get('rejected_no_action', 0)} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Packet Status", status_counts),
        "",
        *_counter_table("Packet Types", type_counts),
        "",
        *_counter_table("Operator Lanes", lane_counts),
        "",
        *_counter_table("Owner Decisions", decision_counts),
        "",
        *_counter_table("Decision Types", decision_type_counts),
        "",
        "## Execution Contract",
        "",
        "- Operator execution packets are internal instructions only.",
        "- Pending owner decisions remain blocked and do not become operator work.",
        "- Approved packets require human review before any send or CRM mutation.",
        "- Deferred packets wait for owner revisit.",
        "- Rejected packets stop with no external action.",
        "- It does not parse raw WhatsApp messages.",
        "- It does not call a cloud LLM.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- Human approval remains mandatory before any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_operator_execution_packets(
    *,
    work_orders_db: Path = DEFAULT_WORK_ORDERS_DB,
    output_dir: Path = DEFAULT_OPERATOR_EXECUTION_PACKET_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    generated_at_utc: str | None = None,
) -> OperatorExecutionPacketsBuildResult:
    """Build local-only operator packets from post-decision work orders."""
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
        source_work_order_count,
    ) = read_source_metadata(work_orders_db)
    work_orders = read_work_orders(work_orders_db)
    packets = build_packets(work_orders)
    source_case_total = source_case_count or len(packets)
    owner_item_total = owner_item_count or len(packets)
    pack_total = pack_count or len(packets)
    brief_total = brief_count or len(packets)
    queue_total = queue_item_count or len(packets)
    ledger_total = ledger_entry_count or len(packets)
    event_row_total = event_row_count or len(packets)
    work_order_total = source_work_order_count or len(work_orders)
    write_operator_execution_packets_sqlite(
        output_db,
        packets=packets,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        ledger_entry_count=ledger_total,
        event_row_count=event_row_total,
        work_order_count=work_order_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    write_summary(
        summary_path=summary_path,
        packets=packets,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        ledger_entry_count=ledger_total,
        event_row_count=event_row_total,
        work_order_count=work_order_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    status_counts = Counter(packet.packet_status for packet in packets)
    lane_counts = Counter(packet.operator_lane for packet in packets)
    return OperatorExecutionPacketsBuildResult(
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        ledger_entry_count=ledger_total,
        event_row_count=event_row_total,
        work_order_count=work_order_total,
        packet_count=len(packets),
        ready_packet_count=status_counts.get("ready_for_operator_review", 0),
        blocked_packet_count=status_counts.get("blocked_awaiting_owner_decision", 0),
        deferred_packet_count=status_counts.get("deferred_owner_followup", 0),
        rejected_packet_count=status_counts.get("rejected_no_action", 0),
        send_whatsapp_count=sum(1 for packet in packets if packet.send_whatsapp),
        crm_mutation_count=sum(1 for packet in packets if packet.crm_mutation),
        packet_status_counts=dict(status_counts),
        operator_lane_counts=dict(lane_counts),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara operator execution packets."
    )
    parser.add_argument("--work-orders-db", type=Path, default=DEFAULT_WORK_ORDERS_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OPERATOR_EXECUTION_PACKET_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_operator_execution_packets(
            work_orders_db=args.work_orders_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Operator execution packets input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Operator execution packets run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Operator execution packets run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "blocked_packet_count": result.blocked_packet_count,
                    "brief_count": result.brief_count,
                    "crm_mutation_count": result.crm_mutation_count,
                    "deferred_packet_count": result.deferred_packet_count,
                    "event_row_count": result.event_row_count,
                    "ledger_entry_count": result.ledger_entry_count,
                    "operator_packet_count": result.packet_count,
                    "owner_item_count": result.owner_item_count,
                    "pack_count": result.pack_count,
                    "queue_item_count": result.queue_item_count,
                    "ready_packet_count": result.ready_packet_count,
                    "rejected_packet_count": result.rejected_packet_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "source_case_count": result.source_case_count,
                    "work_order_count": result.work_order_count,
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Operator execution packets complete: "
            f"{result.packet_count} packets -> {result.output_db.name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
