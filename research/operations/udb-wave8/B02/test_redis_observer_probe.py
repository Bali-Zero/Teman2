"""Unit and isolated ephemeral Redis 8.x integration tests for B02 (`DUX-NOTE-CORRECTION.md`).

Covers:
1. `test_recording_transport_rejects_every_non_allowlisted_observer_command`:
   Proves that `GET`, `KEYS`, `SCAN`, `HGETALL`, `XRANGE`, `SET`, `DEL`, `FLUSHDB`,
   `FLUSHALL`, `CONFIG`, `ACL LIST`, `ACL GETUSER`, `ACL SETUSER`, `ACL DRYRUN`, and
   `EVAL` are rejected by `validate_observer_command` before a single byte is written to
   the observer transport (`recorded_commands == []`, `written_bytes == b""`).
2. `test_mixed_permission_counterexample_leaves_every_forbidden_command_unexecuted`:
   Configures a fake ACL that denies all 9 reads (`GET`, `KEYS`, `SCAN`, `HGETALL`,
   `XRANGE`, `CONFIG GET`, `ACL LIST`, `ACL GETUSER`, `ACL DRYRUN`) and ALLOWS a
   mutation (`SET` or `DEL`). Proves that the observer connection sends zero forbidden
   commands, while the separate provisioner `ACL DRYRUN` matrix detects the allowed
   mutation (`FAILED_OVERPRIVILEGED`, `status == "CONFLICT"`) without executing it.
3. `test_dryrun_failures_unsupported_denied_unexpected_and_stale_binding_never_fallback`:
   Tests `ACL DRYRUN` unsupported, `ACL DRYRUN` denied (`-NOPERM`), `ACL DRYRUN`
   unexpected reply, missing provisioner admission (`provisioner_client=None`), and
   stale identity / endpoint / `acl_policy_sha256` / `source_version` binding mismatches,
   proving zero live-command fallback in every case.
4. `test_ephemeral_redis8_server_isolated_dryrun_and_observer_allowlist`:
   Spawns a real `redis-server` 8.x on a private loopback port (`!= 6379`) using a
   mode-`0600` config file in `tmp_path` (no secrets on `argv`), verifying both
   compliant admission (`ADMITTED_VERIFIED`) and the mixed-permission counterexample
   on real Redis 8.x `ACL DRYRUN`.
5. `test_secret_hygiene_across_proposal_argv_stdout_and_files`:
   Asserts that no synthetic secret or forbidden CLI secret pattern appears in `argv`,
   `stdout`, written artifacts, or `REDIS-OBSERVER-ADMISSION-PROPOSAL.md`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import socketserver
import subprocess
import threading
import time
from typing import Any

import pytest

import importlib.util
import sys


def _load_local_module(module_name: str, filename: str) -> Any:
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _get_probe_mod() -> Any:
    return _load_local_module("b02_redis_observer_probe", "redis_observer_probe.py")


def _get_census_mod() -> Any:
    return _load_local_module("b02_redis_consumer_census", "redis_consumer_census.py")


SYNTHETIC_ADMIN_TOKEN = "SYNTHETIC_TEST_ONLY_ADMIN_TOKEN_99A1"
SYNTHETIC_OBS_TOKEN = "SYNTHETIC_TEST_ONLY_OBSERVER_TOKEN_88B2"


class RecordingObserverClient:
    """In-memory subclass of RespSocketClient that records raw bytes written to the socket."""

    def __init__(self, mod: Any, role: str = "observer") -> None:
        self._mod = mod
        self.role = role
        self.recorded_commands: list[tuple[str, ...]] = []
        self.written_payloads: list[bytes] = []

    def execute(self, *args: str) -> Any:
        if self.role == "observer":
            self._mod.validate_observer_command(args)
        else:
            self._mod.validate_provisioner_command(args)
        self.recorded_commands.append(self._mod._redact_command_for_log(args))
        self.written_payloads.append(self._mod.encode_resp_command(args))
        return "OK"


class FakeRespServer:
    """Threaded in-process RESP2 server for deterministic unit testing."""

    def __init__(
        self,
        observer_password: str = SYNTHETIC_OBS_TOKEN,
        admin_password: str = SYNTHETIC_ADMIN_TOKEN,
        require_auth: bool = True,
        allowed_observer_commands: set[str] | None = None,
        dryrun_mode: str = "normal",
    ) -> None:
        self.observer_password = observer_password
        self.admin_password = admin_password
        self.require_auth = require_auth
        self.dryrun_mode = dryrun_mode
        if allowed_observer_commands is None:
            self.allowed_observer_commands = {
                "PING",
                "ACL|WHOAMI",
                "ROLE",
                "DBSIZE",
                "TIME",
                "COMMAND|COUNT",
                "CLIENT|ID",
                "CLIENT|INFO",
                "INFO",
            }
        else:
            self.allowed_observer_commands = set(allowed_observer_commands)

        self.executed_by_role: dict[str, list[tuple[str, ...]]] = {
            "unauthenticated": [],
            "nuzantara_observer": [],
            "default": [],
        }
        self._lock = threading.Lock()
        self._server = self._build_server()
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def _build_server(self) -> socketserver.ThreadingTCPServer:
        outer = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                authed = not outer.require_auth
                current_user = "default" if not outer.require_auth else "unauthenticated"
                while True:
                    line = self.rfile.readline()
                    if not line:
                        break
                    if not line.startswith(b"*"):
                        break
                    count = int(line[1:-2].decode("ascii"))
                    args: list[str] = []
                    for _ in range(count):
                        len_line = self.rfile.readline()
                        length = int(len_line[1:-2].decode("ascii"))
                        data = self.rfile.read(length)
                        self.rfile.read(2)
                        args.append(data.decode("utf-8"))
                    if not args:
                        continue
                    cmd = args[0].upper()
                    sub = args[1].upper() if len(args) > 1 else ""
                    composite = f"{cmd}|{sub}" if sub else cmd

                    if cmd == "AUTH":
                        if len(args) == 3 and args[1] == "nuzantara_observer" and args[2] == outer.observer_password:
                            authed = True
                            current_user = "nuzantara_observer"
                            self.wfile.write(b"+OK\r\n")
                        elif len(args) == 3 and args[1] == "default" and args[2] == outer.admin_password:
                            authed = True
                            current_user = "default"
                            self.wfile.write(b"+OK\r\n")
                        elif len(args) == 2 and args[1] == outer.admin_password:
                            authed = True
                            current_user = "default"
                            self.wfile.write(b"+OK\r\n")
                        else:
                            self.wfile.write(
                                b"-WRONGPASS invalid username-password pair or user is disabled.\r\n"
                            )
                        continue

                    with outer._lock:
                        outer.executed_by_role.setdefault(current_user, []).append(tuple(args))

                    if not authed:
                        self.wfile.write(b"-NOAUTH Authentication required.\r\n")
                        continue

                    if cmd == "ACL" and sub == "DRYRUN":
                        if current_user != "default":
                            self.wfile.write(
                                b"-NOPERM this user has no permissions to run the 'acl|dryrun' command\r\n"
                            )
                            continue
                        if outer.dryrun_mode == "unsupported":
                            self.wfile.write(
                                b"-ERR unknown subcommand or wrong number of arguments for 'DRYRUN'.\r\n"
                            )
                            continue
                        if outer.dryrun_mode == "denied":
                            self.wfile.write(
                                b"-NOPERM this user has no permissions to run the 'acl|dryrun' command\r\n"
                            )
                            continue
                        if outer.dryrun_mode == "unexpected":
                            self.wfile.write(b":42\r\n")
                            continue

                        sim_cmd = args[3].upper() if len(args) > 3 else ""
                        sim_sub = args[4].upper() if len(args) > 4 else ""
                        sim_comp = f"{sim_cmd}|{sim_sub}" if sim_sub else sim_cmd
                        if (
                            sim_cmd in outer.allowed_observer_commands
                            or sim_comp in outer.allowed_observer_commands
                        ):
                            self.wfile.write(b"+OK\r\n")
                        else:
                            msg = (
                                f"This user has no permissions to run the '{sim_cmd.lower()}' command"
                            ).encode("utf-8")
                            self.wfile.write(f"${len(msg)}\r\n".encode("ascii") + msg + b"\r\n")
                        continue

                    if current_user != "default" and (
                        cmd not in outer.allowed_observer_commands
                        and composite not in outer.allowed_observer_commands
                    ):
                        self.wfile.write(
                            f"-NOPERM this user has no permissions to run the '{ composite.lower() }' command\r\n".encode(
                                "utf-8"
                            )
                        )
                        continue

                    if cmd == "PING":
                        self.wfile.write(b"+PONG\r\n")
                    elif composite == "ACL|WHOAMI":
                        b_user = current_user.encode("utf-8")
                        self.wfile.write(f"${len(b_user)}\r\n".encode("ascii") + b_user + b"\r\n")
                    elif cmd == "ROLE":
                        self.wfile.write(b"*3\r\n$6\r\nmaster\r\n:0\r\n*0\r\n")
                    elif cmd == "DBSIZE":
                        self.wfile.write(b":42\r\n")
                    elif cmd == "TIME":
                        self.wfile.write(b"*2\r\n$10\r\n1760516000\r\n$3\r\n123\r\n")
                    elif composite == "COMMAND|COUNT":
                        self.wfile.write(b":245\r\n")
                    elif composite == "CLIENT|ID":
                        self.wfile.write(b":7\r\n")
                    elif composite == "CLIENT|INFO":
                        cinfo = f"id=7 addr=127.0.0.1:55111 fd=8 name= db=0 flags=N user={current_user} resp=2\n".encode(
                            "utf-8"
                        )
                        self.wfile.write(f"${len(cinfo)}\r\n".encode("ascii") + cinfo + b"\r\n")
                    elif cmd == "INFO":
                        sec = args[1].lower() if len(args) > 1 else "server"
                        payload = outer._info_payload(sec).encode("utf-8")
                        self.wfile.write(f"${len(payload)}\r\n".encode("ascii") + payload + b"\r\n")
                    else:
                        self.wfile.write(b"+OK\r\n")

        class ReusableTCPServer(socketserver.ThreadingTCPServer):
            allow_reuse_address = True

        return ReusableTCPServer(("127.0.0.1", 0), Handler)

    @staticmethod
    def _info_payload(section: str) -> str:
        payloads = {
            "server": (
                "# Server\r\nredis_version:8.10.2\r\nredis_mode:standalone\r\n"
                "os:Darwin 25.0.0 arm64\r\narch_bits:64\r\ntcp_port:6379\r\n"
                "uptime_in_seconds:86400\r\nexecutable:/opt/homebrew/opt/redis/bin/redis-server\r\n"
                "config_file:/opt/homebrew/etc/redis.conf\r\nsecret_line_ignored:should_not_appear\r\n"
            ),
            "persistence": (
                "# Persistence\r\nloading:0\r\naof_enabled:0\r\n"
                "rdb_last_bgsave_status:ok\r\nrdb_last_save_time:1760515000\r\n"
                "rdb_changes_since_last_save:0\r\n"
            ),
            "keyspace": "# Keyspace\r\ndb0:keys=42,expires=10,avg_ttl=3600000\r\n",
            "memory": (
                "# Memory\r\nused_memory:1048576\r\nused_memory_human:1.00M\r\n"
                "used_memory_peak:2097152\r\nmaxmemory:0\r\nmaxmemory_policy:noeviction\r\n"
                "mem_fragmentation_ratio:1.25\r\n"
            ),
            "clients": "# Clients\r\nconnected_clients:3\r\nblocked_clients:0\r\nmaxclients:10000\r\n",
            "stats": (
                "# Stats\r\ntotal_connections_received:100\r\ntotal_commands_processed:5000\r\n"
                "instantaneous_ops_per_sec:2\r\nrejected_connections:0\r\n"
                "keyspace_hits:400\r\nkeyspace_misses:20\r\nevicted_keys:0\r\nexpired_keys:5\r\n"
            ),
            "replication": "# Replication\r\nrole:master\r\nconnected_slaves:0\r\nmaster_repl_offset:0\r\n",
        }
        return payloads.get(section, "")

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()


def test_recording_transport_rejects_every_non_allowlisted_observer_command() -> None:
    """Prove that forbidden commands are rejected on the observer transport before writing any byte."""
    mod = _get_probe_mod()
    recorder = RecordingObserverClient(mod, role="observer")

    forbidden_commands: list[tuple[str, ...]] = [
        ("GET", "any_key"),
        ("KEYS", "*"),
        ("SCAN", "0"),
        ("HGETALL", "any_hash"),
        ("XRANGE", "any_stream", "-", "+"),
        ("SET", "any_key", "1"),
        ("DEL", "any_key"),
        ("FLUSHDB",),
        ("FLUSHALL",),
        ("CONFIG", "GET", "maxmemory"),
        ("CONFIG", "SET", "maxmemory", "0"),
        ("ACL", "LIST"),
        ("ACL", "GETUSER", "default"),
        ("ACL", "SETUSER", "rogue", "on"),
        ("ACL", "DRYRUN", "nuzantara_observer", "PING"),
        ("EVAL", "return 1", "0"),
        ("SHUTDOWN", "NOSAVE"),
        ("INFO", "all"),
        ("INFO", "everything"),
        ("CLIENT", "KILL", "ID", "1"),
    ]

    for cmd in forbidden_commands:
        with pytest.raises(mod.ObserverCommandNotAllowedError):
            recorder.execute(*cmd)

    assert recorder.recorded_commands == []
    assert recorder.written_payloads == []

    # Verify allowlisted observer commands succeed and record redacted AUTH
    recorder.execute("AUTH", "nuzantara_observer", SYNTHETIC_OBS_TOKEN)
    recorder.execute("PING")
    recorder.execute("ACL", "WHOAMI")
    recorder.execute("INFO", "server")
    assert recorder.recorded_commands == [
        ("AUTH", "nuzantara_observer", "<REDACTED>"),
        ("PING",),
        ("ACL", "WHOAMI"),
        ("INFO", "server"),
    ]
    assert SYNTHETIC_OBS_TOKEN.encode("utf-8") not in b"".join(
        " ".join(c).encode("utf-8") for c in recorder.recorded_commands
    )


def test_mixed_permission_counterexample_leaves_every_forbidden_command_unexecuted() -> None:
    """Mixed-ACL counterexample: all 9 reads denied, 1 mutation (SET/DEL) allowed.

    Proves:
    1. The observer connection NEVER sends any forbidden read or write command.
    2. The provisioner `ACL DRYRUN` connection detects the permitted mutation (`SET`)
       via simulation without executing `SET`, returning `FAILED_OVERPRIVILEGED` and
       `status == "CONFLICT"`.
    """
    mod = _get_probe_mod()
    server = FakeRespServer(
        allowed_observer_commands={
            "PING",
            "ACL|WHOAMI",
            "ROLE",
            "DBSIZE",
            "TIME",
            "COMMAND|COUNT",
            "CLIENT|ID",
            "CLIENT|INFO",
            "INFO",
            "SET",  # Counterexample: all forbidden reads denied, but SET mutation allowed!
            "DEL",
        }
    )
    try:
        with (
            mod.RespSocketClient(host="127.0.0.1", port=server.port, role="observer") as obs_client,
            mod.RespSocketClient(
                host="127.0.0.1", port=server.port, role="provisioner"
            ) as prov_client,
        ):
            prov_client.execute("AUTH", "default", SYNTHETIC_ADMIN_TOKEN)
            report = mod.probe_redis_observer(
                host="127.0.0.1",
                port=server.port,
                credentials=("nuzantara_observer", SYNTHETIC_OBS_TOKEN),
                observer_client=obs_client,
                provisioner_client=prov_client,
            )

            # 1. Observer connection never sent SET, DEL, GET, KEYS, SCAN, or ACL DRYRUN
            obs_verbs = {cmd[0].upper() for cmd in obs_client.recorded_commands}
            assert obs_verbs == {"AUTH", "PING", "ACL", "ROLE", "DBSIZE", "TIME", "COMMAND", "CLIENT", "INFO"}
            server_obs_cmds = server.executed_by_role.get("nuzantara_observer", [])
            for sent in server_obs_cmds:
                mod.validate_observer_command(sent)

            # 2. Provisioner connection only sent AUTH and ACL DRYRUN (never live SET/DEL)
            for p_cmd in prov_client.recorded_commands:
                assert p_cmd[0] == "AUTH" or p_cmd[:2] == ("ACL", "DRYRUN")

            # 3. Combined report catches the over-privileged SET via DRYRUN (`DRY-11`)
            assert report["status"] == "CONFLICT"
            assert report["x_observer_state"] == "FAILED_OVERPRIVILEGED"
            assert "DRYRUN_FORBIDDEN_COMMAND_PERMITTED:DRY-11" in report["unknowns"]
    finally:
        server.close()


def test_dryrun_failures_unsupported_denied_unexpected_and_stale_binding_never_fallback() -> None:
    """Verify all ACL DRYRUN failure modes and dual-plane binding checks without fallback."""
    mod = _get_probe_mod()

    for mode, expected_state, expected_status, expected_unknown in [
        ("unsupported", "DRYRUN_UNSUPPORTED", "UNKNOWN", "ACL_DRYRUN_UNSUPPORTED"),
        ("denied", "DRYRUN_DENIED", "BLOCKED", "ACL_DRYRUN_NOPERM"),
        ("unexpected", "DRYRUN_UNEXPECTED_REPLY", "UNKNOWN", "ACL_DRYRUN_UNEXPECTED_REPLY"),
    ]:
        server = FakeRespServer(dryrun_mode=mode)
        try:
            with (
                mod.RespSocketClient(
                    host="127.0.0.1", port=server.port, role="observer"
                ) as obs_client,
                mod.RespSocketClient(
                    host="127.0.0.1", port=server.port, role="provisioner"
                ) as prov_client,
            ):
                prov_client.execute("AUTH", "default", SYNTHETIC_ADMIN_TOKEN)
                report = mod.probe_redis_observer(
                    host="127.0.0.1",
                    port=server.port,
                    credentials=("nuzantara_observer", SYNTHETIC_OBS_TOKEN),
                    observer_client=obs_client,
                    provisioner_client=prov_client,
                )
                assert report["status"] == expected_status
                assert report["x_observer_state"] == expected_state
                assert expected_unknown in report["unknowns"]
                # Zero live fallback commands on either connection
                for p_cmd in prov_client.recorded_commands:
                    assert p_cmd[0] == "AUTH" or p_cmd[:2] == ("ACL", "DRYRUN")
                for o_cmd in obs_client.recorded_commands:
                    mod.validate_observer_command(
                        ("AUTH", "nuzantara_observer", "redacted")
                        if o_cmd[0] == "AUTH"
                        else o_cmd
                    )
        finally:
            server.close()

    # Missing provisioner connection -> NOT_EXECUTED + LIVE_DRYRUN_MATRIX_NOT_EXECUTED_NO_PROVISIONER_ADMISSION
    server_ok = FakeRespServer()
    try:
        report_no_prov = mod.probe_redis_observer(
            host="127.0.0.1",
            port=server_ok.port,
            credentials=("nuzantara_observer", SYNTHETIC_OBS_TOKEN),
            provisioner_client=None,
        )
        assert report_no_prov["status"] == "BLOCKED"
        assert report_no_prov["x_observer_state"] == "OBSERVER_METADATA_ONLY_DRYRUN_PENDING"
        assert (
            "LIVE_DRYRUN_MATRIX_NOT_EXECUTED_NO_PROVISIONER_ADMISSION"
            in report_no_prov["unknowns"]
        )

        # Dual-plane binding verification: stale endpoint, identity, acl_policy_sha256, source_version
        with mod.RespSocketClient(
            host="127.0.0.1", port=server_ok.port, role="provisioner"
        ) as prov_client:
            prov_client.execute("AUTH", "default", SYNTHETIC_ADMIN_TOKEN)
            valid_dryrun = mod.evaluate_provisioner_dryrun_matrix(
                provisioner_client=prov_client,
                observer_user="nuzantara_observer",
                host="127.0.0.1",
                port=server_ok.port,
            )

        assert valid_dryrun["x_dryrun_state"] == "DRYRUN_MATRIX_VERIFIED"
        admitted = mod.combine_observer_and_dryrun_evidence(report_no_prov, valid_dryrun)
        assert admitted["status"] == "EVIDENCED"
        assert admitted["x_observer_state"] == "ADMITTED_VERIFIED"

        for tamper_field, tamper_val, expected_err in [
            ("endpoint", "127.0.0.1:9999", "EVIDENCE_BINDING_MISMATCH_ENDPOINT"),
            ("observer_identity", "stale_observer", "EVIDENCE_BINDING_MISMATCH_IDENTITY"),
            ("acl_policy_sha256", "0" * 64, "EVIDENCE_BINDING_MISMATCH_ACL_POLICY_HASH"),
            ("source_version", "deadbeef" * 5, "EVIDENCE_BINDING_MISMATCH_SOURCE_VERSION"),
        ]:
            tampered_dry = dict(valid_dryrun)
            tampered_dry[tamper_field] = tamper_val
            rejected = mod.combine_observer_and_dryrun_evidence(report_no_prov, tampered_dry)
            assert rejected["status"] == "CONFLICT"
            assert rejected["x_observer_state"] == "FAILED_EVIDENCE_BINDING_MISMATCH"
            assert expected_err in rejected["unknowns"]
    finally:
        server_ok.close()


def test_fake_resp_default_principal_rejected() -> None:
    """Prove that `default` is rejected before or after connection (`X7`)."""
    mod = _get_probe_mod()
    pre_report = mod.probe_redis_observer(
        host="127.0.0.1",
        port=65530,
        credentials=("default", SYNTHETIC_ADMIN_TOKEN),
    )
    assert pre_report["status"] == "CONFLICT"
    assert pre_report["x_observer_state"] == "REJECTED_OVERPRIVILEGED_DEFAULT"

    server = FakeRespServer(require_auth=False)
    try:
        post_report = mod.probe_redis_observer(
            host="127.0.0.1",
            port=server.port,
            credentials=None,
            env_file=Path("/nonexistent/observer.env"),
        )
        assert post_report["status"] == "CONFLICT"
        assert post_report["x_observer_state"] == "REJECTED_OVERPRIVILEGED_DEFAULT"
        assert post_report["effective_principal"] == mod.identity_sha256("default")
    finally:
        server.close()


def test_fake_resp_unauthenticated_returns_authorization_required() -> None:
    """Prove unauthenticated PING returns UNAUTHENTICATED_NOAUTH."""
    mod = _get_probe_mod()
    server = FakeRespServer(require_auth=True)
    try:
        report = mod.probe_redis_observer(
            host="127.0.0.1",
            port=server.port,
            credentials=None,
            env_file=Path("/nonexistent/observer.env"),
        )
        assert report["status"] == "BLOCKED"
        assert report["x_observer_state"] == "UNAUTHENTICATED_NOAUTH"
        assert "OWNER_CONSENT_REQUIRED_REDIS_OBSERVER_ACL" in report["unknowns"]
    finally:
        server.close()


def test_env_file_mode_0600_enforced_and_zero_secret_leakage(tmp_path: Path) -> None:
    """Prove mode-0600 enforcement on credential file and zero secret leakage in JSON."""
    mod = _get_probe_mod()
    env_path = tmp_path / "observer.env"
    env_path.write_text(
        f"REDIS_OBSERVER_USER=nuzantara_observer\nREDIS_OBSERVER_PASSWORD={SYNTHETIC_OBS_TOKEN}\n",
        encoding="utf-8",
    )
    os.chmod(env_path, 0o644)
    with pytest.raises(PermissionError, match="0o600"):
        mod.load_credentials_from_env_file(env_path)

    os.chmod(env_path, 0o600)
    server = FakeRespServer()
    try:
        with mod.RespSocketClient(
            host="127.0.0.1", port=server.port, role="provisioner"
        ) as prov_client:
            prov_client.execute("AUTH", "default", SYNTHETIC_ADMIN_TOKEN)
            report = mod.probe_redis_observer(
                host="127.0.0.1",
                port=server.port,
                env_file=env_path,
                provisioner_client=prov_client,
            )
        assert report["x_observer_state"] == "ADMITTED_VERIFIED"
        serialized = json.dumps(report)
        assert SYNTHETIC_OBS_TOKEN not in serialized
        assert SYNTHETIC_ADMIN_TOKEN not in serialized
    finally:
        server.close()


def test_contract_conventions_19_keys_and_value_domains() -> None:
    """Verify emitted rows conform to CONTRACT-CONVENTIONS.md (X1-X5)."""
    mod = _get_probe_mod()
    server = FakeRespServer()
    try:
        with mod.RespSocketClient(
            host="127.0.0.1", port=server.port, role="provisioner"
        ) as prov_client:
            prov_client.execute("AUTH", "default", SYNTHETIC_ADMIN_TOKEN)
            report = mod.probe_redis_observer(
                host="127.0.0.1",
                port=server.port,
                store_id="redis:mini:6379/db0",
                credentials=("nuzantara_observer", SYNTHETIC_OBS_TOKEN),
                provisioner_client=prov_client,
            )
        row = mod.build_contract_row(
            report,
            evidence_ref="research/operations/udb-wave8/B02/test_redis_observer_probe.py",
        )
        for k in mod.CONTRACT_FROZEN_KEYS:
            assert k in row
        for k in mod.CONTRACT_INSTANCE_KEYS:
            assert k in row
            cell = row[k]
            assert set(cell.keys()) == {"value", "status", "evidence_ref"}
            assert cell["status"] in mod.CONTRACT_STATUS_VALUES
        assert row["operation_id"]["value"] == "UNASSIGNED_B05"
        assert row["store_id"]["value"] == "redis:mini:6379/db0"
        assert row["status"] == "EVIDENCED"
        assert row["x_observer_state"] == "ADMITTED_VERIFIED"
    finally:
        server.close()


def test_ephemeral_redis8_server_isolated_dryrun_and_observer_allowlist(
    tmp_path: Path,
) -> None:
    """Isolated ephemeral `redis-server` 8.x integration test on a private port (`!= 6379`).

    Passes configuration via a mode-`0600` file in `tmp_path` so not even `redis-server`
    `argv` carries `--requirepass`. Tests both compliant ACL (`ADMITTED_VERIFIED`) and
    mixed-permission counterexample ACL (`SET` allowed, reads denied -> caught by
    provisioner `ACL DRYRUN` without executing `SET`).
    """
    mod = _get_probe_mod()
    redis_server_bin = shutil.which("redis-server") or "/opt/homebrew/opt/redis/bin/redis-server"
    if not Path(redis_server_bin).exists():
        pytest.skip("redis-server binary not found")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]
    assert free_port != 6379

    conf_path = tmp_path / "ephemeral-redis.conf"
    fd = os.open(conf_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(
            f"bind 127.0.0.1\n"
            f"port {free_port}\n"
            f"dir {tmp_path}\n"
            f'save ""\n'
            f"appendonly no\n"
            f"requirepass {SYNTHETIC_ADMIN_TOKEN}\n"
        )

    proc = subprocess.Popen(
        [redis_server_bin, str(conf_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # Ensure argv of the spawned process does not contain any secret token
        assert SYNTHETIC_ADMIN_TOKEN not in " ".join(proc.args)

        ready = False
        for _ in range(40):
            try:
                with mod.RespSocketClient(
                    host="127.0.0.1", port=free_port, timeout=0.5, role="provisioner"
                ) as c:
                    auth_res = c.execute("AUTH", SYNTHETIC_ADMIN_TOKEN)
                    if auth_res == "OK" and c.execute("PING") == "PONG":
                        ready = True
                        break
            except OSError:
                time.sleep(0.05)
        assert ready, "Ephemeral redis-server 8.x did not become ready"

        # Provision compliant nuzantara_observer via socket (using raw encode on admin socket)
        with socket.create_connection(("127.0.0.1", free_port), timeout=2.0) as admin_sock:
            admin_fp = admin_sock.makefile("rb")
            admin_sock.sendall(mod.encode_resp_command(("AUTH", SYNTHETIC_ADMIN_TOKEN)))
            assert admin_fp.readline() == b"+OK\r\n"
            admin_sock.sendall(
                mod.encode_resp_command(
                    (
                        "ACL",
                        "SETUSER",
                        "nuzantara_observer",
                        "on",
                        f">{SYNTHETIC_OBS_TOKEN}",
                        "resetkeys",
                        "resetchannels",
                        "-@all",
                        "+ping",
                        "+info",
                        "+dbsize",
                        "+role",
                        "+time",
                        "+command|count",
                        "+acl|whoami",
                        "+client|info",
                        "+client|id",
                    )
                )
            )
            assert admin_fp.readline() == b"+OK\r\n"

        # 1. Innocence case: compliant ACL passes both observer metadata and provisioner DRYRUN
        with (
            mod.RespSocketClient(
                host="127.0.0.1", port=free_port, role="observer"
            ) as obs_client,
            mod.RespSocketClient(
                host="127.0.0.1", port=free_port, role="provisioner"
            ) as prov_client,
        ):
            prov_client.execute("AUTH", "default", SYNTHETIC_ADMIN_TOKEN)
            innocence = mod.probe_redis_observer(
                host="127.0.0.1",
                port=free_port,
                store_id="redis:mini:6379/db0",
                credentials=("nuzantara_observer", SYNTHETIC_OBS_TOKEN),
                observer_client=obs_client,
                provisioner_client=prov_client,
            )
            assert innocence["status"] == "EVIDENCED"
            assert innocence["x_observer_state"] == "ADMITTED_VERIFIED"
            assert innocence["positive_metadata"]["info_sections"]["server"][
                "redis_version"
            ].startswith("8.")
            assert innocence["positive_metadata"]["dbsize"] == 0

        # 2. Guilt case: mixed-permission ACL (reads denied, +set ~* allowed) caught by DRYRUN without writing any key
        with socket.create_connection(("127.0.0.1", free_port), timeout=2.0) as admin_sock:
            admin_fp = admin_sock.makefile("rb")
            admin_sock.sendall(mod.encode_resp_command(("AUTH", SYNTHETIC_ADMIN_TOKEN)))
            assert admin_fp.readline() == b"+OK\r\n"
            admin_sock.sendall(
                mod.encode_resp_command(
                    (
                        "ACL",
                        "SETUSER",
                        "nuzantara_observer",
                        "on",
                        f">{SYNTHETIC_OBS_TOKEN}",
                        "resetkeys",
                        "resetchannels",
                        "-@all",
                        "+ping",
                        "+info",
                        "+dbsize",
                        "+role",
                        "+time",
                        "+command|count",
                        "+acl|whoami",
                        "+client|info",
                        "+client|id",
                        "+set",
                        "~*",
                    )
                )
            )
            assert admin_fp.readline() == b"+OK\r\n"

        with (
            mod.RespSocketClient(
                host="127.0.0.1", port=free_port, role="observer"
            ) as obs_client,
            mod.RespSocketClient(
                host="127.0.0.1", port=free_port, role="provisioner"
            ) as prov_client,
        ):
            prov_client.execute("AUTH", "default", SYNTHETIC_ADMIN_TOKEN)
            guilt = mod.probe_redis_observer(
                host="127.0.0.1",
                port=free_port,
                store_id="redis:mini:6379/db0",
                credentials=("nuzantara_observer", SYNTHETIC_OBS_TOKEN),
                observer_client=obs_client,
                provisioner_client=prov_client,
            )
            assert guilt["status"] == "CONFLICT"
            assert guilt["x_observer_state"] == "FAILED_OVERPRIVILEGED"
            assert "DRYRUN_FORBIDDEN_COMMAND_PERMITTED:DRY-11" in guilt["unknowns"]
            # Prove DBSIZE is still 0 (no SET was executed!)
            assert obs_client.execute("DBSIZE") == 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_secret_hygiene_across_proposal_argv_stdout_and_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Assert zero synthetic secrets or forbidden CLI secret flags in proposal, argv, stdout, or files."""
    mod = _get_probe_mod()
    b02_dir = Path(__file__).resolve().parent

    env_path = tmp_path / "observer.env"
    env_path.write_text(
        f"REDIS_OBSERVER_USER=nuzantara_observer\nREDIS_OBSERVER_PASSWORD={SYNTHETIC_OBS_TOKEN}\n",
        encoding="utf-8",
    )
    os.chmod(env_path, 0o600)

    server = FakeRespServer()
    try:
        cli_argv = [
            "--host",
            "127.0.0.1",
            "--port",
            str(server.port),
            "--env-file",
            str(env_path),
        ]
        assert SYNTHETIC_OBS_TOKEN not in " ".join(cli_argv)
        assert SYNTHETIC_ADMIN_TOKEN not in " ".join(cli_argv)
        mod.main(cli_argv)
        captured = capsys.readouterr()
        assert SYNTHETIC_OBS_TOKEN not in captured.out
        assert SYNTHETIC_OBS_TOKEN not in captured.err
        assert SYNTHETIC_ADMIN_TOKEN not in captured.out
        assert SYNTHETIC_ADMIN_TOKEN not in captured.err
    finally:
        server.close()

    proposal_text = (b02_dir / "REDIS-OBSERVER-ADMISSION-PROPOSAL.md").read_text(
        encoding="utf-8"
    )
    assert "security add-generic-password" not in proposal_text
    assert 'REDISCLI_AUTH="$' not in proposal_text
    assert ">$OBS_SECRET" not in proposal_text

    for doc_name in (
        "ANALYSIS.md",
        "PROPOSAL.md",
        "DEFINITIVE-SYNTHESIS.md",
        "REDIS-OBSERVER-ADMISSION-PROPOSAL.md",
        "RESULT.json",
        "PR_BODY.md",
    ):
        doc_path = b02_dir / doc_name
        if doc_path.exists():
            content = doc_path.read_text(encoding="utf-8")
            assert SYNTHETIC_OBS_TOKEN not in content
            assert SYNTHETIC_ADMIN_TOKEN not in content


def test_redis_consumer_census_against_pinned_inputs(tmp_path: Path) -> None:
    """Verify `redis_consumer_census.py` against pinned Wave-8 inputs (`X10`, `B02-F7`)."""
    census_mod = _get_census_mod()
    repo_root = Path(__file__).resolve().parents[4]
    out_file = tmp_path / "redis-consumer-ledger.json"
    rc = census_mod.main(["--repo-root", str(repo_root), "--output", str(out_file)])
    assert rc == 0
    assert out_file.exists()
    ledger = json.loads(out_file.read_text(encoding="utf-8"))
    assert ledger["summary"]["union_universe_count"] == 6030
    assert ledger["summary"]["total_redis_tagged_rows"] > 0
    liveness_rows = [
        r for r in ledger["rows"] if r["consumer_id"] == "runtime_6e9b0846bcc0bc34"
    ]
    assert len(liveness_rows) == 1
    assert (
        "HOME_FORK_SHA256_DRIFTED_FROM_20261012_CENSUS:6adec8ac4f1e7fbc3a46f026e92c178d15643796b270eea969e556f25cf3885d"
        in liveness_rows[0]["unknowns"]
    )
    assert (
        ledger["inputs_pinned"]["dux_req_b02_04_pro_sha256"]
        == "521658bea8409fc5531a4ff817701c89a98390cf5837cf0f9f5b9ae3894b690a"
    )


# --- B02-OB-1: synthetic output-boundary regressions (never real credentials) ---
_OB_REJECTED_MARKER = "B02_SYNTHETIC_REJECTED_2d590f"


def _ob_check(ok: bool, code: str) -> None:
    if not ok:
        pytest.fail(code, pytrace=False)


def _ob_no_export(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True)
    _ob_check(_OB_REJECTED_MARKER not in serialized, "B02_OB_VALUE_EXPORTED")
    return serialized


def _ob_rejected(call: Any, error_type: type[Exception]) -> str:
    import traceback

    try:
        call()
    except error_type as exc:
        rendered = "".join(traceback.format_exception(exc))
        _ob_check(_OB_REJECTED_MARKER not in rendered, "B02_OB_EXCEPTION_EXPORTED")
        return rendered
    else:
        pytest.fail("B02_OB_EXPECTED_REJECTION", pytrace=False)


@pytest.mark.parametrize("transport", ["observer", "provisioner"])
def test_ob_rejected_commands_do_not_export_arguments_or_write(transport: str) -> None:
    mod = _get_probe_mod()
    recorder = RecordingObserverClient(mod, role=transport)
    error = mod.ObserverCommandNotAllowedError if transport == "observer" else mod.ProvisionerCommandNotAllowedError
    rendered = _ob_rejected(lambda: recorder.execute("GET", _OB_REJECTED_MARKER), error)
    assert _OB_REJECTED_MARKER not in rendered, "OB_REJECTED_INPUT_EXPORTED"
    assert not recorder.recorded_commands and not recorder.written_payloads, "B02_OB_PREWRITE_ORDER_CHANGED"


@pytest.mark.parametrize("case", ["error", "unexpected", "denial", "unsupported"])
def test_ob_dryrun_reply_summaries_never_export_server_text(case: str) -> None:
    mod = _get_probe_mod()
    replies = {
        "error": mod.RespError("ERR " + _OB_REJECTED_MARKER),
        "unexpected": {_OB_REJECTED_MARKER: _OB_REJECTED_MARKER},
        "denial": _OB_REJECTED_MARKER + " has no permissions to run this command",
        "unsupported": mod.RespError("ERR unknown subcommand " + _OB_REJECTED_MARKER),
    }
    result = mod._classify_dryrun_reply(mod.NEGATIVE_DRYRUN_SPECS[0], replies[case])
    serialized = _ob_no_export(result)
    assert _OB_REJECTED_MARKER not in serialized, "OB_REJECTED_INPUT_EXPORTED"
    assert result["outcome"] == ("VERIFIED" if case == "denial" else "DRYRUN_UNSUPPORTED" if case == "unsupported" else "DRYRUN_UNEXPECTED_REPLY"), "B02_OB_DRYRUN_SEMANTICS_CHANGED"


class _BoundaryObserverReplies:
    role = "observer"

    def __init__(self, mod: Any, case: str = "valid") -> None:
        self.mod = mod
        self.case = case
        self.calls: list[tuple[str, ...]] = []

    def execute(self, *args: str) -> Any:
        self.calls.append(args)
        self.mod.validate_observer_command(args)
        marker = _OB_REJECTED_MARKER
        if args[0] == "AUTH":
            return self.mod.RespError(marker + " failure") if self.case == "auth_error" else "OK"
        if args == ("PING",):
            return self.mod.RespError(marker + " failure") if self.case == "ping_error" else "PONG"
        if args == ("ACL", "WHOAMI"):
            if self.case == "identity":
                return marker
            if self.case == "whoami_error":
                return self.mod.RespError(marker + " failure")
            return self.mod.EXPECTED_OBSERVER_USER
        if args == ("ROLE",):
            return self.mod.RespError("ERR " + marker) if self.case == "role_error" else ["master", 0, []]
        if args == ("DBSIZE",):
            return True if self.case == "dbsize_bool" else 42
        if args == ("TIME",):
            return [marker, "0"] if self.case == "time" else ["1760515000", "0"]
        if args == ("COMMAND", "COUNT"):
            return 250
        if args == ("CLIENT", "ID"):
            return marker if self.case == "client_id" else 7
        if args == ("CLIENT", "INFO"):
            user = marker if self.case == "client_user" else self.mod.EXPECTED_OBSERVER_USER
            name = marker if self.case == "client_name" else ""
            return f"user={user} name={name} db=0 resp=2"
        if args[0] == "INFO":
            if self.case == "info_error":
                return self.mod.RespError(marker + " failure")
            result = FakeRespServer._info_payload(args[1])
            if self.case == "info" and args[1] == "server":
                result = result.replace("redis_version:8.10.2", "redis_version:" + marker)
            return result
        pytest.fail("B02_OB_UNEXPECTED_COMMAND", pytrace=False)


@pytest.mark.parametrize("case", [
    "identity", "auth_error", "role_error", "client_name", "info", "ping_error",
    "whoami_error", "client_user", "time", "client_id", "info_error", "dbsize_bool",
])
def test_ob_probe_reports_redact_untrusted_replies_and_fail_closed(case: str) -> None:
    mod = _get_probe_mod()
    client = _BoundaryObserverReplies(mod, case)
    report = mod.probe_redis_observer(
        credentials=(mod.EXPECTED_OBSERVER_USER, SYNTHETIC_OBS_TOKEN),
        observer_client=client,
    )
    serialized = _ob_no_export(report)
    assert _OB_REJECTED_MARKER not in serialized, "OB_REJECTED_INPUT_EXPORTED"
    assert report["x_observer_state"] != "ADMITTED_VERIFIED", "B02_OB_MISSING_EVIDENCE_PROMOTED"
    if case == "identity":
        assert report["effective_principal"] == mod.identity_sha256(_OB_REJECTED_MARKER), "B02_OB_IDENTITY_HASH_MISSING"
        assert report["x_observer_state"] == "REJECTED_UNEXPECTED_PRINCIPAL", "B02_OB_IDENTITY_ACCEPTED"
    elif case == "client_name":
        assert "name" not in report["positive_metadata"]["client_info"], "B02_OB_CLIENT_NAME_EXPORTED"
        assert report["x_observer_state"] == "OBSERVER_METADATA_ONLY_DRYRUN_PENDING", "B02_OB_VALID_METADATA_REJECTED"
    elif case in {"role_error", "info", "client_user", "time", "client_id", "dbsize_bool"}:
        assert report["x_observer_state"] == "OBSERVER_METADATA_INCOMPLETE", "B02_OB_SANITIZED_MISSING_MEASUREMENT_ACCEPTED"


@pytest.mark.parametrize("section", ["server", "persistence", "keyspace", "memory", "clients", "stats", "replication"])
def test_ob_info_values_are_typed_or_fixed_unknown(section: str) -> None:
    mod = _get_probe_mod()
    raw = FakeRespServer._info_payload(section)
    rejected = "\n".join(line.split(":", 1)[0] + ":" + _OB_REJECTED_MARKER for line in raw.splitlines() if ":" in line)
    filtered = mod.parse_and_filter_info(section, rejected)
    serialized = _ob_no_export(filtered)
    assert _OB_REJECTED_MARKER not in serialized, "OB_REJECTED_INPUT_EXPORTED"
    assert all(value is None for value in filtered.values()), "B02_OB_INFO_UNTYPED_VALUE_ACCEPTED"


def test_ob_resp_integer_parse_exception_has_no_payload() -> None:
    import io

    mod = _get_probe_mod()
    client = mod.RespSocketClient(role="observer")
    client._fp = io.BytesIO(b":" + _OB_REJECTED_MARKER.encode() + b"\r\n")
    client._write_encoded_bytes = lambda payload: None
    rendered = _ob_rejected(lambda: client.execute("PING"), ValueError)
    assert _OB_REJECTED_MARKER not in rendered, "OB_REJECTED_INPUT_EXPORTED"


def test_ob_rejected_evidence_identity_is_not_copied_to_output() -> None:
    mod = _get_probe_mod()
    report = mod.probe_redis_observer(
        credentials=(mod.EXPECTED_OBSERVER_USER, SYNTHETIC_OBS_TOKEN),
        observer_client=_BoundaryObserverReplies(mod),
    )
    dryrun = mod.evaluate_provisioner_dryrun_matrix(None)
    dryrun["observer_identity"] = _OB_REJECTED_MARKER
    combined = mod.combine_observer_and_dryrun_evidence(report, dryrun)
    serialized = _ob_no_export(combined)
    assert _OB_REJECTED_MARKER not in serialized, "OB_REJECTED_INPUT_EXPORTED"
    assert combined["x_observer_state"] == "FAILED_EVIDENCE_BINDING_MISMATCH", "B02_OB_BINDING_REJECTION_LOST"


def test_ob_actual_cli_serialization_contains_no_rejected_info(tmp_path: Path) -> None:
    server = FakeRespServer()
    original = FakeRespServer._info_payload
    server._info_payload = lambda section: original(section).replace("redis_version:8.10.2", "redis_version:" + _OB_REJECTED_MARKER)
    env_path = tmp_path / "synthetic-observer.env"
    env_path.write_text("REDIS_OBSERVER_USER=nuzantara_observer\nREDIS_OBSERVER_PASSWORD=" + SYNTHETIC_OBS_TOKEN + "\n", encoding="utf-8")
    env_path.chmod(0o600)
    try:
        assert server.port != 6379, "B02_OB_NATIVE_PORT_FORBIDDEN"
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(Path(__file__).with_name("redis_observer_probe.py")),
             "--host", "127.0.0.1", "--port", str(server.port), "--env-file", str(env_path)],
            capture_output=True, timeout=15, check=False,
        )
        assert _OB_REJECTED_MARKER.encode() not in result.stdout + result.stderr, "B02_OB_CLI_EXPORTED_VALUE"
        assert result.returncode == 1 and not result.stderr, "B02_OB_CLI_REJECTION_FAILED"
        assert json.loads(result.stdout)["x_observer_state"] == "OBSERVER_METADATA_INCOMPLETE", "B02_OB_CLI_PROMOTED_INVALID_METADATA"
    finally:
        server.close()
        env_path.unlink(missing_ok=True)


def test_ob_actual_cli_bad_argument_has_constant_diagnostic() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(Path(__file__).with_name("redis_observer_probe.py")), "--port", _OB_REJECTED_MARKER],
        capture_output=True, timeout=15, check=False,
    )
    assert result.returncode != 0, "B02_OB_CLI_ARGUMENT_ACCEPTED"
    assert _OB_REJECTED_MARKER.encode() not in result.stdout + result.stderr, "B02_OB_CLI_ARGUMENT_EXPORTED"
    assert b"Traceback" not in result.stderr, "B02_OB_CLI_TRACEBACK_EXPORTED"


@pytest.mark.parametrize("field,bad", [
    ("host", _OB_REJECTED_MARKER), ("store_id", _OB_REJECTED_MARKER),
    ("acl_policy_sha256", _OB_REJECTED_MARKER), ("source_version", _OB_REJECTED_MARKER),
    ("port", _OB_REJECTED_MARKER), ("port", True), ("port", 0), ("port", 65536),
], ids=["host", "store", "policy_hash", "source_hash", "port_type", "port_bool", "port_zero", "port_large"])
@pytest.mark.parametrize("surface", ["probe", "dryrun"])
def test_ob_untrusted_context_rejected_before_credentials_or_connection(
    monkeypatch: Any, field: str, bad: Any, surface: str,
) -> None:
    mod = _get_probe_mod()
    touched: list[bool] = []

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        touched.append(True)
        pytest.fail("B02_OB_CONTEXT_TOUCHED_PRIVILEGED_INPUT", pytrace=False)

    monkeypatch.setattr(mod, "resolve_observer_credentials", forbidden)
    monkeypatch.setattr(mod, "RespSocketClient", forbidden)
    if surface == "probe":
        call = lambda: mod.probe_redis_observer(**{field: bad})
    else:
        call = lambda: mod.evaluate_provisioner_dryrun_matrix(None, **{field: bad})
    rendered = _ob_rejected(call, ValueError)
    assert _OB_REJECTED_MARKER not in rendered, "OB_REJECTED_INPUT_EXPORTED"
    assert not touched, "B02_OB_CONTEXT_PREAUTH_ORDER_CHANGED"


@pytest.mark.parametrize("host,store_id", [
    ("127.0.0.1", "redis:mini:6379/db0"),
    ("127.0.0.1", "redis:pro:6379/db0"),
    ("localhost", "redis:mini:6379/db0"),
    ("::1", "redis:mini:6379/db0"),
])
def test_ob_existing_local_contexts_remain_valid(host: str, store_id: str) -> None:
    mod = _get_probe_mod()
    mod._validate_observer_context(host, 31234, store_id, mod.EXPECTED_OBSERVER_ACL_POLICY_SHA256, mod.BASE_COMMIT_SHA)
    with pytest.raises(ValueError, match=r"^OBSERVER_CONTEXT_REJECTED$"):
        mod._validate_observer_context(host, 0, store_id, mod.EXPECTED_OBSERVER_ACL_POLICY_SHA256, mod.BASE_COMMIT_SHA)


@pytest.mark.parametrize("argument", ["--host", "--store-id"])
def test_ob_actual_cli_rejects_context_without_export(argument: str, tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(Path(__file__).with_name("redis_observer_probe.py")),
         argument, _OB_REJECTED_MARKER, "--env-file", str(tmp_path / "absent.env")],
        capture_output=True, timeout=15, check=False,
    )
    assert result.returncode != 0 and not result.stdout, "B02_OB_CLI_CONTEXT_ACCEPTED"
    assert _OB_REJECTED_MARKER.encode() not in result.stderr, "B02_OB_CLI_CONTEXT_EXPORTED"
    assert b"Traceback" not in result.stderr, "B02_OB_CLI_CONTEXT_TRACEBACK"
