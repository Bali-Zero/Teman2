"""Error-boundary tests for FlowKit process and SSH/SCP adapters."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import pytest

from nuzantara_mcp.tools import flowkit


def test_parse_cli_stdout_reports_empty_output() -> None:
    """An empty stdout must retain return code and stderr diagnostics."""
    result = flowkit._parse_cli_stdout(17, "\n", "ssh disconnected\n")

    assert result == {
        "ok": False,
        "error_kind": "flowkit_error",
        "error": "FlowKit CLI returned no JSON",
        "returncode": 17,
        "stderr": "ssh disconnected",
    }


def test_parse_cli_stdout_reports_malformed_last_line() -> None:
    """Human-readable preamble cannot hide malformed terminal JSON."""
    result = flowkit._parse_cli_stdout(
        2,
        "FlowKit starting\n{not-json}\n",
        "remote warning",
    )

    assert result["ok"] is False
    assert result["error"] == "FlowKit CLI returned malformed JSON"
    assert result["returncode"] == 2
    assert result["stdout"].endswith("{not-json}\n")
    assert result["stderr"] == "remote warning"


def test_parse_cli_stdout_rejects_non_object_json() -> None:
    """Only structured object responses are valid bridge payloads."""
    result = flowkit._parse_cli_stdout(0, "[1, 2, 3]\n", "")

    assert result["ok"] is False
    assert result["error"] == "FlowKit CLI JSON was not an object"
    assert result["payload"] == [1, 2, 3]


def test_parse_cli_stdout_preserves_nonzero_returncode_and_stderr() -> None:
    """Valid JSON remains inspectable when the process itself failed."""
    result = flowkit._parse_cli_stdout(
        9,
        'diagnostic\n{"ok": false, "error": "render failed"}\n',
        "GPU unavailable\n",
    )

    assert result["ok"] is False
    assert result["error"] == "render failed"
    assert result["returncode"] == 9
    assert result["stderr"] == "GPU unavailable"


@pytest.mark.asyncio
async def test_run_process_returns_decoded_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The subprocess boundary returns code, stdout, and stderr verbatim."""

    class FakeProcess:
        returncode = 7

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"stdout\n", b"stderr\n"

    process = FakeProcess()

    async def create_process(*argv: str, **kwargs: Any) -> FakeProcess:
        assert argv == ("fake-cli", "health")
        assert kwargs["stdout"] is asyncio.subprocess.PIPE
        assert kwargs["stderr"] is asyncio.subprocess.PIPE
        return process

    monkeypatch.setattr(flowkit.asyncio, "create_subprocess_exec", create_process)

    result = await flowkit._run_process(["fake-cli", "health"], timeout_s=3)

    assert result == (7, "stdout\n", "stderr\n")


@pytest.mark.asyncio
async def test_run_process_kills_and_reaps_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A timed-out process is killed, reaped, and mapped to code 124."""

    class FakeProcess:
        returncode = None

        def __init__(self) -> None:
            self.killed = False
            self.communicate_calls = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            self.communicate_calls += 1
            return b"late stdout", b"late stderr"

        def kill(self) -> None:
            self.killed = True

    process = FakeProcess()

    async def create_process(*argv: str, **kwargs: Any) -> FakeProcess:
        return process

    async def timeout_wait_for(
        awaitable: Coroutine[Any, Any, tuple[bytes, bytes]],
        timeout: int,
    ) -> tuple[bytes, bytes]:
        assert timeout == 4
        awaitable.close()
        raise asyncio.TimeoutError

    monkeypatch.setattr(flowkit.asyncio, "create_subprocess_exec", create_process)
    monkeypatch.setattr(flowkit.asyncio, "wait_for", timeout_wait_for)

    result = await flowkit._run_process(["slow-cli"], timeout_s=4)

    assert result == (124, "", "timeout after 4s")
    assert process.killed is True
    assert process.communicate_calls == 1


@pytest.mark.asyncio
async def test_run_flowkit_cli_returns_cli_staging_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed SSH staging step stops before command execution."""
    staging_error = {
        "ok": False,
        "error_kind": "flowkit_error",
        "error": "scp unavailable",
    }
    run_mock_calls: list[list[str]] = []

    async def stage_cli() -> dict[str, Any]:
        return staging_error

    async def run_process(
        argv: list[str], *, timeout_s: int = 600
    ) -> tuple[int, str, str]:
        run_mock_calls.append(argv)
        return 0, '{"ok": true}', ""

    monkeypatch.setattr(flowkit, "_is_pro", lambda: False)
    monkeypatch.setattr(flowkit, "_stage_cli_for_pro", stage_cli)
    monkeypatch.setattr(flowkit, "_run_process", run_process)

    result = await flowkit._run_flowkit_cli(["health"])

    assert result is staging_error
    assert run_mock_calls == []


@pytest.mark.asyncio
async def test_stage_cli_reports_missing_local_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A missing bridge file is a structured error, not an SCP attempt."""
    monkeypatch.setattr(flowkit, "LOCAL_CLI", tmp_path / "missing-flowkit-cli.py")

    result = await flowkit._stage_cli_for_pro()

    assert result is not None
    assert result["ok"] is False
    assert "missing locally" in result["error"]


@pytest.mark.asyncio
async def test_ssh_mkdir_surfaces_remote_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SSH directory creation failures preserve remote stderr and code."""

    async def run_process(
        argv: list[str], *, timeout_s: int = 600
    ) -> tuple[int, str, str]:
        assert argv[-3:] == ["mkdir", "-p", "/tmp/stage"]
        assert timeout_s == 30
        return 255, "", "connection refused"

    monkeypatch.setattr(flowkit, "_run_process", run_process)

    result = await flowkit._ssh_mkdir("/tmp/stage")

    assert result == {
        "ok": False,
        "error_kind": "flowkit_error",
        "error": "Failed to create Pro staging directory: connection refused",
        "returncode": 255,
    }


@pytest.mark.asyncio
async def test_stage_cli_surfaces_scp_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The CLI staging adapter reports an SCP failure without ambiguity."""
    local_cli = tmp_path / "flowkit_cli.py"
    local_cli.write_text("# bridge\n", encoding="utf-8")
    monkeypatch.setattr(flowkit, "LOCAL_CLI", local_cli)

    async def ssh_mkdir(path: str) -> None:
        return None

    async def run_process(
        argv: list[str], *, timeout_s: int = 600
    ) -> tuple[int, str, str]:
        assert argv == [
            "scp",
            str(local_cli),
            f"{flowkit.PRO_ALIAS}:{flowkit.PRO_REMOTE_CLI}",
        ]
        assert timeout_s == 30
        return 1, "", "permission denied"

    monkeypatch.setattr(flowkit, "_ssh_mkdir", ssh_mkdir)
    monkeypatch.setattr(flowkit, "_run_process", run_process)

    result = await flowkit._stage_cli_for_pro()

    assert result is not None
    assert result["returncode"] == 1
    assert result["error"] == "Failed to stage FlowKit CLI on Pro: permission denied"


@pytest.mark.asyncio
async def test_stage_local_file_surfaces_asset_scp_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A local asset remains identified when its remote SCP staging fails."""
    local_asset = tmp_path / "hero.png"
    local_asset.write_bytes(b"not-a-real-image")
    monkeypatch.setattr(flowkit, "_is_pro", lambda: False)
    monkeypatch.setattr(flowkit.uuid, "uuid4", lambda: type("U", (), {"hex": "asset-id"})())

    async def ssh_mkdir(path: str) -> None:
        assert path == "/tmp/nuz-flowkit-assets/asset-id"
        return None

    async def run_process(
        argv: list[str], *, timeout_s: int = 600
    ) -> tuple[int, str, str]:
        assert argv[0] == "scp"
        assert argv[-1].endswith("/asset-id/hero.png")
        assert timeout_s == 60
        return 23, "", "copy interrupted"

    monkeypatch.setattr(flowkit, "_ssh_mkdir", ssh_mkdir)
    monkeypatch.setattr(flowkit, "_run_process", run_process)

    staged_path, error = await flowkit._stage_local_file_for_pro(str(local_asset))

    assert staged_path == str(local_asset)
    assert error is not None
    assert error["returncode"] == 23
    assert error["error"] == "Failed to stage asset on Pro: copy interrupted"


@pytest.mark.asyncio
async def test_copy_output_surfaces_scp_failure_and_remote_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Copy-back errors retain the remote output for manual recovery."""
    monkeypatch.setattr(flowkit, "_is_pro", lambda: False)
    local_dest = tmp_path / "nested" / "render.mp4"

    async def run_process(
        argv: list[str], *, timeout_s: int = 600
    ) -> tuple[int, str, str]:
        assert argv == [
            "scp",
            f"{flowkit.PRO_ALIAS}:/tmp/output/render.mp4",
            str(local_dest),
        ]
        assert timeout_s == 120
        return 1, "", "disk full"

    monkeypatch.setattr(flowkit, "_run_process", run_process)

    result = await flowkit._copy_output_from_pro(
        "/tmp/output/render.mp4",
        str(local_dest),
    )

    assert local_dest.parent.is_dir()
    assert result is not None
    assert result["returncode"] == 1
    assert result["remote_path"] == "/tmp/output/render.mp4"
    assert "copy-back failed: disk full" in result["error"]
