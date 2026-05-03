"""
Tests for settings.admin_emails_set and settings.notification_cc_emails_list.

Audit 2026-04-18 HIGH-7: admin email allowlist is now read from ADMIN_EMAILS
env var instead of being hardcoded across 8+ routers. These tests verify the
parsing rules so a malformed env var does not silently open the allowlist.
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest


@pytest.fixture(autouse=True)
def _restore_real_config_module():
    """Ensure this suite always sees the real backend.app.core.config.

    The `unit/routers/conftest.py` replaces sys.modules["backend.app.core.config"]
    with a FakeSettings stub. When that conftest runs before this file (which
    happens whenever pytest collects both paths), our tests would read the
    stub instead of the real Settings. We drop whatever is installed and
    reload, then save/restore on teardown so other suites are unaffected.
    """
    saved = sys.modules.get("backend.app.core.config")
    sys.modules.pop("backend.app.core.config", None)
    real_module = importlib.import_module("backend.app.core.config")
    try:
        yield real_module
    finally:
        if saved is not None:
            sys.modules["backend.app.core.config"] = saved


def _fresh_settings(env_vars: dict[str, str | None]):
    """Build a fresh Settings instance with env overrides."""
    # The autouse fixture has already restored the real config module, so
    # importing it here gives us the real Settings class.
    module = importlib.import_module("backend.app.core.config")
    saved: dict[str, str | None] = {}
    try:
        for k, v in env_vars.items():
            saved[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return module.Settings()
    finally:
        for k, old in saved.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old


class TestAdminEmailsFallback:
    def test_unset_env_returns_historical_fallback(self) -> None:
        s = _fresh_settings({"ADMIN_EMAILS": None})
        emails = s.admin_emails_set
        assert "zero@balizero.com" in emails
        assert "asya@balizero.com" in emails
        assert "antonellosiano@balizero.com" in emails
        assert len(emails) == 3

    def test_empty_string_falls_back(self) -> None:
        s = _fresh_settings({"ADMIN_EMAILS": ""})
        assert "zero@balizero.com" in s.admin_emails_set

    def test_only_whitespace_falls_back(self) -> None:
        s = _fresh_settings({"ADMIN_EMAILS": "  ,  ,  "})
        # All parts empty after strip() → fallback kicks in.
        assert "zero@balizero.com" in s.admin_emails_set


class TestAdminEmailsParsing:
    def test_single_email_overrides_fallback(self) -> None:
        s = _fresh_settings({"ADMIN_EMAILS": "override@example.com"})
        assert s.admin_emails_set == frozenset({"override@example.com"})
        assert "zero@balizero.com" not in s.admin_emails_set

    def test_multiple_emails(self) -> None:
        s = _fresh_settings({"ADMIN_EMAILS": "a@x.com,b@x.com,c@x.com"})
        assert s.admin_emails_set == frozenset({"a@x.com", "b@x.com", "c@x.com"})

    def test_whitespace_is_trimmed(self) -> None:
        s = _fresh_settings({"ADMIN_EMAILS": "  a@x.com , b@x.com  "})
        assert s.admin_emails_set == frozenset({"a@x.com", "b@x.com"})

    def test_lowercase_normalised(self) -> None:
        s = _fresh_settings({"ADMIN_EMAILS": "ZERO@Balizero.COM,Asya@BaliZero.com"})
        assert s.admin_emails_set == frozenset({"zero@balizero.com", "asya@balizero.com"})

    def test_duplicate_emails_deduped(self) -> None:
        s = _fresh_settings({"ADMIN_EMAILS": "a@x.com,a@x.com,A@X.COM"})
        assert s.admin_emails_set == frozenset({"a@x.com"})

    def test_result_is_frozenset(self) -> None:
        s = _fresh_settings({"ADMIN_EMAILS": "a@x.com"})
        with pytest.raises((AttributeError, TypeError)):
            s.admin_emails_set.add("b@x.com")  # type: ignore[attr-defined]


class TestNotificationCcEmails:
    def test_unset_returns_empty_tuple(self) -> None:
        s = _fresh_settings({"NOTIFICATION_CC_EMAILS": None})
        assert s.notification_cc_emails_list == ()

    def test_parses_comma_separated(self) -> None:
        s = _fresh_settings({"NOTIFICATION_CC_EMAILS": "a@x.com,b@x.com"})
        assert s.notification_cc_emails_list == ("a@x.com", "b@x.com")

    def test_lowercased_and_trimmed(self) -> None:
        s = _fresh_settings({"NOTIFICATION_CC_EMAILS": " A@X.COM , B@X.com "})
        assert s.notification_cc_emails_list == ("a@x.com", "b@x.com")


class TestHrNotificationEmail:
    def test_unset_uses_asya_default(self) -> None:
        s = _fresh_settings({"HR_NOTIFICATION_EMAIL": None})
        assert s.hr_notification_email == "asya@balizero.com"

    def test_env_override(self) -> None:
        s = _fresh_settings({"HR_NOTIFICATION_EMAIL": "hr-team@example.com"})
        assert s.hr_notification_email == "hr-team@example.com"


class TestAdminSetConsumers:
    """The real check — do the helpers that depend on settings.admin_emails_set
    still behave correctly when the env var is unset vs. overridden?"""

    def test_is_crm_admin_honours_override(self) -> None:
        s = _fresh_settings({"ADMIN_EMAILS": "new-admin@example.com"})
        # Swap the module-level `settings` so helpers reading it see the override.
        import backend.app.utils.crm_utils as crm_utils

        original = crm_utils.settings
        try:
            crm_utils.settings = s
            assert crm_utils.is_crm_admin({"email": "new-admin@example.com"}) is True
            # Old hardcoded admin is no longer an admin when override takes effect
            # (unless it was in the override set — which it isn't).
            assert (
                crm_utils.is_crm_admin({"email": "zero@balizero.com"}) is False
            ), "override must replace, not extend, the historical fallback"
        finally:
            crm_utils.settings = original

    def test_hr_admin_union_preserves_ruslana(self) -> None:
        """Domain-specific extras (Ruslana) survive an ADMIN_EMAILS override."""
        s = _fresh_settings({"ADMIN_EMAILS": "new-admin@example.com"})
        import backend.app.utils.hr_utils as hr_utils

        original = hr_utils.settings
        try:
            hr_utils.settings = s
            emails = hr_utils._hr_admin_emails()
            assert "ruslana@balizero.com" in emails
            assert "new-admin@example.com" in emails
        finally:
            hr_utils.settings = original
