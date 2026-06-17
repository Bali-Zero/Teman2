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

DEFAULT_CASE_TIMELINES_DIR = Path("research/personal/wa-corpus/case-timelines")
DEFAULT_EVIDENCE_GAPS_DIR = Path("research/personal/wa-corpus/evidence-gaps")

DEFAULT_CASE_TIMELINES_DB = DEFAULT_CASE_TIMELINES_DIR / "case_timelines.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_EVIDENCE_GAPS_DIR / "evidence_gaps.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_EVIDENCE_GAPS_DIR / "evidence_gaps_summary.md"

EXPECTED_CASE_TIMELINES_DB_NAME = "case_timelines.local.sqlite"


@dataclass(frozen=True)
class CaseTimelineRow:
    case_card_id: str
    timeline_rank: int
    timeline_status: str
    highest_risk: str
    assigned_lane: str
    primary_action: str
    latest_movement: str
    blocker_code: str
    event_count: int
    has_war_room_item: bool
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class EvidenceGap:
    gap_id: str
    case_card_id: str
    gap_rank: int
    assigned_lane: str
    primary_action: str
    timeline_status: str
    highest_risk: str
    blocker_code: str
    gap_code: str
    gap_category: str
    gap_severity: str
    closure_blocker: bool
    resolution_gate: str
    gap_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class EvidenceGapBuildResult:
    case_count: int
    gap_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    category_counts: dict[str, int]
    severity_counts: dict[str, int]
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


def read_case_timelines(db_path: Path) -> tuple[CaseTimelineRow, ...]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_CASE_TIMELINES_DB_NAME,
        label="Case Timelines",
    ) as conn:
        rows = conn.execute(
            """
            SELECT case_card_id, timeline_rank, timeline_status, highest_risk,
                   assigned_lane, primary_action, latest_movement, blocker_code,
                   event_count, has_war_room_item, send_whatsapp, crm_mutation,
                   requires_human_approval
            FROM case_timelines
            ORDER BY timeline_rank, case_card_id
            """
        ).fetchall()
    return tuple(
        CaseTimelineRow(
            case_card_id=str(row["case_card_id"]),
            timeline_rank=int(row["timeline_rank"]),
            timeline_status=str(row["timeline_status"]),
            highest_risk=str(row["highest_risk"]),
            assigned_lane=str(row["assigned_lane"]),
            primary_action=str(row["primary_action"]),
            latest_movement=str(row["latest_movement"]),
            blocker_code=str(row["blocker_code"]),
            event_count=int(row["event_count"]),
            has_war_room_item=bool(row["has_war_room_item"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def read_source_generated_at(db_path: Path) -> str:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_CASE_TIMELINES_DB_NAME,
        label="Case Timelines",
    ) as conn:
        row = conn.execute(
            "SELECT generated_at_utc FROM case_timeline_runs WHERE id = 1"
        ).fetchone()
    if row is None:
        return "unknown"
    return str(row["generated_at_utc"])


def _gap_mapping(row: CaseTimelineRow) -> tuple[str, str, str]:
    is_war_room = row.timeline_status == "war_room_active" or row.has_war_room_item
    if row.primary_action == "crm_followup":
        return (
            "client_followup_confirmation_missing",
            "client_response",
            "urgent" if is_war_room else "high",
        )
    if row.primary_action == "document_chase":
        return (
            "required_document_evidence_missing",
            "document",
            "high" if is_war_room else "medium",
        )
    if row.primary_action == "immigration_status_check":
        return (
            "immigration_status_evidence_missing",
            "status",
            "urgent" if is_war_room else "medium",
        )
    if row.primary_action == "payment_reconcile":
        return (
            "payment_reconciliation_evidence_missing",
            "finance",
            "high" if is_war_room else "medium",
        )
    return (
        "operator_review_evidence_missing",
        "operator_review",
        "high" if is_war_room else "medium",
    )


def _resolution_gate(*, gap_category: str, gap_severity: str) -> str:
    if gap_severity == "urgent":
        return "owner_review_required"
    if gap_category in {"document", "finance"}:
        return "operator_upload_required"
    return "lane_review_required"


def build_gaps(timelines: Sequence[CaseTimelineRow]) -> tuple[EvidenceGap, ...]:
    gaps: list[EvidenceGap] = []
    for rank, row in enumerate(timelines, start=1):
        gap_code, gap_category, gap_severity = _gap_mapping(row)
        resolution_gate = _resolution_gate(
            gap_category=gap_category,
            gap_severity=gap_severity,
        )
        payload = {
            "schema_version": "evidence_gap_detector.v1",
            "privacy_mode": "local_only_evidence_gap_no_raw_text",
            "source_timeline_status": row.timeline_status,
            "source_highest_risk": row.highest_risk,
            "source_blocker_code": row.blocker_code,
            "source_latest_movement": row.latest_movement,
            "source_event_count": row.event_count,
            "source_has_war_room_item": row.has_war_room_item,
            "closure_blocker": True,
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        gaps.append(
            EvidenceGap(
                gap_id=f"gap-{rank:06d}",
                case_card_id=row.case_card_id,
                gap_rank=rank,
                assigned_lane=row.assigned_lane,
                primary_action=row.primary_action,
                timeline_status=row.timeline_status,
                highest_risk=row.highest_risk,
                blocker_code=row.blocker_code,
                gap_code=gap_code,
                gap_category=gap_category,
                gap_severity=gap_severity,
                closure_blocker=True,
                resolution_gate=resolution_gate,
                gap_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(gaps)


def write_evidence_gap_sqlite(
    output_db: Path,
    *,
    gaps: Sequence[EvidenceGap],
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS evidence_gap_runs;
            DROP TABLE IF EXISTS evidence_gaps;

            CREATE TABLE evidence_gap_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                case_count INTEGER NOT NULL,
                gap_count INTEGER NOT NULL,
                closure_blocker_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE evidence_gaps (
                gap_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                gap_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                primary_action TEXT NOT NULL,
                timeline_status TEXT NOT NULL,
                highest_risk TEXT NOT NULL,
                blocker_code TEXT NOT NULL,
                gap_code TEXT NOT NULL,
                gap_category TEXT NOT NULL,
                gap_severity TEXT NOT NULL,
                closure_blocker INTEGER NOT NULL CHECK (closure_blocker = 1),
                resolution_gate TEXT NOT NULL,
                gap_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_evidence_gaps_rank ON evidence_gaps(gap_rank);
            CREATE INDEX idx_evidence_gaps_category ON evidence_gaps(gap_category);
            CREATE INDEX idx_evidence_gaps_severity ON evidence_gaps(gap_severity);
            CREATE INDEX idx_evidence_gaps_lane ON evidence_gaps(assigned_lane);
            CREATE INDEX idx_evidence_gaps_gate ON evidence_gaps(resolution_gate);
            """
        )
        conn.execute(
            """
            INSERT INTO evidence_gap_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                case_count, gap_count, closure_blocker_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                source_generated_at_utc,
                "local_only_evidence_gap_no_raw_text_no_send_no_crm_mutation",
                len(gaps),
                len(gaps),
                sum(1 for gap in gaps if gap.closure_blocker),
            ),
        )
        conn.executemany(
            """
            INSERT INTO evidence_gaps (
                gap_id, case_card_id, gap_rank, assigned_lane, primary_action,
                timeline_status, highest_risk, blocker_code, gap_code,
                gap_category, gap_severity, closure_blocker, resolution_gate,
                gap_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    gap.gap_id,
                    gap.case_card_id,
                    gap.gap_rank,
                    gap.assigned_lane,
                    gap.primary_action,
                    gap.timeline_status,
                    gap.highest_risk,
                    gap.blocker_code,
                    gap.gap_code,
                    gap.gap_category,
                    gap.gap_severity,
                    int(gap.closure_blocker),
                    gap.resolution_gate,
                    json.dumps(gap.gap_payload, ensure_ascii=False, sort_keys=True),
                    int(gap.send_whatsapp),
                    int(gap.crm_mutation),
                    int(gap.requires_human_approval),
                )
                for gap in gaps
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
    gaps: Sequence[EvidenceGap],
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    category_counts = Counter(gap.gap_category for gap in gaps)
    severity_counts = Counter(gap.gap_severity for gap in gaps)
    action_counts = Counter(gap.primary_action for gap in gaps)
    lane_counts = Counter(gap.assigned_lane for gap in gaps)
    gate_counts = Counter(gap.resolution_gate for gap in gaps)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Evidence Gap Detector Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source Case Timelines UTC: `{source_generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, event IDs, inbox item IDs, or room item IDs.",
        "- Evidence gap rows are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Cases reviewed | {len(gaps)} |",
        f"| Evidence gaps | {len(gaps)} |",
        f"| Closure blockers | {sum(1 for gap in gaps if gap.closure_blocker)} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Gap Categories", category_counts),
        "",
        *_counter_table("Gap Severities", severity_counts),
        "",
        *_counter_table("Primary Actions", action_counts),
        "",
        *_counter_table("Assigned Lanes", lane_counts),
        "",
        *_counter_table("Resolution Gates", gate_counts),
        "",
        "## Execution Contract",
        "",
        "- The Evidence Gap Detector converts local case timelines into explicit closure blockers.",
        "- It does not parse raw WhatsApp messages.",
        "- It does not call a cloud LLM.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- A human must approve every client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_evidence_gap_detector(
    *,
    case_timelines_db: Path = DEFAULT_CASE_TIMELINES_DB,
    output_dir: Path = DEFAULT_EVIDENCE_GAPS_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    generated_at_utc: str | None = None,
) -> EvidenceGapBuildResult:
    """Build local-only evidence gap blockers from case timelines."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    generated = _format_utc(generated_at_utc)
    source_generated = read_source_generated_at(case_timelines_db)
    timelines = read_case_timelines(case_timelines_db)
    gaps = build_gaps(timelines)
    write_evidence_gap_sqlite(
        output_db,
        gaps=gaps,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    write_summary(
        summary_path=summary_path,
        gaps=gaps,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    return EvidenceGapBuildResult(
        case_count=len(timelines),
        gap_count=len(gaps),
        send_whatsapp_count=sum(1 for gap in gaps if gap.send_whatsapp),
        crm_mutation_count=sum(1 for gap in gaps if gap.crm_mutation),
        category_counts=dict(Counter(gap.gap_category for gap in gaps)),
        severity_counts=dict(Counter(gap.gap_severity for gap in gaps)),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara evidence gaps from case timelines."
    )
    parser.add_argument("--case-timelines-db", type=Path, default=DEFAULT_CASE_TIMELINES_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_EVIDENCE_GAPS_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_evidence_gap_detector(
            case_timelines_db=args.case_timelines_db,
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
                    "case_count": result.case_count,
                    "crm_mutation_count": result.crm_mutation_count,
                    "gap_count": result.gap_count,
                    "output_db": str(result.output_db),
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "summary_path": str(result.summary_path),
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Evidence gap build complete: "
            f"{result.gap_count} gaps -> {result.output_db}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
