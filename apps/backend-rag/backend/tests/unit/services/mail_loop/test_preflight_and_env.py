"""Corpus for the three defences added when this loop was armed on the Pro.

Each one pins a failure that was OBSERVED, not imagined:

  1. The loop must refuse to run when the Zoho client credentials are absent.
     `ZohoOAuthService._refresh_token` reads Zoho's `invalid_client` reply as a
     dead USER token and writes `token_expires_at = NOW() - INTERVAL '1 year'`,
     which trips the "invalidated, reconnect required" guard for EVERY other
     consumer — including the live backend, which has the right credentials.
     `invalid_client` is a statement about the CALLER, never about the token.
     Three probe runs from a machine that simply lacked the pair invalidated all
     three of zero@balizero.com's rows before the cause was known.

  2. `DATABASE_URL` from the environment must win over the app settings. The DSN
     in `apps/backend-rag/.env` is stale (its role is refused by the live proxy),
     and settings are read only when the process cwd happens to sit next to that
     file.

  3. Drafting must ATTEMPT the CLI when `CLAUDE_CODE_OAUTH_TOKEN` is unset. The
     CLI also authenticates with its own OAuth session and answers perfectly well
     with no variable exported; refusing on the variable judged a proxy for the
     capability and reported every draft as impossible on a machine where
     drafting works.

Hermetic by construction: the modules `cli` imports lazily are replaced with
fakes, so this file needs no asyncpg, no settings, no mailbox — the property the
rest of this suite has and should keep.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

from backend.services.mail_loop import cli as cli_module
from backend.services.mail_loop import draft as draft_module

# --------------------------------------------------------------------------- #
# fakes
# --------------------------------------------------------------------------- #


class _FakeConn:
    async def fetchrow(self, *_args: Any, **_kwargs: Any) -> dict[str, str]:
        return {"id": "USER-1"}


class _Acquire:
    async def __aenter__(self) -> _FakeConn:
        return _FakeConn()

    async def __aexit__(self, *_exc: Any) -> bool:
        return False


class _FakePool:
    def __init__(self) -> None:
        self.closed = False

    def acquire(self) -> _Acquire:
        return _Acquire()

    async def close(self) -> None:
        self.closed = True


class _FakeOAuth:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret


class _FakeService:
    """Records every call. A Zoho call made while the preflight should have
    blocked is the whole defect, so `calls` IS the assertion."""

    def __init__(self, client_id: str = "cid", client_secret: str = "sec") -> None:
        self.oauth_service = _FakeOAuth(client_id, client_secret)
        self.calls: list[str] = []

    async def list_folders(self, _user_id: str) -> list[dict[str, Any]]:
        self.calls.append("list_folders")
        return []

    async def list_emails(self, *_a: Any, **_k: Any) -> dict[str, Any]:
        self.calls.append("list_emails")
        return {"emails": []}

    async def close(self) -> None:
        self.calls.append("close")


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Install fake `asyncpg` and `zoho_email_service` modules for `cli._amain`.

    `_amain` imports both lazily, so replacing them in `sys.modules` is enough
    and nothing real is ever constructed.
    """
    state: dict[str, Any] = {"dsn": None, "service": _FakeService()}

    async def fake_create_pool(dsn: str, **_kwargs: Any) -> _FakePool:
        state["dsn"] = dsn
        return _FakePool()

    fake_asyncpg = types.ModuleType("asyncpg")
    fake_asyncpg.create_pool = fake_create_pool  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "asyncpg", fake_asyncpg)

    fake_zoho = types.ModuleType("backend.services.integrations.zoho_email_service")
    fake_zoho.ZohoEmailService = lambda _pool: state["service"]  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules, "backend.services.integrations.zoho_email_service", fake_zoho
    )

    monkeypatch.setenv("DATABASE_URL", "postgresql://fake/db")
    monkeypatch.setenv("MAIL_LOOP_USER_ID", "USER-1")
    return state


def _run(tmp_path: Path) -> int:
    return cli_module.main(["--dry-run", "--state-dir", str(tmp_path)])


# --------------------------------------------------------------------------- #
# 1. preflight — the token-invalidation guard
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("client_id", "client_secret", "label"),
    [
        ("", "", "both absent"),
        ("", "sec", "id absent"),
        ("cid", "", "secret absent"),
    ],
)
def test_missing_zoho_client_credentials_refuse_before_any_call(
    wired: dict[str, Any], tmp_path: Path, client_id: str, client_secret: str, label: str
) -> None:
    """GUILT: no credentials -> exit 2, and Zoho is never touched.

    The second half matters more than the exit code: reaching Zoho at all is
    what invalidates the stored token for everyone else.
    """
    wired["service"] = _FakeService(client_id, client_secret)

    assert _run(tmp_path) == 2, label
    assert "list_folders" not in wired["service"].calls, (
        f"{label}: the loop called Zoho without client credentials — that call "
        "is what marks a live production token as permanently invalid"
    )


def test_credentials_present_the_loop_runs(
    wired: dict[str, Any], tmp_path: Path
) -> None:
    """INNOCENCE: with credentials the preflight is invisible.

    Without this row the guard could be a bare `return 2` and still look green.
    """
    assert _run(tmp_path) == 0
    assert "list_folders" in wired["service"].calls


# --------------------------------------------------------------------------- #
# 2. DSN resolution
# --------------------------------------------------------------------------- #


def test_database_url_env_is_used_verbatim(
    wired: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://chosen/one")
    _run(tmp_path)
    assert wired["dsn"] == "postgresql://chosen/one"


def test_no_dsn_anywhere_is_exit_2_not_a_traceback(
    wired: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing DSN is a diagnosable exit code, never a pydantic stack trace.

    The settings fallback validates the WHOLE app config (JWT_SECRET_KEY,
    API_KEYS); importing it raises unless those unrelated secrets are present.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    broken = types.ModuleType("backend.app.core.config")

    def _explode() -> None:
        raise RuntimeError("settings validation failed: JWT_SECRET_KEY must be set")

    broken.__getattr__ = lambda _name: _explode()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "backend.app.core.config", broken)

    assert _run(tmp_path) == 2


# --------------------------------------------------------------------------- #
# 3. drafting authenticates two ways
# --------------------------------------------------------------------------- #


class _Completed:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _request() -> draft_module.DraftRequest:
    return draft_module.DraftRequest(
        subject="KITAS renewal",
        body="What documents do you need?",
        sender_name="someone@example.com",
        language="en",
        intent="visa",
        style_block="(none)",
    )


def test_draft_attempts_the_cli_without_the_token_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INNOCENCE: an unset token must not pre-empt a CLI that can authenticate."""
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("CLAUDE_CLI_PATH", "/fake/claude")

    seen: dict[str, Any] = {}

    def fake_run(argv: list[str], **_kwargs: Any) -> _Completed:
        seen["argv"] = argv
        return _Completed(0, stdout="Dear client, ...")

    monkeypatch.setattr(draft_module.subprocess, "run", fake_run)

    assert draft_module.generate(_request()) == "Dear client, ..."
    assert seen["argv"][0] == "/fake/claude", "the CLI was never invoked"


def test_draft_reports_the_clis_real_error_when_it_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GUILT: a CLI that cannot authenticate still fails — with ITS reason.

    This is what the removed pre-check was really protecting, and the CLI's own
    message is strictly more informative than a guess about a variable.
    """
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("CLAUDE_CLI_PATH", "/fake/claude")
    monkeypatch.setattr(
        draft_module.subprocess,
        "run",
        lambda *_a, **_k: _Completed(1, stderr="Invalid API key / not logged in"),
    )

    with pytest.raises(draft_module.DraftUnavailable) as excinfo:
        draft_module.generate(_request())
    assert "not logged in" in str(excinfo.value)


# ---------------------------------------------------------------------------
# A failure a re-consent would clear must be exit 2, not exit 1.
#
# Exit 1 means "some of it worked, try again tomorrow". A missing OAuth scope is
# not that: the loop can read the mailbox but cannot list the folders it routes
# into, so every future run fails identically. A daily cron answering "degraded"
# forever is the exact shape this repo keeps paying for — green enough to
# ignore, broken enough to be useless.
# ---------------------------------------------------------------------------


def test_missing_scope_is_a_blocker_not_a_degradation() -> None:
    """GUILT: Zoho's own error code is recognised, whatever surrounds it."""
    errors = ["list_folders failed: API error: INVALID_OAUTHSCOPE"]
    assert cli_module._consent_blocker(errors) == errors[0]


def test_the_reconnect_sentence_is_a_blocker() -> None:
    """GUILT: raised verbatim by ZohoOAuthService when a token is invalidated."""
    errors = ["Zoho token invalidated — reconnect required at /admin/zoho/auth"]
    assert cli_module._consent_blocker(errors) is errors[0]


def test_an_ordinary_degraded_run_is_not_a_blocker() -> None:
    """INNOCENCE: without this, every degraded run would exit 2 and the check
    would be indistinguishable from a broken loop."""
    assert (
        cli_module._consent_blocker(
            [
                "folder _Visa does not exist",
                "draft failed for thread 42: claude CLI timed out",
                "move_message failed: API error: URL_RULE_NOT_CONFIGURED",
            ]
        )
        is None
    )


def test_no_errors_is_not_a_blocker() -> None:
    assert cli_module._consent_blocker([]) is None
