"""Guilt + innocence for `fleet_mail.sh`'s host allowlist.

Why this file exists: the allowlist said `local|pro|mini` while the fleet has had
three nodes since 2026-05-31, so every Pro or Mini session that tried to reach M5
with the fleet tool got "unknown host 'air'" and fell back to hand-delivering over
raw ssh. Nothing failed loudly — the tool simply refused a node that exists.

Per superscar #3, a guard gets both halves or neither: `air` must be ACCEPTED
(innocence) and a genuinely unknown host must still be REFUSED (guilt), so this
does not degrade into "accept anything".

`m5` is deliberately NOT in the allowlist and is asserted as refused. Measured
2026-08-24 from both peers: `ssh air` resolves to Air-M5 from Pro and from Mini;
`ssh m5` resolves only from Pro and fails on Mini with "could not resolve
hostname". Admitting an alias that works from one peer and dies on the other is
how a lane comes to fail on exactly one machine.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "fleet_mail.sh"


@pytest.fixture(scope="module")
def stub_path(tmp_path_factory: pytest.TempPathFactory) -> str:
    """A PATH whose `ssh` fails instantly.

    An ACCEPTED host proceeds past the allowlist and tries to reach its peer, so
    without this the test would depend on the network: slow in CI (three hosts x
    an 8s connect timeout) and, worse, it would be measuring reachability when
    the thing under test is the allowlist. The stub makes the run hermetic and
    keeps the two outcomes distinguishable — a host refused by the allowlist
    never reaches `ssh` at all, so only rejection produces "unknown host".
    """
    d = tmp_path_factory.mktemp("stub-bin")
    ssh = d / "ssh"
    ssh.write_text("#!/bin/sh\necho 'stub ssh: refused' >&2\nexit 255\n")
    ssh.chmod(0o755)
    import os

    return f"{d}{os.pathsep}{os.environ.get('PATH', '')}"


def _reject_reason(host: str, path: str) -> str | None:
    """Run the script with `<host> --list`; return its allowlist rejection, if any.

    A rejected host dies in the `case` arm before any ssh or filesystem work.
    """
    import os

    env = dict(os.environ, PATH=path)
    proc = subprocess.run(
        ["bash", str(SCRIPT), host, "--list"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    if "unknown host" in proc.stderr:
        return proc.stderr.strip()
    return None


def test_script_exists() -> None:
    assert SCRIPT.is_file(), f"{SCRIPT} missing — the test's own subject is gone"


@pytest.mark.parametrize("host", ["local", "pro", "mini", "air"])
def test_known_hosts_pass_the_allowlist(host: str, stub_path: str) -> None:
    """INNOCENCE: every real fleet node gets past the host check.

    `air` is the one this test was written for. The others are here so a future
    edit that narrows the allowlist cannot pass by only satisfying `air`.
    """
    assert _reject_reason(host, stub_path) is None, f"{host} was rejected by the host allowlist"


@pytest.mark.parametrize("host", ["m5", "nuzantara", "airm5", "", "localhost", "-"])
def test_unknown_hosts_are_still_refused(host: str, stub_path: str) -> None:
    """GUILT: widening the allowlist must not have turned it into a pass-through.

    `m5` is in this list on purpose — see the module docstring. It is a real ssh
    alias on Pro and a dead name on Mini, so it must not become a fleet-tool host.
    """
    reason = _reject_reason(host, stub_path)
    assert reason is not None, f"{host!r} was accepted by the host allowlist"
    assert "want local|pro|mini|air" in reason


def test_usage_comment_lists_the_same_hosts_as_the_allowlist() -> None:
    """The header comment is what a reader trusts; drift between it and the
    `case` arm is how the next person concludes a node is unsupported when it is
    supported (or the reverse)."""
    text = SCRIPT.read_text()
    assert "local|pro|mini|air) ;;" in text
    assert "# <host> is local|pro|mini|air." in text
    assert "want local|pro|mini|air" in text
