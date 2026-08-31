"""Closed error vocabulary mirroring `products/garuda-voa/contracts/errors.yaml`.

The router maps each of these to its contract-frozen HTTP status/code; this
module never imports FastAPI so `repository.py`/`reconciliation.py` stay
framework-agnostic and independently testable.
"""

from __future__ import annotations


class GarudaOrderError(Exception):
    pass


class ResultNotFound(GarudaOrderError):
    """Malformed, absent, or non-owned source check. -> 404 RESULT_NOT_FOUND."""


class OrderNotReady(GarudaOrderError):
    """Reviewed intake not confirmed. -> 409 ORDER_NOT_READY."""


class OrderNotFound(GarudaOrderError):
    """-> 404 ORDER_NOT_FOUND (non-enumerating)."""


class PersistencePolicyUnavailable(GarudaOrderError):
    """SM-G01/OP-F07: no active GARUDA_ORDER retention policy. -> 503."""


class PriceUnresolvable(GarudaOrderError):
    """G-FRESHNESS-FAIL-CLOSED / pricing.price_for_case returned None. -> 503."""


class PaymentProviderUnavailable(GarudaOrderError):
    """-> 503 PAYMENT_PROVIDER_UNAVAILABLE."""


class InvalidStateTransition(GarudaOrderError):
    """-> 409 INVALID_STATE_TRANSITION."""


class NoOpenLateCase(GarudaOrderError):
    """resolveLateOrder called on an order with no open remediation case. -> 409."""


__all__ = [
    "GarudaOrderError",
    "InvalidStateTransition",
    "NoOpenLateCase",
    "OrderNotFound",
    "OrderNotReady",
    "PaymentProviderUnavailable",
    "PersistencePolicyUnavailable",
    "PriceUnresolvable",
    "ResultNotFound",
]
