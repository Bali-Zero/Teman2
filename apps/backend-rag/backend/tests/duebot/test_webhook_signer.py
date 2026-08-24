"""Proves the B6a signer produces signatures the REAL production verifier
accepts (GREEN), and — the mandatory RED case — that a body tampered by
one byte after signing is REJECTED by that same verifier.

``backend.app.routers.whatsapp_chat._verify_whatsapp_signature`` is
imported and called completely unmodified in every test below — nothing in
this file patches it. That is the entire point: this is not "the harness
trusts its own signer", it is "the production verifier agrees with the
harness's signer on the GREEN case and disagrees with it on the RED case".
"""

from __future__ import annotations

import json

import pytest

from backend.app.core.config import settings
from backend.app.routers.whatsapp_chat import _verify_whatsapp_signature
from backend.tests.duebot.fake_meta_sender import (
    load_static_payload,
    to_raw_body,
    whatsapp_text_payload,
)
from backend.tests.duebot.webhook_signer import (
    malformed_signature_header,
    sign_payload,
    tamper,
)

APP_SECRET = "harness-test-app-secret-do-not-use-in-prod"


@pytest.fixture(autouse=True)
def _configured_app_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_verify_whatsapp_signature`` short-circuits to True ("dev mode")
    when ``settings.whatsapp_app_secret`` is falsy — which it is by
    default in the test environment (not set in
    ``backend/tests/conftest.py``). Every test in this file needs the real
    HMAC comparison to actually run, so this fixture arms it.
    """
    monkeypatch.setattr(settings, "whatsapp_app_secret", APP_SECRET)


def test_verifier_short_circuits_when_no_secret_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Documents the branch the autouse fixture above exists to bypass —
    without an app secret, ANY body/signature pair (including a garbage
    header) passes. This is intentional "dev mode" behavior in the
    production code, not a bug this harness should hide.
    """
    monkeypatch.setattr(settings, "whatsapp_app_secret", None)
    raw_body = to_raw_body(whatsapp_text_payload())

    assert _verify_whatsapp_signature(raw_body, "sha256=not-even-hex") is True
    assert _verify_whatsapp_signature(raw_body, None) is True


def test_valid_signature_over_exact_raw_bytes_is_accepted() -> None:
    """GREEN case: sign the exact bytes, verify the exact same bytes."""
    raw_body = to_raw_body(whatsapp_text_payload())
    signature = sign_payload(raw_body, APP_SECRET)

    assert _verify_whatsapp_signature(raw_body, signature) is True


def test_tampered_body_is_rejected_by_the_real_verifier() -> None:
    """RED case (mandatory per the B6a mandate): flip ONE byte of the body
    AFTER signing it, and confirm the production verifier rejects the
    result. This is the test that proves the harness does not merely
    trust its own signer — the PRODUCTION function disagrees with a body
    that was not the one that got signed.
    """
    raw_body = to_raw_body(whatsapp_text_payload())
    signature = sign_payload(raw_body, APP_SECRET)  # signed for the ORIGINAL body

    tampered_body = tamper(raw_body)
    assert tampered_body != raw_body, "tamper() must actually change the body"
    assert len(tampered_body) == len(raw_body), (
        "same length — proves rejection isn't just a length check catching a truncation"
    )

    assert _verify_whatsapp_signature(tampered_body, signature) is False


def test_tampering_every_byte_position_is_rejected() -> None:
    """The RED case at every offset, not just one lucky/unlucky byte —
    HMAC-SHA256 has no "safe" position to flip a bit.
    """
    raw_body = to_raw_body(whatsapp_text_payload(text="probe"))
    signature = sign_payload(raw_body, APP_SECRET)

    for index in range(len(raw_body)):
        tampered = tamper(raw_body, byte_index=index)
        assert _verify_whatsapp_signature(tampered, signature) is False, (
            f"byte {index} tamper should have been rejected"
        )


def test_wrong_secret_is_rejected() -> None:
    raw_body = to_raw_body(whatsapp_text_payload())
    signature = sign_payload(raw_body, "a-completely-different-app-secret")

    assert _verify_whatsapp_signature(raw_body, signature) is False


def test_missing_header_is_rejected() -> None:
    raw_body = to_raw_body(whatsapp_text_payload())

    assert _verify_whatsapp_signature(raw_body, None) is False


def test_malformed_sha256_prefix_is_rejected() -> None:
    """The header value is a correctly-computed digest, just missing its
    ``sha256=`` prefix (research capture §5.2: "malformed sha256= value").
    """
    raw_body = to_raw_body(whatsapp_text_payload())
    bad_header = malformed_signature_header(raw_body, APP_SECRET)

    assert not bad_header.startswith("sha256=")
    assert _verify_whatsapp_signature(raw_body, bad_header) is False


def test_signature_over_reserialized_json_body_does_not_match() -> None:
    """The classic silent-failure case named in the B6a mandate: sign the
    canonical bytes, then verify against a DIFFERENT (but semantically
    identical) re-serialization of the same logical payload. Meta signs
    the bytes it actually sent — a verifier or replayer that reconstructs
    the body from the parsed dict and re-dumps it can produce different
    bytes (whitespace, indentation) and silently fail. This forces a
    genuine encoding difference — compact vs. pretty-printed — rather
    than relying on dict key-ordering luck.
    """
    payload = whatsapp_text_payload()
    raw_body = to_raw_body(payload)  # compact: json.dumps(payload, ensure_ascii=False)
    signature = sign_payload(raw_body, APP_SECRET)

    reserialized = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    assert reserialized != raw_body, "the two encodings must actually differ for this test to mean anything"

    assert _verify_whatsapp_signature(reserialized, signature) is False


def test_unicode_body_signs_and_verifies() -> None:
    """Non-ASCII text in the message body — the signer must hash the raw
    UTF-8 bytes, not some ASCII-escaped intermediate representation.
    """
    raw_body = to_raw_body(whatsapp_text_payload(text="Halo, apa kabar? 你好 🙏"))
    signature = sign_payload(raw_body, APP_SECRET)

    assert _verify_whatsapp_signature(raw_body, signature) is True


def test_oversized_body_still_signs_and_verifies() -> None:
    """A large body (long conversation history, big attachment metadata)
    must not silently truncate anywhere in the sign/verify path.
    """
    raw_body = to_raw_body(whatsapp_text_payload(text="A" * 200_000))
    signature = sign_payload(raw_body, APP_SECRET)

    assert _verify_whatsapp_signature(raw_body, signature) is True


def test_sign_payload_rejects_non_bytes_input() -> None:
    """A str/dict passed to sign_payload is almost always the
    re-serialization bug this module exists to prevent — fail loudly, not
    silently encode something on the caller's behalf.
    """
    with pytest.raises(TypeError):
        sign_payload(json.dumps({"a": 1}), APP_SECRET)  # type: ignore[arg-type]


def test_tamper_rejects_empty_body() -> None:
    with pytest.raises(ValueError):
        tamper(b"")


@pytest.mark.parametrize(
    "fixture_name",
    [
        "whatsapp_text.json",
        "whatsapp_image.json",
        "whatsapp_status.json",
        "duplicate_batch.json",
    ],
)
def test_static_fixture_files_round_trip_through_signer(fixture_name: str) -> None:
    """Every checked-in ``payloads/*.json`` fixture is a valid, signable,
    verifiable raw body — not just the freshly-built ones from
    ``fake_meta_sender``'s builder functions.
    """
    raw_body = load_static_payload(fixture_name)
    signature = sign_payload(raw_body, APP_SECRET)

    assert _verify_whatsapp_signature(raw_body, signature) is True
