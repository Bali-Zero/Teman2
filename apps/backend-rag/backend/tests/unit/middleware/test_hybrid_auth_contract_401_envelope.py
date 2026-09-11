"""`HybridAuthMiddleware`'s frozen-contract 401 envelope (GARUDA VOA W3C).

The middleware refuses an unauthenticated staff request BEFORE
`garuda_staff_router` runs, so its generic `{"detail": "Authentication
required"}` body used to reach the kita client on a path whose frozen
contract (`products/garuda-voa/contracts/openapi.yaml`) declares
`401 -> {"code": "SESSION_REQUIRED", "retryable": false, "message_key":
"garuda_voa.error.session_required"}`. The client reads `code` for its error
boundary and saw `undefined`.

`contract_401_body()` is the whole cure and it is deliberately tiny: it maps
a path to a BODY. It cannot grant access — public-ness is decided one step
earlier in `dispatch`, exclusively by `PUBLIC_ENDPOINTS` — and every caller
still returns 401 with `WWW-Authenticate: Bearer`.

GUILT + INNOCENCE, on the ENTITY and never on a substring (cicatrix #3):
a sibling path that merely SHARES A PREFIX STRING with `/api/visa/voa/staff`
must NOT get the envelope, or the next contract added here would silently
mislabel someone else's 401.
"""

from __future__ import annotations

import pytest

from backend.middleware.hybrid_auth import contract_401_body

_SESSION_REQUIRED = {
    "code": "SESSION_REQUIRED",
    "retryable": False,
    "message_key": "garuda_voa.error.session_required",
}

# Every staff operation the frozen contract declares with 401 SESSION_REQUIRED,
# written as a CONCRETE path the way a real request arrives (no `{param}`).
_STAFF_PATHS = [
    "/api/visa/voa/staff",
    "/api/visa/voa/staff/practices",
    "/api/visa/voa/staff/practices/prc_abc123",
    "/api/visa/voa/staff/practices/prc_abc123/assignment",
    "/api/visa/voa/staff/practices/prc_abc123/transitions",
    "/api/visa/voa/staff/orders/ord_abc123/late-resolution",
]

_NON_STAFF_PATHS = [
    # Same product, PUBLIC lanes — they never reach the 401 branch, and if a
    # future edit made them reach it their contract code is not SESSION_REQUIRED
    # on every one of them (receivePaymentWebhook is WEBHOOK_SIGNATURE_INVALID).
    "/api/visa/voa/orders/ord_abc123",
    "/api/visa/voa/webhooks/payment",
    "/api/visa/voa/eligibility-checks",
    # SUBSTRING-but-not-ENTITY: shares the `/api/visa/voa/staff` prefix as raw
    # text, is a different path segment. This is the assertion that keeps the
    # matcher on the entity.
    "/api/visa/voa/staffroom",
    "/api/visa/voa/staff-directory",
    # Unrelated surfaces keep the generic body.
    "/api/protected",
    "/health",
    "",
]


@pytest.mark.parametrize("path", _STAFF_PATHS)
def test_staff_paths_get_the_frozen_contract_envelope(path: str) -> None:
    assert contract_401_body(path) == _SESSION_REQUIRED


@pytest.mark.parametrize("path", _NON_STAFF_PATHS)
def test_other_paths_keep_the_generic_body(path: str) -> None:
    assert contract_401_body(path) is None, (
        f"{path} must fall through to the middleware's generic "
        f"{{'detail': 'Authentication required'}} body"
    )


def test_returned_envelope_is_a_copy_not_the_registry_entry() -> None:
    """A caller mutating the returned dict must not poison every later 401."""
    first = contract_401_body("/api/visa/voa/staff/practices")
    assert first is not None
    first["code"] = "MUTATED"
    second = contract_401_body("/api/visa/voa/staff/practices")
    assert second == _SESSION_REQUIRED


def test_envelope_matches_the_frozen_error_catalog() -> None:
    """The envelope is not a hand-typed guess: it must equal what
    `garuda_staff_router._ERROR_CATALOG` (itself a verbatim copy of
    `products/garuda-voa/contracts/errors.yaml`) says SESSION_REQUIRED is.
    Imported here rather than at module scope in `hybrid_auth.py` on purpose —
    the middleware must not import a router."""
    from backend.app.routers.garuda_staff_router import _ERROR_CATALOG

    status_code, retryable, message_key = _ERROR_CATALOG["SESSION_REQUIRED"]
    assert status_code == 401
    assert contract_401_body("/api/visa/voa/staff/practices") == {
        "code": "SESSION_REQUIRED",
        "retryable": retryable,
        "message_key": message_key,
    }
