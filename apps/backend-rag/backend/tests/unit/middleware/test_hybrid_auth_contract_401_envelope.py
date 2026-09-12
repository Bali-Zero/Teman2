"""`HybridAuthMiddleware`'s frozen-contract 401 envelope (GARUDA VOA W3C).

The middleware refuses an unauthenticated staff request BEFORE
`garuda_staff_router` runs, so its generic `{"detail": "Authentication
required"}` body used to reach the kita client on a path whose frozen
contract (`products/garuda-voa/contracts/openapi.yaml`) declares
`401 -> {"code": "SESSION_REQUIRED", "retryable": false, "message_key":
"garuda_voa.error.session_required"}` plus three privacy headers. The client
reads `code` for its error boundary and saw `undefined`.

`contract_401_envelope()` is the whole cure and it is deliberately tiny: it
maps a path to a `(body, headers)` pair. It cannot grant access — public-ness
is decided one step earlier in `dispatch`, exclusively by `PUBLIC_ENDPOINTS` —
and every caller still returns 401 with `WWW-Authenticate: Bearer`.

The HEADERS are contract, not decoration: `Cache-Control: no-store, private`
is what keeps a shared cache from storing a refusal for an authenticated
surface.

TWO ANCHORS, both derived and neither hand-typed, so this file cannot drift
into agreeing with itself (the failure mode `test_garuda_voa_openapi_parity.py`
was written for): the operation templates and the privacy headers are both
read back out of the frozen YAML and compared to what the middleware ships.

GUILT + INNOCENCE on the ENTITY and never on a prefix (cicatrix #3): the
matcher is template-based, so the bare `/api/visa/voa/staff`, the
trailing-slash-only `/api/visa/voa/staff/`, the malformed
`/api/visa/voa/staff//practices` and any arbitrary descendant all fail by
SEGMENT COUNT rather than by vigilance.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from backend.middleware.hybrid_auth import (
    _GARUDA_VOA_STAFF_OPERATIONS,
    contract_401_envelope,
)

_CONTRACT_PATH = (
    Path(__file__).resolve().parents[6] / "products" / "garuda-voa" / "contracts" / "openapi.yaml"
)

_PRIVACY_HEADERS = {
    "Cache-Control": "no-store, private",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
}

_SESSION_REQUIRED = {
    "code": "SESSION_REQUIRED",
    "retryable": False,
    "message_key": "garuda_voa.error.session_required",
}

# CONCRETE paths, written the way a real request arrives (no `{param}`), one
# per frozen staff operation.
_STAFF_PATHS = [
    "/api/visa/voa/staff/practices",
    "/api/visa/voa/staff/practices/prc_abc123",
    "/api/visa/voa/staff/practices/prc_abc123/assignment",
    "/api/visa/voa/staff/practices/prc_abc123/transitions",
    "/api/visa/voa/staff/orders/ord_abc123/late-resolution",
    # Trailing-slash variants of two entries above; same assertions as every entry.
    "/api/visa/voa/staff/practices/",
    "/api/visa/voa/staff/practices/prc_abc123/transitions/",
]

_NON_STAFF_PATHS = [
    # Same product, PUBLIC lanes — they never reach the 401 branch, and their
    # contract code is not SESSION_REQUIRED on every one of them anyway
    # (receivePaymentWebhook is WEBHOOK_SIGNATURE_INVALID).
    "/api/visa/voa/orders/ord_abc123",
    "/api/visa/voa/webhooks/payment",
    "/api/visa/voa/eligibility-checks",
    # SUBSTRING-but-not-ENTITY: shares the `/api/visa/voa/staff` prefix as raw
    # text, is a different path segment.
    "/api/visa/voa/staffroom",
    "/api/visa/voa/staff-directory",
    # The BARE prefix. No frozen operation lives there, while `garuda_voa.py`'s
    # owner-archive route `/api/visa/voa/{hash}` pattern-matches it — claiming
    # it would stamp another router's refusal with this contract's code.
    "/api/visa/voa/staff",
    # Trailing slash only, and the malformed double slash: a prefix matcher
    # accepts both, a template matcher cannot (segment count).
    "/api/visa/voa/staff/",
    "/api/visa/voa/staff//practices",
    # Arbitrary descendants of the prefix that the contract never declares.
    "/api/visa/voa/staff/nope",
    "/api/visa/voa/staff/practices/prc_abc123/not-an-operation",
    "/api/visa/voa/staff/practices/prc_abc123/assignment/extra",
    # An empty path param — `{practice_id}` must be non-empty.
    "/api/visa/voa/staff/practices//assignment",
    # Unrelated surfaces keep the generic body.
    "/api/protected",
    "/health",
    "",
]


def _frozen_staff_operation_paths() -> set[str]:
    """Every path the frozen contract declares with a 401 SESSION_REQUIRED
    response under the staff root — derived from the YAML, never typed here."""
    doc = yaml.safe_load(_CONTRACT_PATH.open())
    found = set()
    for path, methods in doc["paths"].items():
        if not isinstance(methods, dict) or not path.startswith("/api/visa/voa/staff/"):
            continue
        for op in methods.values():
            if not isinstance(op, dict):
                continue
            if "SESSION_REQUIRED" in op.get("responses", {}).get("401", {}).get(
                "x-error-codes", []
            ):
                found.add(path)
    return found


@pytest.mark.parametrize("path", _STAFF_PATHS)
def test_staff_paths_get_the_frozen_contract_envelope(path: str) -> None:
    result = contract_401_envelope(path)
    assert result is not None, f"{path} must carry the frozen contract's 401 envelope"
    body, headers = result
    assert body == _SESSION_REQUIRED
    assert headers == _PRIVACY_HEADERS


@pytest.mark.parametrize("path", _NON_STAFF_PATHS)
def test_other_paths_keep_the_generic_body(path: str) -> None:
    assert contract_401_envelope(path) is None, (
        f"{path} must fall through to the middleware's generic "
        f"{{'detail': 'Authentication required'}} body"
    )


def test_returned_envelope_is_a_copy_not_the_registry_entry() -> None:
    """A caller mutating the returned dicts must not poison every later 401."""
    first = contract_401_envelope("/api/visa/voa/staff/practices")
    assert first is not None
    first[0]["code"] = "MUTATED"
    first[1]["Cache-Control"] = "MUTATED"
    second = contract_401_envelope("/api/visa/voa/staff/practices")
    assert second == (_SESSION_REQUIRED, _PRIVACY_HEADERS)


def test_operation_templates_equal_the_frozen_contracts_staff_paths() -> None:
    """ANCHOR 1, derived: the middleware's copy of the operation templates must
    be exactly the set of staff paths the contract declares with a 401
    SESSION_REQUIRED. A new staff operation landing in the contract without
    landing here fails this, instead of silently getting the generic body."""
    frozen = _frozen_staff_operation_paths()
    assert frozen, "parsed no staff operations out of the frozen contract — fixture is broken"
    assert set(_GARUDA_VOA_STAFF_OPERATIONS) == frozen, (
        f"middleware templates {sorted(_GARUDA_VOA_STAFF_OPERATIONS)} != frozen contract "
        f"{sorted(frozen)}"
    )


def test_privacy_headers_equal_the_frozen_contracts_anchor() -> None:
    """ANCHOR 2, derived: the three headers must be the `const` values the
    contract's `x-public-privacy-response-headers` anchor declares — read out
    of the YAML, not compared against another Python copy of themselves."""
    doc = yaml.safe_load(_CONTRACT_PATH.open())
    anchor = doc["x-public-privacy-response-headers"]
    frozen = {name: spec["schema"]["const"] for name, spec in anchor.items()}
    result = contract_401_envelope("/api/visa/voa/staff/practices")
    assert result is not None
    assert result[1] == frozen, f"middleware serves {result[1]}, contract declares {frozen}"


def test_envelope_matches_the_frozen_error_catalog() -> None:
    """The body is not a hand-typed guess either: it must equal what
    `garuda_staff_router._ERROR_CATALOG` (itself a verbatim copy of
    `products/garuda-voa/contracts/errors.yaml`) says SESSION_REQUIRED is.
    Imported inside the test rather than at module scope on purpose — the
    middleware must not import a router."""
    from backend.app.routers.garuda_staff_router import _ERROR_CATALOG

    status_code, retryable, message_key = _ERROR_CATALOG["SESSION_REQUIRED"]
    assert status_code == 401
    result = contract_401_envelope("/api/visa/voa/staff/practices")
    assert result is not None
    assert result[0] == {
        "code": "SESSION_REQUIRED",
        "retryable": retryable,
        "message_key": message_key,
    }


def test_privacy_headers_match_the_staff_router_they_stand_in_for() -> None:
    """Asserts after == before + middleware as Counters of (lower-cased name, value) pairs."""
    from collections import Counter

    from fastapi import Response

    from backend.app.routers.garuda_staff_router import _privacy_headers

    def pairs(raw: list[tuple[bytes, bytes]]) -> Counter[tuple[str, str]]:
        return Counter(
            (name.decode("latin-1").lower(), value.decode("latin-1")) for name, value in raw
        )

    probe = Response()
    before = pairs(list(probe.headers.raw))
    _privacy_headers(probe)
    after = pairs(list(probe.headers.raw))
    result = contract_401_envelope("/api/visa/voa/staff/practices")
    assert result is not None
    middleware = Counter((name.lower(), value) for name, value in result[1].items())
    expected = before + middleware
    assert after == expected, (
        f"after _privacy_headers: {sorted(after.items())} != before + middleware "
        f"{sorted(expected.items())} — only after: {sorted((after - expected).items())}, "
        f"only expected: {sorted((expected - after).items())}"
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/visa/voa/staff/practices/"),
        ("POST", "/api/visa/voa/staff/practices/prc_abc123/transitions/"),
    ],
)
def test_a_trailing_slash_past_the_middleware_redirects_to_the_same_operation(
    method: str, path: str
) -> None:
    """Asserts 307, Location == "http://testserver" + path.rstrip("/"), equal envelopes."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.app.routers.garuda_staff_router import router

    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).request(method, path, follow_redirects=False)
    assert response.status_code == 307, f"{method} {path} -> {response.status_code}"
    assert response.headers["location"] == f"http://testserver{path.rstrip('/')}"
    assert contract_401_envelope(path) == contract_401_envelope(path.rstrip("/"))
