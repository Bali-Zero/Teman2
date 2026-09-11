"""Provider failures must remain closed and actionable without leaking output."""

import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from nuzantara_mcp.tools import workspace_marketing as marketing


@pytest.mark.parametrize("provider,message,status", [
    ("nlm", b"Authentication expired. Run nlm login", "auth_required"),
    ("nlm", b"Your credentials have expired", "auth_required"),
    ("claude", b"Not logged in", "auth_required"),
    ("nlm", b"Network failure", "unavailable"),
])
async def test_provider_failure_is_classified_without_output(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    provider: str, message: bytes, status: str,
) -> None:
    process = AsyncMock()
    process.returncode = 1
    process.communicate.return_value = (message, b"private-output-not-for-logs")
    monkeypatch.setattr(marketing.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    with pytest.raises(marketing.EditorialProviderFailure) as exc:
        await marketing._run_public_subprocess([provider], timeout_seconds=5, env={})
    assert exc.value.status == status
    assert "private-output" not in caplog.text
    assert "private-output" not in str(exc.value)
    if provider == "nlm" and status == "auth_required":
        assert "nlm login on Pro" in str(exc.value)


async def test_successful_evidence_is_not_classified_as_an_auth_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = AsyncMock()
    process.returncode = 0
    process.communicate.return_value = (b"Article discusses nlm login", b"")
    monkeypatch.setattr(marketing.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    assert await marketing._run_public_subprocess(["nlm"], timeout_seconds=5, env={}) == "Article discusses nlm login"


@pytest.mark.parametrize("nlm_status,reviewer_reply,ready", [
    ("authenticated", '{"loggedIn": true}', True),
    ("auth_required", '{"loggedIn": true}', False),
    ("timeout", '{"loggedIn": true}', False),
    ("authenticated", '{"loggedIn": false}', False),
    ("authenticated", 'invalid-json', False),
    ("authenticated", '[]', False),
])
async def test_health_probes_the_verifier_environment_and_never_claims_a_verdict(
    monkeypatch: pytest.MonkeyPatch, nlm_status: str, reviewer_reply: str, ready: bool,
) -> None:
    monkeypatch.setattr(marketing, "_verification_env", lambda provider: {"PATH": provider})
    monkeypatch.setattr(marketing.shutil, "which", lambda binary, **kwargs: binary)
    calls: list[list[str]] = []

    async def run(argv: list[str], *, timeout_seconds: int, env: dict[str, str]) -> str:
        calls.append(argv)
        assert timeout_seconds == 60
        assert env["PATH"] == ("notebooklm" if argv[0] == "nlm" else "claude")
        if argv[0] == "nlm":
            if nlm_status != "authenticated":
                raise marketing.EditorialProviderFailure("nlm", nlm_status)
            return "Authentication is valid"
        return reviewer_reply

    monkeypatch.setattr(marketing, "_run_public_subprocess", run)
    result = await marketing._editorial_auth_health()
    assert result["authentication_ready"] is ready
    assert result["verdict"] == "not_run"
    assert ["nlm", "login", "--check"] in calls
    assert ["claude", "auth", "status", "--json"] in calls


async def test_missing_binaries_fail_health_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(marketing, "_verification_env", lambda provider: {"PATH": "/missing"})
    monkeypatch.setattr(marketing.shutil, "which", lambda *args, **kwargs: None)
    result = await marketing._editorial_auth_health()
    assert result["authentication_ready"] is False
    assert result["notebooklm_auth"] == result["reviewer_identity"] == "unavailable"


@pytest.mark.parametrize("loaded,exit_code", [(True, 69), (False, 64)])
def test_installer_refuses_a_loaded_supervisor_before_configuring_anything(
    tmp_path: Path, loaded: bool, exit_code: int,
) -> None:
    hostname = tmp_path / "hostname"
    hostname.write_text("#!/bin/sh\nprintf 'Nuzantara\\n'\n")
    hostname.chmod(0o700)
    launchctl = tmp_path / "launchctl"
    launchctl.write_text(
        '#!/bin/sh\n[ "$1" = list ] && [ "$2" = com.nuzantara.chatgpt-marketing-tunnel ] || exit 1\n'
        + ("exit 0\n" if loaded else "exit 1\n")
    )
    launchctl.chmod(0o700)
    script = Path(__file__).resolve().parents[3] / "scripts/setup_chatgpt_marketing_tunnel.sh"
    result = subprocess.run(
        ["/bin/bash", str(script)], capture_output=True, text=True, timeout=5,
        env={**os.environ, "PATH": f"{tmp_path}:/usr/bin:/bin"},
    )
    assert result.returncode == exit_code
    assert ("Launchd already supervises" in result.stderr) is loaded
