#!/usr/bin/env python3
"""WR3 telemetry — JSONL emit helper (Symbiosis Law 7 Numeri prima).

One JSONL line per agent dispatch under ~/.cell-observatory/wr3/<agent>.jsonl.
Mandatory `room: wr3` namespace to share cell_pulse_observed with WR2/mata-garuda.

Schema per line:
  ts                ISO-8601 UTC
  room              "wr3"
  agent             "wr3-<slug>"
  episode_id        string slug
  duration_ms       int
  cost_usd          float or null
  outcome           "PASS" | "FAIL" | "DEGRADED"
  retry_count       int
  critic_lane       int (1..4) or null
  contract_version  semver from <agent>.yaml
  error             optional, only on outcome=FAIL
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TELEMETRY_ROOT = Path(os.environ.get("WR3_TELEMETRY_ROOT", str(Path.home() / ".cell-observatory" / "wr3")))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(
    agent: str,
    episode_id: str,
    *,
    outcome: str,
    duration_ms: int | None = None,
    cost_usd: float | None = None,
    retry_count: int = 0,
    critic_lane: int | None = None,
    contract_version: str | None = None,
    error: str | None = None,
    **extra: Any,
) -> Path:
    if outcome not in {"PASS", "FAIL", "DEGRADED"}:
        raise ValueError(f"outcome must be PASS|FAIL|DEGRADED, got {outcome!r}")
    if not agent.startswith("wr3-"):
        raise ValueError(f"agent must be 'wr3-<slug>', got {agent!r}")

    line: dict[str, Any] = {
        "ts": _utcnow(),
        "room": "wr3",
        "agent": agent,
        "episode_id": episode_id,
        "duration_ms": duration_ms,
        "cost_usd": cost_usd,
        "outcome": outcome,
        "retry_count": retry_count,
        "critic_lane": critic_lane,
        "contract_version": contract_version,
    }
    if error is not None:
        line["error"] = error[:500]
    line.update(extra)

    path = TELEMETRY_ROOT / f"{agent}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return path


if __name__ == "__main__":
    p = emit(
        agent="wr3-brief-interpreter",
        episode_id="smoke-test-manifesto",
        outcome="PASS",
        duration_ms=8421,
        cost_usd=0.12,
        contract_version="1.0.0",
    )
    print(f"emitted to {p}")
