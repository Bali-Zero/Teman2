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

DEFAULT_CLIENT_CAPTAIN_DIR = Path("research/personal/wa-corpus/client-captain")
DEFAULT_SHADOW_DIR = Path("research/personal/wa-corpus/client-captain-shadow")
DEFAULT_ACADEMY_DB = DEFAULT_CLIENT_CAPTAIN_DIR / "client_captain_academy.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_SHADOW_DIR / "client_captain_shadow.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_SHADOW_DIR / "client_captain_shadow_summary.md"

EXPECTED_ACADEMY_DB_NAME = "client_captain_academy.local.sqlite"
CASE_OWNER = "zantara_client_captain"


@dataclass(frozen=True)
class AcademyReplayRow:
    example_id: str
    replay_id: str
    source_window_id: str
    file_id: str
    case_owner: str
    dominant_domain: str
    priority: str
    next_action: str
    human_specialist: str
    operator_coaching_mode: str
    first_month: str
    last_month: str
    first_message_index: int
    last_message_index: int
    cut_message_index: int
    event_count: int
    message_count: int
    domain_count: int
    severity_high_count: int


@dataclass(frozen=True)
class ShadowDraft:
    shadow_id: str
    source_example_id: str
    source_replay_id: str
    source_window_id: str
    source_file_id: str
    case_owner: str
    status: str
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
class ShadowDepthLayer:
    shadow_id: str
    depth_level: int
    layer_code: str
    layer_title: str
    layer_payload: dict[str, object]


@dataclass(frozen=True)
class ShadowBuildResult:
    draft_count: int
    depth_layer_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    priority_counts: dict[str, int]
    action_counts: dict[str, int]
    output_db: Path
    summary_path: Path


def _connect_academy(db_path: Path) -> sqlite3.Connection:
    if db_path.name != EXPECTED_ACADEMY_DB_NAME:
        raise ValueError(f"Refusing to read unexpected Academy DB: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"Academy DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_academy_replays(db_path: Path, *, limit: int | None = None) -> tuple[AcademyReplayRow, ...]:
    with _connect_academy(db_path) as conn:
        sql = """
            SELECT
                t.example_id,
                r.replay_id,
                t.source_window_id,
                t.file_id,
                t.case_owner,
                t.dominant_domain,
                t.priority,
                t.next_action,
                t.human_specialist,
                t.operator_coaching_mode,
                t.first_month,
                t.last_month,
                t.first_message_index,
                t.last_message_index,
                r.cut_message_index,
                t.event_count,
                t.message_count,
                t.domain_count,
                t.severity_high_count
            FROM captain_training_examples AS t
            JOIN captain_replay_scenarios AS r
                ON r.example_id = t.example_id
            ORDER BY
                CASE t.priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,
                t.severity_high_count DESC,
                t.event_count DESC,
                t.example_id
        """
        if limit is not None:
            sql += " LIMIT ?"
            rows = conn.execute(sql, (limit,)).fetchall()
        else:
            rows = conn.execute(sql).fetchall()
    return tuple(
        AcademyReplayRow(
            example_id=str(row["example_id"]),
            replay_id=str(row["replay_id"]),
            source_window_id=str(row["source_window_id"]),
            file_id=str(row["file_id"]),
            case_owner=str(row["case_owner"]),
            dominant_domain=str(row["dominant_domain"]),
            priority=str(row["priority"]),
            next_action=str(row["next_action"]),
            human_specialist=str(row["human_specialist"]),
            operator_coaching_mode=str(row["operator_coaching_mode"]),
            first_month=str(row["first_month"]),
            last_month=str(row["last_month"]),
            first_message_index=int(row["first_message_index"]),
            last_message_index=int(row["last_message_index"]),
            cut_message_index=int(row["cut_message_index"]),
            event_count=int(row["event_count"]),
            message_count=int(row["message_count"]),
            domain_count=int(row["domain_count"]),
            severity_high_count=int(row["severity_high_count"]),
        )
        for row in rows
    )


def _risk_level(priority: str) -> str:
    if priority == "high":
        return "P1"
    if priority == "normal":
        return "P2"
    return "P3"


def _diagnosis_code(row: AcademyReplayRow) -> str:
    if row.dominant_domain == "followup_risk" or row.next_action == "crm_followup":
        return "case_stall_followup_risk"
    if row.next_action == "payment_reconcile":
        return "payment_reconciliation_needed"
    if row.next_action == "document_chase":
        return "missing_document_chase_needed"
    if row.next_action == "immigration_status_check":
        return "immigration_status_gap"
    if row.next_action == "team_escalation":
        return "operator_escalation_needed"
    if row.next_action == "kb_extract":
        return "knowledge_capture_needed"
    return "case_note_needed"


def _draft_reply_intent(row: AcademyReplayRow) -> str:
    return {
        "crm_followup": (
            "Draft a concise status follow-up after a human confirms the latest system update."
        ),
        "payment_reconcile": (
            "Draft a payment status clarification after finance verifies the ledger and proof."
        ),
        "document_chase": (
            "Draft a missing-document request after the operator verifies the case checklist."
        ),
        "immigration_status_check": (
            "Draft an immigration status update after the specialist confirms the current stage."
        ),
        "team_escalation": (
            "Draft no client reply; create an internal escalation brief for the team first."
        ),
        "kb_extract": (
            "Draft no client reply; capture the reusable knowledge point for review first."
        ),
    }.get(row.next_action, "Draft an internal case note for human review before any reply.")


def _operator_nudge(row: AcademyReplayRow) -> str:
    if row.operator_coaching_mode == "firm_accountability_nudge":
        return "Firm: operator must make a system update before continuing; no silent handling."
    if row.operator_coaching_mode == "supportive_urgent_nudge":
        return "Urgent: help the operator close the loop quickly and log the next step."
    return "Supportive: keep the operator moving and reinforce the family-standard workflow."


def build_shadow_drafts(rows: Sequence[AcademyReplayRow]) -> tuple[ShadowDraft, ...]:
    drafts: list[ShadowDraft] = []
    for row in rows:
        if row.case_owner != CASE_OWNER:
            continue
        drafts.append(
            ShadowDraft(
                shadow_id=f"shadow-{row.example_id}",
                source_example_id=row.example_id,
                source_replay_id=row.replay_id,
                source_window_id=row.source_window_id,
                source_file_id=row.file_id,
                case_owner=CASE_OWNER,
                status="shadow_draft",
                priority=row.priority,
                risk_level=_risk_level(row.priority),
                action_type=row.next_action,
                human_specialist=row.human_specialist,
                diagnosis_code=_diagnosis_code(row),
                draft_reply_intent=_draft_reply_intent(row),
                operator_coaching_mode=row.operator_coaching_mode,
                operator_nudge=_operator_nudge(row),
                first_month=row.first_month,
                last_month=row.last_month,
                first_message_index=row.first_message_index,
                last_message_index=row.last_message_index,
                cut_message_index=row.cut_message_index,
                dominant_domain=row.dominant_domain,
                event_count=row.event_count,
                message_count=row.message_count,
                domain_count=row.domain_count,
                severity_high_count=row.severity_high_count,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(drafts)


def build_depth_layers(drafts: Sequence[ShadowDraft]) -> tuple[ShadowDepthLayer, ...]:
    layers: list[ShadowDepthLayer] = []
    for draft in drafts:
        base_payload = {
            "case_owner": draft.case_owner,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        layer_specs = [
            (
                1,
                "signal_readout",
                "Signal readout",
                {
                    "risk_level": draft.risk_level,
                    "dominant_domain": draft.dominant_domain,
                    "event_count": draft.event_count,
                    "message_count": draft.message_count,
                },
            ),
            (
                2,
                "case_diagnosis",
                "Case diagnosis",
                {
                    "diagnosis_code": draft.diagnosis_code,
                    "severity_high_count": draft.severity_high_count,
                    "domain_count": draft.domain_count,
                },
            ),
            (
                3,
                "captain_decision",
                "Captain decision",
                {
                    "action_type": draft.action_type,
                    "human_specialist": draft.human_specialist,
                    "priority": draft.priority,
                },
            ),
            (
                4,
                "draft_gate",
                "Draft gate",
                {
                    "draft_reply_intent": draft.draft_reply_intent,
                    "status": draft.status,
                },
            ),
            (
                5,
                "operator_coaching",
                "Operator coaching",
                {
                    "operator_coaching_mode": draft.operator_coaching_mode,
                    "operator_nudge": draft.operator_nudge,
                },
            ),
        ]
        for depth_level, code, title, payload in layer_specs:
            layers.append(
                ShadowDepthLayer(
                    shadow_id=draft.shadow_id,
                    depth_level=depth_level,
                    layer_code=code,
                    layer_title=title,
                    layer_payload={**base_payload, **payload},
                )
            )
    return tuple(layers)


def write_shadow_sqlite(
    path: Path,
    drafts: Sequence[ShadowDraft],
    layers: Sequence[ShadowDepthLayer],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE shadow_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                draft_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE shadow_drafts (
                shadow_id TEXT PRIMARY KEY,
                source_example_id TEXT NOT NULL,
                source_replay_id TEXT NOT NULL,
                source_window_id TEXT NOT NULL,
                source_file_id TEXT NOT NULL,
                case_owner TEXT NOT NULL,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                action_type TEXT NOT NULL,
                human_specialist TEXT NOT NULL,
                diagnosis_code TEXT NOT NULL,
                draft_reply_intent TEXT NOT NULL,
                operator_coaching_mode TEXT NOT NULL,
                operator_nudge TEXT NOT NULL,
                first_month TEXT NOT NULL,
                last_month TEXT NOT NULL,
                first_message_index INTEGER NOT NULL,
                last_message_index INTEGER NOT NULL,
                cut_message_index INTEGER NOT NULL,
                dominant_domain TEXT NOT NULL,
                event_count INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                domain_count INTEGER NOT NULL,
                severity_high_count INTEGER NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE TABLE shadow_depth_layers (
                shadow_id TEXT NOT NULL,
                depth_level INTEGER NOT NULL,
                layer_code TEXT NOT NULL,
                layer_title TEXT NOT NULL,
                layer_payload_json TEXT NOT NULL,
                PRIMARY KEY (shadow_id, depth_level)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO shadow_runs (
                id, generated_at_utc, privacy_mode, draft_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, 0, 0)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "local_only_shadow_drafts_no_send_no_crm_mutation",
                len(drafts),
            ),
        )
        conn.executemany(
            """
            INSERT INTO shadow_drafts (
                shadow_id, source_example_id, source_replay_id, source_window_id,
                source_file_id, case_owner, status, priority, risk_level, action_type,
                human_specialist, diagnosis_code, draft_reply_intent,
                operator_coaching_mode, operator_nudge, first_month, last_month,
                first_message_index, last_message_index, cut_message_index,
                dominant_domain, event_count, message_count, domain_count,
                severity_high_count, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    draft.shadow_id,
                    draft.source_example_id,
                    draft.source_replay_id,
                    draft.source_window_id,
                    draft.source_file_id,
                    draft.case_owner,
                    draft.status,
                    draft.priority,
                    draft.risk_level,
                    draft.action_type,
                    draft.human_specialist,
                    draft.diagnosis_code,
                    draft.draft_reply_intent,
                    draft.operator_coaching_mode,
                    draft.operator_nudge,
                    draft.first_month,
                    draft.last_month,
                    draft.first_message_index,
                    draft.last_message_index,
                    draft.cut_message_index,
                    draft.dominant_domain,
                    draft.event_count,
                    draft.message_count,
                    draft.domain_count,
                    draft.severity_high_count,
                    int(draft.send_whatsapp),
                    int(draft.crm_mutation),
                    int(draft.requires_human_approval),
                )
                for draft in drafts
            ],
        )
        conn.executemany(
            """
            INSERT INTO shadow_depth_layers (
                shadow_id, depth_level, layer_code, layer_title, layer_payload_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    layer.shadow_id,
                    layer.depth_level,
                    layer.layer_code,
                    layer.layer_title,
                    json.dumps(layer.layer_payload, ensure_ascii=False, sort_keys=True),
                )
                for layer in layers
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
    drafts: Sequence[ShadowDraft],
    generated_at_utc: str | None = None,
) -> None:
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    priority_counts = Counter(draft.priority for draft in drafts)
    risk_counts = Counter(draft.risk_level for draft in drafts)
    action_counts = Counter(draft.action_type for draft in drafts)
    diagnosis_counts = Counter(draft.diagnosis_code for draft in drafts)
    coaching_counts = Counter(draft.operator_coaching_mode for draft in drafts)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Client Captain Shadow Mode Summary",
        "",
        f"Generated UTC: `{generated}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, file IDs, window IDs, or replay IDs.",
        "- Shadow output is local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Shadow drafts | {len(drafts)} |",
        f"| Depth layers | {len(drafts) * 5} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Priorities", priority_counts),
        "",
        *_counter_table("Risk Levels", risk_counts),
        "",
        *_counter_table("Action Types", action_counts),
        "",
        *_counter_table("Diagnosis Codes", diagnosis_counts),
        "",
        *_counter_table("Operator Coaching Modes", coaching_counts),
        "",
        "## Execution Contract",
        "",
        "- The Captain remains the case owner.",
        "- Shadow mode can diagnose, draft, coach, and queue review only.",
        "- Runtime must not send WhatsApp messages from this artifact.",
        "- Runtime must not mutate CRM records from this artifact.",
        "- A human must approve any client-facing message or operational mutation.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_client_captain_shadow(
    *,
    academy_db: Path = DEFAULT_ACADEMY_DB,
    output_dir: Path = DEFAULT_SHADOW_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
    max_drafts: int | None = None,
) -> ShadowBuildResult:
    """Build deterministic local-only Shadow Mode drafts from Academy replays."""
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    rows = read_academy_replays(academy_db, limit=max_drafts)
    drafts = build_shadow_drafts(rows)
    layers = build_depth_layers(drafts)
    write_shadow_sqlite(output_db, drafts, layers)
    write_summary(summary_path=summary_path, drafts=drafts)
    send_whatsapp_count = sum(1 for draft in drafts if draft.send_whatsapp)
    crm_mutation_count = sum(1 for draft in drafts if draft.crm_mutation)
    return ShadowBuildResult(
        draft_count=len(drafts),
        depth_layer_count=len(layers),
        send_whatsapp_count=send_whatsapp_count,
        crm_mutation_count=crm_mutation_count,
        priority_counts=dict(Counter(draft.priority for draft in drafts)),
        action_counts=dict(Counter(draft.action_type for draft in drafts)),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara Client Captain Shadow Mode drafts."
    )
    parser.add_argument("--academy-db", type=Path, default=DEFAULT_ACADEMY_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_SHADOW_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--max-drafts", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_client_captain_shadow(
            academy_db=args.academy_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
            max_drafts=args.max_drafts,
        )
    except (FileNotFoundError, ValueError, TypeError):
        # Keep this fixed literal: exception text may include local paths or DB names.
        print("ERROR: Client Captain input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        # Keep this fixed literal: exception text may include local paths or DB names.
        print("ERROR: Client Captain shadow run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        # CLI boundary must fail closed; the Python API still exposes details.
        print("ERROR: Client Captain shadow run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "draft_count": result.draft_count,
                    "depth_layer_count": result.depth_layer_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "crm_mutation_count": result.crm_mutation_count,
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
