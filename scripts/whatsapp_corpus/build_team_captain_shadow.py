from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

DEFAULT_CLIENT_SHADOW_DIR = Path("research/personal/wa-corpus/client-captain-shadow")
DEFAULT_OPERATOR_REVIEW_CONSOLE_DIR = Path(
    "research/personal/wa-corpus/operator-packet-review-console"
)
DEFAULT_TEAM_SHADOW_DIR = Path("research/personal/wa-corpus/team-captain-shadow")
DEFAULT_CLIENT_SHADOW_DB = DEFAULT_CLIENT_SHADOW_DIR / "client_captain_shadow.local.sqlite"
DEFAULT_OPERATOR_REVIEW_CONSOLE_DB = (
    DEFAULT_OPERATOR_REVIEW_CONSOLE_DIR / "operator_packet_review_console.local.sqlite"
)
DEFAULT_OUTPUT_DB = DEFAULT_TEAM_SHADOW_DIR / "team_captain_shadow.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_TEAM_SHADOW_DIR / "team_captain_shadow_summary.md"

EXPECTED_CLIENT_SHADOW_DB_NAME = "client_captain_shadow.local.sqlite"
EXPECTED_OPERATOR_REVIEW_CONSOLE_DB_NAME = "operator_packet_review_console.local.sqlite"
TEAM_OWNER = "zantara_team_captain"


@dataclass(frozen=True)
class ClientShadowRow:
    shadow_id: str
    risk_level: str
    action_type: str
    human_specialist: str
    diagnosis_code: str
    operator_coaching_mode: str
    dominant_domain: str
    event_count: int
    message_count: int
    severity_high_count: int
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OperatorReviewConsoleRow:
    assigned_lane: str
    operator_lane: str
    review_state: str
    console_bucket: str
    review_priority: str
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class TeamFinding:
    team_captain_id: str
    team_owner: str
    human_specialist: str
    draft_count: int
    p1_count: int
    p2_count: int
    primary_action_type: str
    primary_diagnosis_code: str
    primary_coaching_mode: str
    accountability_mode: str
    total_event_count: int
    total_message_count: int
    input_contract_violation_count: int
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class TeamDepthLayer:
    team_captain_id: str
    depth_level: int
    layer_code: str
    layer_title: str
    layer_payload: dict[str, object]


@dataclass(frozen=True)
class TeamOperatorCoachingCard:
    team_coaching_id: str
    team_owner: str
    assigned_lane: str
    operator_lane: str
    review_state: str
    console_bucket: str
    review_priority: str
    team_signal: str
    captain_tone: str
    operator_push: str
    system_discipline: str
    coaching_payload: dict[str, object]
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class TeamBuildResult:
    finding_count: int
    depth_layer_count: int
    operator_coaching_card_count: int
    input_contract_violation_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
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


def read_client_shadow_rows(db_path: Path) -> tuple[ClientShadowRow, ...]:
    with _connect_client_shadow(db_path) as conn:
        rows = conn.execute(
            """
            SELECT shadow_id, risk_level, action_type, human_specialist,
                   diagnosis_code, operator_coaching_mode, dominant_domain,
                   event_count, message_count, severity_high_count,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM shadow_drafts
            ORDER BY human_specialist, risk_level, action_type, shadow_id
            """
        ).fetchall()
    return tuple(
        ClientShadowRow(
            shadow_id=str(row["shadow_id"]),
            risk_level=str(row["risk_level"]),
            action_type=str(row["action_type"]),
            human_specialist=str(row["human_specialist"]),
            diagnosis_code=str(row["diagnosis_code"]),
            operator_coaching_mode=str(row["operator_coaching_mode"]),
            dominant_domain=str(row["dominant_domain"]),
            event_count=int(row["event_count"]),
            message_count=int(row["message_count"]),
            severity_high_count=int(row["severity_high_count"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def _connect_operator_review_console(db_path: Path) -> sqlite3.Connection:
    if db_path.name != EXPECTED_OPERATOR_REVIEW_CONSOLE_DB_NAME:
        raise ValueError(
            f"Refusing to read unexpected Operator Review Console DB: {db_path.name}"
        )
    if not db_path.exists():
        raise FileNotFoundError(f"Operator Review Console DB not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_operator_review_rows(db_path: Path) -> tuple[OperatorReviewConsoleRow, ...]:
    with _connect_operator_review_console(db_path) as conn:
        rows = conn.execute(
            """
            SELECT assigned_lane, operator_lane, review_state, console_bucket,
                   review_priority, send_whatsapp, crm_mutation,
                   requires_human_approval
            FROM operator_packet_review_items
            ORDER BY review_rank, assigned_lane, operator_lane, review_state
            """
        ).fetchall()
    return tuple(
        OperatorReviewConsoleRow(
            assigned_lane=str(row["assigned_lane"]),
            operator_lane=str(row["operator_lane"]),
            review_state=str(row["review_state"]),
            console_bucket=str(row["console_bucket"]),
            review_priority=str(row["review_priority"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def _most_common(values: Sequence[str], fallback: str = "unknown") -> str:
    if not values:
        return fallback
    return Counter(values).most_common(1)[0][0]


def _accountability_mode(rows: Sequence[ClientShadowRow]) -> str:
    p1_count = sum(1 for row in rows if row.risk_level == "P1")
    firm_count = sum(
        1 for row in rows if row.operator_coaching_mode == "firm_accountability_nudge"
    )
    if p1_count or firm_count:
        return "firm_family_accountability"
    if any(row.risk_level == "P2" for row in rows):
        return "steady_family_motivation"
    return "supportive_family_momentum"


def build_team_findings(rows: Sequence[ClientShadowRow]) -> tuple[TeamFinding, ...]:
    grouped: dict[str, list[ClientShadowRow]] = defaultdict(list)
    for row in rows:
        grouped[row.human_specialist].append(row)

    findings: list[TeamFinding] = []
    for specialist, specialist_rows in sorted(grouped.items()):
        p1_count = sum(1 for row in specialist_rows if row.risk_level == "P1")
        p2_count = sum(1 for row in specialist_rows if row.risk_level == "P2")
        findings.append(
            TeamFinding(
                team_captain_id=f"team-{specialist}",
                team_owner=TEAM_OWNER,
                human_specialist=specialist,
                draft_count=len(specialist_rows),
                p1_count=p1_count,
                p2_count=p2_count,
                primary_action_type=_most_common([row.action_type for row in specialist_rows]),
                primary_diagnosis_code=_most_common(
                    [row.diagnosis_code for row in specialist_rows]
                ),
                primary_coaching_mode=_most_common(
                    [row.operator_coaching_mode for row in specialist_rows]
                ),
                accountability_mode=_accountability_mode(specialist_rows),
                total_event_count=sum(row.event_count for row in specialist_rows),
                total_message_count=sum(row.message_count for row in specialist_rows),
                input_contract_violation_count=sum(
                    1
                    for row in specialist_rows
                    if row.send_whatsapp
                    or row.crm_mutation
                    or not row.requires_human_approval
                ),
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(findings)


def _coaching_classifier(row: OperatorReviewConsoleRow) -> tuple[str, str, str, str]:
    if row.send_whatsapp or row.crm_mutation or not row.requires_human_approval:
        return (
            "runtime_contract_violation",
            "firm_system_correction",
            "stop_and_restore_human_approval_gate",
            "no_send_no_crm_requires_human_approval",
        )
    if (
        row.review_state == "ready_for_human_review"
        and row.operator_lane != row.assigned_lane
    ):
        return (
            "routing_mismatch",
            "firm_system_correction",
            "reroute_to_assigned_lane_before_execution",
            "correct_lane_before_touching_client",
        )
    if row.review_state == "ready_for_human_review":
        return (
            "operator_action_required",
            "warm_family_push",
            "review_ready_packet_now",
            "use_review_console_before_any_send_or_crm",
        )
    if row.review_state == "waiting_owner_decision":
        return (
            "owner_decision_block",
            "protect_operator_focus",
            "do_not_execute_until_owner_decides",
            "respect_owner_gate_before_team_work",
        )
    if row.review_state == "deferred_owner_revisit":
        return (
            "owner_revisit_required",
            "steady_owner_followup",
            "support_owner_revisit_without_client_action",
            "hold_deferred_case_until_owner_revisits",
        )
    if row.review_state == "rejected_closed":
        return (
            "closed_no_action",
            "closure_discipline",
            "record_closure_and_do_not_reopen_without_owner",
            "do_not_execute_rejected_packet",
        )
    raise ValueError(f"Unsupported operator review state: {row.review_state}")


def _team_coaching_id(row: OperatorReviewConsoleRow, index: int) -> str:
    digest = hashlib.sha256(
        "|".join(
            [
                row.assigned_lane,
                row.operator_lane,
                row.review_state,
                row.console_bucket,
                row.review_priority,
                str(index),
            ]
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"team-coach-{index:04d}-{digest}"


def build_operator_coaching_cards(
    rows: Sequence[OperatorReviewConsoleRow],
) -> tuple[TeamOperatorCoachingCard, ...]:
    cards: list[TeamOperatorCoachingCard] = []
    for index, row in enumerate(rows, start=1):
        input_contract_violation = (
            row.send_whatsapp or row.crm_mutation or not row.requires_human_approval
        )
        team_signal, captain_tone, operator_push, system_discipline = _coaching_classifier(
            row
        )
        payload = {
            "assigned_lane": row.assigned_lane,
            "operator_lane": row.operator_lane,
            "review_state": row.review_state,
            "console_bucket": row.console_bucket,
            "team_signal": team_signal,
            "captain_tone": captain_tone,
            "operator_push": operator_push,
            "system_discipline": system_discipline,
            "input_contract_violation": input_contract_violation,
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        cards.append(
            TeamOperatorCoachingCard(
                team_coaching_id=_team_coaching_id(row, index),
                team_owner=TEAM_OWNER,
                assigned_lane=row.assigned_lane,
                operator_lane=row.operator_lane,
                review_state=row.review_state,
                console_bucket=row.console_bucket,
                review_priority=row.review_priority,
                team_signal=team_signal,
                captain_tone=captain_tone,
                operator_push=operator_push,
                system_discipline=system_discipline,
                coaching_payload=payload,
                send_whatsapp=False,
                crm_mutation=False,
                requires_human_approval=True,
            )
        )
    return tuple(cards)


def build_team_depth_layers(findings: Sequence[TeamFinding]) -> tuple[TeamDepthLayer, ...]:
    layers: list[TeamDepthLayer] = []
    for finding in findings:
        base_payload = {
            "team_owner": finding.team_owner,
            "human_specialist": finding.human_specialist,
            "raw_text_included": False,
            "send_whatsapp": False,
            "crm_mutation": False,
            "requires_human_approval": True,
        }
        layer_specs = [
            (
                1,
                "lane_workload",
                "Lane workload",
                {"draft_count": finding.draft_count, "total_message_count": finding.total_message_count},
            ),
            (
                2,
                "risk_pressure",
                "Risk pressure",
                {"p1_count": finding.p1_count, "p2_count": finding.p2_count},
            ),
            (
                3,
                "behavior_pattern",
                "Behavior pattern",
                {
                    "primary_action_type": finding.primary_action_type,
                    "primary_diagnosis_code": finding.primary_diagnosis_code,
                },
            ),
            (
                4,
                "motivation_plan",
                "Motivation plan",
                {"primary_coaching_mode": finding.primary_coaching_mode},
            ),
            (
                5,
                "accountability_nudge",
                "Accountability nudge",
                {"accountability_mode": finding.accountability_mode},
            ),
            (
                6,
                "team_escalation_gate",
                "Team escalation gate",
                {"escalate_to_owner": finding.p1_count > 0},
            ),
        ]
        for depth_level, code, title, payload in layer_specs:
            layers.append(
                TeamDepthLayer(
                    team_captain_id=finding.team_captain_id,
                    depth_level=depth_level,
                    layer_code=code,
                    layer_title=title,
                    layer_payload={**base_payload, **payload},
                )
            )
    return tuple(layers)


def write_team_sqlite(
    path: Path,
    findings: Sequence[TeamFinding],
    layers: Sequence[TeamDepthLayer],
    operator_coaching_cards: Sequence[TeamOperatorCoachingCard],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE team_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                finding_count INTEGER NOT NULL,
                depth_layer_count INTEGER NOT NULL,
                operator_coaching_card_count INTEGER NOT NULL,
                input_contract_violation_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL
            );

            CREATE TABLE team_captain_findings (
                team_captain_id TEXT PRIMARY KEY,
                team_owner TEXT NOT NULL,
                human_specialist TEXT NOT NULL,
                draft_count INTEGER NOT NULL,
                p1_count INTEGER NOT NULL,
                p2_count INTEGER NOT NULL,
                primary_action_type TEXT NOT NULL,
                primary_diagnosis_code TEXT NOT NULL,
                primary_coaching_mode TEXT NOT NULL,
                accountability_mode TEXT NOT NULL,
                total_event_count INTEGER NOT NULL,
                total_message_count INTEGER NOT NULL,
                input_contract_violation_count INTEGER NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE TABLE team_captain_depth_layers (
                team_captain_id TEXT NOT NULL,
                depth_level INTEGER NOT NULL,
                layer_code TEXT NOT NULL,
                layer_title TEXT NOT NULL,
                layer_payload_json TEXT NOT NULL,
                PRIMARY KEY (team_captain_id, depth_level)
            );

            CREATE TABLE team_operator_coaching_cards (
                team_coaching_id TEXT PRIMARY KEY,
                team_owner TEXT NOT NULL,
                assigned_lane TEXT NOT NULL,
                operator_lane TEXT NOT NULL,
                review_state TEXT NOT NULL,
                console_bucket TEXT NOT NULL,
                review_priority TEXT NOT NULL,
                team_signal TEXT NOT NULL,
                captain_tone TEXT NOT NULL,
                operator_push TEXT NOT NULL,
                system_discipline TEXT NOT NULL,
                coaching_payload_json TEXT NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO team_runs (
                id, generated_at_utc, privacy_mode, finding_count, depth_layer_count,
                operator_coaching_card_count, input_contract_violation_count,
                send_whatsapp_count, crm_mutation_count
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "local_only_team_shadow_no_send_no_crm_mutation",
                len(findings),
                len(layers),
                len(operator_coaching_cards),
                _input_contract_violation_count(findings, operator_coaching_cards),
            ),
        )
        conn.executemany(
            """
            INSERT INTO team_captain_findings (
                team_captain_id, team_owner, human_specialist, draft_count,
                p1_count, p2_count, primary_action_type, primary_diagnosis_code,
                primary_coaching_mode, accountability_mode, total_event_count,
                total_message_count, input_contract_violation_count,
                send_whatsapp, crm_mutation, requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    finding.team_captain_id,
                    finding.team_owner,
                    finding.human_specialist,
                    finding.draft_count,
                    finding.p1_count,
                    finding.p2_count,
                    finding.primary_action_type,
                    finding.primary_diagnosis_code,
                    finding.primary_coaching_mode,
                    finding.accountability_mode,
                    finding.total_event_count,
                    finding.total_message_count,
                    finding.input_contract_violation_count,
                    int(finding.send_whatsapp),
                    int(finding.crm_mutation),
                    int(finding.requires_human_approval),
                )
                for finding in findings
            ],
        )
        conn.executemany(
            """
            INSERT INTO team_captain_depth_layers (
                team_captain_id, depth_level, layer_code, layer_title, layer_payload_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    layer.team_captain_id,
                    layer.depth_level,
                    layer.layer_code,
                    layer.layer_title,
                    json.dumps(layer.layer_payload, ensure_ascii=False, sort_keys=True),
                )
                for layer in layers
            ],
        )
        conn.executemany(
            """
            INSERT INTO team_operator_coaching_cards (
                team_coaching_id, team_owner, assigned_lane, operator_lane,
                review_state, console_bucket, review_priority, team_signal,
                captain_tone, operator_push, system_discipline,
                coaching_payload_json, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    card.team_coaching_id,
                    card.team_owner,
                    card.assigned_lane,
                    card.operator_lane,
                    card.review_state,
                    card.console_bucket,
                    card.review_priority,
                    card.team_signal,
                    card.captain_tone,
                    card.operator_push,
                    card.system_discipline,
                    json.dumps(card.coaching_payload, ensure_ascii=False, sort_keys=True),
                    int(card.send_whatsapp),
                    int(card.crm_mutation),
                    int(card.requires_human_approval),
                )
                for card in operator_coaching_cards
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


def _input_contract_violation_count(
    findings: Sequence[TeamFinding],
    operator_coaching_cards: Sequence[TeamOperatorCoachingCard],
) -> int:
    return sum(finding.input_contract_violation_count for finding in findings) + sum(
        1
        for card in operator_coaching_cards
        if bool(card.coaching_payload.get("input_contract_violation"))
    )


def write_summary(
    *,
    summary_path: Path,
    findings: Sequence[TeamFinding],
    layers: Sequence[TeamDepthLayer],
    operator_coaching_cards: Sequence[TeamOperatorCoachingCard],
    generated_at_utc: str | None = None,
) -> None:
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    specialist_counts = Counter(finding.human_specialist for finding in findings)
    action_counts = Counter(finding.primary_action_type for finding in findings)
    accountability_counts = Counter(finding.accountability_mode for finding in findings)
    team_signal_counts = Counter(card.team_signal for card in operator_coaching_cards)
    captain_tone_counts = Counter(card.captain_tone for card in operator_coaching_cards)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Team Captain Shadow Summary",
        "",
        f"Generated UTC: `{generated}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, file IDs, window IDs, or replay IDs.",
        "- Team Shadow output is local-only and ignored under `research/personal/wa-corpus/`.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Team findings | {len(findings)} |",
        f"| Depth layers | {len(layers)} |",
        f"| Operator coaching cards | {len(operator_coaching_cards)} |",
        (
            "| Input contract violations | "
            f"{_input_contract_violation_count(findings, operator_coaching_cards)} |"
        ),
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        *_counter_table("Specialist Lanes", specialist_counts),
        "",
        *_counter_table("Primary Action Types", action_counts),
        "",
        *_counter_table("Accountability Modes", accountability_counts),
        "",
        *_counter_table("Team Signals", team_signal_counts),
        "",
        *_counter_table("Captain Tones", captain_tone_counts),
        "",
        "## Execution Contract",
        "",
        "- The Team Captain motivates, coaches, and flags accountability only.",
        "- The Team Captain can firmly correct wrong system usage or lane mismatch.",
        "- It cannot send WhatsApp messages.",
        "- It cannot mutate CRM records.",
        "- Owner escalation is advisory until a human approves it.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_team_captain_shadow(
    *,
    client_shadow_db: Path = DEFAULT_CLIENT_SHADOW_DB,
    operator_review_console_db: Path | None = None,
    output_dir: Path = DEFAULT_TEAM_SHADOW_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
) -> TeamBuildResult:
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    client_rows = read_client_shadow_rows(client_shadow_db)
    findings = build_team_findings(client_rows)
    layers = build_team_depth_layers(findings)
    operator_rows = (
        read_operator_review_rows(operator_review_console_db)
        if operator_review_console_db is not None
        else ()
    )
    operator_coaching_cards = build_operator_coaching_cards(operator_rows)
    write_team_sqlite(output_db, findings, layers, operator_coaching_cards)
    write_summary(
        summary_path=summary_path,
        findings=findings,
        layers=layers,
        operator_coaching_cards=operator_coaching_cards,
    )
    return TeamBuildResult(
        finding_count=len(findings),
        depth_layer_count=len(layers),
        operator_coaching_card_count=len(operator_coaching_cards),
        input_contract_violation_count=_input_contract_violation_count(
            findings, operator_coaching_cards
        ),
        send_whatsapp_count=sum(1 for finding in findings if finding.send_whatsapp),
        crm_mutation_count=sum(1 for finding in findings if finding.crm_mutation),
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara Team Captain Shadow Mode findings."
    )
    parser.add_argument("--client-shadow-db", type=Path, default=DEFAULT_CLIENT_SHADOW_DB)
    parser.add_argument("--operator-review-console-db", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_TEAM_SHADOW_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_team_captain_shadow(
            client_shadow_db=args.client_shadow_db,
            operator_review_console_db=args.operator_review_console_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
        )
    except (FileNotFoundError, ValueError, TypeError):
        # Keep this fixed literal: exception text may include local paths or DB names.
        print("ERROR: Team Captain input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        # Keep this fixed literal: exception text may include local paths or DB names.
        print("ERROR: Team Captain shadow run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        # CLI boundary must fail closed; the Python API still exposes details.
        print("ERROR: Team Captain shadow run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "finding_count": result.finding_count,
                    "depth_layer_count": result.depth_layer_count,
                    "operator_coaching_card_count": result.operator_coaching_card_count,
                    "input_contract_violation_count": (
                        result.input_contract_violation_count
                    ),
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "crm_mutation_count": result.crm_mutation_count,
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
