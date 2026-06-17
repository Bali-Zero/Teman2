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

DEFAULT_CASE_MEMORY_DIR = Path("research/personal/wa-corpus/case-memory-cards")
DEFAULT_OPERATOR_INBOX_DIR = Path("research/personal/wa-corpus/operator-action-inbox")
DEFAULT_SLA_CLOCK_DIR = Path("research/personal/wa-corpus/operator-sla-clock")
DEFAULT_BREACH_WAR_ROOM_DIR = Path("research/personal/wa-corpus/breach-war-room")
DEFAULT_CASE_TIMELINES_DIR = Path("research/personal/wa-corpus/case-timelines")

DEFAULT_CASE_MEMORY_DB = DEFAULT_CASE_MEMORY_DIR / "case_memory_cards.local.sqlite"
DEFAULT_OPERATOR_INBOX_DB = DEFAULT_OPERATOR_INBOX_DIR / "operator_action_inbox.local.sqlite"
DEFAULT_OPERATOR_SLA_CLOCK_DB = DEFAULT_SLA_CLOCK_DIR / "operator_sla_clock.local.sqlite"
DEFAULT_BREACH_WAR_ROOM_DB = DEFAULT_BREACH_WAR_ROOM_DIR / "breach_war_room.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_CASE_TIMELINES_DIR / "case_timelines.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_CASE_TIMELINES_DIR / "case_timelines_summary.md"

EXPECTED_CASE_MEMORY_DB_NAME = "case_memory_cards.local.sqlite"
EXPECTED_OPERATOR_INBOX_DB_NAME = "operator_action_inbox.local.sqlite"
EXPECTED_OPERATOR_SLA_CLOCK_DB_NAME = "operator_sla_clock.local.sqlite"
EXPECTED_BREACH_WAR_ROOM_DB_NAME = "breach_war_room.local.sqlite"


@dataclass(frozen=True)
class CaseMemoryRow:
    case_card_id: str
    case_status: str
    risk_level: str
    next_best_action: str
    assigned_lane: str
    latest_movement: str
    blocker_code: str
    review_rank: int
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OperatorInboxRow:
    case_card_id: str
    inbox_item_id: str
    queue_rank: int
    assigned_lane: str
    priority_label: str
    queue_bucket: str
    action_code: str
    reason_code: str
    urgency_score: int
    combined_score: int
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class SlaClockRow:
    case_card_id: str
    inbox_item_id: str
    due_at_utc: str
    as_of_utc: str
    minutes_until_due: int
    aging_minutes: int
    sla_status: str
    breach_risk: str
    escalation_label: str
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class WarRoomRow:
    case_card_id: str
    room_item_id: str
    war_room_rank: int
    severity_band: str
    command_channel: str
    decision_gate: str
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class CaseTimeline:
    case_card_id: str
    timeline_rank: int
    timeline_status: str
    highest_risk: str
    assigned_lane: str
    primary_action: str
    latest_movement: str
    blocker_code: str
    event_count: int
    has_war_room_item: bool
    timeline_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class CaseTimelineEvent:
    event_id: str
    case_card_id: str
    event_rank: int
    event_stage: str
    event_status: str
    event_lane: str
    action_code: str
    event_signal: str
    event_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class CaseTimelineBuildResult:
    case_count: int
    event_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    status_counts: dict[str, int]
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


def read_case_memory(db_path: Path) -> tuple[CaseMemoryRow, ...]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_CASE_MEMORY_DB_NAME,
        label="Case Memory",
    ) as conn:
        rows = conn.execute(
            """
            SELECT case_card_id, case_status, risk_level, next_best_action,
                   assigned_lane, latest_movement, blocker_code, review_rank,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM case_memory_cards
            ORDER BY review_rank, case_card_id
            """
        ).fetchall()
    return tuple(
        CaseMemoryRow(
            case_card_id=str(row["case_card_id"]),
            case_status=str(row["case_status"]),
            risk_level=str(row["risk_level"]),
            next_best_action=str(row["next_best_action"]),
            assigned_lane=str(row["assigned_lane"]),
            latest_movement=str(row["latest_movement"]),
            blocker_code=str(row["blocker_code"]),
            review_rank=int(row["review_rank"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def read_operator_inbox(db_path: Path) -> dict[str, OperatorInboxRow]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_OPERATOR_INBOX_DB_NAME,
        label="Operator Inbox",
    ) as conn:
        rows = conn.execute(
            """
            SELECT case_card_id, inbox_item_id, queue_rank, assigned_lane,
                   priority_label, queue_bucket, action_code, reason_code,
                   urgency_score, combined_score, send_whatsapp, crm_mutation,
                   requires_human_approval
            FROM operator_action_inbox
            ORDER BY queue_rank, inbox_item_id
            """
        ).fetchall()
    return {
        str(row["case_card_id"]): OperatorInboxRow(
            case_card_id=str(row["case_card_id"]),
            inbox_item_id=str(row["inbox_item_id"]),
            queue_rank=int(row["queue_rank"]),
            assigned_lane=str(row["assigned_lane"]),
            priority_label=str(row["priority_label"]),
            queue_bucket=str(row["queue_bucket"]),
            action_code=str(row["action_code"]),
            reason_code=str(row["reason_code"]),
            urgency_score=int(row["urgency_score"]),
            combined_score=int(row["combined_score"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    }


def read_sla_clock(db_path: Path) -> dict[str, SlaClockRow]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_OPERATOR_SLA_CLOCK_DB_NAME,
        label="SLA Clock",
    ) as conn:
        rows = conn.execute(
            """
            SELECT case_card_id, inbox_item_id, due_at_utc, as_of_utc,
                   minutes_until_due, aging_minutes, sla_status, breach_risk,
                   escalation_label, send_whatsapp, crm_mutation,
                   requires_human_approval
            FROM operator_sla_clock
            ORDER BY queue_rank, inbox_item_id
            """
        ).fetchall()
    return {
        str(row["case_card_id"]): SlaClockRow(
            case_card_id=str(row["case_card_id"]),
            inbox_item_id=str(row["inbox_item_id"]),
            due_at_utc=str(row["due_at_utc"]),
            as_of_utc=str(row["as_of_utc"]),
            minutes_until_due=int(row["minutes_until_due"]),
            aging_minutes=int(row["aging_minutes"]),
            sla_status=str(row["sla_status"]),
            breach_risk=str(row["breach_risk"]),
            escalation_label=str(row["escalation_label"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    }


def read_war_room(db_path: Path) -> dict[str, WarRoomRow]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_BREACH_WAR_ROOM_DB_NAME,
        label="Breach War Room",
    ) as conn:
        rows = conn.execute(
            """
            SELECT case_card_id, room_item_id, war_room_rank, severity_band,
                   command_channel, decision_gate, send_whatsapp, crm_mutation,
                   requires_human_approval
            FROM breach_war_room
            ORDER BY war_room_rank, room_item_id
            """
        ).fetchall()
    war_room: dict[str, WarRoomRow] = {}
    for row in rows:
        case_card_id = str(row["case_card_id"])
        war_room.setdefault(
            case_card_id,
            WarRoomRow(
                case_card_id=case_card_id,
                room_item_id=str(row["room_item_id"]),
                war_room_rank=int(row["war_room_rank"]),
                severity_band=str(row["severity_band"]),
                command_channel=str(row["command_channel"]),
                decision_gate=str(row["decision_gate"]),
                send_whatsapp=bool(row["send_whatsapp"]),
                crm_mutation=bool(row["crm_mutation"]),
                requires_human_approval=bool(row["requires_human_approval"]),
            ),
        )
    return war_room


def _timeline_status(sla: SlaClockRow | None, war_room: WarRoomRow | None) -> str:
    if war_room is not None:
        return "war_room_active"
    if sla is None:
        return "memory_only"
    if sla.breach_risk in {"breached", "high"}:
        return "sla_hot"
    if sla.sla_status == "due_today":
        return "operator_due_today"
    return "monitor"


def _event_payload(stage: str, **values: object) -> dict[str, object]:
    return {
        "schema_version": "case_timeline_event.v1",
        "event_stage": stage,
        "raw_text_included": False,
        "send_whatsapp": False,
        "crm_mutation": False,
        "requires_human_approval": True,
        **values,
    }


def _build_events(
    card: CaseMemoryRow,
    inbox: OperatorInboxRow | None,
    sla: SlaClockRow | None,
    war_room: WarRoomRow | None,
) -> tuple[CaseTimelineEvent, ...]:
    rows: list[CaseTimelineEvent] = [
        CaseTimelineEvent(
            event_id=f"{card.case_card_id}-event-001",
            case_card_id=card.case_card_id,
            event_rank=1,
            event_stage="case_memory",
            event_status=card.case_status,
            event_lane=card.assigned_lane,
            action_code=card.next_best_action,
            event_signal=card.blocker_code,
            event_payload=_event_payload(
                "case_memory",
                risk_level=card.risk_level,
                latest_movement=card.latest_movement,
                blocker_code=card.blocker_code,
            ),
            send_whatsapp=False,
            crm_mutation=False,
            requires_human_approval=True,
        )
    ]
    if inbox is not None:
        rows.append(
            CaseTimelineEvent(
                event_id=f"{card.case_card_id}-event-{len(rows) + 1:03d}",
                case_card_id=card.case_card_id,
                event_rank=len(rows) + 1,
                event_stage="operator_action",
                event_status=inbox.priority_label,
                event_lane=inbox.assigned_lane,
                action_code=inbox.action_code,
                event_signal=inbox.reason_code,
                event_payload=_event_payload(
                    "operator_action",
                    queue_bucket=inbox.queue_bucket,
                    urgency_score=inbox.urgency_score,
                    combined_score=inbox.combined_score,
                ),
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    if sla is not None:
        rows.append(
            CaseTimelineEvent(
                event_id=f"{card.case_card_id}-event-{len(rows) + 1:03d}",
                case_card_id=card.case_card_id,
                event_rank=len(rows) + 1,
                event_stage="sla_clock",
                event_status=sla.sla_status,
                event_lane=(inbox.assigned_lane if inbox is not None else card.assigned_lane),
                action_code=(inbox.action_code if inbox is not None else card.next_best_action),
                event_signal=sla.breach_risk,
                event_payload=_event_payload(
                    "sla_clock",
                    minutes_until_due=sla.minutes_until_due,
                    aging_minutes=sla.aging_minutes,
                    escalation_label=sla.escalation_label,
                ),
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    if war_room is not None:
        rows.append(
            CaseTimelineEvent(
                event_id=f"{card.case_card_id}-event-{len(rows) + 1:03d}",
                case_card_id=card.case_card_id,
                event_rank=len(rows) + 1,
                event_stage="war_room",
                event_status=war_room.severity_band,
                event_lane=(inbox.assigned_lane if inbox is not None else card.assigned_lane),
                action_code=(inbox.action_code if inbox is not None else card.next_best_action),
                event_signal=war_room.command_channel,
                event_payload=_event_payload(
                    "war_room",
                    severity_band=war_room.severity_band,
                    command_channel=war_room.command_channel,
                    decision_gate=war_room.decision_gate,
                ),
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(rows)


def build_timelines(
    cards: Sequence[CaseMemoryRow],
    inbox_by_case: dict[str, OperatorInboxRow],
    sla_by_case: dict[str, SlaClockRow],
    war_room_by_case: dict[str, WarRoomRow],
) -> tuple[tuple[CaseTimeline, ...], tuple[CaseTimelineEvent, ...]]:
    timelines: list[CaseTimeline] = []
    events: list[CaseTimelineEvent] = []
    for rank, card in enumerate(cards, start=1):
        inbox = inbox_by_case.get(card.case_card_id)
        sla = sla_by_case.get(card.case_card_id)
        war_room = war_room_by_case.get(card.case_card_id)
        case_events = _build_events(card, inbox, sla, war_room)
        events.extend(case_events)
        assigned_lane = inbox.assigned_lane if inbox is not None else card.assigned_lane
        primary_action = inbox.action_code if inbox is not None else card.next_best_action
        payload = {
            "schema_version": "case_timeline_synthesizer.v1",
            "privacy_mode": "local_only_case_timeline_no_raw_text",
            "timeline_status": _timeline_status(sla, war_room),
            "highest_risk": card.risk_level,
            "event_count": len(case_events),
            "has_war_room_item": war_room is not None,
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        timelines.append(
            CaseTimeline(
                case_card_id=card.case_card_id,
                timeline_rank=rank,
                timeline_status=_timeline_status(sla, war_room),
                highest_risk=card.risk_level,
                assigned_lane=assigned_lane,
                primary_action=primary_action,
                latest_movement=card.latest_movement,
                blocker_code=card.blocker_code,
                event_count=len(case_events),
                has_war_room_item=war_room is not None,
                timeline_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(timelines), tuple(events)


def write_timeline_sqlite(
    path: Path,
    *,
    timelines: Sequence[CaseTimeline],
    events: Sequence[CaseTimelineEvent],
    generated_at_utc: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE case_timeline_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                case_count INTEGER NOT NULL,
                event_count INTEGER NOT NULL,
                war_room_case_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE case_timelines (
                case_card_id TEXT PRIMARY KEY,
                timeline_rank INTEGER NOT NULL,
                timeline_status TEXT NOT NULL,
                highest_risk TEXT NOT NULL,
                assigned_lane TEXT NOT NULL,
                primary_action TEXT NOT NULL,
                latest_movement TEXT NOT NULL,
                blocker_code TEXT NOT NULL,
                event_count INTEGER NOT NULL,
                has_war_room_item INTEGER NOT NULL,
                timeline_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE TABLE case_timeline_events (
                event_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                event_rank INTEGER NOT NULL,
                event_stage TEXT NOT NULL,
                event_status TEXT NOT NULL,
                event_lane TEXT NOT NULL,
                action_code TEXT NOT NULL,
                event_signal TEXT NOT NULL,
                event_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_case_timelines_status ON case_timelines(timeline_status);
            CREATE INDEX idx_case_timelines_lane ON case_timelines(assigned_lane);
            CREATE INDEX idx_case_timeline_events_case ON case_timeline_events(case_card_id);
            CREATE INDEX idx_case_timeline_events_stage ON case_timeline_events(event_stage);
            """
        )
        conn.execute(
            """
            INSERT INTO case_timeline_runs (
                id, generated_at_utc, privacy_mode, case_count, event_count,
                war_room_case_count, send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                "local_only_case_timeline_no_raw_text_no_send_no_crm_mutation",
                len(timelines),
                len(events),
                sum(1 for timeline in timelines if timeline.has_war_room_item),
            ),
        )
        conn.executemany(
            """
            INSERT INTO case_timelines (
                case_card_id, timeline_rank, timeline_status, highest_risk,
                assigned_lane, primary_action, latest_movement, blocker_code,
                event_count, has_war_room_item, timeline_payload_json,
                send_whatsapp, crm_mutation, requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    timeline.case_card_id,
                    timeline.timeline_rank,
                    timeline.timeline_status,
                    timeline.highest_risk,
                    timeline.assigned_lane,
                    timeline.primary_action,
                    timeline.latest_movement,
                    timeline.blocker_code,
                    timeline.event_count,
                    int(timeline.has_war_room_item),
                    json.dumps(timeline.timeline_payload, ensure_ascii=False, sort_keys=True),
                    int(timeline.send_whatsapp),
                    int(timeline.crm_mutation),
                    int(timeline.requires_human_approval),
                )
                for timeline in timelines
            ],
        )
        conn.executemany(
            """
            INSERT INTO case_timeline_events (
                event_id, case_card_id, event_rank, event_stage, event_status,
                event_lane, action_code, event_signal, event_payload_json,
                send_whatsapp, crm_mutation, requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    event.event_id,
                    event.case_card_id,
                    event.event_rank,
                    event.event_stage,
                    event.event_status,
                    event.event_lane,
                    event.action_code,
                    event.event_signal,
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
    timelines: Sequence[CaseTimeline],
    events: Sequence[CaseTimelineEvent],
    generated_at_utc: str,
) -> None:
    status_counts = Counter(timeline.timeline_status for timeline in timelines)
    risk_counts = Counter(timeline.highest_risk for timeline in timelines)
    lane_counts = Counter(timeline.assigned_lane for timeline in timelines)
    action_counts = Counter(timeline.primary_action for timeline in timelines)
    stage_counts = Counter(event.event_stage for event in events)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Case Timeline Synthesizer Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, inbox item IDs, room item IDs, shadow IDs, or window IDs.",
        "- Timeline rows are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Cases synthesized | {len(timelines)} |",
        f"| Timeline events | {len(events)} |",
        f"| War room cases | {sum(1 for timeline in timelines if timeline.has_war_room_item)} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Timeline Status", status_counts),
        "",
        *_counter_table("Risk Levels", risk_counts),
        "",
        *_counter_table("Assigned Lanes", lane_counts),
        "",
        *_counter_table("Primary Actions", action_counts),
        "",
        *_counter_table("Event Stages", stage_counts),
        "",
        "## Execution Contract",
        "",
        "- The Case Timeline Synthesizer composes local operational artifacts into a case timeline.",
        "- It does not parse raw WhatsApp messages.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- A human must approve any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_case_timeline_synthesizer(
    *,
    case_memory_db: Path = DEFAULT_CASE_MEMORY_DB,
    operator_inbox_db: Path = DEFAULT_OPERATOR_INBOX_DB,
    operator_sla_clock_db: Path = DEFAULT_OPERATOR_SLA_CLOCK_DB,
    breach_war_room_db: Path = DEFAULT_BREACH_WAR_ROOM_DB,
    output_dir: Path = DEFAULT_CASE_TIMELINES_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    generated_at_utc: str | None = None,
) -> CaseTimelineBuildResult:
    """Build local-only operational timelines from case artifacts."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    generated = _format_utc(generated_at_utc)
    cards = read_case_memory(case_memory_db)
    inbox_by_case = read_operator_inbox(operator_inbox_db)
    sla_by_case = read_sla_clock(operator_sla_clock_db)
    war_room_by_case = read_war_room(breach_war_room_db)
    timelines, events = build_timelines(cards, inbox_by_case, sla_by_case, war_room_by_case)
    write_timeline_sqlite(
        output_db,
        timelines=timelines,
        events=events,
        generated_at_utc=generated,
    )
    write_summary(
        summary_path=summary_path,
        timelines=timelines,
        events=events,
        generated_at_utc=generated,
    )
    return CaseTimelineBuildResult(
        case_count=len(timelines),
        event_count=len(events),
        send_whatsapp_count=sum(1 for timeline in timelines if timeline.send_whatsapp),
        crm_mutation_count=sum(1 for timeline in timelines if timeline.crm_mutation),
        status_counts=dict(Counter(timeline.timeline_status for timeline in timelines)),
        lane_counts=dict(Counter(timeline.assigned_lane for timeline in timelines)),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara case timelines from operational artifacts."
    )
    parser.add_argument("--case-memory-db", type=Path, default=DEFAULT_CASE_MEMORY_DB)
    parser.add_argument("--operator-inbox-db", type=Path, default=DEFAULT_OPERATOR_INBOX_DB)
    parser.add_argument("--operator-sla-clock-db", type=Path, default=DEFAULT_OPERATOR_SLA_CLOCK_DB)
    parser.add_argument("--breach-war-room-db", type=Path, default=DEFAULT_BREACH_WAR_ROOM_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_CASE_TIMELINES_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_case_timeline_synthesizer(
            case_memory_db=args.case_memory_db,
            operator_inbox_db=args.operator_inbox_db,
            operator_sla_clock_db=args.operator_sla_clock_db,
            breach_war_room_db=args.breach_war_room_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, sqlite3.Error, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "case_count": result.case_count,
                    "event_count": result.event_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "crm_mutation_count": result.crm_mutation_count,
                    "output_db": str(result.output_db),
                    "summary_path": str(result.summary_path),
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
