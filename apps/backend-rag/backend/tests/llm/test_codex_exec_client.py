"""Offline tests for `backend.llm.codex_exec_client`.

Every test fakes at the SUBPROCESS boundary (W114 discipline): the fake
`asyncio.create_subprocess_exec` speaks either the MEASURED wire shape
captured from the historical designated R25 re-measure (2026-08-15, see
`codex_exec_client.py`'s module docstring point 7 and the ADR §30), or an
honestly-labelled CONSTRUCTED shape for paths that were not (and, in this
offline/no-wiring phase, should not be) empirically triggered — never an
imagined shape presented as measured. No test performs a real subprocess
call; `codex` need not be installed to run this file.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import time

import pytest

from backend.llm import codex_exec_client as client_module
from backend.llm.codex_exec_client import (
    MODEL_LUNA,
    MODEL_SOL,
    MODEL_TERRA,
    CodexExecAmbiguousError,
    CodexExecAuthError,
    CodexExecClient,
    CodexExecCommunicationError,
    CodexExecModelNotAllowedError,
    CodexExecOutputShapeError,
    CodexExecPolicyBlockedError,
    CodexExecProcessError,
    CodexExecQuotaError,
    CodexExecResult,
    CodexExecTimeoutError,
    CodexExecUnavailableError,
    MatchConfidence,
    OutputShapeReason,
)

# ---------------------------------------------------------------------------
# MEASURED fixtures — R25 RE-MEASURE (2026-08-15 THAW round, R25-1). The
# original R24 probe (`... --skip-git-repo-check -m gpt-5.6-terra -`, no
# `--ignore-user-config`) measured a stderr transcript that included
# `hook: SessionStart` / `hook: UserPromptSubmit` lines — GLM's R25-1 finding
# flagged those as a host-level hook receiving the prompt OUTSIDE the model
# sandbox. The client's argv now adds `--ignore-user-config`
# (`codex_exec_client.py::_FIXED_ARGV_PREFIX`), and this fixture is the
# HISTORICAL R25 RE-MEASURED probe with that flag: `printf 'Reply with exactly PONG' |
# codex exec --sandbox read-only --skip-git-repo-check --ignore-user-config
# -m gpt-5.6-terra -`, cwd `/tmp/codex-probe-neutral-r25`, 2026-08-15,
# codex-cli 0.147.0, exit_code=0 — stdout unchanged (`PONG\n` only), stderr
# now carries ZERO `hook:` lines. The 2026-08-18 R28 probe exercised the
# adapter's final argv (which additionally fixes `--ephemeral` and
# `--ignore-rules`) and measured exact output plus searched persistence
# surfaces, but intentionally did not retain a new stderr transcript. This
# fixture therefore remains labelled R25 rather than being rewritten as
# imagined R28 evidence. See module docstring points 1 and 7.
# ---------------------------------------------------------------------------
_MEASURED_PROMPT = "Reply with exactly PONG"
_MEASURED_SUCCESS_STDOUT = b"PONG\n"
_MEASURED_SUCCESS_STDERR = (
    b"OpenAI Codex v0.147.0\n"
    b"--------\n"
    b"workdir: /private/tmp/codex-probe-neutral-r25\n"
    b"model: gpt-5.6-terra\n"
    b"provider: openai\n"
    b"approval: never\n"
    b"sandbox: read-only\n"
    b"reasoning effort: none\n"
    b"reasoning summaries: none\n"
    b"session id: 01a0054a-a5f9-7d82-9df4-a7417f528127\n"
    b"--------\n"
    b"user\n"
    b"Reply with exactly PONG\n"
    b"warning: Skill descriptions were shortened to fit the skills context budget. "
    b"Codex can still see every skill, but some descriptions are shorter. Disable "
    b"unused skills or plugins to leave more room for the rest.\n"
    b"codex\n"
    b"PONG\n"
    b"tokens used\n"
    b"25.207\n"
)

# ---------------------------------------------------------------------------
# CONSTRUCTED fixtures — NOT measured against a real auth failure (see module
# docstring point 5's "UNMEASURED" callout). Built from `codex login
# status`'s measured "Not logged in" string plus the house
# `claude_oauth_client.py` auth-diagnostic pattern.
# ---------------------------------------------------------------------------
_CONSTRUCTED_AUTH_FAIL_STDERR = b"Error: Not logged in. Run `codex login` to authenticate.\n"
_CONSTRUCTED_GENERIC_FAIL_STDERR = b"Error: network request failed (connect timeout)\n"


class _FakeProcess:
    """Stand-in for the `asyncio.subprocess.Process` object.

    `communicate()` returns the configured (stdout, stderr) pair after an
    optional artificial delay (for timeout tests). `kill()`/`wait()` are
    recorded so timeout tests can assert the process was actually reaped,
    not just abandoned.
    """

    def __init__(
        self,
        stdout: bytes,
        stderr: bytes,
        returncode: int,
        *,
        communicate_delay: float = 0.0,
        communicate_raises: BaseException | None = None,
        wait_delay: float = 0.0,
    ) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        # A real `asyncio.subprocess.Process` always has a pid; the fake
        # must too (PR-6: `_kill_and_reap` calls `os.getpgid(proc.pid)`).
        # OUR OWN pid is the one safe fake value: its pgid equals the test
        # runner's, so the group-kill guard SKIPS it — a made-up number
        # could name a real, innocent process group on the machine.
        self.pid = os.getpid()
        self._delay = communicate_delay
        self._communicate_raises = communicate_raises
        self._wait_delay = wait_delay
        self.received_input: bytes | None = None
        self.killed = False
        self.waited = False
        self.wait_completed = False

    async def communicate(self, input: bytes | None = None) -> tuple[bytes, bytes]:  # noqa: A002
        self.received_input = input
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._communicate_raises is not None:
            raise self._communicate_raises
        return self._stdout, self._stderr

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        self.waited = True
        if self._wait_delay:
            await asyncio.sleep(self._wait_delay)
        self.wait_completed = True
        return self.returncode


class _FakeSubprocessExec:
    """Records every call so tests can assert on argv/cwd/env, and returns
    a queued `_FakeProcess` (or raises a queued exception)."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._queue: list[_FakeProcess | Exception] = []

    def queue(self, result: _FakeProcess | Exception) -> None:
        self._queue.append(result)

    async def __call__(self, *argv: str, cwd: str, env: dict, **kwargs) -> _FakeProcess:
        self.calls.append({"argv": list(argv), "cwd": cwd, "env": env, "kwargs": kwargs})
        result = self._queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def fake_exec(monkeypatch: pytest.MonkeyPatch) -> _FakeSubprocessExec:
    fake = _FakeSubprocessExec()
    monkeypatch.setattr(client_module.asyncio, "create_subprocess_exec", fake)
    return fake


def _make_available_client(tmp_path, **kwargs) -> CodexExecClient:
    """Construct a client whose `available` is True: a fake executable
    binary and a non-empty fake `auth.json` under a fake `codex_home`."""
    binary = tmp_path / "codex"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    codex_home = tmp_path / "codex_home"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text('{"auth_mode": "chatgpt"}')
    return CodexExecClient(binary=str(binary), codex_home=str(codex_home), **kwargs)


# ---------------------------------------------------------------------------
# Invariant 3 — `available` fail-closed, never raises
# ---------------------------------------------------------------------------


class TestAvailable:
    def test_innocence_binary_and_auth_present(self, tmp_path) -> None:
        client = _make_available_client(tmp_path)
        assert client.available is True

    def test_guilt_binary_missing(self, tmp_path) -> None:
        codex_home = tmp_path / "codex_home"
        codex_home.mkdir()
        (codex_home / "auth.json").write_text("{}")
        client = CodexExecClient(
            binary=str(tmp_path / "does-not-exist"), codex_home=str(codex_home)
        )
        assert client.available is False

    def test_guilt_auth_file_missing(self, tmp_path) -> None:
        binary = tmp_path / "codex"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
        codex_home = tmp_path / "codex_home_empty"
        codex_home.mkdir()
        client = CodexExecClient(binary=str(binary), codex_home=str(codex_home))
        assert client.available is False

    def test_guilt_auth_file_empty(self, tmp_path) -> None:
        binary = tmp_path / "codex"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
        codex_home = tmp_path / "codex_home"
        codex_home.mkdir()
        (codex_home / "auth.json").write_text("")
        client = CodexExecClient(binary=str(binary), codex_home=str(codex_home))
        assert client.available is False

    def test_guilt_binary_not_executable(self, tmp_path) -> None:
        binary = tmp_path / "codex"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o644)  # not executable
        codex_home = tmp_path / "codex_home"
        codex_home.mkdir()
        (codex_home / "auth.json").write_text("{}")
        client = CodexExecClient(binary=str(binary), codex_home=str(codex_home))
        assert client.available is False

    def test_construction_never_raises_when_unavailable(self, tmp_path) -> None:
        # Must not raise even with nonsense paths.
        client = CodexExecClient(binary="/nonexistent/nowhere", codex_home="/nonexistent/home")
        assert client.available is False

    def test_guilt_embedded_nul_binary_fails_closed(self) -> None:
        client = CodexExecClient(binary="codex\0binary", codex_home="/nonexistent/home")
        assert client.available is False

    def test_guilt_embedded_nul_codex_home_fails_closed(self, tmp_path) -> None:
        binary = tmp_path / "codex"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
        client = CodexExecClient(binary=str(binary), codex_home="codex\0home")
        assert client.available is False

    def test_env_var_binary_override(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        binary = tmp_path / "codex"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
        codex_home = tmp_path / "codex_home"
        codex_home.mkdir()
        (codex_home / "auth.json").write_text("{}")
        monkeypatch.setenv(client_module._ENV_BIN, str(binary))
        client = CodexExecClient(codex_home=str(codex_home))
        assert client.available is True


# ---------------------------------------------------------------------------
# Constructor validation (beyond the 7 binding invariants) — model allowlist
# (R25-6 doc fix, 2026-08-15 THAW round: the module docstring defines
# exactly 7 numbered invariants; the original "Invariant 8/9" section
# headers here referenced a taxonomy the module never had.)
# ---------------------------------------------------------------------------


class TestModelAllowlist:
    def test_innocence_all_three_candidates_construct(self) -> None:
        for model in (MODEL_SOL, MODEL_TERRA, MODEL_LUNA):
            client = CodexExecClient(model=model)
            assert client._model == model

    def test_guilt_bad_model_at_construction(self) -> None:
        with pytest.raises(CodexExecModelNotAllowedError):
            CodexExecClient(model="gpt-4o")

    @pytest.mark.asyncio
    async def test_guilt_bad_model_per_call_override(
        self, tmp_path, fake_exec: _FakeSubprocessExec
    ) -> None:
        client = _make_available_client(tmp_path)
        with pytest.raises(CodexExecModelNotAllowedError):
            await client.generate("hello", model="not-a-real-model")
        assert fake_exec.calls == []  # never launched


# ---------------------------------------------------------------------------
# Constructor validation (beyond the 7 binding invariants) — timeout
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    @pytest.mark.parametrize("bad_timeout", [0, -1, float("inf"), float("nan"), True, "60"])
    def test_guilt_bad_timeout(self, bad_timeout) -> None:
        with pytest.raises(ValueError):
            CodexExecClient(timeout_s=bad_timeout)

    def test_innocence_good_timeout(self) -> None:
        client = CodexExecClient(timeout_s=30.5)
        assert client._timeout_s == 30.5


# ---------------------------------------------------------------------------
# R25-7 — prompt validation through generate() (fails BEFORE any subprocess
# touch)
# ---------------------------------------------------------------------------


class TestPromptValidation:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_prompt", ["", "   ", "\n\t "])
    async def test_guilt_empty_or_whitespace_prompt(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
        bad_prompt: str,
    ) -> None:
        client = _make_available_client(tmp_path)
        with pytest.raises(ValueError):
            await client.generate(bad_prompt)
        assert fake_exec.calls == []  # never launched

    @pytest.mark.asyncio
    async def test_innocence_nonempty_prompt_proceeds(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(_MEASURED_SUCCESS_STDOUT, _MEASURED_SUCCESS_STDERR, 0))
        result = await client.generate(_MEASURED_PROMPT)
        assert result.text == "PONG"


# ---------------------------------------------------------------------------
# Invariant 1/2 — subprocess shape: argv, stdin, neutral cwd, no shell
# ---------------------------------------------------------------------------


class TestSubprocessShape:
    @pytest.mark.asyncio
    async def test_innocence_argv_shape_and_stdin_prompt(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(_MEASURED_SUCCESS_STDOUT, _MEASURED_SUCCESS_STDERR, 0))

        result = await client.generate(_MEASURED_PROMPT)

        assert isinstance(result, CodexExecResult)
        assert result.text == "PONG"
        assert result.model == MODEL_TERRA

        [call] = fake_exec.calls
        argv = call["argv"]
        assert argv[0].endswith("codex")
        assert argv[1:] == [
            "exec",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "-m",
            MODEL_TERRA,
            "-",
        ]

        # W115 guard: the prompt text must never appear in argv.
        assert not any(_MEASURED_PROMPT in arg for arg in argv)

    @pytest.mark.asyncio
    async def test_innocence_prompt_delivered_via_stdin(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = _make_available_client(tmp_path)
        proc = _FakeProcess(_MEASURED_SUCCESS_STDOUT, _MEASURED_SUCCESS_STDERR, 0)
        fake_exec.queue(proc)

        await client.generate(_MEASURED_PROMPT)

        assert proc.received_input == _MEASURED_PROMPT.encode("utf-8")

    @pytest.mark.asyncio
    async def test_innocence_cwd_is_fresh_and_removed_after(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(_MEASURED_SUCCESS_STDOUT, _MEASURED_SUCCESS_STDERR, 0))

        await client.generate(_MEASURED_PROMPT)

        [call] = fake_exec.calls
        cwd = call["cwd"]
        assert cwd != str(tmp_path)  # never the caller's own dir
        assert "codex-exec-wa-" in cwd
        # cleaned up in the `finally` block:
        assert not os.path.isdir(cwd)

    @pytest.mark.asyncio
    async def test_innocence_env_is_minimal(self, tmp_path, fake_exec: _FakeSubprocessExec) -> None:
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(_MEASURED_SUCCESS_STDOUT, _MEASURED_SUCCESS_STDERR, 0))

        await client.generate(_MEASURED_PROMPT)

        [call] = fake_exec.calls
        env = call["env"]
        # Only the small safelist plus CODEX_HOME (always injected now,
        # R25-2) — never a blanket copy of os.environ.
        assert set(env).issubset({"PATH", "HOME", "TERM", "LANG", "LC_ALL", "TMPDIR", "CODEX_HOME"})
        assert env.get("CODEX_HOME") == str(client._resolve_codex_home())

    @pytest.mark.asyncio
    async def test_guilt_per_call_model_override_reflected_in_argv(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = _make_available_client(tmp_path)  # default model MODEL_TERRA
        fake_exec.queue(_FakeProcess(_MEASURED_SUCCESS_STDOUT, _MEASURED_SUCCESS_STDERR, 0))

        result = await client.generate(_MEASURED_PROMPT, model=MODEL_SOL)

        assert result.model == MODEL_SOL
        [call] = fake_exec.calls
        assert "-m" in call["argv"]
        assert call["argv"][call["argv"].index("-m") + 1] == MODEL_SOL
        assert MODEL_TERRA not in call["argv"]


# ---------------------------------------------------------------------------
# R25-2/R25-7 — env-tier CODEX_HOME/WA_CODEX_BIN: the `available` gate and
# the actually-spawned subprocess must agree by construction (2026-08-15
# THAW round).
# ---------------------------------------------------------------------------


class TestEnvTierResolution:
    def test_guilt_codex_home_env_var_drives_both_available_and_child_env(
        self,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """R25-2 regression: before the fix, `available` honored the
        `CODEX_HOME` env var but `_build_env` injected `CODEX_HOME` into the
        child ONLY when the constructor received an explicit `codex_home=`
        argument — a client constructed with the env var alone could pass
        `available` while the actual subprocess saw no `CODEX_HOME` override
        at all. This test constructs the client with ONLY the env var (no
        explicit `codex_home=`) and asserts both sides agree — a mismatch is
        now structurally impossible (`_build_env` calls the same
        `_resolve_codex_home()` the gate uses)."""
        binary = tmp_path / "codex"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
        codex_home = tmp_path / "codex_home"
        codex_home.mkdir()
        (codex_home / "auth.json").write_text("{}")
        monkeypatch.setenv(client_module._ENV_CODEX_HOME, str(codex_home))

        client = CodexExecClient(binary=str(binary))  # no explicit codex_home=

        assert client.available is True
        env = client._build_env()
        assert env["CODEX_HOME"] == str(codex_home)

    @pytest.mark.asyncio
    async def test_guilt_wa_codex_bin_honored_at_generate_time(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`WA_CODEX_BIN` must be the binary actually launched, not merely
        the one `available` checks."""
        binary = tmp_path / "codex-via-env"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
        codex_home = tmp_path / "codex_home"
        codex_home.mkdir()
        (codex_home / "auth.json").write_text("{}")
        monkeypatch.setenv(client_module._ENV_BIN, str(binary))
        fake_exec.queue(_FakeProcess(_MEASURED_SUCCESS_STDOUT, _MEASURED_SUCCESS_STDERR, 0))

        client = CodexExecClient(codex_home=str(codex_home))  # no explicit binary=
        assert client.available is True

        await client.generate(_MEASURED_PROMPT)

        [call] = fake_exec.calls
        assert call["argv"][0] == str(binary)

    @pytest.mark.asyncio
    async def test_guilt_relative_codex_home_resolves_absolute_and_agrees(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """R27-2 (GLM F4) regression: a RELATIVE `codex_home=` used to stay
        relative through `_resolve_codex_home`, re-opening the R25-2
        gate/child divergence — `available` (the gate) resolves a relative
        `Path` against the CALLING process's cwd at property-access time,
        while the spawned child always runs from a fresh NEUTRAL TEMPDIR cwd
        (point 1) — so the same relative string meant two DIFFERENT
        directories depending on WHEN it was resolved. This test chdir's
        into `tmp_path`, constructs the client with a RELATIVE `codex_home=`
        value, and asserts: (1) `available` still resolves it correctly
        (proving the gate doesn't silently fail on a relative value), (2)
        `_resolve_codex_home()` returns an ABSOLUTE path, and (3) the actual
        child env sees that SAME absolute path — gate and child agree by
        construction, exactly like the R25-2 fix this extends."""
        binary = tmp_path / "codex"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
        codex_home_abs = tmp_path / "codex_home"
        codex_home_abs.mkdir()
        (codex_home_abs / "auth.json").write_text('{"auth_mode": "chatgpt"}')

        monkeypatch.chdir(tmp_path)
        relative_home = "codex_home"  # relative to tmp_path, the cwd just entered

        client = CodexExecClient(binary=str(binary), codex_home=relative_home)

        assert client.available is True
        resolved = client._resolve_codex_home()
        assert resolved.is_absolute()
        assert resolved == codex_home_abs.resolve()

        fake_exec.queue(_FakeProcess(b"PONG\n", b"", 0))
        await client.generate("hello")

        [call] = fake_exec.calls
        assert call["env"]["CODEX_HOME"] == str(codex_home_abs.resolve())


# ---------------------------------------------------------------------------
# Invariant 4 — output contract (measured success shape + shape errors)
# ---------------------------------------------------------------------------


class TestOutputContract:
    @pytest.mark.asyncio
    async def test_innocence_measured_success_shape(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(_MEASURED_SUCCESS_STDOUT, _MEASURED_SUCCESS_STDERR, 0))

        result = await client.generate(_MEASURED_PROMPT)

        assert result.text == "PONG"
        assert result.latency_ms >= 0.0

    @pytest.mark.asyncio
    async def test_guilt_empty_stdout_on_exit_zero(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """Ruling A (B2b): the classic transient — retrying is likely to
        help — is distinguished from an oversized-output failure via
        `reason=OutputShapeReason.EMPTY`."""
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"", b"", 0))

        with pytest.raises(CodexExecOutputShapeError) as exc_info:
            await client.generate("hello")
        assert exc_info.value.reason is OutputShapeReason.EMPTY

    @pytest.mark.asyncio
    async def test_guilt_whitespace_only_stdout_on_exit_zero(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"   \n\t  ", b"", 0))

        with pytest.raises(CodexExecOutputShapeError) as exc_info:
            await client.generate("hello")
        assert exc_info.value.reason is OutputShapeReason.EMPTY

    # -- Ruling A (B2b): oversized-output is the OTHER OUTPUT_INVALID
    #    sub-cause, reached via a non-zero exit + a structured payload-size
    #    signal in stderr — NOT via the exit-0 empty-stdout path above. Its
    #    retry semantics are OPPOSITE: the same prompt reproduces this, so
    #    a caller must truncate/reprompt rather than blind-retry. --

    @pytest.mark.asyncio
    async def test_guilt_oversized_output_reclassified_from_resource_exhausted(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """Refuter finding §2 (over-match): `RESOURCE_EXHAUSTED: received
        message larger than max (...)` was previously read as `QUOTA` via
        bare `resource_exhausted` — a payload-size failure, not account
        quota. B2b reclassifies this exact reproduced string as
        `OUTPUT_INVALID`/`oversized`, never `QUOTA`."""
        client = _make_available_client(tmp_path)
        stderr = b"RESOURCE_EXHAUSTED: received message larger than max (4194304 vs. 1048576)\n"
        fake_exec.queue(_FakeProcess(b"", stderr, 1))

        with pytest.raises(CodexExecOutputShapeError) as exc_info:
            await client.generate("hello")
        assert exc_info.value.reason is OutputShapeReason.OVERSIZED

    @pytest.mark.asyncio
    async def test_innocence_bare_resource_exhausted_stays_unknown(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """SPEC P5 ("unknown stays unknown"): bare `RESOURCE_EXHAUSTED` with
        no size-qualifying context is genuinely ambiguous between quota and
        payload-size (gRPC/Google API convention uses this status code for
        BOTH) with no anchor either way for this CLI — deliberately left
        unmatched rather than guessed at either meaning."""
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"", b"RESOURCE_EXHAUSTED\n", 1))

        with pytest.raises(CodexExecProcessError):
            await client.generate("hello")

    @pytest.mark.asyncio
    async def test_innocence_multiline_answer_preserved_trimmed(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"\n  line one\nline two  \n", b"", 0))

        result = await client.generate("hello")

        assert result.text == "line one\nline two"


# ---------------------------------------------------------------------------
# Invariant 5 — auth-death detection, scoped and prompt-scrubbed
# ---------------------------------------------------------------------------


class TestAuthDeathDetection:
    @pytest.mark.asyncio
    async def test_guilt_constructed_auth_failure_raises_distinct_error(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"", _CONSTRUCTED_AUTH_FAIL_STDERR, 1))

        with pytest.raises(CodexExecAuthError):
            await client.generate("hello")

    @pytest.mark.asyncio
    async def test_guilt_generic_failure_raises_process_error_not_auth(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"", _CONSTRUCTED_GENERIC_FAIL_STDERR, 1))

        with pytest.raises(CodexExecProcessError) as exc_info:
            await client.generate("hello")
        assert exc_info.value.exit_code == 1

    @pytest.mark.asyncio
    async def test_innocence_success_path_never_scanned_for_auth_words(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """Guard against cicatrix family #3 over-match: a legitimate WA
        answer discussing an expired KITAS / portal login must NOT be
        misclassified as this client's own auth-death, because
        `exit_code == 0` never triggers the auth scan at all."""
        client = _make_available_client(tmp_path)
        answer = (
            b"Your KITAS login has expired; you are unauthorized until renewal (401 on the portal)."
        )
        fake_exec.queue(_FakeProcess(answer, b"", 0))

        result = await client.generate("what does expired KITAS login mean")

        assert "expired" in result.text
        assert "unauthorized" in result.text

    @pytest.mark.asyncio
    async def test_innocence_echoed_prompt_does_not_false_positive_on_failure(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """A failing run whose stderr echoes a client prompt that itself
        contains auth-shaped words (real WA traffic: "my login is
        unauthorized, error 401") must not be misclassified as THIS
        client's own auth-death — only genuine auth-failure wording OUTSIDE
        the echoed prompt should trigger `CodexExecAuthError`."""
        client = _make_available_client(tmp_path)
        prompt = "why is my login unauthorized, I got error 401 on the imigrasi portal"
        stderr = b"user\n" + prompt.encode() + b"\nsome unrelated network error\n"
        fake_exec.queue(_FakeProcess(b"", stderr, 1))

        with pytest.raises(CodexExecProcessError):
            await client.generate(prompt)

    @pytest.mark.asyncio
    async def test_guilt_auth_word_outside_echoed_prompt_still_detected(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """Companion to the prior test: stripping the echoed prompt must not
        blind the scanner to a genuine auth failure that appears OUTSIDE the
        echoed prompt block."""
        client = _make_available_client(tmp_path)
        prompt = "tell me about visa renewal"
        stderr = b"user\n" + prompt.encode() + b"\nError: token_revoked\n"
        fake_exec.queue(_FakeProcess(b"", stderr, 1))

        with pytest.raises(CodexExecAuthError):
            await client.generate(prompt)

    # -- R27-1 (GLM F3): the pre-fix `_strip_known_lines` ALSO dropped a
    #    stderr line whenever it was a SUBSTRING of a known line, not just an
    #    exact match — its own fail-open, symmetric to the R26-2 mangle bug --

    @pytest.mark.asyncio
    async def test_guilt_diagnostic_substring_of_prompt_line_still_pages(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """R27-1 (GLM F3) regression: the PRE-fix `_strip_known_lines` dropped
        a stderr line whenever it was merely a SUBSTRING of a known (prompt
        or stdout) line — not just an exact match. Real WA traffic: a client
        prompt phrased as "why am I not logged in after midnight, is this
        urgent?" literally CONTAINS the substring "not logged in" — if the
        genuine diagnostic line "not logged in" then appears INDEPENDENTLY
        in stderr (an actual auth failure, unrelated to how the client
        phrased their question), the old containment check saw it as
        "contained in" the known prompt line and silently dropped it,
        silencing a page that should have fired. Equality-only stripping
        (R27-1 fix) keeps this shorter, genuinely diagnostic line — it is
        never dropped just because it happens to be textually contained in a
        longer known line."""
        client = _make_available_client(tmp_path)
        prompt = "why am I not logged in after midnight, is this urgent?"
        stderr = b"user\n" + prompt.encode() + b"\nnot logged in\n"
        fake_exec.queue(_FakeProcess(b"", stderr, 1))

        with pytest.raises(CodexExecAuthError):
            await client.generate(prompt)

    @pytest.mark.asyncio
    async def test_innocence_genuine_echoed_line_still_dropped_under_equality_only(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """Companion to the prior test: the R27-1 narrowing to equality-only
        must NOT regress the original defusal — a stderr line that is an
        EXACT echo of the prompt (not merely a substring relationship) is
        still dropped and must not false-page, even though it too contains
        auth-shaped vocabulary."""
        client = _make_available_client(tmp_path)
        prompt = "why am I not logged in after midnight, is this urgent?"
        stderr = b"user\n" + prompt.encode() + b"\nsome unrelated network error\n"
        fake_exec.queue(_FakeProcess(b"", stderr, 1))

        with pytest.raises(CodexExecProcessError):
            await client.generate(prompt)

    # -- R25-3: bare "401" false-positive removed; context-anchored instead --

    @pytest.mark.asyncio
    async def test_innocence_bare_401_digits_do_not_page(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """PINNED (R25-3, mandate-specified case): a generic failure whose
        stderr happens to contain the digits "401" in an unrelated context
        (a latency measurement) must NOT be classified as auth-death."""
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"", b"completed after 401 ms\n", 1))

        with pytest.raises(CodexExecProcessError):
            await client.generate("hello")

    @pytest.mark.asyncio
    async def test_guilt_genuine_401_unauthorized_shape_pages(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """PINNED (R25-3, mandate-specified case): a genuine
        `401 unauthorized` shape must still page."""
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"", b"Error: 401 unauthorized\n", 1))

        with pytest.raises(CodexExecAuthError):
            await client.generate("hello")

    @pytest.mark.asyncio
    async def test_guilt_echoed_stdout_line_prevents_boundary_false_positive(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """R25-3(a) regression, RE-EXPRESSED line-based under R26-2 (the
        original version of this test used an intra-line concatenation that
        the R26-2 line-based rewrite no longer defuses the same way — see
        `test_guilt_bare_common_word_stdout_does_not_mangle_stderr_scan`
        below for why intra-line substring stripping had to go). This
        version matches the MEASURED wire shape (point 4/7): the run's own
        stdout is echoed as its OWN complete line in stderr, with role-marker
        lines ("user"/"codex") around it. If that echoed line survived in
        the stderr scan text, an innocuous answer ending in "...was not"
        directly ADJACENT to an unrelated stderr-only line starting with
        "logged in..." would risk `\\s+` in `_AUTH_DEATH_RE` (which matches
        newlines too) bridging the two lines into a false "not logged in"
        match. Dropping the ENTIRE echoed stdout line removes "not" from the
        scan text altogether, so no bridge can form — the "user"/"codex"
        marker lines that survive between the stdout portion and the
        remaining stderr text act as an extra non-whitespace buffer too."""
        client = _make_available_client(tmp_path)
        stdout = b"the appointment was not"
        stderr = (
            b"user\nhello\ncodex\n" + stdout + b"\nlogged in the calendar system, please retry.\n"
        )
        fake_exec.queue(_FakeProcess(stdout, stderr, 1))

        with pytest.raises(CodexExecProcessError):
            await client.generate("hello")

    @pytest.mark.asyncio
    async def test_innocence_echoed_401_unauthorized_prompt_does_not_false_positive(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """R25-3 protection, RECONFIRMED under the R26-2 line-based rewrite:
        real WA traffic — a client literally typing "401 unauthorized" while
        describing their OWN portal error — is echoed verbatim into stderr
        on a failing run and must not be misclassified as THIS client's own
        auth-death."""
        client = _make_available_client(tmp_path)
        prompt = "my portal says 401 unauthorized when I try to renew, what do I do"
        stderr = b"user\n" + prompt.encode() + b"\ncodex\nsome unrelated crash trace\n"
        fake_exec.queue(_FakeProcess(b"", stderr, 1))

        with pytest.raises(CodexExecProcessError):
            await client.generate(prompt)

    @pytest.mark.asyncio
    async def test_guilt_bare_common_word_stdout_does_not_mangle_stderr_scan(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """PINNED (R26-2, agy's mangle scenario, MEDIUM confirmed): the
        pre-R26-2 `_strip_known_texts` did a WHOLE-TEXT `str.replace()` —
        a short/common stdout like "in" would strip every "in" occurrence
        from stderr, including the one INSIDE the genuine diagnostic phrase
        "not logged in", mangling it to "not logged " and making the
        scanner go silent exactly when it must page (fail-OPEN). The
        line-based `_strip_known_lines` rewrite never mutates a surviving
        line — a one-word stdout answer can only cause a WHOLE stderr line
        to be dropped if that whole line equals or is contained in "in",
        which this diagnostic line is not."""
        client = _make_available_client(tmp_path)
        stdout = b"in"
        stderr = b"Error: Not logged in. Run `codex login` to authenticate.\n"
        fake_exec.queue(_FakeProcess(stdout, stderr, 1))

        with pytest.raises(CodexExecAuthError):
            await client.generate("hello")

    # -- R26 addendum (GLM F26-1 HIGH + F26-4): the R26-2 fix above still
    #    concatenated an independently-stripped STDOUT into the scanned
    #    text — a partial answer that discussed the client's OWN
    #    "expired"/"unauthorized" situation could still false-page, and the
    #    join seam between the two streams was itself bridgeable. Unified
    #    fix: scan STDERR ONLY (stdout never enters the scan surface at
    #    all), via `_auth_death_detected`, which searches its argument(s)
    #    independently rather than joining them. --

    @pytest.mark.asyncio
    async def test_innocence_late_failure_partial_stdout_answer_mentions_401_does_not_page(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """GLM F26-1 (HIGH, CONFIRMED): before this fix, `generate()` still
        concatenated `_strip_known_lines(stdout, prompt)` into the scanned
        text — so a LATE failure (`exit_code != 0`) after the model had
        already produced a partial answer discussing the client's own
        "expired"/"unauthorized" KITAS situation would false-page as THIS
        client's own auth-death, even though stderr itself carries no
        diagnostic at all. Stdout must never be part of the scanned text —
        this is the `exit_code != 0` sibling of
        `test_innocence_success_path_never_scanned_for_auth_words` above
        (which only proves the `exit_code == 0` path is safe)."""
        client = _make_available_client(tmp_path)
        stdout = (
            b"Your KITAS login has expired; you are unauthorized until renewal (401 on the portal)."
        )
        stderr = b"process interrupted before completion\n"
        fake_exec.queue(_FakeProcess(stdout, stderr, 1))

        with pytest.raises(CodexExecProcessError):
            await client.generate("what does expired KITAS login mean")

    def test_guilt_boundary_formation_never_bridges_across_independently_searched_texts(
        self,
    ) -> None:
        """GLM F26-4 (MEDIUM, CONFIRMED), RE-EXPRESSED under the B2b
        per-line classifier (`_classify_stderr` supersedes
        `_auth_death_detected`, see that function's docstring): two
        fragments that would JOINTLY form a trigger phrase if concatenated
        ("...was not" + "logged in...") must NOT match when they are two
        SEPARATE LINES of one stderr blob — SPEC P2, classification never
        spans a record boundary. Pins the structural property the module
        docstring and the B2b block comment both describe."""
        fragment_a = "the appointment was not"
        fragment_b = "logged in to the calendar system, please retry"
        # If these were joined with "\n" and searched as ONE string (not
        # split first), "was not\nlogged in" would match `_AUTH_PROSE_RE`'s
        # `not\s+logged\s+in` alternative (`\s+` matches a newline) — the
        # exact seam F26-4 flagged.
        assert client_module._AUTH_PROSE_RE.search(fragment_a + "\n" + fragment_b) is not None
        verdict = client_module._classify_stderr(fragment_a + "\n" + fragment_b)
        assert verdict.winner is None
        assert verdict.ambiguous_classes == frozenset()
        assert client_module._classify_stderr(fragment_a).winner is None
        assert client_module._classify_stderr(fragment_b).winner is None

    # -- R26-3: the backtick-optional tail of the `run codex login` clause,
    #    isolated from every other alternative's vocabulary --

    @pytest.mark.asyncio
    async def test_guilt_run_codex_login_clause_without_backticks(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """Isolated fixture: no other `_AUTH_DEATH_RE` alternative's
        vocabulary appears anywhere in this text — only the `run codex
        login` clause can possibly match."""
        client = _make_available_client(tmp_path)
        stderr = b"Please run codex login now to continue.\n"
        fake_exec.queue(_FakeProcess(b"", stderr, 1))

        with pytest.raises(CodexExecAuthError):
            await client.generate("hello")

    @pytest.mark.asyncio
    async def test_guilt_run_codex_login_clause_with_backticks(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """R26-3 regression target: the backticked form specifically —
        `` `codex login` `` — with NO other matching vocabulary co-occurring
        (unlike `_CONSTRUCTED_AUTH_FAIL_STDERR`, which also contains
        "Not logged in" and could pass even if this specific clause were
        broken)."""
        client = _make_available_client(tmp_path)
        stderr = b"Please run `codex login` now to continue.\n"
        fake_exec.queue(_FakeProcess(b"", stderr, 1))

        with pytest.raises(CodexExecAuthError):
            await client.generate("hello")

    # -- R25-4: under-match — plausible real phrasings that previously
    #    matched nothing, plus innocence for the ordinary-WA-text near-misses
    #    that must keep NOT matching --

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "stderr_text",
        [
            b"Error: token has expired\n",
            b"Error: you need to sign in\n",
            b"Error: session invalidated\n",
            b"Error: sign-in required\n",
            b"Error: sign in required\n",
        ],
    )
    async def test_guilt_new_auth_phrasings_page(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
        stderr_text: bytes,
    ) -> None:
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"", stderr_text, 1))

        with pytest.raises(CodexExecAuthError):
            await client.generate("hello")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "stderr_text",
        [
            b"please sign the form and return it\n",
            b"your passport has expired, please renew\n",
            b"network timeout, please retry\n",
        ],
    )
    async def test_innocence_ordinary_wa_text_near_misses_do_not_page(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
        stderr_text: bytes,
    ) -> None:
        """ "please sign the form" must not match a "sign in" pattern, and
        bare "expired" (without "token has"/"authentication ... ") must not
        page — these are ordinary Indonesian-visa WA vocabulary, not
        diagnostics."""
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"", stderr_text, 1))

        with pytest.raises(CodexExecProcessError):
            await client.generate("hello")


# ---------------------------------------------------------------------------
# Quota / policy-blocked detection (B2a, F3: "auth and quota MUST be
# distinct (today they collapse; split before arming)"). Every trigger
# pattern here is an UNVERIFIED HYPOTHESIS about codex-exec stderr wording
# (see `_QUOTA_RE`/`_POLICY_BLOCKED_RE`'s module-level comments) — these
# tests prove the CODE PATH is reachable given a matching stderr shape, NOT
# that the shape matches real `codex exec` output. Test names say
# "constructed" for the same reason `test_guilt_constructed_auth_failure_
# raises_distinct_error` above does.
# ---------------------------------------------------------------------------


class TestQuotaDetection:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "stderr_text",
        [
            # R28-1 (2026-08-25): "Error: quota exceeded for this billing
            # period" was DROPPED as a guilt fixture — bare "quota
            # exceeded" is now deliberately excluded (reproduced over-match
            # finding, see `_QUOTA_PROSE_RE`'s comment) — replaced with a
            # real under-match target the vocabulary now covers.
            b"Error: you have exceeded your current quota; check your plan and billing details.\n",
            b"429 too many requests: rate limit exceeded\n",
            b"insufficient_quota: you have hit your usage limit\n",
        ],
    )
    async def test_guilt_constructed_quota_failure_raises_distinct_error(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
        stderr_text: bytes,
    ) -> None:
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"", stderr_text, 1))

        with pytest.raises(CodexExecQuotaError):
            await client.generate("hello")

    @pytest.mark.asyncio
    async def test_innocence_success_path_never_scanned_for_quota_words(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """Guard against cicatrix family #3 over-match: a legitimate WA
        answer must NOT be misclassified as this client's own quota
        exhaustion, because `exit_code == 0` never triggers the quota scan
        at all — mirrors `test_innocence_success_path_never_scanned_for_auth_words`.

        Refuter test-defect finding §5 (2026-08-25 correction): the
        pre-B2b version of this fixture ("Your sponsor's KITAS quota is
        exceeded for this year") would NOT have matched the vocabulary
        even if the success path WERE incorrectly scanned ("quota is
        exceeded" is not "quota exceeded"), so the test proved nothing
        about the guard it claimed to cover. This fixture contains a
        genuine `MatchConfidence.HIGH` trigger ("429 too many requests")
        so a regression that starts scanning stdout on success would
        actually be caught here."""
        client = _make_available_client(tmp_path)
        answer = (
            b"The portal logged 429 too many requests while checking your sponsor's "
            b"KITAS quota this year; the limit resets in January."
        )
        fake_exec.queue(_FakeProcess(answer, b"", 0))

        result = await client.generate("what does sponsor quota exceeded mean")

        assert "quota" in result.text

    @pytest.mark.asyncio
    async def test_innocence_ordinary_wa_text_near_misses_do_not_page_as_quota(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """Bare "exhausted"/"limit" wording, plausible ordinary
        WA-immigration vocabulary, must not be misread as quota exhaustion
        — only the anchored multi-word/unambiguous-token phrases in
        `_QUOTA_RE` should page."""
        client = _make_available_client(tmp_path)
        fake_exec.queue(
            _FakeProcess(b"", b"I am exhausted from this process, the daily limit is unclear\n", 1)
        )

        with pytest.raises(CodexExecProcessError):
            await client.generate("hello")

    @pytest.mark.asyncio
    async def test_guilt_auth_and_quota_are_distinct_outcomes(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """F3's core requirement, proven directly on this client: an
        auth-shaped failure raises `CodexExecAuthError`, a quota-shaped
        failure on a SEPARATE call raises `CodexExecQuotaError` — never the
        other. Mirrors `fake_codex_broker.py`'s own named test
        `test_auth_dead_and_quota_are_distinct_outcomes` at the
        codex_exec_client layer."""
        auth_dir = tmp_path / "auth"
        auth_dir.mkdir()
        auth_client = _make_available_client(auth_dir)
        fake_exec.queue(_FakeProcess(b"", _CONSTRUCTED_AUTH_FAIL_STDERR, 1))
        with pytest.raises(CodexExecAuthError):
            await auth_client.generate("hello")

        quota_dir = tmp_path / "quota"
        quota_dir.mkdir()
        quota_client = _make_available_client(quota_dir)
        fake_exec.queue(_FakeProcess(b"", b"Error: insufficient_quota reported by upstream\n", 1))
        with pytest.raises(CodexExecQuotaError):
            await quota_client.generate("hello")


class TestPolicyBlockedDetection:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "stderr_text",
        [
            b"Error: this request violates the usage policy\n",
            # R28-2 (2026-08-25): "safety system refused to respond" was
            # DROPPED as a guilt fixture — bare "safety system" now
            # deliberately excluded (reproduced over-match finding, see
            # `_POLICY_PROSE_RE`'s comment) and bare "refused to respond"
            # (no "... request" object) likewise. Replaced with a fixture
            # that hits the NARROWED, still-reachable vocabulary.
            b"Error: blocked by the safety filter; refused to respond to this request.\n",
        ],
    )
    async def test_guilt_constructed_policy_blocked_failure_raises_distinct_error(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
        stderr_text: bytes,
    ) -> None:
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"", stderr_text, 1))

        with pytest.raises(CodexExecPolicyBlockedError):
            await client.generate("hello")

    @pytest.mark.asyncio
    async def test_innocence_success_path_never_scanned_for_policy_words(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """A legitimate immigration answer must not be misclassified as a
        policy refusal — `exit_code == 0` never triggers the scan at all.

        Refuter test-defect finding §5 (2026-08-25 correction): the pre-B2b
        fixture ("The government policy requires...") would not have
        matched the vocabulary even if scanned. This fixture contains a
        genuine trigger ("cannot assist with that request") so a
        regression that starts scanning stdout on success would actually
        be caught here."""
        client = _make_available_client(tmp_path)
        answer = (
            b"The government policy requires a passport copy; we cannot assist with "
            b"that request outside business hours."
        )
        fake_exec.queue(_FakeProcess(answer, b"", 0))

        result = await client.generate("what does the policy require")

        assert "policy" in result.text

    @pytest.mark.asyncio
    async def test_innocence_ordinary_wa_text_near_misses_do_not_page_as_policy(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """Bare "policy"/"safety" wording, plausible ordinary
        WA-immigration vocabulary, must not be misread as a policy
        refusal."""
        client = _make_available_client(tmp_path)
        fake_exec.queue(
            _FakeProcess(
                b"", b"for your safety, the policy office is closed on weekends\n", 1
            )
        )

        with pytest.raises(CodexExecProcessError):
            await client.generate("hello")

    @pytest.mark.asyncio
    async def test_innocence_bare_safety_system_no_longer_pages(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """R28-2 regression target: this exact string used to be a GUILT
        fixture pre-B2b (it matched two policy alternatives at once,
        masking that neither was a sound anchor — refuter test-defect
        finding §5). "Safety system" over-matches ordinary facilities
        prose ("The office fire safety system is under maintenance" —
        refuter over-match finding §2); "refused to respond" alone (no
        "... request" object) is also too generic. Both were narrowed."""
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"", b"safety system refused to respond\n", 1))

        with pytest.raises(CodexExecProcessError):
            await client.generate("hello")


class TestResidualFailureNotOverclassified:
    @pytest.mark.asyncio
    async def test_innocence_generic_stderr_matches_no_word_class(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """A stderr string engineered to match none of the three word
        classes (auth/quota/policy) still falls through to the pre-existing
        generic `CodexExecProcessError` bucket — proves the three new
        checks did not widen the residual bucket's boundary."""
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"", b"Error: disk write failed unexpectedly\n", 1))

        with pytest.raises(CodexExecProcessError) as exc_info:
            await client.generate("hello")
        assert exc_info.value.exit_code == 1


class TestMultiMatchPrecedence:
    """SUPERSEDES the pre-B2b `TestWordClassDisjointness` (renamed away —
    the old name/docstring described a claim the refuter proved FALSE, not
    a claim this suite still makes). The old
    `test_each_guilt_fixture_matches_exactly_one_word_class` tested each
    vocabulary's OWN alternatives in isolation and reported the
    payload-level disjointness claim settled — per the B2a landing
    commit's own narrative: "That was the weaker test ... it measured the
    wrong thing. The claim is about a stderr LINE, not about a
    vocabulary." SPEC P7 requires testing on realistic COMPOSITE payloads
    instead — every test below constructs one.

    B2b's precedence rule (SPEC P1/P3, see the block comment above
    `MatchConfidence` in `codex_exec_client.py`): a lone
    `MatchConfidence.HIGH` match wins over any number of `.LOW` matches; a
    genuine tie (0 or >=2 classes at HIGH) is `CodexExecAmbiguousError`,
    never guessed.
    """

    @pytest.mark.asyncio
    async def test_guilt_flagship_composite_high_quota_beats_low_auth(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """Refuter finding §1 (Critical, "Ordering"): `Error: token has
        expired; refresh failed with 429 too many requests` is a realistic
        causal chain (expired token -> refresh attempt -> refresh
        rate-limited) that matches BOTH auth (prose "token has expired")
        and quota (structured "429 too many requests") on the SAME line.
        B2a's fixed check order silently picked AUTH and sent an operator
        to `codex login` for something login cannot fix. B2b resolves this
        via P3 (machine-readable evidence wins): QUOTA is raised, not
        AUTH, and the suppressed AUTH_DEATH candidate survives on
        `.suppressed` rather than being silently dropped (P1)."""
        client = _make_available_client(tmp_path)
        stderr = b"Error: token has expired; refresh failed with 429 too many requests\n"
        fake_exec.queue(_FakeProcess(b"", stderr, 1))

        with pytest.raises(CodexExecQuotaError) as exc_info:
            await client.generate("hello")
        assert exc_info.value.confidence is MatchConfidence.HIGH
        assert exc_info.value.suppressed == frozenset({"AUTH_DEATH"})

    def test_guilt_true_tie_between_two_high_confidence_classes_is_ambiguous(self) -> None:
        """SPEC P1: a genuine tie (both classes matched at
        `MatchConfidence.HIGH`, no principled winner) is reported
        AMBIGUOUS by `_classify_stderr`, never resolved by guessing. Direct
        unit test on the classifier (not through `generate()`) —
        `test_guilt_true_tie_raises_ambiguous_error_through_generate`
        below covers the same shape end-to-end."""
        verdict = client_module._classify_stderr(
            "Error: token_revoked; also insufficient_quota reported by upstream"
        )
        assert verdict.winner is None
        assert verdict.ambiguous_classes == frozenset(
            {client_module._WireWordClass.AUTH_DEATH, client_module._WireWordClass.QUOTA}
        )

    @pytest.mark.asyncio
    async def test_guilt_true_tie_raises_ambiguous_error_through_generate(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = _make_available_client(tmp_path)
        stderr = b"Error: token_revoked; also insufficient_quota reported by upstream\n"
        fake_exec.queue(_FakeProcess(b"", stderr, 1))

        with pytest.raises(CodexExecAmbiguousError) as exc_info:
            await client.generate("hello")
        assert exc_info.value.candidates == frozenset({"AUTH_DEATH", "QUOTA"})

    @pytest.mark.asyncio
    async def test_innocence_single_class_match_never_raises_ambiguous(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """Companion: a stderr matching exactly one class must never be
        misrouted through the ambiguity path."""
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"", b"Error: token_revoked\n", 1))

        with pytest.raises(CodexExecAuthError) as exc_info:
            await client.generate("hello")
        assert exc_info.value.suppressed == frozenset()


class TestReproducedRefuterFindings:
    """The 12 findings a fenced cross-family refuter (gpt-5.6-sol, xhigh)
    reproduced against B2a's compiled patterns, pinned as PERMANENT
    regression fixtures per the ops orchestrator's mandate — see
    `docs/plans/2026-08-25-due-bot-live/evidence/b2a-refuter-gpt56sol.txt`.
    Findings §1 (ordering) and one over-match item of §2
    (`RESOURCE_EXHAUSTED`, reclassified to `OUTPUT_INVALID`/`oversized`)
    have dedicated full `generate()`-level tests elsewhere
    (`TestMultiMatchPrecedence`/`TestOutputContract`) — the remaining 10
    are pinned here directly against `_classify_stderr`, which is the
    exact layer the refuter's findings are about. `expected_winner=None`
    means the corrected behavior is "matches nothing" (residual/unknown,
    SPEC P5) — not "unverified", these are all DELIBERATE corrections."""

    @pytest.mark.parametrize(
        ("finding_id", "stderr_text", "expected_winner"),
        [
            # --- over-match findings (evidence file §2) ---
            (
                "over-match: ordinary 'too many requests' sentence",
                "The client complained that the immigration officer made too "
                "many requests for the same document.",
                None,
            ),
            (
                "over-match: 'cannot assist with' business prose",
                "We cannot assist with the visa extension until your sponsor "
                "sends the missing passport scan.",
                None,
            ),
            (
                "over-match: 'refused to answer' about a third party",
                "The applicant refused to answer the immigration officer's question.",
                None,
            ),
            (
                "over-match: 'violates the policy' regulatory advice",
                "Submitting duplicate visa applications violates the policy "
                "and may delay approval.",
                None,
            ),
            (
                "over-match: 'safety system' facilities prose",
                "The office fire safety system is under maintenance.",
                None,
            ),
            (
                "over-match: domain-overloaded 'sponsor's quota exceeded'",
                "Your sponsor's quota exceeded this year's KITAS allocation.",
                None,
            ),
            # --- regex defects (evidence file §4) ---
            (
                "newline-bridging: quota\\nexceeded across two log records",
                "DEBUG field=quota\nexceeded retry budget while writing transcript",
                None,
            ),
            (
                "newline-bridging: content\\npolicy across two log records",
                "DEBUG category=content\npolicy loader failed to initialize",
                None,
            ),
            (
                "underscore-boundary: insufficient_quota_error (trailing suffix)",
                "Error code: insufficient_quota_error",
                client_module._WireWordClass.QUOTA,
            ),
            (
                "underscore-boundary: openai_insufficient_quota (leading prefix)",
                "Error code: openai_insufficient_quota",
                client_module._WireWordClass.QUOTA,
            ),
        ],
    )
    def test_finding_reproduced_and_corrected(
        self,
        finding_id: str,
        stderr_text: str,
        expected_winner,
    ) -> None:
        verdict = client_module._classify_stderr(stderr_text)
        assert verdict.winner == expected_winner, (
            f"finding {finding_id!r}: expected winner={expected_winner!r}, "
            f"got {verdict.winner!r} (stderr={stderr_text!r})"
        )


class TestVendorPhraseCoverage:
    """Refuter under-match findings (evidence file §3) — standard vendor
    phrasings the B2a vocabulary MISSED entirely, each pinned in
    ISOLATION (no other alternative's vocabulary co-occurring) so a later
    edit that breaks one specific alternative cannot hide behind another
    still matching — same discipline as
    `test_guilt_run_codex_login_clause_without_backticks` above."""

    @pytest.mark.parametrize(
        ("stderr_text", "expected_class", "expected_confidence"),
        [
            ("rate_limit_exceeded", client_module._WireWordClass.QUOTA, MatchConfidence.HIGH),
            (
                "the rate limit reached today",
                client_module._WireWordClass.QUOTA,
                MatchConfidence.LOW,
            ),
            (
                "you exceeded your current quota",
                client_module._WireWordClass.QUOTA,
                MatchConfidence.LOW,
            ),
            (
                "monthly credits exhausted",
                client_module._WireWordClass.QUOTA,
                MatchConfidence.LOW,
            ),
            (
                "blocked by the safety filter",
                client_module._WireWordClass.POLICY_BLOCKED,
                MatchConfidence.LOW,
            ),
            (
                "may violate our usage policy",
                client_module._WireWordClass.POLICY_BLOCKED,
                MatchConfidence.LOW,
            ),
            (
                "I can't assist with that request",
                client_module._WireWordClass.POLICY_BLOCKED,
                MatchConfidence.LOW,
            ),
        ],
    )
    def test_previously_undermatched_phrase_now_reachable(
        self,
        stderr_text: str,
        expected_class,
        expected_confidence: MatchConfidence,
    ) -> None:
        verdict = client_module._classify_stderr(stderr_text)
        assert verdict.winner is expected_class
        assert verdict.confidence is expected_confidence


class TestMultilingualInnocence:
    """SPEC P6 ("guilt AND innocence under test"): ordinary IT/EN/ID
    immigration-consultancy sentences a real WA/broker traffic stream
    would plausibly contain, none of which may ever trigger a word
    class."""

    @pytest.mark.parametrize(
        "text",
        [
            "The client's KITAS expired last month and needs renewal before "
            "the sponsor's quota resets.",
            "Please sign the enclosed authorization form and return it with "
            "your passport copy.",
            "Il cliente non e' piu' autorizzato a soggiornare senza rinnovare "
            "il permesso di lavoro.",
            "Il sistema di sicurezza dell'ufficio e' in manutenzione questa settimana.",
            "Klien harus login ke portal imigrasi untuk memperbarui KITAS "
            "sebelum masa berlaku habis.",
            "Kuota sponsor untuk tahun ini sudah terlampaui, jadi permohonan "
            "baru harus menunggu.",
        ],
    )
    def test_ordinary_consultancy_sentence_matches_nothing(self, text: str) -> None:
        verdict = client_module._classify_stderr(text)
        assert verdict.winner is None
        assert verdict.ambiguous_classes == frozenset()


# ---------------------------------------------------------------------------
# Timeout — wall-clock kill + reap (F26-6 fix, R26 GLM addendum,
# 2026-08-15: this is a deadline/output-shape behavior, NOT one of the
# module's 7 numbered invariants — the duplicate "Invariant 4" label here
# collided with line 472's genuine Invariant 4 above)
# ---------------------------------------------------------------------------


class TestTimeout:
    @pytest.mark.asyncio
    async def test_guilt_timeout_kills_and_reaps(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = _make_available_client(tmp_path, timeout_s=0.05)
        proc = _FakeProcess(b"PONG\n", b"", 0, communicate_delay=5.0)
        fake_exec.queue(proc)

        with pytest.raises(CodexExecTimeoutError):
            await client.generate("hello")

        assert proc.killed is True
        assert proc.waited is True
        assert proc.wait_completed is True

    @pytest.mark.asyncio
    async def test_guilt_repeated_cancellation_still_finishes_reap(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """A second cancellation during cleanup must not orphan the child."""
        client = _make_available_client(tmp_path)
        proc = _FakeProcess(
            b"",
            b"",
            0,
            communicate_delay=5.0,
            wait_delay=0.05,
        )
        fake_exec.queue(proc)

        task = asyncio.ensure_future(client.generate("hello"))
        await asyncio.sleep(0.01)
        task.cancel()

        for _ in range(100):
            if proc.waited:
                break
            await asyncio.sleep(0.001)
        assert proc.waited is True

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            unexpected_result = await task
            pytest.fail(f"cancelled task returned unexpectedly: {unexpected_result!r}")

        assert proc.killed is True
        assert proc.wait_completed is True

    @pytest.mark.asyncio
    async def test_innocence_fast_call_does_not_timeout(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = _make_available_client(tmp_path, timeout_s=5.0)
        fake_exec.queue(_FakeProcess(b"PONG\n", b"", 0, communicate_delay=0.01))

        result = await client.generate("hello")
        assert result.text == "PONG"

    @pytest.mark.asyncio
    async def test_guilt_per_call_timeout_override(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = _make_available_client(tmp_path, timeout_s=30.0)  # generous default
        proc = _FakeProcess(b"PONG\n", b"", 0, communicate_delay=1.0)
        fake_exec.queue(proc)

        with pytest.raises(CodexExecTimeoutError):
            await client.generate("hello", timeout_s=0.05)  # tight per-call override wins

    @pytest.mark.asyncio
    async def test_guilt_bad_per_call_timeout(
        self, tmp_path, fake_exec: _FakeSubprocessExec
    ) -> None:
        client = _make_available_client(tmp_path)
        with pytest.raises(ValueError):
            await client.generate("hello", timeout_s=-1)
        assert fake_exec.calls == []

    @pytest.mark.asyncio
    async def test_guilt_arbitrary_communicate_exception_is_sanitized_after_reap(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """R25-5 regression: the original code only called `_kill_and_reap`
        on `asyncio.TimeoutError` — any OTHER exception out of
        `communicate()` (simulated here as a `ConnectionResetError`, e.g. a
        broken stdin pipe) used to propagate with the child left unreaped.
        The child must still be reaped, but the original exception must not
        propagate across the provider boundary. The raw exception and its
        message must not escape."""
        client = _make_available_client(tmp_path)
        boom = ConnectionResetError("stdin pipe broke")
        proc = _FakeProcess(b"", b"", 0, communicate_raises=boom)
        fake_exec.queue(proc)

        with pytest.raises(CodexExecCommunicationError) as exc_info:
            await client.generate("hello")

        assert "stdin pipe broke" not in str(exc_info.value)
        assert exc_info.value.__context__ is None
        assert exc_info.value.__cause__ is None
        assert proc.killed is True
        assert proc.waited is True
        assert proc.wait_completed is True

    @pytest.mark.asyncio
    async def test_guilt_real_cancellation_kills_reaps_and_repropagates(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """R26-1 regression (HIGH, CONFIRMED): `asyncio.CancelledError` has
        been a `BaseException` subclass, NOT an `Exception` subclass, since
        Python 3.8 — the R25-5 catch-all `except Exception:` above never saw
        a real cancellation, so the child process went unreaped when the
        caller's task was cancelled mid-flight. (The `ConnectionResetError`
        stand-in in the previous test cannot exercise this: it IS an
        `Exception`.) This drives a REAL cancellation through a REAL
        `asyncio.Task`: `generate()` is scheduled as a task, allowed to run
        until it is parked inside a slow `communicate()`, cancelled from
        outside, and the test asserts both that `asyncio.CancelledError`
        propagates out of the awaited task — never rewrapped, never
        swallowed — AND that the fake process's kill/wait bookkeeping
        actually ran."""
        client = _make_available_client(tmp_path)
        proc = _FakeProcess(b"", b"", 0, communicate_delay=5.0)
        fake_exec.queue(proc)

        task = asyncio.ensure_future(client.generate("hello"))
        await asyncio.sleep(0.01)  # let the task reach the parked communicate()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            unexpected_result = await task
            pytest.fail(f"cancelled task returned unexpectedly: {unexpected_result!r}")

        assert proc.killed is True
        assert proc.waited is True
        assert proc.wait_completed is True


# ---------------------------------------------------------------------------
# Invariant 3/6 — unavailable fails closed before any subprocess touch
# ---------------------------------------------------------------------------


class TestUnavailable:
    @pytest.mark.asyncio
    async def test_guilt_generate_raises_when_unavailable(
        self,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = CodexExecClient(binary="/nonexistent/nowhere", codex_home="/nonexistent/home")
        with pytest.raises(CodexExecUnavailableError):
            await client.generate("hello")
        assert fake_exec.calls == []  # never launched — fails BEFORE any subprocess touch

    @pytest.mark.asyncio
    async def test_guilt_binary_vanishes_between_check_and_launch(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = _make_available_client(tmp_path)
        fake_exec.queue(FileNotFoundError("codex: no such file"))

        with pytest.raises(CodexExecUnavailableError):
            await client.generate("hello")

    @pytest.mark.asyncio
    async def test_guilt_permission_error_at_launch_maps_to_unavailable(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        """R25-5 regression: the original code caught ONLY
        `FileNotFoundError` at launch — a `PermissionError` (binary present
        but unusable, e.g. a TOCTOU permission change between the
        `available` check and launch) used to escape as a raw, undocumented
        exception instead of the typed `CodexExecUnavailableError`."""
        client = _make_available_client(tmp_path)
        fake_exec.queue(PermissionError("codex: permission denied"))

        with pytest.raises(CodexExecUnavailableError):
            await client.generate("hello")

    @pytest.mark.asyncio
    async def test_guilt_generic_oserror_at_launch_maps_to_unavailable(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        client = _make_available_client(tmp_path)
        fake_exec.queue(OSError("some other OS-level launch failure"))

        with pytest.raises(CodexExecUnavailableError):
            await client.generate("hello")

    @pytest.mark.asyncio
    async def test_guilt_mkdtemp_failure_maps_to_unavailable(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """R27-5 (GLM F6) regression: `tempfile.mkdtemp()` — creating the
        per-call neutral cwd (point 1) — was previously called OUTSIDE every
        typed-exception wrapper. A raw `OSError` from it (disk full, `/tmp`
        unwritable, a TOCTOU permission change) would propagate straight out
        of `generate()`, breaking this module's own fail-closed-with-typed-
        exceptions contract. Now wrapped and mapped to
        `CodexExecUnavailableError`, mirroring the R25-5 treatment of
        `create_subprocess_exec`'s own `OSError` just above."""
        client = _make_available_client(tmp_path)

        def _boom(*args, **kwargs):
            raise OSError("no space left on device")

        monkeypatch.setattr(client_module.tempfile, "mkdtemp", _boom)

        with pytest.raises(CodexExecUnavailableError):
            await client.generate("hello")
        assert fake_exec.calls == []  # never launched — fails before the subprocess touch


# ---------------------------------------------------------------------------
# Invariant 6 — sanitized errors/logs: no prompt text, no raw output
# ---------------------------------------------------------------------------


class TestSanitizedErrors:
    @pytest.mark.asyncio
    async def test_innocence_process_error_message_excludes_raw_stderr(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        secret_stderr = b"some sensitive internal detail that must never leak\n"
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"", secret_stderr, 7))

        with pytest.raises(CodexExecProcessError) as exc_info:
            await client.generate("hello")

        message = str(exc_info.value)
        assert "sensitive internal detail" not in message
        assert message == "codex exec failed (exit_code=7)"

    @pytest.mark.asyncio
    async def test_innocence_auth_error_message_excludes_prompt_and_raw_output(
        self,
        tmp_path,
        fake_exec: _FakeSubprocessExec,
    ) -> None:
        prompt = "my super secret client PII that must never appear in an exception"
        client = _make_available_client(tmp_path)
        fake_exec.queue(_FakeProcess(b"", _CONSTRUCTED_AUTH_FAIL_STDERR, 1))

        with pytest.raises(CodexExecAuthError) as exc_info:
            await client.generate(prompt)

        message = str(exc_info.value)
        assert prompt not in message
        assert "Not logged in" not in message  # raw stderr never echoed into the message


# ---------------------------------------------------------------------------
# Process-group kill (BOT-V4 S2 PR-6, spec §7 chaos row 5: "kill process
# group on expiry"). REAL subprocesses, deliberately not `fake_exec` — the
# fake cannot represent a grandchild, and a grandchild is the entire point:
# `codex exec` spawns descendants of its own, so a direct-child-only
# `proc.kill()` leaves them alive past a wall-clock timeout.
# ---------------------------------------------------------------------------


class TestProcessGroupKill:
    @pytest.mark.asyncio
    async def test_guilt_timeout_kills_grandchildren_via_process_group(
        self,
        tmp_path,
    ) -> None:
        """The fake binary backgrounds a grandchild `sleep` and then blocks;
        after the wall-clock timeout the WHOLE process group must be dead.
        This pins BOTH halves of the cure: without `start_new_session=True`
        the guard in `_kill_and_reap` skips the group-kill (shared pgid),
        and without the `os.killpg` the group is never signalled — either
        mutation leaves the grandchild alive and turns this test red."""
        client = _make_available_client(tmp_path, timeout_s=1.0)
        pid_file = tmp_path / "grandchild.pid"
        binary = tmp_path / "codex"
        binary.write_text(
            "#!/bin/sh\n"
            "sleep 300 &\n"
            f'echo $! > "{pid_file}"\n'
            "exec sleep 300\n"
        )
        binary.chmod(0o755)

        with pytest.raises(CodexExecTimeoutError):
            await client.generate("hello")

        assert pid_file.exists(), "fake binary never ran — harness broken, not a verdict"
        grandchild_pid = int(pid_file.read_text().strip())
        assert grandchild_pid > 1

        deadline = time.monotonic() + 5.0
        alive = True
        while time.monotonic() < deadline:
            try:
                os.kill(grandchild_pid, 0)
            except ProcessLookupError:
                alive = False
                break
            await asyncio.sleep(0.05)
        if alive:
            # Clean up the leak BEFORE failing, so a red run does not strand
            # a 300s sleep on the test machine.
            with contextlib.suppress(ProcessLookupError):
                os.kill(grandchild_pid, signal.SIGKILL)
        assert alive is False, (
            f"grandchild pid={grandchild_pid} survived the timeout kill — "
            "the process group was not killed (chaos row 5 violated)"
        )

    @pytest.mark.asyncio
    async def test_innocence_kill_and_reap_never_kills_our_own_group(self) -> None:
        """A process spawned WITHOUT `start_new_session` shares OUR process
        group; `_kill_and_reap`'s guard must skip the group-kill for it —
        `os.killpg` on our own pgid would SIGKILL the test runner itself, so
        this test's own survival past the call IS the assertion. The
        direct-child backstop must still kill and reap the child."""
        proc = await asyncio.create_subprocess_exec(
            "/bin/sleep",
            "300",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        # Precondition, not an assumption: same group as the test runner.
        assert os.getpgid(proc.pid) == os.getpgid(0)

        await client_module._kill_and_reap(proc)

        # We are alive to assert this — the guard did not fire on our group —
        # and the child was still killed and reaped by the direct backstop.
        assert proc.returncode is not None

    @pytest.mark.asyncio
    async def test_guilt_reap_is_bounded_when_orphans_hold_the_pipes(
        self,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CPython 3.11 resolves `proc.wait()` only when ALL pipe transports
        disconnect (`_call_connection_lost`), not when the process dies — so
        a descendant holding the inherited stdout/stderr write ends kept the
        pre-PR-6 `_kill_and_reap` pending FOREVER on a child that was
        already dead and OS-reaped (measured live: >90s hang). This pins the
        `_REAP_ABANDON_S` bound on the exact shape the group-kill guard
        skips: a child in OUR OWN process group (no `start_new_session`),
        killed via the direct backstop only, whose grandchild survives
        holding the pipes."""
        monkeypatch.setattr(client_module, "_REAP_ABANDON_S", 0.5)
        pid_file = tmp_path / "orphan.pid"
        script = tmp_path / "holder.sh"
        script.write_text(
            "#!/bin/sh\n"
            "sleep 300 &\n"
            f'echo $! > "{pid_file}"\n'
            "exec sleep 300\n"
        )
        script.chmod(0o755)
        proc = await asyncio.create_subprocess_exec(
            str(script),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # Deliberately NOT start_new_session: shared pgid makes the
            # group-kill guard skip, exercising the backstop + bounded wait.
        )
        for _ in range(100):
            if pid_file.exists() and pid_file.read_text().strip():
                break
            await asyncio.sleep(0.05)
        orphan_pid = int(pid_file.read_text().strip())

        reap = asyncio.ensure_future(client_module._kill_and_reap(proc))
        deadline = time.monotonic() + 3.0  # 6x the patched abandon bound
        bounded = False
        while time.monotonic() < deadline:
            if reap.done():
                bounded = True
                break
            await asyncio.sleep(0.05)

        # Unstick + clean up the orphan EITHER WAY: killing it closes the
        # pipes, which lets a regressed (unbounded) reap resolve so this
        # test FAILS instead of hanging the whole suite.
        with contextlib.suppress(ProcessLookupError):
            os.kill(orphan_pid, signal.SIGKILL)
        await reap

        assert bounded is True, (
            "_kill_and_reap hung past its abandon deadline on a dead child "
            "whose orphaned descendant held the pipe FDs"
        )
