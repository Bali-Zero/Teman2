"""Tri-LLM PR-review bot — the claude-opus seat's credential-shape gate.

Scar family #2 (Esiste != Armato). The seat reported `down (no_json)` across
many PRs while every interactive probe of the same CLI worked, because the
macOS keychain item `Claude Code-credentials` holds a ~8KB JSON document, not
a bare token, and the seat assigned that document verbatim to
CLAUDE_CODE_OAUTH_TOKEN. The CLI then failed auth and printed prose; the
parser saw no JSON and blamed the reviewer.

GUILT   = the JSON blob is unwrapped to its accessToken.
INNOCENCE = a bare token, and the already-working env-var path, are untouched.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_tri_llm_review import extract_oauth_access_token  # noqa: E402

BARE = "sk-ant-oat01-" + "x" * 95


def keychain_blob(access="sk-ant-oa" + "t" * 99, **extra):
    """The real shape, per a live `security find-generic-password -w` read."""
    payload = {
        "mcpOAuth": {"some-server": {"accessToken": "unrelated"}},
        "claudeAiOauth": {
            "accessToken": access,
            "refreshToken": "sk-ant-or" + "r" * 99,
            "expiresAt": 1793000000000,
            "refreshTokenExpiresAt": 1795000000000,
            "scopes": ["user:inference"],
            "subscriptionType": "max",
            "rateLimitTier": "default_claude_max",
            **extra,
        },
    }
    return json.dumps(payload)


# --------------------------------------------------------------------- guilt


def test_json_blob_is_unwrapped_to_the_access_token():
    """The bug: 7,993 chars of JSON went in where 108 chars of token belong."""
    raw = keychain_blob()
    got = extract_oauth_access_token(raw)

    assert got is not None
    assert got.startswith("sk-ant-oa")
    assert got != raw.strip(), "the blob was passed through verbatim — the bug is back"
    assert not got.startswith("{"), "a token never starts with a brace"
    assert len(got) < 200, f"got {len(got)} chars — that is a document, not a token"


def test_realistic_blob_size_is_not_forwarded():
    """Size is the tell: the live blob measured 7,993 characters."""
    raw = keychain_blob(padding="z" * 7000)
    assert len(raw) > 7000

    got = extract_oauth_access_token(raw)

    assert got is not None and len(got) < 200


def test_trailing_newline_from_the_security_cli_does_not_break_parsing():
    got = extract_oauth_access_token(keychain_blob() + "\n")
    assert got is not None and got.startswith("sk-ant-oa")


# ----------------------------------------------------------------- innocence


def test_a_bare_token_passes_through_unchanged():
    """The ~/.claude/token file shape must keep working."""
    assert extract_oauth_access_token(BARE) == BARE
    assert extract_oauth_access_token(f"  {BARE}\n") == BARE


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   \n ",
        "{not json at all",
        json.dumps({"mcpOAuth": {"x": 1}}),  # no claudeAiOauth section
        json.dumps({"claudeAiOauth": {"refreshToken": "r"}}),  # no accessToken
        json.dumps({"claudeAiOauth": {"accessToken": "   "}}),  # blank
        json.dumps({"claudeAiOauth": "not-an-object"}),
        json.dumps(["a", "list"]),
    ],
)
def test_unrecoverable_credentials_yield_none_never_a_poisoned_value(raw):
    """None is the contract: the caller then leaves the env var UNSET, so the
    CLI falls back to its own auth instead of being overridden with garbage.
    Returning the raw text here would reproduce the original defect."""
    assert extract_oauth_access_token(raw) is None


def test_caller_leaves_the_env_var_unset_when_extraction_fails():
    """The gate is only useful if the call site honours None — pin the shape
    of that branch so a refactor cannot silently reintroduce the assignment."""
    source = (
        Path(__file__).resolve().parents[1] / "codex_tri_llm_review.py"
    ).read_text(encoding="utf-8")

    assert 'env["CLAUDE_CODE_OAUTH_TOKEN"] = keychain_result.stdout.strip()' not in source, (
        "the verbatim keychain assignment is back — that is the original bug"
    )
    assert "if token:" in source
    assert 'env["CLAUDE_CODE_OAUTH_TOKEN"] = token' in source
