"""Pins the python-jose -> PyJWT migration: what each decode accepts and rejects.

Every case was measured against python-jose 3.5.0 and PyJWT 2.15.1 side by side.
The shared policy is `JWT_DECODE_OPTIONS`; the last tests keep every production
call site on it and keep python-jose out of the tree.
"""

import re
import time
from pathlib import Path

import jwt
import pytest

from backend.app.utils.jwt_decode import JWT_DECODE_OPTIONS, decode_jwt

_KEY = "k" * 48
_BACKEND = Path(__file__).resolve().parents[4]


def _token(claims: dict, key: str = _KEY, algorithm: str = "HS256") -> str:
    return jwt.encode(claims, key, algorithm=algorithm)


def _decode(token: str, key: str = _KEY) -> dict:
    return decode_jwt(token, key, algorithms=["HS256"])


def _exp(seconds: int = 60) -> int:
    return int(time.time()) + seconds


def test_encode_returns_str():
    assert isinstance(_token({"exp": _exp()}), str)


def test_round_trip_keeps_claims():
    assert _decode(_token({"exp": _exp(), "sub": "u1", "email": "a@b.co"}))["sub"] == "u1"


def test_expired_token_is_rejected():
    with pytest.raises(jwt.ExpiredSignatureError):
        _decode(_token({"exp": _exp(-5)}))


def test_exp_boundary_matches_python_jose(monkeypatch):
    # A token is valid through its exp second and expired from the next one;
    # PyJWT alone would expire it one second earlier.
    t = 1_900_000_000
    monkeypatch.setattr(time, "time", lambda: t + 0.9)
    assert _decode(_token({"exp": t}))["exp"] == t
    with pytest.raises(jwt.ExpiredSignatureError):
        _decode(_token({"exp": t - 1}))


def test_missing_exp_is_rejected():
    with pytest.raises(jwt.MissingRequiredClaimError):
        _decode(_token({"sub": "u1"}))


def test_null_exp_is_rejected_not_a_server_error():
    with pytest.raises(jwt.PyJWTError):
        _decode(_token({"exp": None}))


def test_tampered_signature_is_rejected():
    token = _token({"exp": _exp()})
    with pytest.raises(jwt.InvalidSignatureError):
        _decode(token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB"))


def test_wrong_key_is_rejected():
    with pytest.raises(jwt.InvalidSignatureError):
        _decode(_token({"exp": _exp()}), key="z" * 48)


def test_other_hmac_algorithm_is_rejected_when_not_configured():
    with pytest.raises(jwt.InvalidAlgorithmError):
        _decode(_token({"exp": _exp()}, algorithm="HS512"))


@pytest.mark.parametrize("junk", ["", "abc", "x.y.z", "a.b.c.d"])
def test_malformed_token_raises_the_base_error_every_caller_catches(junk):
    with pytest.raises(jwt.PyJWTError):
        _decode(junk)


def test_every_decode_failure_is_a_pyjwt_error():
    for exc in (
        jwt.ExpiredSignatureError,
        jwt.InvalidSignatureError,
        jwt.DecodeError,
        jwt.InvalidAudienceError,
        jwt.MissingRequiredClaimError,
        jwt.ImmatureSignatureError,
    ):
        assert issubclass(exc, jwt.PyJWTError)


def test_token_with_aud_is_rejected_when_no_audience_is_passed():
    with pytest.raises(jwt.InvalidAudienceError):
        _decode(_token({"exp": _exp(), "aud": "someone"}))


def test_token_without_aud_is_accepted_when_no_audience_is_passed():
    assert _decode(_token({"exp": _exp()}))["exp"]


def test_issuer_is_not_checked():
    assert _decode(_token({"exp": _exp(), "iss": "anyone"}))["iss"] == "anyone"


def test_future_nbf_is_rejected():
    with pytest.raises(jwt.ImmatureSignatureError):
        _decode(_token({"exp": _exp(), "nbf": _exp(3600)}))


def test_future_iat_is_still_accepted():
    # PyJWT rejects a future iat by default; python-jose never did, and a token
    # minted by a host whose clock runs a second ahead must keep verifying.
    assert _decode(_token({"exp": _exp(), "iat": _exp(3600)}))["iat"]


def test_float_iat_and_float_exp_are_accepted():
    now = time.time()
    assert _decode(_token({"exp": now + 60.5, "iat": now - 0.5}))["exp"]


@pytest.mark.parametrize("iat", ["not-a-number", None, [], {}])
def test_malformed_iat_is_rejected(iat):
    with pytest.raises(jwt.PyJWTError):
        _decode(_token({"exp": _exp(), "iat": iat}))


@pytest.mark.parametrize("claim", [{"sub": 5}, {"sub": None}, {"jti": 3}])
def test_non_string_sub_or_jti_is_rejected(claim):
    with pytest.raises(jwt.PyJWTError):
        _decode(_token({"exp": _exp(), **claim}))


@pytest.mark.parametrize("algorithms", [["HS256"], ["none"]])
def test_alg_none_token_is_rejected(algorithms):
    # Even an environment that set JWT_ALGORITHM=none stays closed: PyJWT
    # refuses "none" whenever a (non-empty) secret is passed as the key.
    import base64
    import json

    def part(obj: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    unsigned = part({"alg": "none", "typ": "JWT"}) + "." + part({"exp": _exp()}) + "."
    with pytest.raises(jwt.PyJWTError):
        decode_jwt(unsigned, _KEY, algorithms=algorithms)


@pytest.mark.parametrize("audience", ["", [], None, False, 0, {}])
def test_falsy_audience_claim_is_rejected(audience):
    with pytest.raises(jwt.InvalidAudienceError):
        _decode(_token({"exp": _exp(), "aud": audience}))


def test_wrong_audience_is_rejected_when_an_audience_is_expected():
    token = _token({"exp": _exp(), "aud": "actual"})
    with pytest.raises(jwt.InvalidAudienceError):
        jwt.decode(
            token,
            _KEY,
            algorithms=["HS256"],
            audience="wrong",
            options=JWT_DECODE_OPTIONS,
        )


def test_wrong_issuer_is_rejected_when_an_issuer_is_expected():
    token = _token({"exp": _exp(), "iss": "actual"})
    with pytest.raises(jwt.InvalidIssuerError):
        jwt.decode(
            token,
            _KEY,
            algorithms=["HS256"],
            issuer="wrong",
            options=JWT_DECODE_OPTIONS,
        )


def test_at_hash_without_access_token_is_rejected():
    with pytest.raises(jwt.InvalidTokenError):
        _decode(_token({"exp": _exp(), "at_hash": "synthetic-hash"}))


def test_unverified_claim_read_uses_pyjwt_option():
    token = _token({"exp": _exp(), "marker": "visible"})
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["marker"] == "visible"


def test_unverified_claim_read_is_not_needed_by_production_code():
    offenders = [
        p
        for p in (_BACKEND / "backend").rglob("*.py")
        if "tests" not in p.parts
        and re.search(r"get_unverified|verify_signature.{0,12}False", p.read_text())
    ]
    assert offenders == []


def _production_files():
    return [p for p in (_BACKEND / "backend").rglob("*.py") if "tests" not in p.parts]


def test_python_jose_is_gone_from_production_and_tests():
    pattern = re.compile(r"^\s*(from|import)\s+jose\b", re.MULTILINE)
    offenders = [p for p in (_BACKEND / "backend").rglob("*.py") if pattern.search(p.read_text())]
    assert offenders == [], [str(p) for p in offenders]


def test_every_decode_call_site_pins_algorithms_and_uses_the_shared_decoder():
    checked = 0
    for path in _production_files():
        if path.name == "jwt_decode.py":
            continue
        text = path.read_text()
        assert not re.search(r"\b_?(?:py)?jwt\.decode\(", text), f"{path}: bypasses decode_jwt"
        for match in re.finditer(r"\bdecode_jwt\((.*?)\n\s*\)", text, re.DOTALL):
            body = match.group(1)
            checked += 1
            assert "algorithms=" in body, f"{path}: decode without algorithms"
            assert "none" not in body.lower(), f"{path}: decode admits alg none"
    assert checked == 11


def test_shared_options_are_explicit_and_use_pyjwt_spelling():
    assert JWT_DECODE_OPTIONS == {
        "verify_exp": False,
        "require": ["exp"],
        "verify_iat": False,
        "verify_aud": True,
    }
