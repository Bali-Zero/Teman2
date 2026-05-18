#!/usr/bin/env python3
"""WR3 contract loader — reads docs/wr3/contracts/*.yaml into typed dataclasses.

Single source of truth at runtime. Used by:
  - wr3_dispatch_agent.py    (cost ceiling + allowed_tools + cascade decisions)
  - wr3_supervisor.py        (channel router via _router.yaml + handler map)
  - wr3_lint_*.py            (per-agent Symbiosis law conformance enforcement)

Contracts are LOADED ONCE at process start. Modifying YAML during a running
episode does NOT take effect — supervisor must be restarted.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(os.environ.get("WR3_REPO_ROOT", str(Path(__file__).resolve().parent.parent)))
CONTRACTS_DIR = REPO_ROOT / "docs" / "wr3" / "contracts"
PRECEDENCE_DOC = REPO_ROOT / "docs" / "wr3" / "symbiosis-precedence.md"


@dataclass(frozen=True)
class CostBlock:
    ceiling_usd: float | None
    ceiling_unit: str
    hard_halt_on_exceed: bool


@dataclass(frozen=True)
class IOBlock:
    name: str
    kind: str
    source_or_sink: str
    schema_ref: str = "free-form"
    required: bool = True


@dataclass(frozen=True)
class FailureMode:
    code: str
    action: str
    telegram_p0_on: bool = False


@dataclass(frozen=True)
class AgentContract:
    name: str
    contract_version: str
    model: str
    lifecycle_tier: str
    cost_class: str
    cost: CostBlock
    allowed_tools: tuple[str, ...]
    inputs: tuple[IOBlock, ...]
    outputs: tuple[IOBlock, ...]
    emits: tuple[str, ...]
    consumes: tuple[str, ...]
    failure_modes: tuple[FailureMode, ...]
    law_compliance: dict[str, str]

    @property
    def is_core(self) -> bool:
        return self.lifecycle_tier == "core"

    @property
    def is_gate(self) -> bool:
        return self.name in ("wr3-design-architect", "wr3-pre-render-gatekeeper")

    @property
    def is_scheduled(self) -> bool:
        return self.lifecycle_tier == "scheduled"


@dataclass(frozen=True)
class ChannelRoute:
    channel: str
    handler: str
    hot_path: bool
    description: str


@dataclass(frozen=True)
class WR3Contracts:
    schema_version: str
    router_version: str
    agents: dict[str, AgentContract]
    routes: dict[str, ChannelRoute]

    def for_agent(self, name: str) -> AgentContract:
        if name not in self.agents:
            raise KeyError(f"Unknown agent {name!r}. Known: {sorted(self.agents)}")
        return self.agents[name]

    def route_for(self, channel: str) -> ChannelRoute:
        if channel not in self.routes:
            raise KeyError(f"Unknown channel {channel!r}. Known: {sorted(self.routes)}")
        return self.routes[channel]

    @property
    def hot_path_channels(self) -> frozenset[str]:
        return frozenset(c for c, r in self.routes.items() if r.hot_path)


def _parse_io(blocks: list[dict[str, Any]], kind_key: str) -> tuple[IOBlock, ...]:
    out: list[IOBlock] = []
    for b in blocks:
        sink = b.get("sink") or b.get("source") or ""
        out.append(
            IOBlock(
                name=b["name"],
                kind=b["kind"],
                source_or_sink=sink,
                schema_ref=b.get("schema_ref", "free-form"),
                required=bool(b.get("required", True)),
            )
        )
    return tuple(out)


def _parse_agent(name: str, data: dict[str, Any]) -> AgentContract:
    cost_data = data["cost"]
    return AgentContract(
        name=data["name"],
        contract_version=data["contract_version"],
        model=data["model"],
        lifecycle_tier=data["lifecycle_tier"],
        cost_class=data["cost_class"],
        cost=CostBlock(
            ceiling_usd=cost_data["ceiling_usd"],
            ceiling_unit=cost_data["ceiling_unit"],
            hard_halt_on_exceed=bool(cost_data["hard_halt_on_exceed"]),
        ),
        allowed_tools=tuple(data["allowed_tools"]),
        inputs=_parse_io(data.get("inputs") or [], "source"),
        outputs=_parse_io(data.get("outputs") or [], "sink"),
        emits=tuple(data.get("emits") or []),
        consumes=tuple(data.get("consumes") or []),
        failure_modes=tuple(
            FailureMode(
                code=fm["code"],
                action=fm["action"],
                telegram_p0_on=bool(fm.get("telegram_p0_on", False)),
            )
            for fm in (data.get("failure_modes") or [])
        ),
        law_compliance=dict(data.get("law_compliance") or {}),
    )


def load_contracts(contracts_dir: Path = CONTRACTS_DIR) -> WR3Contracts:
    if not contracts_dir.exists():
        raise FileNotFoundError(f"Contracts dir not found: {contracts_dir}")

    schema_path = contracts_dir / "_schema.yaml"
    router_path = contracts_dir / "_router.yaml"
    if not schema_path.exists():
        raise FileNotFoundError(f"_schema.yaml missing: {schema_path}")
    if not router_path.exists():
        raise FileNotFoundError(f"_router.yaml missing: {router_path}")

    schema = yaml.safe_load(schema_path.read_text())
    router = yaml.safe_load(router_path.read_text())

    agents: dict[str, AgentContract] = {}
    for p in sorted(contracts_dir.glob("*.yaml")):
        if p.name.startswith("_"):
            continue
        data = yaml.safe_load(p.read_text())
        agents[data["name"]] = _parse_agent(p.stem, data)

    routes: dict[str, ChannelRoute] = {}
    for channel, route_data in (router.get("channels") or {}).items():
        routes[channel] = ChannelRoute(
            channel=channel,
            handler=route_data["handler"],
            hot_path=bool(route_data.get("hot_path", False)),
            description=route_data.get("description", ""),
        )

    return WR3Contracts(
        schema_version=schema.get("$id", "unknown"),
        router_version=router.get("router_version", "unknown"),
        agents=agents,
        routes=routes,
    )


if __name__ == "__main__":
    contracts = load_contracts()
    print(f"Schema: {contracts.schema_version}")
    print(f"Router: {contracts.router_version}")
    print(f"Agents: {len(contracts.agents)}")
    for name, ac in sorted(contracts.agents.items()):
        ceil = ac.cost.ceiling_unit
        print(f"  {name:30s} model={ac.model:6s} tier={ac.lifecycle_tier:10s} ceil={ceil}")
    print(f"Channels: {len(contracts.routes)}")
    for ch, route in sorted(contracts.routes.items()):
        hp = "HOT" if route.hot_path else "cold"
        print(f"  {ch:35s} → {route.handler:30s} [{hp}]")
