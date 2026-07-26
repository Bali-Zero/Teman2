from __future__ import annotations

import json
from pathlib import Path

import pytest

from zantara_media.magazine.loaders import load_named_projection


VERSIONS = {
    "intel-lake": "intel-public.v1",
    "mata-garuda": "mata-garuda-public.v1",
    "notebooklm": "notebooklm-public.v1",
    "regulatory-watcher": "regulatory-public.v1",
}


def projection(system_id: str, version: str, *, cutoff: str) -> dict[str, object]:
    return {
        "schema_version": "magazine-public-projection.v1",
        "source_schema_version": version,
        "system_id": system_id,
        "cutoff": cutoff,
        "watermark": "wm-1",
        "collector_run": {
            "schema_version": "collector-run.v1",
            "run_id": "run-1",
            "collector_id": "daily",
            "started_at": "2026-07-18T23:59:58Z",
            "completed_at": "2026-07-19T00:00:00Z",
            "status": "healthy",
            "freshness": "fresh",
            "items_seen": 0,
            "items_eligible": 0,
            "source_count": 1,
            "unreachable_source_count": 0,
            "watermark": "wm-1",
            "verified_at": "2026-07-19T00:00:00Z",
        },
        "candidates": [],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(("system_id", "version"), VERSIONS.items())
async def test_named_loader_accepts_only_its_source_schema_version(
    tmp_path: Path, system_id: str, version: str
) -> None:
    path = tmp_path / f"{system_id}.public.json"
    path.write_text(
        json.dumps(projection(system_id, version, cutoff="2026-07-19T00:00:00.100Z")),
        encoding="utf-8",
    )
    assert (await load_named_projection(system_id, path)).source_schema_version == version

    path.write_text(
        json.dumps(projection(system_id, "forged.v9", cutoff="2026-07-19T00:00:00.100Z")),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="source schema version"):
        await load_named_projection(system_id, path)


@pytest.mark.asyncio
async def test_loader_compares_real_instants_and_rejects_invalid_cutoff(
    tmp_path: Path,
) -> None:
    path = tmp_path / "intel.public.json"
    path.write_text(
        json.dumps(
            projection(
                "intel-lake", "intel-public.v1", cutoff="2026-07-19T00:00:00.100Z"
            )
        ),
        encoding="utf-8",
    )
    await load_named_projection("intel-lake", path)

    path.write_text(
        json.dumps(projection("intel-lake", "intel-public.v1", cutoff="not-an-instant")),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="valid instant"):
        await load_named_projection("intel-lake", path)
