from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.whatsapp_corpus.build_operator_execution_packets import (
    build_operator_execution_packets,
)
from scripts.whatsapp_corpus.build_operator_packet_review_console import (
    build_operator_packet_review_console,
)
from scripts.whatsapp_corpus.build_owner_decision_event_capture import (
    build_owner_decision_event_capture,
)
from scripts.whatsapp_corpus.build_owner_decision_intake import (
    build_owner_decision_intake,
)
from scripts.whatsapp_corpus.build_post_decision_work_order_queue import (
    build_post_decision_work_order_queue,
)

DEFAULT_APPROVE_REJECT_LEDGER_DIR = Path(
    "research/personal/wa-corpus/approve-reject-ledger"
)
DEFAULT_OPERATOR_PACKET_REVIEW_CONSOLE_DIR = Path(
    "research/personal/wa-corpus/operator-packet-review-console"
)
DEFAULT_OWNER_DECISION_INTAKE_DIR = Path(
    "research/personal/wa-corpus/owner-decision-intake"
)
DEFAULT_OWNER_DECISION_REPLAY_DIR = Path(
    "research/personal/wa-corpus/owner-decision-replay"
)

DEFAULT_LEDGER_DB = DEFAULT_APPROVE_REJECT_LEDGER_DIR / "approve_reject_ledger.local.sqlite"
DEFAULT_REVIEW_CONSOLE_DB = (
    DEFAULT_OPERATOR_PACKET_REVIEW_CONSOLE_DIR
    / "operator_packet_review_console.local.sqlite"
)
DEFAULT_OWNER_DECISIONS_JSONL = (
    DEFAULT_OWNER_DECISION_INTAKE_DIR / "owner_decisions.local.jsonl"
)
DEFAULT_OUTPUT_DB = DEFAULT_OWNER_DECISION_REPLAY_DIR / "owner_decision_replay.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_OWNER_DECISION_REPLAY_DIR / "owner_decision_replay_summary.md"

INTAKE_STAGE_DIR = "owner-decision-intake"
OWNER_EVENTS_STAGE_DIR = "owner-decision-events"
WORK_ORDERS_STAGE_DIR = "post-decision-work-orders"
OPERATOR_PACKETS_STAGE_DIR = "operator-execution-packets"
FINAL_REVIEW_STAGE_DIR = "operator-packet-review-console"


@dataclass(frozen=True)
class OwnerDecisionReplayBuildResult:
    source_case_count: int
    source_review_item_count: int
    intake_item_count: int
    captured_owner_decision_count: int
    replay_event_count: int
    captured_event_count: int
    awaiting_input_count: int
    work_order_count: int
    ready_work_order_count: int
    blocked_work_order_count: int
    deferred_work_order_count: int
    rejected_work_order_count: int
    packet_count: int
    ready_packet_count: int
    blocked_packet_count: int
    deferred_packet_count: int
    rejected_packet_count: int
    final_review_item_count: int
    final_owner_decision_item_count: int
    final_operator_ready_item_count: int
    final_deferred_item_count: int
    final_rejected_item_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    output_db: Path
    summary_path: Path
    intake_db: Path
    owner_events_db: Path
    work_orders_db: Path
    operator_packets_db: Path
    final_review_console_db: Path


@dataclass(frozen=True)
class StageOutput:
    stage_rank: int
    stage_name: str
    item_count: int
    output_db: Path
    output_summary: Path


def _format_utc(value: str | None = None) -> str:
    if value is not None:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_manifest_sqlite(
    output_db: Path,
    *,
    result: OwnerDecisionReplayBuildResult,
    stages: Sequence[StageOutput],
    generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS owner_decision_replay_runs;
            DROP TABLE IF EXISTS owner_decision_replay_stage_outputs;

            CREATE TABLE owner_decision_replay_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_case_count INTEGER NOT NULL,
                source_review_item_count INTEGER NOT NULL,
                intake_item_count INTEGER NOT NULL,
                captured_owner_decision_count INTEGER NOT NULL,
                replay_event_count INTEGER NOT NULL,
                captured_event_count INTEGER NOT NULL,
                awaiting_input_count INTEGER NOT NULL,
                work_order_count INTEGER NOT NULL,
                ready_work_order_count INTEGER NOT NULL,
                blocked_work_order_count INTEGER NOT NULL,
                deferred_work_order_count INTEGER NOT NULL,
                rejected_work_order_count INTEGER NOT NULL,
                packet_count INTEGER NOT NULL,
                ready_packet_count INTEGER NOT NULL,
                blocked_packet_count INTEGER NOT NULL,
                deferred_packet_count INTEGER NOT NULL,
                rejected_packet_count INTEGER NOT NULL,
                final_review_item_count INTEGER NOT NULL,
                final_owner_decision_item_count INTEGER NOT NULL,
                final_operator_ready_item_count INTEGER NOT NULL,
                final_deferred_item_count INTEGER NOT NULL,
                final_rejected_item_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL CHECK (send_whatsapp_count = 0),
                crm_mutation_count INTEGER NOT NULL CHECK (crm_mutation_count = 0)
            );

            CREATE TABLE owner_decision_replay_stage_outputs (
                stage_rank INTEGER PRIMARY KEY,
                stage_name TEXT NOT NULL UNIQUE,
                item_count INTEGER NOT NULL,
                output_db TEXT NOT NULL,
                output_summary TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO owner_decision_replay_runs (
                id, generated_at_utc, privacy_mode, source_case_count,
                source_review_item_count, intake_item_count,
                captured_owner_decision_count, replay_event_count,
                captured_event_count, awaiting_input_count, work_order_count,
                ready_work_order_count, blocked_work_order_count,
                deferred_work_order_count, rejected_work_order_count,
                packet_count, ready_packet_count, blocked_packet_count,
                deferred_packet_count, rejected_packet_count,
                final_review_item_count, final_owner_decision_item_count,
                final_operator_ready_item_count, final_deferred_item_count,
                final_rejected_item_count, send_whatsapp_count,
                crm_mutation_count
            )
            VALUES (
                1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            )
            """,
            (
                generated_at_utc,
                "local_only_owner_decision_replay_no_raw_text_no_send_no_crm_mutation",
                result.source_case_count,
                result.source_review_item_count,
                result.intake_item_count,
                result.captured_owner_decision_count,
                result.replay_event_count,
                result.captured_event_count,
                result.awaiting_input_count,
                result.work_order_count,
                result.ready_work_order_count,
                result.blocked_work_order_count,
                result.deferred_work_order_count,
                result.rejected_work_order_count,
                result.packet_count,
                result.ready_packet_count,
                result.blocked_packet_count,
                result.deferred_packet_count,
                result.rejected_packet_count,
                result.final_review_item_count,
                result.final_owner_decision_item_count,
                result.final_operator_ready_item_count,
                result.final_deferred_item_count,
                result.final_rejected_item_count,
                result.send_whatsapp_count,
                result.crm_mutation_count,
            ),
        )
        conn.executemany(
            """
            INSERT INTO owner_decision_replay_stage_outputs (
                stage_rank, stage_name, item_count, output_db, output_summary
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    stage.stage_rank,
                    stage.stage_name,
                    stage.item_count,
                    str(stage.output_db),
                    str(stage.output_summary),
                )
                for stage in stages
            ],
        )
        conn.commit()


def _write_summary(
    summary_path: Path,
    *,
    result: OwnerDecisionReplayBuildResult,
    stages: Sequence[StageOutput],
    generated_at_utc: str,
) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Owner Decision Replay Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, judgment IDs, approval IDs, pack IDs, brief IDs, route IDs, ledger entry IDs, event IDs, work order IDs, packet IDs, or review item IDs.",
        "- Owner decision replay artifacts are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Source cases | {result.source_case_count} |",
        f"| Source review items | {result.source_review_item_count} |",
        f"| Intake items | {result.intake_item_count} |",
        f"| Captured owner decisions | {result.captured_owner_decision_count} |",
        f"| Replay events | {result.replay_event_count} |",
        f"| Captured events | {result.captured_event_count} |",
        f"| Awaiting owner input | {result.awaiting_input_count} |",
        f"| Work orders | {result.work_order_count} |",
        f"| Ready work orders | {result.ready_work_order_count} |",
        f"| Rejected work orders | {result.rejected_work_order_count} |",
        f"| Operator packets | {result.packet_count} |",
        f"| Ready packets | {result.ready_packet_count} |",
        f"| Rejected packets | {result.rejected_packet_count} |",
        f"| Final review items | {result.final_review_item_count} |",
        f"| Final owner-decision items | {result.final_owner_decision_item_count} |",
        f"| Final operator-ready items | {result.final_operator_ready_item_count} |",
        f"| Final rejected items | {result.final_rejected_item_count} |",
        f"| WhatsApp sends | {result.send_whatsapp_count} |",
        f"| CRM mutations | {result.crm_mutation_count} |",
        "| Human approval required | 100% |",
        "",
        "## Stage Outputs",
        "",
        "| Stage | Items |",
        "|---|---:|",
    ]
    lines.extend(
        f"| {stage.stage_name} | {stage.item_count} |" for stage in stages
    )
    lines.extend(
        [
            "",
            "## Execution Contract",
            "",
            "- This replay regenerates the owner decision intake, owner event capture, post-decision work orders, operator packets, and final review console.",
            "- It accepts only explicit owner approve, reject, or defer records.",
            "- Empty owner-decision files are valid and keep the chain waiting for owner input.",
            "- It does not invent owner decisions.",
            "- It does not parse raw WhatsApp messages.",
            "- It does not call a cloud LLM.",
            "- Runtime must not send WhatsApp messages from this artifact.",
            "- Runtime must not mutate CRM records from this artifact.",
            "- Human approval remains mandatory before any client-facing message or operational mutation.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_owner_decision_replay(
    *,
    ledger_db: Path = DEFAULT_LEDGER_DB,
    review_console_db: Path = DEFAULT_REVIEW_CONSOLE_DB,
    owner_decisions_jsonl: Path = DEFAULT_OWNER_DECISIONS_JSONL,
    output_dir: Path = DEFAULT_OWNER_DECISION_REPLAY_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    generated_at_utc: str | None = None,
) -> OwnerDecisionReplayBuildResult:
    """Replay explicit owner decisions through the full local-only chain."""
    generated = _format_utc(generated_at_utc)
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name

    intake_dir = output_dir / INTAKE_STAGE_DIR
    owner_events_dir = output_dir / OWNER_EVENTS_STAGE_DIR
    work_orders_dir = output_dir / WORK_ORDERS_STAGE_DIR
    operator_packets_dir = output_dir / OPERATOR_PACKETS_STAGE_DIR
    final_review_dir = output_dir / FINAL_REVIEW_STAGE_DIR

    intake_summary = intake_dir / "owner_decision_intake_summary.md"
    owner_events_summary = owner_events_dir / "owner_decision_event_capture_summary.md"
    work_orders_summary = work_orders_dir / "post_decision_work_order_queue_summary.md"
    operator_packets_summary = operator_packets_dir / "operator_execution_packets_summary.md"
    final_review_summary = final_review_dir / "operator_packet_review_console_summary.md"

    intake_result = build_owner_decision_intake(
        review_console_db=review_console_db,
        owner_decisions_jsonl=owner_decisions_jsonl,
        output_dir=intake_dir,
        summary_path=intake_summary,
        generated_at_utc=generated,
    )
    owner_events_result = build_owner_decision_event_capture(
        ledger_db=ledger_db,
        owner_events_jsonl=intake_result.output_jsonl,
        output_dir=owner_events_dir,
        summary_path=owner_events_summary,
        generated_at_utc=generated,
    )
    work_orders_result = build_post_decision_work_order_queue(
        owner_events_db=owner_events_result.output_db,
        output_dir=work_orders_dir,
        summary_path=work_orders_summary,
        generated_at_utc=generated,
    )
    operator_packets_result = build_operator_execution_packets(
        work_orders_db=work_orders_result.output_db,
        output_dir=operator_packets_dir,
        summary_path=operator_packets_summary,
        generated_at_utc=generated,
    )
    final_review_result = build_operator_packet_review_console(
        packets_db=operator_packets_result.output_db,
        output_dir=final_review_dir,
        summary_path=final_review_summary,
        generated_at_utc=generated,
    )

    send_whatsapp_count = sum(
        (
            intake_result.send_whatsapp_count,
            owner_events_result.send_whatsapp_count,
            work_orders_result.send_whatsapp_count,
            operator_packets_result.send_whatsapp_count,
            final_review_result.send_whatsapp_count,
        )
    )
    crm_mutation_count = sum(
        (
            intake_result.crm_mutation_count,
            owner_events_result.crm_mutation_count,
            work_orders_result.crm_mutation_count,
            operator_packets_result.crm_mutation_count,
            final_review_result.crm_mutation_count,
        )
    )

    result = OwnerDecisionReplayBuildResult(
        source_case_count=intake_result.source_case_count,
        source_review_item_count=intake_result.review_item_count,
        intake_item_count=intake_result.intake_item_count,
        captured_owner_decision_count=intake_result.captured_decision_count,
        replay_event_count=intake_result.replay_event_count,
        captured_event_count=owner_events_result.captured_event_count,
        awaiting_input_count=owner_events_result.awaiting_input_count,
        work_order_count=work_orders_result.work_order_count,
        ready_work_order_count=work_orders_result.ready_count,
        blocked_work_order_count=work_orders_result.blocked_count,
        deferred_work_order_count=work_orders_result.deferred_count,
        rejected_work_order_count=work_orders_result.rejected_count,
        packet_count=operator_packets_result.packet_count,
        ready_packet_count=operator_packets_result.ready_packet_count,
        blocked_packet_count=operator_packets_result.blocked_packet_count,
        deferred_packet_count=operator_packets_result.deferred_packet_count,
        rejected_packet_count=operator_packets_result.rejected_packet_count,
        final_review_item_count=final_review_result.review_item_count,
        final_owner_decision_item_count=final_review_result.owner_decision_item_count,
        final_operator_ready_item_count=final_review_result.operator_ready_item_count,
        final_deferred_item_count=final_review_result.deferred_item_count,
        final_rejected_item_count=final_review_result.rejected_item_count,
        send_whatsapp_count=send_whatsapp_count,
        crm_mutation_count=crm_mutation_count,
        output_db=output_db,
        summary_path=summary_path,
        intake_db=intake_result.output_db,
        owner_events_db=owner_events_result.output_db,
        work_orders_db=work_orders_result.output_db,
        operator_packets_db=operator_packets_result.output_db,
        final_review_console_db=final_review_result.output_db,
    )
    stages = (
        StageOutput(
            1,
            "owner_decision_intake",
            intake_result.intake_item_count,
            intake_result.output_db,
            intake_summary,
        ),
        StageOutput(
            2,
            "owner_decision_event_capture",
            owner_events_result.captured_event_count,
            owner_events_result.output_db,
            owner_events_summary,
        ),
        StageOutput(
            3,
            "post_decision_work_order_queue",
            work_orders_result.work_order_count,
            work_orders_result.output_db,
            work_orders_summary,
        ),
        StageOutput(
            4,
            "operator_execution_packets",
            operator_packets_result.packet_count,
            operator_packets_result.output_db,
            operator_packets_summary,
        ),
        StageOutput(
            5,
            "operator_packet_review_console",
            final_review_result.review_item_count,
            final_review_result.output_db,
            final_review_summary,
        ),
    )
    _write_manifest_sqlite(
        output_db,
        result=result,
        stages=stages,
        generated_at_utc=generated,
    )
    _write_summary(
        summary_path,
        result=result,
        stages=stages,
        generated_at_utc=generated,
    )
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay explicit owner decisions through the full local-only Zantara chain."
    )
    parser.add_argument("--ledger-db", type=Path, default=DEFAULT_LEDGER_DB)
    parser.add_argument("--review-console-db", type=Path, default=DEFAULT_REVIEW_CONSOLE_DB)
    parser.add_argument(
        "--owner-decisions-jsonl",
        type=Path,
        default=DEFAULT_OWNER_DECISIONS_JSONL,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OWNER_DECISION_REPLAY_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_owner_decision_replay(
            ledger_db=args.ledger_db,
            review_console_db=args.review_console_db,
            owner_decisions_jsonl=args.owner_decisions_jsonl,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Owner decision replay input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Owner decision replay run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Owner decision replay run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "awaiting_input_count": result.awaiting_input_count,
                    "captured_event_count": result.captured_event_count,
                    "captured_owner_decision_count": result.captured_owner_decision_count,
                    "crm_mutation_count": result.crm_mutation_count,
                    "final_operator_ready_item_count": result.final_operator_ready_item_count,
                    "final_owner_decision_item_count": result.final_owner_decision_item_count,
                    "final_rejected_item_count": result.final_rejected_item_count,
                    "final_review_item_count": result.final_review_item_count,
                    "packet_count": result.packet_count,
                    "replay_event_count": result.replay_event_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "source_case_count": result.source_case_count,
                    "source_review_item_count": result.source_review_item_count,
                    "work_order_count": result.work_order_count,
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Owner decision replay complete: "
            f"{result.final_review_item_count} final review items -> {result.output_db.name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
