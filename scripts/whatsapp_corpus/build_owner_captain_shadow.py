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
DEFAULT_TEAM_SHADOW_DIR = Path("research/personal/wa-corpus/team-captain-shadow")
DEFAULT_OWNER_SHADOW_DIR = Path("research/personal/wa-corpus/owner-captain-shadow")
DEFAULT_CLIENT_SHADOW_DB = DEFAULT_CLIENT_SHADOW_DIR / "client_captain_shadow.local.sqlite"
DEFAULT_TEAM_SHADOW_DB = DEFAULT_TEAM_SHADOW_DIR / "team_captain_shadow.local.sqlite"
DEFAULT_OUTPUT_DB = DEFAULT_OWNER_SHADOW_DIR / "owner_captain_shadow.local.sqlite"
DEFAULT_SUMMARY = DEFAULT_OWNER_SHADOW_DIR / "owner_captain_shadow_summary.md"

EXPECTED_CLIENT_SHADOW_DB_NAME = "client_captain_shadow.local.sqlite"
EXPECTED_TEAM_SHADOW_DB_NAME = "team_captain_shadow.local.sqlite"
OWNER_SCOPE = "global_case_ops"


@dataclass(frozen=True)
class ClientAggregate:
    draft_count: int
    p1_count: int
    p2_count: int
    action_counts: Counter[str]
    specialist_counts: Counter[str]
    send_whatsapp_count: int
    crm_mutation_count: int
    approval_count: int
    input_contract_violation_count: int


@dataclass(frozen=True)
class TeamAggregateRow:
    human_specialist: str
    draft_count: int
    p1_count: int
    p2_count: int
    primary_action_type: str
    accountability_mode: str
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OwnerFinding:
    owner_captain_id: str
    owner_scope: str
    draft_count: int
    team_lane_count: int
    p1_count: int
    p2_count: int
    primary_bottleneck_lane: str
    primary_action_type: str
    owner_decision_mode: str
    input_contract_violation_count: int
    send_whatsapp: bool
    crm_mutation: bool
    requires_human_approval: bool


@dataclass(frozen=True)
class OwnerDepthLayer:
    owner_captain_id: str
    depth_level: int
    layer_code: str
    layer_title: str
    layer_payload: dict[str, object]


@dataclass(frozen=True)
class OwnerBuildResult:
    finding_count: int
    depth_layer_count: int
    send_whatsapp_count: int
    crm_mutation_count: int
    input_contract_violation_count: int
    output_db: Path
    summary_path: Path


def _connect_expected(db_path: Path, *, expected_name: str, label: str) -> sqlite3.Connection:
    if db_path.name != expected_name:
        raise ValueError(f"Refusing to read unexpected {label}: {db_path.name}")
    if not db_path.exists():
        raise FileNotFoundError(f"{label} not found: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_client_aggregate(db_path: Path) -> ClientAggregate:
    with _connect_expected(
        db_path,
        expected_name=EXPECTED_CLIENT_SHADOW_DB_NAME,
        label="Client Shadow DB",
    ) as conn:
        rows = conn.execute(
            """
            SELECT risk_level, action_type, human_specialist,
                   send_whatsapp, crm_mutation, requires_human_approval
            FROM shadow_drafts
            """
        ).fetchall()
    action_counts = Counter(str(row["action_type"]) for row in rows)
    specialist_counts = Counter(str(row["human_specialist"]) for row in rows)
    return ClientAggregate(
        draft_count=len(rows),
        p1_count=sum(1 for row in rows if str(row["risk_level"]) == "P1"),
        p2_count=sum(1 for row in rows if str(row["risk_level"]) == "P2"),
        action_counts=action_counts,
        specialist_counts=specialist_counts,
        send_whatsapp_count=sum(int(row["send_whatsapp"]) for row in rows),
        crm_mutation_count=sum(int(row["crm_mutation"]) for row in rows),
        approval_count=sum(int(row["requires_human_approval"]) for row in rows),
        input_contract_violation_count=sum(
            1
            for row in rows
            if bool(row["send_whatsapp"])
            or bool(row["crm_mutation"])
            or not bool(row["requires_human_approval"])
        ),
    )


def read_team_rows(db_path: Path) -> tuple[TeamAggregateRow, ...]:
    with _connect_expected(
        db_path,
        expected_name=EXPECTED_TEAM_SHADOW_DB_NAME,
        label="Team Shadow DB",
    ) as conn:
        rows = conn.execute(
            """
            SELECT human_specialist, draft_count, p1_count, p2_count,
                   primary_action_type, accountability_mode, send_whatsapp,
                   crm_mutation, requires_human_approval
            FROM team_captain_findings
            ORDER BY p1_count DESC, draft_count DESC, human_specialist
            """
        ).fetchall()
    return tuple(
        TeamAggregateRow(
            human_specialist=str(row["human_specialist"]),
            draft_count=int(row["draft_count"]),
            p1_count=int(row["p1_count"]),
            p2_count=int(row["p2_count"]),
            primary_action_type=str(row["primary_action_type"]),
            accountability_mode=str(row["accountability_mode"]),
            send_whatsapp=bool(row["send_whatsapp"]),
            crm_mutation=bool(row["crm_mutation"]),
            requires_human_approval=bool(row["requires_human_approval"]),
        )
        for row in rows
    )


def _most_common(counter: Counter[str], fallback: str = "unknown") -> str:
    if not counter:
        return fallback
    return counter.most_common(1)[0][0]


def build_owner_finding(
    client: ClientAggregate,
    team_rows: Sequence[TeamAggregateRow],
) -> OwnerFinding:
    bottleneck = team_rows[0].human_specialist if team_rows else "none"
    team_contract_violation_count = sum(
        1
        for row in team_rows
        if row.send_whatsapp or row.crm_mutation or not row.requires_human_approval
    )
    input_contract_violation_count = (
        client.input_contract_violation_count + team_contract_violation_count
    )
    p1_count = max(client.p1_count, sum(row.p1_count for row in team_rows))
    p2_count = max(client.p2_count, sum(row.p2_count for row in team_rows))
    return OwnerFinding(
        owner_captain_id="owner-global-case-ops",
        owner_scope=OWNER_SCOPE,
        draft_count=client.draft_count,
        team_lane_count=len(team_rows),
        p1_count=p1_count,
        p2_count=p2_count,
        primary_bottleneck_lane=bottleneck,
        primary_action_type=_most_common(client.action_counts),
        owner_decision_mode=(
            "owner_review_required"
            if p1_count or input_contract_violation_count
            else "monitor"
        ),
        input_contract_violation_count=input_contract_violation_count,
        send_whatsapp=False,
        crm_mutation=False,
        requires_human_approval=True,
    )


def build_owner_depth_layers(finding: OwnerFinding) -> tuple[OwnerDepthLayer, ...]:
    base_payload = {
        "owner_scope": finding.owner_scope,
        "send_whatsapp": False,
        "crm_mutation": False,
        "requires_human_approval": True,
        "raw_text_included": False,
    }
    layer_specs = [
        (
            1,
            "operational_volume",
            "Operational volume",
            {"draft_count": finding.draft_count, "team_lane_count": finding.team_lane_count},
        ),
        (
            2,
            "risk_concentration",
            "Risk concentration",
            {"p1_count": finding.p1_count, "p2_count": finding.p2_count},
        ),
        (
            3,
            "team_bottleneck",
            "Team bottleneck",
            {"primary_bottleneck_lane": finding.primary_bottleneck_lane},
        ),
        (
            4,
            "client_experience_risk",
            "Client experience risk",
            {"primary_action_type": finding.primary_action_type},
        ),
        (
            5,
            "automation_leverage",
            "Automation leverage",
            {"candidate_loop": "shadow_to_review_queue"},
        ),
        (
            6,
            "governance_boundary",
            "Governance boundary",
            {
                "runtime_contract": "no_send_no_crm_mutation_without_human_approval",
                "input_contract_violation_count": finding.input_contract_violation_count,
            },
        ),
        (
            7,
            "owner_decision",
            "Owner decision",
            {"owner_decision_mode": finding.owner_decision_mode},
        ),
    ]
    return tuple(
        OwnerDepthLayer(
            owner_captain_id=finding.owner_captain_id,
            depth_level=depth_level,
            layer_code=code,
            layer_title=title,
            layer_payload={**base_payload, **payload},
        )
        for depth_level, code, title, payload in layer_specs
    )


def write_owner_sqlite(
    path: Path,
    finding: OwnerFinding,
    layers: Sequence[OwnerDepthLayer],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE owner_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at_utc TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                finding_count INTEGER NOT NULL,
                depth_layer_count INTEGER NOT NULL,
                send_whatsapp_count INTEGER NOT NULL,
                crm_mutation_count INTEGER NOT NULL,
                input_contract_violation_count INTEGER NOT NULL
            );

            CREATE TABLE owner_captain_findings (
                owner_captain_id TEXT PRIMARY KEY,
                owner_scope TEXT NOT NULL,
                draft_count INTEGER NOT NULL,
                team_lane_count INTEGER NOT NULL,
                p1_count INTEGER NOT NULL,
                p2_count INTEGER NOT NULL,
                primary_bottleneck_lane TEXT NOT NULL,
                primary_action_type TEXT NOT NULL,
                owner_decision_mode TEXT NOT NULL,
                input_contract_violation_count INTEGER NOT NULL,
                send_whatsapp INTEGER NOT NULL CHECK (send_whatsapp = 0),
                crm_mutation INTEGER NOT NULL CHECK (crm_mutation = 0),
                requires_human_approval INTEGER NOT NULL CHECK (requires_human_approval = 1)
            );

            CREATE TABLE owner_captain_depth_layers (
                owner_captain_id TEXT NOT NULL,
                depth_level INTEGER NOT NULL,
                layer_code TEXT NOT NULL,
                layer_title TEXT NOT NULL,
                layer_payload_json TEXT NOT NULL,
                PRIMARY KEY (owner_captain_id, depth_level)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO owner_runs (
                id, generated_at_utc, privacy_mode, finding_count, depth_layer_count,
                send_whatsapp_count, crm_mutation_count, input_contract_violation_count
            )
            VALUES (1, ?, ?, 1, ?, 0, 0, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "local_only_owner_shadow_no_send_no_crm_mutation",
                len(layers),
                finding.input_contract_violation_count,
            ),
        )
        conn.execute(
            """
            INSERT INTO owner_captain_findings (
                owner_captain_id, owner_scope, draft_count, team_lane_count,
                p1_count, p2_count, primary_bottleneck_lane, primary_action_type,
                owner_decision_mode, input_contract_violation_count, send_whatsapp, crm_mutation,
                requires_human_approval
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                finding.owner_captain_id,
                finding.owner_scope,
                finding.draft_count,
                finding.team_lane_count,
                finding.p1_count,
                finding.p2_count,
                finding.primary_bottleneck_lane,
                finding.primary_action_type,
                finding.owner_decision_mode,
                finding.input_contract_violation_count,
                int(finding.send_whatsapp),
                int(finding.crm_mutation),
                int(finding.requires_human_approval),
            ),
        )
        conn.executemany(
            """
            INSERT INTO owner_captain_depth_layers (
                owner_captain_id, depth_level, layer_code, layer_title, layer_payload_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    layer.owner_captain_id,
                    layer.depth_level,
                    layer.layer_code,
                    layer.layer_title,
                    json.dumps(layer.layer_payload, ensure_ascii=False, sort_keys=True),
                )
                for layer in layers
            ],
        )
        conn.commit()


def write_summary(
    *,
    summary_path: Path,
    finding: OwnerFinding,
    layers: Sequence[OwnerDepthLayer],
    generated_at_utc: str | None = None,
) -> None:
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Zantara Owner Captain Shadow Summary",
        "",
        f"Generated UTC: `{generated}`",
        "",
        "## Privacy Mode",
        "",
        "- This summary contains no raw message text.",
        "- This summary contains no message snippets.",
        "- This summary contains no phone numbers, emails, raw paths, file IDs, window IDs, replay IDs, or shadow IDs.",
        "- Owner Shadow output is local-only and ignored by git.",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
        "| Owner findings | 1 |",
        f"| Depth layers | {len(layers)} |",
        f"| Shadow drafts reviewed | {finding.draft_count} |",
        f"| Team lanes reviewed | {finding.team_lane_count} |",
        f"| P1 count | {finding.p1_count} |",
        f"| P2 count | {finding.p2_count} |",
        f"| Input contract violations | {finding.input_contract_violation_count} |",
        "| WhatsApp sends | 0 |",
        "| CRM mutations | 0 |",
        "| Human approval required | 100% |",
        "",
        "## Execution Contract",
        "",
        "- The Owner Captain summarizes business risk and governance gates only.",
        "- It reports upstream contract violations only as aggregate counts.",
        "- It cannot send WhatsApp messages.",
        "- It cannot mutate CRM records.",
        "- It can recommend owner review, but the owner remains the approving human.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_owner_captain_shadow(
    *,
    client_shadow_db: Path = DEFAULT_CLIENT_SHADOW_DB,
    team_shadow_db: Path = DEFAULT_TEAM_SHADOW_DB,
    output_dir: Path = DEFAULT_OWNER_SHADOW_DIR,
    output_db: Path | None = None,
    summary_path: Path = DEFAULT_SUMMARY,
) -> OwnerBuildResult:
    output_db = output_db or output_dir / DEFAULT_OUTPUT_DB.name
    client = read_client_aggregate(client_shadow_db)
    team_rows = read_team_rows(team_shadow_db)
    finding = build_owner_finding(client, team_rows)
    layers = build_owner_depth_layers(finding)
    write_owner_sqlite(output_db, finding, layers)
    write_summary(summary_path=summary_path, finding=finding, layers=layers)
    return OwnerBuildResult(
        finding_count=1,
        depth_layer_count=len(layers),
        send_whatsapp_count=int(finding.send_whatsapp),
        crm_mutation_count=int(finding.crm_mutation),
        input_contract_violation_count=finding.input_contract_violation_count,
        output_db=output_db,
        summary_path=summary_path,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-only Zantara Owner Captain Shadow Mode findings."
    )
    parser.add_argument("--client-shadow-db", type=Path, default=DEFAULT_CLIENT_SHADOW_DB)
    parser.add_argument("--team-shadow-db", type=Path, default=DEFAULT_TEAM_SHADOW_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OWNER_SHADOW_DIR)
    parser.add_argument("--output-db", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_owner_captain_shadow(
            client_shadow_db=args.client_shadow_db,
            team_shadow_db=args.team_shadow_db,
            output_dir=args.output_dir,
            output_db=args.output_db,
            summary_path=args.summary,
        )
    except (FileNotFoundError, ValueError, TypeError):
        # Keep this fixed literal: exception text may include local paths or DB names.
        print("ERROR: Owner Captain input is missing or invalid.", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError):
        # Keep this fixed literal: exception text may include local paths or DB names.
        print("ERROR: Owner Captain shadow run failed safely.", file=sys.stderr)
        return 1
    except Exception:
        # CLI boundary must fail closed; the Python API still exposes details.
        print("ERROR: Owner Captain shadow run failed safely.", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "finding_count": result.finding_count,
                    "depth_layer_count": result.depth_layer_count,
                    "send_whatsapp_count": result.send_whatsapp_count,
                    "crm_mutation_count": result.crm_mutation_count,
                    "input_contract_violation_count": result.input_contract_violation_count,
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
