"""Synthetic tests on a private throwaway Redis; never use the native port."""

from __future__ import annotations

import json
import os
import socket
import signal
import subprocess
import time

import pytest

import redis_observer_admission as admission
import redis_observer_probe as probe


class IsolatedAdmin(probe.RespSocketClient):
    def _validate_before_write(self, args):
        if args[:2] in {("ACL", "GETUSER"), ("ACL", "SETUSER"), ("ACL", "DELUSER")}:
            return
        if args in [
            ("PING",),
            ("DBSIZE",),
            ("SET", "__udb_fixture__", "synthetic-only"),
            ("GET", "__udb_fixture__"),
        ]:
            return
        raise AssertionError("test admin command outside synthetic fixture")


@pytest.fixture(scope="module")
def redis_endpoint(tmp_path_factory):
    root = tmp_path_factory.mktemp("b02-private-redis")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert port != 6379
    process = subprocess.Popen(
        [
            "/opt/homebrew/bin/redis-server",
            "--bind",
            "127.0.0.1",
            "--port",
            str(port),
            "--save",
            "",
            "--appendonly",
            "no",
            "--dir",
            str(root),
            "--protected-mode",
            "yes",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            if process.poll() is not None:
                pytest.fail("private Redis exited before startup")
            try:
                with IsolatedAdmin(port=port) as admin:
                    assert admin.execute("PING") == "PONG"
                    break
            except OSError:
                time.sleep(0.02)
        else:
            pytest.fail("private Redis startup timeout")
        yield "127.0.0.1", port
    finally:
        process.terminate()
        process.wait(timeout=10)


def _run(endpoint, **overrides):
    host, port = endpoint
    args = dict(
        host=host,
        port=port,
        provisioner_credentials=("default", "synthetic-only"),
        provisioner_identity_sha256=admission._sha("default"),
        admitted_endpoint=endpoint,
        evidence_kind="ISOLATED_TEST",
    )
    args.update(overrides)
    return admission.exercise_temporary_observer(**args)


def test_real_isolated_redis_admission_cleanup_and_no_data_commands(
    redis_endpoint, monkeypatch
):
    with IsolatedAdmin(port=redis_endpoint[1]) as admin:
        admin.execute("SET", "__udb_fixture__", "synthetic-only")
        default_before = admin.execute("ACL", "GETUSER", "default")
    commands = []
    original = probe.RespSocketClient._write_encoded_bytes

    def record(self, payload):
        commands.append(payload.split(b"\r\n")[2].decode().upper())
        return original(self, payload)

    monkeypatch.setattr(probe.RespSocketClient, "_write_encoded_bytes", record)
    result = _run(redis_endpoint)
    assert result["status"] == "VERIFIED_TEMPORARY_EXERCISE"
    assert all(
        result[k]
        for k in [
            "role_created",
            "role_removed",
            "policy_off_verified",
            "policy_on_verified",
            "dryrun_verified",
            "observer_metadata_verified",
        ]
    )
    assert result["positive_permission_count"] == len(probe.POSITIVE_DRYRUN_SPECS)
    assert result["negative_permission_count"] == len(probe.NEGATIVE_DRYRUN_SPECS)
    assert not set(commands).intersection(
        {"GET", "SET", "DEL", "KEYS", "SCAN", "EVAL", "FLUSHDB", "CONFIG"}
    )
    assert set(commands) <= {
        "AUTH",
        "ACL",
        "PING",
        "ROLE",
        "DBSIZE",
        "TIME",
        "COMMAND",
        "CLIENT",
        "INFO",
    }
    monkeypatch.undo()
    with IsolatedAdmin(port=redis_endpoint[1]) as admin:
        assert admin.execute("GET", "__udb_fixture__") == "synthetic-only"
        assert admin.execute("ACL", "GETUSER", "default") == default_before
    serialized = json.dumps(result)
    assert "synthetic-only" not in serialized
    assert "password" not in serialized
    assert "ISOLATED_TEST" in serialized


def test_existing_role_collision_never_changes_or_deletes_role(
    redis_endpoint, monkeypatch
):
    nonce = "a" * 32
    target = "nuzantara_observer_wave8_" + nonce
    with IsolatedAdmin(port=redis_endpoint[1]) as admin:
        admin.execute("ACL", "SETUSER", target, "reset", "off", "-@all")
        before = admin.execute("ACL", "GETUSER", target)
        monkeypatch.setattr(admission.secrets, "token_hex", lambda _: nonce)
        result = _run(redis_endpoint)
        assert result["diagnostic"] == "ROLE_COLLISION_NO_MUTATION"
        assert not result["role_created"] and not result["role_removed"]
        assert admin.execute("ACL", "GETUSER", target) == before
        admin.execute("ACL", "DELUSER", target)


def test_wrong_provisioner_pin_never_creates_role(redis_endpoint):
    result = _run(
        redis_endpoint, provisioner_identity_sha256=admission._sha("not-default")
    )
    assert result["diagnostic"] == "PROVISIONER_IDENTITY_NOT_ADMITTED"
    assert not result["role_created"] and not result["role_removed"]


def test_observed_policy_mismatch_prevents_activation_and_cleans_up(
    redis_endpoint, monkeypatch
):
    def mismatch(*args):
        raise admission.AdmissionError("POLICY_MISMATCH")

    monkeypatch.setattr(admission, "_policy", mismatch)
    result = _run(redis_endpoint)
    assert result["diagnostic"] == "POLICY_MISMATCH"
    assert result["role_created"] and result["role_removed"]
    assert not result["policy_on_verified"] and not result["observer_metadata_verified"]


def test_unverified_dryrun_never_activates_observer(redis_endpoint, monkeypatch):
    monkeypatch.setattr(
        probe,
        "evaluate_provisioner_dryrun_matrix",
        lambda *a, **k: {"x_dryrun_state": "UNKNOWN"},
    )
    result = _run(redis_endpoint)
    assert result["diagnostic"] == "DRYRUN_MATRIX_NOT_VERIFIED"
    assert result["role_removed"] and not result["policy_on_verified"]


def test_metadata_probe_failure_still_removes_role(redis_endpoint, monkeypatch):
    monkeypatch.setattr(
        probe, "probe_redis_observer", lambda **k: {"x_observer_state": "UNKNOWN"}
    )
    result = _run(redis_endpoint)
    assert result["diagnostic"] == "OBSERVER_METADATA_NOT_VERIFIED"
    assert result["role_removed"] and result["status"] == "BLOCKED"


def test_admitted_label_without_measured_metadata_cannot_pass(
    redis_endpoint, monkeypatch
):
    monkeypatch.setattr(
        probe,
        "probe_redis_observer",
        lambda **k: {"x_observer_state": "ADMITTED_VERIFIED"},
    )
    result = _run(redis_endpoint)
    assert result["diagnostic"] == "OBSERVER_METADATA_INCOMPLETE"
    assert result["role_removed"] and not result["observer_metadata_verified"]


def test_cleanup_failure_cannot_report_success(redis_endpoint, monkeypatch):
    execute = admission._LifecycleClient.execute
    target = []

    def fail_cleanup(self, *args):
        if args[:2] == ("ACL", "DELUSER"):
            target.append(self.target)
            return probe.RespError("NOPERM synthetic-only")
        return execute(self, *args)

    monkeypatch.setattr(admission._LifecycleClient, "execute", fail_cleanup)
    result = _run(redis_endpoint)
    assert result["observer_metadata_verified"] and not result["role_removed"]
    assert (
        result["status"] == "BLOCKED" and result["diagnostic"] == "ROLE_CLEANUP_FAILED"
    )
    with IsolatedAdmin(port=redis_endpoint[1]) as admin:
        assert len(target) == 1
        assert admin.execute("ACL", "DELUSER", target[0]) == 1


def test_lifecycle_masks_password_hash_and_rejects_other_targets(redis_endpoint):
    target = "nuzantara_observer_wave8_" + "b" * 32
    password_hash = admission._sha("synthetic-credential")
    with admission._LifecycleClient(*redis_endpoint, target, password_hash) as client:
        client.claimed = True
        try:
            assert client.execute(*client.setup) == "OK"
            assert password_hash not in json.dumps(client.recorded_commands)
            assert "synthetic-credential" not in json.dumps(client.recorded_commands)
            with pytest.raises(
                admission.AdmissionError, match="LIFECYCLE_COMMAND_NOT_ALLOWED"
            ):
                client.execute("ACL", "DELUSER", "default")
            with pytest.raises(
                admission.AdmissionError, match="LIFECYCLE_COMMAND_NOT_ALLOWED"
            ):
                client.execute("SET", "__udb_fixture__", "unexpected")
        finally:
            client.execute("ACL", "DELUSER", target)


def test_private_journal_is_exclusive_and_contains_only_recovery_metadata(
    redis_endpoint, tmp_path
):
    path = tmp_path / "exercise-reservation.json"
    result = _run(redis_endpoint, journal_path=path)
    assert result["role_removed"] and result["status"] == "VERIFIED_TEMPORARY_EXERCISE"
    assert path.stat().st_mode & 0o777 == 0o600
    reservation = json.loads(path.read_text())
    assert admission._TARGET.fullmatch(reservation["temporary_role"])
    assert (
        "password" not in path.read_text() and "synthetic-only" not in path.read_text()
    )
    with IsolatedAdmin(port=redis_endpoint[1]) as admin:
        assert admin.execute("ACL", "GETUSER", reservation["temporary_role"]) is None
    with pytest.raises(admission.AdmissionError, match="EXERCISE_RESERVATION_REJECTED"):
        _run(redis_endpoint, journal_path=path)


def test_native_flag_without_journal_rejected_before_connection(redis_endpoint):
    with pytest.raises(admission.AdmissionError, match="NATIVE_JOURNAL_REQUIRED"):
        _run(redis_endpoint, evidence_kind="NATIVE_ADMITTED")


def test_sigterm_cleanup_path_restores_callers_handler(
    redis_endpoint, tmp_path, monkeypatch
):
    original_handler = signal.getsignal(signal.SIGTERM)

    def interrupted(**kwargs):
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)

    monkeypatch.setattr(probe, "probe_redis_observer", interrupted)
    result = _run(redis_endpoint, journal_path=tmp_path / "signal-reservation.json")
    assert result["diagnostic"] == "EXERCISE_INTERRUPTED"
    assert result["role_removed"] and result["status"] == "BLOCKED"
    assert signal.getsignal(signal.SIGTERM) is original_handler


@pytest.mark.parametrize(
    "host,port", [("127.0.0.1", 1), ("localhost", 6379), ("0.0.0.0", 6379)]
)
def test_unadmitted_endpoint_rejected_before_connection(redis_endpoint, host, port):
    with pytest.raises(admission.AdmissionError, match="ENDPOINT_NOT_ADMITTED"):
        _run(redis_endpoint, host=host, port=port)


def test_credential_file_private_explicit_and_never_falls_back(tmp_path, monkeypatch):
    monkeypatch.setenv("REDIS_PASSWORD", "must-not-be-used")
    file = tmp_path / "provisioner.json"
    with pytest.raises(admission.AdmissionError, match="CREDENTIAL_FILE_REJECTED"):
        admission.load_provisioner_credentials(file)
    file.write_text(
        json.dumps({"user": "test-provisioner", "password": "synthetic-only"})
    )
    file.chmod(0o600)
    assert admission.load_provisioner_credentials(file) == (
        "test-provisioner",
        "synthetic-only",
    )
    file.chmod(0o644)
    with pytest.raises(admission.AdmissionError, match="CREDENTIAL_FILE_REJECTED"):
        admission.load_provisioner_credentials(file)


@pytest.mark.parametrize(
    "kind", ["symlink", "hardlink", "directory", "invalid-json", "extra-field"]
)
def test_unsafe_credential_sources_rejected(tmp_path, kind):
    real = tmp_path / "source"
    real.write_text(
        json.dumps({"user": "test-provisioner", "password": "synthetic-only"})
    )
    real.chmod(0o600)
    path = tmp_path / "credential"
    if kind == "symlink":
        path.symlink_to(real)
    elif kind == "hardlink":
        os.link(real, path)
    elif kind == "directory":
        path.mkdir(mode=0o600)
    elif kind == "invalid-json":
        path.write_text("not-json")
        path.chmod(0o600)
    else:
        path.write_text(
            json.dumps({"user": "x", "password": "synthetic-only", "extra": True})
        )
        path.chmod(0o600)
    with pytest.raises(admission.AdmissionError, match="CREDENTIAL_FILE_REJECTED"):
        admission.load_provisioner_credentials(path)


@pytest.fixture
def provisioner_account(redis_endpoint):
    user = "udb_provisioner_fixture_" + admission.secrets.token_hex(8)
    import secrets
    password = secrets.token_urlsafe(32)
    with IsolatedAdmin(port=redis_endpoint[1]) as admin:
        assert admin.execute("ACL", "GETUSER", user) is None
        assert (
            admin.execute(
                "ACL",
                "SETUSER",
                user,
                "reset",
                "on",
                "resetkeys",
                "resetchannels",
                "-@all",
                "+acl|whoami",
                "+acl|getuser",
                "+acl|setuser",
                "+acl|dryrun",
                "+acl|deluser",
                "#" + admission._sha(password),
            )
            == "OK"
        )
        try:
            yield user, password
        finally:
            admin.execute("ACL", "DELUSER", user)


def test_distinct_password_protected_provisioner_can_complete(
    redis_endpoint, provisioner_account
):
    result = _run(
        redis_endpoint,
        provisioner_credentials=provisioner_account,
        provisioner_identity_sha256=admission._sha(provisioner_account[0]),
    )
    assert result["status"] == "VERIFIED_TEMPORARY_EXERCISE"
    assert result["role_removed"] and result["observer_metadata_verified"]


def test_distinct_provisioner_denied_cleanup_cannot_pass(
    redis_endpoint, provisioner_account, tmp_path
):
    with IsolatedAdmin(port=redis_endpoint[1]) as admin:
        assert (
            admin.execute("ACL", "SETUSER", provisioner_account[0], "-acl|deluser")
            == "OK"
        )
        journal = tmp_path / "denied-cleanup.json"
        result = _run(
            redis_endpoint,
            provisioner_credentials=provisioner_account,
            provisioner_identity_sha256=admission._sha(provisioner_account[0]),
            journal_path=journal,
        )
        assert (
            result["status"] == "BLOCKED"
            and result["diagnostic"] == "ROLE_CLEANUP_FAILED"
        )
        assert result["observer_metadata_verified"] and not result["role_removed"]
        target = json.loads(journal.read_text())["temporary_role"]
        assert admin.execute("ACL", "GETUSER", target) is not None
        assert admin.execute("ACL", "DELUSER", target) == 1


def test_real_failed_auth_cannot_create_role(redis_endpoint, provisioner_account):
    result = _run(
        redis_endpoint,
        provisioner_credentials=(
            provisioner_account[0],
            "incorrect-synthetic-password",
        ),
        provisioner_identity_sha256=admission._sha(provisioner_account[0]),
    )
    assert result["diagnostic"] == "PROVISIONER_AUTH_FAILED"
    assert not result["role_created"] and not result["observer_metadata_verified"]


def test_actual_whoami_mismatch_cannot_create_role(
    redis_endpoint, provisioner_account, monkeypatch
):
    execute = admission._LifecycleClient.execute

    def authenticate_wrong_actor(self, *args):
        if args[0] == "AUTH":
            return execute(self, "AUTH", "default", "synthetic-only")
        return execute(self, *args)

    monkeypatch.setattr(admission._LifecycleClient, "execute", authenticate_wrong_actor)
    result = _run(
        redis_endpoint,
        provisioner_credentials=provisioner_account,
        provisioner_identity_sha256=admission._sha(provisioner_account[0]),
    )
    assert result["diagnostic"] == "PROVISIONER_IDENTITY_MISMATCH"
    assert not result["role_created"] and not result["observer_metadata_verified"]


def test_real_overprivileged_getuser_is_rejected_before_activation(
    redis_endpoint, monkeypatch
):
    execute = admission._LifecycleClient.execute
    corrupted = []

    def inject_permission(self, *args):
        if args == ("ACL", "GETUSER", self.target) and self.claimed and not corrupted:
            with IsolatedAdmin(port=redis_endpoint[1]) as admin:
                assert admin.execute("ACL", "SETUSER", self.target, "+get") == "OK"
                corrupted.append(self.target)
        return execute(self, *args)

    monkeypatch.setattr(admission._LifecycleClient, "execute", inject_permission)
    result = _run(redis_endpoint)
    assert len(corrupted) == 1
    assert result["diagnostic"] == "POLICY_MISMATCH" and result["role_removed"]
    assert not result["policy_on_verified"] and not result["observer_metadata_verified"]


def test_uncertain_setup_response_uses_fresh_cleanup_connection(
    redis_endpoint, monkeypatch
):
    execute = admission._LifecycleClient.execute
    connections = {}

    def timeout_after_setup(self, *args):
        if args == self.setup:
            connections["setup"] = self
            assert execute(self, *args) == "OK"
            raise TimeoutError(
                "synthetic uncertain response after server applied setup"
            )
        if args[:2] == ("ACL", "DELUSER"):
            connections["cleanup"] = self
        return execute(self, *args)

    monkeypatch.setattr(admission._LifecycleClient, "execute", timeout_after_setup)
    result = _run(redis_endpoint)
    assert result["diagnostic"] == "EXERCISE_ERROR_REDACTED" and result["role_removed"]
    assert connections["cleanup"] is not connections["setup"]
    assert not result["role_created"] and result["status"] == "BLOCKED"
    with IsolatedAdmin(port=redis_endpoint[1]) as admin:
        assert admin.execute("ACL", "GETUSER", connections["setup"].target) is None


def test_isolated_label_cannot_target_native_port():
    with pytest.raises(
        admission.AdmissionError, match="ISOLATED_TEST_NATIVE_PORT_REJECTED"
    ):
        _run(("127.0.0.1", 6379))


def test_unknown_signal_handler_rejected_before_journal_or_connection(
    redis_endpoint, tmp_path, monkeypatch
):
    monkeypatch.setattr(signal, "getsignal", lambda _: None)
    journal = tmp_path / "must-not-exist.json"
    with pytest.raises(
        admission.AdmissionError, match="EXERCISE_SIGNAL_HANDLER_UNSUPPORTED"
    ):
        _run(redis_endpoint, journal_path=journal)
    assert not journal.exists()
