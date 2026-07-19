"""Read-only loaders for the four named public collector projections."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from zantara_media.magazine.adapters import (
    BasePublicAdapter,
    IntelLakeAdapter,
    MataGarudaAdapter,
    NotebookLMAdapter,
    RegulatoryWatcherAdapter,
    StoryCandidate,
)
from zantara_media.magazine.contracts import CollectorRunProjectionV1


class PublicProjectionEnvelopeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["magazine-public-projection.v1"]
    source_schema_version: str
    system_id: Literal["intel-lake", "mata-garuda", "notebooklm", "regulatory-watcher"]
    cutoff: str
    watermark: str
    collector_run: dict[str, Any]
    candidates: tuple[dict[str, Any], ...]


class LoadedProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    system_id: str
    source_schema_version: str
    cutoff: str
    watermark: str
    collector_run: CollectorRunProjectionV1
    candidates: tuple[StoryCandidate, ...]


class PublicProjectionLoader:
    def __init__(self, adapter: BasePublicAdapter) -> None:
        self._adapter = adapter

    async def load(self, path: Path) -> LoadedProjection:
        if not path.name.endswith(".public.json"):
            raise ValueError("projection input must be an explicitly named .public.json file")
        raw = json.loads(await asyncio.to_thread(path.read_bytes))
        envelope = PublicProjectionEnvelopeV1.model_validate(raw)
        if envelope.system_id != self._adapter.system_id:
            raise ValueError("projection system_id does not match named loader")
        run = self._adapter.collector_run(envelope.collector_run)
        if run.watermark != envelope.watermark:
            raise ValueError("projection watermark does not match collector run")
        if run.verified_at > envelope.cutoff or run.completed_at > envelope.cutoff:
            raise ValueError("projection collector run exceeds projection cutoff")
        return LoadedProjection(
            system_id=envelope.system_id,
            source_schema_version=envelope.source_schema_version,
            cutoff=envelope.cutoff,
            watermark=envelope.watermark,
            collector_run=run,
            candidates=tuple(self._adapter.candidates(envelope.candidates)),
        )


LOADERS = {
    "intel-lake": PublicProjectionLoader(IntelLakeAdapter()),
    "mata-garuda": PublicProjectionLoader(MataGarudaAdapter()),
    "notebooklm": PublicProjectionLoader(NotebookLMAdapter()),
    "regulatory-watcher": PublicProjectionLoader(RegulatoryWatcherAdapter()),
}


async def load_named_projection(system_id: str, path: Path) -> LoadedProjection:
    try:
        loader = LOADERS[system_id]
    except KeyError as exc:
        raise ValueError("unknown public projection system_id") from exc
    return await loader.load(path)
