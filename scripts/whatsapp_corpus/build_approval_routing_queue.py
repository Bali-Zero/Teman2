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

DEFAULT_OWNER_BRIEF_DIR = Path("research/personal/wa-corpus/owner-brief-renderer")
DEFAULT_APPROVAL_ROUTING_DIR = Path(
    "research/personal/wa-corpus/approval-routing-queue"
)

DEFAULT_OWNER_BRIEFS_DB = DEFAULT_OWNER_BRIEF_DIR / "owner_brief_renderer.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_APPROVAL_ROUTING_DIR / "approval_routing_queue.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_APPROVAL_ROUTING_DIR / "approval_routing_queue_summary.md"

EXPECTED_OWNER_BRIEFS_DB_NAME = "owner_brief_renderer.local.sqlite"
ALLOWED_DECISIONS = ("approve", "reject", "defer")


@dataclass(frozen=True)
class OwnerBriefRow:
    brief_id: str
    pack_id: str
    case_card_id: str
    brief_rank: int
    assigned_lane: str
    decision_type: str
    decision_priority: str
    brief_title: str
    owner_focus: str
    recommended_decision: str
    draft_action_type: str
    safety_lock: str
    approval_status: str
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class ApprovalRouteItem:
    route_id: str
    case_card_id: str
    brief_id: str
    pack_id: str
    route_rank: int
    assigned_lane: str
    decision_type: str
    decision_priority: str
    owner_focus: str
    route_bucket: str
    next_actor: str
    queue_status: str
    allowed_decisions: tuple[str, ...]
    recommended_decision: str
    draft_action_type: str
    safety_lock: str
    approval_status: str
    route_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class ApprovalRoutingQueueBuildResult:
    source_case_count: int
    owner_item_count: int
    pack_count: int
    brief_count: int
    queue_item_count: int
    now_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    decision_type_counts: dict[str, int]
    lane_counts: dict[str, int]
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


def read_source_metadata(db_path: Path) -> tuple[str, int, int, int, int]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_OWNER_BRIEFS_DB_NAME,
        label="Owner Brief Renderer",
    ) as conn:
        row = conn.execute(
            """
            SELECT generated_at_utc, source_case_count, owner_item_count,
                   pack_count, brief_count
            FROM owner_brief_renderer_runs
            WHERE id = 1
            """
        ).fetchone()
    if row is None:
        return "unknown", 0, 0, 0, 0
    return (
        str(row["generated_at_utc"]),
        int(row["source_case_count"]),
        int(row["owner_item_count"]),
        int(row["pack_count"]),
        int(row["brief_count"]),
    )


def read_owner_brief_rows(db_path: Path) -> tuple[OwnerBriefRow, ...]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_OWNER_BRIEFS_DB_NAME,
        label="Owner Brief Renderer",
    ) as conn:
        rows = conn.execute(
            """
            SELECT brief_id, pack_id, case_card_id, brief_rank, assigned_lane,
                   decision_type, decision_priority, brief_title, owner_focus,
                   recommended_decision, draft_action_type, safety_lock,
                   approval_status, send_whatsapp, crm_mutation,
                   requires_human_approval
            FROM owner_briefs
            ORDER BY brief_rank, case_card_id
            """
        ).fetchall()
    return tuple(
        OwnerBriefRow(
            brief_id=str(row["brief_id"]),
            pack_id=str(row["pack_id"]),
            case_card_id=str(row["case_card_id"]),
            brief_rank=int(row["brief_rank"]),
            assigned_lane=str(row["assigned_lane"]),
            decision_type=str(row["decision_type"]),
            decision_priority=str(row["decision_priority"]),
            brief_title=str(row["brief_title"]),
            owner_focus=str(row["owner_focus"]),
            recommended_decision=str(row["recommended_decision"]),
            draft_action_type=str(row["draft_action_type"]),
            safety_lock=str(row["safety_lock"]),
            approval_status=str(row["approval_status"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def _route_bucket(decision_priority: str) -> str:
    if decision_priority == "now":
        return "owner_now"
    if decision_priority == "today":
        return "owner_today"
    return "owner_review"


def build_route_items(rows: Sequence[OwnerBriefRow]) -> tuple[ApprovalRouteItem, ...]:
    routes: list[ApprovalRouteItem] = []
    for rank, row in enumerate(rows, start=1):
        route_bucket = _route_bucket(row.decision_priority)
        payload = {
            "schema_version": "approval_routing_queue.v1",
            "privacy_mode": "local_only_approval_routing_no_raw_text",
            "source_brief_rank": row.brief_rank,
            "source_decision_type": row.decision_type,
            "owner_focus": row.owner_focus,
            "route_bucket": route_bucket,
            "next_actor": "owner",
            "queue_status": "waiting_owner_decision",
            "allowed_decisions": list(ALLOWED_DECISIONS),
            "owner_action_required": True,
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        routes.append(
            ApprovalRouteItem(
                route_id=f"approval-route-{rank:06d}",
                case_card_id=row.case_card_id,
                brief_id=row.brief_id,
                pack_id=row.pack_id,
                route_rank=rank,
                assigned_lane=row.assigned_lane,
                decision_type=row.decision_type,
                decision_priority=row.decision_priority,
                owner_focus=row.owner_focus,
                route_bucket=route_bucket,
                next_actor="owner",
                queue_status="waiting_owner_decision",
                allowed_decisions=ALLOWED_DECISIONS,
                recommended_decision=row.recommended_decision,
                draft_action_type=row.draft_action_type,
                safety_lock=row.safety_lock,
                approval_status=row.approval_status,
                route_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(routes)


def write_approval_routing_sqlite(
    output_db: Path,
    *,
    routes: Sequence[ApprovalRouteItem],
    source_case_count: int,
    owner_item_count: int,
    pack_count: int,
    brief_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS approval_routing_queue_runs;
            DROP TABLE IF EXISTS approval_routing_items;

            CREATE TABLE approval_routing_queue_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_case_count INTEGER NOT NULL,
                owner_item_count INTEGER NOT NULL,
                pack_count INTEGER NOT NULL,
                brief_count INTEGER NOT NULL,
                queue_item_count INTEGER NOT NULL,
                now_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE approval_routing_items (
                route_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                brief_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                route_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                owner_focus TEXT NOT NULL,
                route_bucket TEXT NOT NULL,
                next_actor TEXT NOT NULL,
                queue_status TEXT NOT NULL,
                allowed_decisions_json TEXT NOT NULL,
                recommended_decision TEXT NOT NULL,
                draft_action_type TEXT NOT NULL,
                safety_lock TEXT NOT NULL,
                approval_status TEXT NOT NULL,
                route_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_approval_route_rank ON approval_routing_items(route_rank);
            CREATE INDEX idx_approval_route_lane ON approval_routing_items(assigned_lane);
            CREATE INDEX idx_approval_route_type ON approval_routing_items(decision_type);
            CREATE INDEX idx_approval_route_bucket ON approval_routing_items(route_bucket);
            CREATE INDEX idx_approval_route_status ON approval_routing_items(queue_status);
            """
        )
        conn.execute(
            """
            INSERT INTO approval_routing_queue_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count, brief_count,
                queue_item_count, now_count, send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                source_generated_at_utc,
                "local_only_approval_routing_no_raw_text_no_send_no_crm_mutation",
                source_case_count,
                owner_item_count,
                pack_count,
                brief_count,
                len(routes),
                sum(1 for route in routes if route.route_bucket == "owner_now"),
            ),
        )
        conn.executemany(
            """
            INSERT INTO approval_routing_items (
                route_id, case_card_id, brief_id, pack_id, route_rank,
                assigned_lane, decision_type, decision_priority, owner_focus,
                route_bucket, next_actor, queue_status, allowed_decisions_json,
                recommended_decision, draft_action_type, safety_lock,
                approval_status, route_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    route.route_id,
                    route.case_card_id,
                    route.brief_id,
                    route.pack_id,
                    route.route_rank,
                    route.assigned_lane,
                    route.decision_type,
                    route.decision_priority,
                    route.owner_focus,
                    route.route_bucket,
                    route.next_actor,
                    route.queue_status,
                    json.dumps(list(route.allowed_decisions), ensure_ascii=False),
                    route.recommended_decision,
                    route.draft_action_type,
                    route.safety_lock,
                    route.approval_status,
                    json.dumps(route.route_payload, ensure_ascii=False, sort_keys=True),
                    int(route.send_whatsapp),
                    int(route.crm_mutation),
                    int(route.requires_human_approval),
                )
                for route in routes
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
    routes: Sequence[ApprovalRouteItem],
    source_case_count: int,
    owner_item_count: int,
    pack_count: int,
    brief_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    decision_counts = Counter(route.decision_type for route in routes)
    priority_counts = Counter(route.decision_priority for route in routes)
    lane_counts = Counter(route.assigned_lane for route in routes)
    bucket_counts = Counter(route.route_bucket for route in routes)
    queue_counts = Counter(route.queue_status for route in routes)
    actor_counts = Counter(route.next_actor for route in routes)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Approval Routing Queue Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source Owner Brief Renderer UTC: `{source_generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, judgment IDs, approval IDs, pack IDs, brief IDs, route IDs, gap IDs, event IDs, inbox item IDs, or room item IDs.",
        "- Approval routes are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Source cases | {source_case_count} |",
        f"| Owner approval items | {owner_item_count} |",
        f"| Owner decision packs | {pack_count} |",
        f"| Owner briefs | {brief_count} |",
        f"| Queue items | {len(routes)} |",
        f"| Owner now items | {sum(1 for route in routes if route.route_bucket == 'owner_now')} |",
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
        *_counter_table("Next Actors", actor_counts),
        "",
        "## Execution Contract",
        "",
        "- The Approval Routing Queue turns owner briefs into reviewable owner route items.",
        "- Allowed owner decisions are approve, reject, and defer.",
        "- It does not parse raw WhatsApp messages.",
        "- It does not call a cloud LLM.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- Owner approval remains mandatory before any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_approval_routing_queue(
    *,
    owner_briefs_db: Path = DEFAULT_OWNER_BRIEFS_DB,
    output_dir: Path = DEFAULT_APPROVAL_ROUTING_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    generated_at_utc: str | None = None,
) -> ApprovalRoutingQueueBuildResult:
    """Build local-only owner approval routes from rendered owner briefs."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    generated = _format_utc(generated_at_utc)
    (
        source_generated,
        source_case_count,
        owner_item_count,
        pack_count,
        brief_count,
    ) = read_source_metadata(owner_briefs_db)
    rows = read_owner_brief_rows(owner_briefs_db)
    routes = build_route_items(rows)
    now_count = sum(1 for route in routes if route.route_bucket == "owner_now")
    source_case_total = source_case_count or len(rows)
    owner_item_total = owner_item_count or len(rows)
    pack_total = pack_count or len(rows)
    brief_total = brief_count or len(rows)
    write_approval_routing_sqlite(
        output_db,
        routes=routes,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    write_summary(
        summary_path=summary_path,
        routes=routes,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    return ApprovalRoutingQueueBuildResult(
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=brief_total,
        queue_item_count=len(routes),
        now_count=now_count,
        send_whatsapp_count=sum(1 for route in routes if route.send_whatsapp),
        crm_mutation_count=sum(1 for route in routes if route.crm_mutation),
        decision_type_counts=dict(Counter(route.decision_type for route in routes)),
        lane_counts=dict(Counter(route.assigned_lane for route in routes)),
        route_bucket_counts=dict(Counter(route.route_bucket for route in routes)),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara approval routing queue from owner briefs."
    )
    parser.add_argument("--owner-briefs-db", type=Path, default=DEFAULT_OWNER_BRIEFS_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_APPROVAL_ROUTING_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_approval_routing_queue(
            owner_briefs_db=args.owner_briefs_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Approval routing queue input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Approval routing queue run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Approval routing queue run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "brief_count": result.brief_count,
                    "crm_mutation_count": result.crm_mutation_count,
                    "now_count": result.now_count,
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
            "Approval routing queue complete: "
            f"{result.queue_item_count} routes -> {result.output_db.name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
