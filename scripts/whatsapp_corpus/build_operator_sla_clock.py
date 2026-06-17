from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

DEFAULT_OPERATOR_INBOX_DIR = Path("research/personal/wa-corpus/operator-action-inbox")
DEFAULT_SLA_CLOCK_DIR = Path("research/personal/wa-corpus/operator-sla-clock")
DEFAULT_OPERATOR_INBOX_DB = DEFAULT_OPERATOR_INBOX_DIR / "operator_action_inbox.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_SLA_CLOCK_DIR / "operator_sla_clock.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_SLA_CLOCK_DIR / "operator_sla_clock_summary.md"

EXPECTED_OPERATOR_INBOX_DB_NAME = "operator_action_inbox.local.sqlite"

SLA_MINUTES_BY_BUCKET = {
    "finance_now": 120,
    "follow_up_now": 240,
    "status_check_now": 240,
    "team_escalation_now": 240,
    "document_gap_now": 360,
    "finance_today": 480,
    "follow_up_today": 720,
    "document_gap_today": 1440,
    "status_check_today": 1440,
    "team_escalation_today": 1440,
}


@dataclass(frozen=True)
class OperatorInboxRow:
    inbox_item_id: str
    case_card_id: str
    queue_rank: int
    assigned_lane: str
    priority_label: str
    queue_bucket: str
    action_code: str
    reason_code: str
    urgency_score: int
    combined_score: int
    approval_mode: str
    item_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OperatorSlaClock:
    inbox_item_id: str
    case_card_id: str
    queue_rank: int
    assigned_lane: str
    priority_label: str
    queue_bucket: str
    action_code: str
    reason_code: str
    sla_minutes: int
    source_inbox_generated_at_utc: str
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
class OperatorSlaClockBuildResult:
    inbox_item_count: int
    clock_count: int
    overdue_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    status_counts: dict[str, int]
    breach_risk_counts: dict[str, int]
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


def _connect_operator_inbox(db_path: Path) -> sqlite3.Connection:
    if db_path.name != EXPECTED_OPERATOR_INBOX_DB_NAME:
        raise ValueError(f"Refusing to read unexpected Operator Inbox DB: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"Operator Inbox DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_operator_inbox(
    db_path: Path,
) -> tuple[str, tuple[OperatorInboxRow, ...]]:
    with _connect_operator_inbox(db_path) as conn:
        run = conn.execute(
            "SELECT generated_at_utc FROM operator_action_inbox_runs WHERE id = 1"
        ).fetchone()
        if run is None:
            raise ValueError("Operator Inbox DB is missing operator_action_inbox_runs row 1")
        rows = conn.execute(
            """
            SELECT inbox_item_id, case_card_id, queue_rank, assigned_lane,
                   priority_label, queue_bucket, action_code, reason_code,
                   urgency_score, combined_score, approval_mode,
                   item_payload_json, send_whatsapp, crm_mutation,
                   requires_human_approval
            FROM operator_action_inbox
            ORDER BY queue_rank, inbox_item_id
            """
        ).fetchall()
    return (
        str(run["generated_at_utc"]),
        tuple(
            OperatorInboxRow(
                inbox_item_id=str(row["inbox_item_id"]),
                case_card_id=str(row["case_card_id"]),
                queue_rank=int(row["queue_rank"]),
                assigned_lane=str(row["assigned_lane"]),
                priority_label=str(row["priority_label"]),
                queue_bucket=str(row["queue_bucket"]),
                action_code=str(row["action_code"]),
                reason_code=str(row["reason_code"]),
                urgency_score=int(row["urgency_score"]),
                combined_score=int(row["combined_score"]),
                approval_mode=str(row["approval_mode"]),
                item_payload=json.loads(str(row["item_payload_json"])),
                send_whatsapp=bool(row["send_whatsapp"]),
                crm_mutation=bool(row["crm_mutation"]),
                requires_human_approval=bool(row["requires_human_approval"]),
            )
            for row in rows
        ),
    )


def _sla_minutes(row: OperatorInboxRow) -> int:
    if row.queue_bucket in SLA_MINUTES_BY_BUCKET:
        return SLA_MINUTES_BY_BUCKET[row.queue_bucket]
    return {"now": 240, "today": 1440, "next": 4320}.get(row.priority_label, 1440)


def _sla_status(minutes_until_due: int) -> str:
    if minutes_until_due < 0:
        return "overdue"
    if minutes_until_due <= 240:
        return "due_today"
    if minutes_until_due <= 1440:
        return "due_today"
    return "scheduled"


def _breach_risk(status: str, minutes_until_due: int, priority_label: str) -> str:
    if status == "overdue":
        return "breached"
    if priority_label == "now" or minutes_until_due <= 240:
        return "high"
    if status == "due_today":
        return "medium"
    return "low"


def _escalation_label(breach_risk: str) -> str:
    return {
        "breached": "owner_review",
        "high": "lane_lead_watch",
        "medium": "operator_watch",
        "low": "none",
    }.get(breach_risk, "operator_watch")


def build_sla_clocks(
    rows: Sequence[OperatorInboxRow],
    *,
    source_inbox_generated_at_utc: str,
    as_of_utc: str,
) -> tuple[OperatorSlaClock, ...]:
    source_generated = _parse_utc(source_inbox_generated_at_utc)
    as_of = _parse_utc(as_of_utc)
    clocks: list[OperatorSlaClock] = []
    for row in rows:
        sla_minutes = _sla_minutes(row)
        due_at = source_generated + timedelta(minutes=sla_minutes)
        minutes_until_due = int((due_at - as_of).total_seconds() // 60)
        aging_minutes = max(0, int((as_of - source_generated).total_seconds() // 60))
        status = _sla_status(minutes_until_due)
        risk = _breach_risk(status, minutes_until_due, row.priority_label)
        payload = {
            "schema_version": "operator_sla_clock.v1",
            "privacy_mode": "local_only_operator_sla_no_raw_text",
            "source_priority_label": row.priority_label,
            "source_queue_bucket": row.queue_bucket,
            "source_action_code": row.action_code,
            "source_reason_code": row.reason_code,
            "source_risk_level": row.item_payload.get("source_risk_level", "unknown"),
            "latest_movement": row.item_payload.get("latest_movement", "unknown"),
            "sla_minutes": sla_minutes,
            "sla_status": status,
            "breach_risk": risk,
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        clocks.append(
            OperatorSlaClock(
                inbox_item_id=row.inbox_item_id,
                case_card_id=row.case_card_id,
                queue_rank=row.queue_rank,
                assigned_lane=row.assigned_lane,
                priority_label=row.priority_label,
                queue_bucket=row.queue_bucket,
                action_code=row.action_code,
                reason_code=row.reason_code,
                sla_minutes=sla_minutes,
                source_inbox_generated_at_utc=_format_utc(source_generated),
                due_at_utc=_format_utc(due_at),
                as_of_utc=_format_utc(as_of),
                minutes_until_due=minutes_until_due,
                aging_minutes=aging_minutes,
                sla_status=status,
                breach_risk=risk,
                escalation_label=_escalation_label(risk),
                clock_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(clocks)


def write_sla_sqlite(path: Path, clocks: Sequence[OperatorSlaClock], generated_at_utc: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE operator_sla_clock_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_inbox_generated_at_utc TEXT NOT NULL,
                as_of_utc TEXT NOT NULL,
                inbox_item_count INTEGER NOT NULL,
                clock_count INTEGER NOT NULL,
                overdue_count INTEGER NOT NULL,
                breach_risk_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE operator_sla_clock (
                inbox_item_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                queue_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                priority_label TEXT NOT NULL,
                queue_bucket TEXT NOT NULL,
                action_code TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                sla_minutes INTEGER NOT NULL,
                source_inbox_generated_at_utc TEXT NOT NULL,
                due_at_utc TEXT NOT NULL,
                as_of_utc TEXT NOT NULL,
                minutes_until_due INTEGER NOT NULL,
                aging_minutes INTEGER NOT NULL,
                sla_status TEXT NOT NULL,
                breach_risk TEXT NOT NULL,
                escalation_label TEXT NOT NULL,
                clock_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_operator_sla_clock_status ON operator_sla_clock(sla_status);
            CREATE INDEX idx_operator_sla_clock_risk ON operator_sla_clock(breach_risk);
            CREATE INDEX idx_operator_sla_clock_due ON operator_sla_clock(due_at_utc);
            CREATE INDEX idx_operator_sla_clock_lane ON operator_sla_clock(assigned_lane);
            """
        )
        source_generated = clocks[0].source_inbox_generated_at_utc if clocks else ""
        as_of = clocks[0].as_of_utc if clocks else ""
        conn.execute(
            """
            INSERT INTO operator_sla_clock_runs (
                id, generated_at_utc, privacy_mode, source_inbox_generated_at_utc,
                as_of_utc, inbox_item_count, clock_count, overdue_count,
                breach_risk_count, send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                "local_only_operator_sla_clock_no_raw_text_no_send_no_crm_mutation",
                source_generated,
                as_of,
                len(clocks),
                len(clocks),
                sum(1 for clock in clocks if clock.sla_status == "overdue"),
                sum(1 for clock in clocks if clock.breach_risk in {"breached", "high"}),
            ),
        )
        conn.executemany(
            """
            INSERT INTO operator_sla_clock (
                inbox_item_id, case_card_id, queue_rank, assigned_lane, priority_label,
                queue_bucket, action_code, reason_code, sla_minutes,
                source_inbox_generated_at_utc, due_at_utc, as_of_utc,
                minutes_until_due, aging_minutes, sla_status, breach_risk,
                escalation_label, clock_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    clock.inbox_item_id,
                    clock.case_card_id,
                    clock.queue_rank,
                    clock.assigned_lane,
                    clock.priority_label,
                    clock.queue_bucket,
                    clock.action_code,
                    clock.reason_code,
                    clock.sla_minutes,
                    clock.source_inbox_generated_at_utc,
                    clock.due_at_utc,
                    clock.as_of_utc,
                    clock.minutes_until_due,
                    clock.aging_minutes,
                    clock.sla_status,
                    clock.breach_risk,
                    clock.escalation_label,
                    json.dumps(clock.clock_payload, ensure_ascii=False, sort_keys=True),
                    int(clock.send_whatsapp),
                    int(clock.crm_mutation),
                    int(clock.requires_human_approval),
                )
                for clock in clocks
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
    clocks: Sequence[OperatorSlaClock],
    generated_at_utc: str,
) -> None:
    status_counts = Counter(clock.sla_status for clock in clocks)
    breach_risk_counts = Counter(clock.breach_risk for clock in clocks)
    escalation_counts = Counter(clock.escalation_label for clock in clocks)
    lane_counts = Counter(clock.assigned_lane for clock in clocks)
    bucket_counts = Counter(clock.queue_bucket for clock in clocks)
    source_generated = clocks[0].source_inbox_generated_at_utc if clocks else ""
    as_of = clocks[0].as_of_utc if clocks else ""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Operator SLA Clock Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source inbox generated UTC: `{source_generated}`",
        f"As-of UTC: `{as_of}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, inbox item IDs, shadow IDs, or window IDs.",
        "- SLA clock rows are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Inbox items reviewed | {len(clocks)} |",
        f"| SLA clocks | {len(clocks)} |",
        f"| Overdue clocks | {status_counts.get('overdue', 0)} |",
        f"| High/breached clocks | {sum(1 for clock in clocks if clock.breach_risk in {'breached', 'high'})} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("SLA Status", status_counts),
        "",
        *_counter_table("Breach Risk", breach_risk_counts),
        "",
        *_counter_table("Escalation Labels", escalation_counts),
        "",
        *_counter_table("Assigned Lanes", lane_counts),
        "",
        *_counter_table("Queue Buckets", bucket_counts),
        "",
        "## Execution Contract",
        "",
        "- The SLA clock marks urgency and breach risk for operator review.",
        "- It does not execute any action.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- A human must approve any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_operator_sla_clock(
    *,
    operator_inbox_db: Path = DEFAULT_OPERATOR_INBOX_DB,
    output_dir: Path = DEFAULT_SLA_CLOCK_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    as_of_utc: str | None = None,
    generated_at_utc: str | None = None,
) -> OperatorSlaClockBuildResult:
    """Build a local-only SLA clock from the operator action inbox."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    source_generated_at_utc, rows = read_operator_inbox(operator_inbox_db)
    now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    as_of = as_of_utc or now_utc
    generated = generated_at_utc or now_utc
    clocks = build_sla_clocks(
        rows,
        source_inbox_generated_at_utc=source_generated_at_utc,
        as_of_utc=as_of,
    )
    write_sla_sqlite(output_db, clocks, _format_utc(_parse_utc(generated)))
    write_summary(
        summary_path=summary_path,
        clocks=clocks,
        generated_at_utc=_format_utc(_parse_utc(generated)),
    )
    return OperatorSlaClockBuildResult(
        inbox_item_count=len(rows),
        clock_count=len(clocks),
        overdue_count=sum(1 for clock in clocks if clock.sla_status == "overdue"),
        send_whatsapp_count=sum(1 for clock in clocks if clock.send_whatsapp),
        crm_mutation_count=sum(1 for clock in clocks if clock.crm_mutation),
        status_counts=dict(Counter(clock.sla_status for clock in clocks)),
        breach_risk_counts=dict(Counter(clock.breach_risk for clock in clocks)),
        lane_counts=dict(Counter(clock.assigned_lane for clock in clocks)),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a local-only Zantara Operator SLA Clock from the action inbox."
    )
    parser.add_argument("--operator-inbox-db", type=Path, default=DEFAULT_OPERATOR_INBOX_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_SLA_CLOCK_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--as-of-utc", default=None)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_operator_sla_clock(
            operator_inbox_db=args.operator_inbox_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
            as_of_utc=args.as_of_utc,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Operator SLA clock input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Operator SLA clock run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Operator SLA clock run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "inbox_item_count": result.inbox_item_count,
                    "clock_count": result.clock_count,
                    "overdue_count": result.overdue_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "crm_mutation_count": result.crm_mutation_count,
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
