"""
Per-category dedup key builder + severity-upgrade promotion (decision #6).

Dedup policies:
  visa_expiry  → visa:<client_id>:<document_id>         (lifetime of document)
  lkpm         → lkpm:<client_id>:<reporting_period>    (lifetime of period)
  tax_filing   → tax_filing:<client_id>:<tax_year>:<p>  (lifetime of period)
  others       → <category>:<client_id>                 (24h rolling, app-enforced)
"""
from __future__ import annotations

from backend.services.compliance.severity_calculator import AlertSeverity


_SEVERITY_ORDER: dict[AlertSeverity, int] = {
    AlertSeverity.INFO: 0,
    AlertSeverity.WARNING: 1,
    AlertSeverity.URGENT: 2,
    AlertSeverity.CRITICAL: 3,
}


def build_dedup_key(
    *,
    category: str,
    client_id: int,
    compliance_item_ref: str | None,
    reporting_period: str | None,
) -> str:
    """
    Compute the dedup_key string for a given category + identifiers.

    Raises:
        ValueError: when required identifier missing for a category.
    """
    if category == "visa_expiry":
        if not compliance_item_ref:
            raise ValueError("visa_expiry requires compliance_item_ref (document_id)")
        return f"visa:{client_id}:{compliance_item_ref}"
    if category == "lkpm":
        if not reporting_period:
            raise ValueError("lkpm requires reporting_period")
        return f"lkpm:{client_id}:{reporting_period}"
    if category == "tax_filing":
        if not compliance_item_ref:
            raise ValueError("tax_filing requires compliance_item_ref (<year>:<period>)")
        return f"tax_filing:{client_id}:{compliance_item_ref}"
    # All other categories: bare client scope, 24h window enforced at query time.
    return f"{category}:{client_id}"


def should_promote(old: AlertSeverity, new: AlertSeverity) -> bool:
    """Return True if `new` is strictly more severe than `old`."""
    return _SEVERITY_ORDER[new] > _SEVERITY_ORDER[old]


__all__ = ["build_dedup_key", "should_promote"]
