#!/usr/bin/env python3
"""Path confinement for the wa-mirror control API.

Runs the REAL handlers (not a re-implementation of their logic) against a
temporary roster and log directory. Guilt: a traversal name, an absolute path,
a case/whitespace variant and a sibling directory must not open a file outside
the log dir. Innocence: a legitimate roster name still gets its own log.

The defect this pins: `/api/accounts/{name}/logs` DID refuse unknown names, and
then built the path from the *request* string anyway — so the check refused, but
it sanitised nothing. CodeQL called it `py/path-injection` seven times over.

    python3 -m pytest apps/wa-mirror/scripts/test_api_server_path_confinement.py -q
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def _load_module(tmp_path: Path):
    """Import api_server with its environment pointed at a scratch world."""
    os.environ.setdefault("WA_LAUNCHER_DB_DSN", "postgresql://unused/unused")
    os.environ["HOME"] = str(tmp_path)
    os.environ["WA_MIRROR_DIR"] = str(tmp_path / "wa-mirror")

    spec = importlib.util.spec_from_file_location(
        "wa_api_server_under_test", HERE / "api_server.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def api(tmp_path):
    mod = _load_module(tmp_path)

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    mod.LOG_DIR = log_dir
    mod.PID_DIR = tmp_path / "pids"
    mod.PID_DIR.mkdir()

    roster = tmp_path / ".wa-mirror.accounts.json"
    roster.write_text(
        json.dumps({"accounts": [{"name": "Ari", "e164": "+620000000001"}]})
    )
    mod.ACCOUNTS_JSON = roster

    (log_dir / "ari.log").write_text("legitimate line\n")

    # The file a traversal is trying to reach, one level above the log dir.
    (tmp_path / "secret.log").write_text("SHOULD NEVER BE SERVED\n")
    return mod


# ── guilt ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "hostile",
    [
        "../secret",
        "../../etc/passwd",
        "/etc/passwd",
        "ari/../../secret",
        "....//secret",
        "ari\x00../secret",
    ],
)
def test_hostile_names_are_refused_and_serve_nothing(api, hostile):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        api.get_logs(name=hostile, lines=10)
    assert excinfo.value.status_code == 404


def test_refusal_does_not_echo_the_caller_string(api):
    """The 404 body must not reflect unsanitised input back to the browser."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        api.get_logs(name="<img src=x onerror=alert(1)>", lines=10)
    assert "<img" not in str(excinfo.value.detail)


def test_a_name_absent_from_the_roster_is_refused(api):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        api.get_logs(name="mallory", lines=10)
    assert excinfo.value.status_code == 404


# ── innocence ────────────────────────────────────────────────────────────────
def test_a_roster_name_still_gets_its_log(api):
    out = api.get_logs(name="ari", lines=10)
    assert out["status"] == "success"
    assert out["lines"] == ["legitimate line"]


def test_case_and_whitespace_variants_of_a_roster_name_work(api):
    for variant in ("Ari", "  ARI  ", "aRi"):
        out = api.get_logs(name=variant, lines=10)
        assert out["lines"] == ["legitimate line"], variant


def test_missing_log_file_is_a_message_not_an_error(api):
    (api.LOG_DIR / "ari.log").unlink()
    out = api.get_logs(name="ari", lines=10)
    assert out["status"] == "success"
    assert "No log file found" in out["lines"][0]


# ── the property itself ──────────────────────────────────────────────────────
def test_roster_account_returns_the_roster_record_not_the_caller_string(api):
    """The fix is that the path is built from what this RETURNS."""
    assert api.roster_account("  ARI ")["name"] == "Ari"
    assert api.roster_account("../secret") is None
    assert api.roster_account("") is None
    assert api.roster_stem({"name": " Ari "}) == "ari"


def test_log_path_is_always_directly_inside_the_log_dir(api):
    acc = api.roster_account("ari")
    path = api.LOG_DIR / f"{api.roster_stem(acc)}.log"
    assert path.resolve().parent == api.LOG_DIR.resolve()
