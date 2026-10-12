import json
import socket
import ssl
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cert_monitor as monitor  # noqa: E402


NOW = ssl.cert_time_to_seconds("Jan 01 00:00:00 2030 GMT")


def certificate(days: int, issuer: str = "Test CA") -> dict:
    stamp = NOW + days * 86400
    not_after = __import__("datetime").datetime.fromtimestamp(
        stamp, __import__("datetime").timezone.utc
    ).strftime("%b %d %H:%M:%S %Y GMT")
    return {"notAfter": not_after, "issuer": ((('commonName', issuer),),)}


def test_parsing_threshold_and_issuer() -> None:
    cert = certificate(30, "Issuer CN")
    assert monitor.days_until_expiry(cert, NOW) == 30
    assert monitor.issuer_common_name(cert) == "Issuer CN"
    assert monitor.classify(30) == "ok"
    assert monitor.classify(29) == "expiring"


@pytest.mark.parametrize(
    ("effect", "status"),
    [
        (certificate(29), "expiring"),
        (socket.timeout("late"), "unreachable"),
        (ssl.SSLCertVerificationError(1, "bad chain"), "verify_failed"),
        ({"issuer": ()}, "parse_error"),
    ],
)
def test_status_classification_without_network(monkeypatch, effect, status) -> None:
    def fake_fetch(_host, _port):
        if isinstance(effect, BaseException):
            raise effect
        return effect

    monkeypatch.setattr(monitor, "fetch_certificate", fake_fetch)
    summary, rc = monitor.run_checks(("example.invalid",), now_epoch=NOW)
    assert rc == 1
    assert summary["results"][0]["status"] == status


def test_exit_codes_and_single_json_line(monkeypatch, capsys) -> None:
    monkeypatch.setattr(monitor, "HOSTS", ("one.invalid",))
    monkeypatch.setattr(monitor.time, "time", lambda: NOW)
    monkeypatch.setattr(monitor, "fetch_certificate", lambda _h, _p: certificate(45))
    assert monitor.main([]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 1

    monkeypatch.setattr(monitor, "fetch_certificate", lambda _h, _p: certificate(2))
    assert monitor.main([]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["results"][0]["status"] == "expiring"

    with pytest.raises(SystemExit) as exc:
        monitor.main(["--unknown"])
    assert exc.value.code == 2


def test_self_test_is_offline(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        monitor, "fetch_certificate", lambda *_args: pytest.fail("network fetch attempted")
    )
    assert monitor.main(["--self-test"]) == 0
    assert capsys.readouterr().out.strip() == "self-test ok"
