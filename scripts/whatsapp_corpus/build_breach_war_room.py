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

DEFAULT_SLA_CLOCK_DIR = Path("research/personal/wa-corpus/operator-sla-clock")
DEFAULT_BREACH_WAR_ROOM_DIR = Path("research/personal/wa-corpus/breach-war-room")
DEFAULT_OPERATOR_SLA_CLOCK_DB = DEFAULT_SLA_CLOCK_DIR / "operator_sla_clock.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_BREACH_WAR_ROOM_DIR / "breach_war_room.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_BREACH_WAR_ROOM_DIR / "breach_war_room_summary.md"

EXPECTED_SLA_CLOCK_DB_NAME = "operator_sla_clock.local.sqlite"


@dataclass(frozen=True)
class SlaClockRow:
    inbox_item_id: str
    case_card_id: str
    queue_rank: int
    assigned_lane: str
    priority_label: str
    queue_bucket: str
    action_code: str
    reason_code: str
    due_at_utc: str
    as_of_utc: str
    minutes_until_due: int
    aging_minutes: int
    sla_status: str
    breach_risk: str
    escalation_label: str
    clock_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class BreachWarRoomItem:
    room_item_id: str
    inbox_item_id: str
    case_card_id: str
    source_queue_rank: int
    war_room_rank: int
    assigned_lane: str
    priority_label: str
    queue_bucket: str
    action_code: str
    reason_code: str
    due_at_utc: str
    as_of_utc: str
    minutes_until_due: int
    aging_minutes: int
    sla_status: str
    breach_risk: str
    escalation_label: str
    severity_band: str
    command_channel: str
    decision_gate: str
    captain_instruction: str
    war_room_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class BreachWarRoomBuildResult:
    clock_count: int
    room_item_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    severity_counts: dict[str, int]
    lane_counts: dict[str, int]
    output_db: Path
    summary_path: Path


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _connect_sla_clock(db_path: Path) -> sqlite3.Connection:
    if db_path.name != EXPECTED_SLA_CLOCK_DB_NAME:
        raise ValueError(f"Refusing to read unexpected SLA Clock DB: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"SLA Clock DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_sla_clock(
    db_path: Path,
) -> tuple[str, str, tuple[SlaClockRow, ...]]:
    with _connect_sla_clock(db_path) as conn:
        run = conn.execute(
            "SELECT generated_at_utc, as_of_utc FROM operator_sla_clock_runs WHERE id = 1"
        ).fetchone()
        if run is None:
            raise ValueError("SLA Clock DB is missing operator_sla_clock_runs row 1")
        rows = conn.execute(
            """
            SELECT inbox_item_id, case_card_id, queue_rank, assigned_lane,
                   priority_label, queue_bucket, action_code, reason_code,
                   due_at_utc, as_of_utc, minutes_until_due, aging_minutes,
                   sla_status, breach_risk, escalation_label, clock_payload_json,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM operator_sla_clock
            ORDER BY queue_rank, inbox_item_id
            """
        ).fetchall()
    return (
        str(run["generated_at_utc"]),
        str(run["as_of_utc"]),
        tuple(
            SlaClockRow(
                inbox_item_id=str(row["inbox_item_id"]),
                case_card_id=str(row["case_card_id"]),
                queue_rank=int(row["queue_rank"]),
                assigned_lane=str(row["assigned_lane"]),
                priority_label=str(row["priority_label"]),
                queue_bucket=str(row["queue_bucket"]),
                action_code=str(row["action_code"]),
                reason_code=str(row["reason_code"]),
                due_at_utc=str(row["due_at_utc"]),
                as_of_utc=str(row["as_of_utc"]),
                minutes_until_due=int(row["minutes_until_due"]),
                aging_minutes=int(row["aging_minutes"]),
                sla_status=str(row["sla_status"]),
                breach_risk=str(row["breach_risk"]),
                escalation_label=str(row["escalation_label"]),
                clock_payload=json.loads(str(row["clock_payload_json"])),
                send_whatsapp=bool(row["send_whatsapp"]),
                crm_mutation=bool(row["crm_mutation"]),
                requires_human_approval=bool(row["requires_human_approval"]),
            )
            for row in rows
        ),
    )


def _is_war_room_candidate(row: SlaClockRow) -> bool:
    return row.sla_status == "overdue" or row.breach_risk in {"breached", "high"}


def _severity_band(row: SlaClockRow) -> str:
    if row.sla_status == "overdue" or row.breach_risk == "breached":
        return "critical"
    if row.breach_risk == "high":
        return "hot"
    return "watch"


def _command_channel(severity_band: str) -> str:
    return {
        "critical": "owner_war_room",
        "hot": "lane_hot_queue",
        "watch": "operator_watch_queue",
    }.get(severity_band, "operator_watch_queue")


def _decision_gate(severity_band: str) -> str:
    return {
        "critical": "owner_review_required",
        "hot": "lane_lead_review_required",
        "watch": "operator_review_required",
    }.get(severity_band, "operator_review_required")


def _sort_key(row: SlaClockRow) -> tuple[int, int, int, str]:
    severity_rank = {"critical": 0, "hot": 1, "watch": 2}
    return (
        severity_rank.get(_severity_band(row), 9),
        row.minutes_until_due,
        row.queue_rank,
        row.inbox_item_id,
    )


def build_war_room_items(rows: Sequence[SlaClockRow]) -> tuple[BreachWarRoomItem, ...]:
    candidates = sorted((row for row in rows if _is_war_room_candidate(row)), key=_sort_key)
    items: list[BreachWarRoomItem] = []
    for rank, row in enumerate(candidates, start=1):
        severity = _severity_band(row)
        command_channel = _command_channel(severity)
        decision_gate = _decision_gate(severity)
        captain_instruction = (
            f"Review {row.assigned_lane} {row.action_code} SLA clock: "
            f"{severity} risk, {row.minutes_until_due} minutes until due."
        )
        payload = {
            "schema_version": "breach_war_room.v1",
            "privacy_mode": "local_only_breach_war_room_no_raw_text",
            "source_priority_label": row.priority_label,
            "source_queue_bucket": row.queue_bucket,
            "source_action_code": row.action_code,
            "source_reason_code": row.reason_code,
            "source_sla_status": row.sla_status,
            "source_breach_risk": row.breach_risk,
            "severity_band": severity,
            "command_channel": command_channel,
            "decision_gate": decision_gate,
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        items.append(
            BreachWarRoomItem(
                room_item_id=f"war-room-{rank:06d}",
                inbox_item_id=row.inbox_item_id,
                case_card_id=row.case_card_id,
                source_queue_rank=row.queue_rank,
                war_room_rank=rank,
                assigned_lane=row.assigned_lane,
                priority_label=row.priority_label,
                queue_bucket=row.queue_bucket,
                action_code=row.action_code,
                reason_code=row.reason_code,
                due_at_utc=row.due_at_utc,
                as_of_utc=row.as_of_utc,
                minutes_until_due=row.minutes_until_due,
                aging_minutes=row.aging_minutes,
                sla_status=row.sla_status,
                breach_risk=row.breach_risk,
                escalation_label=row.escalation_label,
                severity_band=severity,
                command_channel=command_channel,
                decision_gate=decision_gate,
                captain_instruction=captain_instruction,
                war_room_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(items)


def write_war_room_sqlite(
    path: Path,
    *,
    items: Sequence[BreachWarRoomItem],
    clock_count: int,
    source_sla_clock_generated_at_utc: str,
    source_as_of_utc: str,
    generated_at_utc: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE breach_war_room_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_sla_clock_generated_at_utc TEXT NOT NULL,
                source_as_of_utc TEXT NOT NULL,
                clock_count INTEGER NOT NULL,
                room_item_count INTEGER NOT NULL,
                critical_count INTEGER NOT NULL,
                hot_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE breach_war_room (
                room_item_id TEXT PRIMARY KEY,
                inbox_item_id TEXT NOT NULL,
                case_card_id TEXT NOT NULL,
                source_queue_rank INTEGER NOT NULL,
                war_room_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                priority_label TEXT NOT NULL,
                queue_bucket TEXT NOT NULL,
                action_code TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                due_at_utc TEXT NOT NULL,
                as_of_utc TEXT NOT NULL,
                minutes_until_due INTEGER NOT NULL,
                aging_minutes INTEGER NOT NULL,
                sla_status TEXT NOT NULL,
                breach_risk TEXT NOT NULL,
                escalation_label TEXT NOT NULL,
                severity_band TEXT NOT NULL,
                command_channel TEXT NOT NULL,
                decision_gate TEXT NOT NULL,
                captain_instruction TEXT NOT NULL,
                war_room_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_breach_war_room_severity ON breach_war_room(severity_band);
            CREATE INDEX idx_breach_war_room_lane ON breach_war_room(assigned_lane);
            CREATE INDEX idx_breach_war_room_due ON breach_war_room(due_at_utc);
            CREATE INDEX idx_breach_war_room_channel ON breach_war_room(command_channel);
            """
        )
        severity_counts = Counter(item.severity_band for item in items)
        conn.execute(
            """
            INSERT INTO breach_war_room_runs (
                id, generated_at_utc, privacy_mode,
                source_sla_clock_generated_at_utc, source_as_of_utc,
                clock_count, room_item_count, critical_count, hot_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                "local_only_breach_war_room_no_raw_text_no_send_no_crm_mutation",
                source_sla_clock_generated_at_utc,
                source_as_of_utc,
                clock_count,
                len(items),
                severity_counts.get("critical", 0),
                severity_counts.get("hot", 0),
            ),
        )
        conn.executemany(
            """
            INSERT INTO breach_war_room (
                room_item_id, inbox_item_id, case_card_id, source_queue_rank,
                war_room_rank, assigned_lane, priority_label, queue_bucket,
                action_code, reason_code, due_at_utc, as_of_utc,
                minutes_until_due, aging_minutes, sla_status, breach_risk,
                escalation_label, severity_band, command_channel, decision_gate,
                captain_instruction, war_room_payload_json, send_whatsapp,
                crm_mutation, requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.room_item_id,
                    item.inbox_item_id,
                    item.case_card_id,
                    item.source_queue_rank,
                    item.war_room_rank,
                    item.assigned_lane,
                    item.priority_label,
                    item.queue_bucket,
                    item.action_code,
                    item.reason_code,
                    item.due_at_utc,
                    item.as_of_utc,
                    item.minutes_until_due,
                    item.aging_minutes,
                    item.sla_status,
                    item.breach_risk,
                    item.escalation_label,
                    item.severity_band,
                    item.command_channel,
                    item.decision_gate,
                    item.captain_instruction,
                    json.dumps(item.war_room_payload, ensure_ascii=False, sort_keys=True),
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
    items: Sequence[BreachWarRoomItem],
    clock_count: int,
    source_sla_clock_generated_at_utc: str,
    source_as_of_utc: str,
    generated_at_utc: str,
) -> None:
    severity_counts = Counter(item.severity_band for item in items)
    lane_counts = Counter(item.assigned_lane for item in items)
    action_counts = Counter(item.action_code for item in items)
    channel_counts = Counter(item.command_channel for item in items)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Breach War Room Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source SLA Clock generated UTC: `{source_sla_clock_generated_at_utc}`",
        f"Source as-of UTC: `{source_as_of_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, inbox item IDs, room item IDs, shadow IDs, or window IDs.",
        "- War room rows are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| SLA clocks reviewed | {clock_count} |",
        f"| War room items | {len(items)} |",
        f"| Critical items | {severity_counts.get('critical', 0)} |",
        f"| Hot items | {severity_counts.get('hot', 0)} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Severity Bands", severity_counts),
        "",
        *_counter_table("Assigned Lanes", lane_counts),
        "",
        *_counter_table("Action Codes", action_counts),
        "",
        *_counter_table("Command Channels", channel_counts),
        "",
        "## Execution Contract",
        "",
        "- The Breach War Room prioritizes urgent clocks for owner and lane review.",
        "- It does not execute any action.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- A human must approve any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_breach_war_room(
    *,
    operator_sla_clock_db: Path = DEFAULT_OPERATOR_SLA_CLOCK_DB,
    output_dir: Path = DEFAULT_BREACH_WAR_ROOM_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    generated_at_utc: str | None = None,
) -> BreachWarRoomBuildResult:
    """Build a local-only breach war room from the Operator SLA Clock."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    source_sla_generated_at_utc, source_as_of_utc, rows = read_sla_clock(operator_sla_clock_db)
    now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    generated = _format_utc(_parse_utc(generated_at_utc or now_utc))
    items = build_war_room_items(rows)
    write_war_room_sqlite(
        output_db,
        items=items,
        clock_count=len(rows),
        source_sla_clock_generated_at_utc=source_sla_generated_at_utc,
        source_as_of_utc=source_as_of_utc,
        generated_at_utc=generated,
    )
    write_summary(
        summary_path=summary_path,
        items=items,
        clock_count=len(rows),
        source_sla_clock_generated_at_utc=source_sla_generated_at_utc,
        source_as_of_utc=source_as_of_utc,
        generated_at_utc=generated,
    )
    return BreachWarRoomBuildResult(
        clock_count=len(rows),
        room_item_count=len(items),
        send_whatsapp_count=sum(1 for item in items if item.send_whatsapp),
        crm_mutation_count=sum(1 for item in items if item.crm_mutation),
        severity_counts=dict(Counter(item.severity_band for item in items)),
        lane_counts=dict(Counter(item.assigned_lane for item in items)),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a local-only Zantara Breach War Room from the SLA clock."
    )
    parser.add_argument("--operator-sla-clock-db", type=Path, default=DEFAULT_OPERATOR_SLA_CLOCK_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_BREACH_WAR_ROOM_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_breach_war_room(
            operator_sla_clock_db=args.operator_sla_clock_db,
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
                    "clock_count": result.clock_count,
                    "room_item_count": result.room_item_count,
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
