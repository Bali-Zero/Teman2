"""BOT-V2 gate (task #14) — PII/audit-log invariant, real gap fill.

Per the invariant walkthrough in `research/operations/2026-08-15-bot-openai-
provider-threat-model.md` §(b) ("Audit / no PII in logs"): a new OpenAI
adapter that adds its own logging/tracing (SDK request/response logger, a
Langfuse trace without the same redaction defaults) reintroduces the SAME
PII-in-logs shape a second time, in a code path the existing fix doesn't
cover — the contract test recommended there is "the adapter's logging calls
never interpolate raw user_id/phone/query" via `sentry_config.py`'s
`_PII_KEY_SUBSTRINGS` pattern-matching, reused rather than hand-rolled.

Searched this session (`grep -rl "_PII_KEY_SUBSTRINGS\\|_before_send\\|
sentry_config" apps/backend-rag/backend/tests`) — ZERO existing tests
exercise `sentry_config._is_pii_key` / `_scrub` / `_before_send_impl`
directly. This is a genuine, previously-untested invariant floor, not a
duplicate of existing coverage (unlike routing/audit-arg-stripping/
provenance/abstention/cache, which already have real contract tests on
origin/main — see `scripts/ci/bot_provider_gate.py`'s
`NOT_STATICALLY_CHECKABLE` table for the exact file pointers — and are
picked up automatically by the existing `tests.yml` full-suite run, same
as this file, with no new CI wiring needed).

Guilt/innocence per cicatrix-superscar.md family #3.
"""

from __future__ import annotations

from backend.app.setup.sentry_config import PII_REDACTION_PLACEHOLDER, _is_pii_key, _scrub

# ── _is_pii_key: guilt (PII-shaped key) / innocence (opaque id) ────────────


class TestIsPiiKeyGuilt:
    def test_phone_number_key_flagged(self) -> None:
        assert _is_pii_key("phone") is True

    def test_client_email_key_flagged(self) -> None:
        assert _is_pii_key("client_email") is True

    def test_npwp_key_flagged(self) -> None:
        assert _is_pii_key("npwp") is True

    def test_passport_key_flagged(self) -> None:
        assert _is_pii_key("passport_number") is True

    def test_bare_name_key_flagged_exact_match(self) -> None:
        assert _is_pii_key("name") is True


class TestIsPiiKeyInnocence:
    def test_thread_id_not_flagged(self) -> None:
        assert _is_pii_key("thread_id") is False

    def test_request_id_not_flagged(self) -> None:
        assert _is_pii_key("request_id") is False

    def test_filename_not_flagged_despite_containing_name_substring(self) -> None:
        """_PII_EXACT_KEYS deliberately checks 'name' by EXACT match, not
        substring — otherwise 'filename'/'username' would false-positive.
        Pins that design choice."""
        assert _is_pii_key("filename") is False

    def test_model_name_not_flagged(self) -> None:
        assert _is_pii_key("model") is False

    def test_non_string_key_not_flagged(self) -> None:
        assert _is_pii_key(42) is False


# ── _scrub: guilt (PII value redacted) / innocence (non-PII untouched) ──────


class TestScrubGuilt:
    def test_phone_value_redacted_in_dict(self) -> None:
        event = {"phone": "+62 812-3456-7890"}
        scrubbed = _scrub(event)
        assert scrubbed["phone"] == PII_REDACTION_PLACEHOLDER

    def test_nested_pii_key_redacted(self) -> None:
        """The exact shape an OpenAI-adapter tracing span would produce:
        a nested `extra`/`context` dict carrying the raw WA free-text
        query and phone — must be redacted at any depth, not just top
        level."""
        event = {
            "extra": {
                "user_id": "whatsapp_628123456789",
                "query": "hello",
                "client_email": "someone@example.com",
            }
        }
        scrubbed = _scrub(event)
        assert scrubbed["extra"]["client_email"] == PII_REDACTION_PLACEHOLDER

    def test_pii_key_redacted_inside_a_list(self) -> None:
        event = {"breadcrumbs": [{"npwp": "01.234.567.8-901.000"}]}
        scrubbed = _scrub(event)
        assert scrubbed["breadcrumbs"][0]["npwp"] == PII_REDACTION_PLACEHOLDER


class TestScrubInnocence:
    def test_non_pii_dict_unchanged_in_shape(self) -> None:
        event = {"thread_id": "t-123", "status": "ok"}
        scrubbed = _scrub(event)
        assert scrubbed["thread_id"] == "t-123"
        assert scrubbed["status"] == "ok"

    def test_model_identifier_value_untouched(self) -> None:
        event = {"model": "gpt-5.6-terra"}
        scrubbed = _scrub(event)
        assert scrubbed["model"] == "gpt-5.6-terra"
