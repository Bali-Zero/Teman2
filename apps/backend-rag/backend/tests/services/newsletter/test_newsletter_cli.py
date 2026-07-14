"""Tests for newsletter_cli — recipients default fallback + --daily arg parsing.

2026-07-14: NEWSLETTER_RECIPIENTS was never set in prod, so the cron always
skipped with "no_recipients" (permanent no-op). These tests pin the fix:
a default internal recipient, and the new --daily dispatch flag.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from backend.services.newsletter.newsletter_cli import (
    DEFAULT_RECIPIENT,
    _parse_args,
    _recipients_from_env,
)


@pytest.fixture(autouse=True)
def _clean_env():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("NEWSLETTER_RECIPIENTS", None)
        os.environ.pop("NEWSLETTER_SUBJECT_PREFIX", None)
        yield


def test_recipients_default_to_internal_owner_when_unset():
    assert _recipients_from_env() == [DEFAULT_RECIPIENT]


def test_recipients_default_is_balizero_domain():
    assert DEFAULT_RECIPIENT.endswith("@balizero.com")


def test_recipients_env_overrides_default():
    os.environ["NEWSLETTER_RECIPIENTS"] = "a@balizero.com,b@balizero.com"
    assert _recipients_from_env() == ["a@balizero.com", "b@balizero.com"]


def test_recipients_env_whitespace_only_falls_back_to_default():
    os.environ["NEWSLETTER_RECIPIENTS"] = "   ,  ,"
    assert _recipients_from_env() == [DEFAULT_RECIPIENT]


def test_recipients_env_trims_whitespace():
    os.environ["NEWSLETTER_RECIPIENTS"] = " a@balizero.com , b@balizero.com "
    assert _recipients_from_env() == ["a@balizero.com", "b@balizero.com"]


# ── --daily flag ─────────────────────────────────────────────────


def test_parse_args_defaults_to_weekly():
    args = _parse_args([])
    assert args.daily is False
    assert args.subject_prefix == ""


def test_parse_args_daily_flag():
    args = _parse_args(["--daily"])
    assert args.daily is True


def test_parse_args_subject_prefix_flag():
    args = _parse_args(["--daily", "--subject-prefix", "[TEST] "])
    assert args.subject_prefix == "[TEST] "


def test_parse_args_subject_prefix_from_env():
    os.environ["NEWSLETTER_SUBJECT_PREFIX"] = "[TEST] "
    args = _parse_args(["--daily"])
    assert args.subject_prefix == "[TEST] "
