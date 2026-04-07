"""Multi-Hop Reasoning Engine — GraphRAG 2.0

Decomposes complex cross-domain queries into sub-queries, retrieves per hop,
and synthesizes a merged context for the ReAct loop.

Triggers only for CROSS_DOMAIN queries (2+ domain keyword sets detected).

Example:
    Query: "I want to open a restaurant and hire a foreign chef"
    → Hop 1: "open a restaurant" (company domain: PT PMA + KBLI 56101)
    → Hop 2: "hire a foreign chef" (visa domain: KITAS + RPTKA)
    → Merged context with bridge entities (both hops mention PT PMA)

Usage:
    engine = MultiHopEngine()
    plan = engine.decompose(query, query_plan)
    merged = await engine.execute_hops(plan, kg_retrieval, db_pool)
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Conjunction patterns for query splitting (EN, IT, ID)
_CONJUNCTION_PATTERNS = [
    r"\band\b",
    r"\be\b",
    r"\bdan\b",
    r"\bserta\b",
    r"\balso\b",
    r"\binoltre\b",
    r"\bplus\b",
    # Semicolons and commas as separators
    r"\s*;\s*",
    r"\s*,\s+(?:and|e|dan|also|inoltre)\s+",
]

_CONJUNCTION_RE = re.compile("|".join(_CONJUNCTION_PATTERNS), re.IGNORECASE)

# Domain keyword sets (shared with query_planner.py)
_DOMAIN_KEYWORDS: dict[str, frozenset[str]] = {
    "visa": frozenset({
        "kitas", "kitap", "vitas", "visa", "work permit", "rptka", "imta",
        "immigration", "imigrasi", "izin tinggal", "stay permit", "tka",
    }),
    "tax": frozenset({
        "tax", "pph", "ppn", "npwp", "pajak", "tasse", "fiscal", "vat",
        "spt", "withholding", "pbb",
    }),
    "property": frozenset({
        "property", "villa", "hak pakai", "hgb", "hak milik", "rental",
        "real estate", "land", "tanah", "zoning", "bphtb",
    }),
    "company": frozenset({
        "pt pma", "pt lokal", "cv", "company", "azienda", "firma",
        "nib", "oss", "izin usaha", "business", "restaurant", "restoran",
    }),
    "kbli": frozenset({
        "kbli", "business classification", "kode usaha", "klasifikasi",
    }),
}


@dataclass
class SubQuery:
    """A single hop in a multi-hop plan."""

    text: str
    domain: str = "general"
    entities: list[str] = field(default_factory=list)
    collections: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"SubQuery(domain={self.domain}, text={self.text[:50]})"


@dataclass
class MultiHopPlan:
    """Plan for multi-hop query processing."""

    original_query: str
    sub_queries: list[SubQuery] = field(default_factory=list)
    bridge_entities: list[str] = field(default_factory=list)

    @property
    def hop_count(self) -> int:
        return len(self.sub_queries)

    @property
    def domains(self) -> list[str]:
        return [sq.domain for sq in self.sub_queries]


@dataclass
class HopResult:
    """Result from executing a single hop."""

    sub_query: SubQuery
    kg_entities: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    source_chunks: list[str] = field(default_factory=list)
    graph_summary: str = ""


@dataclass
class MergedHopContext:
    """Merged context from all hops."""

    hop_results: list[HopResult] = field(default_factory=list)
    bridge_entities: list[dict[str, Any]] = field(default_factory=list)
    merged_summary: str = ""
    total_entities: int = 0
    total_relationships: int = 0

    def to_prompt_context(self) -> str:
        """Format as system prompt context with hop annotations."""
        parts: list[str] = []

        for i, hop in enumerate(self.hop_results, 1):
            domain_label = hop.sub_query.domain.upper()
            parts.append(f"[Hop {i}: {domain_label}]")
            if hop.graph_summary:
                parts.append(hop.graph_summary)
            if hop.kg_entities:
                ent_names = [e.get("name", e.get("entity_id", "?")) for e in hop.kg_entities[:5]]
                parts.append(f"Key entities: {', '.join(ent_names)}")
            parts.append("")

        if self.bridge_entities:
            bridge_names = [e.get("name", "?") for e in self.bridge_entities[:5]]
            parts.append(f"[Bridge entities across hops: {', '.join(bridge_names)}]")

        return "\n".join(parts)


def _classify_domain(text: str) -> str:
    """Classify text fragment into a domain using keyword matching."""
    text_lower = text.lower()
    best_domain = "general"
    best_count = 0

    for domain, keywords in _DOMAIN_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > best_count:
            best_count = count
            best_domain = domain

    return best_domain


def _get_collections_for_domain(domain: str) -> list[str]:
    """Map domain to Qdrant collections."""
    mapping: dict[str, list[str]] = {
        "visa": ["visa_oracle", "legal_unified_hybrid_hybrid"],
        "tax": ["nuzantara_general_hybrid", "legal_unified_hybrid_hybrid"],
        "property": ["nuzantara_general_hybrid", "legal_unified_hybrid_hybrid"],
        "company": ["legal_unified_hybrid_hybrid", "kbli_2025_final_hybrid"],
        "kbli": ["kbli_2025_final_hybrid"],
        "general": ["legal_unified_hybrid_hybrid", "nuzantara_general_hybrid"],
    }
    return mapping.get(domain, mapping["general"])


class MultiHopEngine:
    """Heuristic query decomposition and multi-hop execution."""

    def decompose(self, query: str) -> MultiHopPlan:
        """Decompose a query into sub-queries based on conjunctions and domain keywords.

        Args:
            query: The full user query

        Returns:
            MultiHopPlan with sub-queries, or single-hop plan if not decomposable
        """
        # Split on conjunctions
        fragments = _CONJUNCTION_RE.split(query)
        fragments = [f.strip() for f in fragments if f and f.strip() and len(f.strip()) > 5]

        if len(fragments) <= 1:
            # Not decomposable — single hop
            domain = _classify_domain(query)
            return MultiHopPlan(
                original_query=query,
                sub_queries=[
                    SubQuery(
                        text=query,
                        domain=domain,
                        collections=_get_collections_for_domain(domain),
                    ),
                ],
            )

        # Classify each fragment
        sub_queries: list[SubQuery] = []
        for frag in fragments:
            domain = _classify_domain(frag)
            sub_queries.append(SubQuery(
                text=frag,
                domain=domain,
                collections=_get_collections_for_domain(domain),
            ))

        # Deduplicate: merge fragments with same domain
        merged: dict[str, SubQuery] = {}
        for sq in sub_queries:
            if sq.domain in merged:
                merged[sq.domain].text += " " + sq.text
            else:
                merged[sq.domain] = sq

        plan = MultiHopPlan(
            original_query=query,
            sub_queries=list(merged.values()),
        )

        logger.info(
            "[MultiHop] Decomposed into %d hops: %s",
            plan.hop_count,
            plan.domains,
        )
        return plan

    async def execute_hops(
        self,
        plan: MultiHopPlan,
        kg_retrieval: Any,
        db_pool: Any,
    ) -> MergedHopContext:
        """Execute each hop in parallel, then merge contexts.

        Args:
            plan: MultiHopPlan from decompose()
            kg_retrieval: KGEnhancedRetrieval instance
            db_pool: asyncpg pool for KG queries

        Returns:
            MergedHopContext with all hop results and bridge entities
        """
        if plan.hop_count <= 1:
            # Single hop — just execute directly
            sq = plan.sub_queries[0]
            hop_result = await self._execute_single_hop(sq, kg_retrieval, db_pool)
            return MergedHopContext(
                hop_results=[hop_result],
                total_entities=len(hop_result.kg_entities),
                total_relationships=len(hop_result.relationships),
            )

        # Execute hops in parallel
        tasks = [
            self._execute_single_hop(sq, kg_retrieval, db_pool)
            for sq in plan.sub_queries
        ]
        hop_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_results: list[HopResult] = []
        for r in hop_results:
            if isinstance(r, Exception):
                logger.warning("[MultiHop] Hop failed: %s", r)
            else:
                valid_results.append(r)

        # Detect bridge entities (appear in 2+ hops)
        entity_counts: dict[str, int] = {}
        entity_details: dict[str, dict[str, Any]] = {}
        for hop in valid_results:
            seen_in_hop: set[str] = set()
            for ent in hop.kg_entities:
                eid = ent.get("entity_id", "")
                if eid and eid not in seen_in_hop:
                    seen_in_hop.add(eid)
                    entity_counts[eid] = entity_counts.get(eid, 0) + 1
                    entity_details[eid] = ent

        bridge_entities = [
            entity_details[eid]
            for eid, count in entity_counts.items()
            if count >= 2
        ]

        total_ents = sum(len(h.kg_entities) for h in valid_results)
        total_rels = sum(len(h.relationships) for h in valid_results)

        merged = MergedHopContext(
            hop_results=valid_results,
            bridge_entities=bridge_entities,
            total_entities=total_ents,
            total_relationships=total_rels,
        )

        logger.info(
            "[MultiHop] Merged %d hops: %d entities, %d relationships, %d bridge entities",
            len(valid_results),
            total_ents,
            total_rels,
            len(bridge_entities),
        )
        return merged

    async def _execute_single_hop(
        self,
        sub_query: SubQuery,
        kg_retrieval: Any,
        db_pool: Any,
    ) -> HopResult:
        """Execute a single hop: entity extraction → KG lookup → context assembly."""
        try:
            # Use KGEnhancedRetrieval for entity extraction and graph traversal
            kg_context = await kg_retrieval.get_kg_context(
                query=sub_query.text,
                db_pool=db_pool,
            )

            return HopResult(
                sub_query=sub_query,
                kg_entities=kg_context.get("entities_found", []),
                relationships=kg_context.get("relationships", []),
                source_chunks=kg_context.get("source_chunk_ids", []),
                graph_summary=kg_context.get("graph_summary", ""),
            )
        except Exception as e:
            logger.warning("[MultiHop] Hop failed for %s: %s", sub_query.domain, e)
            return HopResult(sub_query=sub_query)
