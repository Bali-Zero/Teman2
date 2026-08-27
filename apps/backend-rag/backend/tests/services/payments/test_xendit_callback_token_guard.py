"""A provider that can never verify a callback must not be constructible.

WHY. `verify_signature` rejects on
`not received or not hmac.compare_digest(received, self._callback_verification_token)`.
With an empty configured token that is EVERY input — measured 2026-08-27
against this class, including a header carrying an arbitrary value, because
`compare_digest(x, "")` is False for any non-empty x.

Nothing gets in, so this is not a security hole. It is a money hole:
`service_initializer.py` §5.7 armed the whole order lane on
`GARUDA_XENDIT_SECRET_KEY` alone while reading the callback token with a `""`
default. Setting one env var and forgetting the other opened checkout and made
every legitimate Xendit callback answer 401 — the customer really charged, the
order never leaving `awaiting_payment`, and nothing surfacing to them.

Guilt and innocence for both halves of that pair.
"""

from __future__ import annotations

import httpx
import pytest

from backend.services.payments.port import WebhookSignatureInvalid
from backend.services.payments.xendit import XenditFeeConfig, XenditPaymentProvider

_FEE = XenditFeeConfig(percentage_bps=350, fixed_idr=6000)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={})))


def _build(*, secret_key: str = "xnd_development_fake", token: str) -> XenditPaymentProvider:
    return XenditPaymentProvider(
        secret_key=secret_key,
        callback_verification_token=token,
        public_base_url="https://example.invalid",
        fee_config=_FEE,
        client=_client(),
    )


class TestTheConstructorRefusesAnUnverifiableProvider:
    @pytest.mark.parametrize("token", ["", " ", "\t", "\n  "])
    def test_an_empty_or_blank_callback_token_is_refused(self, token: str) -> None:
        """Blank, not just empty: `os.environ.get(...).strip()` yields `""` for
        a var set to whitespace, but a direct caller can still pass `" "`."""
        with pytest.raises(ValueError, match="callback_verification_token"):
            _build(token=token)

    def test_the_error_names_the_env_var_an_operator_must_set(self) -> None:
        """The message is the whole value of failing here rather than later.

        A bare `ValueError` would be swallowed by §5.7's `except Exception` and
        surface as one generic "wiring failed" line, leaving whoever armed the
        key to guess which half is missing.
        """
        with pytest.raises(ValueError) as exc:
            _build(token="")
        message = str(exc.value)
        assert "GARUDA_XENDIT_CALLBACK_TOKEN" in message
        assert "never advance" in message or "rejected" in message

    def test_a_real_token_still_constructs(self) -> None:
        """Innocence: the guard rejects the unusable case, not the usable one."""
        provider = _build(token="a-real-callback-token")
        assert provider is not None

    def test_the_sandbox_key_guard_is_unchanged(self) -> None:
        """The pre-existing half of the pair, pinned so this PR cannot have
        loosened it while adding the second."""
        with pytest.raises(ValueError, match="sandbox"):
            _build(secret_key="xnd_production_looks_real", token="a-real-callback-token")


class TestWhatTheEmptyTokenWouldHaveDone:
    """The behaviour the constructor guard now makes unreachable.

    Kept as a live test rather than a comment: it drives the REAL
    `verify_signature` against a provider whose token is emptied AFTER
    construction, so if someone ever relaxes the constructor guard, these
    assertions still describe exactly what they would be re-enabling.
    """

    @pytest.mark.parametrize(
        "headers",
        [
            {},
            {"x-callback-token": ""},
            {"x-callback-token": "anything"},
            {"X-Callback-Token": "anything"},
        ],
    )
    def test_every_callback_is_rejected_when_the_token_is_empty(
        self, headers: dict[str, str]
    ) -> None:
        provider = _build(token="placeholder-to-pass-the-guard")
        provider._callback_verification_token = ""  # the state §5.7 used to allow
        with pytest.raises(WebhookSignatureInvalid):
            provider.verify_signature(raw_body=b"{}", headers=headers)

    def test_a_correct_token_is_accepted_case_insensitively(self) -> None:
        """Innocence for the verifier itself: with a real token, the header is
        matched regardless of case.

        Collects what was accepted and asserts the exact set rather than
        relying on "no exception was raised" — a test whose only claim is the
        absence of a throw states nothing a reader (or a linter) can check, and
        would keep passing if `verify_signature` became a no-op.
        """
        provider = _build(token="real-token")
        casings = ("x-callback-token", "X-Callback-Token", "X-CALLBACK-TOKEN")
        accepted = []
        for header in casings:
            try:
                provider.verify_signature(raw_body=b"{}", headers={header: "real-token"})
            except WebhookSignatureInvalid:
                continue
            accepted.append(header)
        assert accepted == list(casings), (
            f"only {accepted} accepted out of {list(casings)} — HTTP header names are "
            "case-insensitive and Xendit's exact casing is not something to depend on"
        )
