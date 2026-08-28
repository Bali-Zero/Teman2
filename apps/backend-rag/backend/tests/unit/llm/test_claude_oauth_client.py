"""Tests for claude_oauth_client — subprocess behavior mocked end-to-end."""

from __future__ import annotations

import asyncio
import importlib
import time
from typing import Any

import pytest


@pytest.fixture
def clear_oauth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in (
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN_1",
        "CLAUDE_CODE_OAUTH_TOKEN_2",
        "CLAUDE_CODE_OAUTH_TOKEN_3",
        "CLAUDE_CODE_OAUTH_TOKEN_4",
        "CLAUDE_CODE_OAUTH_TOKEN_5",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_REGION",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_CLOUD_PROJECT",
        "CLOUD_ML_REGION",
    ):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture(autouse=True)
def isolate_seat_cooldowns(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Keep the module-level cooldown memo out of every other test.

    ``_seat_cooldowns`` is process state on an imported (therefore cached)
    module, so without this a seat cooled in one test would silently be skipped
    in the next — the W96 class of defect, one scope down. Autouse so it also
    protects the tests that predate the cooldown. Also clears the tuning env
    var so a developer's shell cannot change what the suite measures.
    """
    from backend.llm import claude_oauth_client as mod

    monkeypatch.delenv("CLAUDE_OAUTH_SEAT_COOLDOWN_S", raising=False)
    mod._reset_seat_cooldowns()
    yield
    mod._reset_seat_cooldowns()


def _fake_proc(stdout: bytes, stderr: bytes = b"", returncode: int = 0) -> Any:
    class _P:
        def __init__(self) -> None:
            self.returncode = returncode

        async def communicate(self) -> tuple[bytes, bytes]:
            return stdout, stderr

        async def wait(self) -> None:
            return None

        def kill(self) -> None:
            self.returncode = -9

    return _P()


class _BlockingProc:
    """Fake child that only exits after the client kills and reaps it."""

    def __init__(self) -> None:
        self.returncode: int | None = None
        self.killed = False
        self.waited = False

    async def communicate(self) -> tuple[bytes, bytes]:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def wait(self) -> None:
        self.waited = True

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


@pytest.mark.asyncio
async def test_collect_tokens_ordering(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "tok2")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_3", "tok3")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_4", "tok4")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_5", "team-slot-not-in-hot-path")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok_legacy")

    got = mod._collect_tokens()

    assert [label for _, label in got] == [
        "token_1",
        "token_2",
        "token_3",
        "token_4",
        "token_legacy",
        "keychain",
    ]
    assert [t for t, _ in got] == ["tok1", "tok2", "tok3", "tok4", "tok_legacy", ""]


@pytest.mark.asyncio
async def test_collect_tokens_deduplicates(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "same")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "same")

    got = mod._collect_tokens()

    assert [label for _, label in got] == ["token_1", "keychain"]


@pytest.mark.asyncio
async def test_build_env_strips_alternate_provider_credentials(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    provider_vars = {
        "ANTHROPIC_API_KEY": "api-secret",
        "ANTHROPIC_AUTH_TOKEN": "auth-secret",
        "ANTHROPIC_BASE_URL": "https://paid.invalid",
        "CLAUDE_CODE_USE_BEDROCK": "1",
        "AWS_ACCESS_KEY_ID": "aws-key",
        "AWS_SECRET_ACCESS_KEY": "aws-secret",
        "AWS_BEDROCK_RUNTIME_ENDPOINT": "https://bedrock.invalid",
        "BEDROCK_API_KEY": "bedrock-secret",
        "CLAUDE_CODE_USE_VERTEX": "1",
        "ANTHROPIC_VERTEX_PROJECT_ID": "vertex-project",
        "VERTEX_AI_ENDPOINT": "https://vertex.invalid",
        "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/vertex.json",
        "GOOGLE_CLOUD_PROJECT": "cloud-project",
        "CLOUD_ML_REGION": "asia-southeast1",
        "CLAUDE_CODE_OAUTH_TOKEN_1": "other-seat-1",
        "CLAUDE_CODE_OAUTH_TOKEN_4": "other-seat-4",
    }
    for key, value in provider_vars.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("NUZANTARA_SAFE_MARKER", "preserved")

    env = mod._build_env("tok_xyz")

    assert provider_vars.keys().isdisjoint(env)
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok_xyz"
    assert env["NUZANTARA_SAFE_MARKER"] == "preserved"
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in mod._build_env("")


@pytest.mark.asyncio
async def test_build_env_pins_sterile_headless_config_dir(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    """W132 guilt case: an inherited interactive CLAUDE_CONFIG_DIR must never
    leak into the child. The interactive config dirs carry the control-plane
    hooks (Stop-time cross-machine mailbox delivery) that extend a one-shot
    ``-p`` past its answer — the CLI then prints the LAST turn, so the caller
    receives fleet chatter instead of its completion."""
    import os

    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/Users/someone/.claude-kaiser")
    monkeypatch.delenv(mod.HEADLESS_CONFIG_DIR_ENV, raising=False)

    env = mod._build_env("tok_xyz")

    assert env["CLAUDE_CONFIG_DIR"] == os.path.expanduser(mod.DEFAULT_HEADLESS_CONFIG_DIR)
    assert env["CLAUDE_CONFIG_DIR"] != "/Users/someone/.claude-kaiser"
    # Innocence: the pin is present even with no inherited value at all.
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    env2 = mod._build_env("tok_xyz")
    assert env2["CLAUDE_CONFIG_DIR"] == os.path.expanduser(mod.DEFAULT_HEADLESS_CONFIG_DIR)


@pytest.mark.asyncio
async def test_build_env_headless_config_dir_env_override(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    tmp_path: Any,
) -> None:
    """The escape hatch (CLAUDE_OAUTH_HEADLESS_CONFIG_DIR) wins over the
    default, and a blank value falls back instead of pinning an empty path."""
    import os

    from backend.llm import claude_oauth_client as mod

    custom = str(tmp_path / "headless-cfg")
    monkeypatch.setenv(mod.HEADLESS_CONFIG_DIR_ENV, custom)
    env = mod._build_env("tok_xyz")
    assert env["CLAUDE_CONFIG_DIR"] == custom

    monkeypatch.setenv(mod.HEADLESS_CONFIG_DIR_ENV, "   ")
    env2 = mod._build_env("tok_xyz")
    assert env2["CLAUDE_CONFIG_DIR"] == os.path.expanduser(mod.DEFAULT_HEADLESS_CONFIG_DIR)


@pytest.mark.asyncio
async def test_complete_async_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")

    calls: list[dict[str, Any]] = []

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        calls.append(
            {"args": args, "env_has_api_key": "ANTHROPIC_API_KEY" in kwargs.get("env", {}),
             "env_config_dir": kwargs.get("env", {}).get("CLAUDE_CONFIG_DIR")}
        )
        return _fake_proc(stdout=b"hello world", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("ping", model="claude-sonnet-4-6")

    assert resp.text == "hello world"
    assert resp.token_label == "token_1"
    assert resp.attempts == 1
    assert len(calls) == 1
    assert calls[0]["env_has_api_key"] is False
    # W132 wiring: the sterile config-dir pin must reach the actual subprocess,
    # and the one-shot must not persist a session (the transcript-tail is what
    # let fleet mail extend the session past its answer).
    import os as _os

    assert calls[0]["env_config_dir"] == _os.path.expanduser(mod.DEFAULT_HEADLESS_CONFIG_DIR)
    assert "--no-session-persistence" in calls[0]["args"]


@pytest.mark.asyncio
async def test_complete_async_rate_limit_falls_through(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "t2")

    attempts: list[int] = []

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        attempts.append(len(attempts) + 1)
        if len(attempts) == 1:
            return _fake_proc(stdout=b"", stderr=b"Error: rate limit exceeded", returncode=1)
        return _fake_proc(stdout=b"ok", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("ping")

    assert resp.text == "ok"
    assert resp.token_label == "token_2"
    assert resp.attempts == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "diagnostic",
    [
        b"Error: quota exceeded",
        b"You've hit your weekly limit; resets tomorrow",
        b"Authentication failed",
        b"HTTP 401: Unauthorized",
        b"Error: token_revoked",
        b"Error: refresh_token_reused",
    ],
)
async def test_complete_async_exit_zero_diagnostic_falls_through(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    diagnostic: bytes,
) -> None:
    """Short, strongly framed exit-0 diagnostics must rotate to the next seat."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "t2")
    attempts = 0

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return _fake_proc(stdout=diagnostic, returncode=0)
        return _fake_proc(stdout=b"valid answer", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("ping")

    assert resp.text == "valid answer"
    assert resp.token_label == "token_2"
    assert resp.attempts == 2


@pytest.mark.asyncio
async def test_complete_async_legitimate_auth_content_is_not_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    """Diagnostic keywords inside normal prose must not trigger rotation."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")
    answer = (
        b"The string token_revoked is an OAuth error code. "
        b"A quota is simply an allocated allowance."
    )
    calls = 0

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return _fake_proc(stdout=answer, returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("explain OAuth errors")

    assert resp.text == answer.decode()
    assert resp.token_label == "token_1"
    assert calls == 1


@pytest.mark.asyncio
async def test_complete_async_falls_through_to_fourth_token(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    for slot in range(1, 5):
        monkeypatch.setenv(f"CLAUDE_CODE_OAUTH_TOKEN_{slot}", f"t{slot}")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-propagate")

    attempted_tokens: list[str] = []

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        env = kwargs["env"]
        attempted_tokens.append(env["CLAUDE_CODE_OAUTH_TOKEN"])
        assert "ANTHROPIC_API_KEY" not in env
        if len(attempted_tokens) < 4:
            return _fake_proc(stdout=b"", stderr=b"OAuth quota exhausted", returncode=1)
        return _fake_proc(stdout=b"slot four succeeded", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("ping")

    assert attempted_tokens == ["t1", "t2", "t3", "t4"]
    assert resp.text == "slot four succeeded"
    assert resp.token_label == "token_4"
    assert resp.attempts == 4


@pytest.mark.asyncio
async def test_complete_async_empty_output_falls_through(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")

    counter = {"n": 0}

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        counter["n"] += 1
        if counter["n"] == 1:
            return _fake_proc(stdout=b"   \n", returncode=0)  # empty after trim
        return _fake_proc(stdout=b"fine", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("ping")

    assert resp.text == "fine"
    assert resp.token_label == "keychain"
    assert resp.attempts == 2


@pytest.mark.asyncio
async def test_complete_async_all_fail(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        return _fake_proc(stdout=b"", stderr=b"generic failure", returncode=2)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    with pytest.raises(mod.ClaudeOAuthError):
        await mod.complete_async("ping")


@pytest.mark.asyncio
async def test_complete_async_per_seat_timeout_kills_and_reaps(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    """Seat 1's per-seat timeout fires, kill+reap runs, and the loop falls
    through to seat 2, which succeeds.

    Deterministic by construction (2026-07-26 —
    discovery_prepush_fixed_wallclock_budgets_fail_under_fleet_contention):
    the original version of this test raced a real 10ms asyncio.wait_for
    timeout against real event-loop scheduling. It failed on M5 under fleet
    CPU contention (load average 72.5) — not because complete_async is
    broken, but because seat 2's "instant" mock also missed its own fresh
    10ms wall-clock budget when the OS didn't schedule this process's
    thread in time. A timeout is a ceiling, not an assertion about
    scheduler latency.

    Fixed by faking asyncio.wait_for itself: seat 1's communicate() call is
    scripted to raise TimeoutError immediately (proving the real
    kill+reap+fallthrough control flow — the actual thing under test — not
    asyncio's own timer), every other wait_for call just awaits its target
    with no timer racing a scheduler at all. timeout_s/total_timeout_s no
    longer drive real timing; kept as small/realistic values purely as
    documentation of intent.
    """
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "t2")
    blocked = _BlockingProc()
    calls = 0

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            return blocked
        return _fake_proc(stdout=b"second seat succeeded", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    # wait_for call order for this scenario: (1) launch seat 1, (2)
    # communicate seat 1 [scripted timeout — the ONLY call that doesn't just
    # pass through], (3) launch seat 2, (4) communicate seat 2.
    wait_calls = 0

    async def fake_wait_for(fut: Any, timeout: float) -> Any:
        nonlocal wait_calls
        wait_calls += 1
        if wait_calls == 2:
            if asyncio.iscoroutine(fut):
                fut.close()
            raise asyncio.TimeoutError()
        return await fut

    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)

    resp = await mod.complete_async("ping", timeout_s=0.01, total_timeout_s=0.5)

    assert blocked.killed is True
    assert blocked.waited is True
    assert resp.token_label == "token_2"
    assert resp.attempts == 2


@pytest.mark.asyncio
async def test_complete_async_global_deadline_kills_reaps_and_stops(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    """The global deadline (not the per-seat one) fires after seat 1's
    communicate() times out, so the loop stops instead of trying seat 2.

    total_timeout_s raised from the original 0.01s (2026-07-26, same scar as
    the per-seat test above —
    discovery_prepush_fixed_wallclock_budgets_fail_under_fleet_contention):
    unlike that test, this one's assertion genuinely needs REAL elapsed
    wall-clock time — it proves `time.monotonic() >= deadline` fires AFTER
    one real seat's launch+communicate cycle, not before and not after two.
    A call-scripted fake clock could deliver that, but only by hard-coding
    how many times complete_async happens to read time.monotonic()
    internally — more coupled to implementation detail than the bug this is
    fixing, and silently wrong the next time that internal call count
    changes. 0.5s (50x the original budget) is the "defensible on a shared
    workstation" number the scar calls for: a single Python bytecode
    stretch is never realistically delayed hundreds of ms by OS scheduling,
    even under the load average 72.5 measured live when the sibling test
    flaked.

    Guilt-proven manually during review, TWICE (caught undercounting my own
    first pass — cross-family review flagged it before merge). complete_async
    sets "global_deadline" at FIVE sites in TWO phases, not three in one:
    the capability-probe phase (:648 pre-check, :661 TimeoutError handler,
    guarded by `if supports is None` — only reached when a caller passes
    json_schema AND the process-wide `_JSON_SCHEMA_SUPPORTED` memo is still
    unset) and the seat-loop phase this test actually drives (:674 loop-top
    pre-check, :722 launch-except, :737 communicate-except). This test calls
    complete_async without json_schema, so only the seat-loop three are live
    here; neutralizing any one or two of THOSE three alone left this test
    passing anyway, saved by whichever check was still live — genuine
    defense-in-depth. Only neutralizing all three together produced the
    expected RED: `attempts_made == 3`, `last_error == "keychain:
    launch_timeout"`, `pytest.raises(..., match="global_deadline")`
    correctly failed to match. Restored and reconfirmed 45/45 green.

    The other two (:648/:661) are NOT verified redundancy — grepped the
    whole suite (`grep -rn "_JSON_SCHEMA_SUPPORTED" backend/tests/`, then the
    same for `_cli_supports_json_schema`) and every test that calls
    complete_async(json_schema=...)
    monkeypatches `_JSON_SCHEMA_SUPPORTED` straight to True/False via the
    `force_schema_supported`/`force_schema_unsupported` fixtures — the
    `supports is None` branch, and both deadline checks inside it, are never
    entered by any test in this repo. That's a coverage gap wearing the
    label of defense-in-depth, not a fourth/fifth layer proven to hold;
    logged separately rather than silently folded into this PR's scope.
    """
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "t2")
    blocked = _BlockingProc()
    calls = 0

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return blocked

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    with pytest.raises(mod.ClaudeOAuthError, match="global_deadline"):
        await mod.complete_async("ping", timeout_s=1, total_timeout_s=0.5)

    assert calls == 1
    assert blocked.killed is True
    assert blocked.waited is True


@pytest.mark.asyncio
async def test_complete_async_never_logs_or_raises_raw_stderr(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")
    fake_secret = "synthetic-secret-must-not-leak"
    fake_refresh = "synthetic-refresh-token-must-not-leak"

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        return _fake_proc(
            stdout=b"",
            stderr=(
                f"Authentication failed secret={fake_secret} refresh_token={fake_refresh}"
            ).encode(),
            returncode=2,
        )

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    with caplog.at_level("WARNING"), pytest.raises(mod.ClaudeOAuthError) as exc_info:
        await mod.complete_async("ping")

    surfaced = f"{caplog.text}\n{exc_info.value}"
    assert fake_secret not in surfaced
    assert fake_refresh not in surfaced
    assert "stderr=" not in surfaced
    # Something identifying the failure MUST surface — a silent redaction that
    # reported nothing would satisfy the three assertions above vacuously.
    # This used to read `cli_exit_2`; since 2026-07-25 the non-zero exit path
    # runs the diagnostic classifier too, so a framed auth error is now named
    # rather than reduced to its exit code. Equally redacted (the classifier
    # returns a fixed class and never the raw text), strictly more useful.
    assert "authentication" in surfaced


@pytest.mark.asyncio
async def test_complete_async_cli_missing(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    from backend.llm import claude_oauth_client as mod

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError("no claude binary")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    with pytest.raises(mod.ClaudeOAuthNotAvailable):
        await mod.complete_async("ping")


@pytest.mark.asyncio
async def test_complete_async_argv_is_hardened(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    """The built argv must drop bypassPermissions, end with a ``--`` sentinel
    immediately before the prompt, and reject non-allowlisted model slugs."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")

    captured: dict[str, Any] = {}

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        captured["cmd"] = list(args)
        return _fake_proc(stdout=b"ok", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    # (iv) a valid, allowlisted slug passes and reaches the subprocess.
    resp = await mod.complete_async("untrusted prompt", model="claude-sonnet-4-6")
    assert resp.text == "ok"

    cmd = captured["cmd"]
    # (i) the dangerous permission bypass is gone.
    assert "bypassPermissions" not in cmd
    assert "--permission-mode" not in cmd
    # tools are explicitly disallowed instead.
    assert "--disallowedTools" in cmd
    # (ii) the `--` sentinel is present and sits immediately before the prompt.
    assert "--" in cmd
    assert cmd[-2] == "--"
    assert cmd[-1] == "untrusted prompt"
    # the model slug was forwarded.
    assert "--model" in cmd
    assert "claude-sonnet-4-6" in cmd

    # (iii) a non-allowlisted model (flag-shaped) raises before any subprocess.
    with pytest.raises(ValueError):
        await mod.complete_async("ping", model="--evil-flag")


def test_module_imports_without_anthropic_sdk() -> None:
    """Integrity test: the OAuth client must not import the Anthropic SDK.

    The entire point of this module is to remove the SDK dependency for
    Claude calls.
    """
    import backend.llm.claude_oauth_client as mod

    importlib.reload(mod)

    src = open(mod.__file__).read()
    assert "import anthropic" not in src
    assert "from anthropic" not in src


# ---------------------------------------------------------------------------
# --json-schema structured-output path (SPEC v2)
# ---------------------------------------------------------------------------

_ENVELOPE_OK = (
    b'{"type":"result","subtype":"success","is_error":false,'
    b'"result":"The domain is visa.",'
    b'"structured_output":{"domain":"visa","confidence":0.95},'
    b'"usage":{"input_tokens":120,"output_tokens":18}}'
)


@pytest.fixture
def force_schema_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the memoized --json-schema capability probe to True."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setattr(mod, "_JSON_SCHEMA_SUPPORTED", True)


@pytest.fixture
def force_schema_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setattr(mod, "_JSON_SCHEMA_SUPPORTED", False)


_SCHEMA = {
    "type": "object",
    "properties": {"domain": {"type": "string"}, "confidence": {"type": "number"}},
    "required": ["domain", "confidence"],
}


@pytest.mark.asyncio
async def test_json_schema_none_is_byte_identical(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    """json_schema=None must NOT add --output-format/--json-schema to argv (D1)."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")
    captured: dict[str, Any] = {}

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        captured["cmd"] = list(args)
        return _fake_proc(stdout=b"plain text", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("ping")

    assert resp.text == "plain text"
    assert resp.structured is None
    assert "--json-schema" not in captured["cmd"]
    assert "--output-format" not in captured["cmd"]


@pytest.mark.asyncio
async def test_json_schema_envelope_parsed(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    force_schema_supported: None,
) -> None:
    """A well-formed envelope yields structured + flags placed before `--` (D2/D6)."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")
    captured: dict[str, Any] = {}

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        captured["cmd"] = list(args)
        return _fake_proc(stdout=_ENVELOPE_OK, returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async(
        "classify", model="claude-haiku-4-5-20251001", json_schema=_SCHEMA
    )

    # structured_output is the real answer; text is the PROSE result (D2).
    assert resp.structured == {"domain": "visa", "confidence": 0.95}
    assert resp.text == "The domain is visa."
    cmd = captured["cmd"]
    # flags present and the `--` sentinel still sits immediately before the prompt (D6).
    assert "--output-format" in cmd and "json" in cmd
    assert "--json-schema" in cmd
    assert cmd[-2] == "--"
    assert cmd[-1] == "classify"
    # the schema blob never precedes the model flag chaos — it's a single argv token.
    schema_idx = cmd.index("--json-schema") + 1
    assert cmd[schema_idx].startswith("{") and "domain" in cmd[schema_idx]


@pytest.mark.asyncio
async def test_json_schema_ndjson_last_result_wins(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    force_schema_supported: None,
) -> None:
    """NDJSON stream: the last type==result object provides the structured answer."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")
    ndjson = (
        b'{"type":"system","subtype":"init"}\n'
        b'{"type":"assistant","message":"thinking"}\n' + _ENVELOPE_OK
    )

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        return _fake_proc(stdout=ndjson, returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("classify", json_schema=_SCHEMA)
    assert resp.structured == {"domain": "visa", "confidence": 0.95}


@pytest.mark.asyncio
async def test_json_schema_is_error_envelope_falls_through(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    force_schema_supported: None,
) -> None:
    """is_error:true with an auth diagnostic rotates even when the CLI exits 0."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")
    counter = {"n": 0}

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        counter["n"] += 1
        if counter["n"] == 1:
            return _fake_proc(
                stdout=(
                    b'{"type":"result","is_error":true,"result":"Error: token_revoked (HTTP 401)"}'
                ),
                returncode=0,
            )
        return _fake_proc(stdout=_ENVELOPE_OK, returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("classify", json_schema=_SCHEMA)
    assert resp.structured == {"domain": "visa", "confidence": 0.95}
    assert resp.attempts == 2


@pytest.mark.asyncio
async def test_json_schema_unsupported_cli_degrades_to_text(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    force_schema_unsupported: None,
) -> None:
    """A CLI without the flag drops the schema and runs the plain text path (D4)."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")
    captured: dict[str, Any] = {}

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        captured["cmd"] = list(args)
        return _fake_proc(stdout=b"plain answer", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("classify", json_schema=_SCHEMA)

    assert resp.text == "plain answer"
    assert resp.structured is None
    assert "--json-schema" not in captured["cmd"]


@pytest.mark.asyncio
async def test_json_schema_oversize_drops_to_text(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    force_schema_supported: None,
) -> None:
    """A schema over the argv cap is dropped; the text path runs (D6 size-cap)."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "tok1")
    captured: dict[str, Any] = {}

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        captured["cmd"] = list(args)
        return _fake_proc(stdout=b"text fallback", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    huge_schema = {
        "type": "object",
        "properties": {f"f{i}": {"type": "string"} for i in range(5000)},
    }
    resp = await mod.complete_async("classify", json_schema=huge_schema)

    assert resp.text == "text fallback"
    assert "--json-schema" not in captured["cmd"]


@pytest.mark.asyncio
async def test_json_schema_rate_limit_on_exit_nonzero_scans_stdout(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    force_schema_supported: None,
) -> None:
    """In schema mode, a rate-limit error on STDOUT with exit!=0 must still be
    caught (panel fix: isolate-to-stderr only on exit 0)."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_2", "t2")
    counter = {"n": 0}

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        counter["n"] += 1
        if counter["n"] == 1:
            # rate-limit reported on stdout, empty stderr, non-zero exit.
            return _fake_proc(stdout=b'{"error":"rate limit exceeded"}', stderr=b"", returncode=1)
        return _fake_proc(stdout=_ENVELOPE_OK, returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    resp = await mod.complete_async("classify", json_schema=_SCHEMA)
    assert resp.token_label == "token_2"
    assert resp.structured == {"domain": "visa", "confidence": 0.95}


def test_parse_json_envelope_unit() -> None:
    """Direct unit coverage of the envelope parser's return contract."""
    from backend.llm.claude_oauth_client import _parse_json_envelope

    text, structured, usage, is_error = _parse_json_envelope(_ENVELOPE_OK.decode())
    assert text == "The domain is visa."
    assert structured == {"domain": "visa", "confidence": 0.95}
    assert usage == {"input_tokens": 120, "output_tokens": 18}
    assert is_error is False

    # empty / unparseable → all-None contract
    assert _parse_json_envelope("") == ("", None, None, False)
    assert _parse_json_envelope("not json at all") == ("", None, None, False)

    # envelope without structured_output → text+usage but structured None
    no_struct = '{"type":"result","is_error":false,"result":"hi","usage":{"input_tokens":3,"output_tokens":1}}'
    t, s, u, error = _parse_json_envelope(no_struct)
    assert t == "hi" and s is None and u == {"input_tokens": 3, "output_tokens": 1}
    assert error is False

    error_envelope = '{"type":"result","is_error":true,"result":"Error: refresh_token_reused"}'
    t, s, u, error = _parse_json_envelope(error_envelope)
    assert t == "Error: refresh_token_reused"
    assert s is None and u is None and error is True


def test_serialize_schema_compact_and_capped() -> None:
    from backend.llm.claude_oauth_client import _MAX_SCHEMA_BYTES, _serialize_schema

    blob = _serialize_schema({"a": 1, "b": 2})
    assert blob == '{"a":1,"b":2}'  # compact separators (no spaces)

    with pytest.raises(ValueError):
        _serialize_schema({"x": "y" * (_MAX_SCHEMA_BYTES + 100)})


# ---------------------------------------------------------------------------
# Seat cooldown — an exhausted seat must be recognised AND remembered
# ---------------------------------------------------------------------------
# The message below is the REAL one, copied from a live probe on 2026-07-25
# (`claude -p PONG` against a weekly-exhausted Max seat): exit 1, no rate-limit
# wording the loose RATE_LIMIT_PATTERN would catch. Before the fix it logged as
# `cli_exit_1` and the dead seat was re-spawned on every single call.
_EXHAUSTED_SEAT_MESSAGE = b"You've hit your weekly limit \xc2\xb7 resets 9am (Asia/Makassar)"


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", ["stdout", "stderr"])
async def test_exhausted_seat_is_classified_as_quota_not_a_bare_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    stream: str,
) -> None:
    """The live message must reach the classifier on the NON-zero exit path."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        if stream == "stdout":
            return _fake_proc(stdout=_EXHAUSTED_SEAT_MESSAGE, returncode=1)
        return _fake_proc(stdout=b"", stderr=_EXHAUSTED_SEAT_MESSAGE, returncode=1)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    with pytest.raises(mod.ClaudeOAuthError) as excinfo:
        await mod.complete_async("ping")

    message = str(excinfo.value)
    assert "quota" in message
    assert "cli_exit_1" not in message
    # The raw diagnostic itself never leaks into the error surface.
    assert "Makassar" not in message


@pytest.mark.asyncio
async def test_exhausted_seat_is_skipped_on_the_following_call(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    """The whole point: stop re-spawning a CLI for a seat known to be dead."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")
    attempted: list[str] = []

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        seat = kwargs["env"].get("CLAUDE_CODE_OAUTH_TOKEN", "<keychain>")
        attempted.append(seat)
        if seat == "t1":
            return _fake_proc(stdout=b"", stderr=_EXHAUSTED_SEAT_MESSAGE, returncode=1)
        return _fake_proc(stdout=b"ok", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    first = await mod.complete_async("ping")
    assert attempted == ["t1", "<keychain>"]
    assert first.token_label == "keychain"

    second = await mod.complete_async("ping")
    assert attempted == ["t1", "<keychain>", "<keychain>"], "dead seat re-probed"
    assert second.token_label == "keychain"
    assert second.attempts == 1, "the skipped seat must not be counted as an attempt"


@pytest.mark.asyncio
async def test_a_plain_crash_is_not_a_cooldown(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    """INNOCENCE: a seat that merely crashed is still healthy — retry it."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")
    attempted: list[str] = []

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        seat = kwargs["env"].get("CLAUDE_CODE_OAUTH_TOKEN", "<keychain>")
        attempted.append(seat)
        if seat == "t1":
            return _fake_proc(stdout=b"", stderr=b"Segmentation fault", returncode=139)
        return _fake_proc(stdout=b"ok", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    await mod.complete_async("ping")
    await mod.complete_async("ping")

    assert attempted == ["t1", "<keychain>", "t1", "<keychain>"]
    assert not mod._seat_cooldowns


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "diagnostic",
    [
        b"Error: HTTP 429 Too Many Requests",
        b"Error: rate limited, please retry",
        b"Error: too many requests",
    ],
)
async def test_transient_rate_limit_is_recognised_but_never_cooled(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
    diagnostic: bytes,
) -> None:
    """GUILT+INNOCENCE pair for the cross-family finding (2026-07-25): a 429
    used to share the `quota` class with a genuine weekly-limit exhaustion, so
    it earned the same 15-minute seat cooldown even though it is transient by
    nature.

    Deliberately targets the exit==0 / no-schema classify call site (line
    ~769: `if exit_code == 0 and not use_schema`), NOT the exit!=0 site: an
    exit!=0 stderr containing "429"/"rate limit"/"too many requests" is
    intercepted EARLIER by the pre-existing, unrelated `RATE_LIMIT_PATTERN`
    short-circuit (only guards exit_code != 0), which `continue`s WITHOUT
    ever calling `_mark_seat_cooling` — so that site can never discriminate
    pre/post-fix (confirmed empirically: it passes either way). The exit==0
    stdout site has no such guard, so it is where the granularity bug
    actually lived and is actually fixed.

    Two things must both hold: the diagnostic IS recognised (rotates to the
    next seat WITHIN this call, same as any other framed diagnostic — that
    part is correct and pre-dates this fix), but it must NEVER be
    persisted as a cooldown, so the very next call retries the same seat.

    This test FAILS on the pre-fix code (rate-limit shared the `quota` class,
    so `t1` would still be missing from `attempted` on the second call) and
    PASSES after `_RATE_LIMIT_DIAGNOSTIC_PATTERN` is classified separately
    from `_QUOTA_DIAGNOSTIC_PATTERN` and excluded from `_COOLDOWN_CLASSES`.
    """
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")
    attempted: list[str] = []

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        seat = kwargs["env"].get("CLAUDE_CODE_OAUTH_TOKEN", "<keychain>")
        attempted.append(seat)
        if seat == "t1":
            return _fake_proc(stdout=diagnostic, stderr=b"", returncode=0)
        return _fake_proc(stdout=b"ok", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    first = await mod.complete_async("ping")
    assert attempted == ["t1", "<keychain>"], "429 must still rotate within the same call"
    assert first.token_label == "keychain"
    assert not mod._seat_cooldowns, "a transient 429 must never be memoised as cooling"

    second = await mod.complete_async("ping")
    assert attempted == [
        "t1",
        "<keychain>",
        "t1",
        "<keychain>",
    ], "t1 must be retried on the very next call, not skipped as if exhausted"
    assert second.token_label == "keychain"


def test_transient_429_and_durable_quota_classify_differently() -> None:
    """Unit-level guilt+innocence on the classifier itself, no subprocess."""
    from backend.llm import claude_oauth_client as mod

    assert mod._classify_cli_diagnostic("Error: HTTP 429 Too Many Requests") == "rate_limit"
    assert mod._classify_cli_diagnostic("Error: rate limited") == "rate_limit"
    assert mod._classify_cli_diagnostic("Error: too many requests") == "rate_limit"
    assert (
        mod._classify_cli_diagnostic("You've hit your weekly limit · resets 9am")
        == "quota"
    )
    assert mod._classify_cli_diagnostic("Error: quota exceeded") == "quota"
    assert "rate_limit" not in mod._COOLDOWN_CLASSES
    assert "quota" in mod._COOLDOWN_CLASSES


@pytest.mark.asyncio
async def test_long_prose_mentioning_a_weekly_limit_is_not_a_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    """INNOCENCE: the classifier decides on error SHAPE, never on a substring."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")
    prose = (
        b"The regulation says the applicant has hit your weekly limit only when "
        b"the filing window closes, and the weekly limit is counted from the first "
        b"business day, which for this particular case means the deadline lands on "
        b"a Monday rather than the Friday the client assumed when they filed."
    )

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        return _fake_proc(stdout=prose, stderr=b"", returncode=1)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    with pytest.raises(mod.ClaudeOAuthError) as excinfo:
        await mod.complete_async("ping")

    assert "cli_exit_1" in str(excinfo.value)
    assert not mod._seat_cooldowns, "prose must never cool a healthy seat"


@pytest.mark.asyncio
async def test_cooldown_can_be_disabled_by_env(
    monkeypatch: pytest.MonkeyPatch,
    clear_oauth_env: None,
) -> None:
    """Kill switch: 0 keeps the honest classification, drops the memo."""
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN_1", "t1")
    monkeypatch.setenv("CLAUDE_OAUTH_SEAT_COOLDOWN_S", "0")
    attempted: list[str] = []

    async def fake_create(*args: Any, **kwargs: Any) -> Any:
        seat = kwargs["env"].get("CLAUDE_CODE_OAUTH_TOKEN", "<keychain>")
        attempted.append(seat)
        if seat == "t1":
            return _fake_proc(stdout=b"", stderr=_EXHAUSTED_SEAT_MESSAGE, returncode=1)
        return _fake_proc(stdout=b"ok", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    await mod.complete_async("ping")
    await mod.complete_async("ping")

    assert attempted == ["t1", "<keychain>", "t1", "<keychain>"]
    assert not mod._seat_cooldowns


def test_seat_key_never_contains_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cicatrix #4: the memo holds a fingerprint, never the credential."""
    from backend.llm import claude_oauth_client as mod

    secret = "sk-ant-oat01-VERY-SECRET-VALUE"
    key = mod._seat_key(secret, "token_1")

    assert secret not in key
    assert "VERY-SECRET" not in key
    assert key.startswith("token_1:")
    assert key != mod._seat_key(secret + "x", "token_1")


def test_rotated_token_does_not_inherit_the_old_cooldown() -> None:
    """A new credential under the same label starts clean."""
    from backend.llm import claude_oauth_client as mod

    mod._seat_cooldowns[mod._seat_key("old", "token_1")] = time.monotonic() + 900

    assert mod._drop_cooling_seats([("old", "token_1")]) == [("old", "token_1")], (
        "the only seat is cooling — must fail open"
    )
    kept = mod._drop_cooling_seats([("old", "token_1"), ("new", "token_1")])
    assert kept == [("new", "token_1")]


def test_expired_cooldown_is_dropped_and_the_seat_returns() -> None:
    from backend.llm import claude_oauth_client as mod

    mod._seat_cooldowns[mod._seat_key("t1", "token_1")] = time.monotonic() - 1.0
    pairs = [("t1", "token_1"), ("", "keychain")]

    assert mod._drop_cooling_seats(pairs) == pairs
    assert not mod._seat_cooldowns, "expired entries must be purged, not accumulated"


def test_all_seats_cooling_fails_open() -> None:
    """A cooldown is an optimisation — it may never starve the cascade."""
    from backend.llm import claude_oauth_client as mod

    pairs = [("t1", "token_1"), ("t2", "token_2"), ("", "keychain")]
    for token, label in pairs:
        mod._seat_cooldowns[mod._seat_key(token, label)] = time.monotonic() + 900

    assert mod._drop_cooling_seats(pairs) == pairs


def test_malformed_cooldown_env_degrades_to_a_safe_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.llm import claude_oauth_client as mod

    monkeypatch.setenv("CLAUDE_OAUTH_SEAT_COOLDOWN_S", "not-a-number")
    assert mod._seat_cooldown_s() == mod._DEFAULT_SEAT_COOLDOWN_S

    monkeypatch.setenv("CLAUDE_OAUTH_SEAT_COOLDOWN_S", "nan")
    assert mod._seat_cooldown_s() == 0.0, "NaN must disable, never strand a seat"

    monkeypatch.setenv("CLAUDE_OAUTH_SEAT_COOLDOWN_S", "-5")
    assert mod._seat_cooldown_s() == 0.0
