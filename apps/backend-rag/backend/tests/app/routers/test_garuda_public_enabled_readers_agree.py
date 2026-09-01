"""GARUDA VOA `GARUDA_PUBLIC_ENABLED` — three readers, one verdict.

Gear-3 gate finding D (PR #4959): `garuda_orders_router._flag_enabled()`
used to read `os.environ.get(..., "false").lower() == "true"` (strict,
exact "true") while `garuda_voa_public._public_enabled()` and
`garuda_portal_auth._public_enabled()` read
`os.environ.get(..., "").strip().lower() in {"1", "true", "yes"}`
(permissive, trimmed, case-insensitive). `GARUDA_PUBLIC_ENABLED=1` opened
L2 (eligibility funnel) and L4 (magic-link auth) while leaving L3 (orders/
checkout) dark — a customer could get a quote and never be able to check
out.

All three readers now share the exact same body (kept as local per-file
copies, not a shared import, per LANES.md file-ownership discipline). This
test pins them identical across the value matrix the finding named: unset,
empty, "0", "false", "on", "1", "true", "TRUE", "yes".
"""

from __future__ import annotations

import pytest

from backend.app.routers import garuda_orders_router, garuda_portal_auth, garuda_voa_public

_READERS = (
    ("garuda_voa_public", garuda_voa_public._public_enabled),
    ("garuda_orders_router", garuda_orders_router._flag_enabled),
    ("garuda_portal_auth", garuda_portal_auth._public_enabled),
)

# (env value or None for unset, expected verdict)
_VALUE_MATRIX: list[tuple[str | None, bool]] = [
    (None, False),
    ("", False),
    ("0", False),
    ("false", False),
    ("on", False),
    ("1", True),
    ("true", True),
    ("TRUE", True),
    ("yes", True),
]


@pytest.mark.parametrize(
    "value,expected",
    _VALUE_MATRIX,
    ids=[repr(v) for v, _ in _VALUE_MATRIX],
)
def test_all_three_readers_agree(
    value: str | None, expected: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    if value is None:
        monkeypatch.delenv("GARUDA_PUBLIC_ENABLED", raising=False)
    else:
        monkeypatch.setenv("GARUDA_PUBLIC_ENABLED", value)

    results = {name: reader() for name, reader in _READERS}

    assert results == {name: expected for name, _ in _READERS}, (
        f"readers disagree for GARUDA_PUBLIC_ENABLED={value!r}: {results} "
        f"(all expected {expected}) — this is exactly the class of bug "
        f"finding D caught: one router opens while a sibling stays dark "
        f"for the same env value."
    )
