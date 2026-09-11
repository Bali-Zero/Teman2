"""Tests per scripts/wa_codex_seat_probe.py — il classify() puro.

La disciplina di scansione imita la regola R26 del daemon: solo il testo di
un comando FALLITO viene scansionato, e per `exec` solo STDERR. Le innocenze
qui sotto sono il punto: "unauthorized"/"login" sono lessico ordinario del
dominio visti dentro una risposta legittima del modello (famiglia #3) — un
probe che scansiona l'output di un comando riuscito pagina AUTH DEAD su un
seat sano.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_MODULE_PATH = Path(__file__).parents[1] / "wa_codex_seat_probe.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("wa_codex_seat_probe", _MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


probe = _load()

# ------------------------------------------------------------------- GUILT


def test_guilt_logged_out_login_status_is_auth_death() -> None:
    """Misurato live 2026-08-20: da sloggato `codex login status` stampa
    "Not logged in" su STDOUT con rc=1."""
    verdict = probe.classify(1, "Not logged in\n", "", 0, "pong", "")
    assert verdict == probe.VERDICT_AUTH_DEATH


def test_guilt_exec_401_on_stderr_is_auth_death() -> None:
    verdict = probe.classify(0, "Logged in using ChatGPT\n", "", 1, "", "error 401: unauthorized")
    assert verdict == probe.VERDICT_AUTH_DEATH


def test_guilt_both_unrun_is_probe_error() -> None:
    rc = probe._UNRUN_RC
    assert probe.classify(rc, "", "", rc, "", "") == probe.VERDICT_PROBE_ERROR


def test_guilt_nonzero_without_auth_signature_is_other_failure() -> None:
    verdict = probe.classify(0, "Logged in using ChatGPT\n", "", 1, "", "boom: disk full")
    assert verdict == probe.VERDICT_OTHER_FAILURE


def test_guilt_exec_usage_limit_on_stderr_is_quota_exhausted() -> None:
    """B2b: closes the gap this module's docstring used to declare open —
    quota exhaustion now gets its own verdict, not `other_failure`."""
    verdict = probe.classify(
        0, "Logged in using ChatGPT\n", "", 1, "", "ERROR: You've hit your usage limit."
    )
    assert verdict == probe.VERDICT_QUOTA_EXHAUSTED


def test_guilt_exec_quota_exceeded_on_stderr_is_quota_exhausted() -> None:
    verdict = probe.classify(0, "Logged in using ChatGPT\n", "", 1, "", "quota exceeded")
    assert verdict == probe.VERDICT_QUOTA_EXHAUSTED


# --------------------------------------------------------------- INNOCENCE


def test_innocence_healthy_run_is_ok_even_if_the_answer_discusses_logins() -> None:
    """LA innocenza chiave (R26): un exec RIUSCITO il cui stdout contiene
    lessico auth-shaped (risposta legittima su credenziali del CLIENTE) non
    deve mai classificare auth_death — l'output di un comando a rc=0 non
    viene scansionato affatto."""
    answer = "Your portal login is unauthorized until the KITAS is renewed."
    verdict = probe.classify(0, "Logged in using ChatGPT\n", "", 0, answer, "")
    assert verdict == probe.VERDICT_OK


def test_innocence_failed_exec_stdout_is_not_scanned_only_stderr() -> None:
    """Anche a exec fallito, lo STDOUT (potenziale risposta parziale del
    modello) resta fuori dalla superficie di scansione — solo stderr conta
    per l'exec (regola R26 del daemon)."""
    partial_answer = "...the client's session invalidated her visa portal access"
    verdict = probe.classify(0, "Logged in using ChatGPT\n", "", 1, partial_answer, "boom")
    assert verdict == probe.VERDICT_OTHER_FAILURE


def test_innocence_healthy_login_status_output_does_not_match() -> None:
    """Misurato live 2026-08-20: da loggato stampa "Logged in using ChatGPT"
    con rc=0 — e comunque un rc=0 non viene scansionato."""
    assert probe.classify(0, "Logged in using ChatGPT\n", "", 0, "pong", "") == probe.VERDICT_OK


def test_innocence_healthy_run_answer_discussing_rptka_quota_is_ok() -> None:
    """Over-match guard (cicatrix family #3): a SUCCESSFUL exec whose
    answer discusses a client's real RPTKA quota / KITAS limit of stay is
    ordinary Bali Zero domain vocabulary — a rc=0 output is never scanned
    at all, so this must never classify quota_exhausted."""
    answer = "Your company's RPTKA quota and KITAS limit of stay are both current."
    verdict = probe.classify(0, "Logged in using ChatGPT\n", "", 0, answer, "")
    assert verdict == probe.VERDICT_OK


def test_innocence_failed_exec_bare_quota_word_is_other_failure_not_quota() -> None:
    """Over-match guard: a failed exec whose stderr mentions "quota" without
    the "exceeded"/"exhausted" framing (or "limit" without "usage"/"weekly")
    must not be misclassified as quota_exhausted."""
    verdict = probe.classify(
        0,
        "Logged in using ChatGPT\n",
        "",
        1,
        "",
        "boom: could not resolve the RPTKA quota against the KITAS limit of stay",
    )
    assert verdict == probe.VERDICT_OTHER_FAILURE


def test_fallback_regex_is_byte_identical_to_the_daemon_detector() -> None:
    """Superscar #1 applicata a una regex: la copia fallback DEVE restare
    byte-identica a `_AUTH_DEATH_RE` del daemon, o i due rilevatori
    divergono sullo stesso testo. Questo test confronta pattern e flag
    contro la fonte nel repo (il probe sul host importa la copia runtime;
    qui nel repo le due definizioni devono combaciare)."""
    daemon_src = (
        Path(__file__).parents[2]
        / "apps"
        / "backend-rag"
        / "backend"
        / "llm"
        / "codex_exec_client.py"
    )
    # Textual extraction, not import: the daemon module pulls in backend.*
    # and this comparison is about the SOURCE definitions staying identical.
    import re as _re

    text = daemon_src.read_text()
    match = _re.search(r"_AUTH_DEATH_RE[^=]*= re\.compile\((.*?)\n\)", text, _re.DOTALL)
    assert match is not None, "daemon _AUTH_DEATH_RE definition not found"
    daemon_body = "".join(_re.findall(r'r"([^"]*)"', match.group(1)))
    probe_text = _MODULE_PATH.read_text()
    probe_match = _re.search(
        r"AUTH_DEATH_RE = re\.compile\((.*?)\n    \)", probe_text, _re.DOTALL
    )
    assert probe_match is not None, "probe fallback AUTH_DEATH_RE definition not found"
    probe_body = "".join(_re.findall(r'r"([^"]*)"', probe_match.group(1)))
    assert probe_body == daemon_body, (
        "the probe's fallback regex drifted from the daemon's _AUTH_DEATH_RE — "
        "update the copy in scripts/wa_codex_seat_probe.py"
    )
    # Flags too (Kimi r1 m9): dropping re.IGNORECASE on either side keeps the
    # bodies identical while the detectors diverge on case.
    assert "re.IGNORECASE" in match.group(1), "daemon regex lost re.IGNORECASE"
    assert "re.IGNORECASE" in probe_match.group(1), "probe fallback lost re.IGNORECASE"


def test_fallback_quota_regex_is_byte_identical_to_the_daemon_detector() -> None:
    """Same superscar #1 discipline as the auth-death parity test above,
    applied to `_QUOTA_RE` / the probe's fallback `QUOTA_RE` copy."""
    daemon_src = (
        Path(__file__).parents[2]
        / "apps"
        / "backend-rag"
        / "backend"
        / "llm"
        / "codex_exec_client.py"
    )
    import re as _re

    text = daemon_src.read_text()
    match = _re.search(r"_QUOTA_RE[^=]*= re\.compile\((.*?)\n\)", text, _re.DOTALL)
    assert match is not None, "daemon _QUOTA_RE definition not found"
    daemon_body = "".join(_re.findall(r'r"([^"]*)"', match.group(1)))
    probe_text = _MODULE_PATH.read_text()
    probe_match = _re.search(r"QUOTA_RE = re\.compile\((.*?)\n    \)", probe_text, _re.DOTALL)
    assert probe_match is not None, "probe fallback QUOTA_RE definition not found"
    probe_body = "".join(_re.findall(r'r"([^"]*)"', probe_match.group(1)))
    assert probe_body == daemon_body, (
        "the probe's fallback regex drifted from the daemon's _QUOTA_RE — "
        "update the copy in scripts/wa_codex_seat_probe.py"
    )
    assert "re.IGNORECASE" in match.group(1), "daemon regex lost re.IGNORECASE"
    assert "re.IGNORECASE" in probe_match.group(1), "probe fallback lost re.IGNORECASE"
