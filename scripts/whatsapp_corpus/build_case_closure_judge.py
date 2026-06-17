from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

DEFAULT_EVIDENCE_GAPS_DIR = Path("research/personal/wa-corpus/evidence-gaps")
DEFAULT_CASE_CLOSURE_DIR = Path("research/personal/wa-corpus/case-closure-judge")

DEFAULT_EVIDENCE_GAPS_DB = DEFAULT_EVIDENCE_GAPS_DIR / "evidence_gaps.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_CASE_CLOSURE_DIR / "case_closure_judge.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_CASE_CLOSURE_DIR / "case_closure_judge_summary.md"

EXPECTED_EVIDENCE_GAPS_DB_NAME = "evidence_gaps.local.sqlite"


@dataclass(frozen=True)
class EvidenceGapRow:
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
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class CaseClosureJudgment:
    judgment_id: str
    case_card_id: str
    judgment_rank: int
    assigned_lane: str
    primary_action: str
    closure_status: str
    closure_blocker_count: int
    top_gap_code: str
    top_gap_category: str
    top_gap_severity: str
    resolution_gate: str
    owner_attention_required: bool
    operator_evidence_required: bool
    lane_review_required: bool
    judge_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class CaseClosureJudgeBuildResult:
    case_count: int
    blocked_count: int
    ready_to_close_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    status_counts: dict[str, int]
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


def read_evidence_gaps(db_path: Path) -> tuple[EvidenceGapRow, ...]:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_EVIDENCE_GAPS_DB_NAME,
        label="Evidence Gaps",
    ) as conn:
        rows = conn.execute(
            """
            SELECT gap_id, case_card_id, gap_rank, assigned_lane, primary_action,
                   timeline_status, highest_risk, blocker_code, gap_code,
                   gap_category, gap_severity, closure_blocker, resolution_gate,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM evidence_gaps
            ORDER BY gap_rank, case_card_id, gap_id
            """
        ).fetchall()
    return tuple(
        EvidenceGapRow(
            gap_id=str(row["gap_id"]),
            case_card_id=str(row["case_card_id"]),
            gap_rank=int(row["gap_rank"]),
            assigned_lane=str(row["assigned_lane"]),
            primary_action=str(row["primary_action"]),
            timeline_status=str(row["timeline_status"]),
            highest_risk=str(row["highest_risk"]),
            blocker_code=str(row["blocker_code"]),
            gap_code=str(row["gap_code"]),
            gap_category=str(row["gap_category"]),
            gap_severity=str(row["gap_severity"]),
            closure_blocker=bool(row["closure_blocker"]),
            resolution_gate=str(row["resolution_gate"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def read_source_generated_at(db_path: Path) -> str:
    with _connect_ro(
        db_path,
        expected_name=EXPECTED_EVIDENCE_GAPS_DB_NAME,
        label="Evidence Gaps",
    ) as conn:
        row = conn.execute(
            "SELECT generated_at_utc FROM evidence_gap_runs WHERE id = 1"
        ).fetchone()
    if row is None:
        return "unknown"
    return str(row["generated_at_utc"])


def _severity_weight(value: str) -> int:
    return {"urgent": 3, "high": 2, "medium": 1}.get(value, 0)


def _pick_top_gap(rows: Sequence[EvidenceGapRow]) -> EvidenceGapRow:
    return sorted(
        rows,
        key=lambda row: (
            -_severity_weight(row.gap_severity),
            row.gap_rank,
            row.gap_id,
        ),
    )[0]


def _closure_status(rows: Sequence[EvidenceGapRow]) -> str:
    blockers = [row for row in rows if row.closure_blocker]
    if not blockers:
        return "ready_to_close"
    if any(
        row.resolution_gate == "owner_review_required" or row.gap_severity == "urgent"
        for row in blockers
    ):
        return "owner_review_blocked"
    if any(row.resolution_gate == "operator_upload_required" for row in blockers):
        return "evidence_upload_blocked"
    return "lane_review_blocked"


def build_judgments(gaps: Sequence[EvidenceGapRow]) -> tuple[CaseClosureJudgment, ...]:
    grouped: dict[str, list[EvidenceGapRow]] = defaultdict(list)
    for gap in gaps:
        grouped[gap.case_card_id].append(gap)

    ordered_cases = sorted(
        grouped.items(),
        key=lambda item: (min(row.gap_rank for row in item[1]), item[0]),
    )
    judgments: list[CaseClosureJudgment] = []
    for rank, (case_card_id, rows) in enumerate(ordered_cases, start=1):
        top_gap = _pick_top_gap(rows)
        closure_status = _closure_status(rows)
        owner_attention_required = closure_status == "owner_review_blocked"
        operator_evidence_required = closure_status == "evidence_upload_blocked"
        lane_review_required = closure_status == "lane_review_blocked"
        blocker_count = sum(1 for row in rows if row.closure_blocker)
        payload = {
            "schema_version": "case_closure_judge.v1",
            "privacy_mode": "local_only_case_closure_no_raw_text",
            "closure_decision": "ready_to_close" if blocker_count == 0 else "blocked",
            "closure_status": closure_status,
            "source_gap_count": len(rows),
            "closure_blocker_count": blocker_count,
            "top_gap_code": top_gap.gap_code,
            "top_gap_category": top_gap.gap_category,
            "top_gap_severity": top_gap.gap_severity,
            "resolution_gate": top_gap.resolution_gate,
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        judgments.append(
            CaseClosureJudgment(
                judgment_id=f"closure-{rank:06d}",
                case_card_id=case_card_id,
                judgment_rank=rank,
                assigned_lane=top_gap.assigned_lane,
                primary_action=top_gap.primary_action,
                closure_status=closure_status,
                closure_blocker_count=blocker_count,
                top_gap_code=top_gap.gap_code,
                top_gap_category=top_gap.gap_category,
                top_gap_severity=top_gap.gap_severity,
                resolution_gate=top_gap.resolution_gate,
                owner_attention_required=owner_attention_required,
                operator_evidence_required=operator_evidence_required,
                lane_review_required=lane_review_required,
                judge_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(judgments)


def write_case_closure_sqlite(
    output_db: Path,
    *,
    judgments: Sequence[CaseClosureJudgment],
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_db) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS case_closure_judge_runs;
            DROP TABLE IF EXISTS case_closure_judgments;

            CREATE TABLE case_closure_judge_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                source_generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                case_count INTEGER NOT NULL,
                blocked_count INTEGER NOT NULL,
                ready_to_close_count INTEGER NOT NULL,
                owner_review_count INTEGER NOT NULL,
                operator_evidence_count INTEGER NOT NULL,
                lane_review_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE case_closure_judgments (
                judgment_id TEXT PRIMARY KEY,
                case_card_id TEXT NOT NULL,
                judgment_rank INTEGER NOT NULL,
                assigned_lane TEXT NOT NULL,
                primary_action TEXT NOT NULL,
                closure_status TEXT NOT NULL,
                closure_blocker_count INTEGER NOT NULL,
                top_gap_code TEXT NOT NULL,
                top_gap_category TEXT NOT NULL,
                top_gap_severity TEXT NOT NULL,
                resolution_gate TEXT NOT NULL,
                owner_attention_required INTEGER NOT NULL,
                operator_evidence_required INTEGER NOT NULL,
                lane_review_required INTEGER NOT NULL,
                judge_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE INDEX idx_case_closure_rank ON case_closure_judgments(judgment_rank);
            CREATE INDEX idx_case_closure_status ON case_closure_judgments(closure_status);
            CREATE INDEX idx_case_closure_lane ON case_closure_judgments(assigned_lane);
            CREATE INDEX idx_case_closure_gate ON case_closure_judgments(resolution_gate);
            """
        )
        conn.execute(
            """
            INSERT INTO case_closure_judge_runs (
                id, generated_at_utc, source_generated_at_utc, privacy_mode,
                case_count, blocked_count, ready_to_close_count,
                owner_review_count, operator_evidence_count, lane_review_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                generated_at_utc,
                source_generated_at_utc,
                "local_only_case_closure_no_raw_text_no_send_no_crm_mutation",
                len(judgments),
                sum(1 for row in judgments if row.closure_status != "ready_to_close"),
                sum(1 for row in judgments if row.closure_status == "ready_to_close"),
                sum(1 for row in judgments if row.owner_attention_required),
                sum(1 for row in judgments if row.operator_evidence_required),
                sum(1 for row in judgments if row.lane_review_required),
            ),
        )
        conn.executemany(
            """
            INSERT INTO case_closure_judgments (
                judgment_id, case_card_id, judgment_rank, assigned_lane,
                primary_action, closure_status, closure_blocker_count,
                top_gap_code, top_gap_category, top_gap_severity,
                resolution_gate, owner_attention_required,
                operator_evidence_required, lane_review_required,
                judge_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.judgment_id,
                    row.case_card_id,
                    row.judgment_rank,
                    row.assigned_lane,
                    row.primary_action,
                    row.closure_status,
                    row.closure_blocker_count,
                    row.top_gap_code,
                    row.top_gap_category,
                    row.top_gap_severity,
                    row.resolution_gate,
                    int(row.owner_attention_required),
                    int(row.operator_evidence_required),
                    int(row.lane_review_required),
                    json.dumps(row.judge_payload, ensure_ascii=False, sort_keys=True),
                    int(row.send_whatsapp),
                    int(row.crm_mutation),
                    int(row.requires_human_approval),
                )
                for row in judgments
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
    judgments: Sequence[CaseClosureJudgment],
    generated_at_utc: str,
    source_generated_at_utc: str,
) -> None:
    status_counts = Counter(row.closure_status for row in judgments)
    lane_counts = Counter(row.assigned_lane for row in judgments)
    action_counts = Counter(row.primary_action for row in judgments)
    gate_counts = Counter(row.resolution_gate for row in judgments)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Case Closure Judge Summary",
        "",
        f"Generated UTC: `{generated_at_utc}`",
        f"Source Evidence Gaps UTC: `{source_generated_at_utc}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, case card IDs, gap IDs, event IDs, inbox item IDs, or room item IDs.",
        "- Closure judgment rows are local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Cases judged | {len(judgments)} |",
        f"| Blocked cases | {sum(1 for row in judgments if row.closure_status != 'ready_to_close')} |",
        f"| Ready to close | {sum(1 for row in judgments if row.closure_status == 'ready_to_close')} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Closure Status", status_counts),
        "",
        *_counter_table("Assigned Lanes", lane_counts),
        "",
        *_counter_table("Primary Actions", action_counts),
        "",
        *_counter_table("Resolution Gates", gate_counts),
        "",
        "## Execution Contract",
        "",
        "- The Case Closure Judge converts evidence gaps into case-level closure decisions.",
        "- It does not parse raw WhatsApp messages.",
        "- It does not call a cloud LLM.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- A human must approve every closure decision, client-facing message, or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_case_closure_judge(
    *,
    evidence_gaps_db: Path = DEFAULT_EVIDENCE_GAPS_DB,
    output_dir: Path = DEFAULT_CASE_CLOSURE_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    generated_at_utc: str | None = None,
) -> CaseClosureJudgeBuildResult:
    """Build local-only case closure judgments from evidence gaps."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    generated = _format_utc(generated_at_utc)
    source_generated = read_source_generated_at(evidence_gaps_db)
    gaps = read_evidence_gaps(evidence_gaps_db)
    judgments = build_judgments(gaps)
    write_case_closure_sqlite(
        output_db,
        judgments=judgments,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    write_summary(
        summary_path=summary_path,
        judgments=judgments,
        generated_at_utc=generated,
        source_generated_at_utc=source_generated,
    )
    return CaseClosureJudgeBuildResult(
        case_count=len(judgments),
        blocked_count=sum(1 for row in judgments if row.closure_status != "ready_to_close"),
        ready_to_close_count=sum(
            1 for row in judgments if row.closure_status == "ready_to_close"
        ),
        send_whatsapp_count=sum(1 for row in judgments if row.send_whatsapp),
        crm_mutation_count=sum(1 for row in judgments if row.crm_mutation),
        status_counts=dict(Counter(row.closure_status for row in judgments)),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara case closure judgments from evidence gaps."
    )
    parser.add_argument("--evidence-gaps-db", type=Path, default=DEFAULT_EVIDENCE_GAPS_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_CASE_CLOSURE_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--generated-at-utc", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_case_closure_judge(
            evidence_gaps_db=args.evidence_gaps_db,
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
                    "blocked_count": result.blocked_count,
                    "case_count": result.case_count,
                    "crm_mutation_count": result.crm_mutation_count,
                    "output_db": str(result.output_db),
                    "ready_to_close_count": result.ready_to_close_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "summary_path": str(result.summary_path),
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Case closure judge complete: "
            f"{result.case_count} cases -> {result.output_db}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
