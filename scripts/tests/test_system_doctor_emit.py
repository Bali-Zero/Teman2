import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Ensure apps/organism is importable
sys.path.insert(0, str(Path(__file__).parents[2] / "apps" / "organism"))
sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))


@pytest.mark.asyncio
async def test_scan_cron_agent_logs_emits_on_error(tmp_path, monkeypatch):
    """Broken cron-agent log with ERROR line must emit cron_agent_failure event."""
    import importlib.util
    import sys as _sys

    _SYSTEM_DOCTOR = Path(__file__).parents[1] / "system_doctor.py"
    spec = importlib.util.spec_from_file_location("system_doctor", _SYSTEM_DOCTOR)
    assert spec and spec.loader
    sd = importlib.util.module_from_spec(spec)
    _sys.modules["system_doctor"] = sd
    spec.loader.exec_module(sd)

    log_dir = tmp_path / "cron-agent"
    log_dir.mkdir()
    (log_dir / "core-guardian.log").write_text("[2026-04-22] ERROR script not found\n")
    monkeypatch.setattr(sd, "CRON_AGENT_LOG_DIRS", [log_dir])

    findings = await sd._scan_cron_agent_logs()
    assert len(findings) >= 1
    assert findings[0]["agent"] == "core-guardian"
    assert "ERROR" in findings[0]["line"]
    assert str(log_dir) in findings[0]["log_path"]


@pytest.mark.asyncio
async def test_scan_cron_agent_logs_ignores_clean_logs(tmp_path, monkeypatch):
    """Clean log (no ERROR, no exit-code) returns empty findings."""
    import importlib.util
    import sys as _sys

    _SYSTEM_DOCTOR = Path(__file__).parents[1] / "system_doctor.py"
    spec = importlib.util.spec_from_file_location("system_doctor_clean", _SYSTEM_DOCTOR)
    assert spec and spec.loader
    sd = importlib.util.module_from_spec(spec)
    _sys.modules["system_doctor_clean"] = sd
    spec.loader.exec_module(sd)

    log_dir = tmp_path / "cron-agent"
    log_dir.mkdir()
    (log_dir / "happy.log").write_text("[2026-04-22] Starting...\n[2026-04-22] Done.\n")
    monkeypatch.setattr(sd, "CRON_AGENT_LOG_DIRS", [log_dir])

    findings = await sd._scan_cron_agent_logs()
    assert findings == []
