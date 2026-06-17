from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.whatsapp_corpus.build_owner_decision_cockpit import (
    build_owner_decision_cockpit,
)
from scripts.whatsapp_corpus.build_owner_decision_compiler import (
    build_owner_decision_compiler,
)
from scripts.whatsapp_corpus.build_owner_decision_inbox import (
    build_owner_decision_inbox,
)
from scripts.whatsapp_corpus.build_owner_decision_intake import _format_utc
from scripts.whatsapp_corpus.build_owner_decision_replay import (
    build_owner_decision_replay,
)

DEFAULT_APPROVE_REJECT_LEDGER_DIR = Path(
    "research/personal/wa-corpus/approve-reject-ledger"
)
DEFAULT_OPERATOR_PACKET_REVIEW_CONSOLE_DIR = Path(
    "research/personal/wa-corpus/operator-packet-review-console"
)
DEFAULT_OWNER_DECISION_PIPELINE_DIR = Path(
    "research/personal/wa-corpus/owner-decision-pipeline"
)

DEFAULT_LEDGER_DB = DEFAULT_APPROVE_REJECT_LEDGER_DIR / "approve_reject_ledger.local.sqlite"
DEFAULT_REVIEW_CONSOLE_DB = (
    DEFAULT_OPERATOR_PACKET_REVIEW_CONSOLE_DIR
    / "operator_packet_review_console.local.sqlite"
)
DEFAULT_OUTPUT_DB = DEFAULT_OWNER_DECISION_PIPELINE_DIR / "owner_decision_pipeline.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_OWNER_DECISION_PIPELINE_DIR / "owner_decision_pipeline_summary.md"

INBOX_STAGE_DIR = "owner-decision-inbox"
COCKPIT_STAGE_DIR = "owner-decision-cockpit"
COMPILER_STAGE_DIR = "owner-decision-compiler"
REPLAY_STAGE_DIR = "owner-decision-replay"

PIPELINE_STATUS_REPLAYED = "replayed"
PIPELINE_STATUS_AWAITING_OWNER_INPUT = "awaiting_owner_input"


@dataclass(frozen=True)
class StageOutput:
    stage_rank: int
    stage_name: str
    item_count: int
    output_db: Path
    output_summary: Path


@dataclass(frozen=True)
class OwnerDecisionPipelineBuildResult:
    pipeline_status: str
    inbox_item_count: int
    captured_decision_count: int
    awaiting_owner_input_count: int
    compiled_decision_count: int
    replay_event_count: int
    final_review_item_count: int
    final_operator_ready_item_count: int
    final_rejected_item_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    output_db: Path
    summary_path: Path
    owner_inbox_db: Path
    owner_cockpit_db: Path
    owner_compiler_db: Path | None
    owner_replay_db: Path | None


def _remove_path_if_present(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            return


def _reset_downstream_outputs(output_dir: Path) -> None:
    for stage_dir in (COMPILER_STAGE_DIR, REPLAY_STAGE_DIR):
        _remove_path_if_present(output_dir / stage_dir)


def _sum_stage_count(results: Sequence[object], field_name: str) -> int:
    return sum(int(getattr(result, field_name)) for result in results)


def _write_manifest_sqlite(
    output_db: Path,
    *,
    result: OwnerDecisionPipelineBuildResult,
    stages: Sequence[StageOutput],
    generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    temp_db = output_db.with_name(f".{output_db.name}.tmp")
    if temp_db.exists():
        temp_db.unlink()
    with sqlite3.connect(temp_db) as conn:
        conn.executescript(
            """
            CREATE TABLE owner_decision_pipeline_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                pipeline_status TEXT NOT NULL,
                inbox_item_count INTEGER NOT NULL,
                captured_decision_count INTEGER NOT NULL,
                awaiting_owner_input_count INTEGER NOT NULL,
                compiled_decision_count INTEGER NOT NULL,
                replay_event_count INTEGER NOT NULL,
                final_review_item_count INTEGER NOT NULL,
                final_operator_ready_item_count INTEGER NOT NULL,
                final_rejected_item_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL CHECK (send_whatsapp_count = 0),
                crm_mutation_count INTEGER NOT NULL CHECK (crm_mutation_count = 0),
                owner_inbox_db TEXT NOT NULL,
                owner_cockpit_db TEXT NOT NULL,
                owner_compiler_db TEXT NOT NULL,
                owner_replay_db TEXT NOT NULL
            );

            CREATE TABLE owner_decision_pipeline_stage_outputs (
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
            INSERT INTO owner_decision_pipeline_runs (
                id, generated_at_utc, privacy_mode, pipeline_status,
                inbox_item_count, captured_decision_count,
                awaiting_owner_input_count, compiled_decision_count,
                replay_event_count, final_review_item_count,
                final_operator_ready_item_count, final_rejected_item_count,
                send_whatsapp_count, crm_mutation_count, owner_inbox_db,
                owner_cockpit_db, owner_compiler_db, owner_replay_db
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generated_at_utc,
                "local_only_owner_decision_pipeline_no_raw_text_no_send_no_crm_mutation",
                result.pipeline_status,
                result.inbox_item_count,
                result.captured_decision_count,
                result.awaiting_owner_input_count,
                result.compiled_decision_count,
                result.replay_event_count,
                result.final_review_item_count,
                result.final_operator_ready_item_count,
                result.final_rejected_item_count,
                result.send_whatsapp_count,
                result.crm_mutation_count,
                str(result.owner_inbox_db),
                str(result.owner_cockpit_db),
                str(result.owner_compiler_db or ""),
                str(result.owner_replay_db or ""),
            ),
        )
        conn.executemany(
            """
            INSERT INTO owner_decision_pipeline_stage_outputs (
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
    if output_db.exists():
        output_db.unlink()
    temp_db.replace(output_db)


def _write_summary(
    summary_path: Path,
    *,
    result: OwnerDecisionPipelineBuildResult,
    stages: Sequence[StageOutput],
    generated_at_utc: str,
) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Owner Decision Pipeline Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case IDs, ledger entry IDs, packet IDs, review item IDs, or inbox item IDs.",
        "- Owner Decision Pipeline artifacts stay in the local ignored workspace.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Pipeline status | {result.pipeline_status} |",
        f"| Owner inbox items | {result.inbox_item_count} |",
        f"| Captured decisions | {result.captured_decision_count} |",
        f"| Awaiting owner input | {result.awaiting_owner_input_count} |",
        f"| Compiled decisions | {result.compiled_decision_count} |",
        f"| Replay events | {result.replay_event_count} |",
        f"| Final review items | {result.final_review_item_count} |",
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
    lines.extend(f"| {stage.stage_name} | {stage.item_count} |" for stage in stages)
    lines.extend(
        [
            "",
            "## Execution Contract",
            "",
            "- This pipeline runs Owner Decision Inbox, Owner Decision Cockpit, Owner Decision Compiler, and Owner Decision Replay in order.",
            "- It records only explicit owner approve, reject, or defer inputs.",
            "- If any owner input is missing, it stops at the Cockpit with `awaiting_owner_input` and does not run the Compiler or Replay.",
            "- It passes the Cockpit template path explicitly into the Compiler.",
            "- It does not parse raw WhatsApp messages.",
            "- It does not call a cloud LLM.",
            "- Runtime must not send WhatsApp messages from this artifact.",
            "- Runtime must not mutate CRM records from this artifact.",
            "- Human approval remains mandatory before any client-facing message or operational mutation.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_owner_decision_pipeline(
    *,
    ledger_db: Path = DEFAULT_LEDGER_DB,
    review_console_db: Path = DEFAULT_REVIEW_CONSOLE_DB,
    owner_inputs_jsonl: Path | None = None,
    inline_decisions: Sequence[str] = (),
    inline_decision_notes: Sequence[str] = (),
    inline_event_recorded_at_utc: Sequence[str] = (),
    output_dir: Path = DEFAULT_OWNER_DECISION_PIPELINE_DIR,
    output_db: Path | None = None,
    summary_path: Path | None = None,
    generated_at_utc: str | None = None,
) -> OwnerDecisionPipelineBuildResult:
    """Run the local-only owner decision path from inbox through replay."""
    generated = _format_utc(generated_at_utc)
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    summary_path = summary_path or output_dir / DEFAULT_SUMMARY.name
    _reset_downstream_outputs(output_dir)

    inbox_dir = output_dir / INBOX_STAGE_DIR
    cockpit_dir = output_dir / COCKPIT_STAGE_DIR
    compiler_dir = output_dir / COMPILER_STAGE_DIR
    replay_dir = output_dir / REPLAY_STAGE_DIR

    inbox_summary = inbox_dir / "owner_decision_inbox_summary.md"
    cockpit_summary = cockpit_dir / "owner_decision_cockpit_summary.md"
    compiler_summary = compiler_dir / "owner_decision_compiler_summary.md"
    replay_summary = replay_dir / "owner_decision_replay_summary.md"

    inbox_result = build_owner_decision_inbox(
        review_console_db=review_console_db,
        output_dir=inbox_dir,
        summary_path=inbox_summary,
        generated_at_utc=generated,
    )
    cockpit_result = build_owner_decision_cockpit(
        owner_inbox_db=inbox_result.output_db,
        owner_inputs_jsonl=owner_inputs_jsonl,
        inline_decisions=inline_decisions,
        inline_decision_notes=inline_decision_notes,
        inline_event_recorded_at_utc=inline_event_recorded_at_utc,
        output_dir=cockpit_dir,
        summary_path=cockpit_summary,
        generated_at_utc=generated,
    )

    stages: list[StageOutput] = [
        StageOutput(
            1,
            "owner_decision_inbox",
            inbox_result.inbox_item_count,
            inbox_result.output_db,
            inbox_summary,
        ),
        StageOutput(
            2,
            "owner_decision_cockpit",
            cockpit_result.inbox_item_count,
            cockpit_result.output_db,
            cockpit_summary,
        ),
    ]

    if cockpit_result.awaiting_owner_input_count:
        invoked_results = (inbox_result, cockpit_result)
        result = OwnerDecisionPipelineBuildResult(
            pipeline_status=PIPELINE_STATUS_AWAITING_OWNER_INPUT,
            inbox_item_count=inbox_result.inbox_item_count,
            captured_decision_count=cockpit_result.captured_decision_count,
            awaiting_owner_input_count=cockpit_result.awaiting_owner_input_count,
            compiled_decision_count=0,
            replay_event_count=0,
            final_review_item_count=0,
            final_operator_ready_item_count=0,
            final_rejected_item_count=0,
            send_whatsapp_count=_sum_stage_count(
                invoked_results, "send_whatsapp_count"
            ),
            crm_mutation_count=_sum_stage_count(invoked_results, "crm_mutation_count"),
            output_db=output_db,
            summary_path=summary_path,
            owner_inbox_db=inbox_result.output_db,
            owner_cockpit_db=cockpit_result.output_db,
            owner_compiler_db=None,
            owner_replay_db=None,
        )
    else:
        compiler_result = build_owner_decision_compiler(
            owner_inbox_db=inbox_result.output_db,
            edited_template_jsonl=cockpit_result.output_template,
            output_dir=compiler_dir,
            summary_path=compiler_summary,
            generated_at_utc=generated,
        )
        replay_result = build_owner_decision_replay(
            ledger_db=ledger_db,
            review_console_db=review_console_db,
            owner_decisions_jsonl=compiler_result.output_jsonl,
            output_dir=replay_dir,
            summary_path=replay_summary,
            generated_at_utc=generated,
        )
        invoked_results = (
            inbox_result,
            cockpit_result,
            compiler_result,
            replay_result,
        )
        stages.extend(
            [
                StageOutput(
                    3,
                    "owner_decision_compiler",
                    compiler_result.compiled_decision_count,
                    compiler_result.output_db,
                    compiler_summary,
                ),
                StageOutput(
                    4,
                    "owner_decision_replay",
                    replay_result.final_review_item_count,
                    replay_result.output_db,
                    replay_summary,
                ),
            ]
        )
        result = OwnerDecisionPipelineBuildResult(
            pipeline_status=PIPELINE_STATUS_REPLAYED,
            inbox_item_count=inbox_result.inbox_item_count,
            captured_decision_count=cockpit_result.captured_decision_count,
            awaiting_owner_input_count=0,
            compiled_decision_count=compiler_result.compiled_decision_count,
            replay_event_count=replay_result.replay_event_count,
            final_review_item_count=replay_result.final_review_item_count,
            final_operator_ready_item_count=replay_result.final_operator_ready_item_count,
            final_rejected_item_count=replay_result.final_rejected_item_count,
            send_whatsapp_count=_sum_stage_count(
                invoked_results, "send_whatsapp_count"
            ),
            crm_mutation_count=_sum_stage_count(invoked_results, "crm_mutation_count"),
            output_db=output_db,
            summary_path=summary_path,
            owner_inbox_db=inbox_result.output_db,
            owner_cockpit_db=cockpit_result.output_db,
            owner_compiler_db=compiler_result.output_db,
            owner_replay_db=replay_result.output_db,
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
        description="Run the local-only Zantara Owner Decision Pipeline."
    )
    parser.add_argument("--ledger-db", type=Path, default=DEFAULT_LEDGER_DB)
    parser.add_argument("--review-console-db", type=Path, default=DEFAULT_REVIEW_CONSOLE_DB)
    parser.add_argument("--owner-inputs-jsonl", type=Path, default=None)
    parser.add_argument("--decision", action="append", default=[])
    parser.add_argument("--decision-note", action="append", default=[])
    parser.add_argument("--event-recorded-at-utc", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OWNER_DECISION_PIPELINE_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_owner_decision_pipeline(
            ledger_db=args.ledger_db,
            review_console_db=args.review_console_db,
            owner_inputs_jsonl=args.owner_inputs_jsonl,
            inline_decisions=args.decision,
            inline_decision_notes=args.decision_note,
            inline_event_recorded_at_utc=args.event_recorded_at_utc,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Owner decision pipeline input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Owner decision pipeline run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Owner decision pipeline run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "awaiting_owner_input_count": result.awaiting_owner_input_count,
                    "captured_decision_count": result.captured_decision_count,
                    "compiled_decision_count": result.compiled_decision_count,
                    "crm_mutation_count": result.crm_mutation_count,
                    "final_review_item_count": result.final_review_item_count,
                    "inbox_item_count": result.inbox_item_count,
                    "pipeline_status": result.pipeline_status,
                    "replay_event_count": result.replay_event_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Owner decision pipeline complete: "
            f"{result.pipeline_status} -> {result.output_db.name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
