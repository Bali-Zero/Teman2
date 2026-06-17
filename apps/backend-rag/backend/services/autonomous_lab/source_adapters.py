"""Read-only source adapter contracts for the Autonomous Lab watchtower."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from backend.services.autonomous_lab.planner import MaterialSourceType, ResearchMaterial
from backend.services.autonomous_lab.receipt_safety import (
    receipt_safe_evidence,
    receipt_safe_source_uri,
    safe_sha256_fingerprint,
    shorten_receipt_value,
)

SOURCE_ADAPTER_CONTRACT_VERSION = "autonomous-lab-v1-source-adapters"


class SourceAdapterKind(str, Enum):
    """Source families the Lab can watch without coupling to one provider."""

    NOTEBOOKLM = "notebooklm"
    GITHUB = "github"
    PAPER_INDEX = "paper_index"
    SDK_DOCS = "sdk_docs"
    MCP_REGISTRY = "mcp_registry"
    OPERATOR_NOTE = "operator_note"


@dataclass(frozen=True)
class SourceAdapterSpec:
    """Read-only adapter declaration for one source family."""

    key: str
    kind: SourceAdapterKind
    source_type: MaterialSourceType
    read_policy: str
    write_policy: str
    freshness_window_hours: int
    external_calls_allowed: bool = False

    def to_receipt(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "kind": self.kind.value,
            "source_type": self.source_type.value,
            "read_policy": self.read_policy,
            "write_policy": self.write_policy,
            "freshness_window_hours": self.freshness_window_hours,
            "external_calls_allowed": self.external_calls_allowed,
        }


@dataclass(frozen=True)
class FrontierSignal:
    """Metadata-only novelty signal produced by a watch adapter."""

    signal_id: str
    adapter_key: str
    source_type: MaterialSourceType
    source_uri: str
    title: str
    captured_at: datetime
    implementation_area: str
    tags: tuple[str, ...]
    novelty_score: float
    evidence_reference: str

    def to_receipt(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "adapter_key": self.adapter_key,
            "source_type": self.source_type.value,
            "source_uri": receipt_safe_source_uri(
                self.source_uri,
                self.source_type.value,
                preserve_public_host=self.source_type
                not in {
                    MaterialSourceType.CHAT_METADATA,
                    MaterialSourceType.DRIVE_METADATA,
                    MaterialSourceType.OPERATOR_NOTE,
                    MaterialSourceType.OTHER,
                },
            ),
            "title": receipt_safe_evidence(self.title, force_fingerprint=True),
            "captured_at": self.captured_at.isoformat(),
            "implementation_area": self.implementation_area,
            "tags": list(self.tags),
            "novelty_score": self.novelty_score,
            "evidence_reference": self.evidence_reference,
        }

    def to_research_material(self) -> ResearchMaterial:
        """Build a bounded material envelope for downstream planner simulation."""
        text = (
            f"Frontier signal {self.signal_id} from {self.adapter_key}. "
            f"Area: {self.implementation_area}. "
            f"Tags: {', '.join(self.tags)}. "
            f"Novelty score: {self.novelty_score:.2f}. "
            "Shadow material is generated from metadata only."
        )
        return ResearchMaterial(
            material_id=self.signal_id,
            source_type=self.source_type,
            source_uri=self.source_uri,
            title=self.title,
            text=text,
            captured_at=self.captured_at,
            metadata={
                "adapter_key": self.adapter_key,
                "implementation_area": self.implementation_area,
                "novelty_score": f"{self.novelty_score:.2f}",
                "evidence_reference": self.evidence_reference,
            },
        )


@dataclass(frozen=True)
class WatchtowerTick:
    """One bounded watch cycle with no network calls."""

    version: str
    tick_id: str
    objective_reference: str
    captured_at: datetime
    adapters: tuple[SourceAdapterSpec, ...]
    signals: tuple[FrontierSignal, ...]
    idle: bool = False
    external_calls: int = 0

    def to_receipt(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "tick_id": self.tick_id,
            "objective_reference": self.objective_reference,
            "captured_at": self.captured_at.isoformat(),
            "adapters": [adapter.to_receipt() for adapter in self.adapters],
            "signals": [signal.to_receipt() for signal in self.signals],
            "signal_count": len(self.signals),
            "idle": self.idle,
            "external_calls": self.external_calls,
        }

    def materials(self) -> list[ResearchMaterial]:
        """Convert watched signals into planner inputs."""
        return [signal.to_research_material() for signal in self.signals]


def default_source_adapters() -> tuple[SourceAdapterSpec, ...]:
    """Return the source families for v1 shadow-mode watching."""
    return (
        SourceAdapterSpec(
            key="notebooklm_coding_core",
            kind=SourceAdapterKind.NOTEBOOKLM,
            source_type=MaterialSourceType.OTHER,
            read_policy="query NotebookLM summaries only after auth/profile proof",
            write_policy="operator-approved syntheses only",
            freshness_window_hours=24,
        ),
        SourceAdapterSpec(
            key="github_frontier_repos",
            kind=SourceAdapterKind.GITHUB,
            source_type=MaterialSourceType.REPO,
            read_policy="metadata and diff summaries only",
            write_policy="no upstream writes from Lab",
            freshness_window_hours=24,
        ),
        SourceAdapterSpec(
            key="paper_release_watch",
            kind=SourceAdapterKind.PAPER_INDEX,
            source_type=MaterialSourceType.WEB,
            read_policy="paper metadata and abstract-derived fingerprints only",
            write_policy="no provider writes",
            freshness_window_hours=48,
        ),
        SourceAdapterSpec(
            key="sdk_docs_watch",
            kind=SourceAdapterKind.SDK_DOCS,
            source_type=MaterialSourceType.WEB,
            read_policy="official SDK/docs changelog summaries",
            write_policy="no provider writes",
            freshness_window_hours=24,
        ),
        SourceAdapterSpec(
            key="mcp_registry_watch",
            kind=SourceAdapterKind.MCP_REGISTRY,
            source_type=MaterialSourceType.WEB,
            read_policy="MCP server/tool metadata summaries",
            write_policy="no provider writes",
            freshness_window_hours=24,
        ),
    )


def build_shadow_watchtower_tick(
    *,
    objective: str,
    captured_at: datetime | None = None,
    adapters: tuple[SourceAdapterSpec, ...] | None = None,
) -> WatchtowerTick:
    """Build a deterministic shadow watch tick from local contracts only."""
    now = captured_at or datetime.now(tz=timezone.utc)
    active_adapters = default_source_adapters() if adapters is None else adapters
    objective_reference = (
        f"objective_fingerprint:{safe_sha256_fingerprint(objective)}; "
        f"words:{len(objective.split())}"
    )
    signals = tuple(
        _signal_for_adapter(
            adapter=adapter,
            objective=objective,
            captured_at=now,
            order=index + 1,
        )
        for index, adapter in enumerate(active_adapters[:3])
    )
    return WatchtowerTick(
        version=SOURCE_ADAPTER_CONTRACT_VERSION,
        tick_id=f"watch-{safe_sha256_fingerprint(objective, hex_chars=12)}",
        objective_reference=objective_reference,
        captured_at=now,
        adapters=active_adapters,
        signals=signals,
        idle=len(signals) == 0,
        external_calls=0,
    )


def _signal_for_adapter(
    *,
    adapter: SourceAdapterSpec,
    objective: str,
    captured_at: datetime,
    order: int,
) -> FrontierSignal:
    area = _implementation_area(adapter)
    tags = _tags_for_adapter(adapter)
    title = f"{adapter.key} candidate for {shorten_receipt_value(objective, limit=80)}"
    source_uri = _source_uri(adapter=adapter, order=order)
    novelty_score = round(min(0.95, 0.55 + order * 0.08 + len(tags) * 0.03), 2)
    return FrontierSignal(
        signal_id=f"signal-{order}-{safe_sha256_fingerprint(adapter.key + objective, 8)}",
        adapter_key=adapter.key,
        source_type=adapter.source_type,
        source_uri=source_uri,
        title=title,
        captured_at=captured_at,
        implementation_area=area,
        tags=tags,
        novelty_score=novelty_score,
        evidence_reference=(
            f"evidence_fingerprint:{safe_sha256_fingerprint(source_uri + objective)}"
        ),
    )


def _implementation_area(adapter: SourceAdapterSpec) -> str:
    if adapter.kind is SourceAdapterKind.NOTEBOOKLM:
        return "agent-engineering-synthesis"
    if adapter.kind is SourceAdapterKind.GITHUB:
        return "codebase-pattern-mining"
    if adapter.kind is SourceAdapterKind.PAPER_INDEX:
        return "research-to-evaluator"
    if adapter.kind is SourceAdapterKind.SDK_DOCS:
        return "sdk-integration-pattern"
    if adapter.kind is SourceAdapterKind.MCP_REGISTRY:
        return "tool-runtime-interop"
    return "operator-context"


def _tags_for_adapter(adapter: SourceAdapterSpec) -> tuple[str, ...]:
    tag_map: dict[SourceAdapterKind, tuple[str, ...]] = {
        SourceAdapterKind.NOTEBOOKLM: ("ai_frontier", "agent", "notebooklm"),
        SourceAdapterKind.GITHUB: ("repo", "software_frontier", "test"),
        SourceAdapterKind.PAPER_INDEX: ("research", "eval", "world_model"),
        SourceAdapterKind.SDK_DOCS: ("sdk", "api", "software_frontier"),
        SourceAdapterKind.MCP_REGISTRY: ("mcp", "tooling", "agent"),
        SourceAdapterKind.OPERATOR_NOTE: ("operator", "safety"),
    }
    return tag_map[adapter.kind]


def _source_uri(*, adapter: SourceAdapterSpec, order: int) -> str:
    if adapter.source_type is MaterialSourceType.REPO:
        return f"https://github.com/nuzantara/frontier-shadow-{order}"
    if adapter.source_type is MaterialSourceType.WEB:
        return f"https://research.example/{adapter.key}/{order}"
    return f"{adapter.kind.value}://shadow/{adapter.key}/{order}"


__all__ = [
    "SOURCE_ADAPTER_CONTRACT_VERSION",
    "FrontierSignal",
    "SourceAdapterKind",
    "SourceAdapterSpec",
    "WatchtowerTick",
    "build_shadow_watchtower_tick",
    "default_source_adapters",
]
