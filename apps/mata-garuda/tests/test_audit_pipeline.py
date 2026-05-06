"""Tests for the live audit pipeline — drift detection + T2.a/b/c failure tolerance."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Lazy-import inside tests to avoid loading subprocess at collection time.
def _import():
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import audit_nb_live  # type: ignore[import-not-found]
    return audit_nb_live


def test_drift_detection_consistent():
    mod = _import()
    assert mod.classify_drift(snapshot=10, live=10) == "consistent"
    assert mod.classify_drift(snapshot=10, live=11) == "consistent"  # ±1
    assert mod.classify_drift(snapshot=10, live=9)  == "consistent"


def test_drift_detection_drifted():
    mod = _import()
    assert mod.classify_drift(snapshot=10, live=20) == "drifted"
    assert mod.classify_drift(snapshot=10, live=4)  == "drifted"


def test_drift_detection_unknown():
    mod = _import()
    assert mod.classify_drift(snapshot=10, live=None) == "unknown_via_mcp_failure"


def test_t2a_cookie_refresh_proactive():
    mod = _import()
    with patch.object(mod, "_run", return_value=("", 1, "AUTH FAIL")) as run_mock:
        # First call simulates `nlm whoami` failing; helper must follow up
        # with `nlm login --clear`.
        mod.ensure_session_or_relogin()
    invocations = [args for (args, _) in run_mock.call_args_list]
    cmds = ["".join(a[0]) if isinstance(a[0], list) else a[0] for a in invocations]
    joined = " ".join(c if isinstance(c, str) else " ".join(c) for c in cmds)
    assert "login" in joined and "--clear" in joined


def test_t2b_retry_with_backoff():
    mod = _import()
    calls = {"n": 0}

    def fake_query(uuid):
        calls["n"] += 1
        if calls["n"] == 1:
            raise mod.TransientMCPError("timeout")
        return {"source_count": 7, "title": "ok"}

    with patch.object(mod, "time", MagicMock()) as time_mock, \
         patch.object(mod, "mcp_query_notebook", side_effect=fake_query):
        result = mod.audit_one_with_retry("dc5d01cd-e99f-4c8f-aae4-75060b43d0de")
    assert result["source_count"] == 7
    assert calls["n"] == 2
    time_mock.sleep.assert_called_with(5)  # 5s backoff


def test_t2c_hard_cap_aborts_phase():
    mod = _import()
    # 9 of 17 fail (>50%) — must exit 2 + telegram alert.
    fails = [True] * 9 + [False] * 8
    with patch.object(mod, "telegram_alert") as tg, \
         pytest.raises(SystemExit) as ex:
        mod.enforce_hard_cap(failures=sum(fails), total=len(fails), threshold_pct=50)
    assert ex.value.code == 2
    tg.assert_called_once()


def test_audit_log_append_only(tmp_path, monkeypatch):
    mod = _import()
    log = tmp_path / "audit_log.md"
    mod.append_audit_log(log, "uuid-1", "AUDITED", note="ok")
    mod.append_audit_log(log, "uuid-2", "AUDITED", note="ok")
    content = log.read_text()
    # First entry must precede second by line order.
    pos1 = content.index("uuid-1")
    pos2 = content.index("uuid-2")
    assert pos1 < pos2
    assert content.count("AUDITED") == 2
