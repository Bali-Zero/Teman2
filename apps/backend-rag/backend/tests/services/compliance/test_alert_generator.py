import pytest

from backend.services.compliance.alert_generator import AlertGeneratorService, AlertStatus


def test_alert_status_keeps_backward_compatible_values() -> None:
    assert AlertStatus.PENDING == "pending"
    assert AlertStatus.SENT == "sent"
    assert AlertStatus.ACKNOWLEDGED == "acknowledged"
    assert AlertStatus.RESOLVED == "resolved"
    assert AlertStatus.EXPIRED == "expired"


def test_deprecated_alert_generator_returns_safe_defaults() -> None:
    with pytest.warns(DeprecationWarning, match="AlertGeneratorService is deprecated"):
        service = AlertGeneratorService()

    assert service.alerts == {}

    with pytest.warns(DeprecationWarning, match="generate_alert is a deprecated no-op"):
        assert service.generate_alert(client_id="client-1") is None
    with pytest.warns(DeprecationWarning, match="find_existing_alert is a deprecated no-op"):
        assert service.find_existing_alert(client_id="client-1") is None
    with pytest.warns(DeprecationWarning, match="get_alerts_for_client is a deprecated no-op"):
        assert service.get_alerts_for_client("client-1") == []
    with pytest.warns(DeprecationWarning, match="acknowledge_alert is a deprecated no-op"):
        assert service.acknowledge_alert("alert-1") is False
    with pytest.warns(DeprecationWarning, match="mark_alert_sent is a deprecated no-op"):
        assert service.mark_alert_sent("alert-1") is False

    assert service.get_stats() == {}
