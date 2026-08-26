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


# ------------------------------------------------------- GUILT (S1.5 quota)


def test_guilt_exec_429_structured_on_stderr_is_quota_exhausted() -> None:
    verdict = probe.classify(
        0, "Logged in using ChatGPT\n", "", 1, "", "Error: 429 Too Many Requests"
    )
    assert verdict == probe.VERDICT_QUOTA_EXHAUSTED


def test_guilt_exec_insufficient_quota_structured_token_is_quota_exhausted() -> None:
    verdict = probe.classify(
        0, "Logged in using ChatGPT\n", "", 1, "", '{"error":{"code":"insufficient_quota"}}'
    )
    assert verdict == probe.VERDICT_QUOTA_EXHAUSTED


def test_guilt_exec_prose_usage_limit_reached_is_quota_exhausted() -> None:
    verdict = probe.classify(
        0, "Logged in using ChatGPT\n", "", 1, "", "You've hit your usage limit reached for today."
    )
    assert verdict == probe.VERDICT_QUOTA_EXHAUSTED


def test_guilt_login_status_side_can_also_carry_the_quota_signature() -> None:
    """Symmetric with the auth-death guilt test above (login status side) —
    `classify()` scans BOTH login streams when login_rc failed, not just
    exec's stderr."""
    verdict = probe.classify(1, "", "rate limit reached, try again later", 0, "pong", "")
    assert verdict == probe.VERDICT_QUOTA_EXHAUSTED


def test_guilt_auth_signature_outranks_a_coexisting_quota_signature() -> None:
    """Fixed two-step priority (S1.5 docstring): auth checked before quota.
    A stderr that happens to carry BOTH signatures resolves to auth_death,
    never to quota_exhausted."""
    verdict = probe.classify(
        0,
        "Logged in using ChatGPT\n",
        "",
        1,
        "",
        "error 401: unauthorized — also rate limit reached",
    )
    assert verdict == probe.VERDICT_AUTH_DEATH


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


# ------------------------------------------------- INNOCENCE (S1.5 quota)


def test_innocence_healthy_exec_answer_discussing_a_sponsor_quota_is_ok() -> None:
    """A successful exec (rc=0) whose model answer legitimately discusses a
    KITAS sponsor's "quota" must never classify quota_exhausted — same
    family-#3 discipline as the auth innocence test above: a rc=0 command's
    output is never scanned at all."""
    answer = "Your sponsor's quota exceeded this year's KITAS allocation."
    verdict = probe.classify(0, "Logged in using ChatGPT\n", "", 0, answer, "")
    assert verdict == probe.VERDICT_OK


def test_innocence_failed_exec_stdout_quota_prose_is_not_scanned_only_stderr() -> None:
    """Same R26 discipline as the existing auth innocence test: a FAILED
    exec's STDOUT (a partial model answer) is never scanned, even if it
    happens to carry quota-shaped prose — only stderr counts."""
    partial_answer = "...the client's monthly credits exhausted her visa portal quota"
    verdict = probe.classify(0, "Logged in using ChatGPT\n", "", 1, partial_answer, "boom")
    assert verdict == probe.VERDICT_OTHER_FAILURE


def test_innocence_bare_quota_word_alone_does_not_fire() -> None:
    """Bare "quota"/"exhausted"/"limit" are ordinary immigration-consultancy
    vocabulary (R28-1 in the daemon's own word class) — deliberately
    excluded as standalone alternatives. A failed exec whose stderr merely
    contains the bare word must not false-positive quota_exhausted."""
    verdict = probe.classify(
        0, "Logged in using ChatGPT\n", "", 1, "", "the client's quota question is unresolved"
    )
    assert verdict == probe.VERDICT_OTHER_FAILURE


def test_innocence_quota_regex_does_not_bleed_across_command_boundary() -> None:
    """Mirrors the daemon's per-text (never concatenated) scanning discipline
    — a quota phrase split across the login-status and exec texts must not
    combine into a false match; each text is searched independently."""
    verdict = probe.classify(1, "", "rate limit", 1, "", "reached tomorrow")
    assert verdict != probe.VERDICT_QUOTA_EXHAUSTED


def test_fallback_regexes_are_byte_identical_to_the_daemon_detectors() -> None:
    """Superscar #1 applicata a una regex: OGNI copia fallback in
    scripts/wa_codex_seat_probe.py DEVE restare byte-identica al suo gemello
    nel daemon, o i due rilevatori divergono sullo stesso testo.

    S1.5 (2026-08-26): this test used to check a single `_AUTH_DEATH_RE`.
    That symbol no longer exists in the daemon — B2b's confidence-tier SPEC
    split it into `_AUTH_STRUCTURED_RE`/`_AUTH_PROSE_RE` (the daemon's
    module-level names, both without a leading underscore stripped on
    import — same shape quota already had) and this test had gone RED,
    silently, because it could not even find the old name to compare
    against (verified live on this branch's HEAD before this fix: the old
    assertion failed at "daemon _AUTH_DEATH_RE definition not found", not
    at a content mismatch). Now covers all four regexes the probe
    imports-with-fallback: auth (structured+prose) and quota
    (structured+prose, S1.5's own addition)."""
    import re as _re

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
    daemon_text = daemon_src.read_text()
    probe_text = _MODULE_PATH.read_text()

    def _extract(text: str, pattern: str, label: str) -> tuple[str, bool]:
        # `^`-anchored + MULTILINE (never DOTALL on the anchor): the naive
        # "name, then anything, then = re.compile(" shape used before this
        # fix matched a COMMENT mentioning the name earlier in the file and
        # then walked forward across `[^=]*` (which spans newlines) into a
        # LATER, unrelated regex's own `= re.compile(` — reproduced live:
        # `_QUOTA_STRUCTURED_RE` was preceded by a same-named mention in a
        # comment two definitions above it, and the ungoverned search
        # silently bound to `_AUTH_STRUCTURED_RE`'s body instead. Anchoring
        # to an actual start-of-line assignment (never inside a comment,
        # which starts with `#`) makes that mis-bind structurally
        # impossible instead of merely unlikely.
        match = _re.search(pattern, text, _re.DOTALL | _re.MULTILINE)
        assert match is not None, f"{label} definition not found"
        literal_group = match.group(1)
        # `r"([^"]*)"` only understands adjacent double-quoted raw-string
        # literals. That is a real gap, not a hypothetical one (caught in
        # team-lead review of PR #5028, 2026-08-26, by direct execution
        # against synthetic drift, not by reasoning about the code): a
        # same-shape source on both sides can drift and still compare
        # equal, three separate ways —
        #   1. either side switches to single-quoted `r'...'`      -> both
        #      extract to "" and "" == "" passes on real drift.
        #   2. either side builds the pattern via `"|".join([...])` instead
        #      of adjacent literals                                -> same
        #      "" == "" false-pass.
        #   3. a literal contains an embedded `"` (a raw string CAN carry
        #      one, `r"a[\"]b"` is valid Python) -> the naive extraction
        #      TRUNCATES at that quote and returns a non-empty but PARTIAL
        #      body; any difference placed after the embedded quote is
        #      invisible to the equality check below.
        # "assert body is non-empty" alone closes cases 1-2 but leaves 3
        # open (its body IS non-empty). The fix proves the extraction
        # consumed the WHOLE literal-argument text, not just SOME of it:
        # strip every `r"..."` match out of literal_group and demand the
        # remainder carry no leftover quote character. A single-quoted
        # literal, a join()-built pattern, or a truncated double-quoted
        # literal all leave a tell-tale `"`/`'` behind in what's left.
        literal_re = r'r"([^"]*)"'
        body = "".join(_re.findall(literal_re, literal_group))
        assert body, (
            f"{label}: no r\"...\" literal captured at all — the pattern may "
            f"have switched quote style (r'...') or moved to a non-literal "
            f'construction (e.g. "|".join(...)); this extractor only '
            f'understands adjacent r"..." raw-string concatenation, and a '
            f"silent empty-vs-empty compare would hide real drift"
        )
        remainder = _re.sub(literal_re, "", literal_group)
        assert '"' not in remainder and "'" not in remainder, (
            f"{label}: a quote character survives after removing every "
            f'r"..." literal this extractor found — the extraction is '
            f"INCOMPLETE (a literal was skipped, or an embedded quote inside "
            f'one r"..." literal truncated the capture before the literal '
            f"actually ended), so the compared body is a PARTIAL read, not "
            f"the whole pattern. residual={remainder!r}"
        )
        return body, "re.IGNORECASE" in literal_group

    for daemon_name, probe_name in (
        ("_AUTH_STRUCTURED_RE", "AUTH_STRUCTURED_RE"),
        ("_AUTH_PROSE_RE", "AUTH_PROSE_RE"),
        ("_QUOTA_STRUCTURED_RE", "QUOTA_STRUCTURED_RE"),
        ("_QUOTA_PROSE_RE", "QUOTA_PROSE_RE"),
    ):
        daemon_body, daemon_ic = _extract(
            daemon_text,
            rf"^{daemon_name}:\s*re\.Pattern\[str\]\s*=\s*re\.compile\((.*?)\n\)",
            f"daemon {daemon_name}",
        )
        probe_body, probe_ic = _extract(
            probe_text,
            rf"^    {probe_name} = re\.compile\((.*?)\n    \)",
            f"probe fallback {probe_name}",
        )
        assert probe_body == daemon_body, (
            f"the probe's fallback {probe_name} drifted from the daemon's "
            f"{daemon_name} — update the copy in scripts/wa_codex_seat_probe.py"
        )
        # Flags too (Kimi r1 m9): dropping re.IGNORECASE on either side keeps
        # the bodies identical while the detectors diverge on case.
        assert daemon_ic, f"daemon {daemon_name} lost re.IGNORECASE"
        assert probe_ic, f"probe fallback {probe_name} lost re.IGNORECASE"
