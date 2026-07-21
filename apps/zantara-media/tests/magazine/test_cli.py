from __future__ import annotations

import json
import logging
import base64
import hashlib
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from zantara_media.cli.magazine_publish import (
    _millisecond_timestamp,
    _publish,
    _resolve_assets_if_needed,
    async_main,
)
from zantara_media.magazine.assets import AssetIntentManifestV1, AssetIntentV1
from zantara_media.magazine.audit_anchor import build_audit_event_hash
from zantara_media.magazine.media_resolver import AssetResolutionResult


PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010804000000b51c0c02"
    "0000000b4944415478da6364f80f00010501012718e3660000000049454e44ae426082"
)


def _projection(
    path: Path, candidate: dict[str, Any] | None = None
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "magazine-public-projection.v1",
                "source_schema_version": "regulatory-public.v1",
                "system_id": "regulatory-watcher",
                "cutoff": "2026-07-17T22:15:00Z",
                "watermark": "wm-1",
                "collector_run": {
                    "schema_version": "collector-run.v1",
                    "run_id": "run-1",
                    "collector_id": "daily",
                    "started_at": "2026-07-17T21:00:00Z",
                    "completed_at": "2026-07-17T21:01:00Z",
                    "status": "healthy",
                    "freshness": "fresh",
                    "items_seen": 1 if candidate else 0,
                    "items_eligible": 1 if candidate else 0,
                    "source_count": 1,
                    "unreachable_source_count": 0,
                    "watermark": "wm-1",
                    "verified_at": "2026-07-17T21:02:00Z",
                },
                "candidates": [candidate] if candidate else [],
            }
        ),
        encoding="utf-8",
    )


def _candidate_from_story(story: dict[str, Any]) -> dict[str, Any]:
    return {
        "public_id": story["story_id"],
        "slug": story["slug"],
        "language": story["language"],
        "domain": story["domain"],
        "severity": story["severity"],
        "first_seen_at": story["first_seen_at"],
        "event_occurred_at": story["event_occurred_at"],
        "updated_at": story["updated_at"],
        "title": story["title"],
        "deck": story["deck"],
        "summary": story["summary"],
        "why_it_matters": story["why_it_matters"],
        "curiosity_text": story["curiosity_text"],
        "claims": story["claims"],
        "evidence_refs": story["evidence_refs"],
        "asset_digests": [],
        "legal_effect_claim_ids": ["claim-1"],
        "novelty": 0.9,
        "recency": 0.8,
        "operational_impact": 0.9,
        "expected_current_version": 0,
    }


@pytest.mark.asyncio
async def test_morning_dry_run_is_deterministic_and_never_logs_payload_or_secret(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = tmp_path / "manifest.json"
    projection = tmp_path / "intel-lake.public.json"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    secret_marker = "never-log-this-secret"
    projection.write_text(
        json.dumps(
            {
                "schema_version": "magazine-public-projection.v1",
                "source_schema_version": "intel-public.v1",
                "system_id": "intel-lake",
                "cutoff": "2026-07-17T22:15:00Z",
                "watermark": "wm-1",
                "collector_run": {
                    "schema_version": "collector-run.v1",
                    "run_id": "run-1",
                    "collector_id": "daily",
                    "started_at": "2026-07-17T21:00:00Z",
                    "completed_at": "2026-07-17T21:01:00Z",
                    "status": "healthy",
                    "freshness": "fresh",
                    "items_seen": 0,
                    "items_eligible": 0,
                    "source_count": 1,
                    "unreachable_source_count": 0,
                    "watermark": "wm-1",
                    "verified_at": "2026-07-17T21:02:00Z",
                },
                "candidates": [],
            }
        ),
        encoding="utf-8",
    )
    source.write_text(
        json.dumps(
            {
                "schema_version": "magazine-morning-input.v2",
                "projection_inputs": [
                    {"system_id": "intel-lake", "projection_path": str(projection)}
                ],
                "expected_current_revision": 4,
                "expected_breaking_revision": 3,
            }
        ),
        encoding="utf-8",
    )
    common = [
        "morning",
        "--input",
        str(source),
        "--cutoff",
        "2026-07-17T22:15:00Z",
        "--required-system-id",
        "intel-lake",
        "--dry-run",
    ]
    with caplog.at_level(logging.INFO):
        assert await async_main([*common, "--output", str(first)]) == 0
        assert await async_main([*common, "--output", str(second)]) == 0
    assert first.read_bytes() == second.read_bytes()
    packet = json.loads(first.read_text(encoding="utf-8"))
    assert packet["edition_kind"] == "quiet"
    assert secret_marker not in caplog.text
    assert "private_note" not in caplog.text
    with pytest.raises(ValueError, match="cannot unlock production"):
        await async_main(
            [
                *common[:-1],
                "--output",
                str(first),
                "--publish",
                "--asset-manifest",
                str(source),
                "--offline-audit-events",
                str(first),
            ]
        )


def test_cli_requires_explicit_publish_flag_for_network() -> None:
    source = Path("manifest.json")
    # Importing/building the CLI performs no network I/O; publishing is opt-in.
    assert "--publish" not in ["morning", "--input", str(source), "--dry-run"]


@pytest.mark.asyncio
async def test_empty_manifest_is_resolved_automatically_before_publish(
    tmp_path: Path,
    breaking_factory: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = breaking_factory()
    manifest_path = tmp_path / "assets.json"
    source = tmp_path / "hero.png"
    source.write_bytes(PNG)

    async def resolve(*_args: Any, **_kwargs: Any) -> AssetResolutionResult:
        intent = AssetIntentV1(
            asset_id="hero-auto",
            source_path=source,
            story_ids=(str(packet["story"]["story_id"]),),
            captured_at=str(packet["verified_at"]),
            alt_text="Editorial hero",
            source="Bali Zero editorial generator",
            source_url=None,
            rights_basis="generated",
            rights_status="approved",
            usage_status="approved",
            dlp_status="passed",
            sanitization_status="passed",
            perceptual_dedup_status="unique",
        )
        return AssetResolutionResult(
            manifest=AssetIntentManifestV1(schema_version="asset-intents.v1", intents=(intent,)),
            fallback_reason=None,
        )

    monkeypatch.setattr("zantara_media.cli.magazine_publish.resolve_asset_manifest", resolve)
    result = await _resolve_assets_if_needed(
        packet, breaking=True, asset_manifest_path=manifest_path
    )

    assert result.fallback_reason is None
    stored = AssetIntentManifestV1.model_validate_json(manifest_path.read_bytes())
    assert [item.asset_id for item in stored.intents] == ["hero-auto"]


@pytest.mark.asyncio
async def test_stale_automatic_breaking_asset_is_regenerated_for_new_story(
    tmp_path: Path,
    breaking_factory: Callable[..., dict[str, Any]],
    story_factory: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = breaking_factory(
        story=story_factory(story_id="new-story", slug="new-story", asset_digests=[])
    )
    source = tmp_path / "old.png"
    source.write_bytes(PNG)
    stale = AssetIntentManifestV1(
        schema_version="asset-intents.v1",
        intents=(
            AssetIntentV1(
                asset_id="old-auto",
                source_path=source,
                story_ids=("old-story",),
                captured_at=str(packet["verified_at"]),
                alt_text="Old automatic hero",
                source="Bali Zero editorial generator",
                source_url=None,
                rights_basis="generated",
                rights_status="approved",
                usage_status="approved",
                dlp_status="passed",
                sanitization_status="passed",
                perceptual_dedup_status="unique",
            ),
        ),
    )
    manifest_path = tmp_path / "breaking-assets.json"
    manifest_path.write_text(stale.model_dump_json(), encoding="utf-8")

    async def resolve(*_args: Any, **_kwargs: Any) -> AssetResolutionResult:
        return AssetResolutionResult(
            manifest=AssetIntentManifestV1(schema_version="asset-intents.v1", intents=()),
            fallback_reason="generation_failed",
        )

    monkeypatch.setattr("zantara_media.cli.magazine_publish.resolve_asset_manifest", resolve)
    result = await _resolve_assets_if_needed(
        packet, breaking=True, asset_manifest_path=manifest_path
    )

    assert result.fallback_reason == "generation_failed"
    assert AssetIntentManifestV1.model_validate_json(manifest_path.read_bytes()).intents == ()


@pytest.mark.asyncio
async def test_prebound_manifest_is_never_replaced(
    tmp_path: Path,
    breaking_factory: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet = breaking_factory()
    source = tmp_path / "hero.png"
    source.write_bytes(PNG)
    existing = AssetIntentManifestV1(
        schema_version="asset-intents.v1",
        intents=(
            AssetIntentV1(
                asset_id="approved-internal",
                source_path=source,
                story_ids=(str(packet["story"]["story_id"]),),
                captured_at=str(packet["verified_at"]),
                alt_text="Approved editorial hero",
                source="Bali Zero editorial desk",
                source_url=None,
                rights_basis="internal-owned",
                rights_status="approved",
                usage_status="approved",
                dlp_status="passed",
                sanitization_status="passed",
                perceptual_dedup_status="unique",
            ),
        ),
    )
    manifest_path = tmp_path / "assets.json"
    manifest_path.write_text(existing.model_dump_json(), encoding="utf-8")

    async def unexpected(*_args: Any, **_kwargs: Any) -> AssetResolutionResult:
        raise AssertionError("automatic resolver must not replace explicit assets")

    monkeypatch.setattr("zantara_media.cli.magazine_publish.resolve_asset_manifest", unexpected)
    result = await _resolve_assets_if_needed(
        packet, breaking=True, asset_manifest_path=manifest_path
    )

    assert result.manifest == existing
    assert result.fallback_reason is None


@pytest.mark.asyncio
async def test_auto_assets_kill_switch_preserves_empty_manifest(
    tmp_path: Path,
    breaking_factory: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = tmp_path / "assets.json"
    manifest_path.write_text('{"schema_version":"asset-intents.v1","intents":[]}', encoding="utf-8")
    monkeypatch.setenv("MAGAZINE_AUTO_ASSETS", "false")

    async def unexpected(*_args: Any, **_kwargs: Any) -> AssetResolutionResult:
        raise AssertionError("disabled resolver must not run")

    monkeypatch.setattr("zantara_media.cli.magazine_publish.resolve_asset_manifest", unexpected)
    result = await _resolve_assets_if_needed(
        breaking_factory(), breaking=True, asset_manifest_path=manifest_path
    )

    assert result.manifest.intents == ()
    assert result.fallback_reason == "auto_assets_disabled"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("2026-07-19T00:00:00Z", "2026-07-19T00:00:00.000Z"),
        ("2026-07-19T00:00:00.123Z", "2026-07-19T00:00:00.123Z"),
        ("2026-07-19T00:00:00.123987Z", "2026-07-19T00:00:00.123Z"),
    ],
)
def test_anchor_timestamp_is_canonical_millisecond_utc(
    source: str, expected: str
) -> None:
    assert _millisecond_timestamp(source) == expected


@pytest.mark.asyncio
async def test_unknown_asset_story_is_rejected_before_first_upload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = tmp_path / "hero.png"
    image.write_bytes(PNG)
    manifest = tmp_path / "assets.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "asset-intents.v1",
                "intents": [
                    {
                        "asset_id": "hero-1",
                        "source_path": str(image),
                        "story_ids": ["unknown-story"],
                        "captured_at": "2026-07-19T00:00:00Z",
                        "alt_text": "Editorial hero",
                        "source": "Bali Zero editorial desk",
                        "source_url": None,
                        "rights_basis": "internal-owned",
                        "rights_status": "approved",
                        "usage_status": "approved",
                        "dlp_status": "passed",
                        "sanitization_status": "passed",
                        "perceptual_dedup_status": "unique",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "zantara_media.magazine.transport.httpx.AsyncClient",
        lambda **_: real_client(transport=httpx.MockTransport(handler)),
    )
    key = Ed25519PrivateKey.generate()
    env = {
        "MAGAZINE_BASE_URL": "https://magazine.example",
        "MAGAZINE_SIWC_BEARER_TOKEN": "token",
        "MAGAZINE_HMAC_KEY_ID": "hmac-1",
        "MAGAZINE_HMAC_SECRET": "secret",
        "MAGAZINE_HMAC_AUDIENCE": "magazine",
        "MAGAZINE_AUDIT_PRIVATE_KEY_B64": base64.b64encode(
            key.private_bytes_raw()
        ).decode(),
        "MAGAZINE_OUTCOME_JOURNAL": str(tmp_path / "state" / "outcomes.jsonl"),
    }
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match="unknown story"):
        await _publish(
            {
                "packet_id": "edition-1",
                "verified_at": "2026-07-19T00:00:00Z",
                "stories": [{"story_id": "known-story"}],
            },
            breaking=False,
            asset_manifest_path=manifest,
        )
    assert calls == 0


@pytest.mark.asyncio
async def test_cli_publish_anchors_exact_target_before_later_verified_head(
    tmp_path: Path,
    story_factory: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate_from_story(story_factory())
    projection = tmp_path / "regulatory.public.json"
    _projection(projection, candidate)
    source = tmp_path / "input.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": "magazine-morning-input.v2",
                "projection_inputs": [
                    {"system_id": "regulatory-watcher", "projection_path": str(projection)}
                ],
                "expected_current_revision": 0,
                "expected_breaking_revision": 0,
            }
        ),
        encoding="utf-8",
    )
    image = tmp_path / "hero.png"
    image.write_bytes(PNG)
    assets = tmp_path / "assets.json"
    assets.write_text(
        json.dumps(
            {
                "schema_version": "asset-intents.v1",
                "intents": [
                    {
                        "asset_id": "hero-1",
                        "source_path": str(image),
                        "story_ids": [candidate["public_id"]],
                        "captured_at": "2026-07-17T21:00:00Z",
                        "alt_text": "Editorial hero",
                        "source": "Bali Zero editorial desk",
                        "source_url": None,
                        "rights_basis": "internal-owned",
                        "rights_status": "approved",
                        "usage_status": "approved",
                        "dlp_status": "passed",
                        "sanitization_status": "passed",
                        "perceptual_dedup_status": "unique",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    order: list[str] = []
    staged_packet_id = ""
    publication_calls = 0
    permit_a = False
    anchor_sequence = ""

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal anchor_sequence, permit_a, publication_calls, staged_packet_id
        body = await request.aread()
        order.append(request.url.path)
        if request.url.path == "/api/machine/assets":
            return httpx.Response(
                201,
                json={
                    "ok": True,
                    "status": "created",
                    "asset_id": "hero-1",
                    "source_sha256": hashlib.sha256(body).hexdigest(),
                    "canonical_sha256": "d" * 64,
                    "canonical_mime_type": "image/png",
                    "canonical_byte_count": len(body),
                    "width": 1,
                    "height": 1,
                },
            )
        if request.url.path == "/api/machine/publications/editions":
            publication_calls += 1
            packet = json.loads(body)
            staged_packet_id = packet["packet_id"]
            if publication_calls == 1:
                return httpx.Response(
                    409,
                    headers={"cache-control": "no-store"},
                    json={
                        "ok": False,
                        "error": "promotion_blocked",
                        "operation": "edition.publish",
                        "packet_id": staged_packet_id,
                    },
                )
            if not permit_a:
                return httpx.Response(409, json={"error": "promotion_blocked"})
            return httpx.Response(201, json={"ok": True, "status": "created"})
        if request.url.path == "/api/machine/audit-events/v1":
            payload_a = {
                "schema_version": "publication-operation.v1",
                "operation": "edition.publish",
                "packet_id": staged_packet_id,
            }
            hash_a = build_audit_event_hash(
                "magazine-publication.v1", 1, "0" * 64, payload_a
            )
            payload_b = {
                "schema_version": "publication-operation.v1",
                "operation": "breaking.publish",
                "packet_id": "breaking-later",
            }
            hash_b = build_audit_event_hash(
                "magazine-publication.v1", 2, hash_a, payload_b
            )
            return httpx.Response(
                200,
                headers={"cache-control": "no-store"},
                json={
                    "schema_version": "audit-feed.v1",
                    "stream_id": "magazine-publication.v1",
                    "checkpoint": {"stream_seq": "0", "event_hash": "0" * 64},
                    "head": {"stream_seq": "2", "event_hash": hash_b},
                    "events": [
                        {
                            "schema_version": "audit-event.v1",
                            "stream_id": "magazine-publication.v1",
                            "stream_seq": "1",
                            "previous_event_hash": "0" * 64,
                            "event_hash": hash_a,
                            "payload": payload_a,
                        },
                        {
                            "schema_version": "audit-event.v1",
                            "stream_id": "magazine-publication.v1",
                            "stream_seq": "2",
                            "previous_event_hash": hash_a,
                            "event_hash": hash_b,
                            "payload": payload_b,
                        },
                    ],
                    "promotion_target": {
                        "operation": "edition.publish",
                        "packet_id": staged_packet_id,
                        "stream_seq": "1",
                        "event_hash": hash_a,
                    },
                    "next_cursor": {"after_seq": "2", "checkpoint_hash": hash_b},
                    "has_more": False,
                },
            )
        if request.url.path == "/api/machine/audit-anchor":
            receipt = json.loads(body)
            anchor_sequence = receipt["body"]["stream_seq"]
            if anchor_sequence != "1":
                return httpx.Response(409, json={"error": "wrong_target_receipt"})
            permit_a = True
            return httpx.Response(201, json={"ok": True, "status": "created"})
        return httpx.Response(201, json={"ok": True, "status": "created"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "zantara_media.magazine.transport.httpx.AsyncClient",
        lambda **_: real_client(transport=httpx.MockTransport(handler)),
    )
    key = Ed25519PrivateKey.generate()
    env = {
        "MAGAZINE_BASE_URL": "https://magazine.example",
        "MAGAZINE_SIWC_BEARER_TOKEN": "token",
        "MAGAZINE_HMAC_KEY_ID": "hmac-1",
        "MAGAZINE_HMAC_SECRET": "secret",
        "MAGAZINE_HMAC_AUDIENCE": "magazine",
        "MAGAZINE_AUDIT_PRIVATE_KEY_B64": base64.b64encode(key.private_bytes_raw()).decode(),
        "MAGAZINE_OUTCOME_JOURNAL": str(tmp_path / "state" / "outcomes.jsonl"),
    }
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    output = tmp_path / "edition.json"
    assert await async_main(
        [
            "morning", "--input", str(source), "--output", str(output),
            "--cutoff", "2026-07-17T22:15:00Z", "--required-system-id",
            "regulatory-watcher", "--asset-manifest", str(assets),
            "--publish",
        ]
    ) == 0
    assert order == [
        "/api/machine/assets",
        "/api/machine/publications/editions",
        "/api/machine/audit-events/v1",
        "/api/machine/audit-anchor",
        "/api/machine/publications/editions",
    ]
    assert anchor_sequence == "1"
    packet = json.loads(output.read_text(encoding="utf-8"))
    assert packet["asset_digests"] == ["d" * 64]
    assert packet["stories"][0]["asset_digests"] == ["d" * 64]


@pytest.mark.asyncio
async def test_cli_breaking_dry_run_uses_public_projection(
    tmp_path: Path,
    story_factory: Callable[..., dict[str, Any]],
) -> None:
    candidate = _candidate_from_story(story_factory())
    projection = tmp_path / "regulatory.public.json"
    _projection(projection, candidate)
    source = tmp_path / "breaking.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": "magazine-breaking-input.v2",
                "projection_input": {
                    "system_id": "regulatory-watcher",
                    "projection_path": str(projection),
                },
                "candidate_public_id": candidate["public_id"],
                "expected_breaking_revision": 0,
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "breaking-output.json"
    assert await async_main(
        ["breaking", "--input", str(source), "--output", str(output), "--dry-run"]
    ) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["publication_target"] == "breaking"
