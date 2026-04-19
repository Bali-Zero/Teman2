"""
alert_dedup: build dedup_key per category + severity-upgrade promotion logic.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.services.compliance.alert_dedup import (
    build_dedup_key,
    should_promote,
)
from backend.services.compliance.severity_calculator import AlertSeverity


class TestBuildDedupKey:
    def test_visa_expiry_uses_document_id(self) -> None:
        key = build_dedup_key(
            category="visa_expiry",
            client_id=42,
            compliance_item_ref="visa_doc_9001",
            reporting_period=None,
        )
        assert key == "visa:42:visa_doc_9001"

    def test_lkpm_uses_reporting_period(self) -> None:
        key = build_dedup_key(
            category="lkpm", client_id=7, compliance_item_ref=None, reporting_period="2026-Q1",
        )
        assert key == "lkpm:7:2026-Q1"

    def test_tax_filing_uses_tax_year_period(self) -> None:
        key = build_dedup_key(
            category="tax_filing", client_id=5, compliance_item_ref="2025:Q4", reporting_period=None,
        )
        assert key == "tax_filing:5:2025:Q4"

    def test_other_category_uses_client_id_only(self) -> None:
        key = build_dedup_key(
            category="license_renewal", client_id=9,
            compliance_item_ref=None, reporting_period=None,
        )
        assert key == "license_renewal:9"

    def test_visa_without_document_id_raises(self) -> None:
        with pytest.raises(ValueError):
            build_dedup_key(
                category="visa_expiry", client_id=42,
                compliance_item_ref=None, reporting_period=None,
            )

    def test_lkpm_without_period_raises(self) -> None:
        with pytest.raises(ValueError):
            build_dedup_key(
                category="lkpm", client_id=7,
                compliance_item_ref=None, reporting_period=None,
            )

    def test_tax_filing_without_compliance_item_ref_raises(self) -> None:
        with pytest.raises(ValueError):
            build_dedup_key(
                category="tax_filing", client_id=5,
                compliance_item_ref=None, reporting_period=None,
            )


class TestShouldPromote:
    def test_upgrade_warning_to_urgent_returns_true(self) -> None:
        assert should_promote(AlertSeverity.WARNING, AlertSeverity.URGENT) is True

    def test_upgrade_urgent_to_critical_returns_true(self) -> None:
        assert should_promote(AlertSeverity.URGENT, AlertSeverity.CRITICAL) is True

    def test_same_severity_returns_false(self) -> None:
        assert should_promote(AlertSeverity.URGENT, AlertSeverity.URGENT) is False

    def test_downgrade_returns_false(self) -> None:
        # Should never happen (severity only climbs as deadline approaches),
        # but the function must handle it defensively.
        assert should_promote(AlertSeverity.URGENT, AlertSeverity.WARNING) is False
