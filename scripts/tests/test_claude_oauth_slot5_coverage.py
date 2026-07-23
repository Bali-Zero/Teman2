"""Regression coverage for the fifth Claude OAuth subscription slot."""

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

SLOT5_CONSUMERS = (
    ("infra/launchagents/wrappers/cron-agent.sh", "for i in 1 2 3 4 5; do"),
    (
        "infra/launchagents/wrappers/wr2-ig-metrics-analyst-run.sh",
        "CLAUDE_CODE_OAUTH_TOKEN_5",
    ),
    ("scripts/ai-dispatch.sh", '"CLAUDE_CODE_OAUTH_TOKEN_5"'),
    ("scripts/dlq_autopilot.py", "for i in (1, 2, 3, 4, 5):"),
    ("scripts/wr2_html_renderer/claude_vision.py", "for index in (1, 2, 3, 4, 5):"),
    ("scripts/zantara-gateway/claude_client.py", "for i in (1, 2, 3, 4, 5):"),
    ("apps/backend-rag/scripts/auto_verifier.py", "for i in (1, 2, 3, 4, 5):"),
    ("apps/backend-rag/scripts/verified_generator.py", "for i in (1, 2, 3, 4, 5):"),
    ("apps/bali-intel-scraper/scripts/bz_image_style.py", "for i in (1, 2, 3, 4, 5):"),
    (
        "apps/evaluator/nlm_deep_research/t4_monitor.py",
        "for index in (1, 2, 3, 4, 5):",
    ),
    (
        "apps/mata-garuda/mata_garuda/agents/daily_briefing_agent.py",
        "claude_token_chain",
    ),
    (
        "apps/mata-garuda/mata_garuda/agents/weekly_digest_agent.py",
        "claude_token_chain",
    ),
    (
        "apps/mata-garuda/mata_garuda/runtime/cli_runtime.py",
        '"CLAUDE_CODE_OAUTH_TOKEN_5"',
    ),
    ("apps/mata-garuda/scripts/run_ai_digest.py", "claude_token_chain"),
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


def test_canonical_cascade_preserves_full_provider_order() -> None:
    """Team is the final Claude seat, followed by every non-Claude fallback."""
    source = (
        REPO_ROOT / "infra/launchagents/wrappers/claude-cascade.sh"
    ).read_text(encoding="utf-8")
    sentinels = (
        "claude-acct4:tier2c-claude-acct4",
        "claude-zero-team:tier2d-claude-zero-team",
        "try_gemini && exit 0",
        "try_kimi && exit 0",
        "try_codex && exit 0",
        "try_ollama && exit 0",
    )
    positions = [source.index(sentinel) for sentinel in sentinels]

    assert positions == sorted(positions)


def test_mata_runtime_documents_slot_four_and_team_identities() -> None:
    source = (
        REPO_ROOT / "apps/mata-garuda/mata_garuda/runtime/cli_runtime.py"
    ).read_text(encoding="utf-8")

    assert (
        '"CLAUDE_CODE_OAUTH_TOKEN_4",  '
        "# applevisionpro1987@gmail.com (4th MAX x20)"
    ) in source
    assert (
        '"CLAUDE_CODE_OAUTH_TOKEN_5",  '
        "# zero@balizero.com (Team premium seat — weekly-capped, last-resort)"
    ) in source
