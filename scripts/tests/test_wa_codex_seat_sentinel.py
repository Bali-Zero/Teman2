"""Tests per scripts/wa_codex_seat_sentinel.py.

Ogni cosa che questo organo afferma deve avere il suo test di COLPEVOLEZZA e
il suo test di INNOCENZA: un guardiano senza il secondo e un allarme che
urla, uno senza il primo e un allarme decorativo. Una terza famiglia qui e
la piu importante: **il gauge non-letto non e "va tutto bene"** — un
`gauge_row=None` deve fermare la CLI a 2, mai passare per un run pulito.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest

_MODULE_PATH = Path(__file__).parents[1] / "wa_codex_seat_sentinel.py"
_PROBE_MODULE_PATH = Path(__file__).parents[1] / "wa_codex_seat_probe.py"
NOW = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("wa_codex_seat_sentinel", _MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_probe() -> ModuleType:
    """Loaded under a name distinct from both `wa_codex_seat_probe.py`'s
    own test file (`wa_codex_seat_probe`) and the dotted
    `scripts.wa_codex_seat_probe` the sentinel module imports internally
    — an independent module object, purely so this test can assert the
    sentinel's imported constants EQUAL the probe's own, not merely that
    they are the same Python object by import-caching accident."""
    spec = importlib.util.spec_from_file_location(
        "wa_codex_seat_probe_coupling_check", _PROBE_MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


wa = _load()
probe = _load_probe()


def _gauge(
    breaker_state: str = "closed",
    consecutive_failures: int = 0,
    staleness_s: float = 60.0,
) -> tuple[str, str, int, float]:
    return ("2026-08-20T11:59:00+00:00", breaker_state, consecutive_failures, staleness_s)


def _probe(verdict: str = "ok", login_rc: int = 0, exec_rc: int = 0) -> dict:
    return {
        "checked_at": "2026-08-20T11:59:50Z",
        "verdict": verdict,
        "login_status_rc": login_rc,
        "exec_rc": exec_rc,
    }


# --------------------------------------------------------------------- GUILT


def test_guilt_auth_death_is_red_with_the_relogin_command() -> None:
    verdicts = wa.evaluate(_probe("auth_death", 1, 1), 10.0, _gauge(), NOW)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.level == wa.RED
    assert v.condition == "auth_death"
    assert "codex login" in v.message
    assert "sudo -u zantara-codex" in v.message


def test_guilt_quota_exhausted_is_red_and_distinct_from_auth_death() -> None:
    """S1.5 (2026-08-26), owner packet item 13: the probe's new
    `quota_exhausted` verdict must reach the same severity as `auth_death`
    (the OpenAI/Codex leg is fully blocked either way) but through its own
    condition and its own message — never collapsed into `auth_death`'s
    dedup key or its re-login wording, which is actively WRONG advice for
    a quota-exhausted seat."""
    verdicts = wa.evaluate(_probe("quota_exhausted", 0, 1), 10.0, _gauge(), NOW)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.level == wa.RED
    assert v.condition == "quota_exhausted"
    assert v.condition != "auth_death"
    assert "QUOTA EXHAUSTED" in v.message
    assert "codex login" not in v.message
    assert "do not re-login" in v.message


def test_guilt_quota_exhausted_message_names_wait_or_switch_not_relogin() -> None:
    """The remedy is the whole point of distinguishing this verdict: waiting
    for the usage window or switching seats, never `codex login` (that IS
    the auth_death remedy, and applying it to a healthy-but-quota-exhausted
    seat wastes an operator's time chasing the wrong fix)."""
    verdicts = wa.evaluate(_probe("quota_exhausted", 0, 1), 10.0, _gauge(), NOW)
    assert "wait" in verdicts[0].message.lower() or "switch" in verdicts[0].message.lower()


def test_guilt_probe_module_verdict_constants_still_drive_red() -> None:
    """Round-4 addendum (team-lead review of PR #5028, 2026-08-26): the
    writer (scripts/wa_codex_seat_probe.py) emits `verdict` via named
    `Final[str]` constants; this reader used to compare against bare
    string literals — a rename on the write side would have silently
    stopped matching (RED degrades to WARN, zero visible signal). The
    sentinel module now imports the SAME constants
    (`from scripts.wa_codex_seat_probe import VERDICT_AUTH_DEATH,
    VERDICT_OK, VERDICT_QUOTA_EXHAUSTED`) instead of hardcoding the
    strings, so this test feeds the PROBE's own constants — loaded as an
    independent module, not typed as literals here — through the
    sentinel's real `evaluate()` and asserts the RED classification
    still fires for both. This is the behavioral half of the fix; the
    import itself is the structural half (a rename now raises
    ImportError in this module rather than drifting silently)."""
    verdicts = wa.evaluate(_probe(probe.VERDICT_AUTH_DEATH, 1, 1), 10.0, _gauge(), NOW)
    assert len(verdicts) == 1
    assert verdicts[0].level == wa.RED
    assert verdicts[0].condition == probe.VERDICT_AUTH_DEATH

    verdicts = wa.evaluate(_probe(probe.VERDICT_QUOTA_EXHAUSTED, 0, 1), 10.0, _gauge(), NOW)
    assert len(verdicts) == 1
    assert verdicts[0].level == wa.RED
    assert verdicts[0].condition == probe.VERDICT_QUOTA_EXHAUSTED

    # And the healthy value produces no verdict at all — proves the
    # coupling isn't accidentally satisfied by a permissive `!=` on
    # every branch.
    verdicts = wa.evaluate(_probe(probe.VERDICT_OK, 0, 0), 10.0, _gauge(), NOW)
    assert verdicts == []

    # The sentinel module's OWN imported names must be the identical
    # values the probe module defines — not a re-typed guess that
    # happens to match today. If either side is ever renamed without
    # the other, this equality (or the import at module load) breaks.
    assert wa.VERDICT_AUTH_DEATH == probe.VERDICT_AUTH_DEATH
    assert wa.VERDICT_QUOTA_EXHAUSTED == probe.VERDICT_QUOTA_EXHAUSTED
    assert wa.VERDICT_OK == probe.VERDICT_OK


def test_guilt_missing_probe_file_is_red_naming_probe_silent() -> None:
    """`probe_status=None` — il caso "file assente": deve nominare la causa,
    non limitarsi a un generico 'qualcosa non va'."""
    verdicts = wa.evaluate(None, None, _gauge(), NOW)
    assert len(verdicts) == 1
    assert verdicts[0].level == wa.RED
    assert verdicts[0].condition == "probe_silent"
    assert "probe silent" in verdicts[0].message


def test_guilt_probe_age_past_2x_interval_is_red_probe_silent() -> None:
    """Un file PRESENTE ma vecchio di oltre 2x l'intervallo del probe conta
    come silenzio quanto un file assente — il probe potrebbe essere morto."""
    stale_age_s = 2 * wa.DEFAULT_PROBE_INTERVAL_S + 1
    verdicts = wa.evaluate(_probe(), stale_age_s, _gauge(), NOW)
    assert any(v.condition == "probe_silent" for v in verdicts)


def test_guilt_breaker_open_is_red_naming_the_sudo_grep_hint() -> None:
    verdicts = wa.evaluate(_probe(), 10.0, _gauge(breaker_state="open"), NOW)
    breaker = [v for v in verdicts if v.condition == "breaker_open"]
    assert len(breaker) == 1
    assert breaker[0].level == wa.RED
    assert "sudo grep 'AUTH DEATH'" in breaker[0].message
    assert "wa-codex-broker.err" in breaker[0].message


def test_guilt_three_consecutive_failures_with_closed_breaker_is_red() -> None:
    """Il breaker puo non essersi ancora aperto (soglia server-side diversa)
    ma 3 fallimenti di fila sono gia un segnale che questo organo non deve
    aspettare che il breaker confermi da solo."""
    verdicts = wa.evaluate(_probe(), 10.0, _gauge(consecutive_failures=3), NOW)
    assert any(v.condition == "breaker_open" for v in verdicts)


def test_guilt_gauge_staleness_700s_is_red_daemon_silent() -> None:
    verdicts = wa.evaluate(_probe(), 10.0, _gauge(staleness_s=700.0), NOW)
    silent = [v for v in verdicts if v.condition == "daemon_silent"]
    assert len(silent) == 1
    assert silent[0].level == wa.RED
    assert "daemon silent" in silent[0].message


def test_guilt_other_failure_verdict_is_warn_not_red() -> None:
    """`other_failure` e reale (il probe ha girato ed e fallito) ma NON e
    una morte d'autenticazione confermata: WARN, non RED."""
    verdicts = wa.evaluate(_probe("other_failure", 1, 0), 10.0, _gauge(), NOW)
    other = [v for v in verdicts if v.condition == "other_failure"]
    assert len(other) == 1
    assert other[0].level == wa.WARN
    assert "other_failure" in other[0].message


def test_guilt_unrecognized_probe_verdict_falls_visibly_as_warn_never_silent() -> None:
    """W116: un finale non mappato (un probe futuro che scrive p.es.
    "policy_blocked", non ancora conosciuto da questo reader) deve cadere
    VISIBILE, mai nel secchio sano.

    S1.5 (2026-08-26): "quota_exhausted" used to be THIS test's example of
    an unmapped verdict — it has since graduated to its own explicit branch
    (see test_guilt_quota_exhausted_is_red_and_distinct_from_auth_death)
    and no longer exercises this generic fallback path, so the example had
    to change or this test would silently stop testing the fallback at
    all and start testing the new specific branch instead — a genuinely
    unmapped token is required here to prove the FORWARD-compat contract:
    a status file from a probe newer than this sentinel (naming a verdict
    this reader has never heard of) must still degrade to a visible WARN,
    never to silence and never to a crash."""
    verdicts = wa.evaluate(_probe("policy_blocked", 0, 1), 10.0, _gauge(), NOW)
    assert len(verdicts) == 1
    assert verdicts[0].level == wa.WARN
    assert verdicts[0].condition == "other_failure"
    assert "policy_blocked" in verdicts[0].message


def test_innocence_quota_exhausted_no_longer_reaches_the_generic_fallback() -> None:
    """Companion to the test above: `quota_exhausted` must NOT also produce
    a second, generic `other_failure` verdict alongside its own — `evaluate`
    returns exactly one verdict for it, from the new explicit branch."""
    verdicts = wa.evaluate(_probe("quota_exhausted", 0, 1), 10.0, _gauge(), NOW)
    assert len(verdicts) == 1
    assert verdicts[0].condition == "quota_exhausted"


def test_guilt_never_seen_daemon_null_staleness_parses_to_daemon_silent() -> None:
    """broker_last_seen_at NULL (daemon mai visto) arriva da psql -A -t come
    campo VUOTO: il parser lo legge come staleness infinita (verdetto
    daemon_silent), mai come riga imparsabile (CANNOT-VERIFY) ne' come sana."""
    import subprocess as _sp

    fake = _sp.CompletedProcess(args=[], returncode=0, stdout="|closed|0|\n", stderr="")
    original_run = _sp.run
    try:
        _sp.run = lambda *a, **k: fake  # type: ignore[assignment]
        row = wa._read_gauge()
    finally:
        _sp.run = original_run
    assert row is not None
    assert row[3] == float("inf")
    verdicts = wa.evaluate(_probe(), 10.0, row, NOW)
    assert any(v.condition == "daemon_silent" for v in verdicts)


# ----------------------------------------------------------------- INNOCENCE


def test_innocence_fresh_ok_status_and_healthy_gauge_is_silent() -> None:
    assert wa.evaluate(_probe(), 10.0, _gauge(), NOW) == []


def test_innocence_two_consecutive_failures_with_closed_breaker_is_silent() -> None:
    assert wa.evaluate(_probe(), 10.0, _gauge(consecutive_failures=2), NOW) == []


def test_innocence_a_normal_poll_gap_after_restart_is_silent() -> None:
    """60s di silenzio dopo un riavvio e fisiologico — misurato contro il
    limite di 600s, non un valore a caso."""
    assert wa.evaluate(_probe(), 10.0, _gauge(staleness_s=60.0), NOW) == []


def test_innocence_probe_age_just_under_2x_interval_is_silent() -> None:
    just_fresh_s = 2 * wa.DEFAULT_PROBE_INTERVAL_S - 1
    verdicts = wa.evaluate(_probe(), just_fresh_s, _gauge(), NOW)
    assert verdicts == []


# --------------------------------------------------------- CANNOT-VERIFY (gauge)


def test_evaluate_refuses_a_none_gauge_row_rather_than_a_silent_empty_list() -> None:
    """Se qualcuno chiama evaluate() con gauge_row=None direttamente
    (bypassando run()), deve fallire RUMOROSAMENTE — un ritorno [] qui si
    leggerebbe come 'tutto sano', esattamente il passaggio pulito che un
    gauge mai letto non deve mai produrre."""
    with pytest.raises(ValueError):
        wa.evaluate(_probe(), 10.0, None, NOW)


def test_cannot_verify_when_gauge_unreadable_exits_2_not_a_clean_pass(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Il ramo piu importante del brief: un gauge irraggiungibile (query
    fallita, output vuoto, forma non parsabile) deve fermare run() a 2 — MAI
    a un 0 silenzioso che si legge come 'tutto sano'. Dopo la cura Kimi M1 il
    lato probe viaggia COMUNQUE: qui il probe e assente, quindi arrivano DUE
    messaggi (probe_silent RED + CANNOT-VERIFY), non uno."""
    monkeypatch.setattr(wa, "_read_probe_status", lambda: (None, None))
    monkeypatch.setattr(wa, "_read_gauge", lambda: None)
    sent: list[str] = []
    monkeypatch.setattr(
        wa,
        "send_to_gateway",
        lambda msg, host, level, condition: sent.append(msg) or True,
    )

    rc = wa.run(NOW)
    capsys.readouterr()

    assert rc == wa.EXIT_CANNOT_VERIFY == 2
    assert len(sent) == 2
    assert "probe silent" in sent[0]
    assert "CANNOT-VERIFY" in sent[1]


def test_innocence_run_exits_0_when_both_sources_are_readable_and_healthy(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """INNOCENZA del test sopra, stesso meccanismo: senza questo, un
    `_read_gauge` cablato a restituire sempre None farebbe passare il test
    di CANNOT-VERIFY per la ragione sbagliata."""
    monkeypatch.setattr(wa, "_read_probe_status", lambda: (_probe(), 10.0))
    monkeypatch.setattr(wa, "_read_gauge", _gauge)
    sent: list[str] = []
    monkeypatch.setattr(
        wa,
        "send_to_gateway",
        lambda msg, host, level, condition: sent.append(msg) or True,
    )

    rc = wa.run(NOW)
    out = capsys.readouterr().out

    assert rc == wa.EXIT_OK
    assert sent == []
    assert "all conditions healthy" in out


def test_guilt_cannot_verify_gauge_still_delivers_an_in_hand_auth_death(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Kimi r1 M1: seat morto E gauge illeggibile insieme (il momento
    degradato in cui le due cose co-occorrono) — l'auth_death gia in mano
    NON deve nascondersi dietro il CANNOT-VERIFY generico: viaggia comunque,
    e l'exit resta 2."""
    monkeypatch.setattr(wa, "_read_probe_status", lambda: (_probe("auth_death", 1, 1), 10.0))
    monkeypatch.setattr(wa, "_read_gauge", lambda: None)
    sent: list[str] = []
    monkeypatch.setattr(
        wa,
        "send_to_gateway",
        lambda msg, host, level, condition: sent.append(msg) or True,
    )

    rc = wa.run(NOW)
    capsys.readouterr()

    assert rc == wa.EXIT_CANNOT_VERIFY
    assert any("codex login" in m for m in sent), "the in-hand auth_death must still travel"
    assert any("CANNOT-VERIFY" in m for m in sent)


def test_guilt_failed_red_delivery_exits_nonzero_so_the_receipt_alarm_fires(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Kimi r1 M4: gateway morto durante un RED reale — 'alert FALLITO' su
    un log che nessuno legge + exit 0 = verdetto perso in silenzio. L'unico
    canale rimasto e la receipt-alarm del cron-runner, che scatta SOLO su
    exit non-zero: quindi non-zero deve essere."""
    monkeypatch.setattr(wa, "_read_probe_status", lambda: (_probe("auth_death", 1, 1), 10.0))
    monkeypatch.setattr(wa, "_read_gauge", _gauge)
    monkeypatch.setattr(
        wa,
        "send_to_gateway",
        lambda msg, host, level, condition: False,
    )

    rc = wa.run(NOW)
    capsys.readouterr()

    assert rc == wa.EXIT_CANNOT_VERIFY


def test_innocence_failed_warn_delivery_still_exits_0(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """INNOCENZA del confine M4 (Kimi r2 #5): un WARN e best-effort per
    contratto dichiarato — la sua mancata consegna NON deve diventare una
    receipt-page. Senza questo pin, un flip futuro di _emit che conta anche
    i WARN trasforma ogni outage del tier digest in un page, e niente
    diventa rosso."""
    monkeypatch.setattr(wa, "_read_probe_status", lambda: (_probe("other_failure", 0, 1), 10.0))
    monkeypatch.setattr(wa, "_read_gauge", _gauge)
    monkeypatch.setattr(
        wa,
        "send_to_gateway",
        lambda msg, host, level, condition: False,
    )

    rc = wa.run(NOW)
    capsys.readouterr()

    assert rc == wa.EXIT_OK


def test_run_exits_0_even_with_red_verdicts_because_the_verdict_travels_by_alert(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Un probe assente (RED probe_silent) non deve far fallire il cron: il
    verdetto viaggia via Telegram, non via exit code — stessa convenzione di
    wa_session_liveness.py. Il 2 resta riservato al 'non ho potuto guardare'."""
    monkeypatch.setattr(wa, "_read_probe_status", lambda: (None, None))
    monkeypatch.setattr(wa, "_read_gauge", _gauge)
    sent: list[str] = []
    monkeypatch.setattr(
        wa,
        "send_to_gateway",
        lambda msg, host, level, condition: sent.append(msg) or True,
    )

    rc = wa.run(NOW)
    capsys.readouterr()

    assert rc == wa.EXIT_OK
    assert len(sent) == 1


# ------------------------------------------------- fallback gateway judgment


class _FakeProc:
    def __init__(self, rc: int, stderr: str) -> None:
        self.returncode = rc
        self.stderr = stderr


def test_innocence_fallback_counts_a_spooled_verdict_as_responsibility_taken(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Kimi r2 #2: la barra del fallback rispecchia il contratto dell'alerter
    (alerter.py:207) — spooled/deduped/logged = il gateway POSSIEDE la notizia.
    Con M4 che da i denti al False, giudicare 'fallito' un RED spoolato
    fabbricherebbe una receipt-page falsa durante un semplice rate-limit."""
    monkeypatch.setitem(sys.modules, "sentinel_lib", None)
    monkeypatch.setattr(
        wa.subprocess, "run", lambda *a, **k: _FakeProc(0, "tg_notify: spooled\n")
    )

    assert wa.send_to_gateway("msg", "host", wa.RED, "auth_death") is True
    capsys.readouterr()


def test_guilt_fallback_refuses_rc0_with_no_canonical_verdict(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """COLPEVOLEZZA gemella: rc 0 senza NESSUN verdetto canonico non e
    responsabilita presa — il silenzio del gateway resta un fallimento
    (W104: giudica la REPLY, mai l'exit code)."""
    monkeypatch.setitem(sys.modules, "sentinel_lib", None)
    monkeypatch.setattr(wa.subprocess, "run", lambda *a, **k: _FakeProc(0, "some noise\n"))

    assert wa.send_to_gateway("msg", "host", wa.RED, "auth_death") is False
    capsys.readouterr()
