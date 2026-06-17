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

DEFAULT_OWNER_PACKS_DIR = Path("research/personal/wa-corpus/owner-decision-packs")
DEFAULT_OWNER_BRIEF_DIR = Path("research/personal/wa-corpus/owner-brief-renderer")

DEFAULT_OWNER_PACKS_DB = DEFAULT_OWNER_PACKS_DIR / "owner_decision_packs.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_OWNER_BRIEF_DIR / "owner_brief_renderer.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_OWNER_BRIEF_DIR / "owner_brief_renderer_summary.md"

EXPECTED_OWNER_PACKS_DB_NAME = "owner_decision_packs.local.sqlite"


@dataclass(frozen=True)
class OwnerDecisionPackRow:
    pack_id: str
    case_card_id: str
    pack_rank: int
    assigned_lane: str
    decision_type: str
    decision_priority: str
    owner_prompt_code: str
    pack_title: str
    risk_brief: str
    recommended_decision: str
    draft_action_type: str
    draft_action_status: str
    approval_status: str
    top_gap_code: str
    top_gap_category: str
    top_gap_severity: str
    resolution_gate: str
    owner_decision_required: bool
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OwnerBrief:
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
    brief_markdown: str
    brief_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OwnerBriefRendererBuildResult:
    source_case_count: int
    owner_item_count: int
    pack_count: int
    brief_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    decision_type_counts: dict[str, int]
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


def read_source_metadata(db_path: Path) -> tuple[str, int, int, int]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_OWNER_PACKS_DB_NAME,
        label="Owner Decision Packs",
    ) as conn:
        row = conn.execute(
            """
            SELECT generated_at_utc, source_case_count, owner_item_count, pack_count
            FROM owner_decision_pack_runs
            WHERE id = 1
            """
        ).fetchone()
    if row is None:
        return "unknown", 0, 0, 0
    return (
        str(row["generated_at_utc"]),
        int(row["source_case_count"]),
        int(row["owner_item_count"]),
        int(row["pack_count"]),
    )


def read_owner_pack_rows(db_path: Path) -> tuple[OwnerDecisionPackRow, ...]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_OWNER_PACKS_DB_NAME,
        label="Owner Decision Packs",
    ) as conn:
        rows = conn.execute(
            """
            SELECT pack_id, case_card_id, pack_rank, assigned_lane,
                   decision_type, decision_priority, owner_prompt_code,
                   pack_title, risk_brief, recommended_decision,
                   draft_action_type, draft_action_status, approval_status,
                   top_gap_code, top_gap_category, top_gap_severity,
                   resolution_gate, owner_decision_required, send_whatsapp,
                   crm_mutation, requires_human_approval
            FROM owner_decision_packs
            ORDER BY pack_rank, case_card_id
            """
        ).fetchall()
    return tuple(
        OwnerDecisionPackRow(
            pack_id=str(row["pack_id"]),
            case_card_id=str(row["case_card_id"]),
            pack_rank=int(row["pack_rank"]),
            assigned_lane=str(row["assigned_lane"]),
            decision_type=str(row["decision_type"]),
            decision_priority=str(row["decision_priority"]),
            owner_prompt_code=str(row["owner_prompt_code"]),
            pack_title=str(row["pack_title"]),
            risk_brief=str(row["risk_brief"]),
            recommended_decision=str(row["recommended_decision"]),
            draft_action_type=str(row["draft_action_type"]),
            draft_action_status=str(row["draft_action_status"]),
            approval_status=str(row["approval_status"]),
            top_gap_code=str(row["top_gap_code"]),
            top_gap_category=str(row["top_gap_category"]),
            top_gap_severity=str(row["top_gap_severity"]),
            resolution_gate=str(row["resolution_gate"]),
            owner_decision_required=bool(row["owner_decision_required"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def _owner_focus(decision_type: str) -> str:
    return {
        "approve_client_recovery_followup": "review_client_recovery_language",
        "approve_immigration_status_escalation": "review_immigration_status_escalation",
        "approve_document_evidence_request": "review_document_evidence_request",
        "approve_payment_reconciliation_review": "review_payment_reconciliation",
    }.get(decision_type, "review_owner_case_decision")


def _brief_markdown(row: OwnerDecisionPackRow, *, owner_focus: str) -> str:
    lines = [
        f"# {row.pack_title}",
        "",
        f"Priority: {row.decision_priority}",
        f"Lane: {row.assigned_lane}",
        f"Owner focus: {owner_focus}",
        f"Risk: {row.risk_brief}",
        f"Recommended decision: {row.recommended_decision}",
        f"Draft action: {row.draft_action_type}",
        f"Approval status: {row.approval_status}",
        "Safety lock: owner approval required before send or CRM mutation.",
    ]
    return "\n".join(lines) + "\n"


def build_briefs(rows: Sequence[OwnerDecisionPackRow]) -> tuple[OwnerBrief, ...]:
    briefs: list[OwnerBrief] = []
    for rank, row in enumerate(rows, start=1):
        owner_focus = _owner_focus(row.decision_type)
        markdown = _brief_markdown(row, owner_focus=owner_focus)
        payload = {
            "schema_version": "owner_brief_renderer.v1",
            "privacy_mode": "local_only_owner_brief_no_raw_text",
            "source_pack_rank": row.pack_rank,
            "source_decision_type": row.decision_type,
            "source_owner_prompt_code": row.owner_prompt_code,
            "owner_focus": owner_focus,
            "recommended_decision": row.recommended_decision,
            "draft_action_type": row.draft_action_type,
            "safety_lock": "owner_approval_required_no_send_no_crm",
            "rendered_markdown_includes_ids": False,
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        briefs.append(
            OwnerBrief(
                brief_id=f"owner-brief-{rank:06d}",
                pack_id=row.pack_id,
                case_card_id=row.case_card_id,
                brief_rank=rank,
                assigned_lane=row.assigned_lane,
                decision_type=row.decision_type,
                decision_priority=row.decision_priority,
                brief_title=row.pack_title,
                owner_focus=owner_focus,
                recommended_decision=row.recommended_decision,
                draft_action_type=row.draft_action_type,
                safety_lock="owner_approval_required_no_send_no_crm",
                approval_status=row.approval_status,
                brief_markdown=markdown,
                brief_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(briefs)


def write_owner_briefs_sqlite(
    output_db: Path,
    *,
    briefs: Sequence[OwnerBrief],
    source_case_count: int,
    owner_item_count: int,
    pack_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS owner_brief_renderer_runs;
            DROP TABLE IF EXISTS owner_briefs;

            CREATE TABLE owner_brief_renderer_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                source_case_count INTEGER NOT NULL,
                owner_item_count INTEGER NOT NULL,
                pack_count INTEGER NOT NULL,
                brief_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE owner_briefs (
                brief_id TEXT PRIMARY KEY,
                pack_id TEXT NOT NULL,
                case_card_id TEXT NOT NULL,
                brief_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_priority TEXT NOT NULL,
                brief_title TEXT NOT NULL,
                owner_focus TEXT NOT NULL,
                recommended_decision TEXT NOT NULL,
                draft_action_type TEXT NOT NULL,
                safety_lock TEXT NOT NULL,
                approval_status TEXT NOT NULL,
                brief_markdown TEXT NOT NULL,
                brief_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_owner_brief_rank ON owner_briefs(brief_rank);
            CREATE INDEX idx_owner_brief_lane ON owner_briefs(assigned_lane);
            CREATE INDEX idx_owner_brief_type ON owner_briefs(decision_type);
            CREATE INDEX idx_owner_brief_priority ON owner_briefs(decision_priority);
            CREATE INDEX idx_owner_brief_focus ON owner_briefs(owner_focus);
            """
        )
        conn.execute(
            """
            INSERT INTO owner_brief_renderer_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                source_case_count, owner_item_count, pack_count, brief_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                source_generated_at_utc,
                "local_only_owner_brief_no_raw_text_no_send_no_crm_mutation",
                source_case_count,
                owner_item_count,
                pack_count,
                len(briefs),
            ),
        )
        conn.executemany(
            """
            INSERT INTO owner_briefs (
                brief_id, pack_id, case_card_id, brief_rank, assigned_lane,
                decision_type, decision_priority, brief_title, owner_focus,
                recommended_decision, draft_action_type, safety_lock,
                approval_status, brief_markdown, brief_payload_json,
                send_whatsapp, crm_mutation, requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    brief.brief_id,
                    brief.pack_id,
                    brief.case_card_id,
                    brief.brief_rank,
                    brief.assigned_lane,
                    brief.decision_type,
                    brief.decision_priority,
                    brief.brief_title,
                    brief.owner_focus,
                    brief.recommended_decision,
                    brief.draft_action_type,
                    brief.safety_lock,
                    brief.approval_status,
                    brief.brief_markdown,
                    json.dumps(brief.brief_payload, ensure_ascii=False, sort_keys=True),
                    int(brief.send_whatsapp),
                    int(brief.crm_mutation),
                    int(brief.requires_human_approval),
                )
                for brief in briefs
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
    briefs: Sequence[OwnerBrief],
    source_case_count: int,
    owner_item_count: int,
    pack_count: int,
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    decision_counts = Counter(brief.decision_type for brief in briefs)
    lane_counts = Counter(brief.assigned_lane for brief in briefs)
    priority_counts = Counter(brief.decision_priority for brief in briefs)
    focus_counts = Counter(brief.owner_focus for brief in briefs)
    safety_counts = Counter(brief.safety_lock for brief in briefs)
    approval_counts = Counter(brief.approval_status for brief in briefs)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Owner Brief Renderer Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source Owner Decision Packs UTC: `{source_generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, judgment IDs, approval IDs, pack IDs, brief IDs, gap IDs, event IDs, inbox item IDs, or room item IDs.",
        "- Rendered owner briefs are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Source cases | {source_case_count} |",
        f"| Owner approval items | {owner_item_count} |",
        f"| Owner decision packs | {pack_count} |",
        f"| Rendered owner briefs | {len(briefs)} |",
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
        *_counter_table("Owner Focus", focus_counts),
        "",
        *_counter_table("Safety Locks", safety_counts),
        "",
        *_counter_table("Approval Status", approval_counts),
        "",
        "## Execution Contract",
        "",
        "- The Owner Brief Renderer turns decision packs into readable owner briefs.",
        "- Rendered brief markdown contains no raw IDs.",
        "- It does not parse raw WhatsApp messages.",
        "- It does not call a cloud LLM.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- Owner approval remains mandatory before any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_owner_brief_renderer(
    *,
    owner_packs_db: Path = DEFAULT_OWNER_PACKS_DB,
    output_dir: Path = DEFAULT_OWNER_BRIEF_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    generated_at_utc: str | None = None,
) -> OwnerBriefRendererBuildResult:
    """Build local-only rendered owner briefs from decision packs."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    generated = _format_utc(generated_at_utc)
    source_generated, source_case_count, owner_item_count, pack_count = read_source_metadata(
        owner_packs_db
    )
    rows = read_owner_pack_rows(owner_packs_db)
    briefs = build_briefs(rows)
    source_case_total = source_case_count or len(rows)
    owner_item_total = owner_item_count or len(rows)
    pack_total = pack_count or len(rows)
    write_owner_briefs_sqlite(
        output_db,
        briefs=briefs,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    write_summary(
        summary_path=summary_path,
        briefs=briefs,
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    return OwnerBriefRendererBuildResult(
        source_case_count=source_case_total,
        owner_item_count=owner_item_total,
        pack_count=pack_total,
        brief_count=len(briefs),
        send_whatsapp_count=sum(1 for brief in briefs if brief.send_whatsapp),
        crm_mutation_count=sum(1 for brief in briefs if brief.crm_mutation),
        decision_type_counts=dict(Counter(brief.decision_type for brief in briefs)),
        lane_counts=dict(Counter(brief.assigned_lane for brief in briefs)),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara owner brief renderer from owner decision packs."
    )
    parser.add_argument("--owner-packs-db", type=Path, default=DEFAULT_OWNER_PACKS_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OWNER_BRIEF_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_owner_brief_renderer(
            owner_packs_db=args.owner_packs_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
            generated_at_utc=args.generated_at_utc,
        )
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        print("ERROR: Owner brief renderer input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        print("ERROR: Owner brief renderer run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: Owner brief renderer run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "brief_count": result.brief_count,
                    "crm_mutation_count": result.crm_mutation_count,
                    "owner_item_count": result.owner_item_count,
                    "pack_count": result.pack_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "source_case_count": result.source_case_count,
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Owner brief renderer complete: "
            f"{result.brief_count} briefs -> {result.output_db.name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
