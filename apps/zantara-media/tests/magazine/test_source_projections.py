from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from zantara_media.magazine.adapters import SanitizationError
from zantara_media.magazine.loaders import load_named_projection
from zantara_media.magazine.source_projections import (
    build_intel_lake_projection,
    build_mata_garuda_projection,
    build_notebooklm_projection,
    build_regulatory_projection,
    prepare_morning_inputs,
    resolve_published_revisions,
)


CUTOFF = datetime(2026, 7, 21, 0, 15, tzinfo=timezone.utc)


def test_regulatory_delta_becomes_cited_public_story() -> None:
    projection = build_regulatory_projection(
        {
            "run_at": "2026-07-21T07:58:18+08:00",
            "today": "2026-07-21",
            "partial": False,
            "new_today_count": 1,
            "seen_citations": ["PP 28/2026"],
            "unreachable_sources": [],
            "deltas": [
                {
                    "citation": "PP 28/2026",
                    "title_id": "Perubahan aturan pelaporan",
                    "title_en": "Reporting rules have changed",
                    "service_line": "tax",
                    "summary": "A new official rule changes a reporting obligation.",
                    "impact_note": "Tax operations should review affected filing workflows.",
                    "severity": "high",
                    "confidence": "high",
                    "first_seen_at": "2026-07-21T07:50:00+08:00",
                    "source": "https://jdih.kemenkeu.go.id/example",
                    "verbatim_excerpt": "Not copied into the public projection.",
                }
            ],
        },
        cutoff=CUTOFF,
    )

    assert projection["system_id"] == "regulatory-watcher"
    assert projection["collector_run"]["status"] == "healthy"
    assert projection["collector_run"]["items_eligible"] == 1
    story = projection["candidates"][0]
    assert story["domain"] == "tax"
    assert story["title"] == "Reporting rules have changed"
    assert story["claims"][0]["evidence_ids"] == ["evidence-regulatory-pp-28-2026"]
    assert story["evidence_refs"][0]["source_type"] == "official"
    assert story["evidence_refs"][0]["primary_document_status"] == "verified"
    assert "verbatim_excerpt" not in json.dumps(projection)


def test_mata_empty_feed_is_healthy_quiet_projection() -> None:
    projection = build_mata_garuda_projection(
        {
            "version": 1,
            "generated_at": "2026-07-21T07:33:04+08:00",
            "count": 0,
            "items": [],
        },
        cutoff=CUTOFF,
    )

    assert projection["system_id"] == "mata-garuda"
    assert projection["collector_run"]["status"] == "healthy"
    assert projection["collector_run"]["items_seen"] == 0
    assert projection["candidates"] == []


def test_notebook_inventory_exports_health_without_uuid_or_titles() -> None:
    projection = build_notebooklm_projection(
        {
            "generated_at": "2026-07-20T23:35:43+00:00",
            "notebook_count": 2,
            "notebooks": [
                {
                    "id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
                    "title": "Private inventory title",
                    "source_count": 4,
                    "health": "healthy",
                    "near_cap": False,
                },
                {
                    "id": "ffffffff-1111-4222-8333-444444444444",
                    "title": "Another private title",
                    "source_count": 2,
                    "health": "healthy",
                    "near_cap": False,
                },
            ],
            "nb_intel": {},
        },
        cutoff=CUTOFF,
    )

    encoded = json.dumps(projection)
    assert projection["collector_run"]["items_seen"] == 2
    assert projection["collector_run"]["source_count"] == 6
    assert projection["candidates"] == []
    assert "Private inventory title" not in encoded
    assert "aaaaaaaa-bbbb" not in encoded


def test_revision_resolver_uses_only_completed_publication_packets(
    tmp_path: Path,
) -> None:
    packets = tmp_path / "packets"
    packets.mkdir()
    morning = packets / "morning.json"
    morning.write_text(
        json.dumps(
            {
                "schema_version": "edition.v1",
                "packet_id": "edition-complete",
                "edition_revision": 4,
            }
        ),
        encoding="utf-8",
    )
    (packets / "failed.json").write_text(
        json.dumps(
            {
                "schema_version": "edition.v1",
                "packet_id": "edition-failed",
                "edition_revision": 99,
            }
        ),
        encoding="utf-8",
    )
    (packets / "breaking.json").write_text(
        json.dumps(
            {
                "schema_version": "story.v1",
                "packet_id": "breaking-complete",
                "expected_breaking_revision": 2,
            }
        ),
        encoding="utf-8",
    )
    journal = tmp_path / "outcomes.jsonl"
    rows = [
        {
            "schema_version": "magazine-outcome.v1",
            "operation_id": "/api/machine/publications/editions:edition-complete",
            "path": "/api/machine/publications/editions",
            "body_sha256": "a" * 64,
            "state": "completed",
            "response": {"ok": True},
        },
        {
            "schema_version": "magazine-outcome.v1",
            "operation_id": "/api/machine/publications/editions:edition-failed",
            "path": "/api/machine/publications/editions",
            "body_sha256": "b" * 64,
            "state": "pending",
            "response": None,
        },
        {
            "schema_version": "magazine-outcome.v1",
            "operation_id": "/api/machine/publications/breaking:breaking-complete",
            "path": "/api/machine/publications/breaking",
            "body_sha256": "c" * 64,
            "state": "completed",
            "response": {"ok": True},
        },
    ]
    journal.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    revisions = resolve_published_revisions(packets, journal)

    assert revisions.current_edition == 4
    assert revisions.current_breaking == 3


def test_intel_lake_empty_snapshot_is_a_healthy_quiet_projection() -> None:
    projection = build_intel_lake_projection(
        [],
        cutoff=CUTOFF,
        completed_at="2026-07-21T00:10:00Z",
        status="healthy",
    )

    assert projection["collector_run"]["status"] == "healthy"
    assert projection["collector_run"]["items_seen"] == 0
    assert projection["candidates"] == []


@pytest.mark.asyncio
async def test_prepare_morning_writes_four_loadable_projections_manifest_and_empty_assets(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    (repo / "research/regulatory").mkdir(parents=True)
    (repo / "research/nb-health").mkdir(parents=True)
    (repo / "apps/mata-garuda/data").mkdir(parents=True)
    (repo / "research/regulatory/2026-07-21-delta.json").write_text(
        json.dumps(
            {
                "run_at": "2026-07-21T07:58:18+08:00",
                "today": "2026-07-21",
                "partial": False,
                "new_today_count": 0,
                "seen_citations": [],
                "unreachable_sources": [],
                "deltas": [],
            }
        ),
        encoding="utf-8",
    )
    (repo / "apps/mata-garuda/data/kita_feed.json").write_text(
        json.dumps(
            {
                "version": 1,
                "generated_at": "2026-07-21T07:33:04+08:00",
                "count": 0,
                "items": [],
            }
        ),
        encoding="utf-8",
    )
    (repo / "research/nb-health/nb-inventory-live.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-20T23:35:43+00:00",
                "notebook_count": 0,
                "notebooks": [],
                "nb_intel": {},
            }
        ),
        encoding="utf-8",
    )

    result = prepare_morning_inputs(
        repo_root=repo,
        state_dir=state,
        cutoff=CUTOFF,
        intel_rows=[],
        intel_status="healthy",
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    systems = {item["system_id"] for item in manifest["projection_inputs"]}
    assets = json.loads(result.asset_manifest_path.read_text(encoding="utf-8"))
    assert systems == {
        "intel-lake",
        "mata-garuda",
        "notebooklm",
        "regulatory-watcher",
    }
    assert manifest["expected_current_revision"] == 0
    assert manifest["expected_breaking_revision"] == 0
    assert assets == {"schema_version": "asset-intents.v1", "intents": []}
    for item in manifest["projection_inputs"]:
        assert Path(item["projection_path"]).is_file()
        loaded = await load_named_projection(item["system_id"], Path(item["projection_path"]))
        assert loaded.system_id == item["system_id"]


def test_prepare_morning_rejects_pii_before_any_projection_is_written(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state"

    with pytest.raises(SanitizationError, match="SANITIZATION_PII"):
        prepare_morning_inputs(
            repo_root=repo,
            state_dir=state,
            cutoff=CUTOFF,
            intel_rows=[
                {
                    "canonical_url": "https://example.com/public-story",
                    "title": "Public story",
                    "summary": "Passport B1234567 belongs to a private individual.",
                    "source_domain": "example.com",
                    "language": "en",
                    "topic_tags": ["visa"],
                    "confidence_score": 0.9,
                    "first_seen_at": "2026-07-21T00:10:00Z",
                    "last_seen_at": "2026-07-21T00:10:00Z",
                    "published_at": "2026-07-21T00:05:00Z",
                }
            ],
            intel_status="healthy",
        )

    assert not (state / "inputs").exists()


def test_prepare_morning_preserves_prebound_asset_manifest(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    asset_manifest = state / "inputs" / "assets-2026-07-21.json"
    asset_manifest.parent.mkdir(parents=True)
    original = {
        "schema_version": "asset-intents.v1",
        "intents": [{"operator_prebound_marker": "must-survive-prepare"}],
    }
    asset_manifest.write_text(json.dumps(original), encoding="utf-8")

    result = prepare_morning_inputs(
        repo_root=repo,
        state_dir=state,
        cutoff=CUTOFF,
        intel_rows=[],
        intel_status="healthy",
    )

    assert result.asset_manifest_path == asset_manifest
    assert json.loads(asset_manifest.read_text(encoding="utf-8")) == original
