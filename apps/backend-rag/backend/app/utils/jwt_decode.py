"""Decode policy shared by every HS256 bearer-token verifier (PyJWT).

These options reproduce what python-jose accepted before the migration:
`exp` is mandatory and verified, and a future-dated `iat` is not a reason to
reject (PyJWT rejects it by default; python-jose never did). Signature,
algorithm, `nbf`, `aud`, `sub` and `jti` checks keep PyJWT's defaults, which
match python-jose's. Callers catch `jwt.PyJWTError`, the base of every error
PyJWT raises for an invalid token.
"""

from collections.abc import Sequence
from typing import Any

import jwt

JWT_DECODE_OPTIONS = {
    "verify_exp": True,
    "require": ["exp"],
    "verify_iat": False,
    "verify_aud": True,
}


def decode_jwt(token: str, key: Any, *, algorithms: Sequence[str]) -> dict[str, Any]:
    """Decode with PyJWT while retaining python-jose 3.5 claim semantics."""
    claims = jwt.decode(token, key, algorithms=algorithms, options=JWT_DECODE_OPTIONS)

    # python-jose checked that iat was integer-convertible but did not reject a
    # future value. PyJWT couples those two checks, so keep its check disabled
    # above and retain only the former here. Floats remain accepted.
    if "iat" in claims:
        try:
            int(claims["iat"])
        except (TypeError, ValueError, OverflowError) as exc:
            raise jwt.InvalidIssuedAtError("Issued At claim (iat) must be an integer.") from exc

    # PyJWT treats falsy audiences as absent; python-jose rejected every aud
    # claim when callers (as here) did not provide an expected audience.
    if "aud" in claims and not claims["aud"]:
        raise jwt.InvalidAudienceError("Invalid audience")

    # python-jose verified at_hash by default and rejected it because none of
    # these callers supplied an access_token. PyJWT does not validate at_hash.
    if "at_hash" in claims:
        raise jwt.InvalidTokenError("No access_token provided to compare against at_hash claim.")

    return claims
