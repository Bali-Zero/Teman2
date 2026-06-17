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

DEFAULT_OWNER_DECISION_EVENT_DIR = Path(
    "research/personal/wa-corpus/owner-decision-events"
)
DEFAULT_POST_DECISION_WORK_ORDER_DIR = Path(
    "research/personal/wa-corpus/post-decision-work-orders"
)

DEFAULT_OWNER_EVENTS_DB = (
    DEFAULT_OWNER_DECISION_EVENT_DIR / "owner_decision_event_capture.local.sqlite"
)
DEFAULT_OUTPUT_DB = (
    DEFAULT_POST_DECISION_WORK_ORDER_DIR
    / "post_decision_work_order_queue.local.sqlite"
)
DEFAULT_SUMMARY = (
    DEFAULT_POST_DECISION_WORK_ORDER_DIR
    / "post_decision_work_order_queue_summary.md"
)

EXPECTED_OWNER_EVENTS_DB_NAME = "owner_decision_event_capture.local.sqlite"
PENDING_OWNER_DECISION = "pending"
CAPTURED_STATUS = "captured"


@dataclass(frozen=True)
class OwnerDecisionEventRow:
    event_id: str
    entry_id: str
    route_id: str
    case_card_id: str
    brief_id: str
    pack_id: str
    event_rank: int
    assigned_lane: str
    decision_type: str
    decision_priority: str
    route_bucket: str
    capture_status: str
    owner_decision: str
    event_type: str
    event_source: str
    event_actor: str
    event_recorded_at_utc: str
    recommended_decision: str
    draft_action_type: str
    decision_note: str
    source_ledger_hash: str
    event_hash: str
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class WorkOrderPolicy:
    work_order_status: str
    work_order_type: str
    execution_gate: str
    next_actor: str
    action_intent: str
    decision_effect: str


@dataclass(frozen=True)
class PostDecisionWorkOrder:
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
    work_order_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class PostDecisionWorkOrderQueueBuildResult:
    source_case_count: int
    owner_item_count: int
    pack_count: int
    brief_count: int
    queue_item_count: int
    ledger_entry_count: int
    event_row_count: int
    work_order_count: int
    ready_count: int
    blocked_count: int
    deferred_count: int
    rejected_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    work_order_status_counts: dict[str, int]
    owner_decision_counts: dict[str, int]
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


def _hash_work_order(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_source_metadata(db_path: Path) -> tuple[str, int, int, int, int, int, int, int]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_OWNER_EVENTS_DB_NAME,
        label="Owner Decision Event Capture",
    ) as conn:
        row = conn.execute(
            """
            SELECT generated_at_utc, source_case_count, owner_item_count,
                   pack_count, brief_count, queue_item_count, ledger_entry_count,
                   captured_event_count + awaiting_input_count AS event_row_count
            FROM owner_decision_event_capture_runs
            WHERE id = 1
            """
        ).fetchone()
    if row is None:
        return "unknown", 0, 0, 0, 0, 0, 0, 0
    return (
        str(row["generated_at_utc"]),
        int(row["source_case_count"]),
        int(row["owner_item_count"]),
        int(row["pack_count"]),
        int(row["brief_count"]),
        int(row["queue_item_count"]),
        int(row["ledger_entry_count"]),
        int(row["event_row_count"]),
    )


def read_owner_decision_events(db_path: Path) -> tuple[OwnerDecisionEventRow, ...]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_OWNER_EVENTS_DB_NAME,
        label="Owner Decision Event Capture",
    ) as conn:
        rows = conn.execute(
            """
            SELECT event_id, entry_id, route_id, case_card_id, brief_id, pack_id,
                   event_rank, assigned_lane, decision_type, decision_priority,
                   route_bucket, capture_status, owner_decision, event_type,
                   event_source, event_actor, event_recorded_at_utc,
                   recommended_decision, draft_action_type, decision_note,
                   source_ledger_hash, event_hash, send_whatsapp, crm_mutation,
                   requires_human_approval
            FROM owner_decision_event_rows
            ORDER BY event_rank, case_card_id
            """
        ).fetchall()
    return tuple(
        OwnerDecisionEventRow(
            event_id=str(row["event_id"]),
            entry_id=str(row["entry_id"]),
            route_id=str(row["route_id"]),
            case_card_id=str(row["case_card_id"]),
            brief_id=str(row["brief_id"]),
            pack_id=str(row["pack_id"]),
            event_rank=int(row["event_rank"]),
            assigned_lane=str(row["assigned_lane"]),
            decision_type=str(row["decision_type"]),
            decision_priority=str(row["decision_priority"]),
            route_bucket=str(row["route_bucket"]),
            capture_status=str(row["capture_status"]),
            owner_decision=str(row["owner_decision"]),
            event_type=str(row["event_type"]),
            event_source=str(row["event_source"]),
            event_actor=str(row["event_actor"]),
            event_recorded_at_utc=str(row["event_recorded_at_utc"]),
            recommended_decision=str(row["recommended_decision"]),
            draft_action_type=str(row["draft_action_type"]),
            decision_note=str(row["decision_note"]),
            source_ledger_hash=str(row["source_ledger_hash"]),
            event_hash=str(row["event_hash"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def _approved_action_intent(decision_type: str) -> tuple[str, str]:
    if decision_type == "approve_client_recovery_followup":
        return (
            "approved_client_recovery_followup",
            "prepare_client_recovery_followup_for_human_review",
        )
    if decision_type == "approve_immigration_status_escalation":
        return (
            "approved_immigration_status_escalation",
            "prepare_immigration_status_escalation_for_human_review",
        )
    return (f"approved_{decision_type}", "prepare_approved_action_for_human_review")


def derive_work_order_policy(event: OwnerDecisionEventRow) -> WorkOrderPolicy:
    if event.send_whatsapp or event.crm_mutation:
        raise ValueError(f"Unsafe owner event flags on {event.event_id}")
    if not event.requires_human_approval:
        raise ValueError(f"Owner event missing human approval gate: {event.event_id}")

    if event.capture_status != CAPTURED_STATUS or event.owner_decision == PENDING_OWNER_DECISION:
        return WorkOrderPolicy(
            work_order_status="blocked_awaiting_owner_decision",
            work_order_type="owner_decision_required",
            execution_gate="owner_input_required",
            next_actor="owner",
            action_intent="wait_for_owner_decision",
            decision_effect="no_action_until_owner_decision",
        )
    if event.owner_decision == "approve":
        work_order_type, action_intent = _approved_action_intent(event.decision_type)
        return WorkOrderPolicy(
            work_order_status="ready_for_operator_review",
            work_order_type=work_order_type,
            execution_gate="human_review_before_send_or_crm",
            next_actor=event.assigned_lane,
            action_intent=action_intent,
            decision_effect="owner_approved_internal_work_order",
        )
    if event.owner_decision == "defer":
        return WorkOrderPolicy(
            work_order_status="deferred_owner_followup",
            work_order_type="owner_deferred_followup",
            execution_gate="owner_revisit_required",
            next_actor="owner",
            action_intent="schedule_owner_revisit",
            decision_effect="deferred_no_external_action",
        )
    if event.owner_decision == "reject":
        return WorkOrderPolicy(
            work_order_status="rejected_no_action",
            work_order_type="owner_rejected_no_action",
            execution_gate="no_external_action",
            next_actor="owner",
            action_intent="record_rejection_and_stop",
            decision_effect="rejected_no_external_action",
        )
    raise ValueError(
        f"Unsupported owner decision for {event.event_id}: {event.owner_decision}"
    )


def build_work_orders(
    events: Sequence[OwnerDecisionEventRow],
) -> tuple[PostDecisionWorkOrder, ...]:
    work_orders: list[PostDecisionWorkOrder] = []
    for rank, event in enumerate(events, start=1):
        policy = derive_work_order_policy(event)
        payload = {
            "schema_version": "post_decision_work_order_queue.v1",
            "privacy_mode": "local_only_post_decision_work_order_no_raw_text",
            "source_event_rank": event.event_rank,
            "source_capture_status": event.capture_status,
            "owner_decision": event.owner_decision,
            "work_order_status": policy.work_order_status,
            "work_order_type": policy.work_order_type,
            "execution_gate": policy.execution_gate,
            "next_actor": policy.next_actor,
            "action_intent": policy.action_intent,
            "decision_effect": policy.decision_effect,
            "decision_note": event.decision_note,
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        work_order_id = f"post-decision-work-order-{rank:06d}"
        work_order_hash = _hash_work_order(
            {
                **payload,
                "work_order_id": work_order_id,
                "event_id": event.event_id,
                "entry_id": event.entry_id,
                "route_id": event.route_id,
                "case_card_id": event.case_card_id,
                "brief_id": event.brief_id,
                "pack_id": event.pack_id,
                "work_order_rank": rank,
                "source_event_hash": event.event_hash,
            }
        )
        work_orders.append(
            PostDecisionWorkOrder(
                work_order_id=work_order_id,
                event_id=event.event_id,
                entry_id=event.entry_id,
                route_id=event.route_id,
                case_card_id=event.case_card_id,
                brief_id=event.brief_id,
                pack_id=event.pack_id,
                work_order_rank=rank,
                assigned_lane=event.assigned_lane,
                decision_type=event.decision_type,
                decision_priority=event.decision_priority,
                route_bucket=event.route_bucket,
                owner_decision=event.owner_decision,
                source_capture_status=event.capture_status,
                work_order_status=policy.work_order_status,
                work_order_type=policy.work_order_type,
                execution_gate=policy.execution_gate,
                next_actor=policy.next_actor,
                action_intent=policy.action_intent,
                decision_effect=policy.decision_effect,
                decision_note=event.decision_note,
                source_event_hash=event.event_hash,
                work_order_hash=work_order_hash,
                work_order_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(work_orders)


def write_post_decision_work_orders_sqlite(
    output_db: Path,
    *,
    work_orders: Sequence[PostDecisionWorkOrder],
    source_case_count: int,
    owner_item_count: int,
    pack_count: int,
    brief_count: int,
    queue_item_count: int,
    ledger_entry_count: int,
    event_row_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    status_counts = Counter(order.work_order_status for order in work_orders)
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS post_decision_work_order_runs;
            DROP TABLE IF EXISTS post_decision_work_orders;

            CREATE TABLE post_decision_work_order_runs (
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
                ready_count INTEGER NOT NULL,
                blocked_count INTEGER NOT NULL,
                deferred_count INTEGER NOT NULL,
                rejected_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE post_decision_work_orders (
                work_order_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                route_id TEXT NOT NULL,
                case_card_id TEXT NOT NULL,
                brief_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                work_order_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                route_bucket TEXT NOT NULL,
                owner_decision TEXT NOT NULL,
                source_capture_status TEXT NOT NULL,
                work_order_status TEXT NOT NULL,
                work_order_type TEXT NOT NULL,
                execution_gate TEXT NOT NULL,
                next_actor TEXT NOT NULL,
                action_intent TEXT NOT NULL,
                decision_effect TEXT NOT NULL,
                decision_note TEXT NOT NULL,
                source_event_hash TEXT NOT NULL,
                work_order_hash TEXT NOT NULL UNIQUE,
                work_order_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_post_decision_work_order_rank
                ON post_decision_work_orders(work_order_rank);
            CREATE INDEX idx_post_decision_work_order_status
                ON post_decision_work_orders(work_order_status);
            CREATE INDEX idx_post_decision_work_order_decision
                ON post_decision_work_orders(owner_decision);
            CREATE INDEX idx_post_decision_work_order_actor
                ON post_decision_work_orders(next_actor);
            """
        )
        conn.execute(
            """
            INSERT INTO post_decision_work_order_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count, brief_count,
                queue_item_count, ledger_entry_count, event_row_count,
                work_order_count, ready_count, blocked_count, deferred_count,
                rejected_count, send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                source_generated_at_utc,
                "local_only_post_decision_work_order_no_raw_text_no_send_no_crm_mutation",
                source_case_count,
                owner_item_count,
                pack_count,
                brief_count,
                queue_item_count,
                ledger_entry_count,
                event_row_count,
                len(work_orders),
                status_counts.get("ready_for_operator_review", 0),
                status_counts.get("blocked_awaiting_owner_decision", 0),
                status_counts.get("deferred_owner_followup", 0),
                status_counts.get("rejected_no_action", 0),
            ),
        )
        conn.executemany(
            """
            INSERT INTO post_decision_work_orders (
                work_order_id, event_id, entry_id, route_id, case_card_id,
                brief_id, pack_id, work_order_rank, assigned_lane, decision_type,
                decision_priority, route_bucket, owner_decision,
                source_capture_status, work_order_status, work_order_type,
                execution_gate, next_actor, action_intent, decision_effect,
                decision_note, source_event_hash, work_order_hash,
                work_order_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    order.work_order_id,
                    order.event_id,
                    order.entry_id,
                    order.route_id,
                    order.case_card_id,
                    order.brief_id,
                    order.pack_id,
                    order.work_order_rank,
                    order.assigned_lane,
                    order.decision_type,
                    order.decision_priority,
                    order.route_bucket,
                    order.owner_decision,
                    order.source_capture_status,
                    order.work_order_status,
                    order.work_order_type,
                    order.execution_gate,
                    order.next_actor,
                    order.action_intent,
                    order.decision_effect,
                    order.decision_note,
                    order.source_event_hash,
                    order.work_order_hash,
                    json.dumps(order.work_order_payload, ensure_ascii=False, sort_keys=True),
                    int(order.send_whatsapp),
                    int(order.crm_mutation),
                    int(order.requires_human_approval),
                )
                for order in work_orders
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
    work_orders: Sequence[PostDecisionWorkOrder],
    source_case_count: int,
    owner_item_count: int,
    pack_count: int,
    brief_count: int,
    queue_item_count: int,
    ledger_entry_count: int,
    event_row_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    status_counts = Counter(order.work_order_status for order in work_orders)
    decision_counts = Counter(order.owner_decision for order in work_orders)
    type_counts = Counter(order.work_order_type for order in work_orders)
    actor_counts = Counter(order.next_actor for order in work_orders)
    lane_counts = Counter(order.assigned_lane for order in work_orders)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Post-Decision Work Order Queue Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source Owner Decision Event Capture UTC: `{source_generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, judgment IDs, approval IDs, pack IDs, brief IDs, route IDs, ledger entry IDs, event IDs, work order IDs, inbox item IDs, or room item IDs.",
        "- Post-decision work orders are local-only and ignored under `research/personal/wa-corpus/`.",
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
        f"| Work orders | {len(work_orders)} |",
        f"| Ready work orders | {status_counts.get('ready_for_operator_review', 0)} |",
        f"| Blocked work orders | {status_counts.get('blocked_awaiting_owner_decision', 0)} |",
        f"| Deferred work orders | {status_counts.get('deferred_owner_followup', 0)} |",
        f"| Rejected work orders | {status_counts.get('rejected_no_action', 0)} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Work Order Status", status_counts),
        "",
        *_counter_table("Owner Decisions", decision_counts),
        "",
        *_counter_table("Work Order Types", type_counts),
        "",
        *_counter_table("Next Actors", actor_counts),
        "",
        *_counter_table("Assigned Lanes", lane_counts),
        "",
        "## Execution Contract",
        "",
        "- The Post-Decision Work Order Queue converts owner decision events into internal work orders only.",
        "- Pending owner decisions remain blocked and do not become operational work.",
        "- Approved decisions become operator-review work orders, not automatic sends.",
        "- Deferred and rejected decisions produce no external action.",
        "- It does not parse raw WhatsApp messages.",
        "- It does not call a cloud LLM.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- Human approval remains mandatory before any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_post_decision_work_order_queue(
    *,
    owner_events_db: Path = DEFAULT_OWNER_EVENTS_DB,
    output_dir: Path = DEFAULT_POST_DECISION_WORK_ORDER_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    generated_at_utc: str | None = None,
) -> PostDecisionWorkOrderQueueBuildResult:
    """Build local-only internal work orders from captured owner decisions."""
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
        source_event_row_count,
    ) = read_source_metadata(owner_events_db)
    events = read_owner_decision_events(owner_events_db)
    work_orders = build_work_orders(events)
    source_case_total = source_case_count or len(events)
    owner_item_total = owner_item_count or len(events)
    pack_total = pack_count or len(events)
    brief_total = brief_count or len(events)
    queue_total = queue_item_count or len(events)
    ledger_total = ledger_entry_count or len(events)
    event_row_total = source_event_row_count or len(events)
    write_post_decision_work_orders_sqlite(
        output_db,
        work_orders=work_orders,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        ledger_entry_count=ledger_total,
        event_row_count=event_row_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    write_summary(
        summary_path=summary_path,
        work_orders=work_orders,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        ledger_entry_count=ledger_total,
        event_row_count=event_row_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    status_counts = Counter(order.work_order_status for order in work_orders)
    return PostDecisionWorkOrderQueueBuildResult(
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        ledger_entry_count=ledger_total,
        event_row_count=event_row_total,
        work_order_count=len(work_orders),
        ready_count=status_counts.get("ready_for_operator_review", 0),
        blocked_count=status_counts.get("blocked_awaiting_owner_decision", 0),
        deferred_count=status_counts.get("deferred_owner_followup", 0),
        rejected_count=status_counts.get("rejected_no_action", 0),
        send_whatsapp_count=sum(1 for order in work_orders if order.send_whatsapp),
        crm_mutation_count=sum(1 for order in work_orders if order.crm_mutation),
        work_order_status_counts=dict(status_counts),
        owner_decision_counts=dict(Counter(order.owner_decision for order in work_orders)),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara post-decision work order queue."
    )
    parser.add_argument("--owner-events-db", type=Path, default=DEFAULT_OWNER_EVENTS_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_POST_DECISION_WORK_ORDER_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_post_decision_work_order_queue(
            owner_events_db=args.owner_events_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Post-decision work order queue input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Post-decision work order queue run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Post-decision work order queue run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "blocked_count": result.blocked_count,
                    "brief_count": result.brief_count,
                    "crm_mutation_count": result.crm_mutation_count,
                    "deferred_count": result.deferred_count,
                    "event_row_count": result.event_row_count,
                    "ledger_entry_count": result.ledger_entry_count,
                    "owner_item_count": result.owner_item_count,
                    "pack_count": result.pack_count,
                    "queue_item_count": result.queue_item_count,
                    "ready_count": result.ready_count,
                    "rejected_count": result.rejected_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "source_case_count": result.source_case_count,
                    "work_order_count": result.work_order_count,
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Post-decision work order queue complete: "
            f"{result.work_order_count} work orders -> {result.output_db.name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
