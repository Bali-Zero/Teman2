import importlib.util
import json
import sys
from pathlib import Path

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
