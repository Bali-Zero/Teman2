"""B2.4 — tests for `wa_completion_envelope.py` (design `B2-4-design.md` §1.2).

`encode_completion` is the honest daemon's only path onto the wire and is
tested for GUILT (raises on any input an honest run could never produce).
`decode_completion` is the untrusted-input boundary — the routing leg's
only view of what the daemon claims — and is tested for both INNOCENCE
(round-trips what an honest `encode_completion` produced) and GUILT (`None`
on every way a corrupt or forged wire can look). The guilt cases build
their own hand-forged payloads with a REAL mac computed independently of
the module under test (`_hand_seal` below, deliberately re-deriving the
same tiny HMAC construction rather than importing the module's private
helpers) — this proves `decode_completion` enforces its semantic rules
(verdict/votes/answer shape) even when the MAC itself is unforged, not
merely that the MAC check works.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from backend.services.integrations.wa_completion_envelope import (
    ENVELOPE_VERSION,
    SupportCompletion,
    decode_completion,
    encode_completion,
)
from backend.services.rag.agentic._support_signal import SupportVerdict

KEY = "wa-broker-secret-test-key-0001"
OTHER_KEY = "a-completely-different-key-9999"
PACKAGE_HASH = "deadbeef" * 8
OTHER_HASH = "cafebabe" * 8
JUDGE = "codex:gpt-5.6-terra"

S = SupportVerdict.SUPPORTED
N = SupportVerdict.NOT_SUPPORTED
U = SupportVerdict.UNKNOWN
X = SupportVerdict.UNAVAILABLE


def _canonical(obj: dict[str, object]) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hand_seal(key: str, body: dict[str, object]) -> str:
    """Independent re-derivation of the module's own MAC construction, used
    to hand-forge payloads that are semantically illegal but MAC-VALID —
    the only way to prove `decode_completion` rejects them on their own
    merits rather than on a MAC failure that would mask the real check."""
    derived = hmac.new(key.encode("utf-8"), b"wa-completion-envelope/v1", hashlib.sha256).digest()
    mac = hmac.new(derived, _canonical(body).encode("utf-8"), hashlib.sha256).hexdigest()
    return _canonical({**body, "mac": mac})


def _valid_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "v": ENVELOPE_VERSION,
        "package_hash": PACKAGE_HASH,
        "verdict": S.value,
        "votes": [S.value, S.value, N.value],
        "judge": JUDGE,
        "answer": "the answer",
    }
    body.update(overrides)
    return body


class TestRoundTrip:
    def test_supported_round_trip_unicode_and_json_looking_answer_byte_exact(self) -> None:
        answer = '{"looks": "like JSON", "but": "is text — café, 日本語"}'
        envelope = encode_completion(
            key=KEY,
            package_hash=PACKAGE_HASH,
            verdict=S,
            votes=(S, S, N),
            judge=JUDGE,
            answer=answer,
        )
        decoded = decode_completion(envelope, key=KEY, package_hash=PACKAGE_HASH)
        assert decoded == SupportCompletion(verdict=S, votes=(S, S, N), judge=JUDGE, answer=answer)

    def test_not_supported_round_trip(self) -> None:
        envelope = encode_completion(
            key=KEY, package_hash=PACKAGE_HASH, verdict=N, votes=(N, N, S), judge=JUDGE, answer=None
        )
        decoded = decode_completion(envelope, key=KEY, package_hash=PACKAGE_HASH)
        assert decoded == SupportCompletion(verdict=N, votes=(N, N, S), judge=JUDGE, answer=None)

    def test_unknown_round_trip(self) -> None:
        envelope = encode_completion(
            key=KEY, package_hash=PACKAGE_HASH, verdict=U, votes=(U, U, S), judge=JUDGE, answer=None
        )
        decoded = decode_completion(envelope, key=KEY, package_hash=PACKAGE_HASH)
        assert decoded == SupportCompletion(verdict=U, votes=(U, U, S), judge=JUDGE, answer=None)

    def test_innocence_emoji_and_non_latin_script_answer_round_trips(self) -> None:
        """The `_decode` backstop (added for the crash-oracle fixes below)
        must never swallow an honest, merely-exotic answer — proper
        multi-codepoint unicode (emoji, non-Latin script) is NOT the same
        class of input as a lone surrogate or pathological nesting."""
        answer = "Ya, KITAS bisa 😀🇮🇩 — 一年間有効です, действительно один год."
        envelope = encode_completion(
            key=KEY,
            package_hash=PACKAGE_HASH,
            verdict=S,
            votes=(S, S, N),
            judge=JUDGE,
            answer=answer,
        )
        decoded = decode_completion(envelope, key=KEY, package_hash=PACKAGE_HASH)
        assert decoded == SupportCompletion(verdict=S, votes=(S, S, N), judge=JUDGE, answer=answer)


class TestEncodeGuilt:
    def test_raises_on_empty_key(self) -> None:
        with pytest.raises(ValueError):
            encode_completion(
                key="",
                package_hash=PACKAGE_HASH,
                verdict=S,
                votes=(S, S, N),
                judge=JUDGE,
                answer="a",
            )

    def test_raises_on_empty_package_hash(self) -> None:
        with pytest.raises(ValueError):
            encode_completion(
                key=KEY, package_hash="", verdict=S, votes=(S, S, N), judge=JUDGE, answer="a"
            )

    def test_raises_on_unavailable_verdict(self) -> None:
        """UNAVAILABLE is never enveloped — it travels as an error_class."""
        with pytest.raises(ValueError):
            encode_completion(
                key=KEY,
                package_hash=PACKAGE_HASH,
                verdict=X,
                votes=(X, X, X),
                judge=JUDGE,
                answer=None,
            )

    def test_raises_on_wrong_vote_count(self) -> None:
        with pytest.raises(ValueError):
            encode_completion(
                key=KEY, package_hash=PACKAGE_HASH, verdict=S, votes=(S, S), judge=JUDGE, answer="a"
            )

    def test_raises_on_inconsistent_majority(self) -> None:
        """votes S,N,N majority to N — claiming SUPPORTED is a lie the
        function refuses to seal."""
        with pytest.raises(ValueError):
            encode_completion(
                key=KEY,
                package_hash=PACKAGE_HASH,
                verdict=S,
                votes=(S, N, N),
                judge=JUDGE,
                answer="a",
            )

    def test_raises_on_bad_judge_shape(self) -> None:
        with pytest.raises(ValueError):
            encode_completion(
                key=KEY,
                package_hash=PACKAGE_HASH,
                verdict=S,
                votes=(S, S, N),
                judge="openai:gpt-4",
                answer="a",
            )

    def test_raises_on_blank_answer_for_supported(self) -> None:
        with pytest.raises(ValueError):
            encode_completion(
                key=KEY,
                package_hash=PACKAGE_HASH,
                verdict=S,
                votes=(S, S, N),
                judge=JUDGE,
                answer="   ",
            )

    def test_raises_on_null_answer_for_supported(self) -> None:
        with pytest.raises(ValueError):
            encode_completion(
                key=KEY,
                package_hash=PACKAGE_HASH,
                verdict=S,
                votes=(S, S, N),
                judge=JUDGE,
                answer=None,
            )

    def test_raises_on_answer_present_for_not_supported(self) -> None:
        with pytest.raises(ValueError):
            encode_completion(
                key=KEY,
                package_hash=PACKAGE_HASH,
                verdict=N,
                votes=(N, N, S),
                judge=JUDGE,
                answer="should not be here",
            )


class TestDecodeGuilt:
    def test_none_key(self) -> None:
        envelope = encode_completion(
            key=KEY, package_hash=PACKAGE_HASH, verdict=S, votes=(S, S, N), judge=JUDGE, answer="a"
        )
        assert decode_completion(envelope, key=None, package_hash=PACKAGE_HASH) is None

    def test_empty_key(self) -> None:
        envelope = encode_completion(
            key=KEY, package_hash=PACKAGE_HASH, verdict=S, votes=(S, S, N), judge=JUDGE, answer="a"
        )
        assert decode_completion(envelope, key="", package_hash=PACKAGE_HASH) is None

    def test_none_text(self) -> None:
        assert decode_completion(None, key=KEY, package_hash=PACKAGE_HASH) is None

    def test_wrong_key(self) -> None:
        envelope = encode_completion(
            key=KEY, package_hash=PACKAGE_HASH, verdict=S, votes=(S, S, N), judge=JUDGE, answer="a"
        )
        assert decode_completion(envelope, key=OTHER_KEY, package_hash=PACKAGE_HASH) is None

    def test_hash_mismatch(self) -> None:
        """The envelope is internally consistent and authentically MAC'd —
        just not for THIS leg's package."""
        envelope = encode_completion(
            key=KEY, package_hash=PACKAGE_HASH, verdict=S, votes=(S, S, N), judge=JUDGE, answer="a"
        )
        assert decode_completion(envelope, key=KEY, package_hash=OTHER_HASH) is None

    @pytest.mark.parametrize("field", ["answer", "verdict", "votes", "judge"])
    def test_tampered_field_invalidates_the_mac(self, field: str) -> None:
        envelope = encode_completion(
            key=KEY, package_hash=PACKAGE_HASH, verdict=S, votes=(S, S, N), judge=JUDGE, answer="a"
        )
        obj = json.loads(envelope)
        obj[field] = "TAMPERED" if field != "votes" else ["TAMPERED", "TAMPERED", "TAMPERED"]
        assert decode_completion(_canonical(obj), key=KEY, package_hash=PACKAGE_HASH) is None

    def test_mac_removed(self) -> None:
        envelope = encode_completion(
            key=KEY, package_hash=PACKAGE_HASH, verdict=S, votes=(S, S, N), judge=JUDGE, answer="a"
        )
        obj = json.loads(envelope)
        del obj["mac"]
        assert decode_completion(_canonical(obj), key=KEY, package_hash=PACKAGE_HASH) is None

    def test_extra_key(self) -> None:
        envelope = encode_completion(
            key=KEY, package_hash=PACKAGE_HASH, verdict=S, votes=(S, S, N), judge=JUDGE, answer="a"
        )
        obj = json.loads(envelope)
        obj["extra"] = "unexpected"
        assert decode_completion(_canonical(obj), key=KEY, package_hash=PACKAGE_HASH) is None

    def test_missing_key(self) -> None:
        envelope = encode_completion(
            key=KEY, package_hash=PACKAGE_HASH, verdict=S, votes=(S, S, N), judge=JUDGE, answer="a"
        )
        obj = json.loads(envelope)
        del obj["judge"]
        assert decode_completion(_canonical(obj), key=KEY, package_hash=PACKAGE_HASH) is None

    def test_raw_non_json_text(self) -> None:
        assert decode_completion("not json at all {{{", key=KEY, package_hash=PACKAGE_HASH) is None

    def test_json_array(self) -> None:
        assert decode_completion("[1, 2, 3]", key=KEY, package_hash=PACKAGE_HASH) is None

    def test_hand_forged_with_plausible_but_wrong_mac(self) -> None:
        body = _valid_body()
        forged = _canonical({**body, "mac": "0" * 64})
        assert decode_completion(forged, key=KEY, package_hash=PACKAGE_HASH) is None

    def test_supported_with_null_answer_rejected_even_with_a_valid_mac(self) -> None:
        body = _valid_body(verdict=S.value, votes=[S.value, S.value, N.value], answer=None)
        sealed = _hand_seal(KEY, body)
        assert decode_completion(sealed, key=KEY, package_hash=PACKAGE_HASH) is None

    def test_not_supported_with_an_answer_rejected_even_with_a_valid_mac(self) -> None:
        body = _valid_body(
            verdict=N.value, votes=[N.value, N.value, S.value], answer="should be null"
        )
        sealed = _hand_seal(KEY, body)
        assert decode_completion(sealed, key=KEY, package_hash=PACKAGE_HASH) is None

    def test_majority_mismatch_rejected_even_with_a_valid_mac(self) -> None:
        """votes S,N,N truly majority to N; claiming SUPPORTED in the
        verdict field is a lie decode must catch on its own, independent of
        `encode_completion` ever having refused to produce it."""
        body = _valid_body(verdict=S.value, votes=[S.value, N.value, N.value], answer="a")
        sealed = _hand_seal(KEY, body)
        assert decode_completion(sealed, key=KEY, package_hash=PACKAGE_HASH) is None

    @pytest.mark.parametrize("bad_version", [True, 2])
    def test_bad_version_rejected_even_with_a_valid_mac(self, bad_version: object) -> None:
        body = _valid_body(v=bad_version)
        sealed = _hand_seal(KEY, body)
        assert decode_completion(sealed, key=KEY, package_hash=PACKAGE_HASH) is None

    # -- Dux review: decode_completion must NEVER raise, even on the shapes
    # -- below that an old, un-provisioned daemon could forward as raw,
    # -- prompt-injectable model text. Each of these raised past the
    # -- `_decode` boundary before the `try/except Exception` backstop was
    # -- added; every assertion below is only meaningful if the call
    # -- returns `None` INSTEAD of propagating an exception through pytest.

    def test_non_ascii_mac_returns_none_without_raising(self) -> None:
        """`hmac.compare_digest` raises `TypeError` comparing `str` values
        when either side carries a non-ASCII character — an attacker-
        controlled `mac` field reaches exactly that comparison."""
        body = _valid_body()
        forged = _canonical({**body, "mac": "é" * 64})
        assert decode_completion(forged, key=KEY, package_hash=PACKAGE_HASH) is None

    def test_deeply_nested_json_returns_none_without_raising(self) -> None:
        """70k unmatched '[' is enough to exhaust `json.loads`'s recursive
        descent and raise `RecursionError` (measured against this repo's
        own venv — CPython 3.11 recurses per nesting level here)."""
        forged = "[" * 70_000
        assert decode_completion(forged, key=KEY, package_hash=PACKAGE_HASH) is None

    def test_lone_surrogate_in_answer_returns_none_without_raising(self) -> None:
        """A lone UTF-16 surrogate is a valid Python `str` character (JSON's
        `\\uXXXX` escape does not require a valid pair) but cannot be
        UTF-8-encoded — `_canonical(body).encode('utf-8')` hits it during
        MAC verification, before the answer's own content is ever checked."""
        body = _valid_body(answer="\ud800")
        forged = _canonical({**body, "mac": "0" * 64})
        assert decode_completion(forged, key=KEY, package_hash=PACKAGE_HASH) is None

    def test_lone_surrogate_in_judge_returns_none_without_raising(self) -> None:
        body = _valid_body(judge="codex:\ud800")
        forged = _canonical({**body, "mac": "0" * 64})
        assert decode_completion(forged, key=KEY, package_hash=PACKAGE_HASH) is None

    def test_lone_surrogate_in_mac_returns_none_without_raising(self) -> None:
        """`mac` is excluded from the MAC's own body, so a surrogate here
        survives past `_canonical(body)` and is only hit by `mac.encode(...)`
        in the (now byte-based) comparison itself."""
        body = _valid_body()
        forged = _canonical({**body, "mac": "\ud800" * 8})
        assert decode_completion(forged, key=KEY, package_hash=PACKAGE_HASH) is None
