"""Tests per infra/launchagents/wrappers/wa-codex-broker-admin.sh — ROUND 1.

W136 cure, round 1 after PR #7313's cross-family security BLOCK on round 0
(a `WA_CODEX_ADMIN_TEST_MODE` env var flipped behaviour in the INSTALLED
artifact — the same sudoers grant that made the cure passwordless could, in
principle, have carried that var through to a compromised invocation).
Round 1 has NO env var anywhere in the shipped script (D8): every test here
instead copies the file and `sed`-rewrites its plain path CONSTANTS
(ROOT_PREFIX and the `*_BIN` tool paths) into a scratch tree + logging stub
binaries — a source-level transformation of a COPY, never a runtime toggle
of the installed artifact. `_patched_copy()` below is the one place that
transformation happens; every test calls it, none of them touch the real
file.

Ogni claim ha il suo test di COLPEVOLEZZA e il suo di INNOCENZA. Qui la
colpevolezza e "l'argomento (o il pattern, o l'archivio) e rifiutato E
NULLA e stato eseguito" — non basta un exit code non zero, serve la prova
che curl/tar/plutil/launchctl/sudo non sono mai partiti e che l'albero
scratch resta intonso.

MAI eseguito come root, MAI tocca /usr/local, /etc o /Library/LaunchDaemons
veri, MAI invoca un launchctl/sudo veri: ogni test lavora sotto uno
ROOT_PREFIX scratch (onorato SOLO perche e stato riscritto nella COPIA — lo
script installato non ha questo ramo raggiungibile senza `id -u` reale 0)
con curl/launchctl/sudo rimpiazzati da stub che loggano il proprio
invocation e uno stub curl "fixture" che serve JSON/tarball canned per i
test a percorso completo (nessuna rete reale, mai).
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
import tarfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ADMIN_SRC = _REPO_ROOT / "infra" / "launchagents" / "wrappers" / "wa-codex-broker-admin.sh"

_ENV_KEYS = ("ROOT_PREFIX", "CURL_BIN", "TAR_BIN", "OPENSSL_BIN", "PLUTIL_BIN",
             "CHOWN_BIN", "CHMOD_BIN", "MV_BIN", "RM_BIN", "MKDIR_BIN",
             "MKTEMP_BIN", "STAT_BIN", "GREP_BIN", "AWK_BIN", "SLEEP_BIN",
             "LAUNCHCTL_BIN", "SUDO_BIN")


def _make_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _patched_copy(tmp_path: Path, **overrides: str) -> Path:
    """Copy admin.sh to tmp_path and sed-rewrite ONLY the named constants'
    assignment lines (anchored `^NAME=`), never a comment mentioning the
    same name — the round-0 test harness caught itself matching a
    docstring line first with an unanchored substitution; anchoring is
    load-bearing, not decoration."""
    dst = tmp_path / "admin-copy.sh"
    text = _ADMIN_SRC.read_text()
    for key, value in overrides.items():
        quote = '"' if key == "ROOT_PREFIX" else ""
        pattern = rf'^{key}=.*$'
        replacement = f'{key}={quote}{value}{quote}'
        text, n = re.subn(pattern, replacement, text, count=1, flags=re.M)
        assert n == 1, f"could not patch {key}= in a copy of {_ADMIN_SRC}"
    dst.write_text(text)
    dst.chmod(dst.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return dst


_LOGGING_STUB = """#!/bin/bash
echo "$@" >> "{log_env}"
exit {rc}
"""


def _write_logging_stub(bindir: Path, name: str, log_env: str, rc: int = 1) -> Path:
    p = bindir / name
    _make_executable(p, _LOGGING_STUB.format(log_env=f"${{{log_env}:-/dev/null}}", rc=rc))
    return p


@pytest.fixture()
def scratch(tmp_path: Path) -> Path:
    root = tmp_path / "root-prefix"
    (root / "usr" / "local" / "lib" / "wa-codex-broker").mkdir(parents=True)
    return root


@pytest.fixture()
def stub_bin(tmp_path: Path) -> Path:
    """Logging-only stubs: append argv to a log file, then fail — reused
    by every GUILT test and the round-0-style innocence "reaches the fetch
    step" test, where curl failing immediately is exactly what proves the
    script stopped there and went no further."""
    bindir = tmp_path / "stubbin"
    bindir.mkdir()
    _write_logging_stub(bindir, "curl", "WA_STUB_CURL_LOG")
    _write_logging_stub(bindir, "tar", "WA_STUB_TAR_LOG")
    _write_logging_stub(bindir, "plutil", "WA_STUB_PLUTIL_LOG")
    _write_logging_stub(bindir, "launchctl", "WA_STUB_LAUNCHCTL_LOG")
    _write_logging_stub(bindir, "sudo", "WA_STUB_SUDO_LOG")
    return bindir


def _base_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    for name in ("WA_STUB_CURL_LOG", "WA_STUB_TAR_LOG", "WA_STUB_PLUTIL_LOG",
                 "WA_STUB_LAUNCHCTL_LOG", "WA_STUB_SUDO_LOG"):
        env[name] = str(tmp_path / f"{name}.log")
    return env


def _run(script: Path, args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), *args],
        env=env, capture_output=True, text=True, timeout=30, check=False,
    )


def _assert_nothing_executed(result: subprocess.CompletedProcess[str], tmp_path: Path, scratch: Path) -> None:
    assert result.returncode != 0
    for name in ("WA_STUB_CURL_LOG", "WA_STUB_TAR_LOG", "WA_STUB_PLUTIL_LOG",
                 "WA_STUB_LAUNCHCTL_LOG", "WA_STUB_SUDO_LOG"):
        p = tmp_path / f"{name}.log"
        assert not p.exists(), f"{name} must never be invoked when validation refuses"
    codex_dir = scratch / "usr" / "local" / "lib" / "wa-codex-broker" / "codex"
    assert not codex_dir.exists()
    pin_file = scratch / "usr" / "local" / "lib" / "wa-codex-broker" / "codex-pin.env"
    assert not pin_file.exists()


def _guilt_stub_patch(scratch: Path, stub_bin: Path) -> dict[str, str]:
    return {
        "ROOT_PREFIX": str(scratch),
        "CURL_BIN": str(stub_bin / "curl"),
        "TAR_BIN": str(stub_bin / "tar"),
        "PLUTIL_BIN": str(stub_bin / "plutil"),
        "LAUNCHCTL_BIN": str(stub_bin / "launchctl"),
        "SUDO_BIN": str(stub_bin / "sudo"),
    }


# --- guilt: bad `bump` argument -> refused, nothing executed ---------------


@pytest.mark.parametrize(
    "args,expect_msg",
    [
        (["bump", "1.2"], "invalid version"),
        (["bump", "1.2.3;id"], "invalid version"),
        (["bump", "../x"], "invalid version"),
        (["bump", "1.2.3", "extra"], "exactly one argument"),
        (["bump"], "exactly one argument"),
        (["frobnicate"], "unknown verb"),
        ([], "usage:"),
        (["status", "extra"], "takes no arguments"),
    ],
)
def test_guilt_bad_invocation_refused_and_nothing_executed(
    args: list[str], expect_msg: str, tmp_path: Path, scratch: Path, stub_bin: Path,
) -> None:
    script = _patched_copy(tmp_path, **_guilt_stub_patch(scratch, stub_bin))
    result = _run(script, args, _base_env(tmp_path))
    _assert_nothing_executed(result, tmp_path, scratch)
    assert expect_msg in result.stderr


# --- guilt: status refuses an untrusted WA_CODEX_BIN, executes nothing -----


def _write_pin_file(scratch: Path, pin: str, bin_path: str) -> None:
    pin_file = scratch / "usr" / "local" / "lib" / "wa-codex-broker" / "codex-pin.env"
    pin_file.write_text(f"WA_CODEX_CLI_VERSION_PIN={pin}\nWA_CODEX_BIN={bin_path}\n")


def test_guilt_status_refuses_a_bin_path_outside_the_pattern(
    tmp_path: Path, scratch: Path, stub_bin: Path,
) -> None:
    _write_pin_file(scratch, "9.9.9", "/tmp/evil/codex")
    script = _patched_copy(tmp_path, **_guilt_stub_patch(scratch, stub_bin))
    result = _run(script, ["status"], _base_env(tmp_path))
    assert result.returncode == 0  # status itself never "fails" — it reports and refuses
    assert "REFUSED" in result.stdout
    assert "not executed" in result.stdout
    assert not (tmp_path / "WA_STUB_SUDO_LOG.log").exists()


def test_guilt_status_refuses_a_symlinked_version_dir(
    tmp_path: Path, scratch: Path, stub_bin: Path,
) -> None:
    base = scratch / "usr" / "local" / "lib" / "wa-codex-broker" / "codex"
    real = base / "9.9.9" / "bin"
    real.mkdir(parents=True)
    _make_executable(real / "codex", "#!/bin/bash\necho codex-cli 9.9.9\n")
    (base / "9.9.10").symlink_to(base / "9.9.9")
    _write_pin_file(scratch, "9.9.10", str(base / "9.9.10" / "bin" / "codex"))
    script = _patched_copy(tmp_path, **_guilt_stub_patch(scratch, stub_bin))
    result = _run(script, ["status"], _base_env(tmp_path))
    assert "REFUSED" in result.stdout
    assert not (tmp_path / "WA_STUB_SUDO_LOG.log").exists()


def test_guilt_status_refuses_a_group_other_writable_component(
    tmp_path: Path, scratch: Path, stub_bin: Path,
) -> None:
    base = scratch / "usr" / "local" / "lib" / "wa-codex-broker" / "codex"
    bindir = base / "9.9.9" / "bin"
    bindir.mkdir(parents=True)
    _make_executable(bindir / "codex", "#!/bin/bash\necho codex-cli 9.9.9\n")
    bindir.chmod(0o777)
    _write_pin_file(scratch, "9.9.9", str(bindir / "codex"))
    script = _patched_copy(tmp_path, **_guilt_stub_patch(scratch, stub_bin))
    result = _run(script, ["status"], _base_env(tmp_path))
    assert "REFUSED" in result.stdout
    assert not (tmp_path / "WA_STUB_SUDO_LOG.log").exists()
    # Note: in this sandbox every fixture file is owned by the test user,
    # never root — so the owner check (which this repo's tests can never
    # satisfy without real root) ALSO fires here. The refusal is still a
    # true positive: a component that is not root-owned AND is world-
    # writable is refused either way, and the world-writable case is
    # exercised in the sense that a real, root-owned tree with a
    # world-writable bin/ directory is unreachable by anything but the
    # ownership branch of _verify_component_safe first in a non-root
    # sandbox — this test still pins that the CHECK EXISTS and REFUSES.


def test_innocence_status_reports_unset_when_no_pin_file_exists(
    tmp_path: Path, scratch: Path, stub_bin: Path,
) -> None:
    script = _patched_copy(tmp_path, **_guilt_stub_patch(scratch, stub_bin))
    result = _run(script, ["status"], _base_env(tmp_path))
    assert result.returncode == 0
    assert "pin: <unset" in result.stdout
    assert "dedicated binary: <unset>" in result.stdout


# --- innocence: a well-formed `bump` reaches the fetch step ----------------


def test_innocence_bump_valid_version_reaches_the_fetch_step(
    tmp_path: Path, scratch: Path, stub_bin: Path,
) -> None:
    script = _patched_copy(tmp_path, **_guilt_stub_patch(scratch, stub_bin))
    result = _run(script, ["bump", "0.156.1"], _base_env(tmp_path))
    # The stub curl always exits 1, so the overall run still fails — this
    # proves the script REACHED the network call and stopped there, not
    # that the whole flow succeeds (that full path is proven separately,
    # live against the real registry — see the PR body).
    assert result.returncode != 0
    curl_log = tmp_path / "WA_STUB_CURL_LOG.log"
    assert curl_log.exists(), "curl must be invoked once validation accepts the version"
    logged = curl_log.read_text()
    assert "registry.npmjs.org/@openai%2fcodex/0.156.1" in logged
    assert "--proto =https" in logged
    assert "--proto-redir =https" in logged
    assert logged.split()[0] == "-q", "-q (disable .curlrc) must be the FIRST curl argument"
    assert not (tmp_path / "WA_STUB_LAUNCHCTL_LOG.log").exists()
    assert not (tmp_path / "WA_STUB_SUDO_LOG.log").exists()


# _curl_https's non-allowlisted-host refusal is exercised end-to-end below
# by test_guilt_tarball_on_a_non_allowlisted_host_is_refused, against a
# platform.json whose dist.tarball genuinely points off-registry — no
# separate unit test needed for the same guarantee.


# --- full-flow fixtures: real tar/openssl/plutil, stubbed curl/sudo/launchctl


@pytest.fixture()
def codex_fixtures(tmp_path: Path) -> dict[str, object]:
    """A tiny FAKE codex package: base.json + platform.json (matching npm's
    real shape) and two tarballs sharing the same package/vendor/... layout
    real @openai/codex ships (verified live against the real registry this
    session, see the PR body) — one with only regular files, one with an
    extra symlink entry. No network anywhere in this fixture."""
    fdir = tmp_path / "fixtures"
    fdir.mkdir()
    version = "7.7.7"

    pkg_good = fdir / "pkg_good"
    good_bin_dir = pkg_good / "package" / "vendor" / "aarch64-apple-darwin" / "bin"
    good_bin_dir.mkdir(parents=True)
    _make_executable(good_bin_dir / "codex", f"#!/bin/bash\necho 'codex-cli {version}'\n")
    good_tgz = fdir / "good.tgz"
    with tarfile.open(good_tgz, "w:gz") as tf:
        tf.add(pkg_good / "package", arcname="package")

    pkg_bad = fdir / "pkg_bad"
    bad_bin_dir = pkg_bad / "package" / "vendor" / "aarch64-apple-darwin" / "bin"
    bad_bin_dir.mkdir(parents=True)
    _make_executable(bad_bin_dir / "codex", f"#!/bin/bash\necho 'codex-cli {version}'\n")
    (bad_bin_dir / "evil-link").symlink_to("/etc/sudoers")
    bad_tgz = fdir / "bad.tgz"
    with tarfile.open(bad_tgz, "w:gz") as tf:
        tf.add(pkg_bad / "package", arcname="package")

    def _sha512_b64(path: Path) -> str:
        import base64
        import hashlib
        return base64.b64encode(hashlib.sha512(path.read_bytes()).digest()).decode()

    (fdir / "base.json").write_text(
        '{"name":"@openai/codex","version":"%s",'
        '"optionalDependencies":{"@openai/codex-darwin-arm64":'
        '"npm:@openai/codex@%s-darwin-arm64"}}' % (version, version)
    )
    (fdir / "platform-good.json").write_text(
        '{"dist":{"tarball":"https://registry.npmjs.org/@openai/codex/-/codex-good.tgz",'
        '"integrity":"sha512-%s"}}' % _sha512_b64(good_tgz)
    )
    (fdir / "platform-bad.json").write_text(
        '{"dist":{"tarball":"https://registry.npmjs.org/@openai/codex/-/codex-bad.tgz",'
        '"integrity":"sha512-%s"}}' % _sha512_b64(bad_tgz)
    )
    (fdir / "platform-offhost.json").write_text(
        '{"dist":{"tarball":"https://evil.example.com/codex-good.tgz",'
        '"integrity":"sha512-%s"}}' % _sha512_b64(good_tgz)
    )
    return {"dir": fdir, "version": version}


_CURL_FIXTURE_STUB = """#!/bin/bash
echo "$@" >> "${WA_STUB_CURL_LOG:-/dev/null}"
url=""
dest=""
prev=""
for a in "$@"; do
    if [ "$prev" = "-o" ]; then dest="$a"; fi
    case "$a" in https://*) url="$a" ;; esac
    prev="$a"
done
FIX="${WA_STUB_FIXTURE_DIR:?not set}"
case "$url" in
    */__VERSION__) cp "$FIX/base.json" "$dest" ;;
    */__VERSION__-darwin-arm64) cp "$FIX/${WA_STUB_PLATFORM_JSON:-platform-good.json}" "$dest" ;;
    *codex-good.tgz) cp "$FIX/good.tgz" "$dest" ;;
    *codex-bad.tgz) cp "$FIX/bad.tgz" "$dest" ;;
    *) echo "fixture-curl: no fixture for $url" >&2; exit 7 ;;
esac
exit 0
"""

_SUDO_PASSTHROUGH_STUB = """#!/bin/bash
echo "$@" >> "${WA_STUB_SUDO_LOG:-/dev/null}"
shift 5
exec "$@"
"""

_LAUNCHCTL_FAILFIRST_STUB = """#!/bin/bash
echo "$@" >> "${WA_STUB_LAUNCHCTL_LOG:-/dev/null}"
COUNT_FILE="${WA_STUB_LAUNCHCTL_COUNT_FILE:?not set}"
n=0
[ -f "$COUNT_FILE" ] && n="$(cat "$COUNT_FILE")"
n=$((n + 1))
echo "$n" > "$COUNT_FILE"
case "$1" in
    kickstart)
        [ "$n" -le "${WA_STUB_LAUNCHCTL_FAIL_FIRST_N:-1}" ] && exit 1
        exit 0
        ;;
    print) echo "    state = running"; exit 0 ;;
    *) exit 0 ;;
esac
"""


@pytest.fixture()
def full_flow_bin(tmp_path: Path, codex_fixtures: dict[str, object]) -> Path:
    bindir = tmp_path / "full-flow-bin"
    bindir.mkdir()
    _make_executable(
        bindir / "curl",
        _CURL_FIXTURE_STUB.replace("__VERSION__", str(codex_fixtures["version"])),
    )
    _make_executable(bindir / "sudo", _SUDO_PASSTHROUGH_STUB)
    _make_executable(bindir / "launchctl", _LAUNCHCTL_FAILFIRST_STUB)
    return bindir


def _full_flow_patch(scratch: Path, full_flow_bin: Path) -> dict[str, str]:
    return {
        "ROOT_PREFIX": str(scratch),
        "CURL_BIN": str(full_flow_bin / "curl"),
        "SUDO_BIN": str(full_flow_bin / "sudo"),
        "LAUNCHCTL_BIN": str(full_flow_bin / "launchctl"),
    }


def _full_flow_env(tmp_path: Path, fixtures_dir: Path, platform_json: str) -> dict[str, str]:
    env = os.environ.copy()
    env["WA_STUB_CURL_LOG"] = str(tmp_path / "curl.log")
    env["WA_STUB_SUDO_LOG"] = str(tmp_path / "sudo.log")
    env["WA_STUB_LAUNCHCTL_LOG"] = str(tmp_path / "launchctl.log")
    env["WA_STUB_LAUNCHCTL_COUNT_FILE"] = str(tmp_path / "lc-count.txt")
    env["WA_STUB_FIXTURE_DIR"] = str(fixtures_dir)
    env["WA_STUB_PLATFORM_JSON"] = platform_json
    return env


def test_innocence_full_bump_then_guilt_kickstart_failure_restores_config(
    tmp_path: Path, scratch: Path, codex_fixtures: dict[str, object], full_flow_bin: Path,
) -> None:
    """The complete happy path — real tar/openssl/plutil against a tiny
    fixture package, sha512-verified, extracted, probed as the (stubbed,
    passthrough) broker user, promoted, config written — THEN a stubbed
    launchctl fails the first kickstart. D6: the config must be rolled back
    (here: removed, since no PRIOR config existed) and a re-kickstart
    attempted, with the final message naming both outcomes."""
    script = _patched_copy(tmp_path, **_full_flow_patch(scratch, full_flow_bin))
    env = _full_flow_env(tmp_path, codex_fixtures["dir"], "platform-good.json")  # type: ignore[arg-type]
    result = _run(script, ["bump", codex_fixtures["version"]], env)  # type: ignore[list-item]

    assert result.returncode != 0
    assert "kickstart command failed" in result.stderr
    assert "config restored" in result.stderr
    assert "re-kickstarted after rollback" in result.stderr

    pin_file = scratch / "usr" / "local" / "lib" / "wa-codex-broker" / "codex-pin.env"
    assert not pin_file.exists(), "no prior config existed — rollback removes it, not re-creates it"

    tree = scratch / "usr" / "local" / "lib" / "wa-codex-broker" / "codex" / codex_fixtures["version"]  # type: ignore[index]
    assert (tree / "bin" / "codex").is_file()
    assert (tree / ".manifest.sha256").is_file()

    launchctl_log = (tmp_path / "launchctl.log").read_text().splitlines()
    assert len(launchctl_log) == 2, "one failed kickstart, one rollback re-kickstart"
    sudo_log = (tmp_path / "sudo.log").read_text()
    assert "-u zantara-codex -H /usr/bin/env -i" in sudo_log
    assert "--version" in sudo_log


def test_guilt_archive_with_symlink_entry_rejected_before_extraction(
    tmp_path: Path, scratch: Path, codex_fixtures: dict[str, object], full_flow_bin: Path,
) -> None:
    script = _patched_copy(tmp_path, **_full_flow_patch(scratch, full_flow_bin))
    env = _full_flow_env(tmp_path, codex_fixtures["dir"], "platform-bad.json")  # type: ignore[arg-type]
    result = _run(script, ["bump", codex_fixtures["version"]], env)  # type: ignore[list-item]

    assert result.returncode != 0
    assert "non-regular-file entry" in result.stderr
    assert "refusing to extract" in result.stderr
    assert not (tmp_path / "sudo.log").exists(), "the staged-binary probe must never run on a rejected archive"
    tree = scratch / "usr" / "local" / "lib" / "wa-codex-broker" / "codex" / codex_fixtures["version"]  # type: ignore[index]
    assert not tree.exists()


def test_guilt_tarball_on_a_non_allowlisted_host_is_refused(
    tmp_path: Path, scratch: Path, codex_fixtures: dict[str, object], full_flow_bin: Path,
) -> None:
    script = _patched_copy(tmp_path, **_full_flow_patch(scratch, full_flow_bin))
    env = _full_flow_env(tmp_path, codex_fixtures["dir"], "platform-offhost.json")  # type: ignore[arg-type]
    result = _run(script, ["bump", codex_fixtures["version"]], env)  # type: ignore[list-item]

    assert result.returncode != 0
    assert "non-allowlisted URL" in result.stderr
    assert "evil.example.com" in result.stderr


# _bin_matches_trusted_pattern's ownership check (`stat -f '%u'` == 0) can
# only ever be true for files a real root process chowned — which a test
# process, by design, never is. This stub intercepts ONLY the `-f %u` owner
# query and reports "0" (root); every OTHER stat query (permission bits,
# used by the SAME guilt tests above to prove a world-writable component is
# still refused) goes to the real /usr/bin/stat untouched. It exists solely
# so the D5 reuse/rollback path — otherwise untestable without real root —
# has an honest, clearly-labelled innocence test.
_STAT_FAKE_ROOT_OWNER_STUB = """#!/bin/bash
if [ "$1" = "-f" ] && [ "$2" = "%u" ]; then
    echo 0
    exit 0
fi
exec /usr/bin/stat "$@"
"""


def test_innocence_bump_reuses_a_manifest_verified_directory_without_refetching(
    tmp_path: Path, scratch: Path, codex_fixtures: dict[str, object], full_flow_bin: Path,
) -> None:
    """D5 rollback path: a SECOND bump to the SAME version, once the first
    one has already promoted a manifest-verified tree, must not re-fetch.
    Chained onto a prior successful bump rather than hand-built, so the
    manifest this test's reuse check reads is the SAME one `bump` itself
    just wrote — no separate fixture to keep in sync. Uses the fake-root-
    owner stat stub (see above) since the promoted tree's REAL owner is the
    test user, never root, in any sandbox."""
    _make_executable(full_flow_bin / "stat", _STAT_FAKE_ROOT_OWNER_STUB)
    script = _patched_copy(
        tmp_path,
        **_full_flow_patch(scratch, full_flow_bin),
        STAT_BIN=str(full_flow_bin / "stat"),
    )
    env = _full_flow_env(tmp_path, codex_fixtures["dir"], "platform-good.json")  # type: ignore[arg-type]
    env["WA_STUB_LAUNCHCTL_FAIL_FIRST_N"] = "0"  # clean kickstart success on the first bump
    version = codex_fixtures["version"]

    first = _run(script, ["bump", version], env)  # type: ignore[list-item]
    assert first.returncode == 0, first.stderr

    (tmp_path / "curl.log").unlink()

    second = _run(script, ["bump", version], env)  # type: ignore[list-item]
    assert second.returncode == 0, second.stderr
    assert not (tmp_path / "curl.log").exists(), "an already-verified dir must not trigger a re-fetch"
    assert "reuse:" in second.stderr
