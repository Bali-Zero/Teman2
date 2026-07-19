from __future__ import annotations

from typing import Any

import pytest

from zantara_media.magazine.adapters import (
    AdapterRegistry,
    IntelLakeAdapter,
    MataGarudaAdapter,
    NotebookLMAdapter,
    RegulatoryWatcherAdapter,
    SanitizationError,
    default_adapter_registry,
)


def candidate_payload(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "public_id": "signal-1",
        "slug": "verified-change",
        "domain": "compliance",
        "severity": "high",
        "first_seen_at": "2026-07-17T20:00:00Z",
        "event_occurred_at": None,
        "updated_at": "2026-07-17T21:00:00Z",
        "title": "A verified change",
        "deck": "An official source confirms the change.",
        "summary": "A sanitized summary.",
        "why_it_matters": "The team should review affected services.",
        "curiosity_text": None,
        "claims": [],
        "evidence_refs": [],
        "asset_digests": [],
        "legal_effect_claim_ids": [],
        "novelty": 0.8,
        "operational_impact": 0.9,
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    "adapter",
    [IntelLakeAdapter(), MataGarudaAdapter(), RegulatoryWatcherAdapter(), NotebookLMAdapter()],
)
def test_adapters_reject_denied_nested_fields(adapter: Any) -> None:
    raw = candidate_payload(raw_payload={"passport": "A1234567"}, notebook_uuid="secret")
    with pytest.raises(SanitizationError, match="^SANITIZATION_DENIED_KEY$"):
        adapter.candidates([raw])


def test_adapters_reject_pii_in_allowlisted_copy() -> None:
    with pytest.raises(SanitizationError, match="SANITIZATION_PII"):
        IntelLakeAdapter().candidates([candidate_payload(summary="Passport A1234567 changed")])


def test_adapters_reject_pii_inside_claim_or_evidence_projection() -> None:
    raw = candidate_payload(
        claims=[
            {
                "claim_id": "claim-1",
                "claim_kind": "analysis",
                "legal_effect": "none",
                "normalized_text": "Passport A1234567 requires review.",
                "numeric_value": None,
                "numeric_unit": None,
                "as_of": None,
                "evidence_ids": [],
                "breaking_gate": None,
            }
        ]
    )
    with pytest.raises(SanitizationError, match="SANITIZATION_PII"):
        MataGarudaAdapter().candidates([raw])


def test_intel_lake_excludes_probe_sandbox_rows() -> None:
    rows = [candidate_payload(), candidate_payload(public_id="probe", is_probe_sandbox=True)]
    assert [item.public_id for item in IntelLakeAdapter().candidates(rows)] == ["signal-1"]


def test_regulatory_watcher_normalizes_schema_drift() -> None:
    raw = candidate_payload()
    raw["headline"] = raw.pop("title")
    raw["impact"] = raw.pop("severity")
    candidate = RegulatoryWatcherAdapter().candidates([raw])[0]
    assert candidate.title == "A verified change"
    assert candidate.severity == "high"


def test_notebook_adapter_accepts_only_labeled_health_or_insight() -> None:
    adapter = NotebookLMAdapter()
    assert adapter.candidates([candidate_payload(record_kind="health")]) == []
    insight = adapter.candidates([candidate_payload(record_kind="insight")])
    assert insight[0].contributing_system_ids == ("notebooklm",)
    with pytest.raises(SanitizationError, match="record_kind"):
        adapter.candidates([candidate_payload(record_kind="raw-notebook")])


def test_registry_is_closed_but_supports_explicit_extension() -> None:
    registry = default_adapter_registry()
    assert set(registry.system_ids()) == {
        "intel-lake",
        "mata-garuda",
        "notebooklm",
        "regulatory-watcher",
    }
    with pytest.raises(KeyError):
        registry.get("unknown")
    custom = AdapterRegistry()
    custom.register("custom-public", IntelLakeAdapter())
    assert isinstance(custom.get("custom-public"), IntelLakeAdapter)
    with pytest.raises(ValueError, match="already registered"):
        custom.register("custom-public", IntelLakeAdapter())


def test_adapter_rejects_contaminated_collector_health() -> None:
    with pytest.raises(SanitizationError, match="^SANITIZATION_DENIED_KEY$"):
        IntelLakeAdapter().collector_run(
            {
                "schema_version": "collector-run.v1",
                "run_id": "run-1",
                "system_id": "wrong-private-value",
                "collector_id": "daily",
                "started_at": "2026-07-18T00:00:00Z",
                "completed_at": "2026-07-18T00:01:00Z",
                "status": "healthy",
                "freshness": "fresh",
                "items_seen": 10,
                "items_eligible": 2,
                "source_count": 3,
                "unreachable_source_count": 0,
                "watermark": "public-watermark",
                "verified_at": "2026-07-18T00:01:01Z",
                "raw_payload": {"passport": "A1234567"},
            }
        )
