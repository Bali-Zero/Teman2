"""Tests per scripts/wa_session_liveness.py.

Ogni cosa che questo organo afferma deve avere il suo test di COLPEVOLEZZA e
il suo test di INNOCENZA: un guardiano senza il secondo e un allarme che urla,
uno senza il primo e un allarme decorativo. Piu una terza famiglia che qui e
la piu importante: **non-ho-potuto-guardare non e "va tutto bene"**.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest

_MODULE_PATH = Path(__file__).parents[1] / "wa_session_liveness.py"
NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("wa_session_liveness", _MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


wa = _load()


# --------------------------------------------------------------------- classify


def test_guilt_a_line_silent_past_the_threshold_is_stale() -> None:
    """Il caso vero: vino, ferma 10 giorni, che nessuno aveva visto."""
    status = wa.classify("vino", NOW - timedelta(days=10), NOW)
    assert status.status == wa.STALE
    assert status.hours_silent == pytest.approx(240.0)


def test_innocence_a_line_quiet_over_a_weekend_is_not_stale() -> None:
    """48h di silenzio esiste in natura: misurato sui 60 giorni precedenti.

    Senza questo test la soglia potrebbe scendere a 24h e l'organo urlerebbe
    ogni lunedi, che e il modo piu rapido per non essere piu letto.
    """
    assert wa.classify("asya", NOW - timedelta(hours=47.5), NOW).status == wa.OK


def test_the_threshold_boundary_is_inclusive() -> None:
    assert wa.classify("x", NOW - timedelta(hours=72), NOW).status == wa.STALE
    assert wa.classify("x", NOW - timedelta(hours=71.9), NOW).status == wa.OK


def test_a_line_that_never_mirrored_anything_is_stale_not_ok() -> None:
    """Nessun dato non e salute: una sessione mai funzionante va vista."""
    status = wa.classify("nuovo", None, NOW)
    assert status.status == wa.STALE
    assert status.hours_silent is None


def test_the_threshold_is_configurable_and_actually_used() -> None:
    silent = NOW - timedelta(hours=50)
    assert wa.classify("x", silent, NOW, stale_hours=72).status == wa.OK
    assert wa.classify("x", silent, NOW, stale_hours=48).status == wa.STALE


# ------------------------------------------------------------------- boundary


def test_the_alert_never_contains_a_phone_number() -> None:
    """Law 2: un numero di telefono non entra in un messaggio Telegram."""
    stale = [wa.classify("ari", NOW - timedelta(days=8), NOW)]
    message = wa.format_alert(stale, "Nuzantara", 72)
    assert "ari" in message
    assert not any(chunk.isdigit() and len(chunk) > 8 for chunk in message.split())
    assert "628" not in message


def test_the_alert_says_the_pid_is_not_the_proof() -> None:
    """Il messaggio deve portare la lezione, non solo il fatto: chi lo legge
    andrebbe a guardare `ps` e lo troverebbe verde."""
    message = wa.format_alert([wa.classify("vino", None, NOW)], "Nuzantara", 72)
    assert "PID" in message
    assert "re-pair" in message


# --------------------------------------------------- CANNOT-VERIFY (la parte critica)


def test_missing_accounts_file_is_cannot_verify_not_clean(tmp_path: Path) -> None:
    with pytest.raises(wa.CannotVerify):
        wa.read_active_lines(tmp_path / "non-esiste.json")


def test_accounts_file_without_any_e164_is_cannot_verify(tmp_path: Path) -> None:
    """Zero linee sorvegliate NON e 'zero problemi' — e cecita (W84)."""
    path = tmp_path / "acc.json"
    path.write_text(json.dumps({"accounts": [{"name": "Ari"}]}))
    with pytest.raises(wa.CannotVerify):
        wa.read_active_lines(path)


def test_accounts_file_is_parsed_when_it_is_well_formed(tmp_path: Path) -> None:
    """INNOCENZA del test sopra: un file valido non deve alzare."""
    path = tmp_path / "acc.json"
    path.write_text(json.dumps({"accounts": [{"name": "Ari", "e164": "+628213454721"}]}))
    assert wa.read_active_lines(path) == {"Ari": "628213454721"}


def test_missing_dsn_is_cannot_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(wa.DSN_VAR, raising=False)
    empty = tmp_path / "secrets.env"
    empty.write_text("ALTRA_COSA=1\n")
    with pytest.raises(wa.CannotVerify):
        wa.read_dsn(empty)


def test_dsn_is_read_when_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(wa.DSN_VAR, raising=False)
    path = tmp_path / "secrets.env"
    path.write_text(f'ALTRA=1\n{wa.DSN_VAR}="postgres://u@127.0.0.1/db"\n')
    assert wa.read_dsn(path) == "postgres://u@127.0.0.1/db"


def test_main_exits_2_and_says_so_when_it_could_not_look(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Il ramo piu importante: un DB irraggiungibile NON deve stampare 7 linee
    verdi. Questo e il difetto che ha lasciato due sessioni morte per giorni.
    """
    def boom(_hours):
        raise wa.CannotVerify("query mirror fallita (ConnectionError)")

    monkeypatch.setattr(wa, "run", boom)
    rc = main_rc = wa.main(["--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == wa.EXIT_CANNOT_VERIFY == 2
    assert payload["lines"] == []
    assert "cannot_verify" in payload
    assert main_rc != wa.EXIT_OK


def test_main_exits_0_when_it_could_look(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """INNOCENZA del test sopra, stesso meccanismo: senza questo, un `run` che
    alza SEMPRE farebbe passare il test di sopra per la ragione sbagliata."""
    monkeypatch.setattr(
        wa, "run", lambda _h: [wa.classify("ari", NOW, NOW)]
    )
    rc = wa.main(["--json", "--no-alert"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == wa.EXIT_OK
    assert payload["stale"] == 0
    assert len(payload["lines"]) == 1


def test_stale_lines_still_exit_0_because_the_verdict_travels_by_alert(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Un cron chiamante non deve fallire perche una linea e ferma: il 2 resta
    riservato al non-ho-visto, altrimenti i due casi diventano indistinguibili."""
    monkeypatch.setattr(
        wa, "run", lambda _h: [wa.classify("vino", NOW - timedelta(days=10), NOW)]
    )
    rc = wa.main(["--json", "--no-alert"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == wa.EXIT_OK
    assert payload["stale"] == 1


def test_cannot_verify_rings_the_alarm_itself(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Il 2 lo legge cron-runner e allarma — ma solo finche il chiamante e lui.
    Un organo che per farsi sentire dipende da CHI lo invoca e muto appena lo
    sposti su un plist, senza che una riga del suo codice cambi.
    """
    sent: list[str] = []
    monkeypatch.setattr(wa, "send_to_gateway",
                        lambda msg, host, dedup_suffix="": sent.append(msg) or True)
    monkeypatch.setattr(wa, "run", lambda _h: (_ for _ in ()).throw(
        wa.CannotVerify("query mirror fallita (ConnectionError)")))

    assert wa.main([]) == wa.EXIT_CANNOT_VERIFY
    capsys.readouterr()
    assert len(sent) == 1
    assert "CANNOT-VERIFY" in sent[0]
    assert "NON e un verdetto di salute" in sent[0]


def test_a_healthy_run_never_rings_the_blind_alarm(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """INNOCENZA del test sopra, stesso meccanismo: senza questa, un
    emit_blind_alert cablato a sparare sempre passerebbe il test di sopra.
    """
    sent: list[str] = []
    monkeypatch.setattr(wa, "send_to_gateway",
                        lambda msg, host, dedup_suffix="": sent.append(msg) or True)
    monkeypatch.setattr(wa, "run", lambda _h: [wa.classify("ari", NOW, NOW)])

    assert wa.main([]) == wa.EXIT_OK
    capsys.readouterr()
    assert sent == []


def test_no_alert_suppresses_the_blind_alarm_too(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """--no-alert e un dry-run: deve valere su ENTRAMBE le voci, non solo su
    quella che avevo in mente quando l'ho scritto."""
    sent: list[str] = []
    monkeypatch.setattr(wa, "send_to_gateway",
                        lambda msg, host, dedup_suffix="": sent.append(msg) or True)
    monkeypatch.setattr(wa, "run", lambda _h: (_ for _ in ()).throw(
        wa.CannotVerify("DSN assente")))

    assert wa.main(["--no-alert"]) == wa.EXIT_CANNOT_VERIFY
    capsys.readouterr()
    assert sent == []


def test_selftest_passes_on_a_healthy_organ(capsys: pytest.CaptureFixture) -> None:
    assert wa.selftest() == wa.EXIT_OK
    assert "OK" in capsys.readouterr().out
