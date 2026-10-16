"""Synthetic-only native packet checks; no native endpoint or private store access."""

from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace

import pytest

import redis_observer_native_once as native
from test_redis_observer_admission import (
    IsolatedAdmin as BaseAdmin,
    redis_endpoint as endpoint_fixture,
)

redis_endpoint = endpoint_fixture


class IsolatedAdmin(BaseAdmin):
    def __init__(self, *args, **kwargs):
        port = kwargs.get("port", args[1] if len(args) > 1 else 6379)
        if port == 6379:
            raise AssertionError("NATIVE_PORT_FORBIDDEN_IN_TESTS")
        super().__init__(*args, **kwargs)


@pytest.fixture(autouse=True)
def safe_native_boundaries(tmp_path, monkeypatch):
    canonical_home = tmp_path / "uid-home"
    monkeypatch.setattr(
        native.pwd, "getpwuid", lambda _: SimpleNamespace(pw_dir=str(canonical_home))
    )
    monkeypatch.setenv("HOME", str(canonical_home))
    actual_host = native.sha(socket.gethostname().encode())
    monkeypatch.setattr(native, "HOSTS", {"Pro": actual_host, "Mini": actual_host})
    original = socket.create_connection

    def guarded(address, *args, **kwargs):
        if address[1] == 6379:
            raise AssertionError("NATIVE_PORT_FORBIDDEN_IN_TESTS")
        return original(address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", guarded)
    yield canonical_home
    assert not (canonical_home / ".udb-b02-native-once").exists()


class AuthAdmin(IsolatedAdmin):
    def _validate_before_write(self, args):
        if args[0] == "AUTH":
            return
        super()._validate_before_write(args)


def write_private(path, value):
    path.write_text(json.dumps(value) if isinstance(value, dict) else value)
    path.chmod(0o600)
    return native.sha(path.read_bytes())


@pytest.fixture
def package(tmp_path, monkeypatch):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(native, "DEADLINE", datetime.now(UTC) + timedelta(hours=1))
    packet = {
        "permission": "GRANTED",
        "campaign": "universal-db-wave8-20261015",
        "scope": native.SCOPE,
        "credential_route": native.ROUTE,
        "host": "Mini",
        "host_sha256": native.sha(socket.gethostname().encode()),
        "endpoint": ["127.0.0.1", 26379],
        "deadline": native.DEADLINE.isoformat(),
        "source_pins": {
            n: native.sha(Path(native.__file__).with_name(n).read_bytes())
            for n in native.SOURCES
        },
        "evidence_kind": "ISOLATED_TEST",
    }

    def prepare(**changes):
        packet.update(changes)
        pp, op, gp = (root / n for n in ("packet.json", "owner.json", "gate.json"))
        packet_pin = write_private(pp, packet)
        owner_pin = write_private(
            op,
            {
                "authorized": True,
                "scope": native.SCOPE,
                "campaign": packet["campaign"],
                "credential_route": native.ROUTE,
                "run_packet_sha256": packet_pin,
            },
        )
        gate_pin = write_private(
            gp,
            {
                "report_status": "SAFETY: PASS",
                "template_sha256": native.sha(
                    Path(native.__file__)
                    .with_name("REDIS-NATIVE-RUN-TEMPLATE.json")
                    .read_bytes()
                ),
                "run_packet_sha256": packet_pin,
                "owner_receipt_sha256": owner_pin,
                "source_pins": packet["source_pins"],
            },
        )
        return [pp, op, gp, owner_pin, gate_pin]

    return root, packet, prepare


@pytest.mark.parametrize(
    "case",
    [
        "owner_missing",
        "gate_missing",
        "owner_scope",
        "gate_scope",
        "packet_binding",
        "source",
        "host",
        "ungranted",
        "owner_pin",
        "gate_pin",
        "override",
        "deadline",
    ],
)
@pytest.mark.parametrize("native_mode", [False, True])
def test_preconditions_never_read_secret_or_call_redis(
    package, monkeypatch, case, native_mode
):
    root, packet, prepare = package
    args = prepare(
        **(
            {"endpoint": ["127.0.0.1", 6379], "evidence_kind": "NATIVE_ADMITTED"}
            if native_mode
            else {}
        )
    )
    if case == "owner_missing":
        args[1].unlink()
    elif case == "gate_missing":
        args[2].unlink()
    elif case == "owner_scope":
        args[3] = write_private(args[1], {"authorized": True})
    elif case == "gate_scope":
        args[4] = write_private(args[2], {"report_status": "SAFETY: PASS"})
    elif case == "packet_binding":
        data = json.loads(args[0].read_text())
        data["host"] = "Pro"
        write_private(args[0], data)
    elif case == "source":
        args = prepare(source_pins={})
    elif case == "host":
        args = prepare(host_sha256="0" * 64)
    elif case == "ungranted":
        args = prepare(permission="UNGRANTED")
    elif case in {"owner_pin", "gate_pin"}:
        args[3 if case == "owner_pin" else 4] = "0" * 64
    elif case == "override":
        args = prepare(
            evidence_kind="ISOLATED_TEST" if native_mode else "NATIVE_ADMITTED"
        )
    elif case == "deadline":
        monkeypatch.setattr(
            native, "DEADLINE", datetime.now(UTC) - timedelta(seconds=1)
        )
    calls = []
    monkeypatch.setattr(native, "credentials", lambda *_: calls.append("secret"))
    monkeypatch.setattr(
        native.admission,
        "exercise_temporary_observer",
        lambda **_: calls.append("redis"),
    )
    with pytest.raises((native.admission.AdmissionError, OSError)):
        native.run(*args, isolated_root=None if native_mode else root)
    assert calls == []
    assert not (root / "endpoint.lease").exists()


@pytest.mark.parametrize(
    "change",
    [
        {"endpoint": ["127.0.0.1", 6379]},
        {"endpoint": ["localhost", 26379]},
        {"endpoint": ["127.0.0.1", True]},
        {"test_override": True},
    ],
)
def test_test_endpoint_and_extra_override_rejected(package, monkeypatch, change):
    root, _, prepare = package
    args = prepare(**change)
    monkeypatch.setattr(native, "credentials", lambda *_: pytest.fail("secret"))
    with pytest.raises(native.admission.AdmissionError):
        native.run(*args, isolated_root=root)


def test_native_has_no_test_override(package, monkeypatch):
    _, _, prepare = package
    args = prepare()
    monkeypatch.setattr(native, "credentials", lambda *_: pytest.fail("secret"))
    with pytest.raises(
        native.admission.AdmissionError, match="NATIVE_OVERRIDE_REJECTED"
    ):
        native.run(*args)


@pytest.mark.parametrize(
    "unsafe", ["mode", "symlink", "hardlink", "directory", "fifo", "owner"]
)
def test_private_store_rejects_unsafe_file(tmp_path, monkeypatch, unsafe):
    p = tmp_path / "synthetic.env"
    write_private(p, "REDIS_PASSWORD=synthetic-only\n")
    if unsafe == "mode":
        p.chmod(0o644)
    elif unsafe == "symlink":
        link = tmp_path / "symlink"
        link.symlink_to(p)
        p = link
    elif unsafe == "hardlink":
        os.link(p, tmp_path / "other")
    elif unsafe == "directory":
        p = tmp_path
    elif unsafe == "fifo":
        p.unlink()
        os.mkfifo(p, 0o600)
    elif unsafe == "owner":
        monkeypatch.setattr(native.os, "getuid", lambda: -1)
    with pytest.raises((OSError, native.admission.AdmissionError)):
        native.credentials(p)


def test_decoder_no_interpolation_or_environment_fallback(tmp_path, monkeypatch):
    p = tmp_path / "synthetic.env"
    monkeypatch.setenv("REDIS_PASSWORD", "environment-only")
    monkeypatch.setenv("B02_SYNTHETIC", "expanded")
    write_private(p, "REDIS_PASSWORD='literal-${B02_SYNTHETIC}'\n")
    assert native.credentials(p) == ("default", "literal-${B02_SYNTHETIC}")
    write_private(p, "UNRELATED=synthetic\n")
    with pytest.raises(native.admission.AdmissionError, match="PASSWORD_MISSING"):
        native.credentials(p)
    write_private(p, "REDIS_PASSWORD=synthetic\nREDIS_USER=observer\n")
    with pytest.raises(
        native.admission.AdmissionError, match="BOOTSTRAP_IDENTITY_CONFLICT"
    ):
        native.credentials(p)


@pytest.mark.parametrize("collision", ["endpoint.lease", "recovery.json"])
def test_exclusive_reservations_precede_secret(package, monkeypatch, collision):
    root, _, prepare = package
    args = prepare()
    write_private(root / collision, "existing")
    monkeypatch.setattr(native, "credentials", lambda *_: pytest.fail("secret"))
    with pytest.raises((OSError, native.admission.AdmissionError)):
        native.run(*args, isolated_root=root)
    assert (root / collision).read_text() == "existing"


def test_isolated_password_auth_exercise_and_cleanup(package, redis_endpoint):
    root, _, prepare = package
    args = prepare(endpoint=list(redis_endpoint))
    import secrets
    password = secrets.token_urlsafe(32)
    write_private(root / "synthetic.env", "REDIS_PASSWORD=" + password + "\n")
    # Fixture is throwaway, non6379; configure its default bootstrap in RAM.
    with IsolatedAdmin(port=redis_endpoint[1]) as admin:
        assert (
            admin.execute(
                "ACL",
                "SETUSER",
                "default",
                "#" + hashlib.sha256(password.encode()).hexdigest(),
            )
            == "OK"
        )
    try:
        result = native.run(*args, isolated_root=root)
        assert result["status"] == "VERIFIED_TEMPORARY_EXERCISE"
        assert result["role_removed"] and result["observer_metadata_verified"]
        assert result["evidence_kind"] == "ISOLATED_TEST"
        journal = json.loads((root / "recovery.json").read_text())
        with AuthAdmin(port=redis_endpoint[1]) as admin:
            assert admin.execute("AUTH", "default", password) == "OK"
            assert admin.execute("ACL", "GETUSER", journal["temporary_role"]) is None
        assert password not in json.dumps(result)
        assert password not in (root / "endpoint.lease").read_text()
        assert password not in (root / "recovery.json").read_text()
        with pytest.raises(native.admission.AdmissionError, match="JOURNAL_EXISTS"):
            native.run(*args, isolated_root=root)
    finally:
        with AuthAdmin(port=redis_endpoint[1]) as admin:
            assert admin.execute("AUTH", "default", password) == "OK"
            assert admin.execute("ACL", "SETUSER", "default", "nopass") == "OK"


def test_b01_b05_owner_continuation_is_not_b02_authority(package, monkeypatch):
    root, _, prepare = package
    args = prepare()
    args[3] = write_private(
        args[1],
        {
            "authorized_scope": {"B01": "granted", "B05": "granted"},
            "not_granted": ["New Redis ACL provisioning or secret delivery."],
        },
    )
    monkeypatch.setattr(native, "credentials", lambda *_: pytest.fail("secret"))
    with pytest.raises(native.admission.AdmissionError, match="OWNER_SCOPE_REJECTED"):
        native.run(*args, isolated_root=root)


@pytest.mark.parametrize("spoof", ["other-home", "", "/"])
def test_home_spoof_rejected_before_packet_or_secret_or_filesystem(
    package, monkeypatch, safe_native_boundaries, spoof
):
    root, _, prepare = package
    args = prepare()
    monkeypatch.setenv("HOME", str(root / spoof) if spoof == "other-home" else spoof)
    monkeypatch.setattr(native, "validate", lambda *a: pytest.fail("packet read"))
    monkeypatch.setattr(native, "credentials", lambda *a: pytest.fail("secret read"))
    monkeypatch.setattr(
        Path, "mkdir", lambda *a, **k: pytest.fail("filesystem mutation")
    )
    with pytest.raises(native.admission.AdmissionError, match="HOME_OVERRIDE_REJECTED"):
        native.run(*args)
    assert not (root / ".udb-b02-native-once").exists()
    assert not (safe_native_boundaries / ".udb-b02-native-once").exists()


def test_native_route_must_match_reviewed_fixed_paths(package, monkeypatch):
    _, _, prepare = package
    args = prepare(endpoint=["127.0.0.1", 6379], evidence_kind="NATIVE_ADMITTED")
    monkeypatch.setattr(native, "credentials", lambda *a: pytest.fail("secret read"))
    with pytest.raises(native.admission.AdmissionError, match="NATIVE_ROUTE_REJECTED"):
        native.run(*args)


def test_missing_home_uses_uid_home_before_validation(package, monkeypatch):
    _, _, prepare = package
    args = prepare(permission="UNGRANTED")
    monkeypatch.delenv("HOME")
    with pytest.raises(
        native.admission.AdmissionError, match="OWNER_PERMISSION_UNGRANTED"
    ):
        native.run(*args)


def test_synthetic_admin_rejects_native_port():
    with pytest.raises(AssertionError, match="NATIVE_PORT_FORBIDDEN_IN_TESTS"):
        AuthAdmin(port=6379)


@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "pycache",
        "extra_module",
        "tampered_source",
        "missing_source",
        "symlink_source",
        "manifest_pin",
        "manifest_set",
    ],
)
def test_preimport_stage_contract_rejects_unpinned_code(tmp_path, case):
    template = json.loads(
        Path(native.__file__).with_name("REDIS-NATIVE-RUN-TEMPLATE.json").read_bytes()
    )
    launch = template["detached_invocation"]
    assert launch["argv_after_python"][:3] == ["-B", "-E", "-s"]
    stage = tmp_path / "stage"
    stage.mkdir(mode=0o700)
    names = (*native.SOURCES, "REDIS-NATIVE-RUN-TEMPLATE.json")
    for name in names:
        (stage / name).write_bytes(Path(native.__file__).with_name(name).read_bytes())
    pins = {name: native.sha((stage / name).read_bytes()) for name in names}
    manifest = tmp_path / "reviewed-manifest.json"
    manifest_pin = write_private(manifest, pins)
    marker = tmp_path / "UNPINNED_IMPORT_EXECUTED"
    if case == "pycache":
        cache = stage / "__pycache__"
        cache.mkdir()
        (cache / "json.cpython-314.pyc").write_bytes(b"synthetic-untrusted-cache")
    elif case == "extra_module":
        (stage / "json.py").write_text(
            "from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n"
        )
    elif case == "tampered_source":
        with (stage / "redis_observer_admission.py").open("a") as stream:
            stream.write("\nraise RuntimeError('synthetic-unpinned-source')\n")
    elif case == "missing_source":
        (stage / "redis_observer_probe.py").unlink()
    elif case == "symlink_source":
        source = stage / "redis_observer_probe.py"
        outside = tmp_path / "outside.py"
        source.replace(outside)
        source.symlink_to(outside)
    elif case == "manifest_pin":
        manifest_pin = "0" * 64
    elif case == "manifest_set":
        pins.pop("redis_observer_probe.py")
        manifest_pin = write_private(manifest, pins)
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            launch["preimport_verifier_python"],
            str(stage),
            str(manifest),
            manifest_pin,
        ],
        cwd=tmp_path,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == (0 if case == "valid" else 1)
    assert result.stdout.strip() == (
        b"STAGE_VERIFIED" if case == "valid" else b"STAGE_REJECTED"
    )
    assert result.stderr == b""
    assert not marker.exists()
    if case != "pycache":
        assert not (stage / "__pycache__").exists()
