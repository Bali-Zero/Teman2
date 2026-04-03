"""NLM Notebook Registry — static mapping of domains to NotebookLM notebook IDs.

Each domain has:
- notebook_id: operational notebook (NB-Xb) — T2+T3 verified guides
- primary_notebook_id: oracle notebook (NB-Xa) — T0+T1 law only (None until created)
- keywords: used by resolve_notebook() to route queries
"""

from __future__ import annotations

NLM_NOTEBOOKS: dict[str, dict] = {
    "immigration": {
        "notebook_id": "cff93ab0-813a-42f2-a8de-36987e724271",  # NB-2b operational
        "primary_notebook_id": None,  # NB-2a not yet created
        "label": "Immigration & Visa",
        "keywords": {
            "visa",
            "kitas",
            "kitap",
            "tka",
            "immigration",
            "imigrasi",
            "work permit",
            "stay permit",
            "foreigner",
            "expat",
        },
    },
    "company": {
        "notebook_id": "933509f9-1561-403d-bd44-4a7a67a36df2",  # NB-3
        "primary_notebook_id": None,
        "label": "Company & Licensing",
        "keywords": {
            "company",
            "kbli",
            "pma",
            "oss",
            "licensing",
            "nib",
            "investment",
            "business",
            "pt ",
            "perseroan",
        },
    },
    "tax": {
        "notebook_id": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",  # NB-4
        "primary_notebook_id": None,
        "label": "Tax & Compliance",
        "keywords": {
            "tax",
            "compliance",
            "lkpm",
            "npwp",
            "pph",
            "ppn",
            "coretax",
            "bpjs",
            "fiscal",
            "pajak",
        },
    },
    "property": {
        "notebook_id": "d9438180-5e63-4e2a-a473-6061101f6a8d",  # NB-5
        "primary_notebook_id": None,
        "label": "Property & Zoning",
        "keywords": {
            "property",
            "zoning",
            "land",
            "hgb",
            "hak pakai",
            "building",
            "villa",
            "real estate",
            "leasehold",
        },
    },
    "operations": {
        "notebook_id": "85207af3-352f-4554-8d2a-18f42cc541ba",  # NB-6
        "primary_notebook_id": None,
        "label": "Operations",
        "keywords": {"sop", "team", "pricing", "crm", "workflow", "competitor"},
    },
    "editorial": {
        "notebook_id": "f51ab8a0-50d0-49f1-a64f-ebc131fed7b8",  # NB-7
        "primary_notebook_id": None,
        "label": "Editorial & Market",
        "keywords": {
            "seo",
            "content",
            "market",
            "intel",
            "trends",
            "news",
            "article",
            "editorial",
        },
    },
    "lifestyle": {
        "notebook_id": "4fd8cd0f-93f1-4e43-9c9e-86c0d581852c",  # NB-8
        "primary_notebook_id": None,
        "label": "Expat Life",
        "keywords": {
            "lifestyle",
            "expat",
            "healthcare",
            "cost of living",
            "culture",
            "digital nomad",
            "education",
            "school",
        },
    },
}

# Keywords that indicate the user wants T0/T1 primary law sources
_PRIMARY_LAW_KEYWORDS = frozenset(
    {"pasal", "uu ", "pp ", "peraturan", "permenkumham", "permen", "undang"},
)


def resolve_multi_notebook(
    query: str,
    threshold: int = 1,
    max_notebooks: int = 4,
) -> list[dict[str, object]]:
    """Resolve a query to multiple matching notebooks (ARCH-4 cross-notebook).

    Returns ordered list (by match score) of matching domains.
    Returns empty list if fewer than 2 domains match.

    Args:
        query: Free-text user query.
        threshold: Minimum keyword hits to include a domain.
        max_notebooks: Maximum notebooks to include in fan-out.

    Returns:
        List of dicts with keys ``domain``, ``notebook_id``, ``label``, ``score``.
        Empty list if < 2 domains match (single-domain query).
    """
    if not query:
        return []

    query_lower = query.lower()
    scored: list[tuple[int, str]] = []

    for domain, data in NLM_NOTEBOOKS.items():
        score = sum(1 for kw in data["keywords"] if kw in query_lower)
        if score >= threshold:
            scored.append((score, domain))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_notebooks]

    if len(top) < 2:
        return []  # Not a multi-domain query

    return [
        {
            "domain": domain,
            "notebook_id": NLM_NOTEBOOKS[domain]["notebook_id"],
            "label": NLM_NOTEBOOKS[domain]["label"],
            "score": score,
        }
        for score, domain in top
    ]


def resolve_notebook(query: str) -> dict[str, object] | None:
    """Resolve a user query to the best-matching NLM notebook.

    When a primary notebook exists for the domain, returns it for
    regulation-heavy queries (pasal, uu, pp, permenkumham, etc.).
    Otherwise returns the operational notebook.

    Args:
        query: Free-text user query.

    Returns:
        A dict with keys ``domain``, ``notebook_id``, ``label``, ``keywords``
        for the best match, or ``None`` if nothing matches.
    """
    if not query:
        return None

    query_lower = query.lower()
    wants_primary = any(kw in query_lower for kw in _PRIMARY_LAW_KEYWORDS)

    best_domain: str | None = None
    best_score: int = 0

    for domain, data in NLM_NOTEBOOKS.items():
        score = sum(1 for kw in data["keywords"] if kw in query_lower)
        if score > best_score:
            best_score = score
            best_domain = domain

    if best_domain is None:
        return None

    data = NLM_NOTEBOOKS[best_domain]
    primary = data.get("primary_notebook_id")
    active_id = primary if (wants_primary and primary) else data["notebook_id"]

    return {
        "domain": best_domain,
        "notebook_id": active_id,
        "primary_notebook_id": data.get("primary_notebook_id"),
        "label": data["label"],
        "keywords": frozenset(data["keywords"]),
    }
