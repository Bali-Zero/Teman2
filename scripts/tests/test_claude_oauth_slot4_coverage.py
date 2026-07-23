"""Regression coverage for the fourth Claude OAuth subscription slot."""

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

SLOT4_CONSUMERS = (
    ("infra/launchagents/wrappers/cron-agent.sh", "for i in 1 2 3 4; do"),
    ("scripts/ai-dispatch.sh", '"CLAUDE_CODE_OAUTH_TOKEN_4"'),
    ("scripts/dlq_autopilot.py", "for i in (1, 2, 3, 4):"),
    ("scripts/wr2_html_renderer/claude_vision.py", '"CLAUDE_CODE_OAUTH_TOKEN_4"'),
    ("scripts/zantara-gateway/claude_client.py", "for i in (1, 2, 3, 4):"),
    ("apps/backend-rag/scripts/auto_verifier.py", "for i in (1, 2, 3, 4):"),
    ("apps/backend-rag/scripts/verified_generator.py", "for i in (1, 2, 3, 4):"),
    ("apps/bali-intel-scraper/scripts/bz_image_style.py", "for i in (1, 2, 3, 4):"),
    ("apps/evaluator/nlm_deep_research/t4_monitor.py", '"CLAUDE_CODE_OAUTH_TOKEN_4"'),
    (
        "apps/mata-garuda/mata_garuda/agents/daily_briefing_agent.py",
        '"CLAUDE_CODE_OAUTH_TOKEN_4"',
    ),
    (
        "apps/mata-garuda/mata_garuda/agents/weekly_digest_agent.py",
        '"CLAUDE_CODE_OAUTH_TOKEN_4"',
    ),
    (
        "apps/mata-garuda/mata_garuda/runtime/cli_runtime.py",
        '"CLAUDE_CODE_OAUTH_TOKEN_4"',
    ),
    ("apps/mata-garuda/scripts/run_ai_digest.py", '"CLAUDE_CODE_OAUTH_TOKEN_4"'),
)


@pytest.mark.parametrize(("relative_path", "slot4_sentinel"), SLOT4_CONSUMERS)
def test_every_automation_consumer_reaches_slot4(
    relative_path: str,
    slot4_sentinel: str,
) -> None:
    source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    assert slot4_sentinel in source, (
        f"{relative_path} no longer reaches CLAUDE_CODE_OAUTH_TOKEN_4"
    )
