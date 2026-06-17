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

DEFAULT_OPERATOR_PACKET_REVIEW_CONSOLE_DIR = Path(
    "research/personal/wa-corpus/operator-packet-review-console"
)
DEFAULT_OWNER_DECISION_INTAKE_DIR = Path(
    "research/personal/wa-corpus/owner-decision-intake"
)

DEFAULT_REVIEW_CONSOLE_DB = (
    DEFAULT_OPERATOR_PACKET_REVIEW_CONSOLE_DIR
    / "operator_packet_review_console.local.sqlite"
)
DEFAULT_OUTPUT_DB = DEFAULT_OWNER_DECISION_INTAKE_DIR / "owner_decision_intake.local.sqlite"
DEFAULT_OUTPUT_JSONL = DEFAULT_OWNER_DECISION_INTAKE_DIR / "owner_events.local.jsonl"
DEFAULT_OUTPUT_TEMPLATE = (
    DEFAULT_OWNER_DECISION_INTAKE_DIR / "owner_decisions_template.local.jsonl"
)
DEFAULT_SUMMARY = DEFAULT_OWNER_DECISION_INTAKE_DIR / "owner_decision_intake_summary.md"

EXPECTED_REVIEW_CONSOLE_DB_NAME = "operator_packet_review_console.local.sqlite"
ALLOWED_OWNER_DECISIONS = frozenset({"approve", "reject", "defer"})
ACTIONABLE_REVIEW_STATES = frozenset(
    {"waiting_owner_decision", "deferred_owner_revisit"}
)
DEFAULT_EVENT_ACTOR = "owner"
CAPTURED_STATUS = "captured"


@dataclass(frozen=True)
class ReviewConsoleRow:
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
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OwnerDecisionInput:
    reference_key: str
    owner_decision: str
    decision_note: str
    event_actor: str
    event_recorded_at_utc: str | None


@dataclass(frozen=True)
class OwnerDecisionIntakeItem:
    intake_item_id: str
    review_item_id: str
    packet_id: str
    work_order_id: str
    event_id: str
    entry_id: str
    route_id: str
    case_card_id: str
    brief_id: str
    pack_id: str
    intake_rank: int
    source_review_rank: int
    assigned_lane: str
    operator_lane: str
    decision_type: str
    decision_priority: str
    route_bucket: str
    review_state: str
    console_bucket: str
    review_priority: str
    visible_owner_action: str
    operator_action: str
    submitted_owner_decision: str
    intake_status: str
    replay_event_status: str
    replay_event_type: str
    event_actor: str
    event_recorded_at_utc: str
    decision_note: str
    source_review_hash: str
    intake_hash: str
    intake_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool

    def replay_jsonl_record(self) -> dict[str, str] | None:
        if self.replay_event_status != "emitted_to_owner_events_jsonl":
            return None
        return {
            "decision_note": self.decision_note,
            "entry_id": self.entry_id,
            "event_actor": self.event_actor,
            "event_recorded_at_utc": self.event_recorded_at_utc,
            "owner_decision": self.submitted_owner_decision,
        }


@dataclass(frozen=True)
class OwnerDecisionIntakeBuildResult:
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
    intake_item_count: int
    captured_decision_count: int
    awaiting_owner_decision_count: int
    awaiting_owner_revisit_count: int
    no_owner_action_required_count: int
    closed_item_count: int
    replay_event_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    intake_status_counts: dict[str, int]
    replay_event_status_counts: dict[str, int]
    output_db: Path
    output_jsonl: Path
    output_template: Path
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
        raise ValueError(f"Refusing to read unexpected {label}: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"{label} not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _read_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            decoded = json.loads(stripped)
            if not isinstance(decoded, dict):
                raise ValueError(f"Owner intake line {line_number} must be a JSON object")
            rows.append(decoded)
    return tuple(rows)


def _hash_intake_item(payload: dict[str, object]) -> str:
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
        expected_name=EXPECTED_REVIEW_CONSOLE_DB_NAME,
        label="Operator Packet Review Console DB",
    ) as conn:
        row = conn.execute(
            """
            SELECT generated_at_utc, source_case_count, owner_item_count,
                   pack_count, brief_count, queue_item_count, ledger_entry_count,
                   event_row_count, work_order_count, packet_count
            FROM operator_packet_review_console_runs
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


def read_review_console_items(db_path: Path) -> tuple[ReviewConsoleRow, ...]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_REVIEW_CONSOLE_DB_NAME,
        label="Operator Packet Review Console DB",
    ) as conn:
        rows = conn.execute(
            """
            SELECT review_item_id, packet_id, work_order_id, event_id, entry_id,
                   route_id, case_card_id, brief_id, pack_id, review_rank,
                   source_packet_rank, assigned_lane, operator_lane, decision_type,
                   decision_priority, route_bucket, owner_decision, packet_status,
                   packet_type, packet_gate, packet_action, operator_instruction,
                   escalation_target, review_state, console_bucket, review_priority,
                   visible_owner_action, operator_action, console_instruction,
                   review_gate, action_lock, decision_note, source_packet_hash,
                   review_hash, send_whatsapp, crm_mutation, requires_human_approval
            FROM operator_packet_review_items
            ORDER BY review_rank, case_card_id
            """
        ).fetchall()
    return tuple(
        ReviewConsoleRow(
            review_item_id=str(row["review_item_id"]),
            packet_id=str(row["packet_id"]),
            work_order_id=str(row["work_order_id"]),
            event_id=str(row["event_id"]),
            entry_id=str(row["entry_id"]),
            route_id=str(row["route_id"]),
            case_card_id=str(row["case_card_id"]),
            brief_id=str(row["brief_id"]),
            pack_id=str(row["pack_id"]),
            review_rank=int(row["review_rank"]),
            source_packet_rank=int(row["source_packet_rank"]),
            assigned_lane=str(row["assigned_lane"]),
            operator_lane=str(row["operator_lane"]),
            decision_type=str(row["decision_type"]),
            decision_priority=str(row["decision_priority"]),
            route_bucket=str(row["route_bucket"]),
            owner_decision=str(row["owner_decision"]),
            packet_status=str(row["packet_status"]),
            packet_type=str(row["packet_type"]),
            packet_gate=str(row["packet_gate"]),
            packet_action=str(row["packet_action"]),
            operator_instruction=str(row["operator_instruction"]),
            escalation_target=str(row["escalation_target"]),
            review_state=str(row["review_state"]),
            console_bucket=str(row["console_bucket"]),
            review_priority=str(row["review_priority"]),
            visible_owner_action=str(row["visible_owner_action"]),
            operator_action=str(row["operator_action"]),
            console_instruction=str(row["console_instruction"]),
            review_gate=str(row["review_gate"]),
            action_lock=str(row["action_lock"]),
            decision_note=str(row["decision_note"]),
            source_packet_hash=str(row["source_packet_hash"]),
            review_hash=str(row["review_hash"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def _extract_reference(raw: dict[str, object]) -> str:
    reference_keys = [
        key
        for key in ("review_item_id", "packet_id", "entry_id")
        if isinstance(raw.get(key), str) and raw.get(key)
    ]
    if len(reference_keys) != 1:
        raise ValueError(
            "Owner decision intake must reference exactly one of "
            "review_item_id, packet_id, or entry_id"
        )
    return str(raw[reference_keys[0]])


def read_owner_decision_inputs(
    jsonl_path: Path | None,
    rows: Sequence[ReviewConsoleRow],
) -> dict[str, OwnerDecisionInput]:
    if jsonl_path is None:
        return {}

    by_reference: dict[str, ReviewConsoleRow] = {}
    for row in rows:
        by_reference[row.review_item_id] = row
        by_reference[row.packet_id] = row
        by_reference[row.entry_id] = row

    decisions: dict[str, OwnerDecisionInput] = {}
    for raw in _read_jsonl(jsonl_path):
        reference = _extract_reference(raw)
        row = by_reference.get(reference)
        if row is None:
            raise ValueError(f"Owner decision intake references unknown item: {reference}")
        if row.review_item_id in decisions:
            raise ValueError(f"Duplicate owner decision intake: {row.review_item_id}")
        if row.review_state not in ACTIONABLE_REVIEW_STATES:
            raise ValueError(f"Review item is not owner-actionable: {row.review_item_id}")

        owner_decision = raw.get("owner_decision")
        if not isinstance(owner_decision, str) or not owner_decision:
            raise ValueError(f"Owner decision is missing for {reference}")
        if owner_decision not in ALLOWED_OWNER_DECISIONS:
            raise ValueError(
                f"Owner decision is not allowed for {row.review_item_id}: {owner_decision}"
            )

        decision_note = raw.get("decision_note")
        event_actor = raw.get("event_actor")
        event_recorded_at_utc = raw.get("event_recorded_at_utc")
        if event_actor is not None and event_actor != DEFAULT_EVENT_ACTOR:
            raise ValueError(f"Owner decision actor is not allowed for {reference}")
        if event_recorded_at_utc is not None and not isinstance(event_recorded_at_utc, str):
            raise ValueError(f"Owner decision for {reference} has invalid timestamp")
        decisions[row.review_item_id] = OwnerDecisionInput(
            reference_key=reference,
            owner_decision=owner_decision,
            decision_note=(
                decision_note if isinstance(decision_note, str) and decision_note else ""
            ),
            event_actor=(
                event_actor if isinstance(event_actor, str) and event_actor else DEFAULT_EVENT_ACTOR
            ),
            event_recorded_at_utc=event_recorded_at_utc,
        )
    return decisions


def _status_for_row(
    row: ReviewConsoleRow,
    submitted: OwnerDecisionInput | None,
) -> tuple[str, str, str, str, str]:
    if submitted is not None:
        return (
            submitted.owner_decision,
            CAPTURED_STATUS,
            "emitted_to_owner_events_jsonl",
            "owner_decision_intake_captured",
            submitted.decision_note or f"owner_decision_{submitted.owner_decision}",
        )
    if row.review_state == "waiting_owner_decision":
        return (
            row.owner_decision,
            "awaiting_owner_decision",
            "not_emitted",
            "owner_decision_intake_pending",
            "owner_decision_required",
        )
    if row.review_state == "deferred_owner_revisit":
        return (
            row.owner_decision,
            "awaiting_owner_revisit",
            "not_emitted",
            "owner_revisit_required",
            "owner_revisit_required",
        )
    if row.review_state == "ready_for_human_review":
        return (
            row.owner_decision,
            "no_owner_action_required",
            "not_emitted",
            "owner_action_not_required",
            row.decision_note,
        )
    if row.review_state == "rejected_closed":
        return (
            row.owner_decision,
            "closed_no_owner_action",
            "not_emitted",
            "owner_action_closed",
            row.decision_note,
        )
    raise ValueError(f"Unsupported review state for {row.review_item_id}: {row.review_state}")


def build_intake_items(
    rows: Sequence[ReviewConsoleRow],
    owner_decisions: dict[str, OwnerDecisionInput],
    *,
    generated_at_utc: str,
) -> tuple[OwnerDecisionIntakeItem, ...]:
    items: list[OwnerDecisionIntakeItem] = []
    for rank, row in enumerate(rows, start=1):
        if row.send_whatsapp or row.crm_mutation:
            raise ValueError(f"Unsafe review item flags on {row.review_item_id}")
        if not row.requires_human_approval:
            raise ValueError(f"Review item missing human approval gate: {row.review_item_id}")

        submitted = owner_decisions.get(row.review_item_id)
        (
            submitted_owner_decision,
            intake_status,
            replay_event_status,
            replay_event_type,
            decision_note,
        ) = _status_for_row(row, submitted)
        event_actor = submitted.event_actor if submitted is not None else DEFAULT_EVENT_ACTOR
        event_recorded_at_utc = _format_utc(
            submitted.event_recorded_at_utc if submitted is not None else generated_at_utc
        )
        payload = {
            "schema_version": "owner_decision_intake.v1",
            "privacy_mode": "local_only_owner_decision_intake_no_raw_text",
            "source_review_rank": row.review_rank,
            "review_state": row.review_state,
            "console_bucket": row.console_bucket,
            "visible_owner_action": row.visible_owner_action,
            "submitted_owner_decision": submitted_owner_decision,
            "intake_status": intake_status,
            "replay_event_status": replay_event_status,
            "replay_event_type": replay_event_type,
            "event_actor": event_actor,
            "event_recorded_at_utc": event_recorded_at_utc,
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        intake_item_id = f"owner-decision-intake-item-{rank:06d}"
        intake_hash = _hash_intake_item(
            {
                **payload,
                "intake_item_id": intake_item_id,
                "review_item_id": row.review_item_id,
                "packet_id": row.packet_id,
                "work_order_id": row.work_order_id,
                "event_id": row.event_id,
                "entry_id": row.entry_id,
                "route_id": row.route_id,
                "case_card_id": row.case_card_id,
                "brief_id": row.brief_id,
                "pack_id": row.pack_id,
                "intake_rank": rank,
                "source_review_hash": row.review_hash,
            }
        )
        items.append(
            OwnerDecisionIntakeItem(
                intake_item_id=intake_item_id,
                review_item_id=row.review_item_id,
                packet_id=row.packet_id,
                work_order_id=row.work_order_id,
                event_id=row.event_id,
                entry_id=row.entry_id,
                route_id=row.route_id,
                case_card_id=row.case_card_id,
                brief_id=row.brief_id,
                pack_id=row.pack_id,
                intake_rank=rank,
                source_review_rank=row.review_rank,
                assigned_lane=row.assigned_lane,
                operator_lane=row.operator_lane,
                decision_type=row.decision_type,
                decision_priority=row.decision_priority,
                route_bucket=row.route_bucket,
                review_state=row.review_state,
                console_bucket=row.console_bucket,
                review_priority=row.review_priority,
                visible_owner_action=row.visible_owner_action,
                operator_action=row.operator_action,
                submitted_owner_decision=submitted_owner_decision,
                intake_status=intake_status,
                replay_event_status=replay_event_status,
                replay_event_type=replay_event_type,
                event_actor=event_actor,
                event_recorded_at_utc=event_recorded_at_utc,
                decision_note=decision_note,
                source_review_hash=row.review_hash,
                intake_hash=intake_hash,
                intake_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(items)


def write_owner_decision_intake_sqlite(
    output_db: Path,
    *,
    items: Sequence[OwnerDecisionIntakeItem],
    source_case_count: int,
    owner_item_count: int,
    pack_count: int,
    brief_count: int,
    queue_item_count: int,
    ledger_entry_count: int,
    event_row_count: int,
    work_order_count: int,
    packet_count: int,
    review_item_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    status_counts = Counter(item.intake_status for item in items)
    replay_counts = Counter(item.replay_event_status for item in items)
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS owner_decision_intake_runs;
            DROP TABLE IF EXISTS owner_decision_intake_items;

            CREATE TABLE owner_decision_intake_runs (
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
                intake_item_count INTEGER NOT NULL,
                captured_decision_count INTEGER NOT NULL,
                awaiting_owner_decision_count INTEGER NOT NULL,
                awaiting_owner_revisit_count INTEGER NOT NULL,
                no_owner_action_required_count INTEGER NOT NULL,
                closed_item_count INTEGER NOT NULL,
                replay_event_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE owner_decision_intake_items (
                intake_item_id TEXT PRIMARY KEY,
                review_item_id TEXT NOT NULL,
                packet_id TEXT NOT NULL,
                work_order_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                route_id TEXT NOT NULL,
                case_card_id TEXT NOT NULL,
                brief_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                intake_rank INTEGER NOT NULL,
                source_review_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                operator_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                route_bucket TEXT NOT NULL,
                review_state TEXT NOT NULL,
                console_bucket TEXT NOT NULL,
                review_priority TEXT NOT NULL,
                visible_owner_action TEXT NOT NULL,
                operator_action TEXT NOT NULL,
                submitted_owner_decision TEXT NOT NULL,
                intake_status TEXT NOT NULL,
                replay_event_status TEXT NOT NULL,
                replay_event_type TEXT NOT NULL,
                event_actor TEXT NOT NULL,
                event_recorded_at_utc TEXT NOT NULL,
                decision_note TEXT NOT NULL,
                source_review_hash TEXT NOT NULL,
                intake_hash TEXT NOT NULL UNIQUE,
                intake_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_owner_decision_intake_rank
                ON owner_decision_intake_items(intake_rank);
            CREATE INDEX idx_owner_decision_intake_review
                ON owner_decision_intake_items(review_item_id);
            CREATE INDEX idx_owner_decision_intake_packet
                ON owner_decision_intake_items(packet_id);
            CREATE INDEX idx_owner_decision_intake_entry
                ON owner_decision_intake_items(entry_id);
            CREATE INDEX idx_owner_decision_intake_status
                ON owner_decision_intake_items(intake_status);
            CREATE INDEX idx_owner_decision_intake_replay
                ON owner_decision_intake_items(replay_event_status);
            """
        )
        conn.execute(
            """
            INSERT INTO owner_decision_intake_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count, brief_count,
                queue_item_count, ledger_entry_count, event_row_count,
                work_order_count, packet_count, review_item_count,
                intake_item_count, captured_decision_count,
                awaiting_owner_decision_count, awaiting_owner_revisit_count,
                no_owner_action_required_count, closed_item_count,
                replay_event_count, send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                source_generated_at_utc,
                "local_only_owner_decision_intake_no_raw_text_no_send_no_crm_mutation",
                source_case_count,
                owner_item_count,
                pack_count,
                brief_count,
                queue_item_count,
                ledger_entry_count,
                event_row_count,
                work_order_count,
                packet_count,
                review_item_count,
                len(items),
                status_counts.get(CAPTURED_STATUS, 0),
                status_counts.get("awaiting_owner_decision", 0),
                status_counts.get("awaiting_owner_revisit", 0),
                status_counts.get("no_owner_action_required", 0),
                status_counts.get("closed_no_owner_action", 0),
                replay_counts.get("emitted_to_owner_events_jsonl", 0),
            ),
        )
        conn.executemany(
            """
            INSERT INTO owner_decision_intake_items (
                intake_item_id, review_item_id, packet_id, work_order_id,
                event_id, entry_id, route_id, case_card_id, brief_id, pack_id,
                intake_rank, source_review_rank, assigned_lane, operator_lane,
                decision_type, decision_priority, route_bucket, review_state,
                console_bucket, review_priority, visible_owner_action,
                operator_action, submitted_owner_decision, intake_status,
                replay_event_status, replay_event_type, event_actor,
                event_recorded_at_utc, decision_note, source_review_hash,
                intake_hash, intake_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.intake_item_id,
                    item.review_item_id,
                    item.packet_id,
                    item.work_order_id,
                    item.event_id,
                    item.entry_id,
                    item.route_id,
                    item.case_card_id,
                    item.brief_id,
                    item.pack_id,
                    item.intake_rank,
                    item.source_review_rank,
                    item.assigned_lane,
                    item.operator_lane,
                    item.decision_type,
                    item.decision_priority,
                    item.route_bucket,
                    item.review_state,
                    item.console_bucket,
                    item.review_priority,
                    item.visible_owner_action,
                    item.operator_action,
                    item.submitted_owner_decision,
                    item.intake_status,
                    item.replay_event_status,
                    item.replay_event_type,
                    item.event_actor,
                    item.event_recorded_at_utc,
                    item.decision_note,
                    item.source_review_hash,
                    item.intake_hash,
                    json.dumps(item.intake_payload, ensure_ascii=False, sort_keys=True),
                    int(item.send_whatsapp),
                    int(item.crm_mutation),
                    int(item.requires_human_approval),
                )
                for item in items
            ],
        )
        conn.commit()


def write_replay_jsonl(path: Path, items: Sequence[OwnerDecisionIntakeItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        record
        for item in items
        if (record := item.replay_jsonl_record()) is not None
    ]
    path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


def write_owner_decision_template_jsonl(
    path: Path,
    items: Sequence[OwnerDecisionIntakeItem],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    actionable_statuses = {"awaiting_owner_decision", "awaiting_owner_revisit"}
    records = [
        {
            "allowed_decisions": ["approve", "reject", "defer"],
            "assigned_lane": item.assigned_lane,
            "console_bucket": item.console_bucket,
            "decision_note": "",
            "decision_type": item.decision_type,
            "entry_id": item.entry_id,
            "event_actor": DEFAULT_EVENT_ACTOR,
            "event_recorded_at_utc": item.event_recorded_at_utc,
            "owner_decision": "",
            "packet_id": item.packet_id,
            "review_item_id": item.review_item_id,
            "review_state": item.review_state,
        }
        for item in items
        if item.intake_status in actionable_statuses
    ]
    path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


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
    items: Sequence[OwnerDecisionIntakeItem],
    source_case_count: int,
    owner_item_count: int,
    pack_count: int,
    brief_count: int,
    queue_item_count: int,
    ledger_entry_count: int,
    event_row_count: int,
    work_order_count: int,
    packet_count: int,
    review_item_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    status_counts = Counter(item.intake_status for item in items)
    replay_counts = Counter(item.replay_event_status for item in items)
    decision_counts = Counter(item.submitted_owner_decision for item in items)
    state_counts = Counter(item.review_state for item in items)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Owner Decision Intake Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source Operator Packet Review Console UTC: `{source_generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, judgment IDs, approval IDs, pack IDs, brief IDs, route IDs, ledger entry IDs, event IDs, work order IDs, packet IDs, review item IDs, intake item IDs, inbox item IDs, or room item IDs.",
        "- Owner decision intake artifacts are local-only and ignored under `research/personal/wa-corpus/`.",
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
        f"| Review items | {review_item_count} |",
        f"| Intake items | {len(items)} |",
        f"| Captured decisions | {status_counts.get(CAPTURED_STATUS, 0)} |",
        f"| Awaiting owner decision | {status_counts.get('awaiting_owner_decision', 0)} |",
        f"| Awaiting owner revisit | {status_counts.get('awaiting_owner_revisit', 0)} |",
        f"| No owner action required | {status_counts.get('no_owner_action_required', 0)} |",
        f"| Closed items | {status_counts.get('closed_no_owner_action', 0)} |",
        f"| Replay events | {replay_counts.get('emitted_to_owner_events_jsonl', 0)} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Intake Status", status_counts),
        "",
        *_counter_table("Replay Event Status", replay_counts),
        "",
        *_counter_table("Submitted Owner Decisions", decision_counts),
        "",
        *_counter_table("Source Review States", state_counts),
        "",
        "## Execution Contract",
        "",
        "- The Owner Decision Intake accepts only explicit owner approve, reject, or defer records.",
        "- Missing owner decisions remain awaiting owner input or owner revisit.",
        "- Captured decisions are exported to `owner_events.local.jsonl` for deterministic replay through Owner Decision Event Capture.",
        "- Operator-ready and closed items cannot be changed through this intake.",
        "- It does not parse raw WhatsApp messages.",
        "- It does not call a cloud LLM.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- Human approval remains mandatory before any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_owner_decision_intake(
    *,
    review_console_db: Path = DEFAULT_REVIEW_CONSOLE_DB,
    owner_decisions_jsonl: Path | None = None,
    output_dir: Path = DEFAULT_OWNER_DECISION_INTAKE_DIR,
    output_db: Path | None = None,
    output_jsonl: Path | None = None,
    output_template: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    generated_at_utc: str | None = None,
) -> OwnerDecisionIntakeBuildResult:
    """Build local owner decision intake rows and replay JSONL from review items."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    output_jsonl = output_jsonl or output_dir / DEFAULT_OUTPUT_JSONL.name
    output_template = output_template or output_dir / DEFAULT_OUTPUT_TEMPLATE.name
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
    ) = read_source_metadata(review_console_db)
    review_items = read_review_console_items(review_console_db)
    owner_decisions = read_owner_decision_inputs(owner_decisions_jsonl, review_items)
    intake_items = build_intake_items(
        review_items,
        owner_decisions,
        generated_at_utc=generated,
    )
    source_case_total = source_case_count or len(intake_items)
    owner_item_total = owner_item_count or len(intake_items)
    pack_total = pack_count or len(intake_items)
    brief_total = brief_count or len(intake_items)
    queue_total = queue_item_count or len(intake_items)
    ledger_total = ledger_entry_count or len(intake_items)
    event_total = event_row_count or len(intake_items)
    work_order_total = work_order_count or len(intake_items)
    packet_total = source_packet_count or len(intake_items)
    review_total = len(review_items)

    write_owner_decision_intake_sqlite(
        output_db,
        items=intake_items,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        ledger_entry_count=ledger_total,
        event_row_count=event_total,
        work_order_count=work_order_total,
        packet_count=packet_total,
        review_item_count=review_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    write_replay_jsonl(output_jsonl, intake_items)
    write_owner_decision_template_jsonl(output_template, intake_items)
    write_summary(
        summary_path=summary_path,
        items=intake_items,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        ledger_entry_count=ledger_total,
        event_row_count=event_total,
        work_order_count=work_order_total,
        packet_count=packet_total,
        review_item_count=review_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    status_counts = Counter(item.intake_status for item in intake_items)
    replay_counts = Counter(item.replay_event_status for item in intake_items)
    return OwnerDecisionIntakeBuildResult(
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        ledger_entry_count=ledger_total,
        event_row_count=event_total,
        work_order_count=work_order_total,
        packet_count=packet_total,
        review_item_count=review_total,
        intake_item_count=len(intake_items),
        captured_decision_count=status_counts.get(CAPTURED_STATUS, 0),
        awaiting_owner_decision_count=status_counts.get("awaiting_owner_decision", 0),
        awaiting_owner_revisit_count=status_counts.get("awaiting_owner_revisit", 0),
        no_owner_action_required_count=status_counts.get("no_owner_action_required", 0),
        closed_item_count=status_counts.get("closed_no_owner_action", 0),
        replay_event_count=replay_counts.get("emitted_to_owner_events_jsonl", 0),
        send_whatsapp_count=sum(1 for item in intake_items if item.send_whatsapp),
        crm_mutation_count=sum(1 for item in intake_items if item.crm_mutation),
        intake_status_counts=dict(status_counts),
        replay_event_status_counts=dict(replay_counts),
        output_db=output_db,
        output_jsonl=output_jsonl,
        output_template=output_template,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local owner decision intake rows from the operator packet review console."
    )
    parser.add_argument("--review-console-db", type=Path, default=DEFAULT_REVIEW_CONSOLE_DB)
    parser.add_argument("--owner-decisions-jsonl", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OWNER_DECISION_INTAKE_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--output-jsonl", type=Path, default=None)
    parser.add_argument("--output-template", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_owner_decision_intake(
            review_console_db=args.review_console_db,
            owner_decisions_jsonl=args.owner_decisions_jsonl,
            output_dir=args.output_dir,
            output_db=args.output_db,
            output_jsonl=args.output_jsonl,
            output_template=args.output_template,
            summary_path=args.summary,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Owner decision intake input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Owner decision intake run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Owner decision intake run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "awaiting_owner_decision_count": result.awaiting_owner_decision_count,
                    "awaiting_owner_revisit_count": result.awaiting_owner_revisit_count,
                    "captured_decision_count": result.captured_decision_count,
                    "closed_item_count": result.closed_item_count,
                    "crm_mutation_count": result.crm_mutation_count,
                    "intake_item_count": result.intake_item_count,
                    "no_owner_action_required_count": result.no_owner_action_required_count,
                    "packet_count": result.packet_count,
                    "replay_event_count": result.replay_event_count,
                    "review_item_count": result.review_item_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "source_case_count": result.source_case_count,
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Owner decision intake complete: "
            f"{result.intake_item_count} items -> {result.output_db.name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
