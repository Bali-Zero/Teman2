"""Regression coverage for the Claude OAuth subscription slots.

Consumers cascade across the four MAX x20 seats (slots 1-4) and then the
zero@balizero.com Team premium seat (slot 5, weekly-capped, last-resort).
Each sentinel asserts the consumer reaches the NEW frontier slot (5), which
implies the earlier slots are present too.
"""

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

SLOT5_CONSUMERS = (
    (
        "infra/launchagents/wrappers/claude-cascade.sh",
        "claude-zero-team:tier2d-claude-zero-team",
    ),
    ("infra/launchagents/wrappers/cron-agent.sh", "for i in 1 2 3 4 5; do"),
    (
        "infra/launchagents/wrappers/wr2-ig-metrics-analyst-run.sh",
        "${CLAUDE_CODE_OAUTH_TOKEN_5:-}",
    ),
    ("scripts/ai-dispatch.sh", '"CLAUDE_CODE_OAUTH_TOKEN_5"'),
    ("scripts/dlq_autopilot.py", "for i in (1, 2, 3, 4, 5):"),
    ("scripts/wr2_html_renderer/claude_vision.py", '"CLAUDE_CODE_OAUTH_TOKEN_5"'),
    ("scripts/zantara-gateway/claude_client.py", "for i in (1, 2, 3, 4, 5):"),
    ("apps/backend-rag/scripts/auto_verifier.py", "for i in (1, 2, 3, 4, 5):"),
    ("apps/backend-rag/scripts/verified_generator.py", "for i in (1, 2, 3, 4, 5):"),
    ("apps/bali-intel-scraper/scripts/bz_image_style.py", "for i in (1, 2, 3, 4, 5):"),
    ("apps/evaluator/nlm_deep_research/t4_monitor.py", '"CLAUDE_CODE_OAUTH_TOKEN_5"'),
    (
        "apps/mata-garuda/mata_garuda/agents/daily_briefing_agent.py",
        '"CLAUDE_CODE_OAUTH_TOKEN_5"',
    ),
    (
        "apps/mata-garuda/mata_garuda/agents/weekly_digest_agent.py",
        '"CLAUDE_CODE_OAUTH_TOKEN_5"',
    ),
    (
        "apps/mata-garuda/mata_garuda/runtime/cli_runtime.py",
        '"CLAUDE_CODE_OAUTH_TOKEN_5"',
    ),
    ("apps/mata-garuda/scripts/run_ai_digest.py", '"CLAUDE_CODE_OAUTH_TOKEN_5"'),
)


@pytest.mark.parametrize(("relative_path", "slot5_sentinel"), SLOT5_CONSUMERS)
def test_every_automation_consumer_reaches_slot5(
    relative_path: str,
    slot5_sentinel: str,
) -> None:
    source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    assert slot5_sentinel in source, (
        f"{relative_path} no longer reaches CLAUDE_CODE_OAUTH_TOKEN_5"
    )


def test_canonical_cascade_preserves_all_subscription_and_fallback_tiers() -> None:
    source = (
        REPO_ROOT / "infra/launchagents/wrappers/claude-cascade.sh"
    ).read_text(encoding="utf-8")
    cascade = source.split("# ============= CASCADE =============", maxsplit=1)[1]
    ordered_sentinels = (
        "tier1-claude-default",
        "tier2-claude-acct2",
        "tier2b-claude-acct3",
        "tier2c-claude-acct4",
        "tier2d-claude-zero-team",
        "try_gemini && exit 0",
        "try_kimi && exit 0",
        "try_codex && exit 0",
        "try_ollama && exit 0",
    )

    offsets = [cascade.index(sentinel) for sentinel in ordered_sentinels]

    assert offsets == sorted(offsets)
    assert "weekly limit" in source
    assert "Kimi K3 returned empty output" in source
