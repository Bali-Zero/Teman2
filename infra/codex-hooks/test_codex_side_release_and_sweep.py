"""Two council residuals on the Codex side of the child ledger.

  * install.py's default child_limits carried no `active_ttl`, and the sweep was
    gated on the key being present — so the Codex side had NO zombie detection at
    all and a SIGKILLed supervisor pinned its slot until max_attempts. The Claude
    adapter has always passed active_ttl=1800; the asymmetry was undeclared.
  * child_hook released the ledger slot only AFTER the block path returned, so a
    first BLOCKED SubagentStop skipped the release until the harness's second
    Stop. This is the ordering the Claude side fixed for Blocker 1.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import context_bridge as bridge
import mandate_budget as budget
from test_child_lifecycle import child_transcript
from test_context_bridge import setup, token  # noqa: F401

LIMITS_WITHOUT_TTL = {
    "max_attempts": 24,
    "max_active": 3,
    "max_depth": 1,
    "max_seconds": 3600,
}


def _state(root: Path, mandate: str = "root") -> dict:
    return json.loads(
        (root / (hashlib.sha256(mandate.encode()).hexdigest() + ".json")).read_text()
    )


# --- residual: the Codex side had no zombie detection ----------------------


def test_the_sweep_runs_even_when_the_policy_omits_active_ttl(tmp_path: Path) -> None:
    # Exactly install.py's shipped default before this PR: no active_ttl key.
    assert budget.reserve(tmp_path, "root", "one", LIMITS_WITHOUT_TTL) is None
    budget.observe(tmp_path, "root", "child-a")

    state = _state(tmp_path)
    silent = time.time() - (budget.ACTIVE_TTL_SECONDS + 60)
    for row in state["reservations"].values():
        row["created"] = row["heartbeat"] = silent
    state["children"]["child-a"]["transcript_path"] = str(tmp_path / "gone.jsonl")
    (tmp_path / (hashlib.sha256(b"root").hexdigest() + ".json")).write_text(
        json.dumps(state)
    )

    budget.reserve(tmp_path, "root", "two", LIMITS_WITHOUT_TTL)
    after = _state(tmp_path)
    # Missing transcript cannot establish silence, so the row is RETAINED and the
    # ledger asks for reconciliation — it must never be silently deleted (D1).
    assert after["status"] == "needs_attention"
    assert "UNKNOWN" in after["reason"] or "silent" in after["reason"]


def test_a_silent_transcript_becomes_suspect_zombie_without_an_explicit_ttl(
    tmp_path: Path,
) -> None:
    assert budget.reserve(tmp_path, "root", "one", LIMITS_WITHOUT_TTL) is None
    transcript = tmp_path / "child.jsonl"
    transcript.write_text("{}\n")
    budget.observe(tmp_path, "root", "child-a", transcript=str(transcript))

    state = _state(tmp_path)
    silent = time.time() - (budget.ACTIVE_TTL_SECONDS + 600)
    for row in state["reservations"].values():
        row["created"] = row["heartbeat"] = silent
    (tmp_path / (hashlib.sha256(b"root").hexdigest() + ".json")).write_text(
        json.dumps(state)
    )
    import os

    os.utime(transcript, (silent, silent))

    budget.reserve(tmp_path, "root", "two", LIMITS_WITHOUT_TTL)
    rows = list(_state(tmp_path)["reservations"].values())
    assert any(r["status"] == "suspect_zombie" for r in rows)
    # Never deleted, only stopped from counting.
    assert len(rows) == 2


def test_an_explicit_active_ttl_still_wins(tmp_path: Path) -> None:
    limits = dict(LIMITS_WITHOUT_TTL, active_ttl=1)
    assert budget.reserve(tmp_path, "root", "one", limits) is None
    budget.observe(tmp_path, "root", "child-a")
    state = _state(tmp_path)
    for row in state["reservations"].values():
        row["created"] = row["heartbeat"] = time.time() - 10
    (tmp_path / (hashlib.sha256(b"root").hexdigest() + ".json")).write_text(
        json.dumps(state)
    )
    budget.reserve(tmp_path, "root", "two", limits)
    # active_ttl=1 is far shorter than the default: the sweep must have looked.
    assert _state(tmp_path)["status"] == "needs_attention"


def test_installed_policy_declares_active_ttl() -> None:
    import install

    source = Path(install.__file__).read_text()
    assert '"active_ttl": mandate_budget.ACTIVE_TTL_SECONDS' in source


# --- residual: release after block instead of before -----------------------


def test_a_blocked_stop_releases_the_ledger_slot_before_it_blocks(
    setup: tuple,
) -> None:
    _, log, e = setup
    child = "child-session-release"
    child_transcript(log, child, e["session_id"])
    bridge.hook({**e, "agent_id": child, "hook_event_name": "SubagentStart"})
    with log.open("a") as out:
        out.write(
            json.dumps(
                {
                    "timestamp": "new",
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "model_context_window": 1000,
                            "last_token_usage": {"total_tokens": 500},
                        },
                    },
                }
            )
            + "\n"
        )
    pre = {**e, "hook_event_name": "PreToolUse", "tool_name": "Bash"}
    for _ in range(3):
        assert bridge.hook(pre)["hookSpecificOutput"]["permissionDecision"] == "deny"

    stop = {
        **e,
        "agent_id": child,
        "hook_event_name": "SubagentStop",
        "agent_transcript_path": str(log),
    }
    with patch.object(
        bridge, "launch", side_effect=AssertionError("child must never launch")
    ):
        # FIRST stop, and it BLOCKS — the slot must already be released.
        assert bridge.hook(stop)["decision"] == "block"

    ledger = bridge.state_dir() / "mandates"
    children = {
        cid: row
        for state_file in ledger.glob("*.json")
        for cid, row in json.loads(state_file.read_text()).get("children", {}).items()
    }
    assert children, "the stop must have reached the ledger at all"
    assert children[child]["transport"] == "stopped", (
        "a blocked stop left the child recorded as started: the release ran "
        "after the block path returned instead of before it"
    )
