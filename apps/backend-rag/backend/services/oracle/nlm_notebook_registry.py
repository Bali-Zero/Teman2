"""NLM Notebook Registry — static mapping of domains to NotebookLM notebook IDs.

Each domain has:
- notebook_id: operational notebook (NB-Xb) — T2+T3 verified guides
- primary_notebook_id: oracle notebook (NB-Xa) — T0+T1 law only (None until created)
- keywords: used by resolve_notebook() to route queries
"""
from __future__ import annotations

NLM_NOTEBOOKS: dict[str, dict] = {
    "immigration": {
        "notebook_id": "cff93ab0-813a-42f2-a8de-36987e724271",   # NB-2b operational
        "primary_notebook_id": None,   # NB-2a not yet created
        "label": "Immigration & Visa",
        "keywords": {
            "visa", "kitas", "kitap", "tka", "immigration", "imigrasi",
            "work permit", "stay permit", "foreigner", "expat",
        },
    },
    "company": {
        "notebook_id": "2e84b9b9-3b99-4bc5-8ec5-351a43c52df4",
        "primary_notebook_id": None,
        "label": "Company & Licensing",
        "keywords": {
            "company", "kbli", "pma", "oss", "licensing", "nib",
            "investment", "business", "pt ", "perseroan",
        },
    },
    "tax": {
        "notebook_id": "837b620b-2aca-43ab-812e-97ca92bdad1d",
        "primary_notebook_id": None,
        "label": "Tax & Compliance",
        "keywords": {
            "tax", "compliance", "lkpm", "npwp", "pph", "ppn",
            "coretax", "bpjs", "fiscal", "pajak",
        },
    },
    "property": {
        "notebook_id": "568ec624-ceb8-47d1-a2a2-5b2f793ea7ed",
        "primary_notebook_id": None,
        "label": "Property & Zoning",
        "keywords": {
            "property", "zoning", "land", "hgb", "hak pakai",
            "building", "villa", "real estate", "leasehold",
        },
    },
    "operations": {
        "notebook_id": "3e1baa5f-680f-4499-9430-23a901576bcc",
        "primary_notebook_id": None,
        "label": "Operations",
        "keywords": {"sop", "team", "pricing", "crm", "workflow", "competitor"},
    },
    "editorial": {
        "notebook_id": "dd464d8f-6b8e-4543-8647-f62c498589b1",
        "primary_notebook_id": None,
        "label": "Editorial & Market",
        "keywords": {
            "seo", "content", "market", "intel", "trends", "news", "article", "editorial",
        },
    },
    "lifestyle": {
        "notebook_id": "1143b525-dd3f-40d7-a34d-2e9263b44460",
        "primary_notebook_id": None,
        "label": "Expat Life",
        "keywords": {
            "lifestyle", "expat", "healthcare", "cost of living",
            "culture", "digital nomad", "education", "school",
        },
    },
}

# Keywords that indicate the user wants T0/T1 primary law sources
_PRIMARY_LAW_KEYWORDS = frozenset({"pasal", "uu ", "pp ", "peraturan", "permenkumham", "permen", "undang"})


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
