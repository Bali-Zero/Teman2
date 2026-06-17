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

DEFAULT_APPROVAL_ROUTING_DIR = Path(
    "research/personal/wa-corpus/approval-routing-queue"
)
DEFAULT_APPROVE_REJECT_LEDGER_DIR = Path(
    "research/personal/wa-corpus/approve-reject-ledger"
)

DEFAULT_APPROVAL_ROUTING_DB = (
    DEFAULT_APPROVAL_ROUTING_DIR / "approval_routing_queue.local.sqlite"
)
DEFAULT_OUTPUT_DB = (
    DEFAULT_APPROVE_REJECT_LEDGER_DIR / "approve_reject_ledger.local.sqlite"
)
DEFAULT_SUMMARY = (
    DEFAULT_APPROVE_REJECT_LEDGER_DIR / "approve_reject_ledger_summary.md"
)

EXPECTED_APPROVAL_ROUTING_DB_NAME = "approval_routing_queue.local.sqlite"
PENDING_DECISION_STATUS = "awaiting_owner_decision"
PENDING_OWNER_DECISION = "pending"
IMMUTABLE_EVENT_TYPE = "decision_slot_opened"


@dataclass(frozen=True)
class ApprovalRoutingRow:
    route_id: str
    case_card_id: str
    brief_id: str
    pack_id: str
    route_rank: int
    assigned_lane: str
    decision_type: str
    decision_priority: str
    route_bucket: str
    next_actor: str
    queue_status: str
    allowed_decisions: tuple[str, ...]
    recommended_decision: str
    draft_action_type: str
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class ApproveRejectLedgerEntry:
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
    ledger_payload: dict[str, object]
    ledger_entry_hash: str
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class ApproveRejectLedgerBuildResult:
    source_case_count: int
    owner_item_count: int
    pack_count: int
    brief_count: int
    queue_item_count: int
    ledger_entry_count: int
    pending_decision_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    decision_status_counts: dict[str, int]
    owner_decision_counts: dict[str, int]
    event_type_counts: dict[str, int]
    route_bucket_counts: dict[str, int]
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


def _hash_ledger_entry(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_source_metadata(db_path: Path) -> tuple[str, int, int, int, int, int]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_APPROVAL_ROUTING_DB_NAME,
        label="Approval Routing Queue",
    ) as conn:
        row = conn.execute(
            """
            SELECT generated_at_utc, source_case_count, owner_item_count,
                   pack_count, brief_count, queue_item_count
            FROM approval_routing_queue_runs
            WHERE id = 1
            """
        ).fetchone()
    if row is None:
        return "unknown", 0, 0, 0, 0, 0
    return (
        str(row["generated_at_utc"]),
        int(row["source_case_count"]),
        int(row["owner_item_count"]),
        int(row["pack_count"]),
        int(row["brief_count"]),
        int(row["queue_item_count"]),
    )


def read_approval_routes(db_path: Path) -> tuple[ApprovalRoutingRow, ...]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_APPROVAL_ROUTING_DB_NAME,
        label="Approval Routing Queue",
    ) as conn:
        rows = conn.execute(
            """
            SELECT route_id, case_card_id, brief_id, pack_id, route_rank,
                   assigned_lane, decision_type, decision_priority, route_bucket,
                   next_actor, queue_status, allowed_decisions_json,
                   recommended_decision, draft_action_type, send_whatsapp,
                   crm_mutation, requires_human_approval
            FROM approval_routing_items
            ORDER BY route_rank, case_card_id
            """
        ).fetchall()
    return tuple(
        ApprovalRoutingRow(
            route_id=str(row["route_id"]),
            case_card_id=str(row["case_card_id"]),
            brief_id=str(row["brief_id"]),
            pack_id=str(row["pack_id"]),
            route_rank=int(row["route_rank"]),
            assigned_lane=str(row["assigned_lane"]),
            decision_type=str(row["decision_type"]),
            decision_priority=str(row["decision_priority"]),
            route_bucket=str(row["route_bucket"]),
            next_actor=str(row["next_actor"]),
            queue_status=str(row["queue_status"]),
            allowed_decisions=_parse_allowed_decisions(str(row["allowed_decisions_json"])),
            recommended_decision=str(row["recommended_decision"]),
            draft_action_type=str(row["draft_action_type"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def build_ledger_entries(
    rows: Sequence[ApprovalRoutingRow],
) -> tuple[ApproveRejectLedgerEntry, ...]:
    entries: list[ApproveRejectLedgerEntry] = []
    for rank, row in enumerate(rows, start=1):
        payload = {
            "schema_version": "approve_reject_ledger.v1",
            "privacy_mode": "local_only_approve_reject_ledger_no_raw_text",
            "source_route_rank": row.route_rank,
            "source_queue_status": row.queue_status,
            "decision_status": PENDING_DECISION_STATUS,
            "owner_decision": PENDING_OWNER_DECISION,
            "allowed_decisions": list(row.allowed_decisions),
            "immutable_event_type": IMMUTABLE_EVENT_TYPE,
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        hash_payload = {
            **payload,
            "entry_id": f"ledger-entry-{rank:06d}",
            "route_id": row.route_id,
            "case_card_id": row.case_card_id,
            "brief_id": row.brief_id,
            "pack_id": row.pack_id,
            "ledger_rank": rank,
            "assigned_lane": row.assigned_lane,
            "decision_type": row.decision_type,
            "decision_priority": row.decision_priority,
            "route_bucket": row.route_bucket,
            "recommended_decision": row.recommended_decision,
            "draft_action_type": row.draft_action_type,
        }
        entries.append(
            ApproveRejectLedgerEntry(
                entry_id=f"ledger-entry-{rank:06d}",
                route_id=row.route_id,
                case_card_id=row.case_card_id,
                brief_id=row.brief_id,
                pack_id=row.pack_id,
                ledger_rank=rank,
                assigned_lane=row.assigned_lane,
                decision_type=row.decision_type,
                decision_priority=row.decision_priority,
                route_bucket=row.route_bucket,
                next_actor=row.next_actor,
                queue_status=row.queue_status,
                decision_status=PENDING_DECISION_STATUS,
                owner_decision=PENDING_OWNER_DECISION,
                allowed_decisions=row.allowed_decisions,
                recommended_decision=row.recommended_decision,
                draft_action_type=row.draft_action_type,
                immutable_event_type=IMMUTABLE_EVENT_TYPE,
                ledger_payload=payload,
                ledger_entry_hash=_hash_ledger_entry(hash_payload),
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(entries)


def write_approve_reject_ledger_sqlite(
    output_db: Path,
    *,
    entries: Sequence[ApproveRejectLedgerEntry],
    source_case_count: int,
    owner_item_count: int,
    pack_count: int,
    brief_count: int,
    queue_item_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS approve_reject_ledger_runs;
            DROP TABLE IF EXISTS approve_reject_ledger_entries;

            CREATE TABLE approve_reject_ledger_runs (
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
                pending_decision_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE approve_reject_ledger_entries (
                entry_id TEXT PRIMARY KEY,
                route_id TEXT NOT NULL,
                case_card_id TEXT NOT NULL,
                brief_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                ledger_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                route_bucket TEXT NOT NULL,
                next_actor TEXT NOT NULL,
                queue_status TEXT NOT NULL,
                decision_status TEXT NOT NULL,
                owner_decision TEXT NOT NULL,
                allowed_decisions_json TEXT NOT NULL,
                recommended_decision TEXT NOT NULL,
                draft_action_type TEXT NOT NULL,
                immutable_event_type TEXT NOT NULL,
                ledger_entry_hash TEXT NOT NULL UNIQUE,
                ledger_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_approve_reject_ledger_rank
                ON approve_reject_ledger_entries(ledger_rank);
            CREATE INDEX idx_approve_reject_ledger_route
                ON approve_reject_ledger_entries(route_id);
            CREATE INDEX idx_approve_reject_ledger_status
                ON approve_reject_ledger_entries(decision_status);
            CREATE INDEX idx_approve_reject_ledger_decision
                ON approve_reject_ledger_entries(owner_decision);
            CREATE INDEX idx_approve_reject_ledger_event
                ON approve_reject_ledger_entries(immutable_event_type);
            """
        )
        conn.execute(
            """
            INSERT INTO approve_reject_ledger_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count, brief_count,
                queue_item_count, ledger_entry_count, pending_decision_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                source_generated_at_utc,
                "local_only_approve_reject_ledger_no_raw_text_no_send_no_crm_mutation",
                source_case_count,
                owner_item_count,
                pack_count,
                brief_count,
                queue_item_count,
                len(entries),
                sum(
                    1
                    for entry in entries
                    if entry.decision_status == PENDING_DECISION_STATUS
                ),
            ),
        )
        conn.executemany(
            """
            INSERT INTO approve_reject_ledger_entries (
                entry_id, route_id, case_card_id, brief_id, pack_id, ledger_rank,
                assigned_lane, decision_type, decision_priority, route_bucket,
                next_actor, queue_status, decision_status, owner_decision,
                allowed_decisions_json, recommended_decision, draft_action_type,
                immutable_event_type, ledger_entry_hash, ledger_payload_json,
                send_whatsapp, crm_mutation, requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    entry.entry_id,
                    entry.route_id,
                    entry.case_card_id,
                    entry.brief_id,
                    entry.pack_id,
                    entry.ledger_rank,
                    entry.assigned_lane,
                    entry.decision_type,
                    entry.decision_priority,
                    entry.route_bucket,
                    entry.next_actor,
                    entry.queue_status,
                    entry.decision_status,
                    entry.owner_decision,
                    json.dumps(list(entry.allowed_decisions), ensure_ascii=False),
                    entry.recommended_decision,
                    entry.draft_action_type,
                    entry.immutable_event_type,
                    entry.ledger_entry_hash,
                    json.dumps(entry.ledger_payload, ensure_ascii=False, sort_keys=True),
                    int(entry.send_whatsapp),
                    int(entry.crm_mutation),
                    int(entry.requires_human_approval),
                )
                for entry in entries
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
    entries: Sequence[ApproveRejectLedgerEntry],
    source_case_count: int,
    owner_item_count: int,
    pack_count: int,
    brief_count: int,
    queue_item_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    decision_counts = Counter(entry.decision_type for entry in entries)
    priority_counts = Counter(entry.decision_priority for entry in entries)
    lane_counts = Counter(entry.assigned_lane for entry in entries)
    bucket_counts = Counter(entry.route_bucket for entry in entries)
    queue_counts = Counter(entry.queue_status for entry in entries)
    status_counts = Counter(entry.decision_status for entry in entries)
    owner_decision_counts = Counter(entry.owner_decision for entry in entries)
    event_counts = Counter(entry.immutable_event_type for entry in entries)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Approve/Reject Ledger Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source Approval Routing Queue UTC: `{source_generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, judgment IDs, approval IDs, pack IDs, brief IDs, route IDs, ledger entry IDs, gap IDs, event IDs, inbox item IDs, or room item IDs.",
        "- Approve/reject ledger entries are local-only and ignored under `research/personal/wa-corpus/`.",
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
        f"| Ledger entries | {len(entries)} |",
        f"| Pending owner decisions | {sum(1 for entry in entries if entry.decision_status == PENDING_DECISION_STATUS)} |",
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
        *_counter_table("Route Buckets", bucket_counts),
        "",
        *_counter_table("Queue Status", queue_counts),
        "",
        *_counter_table("Decision Status", status_counts),
        "",
        *_counter_table("Owner Decisions", owner_decision_counts),
        "",
        *_counter_table("Immutable Event Types", event_counts),
        "",
        "## Execution Contract",
        "",
        "- The Approve/Reject Ledger opens one immutable decision slot per approval route.",
        "- Pending means no owner decision has been made yet.",
        "- Allowed owner decisions remain approve, reject, and defer.",
        "- It does not parse raw WhatsApp messages.",
        "- It does not call a cloud LLM.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- Owner approval remains mandatory before any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_approve_reject_ledger(
    *,
    approval_routing_db: Path = DEFAULT_APPROVAL_ROUTING_DB,
    output_dir: Path = DEFAULT_APPROVE_REJECT_LEDGER_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    generated_at_utc: str | None = None,
) -> ApproveRejectLedgerBuildResult:
    """Build local-only immutable owner decision slots from approval routes."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    generated = _format_utc(generated_at_utc)
    (
        source_generated,
        source_case_count,
        owner_item_count,
        pack_count,
        brief_count,
        queue_item_count,
    ) = read_source_metadata(approval_routing_db)
    rows = read_approval_routes(approval_routing_db)
    entries = build_ledger_entries(rows)
    source_case_total = source_case_count or len(rows)
    owner_item_total = owner_item_count or len(rows)
    pack_total = pack_count or len(rows)
    brief_total = brief_count or len(rows)
    queue_total = queue_item_count or len(rows)
    write_approve_reject_ledger_sqlite(
        output_db,
        entries=entries,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    write_summary(
        summary_path=summary_path,
        entries=entries,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    return ApproveRejectLedgerBuildResult(
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=queue_total,
        ledger_entry_count=len(entries),
        pending_decision_count=sum(
            1 for entry in entries if entry.decision_status == PENDING_DECISION_STATUS
        ),
        send_whatsapp_count=sum(1 for entry in entries if entry.send_whatsapp),
        crm_mutation_count=sum(1 for entry in entries if entry.crm_mutation),
        decision_status_counts=dict(
            Counter(entry.decision_status for entry in entries)
        ),
        owner_decision_counts=dict(Counter(entry.owner_decision for entry in entries)),
        event_type_counts=dict(Counter(entry.immutable_event_type for entry in entries)),
        route_bucket_counts=dict(Counter(entry.route_bucket for entry in entries)),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara approve/reject ledger from approval routes."
    )
    parser.add_argument(
        "--approval-routing-db",
        type=Path,
        default=DEFAULT_APPROVAL_ROUTING_DB,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_APPROVE_REJECT_LEDGER_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_approve_reject_ledger(
            approval_routing_db=args.approval_routing_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Approve/reject ledger input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Approve/reject ledger run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Approve/reject ledger run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "brief_count": result.brief_count,
                    "crm_mutation_count": result.crm_mutation_count,
                    "ledger_entry_count": result.ledger_entry_count,
                    "owner_item_count": result.owner_item_count,
                    "pack_count": result.pack_count,
                    "pending_decision_count": result.pending_decision_count,
                    "queue_item_count": result.queue_item_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "source_case_count": result.source_case_count,
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Approve/reject ledger complete: "
            f"{result.ledger_entry_count} entries -> {result.output_db.name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
