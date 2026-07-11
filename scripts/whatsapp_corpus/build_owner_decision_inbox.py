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

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.whatsapp_corpus.build_owner_decision_intake import (
    ReviewConsoleRow,
    read_review_console_items,
    read_source_metadata,
)

DEFAULT_OPERATOR_PACKET_REVIEW_CONSOLE_DIR = Path(
    "research/personal/wa-corpus/operator-packet-review-console"
)
DEFAULT_OWNER_DECISION_INBOX_DIR = Path(
    "research/personal/wa-corpus/owner-decision-inbox"
)

DEFAULT_REVIEW_CONSOLE_DB = (
    DEFAULT_OPERATOR_PACKET_REVIEW_CONSOLE_DIR
    / "operator_packet_review_console.local.sqlite"
)
DEFAULT_OUTPUT_DB = DEFAULT_OWNER_DECISION_INBOX_DIR / "owner_decision_inbox.local.sqlite"
DEFAULT_OUTPUT_TEMPLATE = (
    DEFAULT_OWNER_DECISION_INBOX_DIR / "owner_decisions_template.local.jsonl"
)
DEFAULT_SUMMARY = DEFAULT_OWNER_DECISION_INBOX_DIR / "owner_decision_inbox_summary.md"

ALLOWED_OWNER_DECISIONS = ("approve", "reject", "defer")
ACTIONABLE_REVIEW_STATES = frozenset(
    {"waiting_owner_decision", "deferred_owner_revisit"}
)
DEFAULT_EVENT_ACTOR = "owner"


@dataclass(frozen=True)
class OwnerDecisionInboxItem:
    owner_inbox_item_id: str
    review_item_id: str
    packet_id: str
    work_order_id: str
    event_id: str
    entry_id: str
    route_id: str
    case_card_id: str
    brief_id: str
    pack_id: str
    inbox_rank: int
    source_review_rank: int
    assigned_lane: str
    operator_lane: str
    decision_type: str
    decision_priority: str
    route_bucket: str
    current_owner_decision: str
    review_state: str
    console_bucket: str
    review_priority: str
    visible_owner_action: str
    console_instruction: str
    review_gate: str
    action_lock: str
    owner_decision_status: str
    template_status: str
    allowed_decisions: tuple[str, ...]
    owner_decision_input: str
    decision_note_input: str
    inbox_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool

    def template_record(self) -> dict[str, object]:
        return {
            "allowed_decisions": list(self.allowed_decisions),
            "assigned_lane": self.assigned_lane,
            "console_bucket": self.console_bucket,
            "decision_note": self.decision_note_input,
            "decision_type": self.decision_type,
            "entry_id": self.entry_id,
            "event_actor": DEFAULT_EVENT_ACTOR,
            "event_recorded_at_utc": "",
            "owner_decision": self.owner_decision_input,
            "packet_id": self.packet_id,
            "review_item_id": self.review_item_id,
            "review_state": self.review_state,
        }


@dataclass(frozen=True)
class OwnerDecisionInboxBuildResult:
    source_case_count: int
    source_review_item_count: int
    inbox_item_count: int
    waiting_decision_count: int
    revisit_decision_count: int
    excluded_review_item_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    status_counts: dict[str, int]
    lane_counts: dict[str, int]
    output_db: Path
    output_template: Path
    summary_path: Path


def _format_utc(value: str | None = None) -> str:
    if value is not None:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _priority_sort_value(item: ReviewConsoleRow) -> int:
    if item.review_state == "waiting_owner_decision":
        return 0
    if item.review_state == "deferred_owner_revisit":
        return 1
    return 9


def _owner_decision_status(item: ReviewConsoleRow) -> str:
    if item.review_state == "waiting_owner_decision":
        return "needs_owner_decision"
    if item.review_state == "deferred_owner_revisit":
        return "needs_owner_revisit"
    raise ValueError(f"Unsupported owner inbox review state: {item.review_state}")


def _build_payload(item: ReviewConsoleRow, *, status: str) -> dict[str, object]:
    return {
        "schema_version": "owner_decision_inbox.v1",
        "privacy_mode": "local_only_owner_decision_inbox_no_raw_text",
        "source_review_rank": item.review_rank,
        "source_packet_rank": item.source_packet_rank,
        "decision_type": item.decision_type,
        "decision_priority": item.decision_priority,
        "route_bucket": item.route_bucket,
        "review_state": item.review_state,
        "console_bucket": item.console_bucket,
        "visible_owner_action": item.visible_owner_action,
        "owner_decision_status": status,
        "allowed_decisions": list(ALLOWED_OWNER_DECISIONS),
        "raw_text_included": False,
        "send_whatsapp": False,
        "crm_mutation": False,
        "requires_human_approval": True,
    }


def build_inbox_items(
    review_items: Sequence[ReviewConsoleRow],
) -> tuple[OwnerDecisionInboxItem, ...]:
    actionable = [
        item for item in review_items if item.review_state in ACTIONABLE_REVIEW_STATES
    ]
    actionable.sort(
        key=lambda item: (
            _priority_sort_value(item),
            item.review_rank,
            item.assigned_lane,
            item.review_item_id,
        )
    )

    items: list[OwnerDecisionInboxItem] = []
    for inbox_rank, item in enumerate(actionable, start=1):
        if item.send_whatsapp or item.crm_mutation:
            raise ValueError(f"Unsafe review item flags on {item.review_item_id}")
        if not item.requires_human_approval:
            raise ValueError(f"Review item missing human approval gate: {item.review_item_id}")
        status = _owner_decision_status(item)
        items.append(
            OwnerDecisionInboxItem(
                owner_inbox_item_id=f"owner-inbox-{item.review_item_id}",
                review_item_id=item.review_item_id,
                packet_id=item.packet_id,
                work_order_id=item.work_order_id,
                event_id=item.event_id,
                entry_id=item.entry_id,
                route_id=item.route_id,
                case_card_id=item.case_card_id,
                brief_id=item.brief_id,
                pack_id=item.pack_id,
                inbox_rank=inbox_rank,
                source_review_rank=item.review_rank,
                assigned_lane=item.assigned_lane,
                operator_lane=item.operator_lane,
                decision_type=item.decision_type,
                decision_priority=item.decision_priority,
                route_bucket=item.route_bucket,
                current_owner_decision=item.owner_decision,
                review_state=item.review_state,
                console_bucket=item.console_bucket,
                review_priority=item.review_priority,
                visible_owner_action=item.visible_owner_action,
                console_instruction=item.console_instruction,
                review_gate=item.review_gate,
                action_lock=item.action_lock,
                owner_decision_status=status,
                template_status="blank_owner_decision_required",
                allowed_decisions=ALLOWED_OWNER_DECISIONS,
                owner_decision_input="",
                decision_note_input="",
                inbox_payload=_build_payload(item, status=status),
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(items)


def write_owner_decision_inbox_sqlite(
    path: Path,
    *,
    items: Sequence[OwnerDecisionInboxItem],
    source_case_count: int,
    source_review_item_count: int,
    excluded_review_item_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    status_counts = Counter(item.owner_decision_status for item in items)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE owner_decision_inbox_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_case_count INTEGER NOT NULL,
                source_review_item_count INTEGER NOT NULL,
                inbox_item_count INTEGER NOT NULL,
                waiting_decision_count INTEGER NOT NULL,
                revisit_decision_count INTEGER NOT NULL,
                excluded_review_item_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL CHECK (send_whatsapp_count = 0),
                crm_mutation_count INTEGER NOT NULL CHECK (crm_mutation_count = 0)
            );

            CREATE TABLE owner_decision_inbox_items (
                owner_inbox_item_id TEXT PRIMARY KEY,
                review_item_id TEXT NOT NULL UNIQUE,
                packet_id TEXT NOT NULL,
                work_order_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                entry_id TEXT NOT NULL,
                route_id TEXT NOT NULL,
                case_card_id TEXT NOT NULL,
                brief_id TEXT NOT NULL,
                pack_id TEXT NOT NULL,
                inbox_rank INTEGER NOT NULL,
                source_review_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                operator_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                route_bucket TEXT NOT NULL,
                current_owner_decision TEXT NOT NULL,
                review_state TEXT NOT NULL,
                console_bucket TEXT NOT NULL,
                review_priority TEXT NOT NULL,
                visible_owner_action TEXT NOT NULL,
                console_instruction TEXT NOT NULL,
                review_gate TEXT NOT NULL,
                action_lock TEXT NOT NULL,
                owner_decision_status TEXT NOT NULL,
                template_status TEXT NOT NULL,
                allowed_decisions_json TEXT NOT NULL,
                owner_decision_input TEXT NOT NULL,
                decision_note_input TEXT NOT NULL,
                inbox_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_owner_decision_inbox_rank
                ON owner_decision_inbox_items(inbox_rank);
            CREATE INDEX idx_owner_decision_inbox_lane
                ON owner_decision_inbox_items(assigned_lane);
            CREATE INDEX idx_owner_decision_inbox_status
                ON owner_decision_inbox_items(owner_decision_status);
            CREATE INDEX idx_owner_decision_inbox_review_state
                ON owner_decision_inbox_items(review_state);
            """
        )
        conn.execute(
            """
            INSERT INTO owner_decision_inbox_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, source_review_item_count, inbox_item_count,
                waiting_decision_count, revisit_decision_count,
                excluded_review_item_count, send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                source_generated_at_utc,
                "local_only_owner_decision_inbox_no_raw_text_no_send_no_crm_mutation",
                source_case_count,
                source_review_item_count,
                len(items),
                status_counts.get("needs_owner_decision", 0),
                status_counts.get("needs_owner_revisit", 0),
                excluded_review_item_count,
            ),
        )
        conn.executemany(
            """
            INSERT INTO owner_decision_inbox_items (
                owner_inbox_item_id, review_item_id, packet_id, work_order_id,
                event_id, entry_id, route_id, case_card_id, brief_id, pack_id,
                inbox_rank, source_review_rank, assigned_lane, operator_lane,
                decision_type, decision_priority, route_bucket,
                current_owner_decision, review_state, console_bucket,
                review_priority, visible_owner_action, console_instruction,
                review_gate, action_lock, owner_decision_status,
                template_status, allowed_decisions_json, owner_decision_input,
                decision_note_input, inbox_payload_json, send_whatsapp,
                crm_mutation, requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.owner_inbox_item_id,
                    item.review_item_id,
                    item.packet_id,
                    item.work_order_id,
                    item.event_id,
                    item.entry_id,
                    item.route_id,
                    item.case_card_id,
                    item.brief_id,
                    item.pack_id,
                    item.inbox_rank,
                    item.source_review_rank,
                    item.assigned_lane,
                    item.operator_lane,
                    item.decision_type,
                    item.decision_priority,
                    item.route_bucket,
                    item.current_owner_decision,
                    item.review_state,
                    item.console_bucket,
                    item.review_priority,
                    item.visible_owner_action,
                    item.console_instruction,
                    item.review_gate,
                    item.action_lock,
                    item.owner_decision_status,
                    item.template_status,
                    json.dumps(list(item.allowed_decisions), sort_keys=True),
                    item.owner_decision_input,
                    item.decision_note_input,
                    json.dumps(item.inbox_payload, ensure_ascii=False, sort_keys=True),
                    int(item.send_whatsapp),
                    int(item.crm_mutation),
                    int(item.requires_human_approval),
                )
                for item in items
            ],
        )
        conn.commit()


def write_owner_decision_template_jsonl(
    path: Path,
    items: Sequence[OwnerDecisionInboxItem],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(item.template_record(), ensure_ascii=False, sort_keys=True) + "\n"
            for item in items
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
    items: Sequence[OwnerDecisionInboxItem],
    source_case_count: int,
    source_review_item_count: int,
    excluded_review_item_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    status_counts = Counter(item.owner_decision_status for item in items)
    state_counts = Counter(item.review_state for item in items)
    lane_counts = Counter(item.assigned_lane for item in items)
    bucket_counts = Counter(item.console_bucket for item in items)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Owner Decision Inbox Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source Review Console UTC: `{source_generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, judgment IDs, approval IDs, pack IDs, brief IDs, route IDs, ledger entry IDs, event IDs, work order IDs, packet IDs, review item IDs, or inbox item IDs.",
        "- Owner decision inbox artifacts are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Source cases | {source_case_count} |",
        f"| Source review items | {source_review_item_count} |",
        f"| Owner inbox items | {len(items)} |",
        f"| Waiting owner decision | {status_counts.get('needs_owner_decision', 0)} |",
        f"| Owner revisit needed | {status_counts.get('needs_owner_revisit', 0)} |",
        f"| Excluded review items | {excluded_review_item_count} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Owner Decision Status", status_counts),
        "",
        *_counter_table("Review States", state_counts),
        "",
        *_counter_table("Console Buckets", bucket_counts),
        "",
        *_counter_table("Assigned Lanes", lane_counts),
        "",
        "## Execution Contract",
        "",
        "- The Owner Decision Inbox selects only owner-actionable review items.",
        "- The JSONL template starts with blank owner decisions and requires explicit approve, reject, or defer input.",
        "- It does not invent owner decisions.",
        "- It does not parse raw WhatsApp messages.",
        "- It does not call a cloud LLM.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- Human approval remains mandatory before any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_owner_decision_inbox(
    *,
    review_console_db: Path = DEFAULT_REVIEW_CONSOLE_DB,
    output_dir: Path = DEFAULT_OWNER_DECISION_INBOX_DIR,
    output_db: Path | None = None,
    output_template: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    generated_at_utc: str | None = None,
) -> OwnerDecisionInboxBuildResult:
    """Build local-only owner decision inbox rows from the review console."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    output_template = output_template or output_dir / DEFAULT_OUTPUT_TEMPLATE.name
    generated = _format_utc(generated_at_utc)
    (
        source_generated,
        source_case_count,
        _owner_item_count,
        _pack_count,
        _brief_count,
        _queue_item_count,
        _ledger_entry_count,
        _event_row_count,
        _work_order_count,
        _packet_count,
    ) = read_source_metadata(review_console_db)
    review_items = read_review_console_items(review_console_db)
    inbox_items = build_inbox_items(review_items)
    source_case_total = source_case_count or len(review_items)
    review_total = len(review_items)
    excluded_count = review_total - len(inbox_items)

    write_owner_decision_inbox_sqlite(
        output_db,
        items=inbox_items,
        source_case_count=source_case_total,
        source_review_item_count=review_total,
        excluded_review_item_count=excluded_count,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    write_owner_decision_template_jsonl(output_template, inbox_items)
    write_summary(
        summary_path=summary_path,
        items=inbox_items,
        source_case_count=source_case_total,
        source_review_item_count=review_total,
        excluded_review_item_count=excluded_count,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    status_counts = Counter(item.owner_decision_status for item in inbox_items)
    lane_counts = Counter(item.assigned_lane for item in inbox_items)
    return OwnerDecisionInboxBuildResult(
        source_case_count=source_case_total,
        source_review_item_count=review_total,
        inbox_item_count=len(inbox_items),
        waiting_decision_count=status_counts.get("needs_owner_decision", 0),
        revisit_decision_count=status_counts.get("needs_owner_revisit", 0),
        excluded_review_item_count=excluded_count,
        send_whatsapp_count=sum(1 for item in inbox_items if item.send_whatsapp),
        crm_mutation_count=sum(1 for item in inbox_items if item.crm_mutation),
        status_counts=dict(status_counts),
        lane_counts=dict(lane_counts),
        output_db=output_db,
        output_template=output_template,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a local-only Zantara Owner Decision Inbox from review-console rows."
    )
    parser.add_argument("--review-console-db", type=Path, default=DEFAULT_REVIEW_CONSOLE_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OWNER_DECISION_INBOX_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--output-template", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_owner_decision_inbox(
            review_console_db=args.review_console_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            output_template=args.output_template,
            summary_path=args.summary,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Owner decision inbox input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Owner decision inbox run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Owner decision inbox run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "crm_mutation_count": result.crm_mutation_count,
                    "excluded_review_item_count": result.excluded_review_item_count,
                    "inbox_item_count": result.inbox_item_count,
                    "revisit_decision_count": result.revisit_decision_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "source_case_count": result.source_case_count,
                    "source_review_item_count": result.source_review_item_count,
                    "waiting_decision_count": result.waiting_decision_count,
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Owner decision inbox complete: "
            f"{result.inbox_item_count} owner items -> {result.output_db.name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
