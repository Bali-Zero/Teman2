"""Canonical domain taxonomy for HGT routing.

# Organo: cell-core L0 → provides domain taxonomy → consumed by HGT publisher/consumer
# Produces: validated domain strings for skill tagging
# If fails: falls back to 'generic' (safe default)

Flat taxonomy by design. Semantic routing is overkill at <10 cells and 11 domains.
Extend by adding strings — no breaking change needed.
"""
from __future__ import annotations

CANONICAL_DOMAINS: frozenset[str] = frozenset({
    "visa",          # Visa processing, immigration, KITAS/KITAP
    "tax",           # Tax calculation, PPh21, BPJS, THR
    "kbli",          # Business classification codes, KBLI navigation
    "property",      # Real estate, zoning, investment areas
    "legal",         # Legal documents, akta, contracts, sertifikat
    "crm",           # Client management, practices, compliance
    "news",          # Intelligence, regulations, scraping, monitoring
    "architecture",  # System design, code patterns, infrastructure
    "rag",           # RAG pipeline, search, embedding, reranking
    "graph",         # Knowledge graph, Neo4j, subgraphs, entity resolution
    "generic",       # Cross-domain — broadcast to all consumers
})


def validate_domain(domain: str) -> str:
    """Validate and normalize domain. Returns 'generic' for unknown.

    >>> validate_domain("VISA")
    'visa'
    >>> validate_domain("unknown_thing")
    'generic'
    >>> validate_domain("")
    'generic'
    """
    if not domain:
        return "generic"
    d = domain.lower().strip()
    return d if d in CANONICAL_DOMAINS else "generic"
