"""Tests for modus_green_gate.is_green — GUILT + INNOCENCE corpora.

Scar family #3 discipline (guard-over-match / substring trap): every
disqualifier must be proven both GUILTY (fires on the real surface) and
INNOCENT (does not fire on a lexically-similar-but-different surface).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from modus_green_gate import is_green  # noqa: E402


# ---------------------------------------------------------------------------
# GUILT corpus — must be REJECTED (allowed is False)
# ---------------------------------------------------------------------------


def test_guilt_migration_task_rejected():
    task = {
        "class": "green",
        "perimeter": ["migrations_v2/0042_add_client_index.sql"],
        "mandate": "Add an index to speed up client lookups",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "migrations_v2" in reason


def test_guilt_migrations_dir_rejected():
    task = {
        "class": "green",
        "perimeter": ["backend/migrations/0001_init.py"],
        "mandate": "Initial schema",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "migrations" in reason


def test_guilt_alembic_env_rejected():
    task = {
        "class": "green",
        "perimeter": ["apps/backend-rag/backend/alembic/env.py"],
        "mandate": "Tune alembic env config",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert reason.startswith("perimeter_disqualifier:")


def test_guilt_auth_task_rejected():
    task = {
        "class": "green",
        "perimeter": ["apps/backend-rag/backend/auth/session.py"],
        "mandate": "Fix session expiry bug",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "auth" in reason


def test_guilt_billing_task_rejected():
    task = {
        "class": "green",
        "perimeter": ["apps/backend-rag/backend/billing/invoices.py"],
        "mandate": "Fix invoice rounding",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "billing" in reason


def test_guilt_pricing_task_rejected():
    task = {
        "class": "green",
        "perimeter": ["apps/backend-rag/backend/pricing/engine.py"],
        "mandate": "Adjust pricing engine cache",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "pricing" in reason


def test_guilt_pricing_tool_keyword_rejected():
    task = {
        "class": "green",
        "perimeter": ["apps/backend-rag/backend/services/PricingTool.py"],
        "mandate": "Refactor PricingTool internals",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "pricing_tool" in reason


def test_guilt_deploy_task_rejected():
    task = {
        "class": "green",
        "perimeter": ["scripts/deploy/rollout.sh"],
        "mandate": "Speed up rolling deploy",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "deploy" in reason


def test_guilt_github_workflows_rejected():
    task = {
        "class": "green",
        "perimeter": [".github/workflows/ci.yml"],
        "mandate": "Add a lint step to CI",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "github_workflows" in reason


def test_guilt_fly_toml_rejected():
    task = {
        "class": "green",
        "perimeter": ["fly.toml"],
        "mandate": "Bump memory allocation",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "fly_toml" in reason


def test_guilt_zantara_core_rejected():
    task = {
        "class": "green",
        "perimeter": ["zantara_core.py"],
        "mandate": "Refactor core dispatch loop",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "zantara_core" in reason


def test_guilt_secret_env_rejected():
    task = {
        "class": "green",
        "perimeter": ["apps/backend-rag/.env"],
        "mandate": "Update local env defaults",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "secrets_env" in reason


def test_guilt_business_quote_mandate_rejected():
    task = {
        "class": "green",
        "perimeter": ["research/visa/note.md"],
        "mandate": "Prepare a quote for the new KITAS client",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "business_decision_quote" in reason


def test_guilt_business_refund_mandate_rejected():
    task = {
        "class": "green",
        "perimeter": ["research/tax/note.md"],
        "mandate": "Process a refund for the cancelled practice",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "business_decision_refund" in reason


def test_guilt_business_email_to_client_rejected():
    task = {
        "class": "green",
        "perimeter": ["research/property/note.md"],
        "mandate": "Draft an email to client about the delay",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "business_decision_email_to_client" in reason


def test_guilt_class_proposal_rejected_even_with_clean_perimeter():
    task = {
        "class": "proposal",
        "perimeter": ["backend/tests/test_something.py"],
        "mandate": "Fix a flaky test",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert reason == "class_proposal_never_green"


def test_guilt_class_proposal_rejected_even_with_no_perimeter():
    task = {"class": "proposal", "mandate": "Anything at all"}
    allowed, reason = is_green(task)
    assert allowed is False
    assert reason == "class_proposal_never_green"


def test_guilt_class_missing_rejected():
    task = {"perimeter": ["backend/tests/test_x.py"], "mandate": "Fix test"}
    allowed, reason = is_green(task)
    assert allowed is False
    assert reason == "class_not_green"


def test_guilt_class_other_value_rejected():
    task = {
        "class": "yellow",
        "perimeter": ["backend/tests/test_x.py"],
        "mandate": "Fix test",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert reason == "class_not_green"


# ---------------------------------------------------------------------------
# INNOCENCE corpus — must PASS (allowed is True)
# ---------------------------------------------------------------------------


def test_innocence_broken_test_fix():
    task = {
        "class": "green",
        "perimeter": ["backend/tests/services/rag/test_kg_langgraph.py"],
        "mandate": "Fix a broken assertion in the KG langgraph test",
    }
    allowed, reason = is_green(task)
    assert allowed is True
    assert reason == "green"


def test_innocence_regulatory_delta_capture():
    task = {
        "class": "green",
        "perimeter": ["research/regulatory/2026-07-12-pp28-delta.md"],
        "mandate": "Capture the PP 28/2025 KBLI conversion delta",
    }
    allowed, reason = is_green(task)
    assert allowed is True
    assert reason == "green"


def test_innocence_lint_format_task():
    task = {
        "class": "green",
        "perimeter": ["scripts/lint_home_fork.py"],
        "mandate": "Run ruff format across the lint scripts directory",
    }
    allowed, reason = is_green(task)
    assert allowed is True
    assert reason == "green"


def test_innocence_release_dir_not_auth():
    """Adversarial near-miss: 'release/' contains 'lea' but must not trip
    any auth/lease-style disqualifier — 'auth' is not a path segment here.
    """
    task = {
        "class": "green",
        "perimeter": ["scripts/release/changelog_gen.py"],
        "mandate": "Regenerate the changelog for the release script",
    }
    allowed, reason = is_green(task)
    assert allowed is True
    assert reason == "green"


def test_innocence_author_filename_not_auth():
    """Adversarial near-miss: a research file containing the substring
    'auth' ('author') inside its name/path must NOT trip the auth
    disqualifier — 'auth' is not a path segment of 'author-notes.md' nor of
    'research/regulatory/author-notes.md'.
    """
    task = {
        "class": "green",
        "perimeter": ["research/regulatory/author-notes.md"],
        "mandate": "Capture author notes on the new regulation delta",
    }
    allowed, reason = is_green(task)
    assert allowed is True
    assert reason == "green"


def test_innocence_authoring_guide_dir_not_auth():
    """Second adversarial near-miss on the same axis: a directory named
    'authoring-guide' must not trip 'auth' either.
    """
    task = {
        "class": "green",
        "perimeter": ["docs/authoring-guide/style.md"],
        "mandate": "Update the authoring guide with a new lint rule",
    }
    allowed, reason = is_green(task)
    assert allowed is True
    assert reason == "green"


def test_innocence_multiple_clean_perimeter_paths():
    task = {
        "class": "green",
        "perimeter": [
            "backend/tests/services/rag/test_confidence.py",
            "research/regulatory/2026-07-12-note.md",
        ],
        "mandate": "Fix flaky confidence test and capture regulatory note",
    }
    allowed, reason = is_green(task)
    assert allowed is True
    assert reason == "green"


def test_innocence_perimeter_as_single_string():
    task = {
        "class": "green",
        "perimeter": "backend/tests/test_lint.py",
        "mandate": "Fix lint test",
    }
    allowed, reason = is_green(task)
    assert allowed is True
    assert reason == "green"


def test_innocence_empty_perimeter_and_mandate():
    task = {"class": "green", "perimeter": [], "mandate": ""}
    allowed, reason = is_green(task)
    assert allowed is True
    assert reason == "green"


# --- Regression guilt tests for the two HIGH findings (scar family #3 splitter under-match) ---

def test_guilt_backslash_migrations_path_is_rejected():
    """A backslash-separated migrations path must NOT slip past the splitter."""
    task = {
        "class": "green",
        "perimeter": ["migrations_v2\\v99_evil.sql"],
        "mandate": "apply migration",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "migrations_v2" in reason


def test_guilt_windows_style_backslash_auth_path_is_rejected():
    task = {
        "class": "green",
        "perimeter": ["C:\\repo\\auth\\login.py"],
        "mandate": "touch it",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "auth" in reason


def test_guilt_string_perimeter_with_two_globs_second_is_dangerous():
    """A single whitespace-separated string must have EVERY glob checked."""
    task = {
        "class": "green",
        "perimeter": "research/x.md migrations/evil.sql",
        "mandate": "capture note and also touch migration",
    }
    allowed, reason = is_green(task)
    assert allowed is False
    assert "migrations" in reason


def test_innocence_string_perimeter_two_clean_globs_still_green():
    """The split must not turn two innocent globs into a false rejection."""
    task = {
        "class": "green",
        "perimeter": "research/regulatory/a.md backend/tests/test_b.py",
        "mandate": "capture note and fix test",
    }
    allowed, reason = is_green(task)
    assert allowed is True
    assert reason == "green"
