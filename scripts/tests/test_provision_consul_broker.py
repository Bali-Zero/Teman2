"""Offline package boundaries; never provision users, DB grants, or sudoers."""

from __future__ import annotations

from hashlib import sha256
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTROLS = ROOT / "infra/conductor/consul-broker"
INSTALLER = ROOT / "scripts/provision_consul_broker.sh"


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def verifier() -> ModuleType:
    return load_module("consul_release_verify", CONTROLS / "verify.py")


@pytest.fixture
def builder(monkeypatch: pytest.MonkeyPatch, verifier: ModuleType) -> ModuleType:
    monkeypatch.setitem(sys.modules, "verify", verifier)
    return load_module("consul_release_build", CONTROLS / "build_bundle.py")


@pytest.fixture
def release(tmp_path: Path, verifier: ModuleType) -> Path:
    (tmp_path / "entry.py").write_text("# synthetic source\n")
    (tmp_path / "SHA256SUMS").write_text(verifier.manifest(tmp_path))
    return tmp_path


def test_manifest_detects_modified_and_unlisted_files(
    release: Path, verifier: ModuleType
) -> None:
    verifier.verify(release, native=False)
    (release / "entry.py").write_text("# changed after review\n")
    with pytest.raises(ValueError, match="manifest_mismatch"):
        verifier.verify(release, native=False)
    (release / "SHA256SUMS").write_text(verifier.manifest(release))
    (release / "hidden.py").write_text("# not reviewed\n")
    with pytest.raises(ValueError, match="manifest_mismatch"):
        verifier.verify(release, native=False)


def test_release_rejects_symlink_and_special_file(
    release: Path, verifier: ModuleType
) -> None:
    (release / "linked.py").symlink_to("entry.py")
    with pytest.raises(ValueError, match="symlink_forbidden"):
        verifier.verify(release, native=False)
    (release / "linked.py").unlink()
    os.mkfifo(release / "pipe")
    with pytest.raises(ValueError, match="special_file_forbidden"):
        verifier.verify(release, native=False)


def test_immutable_release_rejects_caller_owned_tree(
    release: Path, verifier: ModuleType
) -> None:
    if os.getuid() == 0:
        pytest.skip("Fixture is deliberately caller owned")
    with pytest.raises(ValueError, match="not_root_protected"):
        verifier.verify(release, immutable=True, native=False)


def test_immutable_release_rejects_acl_even_with_safe_mode_bits(
    release: Path, verifier: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(verifier.sys, "platform", "darwin")

    def listing(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args, 0, "drwxr-xr-x+ root wheel release\n 0: user:caller allow write\n", ""
        )

    monkeypatch.setattr(verifier.subprocess, "run", listing)
    with pytest.raises(ValueError, match="release_acl_forbidden"):
        verifier.verify(release, immutable=True, native=False)


@pytest.mark.parametrize("mode", [0o4755, 0o2755, 0o6755, 0o0775, 0o0757])
def test_immutable_release_rejects_unsafe_modes_even_with_matching_hashes(
    release: Path, verifier: ModuleType, monkeypatch: pytest.MonkeyPatch, mode: int
) -> None:
    # Model root ownership; actual test files remain owned by the ordinary user.
    lstat = Path.lstat

    def root_metadata(path: Path) -> os.stat_result:
        values = list(lstat(path))
        values[4] = 0
        return os.stat_result(values)

    monkeypatch.setattr(Path, "lstat", root_metadata)
    monkeypatch.setattr(verifier.sys, "platform", "linux")
    verifier.verify(release, immutable=True, native=False)
    (release / "entry.py").chmod(mode)
    assert (release / "SHA256SUMS").read_text() == verifier.manifest(release)
    with pytest.raises(ValueError, match="not_root_protected"):
        verifier.verify(release, immutable=True, native=False)


@pytest.mark.parametrize(
    ("reference", "allowed"),
    [
        ("/usr/lib/libSystem.B.dylib", True),
        ("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation", True),
        ("@loader_path/../lib/libpython.dylib", True),
        ("@executable_path/../lib/libpython.dylib", True),
        ("@rpath/libpython.dylib", True),
        ("/opt/homebrew/lib/libpython.dylib", False),
        ("/Users/caller/.venv/libpython.dylib", False),
        ("@loader_path/../../../../outside.dylib", False),
        ("@rpath/../../outside.dylib", False),
    ],
)
def test_native_library_paths_are_bundled_or_system(
    release: Path, verifier: ModuleType, reference: str, allowed: bool
) -> None:
    binary = release / "python/bin/python3"
    assert (
        verifier.native_references_allowed(
            f"{binary}:\n\t{reference} (compatibility version 1.0.0)\n", binary, release
        )
        is allowed
    )


def test_native_rpath_escape_rejected(
    release: Path, verifier: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = release / "python3"
    binary.write_bytes(b"\xcf\xfa\xed\xfe")
    (release / "SHA256SUMS").write_text(verifier.manifest(release))

    def otool(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        content = (
            f"{binary}:\n\t/usr/lib/libSystem.B.dylib (compatibility version 1.0)\n"
            if args[1] == "-L"
            else "cmd LC_RPATH\ncmdsize 48\n    path /opt/homebrew/lib (offset 12)\n"
        )
        return subprocess.CompletedProcess(args, 0, content, "")

    monkeypatch.setattr(verifier.subprocess, "run", otool)
    with pytest.raises(ValueError, match="external_runtime_search_path"):
        verifier.verify(release)


def test_dylib_identity_is_not_an_external_load(
    release: Path, verifier: ModuleType
) -> None:
    binary = release / "python/lib/libthread.dylib"
    identity = "libthread.dylib"
    output = f"{binary}:\n\t{identity} (compatibility version 1.0)\n"
    assert verifier.native_references_allowed(
        output, binary, release, install_name=identity
    )
    assert not verifier.native_references_allowed(output, binary, release)
    assert not verifier.native_references_allowed(
        output + "\t/opt/homebrew/lib/libextra.dylib (compatibility version 1.0)\n",
        binary,
        release,
        install_name=identity,
    )


def test_runtime_dereferences_only_contained_links(
    tmp_path: Path, builder: ModuleType
) -> None:
    source = tmp_path / "python"
    source.mkdir()
    (source / "python3.11").write_bytes(b"synthetic executable")
    (source / "python3").symlink_to("python3.11")
    bundled_site = source / "lib/python3.11/site-packages"
    bundled_site.mkdir(parents=True)
    (bundled_site / "unlocked.py").write_text("# not a locked dependency\n")
    output = tmp_path / "copied"
    builder.copy_runtime(source, output)
    assert not (output / "python3").is_symlink()
    assert (output / "python3").read_bytes() == b"synthetic executable"
    assert not (output / "lib/python3.11/site-packages").exists()
    (source / "external").symlink_to(tmp_path)
    with pytest.raises(ValueError, match="runtime_symlink_escape"):
        builder.copy_runtime(source, tmp_path / "refused")


def test_source_closure_includes_initializers_and_deferred_imports(
    tmp_path: Path, builder: ModuleType
) -> None:
    source = tmp_path / "scripts"
    source.mkdir()
    (source / "consul_broker.py").write_text(
        "def handle():\n    from scripts.helper import run\n"
    )
    (source / "helper.py").write_text("from scripts import other\n")
    (source / "other.py").write_text("import json\n")
    (source / "__init__.py").write_text("# package initialization\n")
    assert {p.name for p in builder.source_closure(tmp_path)} == {
        "consul_broker.py",
        "helper.py",
        "other.py",
        "__init__.py",
    }
    (source / "helper.py").unlink()
    outside = tmp_path.parent / "outside.py"
    outside.write_text("# outside checkout\n")
    (source / "helper.py").symlink_to(outside)
    with pytest.raises(ValueError, match="source_outside_repository"):
        builder.source_closure(tmp_path)


def test_checked_copy_rejects_source_drift(tmp_path: Path, builder: ModuleType) -> None:
    source = tmp_path / "source.py"
    source.write_text("# reviewed\n")
    expected = builder.snapshot([source])[source]
    source.write_text("# changed\n")
    with pytest.raises(ValueError, match="bundle_source_changed"):
        builder.checked_copy(source, tmp_path / "dest.py", expected)


def test_builder_rejects_non_pro_before_subprocess(
    tmp_path: Path, builder: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(builder.socket, "gethostname", lambda: "Air-M5")

    def forbid(*args: object, **kwargs: object) -> None:
        pytest.fail("No downloads or subprocess calls allowed outside Pro")

    monkeypatch.setattr(builder.subprocess, "check_output", forbid)
    with pytest.raises(PermissionError, match="bundle_build_pro_required"):
        builder.build(tmp_path, tmp_path / "release")


def shell_validate(release: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    # Execute the installer's real verifier in isolation, without its OS mutations.
    source = INSTALLER.read_text()
    function = source[source.index("verify_tree() {") : source.index('while [ "$#"')]
    script = tmp_path / "verify-tree.sh"
    script.write_text(
        "set -euo pipefail\ndie() { printf '%s\\n' \"$1\" >&2; exit 1; }\n"
        + function
        + '\nverify_tree "$1" "$2"\n'
    )
    digest = sha256((release / "SHA256SUMS").read_bytes()).hexdigest()
    return subprocess.run(
        ["/bin/bash", str(script), str(release), digest],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("mode", [0o4755, 0o2755, 0o6755])
def test_apply_normalizes_setid_privately_before_ownership_or_publication(
    release: Path, tmp_path: Path, mode: int
) -> None:
    # Run the actual copy/normalization function on inert ordinary-user files.
    # Only chown and platform-specific metadata cleanup are mocked; no root.
    (release / "entry.py").chmod(mode)
    base = tmp_path / "install"
    (base / "releases").mkdir(parents=True)
    target = base / "releases/final"
    source = INSTALLER.read_text()
    functions = source[source.index("verify_tree() {") : source.index('while [ "$#"')]
    script = tmp_path / "prepare-test.sh"
    script.write_text(
        "set -euo pipefail\n"
        'die() { printf "%s\\n" "$1" >&2; exit 1; }\n'
        'BASE="$2"; TARGET="$3"\n'
        'ditto() { [ "$(ls -ld "$(dirname "$2")" | cut -c1-10)" = drwx------ ]; '
        '/bin/cp -Rp "$1" "$2"; }\n'
        'chmod() { if [ "$1" != -RN ]; then /bin/chmod "$@"; fi; }\n'
        "xattr() { :; }\n"
        'chown() { [ ! -e "$TARGET" ]; '
        '[ -z "$(find "$3" \\( -perm -4000 -o -perm -2000 \\) -print)" ]; }\n'
        + functions
        + '\nprepare_release "$1" "$3" "$4"\n'
    )
    # The helpers live outside the reviewed source tree to preserve its manifest.
    original = tmp_path / "payload"
    original.mkdir()
    (original / "entry.py").write_bytes((release / "entry.py").read_bytes())
    (original / "entry.py").chmod(mode)
    (original / "SHA256SUMS").write_bytes((release / "SHA256SUMS").read_bytes())
    digest = sha256((original / "SHA256SUMS").read_bytes()).hexdigest()
    result = subprocess.run(
        ["/bin/bash", str(script), str(original), str(base), str(target), digest],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (target / "entry.py").stat().st_mode & 0o6022 == 0
    assert (target / "entry.py").read_bytes() == (original / "entry.py").read_bytes()
    assert not list((base / "releases").glob(".install.*"))


@pytest.mark.parametrize("mode", [0o4755, 0o2755, 0o6755])
def test_existing_and_rollback_release_mode_guard_precedes_python(
    release: Path, tmp_path: Path, mode: int
) -> None:
    (release / "entry.py").chmod(mode)
    source = INSTALLER.read_text()
    functions = source[source.index("verify_tree() {") : source.index('while [ "$#"')]
    script = tmp_path / "mode-test.sh"
    marker = tmp_path / "python-was-executed"
    script.write_text(
        'set -euo pipefail\ndie() { printf "%s\\n" "$1" >&2; exit 1; }\n'
        + functions
        + '\nverify_installed_modes "$1"\ntouch "$2"\n'
    )
    result = subprocess.run(
        ["/bin/bash", str(script), str(release), str(marker)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "consul_release_unsafe_mode" in result.stderr
    assert not marker.exists()
    rollback = source[
        source.index('if [ "$MODE" = --rollback ]') : source.index(
            'RELEASE="$BASE/releases/'
        )
    ]
    existing = source[
        source.index('RELEASE="$BASE/releases/') : source.index('if ! id "$SERVICE"')
    ]
    for branch in (rollback, existing):
        assert branch.index("verify_installed_modes") < branch.index("env -i")


@pytest.mark.parametrize(
    "mutation", ["none", "duplicate", "traversal", "extra", "tamper"]
)
def test_installer_verifies_reviewed_manifest_before_executing_bundle(
    tmp_path: Path, verifier: ModuleType, mutation: str
) -> None:
    release = tmp_path / "release"
    release.mkdir()
    (release / "entry.py").write_text("# reviewed\n")
    manifest = verifier.manifest(release)
    if mutation == "duplicate":
        manifest += manifest
    elif mutation == "traversal":
        manifest = manifest.replace("entry.py", "../entry.py")
    (release / "SHA256SUMS").write_text(manifest)
    if mutation == "extra":
        (release / "extra.py").write_text("# unreviewed\n")
    if mutation == "tamper":
        (release / "entry.py").write_text("# changed\n")
    result = shell_validate(release, tmp_path)
    assert (result.returncode == 0) is (mutation == "none"), result.stderr
    preflight = subprocess.run(
        [
            "/bin/bash",
            str(INSTALLER),
            "--check",
            "--bundle",
            str(release),
            "--sha256",
            sha256((release / "SHA256SUMS").read_bytes()).hexdigest(),
        ],
        capture_output=True,
        text=True,
    )
    assert (preflight.returncode == 0) is (mutation == "none"), preflight.stderr


def test_default_preflight_and_wrapper_argument_refusal() -> None:
    result = subprocess.run(
        ["/bin/bash", str(INSTALLER)], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "Plan: Pro only" in result.stdout
    result = subprocess.run(
        ["/bin/sh", str(CONTROLS / "wrapper.sh"), "--config", "/untrusted"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 64
    assert result.stderr.strip() == "consul_broker_arguments_forbidden"
