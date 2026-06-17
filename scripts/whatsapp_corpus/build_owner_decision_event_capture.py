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

DEFAULT_APPROVE_REJECT_LEDGER_DIR = Path(
    "research/personal/wa-corpus/approve-reject-ledger"
)
DEFAULT_OWNER_DECISION_EVENT_DIR = Path(
    "research/personal/wa-corpus/owner-decision-events"
)

DEFAULT_LEDGER_DB = DEFAULT_APPROVE_REJECT_LEDGER_DIR / "approve_reject_ledger.local.sqlite"
DEFAULT_OUTPUT_DB = (
    DEFAULT_OWNER_DECISION_EVENT_DIR / "owner_decision_event_capture.local.sqlite"
)
DEFAULT_SUMMARY = (
    DEFAULT_OWNER_DECISION_EVENT_DIR / "owner_decision_event_capture_summary.md"
)

EXPECTED_LEDGER_DB_NAME = "approve_reject_ledger.local.sqlite"
DEFAULT_EVENT_SOURCE = "local_owner_event_capture"
DEFAULT_EVENT_ACTOR = "owner"
CAPTURED_STATUS = "captured"
AWAITING_STATUS = "awaiting_owner_input"
CAPTURED_EVENT_TYPE = "owner_decision_captured"
AWAITING_EVENT_TYPE = "owner_decision_not_submitted"
PENDING_OWNER_DECISION = "pending"
DEFAULT_DECISION_NOTE = "owner_decision_required"


@dataclass(frozen=True)
class LedgerEntryRow:
    entry_id: str
    route_id: str
    case_card_id: str
    brief_id: str
    pack_id: str
    ledger_rank: int
    assigned_lane: str
    decision_type: str
    decision_priority: str
    route_bucket: str
    next_actor: str
    queue_status: str
    decision_status: str
    owner_decision: str
    allowed_decisions: tuple[str, ...]
    recommended_decision: str
    draft_action_type: str
    immutable_event_type: str
    ledger_entry_hash: str
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OwnerDecisionEventInput:
    entry_id: str
    owner_decision: str
    decision_note: str
    event_actor: str
    event_recorded_at_utc: str | None


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
    allowed_decisions: tuple[str, ...]
    recommended_decision: str
    draft_action_type: str
    decision_note: str
    source_ledger_hash: str
    event_hash: str
    event_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OwnerDecisionEventCaptureBuildResult:
    source_case_count: int
    owner_item_count: int
    pack_count: int
    brief_count: int
    queue_item_count: int
    ledger_entry_count: int
    captured_event_count: int
    awaiting_input_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    capture_status_counts: dict[str, int]
    owner_decision_counts: dict[str, int]
    event_type_counts: dict[str, int]
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


def _parse_allowed_decisions(value: str) -> tuple[str, ...]:
    decoded = json.loads(value)
    if not isinstance(decoded, list):
        raise ValueError("allowed_decisions_json must contain a JSON list")
    return tuple(str(item) for item in decoded)


def _hash_event(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_source_metadata(db_path: Path) -> tuple[str, int, int, int, int, int, int]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_LEDGER_DB_NAME,
        label="Approve/Reject Ledger",
    ) as conn:
        row = conn.execute(
            """
            SELECT generated_at_utc, source_case_count, owner_item_count,
                   pack_count, brief_count, queue_item_count, ledger_entry_count
            FROM approve_reject_ledger_runs
            WHERE id = 1
            """
        ).fetchone()
    if row is None:
        return "unknown", 0, 0, 0, 0, 0, 0
    return (
        str(row["generated_at_utc"]),
        int(row["source_case_count"]),
        int(row["owner_item_count"]),
        int(row["pack_count"]),
        int(row["brief_count"]),
        int(row["queue_item_count"]),
        int(row["ledger_entry_count"]),
    )


def read_ledger_entries(db_path: Path) -> tuple[LedgerEntryRow, ...]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_LEDGER_DB_NAME,
        label="Approve/Reject Ledger",
    ) as conn:
        rows = conn.execute(
            """
            SELECT entry_id, route_id, case_card_id, brief_id, pack_id,
                   ledger_rank, assigned_lane, decision_type, decision_priority,
                   route_bucket, next_actor, queue_status, decision_status,
                   owner_decision, allowed_decisions_json, recommended_decision,
                   draft_action_type, immutable_event_type, ledger_entry_hash,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM approve_reject_ledger_entries
            ORDER BY ledger_rank, case_card_id
            """
        ).fetchall()
    return tuple(
        LedgerEntryRow(
            entry_id=str(row["entry_id"]),
            route_id=str(row["route_id"]),
            case_card_id=str(row["case_card_id"]),
            brief_id=str(row["brief_id"]),
            pack_id=str(row["pack_id"]),
            ledger_rank=int(row["ledger_rank"]),
            assigned_lane=str(row["assigned_lane"]),
            decision_type=str(row["decision_type"]),
            decision_priority=str(row["decision_priority"]),
            route_bucket=str(row["route_bucket"]),
            next_actor=str(row["next_actor"]),
            queue_status=str(row["queue_status"]),
            decision_status=str(row["decision_status"]),
            owner_decision=str(row["owner_decision"]),
            allowed_decisions=_parse_allowed_decisions(str(row["allowed_decisions_json"])),
            recommended_decision=str(row["recommended_decision"]),
            draft_action_type=str(row["draft_action_type"]),
            immutable_event_type=str(row["immutable_event_type"]),
            ledger_entry_hash=str(row["ledger_entry_hash"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def _read_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            decoded = json.loads(stripped)
            if not isinstance(decoded, dict):
                raise ValueError(f"Owner event line {line_number} must be a JSON object")
            rows.append(decoded)
    return tuple(rows)


def read_owner_event_inputs(
    jsonl_path: Path | None,
) -> dict[str, OwnerDecisionEventInput]:
    if jsonl_path is None:
        return {}
    events: dict[str, OwnerDecisionEventInput] = {}
    for raw in _read_jsonl(jsonl_path):
        entry_id = raw.get("entry_id")
        owner_decision = raw.get("owner_decision")
        if not isinstance(entry_id, str) or not entry_id:
            raise ValueError("Owner event is missing entry_id")
        if not isinstance(owner_decision, str) or not owner_decision:
            raise ValueError(f"Owner event for {entry_id} is missing owner_decision")
        if entry_id in events:
            raise ValueError(f"Duplicate owner decision event: {entry_id}")
        decision_note = raw.get("decision_note")
        event_actor = raw.get("event_actor")
        event_recorded_at_utc = raw.get("event_recorded_at_utc")
        if event_recorded_at_utc is not None and not isinstance(event_recorded_at_utc, str):
            raise ValueError(f"Owner event for {entry_id} has invalid timestamp")
        events[entry_id] = OwnerDecisionEventInput(
            entry_id=entry_id,
            owner_decision=owner_decision,
            decision_note=(
                decision_note if isinstance(decision_note, str) and decision_note else ""
            ),
            event_actor=(
                event_actor if isinstance(event_actor, str) and event_actor else DEFAULT_EVENT_ACTOR
            ),
            event_recorded_at_utc=event_recorded_at_utc,
        )
    return events


def build_event_rows(
    entries: Sequence[LedgerEntryRow],
    event_inputs: dict[str, OwnerDecisionEventInput],
    *,
    generated_at_utc: str,
) -> tuple[OwnerDecisionEventRow, ...]:
    known_entries = {entry.entry_id for entry in entries}
    unknown_events = sorted(set(event_inputs) - known_entries)
    if unknown_events:
        raise ValueError(f"Owner event references unknown ledger entry: {unknown_events[0]}")

    events: list[OwnerDecisionEventRow] = []
    for rank, entry in enumerate(entries, start=1):
        submitted = event_inputs.get(entry.entry_id)
        if submitted is None:
            capture_status = AWAITING_STATUS
            owner_decision = PENDING_OWNER_DECISION
            event_type = AWAITING_EVENT_TYPE
            decision_note = DEFAULT_DECISION_NOTE
            event_actor = DEFAULT_EVENT_ACTOR
            event_recorded_at_utc = generated_at_utc
        else:
            owner_decision = submitted.owner_decision
            if owner_decision not in entry.allowed_decisions:
                raise ValueError(
                    "Owner decision is not allowed for "
                    f"{entry.entry_id}: {owner_decision}"
                )
            capture_status = CAPTURED_STATUS
            event_type = CAPTURED_EVENT_TYPE
            decision_note = (
                submitted.decision_note or f"owner_decision_{owner_decision}"
            )
            event_actor = submitted.event_actor
            event_recorded_at_utc = _format_utc(
                submitted.event_recorded_at_utc or generated_at_utc
            )

        payload = {
            "schema_version": "owner_decision_event_capture.v1",
            "privacy_mode": "local_only_owner_decision_event_no_raw_text",
            "source_ledger_rank": entry.ledger_rank,
            "source_decision_status": entry.decision_status,
            "capture_status": capture_status,
            "owner_decision": owner_decision,
            "event_type": event_type,
            "event_source": DEFAULT_EVENT_SOURCE,
            "event_actor": event_actor,
            "event_recorded_at_utc": event_recorded_at_utc,
            "decision_note": decision_note,
            "allowed_decisions": list(entry.allowed_decisions),
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        event_id = f"owner-event-{rank:06d}"
        event_hash = _hash_event(
            {
                **payload,
                "event_id": event_id,
                "entry_id": entry.entry_id,
                "route_id": entry.route_id,
                "case_card_id": entry.case_card_id,
                "brief_id": entry.brief_id,
                "pack_id": entry.pack_id,
                "event_rank": rank,
                "source_ledger_hash": entry.ledger_entry_hash,
            }
        )
        events.append(
            OwnerDecisionEventRow(
                event_id=event_id,
                entry_id=entry.entry_id,
                route_id=entry.route_id,
                case_card_id=entry.case_card_id,
                brief_id=entry.brief_id,
                pack_id=entry.pack_id,
                event_rank=rank,
                assigned_lane=entry.assigned_lane,
                decision_type=entry.decision_type,
                decision_priority=entry.decision_priority,
                route_bucket=entry.route_bucket,
                capture_status=capture_status,
                owner_decision=owner_decision,
                event_type=event_type,
                event_source=DEFAULT_EVENT_SOURCE,
                event_actor=event_actor,
                event_recorded_at_utc=event_recorded_at_utc,
                allowed_decisions=entry.allowed_decisions,
                recommended_decision=entry.recommended_decision,
                draft_action_type=entry.draft_action_type,
                decision_note=decision_note,
                source_ledger_hash=entry.ledger_entry_hash,
                event_hash=event_hash,
                event_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(events)


def write_owner_decision_events_sqlite(
    output_db: Path,
    *,
    events: Sequence[OwnerDecisionEventRow],
    source_case_count: int,
    owner_item_count: int,
    pack_count: int,
    brief_count: int,
    queue_item_count: int,
    ledger_entry_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS owner_decision_event_capture_runs;
            DROP TABLE IF EXISTS owner_decision_event_rows;

            CREATE TABLE owner_decision_event_capture_runs (
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
                captured_event_count INTEGER NOT NULL,
                awaiting_input_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE owner_decision_event_rows (
                event_id TEXT PRIMARY KEY,
                entry_id TEXT NOT NULL,
                route_id TEXT NOT NULL,
                case_card_id TEXT NOT NULL,
                brief_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                event_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                route_bucket TEXT NOT NULL,
                capture_status TEXT NOT NULL,
                owner_decision TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_source TEXT NOT NULL,
                event_actor TEXT NOT NULL,
                event_recorded_at_utc TEXT NOT NULL,
                allowed_decisions_json TEXT NOT NULL,
                recommended_decision TEXT NOT NULL,
                draft_action_type TEXT NOT NULL,
                decision_note TEXT NOT NULL,
                source_ledger_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE,
                event_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_owner_decision_event_rank
                ON owner_decision_event_rows(event_rank);
            CREATE INDEX idx_owner_decision_event_entry
                ON owner_decision_event_rows(entry_id);
            CREATE INDEX idx_owner_decision_event_status
                ON owner_decision_event_rows(capture_status);
            CREATE INDEX idx_owner_decision_event_decision
                ON owner_decision_event_rows(owner_decision);
            CREATE INDEX idx_owner_decision_event_type
                ON owner_decision_event_rows(event_type);
            """
        )
        conn.execute(
            """
            INSERT INTO owner_decision_event_capture_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count, brief_count,
                queue_item_count, ledger_entry_count, captured_event_count,
                awaiting_input_count, send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                source_generated_at_utc,
                "local_only_owner_decision_event_no_raw_text_no_send_no_crm_mutation",
                source_case_count,
                owner_item_count,
                pack_count,
                brief_count,
                queue_item_count,
                ledger_entry_count,
                sum(1 for event in events if event.capture_status == CAPTURED_STATUS),
                sum(1 for event in events if event.capture_status == AWAITING_STATUS),
            ),
        )
        conn.executemany(
            """
            INSERT INTO owner_decision_event_rows (
                event_id, entry_id, route_id, case_card_id, brief_id, pack_id,
                event_rank, assigned_lane, decision_type, decision_priority,
                route_bucket, capture_status, owner_decision, event_type,
                event_source, event_actor, event_recorded_at_utc,
                allowed_decisions_json, recommended_decision, draft_action_type,
                decision_note, source_ledger_hash, event_hash,
                event_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    event.event_id,
                    event.entry_id,
                    event.route_id,
                    event.case_card_id,
                    event.brief_id,
                    event.pack_id,
                    event.event_rank,
                    event.assigned_lane,
                    event.decision_type,
                    event.decision_priority,
                    event.route_bucket,
                    event.capture_status,
                    event.owner_decision,
                    event.event_type,
                    event.event_source,
                    event.event_actor,
                    event.event_recorded_at_utc,
                    json.dumps(list(event.allowed_decisions), ensure_ascii=False),
                    event.recommended_decision,
                    event.draft_action_type,
                    event.decision_note,
                    event.source_ledger_hash,
                    event.event_hash,
                    json.dumps(event.event_payload, ensure_ascii=False, sort_keys=True),
                    int(event.send_whatsapp),
                    int(event.crm_mutation),
                    int(event.requires_human_approval),
                )
                for event in events
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
    events: Sequence[OwnerDecisionEventRow],
    source_case_count: int,
    owner_item_count: int,
    pack_count: int,
    brief_count: int,
    queue_item_count: int,
    ledger_entry_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    capture_counts = Counter(event.capture_status for event in events)
    owner_decision_counts = Counter(event.owner_decision for event in events)
    event_type_counts = Counter(event.event_type for event in events)
    decision_counts = Counter(event.decision_type for event in events)
    lane_counts = Counter(event.assigned_lane for event in events)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Owner Decision Event Capture Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source Approve/Reject Ledger UTC: `{source_generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, judgment IDs, approval IDs, pack IDs, brief IDs, route IDs, ledger entry IDs, gap IDs, event IDs, inbox item IDs, or room item IDs.",
        "- Owner decision event rows are local-only and ignored under `research/personal/wa-corpus/`.",
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
        f"| Captured owner events | {capture_counts.get(CAPTURED_STATUS, 0)} |",
        f"| Awaiting owner input | {capture_counts.get(AWAITING_STATUS, 0)} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Capture Status", capture_counts),
        "",
        *_counter_table("Owner Decisions", owner_decision_counts),
        "",
        *_counter_table("Event Types", event_type_counts),
        "",
        *_counter_table("Decision Types", decision_counts),
        "",
        *_counter_table("Assigned Lanes", lane_counts),
        "",
        "## Execution Contract",
        "",
        "- The Owner Decision Event Capture records explicit local owner events when provided.",
        "- Missing owner events remain awaiting owner input and do not become approvals.",
        "- Allowed owner decisions remain approve, reject, and defer.",
        "- It does not parse raw WhatsApp messages.",
        "- It does not call a cloud LLM.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- Human approval remains mandatory before any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_owner_decision_event_capture(
    *,
    ledger_db: Path = DEFAULT_LEDGER_DB,
    owner_events_jsonl: Path | None = None,
    output_dir: Path = DEFAULT_OWNER_DECISION_EVENT_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    generated_at_utc: str | None = None,
) -> OwnerDecisionEventCaptureBuildResult:
    """Capture local owner approve/reject/defer events without acting on them."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    generated = _format_utc(generated_at_utc)
    (
        source_generated,
        source_case_count,
        owner_item_count,
        pack_count,
        brief_count,
        queue_item_count,
        source_ledger_entry_count,
    ) = read_source_metadata(ledger_db)
    entries = read_ledger_entries(ledger_db)
    owner_events = read_owner_event_inputs(owner_events_jsonl)
    events = build_event_rows(entries, owner_events, generated_at_utc=generated)
    source_case_total = source_case_count or len(entries)
    owner_item_total = owner_item_count or len(entries)
    pack_total = pack_count or len(entries)
    brief_total = brief_count or len(entries)
    queue_total = queue_item_count or len(entries)
    ledger_total = source_ledger_entry_count or len(entries)
    write_owner_decision_events_sqlite(
        output_db,
        events=events,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        ledger_entry_count=ledger_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    write_summary(
        summary_path=summary_path,
        events=events,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        ledger_entry_count=ledger_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    return OwnerDecisionEventCaptureBuildResult(
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        ledger_entry_count=ledger_total,
        captured_event_count=sum(
            1 for event in events if event.capture_status == CAPTURED_STATUS
        ),
        awaiting_input_count=sum(
            1 for event in events if event.capture_status == AWAITING_STATUS
        ),
        send_whatsapp_count=sum(1 for event in events if event.send_whatsapp),
        crm_mutation_count=sum(1 for event in events if event.crm_mutation),
        capture_status_counts=dict(Counter(event.capture_status for event in events)),
        owner_decision_counts=dict(Counter(event.owner_decision for event in events)),
        event_type_counts=dict(Counter(event.event_type for event in events)),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture local owner decision events from the approve/reject ledger."
    )
    parser.add_argument("--ledger-db", type=Path, default=DEFAULT_LEDGER_DB)
    parser.add_argument("--owner-events-jsonl", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OWNER_DECISION_EVENT_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_owner_decision_event_capture(
            ledger_db=args.ledger_db,
            owner_events_jsonl=args.owner_events_jsonl,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Owner decision event capture input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Owner decision event capture run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Owner decision event capture run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "awaiting_input_count": result.awaiting_input_count,
                    "brief_count": result.brief_count,
                    "captured_event_count": result.captured_event_count,
                    "crm_mutation_count": result.crm_mutation_count,
                    "ledger_entry_count": result.ledger_entry_count,
                    "owner_item_count": result.owner_item_count,
                    "pack_count": result.pack_count,
                    "queue_item_count": result.queue_item_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "source_case_count": result.source_case_count,
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Owner decision event capture complete: "
            f"{result.ledger_entry_count} entries -> {result.output_db.name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
