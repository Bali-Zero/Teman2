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

from zantara_media.cli.magazine_publish import async_main
from zantara_media.magazine.audit_anchor import build_audit_event_hash


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


def test_cli_requires_explicit_publish_flag_for_network() -> None:
    source = Path("manifest.json")
    # Importing/building the CLI performs no network I/O; publishing is opt-in.
    assert "--publish" not in ["morning", "--input", str(source), "--dry-run"]


@pytest.mark.asyncio
async def test_cli_publish_is_audit_then_upload_then_edition_without_network(
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
    payload = {"event": "ready"}
    event_hash = build_audit_event_hash("publication:main", 1, "0" * 64, payload)
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps(
            [
                {
                    "schema_version": "audit-event.v1",
                    "stream_id": "publication:main",
                    "stream_seq": 1,
                    "previous_event_hash": "0" * 64,
                    "event_hash": event_hash,
                    "payload": payload,
                }
            ]
        ),
        encoding="utf-8",
    )
    order: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
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
            "--audit-events", str(audit), "--publish",
        ]
    ) == 0
    assert order == [
        "/api/machine/audit-anchor",
        "/api/machine/assets",
        "/api/machine/publications/editions",
    ]
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
