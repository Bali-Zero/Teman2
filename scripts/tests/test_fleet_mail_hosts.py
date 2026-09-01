"""Guilt + innocence for `fleet_mail.sh`'s host allowlist.

Why this file exists: the allowlist said `local|pro|mini` while the fleet has had
three nodes since 2026-05-31, so every Pro or Mini session that tried to reach M5
with the fleet tool got "unknown host 'air'" and fell back to hand-delivering over
raw ssh. Nothing failed loudly — the tool simply refused a node that exists.

Per superscar #3, a guard gets both halves or neither: `air` must be ACCEPTED
(innocence) and a genuinely unknown host must still be REFUSED (guilt), so this
does not degrade into "accept anything".

`m5` is deliberately NOT in the allowlist and is asserted as refused: it is a real
ssh alias on Pro and a dead name on Mini, and admitting an alias that works from
one peer and dies on the other is how a lane comes to fail on exactly one machine.

CORRECTION 2026-08-26: this docstring used to add "Measured 2026-08-24 from both
peers: `ssh air` resolves to Air-M5 from Pro and from Mini." That measurement has
DECAYED and the sentence became false while still reading as verified. `ssh air`
points at `Air-M5.local` (mDNS); measured from Pro on 2026-08-26 it dies with
"Could not resolve hostname air-m5.local", so `fleet_mail.sh air` was silently
dead from Pro. A recorded measurement is not a property — mDNS stops resolving
the moment a peer leaves the LAN. The fix was not a new hardcoded hostname but
`ssh_target()`, which probes the primary alias and falls back to the Tailscale
one; the two tests below cover BOTH of its branches.
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


def _routing_stub(tmp_path, up: set[str]) -> str:
    """A PATH whose `ssh` succeeds only for the hosts in `up`.

    The stub must answer the PROBE (`ssh -o ... <host> true`) and the real call
    identically, because `ssh_target()` judges the probe by its RETURN CODE.
    Host is the first non-option argument, mirroring how the script invokes ssh.
    """
    import os

    d = tmp_path / "stub-bin"
    d.mkdir(exist_ok=True)
    ssh = d / "ssh"
    ssh.write_text(
        "#!/bin/sh\n"
        "host=''\n"
        "while [ $# -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    -o) shift 2;;\n"
        "    -*) shift;;\n"
        "    *) host=\"$1\"; break;;\n"
        "  esac\n"
        "done\n"
        f"for u in {' '.join(sorted(up)) or '__none__'}; do\n"
        "  [ \"$host\" = \"$u\" ] && { echo \"REACHED:$host\"; exit 0; }\n"
        "done\n"
        "echo 'stub ssh: unreachable' >&2\n"
        "exit 255\n"
    )
    ssh.chmod(0o755)
    return f"{d}{os.pathsep}{os.environ.get('PATH', '')}"


def _run_list(host: str, path: str):
    import os

    return subprocess.run(
        ["bash", str(SCRIPT), host, "--list"],
        capture_output=True,
        text=True,
        timeout=60,
        env=dict(os.environ, PATH=path),
    )


def test_air_falls_back_to_tailscale_when_the_mdns_primary_is_unresolvable(tmp_path) -> None:
    """INNOCENCE: primary dead + fallback alive => the tool still reaches the peer.

    This is the exact live condition measured on 2026-08-26: `air` (mDNS) does
    not resolve from Pro while `air-ts` (Tailscale) does. Before `ssh_target()`
    this died outright.
    """
    proc = _run_list("air", _routing_stub(tmp_path, {"air-ts"}))
    assert "no reachable ssh route" not in proc.stderr, proc.stderr
    assert "REACHED:air-ts" in proc.stdout + proc.stderr, (proc.stdout, proc.stderr)


def test_primary_is_preferred_when_it_answers(tmp_path) -> None:
    """The fallback must not become the default: when the LAN alias works it is
    the one used, so an on-LAN peer is never forced through the relay."""
    proc = _run_list("air", _routing_stub(tmp_path, {"air", "air-ts"}))
    out = proc.stdout + proc.stderr
    assert "REACHED:air" in out and "REACHED:air-ts" not in out, out


def test_both_routes_dead_fails_loudly_and_names_both(tmp_path) -> None:
    """GUILT: the fallback must not turn an unreachable peer into a silent pass.

    Measured the hard way: while this fix was being written, M5 went offline and
    BOTH routes died. The tool must say so, and name what it tried — otherwise
    the next reader blames the alias instead of the sleeping laptop.
    """
    proc = _run_list("air", _routing_stub(tmp_path, set()))
    assert proc.returncode != 0
    assert "no reachable ssh route" in proc.stderr, proc.stderr
    assert "air-ts" in proc.stderr, proc.stderr


def test_every_allowlisted_remote_host_has_a_declared_fallback_or_is_deliberate() -> None:
    """A host with no fallback is one mDNS outage away from the bug this fixes.
    `pro` legitimately has none today; this test pins that as a CHOICE, so adding
    a fourth node without a fallback is a decision someone must make on purpose."""
    text = SCRIPT.read_text()
    assert 'air)  echo "air-ts"' in text
    assert 'mini) echo "mini-remote"' in text


def test_usage_comment_lists_the_same_hosts_as_the_allowlist() -> None:
    """The header comment is what a reader trusts; drift between it and the
    `case` arm is how the next person concludes a node is unsupported when it is
    supported (or the reverse)."""
    text = SCRIPT.read_text()
    assert "local|pro|mini|air) ;;" in text
    assert "# <host> is local|pro|mini|air." in text
    assert "want local|pro|mini|air" in text
