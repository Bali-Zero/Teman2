import importlib.util
import json
import sys
from pathlib import Path
from subprocess import CompletedProcess

import pytest

_MOD_PATH = Path(__file__).resolve().parents[1] / "expiry_alerter.py"
_spec = importlib.util.spec_from_file_location("expiry_alerter", _MOD_PATH)
expiry = importlib.util.module_from_spec(_spec)
sys.modules["expiry_alerter"] = expiry
_spec.loader.exec_module(expiry)


def _heartbeat_path(home: Path) -> Path:
    return home / ".agent" / "decisions" / "state" / "expiry_alerter.last.json"


def _read_heartbeat(home: Path) -> dict:
    return json.loads(_heartbeat_path(home).read_text())


def test_main_writes_heartbeat_when_no_expiries(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["expiry_alerter.py"])
    monkeypatch.setattr(expiry, "_load_env", lambda: {})
    monkeypatch.setattr(expiry, "_query_expiries", lambda: [])

    expiry.main()

    assert "No expiries found." in capsys.readouterr().out
    heartbeat = _read_heartbeat(tmp_path)
    assert heartbeat["job"] == "expiry_alerter"
    assert heartbeat["status"] == "ok"
    assert heartbeat["host"]
    assert isinstance(heartbeat["ts"], int)


def test_main_writes_heartbeat_when_no_items_are_urgent(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["expiry_alerter.py"])
    monkeypatch.setattr(expiry, "_load_env", lambda: {})
    monkeypatch.setattr(
        expiry,
        "_query_expiries",
        lambda: [
            {
                "client_id": 1,
                "full_name": "Test Client",
                "assigned_to": "ops@example.com",
                "exp_type": "practice",
                "expiry_date": "2030-01-01",
                "passport_expiry": None,
            }
        ],
    )

    expiry.main()

    assert "No urgent expiries." in capsys.readouterr().out
    heartbeat = _read_heartbeat(tmp_path)
    assert heartbeat["job"] == "expiry_alerter"
    assert heartbeat["status"] == "ok"


def test_main_fails_closed_when_query_fails(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["expiry_alerter.py"])
    monkeypatch.setattr(expiry, "_load_env", lambda: {})

    def fail_query() -> list[dict]:
        raise expiry.ExpiryAlerterError("Query failed: auth denied")

    monkeypatch.setattr(expiry, "_query_expiries", fail_query)

    with pytest.raises(SystemExit) as exc_info:
        expiry.main()

    assert exc_info.value.code == 1
    assert "Expiry alerter failed: Query failed: auth denied" in capsys.readouterr().err
    heartbeat = _read_heartbeat(tmp_path)
    assert heartbeat["job"] == "expiry_alerter"
    assert heartbeat["status"] == "failed"


def test_run_fly_console_python_uses_local_shell_on_pro(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(expiry, "SSH_HOST", "pro")
    monkeypatch.setattr(expiry.socket, "gethostname", lambda: "Nuzantara")
    monkeypatch.setattr(expiry.socket, "getfqdn", lambda: "Nuzantara.local")

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return CompletedProcess(cmd, 0, stdout="[]", stderr="")

    monkeypatch.setattr(expiry.subprocess, "run", fake_run)

    result = expiry._run_fly_console_python("abc", timeout_s=7)

    assert result.returncode == 0
    assert calls[0][0][0] == "fly"
    assert "ssh" in calls[0][0]
    assert calls[0][1]["timeout"] == 7
