"""Sefirotic Router — curated multi-NB cascades for complex queries.

Sacred root (comment only): in Kabbalah, 10 sefirot form the Tree of Life;
a divine intention emanates from Keter and reaches manifestation through
ordered sefirot. A client query is analogous: "open a PT PMA with team +
property" is a single intention that must cascade through company/visa/
tax/operations/team NBs in a coherent order. A keyword-scored fan-out
cannot capture this ordering. A curated YAML can.

Design rules:

    1. The YAML (sefirot_paths.yaml) is human-curated. Never auto-generated
       via LLM — risk of hallucinated legal cascades.
    2. Flag-gated: reads ``SEFIROT_ROUTING`` env var at call time (default off).
       When off, the module still loads + exposes ``resolve_path`` for test,
       but ``resolve_with_fallback`` returns ``None`` so callers cascade to
       the pre-existing keyword-based resolver (nlm_orchestrator base map).
    3. Shadow mode: when off, we STILL log the match that *would* have fired
       so divergence between base routing and sefirot routing is visible
       before flipping the flag.
    4. First-match wins in trigger order (YAML order is semantic). When
       retiring a path, mark ``deprecated: true`` to keep existing callers
       consistent.

Use from nlm_orchestrator:

    from apps.backend-rag.backend.services.oracle.sefirot_router import (
        resolve_with_fallback,
    )

    sef_match = resolve_with_fallback(query)
    if sef_match is not None:
        notebooks = sef_match.notebook_ids_in_order()
    else:
        notebooks = existing_keyword_resolver(query)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────

_DIR = Path(__file__).parent
DEFAULT_YAML = _DIR / "sefirot_paths.yaml"

# Module-level cache — invalidated by file mtime change.
_cache: dict[str, Any] = {}


# ── Data model ───────────────────────────────────────────────────────────────


@dataclass
class SefirotStep:
    """A single NB visited on a sefirot path."""

    nb_id: str  # NotebookLM UUID
    key: str    # short key (nb2, nb3, ...) for logs + metrics
    weight: float


@dataclass
class SefirotPath:
    """A curated cascade of NB queries for a specific multi-domain intent."""

    name: str
    description: str
    triggers: list[str]
    sequence: list[SefirotStep]
    aggregator: str
    deprecated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def notebook_ids_in_order(self) -> list[str]:
        """Return NB UUIDs ordered by weight descending."""
        ordered = sorted(self.sequence, key=lambda s: s.weight, reverse=True)
        return [s.nb_id for s in ordered]

    def matched_keys_in_order(self) -> list[str]:
        ordered = sorted(self.sequence, key=lambda s: s.weight, reverse=True)
        return [s.key for s in ordered]


# ── Flag ─────────────────────────────────────────────────────────────────────


def sefirot_routing_enabled() -> bool:
    """Read SEFIROT_ROUTING env var at call time (tests + dev restarts)."""
    raw = os.environ.get("SEFIROT_ROUTING", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


# ── YAML loader ──────────────────────────────────────────────────────────────


def _load_yaml_dict(path: Path) -> Optional[dict[str, Any]]:
    """Read YAML or return None if the file is missing / malformed."""
    if not path.exists():
        return None
    try:
        import yaml  # noqa: PLC0415

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            logger.warning("sefirot: YAML root is not a dict (%s)", path)
            return None
        return data
    except Exception as exc:  # pragma: no cover — defensive, never block caller
        logger.warning("sefirot: failed to read %s — %s", path, exc)
        return None


def _parse_paths(raw: dict[str, Any]) -> list[SefirotPath]:
    """Parse a parsed-YAML dict into typed SefirotPath list."""
    raw_paths = raw.get("paths")
    if not isinstance(raw_paths, list):
        return []

    result: list[SefirotPath] = []
    for entry in raw_paths:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not name:
            continue

        triggers = entry.get("triggers") or []
        if not isinstance(triggers, list):
            triggers = []
        triggers = [str(t).lower() for t in triggers if t]

        sequence_raw = entry.get("sequence") or []
        if not isinstance(sequence_raw, list):
            sequence_raw = []
        steps: list[SefirotStep] = []
        for s in sequence_raw:
            if not isinstance(s, dict):
                continue
            nb = s.get("nb")
            key = s.get("key")
            weight = s.get("weight")
            if not (nb and key and isinstance(weight, (int, float))):
                continue
            steps.append(SefirotStep(nb_id=str(nb), key=str(key), weight=float(weight)))

        if not triggers or not steps:
            # skip incomplete entries but keep YAML tolerant of drafts
            continue

        result.append(
            SefirotPath(
                name=str(name),
                description=str(entry.get("description", "")),
                triggers=triggers,
                sequence=steps,
                aggregator=str(entry.get("aggregator", "synthesis_ordered")),
                deprecated=bool(entry.get("deprecated", False)),
                metadata={k: v for k, v in entry.items() if k not in {"name", "description", "triggers", "sequence", "aggregator", "deprecated"}},
            )
        )
    return result


def load_paths(
    path: Optional[Path] = None,
    force_reload: bool = False,
) -> list[SefirotPath]:
    """Load sefirot paths. Returns [] on failure (silent)."""
    target = path or DEFAULT_YAML
    if not target.exists():
        return []
    try:
        mtime = target.stat().st_mtime
    except OSError:
        return []

    cache_key = str(target)
    cached = _cache.get(cache_key)
    if (
        not force_reload
        and cached is not None
        and cached.get("mtime") == mtime
    ):
        return cached.get("paths", [])

    raw = _load_yaml_dict(target)
    if raw is None:
        return []
    paths = _parse_paths(raw)
    _cache[cache_key] = {"mtime": mtime, "paths": paths}
    return paths


# ── Matching ─────────────────────────────────────────────────────────────────


def match_triggers(query: str, path: SefirotPath) -> list[str]:
    """Return list of triggers that matched inside the query (case-insensitive)."""
    if not query:
        return []
    q_lower = query.lower()
    return [t for t in path.triggers if t in q_lower]


def resolve_path(
    query: str,
    paths: Optional[list[SefirotPath]] = None,
) -> Optional[SefirotPath]:
    """Return the FIRST (in YAML order) non-deprecated path that matches.

    Does NOT consult the flag — exposes pure matching so callers + tests can
    reason about shadow-mode divergence.
    """
    if not query:
        return None
    if paths is None:
        paths = load_paths()
    if not paths:
        return None
    for path in paths:
        if path.deprecated:
            continue
        matched = match_triggers(query, path)
        if matched:
            logger.debug(
                "sefirot match: path=%s matched_triggers=%s",
                path.name,
                matched,
            )
            return path
    return None


def resolve_with_fallback(
    query: str,
    paths: Optional[list[SefirotPath]] = None,
) -> Optional[SefirotPath]:
    """Like resolve_path, but gated by the SEFIROT_ROUTING flag.

    When flag is OFF, we still match + emit a shadow log so operators can
    see where sefirot would diverge from base routing, but we return None so
    the caller falls back to its pre-existing resolver.

    When flag is ON, return the matched SefirotPath (or None on no match).
    """
    path = resolve_path(query, paths=paths)
    if path is None:
        return None

    enabled = sefirot_routing_enabled()
    if not enabled:
        # Shadow-mode observability.
        logger.info(
            "sefirot shadow: path=%s would route to %s (set SEFIROT_ROUTING=1 to activate)",
            path.name,
            path.matched_keys_in_order(),
        )
        return None

    return path


# ── Diagnostics ──────────────────────────────────────────────────────────────


def summarize_paths(paths: Optional[list[SefirotPath]] = None) -> dict[str, Any]:
    """Return stat summary for CLI / tests."""
    if paths is None:
        paths = load_paths()
    total = len(paths)
    deprecated = sum(1 for p in paths if p.deprecated)
    nb_in_use: set[str] = set()
    triggers_total = 0
    for p in paths:
        for s in p.sequence:
            nb_in_use.add(s.key)
        triggers_total += len(p.triggers)
    return {
        "total_paths": total,
        "deprecated": deprecated,
        "active_paths": total - deprecated,
        "distinct_nbs_in_use": sorted(nb_in_use),
        "triggers_total": triggers_total,
    }
