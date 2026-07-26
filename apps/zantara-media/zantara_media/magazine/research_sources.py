"""Closed Pro-side registry for public Magazine research sources and subjects."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)


PublicSystemId = Literal["intel-lake", "mata-garuda", "notebooklm", "regulatory-watcher"]

PUBLIC_SYSTEM_IDS: tuple[PublicSystemId, ...] = (
    "intel-lake",
    "mata-garuda",
    "notebooklm",
    "regulatory-watcher",
)
_STABLE_SUBJECT_ID = re.compile(r"^(?:topic|entity):[a-z0-9]+(?:-[a-z0-9]+)*$")
_SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .,'()&/+-]{0,119}$")
_MAX_CONFIG_BYTES = 1_000_000
_MAX_PROJECTION_BYTES = 32_000_000


class ResearchSubject(BaseModel):
    """A server-held public subject; notebook references remain masked at rest in memory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1, max_length=120)
    search_terms: tuple[str, ...] = Field(min_length=1, max_length=8)
    notebook_ref: SecretStr | None

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        if value.strip() != value or _SAFE_LABEL.fullmatch(value) is None:
            raise ValueError("invalid public subject label")
        return value

    @field_validator("search_terms")
    @classmethod
    def validate_terms(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized: list[str] = []
        for value in values:
            if (
                value.strip() != value
                or not 2 <= len(value) <= 80
                or _SAFE_LABEL.fullmatch(value) is None
            ):
                raise ValueError("invalid public subject search term")
            normalized.append(value.casefold())
        if len(set(normalized)) != len(normalized):
            raise ValueError("duplicate public subject search term")
        return values

    @field_validator("notebook_ref")
    @classmethod
    def validate_notebook_ref(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        secret = value.get_secret_value()
        if not 1 <= len(secret) <= 256 or any(character.isspace() for character in secret):
            raise ValueError("invalid server-held notebook reference")
        return value


class ResearchSourceConfig(BaseModel):
    """Strict registry: exactly four named public projections and stable subjects."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["magazine-research-sources.v1"]
    projection_paths: dict[PublicSystemId, Path]
    subjects: dict[str, ResearchSubject] = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_closed_registry(self) -> ResearchSourceConfig:
        if set(self.projection_paths) != set(PUBLIC_SYSTEM_IDS):
            raise ValueError("all named public projections are required")
        resolved: list[Path] = []
        for path in self.projection_paths.values():
            if (
                not path.is_absolute()
                or not path.name.endswith(".public.json")
                or path.is_symlink()
                or not path.is_file()
                or not 0 < path.stat().st_size <= _MAX_PROJECTION_BYTES
            ):
                raise ValueError("invalid public projection path")
            resolved.append(path.resolve(strict=True))
        if len(set(resolved)) != len(resolved):
            raise ValueError("public projection paths must be distinct")
        for subject_id in self.subjects:
            if _STABLE_SUBJECT_ID.fullmatch(subject_id) is None:
                raise ValueError("invalid stable public subject identifier")
        return self


class ResearchSourceRegistry:
    """Read-only resolver that never exposes notebook references in representations."""

    __slots__ = ("_config",)

    def __init__(self, config: ResearchSourceConfig) -> None:
        self._config = config

    def projection_path(self, system_id: str) -> Path:
        try:
            return self._config.projection_paths[system_id]  # type: ignore[index]
        except KeyError as exc:
            raise ValueError("unknown public projection system") from exc

    def subject(self, subject_id: str) -> ResearchSubject:
        try:
            return self._config.subjects[subject_id]
        except KeyError as exc:
            raise ValueError("unknown public research subject") from exc


def load_research_source_registry(path: Path) -> ResearchSourceRegistry:
    """Load one bounded, local, non-symlink registry file without logging its contents."""

    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError("invalid research source registry path")
    size = path.stat().st_size
    if size <= 0 or size > _MAX_CONFIG_BYTES:
        raise ValueError("invalid research source registry size")
    raw = json.loads(path.read_bytes())
    return ResearchSourceRegistry(ResearchSourceConfig.model_validate(raw))
