"""Tests for scripts/install_wa_codex_pinned.sh — spec v2 (supersedes PR
#7313, which took two cross-family security BLOCKs: round 0, 3 CRITICAL;
round 1 built from a spec, 3 HIGH — first install unreachable, archive
filter fail-open under pipefail/SIGPIPE, installer missing the wrapper).

The shipped script has NO env-var or flag test-mode branch (S10). Every
test here instead copies the file and `sed`-rewrites its plain path/
identity CONSTANTS (ROOT_PREFIX, TRUST_OWNER, TRUST_GROUP, BROKER_USER,
the `*_BIN` tool paths) into a scratch tree — `_patched_copy()` below is
the one place that transformation happens. ROOT_PREFIX="" in the real
script gates the root check too, so a patched copy naturally runs
unprivileged against its own scratch tree without any separate toggle.

MAI eseguito come root, MAI tocca /usr/local, /etc o launchctl veri: ogni
test lavora sotto uno ROOT_PREFIX scratch, con curl/launchctl/sudo
rimpiazzati da stub — un curl "fixture" serve JSON/tarball canned, mai
rete reale.
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import re
import stat
import subprocess
import tarfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INSTALLER = _REPO_ROOT / "scripts" / "install_wa_codex_pinned.sh"
_VERSION = "9.9.9"
_PLATFORM_VERSION = "9.9.8"

_PATCHABLE_KEYS = (
    "ROOT_PREFIX", "TRUST_OWNER", "TRUST_GROUP", "BROKER_USER", "WRAPPER_SRC",
    "STAT_BIN", "CURL_BIN", "TAR_BIN", "OPENSSL_BIN", "PLUTIL_BIN",
    "AWK_BIN", "MKTEMP_BIN", "CHOWN_BIN", "CHMOD_BIN", "MV_BIN", "RM_BIN",
    "MKDIR_BIN", "FIND_BIN", "SUDO_BIN", "LAUNCHCTL_BIN", "SLEEP_BIN",
    "INSTALL_BIN",
)


def _make_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _patched_copy(tmp_path: Path, name: str = "installer-copy.sh", **overrides: str) -> Path:
    """Copy the installer and sed-rewrite ONLY the named constants'
    assignment lines (anchored `^NAME=`, never a comment mentioning the
    same name)."""
    dst = tmp_path / name
    text = _INSTALLER.read_text()
    for key, value in overrides.items():
        assert key in _PATCHABLE_KEYS, f"{key} is not a declared patchable constant"
        pattern = rf'^{key}=.*$'
        replacement = f'{key}="{value}"'
        text, n = re.subn(pattern, replacement, text, count=1, flags=re.M)
        assert n == 1, f"could not patch {key}= in a copy of {_INSTALLER}"
    dst.write_text(text)
    dst.chmod(dst.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return dst


def _broken_s4_copy(tmp_path: Path, **overrides: str) -> Path:
    """A deliberately-flawed variant: the fail-closed, whole-file awk pass
    (S4) is replaced by an early-terminating `head`-limited read — the same
    vulnerability CLASS PR #7313 round 2 found in its `grep -q` pipeline
    (a reader that stops before the archive's true end can pass a large
    archive with an unsafe entry buried past the point it stopped
    reading). Used ONLY as the RED half of a guilt test's RED/GREEN pair —
    never mistaken for the shipped artifact."""
    dst = _patched_copy(tmp_path, name="installer-copy-broken-s4.sh", **overrides)
    text = dst.read_text()
    start = text.index('LISTING="${_STAGING_DIR}/.listing.txt"')
    end = text.index("# --- S5:")
    assert start != -1 and end != -1 and end > start
    broken_block = (
        'LISTING="${_STAGING_DIR}/.listing.txt"\n'
        'LC_ALL=C "$TAR_BIN" -tvzf "$TGZ" > "$LISTING" || die "listing failed"\n'
        '# BROKEN ON PURPOSE: only the first 1000 lines are inspected — a\n'
        '# large archive with the unsafe entry past that point is missed.\n'
        'if "$AWK_BIN" \'NR<=1000{t=substr($0,1,1); if (t!="-" && t!="d") bad=1} END{exit bad?1:0}\' "$LISTING"; then\n'
        '    :\n'
        'else\n'
        '    die "archive contains a symlink/hardlink/absolute-path/.. entry"\n'
        'fi\n'
    )
    text = text[:start] + broken_block + text[end:]
    dst.write_text(text)
    dst.chmod(dst.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return dst


_LOGGING_STUB = """#!/bin/bash
echo "$@" >> "{log}"
exit 1
"""


def _write_logging_stub(bindir: Path, name: str, log: Path) -> Path:
    p = bindir / name
    _make_executable(p, _LOGGING_STUB.format(log=log))
    return p


@pytest.fixture()
def scratch(tmp_path: Path) -> Path:
    """ROOT_PREFIX scratch tree — RUNTIME_DIR pre-planted, owned by the
    test runner (this process's own uid), 0755, not a symlink — the S2
    trust-root precondition scripts/provision_zantara_codex.sh normally
    guarantees for real."""
    root = tmp_path / "root-prefix"
    runtime = root / "usr" / "local" / "lib" / "wa-codex-broker"
    runtime.mkdir(parents=True, mode=0o755)
    # /usr/local/libexec pre-exists on a real host (provision_zantara_codex.sh
    # already created it) — install(1) does not create missing parents.
    (root / "usr" / "local" / "libexec").mkdir(mode=0o755)
    return root


@pytest.fixture()
def stub_bin(tmp_path: Path) -> Path:
    """Logging-only stubs (append argv, then fail) for the tools a GUILT
    test must prove never ran."""
    bindir = tmp_path / "stubbin"
    bindir.mkdir()
    for tool in ("curl", "tar", "plutil", "launchctl"):
        _write_logging_stub(bindir, tool, tmp_path / f"{tool}.log")
    return bindir


def _self_patch_kwargs(scratch: Path, **more: str) -> dict[str, str]:
    return {
        "ROOT_PREFIX": str(scratch),
        "TRUST_OWNER": os.environ.get("USER") or os.environ.get("LOGNAME") or "root",
        "TRUST_GROUP": _current_group(),
        **more,
    }


def _current_group() -> str:
    import grp
    return grp.getgrgid(os.getgid()).gr_name


def _run(script: Path, args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(
        ["bash", str(script), *args],
        env=full_env, capture_output=True, text=True, timeout=60, check=False,
    )


# ---------------------------------------------------------------------------
# S1 — argv validation is FIRST, pure bash builtins, no external command
# runs before it.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [[], ["1.2"], ["1.2.3.4"], ["1.2.3-beta"], ["1.2.3;id"], ["../x"], ["1.2.3", "extra"], ["v1.2.3"]],
)
def test_guilt_bad_argv_usage_exit_2(args: list[str]) -> None:
    result = _run(_INSTALLER, args)
    assert result.returncode == 2
    assert "usage:" in result.stderr


@pytest.mark.parametrize("args", [[], ["1.2"], ["1.2.3", "extra"]])
def test_guilt_bad_argv_traces_zero_external_commands(args: list[str], tmp_path: Path) -> None:
    """`bash -x` trace on a bad invocation must show ZERO absolute-path
    external command invocations — the whole argv gate is pure bash
    builtins (arithmetic test, `[[ =~ ]]`, `printf`)."""
    result = subprocess.run(
        ["bash", "-x", str(_INSTALLER), *args],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 2
    external_calls = [
        line for line in result.stderr.splitlines()
        if line.startswith("+") and re.search(r"^\+\s+/(usr|bin|sbin)", line)
    ]
    assert external_calls == [], f"argv gate invoked external commands: {external_calls}"


def test_innocence_valid_argv_reaches_the_root_check() -> None:
    """A well-formed version string passes the argv gate and reaches the
    NEXT gate (a different, distinguishable refusal message) — proving S1
    let a good value through rather than accidentally rejecting everything."""
    result = _run(_INSTALLER, ["9.9.9"])
    assert result.returncode == 1
    assert "must run as root" in result.stderr
    assert "usage:" not in result.stderr


# ---------------------------------------------------------------------------
# S2 — trust root: RUNTIME_DIR must pre-exist, root:wheel (patched:
# TRUST_OWNER:TRUST_GROUP), not group/other-writable, not a symlink.
# ---------------------------------------------------------------------------


def test_guilt_trust_root_missing_refuses(tmp_path: Path, stub_bin: Path) -> None:
    scratch_root = tmp_path / "no-runtime-dir"
    scratch_root.mkdir()
    copy = _patched_copy(
        tmp_path, ROOT_PREFIX=str(scratch_root), TRUST_OWNER="root", TRUST_GROUP="wheel",
        CURL_BIN=str(stub_bin / "curl"),
    )
    result = _run(copy, ["9.9.9"])
    assert result.returncode == 1
    assert "does not exist" in result.stderr
    assert not (tmp_path / "curl.log").exists()


def test_guilt_trust_root_symlink_refuses(tmp_path: Path, scratch: Path, stub_bin: Path) -> None:
    real = scratch.parent / "elsewhere"
    real.mkdir()
    runtime = scratch / "usr" / "local" / "lib" / "wa-codex-broker"
    runtime.rmdir()
    runtime.symlink_to(real)
    copy = _patched_copy(tmp_path, **_self_patch_kwargs(scratch, CURL_BIN=str(stub_bin / "curl")))
    result = _run(copy, ["9.9.9"])
    assert result.returncode == 1
    assert "is a symlink" in result.stderr
    assert not (tmp_path / "curl.log").exists()


def test_guilt_trust_root_group_writable_refuses(tmp_path: Path, scratch: Path, stub_bin: Path) -> None:
    runtime = scratch / "usr" / "local" / "lib" / "wa-codex-broker"
    runtime.chmod(0o775)
    copy = _patched_copy(tmp_path, **_self_patch_kwargs(scratch, CURL_BIN=str(stub_bin / "curl")))
    result = _run(copy, ["9.9.9"])
    assert result.returncode == 1
    assert "group/other writable" in result.stderr
    assert not (tmp_path / "curl.log").exists()


def test_innocence_trust_root_ok_reaches_download(tmp_path: Path, scratch: Path, stub_bin: Path) -> None:
    copy = _patched_copy(tmp_path, **_self_patch_kwargs(scratch, CURL_BIN=str(stub_bin / "curl")))
    result = _run(copy, ["9.9.9"])
    assert result.returncode == 1
    assert "npm registry lookup failed" in result.stderr
    codex_dir = scratch / "usr" / "local" / "lib" / "wa-codex-broker" / "codex"
    assert codex_dir.is_dir()
    assert not codex_dir.is_symlink()


# ---------------------------------------------------------------------------
# Full-pipeline fixture — a REAL fake npm registry served by a curl stub,
# a REAL tarball, REAL tar/openssl/plutil/find/chown, so the S3-S6 chain
# runs for real end to end without any network access.
# ---------------------------------------------------------------------------


def _b64_sha512(data: bytes) -> str:
    return base64.b64encode(hashlib.sha512(data).digest()).decode()


def _build_good_tarball(dest: Path, version: str = _VERSION) -> None:
    codex_script = f'#!/bin/sh\necho "codex-cli {version}"\n'.encode()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name="package/vendor/aarch64-apple-darwin/bin/codex")
        info.size = len(codex_script)
        info.mode = 0o755
        tf.addfile(info, io.BytesIO(codex_script))
    dest.write_bytes(buf.getvalue())


def _build_malicious_tarball(dest: Path, kind: str) -> None:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for i in range(20_000 if kind == "trailing_symlink_20k" else 5):
            info = tarfile.TarInfo(name=f"package/vendor/aarch64-apple-darwin/f{i:05d}")
            info.size = 0
            tf.addfile(info, io.BytesIO(b""))
        if kind == "trailing_symlink_20k":
            link = tarfile.TarInfo(name="package/vendor/aarch64-apple-darwin/evil-link")
            link.type = tarfile.SYMTYPE
            link.linkname = "/etc/sudoers"
            tf.addfile(link)
        elif kind == "hardlink":
            target = tarfile.TarInfo(name="package/vendor/aarch64-apple-darwin/target")
            target.size = 0
            tf.addfile(target, io.BytesIO(b""))
            hl = tarfile.TarInfo(name="package/vendor/aarch64-apple-darwin/evil-hardlink")
            hl.type = tarfile.LNKTYPE
            hl.linkname = "package/vendor/aarch64-apple-darwin/target"
            tf.addfile(hl)
        elif kind == "absolute_path":
            info = tarfile.TarInfo(name="/etc/evil-absolute")
            info.size = 0
            tf.addfile(info, io.BytesIO(b""))
        elif kind == "dotdot_path":
            info = tarfile.TarInfo(name="package/vendor/aarch64-apple-darwin/../../../etc/evil-dotdot")
            info.size = 0
            tf.addfile(info, io.BytesIO(b""))
        else:
            raise ValueError(kind)
    dest.write_bytes(buf.getvalue())


_CURL_FIXTURE_STUB = """#!/bin/bash
args=("$@")
n=${{#args[@]}}
dest="${{args[$((n-1))]}}"
url="${{args[$((n-3))]}}"
echo "$url" >> "{log}"
case "$url" in
    {base_url}) cp "{base_json}" "$dest" ;;
    {platform_url}) cp "{platform_json}" "$dest" ;;
    {tarball_url}) cp "{tarball}" "$dest" ;;
    *) exit 1 ;;
esac
"""

_SUDO_PASSTHROUGH_STUB = """#!/bin/bash
# args: -u USER -H /usr/bin/env -i BIN --version — drop the user-switch,
# exec the rest for real (this process's own identity, never root).
shift 3
exec "$@"
"""

_LAUNCHCTL_FIXTURE_STUB = """#!/bin/bash
echo "$@" >> "{log}"
case "$1" in
    kickstart) exit 0 ;;
    print) echo "    state = running"; exit 0 ;;
    *) exit 1 ;;
esac
"""


@pytest.fixture()
def registry_fixture(tmp_path: Path):
    fx = tmp_path / "fixture"
    fx.mkdir()
    base_url = f"https://registry.npmjs.org/@openai%2fcodex/{_VERSION}"
    platform_url = f"https://registry.npmjs.org/@openai%2fcodex/{_PLATFORM_VERSION}"
    tarball_url = "https://registry.npmjs.org/@openai/codex-darwin-arm64/-/codex-darwin-arm64-9.9.8.tgz"

    tarball = fx / "codex.tgz"
    _build_good_tarball(tarball)
    integrity = "sha512-" + _b64_sha512(tarball.read_bytes())

    base_json = fx / "base.json"
    base_json.write_text(
        '{"name":"@openai/codex","version":"%s",'
        '"optionalDependencies":{"@openai/codex-darwin-arm64":'
        '"npm:@openai/codex-darwin-arm64@%s"}}' % (_VERSION, _PLATFORM_VERSION)
    )
    platform_json = fx / "platform.json"
    platform_json.write_text(
        '{"name":"@openai/codex-darwin-arm64","version":"%s",'
        '"dist":{"tarball":"%s","integrity":"%s"}}' % (_PLATFORM_VERSION, tarball_url, integrity)
    )

    curl_log = tmp_path / "curl.log"
    bindir = tmp_path / "fixturebin"
    bindir.mkdir()
    curl_stub = bindir / "curl"
    _make_executable(curl_stub, _CURL_FIXTURE_STUB.format(
        log=curl_log, base_url=base_url, platform_url=platform_url, tarball_url=tarball_url,
        base_json=base_json, platform_json=platform_json, tarball=tarball,
    ))
    sudo_stub = bindir / "sudo"
    _make_executable(sudo_stub, _SUDO_PASSTHROUGH_STUB)
    launchctl_log = tmp_path / "launchctl.log"
    launchctl_stub = bindir / "launchctl"
    _make_executable(launchctl_stub, _LAUNCHCTL_FIXTURE_STUB.format(log=launchctl_log))

    def _replace_tarball(kind: str) -> None:
        # Rebuild AND re-sign: the integrity check (S3) runs before the
        # archive-listing check (S4) — a regression fixture for S4 must
        # still carry a matching sha512, or it never reaches S4 at all.
        _build_malicious_tarball(tarball, kind)
        new_integrity = "sha512-" + _b64_sha512(tarball.read_bytes())
        platform_json.write_text(
            '{"name":"@openai/codex-darwin-arm64","version":"%s",'
            '"dist":{"tarball":"%s","integrity":"%s"}}' % (_PLATFORM_VERSION, tarball_url, new_integrity)
        )

    return {
        "bindir": bindir, "tarball": tarball, "curl_log": curl_log,
        "launchctl_log": launchctl_log,
        "replace_tarball": _replace_tarball,
    }


def _pipeline_patch_kwargs(scratch: Path, fx: dict, tmp_path: Path) -> dict[str, str]:
    wrapper_src = _REPO_ROOT / "infra" / "launchagents" / "wrappers" / "wa-codex-broker-wrapper.sh"
    return _self_patch_kwargs(
        scratch,
        CURL_BIN=str(fx["bindir"] / "curl"),
        SUDO_BIN=str(fx["bindir"] / "sudo"),
        LAUNCHCTL_BIN=str(fx["bindir"] / "launchctl"),
        WRAPPER_SRC=str(wrapper_src),
    )


@pytest.mark.parametrize(
    "kind,message",
    [
        ("trailing_symlink_20k", "unsafe entry"),
        ("hardlink", "unsafe entry"),
        ("absolute_path", "unsafe path"),
        ("dotdot_path", "unsafe path"),
    ],
)
def test_guilt_s4_archive_regressions_rejected(
    kind: str, message: str, tmp_path: Path, scratch: Path, registry_fixture: dict,
) -> None:
    registry_fixture["replace_tarball"](kind)
    copy = _patched_copy(tmp_path, **_pipeline_patch_kwargs(scratch, registry_fixture, tmp_path))
    result = _run(copy, ["9.9.9"])
    assert result.returncode == 1
    assert "contains a symlink/hardlink/absolute-path/.. entry" in result.stderr
    codex_dir = scratch / "usr" / "local" / "lib" / "wa-codex-broker" / "codex"
    assert not (codex_dir / "9.9.9").exists()


def test_guilt_s4_20k_symlink_red_broken_green_fixed(
    tmp_path: Path, scratch: Path, registry_fixture: dict,
) -> None:
    """RED: a deliberately-broken copy whose archive check only inspects
    the first 1000 lines of a `tar -tvzf` listing (same vulnerability
    class as PR #7313 round 2's `grep -q` pipeline: an early-terminating
    reader misses an entry buried past where it stopped) WRONGLY accepts
    a 20,000-entry archive with a trailing symlink. GREEN: the shipped
    script's whole-file single awk pass rejects it."""
    registry_fixture["replace_tarball"]("trailing_symlink_20k")
    patch_kwargs = _pipeline_patch_kwargs(scratch, registry_fixture, tmp_path)

    fixed = _patched_copy(tmp_path, **patch_kwargs)
    fixed_result = _run(fixed, ["9.9.9"])
    assert fixed_result.returncode == 1
    assert "contains a symlink/hardlink/absolute-path/.. entry" in fixed_result.stderr

    broken = _broken_s4_copy(tmp_path, **patch_kwargs)
    broken_result = _run(broken, ["9.9.9"])
    assert "contains a symlink/hardlink/absolute-path/.. entry" not in broken_result.stderr, (
        "broken copy correctly caught the symlink — fixture no longer reproduces the bug class"
    )


def test_innocence_full_pipeline_installs_pins_and_kickstarts(
    tmp_path: Path, scratch: Path, registry_fixture: dict,
) -> None:
    runtime = scratch / "usr" / "local" / "lib" / "wa-codex-broker"
    copy = _patched_copy(tmp_path, **_pipeline_patch_kwargs(scratch, registry_fixture, tmp_path))
    result = _run(copy, ["9.9.9"])
    assert result.returncode == 0, result.stderr

    bin_path = runtime / "codex" / "9.9.9" / "bin" / "codex"
    assert bin_path.is_file()
    version_out = subprocess.run([str(bin_path), "--version"], capture_output=True, text=True, check=False)
    assert "9.9.9" in version_out.stdout

    pin_file = runtime / "codex-pin.env"
    pin_content = pin_file.read_text()
    assert "WA_CODEX_CLI_VERSION_PIN=9.9.9" in pin_content
    assert f"WA_CODEX_BIN={bin_path}" in pin_content
    assert oct(pin_file.stat().st_mode)[-3:] == "644"

    wrapper_dst = scratch / "usr" / "local" / "libexec" / "wa-codex-broker-wrapper.sh"
    assert wrapper_dst.is_file()
    assert oct(wrapper_dst.stat().st_mode)[-3:] == "755"

    launchctl_log = registry_fixture["launchctl_log"].read_text()
    assert "kickstart -k system/com.balizero.wa-codex-broker" in launchctl_log


def test_guilt_find_check_rejects_planted_group_writable_file_on_reuse(
    tmp_path: Path, scratch: Path, registry_fixture: dict,
) -> None:
    """S6 reuse path: a pre-existing codex/<ver>/ with a planted
    group/other-writable file must be re-verified and REFUSED, not
    silently trusted or silently overwritten."""
    runtime = scratch / "usr" / "local" / "lib" / "wa-codex-broker"
    dest = runtime / "codex" / "9.9.9"
    (dest / "bin").mkdir(parents=True)
    codex_bin = dest / "bin" / "codex"
    codex_bin.write_text('#!/bin/sh\necho "codex-cli 9.9.9"\n')
    codex_bin.chmod(0o755)
    planted = dest / "planted-world-writable"
    planted.write_text("x")
    planted.chmod(0o777)

    copy = _patched_copy(tmp_path, **_pipeline_patch_kwargs(scratch, registry_fixture, tmp_path))
    result = _run(copy, ["9.9.9"])
    assert result.returncode == 1
    assert "post-normalize find check" in result.stderr
    assert str(planted) in result.stderr
    # the bad tree is left exactly as found — not silently replaced.
    assert planted.exists()
    assert oct(planted.stat().st_mode)[-3:] == "777"
