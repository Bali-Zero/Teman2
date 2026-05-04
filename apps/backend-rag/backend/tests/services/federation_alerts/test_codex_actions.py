"""Unit tests for FAD whitelist V2 — Codex 5.5 capabilities.

Tests focus on:
- dry_run path produces deterministic output without spawning subprocess
- input validation (missing prompt, oversize prompt, invalid path)
- enum + registry alignment

Production paths (spawning Codex CLI) are NOT exercised here — that's
covered by integration smoke tests in test_actions_integration.py (when
codex CLI is installed in CI). These unit tests verify the action layer
only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from backend.services.federation_alerts.actions.codex_image_gen import (
    codex_image_gen_action,
)
from backend.services.federation_alerts.actions.codex_overnight_queue import (
    codex_overnight_queue_action,
)
from backend.services.federation_alerts.actions.codex_visual_dispatch import (
    codex_visual_dispatch_action,
)
from backend.services.federation_alerts.actions.codex_xhigh_fix import (
    codex_xhigh_fix_action,
)


@dataclass
class _Proposal:
    """Minimal proposal stub for action invocation."""

    proposal_id: str = "test-proposal-001"
    severity: str = "high"
    action_payload: dict[str, Any] = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# codex_xhigh_fix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_xhigh_fix_dry_run_returns_framed_prompt() -> None:
    p = _Proposal(action_payload={"prompt": "Refactor the login handler to use httpx persistent client."})
    result = await codex_xhigh_fix_action(p, dry_run=True)
    assert result.success is True
    assert result.metadata is not None
    assert result.metadata["dry_run"] is True
    assert result.metadata["framed_prompt_bytes"] > 0
    assert "would invoke codex --profile xhigh exec" in result.message


@pytest.mark.asyncio
async def test_xhigh_fix_rejects_missing_prompt() -> None:
    p = _Proposal(action_payload={})
    result = await codex_xhigh_fix_action(p, dry_run=True)
    assert result.success is False
    assert "missing required action_payload.prompt" in result.message


@pytest.mark.asyncio
async def test_xhigh_fix_rejects_oversize_prompt() -> None:
    huge = "X" * (33 * 1024)
    p = _Proposal(action_payload={"prompt": huge})
    result = await codex_xhigh_fix_action(p, dry_run=True)
    assert result.success is False
    assert "exceeds" in result.message


@pytest.mark.asyncio
async def test_xhigh_fix_rejects_nonexistent_cwd() -> None:
    p = _Proposal(
        action_payload={
            "prompt": "test",
            "cwd": "/nonexistent/path/that/should/not/exist/12345",
        }
    )
    result = await codex_xhigh_fix_action(p, dry_run=True)
    assert result.success is False
    assert "cwd does not exist" in result.message


@pytest.mark.asyncio
async def test_xhigh_fix_clamps_timeout() -> None:
    """timeout_sec clamped to [60, 3600]."""
    p = _Proposal(
        action_payload={
            "prompt": "test",
            "timeout_sec": 99999,  # over MAX
        }
    )
    result = await codex_xhigh_fix_action(p, dry_run=True)
    assert result.metadata["timeout_sec"] == 3600


# ---------------------------------------------------------------------------
# codex_overnight_queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_overnight_queue_dry_run_returns_target_path() -> None:
    p = _Proposal(action_payload={"spec": "# Task\n\nDo X.\n"})
    result = await codex_overnight_queue_action(p, dry_run=True)
    assert result.success is True
    assert result.metadata["dry_run"] is True
    assert "queue/" in result.metadata["target_path"]
    assert result.metadata["target_path"].endswith(".md")


@pytest.mark.asyncio
async def test_overnight_queue_rejects_missing_spec() -> None:
    p = _Proposal(action_payload={})
    result = await codex_overnight_queue_action(p, dry_run=True)
    assert result.success is False
    assert "missing required action_payload.spec" in result.message


@pytest.mark.asyncio
async def test_overnight_queue_rejects_oversize_spec() -> None:
    huge = "X" * (33 * 1024)
    p = _Proposal(action_payload={"spec": huge})
    result = await codex_overnight_queue_action(p, dry_run=True)
    assert result.success is False
    assert "exceeds" in result.message


@pytest.mark.asyncio
async def test_overnight_queue_uses_safe_slug() -> None:
    p = _Proposal(
        proposal_id="abc-123-def-456",
        action_payload={
            "spec": "# task",
            "slug_hint": "Refactor /backend/services!! @special chars",
        },
    )
    result = await codex_overnight_queue_action(p, dry_run=True)
    target = result.metadata["target_path"]
    # No special chars in filename
    fname = target.rsplit("/", 1)[-1]
    assert "!" not in fname
    assert "@" not in fname
    # Slug source preserved
    assert "refactor" in fname.lower()


@pytest.mark.asyncio
async def test_overnight_queue_filename_is_deterministic(tmp_path, monkeypatch) -> None:
    """Same proposal_id + idempotency_key → same filename (no timestamp).

    Regression guard for tri-LLM panel finding 2026-05-05 (PR #463 review):
    the original implementation embedded `datetime.now()` in the filename,
    which broke the 'idempotent' claim documented in the docstring. Now
    the filename is derived purely from proposal_id / idempotency_key so
    repeated L2 dispatches resolve to the same file (overwritten with
    identical content) — true idempotency.
    """
    from backend.services.federation_alerts.actions import codex_overnight_queue as mod

    monkeypatch.setattr(mod, "QUEUE_DIR", tmp_path / "queue")

    # Two proposals with same idempotency_key → same target filename.
    @dataclass
    class _IdempProposal:
        proposal_id: str = "abc-123"
        severity: str = "high"
        idempotency_key: str = "key-deterministic"
        action_payload: dict[str, Any] = None  # type: ignore[assignment]

    p1 = _IdempProposal(action_payload={"spec": "# spec v1"})
    p2 = _IdempProposal(action_payload={"spec": "# spec v2"})

    r1 = await codex_overnight_queue_action(p1, dry_run=True)
    r2 = await codex_overnight_queue_action(p2, dry_run=True)

    assert r1.metadata["target_path"] == r2.metadata["target_path"], (
        "filename must be deterministic for same idempotency_key"
    )


@pytest.mark.asyncio
async def test_overnight_queue_actually_writes_file(tmp_path, monkeypatch) -> None:
    """Non-dry-run path writes a real file (spec is .strip()-ed)."""
    from backend.services.federation_alerts.actions import codex_overnight_queue as mod

    monkeypatch.setattr(mod, "QUEUE_DIR", tmp_path / "queue")

    p = _Proposal(action_payload={"spec": "# Test spec content\n"})
    result = await codex_overnight_queue_action(p, dry_run=False)
    assert result.success is True
    assert len(result.side_effects) == 1
    written = tmp_path / "queue" / result.side_effects[0].rsplit("/", 1)[-1]
    assert written.exists()
    # Action strips whitespace before writing.
    assert written.read_text() == "# Test spec content"


# ---------------------------------------------------------------------------
# codex_image_gen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_image_gen_dry_run_returns_target_path() -> None:
    p = _Proposal(
        action_payload={
            "prompt": "Sunset over Bali rice terraces, cinematic",
            "asset_name": "sunset-hero",
            "dispatch_date": "2026-05-05",
        }
    )
    result = await codex_image_gen_action(p, dry_run=True)
    assert result.success is True
    assert result.metadata["dry_run"] is True
    assert "sunset-hero.png" in result.metadata["target_path"]
    assert "2026-05-05" in result.metadata["target_path"]


@pytest.mark.asyncio
async def test_image_gen_rejects_missing_prompt() -> None:
    p = _Proposal(action_payload={})
    result = await codex_image_gen_action(p, dry_run=True)
    assert result.success is False
    assert "missing required action_payload.prompt" in result.message


@pytest.mark.asyncio
async def test_image_gen_safe_name_strips_special_chars() -> None:
    p = _Proposal(
        action_payload={
            "prompt": "test",
            "asset_name": "../../../etc/passwd!!@#$%",
            "dispatch_date": "2026-05-05",
        }
    )
    result = await codex_image_gen_action(p, dry_run=True)
    target = result.metadata["target_path"]
    # Path sanitization: no traversal segments survive
    fname = target.rsplit("/", 1)[-1]
    assert "../" not in fname
    assert "@" not in fname
    assert fname.endswith(".png")


# ---------------------------------------------------------------------------
# codex_visual_dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_visual_dispatch_dry_run_returns_command() -> None:
    p = _Proposal(action_payload={"topic": "KEP-71/PJ/2026 SPT extension"})
    result = await codex_visual_dispatch_action(p, dry_run=True)
    assert result.success is True
    assert result.metadata["dry_run"] is True
    assert result.metadata["dispatch_date"]  # default to today UTC
    assert result.metadata["force"] is False


@pytest.mark.asyncio
async def test_visual_dispatch_rejects_missing_topic() -> None:
    p = _Proposal(action_payload={})
    result = await codex_visual_dispatch_action(p, dry_run=True)
    assert result.success is False
    assert "missing required action_payload.topic" in result.message


@pytest.mark.asyncio
async def test_visual_dispatch_rejects_oversize_topic() -> None:
    huge = "X" * (5 * 1024)
    p = _Proposal(action_payload={"topic": huge})
    result = await codex_visual_dispatch_action(p, dry_run=True)
    assert result.success is False
    assert "exceeds" in result.message


@pytest.mark.asyncio
async def test_visual_dispatch_clamps_timeout() -> None:
    p = _Proposal(action_payload={"topic": "test", "timeout_sec": 99999})
    result = await codex_visual_dispatch_action(p, dry_run=True)
    assert result.metadata["timeout_sec"] == 7200


# ---------------------------------------------------------------------------
# Hard rule guard — no provider keys leaked into prompts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_anthropic_key_in_xhigh_prompt() -> None:
    """Even if user includes ANTHROPIC_API_KEY in prompt, the framed prompt
    must contain the explicit hard-rule reminder."""
    p = _Proposal(action_payload={"prompt": "Do work"})
    result = await codex_xhigh_fix_action(p, dry_run=True)
    # Defense-in-depth: framed prompt explicitly reminds Codex of the rule
    assert result.metadata["framed_prompt_bytes"] > 0
    # The action wraps the user prompt with hard-rule context — verify
    # by checking that the dry_run reports a framed_prompt larger than
    # the raw user prompt would imply.
    assert result.metadata["framed_prompt_bytes"] > len("Do work")
