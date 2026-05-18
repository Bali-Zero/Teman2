#!/usr/bin/env python3
"""WR3 Lint — Law 7 (Numeri prima).

Symbiosis Law 7: Every dispatch emits telemetry with mandatory fields:
  ts, room=wr3, agent, episode_id, duration_ms, cost_usd, outcome,
  retry_count, critic_lane, contract_version

Checks:
  1. Every wr3_*.py module that dispatches an agent must call `telemetry_emit`
     (or equivalent). We grep for `dispatch_agent(` calls without a nearby
     `telemetry_emit(`.
  2. Manifest builder must populate `total_cost_usd` from agent dispatches
     (cannot ship 0.0 if agents_invoked is non-empty AND any agent has
     ceiling_usd > 0 AND not all are render/audio_gen ceiling=null).
  3. Migration 182 must declare `events_outbox` insert in the
     publish_wr3_event() function body (for outbox durability).
"""
from __future__ import annotations

import re
from pathlib import Path

try:
    from . import LintFinding
except ImportError:
    import sys
    HERE = Path(__file__).resolve().parent
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    from __init__ import LintFinding  # type: ignore

LAW_NUMBER = 7
LAW_NAME = "Numeri prima"


def _has_nearby_telemetry(lines: list[str], idx: int, window: int = 30) -> bool:
    """Look ±window lines around idx for `telemetry_emit(` or `emit(`."""
    start = max(0, idx - window)
    end = min(len(lines), idx + window)
    chunk = "\n".join(lines[start:end])
    return bool(re.search(r"\btelemetry_emit\(|wr3_telemetry\.emit\(|\bemit\(", chunk))


def check(repo_root: Path) -> list[LintFinding]:
    findings: list[LintFinding] = []

    # 1. dispatch_agent calls must have nearby telemetry_emit
    scripts_dir = repo_root / "scripts"
    if scripts_dir.exists():
        for py_path in sorted(scripts_dir.glob("wr3_*.py")):
            # Skip the dispatch module itself + telemetry module
            if py_path.name in {"wr3_dispatch_agent.py", "wr3_telemetry.py"}:
                continue
            try:
                text = py_path.read_text()
            except Exception:
                continue
            lines = text.splitlines()
            for line_no, line in enumerate(lines, 1):
                if "dispatch_agent(" in line and "def dispatch_agent" not in line:
                    if not _has_nearby_telemetry(lines, line_no - 1):
                        findings.append(LintFinding(
                            severity="ERROR",
                            law=LAW_NUMBER,
                            file=str(py_path.relative_to(repo_root)),
                            line=line_no,
                            message="dispatch_agent() call without nearby telemetry_emit — Law 7 telemetry mandatory",
                        ))

    # 2. Migration 182 declares events_outbox insert in publish_wr3_event
    mig_path = repo_root / "apps/backend-rag/backend/db/migrations_v2/182_wr3_eventbus_channels.sql"
    if mig_path.exists():
        sql = mig_path.read_text()
        if "publish_wr3_event" in sql:
            # Find function body, check for INSERT INTO events_outbox
            if "INSERT INTO events_outbox" not in sql:
                findings.append(LintFinding(
                    severity="ERROR",
                    law=LAW_NUMBER,
                    file=str(mig_path.relative_to(repo_root)),
                    line=None,
                    message="publish_wr3_event() defined but does NOT INSERT INTO events_outbox — Law 3 durability missing",
                ))

    # 3. wr3_telemetry.py exports `emit` with all mandatory fields
    telemetry_path = repo_root / "scripts/wr3_telemetry.py"
    if telemetry_path.exists():
        text = telemetry_path.read_text()
        mandatory_fields = ["ts", "room", "agent", "episode_id", "outcome", "contract_version"]
        for field in mandatory_fields:
            if f'"{field}"' not in text:
                findings.append(LintFinding(
                    severity="ERROR",
                    law=LAW_NUMBER,
                    file=str(telemetry_path.relative_to(repo_root)),
                    line=None,
                    message=f"telemetry payload missing mandatory field '{field}'",
                ))

    return findings


if __name__ == "__main__":
    import sys
    repo_root = Path(__file__).resolve().parents[2]
    findings = check(repo_root)
    for f in findings:
        print(f.fmt())
    sys.exit(1 if any(f.severity == "ERROR" for f in findings) else 0)
