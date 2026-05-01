import pytest
from cell_observatory.config import Config


def test_config_defaults(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-fake")
    monkeypatch.setenv("EVENTBUS_DATABASE_URL", "postgresql://x/y")
    cfg = Config.from_env()
    assert cfg.minimax_api_key == "sk-fake"
    assert cfg.api_port == 17891
    assert cfg.cost_alert_threshold_usd == 1.0  # M6 default
    assert cfg.retention_days == 90
    assert cfg.classifier_max_inflight == 50
    assert cfg.classifier_queue_maxsize == 10000  # G1 fix


def test_config_overrides(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-fake")
    monkeypatch.setenv("EVENTBUS_DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("OBSERVATORY_COST_ALERT_THRESHOLD_USD", "5.0")
    monkeypatch.setenv("OBSERVATORY_API_PORT", "17892")
    cfg = Config.from_env()
    assert cfg.cost_alert_threshold_usd == 5.0
    assert cfg.api_port == 17892


def test_config_required_keys_missing(monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("EVENTBUS_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="MINIMAX_API_KEY"):
        Config.from_env()
