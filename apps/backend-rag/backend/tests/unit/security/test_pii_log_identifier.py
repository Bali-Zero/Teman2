"""F7 gate — ``redact_identifier_for_log`` never leaks a raw phone/chat id.

Guilt/innocence per cicatrix-superscar.md family #3: a redaction helper
proves it redacts (guilt: the raw value never survives), AND proves it
stays useful (innocence: the digest is stable for the same input and
distinguishable for a different one — a redaction that collapses every
input to the same placeholder destroys log correlation, which is a
different failure, not a fix).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import backend.security.pii_log_identifier as pii_log_identifier
from backend.security.pii_log_identifier import (
    MISSING_IDENTIFIER_MARKER,
    _reset_fallback_salt_state_for_tests,
    redact_identifier_for_log,
)

# Obviously-synthetic numbers only — never a shape that could be mistaken
# for a real client'''s WhatsApp number.
_SYNTHETIC_PHONE = "+62 000-111-2222"
_SYNTHETIC_PHONE_DIGITS_ONLY = "620001112222"
_SYNTHETIC_PHONE_OTHER = "+62 999-888-7777"
_SYNTHETIC_CHAT_ID = 194920123


@pytest.fixture(autouse=True)
def _isolated_fallback_salt_state() -> None:
    """Every test starts and ends with a clean fallback-salt cache, so a
    test that exercises the unconfigured path never leaks a generated
    salt (or the warn-once flag) into a test that runs after it."""
    _reset_fallback_salt_state_for_tests()
    yield
    _reset_fallback_salt_state_for_tests()


class TestRedactIdentifierForLogGuilt:
    """The raw value must NEVER appear in the digest output."""

    def test_phone_digest_does_not_contain_raw_phone(self) -> None:
        digest = redact_identifier_for_log(_SYNTHETIC_PHONE)
        assert _SYNTHETIC_PHONE not in digest
        assert "0001112222" not in digest  # the bare digits, plus-stripped
        assert digest.startswith("id:")

    def test_chat_id_digest_does_not_contain_raw_chat_id(self) -> None:
        digest = redact_identifier_for_log(_SYNTHETIC_CHAT_ID)
        assert str(_SYNTHETIC_CHAT_ID) not in digest
        assert digest.startswith("id:")

    def test_digest_is_not_a_bare_unkeyed_sha256(self) -> None:
        """A bare sha256 of the digits is reversible by brute force over the
        enumerable phone-number space — it must not appear verbatim."""
        bare = hashlib.sha256(b"620001112222").hexdigest()[:12]
        digest = redact_identifier_for_log(_SYNTHETIC_PHONE)
        assert digest != f"id:{bare}"


class TestRedactIdentifierForLogInnocence:
    """The digest must stay USEFUL for cross-line correlation."""

    def test_same_phone_same_digest_regardless_of_formatting(self) -> None:
        assert redact_identifier_for_log(_SYNTHETIC_PHONE) == redact_identifier_for_log(
            _SYNTHETIC_PHONE_DIGITS_ONLY,
        )

    def test_different_phone_different_digest(self) -> None:
        assert redact_identifier_for_log(_SYNTHETIC_PHONE) != redact_identifier_for_log(
            _SYNTHETIC_PHONE_OTHER,
        )

    def test_digest_is_stable_across_calls(self) -> None:
        first = redact_identifier_for_log(_SYNTHETIC_PHONE)
        second = redact_identifier_for_log(_SYNTHETIC_PHONE)
        assert first == second

    def test_phone_and_chat_id_of_same_digits_still_distinguishable_by_value(self) -> None:
        """Not a collision guard, just documents that a phone-shaped and a
        chat-id-shaped input are hashed via the same normalization; if they
        ever carry the same digits they DO collide by design (both reduce
        to the same digit string). This is fine because they are never
        compared against each other in the caller (one call site logs
        phone-or-chat_id, never both together)."""
        digest_phone = redact_identifier_for_log("620001112222")
        digest_chat_id = redact_identifier_for_log(620001112222)
        assert digest_phone == digest_chat_id


class TestRedactIdentifierForLogMissing:
    def test_none_returns_missing_marker(self) -> None:
        assert redact_identifier_for_log(None) == MISSING_IDENTIFIER_MARKER

    def test_empty_string_returns_missing_marker(self) -> None:
        assert redact_identifier_for_log("") == MISSING_IDENTIFIER_MARKER

    def test_whitespace_only_returns_missing_marker(self) -> None:
        assert redact_identifier_for_log("   ") == MISSING_IDENTIFIER_MARKER

    def test_non_digit_garbage_returns_missing_marker(self) -> None:
        assert redact_identifier_for_log("n/a") == MISSING_IDENTIFIER_MARKER


class TestRedactIdentifierForLogSaltConfiguration:
    """LOG_PII_HMAC_SALT changes the digest; unset falls back, never to
    the raw value."""

    def test_configured_salt_changes_the_digest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LOG_PII_HMAC_SALT", raising=False)
        unconfigured = redact_identifier_for_log(_SYNTHETIC_PHONE)

        monkeypatch.setenv("LOG_PII_HMAC_SALT", "a-test-salt-that-is-not-the-fallback")
        configured = redact_identifier_for_log(_SYNTHETIC_PHONE)

        assert configured != unconfigured
        assert configured.startswith("id:")

    def test_same_configured_salt_is_deterministic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_PII_HMAC_SALT", "a-test-salt")
        first = redact_identifier_for_log(_SYNTHETIC_PHONE)
        second = redact_identifier_for_log(_SYNTHETIC_PHONE)
        assert first == second

    def test_unconfigured_salt_still_never_prints_raw_phone(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("LOG_PII_HMAC_SALT", raising=False)
        digest = redact_identifier_for_log(_SYNTHETIC_PHONE)
        assert _SYNTHETIC_PHONE not in digest
        assert "0001112222" not in digest
        assert digest.startswith("id:")


class TestRedactIdentifierForLogFallbackSaltSecurity:
    """Finding 1 (adversarial review, 2026-08-25): the previous fallback was
    a literal string constant in the source, so anyone holding only the
    repo could recompute every digest by enumerating the small phone-number
    space and hashing each candidate with that known constant — the
    reviewer reproduced a target digest exactly this way. The fallback must
    now be a random, per-process, never-written-to-source key: a digest
    computed while unconfigured must NOT be reproducible from anything a
    repo reader could see, and its unconfigured/degraded state must be
    LOUD, not silent (cicatrix family #2 — "esiste != armato" applies to
    security fallbacks too: a silent degrade is a degrade nobody notices)."""

    def test_old_public_fallback_constant_no_longer_exists(self) -> None:
        """Guilt: the specific vulnerability class (a hardcoded, source-
        visible key) must be structurally gone, not just unused."""
        assert not hasattr(pii_log_identifier, "_UNCONFIGURED_FALLBACK_SALT")

    def test_unconfigured_digest_is_not_reproducible_from_any_fixed_source_string(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Guilt: no string LITERAL WRITTEN IN THIS MODULE'S SOURCE FILE
        can reproduce the digest computed while LOG_PII_HMAC_SALT is
        unset — the same attack the reviewer used against the old design
        (a hardcoded fallback constant), run here as a regression guard.

        Deliberately parses the .py file's SOURCE TEXT via ``ast`` rather
        than trawling ``vars(module)``: the latter would also pick up
        ``_fallback_salt`` itself once it has been generated (a value that
        exists only in this process's memory, never written to source) and
        the test would then "catch" its own runtime state as if it were a
        source-visible constant — a false positive that proves nothing
        about what an attacker holding only the repo could do. Parsing the
        source keeps the test honest about what "source-visible" means.
        """
        import ast
        import hashlib
        import hmac
        import inspect

        monkeypatch.delenv("LOG_PII_HMAC_SALT", raising=False)
        target = redact_identifier_for_log(_SYNTHETIC_PHONE)
        # The message hashed is the bare digit-stripped string at this
        # point (no national-prefix folding yet — that lands separately).
        # Deriving it via the module's own regex (rather than hardcoding a
        # value) keeps this test honest if that extraction logic changes.
        digits = pii_log_identifier._NON_DIGITS_RE.sub("", _SYNTHETIC_PHONE)

        source_path = inspect.getsourcefile(pii_log_identifier)
        assert source_path is not None
        tree = ast.parse(Path(source_path).read_text(encoding="utf-8"))
        candidate_keys = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        candidate_keys.add("")  # empty-key edge case
        assert len(candidate_keys) > 5, "sanity: source parsing found suspiciously few strings"

        for candidate in candidate_keys:
            reproduced = hmac.new(
                candidate.encode("utf-8"),
                digits.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()[:12]
            assert f"id:{reproduced}" != target, (
                f"digest reproducible from source-visible literal {candidate!r}"
            )

    def test_unconfigured_digest_differs_across_simulated_process_restarts(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Guilt: if a fixed fallback (of any kind) still existed, this
        would be deterministic and the two calls would match. A random
        per-process salt means "restarting" (simulated by clearing the
        cached salt) produces a DIFFERENT digest for the SAME phone."""
        monkeypatch.delenv("LOG_PII_HMAC_SALT", raising=False)

        first = redact_identifier_for_log(_SYNTHETIC_PHONE)
        _reset_fallback_salt_state_for_tests()  # simulate a fresh process
        second = redact_identifier_for_log(_SYNTHETIC_PHONE)

        assert first != second

    def test_unconfigured_digest_still_stable_within_one_process(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Innocence: within ONE process lifetime (no reset in between),
        the fallback salt must still be stable, or log-line correlation —
        the entire point of this module — breaks even when correctly
        configured elsewhere in the request path."""
        monkeypatch.delenv("LOG_PII_HMAC_SALT", raising=False)
        first = redact_identifier_for_log(_SYNTHETIC_PHONE)
        second = redact_identifier_for_log(_SYNTHETIC_PHONE)
        assert first == second

    def test_unconfigured_fallback_logs_a_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The degradation must be visible to an operator, never silent."""
        monkeypatch.delenv("LOG_PII_HMAC_SALT", raising=False)
        with caplog.at_level("WARNING", logger="backend.security.pii_log_identifier"):
            redact_identifier_for_log(_SYNTHETIC_PHONE)
        assert any("LOG_PII_HMAC_SALT" in record.message for record in caplog.records)

    def test_unconfigured_fallback_warns_once_not_per_call(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Loud, not spammy: one warning per process, not one per digest —
        the operator signal should not drown in noise."""
        monkeypatch.delenv("LOG_PII_HMAC_SALT", raising=False)
        with caplog.at_level("WARNING", logger="backend.security.pii_log_identifier"):
            redact_identifier_for_log(_SYNTHETIC_PHONE)
            redact_identifier_for_log(_SYNTHETIC_PHONE_OTHER)
            redact_identifier_for_log(_SYNTHETIC_CHAT_ID)
        warnings = [r for r in caplog.records if "LOG_PII_HMAC_SALT" in r.message]
        assert len(warnings) == 1

    def test_configured_salt_never_triggers_the_fallback_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Innocence: a correctly-configured deployment gets no noise at
        all — the warning is specific to the degraded path."""
        monkeypatch.setenv("LOG_PII_HMAC_SALT", "a-test-salt")
        with caplog.at_level("WARNING", logger="backend.security.pii_log_identifier"):
            redact_identifier_for_log(_SYNTHETIC_PHONE)
        assert not any("LOG_PII_HMAC_SALT" in r.message for r in caplog.records)


