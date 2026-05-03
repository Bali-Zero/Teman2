"""Tests for scripts/wr2-hardening-chain.sh — Sprint 2 W3 observed-shell bridge.

The chain script is best-effort: per-CLI ObservedShellBus emits + final
aggregate emit. The tests mock the helper via OBSERVED_SHELL_HELPER env
and capture what gets called.
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "wr2-hardening-chain.sh"


def _make_wrapper(tmp_path: Path, exit_codes: dict[str, int]) -> Path:
    """Build a fake WR2_WRAPPER that exits with the per-module code from the
    mapping. The wrapper receives the module name as its first arg."""
    wrapper = tmp_path / "wrapper.sh"
    cases = "\n".join(
        f'        {mod}) exit {ec} ;;'
        for mod, ec in exit_codes.items()
    )
    wrapper.write_text(
        "#!/bin/bash\n"
        'case "$1" in\n'
        f"{cases}\n"
        "        *) exit 99 ;;\n"
        "esac\n"
    )
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    return wrapper


def _make_emit_helper(tmp_path: Path, capture_path: Path) -> Path:
    """Build a fake observed-shell-emit.sh that appends every call as a TSV
    line so the test can assert on (name, status, payload, trace_id)."""
    helper = tmp_path / "observed-shell-emit.sh"
    helper.write_text(
        "#!/bin/bash\n"
        "observed_shell_emit() {\n"
        f'    printf "%s\\t%s\\t%s\\t%s\\n" "$1" "$2" "$3" "$4" >> "{capture_path}"\n'
        "    return 0\n"
        "}\n"
    )
    helper.chmod(helper.stat().st_mode | stat.S_IXUSR)
    return helper


def _run_chain(tmp_path: Path, exit_codes: dict[str, int]) -> tuple[int, list[tuple[str, str, str, str]]]:
    """Run the chain script with mocked wrapper + emit helper. Returns
    (exit_code, list of (name, status, payload, trace_id) emit calls)."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    capture = tmp_path / "emits.tsv"
    capture.write_text("")
    wrapper = _make_wrapper(tmp_path, exit_codes)
    helper = _make_emit_helper(tmp_path, capture)

    env = os.environ.copy()
    env["WR2_WRAPPER"] = str(wrapper)
    env["WR2_LOG_DIR"] = str(log_dir)
    env["OBSERVED_SHELL_HELPER"] = str(helper)

    result = subprocess.run(
        ["/bin/bash", str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    emits: list[tuple[str, str, str, str]] = []
    for line in capture.read_text().splitlines():
        if not line:
            continue
        parts = line.split("\t")
        # Pad to 4 in case trace_id is empty (it shouldn't be in our chain)
        while len(parts) < 4:
            parts.append("")
        emits.append((parts[0], parts[1], parts[2], parts[3]))

    return result.returncode, emits


def test_all_clis_ok_emits_ok_status():
    """When every CLI exits 0, all 3 per-CLI emits + 1 aggregate emit are 'ok'."""
    with pytest.MonkeyPatch.context() as mp:
        # Use a fresh tmpdir to avoid env var pollution
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            exit_code, emits = _run_chain(
                Path(td),
                {
                    "backend.services.hardening.missed_runs_cli": 0,
                    "backend.services.hardening.token_watchdog_cli": 0,
                    "backend.services.hardening.quota_cli": 0,
                },
            )
    assert exit_code == 0
    assert len(emits) == 4, f"expected 3 per-CLI + 1 aggregate, got {len(emits)}: {emits}"
    statuses = [e[1] for e in emits]
    assert statuses == ["ok", "ok", "ok", "ok"]
    # Last emit is the aggregate
    assert emits[-1][0] == "wr2.hardening.run"
    # Per-CLI emits use wr2.hardening.<short>
    per_cli_names = {e[0] for e in emits[:-1]}
    assert per_cli_names == {
        "wr2.hardening.missed_runs_cli",
        "wr2.hardening.token_watchdog_cli",
        "wr2.hardening.quota_cli",
    }


def test_one_cli_warning_aggregate_is_warning():
    """exit 1 from any CLI → that emit is 'warning'; aggregate carries max."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        exit_code, emits = _run_chain(
            Path(td),
            {
                "backend.services.hardening.missed_runs_cli": 0,
                "backend.services.hardening.token_watchdog_cli": 1,
                "backend.services.hardening.quota_cli": 0,
            },
        )
    assert exit_code == 1
    assert len(emits) == 4
    # Find the token_watchdog emit
    token_emit = next(e for e in emits if "token_watchdog" in e[0])
    assert token_emit[1] == "warning"
    # Aggregate carries max severity (warning, since max_exit=1)
    agg = emits[-1]
    assert agg[0] == "wr2.hardening.run"
    assert agg[1] == "warning"


def test_one_cli_error_aggregate_is_error():
    """exit >=2 → status='error'; aggregate carries max."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        exit_code, emits = _run_chain(
            Path(td),
            {
                "backend.services.hardening.missed_runs_cli": 2,
                "backend.services.hardening.token_watchdog_cli": 0,
                "backend.services.hardening.quota_cli": 0,
            },
        )
    assert exit_code == 2
    miss_emit = next(e for e in emits if "missed_runs" in e[0])
    assert miss_emit[1] == "error"
    agg = emits[-1]
    assert agg[1] == "error"


def test_aggregate_payload_carries_sub_run_count_and_max_exit():
    """The aggregate emit payload must include sub_run_count=3 and max_exit."""
    import json
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        _, emits = _run_chain(
            Path(td),
            {
                "backend.services.hardening.missed_runs_cli": 0,
                "backend.services.hardening.token_watchdog_cli": 1,
                "backend.services.hardening.quota_cli": 2,
            },
        )
    agg = emits[-1]
    payload = json.loads(agg[2])
    assert payload["sub_run_count"] == 3
    assert payload["max_exit"] == 2


def test_trace_id_shared_across_emits_in_one_run():
    """Per-CLI emits + aggregate emit MUST share the same trace_id so
    consumers can join the rows in observed_shell_events."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        _, emits = _run_chain(
            Path(td),
            {
                "backend.services.hardening.missed_runs_cli": 0,
                "backend.services.hardening.token_watchdog_cli": 0,
                "backend.services.hardening.quota_cli": 0,
            },
        )
    trace_ids = {e[3] for e in emits}
    assert len(trace_ids) == 1, f"trace_id must be constant per run, got {trace_ids}"
    # Trace ID must be non-empty
    assert all(tid for tid in trace_ids)


def test_per_cli_payload_includes_module_exit_code_log_path():
    """Per-CLI payload must carry module / exit_code / log_path so dashboards
    can deep-link to the JSON-line log file."""
    import json
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        _, emits = _run_chain(
            Path(td),
            {
                "backend.services.hardening.missed_runs_cli": 0,
                "backend.services.hardening.token_watchdog_cli": 0,
                "backend.services.hardening.quota_cli": 0,
            },
        )
    miss_emit = next(e for e in emits if "missed_runs" in e[0])
    payload = json.loads(miss_emit[2])
    assert payload["module"] == "backend.services.hardening.missed_runs_cli"
    assert payload["exit_code"] == 0
    assert payload["log_path"].endswith("hardening-missed_runs_cli.log")


def test_chain_continues_through_failures():
    """A non-zero exit on the FIRST CLI must NOT abort subsequent CLIs.
    All 3 CLIs always run; the chain reports max exit at the end."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        exit_code, emits = _run_chain(
            Path(td),
            {
                "backend.services.hardening.missed_runs_cli": 2,
                "backend.services.hardening.token_watchdog_cli": 1,
                "backend.services.hardening.quota_cli": 0,
            },
        )
    # All 3 CLIs ran
    per_cli = [e for e in emits if e[0] != "wr2.hardening.run"]
    assert len(per_cli) == 3
    # Quota was the last and got an emit even though missed_runs and token_watchdog
    # had failures earlier
    quota_emit = next(e for e in emits if "quota" in e[0])
    assert quota_emit[1] == "ok"
    # Max exit propagates
    assert exit_code == 2


def test_helper_missing_does_not_break_chain():
    """If OBSERVED_SHELL_HELPER points to a non-existent file, the script
    must still complete (best-effort observability invariant). The internal
    fallback defines observed_shell_emit as a no-op."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        log_dir = Path(td) / "logs"
        log_dir.mkdir()
        wrapper = _make_wrapper(
            Path(td),
            {
                "backend.services.hardening.missed_runs_cli": 0,
                "backend.services.hardening.token_watchdog_cli": 0,
                "backend.services.hardening.quota_cli": 0,
            },
        )
        env = os.environ.copy()
        env["WR2_WRAPPER"] = str(wrapper)
        env["WR2_LOG_DIR"] = str(log_dir)
        env["OBSERVED_SHELL_HELPER"] = str(Path(td) / "nonexistent.sh")

        result = subprocess.run(
            ["/bin/bash", str(SCRIPT)],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    assert result.returncode == 0, (
        f"chain must succeed when helper is missing — stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
