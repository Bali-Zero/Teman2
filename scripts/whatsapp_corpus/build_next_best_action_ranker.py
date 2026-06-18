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
DEFAULT_NEXT_ACTION_DIR = Path("research/personal/wa-corpus/next-best-actions")
DEFAULT_CASE_MEMORY_DB = DEFAULT_CASE_MEMORY_DIR / "case_memory_cards.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_NEXT_ACTION_DIR / "next_best_actions.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_NEXT_ACTION_DIR / "next_best_actions_summary.md"

EXPECTED_CASE_MEMORY_DB_NAME = "case_memory_cards.local.sqlite"


@dataclass(frozen=True)
class CaseMemoryCardRow:
    case_card_id: str
    case_owner: str
    case_status: str
    risk_level: str
    next_best_action: str
    assigned_lane: str
    latest_movement: str
    blocker_code: str
    review_rank: int
    card_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class RankedAction:
    case_card_id: str
    action_rank: int
    action_code: str
    action_title: str
    reason_code: str
    urgency_score: int
    impact_score: int
    combined_score: int
    assigned_lane: str
    action_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class NextBestActionBuildResult:
    case_count: int
    action_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    top_action_counts: dict[str, int]
    reason_counts: dict[str, int]
    output_db: Path
    summary_path: Path


def _connect_case_memory(db_path: Path) -> sqlite3.Connection:
    if db_path.name != EXPECTED_CASE_MEMORY_DB_NAME:
        raise ValueError(f"Refusing to read unexpected Case Memory DB: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"Case Memory DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_case_memory_cards(
    db_path: Path,
    *,
    limit: int | None = None,
) -> tuple[CaseMemoryCardRow, ...]:
    with _connect_case_memory(db_path) as conn:
        sql = """
            SELECT case_card_id, case_owner, case_status, risk_level,
                   next_best_action, assigned_lane, latest_movement, blocker_code,
                   review_rank, card_payload_json, send_whatsapp, crm_mutation,
                   requires_human_approval
            FROM case_memory_cards
            ORDER BY review_rank, case_card_id
        """
        if limit is not None:
            sql += " LIMIT ?"
            rows = conn.execute(sql, (limit,)).fetchall()
        else:
            rows = conn.execute(sql).fetchall()
    return tuple(
        CaseMemoryCardRow(
            case_card_id=str(row["case_card_id"]),
            case_owner=str(row["case_owner"]),
            case_status=str(row["case_status"]),
            risk_level=str(row["risk_level"]),
            next_best_action=str(row["next_best_action"]),
            assigned_lane=str(row["assigned_lane"]),
            latest_movement=str(row["latest_movement"]),
            blocker_code=str(row["blocker_code"]),
            review_rank=int(row["review_rank"]),
            card_payload=json.loads(str(row["card_payload_json"])),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def _reason_code(card: CaseMemoryCardRow) -> str:
    return {
        "case_stall_followup_risk": "stale_followup",
        "payment_reconciliation_needed": "payment_risk",
        "missing_document_chase_needed": "missing_doc",
        "immigration_status_gap": "status_gap",
        "operator_escalation_needed": "operator_escalation",
        "knowledge_capture_needed": "knowledge_capture",
    }.get(card.blocker_code, "case_review_needed")


def _action_title(action_code: str) -> str:
    return action_code.replace("_", " ").title()


def _action_templates(card: CaseMemoryCardRow) -> tuple[tuple[str, str, int], ...]:
    primary_reason = _reason_code(card)
    templates: dict[str, tuple[tuple[str, str, int], ...]] = {
        "crm_followup": (
            ("crm_followup", primary_reason, 85),
            ("operator_system_update", "missing_system_update", 80),
            ("client_status_draft_review", "client_confused_or_silent", 75),
        ),
        "payment_reconcile": (
            ("payment_reconcile", primary_reason, 90),
            ("ledger_check", "finance_verification", 80),
            ("proof_of_payment_review", "payment_evidence_gap", 75),
        ),
        "document_chase": (
            ("document_chase", primary_reason, 88),
            ("checklist_gap_review", "missing_doc", 82),
            ("document_request_draft_review", "client_confused_or_silent", 74),
        ),
        "immigration_status_check": (
            ("immigration_status_check", primary_reason, 88),
            ("case_timeline_review", "status_gap", 82),
            ("specialist_status_confirmation", "operator_escalation", 76),
        ),
        "team_escalation": (
            ("team_escalation", primary_reason, 86),
            ("owner_attention_review", "operator_escalation", 84),
            ("operator_system_update", "missing_system_update", 78),
        ),
    }
    return templates.get(
        card.next_best_action,
        (
            (card.next_best_action, primary_reason, 80),
            ("case_timeline_review", "case_review_needed", 75),
            ("operator_system_update", "missing_system_update", 70),
        ),
    )


def _urgency_score(card: CaseMemoryCardRow, action_rank: int) -> int:
    base = {"P1": 100, "P2": 70, "P3": 45}.get(card.risk_level, 40)
    score = base - ((action_rank - 1) * 5)
    if card.review_rank > 1000:
        score -= 5
    return max(0, min(100, score))


def _combined_score(urgency_score: int, impact_score: int) -> int:
    return round((urgency_score * 0.6) + (impact_score * 0.4))


def build_ranked_actions(cards: Sequence[CaseMemoryCardRow]) -> tuple[RankedAction, ...]:
    actions: list[RankedAction] = []
    for card in cards:
        for action_rank, (action_code, reason_code, impact_score) in enumerate(
            _action_templates(card),
            start=1,
        ):
            urgency_score = _urgency_score(card, action_rank)
            payload = {
                "schema_version": "next_best_action.v1",
                "privacy_mode": "local_only_case_memory_no_raw_text",
                "case_owner": card.case_owner,
                "source_case_status": card.case_status,
                "source_risk_level": card.risk_level,
                "source_blocker_code": card.blocker_code,
                "latest_movement": card.latest_movement,
                "reason_code": reason_code,
                "urgency_score": urgency_score,
                "impact_score": impact_score,
                "combined_score": _combined_score(urgency_score, impact_score),
                "raw_text_included": False,
                "send_whatsapp": False,
                "crm_mutation": False,
                "requires_human_approval": True,
            }
            actions.append(
                RankedAction(
                    case_card_id=card.case_card_id,
                    action_rank=action_rank,
                    action_code=action_code,
                    action_title=_action_title(action_code),
                    reason_code=reason_code,
                    urgency_score=urgency_score,
                    impact_score=impact_score,
                    combined_score=int(payload["combined_score"]),
                    assigned_lane=card.assigned_lane,
                    action_payload=payload,
                    send_whatsapp=False,
                    crm_mutation=False,
                    requires_human_approval=True,
                )
            )
    return tuple(actions)


def write_rankings_sqlite(path: Path, actions: Sequence[RankedAction]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    case_count = len({action.case_card_id for action in actions})
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE next_best_action_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                case_count INTEGER NOT NULL,
                action_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE next_best_action_rankings (
                case_card_id TEXT NOT NULL,
                action_rank INTEGER NOT NULL,
                action_code TEXT NOT NULL,
                action_title TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                urgency_score INTEGER NOT NULL,
                impact_score INTEGER NOT NULL,
                combined_score INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                action_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1),
                PRIMARY KEY (case_card_id, action_rank)
            );

            CREATE INDEX idx_next_best_action_rankings_rank ON next_best_action_rankings(action_rank);
            CREATE INDEX idx_next_best_action_rankings_code ON next_best_action_rankings(action_code);
            CREATE INDEX idx_next_best_action_rankings_reason ON next_best_action_rankings(reason_code);
            CREATE INDEX idx_next_best_action_rankings_lane ON next_best_action_rankings(assigned_lane);
            """
        )
        conn.execute(
            """
            INSERT INTO next_best_action_runs (
                id, generated_at_utc, privacy_mode, case_count, action_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, 0, 0)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "local_only_next_best_actions_no_raw_text_no_send_no_crm_mutation",
                case_count,
                len(actions),
            ),
        )
        conn.executemany(
            """
            INSERT INTO next_best_action_rankings (
                case_card_id, action_rank, action_code, action_title, reason_code,
                urgency_score, impact_score, combined_score, assigned_lane,
                action_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    action.case_card_id,
                    action.action_rank,
                    action.action_code,
                    action.action_title,
                    action.reason_code,
                    action.urgency_score,
                    action.impact_score,
                    action.combined_score,
                    action.assigned_lane,
                    json.dumps(action.action_payload, ensure_ascii=False, sort_keys=True),
                    int(action.send_whatsapp),
                    int(action.crm_mutation),
                    int(action.requires_human_approval),
                )
                for action in actions
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
    actions: Sequence[RankedAction],
    generated_at_utc: str | None = None,
) -> None:
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    ranked_cases = {action.case_card_id for action in actions}
    top_action_counts = Counter(
        action.action_code for action in actions if action.action_rank == 1
    )
    reason_counts = Counter(action.reason_code for action in actions)
    lane_counts = Counter(action.assigned_lane for action in actions if action.action_rank == 1)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Next Best Action Ranker Summary",
        "",
        f"Generated UTC: `{generated}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, shadow IDs, or window IDs.",
        "- Next best action rankings are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Ranked cases | {len(ranked_cases)} |",
        f"| Ranked actions | {len(actions)} |",
        "| Actions per case | 3 |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Top Ranked Actions", top_action_counts),
        "",
        *_counter_table("Reason Codes", reason_counts),
        "",
        *_counter_table("Primary Lanes", lane_counts),
        "",
        "## Execution Contract",
        "",
        "- The ranker orders possible actions by urgency and impact.",
        "- It creates review-ready options; it does not execute them.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- A human must approve any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_next_best_action_ranker(
    *,
    case_memory_db: Path = DEFAULT_CASE_MEMORY_DB,
    output_dir: Path = DEFAULT_NEXT_ACTION_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    max_cases: int | None = None,
) -> NextBestActionBuildResult:
    """Build local-only top-three next best actions for each case memory card."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    cards = read_case_memory_cards(case_memory_db, limit=max_cases)
    actions = build_ranked_actions(cards)
    write_rankings_sqlite(output_db, actions)
    write_summary(summary_path=summary_path, actions=actions)
    return NextBestActionBuildResult(
        case_count=len(cards),
        action_count=len(actions),
        send_whatsapp_count=sum(1 for action in actions if action.send_whatsapp),
        crm_mutation_count=sum(1 for action in actions if action.crm_mutation),
        top_action_counts=dict(
            Counter(action.action_code for action in actions if action.action_rank == 1)
        ),
        reason_counts=dict(Counter(action.reason_code for action in actions)),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara Next Best Action rankings from case memory cards."
    )
    parser.add_argument("--case-memory-db", type=Path, default=DEFAULT_CASE_MEMORY_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_NEXT_ACTION_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_next_best_action_ranker(
            case_memory_db=args.case_memory_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
            max_cases=args.max_cases,
        )
    except (FileNotFoundError, ValueError, sqlite3.Error, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "case_count": result.case_count,
                    "action_count": result.action_count,
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
