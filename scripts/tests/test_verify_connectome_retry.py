"""verify_connectome._run retries the ssh TRANSPORT, and nothing else.

Guilt: an ssh probe whose transport fails (exit 255, timeout, spawn error) is
retried, and a link that comes back on attempt 2 reports ok — the case that
matters, because one failed `ssh true` in ssh_reachable() blanks every edge on
that machine. Measured on m5 during a real mDNS blip: 1 false REGRESSED
("Could not resolve hostname") and 194 of 354 edges SKIPPED.

Innocence: a probe that actually RAN and returned non-zero is an answer, not a
flap, and is never retried — `launchctl list | grep -F <label>` exits 1 when the
label is absent, which is exactly the death this verifier exists to report. Nor
are local probes retried: there is no transport to flap.

Run:  python3 -m pytest scripts/tests/test_verify_connectome_retry.py -q
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = REPO_ROOT / "scripts" / "verify_connectome.py"
_spec = importlib.util.spec_from_file_location("verify_connectome", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
vc = importlib.util.module_from_spec(_spec)
# Register before exec: @dataclass resolves its own module via sys.modules, so a
# file-loaded module that skips this dies at import with a bare AttributeError.
sys.modules[_spec.name] = vc
_spec.loader.exec_module(vc)  # type: ignore[union-attr]


class _Proc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backoff must not make the suite wait for wall-clock seconds."""
    monkeypatch.setattr(vc.time, "sleep", lambda _s: None)


def _spy(monkeypatch: pytest.MonkeyPatch, outcomes: list) -> list:
    """Feed `outcomes` (a _Proc or an exception instance) to successive calls."""
    calls: list = []

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN003
        calls.append(cmd)
        nxt = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt

    monkeypatch.setattr(vc.subprocess, "run", fake_run)
    return calls


# --------------------------------------------------------------------------- guilt


def test_ssh_transport_failure_is_retried_and_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _spy(
        monkeypatch,
        [
            _Proc(vc.SSH_TRANSPORT_RC, stderr="ssh: Could not resolve hostname"),
            _Proc(0, stdout="pong"),
        ],
    )
    res = vc._run("true", "ssh:pro-lan", no_ssh=False)
    assert res.ok is True
    assert len(calls) == 2, "a 255 must be retried, not reported"
    assert "after 2 attempts" in res.detail, "a papered-over flap must still be visible"


@pytest.mark.parametrize(
    "boom",
    [
        subprocess.TimeoutExpired(cmd="ssh", timeout=30),
        OSError("no such file"),
    ],
)
def test_transport_exceptions_are_retried(
    monkeypatch: pytest.MonkeyPatch, boom: BaseException
) -> None:
    calls = _spy(monkeypatch, [boom])
    res = vc._run("true", "ssh:pro-lan", no_ssh=False)
    assert res.ok is False
    assert len(calls) == vc.PROBE_SSH_ATTEMPTS
    assert "transport failed" in res.detail


def test_persistent_transport_failure_still_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retrying must not turn a genuinely dead link green."""
    calls = _spy(monkeypatch, [_Proc(vc.SSH_TRANSPORT_RC, stderr="no route to host")])
    res = vc._run("true", "ssh:pro-lan", no_ssh=False)
    assert res.ok is False
    assert len(calls) == vc.PROBE_SSH_ATTEMPTS


# ----------------------------------------------------------------------- innocence


def test_remote_nonzero_is_an_answer_not_a_flap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`launchctl list | grep` exiting 1 = the label is gone. Report it at once."""
    calls = _spy(monkeypatch, [_Proc(1, stdout="")])
    res = vc._run("launchctl list | grep -F com.example", "ssh:pro-lan", no_ssh=False)
    assert res.ok is False
    assert len(calls) == 1, "a real remote verdict must not be retried"
    assert "transport failed" not in res.detail


def test_local_cmd_that_shells_out_to_ssh_is_still_ssh_bearing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real ssh_link edges are `type: cmd` with no `via:` — they run local.

    Keying the retry off `via` alone silently skipped the exact edge whose flap
    motivated this (`probe: {type: cmd, cmd: "ssh -o ConnectTimeout=8 pro-lan
    true"}`), which a live run caught: same REGRESSED, no retry banner.
    """
    calls = _spy(
        monkeypatch,
        [_Proc(vc.SSH_TRANSPORT_RC, stderr="ssh: Could not resolve hostname"),
         _Proc(0, stdout="")],
    )
    res = vc._run("ssh -o ConnectTimeout=8 pro-lan true", "local", no_ssh=False)
    assert res.ok is True
    assert len(calls) == 2


@pytest.mark.parametrize(
    "cmd,expected",
    [
        ("ssh -o ConnectTimeout=8 pro-lan true", True),
        ("launchctl list | ssh mini cat", True),
        ("test -e /x && ssh mini true", True),
        # over-match guard: the letters appear, the invocation does not
        ("test -e ~/.ssh/config", False),
        ("grep -qE 'ssh' /etc/hosts", False),
        ("md5 -q /tmp/sshd_config", False),
        ("launchctl list | grep -F com.example", False),
    ],
)
def test_ssh_bearing_matches_invocations_not_spellings(cmd: str, expected: bool) -> None:
    assert vc._ssh_bearing(cmd, "local") is expected


def test_local_probe_is_never_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _spy(monkeypatch, [_Proc(1, stderr="nope")])
    res = vc._run("test -e /nope", "local", no_ssh=False)
    assert res.ok is False
    assert len(calls) == 1


def test_local_success_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _spy(monkeypatch, [_Proc(0, stdout="ok")])
    res = vc._run("true", "local", no_ssh=False)
    assert res.ok is True
    assert len(calls) == 1
    assert res.detail == "ok", "the happy path must not grow an attempt banner"


def test_no_ssh_flag_short_circuits_without_spawning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _spy(monkeypatch, [_Proc(0)])
    res = vc._run("true", "ssh:pro-lan", no_ssh=True)
    assert res.ok is False
    assert calls == [], "--no-ssh must not reach subprocess at all"
