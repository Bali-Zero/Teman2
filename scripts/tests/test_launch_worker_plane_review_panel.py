from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import textwrap
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "launch_worker_plane_review_panel.py"
SPEC = importlib.util.spec_from_file_location(
    "launch_worker_plane_review_panel", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
launcher = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = launcher
SPEC.loader.exec_module(launcher)

FREEZER_SPEC = importlib.util.spec_from_file_location(
    "freeze_worker_plane_review",
    REPO_ROOT / "scripts" / "freeze_worker_plane_review.py",
)
assert FREEZER_SPEC is not None and FREEZER_SPEC.loader is not None
freezer = importlib.util.module_from_spec(FREEZER_SPEC)
sys.modules[FREEZER_SPEC.name] = freezer
FREEZER_SPEC.loader.exec_module(freezer)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _git_blob_oid(payload: bytes) -> str:
    framed = f"blob {len(payload)}\0".encode("ascii") + payload
    return hashlib.sha1(framed, usedforsecurity=False).hexdigest()


def test_process_group_permission_error_still_proves_existence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def permission_denied(process_group: int, requested_signal: int) -> None:
        assert process_group == 4242
        assert requested_signal == 0
        raise PermissionError

    monkeypatch.setattr(launcher.os, "killpg", permission_denied)

    assert launcher._process_group_exists(4242) is True


def test_process_group_cleanup_waits_through_transient_permission_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcomes: list[BaseException] = [
        PermissionError(),
        PermissionError(),
        ProcessLookupError(),
    ]
    signals: list[int] = []

    def transient_permission_error(
        process_group: int,
        requested_signal: int,
    ) -> None:
        assert process_group == 4242
        signals.append(requested_signal)
        outcome = outcomes.pop(0)
        raise outcome

    monkeypatch.setattr(launcher.os, "killpg", transient_permission_error)

    launcher._terminate_process_group(4242, grace_seconds=0.1)

    assert signals == [0, launcher.signal.SIGTERM, 0]
    assert not outcomes


def test_process_group_cleanup_reaps_zombie_leader_before_leak_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reaped = False
    signals: list[int] = []
    clock = iter((0.0, 1.0, 1.0, 2.0))

    class ZombieLeader:
        def poll(self) -> int:
            nonlocal reaped
            assert signals[-1] == launcher.signal.SIGKILL
            reaped = True
            return -launcher.signal.SIGKILL

    def process_group_exists(process_group: int) -> bool:
        assert process_group == 4242
        return not reaped

    def record_signal(process_group: int, requested_signal: int) -> None:
        assert process_group == 4242
        signals.append(requested_signal)

    monkeypatch.setattr(launcher, "_process_group_exists", process_group_exists)
    monkeypatch.setattr(launcher.os, "killpg", record_signal)
    monkeypatch.setattr(launcher.time, "monotonic", lambda: next(clock))

    launcher._terminate_process_group(
        4242,
        grace_seconds=0.1,
        leader_process=ZombieLeader(),
    )

    assert reaped is True
    assert signals == [launcher.signal.SIGTERM, launcher.signal.SIGKILL]


def _frozen_review(
    tmp_path: Path,
    *,
    launcher_sha256: str | None = None,
    launcher_git_blob_oid: str | None = None,
) -> tuple[Path, bytes, bytes, bytes]:
    documents = (
        ("covered", "covered.bin", b"covered bytes\n\n"),
        ("instructions", "00-review-brief.md", b"review exactly these bytes\n"),
    )
    entries = [
        {
            "git_blob_oid": _git_blob_oid(content),
            "path": path,
            "role": role,
            "sha256": _sha256(content),
            "size": len(content),
        }
        for role, path, content in documents
    ]
    manifest = {"entries": entries}
    manifest_bytes = freezer.canonical_json_bytes(manifest)
    packet_parts = [
        freezer.PACKET_MAGIC,
        f"MANIFEST {len(manifest_bytes)}\n".encode("ascii"),
        manifest_bytes,
    ]
    for role, path, content in documents:
        role_bytes = role.encode("utf-8")
        path_bytes = path.encode("utf-8")
        packet_parts.extend(
            [
                f"ENTRY {len(role_bytes)} {len(path_bytes)} {len(content)}\n".encode(
                    "ascii"
                ),
                role_bytes,
                path_bytes,
                content,
            ]
        )
    packet_parts.append(freezer.PACKET_END)
    packet_bytes = b"".join(packet_parts)
    parsed = freezer.parse_packet(packet_bytes)

    review_dir = tmp_path / "external" / "sha256" / parsed.packet_sha256
    review_dir.mkdir(parents=True)
    packet_path = review_dir / "packet.bin"
    manifest_path = review_dir / "input-manifest.json"
    config_path = review_dir / "worker-plane-council-v3.json"
    receipt_path = review_dir / "freeze-receipt.json"
    packet_path.write_bytes(packet_bytes)
    manifest_path.write_bytes(manifest_bytes)
    config_path.write_bytes(freezer.EXPECTED_COUNCIL_ROUTE_CONFIG)
    packet_stat = packet_path.stat()
    launcher_bytes = MODULE_PATH.read_bytes()
    route_config_sha256 = _sha256(freezer.EXPECTED_COUNCIL_ROUTE_CONFIG)
    receipt = {
        "base_commit": "1" * 40,
        "built_at_utc": "2026-07-18T00:00:00+00:00",
        "generator_git_blob_oid": "2" * 40,
        "generator_path": "scripts/freeze_worker_plane_review.py",
        "generator_sha256": "3" * 64,
        "generator_version": "3.0.0",
        "git_object_validation": "pass",
        "input_manifest_sha256": parsed.manifest_sha256,
        "launcher_git_blob_oid": (
            launcher_git_blob_oid or _git_blob_oid(launcher_bytes)
        ),
        "launcher_path": "scripts/launch_worker_plane_review_panel.py",
        "launcher_sha256": launcher_sha256 or _sha256(launcher_bytes),
        "packet_bytes": len(packet_bytes),
        "packet_device": packet_stat.st_dev,
        "packet_inode": packet_stat.st_ino,
        "packet_sha256": parsed.packet_sha256,
        "route_config_git_blob_oid": _git_blob_oid(
            freezer.EXPECTED_COUNCIL_ROUTE_CONFIG
        ),
        "route_config_path": (
            "scripts/review_routes/worker-plane-council-v3.json"
        ),
        "route_config_sha256": route_config_sha256,
        "schema": "nuzantara.worker-plane-review-freeze-receipt/v1",
        "source_head": "4" * 40,
        "source_tree": "5" * 40,
        "tracked_status_sha256": _sha256(b""),
        "upstream_commit": "6" * 40,
        "validator_git_blob_oid": "7" * 40,
        "validator_path": "scripts/check_worker_plane_review.py",
        "validator_sha256": "8" * 64,
    }
    receipt_bytes = freezer.canonical_json_bytes(receipt) + b"\n"
    receipt_path.write_bytes(receipt_bytes)
    for path in (packet_path, manifest_path, config_path, receipt_path):
        path.chmod(0o444)
    review_dir.chmod(0o555)
    return review_dir, packet_bytes, manifest_bytes, receipt_bytes


def _write_executable(path: Path, source: str) -> Path:
    path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    path.chmod(0o755)
    return path.resolve()


def _fake_clients(
    tmp_path: Path,
    output_dir: Path,
    *,
    agy_version: str = "1.1.3",
    fail_model: str | None = None,
    fail_status: int = 7,
    fail_once_model: str | None = None,
    emit_claude_metadata: bool = False,
    mutate_packet: Path | None = None,
    review_body: str | None = None,
    kimi_stream_mode: str = "complete",
) -> Any:
    sync_dir = tmp_path / "sync"
    sync_dir.mkdir()
    common = f"""
        #!{sys.executable}
        import json
        import os
        import pathlib
        import re
        import stat
        import sys
        import time

        argv = sys.argv[1:]
        if CLIENT == 'codex' and argv and argv[0].endswith('codex-wrapper.js'):
            argv = argv[1:]
        if '--version' in argv:
            print(VERSION)
            raise SystemExit(0)
        seat = {{
            'gemini': 'Gemini 3.1 Pro (High)',
            'codex': 'account-default',
            'kimi': 'kimi-code/k3',
        }}[CLIENT]
        if CLIENT == 'kimi':
            prompt = argv[argv.index('--prompt') + 1]
            match = re.search(r'@(\\S+)', prompt)
            if match is None:
                raise SystemExit(12)
            data = pathlib.Path(match.group(1)).read_bytes()
        else:
            data = sys.stdin.buffer.read()
        sync_dir = pathlib.Path({str(sync_dir)!r})
        (sync_dir / seat.replace('/', '_').replace(' ', '_')).write_text('ready')
        deadline = time.monotonic() + 5
        while len(list(sync_dir.iterdir())) < 3 and time.monotonic() < deadline:
            time.sleep(0.01)
        visible = sorted(
            path.name for path in pathlib.Path({str(output_dir)!r}).glob('*')
            if '.raw.' in path.name or path.name.endswith('.invocation.json')
        )
        cwd = pathlib.Path.cwd()
        payload = {{
            'argv': argv,
            'cwd': str(cwd),
            'cwd_entries': sorted(path.name for path in cwd.iterdir()),
            'cwd_mode': stat.S_IMODE(cwd.stat().st_mode),
            'input_hex': data.hex(),
            'visible_outputs': visible,
            'anthropic_api_key_present': 'ANTHROPIC_API_KEY' in os.environ,
            'claude_oauth_present': 'CLAUDE_CODE_OAUTH_TOKEN' in os.environ,
            'unrelated_secret_present': 'UNRELATED_SECRET' in os.environ,
            'client': CLIENT,
        }}
        if {emit_claude_metadata!r}:
            payload['session_id'] = 'session-' + seat
            payload['modelUsage'] = {{seat: {{'inputTokens': 1}}}}
        review_body = {review_body!r}
        body = review_body or json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        )
        if CLIENT == 'gemini':
            output = body.encode('utf-8')
        elif CLIENT == 'codex':
            output = (
                json.dumps(
                    {{
                        'type': 'item.completed',
                        'item': {{'type': 'agent_message', 'text': body}},
                    }},
                    ensure_ascii=False,
                    sort_keys=True,
                ) + '\\n'
            ).encode('utf-8')
        else:
            events = []
            stream_mode = {kimi_stream_mode!r}
            tool_path = match.group(1)
            page_plan_match = re.search(
                r'^NUZANTARA_KIMI_READ_PAGE_PLAN (\\[[^\\n]+\\])$',
                prompt,
                flags=re.MULTILINE,
            )
            if page_plan_match is None:
                raise SystemExit(13)
            page_plan = json.loads(page_plan_match.group(1))
            transport_text = data.decode('utf-8')
            if not transport_text.endswith('\\n') or '\\r' in transport_text:
                raise SystemExit(14)
            transport_lines = transport_text[:-1].split('\\n')
            tool_calls = []
            tool_events = []
            for page_index, (line_offset, n_lines) in enumerate(page_plan):
                tool_call_id = f'tool-read-review-input-{{page_index}}'
                page_path = tool_path
                if stream_mode == 'outside' and page_index == 0:
                    page_path += '.outside'
                tool_call = {{
                    'type': 'function',
                    'id': tool_call_id,
                    'function': {{
                        'name': 'Read',
                        'arguments': json.dumps(
                            {{
                                'path': page_path,
                                'line_offset': line_offset,
                                'n_lines': n_lines,
                            }},
                            sort_keys=True,
                        ),
                    }},
                }}
                selected_lines = transport_lines[
                    line_offset - 1 : line_offset - 1 + n_lines
                ]
                if stream_mode == 'partial' and page_index == 0:
                    selected_lines = selected_lines[:-1]
                tool_content = '\\n'.join(
                    f'{{line_number}}\\t{{line}}'
                    for line_number, line in enumerate(
                        selected_lines,
                        start=line_offset,
                    )
                )
                if stream_mode == 'preview' and page_index == 0:
                    tool_content = (
                        'Tool output exceeded 50000 characters; '
                        'showing a preview only.'
                    )
                tool_calls.append(tool_call)
                tool_events.append(
                    {{
                        'role': 'tool',
                        'tool_call_id': tool_call_id,
                        'content': tool_content,
                    }}
                )
            if stream_mode == 'out_of_order' and len(tool_events) > 1:
                tool_events[0], tool_events[1] = tool_events[1], tool_events[0]
            if stream_mode == 'mixed':
                events.append(
                    {{
                        'role': 'assistant',
                        'content': body,
                        'tool_calls': tool_calls,
                    }}
                )
                events.extend(tool_events)
                events.append({{'role': 'assistant', 'content': body}})
            elif stream_mode == 'no_read':
                events.append({{'role': 'assistant', 'content': body}})
            else:
                events.append({{'role': 'assistant', 'tool_calls': tool_calls}})
                events.extend(tool_events)
                events.append({{'role': 'assistant', 'content': body}})
                if stream_mode == 'multiple':
                    events.append({{'role': 'assistant', 'content': body + '-again'}})
            events.append({{'role': 'meta', 'type': 'session.resume_hint'}})
            if stream_mode == 'post_meta':
                events.append({{'role': 'assistant', 'content': body + '-late'}})
            output = (
                ''.join(
                    json.dumps(
                        event,
                        ensure_ascii=False,
                        sort_keys=True,
                    ) + '\\n'
                    for event in events
                )
            ).encode('utf-8')
        sys.stdout.buffer.write(output)
        sys.stderr.buffer.write(('stderr-' + seat + '\\n').encode())
        if {fail_model!r} == seat:
            raise SystemExit({fail_status!r})
        fail_once_marker = sync_dir / ('failed-once-' + seat.replace('/', '_').replace(' ', '_'))
        if {fail_once_model!r} == seat and not fail_once_marker.exists():
            fail_once_marker.write_text('failed')
            raise SystemExit(7)
    """
    common_source = textwrap.dedent(common).lstrip()
    shebang, body = common_source.split("\n", 1)
    agy = _write_executable(
        tmp_path / "fake-agy",
        f"{shebang}\nCLIENT = 'gemini'\nVERSION = {agy_version!r}\n{body}",
    )
    codex_node = _write_executable(
        tmp_path / "fake-node",
        f"{shebang}\nCLIENT = 'codex'\nVERSION = 'codex-cli 0.145.0'\n{body}",
    )
    kimi = _write_executable(
        tmp_path / "fake-kimi",
        f"{shebang}\nCLIENT = 'kimi'\nVERSION = 'kimi 0.29.0'\n{body}",
    )
    fable = _write_executable(
        tmp_path / "fake-fable",
        f"{shebang}\nCLIENT = 'gemini'\nVERSION = '2.1.216'\n{body}",
    )
    codex_wrapper = tmp_path / "codex-wrapper.js"
    codex_wrapper.write_text("// immutable wrapper\n", encoding="utf-8")
    codex_package = tmp_path / "codex-package.json"
    codex_package.write_text('{"version":"0.145.0"}\n', encoding="utf-8")
    codex_native = _write_executable(
        tmp_path / "codex-native",
        f"#!{sys.executable}\nraise SystemExit(0)\n",
    )
    mutation = ""
    if mutate_packet is not None:
        mutation = (
            f"path = pathlib.Path({str(mutate_packet)!r}); "
            "path.chmod(0o644); "
            "path.write_bytes(path.read_bytes()[:-1] + b'X')\n"
        )
    sandbox_exec = _write_executable(
        tmp_path / "fake-sandbox-exec",
        f"""#!{sys.executable}
import os
import pathlib
import subprocess
import sys

argv = sys.argv[1:]
if argv[:1] == ['-f']:
    argv = argv[2:]
if argv and argv[0] == '/usr/bin/touch':
    {mutation or "pass"}
    raise SystemExit(1)
result = subprocess.run(
    argv,
    input=sys.stdin.buffer.read(),
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    cwd=os.getcwd(),
    env=os.environ,
    check=False,
)
sys.stdout.buffer.write(result.stdout)
sys.stderr.buffer.write(result.stderr)
raise SystemExit(result.returncode)
""",
    )
    return launcher.ClientPaths(
        fable=fable,
        gemini=agy,
        codex_node=codex_node,
        codex_wrapper=codex_wrapper.resolve(),
        codex_package=codex_package.resolve(),
        codex_native=codex_native,
        kimi=kimi,
        sandbox_exec=sandbox_exec,
    )


def _raw_payload(
    path: Path,
    seat: launcher.Seat,
) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    if seat.client == "gemini":
        body = raw.decode("utf-8")
    elif seat.client == "codex":
        body = json.loads(raw.decode("utf-8").splitlines()[-1])["item"]["text"]
    else:
        events = [
            json.loads(line) for line in raw.decode("utf-8").splitlines()
        ]
        body = next(
            event["content"]
            for event in events
            if event.get("role") == "assistant"
            and isinstance(event.get("content"), str)
        )
    return json.loads(body), raw


def _launch_test_panel(**kwargs: Any) -> Any:
    """Run script-based fixtures only through the explicit non-production seam."""
    return launcher.launch_panel(
        **kwargs,
        command_runner=launcher._run_test_path_command,
    )


def test_launch_panel_uses_one_buffer_concurrent_isolated_clients_and_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frozen_review, packet_bytes, manifest_bytes, receipt_bytes = _frozen_review(
        tmp_path
    )
    output_dir = tmp_path / "reviews"
    output_dir.mkdir()
    (output_dir / "00-review-brief.md").write_text("excluded input already committed\n")
    clients = _fake_clients(tmp_path, output_dir)

    packet_path = frozen_review / "packet.bin"
    packet_open_count = 0
    real_open = launcher.os.open
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    executable_sandbox_observations: list[tuple[int, tuple[str, ...]]] = []
    calls_lock = threading.Lock()
    real_run = launcher.subprocess.run

    def tracking_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        nonlocal packet_open_count
        if Path(path) == packet_path and flags & os.O_RDONLY == os.O_RDONLY:
            packet_open_count += 1
        return real_open(path, flags, *args, **kwargs)

    def tracking_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        with calls_lock:
            calls.append((args, dict(kwargs)))
            execution_path = Path(kwargs["executable"])
            if execution_path.parent.name.startswith(
                "worker-plane-review-executables."
            ):
                executable_sandbox_observations.append(
                    (
                        stat.S_IMODE(execution_path.parent.stat().st_mode),
                        tuple(
                            sorted(
                                child.name
                                for child in execution_path.parent.iterdir()
                            )
                        ),
                    )
                )
        return real_run(*args, **kwargs)

    monkeypatch.setattr(launcher.os, "open", tracking_open)
    monkeypatch.setattr(launcher.subprocess, "run", tracking_run)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-leak")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-test-token")
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-leak")

    result = _launch_test_panel(
        frozen_review=frozen_review,
        output_dir=output_dir,
        clients=clients,
    )

    assert packet_open_count == 1
    assert result.packet_sha256 == _sha256(packet_bytes)
    assert (output_dir / "00-review-packet.bin").read_bytes() == packet_bytes
    assert (output_dir / "input-manifest.json").read_bytes() == manifest_bytes
    assert (output_dir / "freeze-receipt.json").read_bytes() == receipt_bytes
    for name in ("00-review-packet.bin", "input-manifest.json", "freeze-receipt.json"):
        assert stat.S_IMODE((output_dir / name).stat().st_mode) == 0o444

    observed: dict[str, dict[str, Any]] = {}
    raw_by_seat: dict[str, bytes] = {}
    receipt_by_seat: dict[str, dict[str, Any]] = {}
    for seat in launcher.SEATS:
        payload, raw = _raw_payload(output_dir / seat.raw_name, seat)
        observed[seat.name] = payload
        raw_by_seat[seat.name] = raw
        receipt_path = output_dir / seat.receipt_name
        receipt_raw = receipt_path.read_bytes()
        receipt = json.loads(receipt_raw)
        assert receipt_raw == freezer.canonical_json_bytes(receipt) + b"\n"
        receipt_by_seat[seat.name] = receipt
        assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o444
        assert stat.S_IMODE((output_dir / seat.raw_name).stat().st_mode) == 0o444
        assert receipt["stdout_sha256"] == _sha256(raw)
        assert receipt["stderr_sha256"] == _sha256(
            (output_dir / seat.stderr_name).read_bytes()
        )
        assert receipt["executable_sha256"] == _sha256(
            Path(receipt["executable_path"]).read_bytes()
        )
        assert receipt["argv_sha256"] == _sha256(
            freezer.canonical_json_bytes(receipt["argv"])
        )
        assert receipt["provider_session_id"] is None
        assert receipt["reported_model"] == {
            "gemini": None,
            "codex": None,
            "kimi": None,
        }[seat.name]
        assert receipt["shell"] is False
        assert receipt["tools_denied"] is False
        assert receipt["cwd_initial_entries"] == []
        assert receipt["cwd_mode"] == "0700"
        assert receipt["cwd_removed_after_run"] is True
        assert receipt["packet_sha256"] == _sha256(packet_bytes)
        assert receipt["review_role"] == seat.role
        assert receipt["input_transport"] == seat.input_transport
        assert receipt["route_config_sha256"] == _sha256(
            freezer.EXPECTED_COUNCIL_ROUTE_CONFIG
        )
        if seat.name == "kimi":
            assert receipt["sandbox_enforced"] is True
            assert receipt["canary_write_denied"] is True
            assert receipt["canary_sha256_before"] == receipt["canary_sha256_after"]
        else:
            assert receipt["sandbox_enforced"] is False

    assert (
        len(
            {
                receipt["launcher_invocation_uuid"]
                for receipt in receipt_by_seat.values()
            }
        )
        == 3
    )
    expected_review_input = launcher._review_input_bytes(
        packet_bytes=packet_bytes,
        input_manifest_sha256=_sha256(manifest_bytes),
    )
    assert bytes.fromhex(observed["gemini"]["input_hex"]) == expected_review_input
    assert bytes.fromhex(observed["codex"]["input_hex"]) == expected_review_input
    expected_kimi_transport = launcher._kimi_review_transport_bytes(
        expected_review_input
    )
    assert bytes.fromhex(observed["kimi"]["input_hex"]) == expected_kimi_transport
    for receipt in receipt_by_seat.values():
        assert receipt["review_input_schema"] == launcher.REVIEW_INPUT_SCHEMA
        assert receipt["review_input_bytes"] == len(expected_review_input)
        assert receipt["review_input_sha256"] == _sha256(expected_review_input)
    assert {value["cwd"] for value in observed.values()} == {
        receipt["cwd_path"] for receipt in receipt_by_seat.values()
    }
    assert len({value["cwd"] for value in observed.values()}) == 3
    assert all(value["cwd_mode"] == 0o700 for value in observed.values())
    assert observed["gemini"]["cwd_entries"] == []
    assert observed["codex"]["cwd_entries"] == []
    assert observed["kimi"]["cwd_entries"] == [
        "00-review-input.transport.txt",
        "kimi-read-only.sb",
        "write-denied.canary",
    ]
    assert all(value["visible_outputs"] == [] for value in observed.values())

    gemini = observed["gemini"]
    codex = observed["codex"]
    kimi = observed["kimi"]
    assert gemini["argv"] == list(launcher.GEMINI_ARGV_SUFFIX)
    assert codex["argv"] == list(launcher.CODEX_ARGV_SUFFIX)
    assert kimi["argv"][: len(launcher.KIMI_ARGV_SUFFIX)] == list(
        launcher.KIMI_ARGV_SUFFIX
    )
    assert kimi["argv"][-2] == "--prompt"
    assert "@/" in kimi["argv"][-1]
    for payload in observed.values():
        assert "--session-id" not in payload["argv"]
        assert packet_bytes not in [arg.encode() for arg in payload["argv"]]
        assert payload["anthropic_api_key_present"] is False
        assert payload["unrelated_secret_present"] is False
    assert "-p" not in gemini["argv"] and "-p -" not in gemini["argv"]
    assert all(payload["claude_oauth_present"] is False for payload in observed.values())
    assert "ephemeral-test-token" not in "".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in output_dir.iterdir()
        if path.is_file()
    )
    assert {
        receipt["requested_route"] for receipt in receipt_by_seat.values()
    } == {"Gemini 3.1 Pro (High)", "account-default", "kimi-code/k3"}

    # Production dispatch uses the authenticated descriptor/spawn seam rather
    # than subprocess.run(input=...), so the three provider payloads are
    # asserted from their captured raw responses above.
    assert len(observed) == 3
    # Low-level descriptor spawning intentionally bypasses subprocess.run;
    # the authenticated executable and shared cwd are proven by receipts and
    # captured provider payloads above.


def test_launch_panel_rejects_old_gemini_without_spawning_reviewers(
    tmp_path: Path,
) -> None:
    frozen_review, _, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    clients = _fake_clients(tmp_path, output_dir, agy_version="1.1.1")

    with pytest.raises(launcher.LauncherError, match="Gemini client 1.1.2 or newer"):
        _launch_test_panel(
            frozen_review=frozen_review,
            output_dir=output_dir,
            clients=clients,
        )

    assert not list(output_dir.glob("*.raw.*"))
    assert not list(output_dir.glob("*.invocation.json"))


def test_launch_panel_fails_closed_on_nonzero_seat_without_publishing_outputs(
    tmp_path: Path,
) -> None:
    frozen_review, _, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    clients = _fake_clients(tmp_path, output_dir, fail_model="kimi-code/k3")

    with pytest.raises(launcher.LauncherError, match="kimi exited with status 7"):
        _launch_test_panel(
            frozen_review=frozen_review,
            output_dir=output_dir,
            clients=clients,
        )

    assert not list(output_dir.glob("*.raw.*"))
    assert not list(output_dir.glob("*.invocation.json"))


def test_launch_panel_detects_frozen_packet_mutation_before_dispatch(
    tmp_path: Path,
) -> None:
    frozen_review, _, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    clients = _fake_clients(
        tmp_path,
        output_dir,
        mutate_packet=frozen_review / "packet.bin",
    )

    with pytest.raises(
        launcher.LauncherError, match="frozen packet changed after verification"
    ):
        _launch_test_panel(
            frozen_review=frozen_review,
            output_dir=output_dir,
            clients=clients,
        )

    assert not list(output_dir.glob("*.raw.*"))
    assert not list(output_dir.glob("*.invocation.json"))


def test_launch_panel_fails_if_any_output_cannot_be_published(tmp_path: Path) -> None:
    frozen_review, _, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    output_dir.mkdir()
    clients = _fake_clients(tmp_path, output_dir)
    occupied = output_dir / launcher.SEATS[0].raw_name
    occupied.write_bytes(b"pre-existing")

    with pytest.raises(
        launcher.LauncherError, match="refusing to replace existing output"
    ):
        _launch_test_panel(
            frozen_review=frozen_review,
            output_dir=output_dir,
            clients=clients,
        )

    assert occupied.read_bytes() == b"pre-existing"
    assert not list(output_dir.glob("*.invocation.json"))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"launcher_sha256": "0" * 64}, "launcher SHA-256"),
        ({"launcher_git_blob_oid": "0" * 40}, "launcher Git blob"),
    ],
)
def test_launch_panel_authenticates_launcher_from_freeze_receipt_before_spawn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, str],
    message: str,
) -> None:
    frozen_review, _, _, _ = _frozen_review(tmp_path, **overrides)
    output_dir = tmp_path / "reviews"
    clients = _fake_clients(tmp_path, output_dir)

    def forbidden_spawn(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a client was spawned before launcher authentication")

    monkeypatch.setattr(launcher.subprocess, "run", forbidden_spawn)
    with pytest.raises(launcher.LauncherError, match=message):
        _launch_test_panel(
            frozen_review=frozen_review,
            output_dir=output_dir,
            clients=clients,
        )

    assert not output_dir.exists() or not list(output_dir.iterdir())


def test_launch_panel_records_protocol_defined_reviewer_metadata(
    tmp_path: Path,
) -> None:
    frozen_review, _, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    clients = _fake_clients(tmp_path, output_dir, emit_claude_metadata=True)

    _launch_test_panel(
        frozen_review=frozen_review,
        output_dir=output_dir,
        clients=clients,
    )

    receipts = {
        seat.name: json.loads((output_dir / seat.receipt_name).read_bytes())
        for seat in launcher.SEATS
    }
    assert receipts["gemini"]["provider_session_id"] is None
    assert receipts["gemini"]["reported_model"] is None
    assert receipts["codex"]["provider_session_id"] is None
    assert receipts["codex"]["reported_model"] is None
    assert receipts["kimi"]["provider_session_id"] is None
    assert receipts["kimi"]["reported_model"] is None


def test_launch_panel_atomically_normalizes_exact_unedited_provider_bodies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen_review, _, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    body = "\n# Exact body\nUnicode: café 日本語\n\ntrailing blank line\n\n"
    clients = _fake_clients(
        tmp_path,
        output_dir,
        emit_claude_metadata=True,
        review_body=body,
    )
    real_publish = launcher._publish_new_files
    publication_groups: list[tuple[str, ...]] = []

    def tracking_publish(
        directory: Path,
        files: dict[str, bytes],
    ) -> tuple[launcher.PublishedFile, ...]:
        publication_groups.append(tuple(files))
        return real_publish(directory, files)

    monkeypatch.setattr(launcher, "_publish_new_files", tracking_publish)
    _launch_test_panel(
        frozen_review=frozen_review,
        output_dir=output_dir,
        clients=clients,
    )

    assert publication_groups[0] == launcher.VALIDATOR_INPUT_NAMES
    expected_review_group = tuple(
        name
        for seat in launcher.SEATS
        for name in (
            seat.raw_name,
            seat.stderr_name,
            seat.receipt_name,
            seat.review_name,
        )
    )
    assert set(publication_groups[1]) == {
        *expected_review_group,
        launcher.REVIEWERS_MARKER_NAME,
    }
    assert len(publication_groups) == 2

    expected_frontmatter_keys = (
        "requested_route",
        "launcher_invocation_uuid",
        "provider_session_id",
        "reported_model",
        "input_manifest_sha256",
        "packet_sha256",
        "launcher_proof_sha256",
        "raw_response_sha256",
    )
    for seat in launcher.SEATS:
        normalized = (output_dir / seat.review_name).read_bytes()
        frontmatter_end = normalized.find(b"---\n", 4)
        assert frontmatter_end > 4
        frontmatter_lines = normalized[4:frontmatter_end].decode("utf-8").splitlines()
        frontmatter = dict(line.split(": ", 1) for line in frontmatter_lines)
        assert tuple(frontmatter) == expected_frontmatter_keys
        assert normalized[frontmatter_end + 4 :] == body.encode("utf-8")

        raw = (output_dir / seat.raw_name).read_bytes()
        if seat.client == "gemini":
            assert raw == body.encode("utf-8")
        elif seat.client == "codex":
            event = json.loads(raw.decode("utf-8").splitlines()[-1])
            assert event["item"]["text"] == body
        else:
            events = [
                json.loads(line) for line in raw.decode("utf-8").splitlines()
            ]
            assert [event["role"] for event in events] == [
                "assistant",
                "tool",
                "assistant",
                "meta",
            ]
            assert events[0]["tool_calls"][0]["function"]["name"] == "Read"
            assert events[2]["content"] == body
            assert events[3]["type"] == "session.resume_hint"
        receipt_bytes = (output_dir / seat.receipt_name).read_bytes()
        assert frontmatter["launcher_proof_sha256"] == _sha256(receipt_bytes)
        assert frontmatter["raw_response_sha256"] == _sha256(raw)
    assert not (output_dir / launcher.FINAL_GATE_MARKER_NAME).exists()


def test_kimi_stream_accepts_attested_read_trace_before_review(
    tmp_path: Path,
) -> None:
    frozen_review, _, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    review_body = "Kimi review body"
    clients = _fake_clients(
        tmp_path,
        output_dir,
        review_body=review_body,
    )

    _launch_test_panel(
        frozen_review=frozen_review,
        output_dir=output_dir,
        clients=clients,
    )

    kimi = next(seat for seat in launcher.SEATS if seat.name == "kimi")
    events = [
        json.loads(line)
        for line in (output_dir / kimi.raw_name).read_text().splitlines()
    ]
    assert [event["role"] for event in events] == [
        "assistant",
        "tool",
        "assistant",
        "meta",
    ]
    assert events[0]["tool_calls"][0]["function"]["name"] == "Read"
    assert events[2]["content"] == review_body
    assert (output_dir / kimi.review_name).read_bytes().endswith(
        review_body.encode("utf-8")
    )


def test_kimi_stream_accepts_one_batched_assistant_event_for_many_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(launcher, "KIMI_READ_MAX_LINES", 1)
    frozen_review, _, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    review_body = "Batched Kimi review body"
    clients = _fake_clients(
        tmp_path,
        output_dir,
        review_body=review_body,
    )

    _launch_test_panel(
        frozen_review=frozen_review,
        output_dir=output_dir,
        clients=clients,
    )

    kimi = next(seat for seat in launcher.SEATS if seat.name == "kimi")
    events = [
        json.loads(line)
        for line in (output_dir / kimi.raw_name).read_text().splitlines()
    ]
    tool_calls = events[0]["tool_calls"]
    tool_events = events[1:-2]
    assert len(tool_calls) > 1
    assert len(tool_events) == len(tool_calls)
    assert [event["role"] for event in tool_events] == ["tool"] * len(tool_calls)
    assert [event["tool_call_id"] for event in tool_events] == [
        tool_call["id"] for tool_call in tool_calls
    ]
    assert events[-2] == {"role": "assistant", "content": review_body}
    assert events[-1] == {"role": "meta", "type": "session.resume_hint"}


def test_kimi_stream_rejects_out_of_order_batched_results_without_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(launcher, "KIMI_READ_MAX_LINES", 1)
    frozen_review, _, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    clients = _fake_clients(
        tmp_path,
        output_dir,
        kimi_stream_mode="out_of_order",
    )

    with pytest.raises(launcher.LauncherError, match="canonical order"):
        _launch_test_panel(
            frozen_review=frozen_review,
            output_dir=output_dir,
            clients=clients,
        )

    assert not list(output_dir.iterdir())


def test_kimi_stream_ignores_tool_preamble_and_keeps_only_terminal_review(
    tmp_path: Path,
) -> None:
    frozen_review, _, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    review_body = "Terminal Kimi review body"
    clients = _fake_clients(
        tmp_path,
        output_dir,
        review_body=review_body,
        kimi_stream_mode="mixed",
    )

    _launch_test_panel(
        frozen_review=frozen_review,
        output_dir=output_dir,
        clients=clients,
    )

    kimi = next(seat for seat in launcher.SEATS if seat.name == "kimi")
    events = [
        json.loads(line)
        for line in (output_dir / kimi.raw_name).read_text().splitlines()
    ]
    assert events[0]["content"] == review_body
    assert events[0]["tool_calls"][0]["function"]["name"] == "Read"
    assert events[-2] == {"role": "assistant", "content": review_body}
    assert (output_dir / kimi.review_name).read_bytes().endswith(
        review_body.encode("utf-8")
    )


def test_kimi_transport_wraps_long_lines_losslessly_below_read_limit() -> None:
    source = (
        "short\n"
        + ("A" * 2_500)
        + "\n"
        + ("🌋" * 600)
        + "\n"
    ).encode("utf-8")

    transport = launcher._kimi_review_transport_bytes(source)
    lines = transport.decode("utf-8").splitlines()

    assert lines[0] == launcher.KIMI_TRANSPORT_SCHEMA
    assert f"SOURCE_REVIEW_INPUT_SHA256 {_sha256(source)}" in lines
    assert any(" part=1/2\t" in line for line in lines)
    assert max(len(line.encode("utf-8")) for line in lines) <= (
        launcher.KIMI_TRANSPORT_MAX_LINE_BYTES
    )


def test_kimi_read_page_plan_stays_below_framework_and_tool_limits() -> None:
    source = (
        "".join(
            f"line-{index:05d} " + ("🌋" if index % 7 == 0 else "A") * 240 + "\n"
            for index in range(2_500)
        )
    ).encode("utf-8")
    transport = launcher._kimi_review_transport_bytes(source)
    transport_text = transport.decode("utf-8")
    transport_lines = transport_text[:-1].split("\n")
    page_plan = launcher._kimi_read_page_plan(transport)

    assert len(page_plan) > 1
    assert page_plan[0][0] == 1
    assert sum(n_lines for _, n_lines in page_plan) == len(transport_lines)
    expected_offset = 1
    for line_offset, n_lines in page_plan:
        assert line_offset == expected_offset
        assert 1 <= n_lines <= launcher.KIMI_READ_MAX_LINES
        rendered = "\n".join(
            f"{line_number}\t{transport_lines[line_number - 1]}"
            for line_number in range(line_offset, line_offset + n_lines)
        )
        assert launcher._utf16_code_units(rendered) <= (
            launcher.KIMI_READ_PAGE_MAX_UTF16_UNITS
        )
        assert len(rendered.encode("utf-8")) <= (launcher.KIMI_READ_PAGE_MAX_UTF8_BYTES)
        expected_offset += n_lines


def test_kimi_read_page_plan_honors_exact_independent_boundaries() -> None:
    exact_utf16 = (("🌋" * 19_999) + "\nnext\n").encode("utf-8")
    assert (
        launcher._utf16_code_units("1\t" + ("🌋" * 19_999))
        == launcher.KIMI_READ_PAGE_MAX_UTF16_UNITS
    )
    assert launcher._kimi_read_page_plan(exact_utf16) == ((1, 1), (2, 1))

    exact_utf8 = (("€" * 27_306) + "\nnext\n").encode("utf-8")
    assert len(("1\t" + ("€" * 27_306)).encode("utf-8")) == (
        launcher.KIMI_READ_PAGE_MAX_UTF8_BYTES
    )
    assert launcher._kimi_read_page_plan(exact_utf8) == ((1, 1), (2, 1))

    line_limited = ("x\n" * 1_001).encode("utf-8")
    assert launcher._kimi_read_page_plan(line_limited) == ((1, 1_000), (1_001, 1))

    unicode_separator_is_content = "alpha\u2028beta\nomega\n".encode("utf-8")
    page_plan = launcher._kimi_read_page_plan(unicode_separator_is_content)
    assert sum(n_lines for _, n_lines in page_plan) == 2


def test_kimi_read_registration_accepts_exact_ordered_batch_atomically() -> None:
    planned_pages = ((1, 10), (11, 10), (21, 10))
    expected_path = "/immutable/review.transport.txt"
    pending: dict[str, tuple[int, int]] = {}
    seen_pages: list[tuple[int, int]] = []
    seen_ids: set[str] = set()

    def event(*calls: tuple[str, int, int]) -> dict[str, object]:
        return {
            "tool_calls": [
                {
                    "type": "function",
                    "id": tool_call_id,
                    "function": {
                        "name": "Read",
                        "arguments": json.dumps(
                            {
                                "path": expected_path,
                                "line_offset": line_offset,
                                "n_lines": n_lines,
                            }
                        ),
                    },
                }
                for tool_call_id, line_offset, n_lines in calls
            ]
        }

    with pytest.raises(launcher.LauncherError, match="canonical page plan"):
        launcher._register_kimi_read_calls(
            event(("swapped", 11, 10)),
            expected_input_path=expected_path,
            planned_read_pages=planned_pages,
            pending_tool_reads=pending,
            seen_read_pages=seen_pages,
            seen_tool_ids=seen_ids,
        )
    assert pending == {}
    assert seen_pages == []
    assert seen_ids == set()

    launcher._register_kimi_read_calls(
        event(("first", 1, 10), ("second", 11, 10)),
        expected_input_path=expected_path,
        planned_read_pages=planned_pages,
        pending_tool_reads=pending,
        seen_read_pages=seen_pages,
        seen_tool_ids=seen_ids,
    )
    assert pending == {"first": (1, 10), "second": (11, 10)}
    assert seen_pages == [(1, 10), (11, 10)]
    assert seen_ids == {"first", "second"}

    with pytest.raises(launcher.LauncherError, match="no result pending"):
        launcher._register_kimi_read_calls(
            event(("third", 21, 10)),
            expected_input_path=expected_path,
            planned_read_pages=planned_pages,
            pending_tool_reads=pending,
            seen_read_pages=seen_pages,
            seen_tool_ids=seen_ids,
        )


@pytest.mark.parametrize(
    "invalid_calls",
    (
        (("first", 1, 10), ("first", 11, 10)),
        (("first", 1, 10), ("third", 21, 10)),
    ),
)
def test_kimi_read_registration_rejects_invalid_batch_without_partial_state(
    invalid_calls: tuple[tuple[str, int, int], ...],
) -> None:
    expected_path = "/immutable/review.transport.txt"
    planned_pages = ((1, 10), (11, 10), (21, 10))
    event = {
        "tool_calls": [
            {
                "type": "function",
                "id": tool_call_id,
                "function": {
                    "name": "Read",
                    "arguments": json.dumps(
                        {
                            "path": expected_path,
                            "line_offset": line_offset,
                            "n_lines": n_lines,
                        }
                    ),
                },
            }
            for tool_call_id, line_offset, n_lines in invalid_calls
        ]
    }
    pending: dict[str, tuple[int, int]] = {}
    seen_pages: list[tuple[int, int]] = []
    seen_ids: set[str] = set()

    with pytest.raises(launcher.LauncherError):
        launcher._register_kimi_read_calls(
            event,
            expected_input_path=expected_path,
            planned_read_pages=planned_pages,
            pending_tool_reads=pending,
            seen_read_pages=seen_pages,
            seen_tool_ids=seen_ids,
        )

    assert pending == {}
    assert seen_pages == []
    assert seen_ids == set()


def test_kimi_read_results_must_follow_batched_call_order() -> None:
    pending = {"first": (1, 1), "second": (2, 1)}
    transport_lines = ("alpha", "beta")
    covered_lines: set[int] = set()

    with pytest.raises(launcher.LauncherError, match="canonical order"):
        launcher._consume_kimi_read_result(
            {
                "role": "tool",
                "tool_call_id": "second",
                "content": "2\tbeta",
            },
            pending_tool_reads=pending,
            transport_lines=transport_lines,
            covered_lines=covered_lines,
        )

    assert pending == {"first": (1, 1), "second": (2, 1)}
    assert covered_lines == set()


def test_invalid_kimi_read_result_does_not_mutate_pending_or_coverage() -> None:
    pending = {"first": (1, 2)}
    covered_lines: set[int] = set()

    with pytest.raises(launcher.LauncherError, match="review transport"):
        launcher._consume_kimi_read_result(
            {
                "role": "tool",
                "tool_call_id": "first",
                "content": "1\talpha\n2\taltered",
            },
            pending_tool_reads=pending,
            transport_lines=("alpha", "beta"),
            covered_lines=covered_lines,
        )

    assert pending == {"first": (1, 2)}
    assert covered_lines == set()


@pytest.mark.parametrize(
    ("stream_mode", "message"),
    (
        ("no_read", "before reading the full transport"),
        ("partial", "lacks its exact requested range"),
        ("preview", "lacks its exact requested range"),
        ("outside", "outside its review input"),
        ("multiple", "multiple review responses"),
        ("post_meta", "resume hint is not the final event"),
    ),
)
def test_kimi_stream_rejects_incomplete_or_ambiguous_read_proof(
    tmp_path: Path,
    stream_mode: str,
    message: str,
) -> None:
    frozen_review, _, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    clients = _fake_clients(
        tmp_path,
        output_dir,
        kimi_stream_mode=stream_mode,
    )

    with pytest.raises(launcher.LauncherError, match=message):
        _launch_test_panel(
            frozen_review=frozen_review,
            output_dir=output_dir,
            clients=clients,
        )

    assert not list(output_dir.glob("*.raw.*"))
    assert not list(output_dir.glob("*.invocation.json"))


def test_failed_launch_cleans_own_validator_inputs_and_can_retry_same_directory(
    tmp_path: Path,
) -> None:
    frozen_review, _, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    clients = _fake_clients(tmp_path, output_dir, fail_once_model="kimi-code/k3")

    with pytest.raises(launcher.LauncherError, match="kimi exited with status 7"):
        _launch_test_panel(
            frozen_review=frozen_review,
            output_dir=output_dir,
            clients=clients,
        )

    assert not list(output_dir.iterdir())
    result = _launch_test_panel(
        frozen_review=frozen_review,
        output_dir=output_dir,
        clients=clients,
    )
    assert len(result.receipt_paths) == 3


@pytest.mark.parametrize("cleanup_mode", ["raise", "noop"])
def test_launch_panel_fails_closed_without_receipts_when_cwd_cleanup_is_unproven(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cleanup_mode: str,
) -> None:
    frozen_review, _, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    clients = _fake_clients(tmp_path, output_dir)
    real_rmtree = launcher.shutil.rmtree
    attempted: list[Path] = []

    def broken_rmtree(path: Any, *args: Any, **kwargs: Any) -> None:
        attempted.append(Path(path))
        if cleanup_mode == "raise":
            raise OSError("synthetic cleanup failure")

    monkeypatch.setattr(launcher.shutil, "rmtree", broken_rmtree)
    try:
        with pytest.raises(launcher.LauncherError, match="review cwd cleanup"):
            _launch_test_panel(
                frozen_review=frozen_review,
                output_dir=output_dir,
                clients=clients,
            )
        assert attempted
        assert not list(output_dir.iterdir())
    finally:
        monkeypatch.setattr(launcher.shutil, "rmtree", real_rmtree)
        for path in attempted:
            if path.exists():
                real_rmtree(path)


def test_preexisting_canonical_output_blocks_before_any_provider_spawn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen_review, _, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    output_dir.mkdir()
    occupied = output_dir / launcher.SEATS[0].raw_name
    occupied.write_bytes(b"pre-existing")
    clients = _fake_clients(tmp_path, output_dir)
    spawn_count = 0

    def forbidden_spawn(*args: Any, **kwargs: Any) -> Any:
        nonlocal spawn_count
        spawn_count += 1
        raise AssertionError("provider spawn was not preflighted")

    monkeypatch.setattr(launcher.subprocess, "run", forbidden_spawn)
    with pytest.raises(
        launcher.LauncherError, match="refusing to replace existing output"
    ):
        _launch_test_panel(
            frozen_review=frozen_review,
            output_dir=output_dir,
            clients=clients,
        )

    assert spawn_count == 0
    assert occupied.read_bytes() == b"pre-existing"
    assert sorted(path.name for path in output_dir.iterdir()) == [occupied.name]


def test_launch_panel_rejects_symlinked_client_without_spawning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen_review, _, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    clients = _fake_clients(tmp_path, output_dir)
    linked_kimi = tmp_path / "linked-kimi"
    linked_kimi.symlink_to(clients.kimi)
    clients = replace(clients, kimi=linked_kimi.absolute())
    spawn_count = 0

    def forbidden_spawn(*args: Any, **kwargs: Any) -> Any:
        nonlocal spawn_count
        spawn_count += 1
        raise AssertionError("symlinked executable was spawned")

    monkeypatch.setattr(launcher.subprocess, "run", forbidden_spawn)
    with pytest.raises(launcher.LauncherError, match="must not be a symlink"):
        _launch_test_panel(
            frozen_review=frozen_review,
            output_dir=output_dir,
            clients=clients,
        )
    assert spawn_count == 0


def test_launch_panel_detects_same_bytes_executable_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen_review, packet_bytes, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    clients = _fake_clients(tmp_path, output_dir)
    real_run = launcher._run_popen_command
    replaced = False

    def replace_after_gemini_run(
        *args: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[bytes]:
        nonlocal replaced
        result = real_run(*args, **kwargs)
        argv = kwargs["argv"]
        if not replaced and "--mode" in argv:
            replacement = tmp_path / "replacement-agy"
            replacement.write_bytes(clients.gemini.read_bytes())
            replacement.chmod(0o755)
            os.replace(replacement, clients.gemini)
            replaced = True
        return result

    monkeypatch.setattr(launcher, "_run_popen_command", replace_after_gemini_run)
    with pytest.raises(launcher.LauncherError, match="Gemini executable changed"):
        _launch_test_panel(
            frozen_review=frozen_review,
            output_dir=output_dir,
            clients=clients,
        )
    assert replaced is True
    assert not list(output_dir.iterdir())


def test_launch_panel_never_executes_canonical_path_after_authentication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen_review, packet_bytes, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    clients = _fake_clients(tmp_path, output_dir)
    unauthenticated_marker = tmp_path / "unauthenticated-executable-ran"
    gemini_sync_marker = tmp_path / "sync" / "Gemini_3.1_Pro_(High)"
    unauthenticated_gemini = _write_executable(
        tmp_path / "unauthenticated-agy",
        f"""#!{sys.executable}
import pathlib
import sys

pathlib.Path({str(unauthenticated_marker)!r}).write_text("executed")
pathlib.Path({str(gemini_sync_marker)!r}).write_text("ready")
sys.stdin.buffer.read()
sys.stdout.write("unauthenticated review")
""",
    )
    authenticated_backup = tmp_path / "authenticated-agy"
    real_run = launcher._run_popen_command
    swapped = False

    def swap_canonical_path_during_run(
        *args: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[bytes]:
        nonlocal swapped
        argv = kwargs["argv"]
        if not swapped and "--mode" in argv:
            clients.gemini.rename(authenticated_backup)
            unauthenticated_gemini.rename(clients.gemini)
            try:
                return real_run(*args, **kwargs)
            finally:
                clients.gemini.rename(unauthenticated_gemini)
                authenticated_backup.rename(clients.gemini)
                swapped = True
        return real_run(*args, **kwargs)

    monkeypatch.setattr(launcher, "_run_popen_command", swap_canonical_path_during_run)
    with pytest.raises(launcher.LauncherError, match="Gemini executable changed"):
        try:
            _launch_test_panel(
                frozen_review=frozen_review,
                output_dir=output_dir,
                clients=clients,
            )
        finally:
            assert not unauthenticated_marker.exists()

    assert swapped is True


def test_darwin_canonical_policy_attests_loaded_image_without_private_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_path = _write_executable(
        tmp_path / "canonical-client",
        f"""#!{sys.executable}
print("canonical")
""",
    )
    private_path = _write_executable(
        tmp_path / "private-client",
        f"""#!{sys.executable}
print("private")
""",
    )
    canonical = launcher._authenticate_file(
        canonical_path,
        "canonical test client",
        require_executable=True,
    )
    private_copy = launcher._authenticate_file(
        private_path,
        "private test client",
        require_executable=True,
    )
    identity = launcher.ExecutableIdentity(
        path=canonical.path,
        sha256=canonical.sha256,
        cdhash="ab" * 20,
        team_identifier="TESTTEAM",
        designated_requirement="synthetic test requirement",
        darwin_spawn_canonical=True,
    )
    prepared = launcher.PreparedExecutable(
        canonical=canonical,
        private_copy=private_copy,
        identity=identity,
    )
    attested: list[tuple[launcher.AuthenticatedFile, launcher.ExecutableIdentity]] = []
    observed: dict[str, Any] = {}

    def attest(
        authenticated: launcher.AuthenticatedFile,
        expected: launcher.ExecutableIdentity,
        label: str,
    ) -> None:
        assert label == "canonical policy"
        attested.append((authenticated, expected))

    def spawn(**kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        observed.update(kwargs)
        return subprocess.CompletedProcess(
            args=list(kwargs["argv"]),
            returncode=0,
            stdout=b"review",
            stderr=b"",
        )

    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    monkeypatch.setattr(launcher, "_attest_executable_identity", attest)
    monkeypatch.setattr(launcher, "_darwin_spawn_suspended", spawn)

    result = launcher._run_bound_command(
        executable=prepared,
        argv=(str(canonical.path), "--review"),
        input_bytes=b"packet",
        cwd=tmp_path,
        environment={},
        label="canonical policy",
        wall_timeout_seconds=30,
        termination_grace_seconds=1,
        max_output_bytes=1024,
    )

    assert result.stdout == b"review"
    assert attested == [(canonical, identity)]
    assert observed["executable_path"] == canonical.path
    assert observed["expected_cdhash"] == bytes.fromhex(identity.cdhash)


def test_codesign_identity_accepts_adhoc_designated_requirement_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = _write_executable(tmp_path / "adhoc-client", "#!/bin/sh\n")
    outputs = iter(
        (
            subprocess.CompletedProcess(
                args=["codesign", "--verify"],
                returncode=0,
                stdout=b"",
                stderr=b"",
            ),
            subprocess.CompletedProcess(
                args=["codesign", "-dvvv"],
                returncode=0,
                stdout=b"",
                stderr=(
                    b"CDHash=e31a6a98489a6d1c0afeaec28a86c70c9f8d3644\n"
                    b"TeamIdentifier=not set\n"
                    b'# designated => cdhash H"e31a6a98489a6d1c0afeaec28a86c70c9f8d3644"\n'
                ),
            ),
        )
    )

    monkeypatch.setattr(
        launcher.subprocess,
        "run",
        lambda *args, **kwargs: next(outputs),
    )

    assert launcher._codesign_identity(executable, "ad-hoc fixture") == (
        "e31a6a98489a6d1c0afeaec28a86c70c9f8d3644",
        "not set",
        'cdhash H"e31a6a98489a6d1c0afeaec28a86c70c9f8d3644"',
    )


def test_macho_cdhash_ignores_short_non_code_directory_blob() -> None:
    non_code_directory = struct.pack(">II", 0xFADE0C01, 8)
    code_directory = bytearray(44)
    struct.pack_into(">II", code_directory, 0, 0xFADE0C02, len(code_directory))
    code_directory[37] = 2
    index_bytes = 2 * 8
    first_blob_offset = 12 + index_bytes
    second_blob_offset = first_blob_offset + len(non_code_directory)
    signature_length = second_blob_offset + len(code_directory)
    signature = b"".join(
        (
            struct.pack(">III", 0xFADE0CC0, signature_length, 2),
            struct.pack(">II", 0, first_blob_offset),
            struct.pack(">II", 0, second_blob_offset),
            non_code_directory,
            bytes(code_directory),
        )
    )
    header_size = 32
    command_size = 16
    signature_offset = header_size + command_size
    header = bytearray(header_size)
    header[:4] = b"\xcf\xfa\xed\xfe"
    struct.pack_into("<I", header, 16, 1)
    command = struct.pack(
        "<IIII",
        0x1D,
        command_size,
        signature_offset,
        len(signature),
    )

    assert launcher._macho_cdhash(bytes(header) + command + signature) == (
        hashlib.sha256(code_directory).digest()[:20]
    )


@pytest.mark.skipif(sys.platform != "darwin", reason="Darwin vnode race proof")
def test_private_copy_replacement_after_last_check_never_executes_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A same-UID swap at the exec boundary must not run a different vnode."""
    jq_path = shutil.which("jq")
    if jq_path is None:
        pytest.skip("jq is required for the signed Mach-O race fixture")
    canonical = Path(jq_path).resolve()
    replacement_source = Path(sys.executable).resolve()
    try:
        launcher._macho_cdhash(canonical.read_bytes())
        launcher._macho_cdhash(replacement_source.read_bytes())
    except launcher.LauncherError:
        pytest.skip("race fixture requires two signed thin Mach-O images")
    executable_sandbox, _ = launcher._sandbox(
        prefix="worker-plane-review-executables-guilt."
    )
    marker = tmp_path / "replacement-executed"
    python_program = (
        "from pathlib import Path; "
        f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')"
    )
    seat = launcher.Seat(
        name="guilt",
        requested_route="guilt",
        client="test",
        argv_suffix=("-c", python_program),
        raw_name="guilt.raw",
        stderr_name="guilt.stderr",
        receipt_name="guilt.invocation",
        review_name="guilt.md",
    )
    real_spawn = launcher._darwin_spawn_suspended
    swapped = False

    try:
        prepared = launcher._validate_executable(
            canonical.resolve(),
            "guilt",
            executable_sandbox,
        )
        launcher._seal_executable_sandbox(executable_sandbox, (prepared,))

        def swap_private_copy_at_exec_boundary(
            **kwargs: Any,
        ) -> subprocess.CompletedProcess[bytes]:
            nonlocal swapped
            if not swapped:
                executable_sandbox.chmod(0o700)
                replacement = tmp_path / "replacement-python"
                shutil.copyfile(
                    replacement_source,
                    replacement,
                )
                replacement.chmod(0o500)
                os.replace(replacement, prepared.private_copy.path)
                executable_sandbox.chmod(0o500)
                swapped = True
            return real_spawn(**kwargs)

        monkeypatch.setattr(
            launcher,
            "_darwin_spawn_suspended",
            swap_private_copy_at_exec_boundary,
        )
        with pytest.raises(
            launcher.LauncherError,
            match="executable changed at the Darwin spawn boundary",
        ):
            launcher._run_seat(
                seat=seat,
                executable=prepared,
                client_version="test",
                packet_bytes=b"",
                cwd=tmp_path,
                environment=launcher._base_environment(os.environ),
                invocation_uuid="00000000-0000-0000-0000-000000000000",
                command_runner=launcher._run_bound_command,
            )
        assert swapped is True
        assert not marker.exists()
    finally:
        launcher._remove_sandbox(executable_sandbox)


@pytest.mark.skipif(sys.platform != "darwin", reason="Darwin bound-spawn primitive")
def test_darwin_bound_runner_executes_authenticated_signed_image(
    tmp_path: Path,
) -> None:
    jq_path = shutil.which("jq")
    if jq_path is None:
        pytest.skip("jq is required for the signed Mach-O execution fixture")
    canonical = Path(jq_path).resolve()
    try:
        launcher._macho_cdhash(canonical.read_bytes())
    except launcher.LauncherError:
        pytest.skip("execution fixture requires a signed thin Mach-O image")
    executable_sandbox, _ = launcher._sandbox(
        prefix="worker-plane-review-executables-bound."
    )
    try:
        prepared = launcher._validate_executable(
            canonical,
            "bound execution",
            executable_sandbox,
        )
        launcher._seal_executable_sandbox(executable_sandbox, (prepared,))
        result = launcher._run_bound_command(
            executable=prepared,
            argv=(str(prepared.canonical.path), "--version"),
            input_bytes=b"",
            cwd=tmp_path,
            environment=launcher._base_environment(os.environ),
            label="bound execution",
        )
        assert result.returncode == 0
        assert result.stdout.startswith(b"jq-")
    finally:
        launcher._remove_sandbox(executable_sandbox)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS system binary contract")
def test_macos_sandbox_exec_uses_authenticated_read_only_system_image(
    tmp_path: Path,
) -> None:
    executable_sandbox, _ = launcher._sandbox(
        prefix="worker-plane-review-security-test."
    )
    try:
        prepared = launcher._validate_executable(
            launcher.PRODUCTION_CLIENTS.sandbox_exec,
            "sandbox-exec",
            executable_sandbox,
            allow_read_only_canonical=True,
        )
        assert prepared.private_copy.path == launcher.PRODUCTION_CLIENTS.sandbox_exec
        result = subprocess.run(
            [
                str(prepared.canonical.path),
                "-p",
                "(version 1)(allow default)",
                "/usr/bin/true",
            ],
            executable=str(prepared.private_copy.path),
            input=b"",
            shell=False,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0
    finally:
        launcher._remove_sandbox(executable_sandbox)


def test_cli_pins_production_absolute_routes() -> None:
    parser = launcher.build_parser()
    args = parser.parse_args(
        ["--frozen-review", "/tmp/frozen", "--output-dir", "/tmp/output"]
    )

    assert args.clients == launcher.PRODUCTION_CLIENTS
    assert launcher.PRODUCTION_CLIENTS.fable == Path(
        "/Users/nuzantara/.local/share/claude/versions/2.1.216"
    )
    assert launcher.PRODUCTION_CLIENTS.gemini == Path("/Users/nuzantara/.local/bin/agy")
    assert launcher.PRODUCTION_CLIENTS.codex_node == Path(
        "/opt/homebrew/Cellar/node/26.5.0/bin/node"
    )
    assert launcher.PRODUCTION_CLIENTS.kimi == Path(
        "/Users/nuzantara/.kimi-code/bin/kimi"
    )
    assert launcher.PRODUCTION_CLIENTS.sandbox_exec == Path(
        "/usr/bin/sandbox-exec"
    )
    assert launcher.DEFAULT_WALL_TIMEOUT_SECONDS == 30 * 60.0
    assert launcher.GEMINI_ARGV_SUFFIX[4] == "30m"


def test_kimi_timeout_124_marks_seat_unavailable_and_publishes_nothing(
    tmp_path: Path,
) -> None:
    frozen_review, _, _, _ = _frozen_review(tmp_path)
    output_dir = tmp_path / "reviews"
    clients = _fake_clients(
        tmp_path,
        output_dir,
        fail_model="kimi-code/k3",
        fail_status=124,
    )

    with pytest.raises(
        launcher.LauncherError,
        match=r"Kimi seat unavailable \(timeout exit 124\)",
    ):
        _launch_test_panel(
            frozen_review=frozen_review,
            output_dir=output_dir,
            clients=clients,
        )

    assert not list(output_dir.glob("*.raw.*"))
    assert not list(output_dir.glob("*.invocation.json"))


def test_production_kimi_and_codex_identity_chain_is_fully_pinned() -> None:
    kimi = launcher.PRODUCTION_IDENTITIES["kimi"]
    codex_node = launcher.PRODUCTION_IDENTITIES["codex_node"]
    codex_native = launcher.PRODUCTION_IDENTITIES["codex_native"]

    assert launcher.REQUIRED_KIMI_VERSION == (0, 29, 0)
    assert kimi.sha256 == (
        "5cccf53604f20c5499ea10c3094298f49a1ad59fa90cddd9fd7e0ba44815fdd3"
    )
    assert kimi.cdhash == "160e1dd4f3a46bc6f5179f58785f53e20ad9f4ea"
    assert kimi.team_identifier == "2J9472RW75"
    assert launcher.REQUIRED_CODEX_VERSION == (0, 145, 0)
    assert codex_node.sha256 == (
        "70851490e028b3d699a8d6d4e1de909af2a989359ae807974c92af9c6580a8e8"
    )
    assert codex_native.sha256 == (
        "1da3f4e0e96028b8a771814293c3033dafd1971f943f6c7e79b0897fe705f590"
    )
    assert launcher.PRODUCTION_ARTIFACT_SHA256 == {
        "codex_wrapper": (
            "134063e133f0b4244fa3b251acf973d4fe4b4aeeacbdc135211bf480f59f1477"
        ),
        "codex_package": (
            "ff896fd5e5444cfc645890b21273ad1c6b3e26e4e4ab0934de597a0f8db5aafb"
        ),
    }


def test_sequential_fable_gate_is_explicitly_fail_closed(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        launcher.LauncherError,
        match="sequential Fable final gate is not implemented",
    ):
        launcher.launch_final_gate(
            reviewer_output_dir=tmp_path / "reviews",
            disposition_path=tmp_path / "99-disposition.md",
        )
