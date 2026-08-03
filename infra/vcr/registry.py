"""infra/vcr/registry.py — the expected-claim registry loader (R5).

The registry is the authority on "what does this pilot track": a query for a
(seat, host, auth_context) triple NOT in it is a caller error, not a MISSING
claim (MISSING is reserved for a registered claim that has never actually been
observed — see accessor.py). Loaded from expected_claims.yaml, in-repo,
code-reviewed, versioned — never hand-edited at runtime.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parent / "expected_claims.yaml"


@dataclasses.dataclass(frozen=True)
class ExpectedClaim:
    seat: str
    host: str
    auth_context: str
    ttl_s: int
    latency_budget_ms: int
    certified_hash: Optional[str]


def load_registry(path: Optional[Path] = None) -> list[ExpectedClaim]:
    p = path or DEFAULT_REGISTRY_PATH
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    claims = data.get("claims", [])
    if not isinstance(claims, list):
        raise ValueError(f"{p}: 'claims' must be a list, got {type(claims).__name__}")
    out = []
    for i, c in enumerate(claims):
        try:
            out.append(
                ExpectedClaim(
                    seat=c["seat"],
                    host=c["host"],
                    auth_context=c["auth_context"],
                    ttl_s=int(c["ttl_s"]),
                    latency_budget_ms=int(c["latency_budget_ms"]),
                    certified_hash=c.get("certified_hash") or None,
                )
            )
        except KeyError as e:
            raise ValueError(f"{p}: claims[{i}] missing required key {e}") from e
    return out


def lookup(registry: list[ExpectedClaim], seat: str, host: str, auth_context: str) -> Optional[ExpectedClaim]:
    for c in registry:
        if c.seat == seat and c.host == host and c.auth_context == auth_context:
            return c
    return None
