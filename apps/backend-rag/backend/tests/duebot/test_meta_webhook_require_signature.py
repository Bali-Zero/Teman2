"""Cross-surface contract tests for ``settings.meta_webhook_require_signature``
(igverify lane, 2026-08-25).

This setting is the ONE explicitly named knob that decides fail-open vs
fail-closed behavior when a Meta webhook's app secret (``WHATSAPP_APP_SECRET``
/ ``INSTAGRAM_APP_SECRET``) is not configured. It defaults to ``False``,
which is BOTH surfaces' pre-existing behavior — this file exists to prove
that default changes nothing observable except a new WARNING log line, and
that flipping the setting to ``True`` is a real, working fail-closed switch
with no code change required.

This file does NOT re-prove HMAC correctness (that's
``test_webhook_signer.py`` and ``test_webhook_replay.py``, both left
green by this lane). It proves exactly two things, for BOTH surfaces:

  1. No secret configured + ``meta_webhook_require_signature=False``
     (default): the request is accepted (fail-open, unchanged from before
     this lane) AND a WARNING naming the surface is logged — "must never
     sit in that state quietly" is a log-observable property, not just a
     docstring claim.
  2. No secret configured + ``meta_webhook_require_signature=True``: the
     request is rejected with 401 (fail-closed) AND a WARNING is still
     logged (a different reason — the verifier's own `missing_secret`
     code — but the same visibility requirement).
"""

from __future__ import annotations

import logging

import pytest

from backend.app.core.config import settings
from backend.tests.duebot.conftest import DuebotHarness
from backend.tests.duebot.fake_meta_sender import (
    instagram_dm_payload,
    to_raw_body,
    whatsapp_text_payload,
)
from backend.tests.duebot.replay import instagram_replayer, whatsapp_replayer

_SURFACES = [
    pytest.param(
        "whatsapp",
        "whatsapp_app_secret",
        whatsapp_text_payload,
        whatsapp_replayer,
        "backend.app.routers.whatsapp_chat",
        id="whatsapp",
    ),
    pytest.param(
        "instagram",
        "instagram_app_secret",
        instagram_dm_payload,
        instagram_replayer,
        "backend.app.routers.instagram_chat",
        id="instagram",
    ),
]


@pytest.mark.parametrize(
    ("surface", "secret_attr", "payload_builder", "replayer_factory", "logger_name"),
    _SURFACES,
)
def test_missing_secret_skips_and_warns_when_require_signature_is_false(
    duebot: DuebotHarness,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    surface: str,
    secret_attr: str,
    payload_builder,
    replayer_factory,
    logger_name: str,
) -> None:
    """Default policy, unchanged by this lane: no secret configured means
    fail OPEN — but the skip is now LOUD. Before this lane, WhatsApp's
    skip was silent (no log line at all) and Instagram had no verifier to
    warn from in the first place.
    """
    monkeypatch.setattr(settings, secret_attr, None)
    monkeypatch.setattr(settings, "meta_webhook_require_signature", False)
    raw_body = to_raw_body(payload_builder())
    replayer = replayer_factory(duebot.client)

    with caplog.at_level(logging.WARNING, logger=logger_name):
        result = replayer.send_raw(raw_body, signature=None)

    assert result.status_code == 200, (
        f"{surface}: fail-open default must still accept the request"
    )
    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("SKIPPED" in msg and "fail-open" in msg for msg in warnings), (
        f"{surface}: expected a loud fail-open skip warning, got: {warnings}"
    )
    assert any(surface.upper() in msg for msg in warnings), (
        f"{surface}: warning must name the surface explicitly, got: {warnings}"
    )


@pytest.mark.parametrize(
    ("surface", "secret_attr", "payload_builder", "replayer_factory", "logger_name"),
    _SURFACES,
)
def test_missing_secret_rejects_and_warns_when_require_signature_is_true(
    duebot: DuebotHarness,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    surface: str,
    secret_attr: str,
    payload_builder,
    replayer_factory,
    logger_name: str,
) -> None:
    """Flip the knob: same missing secret, now fails CLOSED with a 401 —
    the owner's one-value production decision this lane exists to make
    possible without a code change, proved here as an actual rejection,
    not just documented as an intention.
    """
    monkeypatch.setattr(settings, secret_attr, None)
    monkeypatch.setattr(settings, "meta_webhook_require_signature", True)
    raw_body = to_raw_body(payload_builder())
    replayer = replayer_factory(duebot.client)

    with caplog.at_level(logging.WARNING, logger=logger_name):
        result = replayer.send_raw(raw_body, signature=None)

    assert result.status_code == 401, (
        f"{surface}: require_signature=True with no secret must fail closed"
    )
    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("missing_secret" in msg for msg in warnings), (
        f"{surface}: expected the missing_secret reason surfaced in a warning, got: {warnings}"
    )


@pytest.mark.parametrize(
    ("surface", "secret_attr", "payload_builder", "replayer_factory", "logger_name"),
    _SURFACES,
)
def test_require_signature_true_does_not_affect_a_correctly_signed_request(
    duebot: DuebotHarness,
    monkeypatch: pytest.MonkeyPatch,
    surface: str,
    secret_attr: str,
    payload_builder,
    replayer_factory,
    logger_name: str,
) -> None:
    """The knob only changes what happens when a secret is ABSENT. With a
    secret configured and a valid signature, both settings states must
    behave identically — flipping the flag is not supposed to be a second
    way to break a correctly configured deployment.
    """
    secret = f"igverify-require-signature-true-{surface}-secret"
    monkeypatch.setattr(settings, secret_attr, secret)
    monkeypatch.setattr(settings, "meta_webhook_require_signature", True)
    raw_body = to_raw_body(payload_builder())
    replayer = replayer_factory(duebot.client)

    result = replayer.send_signed(raw_body, secret)

    assert result.status_code == 200
