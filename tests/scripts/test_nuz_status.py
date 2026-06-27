from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "nuz_status",
    ROOT / "scripts" / "nuz_status.py",
)
assert SPEC is not None
assert SPEC.loader is not None
nuz_status = importlib.util.module_from_spec(SPEC)
sys.modules["nuz_status"] = nuz_status
SPEC.loader.exec_module(nuz_status)


def test_machine_role_air_m5_for_balizero() -> None:
    assert nuz_status.machine_role("Air-M5", "balizero") == "Air-M5"


def test_http_json_handles_error_without_raising() -> None:
    with patch("nuz_status.urllib.request.urlopen", side_effect=OSError("offline")):
        result = nuz_status.http_json("https://example.invalid")

    assert result["ok"] is False
    assert "offline" in result["error"]


def test_http_json_falls_back_to_curl_on_python_ca_error() -> None:
    with (
        patch(
            "nuz_status.urllib.request.urlopen",
            side_effect=OSError("CERTIFICATE_VERIFY_FAILED"),
        ),
        patch(
            "nuz_status.run_command",
            return_value=nuz_status.CommandResult(0, '{"status":"healthy"}\n200', ""),
        ) as run_command,
    ):
        result = nuz_status.http_json("https://example.invalid")

    assert result == {
        "ok": True,
        "status_code": 200,
        "body": {"status": "healthy"},
    }
    run_command.assert_called_once()


def test_collect_status_marks_drive_401_without_key_as_warning() -> None:
    args = Namespace(
        refresh=False,
        offline=False,
        peer="pro",
        fly_health_url="https://example.invalid/health",
        drive_status_url="https://example.invalid/drive",
    )

    def fake_http_json(url: str, **_kwargs: object) -> dict[str, object]:
        if url.endswith("/health"):
            return {"ok": True, "status_code": 200, "body": {"status": "healthy"}}
        return {"ok": False, "status_code": 401, "error": {"detail": "Authentication required"}}

    with (
        patch("nuz_status.repo_root", return_value=Path.cwd()),
        patch(
            "nuz_status.git_status",
            return_value={
                "branch": "main",
                "head": "abc123",
                "origin_main": "abc123",
                "ahead": 0,
                "behind": 0,
                "dirty": False,
                "dirty_count": 0,
                "dirty_preview": [],
            },
        ),
        patch("nuz_status.peer_git_status", return_value={"reachable": True, "branch": "main"}),
        patch("nuz_status.gh_latest_run", return_value={"available": False}),
        patch("nuz_status.http_json", side_effect=fake_http_json),
        patch.dict("os.environ", {"NUZANTARA_API_KEY": ""}, clear=False),
    ):
        payload = nuz_status.collect_status(args)

    drive_check = next(check for check in payload["checks"] if check["id"] == "drive_worker")
    assert drive_check["status"] == "warn"
    assert "NUZANTARA_API_KEY" in drive_check["summary"]


def test_collect_status_offline_skips_network() -> None:
    args = Namespace(
        refresh=False,
        offline=True,
        peer="pro",
        fly_health_url="https://example.invalid/health",
        drive_status_url="https://example.invalid/drive",
    )
    with (
        patch("nuz_status.repo_root", return_value=Path.cwd()),
        patch(
            "nuz_status.git_status",
            return_value={
                "branch": "main",
                "head": "abc123",
                "origin_main": "abc123",
                "ahead": 0,
                "behind": 0,
                "dirty": False,
                "dirty_count": 0,
                "dirty_preview": [],
            },
        ),
        patch("nuz_status.peer_git_status") as peer_git,
        patch("nuz_status.http_json") as http_json,
    ):
        payload = nuz_status.collect_status(args)

    assert payload["overall"] == "unknown"
    assert {check["id"] for check in payload["checks"]} >= {
        "git_local",
        "git_peer",
        "fly_health",
        "drive_worker",
    }
    peer_git.assert_not_called()
    http_json.assert_not_called()
