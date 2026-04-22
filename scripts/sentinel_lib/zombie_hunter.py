"""Zombie-hunter — historical exit-code accumulator.

Audit 2026-04-19 blind-spot #3
==============================

The old zombie criterion was "running AND cpu ≈ 0 AND old" — it caught stuck
processes but missed crash-looping LaunchAgents (they WERE running, just dying
every cycle). This module fixes that by keeping a rolling window of the last
N exit codes per agent label and flagging any label whose last 3 consecutive
exits are non-zero, regardless of its current running state.

State lives in `~/.agent/decisions/state/launchd_bad_exits.json`. The existing
shell-side zombie-hunter already writes this file every 60s for its own
"bad-exit snapshot"; this module adds the `history` sub-tree + the consumer
logic. Both producers share the same file so a single SSoT is preserved.

File schema (forward-compatible — old fields untouched)::

    {
      "ts": "2026-04-20 11:22:33",
      "bad": [ {"label": "com.example.foo", "last_exit": 75}, ... ],
      "history": {
        "com.example.foo": [
          {"ts": "...", "exit_code": 75},
          {"ts": "...", "exit_code": 75}
        ],
        ...
      }
    }
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

STATE_FILE: Path = (
    Path.home() / ".agent" / "decisions" / "state" / "launchd_bad_exits.json"
)

HISTORY_WINDOW: int = 10
CONSECUTIVE_BAD_THRESHOLD: int = 3


@dataclass
class ZombieFinding:
    label: str
    reason: str
    consecutive_bad_exits: int
    last_exit_code: int
    currently_running: bool = False


def _load() -> dict:
    """Load the state file. Missing file -> fresh dict (never raises)."""
    try:
        return json.loads(STATE_FILE.read_text())
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        # Corrupt state file is treated as empty — the alternative is to crash
        # the whole self-repair pipeline on a single bad write, which defeats
        # the point of having a watchdog.
        return {}


def _save(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(STATE_FILE.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(STATE_FILE)


def record_run(label: str, exit_code: int, ts: str | None = None) -> None:
    """Append a run to the rolling history window for `label`.

    Safe to call concurrently with the shell-side zombie-hunter: we only
    modify the `history` sub-tree, leaving `ts` / `bad` alone.
    """
    data = _load()
    history = data.setdefault("history", {})
    entries: list[dict] = history.setdefault(label, [])
    entries.append({
        "ts": ts or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "exit_code": int(exit_code),
    })
    # Keep only the last HISTORY_WINDOW entries.
    if len(entries) > HISTORY_WINDOW:
        history[label] = entries[-HISTORY_WINDOW:]
    _save(data)


def _trailing_bad_streak(entries: Iterable[dict]) -> int:
    """Count consecutive non-zero exit codes at the *tail* of the list."""
    streak = 0
    for entry in reversed(list(entries)):
        if int(entry.get("exit_code", 0)) != 0:
            streak += 1
        else:
            break
    return streak


def identify_zombies(
    agent_state: dict[str, dict],
) -> dict[str, dict]:
    """Relaxed zombie criterion for direct agent-state dicts (W0.2 blind-spot).

    Accepts a dict mapping agent_name -> state dict with keys:
      - ``consecutive_exit1``: int — number of consecutive last_exit=1 cycles
      - ``last_pid``: int | None
      - ``label``: str (launchd label, optional)

    An agent is zombie when ``consecutive_exit1 >= CONSECUTIVE_BAD_THRESHOLD``
    (default 3). Returns a sub-dict of zombies {agent_name: state_dict}.

    Emits a ``zombie_detected`` event per zombie via organism.emit.emit_event
    (CRITICAL severity). The emit is fire-and-forget via asyncio.run(); if the
    organism bus is unavailable the detection still returns normally.
    """
    zombies: dict[str, dict] = {}
    for agent_name, state in agent_state.items():
        consecutive = int(state.get("consecutive_exit1", 0))
        if consecutive >= CONSECUTIVE_BAD_THRESHOLD:
            zombies[agent_name] = state

    if zombies:
        async def _emit_all() -> None:
            import sys as _sys
            from pathlib import Path as _Path
            _org = str(_Path(__file__).parents[2] / "apps" / "organism")
            if _org not in _sys.path:
                _sys.path.insert(0, _org)
            from organism.emit import emit_event
            from organism.schemas import Severity
            for agent_name, state in zombies.items():
                await emit_event(
                    severity=Severity.CRITICAL,
                    source="guardian.zombie_hunter",
                    kind="zombie_detected",
                    payload={
                        "agent": agent_name,
                        "consecutive_exit1": int(state.get("consecutive_exit1", 0)),
                        "last_pid": state.get("last_pid"),
                    },
                )

        try:
            asyncio.get_running_loop()
            # Already inside an event loop (pytest-asyncio, async caller) — schedule fire-and-forget
            asyncio.ensure_future(_emit_all())
        except RuntimeError:
            # No running loop (sync cron context) — run to completion
            try:
                asyncio.run(_emit_all())
            except Exception:
                pass  # organism bus unavailable — detection result still returned

    return zombies


def detect_zombies(
    current_state: dict[str, str] | None = None,
) -> list[ZombieFinding]:
    """Return every label whose trailing bad-exit streak >= threshold.

    `current_state` maps label -> state string ("running", "stopped", ...).
    When provided, the matching `ZombieFinding.currently_running` flag is set
    so system_doctor can distinguish "crash-loop" (currently running) from
    "dead for good" (stopped).
    """
    data = _load()
    history = data.get("history", {})
    findings: list[ZombieFinding] = []

    for label, entries in history.items():
        streak = _trailing_bad_streak(entries)
        if streak < CONSECUTIVE_BAD_THRESHOLD:
            continue
        last = entries[-1] if entries else {}
        state = (current_state or {}).get(label, "")
        findings.append(ZombieFinding(
            label=label,
            reason=(
                f"{streak} consecutive bad exits "
                f"(>= {CONSECUTIVE_BAD_THRESHOLD} threshold)"
            ),
            consecutive_bad_exits=streak,
            last_exit_code=int(last.get("exit_code", -1)),
            currently_running=(state == "running"),
        ))
    return findings
