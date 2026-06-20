from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.services.autonomous_lab.normalizer import normalize_and_dedupe_materials
from backend.services.autonomous_lab.planner import MaterialSourceType, ResearchMaterial


def test_normalizer_dedupes_by_content_fingerprint_and_keeps_receipt_safe() -> None:
    raw_text = "Agent workflow research. RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR"
    materials = [
        ResearchMaterial(
            material_id="m1",
            source_type=MaterialSourceType.WEB,
            source_uri="https://example.com/a",
            title="First",
            text=raw_text,
            captured_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
        ),
        ResearchMaterial(
            material_id="m2",
            source_type=MaterialSourceType.WEB,
            source_uri="https://example.com/b",
            title="Second",
            text=raw_text,
            captured_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
        ),
    ]

    batch = normalize_and_dedupe_materials(materials=materials)
    receipt = batch.to_receipt()
    receipt_text = json.dumps(receipt, sort_keys=True)

    assert receipt["material_count"] == 2
    assert receipt["cluster_count"] == 1
    assert receipt["duplicate_count"] == 1
    assert receipt["novelty_score"] < 1
    assert "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR" not in receipt_text
