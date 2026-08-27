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

    def _extract(text: str, pattern: str, label: str) -> tuple[str, frozenset[str]]:
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
        # `"re.IGNORECASE" in literal_group` (independent cross-family
        # refuter finding on PR #5028, team-lead review 2026-08-26) proves
        # only that ONE flag name is present, not that the flag SET
        # matches between daemon and probe: adding `re.ASCII`/
        # `re.MULTILINE`/`re.VERBOSE` to ONE side changes the compiled
        # behaviour, and the boolean check still passes because
        # IGNORECASE itself never moved. Extract every `re.FLAGNAME`
        # token from `remainder` — the non-literal leftover after every
        # `r"..."` match was already stripped out above, so this can
        # never accidentally match text INSIDE the pattern body itself
        # (there is no legitimate reason a regex alternative here would
        # contain the literal substring "re." followed by capital
        # letters) — and return the whole SET for an equality check, not
        # a single flag's presence.
        flags = frozenset(_re.findall(r"\bre\.([A-Z_]+)\b", remainder))
        return body, flags

    for daemon_name, probe_name in (
        ("_AUTH_STRUCTURED_RE", "AUTH_STRUCTURED_RE"),
        ("_AUTH_PROSE_RE", "AUTH_PROSE_RE"),
        ("_QUOTA_STRUCTURED_RE", "QUOTA_STRUCTURED_RE"),
        ("_QUOTA_PROSE_RE", "QUOTA_PROSE_RE"),
    ):
        daemon_body, daemon_flags = _extract(
            daemon_text,
            rf"^{daemon_name}:\s*re\.Pattern\[str\]\s*=\s*re\.compile\((.*?)\n\)",
            f"daemon {daemon_name}",
        )
        probe_body, probe_flags = _extract(
            probe_text,
            rf"^    {probe_name} = re\.compile\((.*?)\n    \)",
            f"probe fallback {probe_name}",
        )
        assert probe_body == daemon_body, (
            f"the probe's fallback {probe_name} drifted from the daemon's "
            f"{daemon_name} — update the copy in scripts/wa_codex_seat_probe.py"
        )
        # Flags too (Kimi r1 m9, ORIGINAL finding): dropping re.IGNORECASE
        # on either side keeps the bodies identical while the detectors
        # diverge on case.
        assert "IGNORECASE" in daemon_flags, f"daemon {daemon_name} lost re.IGNORECASE"
        assert "IGNORECASE" in probe_flags, f"probe fallback {probe_name} lost re.IGNORECASE"
        # Flags SET, not just IGNORECASE's presence (independent
        # cross-family refuter, team-lead review 2026-08-26): the check
        # above is blind to a flag added to only ONE side — re.ASCII,
        # re.MULTILINE, re.VERBOSE all change what the compiled pattern
        # actually matches, and two detectors compiled from
        # byte-identical pattern TEXT under different flags are not
        # byte-identical detectors.
        assert probe_flags == daemon_flags, (
            f"the probe's fallback {probe_name} flags {sorted(probe_flags)} "
            f"differ from the daemon's {daemon_name} flags "
            f"{sorted(daemon_flags)} — a flag was added to only one side"
        )


# ---------------------------------------------------------------------------
# detector_source status field (team-lead ask, PR #5028 round-4, 2026-08-26,
# live measurement on Pro): seat-status.json could not previously say
# whether a probe run resolved its detectors by IMPORT or fell back to its
# own copies — the ONE thing wa_codex_seat_sentinel.py needs to tell a
# healthy probe from a blind one, per that module's own docstring naming
# this status file the SOLE channel across the user boundary. These two
# tests load the module FRESH under each condition and read the field the
# module itself actually resolved — never a hand-typed expectation.
# ---------------------------------------------------------------------------


def test_guilt_detector_source_reports_fallback_copy_when_import_is_blocked() -> None:
    """`unittest.mock.patch.dict(sys.modules, {...: None})` is the standard
    trick for forcing `import x` to raise `ImportError` regardless of
    whether `x` is actually resolvable on `sys.path` — Python's import
    system treats a `None` value in `sys.modules` as "this import is
    blocked" (see CPython import system docs). Blocking all three dotted
    prefixes covers `from backend.llm.codex_exec_client import ...`
    regardless of which segment Python's import machinery consults first."""
    import sys as _sys
    from unittest.mock import patch as _patch

    with _patch.dict(
        _sys.modules,
        {"backend.llm.codex_exec_client": None, "backend.llm": None, "backend": None},
    ):
        spec = importlib.util.spec_from_file_location(
            "wa_codex_seat_probe_forced_fallback", _MODULE_PATH
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        _sys.modules[spec.name] = module
        spec.loader.exec_module(module)

    assert module._AUTH_DEATH_SOURCE == "fallback-copy"
    # WA_CODEX_BIN points at a path that cannot exist, so `_run()` hits its
    # OSError/spawn-failure branch deterministically (rc=_UNRUN_RC for both
    # commands) regardless of whether a real `codex` binary happens to be on
    # this machine's PATH — the point of this test is `detector_source`,
    # not a real subprocess round-trip.
    status = module.probe(env={"WA_CODEX_BIN": "/nonexistent/codex-binary-for-test"})
    assert status.detector_source == "fallback-copy"
    assert '"detector_source": "fallback-copy"' in status.to_json()


def test_guilt_detector_source_reports_import_when_daemon_client_resolves() -> None:
    """Mirror case: with `apps/backend-rag` explicitly on `sys.path` — the
    same PYTHONPATH shape `infra/launchagents/wrappers/
    wa-codex-seat-probe-wrapper.sh` sets up against the root-owned runtime
    tree in production — the real
    `from backend.llm.codex_exec_client import ...` succeeds and
    `_AUTH_DEATH_SOURCE` must read "import", not "fallback-copy"."""
    import sys as _sys

    backend_rag_root = str(Path(__file__).parents[2] / "apps" / "backend-rag")
    _sys.path.insert(0, backend_rag_root)
    try:
        spec = importlib.util.spec_from_file_location(
            "wa_codex_seat_probe_forced_import", _MODULE_PATH
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        _sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        _sys.path.remove(backend_rag_root)

    assert module._AUTH_DEATH_SOURCE == "import"
    status = module.probe(env={"WA_CODEX_BIN": "/nonexistent/codex-binary-for-test"})
    assert status.detector_source == "import"
    assert '"detector_source": "import"' in status.to_json()


# ---------------------------------------------------------------------------
# Cross-classifier agreement corpus (PATH C addition, team-lead review of
# PR #5028, 2026-08-26 — not optional, the condition of accepting PATH C
# over full classifier unification): PATH C narrows the probe/daemon
# divergence, it does not eliminate it. This corpus proves EXACTLY where
# the twins still disagree — a gap and an accepted, enumerated exception
# must never look the same. Fails if a NEW divergence appears; the
# enumeration SHRINKING (the follow-up classifier-unification PR's job)
# is success, not failure — this test does not pin the enumeration's
# size, only its accuracy against whatever the corpus currently holds.
#
# `backend.llm.codex_exec_client` is imported HERE, not at module level:
# CI's `scripts-tests-sweep.yml` runs `PYTHONPATH=. python -m pytest
# scripts/tests/` from the REPO ROOT, so a bare module-level
# `from backend...` would raise ModuleNotFoundError in that context
# (`backend` lives under `apps/backend-rag/`, not the repo root) — same
# reasoning as `test_guilt_detector_source_reports_import_when_daemon_client_resolves`
# above. Insert-then-remove keeps the path change scoped to this one
# call, never leaking into other test files collected in the same
# session (W96-class module/path leakage).
# ---------------------------------------------------------------------------

# LIMITATION (team-lead review, PR #5028, 2026-08-26 — documented, not
# fixed, per explicit ask): every case below is driven through `classify()`
# as `exec_err` only (`login_err=""` in `test_cross_classifier_agreement_corpus`
# and `test_flagship_string_is_in_the_corpus_and_now_agrees_with_the_daemon`
# below) — matching the real-world shape the probe was built for, since a
# login-leg failure that also carries an auth/quota-shaped stderr is the
# rarer case in practice. A divergence that ONLY manifests when the guilty
# text arrives via `login_err` (or via BOTH legs at once, exercising
# `guilty_texts`' multi-element path together) is outside what a green run
# of this corpus can see. Not a defect in the corpus's design — the daemon's
# own P2 per-line-isolation property this probe borrows does not care which
# leg a line came from — but a real boundary of what "this test is green"
# proves, worth knowing before treating it as exhaustive.
_CROSS_CLASSIFIER_CORPUS: list[tuple[str, str]] = [
    ("A-auth-structured-only", "error 401: unauthorized"),
    ("B-quota-structured-only", "429 too many requests"),
    (
        "C-auth-structured-quota-prose",
        "error 401: unauthorized — also rate limit reached",
    ),
    (
        "D-flagship-auth-prose-quota-structured",
        "Error: token has expired; refresh failed with 429 too many requests",
    ),
    (
        "E-both-structured-tie",
        "error 401: unauthorized; insufficient_quota reported",
    ),
    (
        "F-both-prose-tie",
        "not logged in; you exceeded your current quota",
    ),
]

# PATH C's documented, deliberate residual gap: a genuine STRUCTURED/
# STRUCTURED or PROSE/PROSE tie has no principled winner in EITHER
# classifier, but the probe has no AMBIGUOUS verdict to raise (unlike the
# daemon, which reports one) — see classify()'s docstring. Each entry
# names WHY it diverges, not just that it does.
_KNOWN_DIVERGENCES: dict[str, str] = {
    "E-both-structured-tie": (
        "both classes matched at STRUCTURED (HIGH) — the daemon has no "
        "principled winner and reports AMBIGUOUS (SPEC P1: >=2 classes at "
        "HIGH); the probe has no AMBIGUOUS verdict and falls to the "
        "historical fixed auth-first order, returning auth_death"
    ),
    "F-both-prose-tie": (
        "both classes matched at PROSE (LOW) only — 0 classes at HIGH is "
        "ALSO a daemon tie (SPEC P1: 0 or >=2 at HIGH both count as no "
        "principled winner), so this is AMBIGUOUS on the daemon side too; "
        "the probe again falls to auth-first"
    ),
}


def _daemon_verdict_as_probe_vocabulary(stderr_text: str) -> str:
    """Runs `stderr_text` through the REAL daemon classifier and maps its
    `StderrVerdict` onto the probe's VERDICT_* vocabulary for comparison.
    "AMBIGUOUS" and "NONE" are sentinels, never a real probe VERDICT_*
    string — so they can never accidentally produce a false agreement."""
    import sys as _sys

    backend_rag_root = str(Path(__file__).parents[2] / "apps" / "backend-rag")
    _sys.path.insert(0, backend_rag_root)
    try:
        from backend.llm.codex_exec_client import _classify_stderr, _WireWordClass

        verdict = _classify_stderr(stderr_text)
    finally:
        _sys.path.remove(backend_rag_root)

    if verdict.winner is _WireWordClass.AUTH_DEATH:
        return probe.VERDICT_AUTH_DEATH
    if verdict.winner is _WireWordClass.QUOTA:
        return probe.VERDICT_QUOTA_EXHAUSTED
    if verdict.ambiguous_classes:
        return "AMBIGUOUS"
    return "NONE"


def test_cross_classifier_agreement_corpus() -> None:
    for case_id, stderr_text in _CROSS_CLASSIFIER_CORPUS:
        probe_verdict = probe.classify(0, "", "", 1, "", stderr_text)
        daemon_verdict = _daemon_verdict_as_probe_vocabulary(stderr_text)
        agree = probe_verdict == daemon_verdict
        expected_divergence = _KNOWN_DIVERGENCES.get(case_id)

        if expected_divergence is not None:
            assert not agree, (
                f"{case_id}: expected a KNOWN divergence ({expected_divergence}) "
                f"but probe and daemon now AGREE ({probe_verdict!r}) — the "
                f"underlying case is fixed, shrink _KNOWN_DIVERGENCES rather "
                f"than leave a stale exception standing"
            )
        else:
            assert agree, (
                f"{case_id}: probe={probe_verdict!r} vs daemon={daemon_verdict!r} "
                f"for stderr={stderr_text!r} — a NEW, unenumerated divergence. "
                f"Either this is a real regression in classify()'s precedence, "
                f"or it is a genuinely new known-divergent shape that needs its "
                f"own entry (with a reason) in _KNOWN_DIVERGENCES — never leave "
                f"it silently unlisted."
            )


def test_flagship_string_is_in_the_corpus_and_now_agrees_with_the_daemon() -> None:
    """Team-lead's exact missing fixture, pinned directly (PR #5028,
    2026-08-26): before PATH C, `probe.classify()` returned auth_death for
    this string while the daemon's `_classify_stderr` returned QUOTA at
    HIGH confidence — a real disagreement on what remedy an operator
    should be told. Asserts BOTH that the string is IN the shared corpus
    above (not merely checked in isolation, elsewhere, disconnected from
    the agreement sweep) and that it now resolves to QUOTA_EXHAUSTED."""
    flagship = "Error: token has expired; refresh failed with 429 too many requests"
    assert any(text == flagship for _, text in _CROSS_CLASSIFIER_CORPUS), (
        "the flagship string must be IN _CROSS_CLASSIFIER_CORPUS, not just "
        "asserted in a separate, disconnected test"
    )
    assert probe.classify(0, "", "", 1, "", flagship) == probe.VERDICT_QUOTA_EXHAUSTED
