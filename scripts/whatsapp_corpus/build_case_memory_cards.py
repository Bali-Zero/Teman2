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

DEFAULT_CLIENT_SHADOW_DIR = Path("research/personal/wa-corpus/client-captain-shadow")
DEFAULT_CASE_MEMORY_DIR = Path("research/personal/wa-corpus/case-memory-cards")
DEFAULT_CLIENT_SHADOW_DB = DEFAULT_CLIENT_SHADOW_DIR / "client_captain_shadow.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_CASE_MEMORY_DIR / "case_memory_cards.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_CASE_MEMORY_DIR / "case_memory_cards_summary.md"

EXPECTED_CLIENT_SHADOW_DB_NAME = "client_captain_shadow.local.sqlite"


@dataclass(frozen=True)
class ShadowDraftRow:
    shadow_id: str
    source_window_id: str
    case_owner: str
    priority: str
    risk_level: str
    action_type: str
    human_specialist: str
    diagnosis_code: str
    draft_reply_intent: str
    operator_coaching_mode: str
    operator_nudge: str
    first_month: str
    last_month: str
    first_message_index: int
    last_message_index: int
    cut_message_index: int
    dominant_domain: str
    event_count: int
    message_count: int
    domain_count: int
    severity_high_count: int
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class CaseMemoryCard:
    case_card_id: str
    source_shadow_id: str
    source_window_id: str
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
class CaseMemoryBuildResult:
    card_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    risk_counts: dict[str, int]
    action_counts: dict[str, int]
    output_db: Path
    summary_path: Path


def _connect_client_shadow(db_path: Path) -> sqlite3.Connection:
    if db_path.name != EXPECTED_CLIENT_SHADOW_DB_NAME:
        raise ValueError(f"Refusing to read unexpected Client Shadow DB: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"Client Shadow DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_shadow_drafts(db_path: Path, *, limit: int | None = None) -> tuple[ShadowDraftRow, ...]:
    with _connect_client_shadow(db_path) as conn:
        sql = """
            SELECT shadow_id, source_window_id, case_owner, priority, risk_level,
                   action_type, human_specialist, diagnosis_code, draft_reply_intent,
                   operator_coaching_mode, operator_nudge, first_month, last_month,
                   first_message_index, last_message_index, cut_message_index,
                   dominant_domain, event_count, message_count, domain_count,
                   severity_high_count, send_whatsapp, crm_mutation,
                   requires_human_approval
            FROM shadow_drafts
            ORDER BY
                CASE risk_level WHEN 'P1' THEN 0 WHEN 'P2' THEN 1 WHEN 'P3' THEN 2 ELSE 3 END,
                severity_high_count DESC,
                event_count DESC,
                message_count DESC,
                shadow_id
        """
        if limit is not None:
            sql += " LIMIT ?"
            rows = conn.execute(sql, (limit,)).fetchall()
        else:
            rows = conn.execute(sql).fetchall()
    return tuple(
        ShadowDraftRow(
            shadow_id=str(row["shadow_id"]),
            source_window_id=str(row["source_window_id"]),
            case_owner=str(row["case_owner"]),
            priority=str(row["priority"]),
            risk_level=str(row["risk_level"]),
            action_type=str(row["action_type"]),
            human_specialist=str(row["human_specialist"]),
            diagnosis_code=str(row["diagnosis_code"]),
            draft_reply_intent=str(row["draft_reply_intent"]),
            operator_coaching_mode=str(row["operator_coaching_mode"]),
            operator_nudge=str(row["operator_nudge"]),
            first_month=str(row["first_month"]),
            last_month=str(row["last_month"]),
            first_message_index=int(row["first_message_index"]),
            last_message_index=int(row["last_message_index"]),
            cut_message_index=int(row["cut_message_index"]),
            dominant_domain=str(row["dominant_domain"]),
            event_count=int(row["event_count"]),
            message_count=int(row["message_count"]),
            domain_count=int(row["domain_count"]),
            severity_high_count=int(row["severity_high_count"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def read_depth_layer_counts(db_path: Path) -> dict[str, int]:
    with _connect_client_shadow(db_path) as conn:
        rows = conn.execute(
            """
            SELECT shadow_id, COUNT(*) AS layer_count
            FROM shadow_depth_layers
            GROUP BY shadow_id
            """
        ).fetchall()
    return {str(row["shadow_id"]): int(row["layer_count"]) for row in rows}


def _case_status(row: ShadowDraftRow) -> str:
    if row.risk_level == "P1":
        return "needs_human_review"
    if row.risk_level == "P2":
        return "monitor_and_prepare"
    return "watch"


def _risk_rank(risk_level: str) -> int:
    return {"P1": 1, "P2": 2, "P3": 3}.get(risk_level, 9)


def _latest_movement(row: ShadowDraftRow) -> str:
    return f"{row.last_month}:{row.last_message_index}"


def build_cards(
    rows: Sequence[ShadowDraftRow],
    *,
    depth_layer_counts: dict[str, int],
) -> tuple[CaseMemoryCard, ...]:
    cards: list[CaseMemoryCard] = []
    for index, row in enumerate(rows, start=1):
        payload = {
            "schema_version": "case_memory_card.v1",
            "privacy_mode": "local_only_shadow_aggregate_no_raw_text",
            "case_owner": row.case_owner,
            "dominant_domain": row.dominant_domain,
            "priority": row.priority,
            "diagnosis_code": row.diagnosis_code,
            "draft_reply_intent": row.draft_reply_intent,
            "operator_coaching_mode": row.operator_coaching_mode,
            "operator_nudge": row.operator_nudge,
            "first_month": row.first_month,
            "last_month": row.last_month,
            "message_count": row.message_count,
            "event_count": row.event_count,
            "domain_count": row.domain_count,
            "severity_high_count": row.severity_high_count,
            "depth_layer_count": depth_layer_counts.get(row.shadow_id, 0),
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        cards.append(
            CaseMemoryCard(
                case_card_id=f"card-{row.shadow_id}",
                source_shadow_id=row.shadow_id,
                source_window_id=row.source_window_id,
                case_owner=row.case_owner,
                case_status=_case_status(row),
                risk_level=row.risk_level,
                next_best_action=row.action_type,
                assigned_lane=row.human_specialist,
                latest_movement=_latest_movement(row),
                blocker_code=row.diagnosis_code,
                review_rank=index,
                card_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(cards)


def write_cards_sqlite(path: Path, cards: Sequence[CaseMemoryCard]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE case_memory_card_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                card_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE case_memory_cards (
                case_card_id TEXT PRIMARY KEY,
                source_shadow_id TEXT NOT NULL,
                source_window_id TEXT NOT NULL,
                case_owner TEXT NOT NULL,
                case_status TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                next_best_action TEXT NOT NULL,
                assigned_lane TEXT NOT NULL,
                latest_movement TEXT NOT NULL,
                blocker_code TEXT NOT NULL,
                review_rank INTEGER NOT NULL,
                card_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_case_memory_cards_rank ON case_memory_cards(review_rank);
            CREATE INDEX idx_case_memory_cards_risk ON case_memory_cards(risk_level);
            CREATE INDEX idx_case_memory_cards_lane ON case_memory_cards(assigned_lane);
            """
        )
        conn.execute(
            """
            INSERT INTO case_memory_card_runs (
                id, generated_at_utc, privacy_mode, card_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, 0, 0)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "local_only_case_memory_cards_no_raw_text_no_send_no_crm_mutation",
                len(cards),
            ),
        )
        conn.executemany(
            """
            INSERT INTO case_memory_cards (
                case_card_id, source_shadow_id, source_window_id, case_owner,
                case_status, risk_level, next_best_action, assigned_lane,
                latest_movement, blocker_code, review_rank, card_payload_json,
                send_whatsapp, crm_mutation, requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    card.case_card_id,
                    card.source_shadow_id,
                    card.source_window_id,
                    card.case_owner,
                    card.case_status,
                    card.risk_level,
                    card.next_best_action,
                    card.assigned_lane,
                    card.latest_movement,
                    card.blocker_code,
                    card.review_rank,
                    json.dumps(card.card_payload, ensure_ascii=False, sort_keys=True),
                    int(card.send_whatsapp),
                    int(card.crm_mutation),
                    int(card.requires_human_approval),
                )
                for card in cards
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
    cards: Sequence[CaseMemoryCard],
    generated_at_utc: str | None = None,
) -> None:
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    risk_counts = Counter(card.risk_level for card in cards)
    action_counts = Counter(card.next_best_action for card in cards)
    lane_counts = Counter(card.assigned_lane for card in cards)
    status_counts = Counter(card.case_status for card in cards)
    blocker_counts = Counter(card.blocker_code for card in cards)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Case Memory Cards Summary",
        "",
        f"Generated UTC: `{generated}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, file IDs, window IDs, or shadow IDs.",
        "- Case memory cards are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Case memory cards | {len(cards)} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Case Statuses", status_counts),
        "",
        *_counter_table("Risk Levels", risk_counts),
        "",
        *_counter_table("Next Best Actions", action_counts),
        "",
        *_counter_table("Assigned Lanes", lane_counts),
        "",
        *_counter_table("Blocker Codes", blocker_counts),
        "",
        "## Execution Contract",
        "",
        "- A card is a compact local memory object for human review.",
        "- Cards can rank, summarize, and route work.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- A human must approve any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_case_memory_cards(
    *,
    client_shadow_db: Path = DEFAULT_CLIENT_SHADOW_DB,
    output_dir: Path = DEFAULT_CASE_MEMORY_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    max_cards: int | None = None,
) -> CaseMemoryBuildResult:
    """Build compact local-only case memory cards from Client Captain Shadow drafts."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    rows = read_shadow_drafts(client_shadow_db, limit=max_cards)
    depth_layer_counts = read_depth_layer_counts(client_shadow_db)
    cards = build_cards(rows, depth_layer_counts=depth_layer_counts)
    write_cards_sqlite(output_db, cards)
    write_summary(summary_path=summary_path, cards=cards)
    return CaseMemoryBuildResult(
        card_count=len(cards),
        send_whatsapp_count=sum(1 for card in cards if card.send_whatsapp),
        crm_mutation_count=sum(1 for card in cards if card.crm_mutation),
        risk_counts=dict(Counter(card.risk_level for card in cards)),
        action_counts=dict(Counter(card.next_best_action for card in cards)),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara Case Memory Cards from Client Captain Shadow."
    )
    parser.add_argument("--client-shadow-db", type=Path, default=DEFAULT_CLIENT_SHADOW_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_CASE_MEMORY_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--max-cards", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_case_memory_cards(
            client_shadow_db=args.client_shadow_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
            max_cards=args.max_cards,
        )
    except (FileNotFoundError, ValueError, sqlite3.Error, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "card_count": result.card_count,
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
